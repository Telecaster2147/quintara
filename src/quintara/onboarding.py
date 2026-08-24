"""Versioned first-run workflow and mutually exclusive data-source consent."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .core import content_hash, now_utc

RISK_STATEMENT_VERSION = "CN-A-SHARE-RESEARCH-2"
RISK_STATEMENT = "Quintara 仅用于本地量化研究；结果不是收益保证或交易指令。"
ONBOARDING_VERSION = 2
ONBOARDING_STEPS = ("risk", "environment", "source", "storage", "ready")


@dataclass(frozen=True)
class DataSourceChoice:
    kind: str
    accepted_license: bool = False
    accepted_transfer: bool = False
    selected_at: str = ""

    def validate(self) -> None:
        if self.kind not in {"provider", "csv"}:
            raise ValueError("data source must be provider or csv")
        if self.kind == "provider" and not (self.accepted_license and self.accepted_transfer):
            raise ValueError("provider transfer requires license and transfer confirmation")


class OnboardingFlow:
    """Persist resumable wizard state in the existing local settings registry."""

    def __init__(self, registry: Any) -> None:
        self.registry = registry

    def status(self) -> dict[str, Any]:
        value = self.registry.setting("onboarding", {}) or {}
        step = int(value.get("step", 0))
        return {
            "schema_version": ONBOARDING_VERSION,
            "step": min(max(step, 0), len(ONBOARDING_STEPS) - 1),
            "step_key": ONBOARDING_STEPS[min(max(step, 0), len(ONBOARDING_STEPS) - 1)],
            "completed": bool(value.get("completed", False)),
            "skipped": bool(value.get("skipped", False)),
            "source": value.get("source"),
        }

    def advance(self, step: int, *, source: DataSourceChoice | None = None) -> dict[str, Any]:
        current = self.status()
        if step < current["step"] or step >= len(ONBOARDING_STEPS):
            raise ValueError("wizard steps advance monotonically")
        value = dict(current)
        value["step"] = step
        value["step_key"] = ONBOARDING_STEPS[step]
        value["updated_at"] = now_utc()
        if source is not None:
            source.validate()
            value["source"] = asdict(source) | {"selected_at": source.selected_at or now_utc()}
        if step == len(ONBOARDING_STEPS) - 1 and current["step"] == step:
            value["completed"] = True
            value["skipped"] = False
        self.registry.set_setting("onboarding", value)
        return self.status()

    def skip(self) -> dict[str, Any]:
        value = self.status() | {"skipped": True, "completed": False, "updated_at": now_utc()}
        self.registry.set_setting("onboarding", value)
        return self.status()

    def reopen(self) -> dict[str, Any]:
        value = self.status() | {"step": 0, "completed": False, "skipped": False, "updated_at": now_utc()}
        self.registry.set_setting("onboarding", value)
        return self.status()


def consent_record(application_version: str) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "statement_version": RISK_STATEMENT_VERSION,
        "statement_hash": content_hash(RISK_STATEMENT),
        "confirmed_at": now_utc(),
        "application_version": application_version,
    }


def consent_is_current(value: dict[str, Any]) -> bool:
    return value.get("statement_version") == RISK_STATEMENT_VERSION and value.get("statement_hash") == content_hash(RISK_STATEMENT)
