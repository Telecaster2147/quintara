"""Build a Python-free PyInstaller directory used by the OS installers."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
import sysconfig
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_path(name: str) -> Path:
    """Resolve the platform-specific PyInstaller output name."""
    plain = ROOT / "dist" / name
    windows = ROOT / "dist" / f"{name}.exe"
    # A release workspace may retain both Linux and Windows artifacts.  Select
    # the output for the interpreter that performed this build instead of
    # silently hashing the other platform's stale file.
    if sys.platform == "win32":
        return windows if windows.is_file() else plain
    return plain if plain.is_file() else windows


def main() -> int:
    pyinstaller = shutil.which("pyinstaller") or shutil.which("pyinstaller.exe")
    if not pyinstaller and subprocess.call([sys.executable, "-c", "import PyInstaller"]) != 0:
        print("Install PyInstaller in the release environment before building.", file=sys.stderr)
        return 2
    prefix = [pyinstaller] if pyinstaller else [sys.executable, "-m", "PyInstaller"]
    for spec in ("quintara.spec", "quintara-cli.spec"):
        result = subprocess.call(prefix + ["--noconfirm", "--clean", str(ROOT / "packaging" / spec)], cwd=ROOT)
        if result:
            return result
    artifacts = {}
    for name in ("Quintara", "quintara-cli"):
        path = _artifact_path(name)
        if path.is_file():
            digest = _sha256(path)
            artifacts[path.name] = {"sha256": digest, "bytes": path.stat().st_size}
    metadata = {
        "schema_version": 1,
        "built_at": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "python_library": str(Path(sysconfig.get_config_var("LIBDIR") or "") / str(sysconfig.get_config_var("LDLIBRARY") or "")),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "artifacts": artifacts,
        "developer_data": {},
    }
    developer_data = ROOT / "packaging/developer_data/quintara-developer-data-v1.zip"
    if developer_data.is_file():
        metadata["developer_data"] = {
            "relative_install_path": "data/developer/quintara-developer-data-v1.zip",
            "sha256": _sha256(developer_data),
            "bytes": developer_data.stat().st_size,
        }
    (ROOT / "dist/build-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
