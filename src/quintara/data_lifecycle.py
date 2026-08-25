"""Versioned local data lifecycle and BaoStock update adapter.

The lifecycle is deliberately boring: every import is written to a staging
directory, hashed, fsynced, and published through one small JSON pointer.  A
failed download therefore leaves the active generation untouched.
"""
from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Callable, Iterable
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, cast

import pandas as pd

from .core import AppPaths, content_hash, file_hash, new_id, now_utc
from .csv_validation import REQUIRED_UNITS, csv_to_market
from .platform import atomic_json, recover_staging
from .registry import Registry

LOG = logging.getLogger(__name__)


def _freshness_warning() -> str | None:
    try:
        from zoneinfo import ZoneInfo

        current = datetime.now(ZoneInfo("Asia/Shanghai"))
        if current.weekday() < 5 and current.time() < time(18, 0):
            return "交易日18:00前数据可能尚未完整发布；建议稍后手动重试。"
    except Exception:
        return None
    return None


class DataError(RuntimeError):
    """A user-actionable data lifecycle error."""


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")


def _normalise_listing(listing: pd.DataFrame) -> pd.DataFrame:
    frame = listing.copy()
    aliases = {"code": "stock_id", "ipoDate": "ipo_date", "outDate": "out_date"}
    frame = frame.rename(columns=aliases)
    required = {"stock_id", "ipo_date", "out_date"}
    if not required.issubset(frame.columns):
        raise DataError(f"listing fields missing: {sorted(required - set(frame.columns))}")
    keep = ["stock_id", "ipo_date", "out_date"] + [
        column
        for column in (
            "name",
            "stock_name",
            "code_name",
            "status",
            "is_st",
            "is_suspended",
            "trade_status",
            "exchange",
        )
        if column in frame.columns
    ]
    frame = frame[keep].copy()
    frame["stock_id"] = frame["stock_id"].astype(str).str.extract(r"(\d{6})")[0]
    frame["ipo_date"] = pd.to_datetime(frame["ipo_date"], errors="coerce").dt.normalize()
    frame["out_date"] = pd.to_datetime(frame["out_date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["stock_id", "ipo_date"]).drop_duplicates("stock_id")
    return frame.sort_values("stock_id").reset_index(drop=True)


def _normalise_membership(membership: pd.DataFrame) -> pd.DataFrame:
    frame = membership.copy()
    if "code" in frame.columns and "stock_id" not in frame.columns:
        frame = frame.rename(columns={"code": "stock_id"})
    if "index_code" not in frame.columns:
        frame["index_code"] = "CSI300"
    if "start_date" not in frame.columns:
        frame["start_date"] = frame.get("date", pd.Timestamp("2000-01-01"))
    if "end_date" not in frame.columns:
        frame["end_date"] = pd.NaT
    required = {"stock_id", "index_code", "start_date", "end_date"}
    if not required.issubset(frame.columns):
        raise DataError(f"membership fields missing: {sorted(required - set(frame.columns))}")
    frame = frame[["stock_id", "index_code", "start_date", "end_date"]].copy()
    frame["stock_id"] = frame["stock_id"].astype(str).str.extract(r"(\d{6})")[0]
    frame["start_date"] = pd.to_datetime(frame["start_date"], errors="coerce").dt.normalize()
    frame["end_date"] = pd.to_datetime(frame["end_date"], errors="coerce").dt.normalize()
    if frame[["stock_id", "start_date"]].isna().any().any():
        raise DataError("membership has invalid stock_id or start_date")
    if (frame["end_date"].notna() & (frame["end_date"] < frame["start_date"])).any():
        raise DataError("membership end_date precedes start_date")
    for stock_id, group in frame.sort_values(["stock_id", "start_date"]).groupby("stock_id", sort=True):
        previous_end: pd.Timestamp | None = None
        for row in group.itertuples(index=False):
            if previous_end is not None and (pd.isna(previous_end) or row.start_date <= previous_end):
                raise DataError(f"overlapping membership intervals: {stock_id}")
            previous_end = row.end_date
    return frame.sort_values(["start_date", "stock_id"]).reset_index(drop=True)


class DataManager:
    """Create, validate, publish, and read immutable data generations."""

    def __init__(self, paths: AppPaths, registry: Registry | None = None, fault_hook: Callable[[str], None] | None = None) -> None:
        self.paths = paths
        self.paths.ensure()
        self.registry = registry
        self.fault_hook = fault_hook

    def _fault(self, stage: str) -> None:
        if self.fault_hook is not None:
            self.fault_hook(stage)

    def active_manifest(self) -> dict[str, Any] | None:
        if not self.paths.active_data.exists():
            return None
        try:
            pointer = json.loads(self.paths.active_data.read_text(encoding="utf-8"))
            manifest_path = self.paths.data_generations / pointer["generation"] / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            expected = pointer.get("manifest_hash")
            if expected and expected != content_hash(manifest):
                raise DataError("DATA-HASH-MISMATCH: active manifest hash does not match its pointer")
            generation_root = manifest_path.parent
            for name, details in manifest.get("files", {}).items():
                path = generation_root / name
                if not path.exists() or file_hash(path) != details.get("sha256"):
                    raise DataError(f"DATA-HASH-MISMATCH: active data file hash mismatch: {name}")
            return manifest
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            raise DataError(f"active data pointer is invalid: {exc}") from exc

    def active_bundle(self) -> dict[str, pd.DataFrame | dict[str, Any]]:
        manifest = self.active_manifest()
        if manifest is None:
            raise DataError("no active data generation; run `quintara data update` or import a CSV")
        root = self.paths.data_generations / manifest["generation"]
        try:
            return {
                "market": pd.read_csv(
                    root / "market.csv", parse_dates=["日期"], dtype={"股票代码": str}
                ),
                "membership": pd.read_csv(
                    root / "membership.csv",
                    parse_dates=["start_date", "end_date"],
                    dtype={"stock_id": str},
                ),
                "listing": pd.read_csv(
                    root / "listing.csv",
                    parse_dates=["ipo_date", "out_date"],
                    dtype={"stock_id": str},
                ),
                "extra_features": (
                    pd.read_csv(
                        root / "extra_features.csv",
                        parse_dates=["日期"],
                        dtype={"股票代码": str},
                    )
                    if (root / "extra_features.csv").exists()
                    else pd.DataFrame()
                ),
                "manifest": manifest,
            }
        except (OSError, pd.errors.ParserError, ValueError) as exc:
            raise DataError(f"active data generation cannot be read: {exc}") from exc

    def publish(
        self,
        market: pd.DataFrame,
        membership: pd.DataFrame,
        listing: pd.DataFrame,
        *,
        source: str,
        extra_features: pd.DataFrame | None = None,
        source_file: str | Path | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Publish one fully self-contained generation and update the pointer."""
        parent_manifest = self.active_manifest()
        market = market.copy()
        membership = _normalise_membership(membership)
        listing = _normalise_listing(listing)
        required_market = {"股票代码", "日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌额", "换手率", "涨跌幅"}
        missing = required_market - set(market.columns)
        if missing:
            raise DataError(f"market fields missing: {sorted(missing)}")
        market["股票代码"] = market["股票代码"].astype(str).str.extract(r"(\d{6})")[0]
        market["日期"] = pd.to_datetime(market["日期"], errors="raise").dt.normalize()
        if market[["股票代码", "日期"]].isna().any().any() or market.duplicated(["股票代码", "日期"]).any():
            raise DataError("market has invalid or duplicate stock/date keys")
        market = market.sort_values(["日期", "股票代码"]).reset_index(drop=True)
        if extra_features is not None:
            extra_features = extra_features.copy()
            if "code" in extra_features.columns and "股票代码" not in extra_features.columns:
                extra_features = extra_features.rename(columns={"code": "股票代码"})
            if "date" in extra_features.columns and "日期" not in extra_features.columns:
                extra_features = extra_features.rename(columns={"date": "日期"})
            if not {"股票代码", "日期"}.issubset(extra_features.columns):
                raise DataError("extra features require stock/date keys")
            extra_features["股票代码"] = extra_features["股票代码"].astype(str).str.extract(r"(\d{6})")[0]
            extra_features["日期"] = pd.to_datetime(extra_features["日期"], errors="raise").dt.normalize()
            if extra_features.duplicated(["股票代码", "日期"]).any():
                raise DataError("extra features contain duplicate stock/date keys")
            join_columns = [column for column in extra_features.columns if column not in {"股票代码", "日期"}]
            if join_columns:
                market = market.merge(extra_features, on=["股票代码", "日期"], how="left", sort=False, validate="one_to_one")
        staging = self.paths.data_staging / new_id("generation")
        staging.mkdir(parents=True, exist_ok=False)
        try:
            _write_csv(market, staging / "market.csv")
            _write_csv(membership, staging / "membership.csv")
            _write_csv(listing, staging / "listing.csv")
            files = {name: {"sha256": file_hash(staging / name), "bytes": (staging / name).stat().st_size} for name in ("market.csv", "membership.csv", "listing.csv")}
            if extra_features is not None:
                _write_csv(extra_features, staging / "extra_features.csv")
                files["extra_features.csv"] = {"sha256": file_hash(staging / "extra_features.csv"), "bytes": (staging / "extra_features.csv").stat().st_size}
            if source_file is not None:
                original = Path(source_file).expanduser().resolve()
                original_copy = staging / "source-input.csv"
                original_copy.write_bytes(original.read_bytes())
                files["source-input.csv"] = {"sha256": file_hash(original_copy), "bytes": original_copy.stat().st_size, "original_name": original.name}
            generation = f"data-{content_hash({'files': {key: value['sha256'] for key, value in files.items()}, 'source': source})[:24]}"
            target = self.paths.data_generations / generation
            if target.exists():
                existing = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
                same_files = {key: value.get("sha256") for key, value in existing.get("files", {}).items()} == {key: value.get("sha256") for key, value in files.items()}
                if not same_files:
                    raise DataError(f"generation hash collision: {generation}")
                import shutil

                shutil.rmtree(staging, ignore_errors=True)
                pointer = {"schema_version": 1, "generation": generation, "manifest_hash": content_hash(existing), "published_at": now_utc()}
                atomic_json(self.paths.active_data, pointer)
                if self.registry:
                    self.registry.put_generation(generation, "data", existing, status="active")
                return existing
            manifest = {
                "schema_version": 1,
                "generation": generation,
                "source": source,
                "created_at": now_utc(),
                "parent_generation": parent_manifest.get("generation") if parent_manifest else None,
                "date_min": str(market["日期"].min().date()),
                "date_max": str(market["日期"].max().date()),
                "market_rows": int(len(market)),
                "market_stocks": int(market["股票代码"].nunique()),
                "membership_rows": int(len(membership)),
                "files": files,
                "metadata": metadata or {},
            }
            self._fault("before_manifest")
            atomic_json(staging / "manifest.json", manifest)
            self._fault("after_manifest")
            self._fault("before_generation_rename")
            staging.rename(target)
            self._fault("after_generation_rename")
            self._fault("before_active_pointer")
            atomic_json(self.paths.active_data, {"schema_version": 1, "generation": generation, "manifest_hash": content_hash(manifest), "published_at": now_utc()})
            self._fault("after_active_pointer")
            if self.registry:
                self.registry.put_generation(generation, "data", manifest, status="active")
            self._fault("after_registry")
            return manifest
        except Exception:
            import shutil

            shutil.rmtree(staging, ignore_errors=True)
            raise

    def import_csv(
        self,
        market_csv: str | Path,
        *,
        membership_csv: str | Path | None = None,
        listing_csv: str | Path | None = None,
        mapping: dict[str, str] | None = None,
        units: dict[str, str] | None = None,
        source: str = "local_csv",
        merge_active: bool = False,
        conflict_precedence: str | None = None,
    ) -> dict[str, Any]:
        if not units or any(units.get(field) != expected for field, expected in REQUIRED_UNITS.items()):
            raise DataError("CSV unit declarations are required for price, volume, amount, turnover, and percentage fields")
        from .csv_validation import validate_csv

        validation = validate_csv(market_csv, mapping, units=units)
        if validation["status"] == "FAIL":
            raise DataError("CSV validation failed: " + "; ".join(item["message"] for item in validation["findings"]))
        market = csv_to_market(market_csv, mapping, units)
        validation_manifest = dict(validation)
        validation_manifest["source"] = "<LOCAL_SOURCE>"
        conflict_count = 0
        if merge_active:
            if conflict_precedence not in {"user", "managed"}:
                raise DataError("merging an existing generation requires conflict_precedence=user or managed")
            current_manifest = self.active_manifest()
            if current_manifest is None:
                raise DataError("cannot merge because no managed generation is active")
            current = self.active_bundle()
            managed_market = cast(pd.DataFrame, current["market"])
            conflict_count = int(
                market.merge(managed_market[["股票代码", "日期"]], on=["股票代码", "日期"], how="inner").shape[0]
            )
            market = (
                pd.concat([managed_market, market], ignore_index=True)
                .drop_duplicates(["股票代码", "日期"], keep="last" if conflict_precedence == "user" else "first")
            )
        if membership_csv:
            membership = pd.read_csv(membership_csv)
        else:
            membership = pd.DataFrame({"stock_id": sorted(market["股票代码"].unique()), "index_code": "CSI300", "start_date": market["日期"].min(), "end_date": pd.NaT})
        if listing_csv:
            listing = pd.read_csv(listing_csv)
        else:
            listing = pd.DataFrame({"stock_id": sorted(market["股票代码"].unique()), "ipo_date": market["日期"].min(), "out_date": pd.NaT})
        return self.publish(
            market,
            membership,
            listing,
            source=source,
            source_file=market_csv,
            metadata={
                "input_csv_name": Path(market_csv).name,
                "membership_route": "CUSTOM_UNIVERSE",
                "csv_validation": validation_manifest,
                "unit_contract": dict(units),
                "field_mapping": dict(mapping or {}),
                "price_adjustment": "user-declared-source-values",
                "source_hash": validation.get("sha256"),
                "merge_active": merge_active,
                "conflict_count": conflict_count,
                "conflict_precedence": conflict_precedence,
            },
        )

    def update_baostock(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        pit_membership_csv: str | Path | None = None,
        codes: Iterable[str] | None = None,
        allow_non_pit: bool = False,
        progress: Callable[[dict[str, Any]], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """Build and atomically publish a BaoStock-derived data generation.

        The source generation is immutable.  Provider downloads, checkpoints,
        validation, and the new manifest are completed before the active pointer
        moves, so an interrupted update leaves the previous generation usable.
        """
        try:
            import baostock as bs  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise DataError("BaoStock connector is not installed; install the optional baostock extra") from exc
        previous_manifest = self.active_manifest()
        previous = self.active_bundle() if previous_manifest else None
        previous_route = str(((previous_manifest or {}).get("metadata") or {}).get("membership_route", ""))
        supplied_membership = pd.read_csv(pit_membership_csv) if pit_membership_csv else None
        explicit_codes = sorted({str(value).strip().zfill(6) for value in (codes or []) if str(value).strip()})

        def emit(stage: str, completed: int = 0, total: int = 1, message: str = "") -> None:
            if cancelled and cancelled():
                raise DataError("数据更新已取消；上一活动版本保持不变")
            if progress:
                progress(
                    {
                        "stage": stage,
                        "completed": int(completed),
                        "total": max(1, int(total)),
                        "progress": min(1.0, max(0.0, completed / max(1, total))),
                        "message": message,
                    }
                )

        emit("connecting", message="正在登录 BaoStock")
        login = bs.login()
        if getattr(login, "error_code", "0") != "0":
            raise DataError(f"BaoStock login failed: {getattr(login, 'error_msg', login)}")
        try:
            target, sessions = self._baostock_sessions(bs, start_date, end_date, previous_manifest)
            cutoff = str(previous_manifest.get("date_max")) if previous_manifest else None
            effective_start = sessions[0] if sessions else target
            if not sessions and previous_manifest and not explicit_codes and supplied_membership is None:
                result = dict(previous_manifest)
                result["no_change"] = True
                result["update_plan"] = {
                    "current_cutoff": cutoff,
                    "target_cutoff": target,
                    "message": "当前数据已到 BaoStock 可用的最新完整交易日",
                }
                emit("complete", 1, 1, result["update_plan"]["message"])
                return result

            emit("listing", message="正在读取证券基础资料")
            stocks = self._query_with_retry(
                bs.query_stock_basic,
                fallback_kwargs={
                    "fields": "code,code_name,ipoDate,outDate,status",
                    "query_date": target,
                },
            )
            provider_listing = stocks.rename(columns={"code": "stock_id", "ipoDate": "ipo_date", "outDate": "out_date"})
            provider_listing["provider_code"] = provider_listing["stock_id"].astype(str)
            provider_listing["stock_id"] = provider_listing["stock_id"].astype(str).str.extract(r"(\d{6})")[0]

            emit("pool", message="正在构建可回溯股票池")
            if supplied_membership is not None:
                membership = _normalise_membership(supplied_membership)
                membership_route = "PIT_BASELINE"
                pit_status = "user_supplied_verified_sidecar"
                requested_codes = sorted(membership["stock_id"].astype(str).unique())
            elif explicit_codes:
                old_custom = cast(pd.DataFrame, previous["membership"]) if previous is not None and previous_route == "CUSTOM_UNIVERSE" else None
                membership = self._custom_membership_update(old_custom, explicit_codes, effective_start, cutoff)
                membership_route = "CUSTOM_UNIVERSE"
                pit_status = "explicit_custom_code_set"
                requested_codes = explicit_codes
            elif previous is not None and previous_route in {"CUSTOM_UNIVERSE", "NON_PIT_FALLBACK"}:
                membership = cast(pd.DataFrame, previous["membership"]).copy()
                previous_market = cast(pd.DataFrame, previous["market"])
                requested_codes = sorted(previous_market["股票代码"].astype(str).str.extract(r"(\d{6})")[0].dropna().unique())
                membership_route = previous_route
                pit_status = "retained_previous_custom_pool"
            else:
                try:
                    if not hasattr(bs, "query_trade_dates"):
                        raise DataError("BaoStock trading calendar endpoint is unavailable")
                    snapshots: list[tuple[str, set[str]]] = []
                    for index, session in enumerate(sessions, start=1):
                        emit("pool", index - 1, len(sessions), f"正在核对 {session} 的沪深300历史成分")
                        frame = self._query_with_retry(
                            bs.query_hs300_stocks,
                            date=session,
                            fallback_kwargs={"query_date": session},
                        )
                        values = set(frame.get("code", pd.Series(dtype=str)).astype(str).str.extract(r"(\d{6})")[0].dropna())
                        if not values:
                            raise DataError(f"BaoStock 未返回 {session} 的历史成分")
                        if len(values) != 300:
                            raise DataError(f"BaoStock 返回的 {session} 沪深300成分数量为 {len(values)}，预期 300")
                        snapshots.append((session, values))
                    old_membership = cast(pd.DataFrame, previous["membership"]) if previous is not None and previous_route == "PIT_BASELINE" else None
                    membership = self._membership_from_snapshots(snapshots, old_membership, cutoff)
                    membership_route = "PIT_BASELINE"
                    pit_status = "provider_historical_intervals_verified"
                    requested_codes = sorted(set().union(*(values for _, values in snapshots)))
                except (AttributeError, DataError):
                    if not allow_non_pit:
                        raise DataError("历史 PIT 成分查询未完成；请提供 PIT 成分文件或显式确认 --allow-non-pit；活动数据仍保持原版本") from None
                    current_membership = self._query_with_retry(
                        bs.query_hs300_stocks,
                        date=target,
                        fallback_kwargs={"query_date": target},
                    ).rename(columns={"code": "stock_id"})
                    requested_codes = sorted(set(current_membership["stock_id"].astype(str).str.extract(r"(\d{6})")[0].dropna()))
                    membership = current_membership.assign(index_code="CSI300", start_date=effective_start, end_date=pd.NaT)
                    membership_route = "NON_PIT_FALLBACK"
                    pit_status = "current_snapshot_only_explicit_ack"

            requested_codes = sorted(set(requested_codes))
            if not requested_codes:
                raise DataError("BaoStock returned no supported stock codes for the requested universe")
            estimated_bytes = len(requested_codes) * max(1, len(sessions)) * 240
            required_free = max(64 * 1024 * 1024, estimated_bytes * 2)
            free_bytes = shutil.disk_usage(self.paths.root).free
            if free_bytes < required_free:
                raise DataError(
                    f"数据更新磁盘空间不足：预计至少需要 {required_free} 字节，当前可用 {free_bytes} 字节"
                )

            previous_listing = cast(pd.DataFrame, previous["listing"]) if previous is not None else pd.DataFrame()
            listing = pd.concat([previous_listing, provider_listing], ignore_index=True, sort=False)
            listing = listing.drop_duplicates("stock_id", keep="last")
            historical_codes = set(membership["stock_id"].astype(str))
            if previous is not None:
                historical_codes |= set(cast(pd.DataFrame, previous["market"])["股票代码"].astype(str).str.extract(r"(\d{6})")[0].dropna())
            listing = listing[listing["stock_id"].isin(historical_codes | set(requested_codes))].copy()
            listing["exchange"] = listing["stock_id"].map(self._exchange_for_code)
            available = set(provider_listing["stock_id"].dropna()) | set(previous_listing.get("stock_id", pd.Series(dtype=str)).astype(str))
            missing_listing = sorted(set(requested_codes) - available)
            if missing_listing:
                raise DataError(f"BaoStock listing metadata missing {len(missing_listing)} requested codes")
            provider_code_by_id = dict(zip(provider_listing["stock_id"], provider_listing["provider_code"], strict=False))
            codes_to_pull = requested_codes
            rows: list[pd.DataFrame] = []
            extra: list[pd.DataFrame] = []
            fields = "date,code,open,high,low,close,volume,amount,turn,pctChg"
            extra_fields = "date,code,peTTM,psTTM,pcfNcfTTM,pbMRQ"
            request_identity = {
                "connector": "baostock-0.9.3",
                "codes": requested_codes,
                "start": effective_start,
                "end": target,
                "adjustflag": "3",
                "fields": [fields, extra_fields],
                "membership_route": membership_route,
            }
            checkpoint_key = content_hash(request_identity)[:16]
            checkpoint_root = self.paths.data_checkpoints / checkpoint_key
            checkpoint_root.mkdir(parents=True, exist_ok=True)
            atomic_json(
                checkpoint_root / "state.json",
                {"key": checkpoint_key, "request_identity": request_identity, "completed": []},
            )
            completed: list[str] = []
            for index, code in enumerate(codes_to_pull, start=1):
                emit("market", index - 1, len(codes_to_pull), f"正在下载 {code} 的行情与估值字段")
                market_cache = checkpoint_root / f"{code}.market.csv"
                extra_cache = checkpoint_root / f"{code}.extra.csv"
                if market_cache.exists() and extra_cache.exists():
                    rows.append(pd.read_csv(market_cache, dtype=str))
                    extra.append(pd.read_csv(extra_cache, dtype=str))
                else:
                    provider_code = provider_code_by_id.get(code, self._provider_code(code))
                    market_part = self._query_with_retry(bs.query_history_k_data_plus, provider_code, fields, start_date=effective_start, end_date=target, frequency="d", adjustflag="3")
                    extra_part = self._query_with_retry(bs.query_history_k_data_plus, provider_code, extra_fields, start_date=effective_start, end_date=target, frequency="d", adjustflag="3")
                    _write_csv(market_part, market_cache)
                    _write_csv(extra_part, extra_cache)
                    rows.append(market_part)
                    extra.append(extra_part)
                completed.append(code)
                atomic_json(
                    checkpoint_root / "state.json",
                    {"key": checkpoint_key, "request_identity": request_identity, "completed": completed},
                )
                if index % 100 == 0:
                    LOG.info("BaoStock update: %s/%s securities", index, len(codes_to_pull))
            market = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
            market = market.rename(columns={"code": "股票代码", "date": "日期", "open": "开盘", "close": "收盘", "high": "最高", "low": "最低", "volume": "成交量", "amount": "成交额", "turn": "换手率", "pctChg": "涨跌幅"})
            market["股票代码"] = market["股票代码"].astype(str).str.extract(r"(\d{6})")[0]
            market["日期"] = pd.to_datetime(market["日期"], errors="raise").dt.normalize()
            numeric = {column: pd.to_numeric(market[column], errors="coerce") for column in ("开盘", "收盘", "最高", "最低")}
            market["振幅"] = ((numeric["最高"] - numeric["最低"]) / numeric["开盘"].replace(0, pd.NA) * 100).fillna(0.0)
            market["涨跌额"] = (numeric["收盘"] - numeric["开盘"]).fillna(0.0)
            downloaded_market = market.copy()
            if previous is not None:
                old_market = cast(pd.DataFrame, previous["market"])
                old_market = old_market.copy()
                old_market["股票代码"] = old_market["股票代码"].astype(str).str.extract(r"(\d{6})")[0]
                old_market["日期"] = pd.to_datetime(old_market["日期"], errors="raise").dt.normalize()
                market = pd.concat([old_market, market], ignore_index=True).drop_duplicates(["股票代码", "日期"], keep="last")
            extra_frame = pd.concat(extra, ignore_index=True) if extra else None
            if extra_frame is not None:
                extra_frame = extra_frame.rename(columns={"code": "股票代码", "date": "日期"})
                if {"股票代码", "日期"}.issubset(extra_frame.columns):
                    extra_frame["股票代码"] = extra_frame["股票代码"].astype(str).str.extract(r"(\d{6})")[0]
                    extra_frame["日期"] = pd.to_datetime(extra_frame["日期"], errors="coerce").dt.normalize()
                    extra_frame = extra_frame.dropna(subset=["股票代码", "日期"])
                    extra_frame = extra_frame.drop_duplicates(["股票代码", "日期"], keep="last")
            if previous is not None and extra_frame is not None:
                previous_extra = cast(pd.DataFrame, previous.get("extra_features", pd.DataFrame()))
                if not previous_extra.empty:
                    previous_extra = previous_extra.rename(columns={"code": "股票代码", "date": "日期"})
                    previous_extra["股票代码"] = previous_extra["股票代码"].astype(str).str.extract(r"(\d{6})")[0]
                    previous_extra["日期"] = pd.to_datetime(previous_extra["日期"], errors="coerce").dt.normalize()
                    extra_frame = (
                        pd.concat([previous_extra, extra_frame], ignore_index=True)
                        .drop_duplicates(["股票代码", "日期"], keep="last")
                    )
            emit("extra", 1, 1, "行情与估值扩展字段已下载，准备执行完整校验")
            emit("validation", message="正在校验键、OHLC、范围、覆盖率、复权和 PIT 区间")
            validation_start = start_date if not sessions and start_date else effective_start
            self._validate_baostock_market(downloaded_market, validation_start, target)
            derived_from = str(previous_manifest.get("source")) if previous_manifest else "baostock"
            previous_contract = dict((previous_manifest or {}).get("metadata") or {})
            emit("publish", message="正在原子发布新的活动数据版本")
            if extra_frame is not None:
                repeated_features = [
                    column
                    for column in extra_frame.columns
                    if column not in {"股票代码", "日期"} and column in market.columns
                ]
                if repeated_features:
                    market = market.drop(columns=repeated_features)
            manifest = self.publish(
                market,
                membership,
                listing,
                source="baostock",
                extra_features=extra_frame,
                metadata={
                    "start_date": effective_start,
                    "end_date": target,
                    "connector": "baostock",
                    "derived_from_source": derived_from,
                    "derived_from_generation": previous_manifest.get("generation") if previous_manifest else None,
                    "source_contract_review": {
                        "previous_adjustment": previous_contract.get("adjustflag") or previous_contract.get("price_adjustment") or (previous_contract.get("market_contract") or {}).get("price_adjustment") or "未标记",
                        "previous_units": previous_contract.get("unit_contract") or (previous_contract.get("market_contract") or {}).get("units") or {},
                        "provider_adjustment": "3",
                        "provider_units": {"price": "CNY", "volume": "shares", "amount": "CNY", "turnover": "percentage", "change_pct": "percentage"},
                    },
                    "membership_route": membership_route,
                    "pit_status": pit_status,
                    "fallback_ack": "NON_PIT_SURVIVORSHIP_WARNING_V1" if membership_route == "NON_PIT_FALLBACK" else None,
                    "requested_codes": len(requested_codes),
                    "actual_latest_full_session": target,
                    "incremental_sessions": len(sessions),
                    "adjustflag": "3",
                    "price_adjustment": "post-adjusted",
                    "field_contract": {"market": fields.split(","), "extra": extra_fields.split(",")},
                    "unit_contract": {"price": "CNY", "volume": "shares", "amount": "CNY", "turnover": "percentage", "change_pct": "percentage"},
                    "checkpoint_identity": checkpoint_key,
                    "estimated_download_bytes": estimated_bytes,
                    "disk_free_before_update": free_bytes,
                    "market_source": "baostock.query_history_k_data_plus",
                    "extra_features_source": "baostock.query_history_k_data_plus",
                    "terms_url": "https://www.baostock.com/",
                    "freshness_warning": _freshness_warning(),
                },
            )
            shutil.rmtree(checkpoint_root, ignore_errors=True)
            emit("complete", 1, 1, "数据更新完成")
            return manifest
        finally:
            bs.logout()

    def plan_baostock_update(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        codes: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Return a user-facing, read-only preview before an update starts."""
        try:
            import baostock as bs  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise DataError("BaoStock connector is not installed") from exc
        active = self.active_manifest()
        login = bs.login()
        if getattr(login, "error_code", "0") != "0":
            raise DataError(f"BaoStock login failed: {getattr(login, 'error_msg', login)}")
        try:
            target, sessions = self._baostock_sessions(bs, start_date, end_date, active)
            active_metadata = dict((active or {}).get("metadata") or {})
            selected = sorted({str(value).strip().zfill(6) for value in (codes or []) if str(value).strip()})
            if not selected and active:
                selected = cast(pd.DataFrame, self.active_bundle()["market"])["股票代码"].astype(str).str.zfill(6).drop_duplicates().tolist()
            estimated_rows = len(selected or range(300)) * len(sessions)
            estimated_bytes = estimated_rows * 240
            disk_free = shutil.disk_usage(self.paths.root).free
            disk_required = max(64 * 1024 * 1024, estimated_bytes * 2)
            return {
                "source": "BaoStock",
                "current_source": active.get("source") if active else "尚未初始化",
                "current_generation": active.get("generation") if active else "尚未生成",
                "current_cutoff": active.get("date_max") if active else "尚无截止日",
                "target_cutoff": target,
                "start_session": sessions[0] if sessions else "无需新增",
                "trading_sessions": len(sessions),
                "stock_count": len(selected) or 300,
                "estimated_rows": estimated_rows,
                "estimated_download_bytes": estimated_bytes,
                "disk_required_bytes": disk_required,
                "disk_free_bytes": disk_free,
                "disk_ok": disk_free >= disk_required,
                "content_root": str(self.paths.root),
                "active_data_root": str(self.paths.data_generations),
                "membership_route": str(((active or {}).get("metadata") or {}).get("membership_route") or "PIT_BASELINE"),
                "adjustflag": "3（后复权）",
                "fields": "日线 OHLCV、成交额、换手率、涨跌幅、PE/PS/PCF/PB",
                "current_adjustment": active_metadata.get("adjustflag") or active_metadata.get("price_adjustment") or (active_metadata.get("market_contract") or {}).get("price_adjustment") or "未标记",
                "current_units": active_metadata.get("unit_contract") or (active_metadata.get("market_contract") or {}).get("units") or {},
                "identity_change": "数据截止日、股票池或字段契约变化后，旧模型会标记为待重训",
                "freshness_warning": _freshness_warning(),
            }
        finally:
            bs.logout()

    def _baostock_sessions(
        self,
        bs: Any,
        start_date: str | None,
        end_date: str | None,
        active: dict[str, Any] | None,
    ) -> tuple[str, list[str]]:
        cutoff = cast(pd.Timestamp, pd.Timestamp(str(active["date_max"]))).normalize() if active else None
        default_start = str((cutoff + pd.Timedelta(days=1)).date()) if cutoff is not None else "2015-01-01"
        requested_start = cast(pd.Timestamp, pd.Timestamp(start_date or default_start)).normalize()
        requested_end = cast(pd.Timestamp, pd.Timestamp(end_date or date.today().isoformat())).normalize()
        if requested_start > requested_end:
            return str(cutoff.date() if cutoff is not None else requested_end.date()), []
        if hasattr(bs, "query_trade_dates"):
            calendar = self._query_with_retry(
                bs.query_trade_dates,
                start_date=str(requested_start.date()),
                end_date=str(requested_end.date()),
            )
            date_column = "calendar_date" if "calendar_date" in calendar else "date"
            flag_column = "is_trading_day" if "is_trading_day" in calendar else None
            if date_column not in calendar:
                raise DataError("BaoStock trading calendar schema is missing calendar_date")
            valid = calendar if flag_column is None else calendar[calendar[flag_column].astype(str).eq("1")]
            sessions = pd.to_datetime(valid[date_column], errors="coerce").dropna().dt.strftime("%Y-%m-%d").tolist()
        elif end_date is not None:
            sessions = pd.date_range(requested_start, requested_end, freq="D").strftime("%Y-%m-%d").tolist()
        else:
            raise DataError("BaoStock trading calendar endpoint is unavailable")
        if cutoff is not None:
            sessions = [value for value in sessions if pd.Timestamp(value) > cutoff]
        if not sessions:
            target = str(cutoff.date()) if cutoff is not None else str(requested_end.date())
            return target, []
        target = sessions[-1]
        if end_date is None:
            # Calendar membership alone does not prove that today's daily bars
            # are complete.  Probe the broad-market index and walk backwards.
            fields = "date,code,close"
            while sessions:
                candidate = sessions[-1]
                probe = self._query_with_retry(
                    bs.query_history_k_data_plus,
                    "sh.000300",
                    fields,
                    start_date=candidate,
                    end_date=candidate,
                    frequency="d",
                    adjustflag="3",
                )
                if not probe.empty:
                    target = candidate
                    break
                sessions.pop()
            if not sessions:
                target = str(cutoff.date()) if cutoff is not None else str(requested_end.date())
        return target, sessions

    @staticmethod
    def _membership_from_snapshots(
        snapshots: list[tuple[str, set[str]]],
        previous: pd.DataFrame | None,
        previous_cutoff: str | None,
    ) -> pd.DataFrame:
        if not snapshots:
            return _normalise_membership(previous) if previous is not None else pd.DataFrame()
        intervals: list[dict[str, Any]] = []
        open_since: dict[str, str] = {}
        prior_session = previous_cutoff
        for session, codes in snapshots:
            for code in sorted(set(open_since) - codes):
                intervals.append({"stock_id": code, "index_code": "CSI300", "start_date": open_since.pop(code), "end_date": prior_session})
            for code in sorted(codes - set(open_since)):
                open_since[code] = session
            prior_session = session
        intervals.extend({"stock_id": code, "index_code": "CSI300", "start_date": start, "end_date": pd.NaT} for code, start in sorted(open_since.items()))
        new_frame = pd.DataFrame(intervals)
        if previous is None or previous.empty:
            return _normalise_membership(new_frame)
        old = _normalise_membership(previous)
        first_codes = snapshots[0][1]
        first_session = pd.Timestamp(snapshots[0][0])
        closed = old[old["end_date"].notna()].copy()
        open_old = old[old["end_date"].isna()].copy()
        leaving = open_old[~open_old["stock_id"].isin(first_codes)].copy()
        if not leaving.empty:
            leaving["end_date"] = pd.Timestamp(previous_cutoff) if previous_cutoff else first_session - pd.Timedelta(days=1)
        continuing = open_old[open_old["stock_id"].isin(first_codes)]
        for row in continuing.itertuples(index=False):
            mask = new_frame["stock_id"].eq(row.stock_id) & new_frame["start_date"].eq(snapshots[0][0])
            new_frame.loc[mask, "start_date"] = row.start_date
        combined = pd.concat([closed, leaving, new_frame], ignore_index=True)
        return _normalise_membership(combined)

    @staticmethod
    def _custom_membership_update(
        previous: pd.DataFrame | None,
        codes: list[str],
        effective_start: str,
        previous_cutoff: str | None,
    ) -> pd.DataFrame:
        if previous is None or previous.empty:
            return _normalise_membership(
                pd.DataFrame(
                    {"stock_id": codes, "index_code": "CUSTOM", "start_date": effective_start, "end_date": pd.NaT}
                )
            )
        old = _normalise_membership(previous)
        open_mask = old["end_date"].isna()
        active_codes = set(old.loc[open_mask, "stock_id"].astype(str))
        selected = set(codes)
        removed = active_codes - selected
        old.loc[open_mask & old["stock_id"].isin(removed), "end_date"] = pd.Timestamp(previous_cutoff or effective_start)
        additions = sorted(selected - active_codes)
        if additions:
            old = pd.concat(
                [
                    old,
                    pd.DataFrame(
                        {"stock_id": additions, "index_code": "CUSTOM", "start_date": effective_start, "end_date": pd.NaT}
                    ),
                ],
                ignore_index=True,
            )
        return _normalise_membership(old)

    @staticmethod
    def _exchange_for_code(code: str) -> str:
        value = str(code).zfill(6)
        if value.startswith(("600", "601", "603", "605", "688")):
            return "SH"
        if value.startswith(("000", "001", "002", "003", "300", "301")):
            return "SZ"
        return "BJ"

    @classmethod
    def _provider_code(cls, code: str) -> str:
        exchange = cls._exchange_for_code(code).lower()
        return f"{exchange}.{str(code).zfill(6)}"

    @staticmethod
    def _validate_baostock_market(market: pd.DataFrame, start: str, end: str) -> None:
        if market.empty:
            raise DataError("BaoStock did not return market rows for the requested interval")
        if market.duplicated(["股票代码", "日期"]).any():
            raise DataError("BaoStock returned duplicate stock/date keys")
        numeric = market[["开盘", "收盘", "最高", "最低"]].apply(pd.to_numeric, errors="coerce")
        if numeric.isna().any().any() or (numeric <= 0).any().any():
            raise DataError("BaoStock returned invalid OHLC values")
        if (numeric["最高"] < numeric[["开盘", "收盘", "最低"]].max(axis=1)).any() or (numeric["最低"] > numeric[["开盘", "收盘", "最高"]].min(axis=1)).any():
            raise DataError("BaoStock returned inconsistent OHLC relationships")
        dates = pd.to_datetime(market["日期"], errors="coerce")
        if dates.isna().any() or dates.min() < pd.Timestamp(start) or dates.max() > pd.Timestamp(end):
            raise DataError("BaoStock returned rows outside the requested date range")

    @staticmethod
    def _query_result(query: Any) -> pd.DataFrame:
        if getattr(query, "error_code", "0") != "0":
            raise DataError(f"BaoStock query failed: {getattr(query, 'error_msg', query)}")
        rows = []
        while query.next():
            rows.append(query.get_row_data())
        return pd.DataFrame(rows, columns=query.fields)

    @staticmethod
    def _query_all(fn: Any, **kwargs: Any) -> pd.DataFrame:
        return DataManager._query_result(fn(**kwargs))

    @staticmethod
    def _query_with_retry(
        fn: Any,
        *args: Any,
        attempts: int = 3,
        fallback_kwargs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                try:
                    query = fn(*args, **kwargs)
                except TypeError:
                    if fallback_kwargs is None:
                        raise
                    query = fn(*args, **fallback_kwargs)
                return DataManager._query_result(query)
            except Exception as exc:
                last = exc
                LOG.warning("BaoStock request failed (attempt %s/%s): %s", attempt + 1, attempts, exc)
        raise DataError(f"BaoStock request failed after {attempts} attempts: {last}") from last

    def recover(self) -> list[str]:
        return recover_staging(self.paths)

    def search_baostock(self, query: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """Search BaoStock's local listing endpoint for supported A-share names/codes."""
        try:
            import baostock as bs  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise DataError("BaoStock connector is not installed") from exc
        login = bs.login()
        if getattr(login, "error_code", "0") != "0":
            raise DataError(f"BaoStock login failed: {getattr(login, 'error_msg', login)}")
        try:
            frame = self._query_with_retry(
                bs.query_stock_basic,
                fallback_kwargs={
                    "fields": "code,code_name,ipoDate,outDate,status",
                    "query_date": date.today().isoformat(),
                },
            )
            text = str(query).strip().lower()
            code = frame["code"].astype(str).str.extract(r"(\d{6})")[0]
            name = frame.get("code_name", pd.Series("", index=frame.index)).astype(str)
            mask = code.str.startswith(("600", "601", "603", "605", "688", "000", "001", "002", "003", "300", "301", "430", "440", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "920"))
            if text:
                mask &= code.str.contains(text, case=False, na=False) | name.str.lower().str.contains(text, na=False)
            result = frame.loc[mask].copy().head(max(1, int(limit)))
            result["stock_id"] = result["code"].astype(str).str.extract(r"(\d{6})")[0]
            result = result.rename(columns={"code_name": "name", "ipoDate": "ipo_date", "outDate": "out_date"})
            columns = [column for column in ("stock_id", "name", "ipo_date", "out_date", "status") if column in result.columns]
            return result[columns].to_dict(orient="records")
        finally:
            bs.logout()
