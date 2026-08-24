from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from quintara.contracts import (
    DEFAULT_STRATEGY,
    LABEL_CONTRACTS,
    STRATEGY_POLICIES,
    ContractError,
    load_legacy_artifact,
    validate_artifact_closure,
)
from quintara.core import COMPETITION_LABEL, DEFAULT_LABEL, UniverseMode

FIXTURES = Path(__file__).parent / "fixtures" / "v1"


def _closure() -> tuple[dict, dict, dict]:
    data = json.loads((FIXTURES / "data_manifest.json").read_text(encoding="utf-8"))
    model = json.loads((FIXTURES / "model_identity.json").read_text(encoding="utf-8"))
    result = json.loads((FIXTURES / "result_manifest.json").read_text(encoding="utf-8"))
    return data, model, result


def test_v1_artifacts_are_read_only_and_compatible():
    for name, kind in (
        ("data_manifest.json", "data"),
        ("model_identity.json", "model"),
        ("result_manifest.json", "result"),
    ):
        path = FIXTURES / name
        before = path.read_bytes()
        assert load_legacy_artifact(path, kind)["schema_version"] == 1
        assert path.read_bytes() == before
    assert json.loads((FIXTURES / "application_snapshot.json").read_text())["active_data"]
    assert json.loads((FIXTURES / "cli_bootstrap.json").read_text())["exit_code"] == 0


def test_label_and_strategy_contracts_are_explicit_and_versioned():
    assert LABEL_CONTRACTS[COMPETITION_LABEL]["version"] == "competition-open-open-v1"
    assert LABEL_CONTRACTS[DEFAULT_LABEL]["version"] == "quintara-close5-open1-v1"
    assert LABEL_CONTRACTS[COMPETITION_LABEL]["formula"] != LABEL_CONTRACTS[DEFAULT_LABEL]["formula"]
    assert DEFAULT_STRATEGY == "balanced"
    assert set(STRATEGY_POLICIES) == {"aggressive", "balanced", "conservative"}
    assert len({policy["version"] for policy in STRATEGY_POLICIES.values()}) == 3


def test_small_production_contract_fixture_covers_all_routes():
    fixture_root = Path(__file__).parents[1] / "fixtures"
    manifest = json.loads((fixture_root / "manifest.json").read_text(encoding="utf-8"))
    routes = json.loads((fixture_root / "synthetic_routes.json").read_text(encoding="utf-8"))
    assert manifest["fixture_identity"] == "quintara-production-contract-fixture-v2"
    assert manifest["market_stocks"] == 120
    assert set(manifest["routes"]) == {mode.value for mode in UniverseMode}
    assert len(routes["routes"]["CUSTOM_UNIVERSE"]["codes"]) == 100
    assert routes["routes"]["NON_PIT_FALLBACK"]["warning_ack"]
    for name, details in manifest["files"].items():
        path = fixture_root / name
        assert path.stat().st_size == details["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == details["sha256"]


@settings(max_examples=40)
@given(
    data_mode=st.sampled_from(list(UniverseMode)),
    model_mode=st.sampled_from(list(UniverseMode)),
    result_mode=st.sampled_from(list(UniverseMode)),
)
def test_cross_route_artifact_reuse_fails_closed(data_mode, model_mode, result_mode):
    data, model, result = _closure()
    data["metadata"]["membership_route"] = data_mode.value
    model["mode"] = model_mode.value
    result["route"] = result_mode.value
    result["model_identity"] = copy.deepcopy(model)
    if data_mode == UniverseMode.PIT_BASELINE:
        data["files"].setdefault(
            "membership.csv", {"sha256": "membership-fixture-sha256", "bytes": 234}
        )
    if data_mode == model_mode == result_mode:
        validate_artifact_closure(data, model, result)
    else:
        with pytest.raises(ContractError):
            validate_artifact_closure(data, model, result)


@settings(max_examples=30)
@given(field=st.sampled_from(["market_data_generation", "universe_id", "label_contract"]))
def test_model_result_identity_mutation_fails_closed(field):
    data, model, result = _closure()
    result["model_identity"] = copy.deepcopy(model)
    if field == "label_contract":
        result[field] = COMPETITION_LABEL
    else:
        result[field.replace("market_data_generation", "data_generation")] = "foreign-identity"
    with pytest.raises(ContractError):
        validate_artifact_closure(data, model, result)
