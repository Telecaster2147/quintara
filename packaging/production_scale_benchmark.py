"""Measure a five-year, 300-stock synthetic production-scale workload."""
from __future__ import annotations

import json
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from quintara.application import ProductUseCases
from quintara.service import QuintaraService

ROOT = Path(__file__).resolve().parents[1]


def _frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    stock_count = 300
    dates = pd.bdate_range("2021-01-04", periods=1260)
    codes = np.array([f"{600000 + index:06d}" for index in range(stock_count)])
    stock_index = np.tile(np.arange(stock_count), len(dates))
    day_index = np.repeat(np.arange(len(dates)), stock_count)
    code_values = np.tile(codes, len(dates))
    date_values = np.repeat(dates.to_numpy(), stock_count)
    opening = 8.0 + stock_index * 0.04 + day_index * 0.001 + np.sin(day_index / 17 + stock_index / 11) * 0.3
    change = 0.004 * np.sin(day_index / 7 + stock_index / 13) + stock_index / stock_count * 0.0005
    close = opening * (1 + change)
    market = pd.DataFrame(
        {
            "股票代码": code_values,
            "日期": date_values,
            "开盘": opening,
            "收盘": close,
            "最高": np.maximum(opening, close) * 1.008,
            "最低": np.minimum(opening, close) * 0.992,
            "成交量": 1_000_000 + stock_index * 100 + day_index,
            "成交额": (1_000_000 + stock_index * 100 + day_index) * close,
            "振幅": 1.6,
            "涨跌额": close - opening,
            "换手率": 0.8 + (stock_index % 20) * 0.05,
            "涨跌幅": change * 100,
        }
    )
    membership = pd.DataFrame({"stock_id": codes, "index_code": "CSI300", "start_date": dates.min(), "end_date": pd.NaT})
    listing = pd.DataFrame(
        {
            "stock_id": codes,
            "name": [f"规模样本{index + 1:03d}" for index in range(stock_count)],
            "exchange": "上海证券交易所",
            "status": "正常",
            "ipo_date": dates.min() - pd.DateOffset(years=10),
            "out_date": pd.NaT,
        }
    )
    return market, membership, listing


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="quintara-production-benchmark-") as temporary:
        root = Path(temporary)
        market, membership, listing = _frames()
        service = QuintaraService(root / "data-root")
        service.confirm_consent()
        started = time.perf_counter()
        manifest = service.data.publish(market, membership, listing, source="production-scale-benchmark")
        publish_seconds = time.perf_counter() - started
        generation_root = service.paths.data_generations / manifest["generation"]
        archive = root / "dataset.zip"
        started = time.perf_counter()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for name in ("market.csv", "membership.csv", "listing.csv", "manifest.json"):
                bundle.write(generation_root / name, name)
        pack_seconds = time.perf_counter() - started
        copied = root / "downloaded.zip"
        started = time.perf_counter()
        with archive.open("rb") as source, copied.open("wb") as target:
            shutil.copyfileobj(source, target, 1024 * 1024)
        transfer_seconds = time.perf_counter() - started
        started = time.perf_counter()
        with zipfile.ZipFile(copied) as bundle:
            bundle.extractall(root / "unpacked")
        unpack_seconds = time.perf_counter() - started
        started = time.perf_counter()
        run = service.run(
            config={
                "lgbm_fixed_rounds": 256,
                "lgbm_num_threads": 4,
                "lgbm_num_leaves": 127,
                "lgbm_min_data_in_leaf": 20,
                "training_years": 5,
            }
        )
        training_seconds = time.perf_counter() - started
        started = time.perf_counter()
        ProductUseCases(service).results(run["run_id"])
        page_seconds = time.perf_counter() - started
        service.close()
        measurements = {
            "rows": len(market),
            "stocks": int(market["股票代码"].nunique()),
            "trading_days": int(market["日期"].nunique()),
            "generation_bytes": sum(path.stat().st_size for path in generation_root.glob("*") if path.is_file()),
            "package_bytes": archive.stat().st_size,
            "publish_seconds": publish_seconds,
            "pack_seconds": pack_seconds,
            "local_transfer_seconds": transfer_seconds,
            "unpack_seconds": unpack_seconds,
            "cpu_training_256_round_seconds": training_seconds,
            "results_page_seconds": page_seconds,
        }
    budgets = {"cpu_training_seconds": 1800, "results_page_seconds": 2.0, "publish_seconds": 120, "unpack_seconds": 120}
    passed = (
        measurements["cpu_training_256_round_seconds"] <= budgets["cpu_training_seconds"]
        and measurements["results_page_seconds"] <= budgets["results_page_seconds"]
        and measurements["publish_seconds"] <= budgets["publish_seconds"]
        and measurements["unpack_seconds"] <= budgets["unpack_seconds"]
    )
    evidence = {"schema_version": 1, "fixture": "five-year-300-stock-synthetic", "measurements": measurements, "budgets": budgets, "passed": passed}
    output = ROOT / "dist/production-scale-performance.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
