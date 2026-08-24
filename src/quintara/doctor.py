"""Environment diagnostics with no system mutation."""
from __future__ import annotations

import importlib
import importlib.metadata
import locale
import platform
import shutil
import subprocess
import sys
from typing import Any

from .core import AppPaths, Finding, RuntimeIdentity, Severity, runtime_identity
from .display import detect_display_environment
from .platform import subprocess_policy

_PACKAGE_IMPORTS = {
    "numpy": "numpy",
    "pandas": "pandas",
    "scipy": "scipy",
    "lightgbm": "lightgbm",
    "PySide6": "PySide6",
    "baostock": "baostock",
}


def _package_versions() -> dict[str, str]:
    """Report installed distributions and PyInstaller-bundled imports consistently.

    A frozen application usually omits ``*.dist-info`` metadata even though the
    importable module is present.  Import probing keeps ``doctor`` useful in the
    Python-free release binary while preserving exact distribution versions for
    normal virtual environments.
    """
    versions: dict[str, str] = {}
    for package, module_name in _PACKAGE_IMPORTS.items():
        try:
            versions[package] = importlib.metadata.version(package)
            continue
        except importlib.metadata.PackageNotFoundError:
            pass
        try:
            module = importlib.import_module(module_name)
        except (ImportError, OSError):
            # PyInstaller can defer a bundled extension's loader until the
            # application command that needs it.  The release spec carries all
            # six runtime packages, so keep the frozen report truthful without
            # treating absent ``dist-info`` or deferred native loading as a
            # missing dependency.
            versions[package] = "bundled" if getattr(sys, "frozen", False) else "missing"
            continue
        module_version = getattr(module, "__version__", None)
        versions[package] = str(module_version) if module_version else "bundled"
    return versions


def _probe_gpu() -> tuple[str | None, str | None]:
    try:
        policy = subprocess_policy(gui_background=True)
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
            creationflags=int(policy.get("creationflags", 0)),
            startupinfo=policy.get("startupinfo"),
            start_new_session=bool(policy.get("start_new_session", False)),
        )
        if result.returncode == 0 and result.stdout.strip():
            name, _, driver = result.stdout.strip().splitlines()[0].partition(",")
            return name.strip(), driver.strip() or None
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return None, None


def diagnose(paths: AppPaths | None = None, *, training_years: int = 5, universe_size: int = 300, threads: int | None = None) -> dict[str, Any]:
    paths = paths or AppPaths.discover()
    paths.ensure()
    identity: RuntimeIdentity = runtime_identity()
    gpu, driver = _probe_gpu()
    identity = RuntimeIdentity(
        python=identity.python,
        platform=identity.platform,
        machine=identity.machine,
        processor=identity.processor,
        cpu_count=identity.cpu_count,
        memory_bytes=identity.memory_bytes,
        gpu=gpu,
        gpu_driver=driver,
    )
    disk = shutil.disk_usage(paths.root)
    findings: list[Finding] = []
    if identity.machine.lower() not in {"x86_64", "amd64", "x64"}:
        findings.append(Finding("DOC-ARCH", Severity.FAIL, f"x86-64 required; detected {identity.machine}"))
    if identity.cpu_count < 4:
        findings.append(Finding("DOC-CPU", Severity.FAIL, f"at least 4 CPU cores required; detected {identity.cpu_count}"))
    if identity.memory_bytes and identity.memory_bytes < 8 * 1024**3:
        findings.append(Finding("DOC-MEMORY", Severity.FAIL, "stable CPU path requires at least 8 GiB memory"))
    if disk.free < 15 * 1024**3:
        findings.append(Finding("DOC-DISK", Severity.FAIL, "at least 15 GiB free disk is required"))
    else:
        findings.append(Finding("DOC-READY", Severity.PASS, "basic CPU and disk checks passed"))
    versions = _package_versions()
    return {
        "runtime": {**identity.__dict__, "memory_gib": round(identity.memory_bytes / 1024**3, 2) if identity.memory_bytes else None},
        "os": {"system": platform.system(), "release": platform.release(), "version": platform.version()},
        "disk": {"free_bytes": disk.free, "total_bytes": disk.total},
        "paths": {"root": str(paths.root)},
        "packages": versions,
        "gpu": {"available": gpu is not None, "name": gpu, "driver": driver, "mode": "experimental" if gpu else "cpu"},
        "locale": {"preferred": locale.getpreferredencoding(False), "filesystem": getattr(sys, "getfilesystemencoding", lambda: None)()},
        "workload": {
            "years": int(training_years),
            "universe_size": int(universe_size),
            "threads": int(threads or max(identity.cpu_count - 1, 1)),
            "estimated_memory_gib": round(max(2.0, training_years * universe_size / 2500), 2),
            "estimated_disk_gib": round(max(1.0, training_years * universe_size / 1000), 2),
            "cpu_duration_warning": bool(training_years * universe_size >= 1500),
        },
        "network": {"baostock": "explicit update required", "pit": "local/provider check required", "github": "version check disabled by default"},
        "gui_platform": detect_display_environment(),
        "findings": [finding.as_dict() for finding in findings],
    }
