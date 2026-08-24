"""Cross-platform locking, atomic publication, and worker helpers."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .core import AppPaths, new_id, now_utc


def subprocess_policy(*, gui_background: bool, platform_name: str | None = None) -> dict[str, Any]:
    """Return one explicit child-process policy for GUI or CLI callers."""
    target = platform_name or os.name
    if target == "nt" and gui_background:
        return {
            "creationflags": int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)),
            "startupinfo": _hidden_startupinfo(),
        }
    return {"start_new_session": target != "nt"}


def _hidden_startupinfo() -> Any:
    startup_class = getattr(subprocess, "STARTUPINFO", None)
    if startup_class is None:
        return None
    info = startup_class()
    info.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 1))
    info.wShowWindow = 0
    return info


class LockBusy(RuntimeError):
    pass


class FileLock:
    def __init__(self, path: Path, timeout: float = 0.0) -> None:
        self.path = path
        self.timeout = timeout
        self._handle = None
        self.owner = new_id("owner")

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()
        while True:
            try:
                self._handle = self.path.open("x", encoding="utf-8")
                self._handle.write(json.dumps({"owner": self.owner, "pid": os.getpid(), "created": now_utc()}))
                self._handle.flush()
                return
            except FileExistsError:
                try:
                    metadata = json.loads(self.path.read_text(encoding="utf-8"))
                    pid = int(metadata.get("pid", 0))
                    if pid and pid != os.getpid():
                        os.kill(pid, 0)
                except (OSError, ValueError, json.JSONDecodeError):
                    # A lock with a dead owner or malformed metadata is stale.
                    self.path.unlink(missing_ok=True)
                    continue
                if time.monotonic() - start >= self.timeout:
                    raise LockBusy(f"another Quintara job owns {self.path}") from None
                time.sleep(0.1)

    def release(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None
            try:
                metadata = json.loads(self.path.read_text(encoding="utf-8"))
                if metadata.get("owner") == self.owner:
                    self.path.unlink()
            except json.JSONDecodeError:
                self.path.unlink(missing_ok=True)
            except FileNotFoundError:
                pass

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{new_id('tmp')}")
    try:
        with temp.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def atomic_json(path: Path, value: object) -> None:
    atomic_write(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode())


def recover_staging(paths: AppPaths) -> list[str]:
    """Remove abandoned staging jobs while retaining a recovery log."""
    removed: list[str] = []
    if paths.data_staging.exists():
        for child in paths.data_staging.iterdir():
            if child.is_dir():
                import shutil

                shutil.rmtree(child, ignore_errors=True)
                removed.append(str(child))
    if paths.results_staging.exists():
        import shutil

        for child in paths.results_staging.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
                removed.append(str(child))
    if removed:
        paths.logs.mkdir(parents=True, exist_ok=True)
        with (paths.logs / "recovery.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"time": now_utc(), "removed": removed}, ensure_ascii=False) + "\n")
    return removed


class Worker:
    def __init__(self, command: list[str], cwd: Path | None = None, *, gui_background: bool = False) -> None:
        self.command = command
        self.cwd = cwd
        self.gui_background = gui_background
        self.process: subprocess.Popen[str] | None = None

    def start(self) -> None:
        policy = subprocess_policy(gui_background=self.gui_background)
        self.process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            start_new_session=bool(policy.get("start_new_session", False)),
            creationflags=int(policy.get("creationflags", 0)),
            startupinfo=policy.get("startupinfo"),
        )

    def lines(self) -> Iterator[str]:
        if self.process and self.process.stdout:
            yield from self.process.stdout

    def cancel(self, grace: float = 5.0) -> int | None:
        if not self.process or self.process.poll() is not None:
            return self.process.returncode if self.process else None
        if os.name == "nt":
            self.process.terminate()
        else:
            os.killpg(self.process.pid, signal.SIGTERM)
        try:
            return self.process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            self.process.kill()
            return self.process.wait()
