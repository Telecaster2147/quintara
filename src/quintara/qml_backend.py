"""Narrow QObject controller exposed to the QML presentation layer."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication

from .application import ProductUseCases
from .dto import ErrorSummaryDTO, PageStatus


class QmlBackend(QObject):
    pageChanged = Signal()
    themeChanged = Signal()
    onboardingChanged = Signal()
    jobChanged = Signal()
    _trainingFinished = Signal(object)

    def __init__(self, use_cases: ProductUseCases) -> None:
        super().__init__()
        self.use_cases = use_cases
        self.service = use_cases.service
        self._current_page = "home"
        self._payload: dict[str, Any] = {}
        self._theme = str(self.service.registry.setting("theme", "system"))
        self._reduced_motion = bool(self.service.registry.setting("reduced_motion", False))
        self._onboarding = self.service.onboarding_status()
        self._job_running = False
        self._job_operation = ""
        self._worker_thread: threading.Thread | None = None
        self._trainingFinished.connect(self._finish_training)
        self.refresh()

    @Property(str, notify=pageChanged)
    def currentPage(self) -> str:  # noqa: N802
        return self._current_page

    @Property(dict, notify=pageChanged)
    def currentPagePayload(self) -> dict[str, Any]:  # noqa: N802
        return self._payload

    @Property(bool, notify=themeChanged)
    def effectiveDark(self) -> bool:  # noqa: N802
        if self._theme == "dark":
            return True
        if self._theme == "light":
            return False
        app = QGuiApplication.instance()
        hints = app.styleHints() if isinstance(app, QGuiApplication) else None
        return bool(hints and int(hints.colorScheme().value) == 2)

    @Property(str, notify=themeChanged)
    def themeMode(self) -> str:  # noqa: N802
        return self._theme

    @Property(bool, notify=themeChanged)
    def reducedMotion(self) -> bool:  # noqa: N802
        return self._reduced_motion

    @Property(bool, notify=onboardingChanged)
    def onboardingRequired(self) -> bool:  # noqa: N802
        pending = not bool(self._onboarding.get("completed")) and not bool(self._onboarding.get("skipped"))
        return self.service.consent_status()["status"] != "CONFIRMED" or pending

    @Property(bool, notify=onboardingChanged)
    def consentConfirmed(self) -> bool:  # noqa: N802
        """Expose the persisted declaration state for a resumed wizard."""
        return self.service.consent_status()["status"] == "CONFIRMED"

    @Property(int, notify=onboardingChanged)
    def onboardingStep(self) -> int:  # noqa: N802
        return int(self._onboarding.get("step", 0))

    @Property(str, notify=onboardingChanged)
    def onboardingSource(self) -> str:  # noqa: N802
        """Expose the persisted source choice so a resumed wizard keeps context."""
        value = self._onboarding.get("source") or {}
        return str(value.get("kind", "")) if isinstance(value, dict) else str(value)

    @Property(dict, notify=onboardingChanged)
    def onboardingDataSummary(self) -> dict[str, Any]:  # noqa: N802
        """Return a plain-language source summary without exposing raw manifests."""
        active = self.service.data_status().get("active") or {}
        metadata = active.get("metadata") or {}
        if active and str(active.get("source")) == "quintara_provider":
            return {
                "version": str(metadata.get("provider_version") or active.get("generation") or "已校验版本"),
                "coverage": f"{active.get('date_min', '—')} 至 {active.get('date_max', '—')} · {active.get('market_stocks', 0)} 只",
                "size": f"{sum(int(item.get('bytes', 0)) for item in (active.get('files') or {}).values()) / 1024 / 1024:.1f} MiB",
                "location": "本机已保存",
            }
        return {
            "version": "安装介质或受控发布端提供",
            "coverage": "版本、截止日和股票范围以下载前 manifest 为准",
            "size": "传输前显示预计大小与磁盘预算",
            "location": str(self.service.paths.data_generations),
        }

    @Property(bool, notify=jobChanged)
    def jobRunning(self) -> bool:  # noqa: N802
        return self._job_running

    @Slot(int, str, bool, bool, bool)
    def advanceOnboarding(self, step: int, source: str, acceptedRisk: bool, acceptedLicense: bool, acceptedTransfer: bool) -> None:  # noqa: N802
        from .onboarding import DataSourceChoice

        if step >= 1 and not acceptedRisk and not self.consentConfirmed:
            self._show_error(ValueError("请先确认研究用途与风险声明"))
            return
        if step >= 1 and self.service.consent_status()["status"] != "CONFIRMED":
            self.service.confirm_consent()
        choice = DataSourceChoice(source, acceptedLicense, acceptedTransfer) if source else None
        self._onboarding = self.service.onboarding_advance(step, source=choice)
        self.onboardingChanged.emit()
        self.refresh()

    @Slot()
    def skipOnboarding(self) -> None:  # noqa: N802
        self._onboarding = self.service.onboarding_skip()
        self.onboardingChanged.emit()

    @Slot()
    def reopenOnboarding(self) -> None:  # noqa: N802
        self._onboarding = self.service.onboarding_reopen()
        self.onboardingChanged.emit()

    @Slot(str)
    def navigate(self, page: str) -> None:
        if page not in self.use_cases.PAGE_KEYS or page == "settings":
            if page == "settings":
                self.openSettings()
            return
        self._current_page = page
        self.refresh()

    @Slot()
    def refresh(self) -> None:
        try:
            dto = self.use_cases.page(self._current_page)
            self._payload = dto.as_dict()
        except Exception as exc:
            error = ErrorSummaryDTO.from_exception(exc, data_root=self.service.paths.root)
            self._payload = {
                "key": self._current_page,
                "title": "页面暂时不可用",
                "status": PageStatus.ERROR.value,
                "summary": error.message,
                "error": {
                    "code": error.code,
                    "title": error.title,
                    "message": error.message,
                    "impact": error.impact,
                },
            }
        self.pageChanged.emit()

    @Slot(str, str)
    def perform(self, key: str, target: str) -> None:
        if key == "choose-data":
            self.reopenOnboarding()
        elif key == "complete-setup":
            self._current_page = "train"
        elif key == "open-data":
            self._current_page = "data"
        elif key == "open-train":
            self._current_page = "train"
        elif key == "update-data":
            self.startDataUpdate()
            return
        elif key == "retry":
            pass
        elif key == "reopen-onboarding":
            self.reopenOnboarding()
        elif key == "start-training":
            self.startTraining()
            return
        elif key == "export-result":
            self.exportLatestResult("")
            return
        elif target in self.use_cases.PAGE_KEYS:
            self._current_page = target
        self.refresh()

    @Slot(str)
    def importProviderPackage(self, value: str) -> None:  # noqa: N802
        """Import an offline standard-data package without blocking the window."""
        if self._job_running:
            return
        package = self._local_path(value)
        self._start_background(
            "provider-import",
            "正在校验标准数据包",
            lambda: self.service.import_provider_package(package),
        )

    @Slot(str)
    def importCsv(self, value: str) -> None:  # noqa: N802
        path = self._local_path(value)
        if not self.consentConfirmed:
            self._show_error(ValueError("请先确认本地研究免责声明，再导入数据"))
            return
        units = {
            "open": "price", "close": "price", "high": "price", "low": "price",
            "volume": "volume", "amount": "amount", "turnover": "percentage", "change_pct": "percentage",
        }
        try:
            self.service.import_csv(path, units=units)
            from .onboarding import DataSourceChoice

            step = max(2, int(self._onboarding.get("step", 0)))
            self._onboarding = self.service.onboarding_advance(
                step, source=DataSourceChoice("csv")
            )
            self.onboardingChanged.emit()
            self._current_page = "data"
            self.refresh()
        except Exception as exc:
            self._show_error(exc)

    @Slot(str)
    def migrateContentRoot(self, value: str) -> None:  # noqa: N802
        from .storage import migrate_content_root

        try:
            report = migrate_content_root(self.service.paths, self._local_path(value))
            self._payload = {
                "key": "settings", "title": "数据目录迁移完成", "eyebrow": "本地存储", "status": "ready",
                "summary": "新目录已经过 generation 校验。重新启动 Quintara 后使用新目录；旧目录会保留到你确认清理。",
                "cards": [{"title": "新目录", "summary": report["active_root"], "status": "ready"}],
            }
            self.pageChanged.emit()
        except Exception as exc:
            self._show_error(exc)

    @Slot()
    def startTraining(self) -> None:  # noqa: N802
        if self._job_running:
            return
        self._job_running = True
        self._job_operation = "training"
        self._payload = {
            "key": "train", "title": "训练进行中", "eyebrow": "本机 CPU 研究任务", "status": "loading",
            "summary": "正在准备数据、训练模型并生成 Top-5；可在任务安全点停止。",
            "notices": [{"tone": "info", "text": "关闭窗口前 Quintara 会确认任务退出方式。"}],
        }
        self.pageChanged.emit()
        self.jobChanged.emit()

        def work() -> None:
            try:
                result = self.service.run(strategy="balanced")
                self._trainingFinished.emit({"result": result, "operation": "training"})
            except Exception as exc:
                self._trainingFinished.emit({"error": exc, "operation": "training"})

        self._worker_thread = threading.Thread(target=work, name="quintara-training", daemon=True)
        self._worker_thread.start()

    @Slot()
    def startDataUpdate(self) -> None:  # noqa: N802
        if self._job_running:
            return
        self._start_background(
            "update",
            "正在连接受控数据更新路径",
            lambda: self.service.update_data(),
        )

    @Slot()
    def cancelTraining(self) -> None:  # noqa: N802
        self.service.cancel_active()

    @Slot(object)
    def _finish_training(self, outcome: object) -> None:
        value = outcome if isinstance(outcome, dict) else {}
        self._job_running = False
        operation = str(value.get("operation", self._job_operation))
        self._job_operation = ""
        self.jobChanged.emit()
        if "error" in value:
            self._show_error(value["error"])
            return
        self._current_page = "results" if operation == "training" else "data"
        self.refresh()

    def _start_background(self, operation: str, message: str, work: Any) -> None:
        self._job_running = True
        self._job_operation = operation
        self._payload = {
            "key": self._current_page,
            "title": message,
            "eyebrow": "本机任务",
            "status": "loading",
            "summary": "正在安全点处理；上一份已发布数据仍保持可用。",
            "notices": [{"tone": "info", "text": "任务完成后会自动刷新当前页面。"}],
        }
        self.pageChanged.emit()
        self.jobChanged.emit()

        def worker() -> None:
            try:
                result = work()
                self._trainingFinished.emit({"result": result, "operation": operation})
            except Exception as exc:
                self._trainingFinished.emit({"error": exc, "operation": operation})

        self._worker_thread = threading.Thread(target=worker, name=f"quintara-{operation}", daemon=True)
        self._worker_thread.start()

    @Slot(str)
    @Slot(str, bool)
    def exportLatestResult(self, value: str, overwrite: bool = False) -> None:  # noqa: N802
        runs = self.service.runs(100)
        row = next((item for item in runs if item.get("state") in {"SUCCEEDED", "CACHED"}), None)
        if row is None:
            self._show_error(RuntimeError("还没有可导出的结果"))
            return
        destination = self._local_path(value) if value else Path.home() / "Documents" / f"quintara-{row['id']}.csv"
        try:
            report = self.service.export_result(str(row["id"]), destination, overwrite=overwrite)
            self._payload = self.use_cases.results(str(row["id"])).as_dict()
            self._payload["notices"] = list(self._payload.get("notices", [])) + [{"tone": "success", "text": f"已导出到 {report['result_csv']}"}]
            self.pageChanged.emit()
        except Exception as exc:
            self._show_error(exc)

    @Slot(str, result=bool)
    def exportDestinationExists(self, value: str) -> bool:  # noqa: N802
        return self._local_path(value).exists()

    @staticmethod
    def _local_path(value: str) -> Path:
        """Convert Qt file URLs and native paths consistently on every OS."""
        url = QUrl(str(value))
        if url.isLocalFile():
            return Path(url.toLocalFile())
        return Path(str(value).removeprefix("file://"))

    def _show_error(self, exc: Exception) -> None:
        error = ErrorSummaryDTO.from_exception(exc, data_root=self.service.paths.root)
        self._payload = {
            "key": self._current_page, "title": error.title, "status": "error", "summary": error.message,
            "error": {"code": error.code, "title": error.title, "message": error.message, "impact": error.impact},
            "technical": {"title": "技术详情", "copy_text": json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False)},
        }
        self.pageChanged.emit()

    def shutdown(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            self.service.cancel_active()
            self._worker_thread.join(timeout=5)

    @Slot()
    def openSettings(self) -> None:  # noqa: N802
        self._payload = {
            "key": "settings",
            "title": "设置",
            "eyebrow": "本机偏好",
            "status": "ready",
            "summary": "显示偏好和隐私选项保存在本机。",
            "cards": [
                {"title": "显示主题", "summary": self._theme, "status": "ready"},
                {"title": "减少动态效果", "summary": "已开启" if self._reduced_motion else "已关闭", "status": "ready"},
                {"title": "遥测", "summary": "永久关闭", "status": "ready"},
            ],
            "notices": [{"tone": "info", "text": "Quintara 不会自动上传诊断、截图或使用记录。"}],
            "primary_action": {"key": "reopen-onboarding", "label": "重新打开首次向导", "target": "settings", "primary": True},
            "actions": [{"key": "choose-content-root", "label": "迁移数据目录", "target": "settings", "primary": False}],
        }
        self._current_page = "settings"
        self.pageChanged.emit()

    @Slot(str)
    def setTheme(self, value: str) -> None:  # noqa: N802
        if value not in {"system", "light", "dark"}:
            return
        self._theme = value
        self.service.registry.set_setting("theme", value)
        self.themeChanged.emit()

    @Slot(bool)
    def setReducedMotion(self, value: bool) -> None:  # noqa: N802
        self._reduced_motion = bool(value)
        self.service.registry.set_setting("reduced_motion", self._reduced_motion)
        self.themeChanged.emit()
