"""Build the deterministic developer CSV package shipped beside Quintara."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "packaging" / "developer_data"
ARCHIVE = OUTPUT / "quintara-developer-data-v1.zip"


def _identity(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return {
        "path": path.name,
        "sha256": digest.hexdigest(),
        "bytes": path.stat().st_size,
    }


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reference_model = Path(
        os.environ.get(
            "QUINTARA_REFERENCE_MODEL",
            ROOT.parent / "bigdata" / "app" / "model",
        )
    ).expanduser().resolve()
    source_data = reference_model / "data"
    source_files = {
        "market.csv": source_data / "stock_data.csv",
        "membership.csv": source_data / "hs300_membership_asof.csv",
        "listing.csv": source_data / "listing_basic.csv",
    }
    missing = [str(path) for path in source_files.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("reference model data is incomplete: " + ", ".join(missing))

    with tempfile.TemporaryDirectory(prefix="quintara-developer-data-") as temporary:
        staging = Path(temporary)
        for name, source in source_files.items():
            target = staging / name
            shutil.copyfile(source, target)

        market_dates = pd.read_csv(
            staging / "market.csv", usecols=["日期"], dtype={"日期": str}
        )["日期"].drop_duplicates().sort_values()
        # The released model ignores optional extra features, while the package
        # contract keeps an explicit, empty keyed component for forward readers.
        pd.DataFrame(columns=["股票代码", "日期"]).to_csv(
            staging / "extra_features.csv", index=False, encoding="utf-8"
        )
        pd.DataFrame({"date": market_dates, "is_trading": True}).to_csv(
            staging / "calendar.csv", index=False, encoding="utf-8"
        )

        files = [
            _identity(staging / name)
            for name in (
                "market.csv",
                "membership.csv",
                "listing.csv",
                "extra_features.csv",
                "calendar.csv",
            )
        ]
        manifest = {
            "schema": "quintara-dataset-v1",
            "dataset_id": "quintara-developer-data-v1",
            "version": "1.0.0",
            "coverage": "2015-01-05 至 2026-07-31 · 917 只股票 · PIT 沪深 300 历史区间",
            "platforms": ["any"],
            "label_contract": "competition-open-open-v1",
            "mode": "PIT_BASELINE",
            "pit": {"closed": True, "expected_members": 300},
            "components": {
                "market": "market.csv",
                "extra_features": "extra_features.csv",
                "calendar": "calendar.csv",
                "listing": "listing.csv",
                "membership": "membership.csv",
            },
            "market_contract": {
                "price_adjustment": "post-adjusted-compatible",
                "baostock_adjustflag": "3",
                "units": {
                    "price": "CNY",
                    "volume": "shares",
                    "amount": "CNY",
                    "turnover": "percentage",
                    "change_pct": "percentage",
                },
            },
            "files": files,
            "source": {
                "provider": "Quintara developer data",
                "kind": "versioned local reference dataset",
                "reference_input_manifest_sha256": hashlib.sha256(
                    (source_data / "input_manifest.json").read_bytes()
                ).hexdigest(),
                "reference_result_sha256": hashlib.sha256(
                    (reference_model.parent / "output" / "result.csv").read_bytes()
                ).hexdigest(),
            },
            "license": {
                "id": "quintara-developer-data-v1",
                "redistribution": True,
                "purpose": "local research walkthrough and reproducible result verification",
            },
        }
        (staging / "dataset-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (staging / "reference-result.csv").write_bytes(
            (reference_model.parent / "output" / "result.csv").read_bytes()
        )
        manifest["files"].append(_identity(staging / "reference-result.csv"))
        (staging / "dataset-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary_archive = ARCHIVE.with_suffix(".zip.tmp")
        temporary_archive.unlink(missing_ok=True)
        with zipfile.ZipFile(
            temporary_archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as bundle:
            for path in sorted(staging.iterdir()):
                bundle.write(path, path.name)
        os.replace(temporary_archive, ARCHIVE)

    # Sidecar text remains directly readable next to the archive.
    (OUTPUT / "README.txt").write_text(
        "Quintara 自带开发者数据\n"
        "\n"
        "quintara-developer-data-v1.zip 与应用安装在同一目录树。\n"
        "首次向导可直接校验并导入，用于训练、结果展示以及与参考结果逐行核对。\n"
        "应用会在导入前校验包内 dataset-manifest.json 记录的大小和 SHA-256。\n",
        encoding="utf-8",
    )
    print(f"{ARCHIVE} ({ARCHIVE.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
