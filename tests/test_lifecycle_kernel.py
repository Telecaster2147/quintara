from __future__ import annotations

import json
import types

import pandas as pd

from quintara.core import COMPETITION_LABEL, DEFAULT_LABEL, AppPaths, UniverseMode
from quintara.data_lifecycle import DataError, DataManager
from quintara.kernel import prepare
from quintara.registry import Registry


def test_publish_pointer_and_product_label(app_root, market_fixture):
    market, membership, listing = market_fixture
    registry = Registry(AppPaths.discover(app_root))
    manager = DataManager(registry.paths, registry)
    manifest = manager.publish(market, membership, listing, source="pytest")
    assert manager.active_manifest()["generation"] == manifest["generation"]
    pointer = json.loads(manager.paths.active_data.read_text(encoding="utf-8"))
    assert pointer["generation"] == manifest["generation"]
    prepared = prepare(market, membership, listing, mode=UniverseMode.PIT_BASELINE, config={"lgbm_fixed_rounds": 2})
    first_code = market["股票代码"].iloc[0]
    first = prepared.frame[(prepared.frame["股票代码"] == first_code) & (prepared.frame["日期"] == market["日期"].min())].iloc[0]
    group = market[market["股票代码"] == first_code].sort_values("日期").reset_index(drop=True)
    expected = (group.loc[5, "收盘"] - group.loc[1, "开盘"]) / group.loc[1, "开盘"]
    assert prepared.report["label_contract"] == DEFAULT_LABEL
    assert abs(float(first["label"]) - float(expected)) < 1e-10
    registry.close()


def test_generation_hash_is_row_order_invariant(app_root, market_fixture):
    market, membership, listing = market_fixture
    first = Registry(AppPaths.discover(app_root))
    manager = DataManager(first.paths, first)
    left = manager.publish(market, membership, listing, source="pytest")
    second_root = app_root.parent / "other"
    second = Registry(AppPaths.discover(second_root))
    right = DataManager(second.paths, second).publish(market.sample(frac=1, random_state=4), membership.sample(frac=1, random_state=5), listing.sample(frac=1, random_state=6), source="pytest")
    assert left["generation"] == right["generation"]
    first.close()
    second.close()


def test_publication_fault_keeps_previous_active_generation(app_root, market_fixture):
    market, membership, listing = market_fixture
    registry = Registry(AppPaths.discover(app_root))
    manager = DataManager(registry.paths, registry)
    previous = manager.publish(market, membership, listing, source="first")
    failing = DataManager(registry.paths, registry, fault_hook=lambda stage: (_ for _ in ()).throw(RuntimeError(stage)) if stage == "before_active_pointer" else None)
    try:
        failing.publish(market.assign(收盘=market["收盘"] + 0.01), membership, listing, source="second")
    except RuntimeError as exc:
        assert str(exc) == "before_active_pointer"
    else:
        raise AssertionError("fault hook should interrupt publication")
    assert manager.active_manifest()["generation"] == previous["generation"]
    registry.close()


def test_csv_manifest_redacts_original_path(app_root, tmp_path):
    path = tmp_path / "market.csv"
    codes = [f"6000{index:02d}" for index in range(6)]
    frame = pd.DataFrame(
        {
            "stock_id": codes * 6,
            "date": list(pd.date_range("2024-01-01", periods=6).repeat(6)),
            "open": [10.0] * 36,
            "close": [11.0] * 36,
            "high": [11.0] * 36,
            "low": [10.0] * 36,
            "volume": [100.0] * 36,
            "amount": [1000.0] * 36,
            "amplitude": [1.0] * 36,
            "change_amount": [1.0] * 36,
            "turnover": [1.0] * 36,
            "change_pct": [10.0] * 36,
        }
    )
    frame.to_csv(path, index=False)
    units = {"open": "price", "close": "price", "high": "price", "low": "price", "volume": "volume", "amount": "amount", "turnover": "percentage", "change_pct": "percentage"}
    registry = Registry(AppPaths.discover(app_root))
    manager = DataManager(registry.paths, registry)
    try:
        manifest = manager.import_csv(path, units=units)
        assert manifest["metadata"]["csv_validation"]["source"] == "<LOCAL_SOURCE>"
        assert str(path) not in json.dumps(manifest, ensure_ascii=False)
    finally:
        registry.close()


