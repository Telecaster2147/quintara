"""Discovery and metadata for the read-only developer data shipped beside the app."""
from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any

DEVELOPER_DATA_ENV = "QUINTARA_DEVELOPER_DATA"
DEVELOPER_DATA_RELATIVE = Path("data") / "developer"
DEVELOPER_DATA_ARCHIVE = "quintara-developer-data-v1.zip"


def _candidate_roots() -> tuple[Path, ...]:
    candidates: list[Path] = []
    explicit = os.environ.get(DEVELOPER_DATA_ENV, "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())

    if getattr(sys, "frozen", False):
        # The installer and portable archive keep the CSV package beside the
        # executable. PyInstaller's temporary extraction directory is a final
        # compatibility fallback for custom one-file builds.
        candidates.append(Path(sys.executable).resolve().parent / DEVELOPER_DATA_RELATIVE)
        extraction_root = getattr(sys, "_MEIPASS", "")
        if extraction_root:
            candidates.append(Path(extraction_root) / DEVELOPER_DATA_RELATIVE)

    repository_root = Path(__file__).resolve().parents[2]
    candidates.append(repository_root / "packaging" / "developer_data")
    candidates.append(Path(__file__).resolve().parent / DEVELOPER_DATA_RELATIVE)
    return tuple(path.resolve() for path in candidates)


def developer_data_package() -> Path | None:
    """Return the first complete package without copying it to user storage."""
    for candidate in _candidate_roots():
        archive = candidate / DEVELOPER_DATA_ARCHIVE if candidate.is_dir() else candidate
        if archive.is_file() and zipfile.is_zipfile(archive):
            try:
                with zipfile.ZipFile(archive) as bundle:
                    if "dataset-manifest.json" in bundle.namelist():
                        return archive
            except (OSError, zipfile.BadZipFile):
                continue
        if (candidate / "dataset-manifest.json").is_file():
            return candidate
    return None


def developer_data_root() -> Path | None:
    """Return the installation directory containing the developer package."""
    package = developer_data_package()
    return package.parent if package is not None and package.is_file() else package


def _manifest(package: Path) -> dict[str, Any]:
    if package.is_dir():
        return json.loads((package / "dataset-manifest.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(package) as bundle:
        return json.loads(bundle.read("dataset-manifest.json").decode("utf-8"))


def developer_data_summary() -> dict[str, Any]:
    package = developer_data_package()
    if package is None:
        return {
            "available": False,
            "path": "",
            "version": "",
            "coverage": "",
            "size": "",
            "dataset_id": "",
        }
    manifest = _manifest(package)
    market = next((item for item in manifest.get("files", []) if item.get("path") == "market.csv"), {})
    total = sum(int(item.get("bytes", 0)) for item in manifest.get("files", []))
    return {
        "available": True,
        "path": str(package),
        "version": str(manifest.get("version", "")),
        "coverage": str(manifest.get("coverage", "120 只演示股票 · 70 个交易日")),
        "size": f"{total / 1024 / 1024:.1f} MiB",
        "market_bytes": int(market.get("bytes", 0)),
        "dataset_id": str(manifest.get("dataset_id", "")),
        "license": manifest.get("license", {}),
    }
