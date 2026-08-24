"""Small real-protocol probe; evidence is informational and separate from release gates."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import baostock as bs


def main() -> int:
    login = bs.login()
    evidence = {"schema_version": 1, "date": date.today().isoformat(), "login_code": login.error_code, "queries": {}}
    try:
        if login.error_code != "0":
            evidence["status"] = "network-or-upstream-failure"
        else:
            listing = bs.query_stock_basic(code="sh.600000")
            hs300 = bs.query_hs300_stocks(date=date.today().isoformat())
            evidence["queries"] = {
                "stock_basic": {"code": listing.error_code, "fields": list(listing.fields)},
                "hs300": {"code": hs300.error_code, "fields": list(hs300.fields)},
            }
            evidence["status"] = "pass" if listing.error_code == hs300.error_code == "0" else "upstream-protocol-change"
    finally:
        bs.logout()
    output = Path("dist/baostock-probe.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
