"""Versioned compatibility and identity contracts for Quintara artifacts.

The validators in this module are deliberately side-effect free.  They are used
by migration scans, provider imports, GUI summaries, and tests so legacy
artifacts are inspected read-only and cross-route reuse fails closed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import (
    COMPETITION_LABEL,
    COMPETITION_LABEL_VERSION,
    DEFAULT_LABEL,
    PRODUCT_LABEL_VERSION,
    UniverseMode,
    content_hash,
    file_hash,
)


class ContractError(ValueError):
    """An artifact is incomplete, unsupported, or crosses an identity boundary."""


LABEL_CONTRACTS: dict[str, dict[str, str]] = {
    DEFAULT_LABEL: {
        "version": PRODUCT_LABEL_VERSION,
        "formula": "close(T+5) / open(T+1) - 1",
        "purpose": "product",
    },
    COMPETITION_LABEL: {
        "version": COMPETITION_LABEL_VERSION,
        "formula": "open(T+5) / open(T+1) - 1",
        "purpose": "differential-fixture",
    },
}

STRATEGY_POLICIES: dict[str, dict[str, Any]] = {
    "aggressive": {
        "version": "strategy-aggressive-v1",
        "display_name": "激进",
        "summary": "弱化波动与回撤惩罚，更重视模型排序差异。",
        "risk_bias": "higher",
    },
    "balanced": {
        "version": "strategy-balanced-v1",
        "display_name": "稳健平衡",
        "summary": "在模型评分、波动和回撤控制之间保持平衡。",
        "risk_bias": "balanced",
    },
    "conservative": {
        "version": "strategy-conservative-v1",
        "display_name": "保守",
        "summary": "提高稳定性约束，更重视波动和回撤控制。",
        "risk_bias": "lower",
    },
}
DEFAULT_STRATEGY = "balanced"


def _require(mapping: dict[str, Any], keys: set[str], *, artifact: str) -> None:
    missing = sorted(
        key for key in keys if key not in mapping or mapping[key] is None or mapping[key] == ""
    )
    if missing:
        raise ContractError(f"{artifact} missing required fields: {', '.join(missing)}")


def _mode(value: Any, *, artifact: str) -> UniverseMode:
    try:
        return UniverseMode(str(value))
    except ValueError as exc:
        raise ContractError(f"{artifact} has unsupported route: {value}") from exc


def data_mode(manifest: dict[str, Any]) -> UniverseMode:
    metadata = manifest.get("metadata") or {}
    return _mode(manifest.get("mode") or metadata.get("membership_route"), artifact="data manifest")


def validate_data_manifest(
    manifest: dict[str, Any],
    *,
    root: Path | None = None,
    expected_mode: UniverseMode | None = None,
) -> dict[str, Any]:
    """Validate a v1/v2 data manifest without modifying its directory."""
    _require(
        manifest,
        {"schema_version", "generation", "source", "date_min", "date_max", "files"},
        artifact="data manifest",
    )
    if int(manifest["schema_version"]) not in {1, 2}:
        raise ContractError(f"unsupported data manifest schema: {manifest['schema_version']}")
    mode = data_mode(manifest)
    if expected_mode is not None and mode != expected_mode:
        raise ContractError(f"data route mismatch: expected {expected_mode.value}, got {mode.value}")
    files = manifest["files"]
    if not isinstance(files, dict) or not files:
        raise ContractError("data manifest files must be a non-empty object")
    for name, entry in files.items():
        if not isinstance(entry, dict) or not entry.get("sha256") or int(entry.get("bytes", -1)) < 0:
            raise ContractError(f"invalid data file entry: {name}")
        if root is not None:
            path = root / name
            if not path.is_file() or file_hash(path) != entry["sha256"]:
                raise ContractError(f"data file identity mismatch: {name}")
    if mode == UniverseMode.PIT_BASELINE:
        names = set(files)
        if not ({"membership.csv", "membership/pit_intervals.csv"} & names):
            raise ContractError("PIT_BASELINE data is missing historical membership intervals")
    return manifest


def validate_model_identity(
    identity: dict[str, Any], *, expected_mode: UniverseMode | None = None
) -> dict[str, Any]:
    _require(
        identity,
        {
            "schema_version",
            "mode",
            "universe_id",
            "market_data_generation",
            "label_contract",
            "kernel_version",
            "config_hash",
            "training_cutoff",
        },
        artifact="model identity",
    )
    mode = _mode(identity["mode"], artifact="model identity")
    if expected_mode is not None and mode != expected_mode:
        raise ContractError(f"model route mismatch: expected {expected_mode.value}, got {mode.value}")
    label = str(identity["label_contract"])
    if label not in LABEL_CONTRACTS:
        raise ContractError(f"unsupported label contract: {label}")
    expected_version = LABEL_CONTRACTS[label]["version"]
    if not str(identity["kernel_version"]).startswith(expected_version):
        raise ContractError(
            f"kernel/label boundary mismatch: expected {expected_version}, got {identity['kernel_version']}"
        )
    return identity


def validate_result_manifest(
    manifest: dict[str, Any], *, expected_mode: UniverseMode | None = None
) -> dict[str, Any]:
    _require(
        manifest,
        {
            "schema_version",
            "run_id",
            "status",
            "route",
            "universe_id",
            "strategy",
            "label_contract",
            "data_generation",
            "model_generation",
            "result_generation",
            "model_identity",
            "files",
        },
        artifact="result manifest",
    )
    mode = _mode(manifest["route"], artifact="result manifest")
    if expected_mode is not None and mode != expected_mode:
        raise ContractError(f"result route mismatch: expected {expected_mode.value}, got {mode.value}")
    if manifest["strategy"] not in STRATEGY_POLICIES:
        raise ContractError(f"unsupported strategy policy: {manifest['strategy']}")
    identity = validate_model_identity(manifest["model_identity"], expected_mode=mode)
    if manifest["universe_id"] != identity["universe_id"]:
        raise ContractError("result universe does not match model identity")
    if manifest["data_generation"] != identity["market_data_generation"]:
        raise ContractError("result data generation does not match model identity")
    if manifest["label_contract"] != identity["label_contract"]:
        raise ContractError("result label contract does not match model identity")
    return manifest


def validate_artifact_closure(
    data_manifest: dict[str, Any],
    model_identity: dict[str, Any],
    result_manifest: dict[str, Any],
) -> None:
    """Fail closed unless data, model, and result share one exact identity closure."""
    mode = data_mode(validate_data_manifest(data_manifest))
    validate_model_identity(model_identity, expected_mode=mode)
    validate_result_manifest(result_manifest, expected_mode=mode)
    if result_manifest["model_identity"] != model_identity:
        raise ContractError("embedded result model identity differs from the selected model")
    if data_manifest["generation"] != model_identity["market_data_generation"]:
        raise ContractError("data generation differs from the selected model")


def load_legacy_artifact(path: str | Path, kind: str) -> dict[str, Any]:
    """Read and validate one legacy fixture while preserving the source bytes."""
    artifact_path = Path(path)
    before = file_hash(artifact_path)
    value = json.loads(artifact_path.read_text(encoding="utf-8"))
    if kind == "data":
        validate_data_manifest(value)
    elif kind == "model":
        validate_model_identity(value)
    elif kind == "result":
        validate_result_manifest(value)
    else:
        raise ContractError(f"unknown legacy artifact kind: {kind}")
    if file_hash(artifact_path) != before:
        raise ContractError("legacy artifact changed during read-only validation")
    return value


@dataclass(frozen=True)
class ContractFingerprint:
    mode: UniverseMode
    data_generation: str
    universe_id: str
    label_contract: str
    strategy_policy: str

    @property
    def digest(self) -> str:
        return content_hash(
            {
                "mode": self.mode.value,
                "data_generation": self.data_generation,
                "universe_id": self.universe_id,
                "label_contract": self.label_contract,
                "strategy_policy": self.strategy_policy,
            }
        )
