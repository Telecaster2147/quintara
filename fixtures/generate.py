from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent

def main() -> None:
    rng = np.random.default_rng(147)
    dates = pd.bdate_range("2024-01-01", periods=70)
    codes = [f"{600000 + index:06d}" for index in range(8)]
    rows = []
    for index, code in enumerate(codes):
        close = 10.0 + index
        for day, stamp in enumerate(dates):
            ret = rng.normal(0.002, 0.03) + index * 0.0004
            opening = close * (1 + rng.normal(0, 0.005))
            close = max(0.1, opening * (1 + ret))
            rows.append({"股票代码": code, "日期": stamp, "开盘": opening, "收盘": close, "最高": max(opening, close) * (1 + rng.random() * 0.01), "最低": min(opening, close) * (1 - rng.random() * 0.01), "成交量": 1000 + rng.random() * 1000 + day, "成交额": 10000 + rng.random() * 10000 + day, "振幅": 2.0, "涨跌额": close - opening, "换手率": 1 + rng.random() * 2, "涨跌幅": (close / opening - 1) * 100})
    market = pd.DataFrame(rows)
    membership = pd.DataFrame({"stock_id": codes, "index_code": "CSI300", "start_date": dates.min(), "end_date": pd.NaT})
    listing = pd.DataFrame({"stock_id": codes, "ipo_date": dates.min(), "out_date": pd.NaT})
    for name, frame in (("synthetic_market.csv", market), ("synthetic_membership.csv", membership), ("synthetic_listing.csv", listing)):
        frame.to_csv(ROOT / name, index=False, encoding="utf-8")
    files = {}
    for path in sorted(ROOT.glob("synthetic_*.csv")):
        files[path.name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
    (ROOT / "manifest.json").write_text(json.dumps({"schema_version": 1, "kind": "synthetic-test-only", "files": files}, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
