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


def _artifact_path(name: str) -> Path:
    """Resolve the platform-specific PyInstaller output name."""
    plain = ROOT / "dist" / name
    return plain if plain.is_file() else ROOT / "dist" / f"{name}.exe"


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
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            artifacts[path.name] = {"sha256": digest, "bytes": path.stat().st_size}
    metadata = {
        "schema_version": 1,
        "built_at": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "python_library": str(Path(sysconfig.get_config_var("LIBDIR") or "") / str(sysconfig.get_config_var("LDLIBRARY") or "")),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "artifacts": artifacts,
    }
    (ROOT / "dist/build-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
