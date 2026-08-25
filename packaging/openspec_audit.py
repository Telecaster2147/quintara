"""Audit OpenSpec task status and requirement-to-evidence coverage.

This is deliberately a read-only audit: it never edits ``tasks.md``.  It makes the
distinction between a requirement mapped to evidence and a release gate that still
needs a native host or an independent review record visible in the candidate manifest.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGE = ROOT / "docs/openspec/openspec/changes/quintara-product-experience-v2"
TASKS = CHANGE / "tasks.md"
EVIDENCE = ROOT / "docs/V2_EVIDENCE_MATRIX.md"
OUTPUT = ROOT / "dist/openspec-audit.json"
ID_RE = re.compile(r"\b(FRC|PPD|DPE|LRO|RRW|DRE)-(\d{3})(?:\s*[-–—]\s*(\d{3}))?\b")

# GitHub's Windows runner defaults stdout to the active legacy code page.  The
# audit intentionally includes Chinese task descriptions, so emit UTF-8 in both
# interactive logs and redirected CI output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _ids(text: str) -> set[str]:
    values: set[str] = set()
    for prefix, start, end in ID_RE.findall(text):
        first = int(start)
        last = int(end or start)
        values.update(f"{prefix}-{number:03d}" for number in range(first, last + 1))
    return values


def _task_status() -> dict[str, object]:
    pattern = re.compile(r"^- \[([ xX])\] (\d+\.\d+) (.+)$")
    tasks: list[dict[str, object]] = []
    for line in TASKS.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            tasks.append({"id": match.group(2), "description": match.group(3), "done": match.group(1).lower() == "x"})
    return {
        "total": len(tasks),
        "complete": sum(bool(task["done"]) for task in tasks),
        "pending": [task for task in tasks if not task["done"]],
        "tasks": tasks,
    }


def _strict_validation() -> dict[str, object]:
    validator = next(
        (shutil.which(name) for name in ("openspec", "openspec.cmd", "openspec.exe") if shutil.which(name)),
        None,
    )
    if validator:
        command = [validator, "validate", "quintara-product-experience-v2", "--strict", "--json"]
    else:
        # npm's global bin directory is not consistently added to PATH by
        # ``uv run`` on Windows.  npx is present on the hosted runner and can
        # invoke the pinned validator without relying on PATHEXT resolution.
        npx = shutil.which("npx.cmd") or shutil.which("npx")
        if npx:
            command = [npx, "--yes", "@fission-ai/openspec@1.9.0", "validate", "quintara-product-experience-v2", "--strict", "--json"]
        else:
            npm = shutil.which("npm.cmd") or shutil.which("npm")
            if not npm:
                return {"status": "unavailable", "error": "openspec, npx and npm were not found on PATH"}
            command = [npm, "exec", "--yes", "--package=@fission-ai/openspec@1.9.0", "--", "openspec", "validate", "quintara-product-experience-v2", "--strict", "--json"]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT / "docs/openspec",
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except OSError as exc:
        return {"status": "unavailable", "error": str(exc)}
    return {"status": "passed" if result.returncode == 0 else "failed", "returncode": result.returncode, "stderr_tail": result.stderr[-1000:]}


def main() -> int:
    spec_ids: set[str] = set()
    for path in sorted((CHANGE / "specs").glob("*/spec.md")):
        spec_ids.update(_ids(path.read_text(encoding="utf-8")))
    evidence_ids = _ids(EVIDENCE.read_text(encoding="utf-8"))
    missing = sorted(spec_ids - evidence_ids)
    extra = sorted(evidence_ids - spec_ids)
    tasks = _task_status()
    validation = _strict_validation()
    checks = {
        "tasks_file_present": TASKS.is_file(),
        "evidence_matrix_present": EVIDENCE.is_file(),
        "all_spec_requirements_mapped": not missing,
        "strict_validation": validation.get("status") == "passed",
        "expected_task_count": tasks["total"] == 126,
    }
    evidence = {
        "schema_version": 1,
        "change": "quintara-product-experience-v2",
        "requirements": {
            "spec_count": len(spec_ids),
            "evidence_count": len(evidence_ids),
            "missing": missing,
            "extra": extra,
        },
        "tasks": tasks,
        "strict_validation": validation,
        "checks": checks,
        "bidirectional_mapping_passed": all(checks.values()),
        "candidate_ready": bool(
            not tasks["pending"]
            and checks["strict_validation"]
            and checks["all_spec_requirements_mapped"]
        ),
        "candidate_blockers": [
            "native Windows/Ubuntu/Debian install and real-window evidence",
            "Linux release bundle glibc baseline audit from the Ubuntu 22.04 builder",
            "Windows installer upgrade/uninstall and icon-cache evidence",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["bidirectional_mapping_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
