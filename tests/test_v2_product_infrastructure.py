from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from quintara import doctor
from quintara.bundled_data import developer_data_package, developer_data_summary
from quintara.core import PRODUCT_LABEL_VERSION, AppPaths, file_hash
from quintara.display import detect_display_environment
from quintara.jobs import JobCancelled, JobContext, JobCoordinator, progress_snapshot
from quintara.migration import scan_legacy_root
from quintara.onboarding import DataSourceChoice, OnboardingFlow, consent_is_current, consent_record
from quintara.platform import subprocess_policy
from quintara.provider import (
    DATASET_SCHEMA,
    DownloadIdentity,
    ProviderError,
    ProviderPackageImporter,
    download_resumable,
    preflight,
    select_channel_release,
    validate_dataset_manifest,
)
from quintara.service import QuintaraService
from quintara.storage import migrate_content_root


def _provider_package(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / "package"
    root.mkdir()
    fixture = Path(__file__).parents[1] / "fixtures"
    mapping = {
        "market.csv": fixture / "synthetic_market.csv",
        "membership.csv": fixture / "synthetic_membership.csv",
        "listing.csv": fixture / "synthetic_listing.csv",
    }
    files = []
    for name, source in mapping.items():
        target = root / name
        target.write_bytes(source.read_bytes())
        files.append({"path": name, "bytes": target.stat().st_size, "sha256": file_hash(target)})
    market = pd.read_csv(root / "market.csv")
    extra = market[["股票代码", "日期"]].copy()
    extra["peTTM"] = 12.0
    extra.to_csv(root / "extra_features.csv", index=False)
    calendar = pd.DataFrame({"date": sorted(market["日期"].unique()), "is_trading": True})
    calendar.to_csv(root / "calendar.csv", index=False)
    for name in ("extra_features.csv", "calendar.csv"):
        target = root / name
        files.append({"path": name, "bytes": target.stat().st_size, "sha256": file_hash(target)})
    manifest = {
        "schema": DATASET_SCHEMA,
        "dataset_id": "synthetic-production-contract",
        "version": "1.0.0",
        "platforms": ["any"],
        "label_contract": PRODUCT_LABEL_VERSION,
        "mode": "PIT_BASELINE",
        "pit": {"closed": True, "membership": "fixture", "listing": "fixture", "calendar": "market"},
        "components": {
            "market": "market.csv", "extra_features": "extra_features.csv", "calendar": "calendar.csv",
            "listing": "listing.csv", "membership": "membership.csv",
        },
        "files": files,
        "source": {"provider": "Quintara fixture", "retrieved": "2026-08-24"},
        "license": {"id": "fixture-only", "redistribution": True},
    }
    (root / "dataset-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root, manifest


def test_versioned_consent_and_resumable_five_step_onboarding(app_root):
    service = QuintaraService(app_root)
    try:
        assert service.consent_status()["status"] == "REQUIRED"
        assert consent_is_current(consent_record("test"))
        flow = OnboardingFlow(service.registry)
        assert flow.status()["step_key"] == "risk"
        flow.advance(1)
        source = DataSourceChoice("provider", accepted_license=True, accepted_transfer=True)
        flow.advance(2, source=source)
        flow.advance(3)
        ready = flow.advance(4)
        assert not ready["completed"]
        assert flow.advance(4)["completed"]
        assert flow.reopen()["step"] == 0
        assert flow.skip()["skipped"]
        bundled = DataSourceChoice("bundled", accepted_license=True)
        bundled.validate()
        DataSourceChoice("baostock").validate()
        with pytest.raises(ValueError, match="package notice"):
            DataSourceChoice("bundled").validate()
        assert len(consent_record("test")["sections"]) == 5
    finally:
        service.close()


def test_provider_contract_preflight_local_media_and_quarantine(app_root, tmp_path):
    package, manifest = _provider_package(tmp_path)
    assert validate_dataset_manifest(manifest, package)["dataset_id"] == "synthetic-production-contract"
    assert preflight(tmp_path / "data", required_bytes=1024, accepted_license=True, pit_closed=True)["writable"]
    service = QuintaraService(app_root)
    try:
        published = ProviderPackageImporter(service.data).import_package(package)
        assert published["metadata"]["membership_route"] == "PIT_BASELINE"
        (package / "market.csv").write_bytes(b"corrupt")
        with pytest.raises(ProviderError, match="verification failed"):
            ProviderPackageImporter(service.data).import_package(package)
        assert list((service.paths.data / "quarantine").iterdir())
    finally:
        service.close()


def test_channel_origin_pin_and_resumable_download(tmp_path):
    channel = {
        "schema": "quintara-channel-v1",
        "releases": [
            {"version": "1.0.0", "url": "https://data.example/v1.zip", "platforms": ["any"]},
            {"version": "1.1.0", "url": "https://data.example/v11.zip", "platforms": ["linux-x64"]},
        ],
    }
    assert select_channel_release(channel, platform_tag="linux-x64", pinned_origin="data.example")["version"] == "1.1.0"
    payload = b"provider-payload"

    class Response(io.BytesIO):
        headers = {"ETag": '"stable"'}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    offsets = []

    def opener(request):
        value = request.headers.get("Range")
        offset = int(value.split("=")[1].split("-")[0]) if value else 0
        offsets.append(offset)
        return Response(payload[offset:])

    target = tmp_path / "dataset.zip"
    identity = DownloadIdentity("https://data.example/dataset.zip", '"stable"', len(payload))
    target.with_suffix(".zip.part").write_bytes(payload[:4])
    target.with_suffix(".zip.part.json").write_text(json.dumps({"url": identity.url, "etag": identity.etag, "length": identity.length}), encoding="utf-8")
    assert download_resumable(identity, target, opener=opener).read_bytes() == payload
    assert offsets == [4]

    cancelled_target = tmp_path / "cancelled.zip"
    with pytest.raises(ProviderError, match="cancelled"):
        download_resumable(identity, cancelled_target, opener=lambda _request: Response(payload), cancelled=lambda: True)
    assert cancelled_target.with_suffix(".zip.part").exists()


@given(completed=st.integers(min_value=0, max_value=10_000), total=st.integers(min_value=1, max_value=10_000), elapsed=st.floats(min_value=0.1, max_value=10_000, allow_nan=False))
def test_progress_dto_is_bounded(completed, total, elapsed):
    completed = min(completed, total)
    value = progress_snapshot(completed=completed, total=total, elapsed_seconds=elapsed, phase="transfer")
    assert 0 <= value["fraction"] <= 1
    assert value["rate_per_second"] >= 0


def test_job_coordinator_idempotency_terminal_boundary_and_recovery(app_root):
    coordinator = JobCoordinator(AppPaths.discover(app_root))
    first = coordinator.create("download", {"dataset": "fixture"}, idempotency_key="same")
    assert coordinator.create("download", {"dataset": "fixture"}, idempotency_key="same")["job_id"] == first["job_id"]
    running = coordinator.transition(first["job_id"], state="RUNNING", phase="transfer")
    assert running["state"] == "RUNNING"
    with pytest.raises(ValueError, match="invalid job transition"):
        coordinator.transition(first["job_id"], state="PLANNING", phase="transfer")
    recovered = coordinator.recover()
    assert recovered[0]["recovery_action"] == "resume"
    context = JobContext(AppPaths.discover(app_root), "job-cancel-fixture")
    context.request_cancel()
    with pytest.raises(JobCancelled):
        context.checkpoint("verify")


def test_new_data_marks_models_with_other_generation_stale(app_root):
    service = QuintaraService(app_root)
    try:
        manifest = {"model_identity": {"market_data_generation": "data-old"}}
        service.registry.put_generation("model-old", "model", manifest, status="active")
        assert service.registry.mark_models_stale_for_data("data-new") == 1
        models = [row for row in service.registry.connection.execute("SELECT id,status FROM models")]
        assert dict(models[0])["status"] == "stale"
    finally:
        service.close()


def test_verified_content_root_migration_retains_source(app_root, tmp_path, monkeypatch):
    paths = AppPaths.discover(app_root)
    paths.ensure()
    (paths.root / "sentinel.txt").write_text("local", encoding="utf-8")
    result = migrate_content_root(paths, tmp_path / "migrated")
    assert Path(result["active_root"], "sentinel.txt").read_text(encoding="utf-8") == "local"
    assert result["source_retained"]
    assert paths.root.exists()
    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", str(paths.root.parent))
    else:
        monkeypatch.setenv("XDG_DATA_HOME", str(paths.root.parent))
    assert AppPaths.discover().root == Path(result["active_root"])
    # Explicit roots remain deterministic and do not silently follow a redirect.
    assert AppPaths.discover(paths.root).root == paths.root


def test_desktop_detection_and_windows_subprocess_policy():
    assert detect_display_environment({}, system="Linux")["kind"] == "terminal"
    assert detect_display_environment({"DISPLAY": ":0"}, system="Linux")["qt_platform"] == "xcb"
    assert detect_display_environment({"WSL_INTEROP": "1", "WAYLAND_DISPLAY": "wayland-0"}, system="Linux")["kind"] == "wslg"
    assert subprocess_policy(gui_background=True, platform_name="nt")["creationflags"] == 0x08000000
    assert subprocess_policy(gui_background=False, platform_name="nt").get("creationflags", 0) == 0


def test_gpu_probe_uses_gui_hidden_process_policy(monkeypatch):
    calls = {}

    def fake_run(*args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return type("Result", (), {"returncode": 1, "stdout": ""})()

    monkeypatch.setattr(doctor.subprocess, "run", fake_run)
    monkeypatch.setattr(doctor, "subprocess_policy", lambda **_kwargs: {"creationflags": 0x08000000, "startupinfo": "hidden"})
    assert doctor._probe_gpu() == (None, None)
    assert calls["kwargs"]["creationflags"] == 0x08000000
    assert calls["kwargs"]["startupinfo"] == "hidden"


def test_packaging_has_distinct_gui_and_cli_subsystems_and_icon():
    root = Path(__file__).parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    cli_source = (root / "src/quintara/cli.py").read_text(encoding="utf-8")
    gui = (root / "packaging/quintara.spec").read_text(encoding="utf-8")
    cli = (root / "packaging/quintara-cli.spec").read_text(encoding="utf-8")
    release_builder = (root / "packaging/build_release.py").read_text(encoding="utf-8")
    installer = (root / "packaging/windows/Quintara.iss").read_text(encoding="utf-8")
    assert "console=False" in gui and "quintara.ico" in gui
    assert "PySide6.QtWidgets" not in gui
    assert '../../assets/quintara-icon.png' in (root / "src/quintara/qml/Quintara/AppShell.qml").read_text(encoding="utf-8")
    assert "console=True" in cli
    assert '[project.gui-scripts]' in pyproject and 'quintara-gui = "quintara.qml_gui:main"' in pyproject
    assert "from .qml_gui import launch" in cli_source and "from .gui import launch" not in cli_source
    assert 'f"{name}.exe"' in release_builder and "artifacts[path.name]" in release_builder
    assert "SetupIconFile" in installer and "Parameters: \"gui\"" not in installer
    assert "developer_data\\quintara-developer-data-v1.zip" in installer
    assert "DestDir: \"{app}\\data\\developer\"" in installer
    assert (root / "src/quintara/assets/icons/quintara.ico").read_bytes()[:4] == b"\x00\x00\x01\x00"


def test_developer_data_sidecar_is_complete_and_reference_bound():
    package = developer_data_package()
    assert package is not None and package.is_file()
    summary = developer_data_summary()
    assert summary["dataset_id"] == "quintara-developer-data-v1"
    assert summary["market_bytes"] > 250_000_000
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read("dataset-manifest.json"))
        reference = archive.read("reference-result.csv")
    assert manifest["pit"]["expected_members"] == 300
    assert manifest["source"]["reference_result_sha256"] == file_hash(
        Path(__file__).parents[2] / "bigdata/app/output/result.csv"
    )
    assert reference == (Path(__file__).parents[2] / "bigdata/app/output/result.csv").read_bytes()


def test_source_tree_does_not_embed_a_developer_home_path():
    root = Path(__file__).parents[1] / "src"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in root.rglob("*")
        if path.is_file() and path.suffix in {".py", ".qml", ".json"}
    )
    assert "/home/olm" not in source


def test_release_gates_pin_linux_abi_and_windows_upgrade_contract():
    root = Path(__file__).parents[1]
    workflow = (root / ".github/workflows/package.yml").read_text(encoding="utf-8")
    install_smoke = (root / "packaging/windows/install_smoke.ps1").read_text(encoding="utf-8")
    candidate = (root / "packaging/candidate_gate.py").read_text(encoding="utf-8")
    assert "runs-on: ubuntu-22.04" in workflow
    assert "elf_compat_audit.py --max-glibc 2.35" in workflow
    assert "upgrade_preserves_data" in install_smoke
    assert "uninstall_preserves_data_by_default" in install_smoke
    assert "for ($sample = 0; $sample -lt 16; $sample++)" in install_smoke
    assert "developer_data_beside_app = $developerDataInstalled" in install_smoke
    assert "for ($sample = 0; $sample -lt 16; $sample++)" in (root / "packaging/windows/smoke.ps1").read_text(encoding="utf-8")
    assert "--strict" in candidate and "native_matrix_passed" in candidate


def test_native_platform_workflow_has_hosted_windows_and_aggregate_evidence():
    root = Path(__file__).parents[1]
    workflow = (root / ".github/workflows/platform-matrix.yml").read_text(encoding="utf-8")
    package_workflow = (root / ".github/workflows/package.yml").read_text(encoding="utf-8")
    assert "runs-on: windows-latest" in workflow
    assert "binutils build-essential" in workflow
    assert "aggregate-evidence:" in workflow
    assert "native_evidence.py --merge" in workflow
    assert "candidate_gate.py --strict" in workflow
    assert 'key: debian-12' in workflow and 'key: debian-13' in workflow
    assert '--platform "${{ matrix.key }}"' in workflow
    assert 'ubuntu22_dist="$ubuntu22"' in workflow and 'chmod +x dist/Quintara dist/quintara-cli' in workflow
    assert workflow.count("@fission-ai/openspec@1.9.0") == 1
    assert package_workflow.count("@fission-ai/openspec@1.9.0") == 2
    assert package_workflow.count("actions/setup-node@v4") == 2
    assert "/tmp/quintara-wheel-smoke/bin/quintara-gui" in package_workflow
    assert "{'Quintara.exe','quintara-cli.exe'}" in workflow
    assert "{'Quintara.exe','quintara-cli.exe'}" in package_workflow
    assert "Quintara-Windows-x64-Portable.zip" in package_workflow
    assert "Quintara-Windows-x64-Portable.exe" not in package_workflow
    assert "data/developer" in package_workflow


def test_linux_install_publishes_hicolor_icon_family():
    root = Path(__file__).parents[1]
    script = (root / "packaging/install_linux.sh").read_text(encoding="utf-8")
    assert 'for size in 16 20 24 32 48 64 128 256' in script
    assert 'hicolor/${size}x${size}/apps' in script
    assert 'quintara-${size}.png' in script
    assert 'lib/quintara/data/developer' in script
    assert 'quintara-developer-data-v1.zip' in script


def test_legacy_scan_is_read_only_and_marks_incomplete_identity(tmp_path):
    manifest_root = tmp_path / "data/generations/v1"
    manifest_root.mkdir(parents=True)
    manifest = {"schema_version": 1, "generation": "v1", "files": {}}
    path = manifest_root / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    before = path.read_bytes()
    report = scan_legacy_root(tmp_path)
    assert report["records"][0]["status"] == "compatible"
    assert report["mutated"] is False
    assert path.read_bytes() == before


def test_provider_preflight_rejects_missing_consent_and_impossible_space(tmp_path, monkeypatch):
    with pytest.raises(ProviderError, match="license"):
        preflight(tmp_path / "license", required_bytes=1, accepted_license=False, pit_closed=True)
    with pytest.raises(ProviderError, match="PIT"):
        preflight(tmp_path / "pit", required_bytes=1, accepted_license=True, pit_closed=False)
    monkeypatch.setattr("quintara.provider.shutil.disk_usage", lambda _root: type("Usage", (), {"free": 1})())
    with pytest.raises(ProviderError, match="disk"):
        preflight(tmp_path / "disk", required_bytes=1024, accepted_license=True, pit_closed=True)
