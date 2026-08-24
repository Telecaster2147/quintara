"""Qt Quick desktop launcher used by release GUI entry points."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .application import ProductUseCases
from .core import AppPaths
from .display import prepare_qt_environment
from .platform import FileLock, LockBusy
from .qml_backend import QmlBackend
from .service import QuintaraService


def qml_root() -> Path:
    return Path(__file__).with_name("qml")


def icon_path() -> Path:
    return Path(__file__).with_name("assets") / "quintara-icon.png"


def main() -> int:
    """GUI-script entry point with an optional isolated content root."""
    parser = argparse.ArgumentParser(prog="quintara-gui", description="Quintara desktop application")
    parser.add_argument("--root", help=argparse.SUPPRESS)
    args = parser.parse_args()
    return launch(args.root)


def launch(root: str | Path | None = None) -> int:
    display = prepare_qt_environment()
    if not display.get("gui_available") and os.environ.get("QT_QPA_PLATFORM") not in {"offscreen", "minimal"}:
        return 4
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    QQuickStyle.setStyle("Basic")
    existing = QGuiApplication.instance()
    if existing is None:
        app = QGuiApplication([])
    elif isinstance(existing, QGuiApplication):
        app = existing
    else:
        raise RuntimeError("Quintara GUI requires QGuiApplication")
    app.setApplicationName("Quintara")
    app.setOrganizationName("Quintara")
    if icon_path().exists():
        app.setWindowIcon(QIcon(str(icon_path())))

    paths = AppPaths.discover(root)
    paths.ensure()
    instance_lock = FileLock(paths.root / "gui-instance.lock")
    server_name = f"quintara-{hashlib.sha256(str(paths.root).encode()).hexdigest()[:20]}"
    try:
        instance_lock.acquire()
    except LockBusy:
        socket = QLocalSocket()
        socket.connectToServer(server_name)
        if socket.waitForConnected(500):
            socket.write(b"activate")
            socket.flush()
            socket.waitForBytesWritten(200)
        return 0

    service = QuintaraService(root)
    backend = QmlBackend(ProductUseCases(service))
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root()))
    engine.setInitialProperties({"backend": backend})
    engine.load(QUrl.fromLocalFile(str(qml_root() / "main.qml")))
    if not engine.rootObjects():
        service.close()
        instance_lock.release()
        return 2

    QLocalServer.removeServer(server_name)
    server = QLocalServer(app)

    def activate() -> None:
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            if connection is not None:
                connection.disconnectFromServer()
        for window in app.allWindows():
            window.show()
            window.raise_()
            window.requestActivate()

    if server.listen(server_name):
        server.newConnection.connect(activate)
    try:
        return app.exec()
    finally:
        backend.shutdown()
        service.close()
        instance_lock.release()
