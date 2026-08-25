"""Create a reproducible, local release-evidence manifest."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def evidence_file(relative: str) -> dict[str, object]:
    path = ROOT / relative
    if not path.exists():
        return {"status": "not-generated", "path": relative}
    return {"status": "present", "path": relative, "sha256": sha256(path), "bytes": path.stat().st_size}


def main() -> int:
    tracked = [
        ROOT / "uv.lock",
        ROOT / "pyproject.toml",
        ROOT / "fixtures/manifest.json",
        ROOT / "README.md",
    ]
    schema_files = [
        ROOT / "docs/CSV_FIELD_DICTIONARY.md",
        ROOT / "docs/LEGAL_NOTICE.md",
        ROOT / "docs/PRIVACY.md",
    ]
    artifact_root = ROOT / "dist"
    artifacts = {}
    if artifact_root.exists():
        for path in sorted(artifact_root.rglob("*")):
            if path.is_file() and path.name != "release-evidence.json":
                artifacts[str(path.relative_to(ROOT))] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    evidence = {
        "schema_version": 1,
        "git_revision": git_revision(),
        "inputs": {str(path.relative_to(ROOT)): {"sha256": sha256(path), "bytes": path.stat().st_size} for path in tracked if path.exists()},
        "schemas": {str(path.relative_to(ROOT)): {"sha256": sha256(path), "bytes": path.stat().st_size} for path in schema_files if path.exists()},
        "artifacts": artifacts,
        "test_result": (
            {"path": "dist/pytest.xml", "sha256": sha256(ROOT / "dist/pytest.xml"), "bytes": (ROOT / "dist/pytest.xml").stat().st_size}
            if (ROOT / "dist/pytest.xml").exists()
            else {"status": "not-generated; run pytest --junitxml=dist/pytest.xml"}
        ),
        "gates": {
            "ci": "GitHub Actions Quintara CI matrix",
            "package": "GitHub Actions Package smoke Linux/Windows",
        },
        "artifact_policy": {
            "historical_market_data_bundled": True,
            "developer_data_location": "data/developer/quintara-developer-data-v1.zip beside the application",
            "developer_data": evidence_file("packaging/developer_data/quintara-developer-data-v1.zip"),
            "telemetry": False,
            "result_export": "CSV plus adjacent provenance manifest",
        },
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "visual_evidence": {
            str(path.relative_to(ROOT)): {"sha256": sha256(path), "bytes": path.stat().st_size}
            for path in sorted((ROOT / "docs/evidence").glob("*.png"))
        },
        "native_evidence": {
            str(path.relative_to(ROOT)): {"sha256": sha256(path), "bytes": path.stat().st_size}
            for path in sorted((ROOT / "docs/evidence").glob("v2-*-native.json"))
        },
        "journeys": {
            "pytest_junit": "dist/pytest.xml",
            "linux_ordinary_user": "dist/linux-user-journey.json",
            "windows_no_console": "packaging/windows/smoke.ps1",
        },
        "verification": {
            "test_matrix": evidence_file("dist/test-matrix.json"),
            "openspec_audit": evidence_file("dist/openspec-audit.json"),
            "icon_release_audit": evidence_file("dist/icon-release-audit.json"),
            "legal_review": evidence_file("dist/legal-review.json"),
            "visual_matrix": evidence_file("dist/visual-matrix/manifest.json"),
            "build_metadata": evidence_file("dist/build-metadata.json"),
            "elf_compatibility": evidence_file("dist/elf-compatibility.json"),
            "candidate_gate": evidence_file("dist/candidate-gate.json"),
            "native_platform_evidence": evidence_file("dist/native-platform-evidence.json"),
        },
        "candidate": (
            json.loads((ROOT / "dist/candidate-gate.json").read_text(encoding="utf-8"))
            if (ROOT / "dist/candidate-gate.json").is_file()
            else {
                "status": "pre-release",
                "reason": "native platform, installer, icon-cache, and package evidence are required before stable labeling",
            }
        ),
        "known_items": [
            "Windows 10 22H2, WSLg and NVIDIA GPU are best-effort",
            "developer data output is checked against its packaged reference result",
        ],
    }
    output = ROOT / "dist/release-evidence.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
