"""Exercise the three GUI data-source routes against a deterministic BaoStock fixture."""
from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import time
import types
from pathlib import Path
from typing import Any

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QSG_RHI_BACKEND", "software")

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from quintara.application import ProductUseCases
from quintara.qml_backend import QmlBackend
from quintara.qml_gui import qml_root
from quintara.service import QuintaraService

ROOT = Path(__file__).resolve().parents[1]


class Query:
    def __init__(self, fields: str, rows: list[list[str]]) -> None:
        self.fields = fields.split(",")
        self.rows = rows
        self.error_code = "0"
        self.error_msg = ""
        self.index = 0

    def next(self) -> bool:
        value = self.index < len(self.rows)
        self.index += 1
        return value

    def get_row_data(self) -> list[str]:
        return self.rows[self.index - 1]


def provider_fixture() -> types.SimpleNamespace:
    codes = [f"{value:06d}" for value in range(1, 301)]
    csv_codes = [f"{600000 + value:06d}" for value in range(120)]

    def calendar(start_date: str, end_date: str) -> Query:
        values = pd.date_range(start_date, end_date, freq="B")[:2]
        return Query("calendar_date,is_trading_day", [[str(value.date()), "1"] for value in values])

    def membership(date: str = "") -> Query:
        del date
        return Query("code,code_name", [[f"sz.{code}", f"Fixture-{code}"] for code in codes])

    def listing() -> Query:
        return Query(
            "code,code_name,ipoDate,outDate,status",
            [[("sh." if code.startswith("6") else "sz.") + code, f"Fixture-{code}", "2010-01-01", "", "1"] for code in codes + csv_codes],
        )

    def history(code: str, fields: str, **kwargs: str) -> Query:
        values = pd.date_range(kwargs["start_date"], kwargs["end_date"], freq="B")
        if fields == "date,code,close":
            return Query(fields, [[str(value.date()), code, "10.5"] for value in values])
        if fields.startswith("date,code,open"):
            return Query(
                fields,
                [[str(value.date()), code, "10", "11", "9", "10.5", "100", "1000", "1", "5"] for value in values],
            )
        return Query(fields, [[str(value.date()), code, "1", "1", "1", "1"] for value in values])

    return types.SimpleNamespace(
        login=lambda: types.SimpleNamespace(error_code="0", error_msg=""),
        logout=lambda: None,
        query_trade_dates=calendar,
        query_hs300_stocks=membership,
        query_stock_basic=listing,
        query_history_k_data_plus=history,
    )


def wait_for(app: QGuiApplication, predicate: Any, *, timeout: float = 90) -> None:
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    if not predicate():
        raise TimeoutError("GUI journey operation did not reach its expected state")


def journey(app: QGuiApplication, source: str, root: Path) -> dict[str, Any]:
    service = QuintaraService(root)
    service.confirm_consent()
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root()))
    backend = QmlBackend(ProductUseCases(service))
    engine.setInitialProperties({"backend": backend})
    engine.load(QUrl.fromLocalFile(str(qml_root() / "main.qml")))
    if not engine.rootObjects():
        raise RuntimeError("QML window did not load")
    window = engine.rootObjects()[0]
    window.show()
    app.processEvents()
    try:
        backend.advanceOnboarding(2, source, True, source == "bundled", False)
        if source == "bundled":
            backend.importBundledData()
            wait_for(app, lambda: not backend.jobRunning)
        elif source == "csv":
            backend.importCsv(str(ROOT / "fixtures/synthetic_market.csv"))
        else:
            backend.prepareDataUpdate(True)
            wait_for(app, lambda: not backend.jobRunning and bool(backend.dataUpdatePreview))
            backend.confirmDataUpdate()
            wait_for(app, lambda: not backend.jobRunning)

        before = service.data.active_manifest()
        if before is None:
            raise RuntimeError(f"{source} did not create an active generation")
        backend.prepareDataUpdate(False)
        wait_for(app, lambda: not backend.jobRunning and bool(backend.dataUpdatePreview))
        preview = dict(backend.dataUpdatePreview)
        backend.confirmDataUpdate()
        wait_for(app, lambda: not backend.jobRunning)
        after = service.data.active_manifest()
        if after is None or str(after.get("source")) != "baostock":
            raise RuntimeError(f"{source} update did not publish a BaoStock generation: {backend.currentPagePayload}")
        backend.navigate("data")
        paths = backend.pathSummary
        return {
            "source_route": source,
            "initial_generation": before["generation"],
            "updated_generation": after["generation"],
            "derived_from_source": (after.get("metadata") or {}).get("derived_from_source"),
            "target_cutoff": preview.get("target_cutoff"),
            "data_page_action": (backend.currentPagePayload.get("primary_action") or {}).get("label"),
            "paths": paths,
            "passed": all(str(paths[key]) for key in ("content_root", "active_data", "bundled_data")),
        }
    finally:
        backend.shutdown()
        engine.deleteLater()
        app.processEvents()
        service.close()


def main() -> int:
    sys.modules["baostock"] = provider_fixture()
    app = QGuiApplication.instance() or QGuiApplication([])
    with tempfile.TemporaryDirectory(prefix="quintara-three-source-") as temporary:
        base = Path(temporary)
        selected_sources = tuple(filter(None, os.environ.get("QUINTARA_JOURNEY_SOURCES", "bundled,baostock,csv").split(",")))
        routes = [journey(app, source, base / source) for source in selected_sources]
    evidence = {
        "schema_version": 1,
        "platform": platform.platform(),
        "qt_platform": os.environ.get("QT_QPA_PLATFORM"),
        "routes": routes,
        "passed": all(item["passed"] for item in routes),
    }
    destination = ROOT / "dist/baostock-three-source-gui-journey.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
