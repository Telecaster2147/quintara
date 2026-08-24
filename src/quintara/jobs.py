"""Local JSONL job events and cooperative cancellation state."""
from __future__ import annotations

import json
import threading
from typing import Any

from .core import AppPaths, Severity, now_utc


class JobCancelled(RuntimeError):
    """Raised at a safe point after a cancellation request."""


class JobContext:
    def __init__(self, paths: AppPaths, job_id: str, *, emit_initial: bool = True) -> None:
        self.paths = paths
        self.job_id = job_id
        self.events_path = paths.jobs / f"{job_id}.jsonl"
        self.cancel_path = paths.jobs / f"{job_id}.cancel"
        self._cancelled = threading.Event()
        self._sequence = 0
        if emit_initial:
            self.emit("queued", "JOB_QUEUED", "作业已排队", Severity.PASS)

    def emit(self, stage: str, message_key: str, message: str, severity: Severity = Severity.PASS, progress: float | None = None, **context: Any) -> dict[str, Any]:
        self._sequence += 1
        event = {"sequence": self._sequence, "job_id": self.job_id, "stage": stage, "timestamp": now_utc(), "severity": severity.value, "message_key": message_key, "message": message, "progress": progress, "context": context}
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True, default=str) + "\n")
        return event

    def request_cancel(self) -> None:
        self.cancel_path.write_text("cancel\n", encoding="utf-8")
        self._cancelled.set()
        self.emit("cancelling", "JOB_CANCEL_REQUESTED", "已请求取消", Severity.WARNING)

    def cancelled(self) -> bool:
        return self._cancelled.is_set() or self.cancel_path.exists()

    def checkpoint(self, stage: str = "running") -> None:
        if self.cancelled():
            self.emit(stage, "JOB_CANCELLED", "作业已取消", Severity.WARNING)
            raise JobCancelled(self.job_id)

    def finish(self) -> None:
        self.cancel_path.unlink(missing_ok=True)


def read_events(paths: AppPaths, job_id: str) -> list[dict[str, Any]]:
    path = paths.jobs / f"{job_id}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
