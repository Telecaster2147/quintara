"""Qt-facing state holders for QML pages and navigation."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from .application import ProductUseCases
from .dto import ErrorSummaryDTO, PageDTO, PageStatus


class NavigationCoordinator(QObject):
    changed = Signal()
    pageChanged = Signal(str)

    def __init__(self, initial: str = "home") -> None:
        super().__init__()
        self._current_page = initial
        self._compact = False

    @Property(str, notify=changed)
    def currentPage(self) -> str:  # noqa: N802 - QML property naming
        return self._current_page

    @Property(bool, notify=changed)
    def compact(self) -> bool:
        return self._compact

    @Slot(str)
    def navigate(self, page: str) -> None:
        if page == self._current_page:
            return
        self._current_page = page
        self.changed.emit()
        self.pageChanged.emit(page)

    @Slot(bool)
    def setCompact(self, value: bool) -> None:  # noqa: N802 - QML slot naming
        value = bool(value)
        if value != self._compact:
            self._compact = value
            self.changed.emit()


class PageViewModel(QObject):
    changed = Signal()

    def __init__(self, key: str, provider: Callable[[], PageDTO], data_root: Any = None) -> None:
        super().__init__()
        self.key = key
        self.provider = provider
        self.data_root = data_root
        self._status = PageStatus.LOADING.value
        self._payload: dict[str, Any] = {"key": key, "status": self._status}

    @Property(str, notify=changed)
    def status(self) -> str:
        return self._status

    @Property(dict, notify=changed)
    def payload(self) -> dict[str, Any]:
        return self._payload

    @Slot()
    def load(self) -> None:
        self._status = PageStatus.LOADING.value
        self.changed.emit()
        try:
            dto = self.provider()
        except Exception as exc:
            error = ErrorSummaryDTO.from_exception(exc, data_root=self.data_root)
            self._status = PageStatus.ERROR.value
            self._payload = {
                "key": self.key,
                "status": self._status,
                "title": "页面暂时不可用",
                "error": {
                    "code": error.code,
                    "title": error.title,
                    "message": error.message,
                    "impact": error.impact,
                },
            }
        else:
            self._status = dto.status.value
            self._payload = dto.as_dict()
        self.changed.emit()


class ApplicationViewModels(QObject):
    """Own stable page objects so QML bindings never depend on domain internals."""

    def __init__(self, use_cases: ProductUseCases) -> None:
        super().__init__()
        root = use_cases.service.paths.root
        self.navigation = NavigationCoordinator()
        self.pages: dict[str, PageViewModel] = {
            key: PageViewModel(key, lambda key=key: use_cases.page(key), root)
            for key in ("home", "data", "universe", "train", "results", "history", "diagnostics")
        }

    def load_all(self) -> None:
        for page in self.pages.values():
            page.load()
