"""Pre-Qt desktop detection for Windows, X11, Wayland, WSLg and terminals."""
from __future__ import annotations

import os
import platform
import stat
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def detect_display_environment(env: Mapping[str, str] | None = None, *, system: str | None = None) -> dict[str, Any]:
    values = dict(os.environ if env is None else env)
    target = system or platform.system()
    if target == "Windows":
        return {"kind": "windows", "qt_platform": "windows", "gui_available": True, "wslg": False}
    wsl = bool(values.get("WSL_INTEROP") or values.get("WSL_DISTRO_NAME"))
    wayland = values.get("WAYLAND_DISPLAY")
    display = values.get("DISPLAY")
    runtime = values.get("XDG_RUNTIME_DIR")
    if wsl and (wayland or display):
        kind = "wslg"
    elif wayland:
        kind = "wayland"
    elif display:
        kind = "x11"
    else:
        kind = "terminal"
    qt_platform = "wayland" if wayland else "xcb" if display else None
    return {
        "kind": kind,
        "qt_platform": qt_platform,
        "gui_available": qt_platform is not None,
        "wslg": kind == "wslg",
        "display": display,
        "wayland_display": wayland,
        "runtime_dir": runtime,
    }


def prepare_qt_environment(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Choose a viable plugin and repair only the current process runtime dir."""
    values = os.environ if env is None else env
    report = detect_display_environment(values)
    if not report["gui_available"]:
        return report | {"action": "use-cli"}
    if report["qt_platform"] == "wayland":
        wslg_runtime = Path("/mnt/wslg/runtime-dir")
        configured_runtime = values.get("XDG_RUNTIME_DIR")
        runtime = (
            wslg_runtime
            if report.get("wslg") and (wslg_runtime / str(values.get("WAYLAND_DISPLAY", "wayland-0"))).exists()
            else Path(configured_runtime)
            if configured_runtime
            else Path(tempfile.gettempdir()) / f"quintara-runtime-{os.getpid()}"
        )
        try:
            if runtime != wslg_runtime:
                runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
                runtime.chmod(stat.S_IRWXU)
            socket = runtime / str(values.get("WAYLAND_DISPLAY", "wayland-0"))
            if not socket.exists() and values.get("DISPLAY"):
                report["qt_platform"] = "xcb"
            values["XDG_RUNTIME_DIR"] = str(runtime)
        except OSError:
            if values.get("DISPLAY"):
                report["qt_platform"] = "xcb"
    values.setdefault("QT_QPA_PLATFORM", str(report["qt_platform"]))
    return report | {"action": "launch", "effective_qt_platform": values.get("QT_QPA_PLATFORM")}
