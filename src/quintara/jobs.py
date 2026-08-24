"""Local JSONL job events and cooperative cancellation state."""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from typing import Any

from .core import AppPaths, Severity, content_hash, new_id, now_utc
from .platform import FileLock, atomic_json


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


@dataclass(frozen=True)
class JobSpec:
    kind: str
    phases: tuple[str, ...]
    progress_type: str
    stop_points: tuple[str, ...]
    publication_phase: str


JOB_SPECS = {
    "download": JobSpec("download", ("preflight", "transfer", "verify", "publish"), "bytes", ("transfer", "verify"), "publish"),
    "inspect": JobSpec("inspect", ("read", "validate", "report"), "items", ("read", "validate"), "report"),
    "update": JobSpec("update", ("plan", "market", "membership", "verify", "publish"), "phase", ("market", "membership", "verify"), "publish"),
    "train": JobSpec("train", ("prepare", "features", "fit", "score", "publish"), "phase", ("prepare", "features", "fit", "score"), "publish"),
    "predict": JobSpec("predict", ("load", "score", "rank", "publish"), "items", ("load", "score", "rank"), "publish"),
}


def progress_snapshot(*, completed: int, total: int | None, elapsed_seconds: float, phase: str) -> dict[str, Any]:
    rate = completed / elapsed_seconds if elapsed_seconds > 0 else None
    remaining = ((total - completed) / rate) if total is not None and rate and completed <= total else None
    return {
        "phase": phase,
        "completed": completed,
        "total": total,
        "fraction": completed / total if total else None,
        "rate_per_second": rate,
        "elapsed_seconds": elapsed_seconds,
        "remaining_seconds": remaining if remaining is not None and remaining >= 2 else None,
    }


class JobCoordinator:
    """Single-writer durable state used equally by GUI and CLI."""

    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths
        paths.ensure()

    def create(self, kind: str, payload: dict[str, Any], *, idempotency_key: str | None = None) -> dict[str, Any]:
        if kind not in JOB_SPECS:
            raise ValueError(f"unknown job kind: {kind}")
        key = idempotency_key or content_hash({"kind": kind, "payload": payload})
        index = self.paths.jobs / "idempotency.json"
        with FileLock(self.paths.jobs / ".coordinator.lock"):
            values = json.loads(index.read_text(encoding="utf-8")) if index.exists() else {}
            existing = values.get(key)
            if existing and (self.paths.jobs / f"{existing}.snapshot.json").exists():
                return self.snapshot(existing)
            job_id = new_id("job")
            spec = JOB_SPECS[kind]
            snapshot = {
                "schema_version": 1,
                "job_id": job_id,
                "kind": kind,
                "state": "QUEUED",
                "phase": spec.phases[0],
                "progress": progress_snapshot(completed=0, total=None, elapsed_seconds=0, phase=spec.phases[0]),
                "payload": payload,
                "spec": asdict(spec),
                "idempotency_key": key,
                "created_at": now_utc(),
                "updated_at": now_utc(),
            }
            atomic_json(self.paths.jobs / f"{job_id}.snapshot.json", snapshot)
            JobContext(self.paths, job_id)
            values[key] = job_id
            atomic_json(index, values)
            return snapshot

    def snapshot(self, job_id: str) -> dict[str, Any]:
        return json.loads((self.paths.jobs / f"{job_id}.snapshot.json").read_text(encoding="utf-8"))

    def transition(self, job_id: str, *, state: str, phase: str, progress: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
        with FileLock(self.paths.jobs / f"{job_id}.lock"):
            value = self.snapshot(job_id)
            terminal = {"SUCCEEDED", "FAILED", "CANCELLED"}
            if value["state"] in terminal:
                raise ValueError("terminal job state is immutable")
            allowed = {
                "QUEUED": {"PLANNING", "READY", "RUNNING", "CANCELLED", "FAILED"},
                "PLANNING": {"READY", "FAILED", "CANCELLED"},
                "READY": {"RUNNING", "CANCELLED"},
                "RUNNING": {"PAUSING", "CANCELLING", "SUCCEEDED", "FAILED", "RECOVERABLE"},
                "PAUSING": {"READY", "CANCELLING", "RECOVERABLE"},
                "CANCELLING": {"CANCELLED", "FAILED", "RECOVERABLE"},
                "RECOVERABLE": {"READY", "RUNNING", "CANCELLED", "FAILED"},
                "RECOVERED": {"READY", "RUNNING", "CANCELLED", "FAILED"},
            }
            if state not in allowed.get(str(value["state"]), set()):
                raise ValueError(f"invalid job transition: {value['state']} -> {state}")
            if phase not in value["spec"]["phases"]:
                raise ValueError("phase is outside job specification")
            value.update({"state": state, "phase": phase, "updated_at": now_utc()})
            if progress is not None:
                value["progress"] = progress
            if error is not None:
                value["error"] = error
            atomic_json(self.paths.jobs / f"{job_id}.snapshot.json", value)
            JobContext(self.paths, job_id, emit_initial=False).emit(phase, f"JOB_{state}", state, progress=(progress or {}).get("fraction"))
            return value

    def recover(self) -> list[dict[str, Any]]:
        recovered = []
        for path in self.paths.jobs.glob("job-*.snapshot.json"):
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("state") in {"RUNNING", "CANCELLING"}:
                value["state"] = "RECOVERABLE"
                value["recovery_action"] = "resume" if value.get("kind") == "download" else "restart"
                value["updated_at"] = now_utc()
                atomic_json(path, value)
                recovered.append(value)
        return recovered
