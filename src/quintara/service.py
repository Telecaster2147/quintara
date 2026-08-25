"""Application service shared by the shell CLI and the standalone Qt GUI."""
from __future__ import annotations

import json
import logging
import re
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import pandas as pd

from .contracts import STRATEGY_POLICIES
from .core import (
    COMPETITION_LABEL,
    DEFAULT_LABEL,
    DEFAULT_WEIGHTS,
    AppPaths,
    JobState,
    Severity,
    UniverseMode,
    app_version,
    content_hash,
    new_id,
    now_utc,
    runtime_identity,
)
from .data_lifecycle import DataManager
from .doctor import diagnose
from .explainability import correlation_matrix, feature_contributions, risk_metrics
from .jobs import JobCancelled, JobContext, read_events
from .kernel import (
    PreparedData,
    TrainedModel,
    default_model_config,
    kernel_source_hash,
    predict,
    prepare,
    train,
)
from .onboarding import RISK_STATEMENT_VERSION, OnboardingFlow, consent_is_current, consent_record
from .platform import FileLock, atomic_json
from .provider import ProviderPackageImporter
from .registry import Registry
from .universe import create_definition, membership_for_definition, normalize_codes

LOG = logging.getLogger(__name__)

STRATEGIES: dict[str, dict[str, Any]] = {
    "aggressive": {"lgbm_num_leaves": 31, "lgbm_min_data_in_leaf": 120, "lgbm_feature_fraction": 0.9, "lgbm_bagging_fraction": 0.9},
    "balanced": {"lgbm_num_leaves": 15, "lgbm_min_data_in_leaf": 500, "lgbm_feature_fraction": 0.7, "lgbm_bagging_fraction": 0.7},
    "conservative": {"lgbm_num_leaves": 7, "lgbm_min_data_in_leaf": 800, "lgbm_feature_fraction": 0.6, "lgbm_bagging_fraction": 0.6, "lgbm_time_decay_half_life_days": 720},
}
CONSENT_VERSION = RISK_STATEMENT_VERSION


class ServiceError(RuntimeError):
    """An error suitable for presentation in either frontend."""


