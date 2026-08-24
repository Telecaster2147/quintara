from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest


@pytest.fixture()
def market_fixture() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(147)
    dates = pd.bdate_range("2024-01-01", periods=70)
    codes = [f"{600000 + index:06d}" for index in range(100)]
    rows: list[dict[str, object]] = []
    for index, code in enumerate(codes):
        close = 10.0 + index
        for day, stamp in enumerate(dates):
            ret = rng.normal(0.002, 0.03) + index * 0.0004
            opening = close * (1 + rng.normal(0, 0.005))
            close = max(0.1, opening * (1 + ret))
            rows.append(
                {
                    "股票代码": code,
                    "日期": stamp,
                    "开盘": opening,
                    "收盘": close,
                    "最高": max(opening, close) * (1 + rng.random() * 0.01),
                    "最低": min(opening, close) * (1 - rng.random() * 0.01),
                    "成交量": 1000 + rng.random() * 1000 + day,
                    "成交额": 10000 + rng.random() * 10000 + day,
                    "振幅": 2.0,
                    "涨跌额": close - opening,
                    "换手率": 1 + rng.random() * 2,
                    "涨跌幅": (close / opening - 1) * 100,
                }
            )
    market = pd.DataFrame(rows)
    listing = pd.DataFrame(
        {
            "stock_id": codes,
            "name": [f"样本股票{index + 1:03d}" for index in range(len(codes))],
            "exchange": ["上海证券交易所" for _ in codes],
            "status": ["正常" for _ in codes],
            "ipo_date": dates.min(),
            "out_date": pd.NaT,
        }
    )
    membership = pd.DataFrame({"stock_id": codes, "index_code": "CSI300", "start_date": dates.min(), "end_date": pd.NaT})
    return market, membership, listing


@pytest.fixture()
def app_root(tmp_path: Path) -> Path:
    return tmp_path / "quintara"
