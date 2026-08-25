from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QSG_RHI_BACKEND", "software")

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QColor
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from quintara.application import ProductUseCases
from quintara.qml_backend import QmlBackend
from quintara.qml_gui import qml_root
from quintara.service import QuintaraService


def _wait_for_job(app: QApplication, backend: QmlBackend, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while backend.jobRunning and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()
    assert not backend.jobRunning


def _luminance(color: str) -> float:
    value = QColor(color)
    channels = [value.redF(), value.greenF(), value.blueF()]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(foreground: str, background: str) -> float:
    bright, dark = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (bright + 0.05) / (dark + 0.05)


def test_qml_shell_loads_with_semantic_navigation_and_screenshot(app_root, tmp_path):
    app = QApplication.instance() or QApplication([])
    service = QuintaraService(app_root)
    engine = QQmlApplicationEngine()
    backend = QmlBackend(ProductUseCases(service))
    engine.addImportPath(str(qml_root()))
    engine.setInitialProperties({"backend": backend})
    engine.load(QUrl.fromLocalFile(str(qml_root() / "main.qml")))
    try:
        assert engine.rootObjects(), "QML main window must load"
        window = engine.rootObjects()[0]
        assert window.objectName() == "mainWindow"
        assert window.minimumWidth() == 960
        assert window.minimumHeight() == 640
        shell = window.findChild(QObject, "appShell")
        assert shell is not None
        window.show()
        app.processEvents()
        shell_source = (qml_root() / "Quintara" / "AppShell.qml").read_text(encoding="utf-8")
        for label in ("首页", "数据", "股票池", "训练", "结果", "历史"):
            assert f'qsTr("{label}")' in shell_source
        target = tmp_path / "qml-home.png"
        assert window.grabWindow().save(str(target))
        assert target.stat().st_size > 10_000
    finally:
        engine.deleteLater()
        app.processEvents()
        service.close()


def test_design_tokens_meet_core_contrast_and_accessibility_contract():
    assert _contrast("#10243D", "#FFFFFF") >= 4.5
    assert _contrast("#F3F7FB", "#0D2037") >= 4.5
    assert _contrast("#FFFFFF", "#087E8B") >= 4.5
    root = Path(__file__).parents[1] / "src" / "quintara" / "qml"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.qml"))
    assert "minimumWidth: 960" in source
    assert "minimumHeight: 640" in source
    assert "activeFocusOnTab: true" in source
    assert "Accessible.name" in source
    assert "qsTr(" in source
    assert "reducedMotion" in source


def test_workspace_long_content_has_real_vertical_scroll_contract():
    source = (qml_root() / "Quintara/pages/WorkspacePage.qml").read_text(encoding="utf-8")
    assert "contentHeight: contentColumn.implicitHeight" in source
    assert "ScrollBar.vertical: ScrollBar" in source
    assert "policy: ScrollBar.AlwaysOn" in source
    assert "visible: root.contentHeight > root.availableHeight + 1" in source
    assert "interactive: true" in source
    assert "opacity: verticalBar.visible" in source
    assert "ScrollBar.horizontal.policy: ScrollBar.AlwaysOff" in source


def test_theme_and_reduced_motion_persist_across_backend_instances(app_root):
    app = QApplication.instance() or QApplication([])
    del app
    service = QuintaraService(app_root)
    backend = QmlBackend(ProductUseCases(service))
    backend.setTheme("dark")
    backend.setReducedMotion(True)
    service.close()
    second = QuintaraService(app_root)
    try:
        restored = QmlBackend(ProductUseCases(second))
        assert restored.effectiveDark
        assert restored.reducedMotion
    finally:
        second.close()


def test_onboarding_source_resumes_with_backend_state(app_root):
    app = QApplication.instance() or QApplication([])
    del app
    service = QuintaraService(app_root)
    try:
        backend = QmlBackend(ProductUseCases(service))
        backend.advanceOnboarding(1, "", True, False, False)
        backend.advanceOnboarding(2, "csv", True, False, False)
        assert backend.onboardingSource == "csv"
        service.close()
        service = QuintaraService(app_root)
        resumed = QmlBackend(ProductUseCases(service))
        assert resumed.onboardingSource == "csv"
    finally:
        service.close()


def test_baostock_is_visible_as_third_source_and_update_has_preview_contract(app_root):
    service = QuintaraService(app_root)
    try:
        service.confirm_consent()
        backend = QmlBackend(ProductUseCases(service))
        backend.advanceOnboarding(2, "baostock", True, False, False)
        assert backend.onboardingSource == "baostock"
        onboarding = (qml_root() / "Quintara/components/OnboardingDialog.qml").read_text(encoding="utf-8")
        main = (qml_root() / "main.qml").read_text(encoding="utf-8")
        assert "BaoStock 在线初始化" in onboarding
        assert "安装包自带数据" in onboarding
        assert "我自己的 CSV" in onboarding
        for key in ("target_cutoff", "stock_count", "adjustflag", "disk_required_bytes", "content_root"):
            assert key in main
        assert "contentItem: ScrollView" in main
        assert "footer: Frame" in main
        assert "updatePlanConfirmButton" in main
        assert "CloseOnPressOutside" in main
    finally:
        service.close()


def test_baostock_preview_keeps_confirm_action_visible_at_minimum_window(app_root, tmp_path):
    app = QApplication.instance() or QApplication([])
    service = QuintaraService(app_root)
    backend = QmlBackend(ProductUseCases(service))
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root()))
    engine.setInitialProperties({"backend": backend})
    engine.load(QUrl.fromLocalFile(str(qml_root() / "main.qml")))
    try:
        assert engine.rootObjects()
        window = engine.rootObjects()[0]
        window.setWidth(960)
        window.setHeight(640)
        window.show()
        backend._data_update_preview = {  # type: ignore[attr-defined]
            "current_cutoff": "2026-07-31",
            "target_cutoff": "2026-08-25",
            "membership_route": "PIT_BASELINE",
            "stock_count": 917,
            "start_session": "2026-08-03",
            "trading_sessions": 17,
            "fields": "日线 OHLCV、成交额、换手率、涨跌幅、PE/PS/PCF/PB",
            "adjustflag": "3（后复权）",
            "current_adjustment": "3",
            "current_units": {"amount": "CNY", "volume": "shares"},
            "estimated_download_bytes": 3_600_000,
            "disk_required_bytes": 64 * 1024 * 1024,
            "disk_free_bytes": 194_974 * 1024 * 1024,
            "disk_ok": True,
            "content_root": str(app_root),
            "identity_change": "数据截止日、股票池或字段变化后，旧模型会标记为待重训",
        }
        backend.updatePreviewChanged.emit()
        for _ in range(8):
            app.processEvents()
        dialog = window.findChild(QObject, "updatePlanDialog")
        confirm = window.findChild(QObject, "updatePlanConfirmButton")
        cancel = window.findChild(QObject, "updatePlanCancelButton")
        assert dialog is not None and dialog.property("visible")
        assert float(dialog.property("height")) <= window.height() - 2 * 16
        assert confirm is not None and confirm.property("visible") and confirm.property("enabled")
        assert cancel is not None and cancel.property("visible")
        target = tmp_path / "baostock-preview-minimum.png"
        assert window.grabWindow().save(str(target))
        assert target.stat().st_size > 10_000
    finally:
        engine.deleteLater()
        app.processEvents()
        backend.shutdown()
        service.close()


