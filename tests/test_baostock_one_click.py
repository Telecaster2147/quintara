from __future__ import annotations

import sys
import types

import pandas as pd
import pytest

from quintara.core import AppPaths
from quintara.data_lifecycle import DataError, DataManager
from quintara.registry import Registry


class Query:
    def __init__(self, fields: str, rows: list[list[str]]) -> None:
        self.fields = fields.split(",")
        self.rows = rows
        self.error_code = "0"
        self.error_msg = ""
        self.index = 0

    def next(self) -> bool:
        value = self.index < len(self.rows)
        self.index += 1
        return value

    def get_row_data(self) -> list[str]:
        return self.rows[self.index - 1]


def _provider(*, bad_ohlc: list[bool] | None = None) -> types.SimpleNamespace:
    codes = [f"{value:06d}" for value in range(1, 302)]

    def trade_dates(start_date: str, end_date: str) -> Query:
        dates = pd.date_range(start_date, end_date, freq="D")
        rows = [[str(value.date()), "1" if value.weekday() < 5 else "0"] for value in dates]
        return Query("calendar_date,is_trading_day", rows)

    def membership(date: str = "") -> Query:
        selected = codes[:300] if date <= "2024-01-02" else codes[1:301]
        return Query("code,code_name", [[f"sz.{code}", f"Name-{code}"] for code in selected])

    def stock_basic() -> Query:
        rows = []
        for code in codes:
            status = "0" if code == "000001" else "1"
            out_date = "2024-01-03" if code == "000001" else ""
            rows.append([f"sz.{code}", f"Name-{code}", "2010-01-01", out_date, status])
        return Query("code,code_name,ipoDate,outDate,status", rows)

    def history(code: str, fields: str, **kwargs: str) -> Query:
        start = kwargs["start_date"]
        end = kwargs["end_date"]
        dates = pd.date_range(start, end, freq="D")
        dates = [value for value in dates if value.weekday() < 5]
        if fields == "date,code,close":
            return Query(fields, [[str(value.date()), code, "10"] for value in dates])
        if fields.startswith("date,code,open"):
            high = "8" if bad_ohlc and bad_ohlc[0] else "11"
            return Query(
                fields,
                [[str(value.date()), code, "10", high, "9", "10.5", "100", "1000", "1", "2"] for value in dates],
            )
        return Query(fields, [[str(value.date()), code, "1", "1", "1", "1"] for value in dates])

    return types.SimpleNamespace(
        login=lambda: types.SimpleNamespace(error_code="0", error_msg=""),
        logout=lambda: None,
        query_trade_dates=trade_dates,
        query_hs300_stocks=membership,
        query_stock_basic=stock_basic,
        query_history_k_data_plus=history,
    )


def test_pit_initialization_tracks_changes_and_preserves_delisted_history(monkeypatch, app_root):
    monkeypatch.setitem(sys.modules, "baostock", _provider())
    registry = Registry(AppPaths.discover(app_root))
    manager = DataManager(registry.paths, registry)
    try:
        events: list[dict[str, object]] = []
        manifest = manager.update_baostock(
            start_date="2024-01-02",
            end_date="2024-01-03",
            progress=events.append,
        )
        assert manifest["metadata"]["membership_route"] == "PIT_BASELINE"
        assert manifest["metadata"]["adjustflag"] == "3"
        bundle = manager.active_bundle()
        membership = bundle["membership"]
        removed = membership[membership["stock_id"].eq("000001")].iloc[0]
        added = membership[membership["stock_id"].eq("000301")].iloc[0]
        assert str(removed["end_date"].date()) == "2024-01-02"
        assert str(added["start_date"].date()) == "2024-01-03"
        listing = bundle["listing"]
        assert "000001" in set(listing["stock_id"])
        assert set(item["stage"] for item in events) >= {"connecting", "listing", "pool", "market", "validation", "publish", "complete"}
        plan = manager.plan_baostock_update(end_date="2024-01-05")
        assert plan["start_session"] == "2024-01-04"
        assert plan["target_cutoff"] == "2024-01-05"
        updated = manager.update_baostock(end_date="2024-01-05")
        repeated = manager.update_baostock(end_date="2024-01-05")
        assert repeated["no_change"] is True
        assert repeated["generation"] == updated["generation"]
    finally:
        registry.close()


def test_provider_failure_keeps_previous_generation_active(monkeypatch, app_root):
    state = [False]
    monkeypatch.setitem(sys.modules, "baostock", _provider(bad_ohlc=state))
    registry = Registry(AppPaths.discover(app_root))
    manager = DataManager(registry.paths, registry)
    try:
        first = manager.update_baostock(start_date="2024-01-02", end_date="2024-01-03")
        state[0] = True
        with pytest.raises(DataError, match="OHLC"):
            manager.update_baostock(end_date="2024-01-04")
        assert manager.active_manifest()["generation"] == first["generation"]
    finally:
        registry.close()


def test_bundled_or_csv_generation_becomes_baostock_derived_without_source_mutation(monkeypatch, app_root):
    monkeypatch.setitem(sys.modules, "baostock", _provider())
    registry = Registry(AppPaths.discover(app_root))
    manager = DataManager(registry.paths, registry)
    market = pd.DataFrame(
        {
            "股票代码": ["000001"], "日期": ["2024-01-02"], "开盘": [10], "收盘": [10.5],
            "最高": [11], "最低": [9], "成交量": [100], "成交额": [1000], "振幅": [20],
            "涨跌额": [0.5], "换手率": [1], "涨跌幅": [5],
        }
    )
    membership = pd.DataFrame({"stock_id": ["000001"], "index_code": ["CUSTOM"], "start_date": ["2024-01-02"], "end_date": [pd.NaT]})
    listing = pd.DataFrame({"stock_id": ["000001"], "ipo_date": ["2010-01-01"], "out_date": [pd.NaT]})
    try:
        source = manager.publish(market, membership, listing, source="quintara_provider", metadata={"membership_route": "CUSTOM_UNIVERSE"})
        derived = manager.update_baostock(end_date="2024-01-03", codes=["000001"])
        assert derived["source"] == "baostock"
        assert derived["metadata"]["derived_from_source"] == "quintara_provider"
        assert derived["parent_generation"] == source["generation"]
        assert (registry.paths.data_generations / source["generation"] / "manifest.json").exists()
    finally:
        registry.close()
