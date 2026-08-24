"""Read-only v1 discovery for explicit v2 migration decisions."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import validate_artifact_closure
from .core import file_hash, now_utc


def scan_legacy_root(root: Path) -> dict[str, Any]:
    """Index legacy artifacts without renaming, rewriting, or activating them."""
    records = []
    patterns = (("data", "data/generations/*/manifest.json"), ("model", "models/*/manifest.json"), ("result", "results/*/manifest.json"))
    for kind, pattern in patterns:
        for path in sorted(root.glob(pattern)):
            try:
                manifest = json.loads(path.read_text(encoding="utf-8"))
                valid_files = all(
                    (path.parent / name).is_file() and file_hash(path.parent / name) == details.get("sha256")
                    for name, details in manifest.get("files", {}).items()
                )
                identity_complete = True
                if kind == "result" and manifest.get("model_identity"):
                    try:
                        validate_artifact_closure(manifest.get("data_manifest", {}), manifest["model_identity"], manifest)
                    except (KeyError, TypeError, ValueError):
                        identity_complete = False
                records.append(
                    {
                        "kind": kind,
                        "path": str(path),
                        "id": manifest.get("generation") or manifest.get("run_id") or path.parent.name,
                        "read_only": True,
                        "file_integrity": valid_files,
                        "identity_complete": identity_complete,
                        "status": "compatible" if valid_files and identity_complete else "pending_revalidation",
                    }
                )
            except (OSError, json.JSONDecodeError):
                records.append({"kind": kind, "path": str(path), "read_only": True, "status": "pending_revalidation"})
    return {"schema_version": 1, "legacy_root": str(root), "scanned_at": now_utc(), "records": records, "mutated": False}
