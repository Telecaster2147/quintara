from __future__ import annotations

from quintara.core import UniverseMode
from quintara.service import QuintaraService


def test_service_run_writes_five_stock_artifacts(app_root, market_fixture):
    market, membership, listing = market_fixture
    service = QuintaraService(app_root)
    try:
        service.data.publish(market, membership, listing, source="pytest")
        service.confirm_consent()
        result = service.run(config={"lgbm_fixed_rounds": 8, "lgbm_min_data_in_leaf": 5, "lgbm_num_threads": 1})
        assert len(result["result"]) == 5
        assert sum(row["weight"] for row in result["result"]) == 1.0
        manifest = service.result_manifest(result["run_id"])
        assert manifest["route"] == "PIT_BASELINE"
        assert (service.paths.results / result["run_id"] / "result.csv").exists()
        assert service.runs(1)[0]["state"] == "SUCCEEDED"
        assert (service.paths.results / result["run_id"] / "result_view.json").exists()
        assert (service.paths.results / result["run_id"] / "explanations.json").exists()
        cached = service.run(config={"lgbm_fixed_rounds": 8, "lgbm_min_data_in_leaf": 5, "lgbm_num_threads": 1})
        assert cached["cached"] is True
        assert service.runs(1)[0]["state"] == "CACHED"
        assert service.result_details(result["run_id"])["identity_badge"] == "PIT_BASELINE"
    finally:
        service.close()


def test_custom_universe_codes_can_be_added_and_removed(app_root):
    service = QuintaraService(app_root)
    try:
        codes = [f"600{index:03d}" for index in range(100)]
        universe = service.create_universe("可编辑池", UniverseMode.CUSTOM_UNIVERSE, codes)
        edited = service.edit_custom_universe(universe["id"], add_codes=["600100"], remove_codes=[codes[0]])
        result_codes = edited["definition"]["codes"]
        assert "600000" not in result_codes
        assert "600100" in result_codes
        assert len(result_codes) == 100
    finally:
        service.close()
