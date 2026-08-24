"""Emit a small local CycloneDX-style inventory for release evidence."""
from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path

PACKAGES = ("quintara", "baostock", "lightgbm", "numpy", "pandas", "scipy", "PySide6", "shiboken6")

components = []
for name in PACKAGES:
    try:
        metadata = importlib.metadata.metadata(name)
        version = metadata["Version"]
    except importlib.metadata.PackageNotFoundError:
        continue
    components.append(
        {
            "type": "library",
            "name": name,
            "version": version,
            "licenses": [value for value in (metadata.get("License"), metadata.get("License-Expression")) if value],
            "homepage": metadata.get("Home-page") or metadata.get("Project-URL"),
        }
    )
components.extend(
    [
        {"type": "application", "name": "Inno Setup", "version": "6", "licenses": ["Inno Setup License"], "scope": "build"},
        {"type": "data", "name": "Quintara production dataset", "version": "channel-manifest", "licenses": ["Per dataset manifest"], "scope": "optional"},
    ]
)
out = {"bomFormat": "CycloneDX", "specVersion": "1.5", "components": components}
Path("dist").mkdir(exist_ok=True)
Path("dist/sbom.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(out, indent=2, ensure_ascii=False))
