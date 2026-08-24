"""Evaluate the final v2 candidate gate without guessing native evidence.

The normal invocation writes a machine-readable pre-release result and exits
successfully so regular CI can publish diagnostics. ``--strict`` returns
non-zero until every OpenSpec task, native matrix result, ABI check, icon
check, legal-material check, and rollback drill is present. Release status is
based on these reproducible engineering artifacts; no separate reviewer or
release-owner signature is required.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist/candidate-gate.json"


def _read(relative: str) -> dict[str, object] | None:
    path = ROOT / relative
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate Quintara stable candidate evidence")
    parser.add_argument("--strict", action="store_true", help="return 2 while any candidate gate is open")
    args = parser.parse_args(argv)

    audit = _read("dist/openspec-audit.json") or {}
    matrix = _read("dist/test-matrix.json") or {}
    abi = _read("dist/elf-compatibility.json") or {}
    icon = _read("dist/icon-release-audit.json") or {}
    legal = _read("dist/legal-review.json") or {}
    rollback = _read("dist/rollback-drill.json") or {}
    native = _read("dist/native-platform-evidence.json") or {}
    if not native:
        native_records = {}
        for path in sorted((ROOT / "dist").glob("native-*.json")):
            record = _read(str(path.relative_to(ROOT)))
            if record and isinstance(record.get("platform"), str):
                native_records[record["platform"]] = record
        native = {"platforms": native_records}
    tasks = audit.get("tasks") if isinstance(audit.get("tasks"), dict) else {}
    pending = tasks.get("pending", []) if isinstance(tasks, dict) else []
    native_results = native.get("platforms", {}) if isinstance(native.get("platforms"), dict) else {}
    required_native = {"windows-11-x64", "ubuntu-22.04", "ubuntu-24.04", "debian-12", "debian-13", "wslg"}
    native_ok = required_native.issubset(native_results) and all(
        isinstance(native_results[name], dict) and native_results[name].get("status") == "passed"
        for name in required_native
    )
    checks = {
        "openspec_tasks_complete": not pending and audit.get("candidate_ready") is True,
        "local_matrix_passed": matrix.get("local_passed") is True,
        "native_matrix_passed": native_ok,
        "abi_baseline_passed": abi.get("passed") is True,
        "icon_audit_passed": icon.get("passed") is True,
        "legal_review_passed": legal.get("passed") is True,
        "rollback_drill_passed": rollback.get("passed") is True,
    }
    passed = all(checks.values())
    evidence = {
        "schema_version": 1,
        "status": "candidate" if passed else "pre-release",
        "checks": checks,
        "blockers": [name for name, value in checks.items() if not value],
        "strict": args.strict,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if passed or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
