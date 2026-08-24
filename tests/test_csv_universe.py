from __future__ import annotations

import pandas as pd
from hypothesis import given
from hypothesis import strategies as st

from quintara.core import UniverseMode
from quintara.csv_validation import export_issue_sample, validate_csv
from quintara.universe import create_definition, normalize_codes


@given(st.lists(st.sampled_from(["600000", "600001", "000001", "300001", "600000.SH"]), min_size=0, max_size=20))
def test_code_normalization_is_idempotent(codes):
    normalized = normalize_codes(codes)
    assert normalize_codes(normalized) == normalized


def test_csv_validator_reports_warning_without_mutating_source(tmp_path):
    path = tmp_path / "market.csv"
    pd.DataFrame(
        {
            "stock_id": ["600000"] * 6,
            "date": [f"2024-01-0{index}" for index in range(1, 7)],
            "open": [10] * 6,
            "close": [11] * 6,
            "high": [11] * 6,
            "low": [10] * 6,
            "volume": [100] * 6,
            "amount": [1000] * 6,
            "amplitude": [1] * 6,
            "change_amount": [1] * 6,
            "turnover": [1] * 6,
            "change_pct": [10] * 6,
        }
    ).to_csv(path, index=False)
    original = path.read_bytes()
    report = validate_csv(path)
    assert report["status"] == "WARNING"
    assert report["rows"] == 6
    assert path.read_bytes() == original


def test_custom_universe_requires_explicit_size_and_fallback_ack():
    codes = [f"600{index:03d}" for index in range(100)]
    definition = create_definition("custom", UniverseMode.CUSTOM_UNIVERSE, codes)
    assert definition["generation"]
    try:
        create_definition("fallback", UniverseMode.NON_PIT_FALLBACK, codes)
    except ValueError as exc:
        assert "acknowledgement" in str(exc)
    else:
        raise AssertionError("fallback warning must be explicit")
    assert normalize_codes(["600000.SH", "600000"]) == ["600000"]


def test_semicolon_csv_is_parsed_with_declared_units(tmp_path):
    path = tmp_path / "semicolon.csv"
    frame = pd.DataFrame(
        {
            "stock_id": ["600000"] * 6,
            "date": pd.date_range("2024-01-01", periods=6).astype(str),
            "open": [10] * 6,
            "close": [11] * 6,
            "high": [11] * 6,
            "low": [10] * 6,
            "volume": [100] * 6,
            "amount": [1000] * 6,
            "amplitude": [1] * 6,
            "change_amount": [1] * 6,
            "turnover": [1] * 6,
            "change_pct": [10] * 6,
        }
    )
    frame.to_csv(path, index=False, sep=";")
    units = {"open": "price", "close": "price", "high": "price", "low": "price", "volume": "volume", "amount": "amount", "turnover": "percentage", "change_pct": "percentage"}
    report = validate_csv(path, units=units)
    assert report["status"] in {"PASS", "WARNING"}
    assert report["separator"] == ";"


def test_csv_validator_rejects_nonfinite_train_inputs(tmp_path):
    path = tmp_path / "nonfinite.csv"
    frame = pd.DataFrame(
        {
            "stock_id": ["600000"] * 6,
            "date": pd.date_range("2024-01-01", periods=6).astype(str),
            "open": [10] * 6,
            "close": [11] * 6,
            "high": [11] * 6,
            "low": [10] * 6,
            "volume": [100, 100, "bad", 100, 100, 100],
            "amount": [1000] * 6,
            "amplitude": [1] * 6,
            "change_amount": [1] * 6,
            "turnover": [1] * 6,
            "change_pct": [10] * 6,
        }
    )
    frame.to_csv(path, index=False)
    report = validate_csv(path)
    assert report["status"] == "FAIL"
    assert any(item["code"] == "CSV-NUMERIC" for item in report["findings"])


def test_issue_sample_is_bounded_and_path_free(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame(
        {
            "stock_id": ["bad", "600000"],
            "date": ["2024-01-01", "not-a-date"],
            "open": [10, 10],
            "close": [11, 11],
            "high": [11, 11],
            "low": [10, 10],
            "volume": [100, 100],
            "amount": [1000, 1000],
            "amplitude": [1, 1],
            "change_amount": [1, 1],
            "turnover": [1, 1],
            "change_pct": [10, 10],
        }
    ).to_csv(path, index=False)
    report = validate_csv(path)
    output = export_issue_sample(path, tmp_path / "issues.csv", report)
    sample = pd.read_csv(output)
    assert "issue_code" in sample
    assert str(path) not in output.read_text(encoding="utf-8")
    assert len(sample) <= 200
