"""Standalone Qt Widgets frontend; no browser, local HTTP server, or telemetry."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QPalette
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .core import AppPaths, UniverseMode
from .csv_validation import REQUIRED_UNITS
from .platform import FileLock, LockBusy
from .service import STRATEGIES, QuintaraService


class _Worker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: Callable[[], Any]) -> None:
        super().__init__()
        self.operation = operation

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(self.operation())
        except Exception as exc:  # pragma: no cover - exercised by GUI users
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, root: str | Path | None = None) -> None:
        super().__init__()
        self.service = QuintaraService(root)
        self.setWindowTitle(f"Quintara {__version__} · A股周度组合")
        self.resize(1120, 720)
        self._threads: list[QThread] = []
        self._running = False
        self._closing = False
        self._close_after_job = False
        self._single_instance_server: QLocalServer | None = None
        self._progress_target: QPlainTextEdit | None = None
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(500)
        self._progress_timer.timeout.connect(self._poll_progress)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._shutdown_threads)
        self._build()
        self._refresh()

    def _build(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.addTab(self._overview(), "概览")
        self.tabs.addTab(self._data_page(), "数据")
        self.tabs.addTab(self._universe_page(), "股票池")
        self.tabs.addTab(self._run_page(), "训练与预测")
        self.tabs.addTab(self._results_page(), "结果")
        self.tabs.addTab(self._history_page(), "运行历史")
        self.tabs.addTab(self._settings_page(), "设置")
        self.tabs.addTab(self._doctor_page(), "环境诊断")
        self.setCentralWidget(self.tabs)

    def _text_page(self, title: str) -> tuple[QWidget, QPlainTextEdit]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(f"<h2>{title}</h2>"))
        text = QPlainTextEdit()
        text.setReadOnly(True)
        layout.addWidget(text)
        return page, text

    def _overview(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>Quintara 本地研究工作区</h2><p>只在本机处理行情、模型和结果，不启动 WebUI。</p>"))
        actions = QHBoxLayout()
        guide = QPushButton("打开首次使用向导")
        guide.clicked.connect(self._show_guide)
        weekly = QPushButton("一键检查、训练并输出 Top-5")
        weekly.clicked.connect(self._run_job)
        self.weekly_button = weekly
        actions.addWidget(guide)
        actions.addWidget(weekly)
        layout.addLayout(actions)
        self.overview_text = QPlainTextEdit()
        self.overview_text.setReadOnly(True)
        layout.addWidget(self.overview_text)
        self.overview_text.setPlaceholderText("首次运行时请先在“数据”页更新或导入数据。")
        return page

    def _data_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>数据生命周期</h2><p>每次导入/更新生成不可变快照，源 CSV 保持不变。</p>"))
        row = QHBoxLayout()
        update = QPushButton("登录 BaoStock 并更新（PIT侧车）")
        update.clicked.connect(self._update_data)
        fallback = QPushButton("显式使用当前快照（无 PIT 回退）")
        fallback.clicked.connect(self._update_non_pit)
        import_button = QPushButton("导入 CSV")
        import_button.clicked.connect(self._import_csv)
        status = QPushButton("刷新状态")
        status.clicked.connect(self._refresh)
        row.addWidget(update)
        row.addWidget(fallback)
        row.addWidget(import_button)
        row.addWidget(status)
        layout.addLayout(row)
        self.data_text = QPlainTextEdit()
        self.data_text.setReadOnly(True)
        layout.addWidget(self.data_text)
        return page

    def _run_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>训练与预测</h2><p>CPU 为权威路径；GPU 仅在环境诊断通过时作为实验选项。</p>"))
        form = QFormLayout()
        self.strategy = QComboBox()
        self.strategy.addItems(sorted(STRATEGIES))
        form.addRow("选股策略", self.strategy)
        self.years = QSpinBox()
        self.years.setRange(3, 10)
        self.years.setValue(5)
        form.addRow("历史年限", self.years)
        self.mode = QComboBox()
        self.mode.addItem("使用当前宇宙", "")
        for value in UniverseMode:
            self.mode.addItem(value.value, value.value)
        form.addRow("宇宙路由", self.mode)
        layout.addLayout(form)
        run_button = QPushButton("开始训练并输出 Top-5")
        run_button.clicked.connect(self._run_job)
        self.run_button = run_button
        layout.addWidget(run_button)
        cancel_button = QPushButton("请求停止当前作业")
        cancel_button.clicked.connect(self._cancel_job)
        layout.addWidget(cancel_button)
        self.run_text = QPlainTextEdit()
        self.run_text.setReadOnly(True)
        layout.addWidget(self.run_text)
        return page

    def _results_page(self) -> QWidget:
        page, self.results_text = self._text_page("最近结果")
        return page

    def _universe_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>股票池与路线</h2>"))
        row = QHBoxLayout()
        create = QPushButton("创建自定义股票池")
        create.clicked.connect(self._create_universe)
        add_codes = QPushButton("追加代码")
        add_codes.clicked.connect(self._add_codes)
        remove_codes = QPushButton("删除代码")
        remove_codes.clicked.connect(self._remove_codes)
        import_codes = QPushButton("从 CSV 批量导入代码")
        import_codes.clicked.connect(self._import_codes_csv)
        search = QPushButton("BaoStock 搜索")
        search.clicked.connect(self._search_stocks)
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self._refresh)
        row.addWidget(create)
        row.addWidget(add_codes)
        row.addWidget(remove_codes)
        row.addWidget(import_codes)
        row.addWidget(search)
        row.addWidget(refresh)
        layout.addLayout(row)
        self.universe_text = QPlainTextEdit()
        self.universe_text.setReadOnly(True)
        layout.addWidget(self.universe_text)
        return page

    def _history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>运行历史与事件</h2>"))
        refresh = QPushButton("刷新历史")
        refresh.clicked.connect(self._refresh)
        layout.addWidget(refresh)
        self.history_text = QPlainTextEdit()
        self.history_text.setReadOnly(True)
        layout.addWidget(self.history_text)
        return page

    def _settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>设置与隐私</h2><p>默认无遥测。版本检查只有在此处主动点击时发生。</p>"))
        consent = QPushButton("确认/更新研究免责声明")
        consent.clicked.connect(self._accept_consent)
        version = QPushButton("检查 GitHub Release 版本")
        version.clicked.connect(lambda: self._start(lambda: self.service.version_info(check=True), self.settings_text))
        version_toggle = QPushButton("切换版本提示开关")
        version_toggle.clicked.connect(lambda: self._start(lambda: self.service.set_version_check(not self.service.version_info()["enabled"]), self.settings_text))
        diagnostics = QPushButton("导出本地脱敏诊断 JSON")
        diagnostics.clicked.connect(lambda: self._start(self.service.export_diagnostics, self.settings_text))
        theme = QComboBox()
        theme.addItem("跟随系统", "system")
        theme.addItem("浅色", "light")
        theme.addItem("深色", "dark")
        theme.currentIndexChanged.connect(lambda: self._apply_theme(str(theme.currentData())))
        layout.addWidget(QLabel("显示主题"))
        layout.addWidget(theme)
        layout.addWidget(consent)
        layout.addWidget(version)
        layout.addWidget(version_toggle)
        layout.addWidget(diagnostics)
        self.settings_text = QPlainTextEdit()
        self.settings_text.setReadOnly(True)
        layout.addWidget(self.settings_text)
        return page

    def _doctor_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>环境诊断</h2>"))
        button = QPushButton("重新检测")
        button.clicked.connect(self._refresh)
        layout.addWidget(button)
        self.doctor_text = QPlainTextEdit()
        self.doctor_text.setReadOnly(True)
        layout.addWidget(self.doctor_text)
        return page

    def _refresh(self) -> None:
        try:
            bootstrap = self.service.bootstrap()
            doctor = self.service.doctor()
            runs = self.service.runs(5)
            universes = self.service.universes()
            self.overview_text.setPlainText(json.dumps(bootstrap, ensure_ascii=False, indent=2, default=str))
            self.data_text.setPlainText(json.dumps(bootstrap.get("active_data") or {"status": "NO_ACTIVE_DATA"}, ensure_ascii=False, indent=2, default=str))
            self.doctor_text.setPlainText(json.dumps(doctor, ensure_ascii=False, indent=2, default=str))
            latest_result = None
            if runs and runs[0].get("state") in {"SUCCEEDED", "CACHED"}:
                try:
                    latest_result = self.service.result_details(str(runs[0]["id"]))
                except Exception as exc:
                    latest_result = {"error": str(exc)}
            self.results_text.setPlainText(json.dumps(latest_result or runs, ensure_ascii=False, indent=2, default=str))
            self.universe_text.setPlainText(json.dumps(universes, ensure_ascii=False, indent=2, default=str))
            self.history_text.setPlainText(json.dumps([{**run, "events": self.service.job_events(run["id"])} for run in runs], ensure_ascii=False, indent=2, default=str))
            self.settings_text.setPlainText(json.dumps(self.service.consent_status(), ensure_ascii=False, indent=2, default=str))
            enabled = bool(bootstrap.get("active_data")) and bool(universes)
            self.weekly_button.setEnabled(enabled)
            self.run_button.setEnabled(enabled)
        except Exception as exc:
            self._show_error(str(exc))

    def _start(
        self,
        operation: Callable[[], Any],
        target: QPlainTextEdit,
        on_done: Callable[[Any], None] | None = None,
    ) -> None:
        if self._running:
            self._show_error("已有作业在运行；请等待其完成或先请求停止。")
            return
        self._running = True
        self._progress_target = target
        self._progress_timer.start()
        thread = QThread(self)
        worker = _Worker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda value: self._worker_done(thread, value, target, on_done))
        worker.failed.connect(lambda error: self._worker_failed(thread, error))
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        thread.start()

    def _worker_done(
        self,
        thread: QThread,
        value: Any,
        target: QPlainTextEdit,
        on_done: Callable[[Any], None] | None = None,
    ) -> None:
        target.setPlainText(json.dumps(value, ensure_ascii=False, indent=2, default=str))
        thread.quit()
        self._running = False
        self._progress_timer.stop()
        if on_done is not None:
            on_done(value)
        self._refresh()
        if self._close_after_job:
            self._finish_close()

    def _worker_failed(self, thread: QThread, error: str) -> None:
        self._show_error(error)
        thread.quit()
        self._running = False
        self._progress_timer.stop()
        if self._close_after_job:
            self._finish_close()

    def _poll_progress(self) -> None:
        run_id = self.service.active_run_id
        if not run_id or self._progress_target is None:
            return
        events = self.service.job_events(run_id)
        if events:
            latest = events[-1]
            self._progress_target.setPlainText(
                f"阶段：{latest.get('stage')}\n状态：{latest.get('message')}\n"
                f"严重性：{latest.get('severity')}\n已用事件数：{len(events)}\n\n"
                "技术详情：\n" + json.dumps(events, ensure_ascii=False, indent=2, default=str)
            )

    def _update_data(self) -> None:
        sidecar, _ = QFileDialog.getOpenFileName(
            self,
            "选择可选的历史 PIT 成分 CSV（取消则沿用已验证 PIT）",
            "",
            "CSV (*.csv)",
        )
        kwargs = {"pit_membership_csv": sidecar} if sidecar else {}
        self._start(lambda: self.service.update_data(**kwargs), self.data_text)

    def _update_non_pit(self) -> None:
        answer = QMessageBox.question(
            self,
            "确认无 PIT 回退",
            "当前快照不能代表历史成分。继续后结果会标记 NON_PIT_FALLBACK，并提示幸存者偏差。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._start(lambda: self.service.update_data(allow_non_pit=True), self.data_text)

    def _import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择市场 CSV", "", "CSV (*.csv)")
        if path:
            units = ", ".join(f"{field}={unit}" for field, unit in REQUIRED_UNITS.items())
            answer = QMessageBox.question(
                self,
                "确认 CSV 单位",
                f"Quintara 不替用户换算数据。请确认此 CSV 已使用以下单位：\n{units}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._start(lambda: self.service.import_csv(path, units=dict(REQUIRED_UNITS)), self.data_text)

    def _run_job(self) -> None:
        if self.service.consent_status()["status"] != "CONFIRMED":
            answer = QMessageBox.question(
                self,
                "研究免责声明确认",
                "Quintara 仅用于中国大陆 A 股研究，输出不构成收益承诺或个性化投资建议。\n\n确认后将在本机记录声明版本和时间，不会上传。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.service.confirm_consent()
        mode_value = self.mode.currentData()
        mode = UniverseMode(mode_value) if mode_value else None
        self._start(lambda: self.service.run(mode=mode, strategy=self.strategy.currentText(), config={"training_years": self.years.value()}), self.run_text)

    def _cancel_job(self) -> None:
        run_id = self.service.cancel_active()
        if run_id:
            self.run_text.appendPlainText(f"已请求停止作业 {run_id}")

    def _accept_consent(self) -> None:
        self.service.confirm_consent()
        self._refresh()

    def _show_guide(self) -> None:
        QMessageBox.information(self, "首次使用向导", "1. 阅读研究免责声明\n2. 运行环境诊断\n3. 导入 CSV 或更新 BaoStock\n4. 选择 PIT/CUSTOM 路线\n5. 训练并查看本地结果\n\n此向导可随时从概览页重新打开。")

    def _create_universe(self) -> None:
        name, accepted = QInputDialog.getText(self, "创建股票池", "名称")
        if not accepted or not name.strip():
            return
        codes, accepted = QInputDialog.getText(self, "股票代码", "输入逗号分隔的六位代码（至少 100 个）")
        if not accepted:
            return
        try:
            value = self.service.create_universe(name.strip(), UniverseMode.CUSTOM_UNIVERSE, [item.strip() for item in codes.split(",") if item.strip()])
            self.universe_text.setPlainText(json.dumps(value, ensure_ascii=False, indent=2, default=str))
        except Exception as exc:
            self._show_error(str(exc))

    def _active_custom_universe(self) -> dict[str, Any] | None:
        for item in self.service.universes():
            if item.get("active") and item.get("mode") == UniverseMode.CUSTOM_UNIVERSE.value:
                return item
        return None

    def _edit_codes(self, *, add: bool) -> None:
        active = self._active_custom_universe()
        if active is None:
            self._show_error("当前没有激活的自定义股票池；请先创建或激活一个股票池。")
            return
        label = "追加" if add else "删除"
        codes, accepted = QInputDialog.getText(self, f"{label}代码", "输入逗号分隔的六位代码")
        if not accepted or not codes.strip():
            return
        values = [item.strip() for item in codes.split(",") if item.strip()]
        def operation() -> Any:
            if add:
                return self.service.edit_custom_universe(str(active["id"]), add_codes=values)
            return self.service.edit_custom_universe(str(active["id"]), remove_codes=values)
        # Keep network-free definition edits on the same worker path as the
        # other universe actions, so the window remains responsive.
        self._start(operation, self.universe_text)

    def _add_codes(self) -> None:
        self._edit_codes(add=True)

    def _remove_codes(self) -> None:
        self._edit_codes(add=False)

    def _import_codes_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择代码 CSV", "", "CSV (*.csv);;Text (*.txt)")
        if not path:
            return
        try:
            import pandas as pd

            frame = pd.read_csv(path, dtype=str)
            column = next((value for value in ("stock_id", "股票代码", "code", "代码") if value in frame.columns), frame.columns[0])
            codes = frame[column].dropna().astype(str).tolist()
            active = self._active_custom_universe()
            if active is None:
                value = self.service.create_universe(Path(path).stem, UniverseMode.CUSTOM_UNIVERSE, codes)
            else:
                value = self.service.edit_custom_universe(str(active["id"]), add_codes=codes)
            self.universe_text.setPlainText(json.dumps(value, ensure_ascii=False, indent=2, default=str))
            self._refresh()
        except Exception as exc:
            self._show_error(str(exc))

    def _search_stocks(self) -> None:
        query, accepted = QInputDialog.getText(self, "BaoStock 搜索", "输入代码或股票名称")
        if accepted and query.strip():
            def choose_and_add(results: Any) -> None:
                active = self._active_custom_universe()
                if active is None or not results:
                    return
                labels = [f"{item.get('stock_id', '')}  {item.get('name', '')}" for item in results]
                selected, ok = QInputDialog.getItem(self, "选择股票", "追加到当前自定义池", labels, 0, False)
                if ok and selected:
                    code = selected.split()[0]
                    self._start(
                        lambda: self.service.edit_custom_universe(str(active["id"]), add_codes=[code]),
                        self.universe_text,
                    )

            self._start(lambda: self.service.search_stocks(query.strip()), self.universe_text, choose_and_add)

    def _apply_theme(self, theme: str) -> None:
        app = QApplication.instance()
        if app is None or not isinstance(app, QApplication):
            return
        if theme == "dark":
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor("#202124"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#f1f3f4"))
            palette.setColor(QPalette.ColorRole.Base, QColor("#303134"))
            palette.setColor(QPalette.ColorRole.Text, QColor("#f1f3f4"))
            palette.setColor(QPalette.ColorRole.Button, QColor("#3c4043"))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f1f3f4"))
            app.setPalette(palette)
        else:
            app.setPalette(QApplication.style().standardPalette())

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Quintara", message)

    def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt API
        if self._closing:
            event.accept()
            return
        if self._running:
            answer = QMessageBox.question(self, "作业正在运行", "当前作业尚未完成，确认请求停止并退出？")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._close_after_job = True
            self._cancel_job()
            self.hide()
            QTimer.singleShot(8000, self._force_close)
            event.accept()
            return
        self._finish_close()
        event.accept()

    def _finish_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.service.close()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _force_close(self) -> None:
        if self._running:
            for thread in self._threads:
                if thread.isRunning():
                    thread.requestInterruption()
                    thread.terminate()
                    thread.wait(1000)
            self.service.data.recover()
            self._running = False
        self._finish_close()

    def _shutdown_threads(self) -> None:
        """Keep Qt from destroying a live worker during application teardown."""
        try:
            if self._running:
                self.service.cancel_active()
            for thread in self._threads:
                if thread.isRunning():
                    thread.requestInterruption()
                    if not thread.wait(1500):
                        thread.terminate()
                        thread.wait(1000)
            if self._running:
                self.service.data.recover()
                self._running = False
        except Exception:
            # Qt does not support exceptions escaping an aboutToQuit handler;
            # startup recovery will remove any remaining staging directories.
            self._running = False


def launch(root: str | Path | None = None) -> int:
    """Launch the Qt Quick release GUI; MainWindow remains a v1 test fixture."""
    from .qml_gui import launch as launch_qml

    return launch_qml(root)


def launch_widgets_fixture(root: str | Path | None = None) -> int:
    """Launch the historical Widgets shell for migration comparison tests."""
    app = QApplication.instance() or QApplication([])
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
    QLocalServer.removeServer(server_name)
    server = QLocalServer()
    window = MainWindow(root)
    window._single_instance_server = server  # keep the server alive with the window

    def activate() -> None:
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            if connection is not None:
                connection.disconnectFromServer()
        window.showNormal()
        window.raise_()
        window.activateWindow()

    if server.listen(server_name):
        server.newConnection.connect(activate)
    else:
        # Some locked-down Linux desktop images disable Qt local sockets.  The
        # filesystem lock still prevents a second writer; the first window
        # remains usable and the second launch exits without starting a worker.
        window._single_instance_server = None
    window.show()
    try:
        return app.exec()
    finally:
        instance_lock.release()