def test_onboarding_source_summary_and_file_url_helpers(app_root, tmp_path):
    service = QuintaraService(app_root)
    try:
        service.confirm_consent()
        service.onboarding_advance(2)
        backend = QmlBackend(ProductUseCases(service))
        summary = backend.onboardingDataSummary
        assert {"version", "coverage", "size", "location"} <= set(summary)
        target = tmp_path / "result.csv"
        target.write_text("fixture", encoding="utf-8")
        assert backend.exportDestinationExists(target.as_uri())
        assert backend._local_path(target.as_uri()) == target
        assert backend.pathSummary["content_root"] == str(app_root)
        assert "developer_data" in backend.pathSummary["bundled_data"]
        assert len(backend.onboardingDisclosures) == 5
    finally:
        service.close()


def test_qml_layout_smoke_at_125_to_200_percent_dpi():
    script = r'''
import os
from tempfile import TemporaryDirectory
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from quintara.application import ProductUseCases
from quintara.qml_backend import QmlBackend
from quintara.qml_gui import qml_root
from quintara.service import QuintaraService
with TemporaryDirectory() as root:
    app = QGuiApplication([])
    service = QuintaraService(root)
    service.confirm_consent()
    service.onboarding_skip()
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root()))
    backend = QmlBackend(ProductUseCases(service))
    engine.setInitialProperties({"backend": backend})
    engine.load(QUrl.fromLocalFile(str(qml_root() / "main.qml")))
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    window.setWidth(960); window.setHeight(640); window.show()
    for _ in range(4): app.processEvents()
    image = window.grabWindow()
    assert image.width() >= 960 and image.height() >= 640
    service.close()
'''
    for scale in ("1.25", "1.5", "2.0"):
        env = os.environ | {"QT_QPA_PLATFORM": "offscreen", "QSG_RHI_BACKEND": "software", "QT_SCALE_FACTOR": scale}
        result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stderr


