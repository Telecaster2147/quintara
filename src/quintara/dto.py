"""Presentation DTOs shared by the QML GUI, CLI summaries, and tests."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class PageStatus(StrEnum):
    LOADING = "loading"
    READY = "ready"
    EMPTY = "empty"
    ERROR = "error"


@dataclass(frozen=True)
class RecoveryActionDTO:
    key: str
    label: str
    target: str
    primary: bool = False


@dataclass(frozen=True)
class ErrorSummaryDTO:
    code: str
    title: str
    message: str
    impact: str
    actions: tuple[RecoveryActionDTO, ...] = ()

    @classmethod
    def from_exception(cls, exc: Exception, *, data_root: Path | None = None) -> ErrorSummaryDTO:
        raw_message = str(exc).strip() or exc.__class__.__name__
        lowered = raw_message.lower()
        if isinstance(exc, FileNotFoundError) or "file not found" in lowered or "no such file" in lowered:
            message = "找不到所选文件。请确认文件仍在原位置，然后重新选择。"
        elif "permission" in lowered or "read-only" in lowered or "writable" in lowered:
            message = "所选位置当前不可写。请选择有写入权限且空间充足的本地目录。"
        elif "disk" in lowered or "space" in lowered:
            message = "本机可用空间不足，数据与暂存区需要预留约两倍包体积。"
        elif "tie" in lowered:
            message = "本次模型评分存在未解决的并列，结果没有发布。请检查数据质量后重新训练。"
        else:
            message = "本次操作在完成前停止。请按下方建议重试；技术详情保留了脱敏错误信息。"
        if data_root is not None:
            message = message.replace(str(data_root), "<DATA_ROOT>")
        message = message.replace(str(Path.home()), "<HOME>")
        message = re.sub(r"(?:[A-Za-z]:)?[/\\](?:[^\s:/\\]+[/\\]){2,}[^\s]+", "<PATH>", message)
        technical_code = exc.__class__.__name__.upper()
        return cls(
            code=technical_code,
            title="操作未完成",
            message=message,
            impact="上一份已经发布的数据、模型和结果仍保持可用。",
            actions=(RecoveryActionDTO("retry", "重试", "current", True),),
        )


@dataclass(frozen=True)
class TechnicalDetailsDTO:
    title: str
    entries: tuple[tuple[str, str], ...] = ()
    copy_text: str = ""


@dataclass(frozen=True)
class PageDTO:
    key: str
    title: str
    status: PageStatus
    eyebrow: str = ""
    summary: str = ""
    primary_action: RecoveryActionDTO | None = None
    actions: tuple[RecoveryActionDTO, ...] = ()
    cards: tuple[dict[str, Any], ...] = ()
    rows: tuple[dict[str, Any], ...] = ()
    notices: tuple[dict[str, str], ...] = ()
    technical: TechnicalDetailsDTO | None = None
    error: ErrorSummaryDTO | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        # Qt's QVariant bridge exposes lists more reliably than Python tuples.
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