class QuintaraService:
    def __init__(self, root: str | Path | None = None) -> None:
        self.paths = AppPaths.discover(root)
        self.paths.ensure()
        self.registry = Registry(self.paths)
        self.data = DataManager(self.paths, self.registry)
        self._active_run_id: str | None = None

    def close(self) -> None:
        self.registry.close()

    @staticmethod
    def _safe_run_id(run_id: str) -> str:
        value = str(run_id)
        if not re.fullmatch(r"run-[0-9a-f]{32}", value):
            raise ServiceError("run identifier format is invalid")
        return value

    def bootstrap(self) -> dict[str, Any]:
        self.paths.ensure()
        recovered = self.data.recover()
        active = self.registry.active_universe()
        data_manifest = self.data.active_manifest()
        if active is None and data_manifest is not None:
            bundle = self.data.active_bundle()
            codes = bundle["membership"]["stock_id"].astype(str).unique().tolist()  # type: ignore[index]
            metadata = data_manifest.get("metadata", {})
            route = UniverseMode(str(metadata.get("membership_route", UniverseMode.PIT_BASELINE.value)))
            name = "BaoStock HS300 PIT baseline" if route == UniverseMode.PIT_BASELINE else "Imported custom universe"
            if route == UniverseMode.NON_PIT_FALLBACK and metadata.get("fallback_ack"):
                definition = create_definition(name, route, codes, warning_ack=str(metadata["fallback_ack"]))
                universe_id = f"non-pit-fallback-{content_hash(definition)[:12]}"
                atomic_json(self.paths.universes / f"{universe_id}.json", {"id": universe_id, **definition})
                self.registry.put_universe(universe_id, definition["name"], route.value, definition, active=True)
            elif route == UniverseMode.NON_PIT_FALLBACK:
                LOG.warning("current-only membership is available; explicit NON_PIT_FALLBACK acknowledgement is required")
            elif route == UniverseMode.CUSTOM_UNIVERSE and len(codes) < 100:
                LOG.warning("imported custom universe has %s stocks; 100 are required before running", len(codes))
            else:
                definition = create_definition(name, route, codes)
                universe_id = "pit-baseline" if route == UniverseMode.PIT_BASELINE else f"custom-{content_hash(definition)[:12]}"
                atomic_json(self.paths.universes / f"{universe_id}.json", {"id": universe_id, **definition})
                self.registry.put_universe(universe_id, definition["name"], route.value, definition, active=True)
            active = self.registry.active_universe()
        return {"root": str(self.paths.root), "recovered_staging": recovered, "active_data": data_manifest, "active_universe": dict(active) if active else None, "consent": self.consent_status()}

    def consent_status(self) -> dict[str, Any]:
        if not self.paths.consent.exists():
            return {"status": "REQUIRED", "version": CONSENT_VERSION}
        try:
            value = json.loads(self.paths.consent.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"status": "REQUIRED", "version": CONSENT_VERSION}
        return {"status": "CONFIRMED" if consent_is_current(value) else "REQUIRED", **value, "required_version": CONSENT_VERSION}

    def confirm_consent(self) -> dict[str, Any]:
        value = consent_record(app_version())
        atomic_json(self.paths.consent, value)
        return {"status": "CONFIRMED", **value}

    def onboarding_status(self) -> dict[str, Any]:
        return OnboardingFlow(self.registry).status()

    def onboarding_advance(self, step: int, *, source: Any = None) -> dict[str, Any]:
        return OnboardingFlow(self.registry).advance(step, source=source)

    def onboarding_skip(self) -> dict[str, Any]:
        return OnboardingFlow(self.registry).skip()

    def onboarding_reopen(self) -> dict[str, Any]:
        return OnboardingFlow(self.registry).reopen()

    def doctor(self) -> dict[str, Any]:
        report = diagnose(self.paths)
        manifest = self.data.active_manifest()
        report["data"] = {"status": "VALID" if manifest else "NO_ACTIVE_DATA", "generation": manifest.get("generation") if manifest else None, "date_max": manifest.get("date_max") if manifest else None}
        report["model_compatibility"] = {"status": "NOT_CHECKED", "message": "a run validates model identity before scoring"}
        return report

    def import_csv(self, market_csv: str | Path, **kwargs: Any) -> dict[str, Any]:
        with FileLock(self.paths.lock):
            manifest = self.data.import_csv(market_csv, **kwargs)
        manifest["stale_models"] = self.registry.mark_models_stale_for_data(str(manifest["generation"]))
        self.bootstrap()
        return manifest

    def import_provider_package(self, package: str | Path, *, platform_tag: str = "any") -> dict[str, Any]:
        with FileLock(self.paths.lock):
            manifest = ProviderPackageImporter(self.data).import_package(Path(package), platform_tag=platform_tag)
        manifest["stale_models"] = self.registry.mark_models_stale_for_data(str(manifest["generation"]))
        self.bootstrap()
        return manifest

    def data_status(self) -> dict[str, Any]:
        active = self.data.active_manifest()
        generations = [dict(row) for row in self.registry.list_generations("data")]
        for row in generations:
            try:
                row["manifest"] = json.loads(row["manifest"])
            except (KeyError, TypeError, json.JSONDecodeError):
                pass
        difference = None
        if active and active.get("parent_generation"):
            parent_path = self.paths.data_generations / str(active["parent_generation"]) / "manifest.json"
            if parent_path.exists():
                parent = json.loads(parent_path.read_text(encoding="utf-8"))
                difference = {
                    "from": parent.get("generation"),
                    "to": active.get("generation"),
                    "date_max": [parent.get("date_max"), active.get("date_max")],
                    "market_rows_added": int(active.get("market_rows", 0)) - int(parent.get("market_rows", 0)),
                    "stocks_changed": int(active.get("market_stocks", 0)) - int(parent.get("market_stocks", 0)),
                }
        return {"active": active, "generations": generations, "difference": difference, "content_root": str(self.paths.root)}

    def update_data(self, **kwargs: Any) -> dict[str, Any]:
        # Keep BaoStock updates connected to the currently selected custom
        # pool.  Newly appended codes therefore receive market and
        # extra-feature rows on the next update without a second hidden
        # configuration file.
        if kwargs.get("codes") is None:
            active_universe = self.registry.active_universe()
            if active_universe is not None and str(active_universe["mode"]) == UniverseMode.CUSTOM_UNIVERSE.value:
                try:
                    definition = json.loads(active_universe["definition"])
                    kwargs["codes"] = list(definition.get("codes", []))
                except (TypeError, json.JSONDecodeError):
                    raise ServiceError("active custom universe definition is invalid") from None
        with FileLock(self.paths.lock):
            manifest = self.data.update_baostock(**kwargs)
        if manifest.get("no_change"):
            return manifest
        manifest["stale_models"] = self.registry.mark_models_stale_for_data(str(manifest["generation"]))
        self.bootstrap()
        return manifest

    def plan_data_update(self, **kwargs: Any) -> dict[str, Any]:
        """Build a read-only BaoStock update preview for GUI confirmation."""
        if kwargs.get("codes") is None:
            active_universe = self.registry.active_universe()
            if active_universe is not None and str(active_universe["mode"]) == UniverseMode.CUSTOM_UNIVERSE.value:
                try:
                    definition = json.loads(active_universe["definition"])
                    kwargs["codes"] = list(definition.get("codes", []))
                except (TypeError, json.JSONDecodeError):
                    raise ServiceError("active custom universe definition is invalid") from None
        return self.data.plan_baostock_update(**kwargs)

    def search_stocks(self, query: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.data.search_baostock(query, limit=limit)

    def universes(self) -> list[dict[str, Any]]:
        return [dict(row) | {"definition": json.loads(row["definition"])} for row in self.registry.list_universes()]

    def create_universe(
        self,
        name: str,
        mode: UniverseMode,
        codes: list[str],
        *,
        warning_ack: str | None = None,
        status_filter: str = "exclude_special",
        activate: bool = True,
    ) -> dict[str, Any]:
        definition = create_definition(name, mode, codes, warning_ack=warning_ack, status_filter=status_filter)
        universe_id = f"{mode.value.lower()}-{content_hash(definition)[:12]}"
        atomic_json(self.paths.universes / f"{universe_id}.json", {"id": universe_id, **definition})
        self.registry.put_universe(universe_id, name, mode.value, definition, active=activate)
        return {"id": universe_id, "name": name, "mode": mode.value, "definition": definition, "active": activate}

    def activate_universe(self, universe_id: str) -> None:
        self.registry.activate_universe(universe_id)

    def edit_custom_universe(
        self,
        universe_id: str,
        *,
        add_codes: list[str] | None = None,
        remove_codes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Atomically append/remove codes from a named custom universe.

        The definition is rewritten through the same canonicalizer used at
        creation time, so GUI, CLI, and future integrations share code
        normalization and the 100-stock product gate.
        """
        row = next((item for item in self.registry.list_universes() if str(item["id"]) == str(universe_id)), None)
        if row is None:
            raise ServiceError(f"universe not found: {universe_id}")
        if str(row["mode"]) != UniverseMode.CUSTOM_UNIVERSE.value:
            raise ServiceError("only CUSTOM_UNIVERSE can be edited")
        definition = json.loads(row["definition"])
        current = set(normalize_codes(definition.get("codes", [])))
        additions = set(normalize_codes(add_codes or []))
        removals = set(normalize_codes(remove_codes or []))
        next_codes = sorted((current | additions) - removals)
        try:
            updated = create_definition(
                str(definition.get("name", row["name"])),
                UniverseMode.CUSTOM_UNIVERSE,
                next_codes,
                warning_ack=definition.get("warning_ack"),
                status_filter=str(definition.get("status_filter", "exclude_special")),
            )
        except ValueError as exc:
            raise ServiceError(str(exc)) from exc
        atomic_json(self.paths.universes / f"{universe_id}.json", {"id": universe_id, **updated})
        self.registry.put_universe(
            str(universe_id),
            str(updated["name"]),
            UniverseMode.CUSTOM_UNIVERSE.value,
            updated,
            active=bool(row["active"]),
        )
        return {"id": universe_id, "mode": UniverseMode.CUSTOM_UNIVERSE.value, "definition": updated, "active": bool(row["active"])}

    def runs(self, limit: int = 20) -> list[dict[str, Any]]:
        return [dict(row) for row in self.registry.list_runs(limit)]

    def retention_preview(self, keep_successes: int = 5) -> list[dict[str, Any]]:
        return self.registry.cleanup_preview(keep_successes)

    def cleanup_retention(self, *, confirm: bool = False, keep_successes: int = 5) -> dict[str, Any]:
        candidates = self.retention_preview(keep_successes)
        if not confirm:
            return {"preview": candidates, "deleted": []}
        import shutil

        deleted = []
        for row in candidates:
            run_id = self._safe_run_id(str(row["id"]))
            shutil.rmtree(self.paths.results / run_id, ignore_errors=True)
            (self.paths.jobs / f"{run_id}.jsonl").unlink(missing_ok=True)
            deleted.append(run_id)
        return {"preview": candidates, "deleted": deleted}

    def job_events(self, run_id: str) -> list[dict[str, Any]]:
        return read_events(self.paths, self._safe_run_id(run_id))

    def cancel(self, run_id: str) -> None:
        run_id = self._safe_run_id(run_id)
        row = self.registry.run(run_id)
        if row is None:
            raise ServiceError(f"run not found: {run_id}")
        if str(row["state"]) not in {JobState.QUEUED.value, JobState.RUNNING.value}:
            raise ServiceError(f"run is already terminal: {row['state']}")
        context = JobContext(self.paths, run_id, emit_initial=False)
        context.request_cancel()

    def _active_route(self, mode: UniverseMode | None) -> tuple[UniverseMode, str, dict[str, Any]]:
        self.bootstrap()
        row = self.registry.active_universe()
        if row is None:
            raise ServiceError("create or import a universe before running a job")
        actual = UniverseMode(str(row["mode"]))
        if mode is not None and mode != actual:
            raise ServiceError(f"requested route {mode.value} differs from active universe {actual.value}")
        return actual, str(row["id"]), json.loads(row["definition"])

    def run(
        self,
        *,
        mode: UniverseMode | None = None,
        strategy: str = "balanced",
        label_contract: str = DEFAULT_LABEL,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run prepare → train → rank → atomic artifact publication."""
        if self.consent_status()["status"] != "CONFIRMED":
            raise ServiceError(f"先确认本地研究免责声明后再运行（quintara consent accept；版本 {CONSENT_VERSION}）")
        if strategy not in STRATEGIES:
            raise ServiceError(f"unknown strategy {strategy}; choose {', '.join(STRATEGIES)}")
        route, universe_id, definition = self._active_route(mode)
        bundle = self.data.active_bundle()
        market = cast(pd.DataFrame, bundle["market"])
        source_membership = cast(pd.DataFrame, bundle["membership"])
        listing = cast(pd.DataFrame, bundle["listing"])
        data_manifest = cast(dict[str, Any], bundle["manifest"])
        data_metadata = cast(dict[str, Any], data_manifest.get("metadata") or {})
        reference_profile = data_metadata.get("provider_dataset") == "quintara-developer-data-v1"
        if reference_profile:
            label_contract = COMPETITION_LABEL
        membership = source_membership if route == UniverseMode.PIT_BASELINE else membership_for_definition(definition, market["日期"].unique())  # type: ignore[index]
        if route != UniverseMode.PIT_BASELINE and definition.get("status_filter") == "exclude_special":
            excluded: set[str] = set()
            for column in ("is_st", "is_suspended"):
                if column in listing.columns:
                    values = listing[column].astype(str).str.lower()
                    excluded.update(listing.loc[values.isin({"1", "true", "yes", "y", "st"}), "stock_id"].astype(str))
            for column in ("status", "trade_status"):
                if column in listing.columns:
                    values = listing[column].astype(str).str.lower()
                    excluded.update(listing.loc[values.str.contains("st|suspend|delist", regex=True), "stock_id"].astype(str))
            if excluded:
                membership = membership[~membership["stock_id"].astype(str).isin(excluded)].copy()
        if int(membership["stock_id"].nunique()) < 100:
            raise ServiceError("活动股票池清单少于100只；请补足股票或显式切换研究路线")
        starts = pd.to_datetime(membership["start_date"], errors="coerce")
        ends = pd.to_datetime(membership["end_date"], errors="coerce")
        minimum_slice = min(
            int(membership[(starts <= stamp) & (ends.isna() | (ends >= stamp))]["stock_id"].nunique())
            for stamp in pd.to_datetime(market["日期"].unique())
        )
        if minimum_slice < 100:
            raise ServiceError(f"历史截面最少仅 {minimum_slice} 只有效股票；训练要求每个截面至少100只")
        cfg = default_model_config()
        cfg.update(STRATEGIES[strategy])
        requested_config = config or {}
        allowed_overrides = {"device", "lgbm_num_threads", "training_years"}
        unsupported = sorted(set(requested_config) - allowed_overrides)
        cfg.update(requested_config)
        if unsupported:
            cfg["unsupported_experiment_overrides"] = unsupported
        device = str(cfg.get("device", "cpu")).lower()
        if device not in {"cpu", "gpu"}:
            raise ServiceError("device must be cpu or gpu")
        if device == "gpu":
            gpu = self.doctor().get("gpu", {})
            if not gpu.get("available"):
                raise ServiceError("GPU experimental path requires a visible NVIDIA device; CPU remains authoritative")
            cfg["lgbm_device_type"] = "gpu"
        else:
            cfg["lgbm_device_type"] = "cpu"
        cfg["portfolio_rank_weights"] = list(DEFAULT_WEIGHTS)
        cfg["pit_expected_members"] = (
            int(default_model_config().get("pit_expected_members", 300))
            if reference_profile and route == UniverseMode.PIT_BASELINE
            else int(membership["stock_id"].nunique())
        )
        years = int(cfg.get("training_years", 5))
        if years < 3 or years > 10:
            raise ServiceError("training_years must be between 3 and 10")
        cached = self._find_cached_run(
            data_generation=str(data_manifest["generation"]),
            route=route,
            universe_id=universe_id,
            strategy=strategy,
            label_contract=label_contract,
            config=cfg,
        )
        if cached is not None:
            return self._record_cached_run(cached, route, universe_id, data_manifest)
        run_id = new_id("run")
        self._active_run_id = run_id
        self.registry.start_run(run_id, route.value, universe_id, str(self.paths.jobs / f"{run_id}.jsonl"))
        context = JobContext(self.paths, run_id)
        try:
            with FileLock(self.paths.lock):
                context.emit("preparing", "KERNEL_PREPARE", "正在检查数据和标签")
                context.checkpoint("preparing")
                prepared = prepare(market, membership, listing, mode=route, config=cfg, contract=label_contract)
                if reference_profile:
                    prepared.report["training_years"] = "all_available"
                    prepared.report["reference_profile"] = "bigdata-result-v1"
                else:
                    window_start = prepared.cutoff - pd.DateOffset(years=years)
                    prepared.frame = prepared.frame[pd.to_datetime(prepared.frame["日期"]) >= window_start].copy()
                    prepared.report["training_years"] = years
                context.emit("training", "KERNEL_TRAIN", "正在训练模型")
                context.checkpoint("training")
                model = train(prepared, mode=route, universe_id=universe_id, config=cfg, source_hash=kernel_source_hash())
                context.emit("predicting", "KERNEL_PREDICT", "正在生成候选排名")
                context.checkpoint("predicting")
                result, ranking = predict(model)
                if reference_profile:
                    expected = pd.DataFrame(data_metadata.get("reference_result") or [])
                    if list(expected.columns) != ["stock_id", "weight"]:
                        raise ServiceError("开发者数据缺少有效的参考结果闭包")
                    expected["stock_id"] = expected["stock_id"].astype(str).str.zfill(6)
                    expected["weight"] = pd.to_numeric(expected["weight"], errors="raise")
                    actual = result[["stock_id", "weight"]].copy()
                    actual["stock_id"] = actual["stock_id"].astype(str).str.zfill(6)
                    actual["weight"] = pd.to_numeric(actual["weight"], errors="raise")
                    if actual.to_dict(orient="records") != expected.to_dict(orient="records"):
                        raise ServiceError(
                            "开发者数据训练结果与参考结果不一致："
                            f"actual={actual.to_dict(orient='records')} expected={expected.to_dict(orient='records')}"
                        )
                    expected_hash = str(data_metadata.get("reference_result_sha256") or "")
                    actual_hash = content_hash(actual.to_csv(index=False).encode("utf-8"))
                    if expected_hash and actual_hash != expected_hash:
                        raise ServiceError(
                            f"开发者数据结果哈希不一致：{actual_hash} != {expected_hash}"
                        )
                    prepared.report["reference_result_match"] = True
                    prepared.report["reference_result_sha256"] = actual_hash
                context.emit("publishing", "ARTIFACT_PUBLISH", "正在发布结果")
                context.checkpoint("publishing")
                artifact = self._publish_artifacts(run_id, route, universe_id, strategy, cfg, prepared, model, result, ranking, data_manifest, listing)
                context.emit("succeeded", "JOB_SUCCEEDED", "训练和预测已完成", Severity.PASS, 1.0)
                context.finish()
            self.registry.finish_run(run_id, JobState.SUCCEEDED.value, data_generation=data_manifest["generation"], model_generation=artifact["model_generation"], result_generation=artifact["result_generation"], stage="succeeded", progress=1.0)
            return artifact
        except JobCancelled as exc:
            context.emit("cancelled", "JOB_CANCELLED", "作业已取消", Severity.WARNING)
            context.finish()
            self.registry.finish_run(run_id, JobState.CANCELLED.value, error=str(exc), stage="cancelled")
            raise ServiceError("作业已取消") from exc
        except Exception as exc:
            LOG.exception("Quintara run %s failed", run_id)
            context.emit("failed", "JOB_FAILED", str(exc), Severity.FAIL)
            context.finish()
            self.registry.finish_run(run_id, JobState.FAILED.value, error=str(exc), stage="failed")
            raise
        finally:
            self._active_run_id = None

    @property
    def active_run_id(self) -> str | None:
        return self._active_run_id

    def cancel_active(self) -> str | None:
        if self._active_run_id:
            self.cancel(self._active_run_id)
        return self._active_run_id

    def _publish_artifacts(
        self,
        run_id: str,
        route: UniverseMode,
        universe_id: str,
        strategy: str,
        config: dict[str, Any],
        prepared: PreparedData,
        model: TrainedModel,
        result: pd.DataFrame,
        ranking: pd.DataFrame,
        data_manifest: dict[str, Any],
        listing: pd.DataFrame,
    ) -> dict[str, Any]:
        staging_root = self.paths.results_staging / run_id
        root = staging_root
        root.mkdir(parents=True, exist_ok=False)
        model_generation = f"model-{content_hash(model.identity.as_dict())[:16]}"
        result_generation = f"result-{content_hash({'identity': model.identity.as_dict(), 'ids': result['stock_id'].tolist(), 'weights': result['weight'].tolist()})[:24]}"
        model_path = self.paths.models / f"{model_generation}.txt"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model.booster.save_model(str(model_path))
        result.to_csv(root / "result.csv", index=False)
        ranking.to_csv(root / "ranking.csv", index=False)
        listing_view = listing.copy()
        listing_view["stock_id"] = listing_view["stock_id"].astype(str).str.extract(r"(\d{6})")[0].str.zfill(6)
        name_column = next((column for column in ("name", "stock_name", "code_name") if column in listing_view.columns), None)
        metadata_columns = ["stock_id", "exchange", "status", "trade_status", "is_st", "is_suspended"] + ([name_column] if name_column else [])
        metadata_view = listing_view[[column for column in metadata_columns if column in listing_view.columns]].drop_duplicates("stock_id")
        result_view = result.merge(ranking[["stock_id", "prediction", "predicted_rank"]], on="stock_id", how="left")
        result_view = result_view.merge(metadata_view, on="stock_id", how="left")
        result_view.to_json(root / "result_view.json", orient="records", force_ascii=False, indent=2)
        explanations: dict[str, list[dict[str, Any]]] = {}
        cutoff_rows = prepared.frame[prepared.frame["日期"] == prepared.cutoff]
        for stock_id in result["stock_id"].astype(str).str.zfill(6):
            row = cutoff_rows[cutoff_rows["股票代码"].astype(str).str.zfill(6) == stock_id]
            if not row.empty:
                try:
                    explanations[stock_id] = feature_contributions(model.booster, row.iloc[[0]], prepared.features)
                except Exception as exc:  # attribution must not block an otherwise verified result
                    explanations[stock_id] = [{"feature": "unavailable", "contribution": None, "message": str(exc)}]
        atomic_json(root / "explanations.json", explanations)
        atomic_json(root / "identity.json", model.identity.as_dict())
        atomic_json(root / "prepared_report.json", prepared.report)
        atomic_json(root / "runtime.json", asdict(runtime_identity()) | {"application": app_version(), "strategy": strategy})
        manifest = {
            "schema_version": 1,
            "run_id": run_id,
            "status": JobState.SUCCEEDED.value,
            "created_at": now_utc(),
            "route": route.value,
            "universe_id": universe_id,
            "strategy": strategy,
            "strategy_policy": STRATEGY_POLICIES[strategy],
            "label_contract": prepared.report["label_contract"],
            "data_generation": data_manifest["generation"],
            "model_generation": model_generation,
            "result_generation": result_generation,
            "model_identity": model.identity.as_dict(),
            "metrics": model.metrics,
            "files": {"result": "result.csv", "result_view": "result_view.json", "ranking": "ranking.csv", "explanations": "explanations.json", "identity": "identity.json", "prepared_report": "prepared_report.json", "runtime": "runtime.json", "model": str(Path("models") / model_path.name)},
            "config": config,
            "provenance": {
                "source": data_manifest.get("source"),
                "metadata": data_manifest.get("metadata", {}),
                "data_created_at": data_manifest.get("created_at"),
                "data_date_min": data_manifest.get("date_min"),
                "data_date_max": data_manifest.get("date_max"),
                "consent_version": CONSENT_VERSION,
            },
        }
        atomic_json(root / "manifest.json", manifest)
        final_root = self.paths.results / run_id
        if final_root.exists():
            raise ServiceError(f"result generation already exists: {run_id}")
        staging_root.rename(final_root)
        root = final_root
        self.registry.put_generation(model_generation, "model", manifest, mode=route.value, universe_id=universe_id)
        self.registry.put_generation(result_generation, "result", manifest, mode=route.value, universe_id=universe_id)
        return {"run_id": run_id, "result_generation": result_generation, "model_generation": model_generation, "result": result.to_dict(orient="records"), "ranking": ranking.to_dict(orient="records"), "explanations": explanations, "manifest": manifest, "cached": False}

    def _find_cached_run(
        self,
        *,
        data_generation: str,
        route: UniverseMode,
        universe_id: str,
        strategy: str,
        label_contract: str,
        config: dict[str, Any],
    ) -> dict[str, Any] | None:
        for row in self.registry.list_runs(100):
            if str(row["state"]) != JobState.SUCCEEDED.value or not row["result_generation"]:
                continue
            run_id = str(row["id"])
            try:
                manifest = self.result_manifest(run_id)
            except (OSError, ServiceError, json.JSONDecodeError):
                continue
            if (
                manifest.get("data_generation") == data_generation
                and manifest.get("route") == route.value
                and manifest.get("universe_id") == universe_id
                and manifest.get("strategy") == strategy
                and manifest.get("label_contract") == label_contract
                and content_hash(manifest.get("config", {})) == content_hash(config)
            ):
                return {"run_id": run_id, "manifest": manifest}
        return None

    def _record_cached_run(self, cached: dict[str, Any], route: UniverseMode, universe_id: str, data_manifest: dict[str, Any]) -> dict[str, Any]:
        run_id = new_id("run")
        events_path = str(self.paths.jobs / f"{run_id}.jsonl")
        self.registry.start_run(run_id, route.value, universe_id, events_path)
        context = JobContext(self.paths, run_id)
        context.emit("cached", "JOB_CACHE_HIT", "当前数据和模型均匹配，复用已验证结果", Severity.PASS, 1.0, source_run=cached["run_id"])
        context.finish()
        manifest = cast(dict[str, Any], cached["manifest"])
        self.registry.finish_run(
            run_id,
            JobState.CACHED.value,
            data_generation=data_manifest["generation"],
            model_generation=manifest.get("model_generation"),
            result_generation=manifest.get("result_generation"),
            stage="cached",
            progress=1.0,
        )
        source_root = self.paths.results / str(cached["run_id"])
        explanation_path = source_root / "explanations.json"
        return {
            "run_id": run_id,
            "source_run_id": cached["run_id"],
            "result_generation": manifest.get("result_generation"),
            "model_generation": manifest.get("model_generation"),
            "result": pd.read_csv(source_root / "result.csv").to_dict(orient="records"),
            "ranking": pd.read_csv(source_root / "ranking.csv").to_dict(orient="records"),
            "explanations": json.loads(explanation_path.read_text(encoding="utf-8")) if explanation_path.exists() else {},
            "manifest": manifest,
            "cached": True,
        }

    def result_manifest(self, run_id: str) -> dict[str, Any]:
        run_id = self._safe_run_id(run_id)
        path = self.paths.results / run_id / "manifest.json"
        if not path.exists():
            raise ServiceError(f"run not found: {run_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def result_details(self, run_id: str) -> dict[str, Any]:
        run_id = self._safe_run_id(run_id)
        manifest = self.result_manifest(run_id)
        result_path = self.paths.results / run_id / "result.csv"
        result = pd.read_csv(result_path)
        data_root = self.paths.data_generations / str(manifest["data_generation"])
        market = pd.read_csv(data_root / "market.csv", parse_dates=["日期"])
        cutoff = cast(pd.Timestamp, pd.Timestamp(manifest["model_identity"]["training_cutoff"]))
        stock_ids = result["stock_id"].astype(str).str.zfill(6).tolist()
        return {
            "manifest": manifest,
            "risk": {stock_id: risk_metrics(market, stock_id, cutoff) for stock_id in stock_ids},
            "correlation": correlation_matrix(market, stock_ids, cutoff),
            "result_view": json.loads((self.paths.results / run_id / "result_view.json").read_text(encoding="utf-8")) if (self.paths.results / run_id / "result_view.json").exists() else [],
            "explanations": json.loads((self.paths.results / run_id / "explanations.json").read_text(encoding="utf-8")) if (self.paths.results / run_id / "explanations.json").exists() else {},
            "identity_badge": manifest.get("route"),
            "pit_warning": "当前结果使用静态成员回看，存在幸存者偏差。" if manifest.get("route") == UniverseMode.NON_PIT_FALLBACK.value else None,
            "disclaimer": "模型排名和特征影响用于研究，不是因果证明或交易指令。",
        }

    def export_result(self, run_id: str, output: str | Path | None = None, *, overwrite: bool = False) -> dict[str, Any]:
        run_id = self._safe_run_id(run_id)
        manifest = self.result_manifest(run_id)
        source = self.paths.results / run_id / "result.csv"
        destination = Path(output) if output else Path.cwd() / f"quintara-{run_id}.csv"
        if destination.exists() and not overwrite:
            raise ServiceError("export destination exists; confirm overwrite explicitly")
        destination.parent.mkdir(parents=True, exist_ok=True)
        frame = pd.read_csv(source, dtype={"stock_id": str})
        frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(6)
        frame["research_only"] = True
        frame["risk_notice"] = "研究排序，不是收益保证或交易指令"
        frame["mode"] = manifest.get("route")
        from .platform import atomic_write

        atomic_write(destination, frame.to_csv(index=False).encode("utf-8"))
        provenance = destination.with_suffix(destination.suffix + ".manifest.json")
        export_manifest = manifest | {"export_sha256": content_hash(destination.read_bytes()), "exported_at": now_utc()}
        atomic_json(provenance, export_manifest)
        return {"result_csv": str(destination), "provenance_manifest": str(provenance), "columns": list(frame.columns), "sha256": export_manifest["export_sha256"], "uploaded": False}

    def export_diagnostics(self, output: str | Path | None = None) -> dict[str, Any]:
        report = {"doctor": self.doctor(), "bootstrap": self.bootstrap(), "runs": self.runs(20), "consent": self.consent_status()}
        root = str(self.paths.root)

        def redact(value: Any) -> Any:
            if isinstance(value, dict):
                return {key: redact(item) for key, item in value.items()}
            if isinstance(value, list):
                return [redact(item) for item in value]
            if isinstance(value, str):
                return re.sub(re.escape(root), "<DATA_ROOT>", value).replace(str(Path.home()), "<HOME>")
            return value

        result = redact(report)
        destination = Path(output) if output else self.paths.diagnostics / f"diagnostics-{new_id('bundle')}.json"
        included = ["doctor", "bootstrap", "runs", "consent"]
        if destination.suffix.lower() == ".zip":
            import zipfile

            destination.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("diagnostics.json", json.dumps(result, ensure_ascii=False, indent=2, default=str))
                archive.writestr("README.txt", "Quintara 本地脱敏诊断；未包含原始行情 CSV，也不会自动上传。\n")
            return {"path": str(destination), "included": [*included, "README.txt"], "uploaded": False}
        atomic_json(destination, result)
        return {"path": str(destination), "included": included, "uploaded": False}

    def version_info(self, *, check: bool = False) -> dict[str, Any]:
        enabled = bool(self.registry.setting("version_check_enabled", False))
        result: dict[str, Any] = {"current": app_version(), "checked": False, "network": "disabled", "enabled": enabled}
        if not check:
            return result
        url = "https://api.github.com/repos/Telecaster2147/quintara/releases/latest"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 - fixed allowlisted URL
                payload = json.loads(response.read().decode("utf-8"))
            result.update({"checked": True, "network": "github", "latest": payload.get("tag_name"), "url": payload.get("html_url")})
        except Exception as exc:  # network status is an informational probe
            result.update({"checked": True, "network": "error", "error": str(exc)})
        return result

    def set_version_check(self, enabled: bool) -> dict[str, Any]:
        self.registry.set_setting("version_check_enabled", bool(enabled))
        return self.version_info(check=False)
