"""Narrow QObject controller exposed to the QML presentation layer."""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication

from .application import ProductUseCases
from .bundled_data import developer_data_package, developer_data_summary
from .dto import ErrorSummaryDTO, PageStatus
from .onboarding import RISK_SECTIONS

LOG = logging.getLogger(__name__)


class QmlBackend(QObject):
    pageChanged = Signal()
    themeChanged = Signal()
    onboardingChanged = Signal()
    jobChanged = Signal()
    pathsChanged = Signal()
    updatePreviewChanged = Signal()
    _trainingFinished = Signal(object)
    _jobProgress = Signal(object)

    def __init__(self, use_cases: ProductUseCases) -> None:
        super().__init__()
        self.use_cases = use_cases
        self.service = use_cases.service
        self._current_page = "home"
        self._payload: dict[str, Any] = {}
        self._theme = str(self.service.registry.setting("theme", "system"))
        self._reduced_motion = bool(self.service.registry.setting("reduced_motion", False))
        self._onboarding = self.service.onboarding_status()
        self._last_csv_path = str(self.service.registry.setting("last_csv_path", "") or "")
        self._last_export_path = str(self.service.registry.setting("last_export_path", "") or "")
        self._last_provider_path = str(self.service.registry.setting("last_provider_path", "") or "")
        self._job_running = False
        self._job_operation = ""
        self._job_progress = 0.0
        self._job_stage = ""
        self._job_logs: list[dict[str, Any]] = []
        self._job_started_at = 0.0
        self._data_update_preview: dict[str, Any] = {}
        self._data_update_initializing = False
        self._data_update_cancel = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._trainingFinished.connect(self._finish_training)
        self._jobProgress.connect(self._apply_job_progress)
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self.jobChanged.emit)
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

    @Property(list, notify=onboardingChanged)
    def onboardingDisclosures(self) -> list[dict[str, str]]:  # noqa: N802
        return [dict(item) for item in RISK_SECTIONS]

    @Property(dict, notify=pathsChanged)
    def pathSummary(self) -> dict[str, Any]:  # noqa: N802
        return self._path_summary()

    def _path_summary(self) -> dict[str, Any]:
        bundled = developer_data_summary()
        active = self.service.data.active_manifest()
        active_path = (
            self.service.paths.data_generations / str(active["generation"])
            if active
            else None
        )
        return {
            "content_root": str(self.service.paths.root),
            "active_data": str(active_path) if active_path else "尚未生成",
            "bundled_data": str(bundled.get("path") or "未检测到安装包数据"),
            "last_csv": self._last_csv_path or "尚未选择",
            "last_provider": self._last_provider_path or "尚未选择",
            "last_export": self._last_export_path or "尚未导出",
        }

    @Property(bool, notify=onboardingChanged)
    def bundledDataAvailable(self) -> bool:  # noqa: N802
        return developer_data_package() is not None

    @Property(bool, notify=onboardingChanged)
    def bundledDataImported(self) -> bool:  # noqa: N802
        active = self.service.data.active_manifest() or {}
        metadata = active.get("metadata") or {}
        return metadata.get("provider_dataset") == "quintara-developer-data-v1"

    @Property(bool, notify=onboardingChanged)
    def activeDataAvailable(self) -> bool:  # noqa: N802
        return self.service.data.active_manifest() is not None

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
                "location": str(metadata.get("package_location") or self.service.paths.data_generations),
                "working_location": str(self.service.paths.data_generations / str(active.get("generation"))),
            }
        bundled = developer_data_summary()
        return {
            "version": bundled.get("version") or "待检测",
            "coverage": bundled.get("coverage") or "安装数据包清单待检测",
            "size": bundled.get("size") or "待检测",
            "location": bundled.get("path") or "安装目录中未检测到数据包",
            "working_location": str(self.service.paths.data_generations),
        }

    @Property(bool, notify=jobChanged)
    def jobRunning(self) -> bool:  # noqa: N802
        return self._job_running

    @Property(float, notify=jobChanged)
    def jobProgress(self) -> float:  # noqa: N802
        return self._job_progress

    @Property(str, notify=jobChanged)
    def jobStage(self) -> str:  # noqa: N802
        return self._job_stage

    @Property(int, notify=jobChanged)
    def jobElapsedSeconds(self) -> int:  # noqa: N802
        if not self._job_started_at:
            return 0
        return max(0, int(time.monotonic() - self._job_started_at))

    @Property(list, notify=jobChanged)
    def jobLogs(self) -> list[dict[str, Any]]:  # noqa: N802
        return [dict(item) for item in self._job_logs]

    @Property(dict, notify=updatePreviewChanged)
    def dataUpdatePreview(self) -> dict[str, Any]:  # noqa: N802
        return dict(self._data_update_preview)

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
            self._payload["path_rows"] = self._path_rows(self._current_page)
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

    def _path_rows(self, page: str) -> list[dict[str, str]]:
        paths = self._path_summary()
        rows = [{"label": "当前工作目录", "path": str(paths["content_root"])}]
        if page in {"home", "data", "settings"}:
            rows.append({"label": "安装包自带数据", "path": str(paths["bundled_data"])})
            rows.append({"label": "当前活动数据", "path": str(paths["active_data"])})
        if page in {"data", "settings"} and self._last_csv_path:
            rows.append({"label": "最近导入 CSV", "path": self._last_csv_path})
        if page in {"results", "history", "settings"} and self._last_export_path:
            rows.append({"label": "最近导出结果", "path": self._last_export_path})
        return rows

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
        elif key == "initialize-baostock":
            self.prepareDataUpdate(True)
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
        self._last_provider_path = str(package.resolve())
        self.service.registry.set_setting("last_provider_path", self._last_provider_path)
        self.pathsChanged.emit()
        self._start_background(
            "provider-import",
            "正在校验标准数据包",
            lambda: self.service.import_provider_package(package),
        )

    @Slot()
    def importBundledData(self) -> None:  # noqa: N802
        if self._job_running:
            return
        package = developer_data_package()
        if package is None:
            self._show_error(FileNotFoundError("安装目录中的开发者数据包未通过完整性检测"))
            return
        if not self.consentConfirmed:
            self._show_error(ValueError("请先逐步阅读并确认研究边界声明"))
            return
        self._last_provider_path = str(package)
        self.service.registry.set_setting("last_provider_path", self._last_provider_path)
        self.pathsChanged.emit()
        self._start_background(
            "bundled-import",
            "正在校验并导入开发者自带数据",
            lambda: self.service.import_provider_package(package),
        )

    @Slot(str)
    def importCsv(self, value: str) -> None:  # noqa: N802
        if self._job_running:
            return
        path = self._local_path(value)
        if not self.consentConfirmed:
            self._show_error(ValueError("请先确认本地研究免责声明，再导入数据"))
            return
        units = {
            "open": "price", "close": "price", "high": "price", "low": "price",
            "volume": "volume", "amount": "amount", "turnover": "percentage", "change_pct": "percentage",
        }
        self._last_csv_path = str(path.resolve())
        self.service.registry.set_setting("last_csv_path", self._last_csv_path)
        self.pathsChanged.emit()
        self._start_background(
            "csv-import",
            "正在检查并导入 CSV",
            lambda: self.service.import_csv(path, units=units),
        )

    @Slot(str)
    def migrateContentRoot(self, value: str) -> None:  # noqa: N802
        from .storage import migrate_content_root

        if self._job_running:
            return
        destination = self._local_path(value)
        self._start_background(
            "content-root-migration",
            "正在校验并迁移数据目录",
            lambda: migrate_content_root(self.service.paths, destination),
        )

    def _begin_job(self, operation: str, stage: str, message: str) -> None:
        self._job_running = True
        self._job_operation = operation
        self._job_progress = 0.0
        self._job_stage = stage
        self._job_logs = []
        self._job_started_at = time.monotonic()
        self._append_job_log(stage, message, "info", emit=False)
        self._elapsed_timer.start()

    def _append_job_log(
        self,
        stage: str,
        message: str,
        severity: str = "info",
        *,
        emit: bool = True,
    ) -> None:
        entry = {
            "stage": stage,
            "message": message,
            "severity": severity,
            "elapsed_seconds": self.jobElapsedSeconds,
        }
        if not self._job_logs or (
            self._job_logs[-1].get("stage"), self._job_logs[-1].get("message")
        ) != (stage, message):
            self._job_logs.append(entry)
            self._job_logs = self._job_logs[-12:]
        if emit:
            self.jobChanged.emit()

    @staticmethod
    def _friendly_failure(exc: Exception) -> str:
        message = str(exc).lower()
        if "lightgbm" in message or "lib_lightgbm" in message or "dll" in message:
            return "训练组件没有完整加载。请重新运行当前安装器执行覆盖安装，再从训练页重试。"
        if "label" in message or "history" in message or "历史截面" in message:
            return "当前数据历史或标签覆盖不足。请在数据页更新完整历史并检查股票池后重试。"
        if "100" in message or "universe" in message or "股票池" in message:
            return "当前股票池未达到训练条件。请补足股票或重新选择活动股票池。"
        if "memory" in message or "内存" in message:
            return "本机可用内存不足。请关闭占用较高的程序后重新开始训练。"
        if "space" in message or "disk" in message or "磁盘" in message:
            return "结果暂存空间不足。请释放工作目录所在磁盘空间后重试。"
        return "训练在当前阶段停止。上一份已发布结果保持可用，请查看技术详情后重试。"

    @Slot()
    def startTraining(self) -> None:  # noqa: N802
        if self._job_running:
            return
        self._begin_job("training", "queued", "训练任务已开始，正在检查本机数据与股票池")
        self._payload = {
            "key": "train", "title": "训练进行中", "eyebrow": "本机 CPU 研究任务", "status": "loading",
            "summary": "正在准备数据、训练模型并生成 Top-5；可在任务安全点停止。",
            "notices": [{"tone": "info", "text": "关闭窗口前 Quintara 会确认任务退出方式。"}],
            "job_logs": self.jobLogs,
        }
        self.pageChanged.emit()
        self.jobChanged.emit()

        def work() -> None:
            try:
                result = self.service.run(
                    strategy="balanced",
                    progress=lambda value: self._jobProgress.emit(
                        {"operation": "training", **value}
                    ),
                )
                self._trainingFinished.emit({"result": result, "operation": "training"})
            except Exception as exc:
                LOG.exception("Training worker stopped with an exception")
                self._trainingFinished.emit({"error": exc, "operation": "training"})

        self._worker_thread = threading.Thread(target=work, name="quintara-training", daemon=True)
        self._worker_thread.start()

    @Slot()
    def startDataUpdate(self) -> None:  # noqa: N802
        self.prepareDataUpdate(False)

    @Slot(bool)
    def prepareDataUpdate(self, initializing: bool = False) -> None:  # noqa: N802
        if self._job_running:
            return
        self._data_update_initializing = bool(initializing)
        self._start_background(
            "update-preview",
            "正在读取 BaoStock 更新计划",
            lambda: self.service.plan_data_update(),
        )

    @Slot()
    def confirmDataUpdate(self) -> None:  # noqa: N802
        if self._job_running or not self._data_update_preview:
            return
        initializing = self._data_update_initializing
        self._data_update_preview = {}
        self.updatePreviewChanged.emit()
        self._data_update_cancel.clear()
        self._start_background(
            "baostock-initialize" if initializing else "baostock-update",
            "正在从 BaoStock 构建活动数据",
            lambda: self.service.update_data(
                progress=lambda value: self._jobProgress.emit(value),
                cancelled=self._data_update_cancel.is_set,
            ),
        )

    @Slot()
    def cancelDataUpdate(self) -> None:  # noqa: N802
        self._data_update_cancel.set()

    @Slot()
    def cancelTraining(self) -> None:  # noqa: N802
        if self._job_operation.startswith("baostock"):
            self.cancelDataUpdate()
        else:
            self.service.cancel_active()

    @Slot(object)
    def _finish_training(self, outcome: object) -> None:
        value = outcome if isinstance(outcome, dict) else {}
        operation = str(value.get("operation", self._job_operation))
        self._job_running = False
        self._elapsed_timer.stop()
        self._job_operation = ""
        if "error" in value:
            exc = value["error"]
            if isinstance(exc, Exception):
                self._job_stage = "failed"
                self._job_progress = 0.0
                self._append_job_log("failed", self._friendly_failure(exc), "error", emit=False)
                self.jobChanged.emit()
                self._show_error(exc, operation=operation)
            return
        self._job_progress = 1.0
        if operation == "training":
            self._job_stage = "succeeded"
            if not self._job_logs or self._job_logs[-1].get("stage") != "succeeded":
                self._append_job_log("succeeded", "训练与结果发布已完成", "success", emit=False)
        elif operation.startswith("baostock"):
            self._job_stage = "complete"
            if not self._job_logs or self._job_logs[-1].get("stage") != "complete":
                self._append_job_log("complete", "数据更新完成，活动数据已安全发布", "success", emit=False)
        self.jobChanged.emit()
        if operation == "update-preview":
            result = value.get("result")
            self._data_update_preview = dict(result) if isinstance(result, dict) else {}
            self.updatePreviewChanged.emit()
            self.refresh()
            return
        if operation == "content-root-migration":
            raw_report = value.get("result")
            report: dict[str, Any] = dict(raw_report) if isinstance(raw_report, dict) else {}
            previous_service = self.service
            replacement = type(previous_service)(str(report.get("active_root", self.service.paths.root)))
            previous_service.close()
            self.service = replacement
            self.use_cases.service = replacement
            self._onboarding = replacement.onboarding_status()
            self._payload = {
                "key": "settings",
                "title": "数据目录迁移完成",
                "eyebrow": "本地存储",
                "status": "ready",
                "summary": "新目录已经过 generation 校验并立即成为当前工作目录；旧目录保留到后续确认清理。",
                "cards": [{"title": "新目录", "summary": report.get("active_root", ""), "status": "ready"}],
                "path_rows": self._path_rows("settings"),
            }
            self._current_page = "settings"
            self.pathsChanged.emit()
            self.onboardingChanged.emit()
            self.pageChanged.emit()
            return
        if operation == "export-result":
            raw_report = value.get("result")
            report = dict(raw_report) if isinstance(raw_report, dict) else {}
            self._last_export_path = str(Path(str(report.get("result_csv", ""))).resolve())
            self.service.registry.set_setting("last_export_path", self._last_export_path)
            self.pathsChanged.emit()
            runs = self.service.runs(100)
            row = next((item for item in runs if item.get("state") in {"SUCCEEDED", "CACHED"}), None)
            if row is not None:
                self._payload = self.use_cases.results(str(row["id"])).as_dict()
                self._payload["notices"] = list(self._payload.get("notices", [])) + [
                    {"tone": "success", "text": f"已导出到 {report.get('result_csv', '')}"}
                ]
                self._payload["path_rows"] = self._path_rows("results")
                self.pageChanged.emit()
            return
        if operation == "bundled-import":
            from .onboarding import DataSourceChoice

            step = max(2, int(self._onboarding.get("step", 0)))
            self._onboarding = self.service.onboarding_advance(
                step,
                source=DataSourceChoice("bundled", accepted_license=True),
            )
            self.onboardingChanged.emit()
            self.pathsChanged.emit()
        elif operation == "csv-import":
            from .onboarding import DataSourceChoice

            step = max(2, int(self._onboarding.get("step", 0)))
            self._onboarding = self.service.onboarding_advance(
                step,
                source=DataSourceChoice("csv"),
            )
            self.onboardingChanged.emit()
            self.pathsChanged.emit()
        elif operation == "provider-import":
            self.pathsChanged.emit()
        elif operation == "baostock-initialize":
            from .onboarding import DataSourceChoice

            step = max(2, int(self._onboarding.get("step", 0)))
            self._onboarding = self.service.onboarding_advance(step, source=DataSourceChoice("baostock"))
            self.onboardingChanged.emit()
            self.pathsChanged.emit()
        self._current_page = "results" if operation == "training" else "data"
        self.refresh()

    @Slot(object)
    def _apply_job_progress(self, payload: object) -> None:
        value = payload if isinstance(payload, dict) else {}
        operation = str(value.get("operation", self._job_operation))
        if operation == "training":
            stage = str(value.get("stage", "training"))
            message = str(value.get("message") or "正在进行本机训练")
            severity = str(value.get("severity", "info"))
            self._job_stage = stage
            self._job_progress = max(0.0, min(1.0, float(value.get("progress", 0.0))))
            self._append_job_log(stage, message, severity, emit=False)
            stage_labels = {
                "checking": "正在检查训练条件",
                "preparing": "正在准备完整历史",
                "training": "正在训练排序模型",
                "predicting": "正在生成候选排名",
                "analysing": "正在计算组合摘要",
                "publishing": "正在安全发布结果",
                "cached": "正在打开已验证结果",
                "succeeded": "训练已完成",
                "failed": "训练未完成",
                "cancelled": "训练已停止",
            }
            self._payload = {
                "key": "train",
                "title": stage_labels.get(stage, "训练进行中"),
                "eyebrow": "本机 CPU 研究任务",
                "status": "loading" if stage not in {"failed", "cancelled"} else "error",
                "summary": message,
                "metadata": {"stage": stage, "progress": self._job_progress},
                "job_logs": self.jobLogs,
                "notices": [{"tone": "info", "text": "模型与结果通过完整校验后才会进入结果页。"}],
            }
            self.pageChanged.emit()
            self.jobChanged.emit()
            return
        stage_labels = {
            "connecting": "正在连接 BaoStock",
            "listing": "正在读取证券资料",
            "pool": "正在构建历史股票池",
            "market": "正在下载行情与扩展字段",
            "extra": "正在整理估值扩展字段",
            "validation": "正在校验数据契约",
            "publish": "正在发布完整版本",
            "complete": "数据更新完成",
        }
        stage = str(value.get("stage", "market"))
        message = str(value.get("message") or stage_labels.get(stage, "正在处理"))
        self._job_stage = stage
        self._job_progress = max(0.0, min(1.0, float(value.get("progress", 0.0))))
        self._append_job_log(
            stage,
            message,
            "success" if stage == "complete" else str(value.get("severity", "info")),
            emit=False,
        )
        self._payload = {
            "key": "data",
            "title": stage_labels.get(stage, "正在更新数据"),
            "eyebrow": "BaoStock 一键更新",
            "status": "loading",
            "summary": message,
            "metadata": {
                "stage": stage,
                "completed": int(value.get("completed", 0)),
                "total": int(value.get("total", 1)),
                "progress": self._job_progress,
            },
            "job_logs": self.jobLogs,
            "notices": [{"tone": "info", "text": "下载写入暂存区；发布完成前上一活动数据持续可用。"}],
            "path_rows": self._path_rows("data"),
        }
        self.pageChanged.emit()
        self.jobChanged.emit()

    def _start_background(self, operation: str, message: str, work: Any) -> None:
        self._begin_job(operation, "queued", message)
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
                LOG.exception("Background operation %s stopped with an exception", operation)
                self._trainingFinished.emit({"error": exc, "operation": operation})

        self._worker_thread = threading.Thread(target=worker, name=f"quintara-{operation}", daemon=True)
        self._worker_thread.start()

    @Slot(str)
    @Slot(str, bool)
    def exportLatestResult(self, value: str, overwrite: bool = False) -> None:  # noqa: N802
        if self._job_running:
            return
        runs = self.service.runs(100)
        row = next((item for item in runs if item.get("state") in {"SUCCEEDED", "CACHED"}), None)
        if row is None:
            self._show_error(RuntimeError("还没有可导出的结果"))
            return
        destination = self._local_path(value) if value else Path.home() / "Documents" / f"quintara-{row['id']}.csv"
        self._start_background(
            "export-result",
            "正在安全导出结果 CSV",
            lambda: self.service.export_result(
                str(row["id"]),
                destination,
                overwrite=overwrite,
            ),
        )

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

    def _show_error(self, exc: Exception, *, operation: str = "") -> None:
        error = ErrorSummaryDTO.from_exception(exc, data_root=self.service.paths.root)
        training_failure = operation == "training"
        user_message = self._friendly_failure(exc) if training_failure else error.message
        recovery = (
            {"key": "start-training", "label": "重新开始训练", "target": "train", "primary": True}
            if training_failure
            else {"key": "update-data", "label": "重新规划并重试", "target": "data", "primary": True}
        )
        self._payload = {
            "key": "train" if training_failure else self._current_page,
            "title": "训练未完成" if training_failure else error.title,
            "status": "error",
            "summary": user_message,
            "error": {
                "code": error.code,
                "title": "训练未完成" if training_failure else error.title,
                "message": user_message,
                "impact": error.impact,
            },
            "primary_action": recovery,
            "job_logs": self.jobLogs if training_failure else [],
            "metadata": {"stage": self._job_stage, "progress": self._job_progress},
            "technical": {
                "title": "技术详情",
                "copy_text": json.dumps(
                    {
                        "operation": operation or self._job_operation,
                        "stage": self._job_stage,
                        "error": type(exc).__name__,
                        "message": str(exc),
                        "application_log": str(self.service.paths.logs / "quintara-gui.log"),
                    },
                    ensure_ascii=False,
                ),
            },
            "path_rows": self._path_rows(self._current_page),
        }
        self.pageChanged.emit()

    def shutdown(self) -> None:
        self._elapsed_timer.stop()
        if self._worker_thread and self._worker_thread.is_alive():
            if self._job_operation.startswith("baostock"):
                self._data_update_cancel.set()
            else:
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
            "path_rows": self._path_rows("settings"),
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
