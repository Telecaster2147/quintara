"""Stable domain values shared by GUI, CLI, and workers."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class UniverseMode(StrEnum):
    PIT_BASELINE = "PIT_BASELINE"
    CUSTOM_UNIVERSE = "CUSTOM_UNIVERSE"
    NON_PIT_FALLBACK = "NON_PIT_FALLBACK"


class JobState(StrEnum):
    PLANNING = "PLANNING"
    READY = "READY"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSING = "PAUSING"
    CANCELLING = "CANCELLING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    CACHED = "CACHED"
    RECOVERED = "RECOVERED"
    RECOVERABLE = "RECOVERABLE"


class Severity(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    message: str
    field: str | None = None
    row: int | None = None
    key: str | None = None
    docs: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self) | {"severity": self.severity.value}


@dataclass(frozen=True)
class RuntimeIdentity:
    python: str
    platform: str
    machine: str
    processor: str
    cpu_count: int
    memory_bytes: int
    gpu: str | None = None
    gpu_driver: str | None = None


@dataclass(frozen=True)
class ModelIdentity:
    schema_version: int
    mode: UniverseMode
    universe_id: str
    universe_generation: str
    market_data_generation: str
    membership_generation: str
    listing_generation: str
    calendar_generation: str
    label_contract: str
    feature_contract: str
    kernel_version: str
    source_hash: str
    config_hash: str
    training_start: str
    training_cutoff: str
    runtime_lock_hash: str
    device_profile: str

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["mode"] = self.mode.value
        return value


@dataclass
class AppPaths:
    root: Path

    @classmethod
    def discover(cls, override: str | Path | None = None) -> AppPaths:
        if override:
            root = Path(override).expanduser()
        elif os.name == "nt":
            root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "Quintara"
        else:
            root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "quintara"
        if override is None:
            marker = root.expanduser() / "migration.json"
            try:
                selected = Path(json.loads(marker.read_text(encoding="utf-8"))["active_root"]).expanduser()
                if selected.is_absolute() and selected.exists():
                    root = selected
            except (OSError, KeyError, TypeError, json.JSONDecodeError):
                pass
        return cls(root.resolve())

    @property
    def config(self) -> Path:
        return self.root / "config.json"

    @property
    def registry(self) -> Path:
        return self.root / "registry.sqlite3"

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def data_generations(self) -> Path:
        return self.data / "generations"

    @property
    def data_staging(self) -> Path:
        return self.data / "staging"

    @property
    def data_checkpoints(self) -> Path:
        return self.data / "checkpoints"

    @property
    def active_data(self) -> Path:
        return self.data / "active.json"

    @property
    def universes(self) -> Path:
        return self.root / "universes"

    @property
    def models(self) -> Path:
        return self.root / "models"

    @property
    def results(self) -> Path:
        return self.root / "results"

    @property
    def results_staging(self) -> Path:
        return self.results / ".staging"

    @property
    def jobs(self) -> Path:
        return self.root / "jobs"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def diagnostics(self) -> Path:
        return self.root / "diagnostics"

    @property
    def consent(self) -> Path:
        return self.root / "consent.json"

    @property
    def lock(self) -> Path:
        return self.root / "quintara.lock"

    def ensure(self) -> None:
        for path in (
            self.root,
            self.data_generations,
            self.data_staging,
            self.data_checkpoints,
            self.universes,
            self.models,
            self.results,
            self.results_staging,
            self.jobs,
            self.logs,
            self.diagnostics,
        ):
            path.mkdir(parents=True, exist_ok=True)


def canonical_json(value: Any) -> bytes:
    """Stable JSON bytes; timestamps/paths must be omitted by callers."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()


def content_hash(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        payload = bytes(value)
    elif isinstance(value, Path):
        payload = value.read_bytes()
    else:
        payload = canonical_json(value)
    return hashlib.sha256(payload).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def now_utc() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str = "job") -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def app_version() -> str:
    try:
        from . import __version__

        return __version__
    except ImportError:
        return "0.0.0"


def runtime_identity() -> RuntimeIdentity:
    memory = 0
    try:
        import psutil  # type: ignore[import-not-found]

        memory = int(psutil.virtual_memory().total)
    except Exception:
        if os.name == "nt":
            try:
                import ctypes

                class _MemoryStatus(ctypes.Structure):
                    _fields_ = [
                        ("length", ctypes.c_ulong),
                        ("memory_load", ctypes.c_ulong),
                        ("total_phys", ctypes.c_ulonglong),
                        ("available_phys", ctypes.c_ulonglong),
                        ("total_page", ctypes.c_ulonglong),
                        ("available_page", ctypes.c_ulonglong),
                        ("total_virtual", ctypes.c_ulonglong),
                        ("available_virtual", ctypes.c_ulonglong),
                        ("available_extended", ctypes.c_ulonglong),
                    ]

                status = _MemoryStatus()
                status.length = ctypes.sizeof(_MemoryStatus)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                    memory = int(status.total_phys)
            except (AttributeError, OSError, TypeError):
                memory = 0
        if hasattr(os, "sysconf"):
            try:
                memory = int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
            except (OSError, ValueError):
                memory = 0
    return RuntimeIdentity(
        python=sys.version.split()[0],
        platform=platform.platform(),
        machine=platform.machine(),
        processor=platform.processor(),
        cpu_count=os.cpu_count() or 1,
        memory_bytes=memory,
    )


DEFAULT_WEIGHTS = (0.40, 0.25, 0.15, 0.12, 0.08)
DEFAULT_LABEL = "close_t5_over_open_t1_minus_1"
COMPETITION_LABEL = "open_t5_over_open_t1_minus_1"
PRODUCT_LABEL_VERSION = "quintara-close5-open1-v1"
COMPETITION_LABEL_VERSION = "competition-open-open-v1"
