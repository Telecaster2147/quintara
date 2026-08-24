"""Non-causal ranking explanations and transparent risk summaries."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd


def risk_metrics(market: pd.DataFrame, stock_id: str, cutoff: pd.Timestamp, windows: Iterable[int] = (20, 60, 120)) -> dict[str, Any]:
    frame = market[market["股票代码"].astype(str).str.zfill(6) == str(stock_id).zfill(6)].copy()
    frame = frame[pd.to_datetime(frame["日期"]) <= pd.Timestamp(cutoff)].sort_values("日期")
    close = pd.to_numeric(frame["收盘"], errors="coerce").dropna()
    returns = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).dropna()
    result: dict[str, Any] = {"stock_id": str(stock_id).zfill(6), "cutoff": str(pd.Timestamp(cutoff).date()), "windows": {}}
    for window in windows:
        values = returns.tail(int(window))
        if len(values) < int(window):
            result["windows"][str(window)] = {"status": "INSUFFICIENT_HISTORY", "observations": int(len(values))}
            continue
        equity = (1 + values).cumprod()
        drawdown = equity / equity.cummax() - 1
        downside = values[values < 0]
        result["windows"][str(window)] = {
            "status": "PASS",
            "observations": int(len(values)),
            "volatility": float(values.std(ddof=1) * np.sqrt(252)),
            "downside_volatility": float(downside.std(ddof=1) * np.sqrt(252)) if len(downside) > 1 else 0.0,
            "maximum_drawdown": float(drawdown.min()),
        }
    return result


def correlation_matrix(market: pd.DataFrame, stock_ids: Iterable[str], cutoff: pd.Timestamp, window: int = 60) -> dict[str, Any]:
    frame = market.copy()
    frame["股票代码"] = frame["股票代码"].astype(str).str.zfill(6)
    frame = frame[pd.to_datetime(frame["日期"]) <= pd.Timestamp(cutoff)]
    close = frame.pivot(index="日期", columns="股票代码", values="收盘").sort_index().tail(window)
    selected = [str(value).zfill(6) for value in stock_ids]
    available = [value for value in selected if value in close.columns]
    matrix = close[available].pct_change(fill_method=None).corr().fillna(0.0)
    return {"window": window, "stocks": available, "matrix": matrix.to_dict()}


def feature_contributions(booster: Any, row: pd.DataFrame, features: list[str], top_n: int = 8) -> list[dict[str, Any]]:
    """Return model-attribution values; these are influences, not causal claims."""
    values = row[features].to_numpy(dtype=np.float32)
    try:
        contribution = np.asarray(booster.predict(values, pred_contrib=True))[0, :-1]
    except Exception:
        importance = np.asarray(booster.feature_importance(importance_type="gain"), dtype=float)
        contribution = importance * values[0]
    order = np.argsort(np.abs(contribution))[::-1][:top_n]
    return [{"feature": features[index], "contribution": float(contribution[index]), "wording": "影响模型分数的特征，不是因果证明"} for index in order]
