"""Build a Python-free PyInstaller directory used by the OS installers."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    pyinstaller = shutil.which("pyinstaller") or shutil.which("pyinstaller.exe")
    if pyinstaller:
        command = [pyinstaller, "--noconfirm", "--clean", str(ROOT / "packaging/quintara.spec")]
    else:
        command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(ROOT / "packaging/quintara.spec")]
    if not pyinstaller and subprocess.call([sys.executable, "-c", "import PyInstaller"]) != 0:
        print("Install PyInstaller in the release environment before building.", file=sys.stderr)
        return 2
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
