"""Create or merge native platform evidence records for the candidate gate."""
from __future__ import annotations

import argparse
import json
import platform
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist/native-platform-evidence.json"


def _artifact_hashes() -> dict[str, str]:
    import hashlib

    result: dict[str, str] = {}
    for path in sorted((ROOT / "dist").glob("Quintara*")):
        if path.is_file():
            result[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted((ROOT / "dist").glob("quintara-cli*")):
        if path.is_file():
            result[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record native platform evidence")
    parser.add_argument("--platform", help="platform key, for example ubuntu-22.04")
    parser.add_argument("--status", default="passed", choices=("passed", "failed", "partial"))
    parser.add_argument("--scope", default="native build, install, GUI and CLI acceptance")
    parser.add_argument("--workflow", default=".github/workflows/platform-matrix.yml")
    parser.add_argument("--merge", action="store_true", help="merge dist/native-*.json into the aggregate file")
    args = parser.parse_args(argv)
    if args.merge:
        platforms: dict[str, object] = {}
        for path in sorted((ROOT / "dist").glob("native-*.json")):
            if path.name == OUTPUT.name:
                continue
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(record, dict) and isinstance(record.get("platform"), str):
                platforms[record["platform"]] = record
        evidence = {"schema_version": 1, "merged_at": datetime.now(UTC).isoformat(), "platforms": platforms}
    else:
        if not args.platform:
            parser.error("--platform is required unless --merge is used")
        evidence = {
            "schema_version": 1,
            "platform": args.platform,
            "status": args.status,
            "scope": args.scope,
            "workflow": args.workflow,
            "recorded_at": datetime.now(UTC).isoformat(),
            "host": {"platform": platform.platform(), "machine": platform.machine()},
            "artifacts": _artifact_hashes(),
        }
    output = OUTPUT if args.merge else ROOT / f"dist/native-{args.platform}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
