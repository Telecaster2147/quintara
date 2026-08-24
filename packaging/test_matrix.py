"""Run the repository-local release test matrix and write machine-readable evidence.

The required native hosts are intentionally represented separately from local checks.  A
Linux/WSLg run can prove the source and bundle contract here, while the Windows and
Debian/Ubuntu jobs remain explicit CI inputs instead of being inferred from an offscreen
process.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist/test-matrix.json"


def _command(
    name: str,
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout: int = 600,
    acceptable_returncodes: tuple[int, ...] = (0,),
) -> dict[str, object]:
    started = time.perf_counter()
    merged = os.environ.copy()
    merged.update(env or {})
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=merged,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        status = "passed" if result.returncode in acceptable_returncodes else "failed"
        error = None
    except subprocess.TimeoutExpired as exc:
        result = None
        status = "timeout"
        error = str(exc)
    except OSError as exc:
        result = None
        status = "unavailable"
        error = str(exc)
    evidence: dict[str, object] = {
        "status": status,
        "command": command,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    if result is not None:
        evidence["returncode"] = result.returncode
        if result.returncode != 0 and result.returncode in acceptable_returncodes:
            evidence["expected_returncode"] = True
        evidence["stdout_tail"] = result.stdout[-2000:]
        evidence["stderr_tail"] = result.stderr[-2000:]
    if error:
        evidence["error"] = error
    print(f"[{status}] {name}")
    return evidence


def _qml_lint_command() -> list[str] | None:
    candidates = [ROOT / ".venv/bin/pyside6-qmllint", Path(shutil.which("pyside6-qmllint") or "")]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return [str(candidate), "-I", "src/quintara/qml", *map(str, sorted((ROOT / "src/quintara/qml").rglob("*.qml")))]
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local Quintara release checks")
    parser.add_argument("--skip-visual", action="store_true", help="skip the 36-image visual capture")
    parser.add_argument("--skip-benchmark", action="store_true", help="skip production-scale performance evidence")
    args = parser.parse_args(argv)
    python = sys.executable
    env = {"QT_QPA_PLATFORM": "offscreen", "QT_QUICK_CONTROLS_STYLE": "Basic", "QSG_RHI_BACKEND": "software"}
    checks: dict[str, dict[str, object]] = {}
    checks["unit_property_contract_gui"] = _command(
        "unit/property/contract/gui", [python, "-m", "pytest", "-q", "--junitxml=dist/pytest.xml"], timeout=900
    )
    checks["ruff"] = _command("ruff", [python, "-m", "ruff", "check", "src", "tests", "packaging"])
    checks["typecheck"] = _command("typecheck", [python, "packaging/typecheck.py"], timeout=300)
    qml_command = _qml_lint_command()
    checks["qml_lint"] = (
        _command("qmllint", qml_command, timeout=300)
        if qml_command
        else {"status": "unavailable", "reason": "pyside6-qmllint not found"}
    )
    checks["linux_user_journey"] = _command("ordinary-user-linux-journey", [python, "packaging/linux_user_journey.py"], env=env, timeout=900)
    checks["single_instance"] = _command("single-instance", [python, "packaging/single_instance_smoke.py"], env=env, timeout=120)
    if args.skip_visual:
        checks["visual_regression"] = {"status": "skipped", "reason": "--skip-visual"}
    else:
        checks["visual_regression"] = _command("visual-regression", [python, "packaging/visual_matrix.py"], env=env, timeout=900)
    if args.skip_benchmark:
        checks["production_scale"] = {"status": "skipped", "reason": "--skip-benchmark"}
    else:
        checks["production_scale"] = _command("production-scale", [python, "packaging/production_scale_benchmark.py"], timeout=900)
    checks["icon_release"] = _command("icon-release", [python, "packaging/icon_release_audit.py"], timeout=120)
    checks["legal_wording"] = _command("legal-wording", [python, "packaging/legal_review.py"], timeout=120)
    checks["rollback_drill"] = _command("catalog-rollback-drill", [python, "packaging/rollback_drill.py"], timeout=120)
    checks["cli_regression"] = _command("cli-version", [python, "-m", "quintara", "--version"], timeout=120)
    bundle = ROOT / "dist/Quintara"
    cli_bundle = ROOT / "dist/quintara-cli"
    if bundle.is_file() and cli_bundle.is_file():
        checks["bundle_cli_regression"] = _command("bundled-cli-version", [str(cli_bundle), "--version"], timeout=120)
        bundle_root = tempfile.mkdtemp(prefix="quintara-test-matrix-bundle-")
        checks["bundle_gui_offscreen"] = _command(
            "bundled-gui-offscreen",
            ["timeout", "8", str(bundle), "--root", bundle_root],
            env=env,
            timeout=30,
            acceptable_returncodes=(0, 124),
        )
    else:
        checks["bundle_cli_regression"] = {"status": "unavailable", "reason": "bundle not built"}
        checks["bundle_gui_offscreen"] = {"status": "unavailable", "reason": "bundle not built"}
    with tempfile.TemporaryDirectory(prefix="quintara-matrix-prefix-") as prefix:
        checks["linux_prefix_install"] = _command(
            "linux-prefix-install",
            ["bash", "packaging/install_linux.sh"],
            env={"QUINTARA_PREFIX": prefix},
            timeout=120,
        )
        checks["linux_prefix_cli"] = _command(
            "installed-cli-version",
            [str(Path(prefix) / "bin/quintara-cli"), "--version"],
            timeout=120,
        )
        icon_paths = [
            Path(prefix) / "share/icons/hicolor" / f"{size}x{size}/apps/quintara.png"
            for size in (16, 20, 24, 32, 48, 64, 128, 256)
        ]
        missing_icons = [str(path) for path in icon_paths if not path.is_file()]
        checks["linux_prefix_icon_family"] = {
            "status": "passed" if not missing_icons else "failed",
            "expected_sizes": [16, 20, 24, 32, 48, 64, 128, 256],
            "missing": missing_icons,
        }

    native = {
        "windows-11-x64": {"status": "external_ci_required", "workflow": ".github/workflows/platform-matrix.yml"},
        "windows-10-22H2": {"status": "best_effort_external_ci_required", "workflow": ".github/workflows/platform-matrix.yml"},
        "ubuntu-22.04": {"status": "external_ci_required", "workflow": ".github/workflows/platform-matrix.yml"},
        "ubuntu-24.04": {"status": "external_ci_required", "workflow": ".github/workflows/platform-matrix.yml"},
        "debian-12": {"status": "external_ci_required", "workflow": ".github/workflows/platform-matrix.yml"},
        "debian-13": {"status": "external_ci_required", "workflow": ".github/workflows/platform-matrix.yml"},
        "wslg": {"status": "external_or_local_native_evidence", "workflow": ".github/workflows/platform-matrix.yml"},
    }
    # Native probes are additive evidence; a partial Debian/WSLg run never gets
    # promoted to a full release gate without the complete workflow scope.
    native_evidence = {
        "debian-12": ROOT / "docs/evidence/v2-debian12-native.json",
        "ubuntu-24.04": ROOT / "docs/evidence/v2-ubuntu24-installed-prefix.json",
        "wslg": ROOT / "docs/evidence/v2-ubuntu24-wslg-native.json",
    }
    for platform_name, path in native_evidence.items():
        if path.is_file():
            native[platform_name]["evidence"] = str(path.relative_to(ROOT))
            native[platform_name]["status"] = "partial_native_evidence"
    passed = all(item.get("status") == "passed" for item in checks.values() if item.get("status") != "skipped")
    evidence = {
        "schema_version": 1,
        "python": sys.version,
        "local": checks,
        "native": native,
        "local_passed": passed,
        "stable_candidate": False,
        "candidate_reason": "native platform and required data-rights/release review sign-offs are recorded separately",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
