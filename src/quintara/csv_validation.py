"""CSV trainability validator; source files remain immutable."""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

import pandas as pd

from .core import Finding, Severity

CANONICAL_FIELDS = {
    "stock_id": ("股票代码", "stock_id", "code", "代码"),
    "date": ("日期", "date", "trade_date", "交易日期"),
    "open": ("开盘", "open"),
    "close": ("收盘", "close"),
    "high": ("最高", "high"),
    "low": ("最低", "low"),
    "volume": ("成交量", "volume"),
    "amount": ("成交额", "amount"),
    "amplitude": ("振幅", "amplitude"),
    "change_amount": ("涨跌额", "change_amount"),
    "turnover": ("换手率", "turnover"),
    "change_pct": ("涨跌幅", "change_pct"),
}

REQUIRED_UNITS = {
    "open": "price",
    "close": "price",
    "high": "price",
    "low": "price",
    "volume": "volume",
    "amount": "amount",
    "turnover": "percentage",
    "change_pct": "percentage",
}


def detect_mapping(columns: list[str]) -> dict[str, str]:
    return {field: next((column for column in aliases if column in columns), "") for field, aliases in CANONICAL_FIELDS.items()}


def validate_csv(path: str | Path, mapping: dict[str, str] | None = None, *, units: dict[str, str] | None = None, sample_limit: int = 100) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        return {"status": "FAIL", "findings": [Finding("CSV-FILE", Severity.FAIL, f"file not found: {source}").as_dict()]}
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    findings: list[Finding] = []
    try:
        sample = source.read_text(encoding="utf-8-sig", errors="strict")[:8192]
        dialect = csv.Sniffer().sniff(sample) if sample.strip() else csv.excel
        separator = dialect.delimiter
    except (UnicodeError, csv.Error):
        separator = ","
        findings.append(Finding("CSV-ENCODING", Severity.FAIL, "file is not a readable UTF-8 CSV"))
    try:
        raw = pd.read_csv(source, sep=separator, dtype=str)
    except Exception as exc:
        findings.append(Finding("CSV-PARSE", Severity.FAIL, f"CSV parsing failed: {exc}"))
        return {"status": "FAIL", "source": str(source), "sha256": digest, "findings": [f.as_dict() for f in findings]}
    mapping = mapping or detect_mapping(list(raw.columns))
    missing = [key for key, column in mapping.items() if not column]
    if missing:
        findings.append(Finding("CSV-MAPPING", Severity.FAIL, f"missing mapped fields: {', '.join(missing)}", field=", ".join(missing)))
        return {"status": "FAIL", "source": str(source), "sha256": digest, "mapping": mapping, "separator": separator, "rows": len(raw), "findings": [f.as_dict() for f in findings]}
    frame = raw.rename(columns={value: key for key, value in mapping.items()}).copy()
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    bad_codes = ~frame["stock_id"].str.fullmatch(r"\d{6}")
    if bad_codes.any():
        findings.append(Finding("CSV-CODE", Severity.FAIL, f"{int(bad_codes.sum())} stock IDs are not six digits", field="stock_id"))
    dates = pd.to_datetime(frame["date"], errors="coerce")
    if dates.isna().any():
        findings.append(Finding("CSV-DATE", Severity.FAIL, f"{int(dates.isna().sum())} dates are invalid", field="date"))
    duplicates = frame.duplicated(["stock_id", "date"])
    if duplicates.any():
        findings.append(Finding("CSV-DUPLICATE", Severity.FAIL, f"{int(duplicates.sum())} duplicate stock/date keys"))
    numeric = ["open", "close", "high", "low", "volume", "amount", "amplitude", "change_amount", "turnover", "change_pct"]
    for field in numeric:
        values = pd.to_numeric(frame[field], errors="coerce")
        if values.isna().any():
            findings.append(Finding("CSV-NUMERIC", Severity.FAIL, f"{int(values.isna().sum())} invalid values in {field}", field=field))
        if field in {"open", "close", "high", "low"} and (values.dropna() <= 0).any():
            findings.append(Finding("CSV-OHLC", Severity.FAIL, f"non-positive values in {field}", field=field))
    history_counts = frame.groupby("stock_id")["date"].nunique()
    if (history_counts < 6).any():
        findings.append(Finding("CSV-HISTORY", Severity.FAIL, f"{int((history_counts < 6).sum())} stocks have fewer than six sessions", field="date"))
    if not frame.sort_values(["stock_id", "date"]).index.equals(frame.index):
        findings.append(Finding("CSV-ORDER", Severity.WARNING, "rows are not in canonical stock/date order; import will sort a derived generation"))
    open_, close, high, low = (pd.to_numeric(frame[x], errors="coerce") for x in ("open", "close", "high", "low"))
    bad_ranges = (high < low) | (high < open_) | (high < close) | (low > open_) | (low > close)
    if bad_ranges.fillna(False).any():
        findings.append(Finding("CSV-RANGE", Severity.FAIL, f"{int(bad_ranges.fillna(False).sum())} OHLC ranges are inconsistent"))
    # A visible unit warning is preferable to guessing; users confirm units in the UI/CLI mapping step.
    missing_units = [field for field, unit in REQUIRED_UNITS.items() if not units or units.get(field) != unit]
    if missing_units:
        findings.append(Finding("CSV-UNITS", Severity.WARNING, f"confirm units for: {', '.join(missing_units)}", field=", ".join(missing_units)))
    findings = [
        Finding(f.code, f.severity, f.message, f.field, f.row, f.key, f.docs or "docs/ERROR_CATALOG.md")
        for f in findings
    ]
    status = "FAIL" if any(f.severity == Severity.FAIL for f in findings) else "WARNING" if findings else "PASS"
    issues = [f.as_dict() for f in findings]
    return {"status": status, "source": str(source), "sha256": digest, "mapping": mapping, "separator": separator, "units": units or {}, "rows": len(frame), "stocks": int(frame["stock_id"].nunique()), "date_min": str(dates.min().date()) if dates.notna().any() else None, "date_max": str(dates.max().date()) if dates.notna().any() else None, "findings": issues, "issue_sample": issues[:sample_limit]}