def test_gui_backend_csv_training_top5_and_export_journey(app_root, tmp_path):
    app = QApplication.instance() or QApplication([])
    service = QuintaraService(app_root)
    backend = QmlBackend(ProductUseCases(service))
    try:
        service.confirm_consent()
        service.onboarding_skip()
        csv_path = Path(__file__).parents[1] / "fixtures/synthetic_market.csv"
        backend.importCsv(str(csv_path))
        _wait_for_job(app, backend)
        assert backend.currentPagePayload["status"] == "ready"
        backend.startTraining()
        _wait_for_job(app, backend)
        assert backend.currentPage == "results"
        assert len(backend.currentPagePayload["rows"]) == 5
        stages = [item["stage"] for item in backend.jobLogs]
        assert {"checking", "preparing", "training", "predicting", "analysing", "publishing", "succeeded"} <= set(stages)
        target = tmp_path / "gui-export.csv"
        backend.exportLatestResult(str(target))
        _wait_for_job(app, backend)
        assert target.exists()
        assert "research_only" in target.read_text(encoding="utf-8").splitlines()[0]
    finally:
        backend.shutdown()
        service.close()


def test_training_failure_keeps_live_stages_and_actionable_error(app_root):
    app = QApplication.instance() or QApplication([])
    service = QuintaraService(app_root)
    backend = QmlBackend(ProductUseCases(service))

    def failing_run(**kwargs):
        kwargs["progress"]({
            "stage": "preparing",
            "message": "正在读取完整历史并构造训练标签",
            "progress": 0.08,
            "severity": "info",
        })
        kwargs["progress"]({
            "stage": "training",
            "message": "特征已准备完成，正在进行 CPU 模型训练",
            "progress": 0.62,
            "severity": "info",
        })
        raise RuntimeError("lib_lightgbm.dll was not found")

    service.run = failing_run  # type: ignore[method-assign]
    try:
        backend.startTraining()
        _wait_for_job(app, backend)
        assert [item["stage"] for item in backend.jobLogs][-1] == "failed"
        assert "训练组件" in backend.currentPagePayload["summary"]
        assert backend.currentPagePayload["primary_action"]["key"] == "start-training"
        assert "lib_lightgbm.dll" in backend.currentPagePayload["technical"]["copy_text"]
    finally:
        backend.shutdown()
        service.close()


def test_baostock_update_streams_live_stages_to_data_workspace(app_root):
    app = QApplication.instance() or QApplication([])
    service = QuintaraService(app_root)
    backend = QmlBackend(ProductUseCases(service))

    def update_data(*, progress, cancelled):
        assert not cancelled()
        progress({"stage": "connecting", "message": "正在连接 BaoStock", "progress": 0.05})
        progress({"stage": "market", "message": "正在下载行情与扩展字段", "progress": 0.62})
        progress({"stage": "publish", "message": "正在发布完整版本", "progress": 0.94})
        return {"generation": "data-test"}

    service.update_data = update_data  # type: ignore[method-assign]
    try:
        backend._data_update_preview = {"disk_ok": True}  # type: ignore[attr-defined]
        backend.confirmDataUpdate()
        _wait_for_job(app, backend)
        stages = [item["stage"] for item in backend.jobLogs]
        assert {"queued", "connecting", "market", "publish", "complete"} <= set(stages)
        assert backend.currentPage == "data"
        assert backend.jobProgress == 1.0
        assert backend.jobLogs[-1]["severity"] == "success"
        workspace = (qml_root() / "Quintara/pages/WorkspacePage.qml").read_text(encoding="utf-8")
        assert 'root.page.key === "data"' in workspace
        assert "数据更新实时进度" in workspace
    finally:
        backend.shutdown()
        service.close()
