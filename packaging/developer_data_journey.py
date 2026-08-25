"""Exercise the complete first-run GUI path with the shipped developer data."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from quintara.application import ProductUseCases
from quintara.bundled_data import developer_data_package
from quintara.core import file_hash
from quintara.qml_backend import QmlBackend
from quintara.qml_gui import qml_root
from quintara.service import QuintaraService

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT.parent / "bigdata" / "app" / "output" / "result.csv"
EXPECTED_SHA256 = "e61f54a070e3c5ac331cf198c620757a49711268d44b4c1e4451f2dd86b2ecd6"


def _wait(app: QGuiApplication, backend: QmlBackend, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while backend.jobRunning and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.05)
    app.processEvents()
    if backend.jobRunning:
        raise TimeoutError(f"GUI task exceeded {timeout:.0f} seconds")
    payload = backend.currentPagePayload
    if payload.get("status") == "error":
        raise RuntimeError(
            str(payload.get("technical") or payload.get("error") or payload.get("summary"))
        )


def _capture(app: QGuiApplication, window: object, path: Path) -> None:
    for _ in range(20):
        app.processEvents()
        time.sleep(0.05)
    path.parent.mkdir(parents=True, exist_ok=True)
    image = window.grabWindow()  # type: ignore[attr-defined]
    if image.isNull() or not image.save(str(path)):
        raise RuntimeError(f"failed to capture {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, default=Path("/tmp/quintara-developer-journey"))
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args()

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QSG_RHI_BACKEND", "software")
    work_root = args.work_root.expanduser().resolve()
    if args.reset and work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True, exist_ok=True)

    package = developer_data_package()
    if package is None:
        raise FileNotFoundError("developer data package was not discovered beside the application")

    app = QGuiApplication.instance() or QGuiApplication([])
    service = QuintaraService(work_root)
    backend = QmlBackend(ProductUseCases(service))
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root()))
    engine.setInitialProperties({"backend": backend})
    engine.load(QUrl.fromLocalFile(str(qml_root() / "main.qml")))
    if not engine.rootObjects():
        raise RuntimeError("first-run QML did not load")
    window = engine.rootObjects()[0]
    window.setWidth(1200)
    window.setHeight(760)
    window.show()

    steps: list[dict[str, object]] = []
    try:
        onboarding_image = ROOT / "dist" / "developer-data-onboarding.png"
        _capture(app, window, onboarding_image)
        steps.append({"step": "risk", "screenshot_sha256": file_hash(onboarding_image)})

        backend.advanceOnboarding(1, "", True, False, False)
        backend.advanceOnboarding(2, "", True, False, False)
        backend.importBundledData()
        _wait(app, backend, args.timeout)
        if not backend.bundledDataImported:
            raise RuntimeError("developer data import did not become active")
        steps.append({"step": "bundled-import", "active_data": backend.pathSummary["active_data"]})

        backend.advanceOnboarding(3, "bundled", True, True, False)
        backend.advanceOnboarding(4, "", True, True, False)
        backend.advanceOnboarding(4, "", True, True, False)
        if backend.onboardingRequired:
            raise RuntimeError("first-run wizard did not reach its completed state")
        steps.append({"step": "wizard-complete", "content_root": backend.pathSummary["content_root"]})

        backend.navigate("train")
        backend.startTraining()
        _wait(app, backend, args.timeout)
        if backend.currentPage != "results":
            raise RuntimeError(f"training finished on unexpected page: {backend.currentPage}")

        run = next(item for item in service.runs(100) if item.get("state") == "SUCCEEDED")
        result_path = service.paths.results / str(run["id"]) / "result.csv"
        result_sha256 = file_hash(result_path)
        if result_sha256 != EXPECTED_SHA256:
            raise RuntimeError(f"result hash mismatch: {result_sha256} != {EXPECTED_SHA256}")
        if REFERENCE.is_file() and result_path.read_bytes() != REFERENCE.read_bytes():
            raise RuntimeError("result bytes differ from the local reference CSV")
        output = ROOT / "dist" / "developer-data-result.csv"
        shutil.copyfile(result_path, output)
        result_image = ROOT / "dist" / "developer-data-results.png"
        _capture(app, window, result_image)
        steps.append(
            {
                "step": "train-and-result",
                "run_id": run["id"],
                "result_sha256": result_sha256,
                "result_path": str(output),
                "screenshot_sha256": file_hash(result_image),
            }
        )

        evidence = {
            "schema_version": 1,
            "platform": sys.platform,
            "developer_data_package": str(package),
            "developer_data_sha256": file_hash(package),
            "work_root": str(work_root),
            "expected_result_sha256": EXPECTED_SHA256,
            "steps": steps,
            "passed": True,
        }
        evidence_path = ROOT / "dist" / "developer-data-journey.json"
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 0
    finally:
        window.close()
        backend.shutdown()
        service.close()


if __name__ == "__main__":
    raise SystemExit(main())
