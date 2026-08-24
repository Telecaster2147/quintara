"""Exercise the catalog pointer rollback promised by the v2 release plan."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd

from quintara.core import AppPaths, file_hash
from quintara.data_lifecycle import DataManager
from quintara.platform import atomic_json
from quintara.registry import Registry

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist/rollback-drill.json"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="quintara-rollback-drill-") as temporary:
        root = Path(temporary)
        registry = Registry(AppPaths.discover(root))
        manager = DataManager(registry.paths, registry)
        market = pd.read_csv(ROOT / "fixtures/synthetic_market.csv")
        membership = pd.read_csv(ROOT / "fixtures/synthetic_membership.csv")
        listing = pd.read_csv(ROOT / "fixtures/synthetic_listing.csv")
        first = manager.publish(market, membership, listing, source="rollback-before")
        first_pointer = json.loads(manager.paths.active_data.read_text(encoding="utf-8"))
        second = manager.publish(market.assign(收盘=market["收盘"] * 1.001), membership, listing, source="rollback-after")
        active_before = manager.active_manifest()["generation"]
        atomic_json(manager.paths.active_data, first_pointer)
        active_after = manager.active_manifest()["generation"]
        evidence = {
            "schema_version": 1,
            "previous_generation": first["generation"],
            "new_generation": second["generation"],
            "active_before_rollback": active_before,
            "active_after_rollback": active_after,
            "pointer_sha256": file_hash(manager.paths.active_data),
            "passed": (
                first["generation"] != second["generation"]
                and active_before == second["generation"]
                and active_after == first["generation"]
            ),
        }
        registry.close()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
