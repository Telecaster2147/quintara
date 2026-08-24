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
    frame.to_csv(path, index=False, encoding="utf-8")


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
                "market": pd.read_csv(root / "market.csv", parse_dates=["日期"]),
                "membership": pd.read_csv(root / "membership.csv", parse_dates=["start_date", "end_date"]),
                "listing": pd.read_csv(root / "listing.csv", parse_dates=["ipo_date", "out_date"]),
                "extra_features": (
                    pd.read_csv(root / "extra_features.csv", parse_dates=["日期"])
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
    ) -> dict[str, Any]:
        """Pull market, listing, HS300 membership, and extra valuation fields."""
        try:
            import baostock as bs  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise DataError("BaoStock connector is not installed; install the optional baostock extra") from exc
        end = end_date or date.today().isoformat()
        if start_date is None:
            active = self.active_manifest()
            start_date = str(active["date_max"]) if active else "2015-01-01"
        previous_manifest = self.active_manifest()
        previous = self.active_bundle() if previous_manifest else None
        previous_route = str(((previous_manifest or {}).get("metadata") or {}).get("membership_route", ""))
        supplied_membership = pd.read_csv(pit_membership_csv) if pit_membership_csv else None
        login = bs.login()
        if getattr(login, "error_code", "0") != "0":
            raise DataError(f"BaoStock login failed: {getattr(login, 'error_msg', login)}")
        try:
            # BaoStock's Python client calls this argument ``date``.  A few
            # local compatibility shims (including older fake connectors)
            # used ``query_date``; the retry helper keeps those fixtures
            # usable while the real connector receives its documented API.
            current_membership = self._query_with_retry(
                bs.query_hs300_stocks,
                date=end,
                fallback_kwargs={"query_date": end},
            )
            current_membership = current_membership.rename(columns={"code": "stock_id"})
            current_codes = current_membership["stock_id"].astype(str).str.extract(r"(\d{6})")[0].dropna().tolist() if "stock_id" in current_membership else []
            if supplied_membership is not None:
                pit_normalized = _normalise_membership(supplied_membership)
                requested_codes = pit_normalized["stock_id"].astype(str).unique().tolist()
            elif codes is not None:
                # An explicit code set is the custom-universe route.  It is
                # intentionally evaluated before retaining a previous PIT
                # route so a user can extend or switch the active universe in
                # one update operation.
                requested_codes = [str(value).strip().zfill(6) for value in codes if str(value).strip()]
                pit_normalized = None
            elif previous is not None and previous_route == "PIT_BASELINE":
                pit_normalized = cast(pd.DataFrame, previous["membership"])
                requested_codes = pit_normalized["stock_id"].astype(str).unique().tolist()
            elif previous is not None and previous_route in {"CUSTOM_UNIVERSE", "NON_PIT_FALLBACK"} and codes is None:
                # An update against an existing user generation follows that
                # generation's exact stock closure instead of silently
                # switching back to BaoStock's current HS300 snapshot.  This
                # is what makes extra features reconnect to the active CSV.
                pit_normalized = cast(pd.DataFrame, previous["membership"])
                previous_market = cast(pd.DataFrame, previous["market"])
                requested_codes = previous_market["股票代码"].astype(str).str.extract(r"(\d{6})")[0].dropna().unique().tolist()
            else:
                requested_codes = current_codes
                pit_normalized = None
            requested_codes = sorted(set(requested_codes))
            if not requested_codes:
                raise DataError("BaoStock returned no supported stock codes for the requested universe")
            # ``query_stock_basic`` returns its canonical fields and accepts
            # no date/fields keyword in the released BaoStock client.  The
            # fallback is retained for the small connector fakes used by
            # downstream integrations.
            stocks = self._query_with_retry(
                bs.query_stock_basic,
                fallback_kwargs={
                    "fields": "code,code_name,ipoDate,outDate,status",
                    "query_date": end,
                },
            )
            stocks = stocks[stocks["status"].astype(str).eq("1")].copy() if "status" in stocks else stocks
            listing = stocks.rename(columns={"code": "stock_id", "ipoDate": "ipo_date", "outDate": "out_date"})
            listing = listing[listing["stock_id"].astype(str).str.extract(r"(\d{6})")[0].isin(requested_codes)].copy()
            listing["exchange"] = listing["stock_id"].astype(str).str.extract(r"(\d{6})")[0].map(lambda value: "SH" if str(value).startswith(("600", "601", "603", "605", "688")) else "SZ" if str(value).startswith(("000", "001", "002", "003", "300", "301")) else "BJ")
            codes_to_pull = listing["stock_id"].astype(str).str.extract(r"(\d{6})")[0].dropna().tolist()
            missing_listing = sorted(set(requested_codes) - set(codes_to_pull))
            if missing_listing:
                raise DataError(f"BaoStock listing metadata missing {len(missing_listing)} requested codes")
            rows: list[pd.DataFrame] = []
            extra: list[pd.DataFrame] = []
            fields = "date,code,open,high,low,close,volume,amount,turn,pctChg"
            extra_fields = "date,code,peTTM,psTTM,pcfNcfTTM,pbMRQ"
            checkpoint_key = content_hash({"codes": requested_codes, "start": start_date, "end": end})[:16]
            checkpoint_root = self.paths.data_checkpoints / checkpoint_key
            checkpoint_root.mkdir(parents=True, exist_ok=True)
            atomic_json(
                checkpoint_root / "state.json",
                {"key": checkpoint_key, "requested_codes": requested_codes, "start_date": start_date, "end_date": end, "completed": []},
            )
            completed: list[str] = []
            for index, code in enumerate(codes_to_pull, start=1):
                market_cache = checkpoint_root / f"{code}.market.csv"
                extra_cache = checkpoint_root / f"{code}.extra.csv"
                if market_cache.exists() and extra_cache.exists():
                    rows.append(pd.read_csv(market_cache, dtype=str))
                    extra.append(pd.read_csv(extra_cache, dtype=str))
                else:
                    market_part = self._query_with_retry(bs.query_history_k_data_plus, f"{code}", fields, start_date=start_date, end_date=end, frequency="d", adjustflag="3")
                    extra_part = self._query_with_retry(bs.query_history_k_data_plus, f"{code}", extra_fields, start_date=start_date, end_date=end, frequency="d", adjustflag="3")
                    _write_csv(market_part, market_cache)
                    _write_csv(extra_part, extra_cache)
                    rows.append(market_part)
                    extra.append(extra_part)
                completed.append(code)
                atomic_json(
                    checkpoint_root / "state.json",
                    {"key": checkpoint_key, "requested_codes": requested_codes, "start_date": start_date, "end_date": end, "completed": completed},
                )
                if index % 100 == 0:
                    LOG.info("BaoStock update: %s/%s securities", index, len(codes_to_pull))
            market = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
            market = market.rename(columns={"code": "股票代码", "date": "日期", "open": "开盘", "close": "收盘", "high": "最高", "low": "最低", "volume": "成交量", "amount": "成交额", "turn": "换手率", "pctChg": "涨跌幅"})
            market["股票代码"] = market["股票代码"].astype(str).str.extract(r"(\d{6})")[0]
            market["日期"] = pd.to_datetime(market["日期"], errors="raise").dt.normalize()
            for column in ("振幅", "涨跌额"):
                market[column] = 0.0
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
            if supplied_membership is not None:
                membership = pit_normalized
                membership_route = "PIT_BASELINE"
                pit_status = "user_supplied_verified_sidecar"
            elif codes is not None:
                membership = pd.DataFrame(
                    {
                        "stock_id": requested_codes,
                        "index_code": "CUSTOM",
                        "start_date": str(pd.Timestamp(market["日期"].min()).date()) if not market.empty else start_date,
                        "end_date": pd.NaT,
                    }
                )
                membership_route = "CUSTOM_UNIVERSE"
                pit_status = "explicit_custom_code_set"
            elif previous is not None and previous_route == "PIT_BASELINE":
                membership = pit_normalized
                membership_route = "PIT_BASELINE"
                pit_status = "retained_previous_verified"
            elif previous is not None and previous_route == "CUSTOM_UNIVERSE" and codes is None:
                membership = pit_normalized
                membership_route = "CUSTOM_UNIVERSE"
                pit_status = "retained_previous_custom_pool"
            elif previous is not None and previous_route == "NON_PIT_FALLBACK" and codes is None:
                membership = pit_normalized
                membership_route = "NON_PIT_FALLBACK"
                pit_status = "retained_previous_explicit_fallback"
            else:
                if not allow_non_pit:
                    raise DataError("历史 PIT 成分不可用；请提供 --pit-membership-csv，或显式确认 --allow-non-pit")
                membership = current_membership
                membership["index_code"] = "CSI300"
                membership["start_date"] = str(pd.Timestamp(market["日期"].min()).date()) if not market.empty else start_date
                membership["end_date"] = pd.NaT
                membership_route = "NON_PIT_FALLBACK"
                pit_status = "current_snapshot_only_explicit_ack"
            if membership is None:
                raise DataError("membership planning produced no route")
            manifest = self.publish(
                market,
                membership,
                listing,
                source="baostock",
                extra_features=extra_frame,
                metadata={
                    "start_date": start_date,
                    "end_date": end,
                    "connector": "baostock",
                    "membership_route": membership_route,
                    "pit_status": pit_status,
                    "fallback_ack": "NON_PIT_SURVIVORSHIP_WARNING_V1" if membership_route == "NON_PIT_FALLBACK" else None,
                    "requested_codes": len(requested_codes),
                    "market_source": "baostock.query_history_k_data_plus",
                    "extra_features_source": "baostock.query_history_k_data_plus",
                    "terms_url": "https://www.baostock.com/",
                    "freshness_warning": _freshness_warning(),
                },
            )
            shutil.rmtree(checkpoint_root, ignore_errors=True)
            return manifest
        finally:
            bs.logout()

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
