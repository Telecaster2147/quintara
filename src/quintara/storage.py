"""Verified content-root migration and generation catalog helpers."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from .core import AppPaths, file_hash, now_utc
from .platform import atomic_json


class StorageError(RuntimeError):
    pass


def disk_budget(root: Path, *, incoming_bytes: int = 0, reserve_bytes: int = 2 * 1024**3) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(root)
    required = incoming_bytes * 2 + reserve_bytes
    return {"free_bytes": usage.free, "required_bytes": required, "ready": usage.free >= required}


def generation_catalog(paths: AppPaths) -> dict[str, Any]:
    entries = []
    for manifest_path in sorted(paths.data_generations.glob("*/manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            valid = all(
                (manifest_path.parent / name).is_file()
                and file_hash(manifest_path.parent / name) == details.get("sha256")
                for name, details in manifest.get("files", {}).items()
            )
            entries.append({"generation": manifest.get("generation"), "valid": valid, "manifest": manifest})
        except (OSError, json.JSONDecodeError):
            entries.append({"generation": manifest_path.parent.name, "valid": False, "manifest": None})
    return {"schema_version": 1, "entries": entries, "scanned_at": now_utc()}


def migrate_content_root(source: AppPaths, destination_root: Path) -> dict[str, Any]:
    """Stage/copy/verify/switch metadata; source cleanup is deliberately deferred."""
    destination = AppPaths.discover(destination_root)
    if destination.root == source.root:
        raise StorageError("destination already is the active content root")
    size = sum(path.stat().st_size for path in source.root.rglob("*") if path.is_file())
    budget = disk_budget(destination.root, incoming_bytes=size)
    if not budget["ready"]:
        raise StorageError("destination lacks migration disk budget")
    staging = destination.root.with_name(destination.root.name + ".migration-staging")
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(source.root, staging)
    staged_paths = AppPaths.discover(staging)
    catalog = generation_catalog(staged_paths)
    if any(not item["valid"] for item in catalog["entries"]):
        shutil.rmtree(staging, ignore_errors=True)
        raise StorageError("staged generation verification failed")
    if destination.root.exists():
        if any(destination.root.iterdir()):
            raise StorageError("destination content root is not empty")
        destination.root.rmdir()
    os.replace(staging, destination.root)
    marker = source.root / "migration.json"
    atomic_json(marker, {"active_root": str(destination.root), "source_cleanup_after": "manual-confirmation", "migrated_at": now_utc()})
    return {"active_root": str(destination.root), "source_retained": True, "bytes": size, "catalog": catalog}
