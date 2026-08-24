"""Verify a duplicate GUI launch activates the first instance and exits."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="quintara-single-instance-") as root:
        env = os.environ | {"QT_QPA_PLATFORM": "offscreen", "QSG_RHI_BACKEND": "software"}
        command = [sys.executable, "packaging/entrypoint.py", "--root", root]
        first = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            time.sleep(2)
            duplicate = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=10, check=False)
            if duplicate.returncode != 0:
                print(duplicate.stderr, file=sys.stderr)
                return 2
            if first.poll() is not None:
                print("primary GUI exited before duplicate activation", file=sys.stderr)
                return 3
            return 0
        finally:
            first.terminate()
            try:
                first.wait(timeout=5)
            except subprocess.TimeoutExpired:
                first.kill()


if __name__ == "__main__":
    raise SystemExit(main())
