"""Run ty on first-party product code while preserving the vendored kernel boundary.

The competition kernel is intentionally kept byte-for-byte compatible with the
source baseline.  Its pandas typing surface is checked by runtime/integration
tests; product adapters are checked here with an explicit file list so the
selection behaves identically on POSIX and Windows path implementations.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    files = sorted(
        str(path.relative_to(ROOT))
        for path in (ROOT / "src").rglob("*.py")
        if "_kernel" not in path.parts
    )
    command = [
        sys.executable,
        "-m",
        "ty",
        "check",
        "--python",
        str(ROOT / ".venv"),
        "--ignore",
        "unresolved-import",
        *files,
    ]
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
