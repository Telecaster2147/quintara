"""Measure local release budgets and emit machine-readable evidence."""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from quintara.application import ProductUseCases
from quintara.service import QuintaraService

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="quintara-performance-") as data_root:
        service = QuintaraService(data_root)
        started = time.perf_counter()
        service.bootstrap()
        bootstrap_seconds = time.perf_counter() - started
        started = time.perf_counter()
        ProductUseCases(service).home()
        home_seconds = time.perf_counter() - started
        service.close()
    evidence = {
        "schema_version": 1,
        "fixture": "local-empty-bootstrap",
        "budgets": {"bootstrap_seconds": 3.0, "home_dto_seconds": 0.25},
        "measurements": {"bootstrap_seconds": bootstrap_seconds, "home_dto_seconds": home_seconds},
        "passed": bootstrap_seconds <= 3.0 and home_seconds <= 0.25,
        "production_scale_required": ["download", "unpack", "storage", "cpu_training"],
    }
    output = ROOT / "dist/performance-evidence.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
