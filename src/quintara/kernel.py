"""Adapter around the authoritative app kernel with a versioned product label."""
from __future__ import annotations

import hashlib
import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from .core import (
    COMPETITION_LABEL,
    COMPETITION_LABEL_VERSION,
    DEFAULT_LABEL,
    DEFAULT_WEIGHTS,
    PRODUCT_LABEL_VERSION,
    ModelIdentity,
    UniverseMode,
    content_hash,
    file_hash,
)

SOURCE_ROOT = Path("/home/olm/bigdata/bigdata/app/code/src")


def _source_modules() -> tuple[Any, Any, Any]:
    """Load the vendored kernel in installed builds, source modules in development.

    The source tree remains the authority during development; the package ships a
    copy so a user does not need the competition checkout on their machine.
    """
    try:
        data = importlib.import_module("quintara._kernel.data")
        utils = importlib.import_module("quintara._kernel.utils")
        return data, utils, None
    except ModuleNotFoundError:
        pass
    source = str(SOURCE_ROOT)
    if source not in sys.path:
        sys.path.insert(0, source)
    data = importlib.import_module("data")
    utils = importlib.import_module("utils")
    config = importlib.import_module("config")
    return data, utils, config


@dataclass
class PreparedData:
    frame: pd.DataFrame
    features: list[str]
    cutoff: pd.Timestamp
    report: dict[str, Any]
    market_hash: str


@dataclass
class TrainedModel:
    booster: Any
    prepared: PreparedData
    identity: ModelIdentity
    metrics: dict[str, Any]


def default_model_config() -> dict[str, Any]:
    bundled = Path(__file__).with_name("model_config.json")
    source_path = Path("/home/olm/bigdata/bigdata/app/model/model_config.json")
    config_path = bundled if bundled.exists() else source_path
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    config.update({"lgbm_label_mode": "competition", "lgbm_selection_mode": "fixed_rounds", "lgbm_fixed_rounds": int(config.get("lgbm_fixed_rounds", 128)), "portfolio_rank_weights": list(DEFAULT_WEIGHTS)})
    return config


def kernel_source_hash() -> str:
    """Hash the vendored source closure and frozen model config."""
    files = [Path(__file__), Path(__file__).with_name("model_config.json"), Path(__file__).parent / "_kernel" / "data.py", Path(__file__).parent / "_kernel" / "utils.py"]
    return content_hash({str(path.name): content_hash(path) for path in files if path.exists()})


def _market_bytes(market: pd.DataFrame) -> bytes:
    ordered = market.sort_values(["股票代码", "日期"]).copy()
    return ordered.to_csv(index=False, date_format="%Y-%m-%d").encode()


def _apply_product_label(frame: pd.DataFrame, market: pd.DataFrame, *, contract: str) -> pd.DataFrame:
    result = frame.copy().sort_values(["股票代码", "日期"]).reset_index(drop=True)
    calendar = {cast(pd.Timestamp, pd.Timestamp(value)).normalize(): idx for idx, value in enumerate(sorted(pd.to_datetime(market["日期"]).dt.normalize().unique()))}
    result["label"] = np.nan
    result["label_t1_date"] = pd.NaT
    result["label_t5_date"] = pd.NaT
    result["label_end_date"] = pd.NaT
    result["label_gap_free"] = False
    result["open_t1"] = np.nan
    result["close_t5"] = np.nan
    for _, indices in result.groupby("股票代码", sort=False).groups.items():
        idx = list(indices)
        group = result.loc[idx].sort_values("日期")
        dates = pd.to_datetime(group["日期"]).dt.normalize()
        positions = dates.map(calendar).to_numpy()
        gap = np.r_[np.diff(positions), [999]]
        t1 = pd.to_numeric(group["开盘"], errors="coerce").shift(-1).to_numpy()
        t5 = pd.to_numeric(group["收盘"], errors="coerce").shift(-5).to_numpy()
        d1 = dates.shift(-1).to_numpy()
        d5 = dates.shift(-5).to_numpy()
        five_step = np.r_[positions[5:] - positions[:-5], np.repeat(999, 5)]
        valid = (gap == 1) & (five_step == 5) & np.isfinite(t1) & np.isfinite(t5) & (t1 > 1e-4) & (t5 > 1e-4)
        if contract == COMPETITION_LABEL:
            t5 = pd.to_numeric(group["开盘"], errors="coerce").shift(-5).to_numpy()
        labels = np.where(valid, (t5 - t1) / (t1 + 1e-12), np.nan)
        result.loc[group.index, "label"] = labels
        result.loc[group.index, "label_t1_date"] = d1
        result.loc[group.index, "label_t5_date"] = d5
        result.loc[group.index, "label_end_date"] = d5
        result.loc[group.index, "label_gap_free"] = valid
        result.loc[group.index, "open_t1"] = t1
        result.loc[group.index, "close_t5"] = t5
    return result.sort_values(["日期", "股票代码"]).reset_index(drop=True)