def test_competition_contract_is_explicit_and_trading_calendar_is_used(market_fixture):
    market, membership, listing = market_fixture
    dates = pd.to_datetime(market["日期"].unique())
    # Removing a session from the global calendar makes the next observed date the next session.
    market = market[market["日期"] != dates[2]].copy()
    prepared = prepare(market, membership, listing, mode=UniverseMode.PIT_BASELINE, contract=COMPETITION_LABEL)
    code = market["股票代码"].iloc[0]
    group = market[market["股票代码"] == code].sort_values("日期").reset_index(drop=True)
    first = prepared.frame[(prepared.frame["股票代码"] == code) & (prepared.frame["日期"] == group.loc[0, "日期"])].iloc[0]
    expected = (group.loc[5, "开盘"] - group.loc[1, "开盘"]) / group.loc[1, "开盘"]
    assert prepared.report["label_version"] == "competition-open-open-v1"
    assert abs(float(first["label"]) - float(expected)) < 1e-10


def test_baostock_update_requires_explicit_non_pit_ack_and_connects_extra_features(monkeypatch, app_root):
    codes = [f"60000{index}" for index in range(6)]
    dates = pd.date_range("2024-01-01", periods=6, freq="D")

    class Query:
        def __init__(self, fields, rows):
            self.fields = fields.split(",")
            self.rows = rows
            self.error_code = "0"
            self.error_msg = ""
            self.index = 0

        def next(self):
            value = self.index < len(self.rows)
            self.index += 1
            return value

        def get_row_data(self):
            return self.rows[self.index - 1]

    def stock_basic():
        return Query("code,code_name,ipoDate,outDate,status", [[f"{code}.SH", f"Name-{code}", "2010-01-01", "", "1"] for code in codes])

    def hs300(date=""):
        del date
        return Query("code", [[f"{code}.SH"] for code in codes])

    def history(code, fields, **kwargs):
        del kwargs
        code = code.split(".")[0]
        if fields.startswith("date,code,open"):
            rows = [[str(day.date()), f"{code}.SH", "10", "11", "9", "10.5", "100", "1000", "1", "2"] for day in dates]
        else:
            rows = [[str(day.date()), f"{code}.SH", "1", "1", "1", "1"] for day in dates]
        return Query(fields, rows)

    fake = types.SimpleNamespace(
        login=lambda: types.SimpleNamespace(error_code="0", error_msg=""),
        logout=lambda: None,
        query_stock_basic=stock_basic,
        query_hs300_stocks=hs300,
        query_history_k_data_plus=history,
    )
    monkeypatch.setitem(__import__("sys").modules, "baostock", fake)
    registry = Registry(AppPaths.discover(app_root))
    manager = DataManager(registry.paths, registry)
    try:
        try:
            manager.update_baostock(start_date="2024-01-01", end_date="2024-01-06")
        except DataError as exc:
            assert "allow-non-pit" in str(exc)
        else:
            raise AssertionError("non-PIT update must require an explicit acknowledgement")
        manifest = manager.update_baostock(start_date="2024-01-01", end_date="2024-01-06", allow_non_pit=True)
        assert manifest["metadata"]["membership_route"] == "NON_PIT_FALLBACK"
        bundle = manager.active_bundle()
        assert not bundle["extra_features"].empty
        assert "peTTM" in bundle["market"].columns
        custom = manager.update_baostock(start_date="2024-01-01", end_date="2024-01-06", codes=codes)
        assert custom["metadata"]["membership_route"] == "CUSTOM_UNIVERSE"
    finally:
        registry.close()