def export_issue_sample(
    path: str | Path,
    output: str | Path,
    report: dict[str, Any] | None = None,
    *,
    mapping: dict[str, str] | None = None,
    units: dict[str, str] | None = None,
    sample_limit: int = 100,
) -> Path:
    """Write a bounded, local-only issue sample without copying the source path."""
    source = Path(path).expanduser().resolve()
    report = report or validate_csv(source, mapping, units=units, sample_limit=sample_limit)
    separator = str(report.get("separator", ","))
    raw = pd.read_csv(source, sep=separator, dtype=str)
    resolved = mapping or report.get("mapping") or detect_mapping(list(raw.columns))
    frame = raw.rename(columns={value: key for key, value in resolved.items()}).copy()
    for field in ("stock_id", "date", "open", "close", "high", "low", "volume", "amount", "turnover", "change_pct"):
        if field not in frame:
            frame[field] = ""
    frame["source_row"] = frame.index + 2
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    dates = pd.to_datetime(frame["date"], errors="coerce")
    numeric = {field: pd.to_numeric(frame[field], errors="coerce") for field in ("open", "close", "high", "low", "volume", "amount", "turnover", "change_pct")}
    masks: dict[str, pd.Series] = {
        "CSV-CODE": ~frame["stock_id"].str.fullmatch(r"\d{6}"),
        "CSV-DATE": dates.isna(),
        "CSV-DUPLICATE": frame.duplicated(["stock_id", "date"], keep=False),
        "CSV-OHLC": sum((numeric[field] <= 0 for field in ("open", "close", "high", "low")), start=pd.Series(False, index=frame.index)).astype(bool),
        "CSV-RANGE": (numeric["high"] < numeric["low"]) | (numeric["high"] < numeric["open"]) | (numeric["high"] < numeric["close"]) | (numeric["low"] > numeric["open"]) | (numeric["low"] > numeric["close"]),
    }
    rows: list[pd.DataFrame] = []
    for code, mask in masks.items():
        selected = frame.loc[mask].head(sample_limit).copy()
        if selected.empty:
            continue
        selected.insert(0, "issue_code", code)
        rows.append(selected[["issue_code", "source_row", "stock_id", "date", "open", "close", "high", "low", "volume", "amount", "turnover", "change_pct"]])
    columns = ("issue_code", "source_row", "stock_id", "date", "open", "close", "high", "low", "volume", "amount", "turnover", "change_pct")
    result = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=pd.Index(columns))
    destination = Path(output).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(destination, index=False, encoding="utf-8")
    return destination


def csv_to_market(path: str | Path, mapping: dict[str, str] | None = None, units: dict[str, str] | None = None) -> pd.DataFrame:
    source = Path(path)
    report = validate_csv(source, mapping, units=units)
    if report["status"] == "FAIL":
        raise ValueError("CSV validation failed: " + "; ".join(x["message"] for x in report["findings"]))
    raw = pd.read_csv(source, sep=report.get("separator", ","), dtype=str)
    mapping = mapping or report["mapping"]
    frame = raw.rename(columns={value: key for key, value in mapping.items()})
    result = frame.rename(columns={"stock_id": "股票代码", "date": "日期", "open": "开盘", "close": "收盘", "high": "最高", "low": "最低", "volume": "成交量", "amount": "成交额", "amplitude": "振幅", "change_amount": "涨跌额", "turnover": "换手率", "change_pct": "涨跌幅"})
    for column in ("开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌额", "换手率", "涨跌幅"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["股票代码"] = result["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    result["日期"] = pd.to_datetime(result["日期"]).dt.normalize()
    return result
