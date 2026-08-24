"""Capture the deterministic QML theme/page/minimum-window matrix."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from quintara.application import ProductUseCases
from quintara.core import file_hash
from quintara.qml_backend import QmlBackend
from quintara.qml_gui import qml_root
from quintara.service import QuintaraService

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("home", "data", "universe", "train", "results", "history", "diagnostics")


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QSG_RHI_BACKEND", "software")
    output = ROOT / "dist/visual-matrix"
    output.mkdir(parents=True, exist_ok=True)
    app = QGuiApplication([])
    records = []
    with tempfile.TemporaryDirectory(prefix="quintara-visual-") as root:
        service = QuintaraService(root)
        service.confirm_consent()
        backend = QmlBackend(ProductUseCases(service))
        engine = QQmlApplicationEngine()
        engine.addImportPath(str(qml_root()))
        engine.setInitialProperties({"backend": backend})
        engine.load(QUrl.fromLocalFile(str(qml_root() / "main.qml")))
        if not engine.rootObjects():
            return 2
        window = engine.rootObjects()[0]
        for theme in ("light", "dark"):
            backend.setTheme(theme)
            for width, height, scale_label in ((960, 640, "minimum"), (1200, 760, "standard")):
                window.setWidth(width)
                window.setHeight(height)
                window.show()
                for _ in range(4):
                    app.processEvents()
                target = output / f"{theme}-{scale_label}-onboarding.png"
                image = window.grabWindow()
                if image.isNull() or not image.save(str(target)):
                    return 3
                records.append({"theme": theme, "viewport": [width, height], "page": "onboarding", "sha256": file_hash(target), "bytes": target.stat().st_size})
        backend.skipOnboarding()
        for theme in ("light", "dark"):
            backend.setTheme(theme)
            for width, height, scale_label in ((960, 640, "minimum"), (1200, 760, "standard")):
                window.setWidth(width)
                window.setHeight(height)
                window.show()
                for page in PAGES:
                    backend.navigate(page)
                    for _ in range(4):
                        app.processEvents()
                    target = output / f"{theme}-{scale_label}-{page}.png"
                    image = window.grabWindow()
                    if image.isNull() or not image.save(str(target)):
                        return 3
                    records.append({"theme": theme, "viewport": [width, height], "page": page, "sha256": file_hash(target), "bytes": target.stat().st_size})
                backend.importCsv(str(root) + "/missing.csv")
                for _ in range(4):
                    app.processEvents()
                target = output / f"{theme}-{scale_label}-failure.png"
                image = window.grabWindow()
                if image.isNull() or not image.save(str(target)):
                    return 3
                records.append({"theme": theme, "viewport": [width, height], "page": "failure", "sha256": file_hash(target), "bytes": target.stat().st_size})
                backend.navigate("home")
        window.close()
        service.close()
    manifest = {"schema_version": 1, "captures": records, "checks": {"nonempty": all(item["bytes"] > 5000 for item in records), "count": len(records)}}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["checks"]["nonempty"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
