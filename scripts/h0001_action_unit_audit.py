"""Build immutable admission evidence from captured public sources, offline."""

from datetime import datetime, timezone
from hashlib import sha256
import inspect
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import yfinance
from yfinance.utils import parse_quotes

from richping.core import canonical, digest
from richping.research_v2.daily_data import DailyVintage
from richping.research_v2.daily_identity import COMPLETENESS, UNIT, FIELDS, NAV_TOLERANCE, unit_comparison

ROOT = Path("research/data_evidence/h0001-action-unit-20261003")
PARENT = Path("research/data_evidence/h0001-daily-pit-20261003")


def immutable(name, body):
    path = ROOT / name
    text = canonical(body)
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise ValueError("Immutable audit collision: " + name)
    else:
        with path.open("x", encoding="utf-8") as f:
            f.write(text)


def main():
    captures = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(ROOT.glob("source-capture-*.json"))]
    sources = {}
    for capture in captures:
        for s in capture["sources"]:
            if s.get("http_status") == 200:
                raw = Path(s["path"]).read_bytes()
                assert sha256(raw).hexdigest() == s["sha256"]
                if s["identity"] == "nasdaq-history" and json.loads(raw)["data"] is None:
                    continue
                sources[s["identity"]] = s
    v = DailyVintage.loads((PARENT / "daily-vintage.json").read_text(encoding="utf-8"))
    captured = max(s["captured_at"] for s in sources.values())

    def ref(name, role=None):
        s = sources[name]
        return {k: s[k] for k in ("identity", "url", "sha256", "path", "captured_at")} | ({"role": role} if role else {})

    old_action = json.loads((PARENT / "corporate-actions.json").read_text(encoding="utf-8"))
    yahoo_path = Path(old_action["yahoo_full_history_capture"])
    yahoo = json.loads(yahoo_path.read_text(encoding="utf-8"))
    events = yahoo["response"]["chart"]["result"][0]["events"]["splits"]
    assert len(events) == 1 and list(events.values())[0]["splitRatio"] == "3:1"
    assert datetime.fromtimestamp(list(events.values())[0]["date"], timezone.utc).date().isoformat() == "2024-03-07"
    yahoo_ref = {"identity": "yahoo-full-history-20010710-20261002", "url": "https://query1.finance.yahoo.com/v8/finance/chart/SOXX",
        "sha256": sha256(yahoo_path.read_bytes()).hexdigest(), "path": yahoo_path.as_posix(),
        "captured_at": yahoo["captured_at"], "role": "CURRENT_PROVIDER_HISTORY"}
    split_text = BeautifulSoup(Path(sources["twelvedata-splits"]["path"]).read_text(encoding="utf-8"), "html.parser")
    split_rows = [[c.get_text(strip=True) for c in r.find_all("td")] for r in split_text.select("table tr") if r.find("td")]
    assert split_rows == [["Mar 07, 2024", "3-for-1 split"]]
    filing = BeautifulSoup(Path(sources["issuer-2026-filing"]["path"]).read_text(encoding="utf-8"), "html.parser").get_text(" ", strip=True)
    assert "3:1" in filing and "November" in filing and "2026" in filing
    action = {
        "schema_version": COMPLETENESS, "evidence_ref": (ROOT / "action-history-audit.json").as_posix(),
        "symbol": "SOXX", "interval_start": v.bars[0].session, "interval_end": v.bars[-1].session,
        "captured_at": captured, "certification_scope": "EX_POST_DATASET_ADMISSION_NOT_STRATEGY_KNOWN_AT",
        "previous_effective_split": {"old_shares": 1, "new_shares": 3, "factor_units": "NEW_SHARES_PER_OLD_SHARES",
            "announcement_date": "2023-12-21", "record_date": "2024-03-04", "payable_after_close_date": "2024-03-06",
            "trading_date": "2024-03-07", "sources": [ref("issuer-2024-tax"), yahoo_ref, ref("twelvedata-splits")]},
        "splits_inside_interval": [],
        "next_effective_split": {"old_shares": 1, "new_shares": 3, "factor_units": "NEW_SHARES_PER_OLD_SHARES",
            "announcement_date": "2026-08-21", "record_date": "2026-11-03", "effectuated_after_close_date": "2026-11-04",
            "trading_date": "2026-11-05", "sources": [ref("issuer-2026-filing"), ref("issuer-product")]},
        "dataset_completeness_sources": [ref("issuer-2024-tax", "OFFICIAL_ISSUER"), ref("issuer-2026-filing", "OFFICIAL_ISSUER"),
            ref("issuer-product", "OFFICIAL_ISSUER"), yahoo_ref, ref("twelvedata-splits", "INDEPENDENT_ACTION_HISTORY")],
        "source_coverage_and_limitations": {
            "issuer": "Official event terms/boundaries; dated filing is not a measured historical API receipt. Release URL currently 404; tax filing is retained.",
            "yahoo": "Actual current full-history query 2001-07-10 through 2026-10-02 lists one effective split; not a revision/availability archive or future-announcement table.",
            "twelvedata": "Independent provider public split table lists only 2024-03-07. No historical receipt/revision guarantee; future event absence is not evidence it is unannounced."},
        "audit_conclusion": "Official boundary terms agree with two effective-event histories. No effective split found inside selected interval; full500 OHLC exchange unit check separately corroborates snapshot.",
        "result": "PASS", "historical_event_known_at_assigned": False,
        "limitations": ["Ex-post research completeness certification, not live/shadow PIT or historical delivery reconstruction.",
            "No general revision guarantee; changing interval, snapshot or evidence requires a new audit/vintage.",
            "Announcement dates retained as metadata only; no factor or absence receipt is backdated."]}

    nasdaq = json.loads(Path(sources["nasdaq-history"]["path"]).read_text(encoding="utf-8"))
    market = {datetime.strptime(r["date"], "%m/%d/%Y").date().isoformat(): {k: float(r[k].replace(",", "")) for k in FIELDS}
              for r in nasdaq["data"]["tradesTable"]["rows"]}
    assert nasdaq["data"]["totalRecords"] == len(market) == 500
    xml = Path(sources["issuer-history"]["path"]).read_text(encoding="utf-8")
    # Issuer's SpreadsheetML has unescaped ampersands in disclaimers. Escape
    # only these for parsing; preserve the original bytes/hash untouched.
    xml = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;#)", "&amp;", xml)
    ns = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
    tree = ET.fromstring(xml)
    historical = next(w for w in tree.findall("ss:Worksheet", ns) if w.attrib["{" + ns["ss"] + "}Name"] == "Historical")
    nav = {}
    for r in historical.findall(".//ss:Row", ns)[1:]:
        cells = [d.text for d in r.findall(".//ss:Data", ns)]
        nav[datetime.strptime(cells[0], "%b %d, %Y").date().isoformat()] = float(cells[1])
    rows = []
    for b in v.bars:
        quote = {k: getattr(b, k) for k in FIELDS}
        comparison = unit_comparison(quote, market[b.session])
        assert comparison["unit_certification_result"] == "PASS"
        assert abs(b.close / nav[b.session] - 1) <= NAV_TOLERANCE
        rows.append({"session": b.session, "yahoo_quote": quote, "market_ohlc": market[b.session],
            "issuer_NAV": nav[b.session], "comparison": comparison,
            "comparison_meaning": "Nasdaq market OHLC direct USD/share match; issuer NAV distinct valuation supplies unit sanity only.",
            "sources": [ref("nasdaq-history"), ref("issuer-history")]})
    raw_daily = json.loads((PARENT / "daily-provider-capture.json").read_text(encoding="utf-8"))
    result = raw_daily["response"]["chart"]["result"][0]
    parsed = parse_quotes(result)
    assert list(parsed["Close"]) == result["indicators"]["quote"][0]["close"]
    assert list(parsed["Adj Close"]) == result["indicators"]["adjclose"][0]["adjclose"]
    unit = {"schema_version": UNIT, "evidence_ref": (ROOT / "ohlc-unit-crosscheck.json").as_posix(),
        "symbol": "SOXX", "interval_start": v.bars[0].session, "interval_end": v.bars[-1].session,
        "captured_at": captured, "raw_capture_hash": v.manifest.unpack()["raw_capture_hash"],
        "source_price_basis": v.manifest.unpack()["raw_price_basis"], "result": "PASS",
        "market_sources": [ref("nasdaq-history"), ref("issuer-history")], "rows": rows,
        "nav_relative_tolerance": NAV_TOLERANCE,
        "max_OHLC_absolute_differences_USD": {k: max(r["comparison"]["absolute_differences_USD"][k] for r in rows) for k in FIELDS},
        "maximum_NAV_close_relative_difference": max(abs(b.close/nav[b.session]-1) for b in v.bars),
        "issuer_market_close_check": {"session": "2026-10-01", "issuer_market_close": 576.33,
            "yahoo_close": next(b.close for b in v.bars if b.session == "2026-10-01"), "tolerance_USD": .02, "source": ref("issuer-product")},
        "quote_vs_adjclose": {"provider_version": yfinance.__version__, "parsing_function": "yfinance.utils.parse_quotes",
            "parsing_source_sha256": sha256(inspect.getsource(parse_quotes).encode()).hexdigest(),
            "quote_path": "indicators.quote[0]", "adjclose_path": "indicators.adjclose[0].adjclose",
            "actual_parser_quote_equal": True, "actual_parser_adjclose_equal": True,
            "differing_Close_AdjClose_rows": sum(a != b for a, b in zip(parsed["Close"], parsed["Adj Close"])),
            "adapter_uses": "quote OHLC directly; no auto_adjust/back_adjust/repair or Adj Close"},
        "limitations": ["Certifies identical share units for this exact split-free500-session snapshot only; not all Yahoo history raw/as-traded.",
            "NAV is not market close and cannot alone certify OHLC; all500 Nasdaq OHLC rows independently matched within USD0.02.",
            "Current source capture is ex-post admission metadata, not historical price delivery or live PIT.",
            "No future split preadjustment detected; only this source vintage/interval is admitted."]}
    immutable("action-history-audit.json", action)
    immutable("ohlc-unit-crosscheck.json", unit)
    print(canonical({"status": "PASS", "sessions": len(rows), "max_differences": unit["max_OHLC_absolute_differences_USD"],
                     "max_NAV_difference": unit["maximum_NAV_close_relative_difference"]}))


if __name__ == "__main__":
    main()
