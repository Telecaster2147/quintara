"""Check the glibc baseline used for Linux frozen artifacts.

PyInstaller embeds the Python shared library in the one-file executable.  A
bundle built on a newer distribution can therefore pass a local smoke test and
still fail on Debian 12 with a missing GLIBC symbol.  Release Linux artifacts
are built on Ubuntu 22.04 and this audit records the builder's Python ABI and
fails when it is newer than the declared deployment baseline.
"""
from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist/elf-compatibility.json"
GLIBC_RE = re.compile(rb"GLIBC_(\d+)\.(\d+)")


def _version(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)", value.strip())
    if not match:
        raise ValueError(f"invalid glibc version: {value!r}")
    return int(match.group(1)), int(match.group(2))


def _max_glibc(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    versions = {(int(match.group(1)), int(match.group(2))) for match in GLIBC_RE.finditer(data)}
    return f"{max(versions)[0]}.{max(versions)[1]}" if versions else None


def _python_library() -> Path | None:
    libdir = sysconfig.get_config_var("LIBDIR")
    library = sysconfig.get_config_var("LDLIBRARY")
    if not libdir or not library:
        return None
    path = Path(libdir) / library
    return path if path.is_file() else None


def _elf_probe(path: Path) -> dict[str, object]:
    result: dict[str, object] = {"path": str(path.relative_to(ROOT)), "present": path.is_file()}
    if not path.is_file():
        return result
    result["bytes"] = path.stat().st_size
    result["sha256"] = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
    result["embedded_strings_max_glibc"] = _max_glibc(path)
    file_command = shutil.which("file")
    if file_command:
        result["file"] = subprocess.run(
            [file_command, str(path)], capture_output=True, text=True, check=False
        ).stdout.strip()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit Linux frozen artifact glibc compatibility")
    parser.add_argument("--max-glibc", default="2.35", help="maximum builder ABI accepted by release")
    parser.add_argument(
        "artifacts",
        nargs="*",
        type=Path,
        default=[ROOT / "dist/Quintara", ROOT / "dist/quintara-cli"],
    )
    args = parser.parse_args(argv)
    allowed = _version(args.max_glibc)
    python_library = _python_library()
    python_max = _max_glibc(python_library) if python_library else None
    python_tuple = _version(python_max) if python_max else None
    probes = [_elf_probe(path if path.is_absolute() else ROOT / path) for path in args.artifacts]
    passed = python_tuple is not None and python_tuple <= allowed and all(
        bool(probe.get("present")) for probe in probes
    )
    evidence = {
        "schema_version": 1,
        "deployment_baseline_glibc": args.max_glibc,
        "python_library": str(python_library) if python_library else None,
        "python_library_max_glibc": python_max,
        "python": sys.version,
        "platform": platform.platform(),
        "artifacts": probes,
        "passed": passed,
        "reason": (
            "builder Python ABI is within the deployment baseline"
            if passed
            else "rebuild Linux release artifacts on the declared oldest supported builder"
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