def prepare(market: pd.DataFrame, membership: pd.DataFrame, listing: pd.DataFrame, *, mode: UniverseMode, config: dict[str, Any] | None = None, contract: str = DEFAULT_LABEL) -> PreparedData:
    data, _, _ = _source_modules()
    cfg = default_model_config()
    cfg.update(config or {})
    cfg["pit_expected_members"] = int(membership["stock_id"].nunique())
    # The source production gate currently recognizes its historical member file as CSI300.
    membership = membership.copy()
    membership["index_code"] = "CSI300"
    prepared_frame, features, cutoff, report = data.prepare_model_data(market, membership, listing, cfg)
    frame = _apply_product_label(prepared_frame, market, contract=contract)
    report = dict(report)
    report.update({"route": mode.value, "label_contract": contract, "label_version": PRODUCT_LABEL_VERSION if contract == DEFAULT_LABEL else COMPETITION_LABEL_VERSION, "kernel_version": PRODUCT_LABEL_VERSION if contract == DEFAULT_LABEL else COMPETITION_LABEL_VERSION, "membership_hash": content_hash(membership.to_dict(orient="records")), "listing_hash": content_hash(listing.to_dict(orient="records")), "calendar_hash": content_hash(sorted(pd.to_datetime(market["日期"]).dt.normalize().astype(str).unique().tolist()))})
    return PreparedData(frame, features, cutoff, report, hashlib.sha256(_market_bytes(market)).hexdigest())


def train(prepared: PreparedData, *, mode: UniverseMode, universe_id: str, config: dict[str, Any] | None = None, source_hash: str = "local") -> TrainedModel:
    _, utils, _ = _source_modules()
    cfg = default_model_config()
    cfg.update(config or {})
    known = prepared.frame.dropna(subset=["label", "label_end_date"]).copy()
    known["label_end_date"] = pd.to_datetime(known["label_end_date"])
    known = known[known["label_end_date"] <= prepared.cutoff]
    if known.empty:
        raise ValueError("no labelled rows available for training")
    rounds = int(cfg.get("lgbm_fixed_rounds", 16 if len(known) < 2000 else 128))
    # Small user fixtures need a lower leaf floor while preserving the frozen default for real data.
    if len(known) < int(cfg.get("lgbm_min_data_in_leaf", 500)) * 2:
        cfg["lgbm_min_data_in_leaf"] = max(5, min(50, len(known) // 10))
    booster = utils.fit_regressor_fixed_rounds(known, prepared.features, cfg, rounds)
    source_payload = {"source": source_hash, "config": cfg, "features": prepared.features, "mode": mode.value}
    lock_path = Path(__file__).parents[2] / "uv.lock"
    runtime_lock = file_hash(lock_path) if lock_path.exists() else content_hash({"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__})
    kernel_version = prepared.report["kernel_version"] + ("-experiment" if cfg.get("unsupported_experiment_overrides") else "")
    identity = ModelIdentity(1, mode, universe_id, content_hash({"universe": universe_id}), prepared.market_hash, str(prepared.report.get("membership_hash", "")), str(prepared.report.get("listing_hash", "")), str(prepared.report.get("calendar_hash", "")), prepared.report["label_contract"], content_hash(prepared.features), kernel_version, content_hash(source_payload), content_hash(cfg), str(known["日期"].min().date()), str(prepared.cutoff.date()), runtime_lock, str(cfg.get("device", "cpu")))
    return TrainedModel(booster, prepared, identity, {"train_rows": len(known), "rounds": rounds, "label_contract": prepared.report["label_contract"]})


def predict(model: TrainedModel) -> tuple[pd.DataFrame, pd.DataFrame]:
    _, utils, _ = _source_modules()
    rows = model.prepared.frame[model.prepared.frame["日期"] == model.prepared.cutoff].copy()
    if rows.empty:
        raise ValueError("no cutoff rows")
    ranking = utils.predict_ranking(model.booster, rows, model.prepared.features)
    ranking["stock_id"] = ranking["stock_id"].astype(str).str.zfill(6)
    config = default_model_config()
    config["portfolio_rank_weights"] = list(DEFAULT_WEIGHTS)
    result, ranking = utils.build_portfolio(ranking, config)
    utils.validate_result(result)
    if len(result) != 5 or result["stock_id"].astype(str).str.zfill(6).nunique() != 5:
        raise ValueError("stable portfolio must contain exactly five distinct stocks")
    weights = pd.to_numeric(result["weight"], errors="coerce")
    if not np.isfinite(weights).all() or not np.isclose(float(weights.sum()), 1.0, rtol=0.0, atol=1e-12):
        raise ValueError("stable portfolio weights must be finite and sum to one")
    return result, ranking
