"""Universe creation and identity helpers."""
from __future__ import annotations

from collections.abc import Iterable
from typing import cast

import pandas as pd

from .core import UniverseMode, content_hash

SUPPORTED_PREFIXES = ("600", "601", "603", "605", "688", "000", "001", "002", "003", "300", "301", "302", "430", "440", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "920")


def normalize_codes(codes: Iterable[str]) -> list[str]:
    values = set()
    for code in codes:
        value = str(code).strip().upper().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
        value = value[:-2] if value.endswith(".0") else value
        if value:
            values.add(value.zfill(6))
    values = sorted(values)
    return values


def is_supported_a_share(code: str) -> bool:
    code = str(code).zfill(6)
    return len(code) == 6 and code.startswith(SUPPORTED_PREFIXES)


def create_definition(name: str, mode: UniverseMode, codes: Iterable[str], *, warning_ack: str | None = None, status_filter: str = "exclude_special") -> dict:
    normalized = normalize_codes(codes)
    unsupported = [code for code in normalized if not is_supported_a_share(code)]
    if unsupported:
        raise ValueError(f"unsupported A-share codes: {', '.join(unsupported[:10])}")
    if mode == UniverseMode.CUSTOM_UNIVERSE and len(normalized) < 100:
        raise ValueError("custom universe requires at least 100 stocks")
    if mode == UniverseMode.NON_PIT_FALLBACK and not warning_ack:
        raise ValueError("NON_PIT_FALLBACK requires explicit warning acknowledgement")
    if status_filter not in {"exclude_special", "include_special_experiment"}:
        raise ValueError("unsupported status filter")
    if status_filter == "include_special_experiment" and not warning_ack:
        raise ValueError("including special-status stocks requires explicit warning acknowledgement")
    definition = {"name": name, "mode": mode.value, "codes": normalized, "status_filter": status_filter, "warning_ack": warning_ack}
    definition["generation"] = content_hash(definition)
    return definition


def static_membership(codes: Iterable[str], dates: Iterable[pd.Timestamp]) -> pd.DataFrame:
    normalized = normalize_codes(codes)
    dates = sorted(cast(pd.Timestamp, pd.Timestamp(value)).normalize() for value in dates)
    if not dates:
        raise ValueError("membership requires dates")
    return pd.DataFrame({"stock_id": normalized, "index_code": "CUSTOM", "start_date": dates[0], "end_date": pd.NaT}).copy()


def membership_for_definition(definition: dict, dates: Iterable[pd.Timestamp]) -> pd.DataFrame:
    """Materialize a route definition without modifying the source generation."""
    mode = UniverseMode(str(definition["mode"]))
    if mode == UniverseMode.PIT_BASELINE:
        raise ValueError("PIT_BASELINE membership must come from the data generation")
    frame = static_membership(definition.get("codes", []), dates)
    frame["index_code"] = mode.value
    return frame
