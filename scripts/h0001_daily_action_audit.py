"""Explicit actual-source smoke; never assigns historical known_at to ex-dates."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from richping.core import canonical, digest
from richping.research_v2.daily_data import daily_request, fetch_daily
from richping.research_v2.real_data import archive_capture


def main():
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)
    capture = fetch_daily(daily_request("SOXX", "2001-07-10", "2026-10-03"))
    path = archive_capture(capture, root)
    split_table = capture["response"]["chart"]["result"][0].get("events", {}).get("splits", {})
    url = "https://data.alpaca.markets/v1/corporate-actions?symbols=SOXX&types=forward_split,reverse_split&start=2024-01-01&end=2026-10-03&limit=1000"
    try:
        # No credentials found in this environment. Do not load arbitrary
        # secret files or print headers; this verifies endpoint access only.
        with urlopen(Request(url), timeout=30) as response:
            status = response.status
            body = response.read().decode()
    except HTTPError as exc:
        status, body = exc.code, exc.read().decode()
    result = {"captured_at": datetime.now(timezone.utc).isoformat(),
              "yahoo_full_history_capture": str(path), "yahoo_capture_hash": digest(capture),
              "yahoo_split_events": split_table,
              "yahoo_known_at_semantics": "ACTUAL_CAPTURE_RECEIPT_ONLY_NOT_BACKDATED",
              "split_free_interval": ["2024-10-04", "2026-10-02"],
              "historical_no_action_known_at": "UNVERIFIED",
              "alpaca": {"url": url, "http_status": status, "body": body,
                         "authenticated_payload_verified": False, "credentials_available": False},
              "official_sources": [
                  "https://www.ishares.com/us/literature/press-release/stock-split-press-release-2023.pdf",
                  "https://www.ishares.com/us/products/239705/ishares-phlx-semiconductor-etf",
                  "https://docs.alpaca.markets/us/reference/corporateactions-1",
                  "https://raw.githubusercontent.com/alpacahq/alpaca-py/master/alpaca/data/models/corporate_actions.py",
                  "https://alpaca.markets/blog/introducing-corporate-actions-api-announcements/"],
              "issuer_cross_check": {"2024_split": {"new": 3, "old": 1, "trading_ex_date": "2024-03-07",
                  "document_declared_date": "2023-12-21", "historical_source_receipt_time": None},
                  "future_notice": {"filed_date_claim": "2026-08-21", "trading_ex_date": "2026-11-05",
                                    "ratio": None, "must_apply_in_current_overlap": False}},
              "PIT_certification": False, "profitability": "NOT_RUN"}
    (root/"corporate-actions.json").write_text(canonical(result), encoding="utf-8")
    print(canonical({"splits": split_table, "alpaca_http_status": status, "artifact": str(root/"corporate-actions.json")}))


if __name__ == "__main__":
    main()
