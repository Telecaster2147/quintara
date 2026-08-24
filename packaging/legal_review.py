"""Check the versioned product/legal wording and release notices as one gate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "docs/LEGAL_NOTICE.md": ("研究", "收益", "交易"),
    "docs/PRIVACY.md": ("遥测", "本地"),
    "docs/THIRD_PARTY_NOTICES.md": ("Qt", "LightGBM"),
    "docs/LEGAL_REVIEW_RECORD.md": ("工程审阅状态", "候选门禁"),
}


def main() -> int:
    checks = {}
    hashes = {}
    for relative, phrases in REQUIRED.items():
        path = ROOT / relative
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        checks[relative] = bool(text) and all(phrase in text for phrase in phrases)
        hashes[relative] = hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None
    sbom = ROOT / "dist/sbom.json"
    if sbom.exists():
        inventory = json.loads(sbom.read_text(encoding="utf-8"))
        names = {item.get("name") for item in inventory.get("components", [])}
        checks["sbom_components"] = {"Qt/PySide6": "PySide6" in names, "LightGBM": "lightgbm" in names, "Inno": "Inno Setup" in names}
    else:
        checks["sbom_components"] = False
    evidence = {
        "schema_version": 1,
        "review_type": "engineering wording and provenance review",
        "checks": checks,
        "document_hashes": hashes,
        "status": "engineering_review_pass_with_required_review_signoff_gate",
        "required_signoff_fields": ["DATA_RIGHTS_REVIEWER", "RELEASE_MANAGER"],
        "passed": all(value if isinstance(value, bool) else all(value.values()) for value in checks.values()),
    }
    output = ROOT / "dist/legal-review.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
