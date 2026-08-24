"""Run the complete fixture-backed Linux journey and retain release evidence."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from quintara.application import ProductUseCases
from quintara.core import PRODUCT_LABEL_VERSION, file_hash
from quintara.qml_backend import QmlBackend
from quintara.qml_gui import qml_root
from quintara.service import QuintaraService

ROOT = Path(__file__).resolve().parents[1]


def _package(root: Path) -> Path:
    package = root / "provider-package"
    package.mkdir()
    files = []
    for target_name, source_name in (
        ("market.csv", "synthetic_market.csv"),
        ("membership.csv", "synthetic_membership.csv"),
        ("listing.csv", "synthetic_listing.csv"),
    ):
        target = package / target_name
        shutil.copyfile(ROOT / "fixtures" / source_name, target)
        files.append({"path": target_name, "sha256": file_hash(target), "bytes": target.stat().st_size})
    market = pd.read_csv(package / "market.csv")
    extra = market[["股票代码", "日期"]].copy()
    extra["peTTM"] = 12.0
    extra.to_csv(package / "extra_features.csv", index=False)
    pd.DataFrame({"date": sorted(market["日期"].unique()), "is_trading": True}).to_csv(package / "calendar.csv", index=False)
    for name in ("extra_features.csv", "calendar.csv"):
        target = package / name
        files.append({"path": name, "sha256": file_hash(target), "bytes": target.stat().st_size})
    manifest = {
        "schema": "quintara-dataset-v1",
        "dataset_id": "ordinary-user-linux-fixture",
        "version": "1.0.0",
        "platforms": ["any"],
        "label_contract": PRODUCT_LABEL_VERSION,
        "mode": "PIT_BASELINE",
        "pit": {"closed": True},
        "components": {
            "market": "market.csv", "extra_features": "extra_features.csv", "calendar": "calendar.csv",
            "listing": "listing.csv", "membership": "membership.csv",
        },
        "files": files,
        "source": {"provider": "Quintara deterministic fixture"},
        "license": {"id": "fixture-only", "redistribution": True},
    }
    (package / "dataset-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return package


def _command(data_root: Path, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "quintara", "--root", str(data_root), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}\n{result.stderr}\n{result.stdout}")
    return json.loads(result.stdout)


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QSG_RHI_BACKEND", "software")
    with tempfile.TemporaryDirectory(prefix="quintara-user-journey-") as temporary:
        base = Path(temporary)
        data_root = base / "user-data"
        package = _package(base)
        steps = []
        steps.append({"step": "bootstrap", "result": _command(data_root, "bootstrap")})
        steps.append({"step": "consent", "result": _command(data_root, "consent", "accept")})
        imported = _command(data_root, "data", "import-package", str(package))
        steps.append({"step": "provider-import", "generation": imported["generation"]})
        run = _command(
            data_root,
            "run",
            "--strategy",
            "balanced",
            "--years",
            "3",
            "--config",
            json.dumps({"lgbm_fixed_rounds": 64, "lgbm_min_data_in_leaf": 5, "lgbm_num_threads": 1}),
        )
        run_id = run["run_id"]
        steps.append({"step": "train-top5", "run_id": run_id, "count": len(run["result"])})
        details = _command(data_root, "results", run_id, "--details")
        steps.append({"step": "results", "route": details["manifest"]["route"]})
        export_path = base / "top5.csv"
        exported = _command(data_root, "export", run_id, "--output", str(export_path))
        steps.append({"step": "export", "sha256": exported["sha256"], "bytes": export_path.stat().st_size})

        app = QGuiApplication([])
        service = QuintaraService(data_root)
        backend = QmlBackend(ProductUseCases(service))
        backend.advanceOnboarding(1, "", True, False, False)
        backend.advanceOnboarding(2, "csv", True, False, False)
        backend.advanceOnboarding(3, "", True, False, False)
        backend.advanceOnboarding(4, "", True, False, False)
        backend.advanceOnboarding(4, "", True, False, False)
        backend.navigate("results")
        engine = QQmlApplicationEngine()
        engine.addImportPath(str(qml_root()))
        engine.setInitialProperties({"backend": backend})
        engine.load(QUrl.fromLocalFile(str(qml_root() / "main.qml")))
        if not engine.rootObjects():
            raise RuntimeError("QML result workspace did not load")
        window = engine.rootObjects()[0]
        window.show()
        for _ in range(8):
            app.processEvents()
        screenshot = ROOT / "dist/linux-user-journey-results.png"
        if not window.grabWindow().save(str(screenshot)):
            raise RuntimeError("result screenshot failed")
        steps.append({"step": "qml-results", "screenshot_sha256": file_hash(screenshot), "bytes": screenshot.stat().st_size})
        window.close()
        service.close()

        evidence = {
            "schema_version": 1,
            "platform": sys.platform,
            "fixture_manifest_sha256": file_hash(ROOT / "fixtures/manifest.json"),
            "steps": steps,
            "passed": len(run["result"]) == 5 and export_path.exists(),
        }
        output = ROOT / "dist/linux-user-journey.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps(evidence, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
