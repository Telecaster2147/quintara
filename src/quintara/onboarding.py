"""Versioned first-run workflow and mutually exclusive data-source consent."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .core import content_hash, now_utc

RISK_STATEMENT_VERSION = "CN-A-SHARE-RESEARCH-3"
RISK_SECTIONS = (
    {
        "key": "purpose",
        "title": "用途边界",
        "text": "Quintara 是本地量化研究软件，用于整理数据、训练模型和复查历史结果。软件输出是研究记录，不是收益承诺、个性化投资建议或自动交易指令。",
    },
    {
        "key": "data",
        "title": "数据边界",
        "text": "历史数据可能存在缺失、复权差异、停牌、退市、成分变更和发布时间差异。自带开发者数据固定在随安装包交付的版本；用户 CSV 由用户确认来源、字段和单位。",
    },
    {
        "key": "model",
        "title": "模型边界",
        "text": "模型依据历史样本计算排序，结果会随数据版本、股票池、参数、运行环境和截止日期变化。历史拟合与单次结果都不代表未来表现。",
    },
    {
        "key": "decision",
        "title": "决策责任",
        "text": "用户在使用结果前需要独立核对证券状态、交易规则、流动性、费用、风险承受能力以及适用要求，并自行决定是否采纳任何研究结论。",
    },
    {
        "key": "privacy",
        "title": "本地与联网",
        "text": "数据、模型和结果默认保存在用户选择的本机工作目录。遥测保持关闭；只有用户主动发起数据更新或版本检查时才发生对应联网操作。",
    },
)
RISK_STATEMENT = "\n\n".join(f"{item['title']}：{item['text']}" for item in RISK_SECTIONS)
ONBOARDING_VERSION = 3
ONBOARDING_STEPS = ("risk", "environment", "source", "storage", "ready")


@dataclass(frozen=True)
class DataSourceChoice:
    kind: str
    accepted_license: bool = False
    accepted_transfer: bool = False
    selected_at: str = ""

    def validate(self) -> None:
        if self.kind not in {"bundled", "baostock", "provider", "csv"}:
            raise ValueError("data source must be bundled, baostock, provider or csv")
        if self.kind == "provider" and not (self.accepted_license and self.accepted_transfer):
            raise ValueError("provider transfer requires license and transfer confirmation")
        if self.kind == "bundled" and not self.accepted_license:
            raise ValueError("bundled developer data requires the package notice confirmation")


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
        "sections": [
            {
                "key": item["key"],
                "hash": content_hash(item["text"]),
            }
            for item in RISK_SECTIONS
        ],
        "confirmed_at": now_utc(),
        "application_version": application_version,
    }


def consent_is_current(value: dict[str, Any]) -> bool:
    return value.get("statement_version") == RISK_STATEMENT_VERSION and value.get("statement_hash") == content_hash(RISK_STATEMENT)
