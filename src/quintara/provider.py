"""Fail-closed provider package/channel validation and resumable acquisition."""
from __future__ import annotations

import json
import os
import shutil
import time
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .core import PRODUCT_LABEL_VERSION, UniverseMode, file_hash, now_utc
from .data_lifecycle import DataManager
from .platform import atomic_json

CHANNEL_SCHEMA = "quintara-channel-v1"
DATASET_SCHEMA = "quintara-dataset-v1"


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class DownloadIdentity:
    url: str
    etag: str | None
    length: int


def validate_dataset_manifest(manifest: dict[str, Any], root: Path, *, platform_tag: str = "any") -> dict[str, Any]:
    required = {"schema", "dataset_id", "version", "platforms", "label_contract", "mode", "files", "source", "license"}
    missing = required - manifest.keys()
    if missing:
        raise ProviderError(f"dataset manifest fields missing: {sorted(missing)}")
    if manifest["schema"] != DATASET_SCHEMA:
        raise ProviderError("unsupported dataset schema")
    if platform_tag not in manifest["platforms"] and "any" not in manifest["platforms"]:
        raise ProviderError("dataset does not support this platform")
    if manifest["label_contract"] != PRODUCT_LABEL_VERSION:
        raise ProviderError("dataset label contract is incompatible")
    try:
        mode = UniverseMode(str(manifest["mode"]))
    except ValueError as exc:
        raise ProviderError("dataset research mode is invalid") from exc
    if mode == UniverseMode.PIT_BASELINE and not manifest.get("pit", {}).get("closed"):
        raise ProviderError("PIT dataset lacks a closed membership/listing/calendar identity")
    components = manifest.get("components", {})
    required_components = {"market", "extra_features", "calendar", "listing", "membership"}
    if set(components) < required_components:
        raise ProviderError(f"dataset logical components missing: {sorted(required_components - set(components))}")
    for entry in manifest["files"]:
        if set(entry) < {"path", "sha256", "bytes"}:
            raise ProviderError("dataset file entry is incomplete")
        relative = Path(str(entry["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ProviderError("dataset file path leaves package root")
        path = root / relative
        if not path.is_file() or path.stat().st_size != int(entry["bytes"]) or file_hash(path) != entry["sha256"]:
            raise ProviderError(f"dataset file verification failed: {relative}")
    declared_paths = {str(entry["path"]) for entry in manifest["files"]}
    if any(str(components[name]) not in declared_paths for name in required_components):
        raise ProviderError("dataset component is not bound to a verified file")
    return manifest


def select_channel_release(channel: dict[str, Any], *, platform_tag: str, pinned_origin: str) -> dict[str, Any]:
    if channel.get("schema") != CHANNEL_SCHEMA or not isinstance(channel.get("releases"), list):
        raise ProviderError("channel index schema is invalid")
    candidates = []
    for release in channel["releases"]:
        origin = urllib.parse.urlsplit(str(release.get("url", ""))).netloc
        if origin != pinned_origin:
            raise ProviderError("release origin differs from pinned provider identity")
        if platform_tag in release.get("platforms", []) or "any" in release.get("platforms", []):
            candidates.append(release)
    if not candidates:
        raise ProviderError("channel has no compatible release")
    return sorted(candidates, key=lambda item: tuple(int(part) for part in str(item["version"]).split(".")), reverse=True)[0]


def preflight(root: Path, *, required_bytes: int, accepted_license: bool, pit_closed: bool) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    probe = root / ".write-probe"
    try:
        probe.write_text("ok", encoding="utf-8")
    except OSError as exc:
        raise ProviderError("data directory is not writable") from exc
    finally:
        probe.unlink(missing_ok=True)
    free = shutil.disk_usage(root).free
    if free < required_bytes * 2:
        raise ProviderError("insufficient disk budget for download and staging")
    if not accepted_license:
        raise ProviderError("dataset license has not been accepted")
    if not pit_closed:
        raise ProviderError("PIT closure preflight failed")
    return {"writable": True, "free_bytes": free, "required_bytes": required_bytes, "checked_at": now_utc()}


def download_resumable(
    identity: DownloadIdentity,
    target: Path,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
    cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[int, int], None] = lambda _done, _total: None,
    retries: int = 3,
    chunk_size: int = 1024 * 1024,
) -> Path:
    """Download to `.part`, resume by Range, and bind every byte to ETag/length."""
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + ".part")
    sidecar = part.with_suffix(part.suffix + ".json")
    expected = {"url": identity.url, "etag": identity.etag, "length": identity.length}
    if sidecar.exists() and json.loads(sidecar.read_text(encoding="utf-8")) != expected:
        part.unlink(missing_ok=True)
    atomic_json(sidecar, expected)
    for attempt in range(retries):
        offset = part.stat().st_size if part.exists() else 0
        request = urllib.request.Request(identity.url, headers={"Range": f"bytes={offset}-"} if offset else {})
        try:
            with opener(request) as response, part.open("ab" if offset else "wb") as handle:
                response_etag = response.headers.get("ETag")
                if identity.etag and response_etag and response_etag != identity.etag:
                    raise ProviderError("remote object ETag changed")
                while True:
                    if cancelled():
                        raise ProviderError("download cancelled at a resumable boundary")
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
                    progress(handle.tell(), identity.length)
            if part.stat().st_size != identity.length:
                raise ProviderError("download length differs from pinned identity")
            os.replace(part, target)
            sidecar.unlink(missing_ok=True)
            return target
        except ProviderError:
            raise
        except OSError as exc:
            if attempt + 1 == retries:
                raise ProviderError(f"download failed after {retries} attempts") from exc
            time.sleep(min(0.2 * (2**attempt), 2.0))
    raise ProviderError("download failed")


class ProviderPackageImporter:
    def __init__(self, manager: DataManager) -> None:
        self.manager = manager

    def import_package(self, package: Path, *, platform_tag: str = "any") -> dict[str, Any]:
        staging = self.manager.paths.data_staging / f"provider-{int(time.time_ns())}"
        quarantine = self.manager.paths.data / "quarantine"
        staging.mkdir(parents=True, exist_ok=False)
        try:
            if package.is_dir():
                shutil.copytree(package, staging, dirs_exist_ok=True)
            elif zipfile.is_zipfile(package):
                with zipfile.ZipFile(package) as archive:
                    if any(Path(name).is_absolute() or ".." in Path(name).parts for name in archive.namelist()):
                        raise ProviderError("package archive contains an unsafe path")
                    archive.extractall(staging)
            else:
                raise ProviderError("provider package must be a directory or ZIP")
            manifest = json.loads((staging / "dataset-manifest.json").read_text(encoding="utf-8"))
            validate_dataset_manifest(manifest, staging, platform_tag=platform_tag)
            market = pd.read_csv(staging / "market.csv", parse_dates=["日期"])
            membership = pd.read_csv(staging / "membership.csv")
            listing = pd.read_csv(staging / "listing.csv")
            extra = pd.read_csv(staging / "extra_features.csv") if (staging / "extra_features.csv").exists() else None
            return self.manager.publish(
                market,
                membership,
                listing,
                source="quintara_provider",
                extra_features=extra,
                metadata={
                    "provider_dataset": manifest["dataset_id"],
                    "provider_version": manifest["version"],
                    "membership_route": manifest["mode"],
                    "license": manifest["license"],
                    "provenance": manifest["source"],
                },
            )
        except Exception:
            quarantine.mkdir(parents=True, exist_ok=True)
            destination = quarantine / staging.name
            if staging.exists():
                os.replace(staging, destination)
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
