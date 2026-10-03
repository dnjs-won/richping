"""Immutable RTH Daily captures and explicit action import; no implicit PIT claim.

Yahoo OHLC (even auto_adjust=False) is a current split-normalized snapshot.
Neither an empty event table nor its ex-dates certify historical action knowledge.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from importlib.metadata import version
import json
from pathlib import Path
import re

from ..core import calendar, canonical, digest, sessions, ticker, timestamp
from .contracts import JsonObject, MarketBar, payload
from .sessions import NY, RTH, session_bounds

SCHEMA = "rth_daily_vintage_v1"
BAR_CLOCK = "HISTORICAL_RESEARCH_BAR_END_AVAILABILITY_ASSUMPTION_V1"
YAHOO_BASIS = "YAHOO_CURRENT_SPLIT_NORMALIZED_OHLC_NOT_CERTIFIED_AS_TRADED"


def daily_request(symbol, start, end):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    if start >= end:
        raise ValueError("Daily range must be start-inclusive/end-exclusive")
    return {"symbol": ticker(symbol), "start": start.isoformat(), "end": end.isoformat(),
            "interval": "1d", "includePrePost": False, "events": "div,splits,capitalGains"}


def warmup_request(symbol, end, count=500):
    if type(count) is not int or count < 381:
        raise ValueError("At least 381 completed sessions required")
    days = sessions(calendar().first_session.date().isoformat(), (date.fromisoformat(end)-timedelta(days=1)).isoformat())
    if len(days) < count:
        raise ValueError("Insufficient supported calendar history")
    return daily_request(symbol, days[-count], end)


def fetch_daily(req):
    """Explicit network boundary; preserve arrays before yfinance repairs/dedups."""
    import yfinance as yf
    from yfinance.data import YfData

    def epoch(day):
        return int(datetime.combine(date.fromisoformat(day), time(), NY).timestamp())
    response = YfData().get(
        url="https://query1.finance.yahoo.com/v8/finance/chart/"+req["symbol"],
        params={"period1": epoch(req["start"]), "period2": epoch(req["end"]),
                "interval": "1d", "includePrePost": False, "events": req["events"]}, timeout=30)
    if response.status_code != 200:
        raise ValueError(f"Yahoo Daily HTTP failure: {response.status_code}")
    return {"provider": "yahoo_chart", "adapter_version": "yahoo_chart_rth_daily_v1",
            "provider_version": yf.__version__, "request": req,
            "captured_at": datetime.now(timezone.utc).isoformat(), "response": response.json()}


def validate_actions(body):
    """Provider-independent evidence contract. Import never invents known_at.

    VERIFIED requires a source receipt/availability audit AND completeness audit.
    Source capture alone may be conservative known_at, never an older ex-date.
    Revisions are immutable records sharing event_id with distinct known_at.
    """
    if body.get("schema_version") != "split_evidence_v1":
        raise ValueError("Explicit split evidence schema required")
    for key in ("provider", "source_vintage", "symbol"):
        if not isinstance(body.get(key), str) or not body[key]:
            raise ValueError("Action source identity required")
    if ticker(body["symbol"]) != body["symbol"]:
        raise ValueError("Normalized action symbol required")
    captured = timestamp(body["captured_at"])
    if body.get("status") not in {"VERIFIED", "CROSS_CHECK_ONLY", "FIXTURE"}:
        raise ValueError("Action evidence status required")
    if body["status"] == "VERIFIED" and not body.get("availability_and_completeness_audit_ref"):
        raise ValueError("Actual availability/completeness audit required")
    seen, revisions = set(), set()
    for action in body["events"]:
        if action["symbol"] != body["symbol"] or action["type"] not in {"forward_split", "reverse_split"}:
            raise ValueError("Unsupported/mismatched split action")
        if action["factor_units"] != "NEW_SHARES_PER_OLD_SHARES":
            raise ValueError("Mismatched split units")
        if not action["event_id"] or not action["revision_id"] or not action["source_fields"]:
            raise ValueError("Event/revision/source evidence required")
        effective, known = timestamp(action["effective_at"]), timestamp(action["known_at"])
        if known > captured:
            raise ValueError("Action known_at after capture")
        _validate_receipt(action, body)
        old, new = action["old_shares"], action["new_shares"]
        import math
        if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in (old, new)):
            raise ValueError("Unknown/nonpositive split factor")
        if (action["type"] == "forward_split" and new <= old
                or action["type"] == "reverse_split" and new >= old):
            raise ValueError("Split type/factor direction mismatch")
        key = (action["event_id"], known)
        if key in seen:
            raise ValueError("Action identity collision")
        seen.add(key)
        revision_key = (action["event_id"], action["revision_id"])
        if revision_key in revisions:
            raise ValueError("Action revision identity collision")
        revisions.add(revision_key)
    cover_ids = set()
    for coverage in body["coverage"]:
        if not coverage["evidence_ref"]:
            raise ValueError("No-action coverage evidence required")
        start, end, known = (timestamp(coverage[k]) for k in ("start_at", "through_at", "known_at"))
        if not start <= end <= known <= captured:
            raise ValueError("Coverage cannot assert future action absence")
        _validate_receipt(coverage, body)
        if coverage["evidence_ref"] in cover_ids:
            raise ValueError("Coverage source identity collision")
        cover_ids.add(coverage["evidence_ref"])
    return JsonObject.of(body)


def _validate_receipt(record, body):
    semantics = record["known_at_semantics"]
    if body["status"] == "FIXTURE":
        if semantics != "FIXTURE_SOURCE_CLOCK":
            raise ValueError("Fixtures must be explicitly labelled")
    elif semantics == "ACTUAL_CAPTURE_RECEIPT":
        if timestamp(record["known_at"]) != timestamp(body["captured_at"]):
            raise ValueError("Capture receipt cannot be backdated")
    elif semantics == "AUDITED_HISTORICAL_SOURCE_AVAILABILITY":
        if body["status"] != "VERIFIED" or not record.get("availability_audit_ref"):
            raise ValueError("Historical source timestamp audit required")
    else:
        raise ValueError("Declaration/process/ex dates are not automatic known_at")


@dataclass(frozen=True, slots=True)
class DailyVintage:
    dataset_id: str
    bars: tuple[MarketBar, ...]
    manifest: JsonObject
    actions: JsonObject

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,120}", self.dataset_id):
            raise ValueError("Safe Daily identity required")
        object.__setattr__(self, "bars", tuple(self.bars))
        meta, actions = self.manifest.unpack(), self.actions.unpack()
        validate_actions(actions)
        if meta["schema_version"] != SCHEMA or meta["session_profile"] != RTH:
            raise ValueError("Unsupported Daily contract")
        req = meta["requested_range"]
        if req != daily_request(req["symbol"], req["start"], req["end"]):
            raise ValueError("Wrong Daily request identity")
        if actions["symbol"] != req["symbol"]:
            raise ValueError("Action/Daily symbol mismatch")
        if meta["raw_unit_status"] not in {"UNVERIFIED", "VERIFIED_AS_TRADED", "FIXTURE", "VERIFIED_IDENTITY_INTERVAL"}:
            raise ValueError("Explicit raw share-unit status required")
        if meta["raw_unit_status"] == "VERIFIED_AS_TRADED":
            if meta["raw_price_basis"] != "RAW_UNADJUSTED_RTH_OHLC" or not meta.get("unit_audit_ref"):
                raise ValueError("As-traded raw OHLC unit audit required")
            if timestamp(meta["unit_known_at"]) > timestamp(meta["captured_at"]):
                raise ValueError("Raw unit evidence after capture")
        if (meta["raw_unit_status"] == "FIXTURE") != (actions["status"] == "FIXTURE"):
            raise ValueError("Do not mix fixture/real evidence")
        captured = timestamp(meta["captured_at"])
        if len(meta["raw_capture_hash"]) != 64 or timestamp(actions["captured_at"]) > captured:
            raise ValueError("Invalid capture provenance")
        expected = sessions(req["start"], (date.fromisoformat(req["end"])-timedelta(days=1)).isoformat())
        seen, prior = set(), None
        for bar in self.bars:
            if (bar.dataset_id != self.dataset_id or bar.symbol != req["symbol"]
                    or bar.timeframe != "Daily" or bar.session not in expected
                    or bar.corporate_action != "UNKNOWN"
                    or (bar.start_at, bar.end_at) != session_bounds(bar.session, RTH)):
                raise ValueError("Wrong timezone/session/partial Daily candle")
            if bar.session in seen:
                raise ValueError("Duplicate Daily session")
            if prior is not None and bar.session <= prior:
                raise ValueError("Daily ordering reversal")
            seen.add(bar.session)
            prior = bar.session
            provenance = bar.provenance.unpack()
            if any(provenance.get(k) != meta[k] for k in
                   ("raw_price_basis", "raw_capture_hash", "known_at_policy", "session_profile")):
                raise ValueError("Mixed Daily source vintage")
            if bar.source != meta["provider"] or bar.known_at > captured:
                raise ValueError("Invalid Daily capture/receipt")
            if meta["known_at_policy"] == BAR_CLOCK and bar.known_at != bar.end_at:
                raise ValueError("Assumed bar-end policy mismatch")
            if meta["known_at_policy"] not in {BAR_CLOCK, "ACTUAL_BAR_RECEIPT_V1", "FIXTURE_BAR_CLOCK"}:
                raise ValueError("Unknown price bar availability policy")
        missing = sorted(set(expected)-seen)
        if not self.bars or meta["missing_sessions"] != missing:
            raise ValueError("Empty/incorrect Daily coverage")
        if meta["raw_unit_status"] == "VERIFIED_IDENTITY_INTERVAL":
            from .daily_identity import validate_identity
            validate_identity(meta, actions, self.bars)
        elif "identity_interval_certification" in meta:
            raise ValueError("Identity certification/status mismatch")

    @property
    def content_hash(self):
        return digest(payload(self))

    def dumps(self):
        return canonical({"content_hash": self.content_hash, "vintage": payload(self)})

    @classmethod
    def loads(cls, text):
        body = json.loads(text)
        v = body["vintage"]
        bars = tuple(MarketBar(**{**b, "provenance": JsonObject.of(b["provenance"])}) for b in v["bars"])
        value = cls(v["dataset_id"], bars, JsonObject.of(v["manifest"]), JsonObject.of(v["actions"]))
        if value.content_hash != body["content_hash"]:
            raise ValueError("Daily hash mismatch")
        return value


def normalize_daily(capture, dataset_id):
    if capture["provider"] != "yahoo_chart" or capture["adapter_version"] != "yahoo_chart_rth_daily_v1":
        raise ValueError("Unsupported Daily provider/adapter")
    req = capture["request"]
    if req != daily_request(req["symbol"], req["start"], req["end"]):
        raise ValueError("Wrong Daily request")
    if not capture["provider_version"]:
        raise ValueError("Provider version required")
    chart = capture["response"]["chart"]
    if chart.get("error") or not isinstance(chart.get("result"), list) or len(chart["result"]) != 1:
        raise ValueError("Provider partial/error response")
    result = chart["result"][0]
    metadata = result["meta"]
    if (metadata.get("symbol") != req["symbol"] or metadata.get("dataGranularity") != "1d"
            or metadata.get("exchangeTimezoneName") != "America/New_York"
            or metadata.get("currency") != "USD" or metadata.get("instrumentType") not in {"ETF", "EQUITY"}):
        raise ValueError("Wrong Daily symbol/timezone/granularity/currency")
    times, quotes = result["timestamp"], result["indicators"]["quote"]
    if len(quotes) != 1 or not times or any(len(quotes[0].get(k, [])) != len(times)
                                         for k in ("open", "high", "low", "close", "volume")):
        raise ValueError("Partial Daily OHLCV arrays")
    captured = timestamp(capture["captured_at"])
    common = {"session_profile": RTH, "raw_price_basis": YAHOO_BASIS,
              "raw_capture_hash": digest(capture), "known_at_policy": BAR_CLOCK}
    bars = []
    for i, epoch in enumerate(times):
        if type(epoch) is not int:
            raise ValueError("Invalid Daily timestamp")
        provider_at = datetime.fromtimestamp(epoch, timezone.utc)
        day = provider_at.astimezone(NY).date().isoformat()
        opened, closed = session_bounds(day, RTH)
        if provider_at != opened or closed > captured:
            raise ValueError("Partial/wrong-timezone Daily candle")
        bars.append(MarketBar(dataset_id, req["symbol"], "Daily", opened, closed, day,
            *(quotes[0][k][i] for k in ("open", "high", "low", "close", "volume")),
            closed, "yahoo_chart", JsonObject.of({**common, "provider_row": i}), "UNKNOWN"))
    events = result.get("events", {})
    split_events = []
    for key, event in events.get("splits", {}).items():
        new, old = event["numerator"], event["denominator"]
        split_events.append({"event_id": "yahoo:"+req["symbol"]+":"+key,
            "revision_id": digest(event), "symbol": req["symbol"],
            "type": "forward_split" if new > old else "reverse_split",
            "effective_at": datetime.fromtimestamp(event["date"], timezone.utc).isoformat(),
            "known_at": captured.isoformat(), "known_at_semantics": "ACTUAL_CAPTURE_RECEIPT",
            "old_shares": old, "new_shares": new, "factor_units": "NEW_SHARES_PER_OLD_SHARES",
            "source_fields": event})
    actions = validate_actions({"schema_version": "split_evidence_v1", "provider": "yahoo_chart",
        "symbol": req["symbol"], "source_vintage": digest(capture), "captured_at": captured.isoformat(),
        "status": "CROSS_CHECK_ONLY", "events": split_events, "coverage": [],
        "limitations": ["Current table is not an historical PIT or completeness feed; no-action coverage is unverified.",
                        "Event date is effective/ex date, not actual source availability; known_at is capture receipt."]})
    expected = sessions(req["start"], (date.fromisoformat(req["end"])-timedelta(days=1)).isoformat())
    manifest = {"schema_version": SCHEMA, **common, "requested_range": req,
                "provider": capture["provider"], "adapter_version": capture["adapter_version"],
                "provider_version": capture["provider_version"], "captured_at": captured.isoformat(),
                "raw_unit_status": "UNVERIFIED", "calendar": "XNYS",
                "calendar_version": version("exchange-calendars"),
                "missing_sessions": sorted(set(expected)-{b.session for b in bars}),
                "provider_events": events,
                "limitations": ["Not live/shadow PIT or measured provider latency.",
                                 "Yahoo snapshot may already reflect splits; auto_adjust=False does not undo them."]}
    return DailyVintage(dataset_id, tuple(bars), JsonObject.of(manifest), actions)


def save_daily(vintage, root):
    path = Path(root)/"daily"/(vintage.dataset_id+".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = vintage.dumps()
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise ValueError("Immutable Daily source identity collision")
    else:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(text)
    return path


def load_daily(dataset_id, root):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,120}", dataset_id):
        raise ValueError("Safe Daily identity required")
    return DailyVintage.loads((Path(root)/"daily"/(dataset_id+".json")).read_text(encoding="utf-8"))


def daily_coverage(vintage):
    m = vintage.manifest.unpack()
    return {"dataset_id": vintage.dataset_id, "content_hash": vintage.content_hash,
            "provider": m["provider"], "requested_range": m["requested_range"],
            "actual_range": [vintage.bars[0].session, vintage.bars[-1].session],
            "sessions": len(vintage.bars), "missing_sessions": m["missing_sessions"],
            "expected_sessions": len(vintage.bars)+len(m["missing_sessions"]),
            "raw_price_basis": m["raw_price_basis"], "raw_unit_status": m["raw_unit_status"],
            "known_at_policy": m["known_at_policy"], "captured_at": m["captured_at"],
            "raw_capture_hash": m["raw_capture_hash"], "session_profile": RTH,
            "action_evidence_status": vintage.actions.unpack()["status"],
            "admission_capability": m.get("identity_interval_certification", {}).get("version"),
            "admission_scope": m.get("identity_interval_certification", {}).get("scope"),
            "eligible_PIT_certification": False if m["raw_unit_status"] == "UNVERIFIED" else None}
