"""Offline point-in-time data preparation for training and prediction.

The competition contract defines the label as raw open(T+5) / raw open(T+1)
minus one.  Feature price scaling is independent from that label contract: the
technical features may use the reported-return path, while the label always
uses the supplied raw open prices.  Historical rows outside the active
CSI300 universe may provide a legally listed stock's own lag history, but
only complete 300-member dates are sent to cross-sectional training or
cutoff prediction.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .utils import LGBM_FEATURE_COLUMNS, build_feature_frame

RAW_COLUMNS = (
    "开盘",
    "收盘",
    "最高",
    "最低",
    "成交量",
    "成交额",
    "振幅",
    "涨跌额",
    "换手率",
    "涨跌幅",
)
CRITICAL_COLUMNS = ("开盘", "收盘", "最高", "最低")
MARKET_KEYS = ("股票代码", "日期")
FEATURE_DROP = ("return_5", "reversal_5")


def load_listing_basic(path: Path) -> pd.DataFrame:
    """Load the bundled BaoStock code/IPO/out-date snapshot."""
    raw = pd.read_csv(path, dtype={"code": str})
    required = {"code", "ipoDate", "outDate"}
    if not required.issubset(raw.columns):
        raise ValueError(f"listing basic columns missing: {sorted(required - set(raw.columns))}")
    stock_id = raw["code"].astype("string").str.extract(r"\.(\d+)$")[0]
    frame = pd.DataFrame(
        {"stock_id": stock_id, "ipo_date": raw["ipoDate"], "out_date": raw["outDate"]}
    )
    frame["stock_id"] = frame["stock_id"].astype("string").str.strip()
    if frame["stock_id"].isna().any() or not frame["stock_id"].str.fullmatch(r"\d{6}").all():
        raise ValueError("listing basic contains non-six-digit codes")
    frame["stock_id"] = frame["stock_id"].astype(str)
    frame["ipo_date"] = pd.to_datetime(frame["ipo_date"], errors="raise").dt.normalize()
    frame["out_date"] = pd.to_datetime(frame["out_date"], errors="coerce").dt.normalize()
    if frame["stock_id"].duplicated().any():
        raise ValueError("listing basic contains duplicate stock IDs")
    if (frame["out_date"].notna() & (frame["out_date"] < frame["ipo_date"])).any():
        raise ValueError("listing basic contains out_date before ipo_date")
    return frame.set_index("stock_id")


def _normalise_market(market: pd.DataFrame) -> pd.DataFrame:
    required = set(MARKET_KEYS) | set(RAW_COLUMNS)
    missing = sorted(required - set(market.columns))
    if missing:
        raise ValueError(f"market columns missing: {missing}")
    frame = market.copy()
    codes = frame["股票代码"].astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    if codes.isna().any() or not codes.str.fullmatch(r"\d{6}").all():
        raise ValueError("market stock IDs must be exactly six digits")
    frame["股票代码"] = codes.astype(str)
    frame["日期"] = pd.to_datetime(frame["日期"], errors="raise").dt.normalize()
    if frame.duplicated(list(MARKET_KEYS)).any():
        raise ValueError("market data contains duplicate stock/date keys")
    for column in RAW_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values(list(MARKET_KEYS)).reset_index(drop=True)


def _normalise_membership(membership: pd.DataFrame) -> pd.DataFrame:
    required = {"stock_id", "index_code", "start_date", "end_date"}
    missing = sorted(required - set(membership.columns))
    if missing:
        raise ValueError(f"membership columns missing: {missing}")
    frame = membership.copy()
    frame["stock_id"] = frame["stock_id"].astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    if frame["stock_id"].isna().any() or not frame["stock_id"].str.fullmatch(r"\d{6}").all():
        raise ValueError("membership stock IDs must be exactly six digits")
    frame["stock_id"] = frame["stock_id"].astype(str)
    frame["index_code"] = frame["index_code"].astype(str)
    frame["start_date"] = pd.to_datetime(frame["start_date"], errors="raise").dt.normalize()
    frame["end_date"] = pd.to_datetime(frame["end_date"], errors="coerce").dt.normalize()
    frame = frame[frame["index_code"] == "CSI300"].copy()
    if (frame["end_date"].notna() & (frame["end_date"] < frame["start_date"])).any():
        raise ValueError("membership end_date precedes start_date")
    for stock_id, group in frame.sort_values(["stock_id", "start_date"]).groupby("stock_id", sort=True):
        previous_end = None
        for row in group.itertuples(index=False):
            if previous_end is not None and (pd.isna(previous_end) or row.start_date <= previous_end):
                raise ValueError(f"overlapping membership intervals: {stock_id}")
            previous_end = row.end_date
    return frame


def _active_set(membership: pd.DataFrame, date: pd.Timestamp) -> set[str]:
    date = pd.Timestamp(date).normalize()
    rows = membership[
        (membership["start_date"] <= date)
        & (membership["end_date"].isna() | (membership["end_date"] >= date))
    ]
    return set(rows["stock_id"])


def _engineer_segment(
    segment: pd.DataFrame,
    feature_price_scale_mode: str,
    calendar: dict[pd.Timestamp, int],
) -> pd.DataFrame:
    engineered, _ = build_feature_frame(
        segment,
        feature_drop=list(FEATURE_DROP),
        price_scale_mode=feature_price_scale_mode,
        label_mode="competition",
    )
    engineered = engineered.reset_index(drop=True)
    dates = pd.to_datetime(segment["日期"], errors="raise").dt.normalize().reset_index(drop=True)
    date_index = dates.map(calendar)
    engineered["label_t1_date"] = dates.shift(-1)
    engineered["label_t5_date"] = dates.shift(-5)
    engineered["label_t1_step"] = date_index.shift(-1) - date_index
    engineered["label_t5_step"] = date_index.shift(-5) - date_index
    engineered["label_gap_free"] = engineered["label_t1_step"].eq(1) & engineered["label_t5_step"].eq(5)

    # Official competition label: raw open at T+5 divided by raw open at T+1.
    raw_open = pd.to_numeric(segment["开盘"], errors="coerce").reset_index(drop=True)
    open_t1 = raw_open.shift(-1)
    open_t5 = raw_open.shift(-5)
    valid = open_t1.gt(1e-4) & open_t5.gt(1e-4) & engineered["label_gap_free"]
    engineered["open_t1"] = open_t1
    engineered["open_t5"] = open_t5
    engineered["label_end_date"] = engineered["label_t5_date"]
    engineered["label"] = np.where(valid, (open_t5 - open_t1) / (open_t1 + 1e-12), np.nan)
    return engineered


def _build_history(
    market: pd.DataFrame,
    history_mask: np.ndarray,
    feature_price_scale_mode: str,
    calendar: dict[pd.Timestamp, int],
) -> tuple[pd.DataFrame, dict]:
    history = market.loc[history_mask].copy()
    if history.empty:
        raise ValueError("no legal critical-valid history remains")
    parts: list[pd.DataFrame] = []
    segment_count = 0
    gap_breaks = 0
    for _, group in history.groupby("股票代码", sort=False):
        group = group.sort_values("日期").reset_index(drop=True)
        positions = [calendar[pd.Timestamp(value).normalize()] for value in group["日期"]]
        boundaries = [0]
        for index in range(1, len(group)):
            if positions[index] != positions[index - 1] + 1:
                boundaries.append(index)
                gap_breaks += 1
        boundaries.append(len(group))
        for left, right in zip(boundaries[:-1], boundaries[1:], strict=True):
            segment = group.iloc[left:right].copy().reset_index(drop=True)
            if not segment.empty:
                parts.append(_engineer_segment(segment, feature_price_scale_mode, calendar))
                segment_count += 1
    if not parts:
        raise ValueError("history segmentation produced no rows")
    return pd.concat(parts, ignore_index=True), {
        "feature_segments": int(segment_count),
        "trading_gap_breaks": int(gap_breaks),
    }


def prepare_model_data(
    market: pd.DataFrame,
    membership: pd.DataFrame,
    listing_basic: pd.DataFrame,
    model_config: dict | None = None,
) -> tuple[pd.DataFrame, list[str], pd.Timestamp, dict]:
    """Construct the production PIT frame and its auditable quality report."""
    config = dict(model_config or {})
    expected_members = int(config.get("pit_expected_members", 300))
    if expected_members <= 0:
        raise ValueError("pit_expected_members must be positive")
    market = _normalise_market(market)
    membership = _normalise_membership(membership)
    if listing_basic is None:
        raise ValueError("production PIT frame requires listing basic data")
    basic = listing_basic.copy()
    if "stock_id" not in basic.columns and basic.index.name == "stock_id":
        basic = basic.reset_index()
    basic["stock_id"] = basic["stock_id"].astype(str).str.zfill(6)
    basic["ipo_date"] = pd.to_datetime(basic["ipo_date"], errors="raise").dt.normalize()
    basic["out_date"] = pd.to_datetime(basic["out_date"], errors="coerce").dt.normalize()
    basic = basic.set_index("stock_id")
    cutoff = pd.Timestamp(market["日期"].max()).normalize()
    codes = set(market["股票代码"])
    if not codes.issubset(set(basic.index)):
        raise ValueError(f"listing basic missing market codes: {sorted(codes - set(basic.index))[:20]}")

    ipo = market["股票代码"].map(basic["ipo_date"])
    out = market["股票代码"].map(basic["out_date"])
    legal = (market["日期"] >= ipo).to_numpy() & (out.isna() | (market["日期"] <= out)).to_numpy()
    critical = market[list(CRITICAL_COLUMNS)].notna().all(axis=1).to_numpy()
    critical &= (market[list(CRITICAL_COLUMNS)] > 0).all(axis=1).to_numpy()
    history_mask = legal & critical
    calendar = {
        pd.Timestamp(value).normalize(): index
        for index, value in enumerate(sorted(pd.to_datetime(market["日期"]).dt.normalize().unique()))
    }

    active_mask = np.zeros(len(market), dtype=bool)
    valid_dates: set[pd.Timestamp] = set()
    date_contract: list[dict] = []
    for date, group in market.groupby("日期", sort=True):
        date = pd.Timestamp(date).normalize()
        active = _active_set(membership, date)
        ids = set(group["股票代码"])
        active_rows = group["股票代码"].isin(active).to_numpy()
        active_mask[group.index.to_numpy()] = active_rows
        missing = sorted(active - ids)
        extra = sorted(ids - active)
        active_indices = group.index.to_numpy()[active_rows]
        active_legal = bool(active_rows.any() and legal[active_indices].all())
        active_critical = bool(active_rows.any() and critical[active_indices].all())
        valid = len(active) == expected_members and not missing and active_legal and active_critical
        if valid:
            valid_dates.add(date)
        date_contract.append(
            {
                "date": str(date.date()),
                "active_members": len(active),
                "market_stocks": len(ids),
                "covered_members": len(active & ids),
                "missing_members": missing[:20],
                "extra_stock_count": len(extra),
                "listing_invalid_active": int((~legal[active_indices]).sum()) if active_rows.any() else 0,
                "critical_invalid_active": int((~critical[active_indices]).sum()) if active_rows.any() else 0,
                "valid_training_date": bool(valid),
            }
        )
    if cutoff not in valid_dates:
        raise ValueError("cutoff does not satisfy exact 300-member PIT contract")

    engineered, segment_report = _build_history(
        market, history_mask, str(config.get("lgbm_price_scale_mode", "reported_return")), calendar
    )
    eligible = pd.DataFrame(
        {
            "股票代码": market["股票代码"].to_numpy(),
            "日期": market["日期"].to_numpy(),
            "pit_training_eligible": active_mask & market["日期"].isin(valid_dates).to_numpy(),
        }
    )
    indicators = market[["股票代码", "日期", *RAW_COLUMNS]].copy()
    indicator_columns = []
    for column in RAW_COLUMNS:
        name = f"missing_{column}"
        indicator_columns.append(name)
        indicators[name] = indicators[column].isna().astype(np.float32)
    indicators = indicators[["股票代码", "日期", *indicator_columns]]
    engineered = engineered.merge(indicators, on=list(MARKET_KEYS), how="left", validate="one_to_one")
    engineered = engineered.merge(eligible, on=list(MARKET_KEYS), how="left", validate="one_to_one")
    if engineered[indicator_columns + ["pit_training_eligible"]].isna().any().any():
        raise ValueError("PIT metadata merge lost a stock/date key")
    engineered["pit_training_eligible"] = engineered["pit_training_eligible"].astype(bool)
    frame = engineered[engineered["pit_training_eligible"]].copy()
    labelled = frame.dropna(subset=["label", "label_end_date"])
    if not labelled["label_gap_free"].astype(bool).all():
        raise ValueError("label horizon crosses a stock/date gap")
    cutoff_rows = frame[frame["日期"] == cutoff]
    if len(cutoff_rows) != expected_members or cutoff_rows["股票代码"].nunique() != expected_members:
        raise ValueError(f"PIT cutoff prediction universe is not exactly {expected_members} stocks")
    features = [column for column in LGBM_FEATURE_COLUMNS if column not in FEATURE_DROP] + indicator_columns
    values = frame[features].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("PIT model features contain non-finite values")
    report = {
        "schema_version": 1,
        "route": "production_pit_union",
        "label_contract": "raw_open_t5_over_raw_open_t1_minus_1",
        "expected_members": expected_members,
        "feature_history_policy": "legal_listed_history_with_trading_gap_segmentation",
        "feature_price_scale_mode": str(config.get("lgbm_price_scale_mode", "reported_return")),
        "cutoff": str(cutoff.date()),
        "market_rows": int(len(market)),
        "market_stocks": int(market["股票代码"].nunique()),
        "market_dates": int(market["日期"].nunique()),
        "legal_history_rows": int(legal.sum()),
        "critical_valid_history_rows": int(history_mask.sum()),
        "critical_invalid_rows": int((~critical).sum()),
        "training_rows": int(len(frame)),
        "training_stocks": int(frame["股票代码"].nunique()),
        "training_dates": int(frame["日期"].nunique()),
        "labelled_rows": int(len(labelled)),
        "invalid_contract_dates": int(len(date_contract) - len(valid_dates)),
        "valid_contract_dates": int(len(valid_dates)),
        "excluded_training_rows": int((~(active_mask & market["日期"].isin(valid_dates).to_numpy())).sum()),
        "missing_indicator_columns": indicator_columns,
        "missing_indicator_sums": {column: int(frame[column].sum()) for column in indicator_columns},
        "active_count_distribution": pd.Series([row["active_members"] for row in date_contract]).value_counts().sort_index().to_dict(),
        "date_contract_examples": [row for row in date_contract if not row["valid_training_date"]][:20],
        "date_contract": date_contract,
        **segment_report,
    }
    return frame.sort_values(["日期", "股票代码"]).reset_index(drop=True), features, cutoff, report
