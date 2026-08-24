"""Real QML harness with isolated data root and semantic QObject lookup."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlApplicationEngine

from quintara.application import ProductUseCases
from quintara.qml_backend import QmlBackend
from quintara.qml_gui import qml_root
from quintara.service import QuintaraService


class GuiHarness:
    def __init__(self, data_root: Path) -> None:
        self.service = QuintaraService(data_root)
        self.backend = QmlBackend(ProductUseCases(self.service))
        self.engine = QQmlApplicationEngine()
        self.engine.addImportPath(str(qml_root()))
        self.engine.setInitialProperties({"backend": self.backend})
        self.engine.load(QUrl.fromLocalFile(str(qml_root() / "main.qml")))
        if not self.engine.rootObjects():
            raise RuntimeError("QML harness load failed")
        self.window = self.engine.rootObjects()[0]

    def semantic(self, object_name: str) -> QObject:
        item = self.window.findChild(QObject, object_name)
        if item is None:
            raise LookupError(f"semantic QML object not found: {object_name}")
        return item

    def navigate(self, key: str) -> dict:
        self.backend.navigate(key)
        return self.backend.currentPagePayload

    def close(self) -> None:
        self.backend.shutdown()
        self.service.close()
