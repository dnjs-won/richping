"""One Yahoo chart adapter, immutable capture vintages, and offline diagnostics.

Historical snapshots are NOT historical point-in-time observations. Bar-end
availability is a research assumption; actual receipt time remains captured_at.
No fill, repair, adjustment, strategy, or provider fallback is performed here.
"""

from collections import Counter
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from ..core import canonical, digest, sessions, ticker, timestamp
from .contracts import CONTRACT_VERSION, JsonObject, MarketBar
from .sessions import EXTENDED, NY, extended_bar_metadata, session_bounds, session_profile

PROVIDER = "yahoo_chart"
ADAPTER = "yahoo_chart_15m_v1"
AVAILABILITY = "historical_snapshot_bar_end_assumed_v1"
PRICE_BASIS = "yahoo_chart_snapshot_ohlc_no_local_adjustment"
ACTION_BASIS = "provider_snapshot_split_basis_not_pit_dividends_not_reinvested"
LIMITATIONS = (
    "15m historical lookback is limited to the most recent 60 calendar days; chunking cannot recover older history.",
    "known_at=end_at is an assumed research clock, NOT historical publication/receipt time or live/shadow PIT evidence.",
    "Yahoo snapshot prices may include later split restatements; no PIT action transform or dividend normalization is applied.",
    "Provider zero volume is retained; especially in extended hours it does NOT establish zero trading activity.",
    "Absent slots are UNKNOWN/UNAVAILABLE: no-trade omission cannot be distinguished from collection/provider failure.",
    "Nonstandard/early-close sessions are unsupported by extended v1; no holiday skipping or filling.",
    "A complete intraday grid does not establish chart parity, price accuracy, Daily warmup, or strategy efficacy.",
    "Yahoo has no guaranteed rate limit/SLA or stable chart API; yfinance internal transport version is recorded.",
)


def request(symbol, start, end):
    symbol = ticker(symbol)
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    if start >= end:
        raise ValueError("Date range must be start-inclusive/end-exclusive")
    return {"symbol": symbol, "start": start.isoformat(), "end": end.isoformat(),
            "interval": "15m", "includePrePost": True,
            "events": "div,splits,capitalGains"}


def _midnight(day):
    return datetime.combine(date.fromisoformat(day), time(), NY)


def fetch_capture(req):
    """Only network boundary. All callers must explicitly request sync/update."""
    import yfinance as yf
    from yfinance.data import YfData

    params = {"period1": int(_midnight(req["start"]).timestamp()),
              "period2": int(_midnight(req["end"]).timestamp()),
              "interval": "15m", "includePrePost": True,
              "events": "div,splits,capitalGains"}
    # Use the chart response before PriceHistory drops duplicate/null rows,
    # normalizes volume, or repairs/resamples. No automatic retries/fallback.
    response = YfData().get(
        url="https://query1.finance.yahoo.com/v8/finance/chart/" + req["symbol"],
        params=params, timeout=30)
    if response.status_code != 200:
        raise ValueError(f"Provider HTTP failure: {response.status_code}")
    return {"provider": PROVIDER, "adapter_version": ADAPTER,
            "provider_version": yf.__version__, "request": req,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "response": response.json()}


def expected_slots(req):
    slots, unsupported = [], []
    last = (date.fromisoformat(req["end"]) - timedelta(days=1)).isoformat()
    for day in sessions(req["start"], last):
        try:
            opened, closed = session_bounds(day, EXTENDED)
        except ValueError as exc:
            unsupported.append({"session": day, "status": "UNSUPPORTED",
                                "reason": str(exc), "observed_bars": 0})
            continue
        while opened < closed:
            slots.append(opened)
            opened += timedelta(minutes=15)
    return tuple(slots), unsupported


def normalize_capture(capture, dataset_id):
    """Strict original arrays; no sorting, deduplication or null-to-zero repair."""
    from .market_data import MarketDataset

    if capture["provider"] != PROVIDER or capture["adapter_version"] != ADAPTER:
        raise ValueError("Unsupported capture provenance")
    if not isinstance(capture["provider_version"], str) or not capture["provider_version"]:
        raise ValueError("Provider library version required")
    req = capture["request"]
    if req != request(req["symbol"], req["start"], req["end"]):
        raise ValueError("Unexpected request/timeframe/session")
    captured = timestamp(capture["captured_at"])
    expected, unsupported = expected_slots(req)
    if not expected or expected[-1] + timedelta(minutes=15) > captured:
        raise ValueError("Only completed historical date ranges supported")
    chart = capture["response"].get("chart", {})
    results = chart.get("result")
    if chart.get("error") or not isinstance(results, list) or len(results) != 1:
        raise ValueError("Provider failure/partial result")
    result = results[0]
    meta = result.get("meta", {})
    if (meta.get("symbol") != req["symbol"] or meta.get("dataGranularity") != "15m"
            or meta.get("exchangeTimezoneName") != "America/New_York"
            or meta.get("currency") != "USD"
            or meta.get("instrumentType") not in {"ETF", "EQUITY"}):
        raise ValueError("Unexpected provider symbol/timeframe/timezone/currency/instrument")
    times = result.get("timestamp")
    quotes = result.get("indicators", {}).get("quote")
    if not isinstance(times, list) or not times or not isinstance(quotes, list) or len(quotes) != 1:
        raise ValueError("Provider empty/partial quote response")
    quote = quotes[0]
    if any(not isinstance(quote.get(k), list) or len(quote[k]) != len(times)
           for k in ("open", "high", "low", "close", "volume")):
        raise ValueError("Provider partial OHLCV arrays")
    raw_hash = digest(capture)
    common = {"quality": "REAL_HISTORICAL_RESEARCH", "provider": PROVIDER,
              "adapter_version": ADAPTER, "provider_version": capture["provider_version"],
              "captured_at": captured.isoformat(), "timezone": "America/New_York",
              "price_basis": PRICE_BASIS, "corporate_actions": ACTION_BASIS,
              "known_at_policy": AVAILABILITY, "raw_capture_hash": raw_hash}
    events = result.get("events", {})
    if not isinstance(events, dict):
        raise ValueError("Malformed corporate action response")
    bars, seen, prior = [], set(), None
    begin, end = timestamp(_midnight(req["start"])), timestamp(_midnight(req["end"]))
    for i, epoch in enumerate(times):
        if type(epoch) is not int:
            raise ValueError("Invalid provider epoch timestamp")
        start = datetime.fromtimestamp(epoch, timezone.utc)
        finish = start + timedelta(minutes=15)
        if start in seen:
            raise ValueError("Duplicate provider bar")
        if prior is not None and start < prior:
            raise ValueError("Provider timestamp ordering reversal")
        seen.add(start)
        prior = start
        if not begin <= start < finish <= end:
            raise ValueError("Provider bar outside requested range")
        bar = MarketBar(dataset_id, req["symbol"], "15m", start, finish,
                        start.astimezone(NY).date().isoformat(),
                        *(quote[k][i] for k in ("open", "high", "low", "close", "volume")),
                        finish, PROVIDER,
                        JsonObject.of({**common, "provider_row": i,
                                       **extended_bar_metadata(start, finish)}), "UNKNOWN")
        # MarketDataset validates the exact extended boundaries/grid below.
        bars.append(bar)
    manifest = {"schema_version": CONTRACT_VERSION, **common,
                "symbols": [req["symbol"]], "membership_limitations": "SOXX single-symbol research capture; no historical universe claim",
                "base_timeframe": "15m", "calendar": "XNYS", "session_policy": "RTH_EXTENDED",
                "session_contract": session_profile(EXTENDED).metadata,
                "requested_range": req, "corporate_action_events": events,
                "known_limitations": list(LIMITATIONS)}
    present = {b.start_at for b in bars}
    missing = sorted(set(expected) - present)
    manifest["coverage_status"] = "UNAVAILABLE" if missing or unsupported else "COMPLETE_GRID"
    manifest["missing_slots"] = [s.isoformat() for s in missing]
    manifest["unsupported_sessions"] = unsupported
    return MarketDataset(dataset_id, tuple(bars), JsonObject.of(manifest))


def validate_real_manifest(meta):
    """Called by MarketDataset on every construction, including SQLite reload."""
    if meta.get('provider') == 'alpaca_sip':
        from .alpaca_data import validate_manifest
        return validate_manifest(meta)
    required = {"provider_version", "requested_range", "raw_capture_hash", "known_limitations",
                "corporate_action_events", "coverage_status", "missing_slots", "unsupported_sessions"}
    if not required <= meta.keys():
        raise ValueError("Incomplete real dataset provenance")
    expected = {"provider": PROVIDER, "adapter_version": ADAPTER,
                "price_basis": PRICE_BASIS, "corporate_actions": ACTION_BASIS,
                "known_at_policy": AVAILABILITY, "session_policy": "RTH_EXTENDED"}
    if any(meta[k] != v for k, v in expected.items()):
        raise ValueError("Mixed/unsupported real provider or price basis")
    req = meta["requested_range"]
    if req != request(req["symbol"], req["start"], req["end"]) or meta["symbols"] != [req["symbol"]]:
        raise ValueError("Real request provenance mismatch")
    if len(meta["raw_capture_hash"]) != 64 or not meta["provider_version"]:
        raise ValueError("Real capture/version provenance required")


def validate_real_bar(bar, meta):
    if meta.get('provider') == 'alpaca_sip':
        from .alpaca_data import validate_bar
        return validate_bar(bar, meta)
    provenance = bar.provenance.unpack()
    keys = ("quality", "provider", "adapter_version", "provider_version", "timezone",
            "price_basis", "corporate_actions", "known_at_policy")
    if any(provenance.get(k) != meta[k] for k in keys) or bar.source != PROVIDER:
        raise ValueError("Mixed real bar provenance/price basis")
    if bar.corporate_action != "UNKNOWN" or bar.known_at != bar.end_at:
        raise ValueError("Real snapshot must retain UNKNOWN actions and assumed bar-end clock")
    if (timestamp(provenance["captured_at"]) > timestamp(meta["captured_at"])
            or timestamp(provenance["captured_at"]) < bar.end_at
            or len(provenance["raw_capture_hash"]) != 64):
        raise ValueError("Invalid real per-bar capture provenance")
    req = meta["requested_range"]
    if not timestamp(_midnight(req["start"])) <= bar.start_at < bar.end_at <= timestamp(_midnight(req["end"])):
        raise ValueError("Real bar outside manifest request")


def validate_real_coverage(bars, meta):
    expected, unsupported = expected_slots(meta["requested_range"])
    if meta.get('provider') == 'alpaca_sip' and ({b.start_at for b in bars} != set(expected) or unsupported):
        raise ValueError('Exact Alpaca expected-grid equality required')
    missing = sorted(set(expected) - {b.start_at for b in bars})
    status = "UNAVAILABLE" if missing or unsupported else "COMPLETE_GRID"
    if (meta["missing_slots"] != [s.isoformat() for s in missing]
            or meta["unsupported_sessions"] != unsupported or meta["coverage_status"] != status):
        raise ValueError("Real coverage manifest mismatch")


def is_research_snapshot(bar):
    """Permit UNKNOWN actions only under this explicit historical-only policy.

    This never certifies NONE_CONFIRMED or supplies the frozen Daily PIT contract.
    Derived bars must carry the policy and retain UNKNOWN action state.
    """
    meta = bar.provenance.unpack()
    if meta.get('provider') == 'alpaca_sip':
        from .alpaca_data import is_snapshot
        return is_snapshot(bar)
    return (bar.corporate_action == "UNKNOWN"
            and meta.get("quality") == "REAL_HISTORICAL_RESEARCH"
            and meta.get("provider") == PROVIDER and meta.get("adapter_version") == ADAPTER
            and meta.get("price_basis") == PRICE_BASIS
            and meta.get("corporate_actions") == ACTION_BASIS
            and meta.get("known_at_policy") == AVAILABILITY)


def coverage(dataset):
    meta = dataset.manifest.unpack()
    counts = Counter(b.provenance.unpack()["session_segment"] for b in dataset.bars)
    missing = meta["missing_slots"]
    # Gap count is runs of consecutive missing 15m slots, never overnight breaks.
    gap_count = sum(i == 0 or timestamp(s) - timestamp(missing[i-1]) != timedelta(minutes=15)
                    for i, s in enumerate(missing))
    expected, unsupported = expected_slots(meta["requested_range"])
    return {"schema_version": "real_15m_coverage_v1", "provider": meta["provider"],
            "adapter_version": meta["adapter_version"], "provider_version": meta["provider_version"],
            "symbol": meta["symbols"][0], "dataset_id": dataset.dataset_id,
            "content_hash": dataset.content_hash, "captured_at": meta["captured_at"],
            "requested_date_range": meta["requested_range"],
            "actual_date_range": {"start": dataset.bars[0].session, "end": dataset.bars[-1].session},
            "timezone": meta["timezone"], "session_profile": dataset.session_profile,
            "coverage_status": meta["coverage_status"], "expected_15m_bars": len(expected),
            "observed_bars": len(dataset.bars), "missing_bars": len(missing),
            "missing_slots": missing, "missing_status": "UNKNOWN/UNAVAILABLE" if missing else "NONE",
            "unsupported_sessions": unsupported, "duplicate_count": 0, "gap_count": gap_count,
            "premarket_count": counts["PREMARKET"], "rth_count": counts["RTH"],
            "after_hours_count": counts["AFTER_HOURS"],
            "zero_volume_by_segment": dict(Counter(b.provenance.unpack()["session_segment"]
                                                     for b in dataset.bars if b.volume == 0)),
            "earliest_timestamp": dataset.bars[0].start_at.isoformat(),
            "latest_timestamp": dataset.bars[-1].end_at.isoformat(),
            "price_basis": meta["price_basis"], "corporate_action_basis": meta["corporate_actions"],
            "corporate_action_state": "UNKNOWN", "corporate_action_events": meta["corporate_action_events"],
            "known_at_policy": meta["known_at_policy"], "raw_capture_hash": meta["raw_capture_hash"],
            "incremental": meta.get("incremental"), "known_limitations": meta["known_limitations"]}


def incremental_request(parent, end, overlap_days=7):
    if type(overlap_days) is not int or overlap_days < 1:
        raise ValueError("Positive overlap days required")
    meta = parent.manifest.unpack()
    validate_real_manifest(meta)
    original = meta["requested_range"]
    if end < original["end"]:
        raise ValueError("Incremental range cannot shrink")
    start = max(date.fromisoformat(original["start"]),
                date.fromisoformat(original["end"]) - timedelta(days=overlap_days))
    return request(original["symbol"], start.isoformat(), end)


def new_vintage(parent, incoming, dataset_id):
    """Replace only fully re-requested days; detect revisions including deletions.

    Older retained bars keep their original capture hash/time. Missing overlap
    bars are removed from the NEW vintage and reported, never silently retained.
    Split events trigger fail-closed full recapture to avoid mixing split vintages.
    """
    from .market_data import MarketDataset

    if dataset_id == parent.dataset_id:
        raise ValueError("Incremental update requires a new dataset identity")
    old, fresh = parent.manifest.unpack(), incoming.manifest.unpack()
    validate_real_manifest(old)
    validate_real_manifest(fresh)
    for key in ("symbols", "provider", "adapter_version", "provider_version", "price_basis",
                "corporate_actions", "known_at_policy", "session_contract"):
        if old[key] != fresh[key]:
            raise ValueError("Mixed incremental provenance; full recapture required")
    a, b = old["requested_range"], fresh["requested_range"]
    if not a["start"] <= b["start"] < a["end"] <= b["end"]:
        raise ValueError("Incremental refresh must overlap and cannot shrink")
    if timestamp(fresh["captured_at"]) < timestamp(old["captured_at"]):
        raise ValueError("Incremental capture clock reversal")
    if old["corporate_action_events"].get("splits") or fresh["corporate_action_events"].get("splits"):
        raise ValueError("Split snapshot requires full recapture, not mixed vintage")
    cutoff = timestamp(_midnight(b["start"]))
    old_overlap = {v.start_at: v for v in parent.bars if v.start_at >= cutoff}
    new_overlap = {v.start_at: v for v in incoming.bars if v.start_at < timestamp(_midnight(a["end"]))}
    def values(v):
        return tuple(getattr(v, k) for k in ("open", "high", "low", "close", "volume"))
    revised = [at.isoformat() for at in sorted(old_overlap.keys() & new_overlap.keys())
               if values(old_overlap[at]) != values(new_overlap[at])]
    deleted = [at.isoformat() for at in sorted(old_overlap.keys() - new_overlap.keys())]
    added = [at.isoformat() for at in sorted(new_overlap.keys() - old_overlap.keys())]
    bars = tuple(replace(v, dataset_id=dataset_id) for v in
                 (*[v for v in parent.bars if v.start_at < cutoff], *incoming.bars))
    meta = {**fresh, "requested_range": request(a["symbol"], a["start"], b["end"]),
            "incremental": {"parent_dataset_id": parent.dataset_id, "parent_content_hash": parent.content_hash,
                            "refresh_range": b, "revised_slots": revised, "deleted_slots": deleted,
                            "added_overlap_slots": added},
            "raw_capture_hashes": sorted({v.provenance.unpack()["raw_capture_hash"] for v in bars})}
    # Retain prior action events only before the fully refreshed overlap.
    merged = {}
    for kind in old["corporate_action_events"].keys() | fresh["corporate_action_events"].keys():
        merged[kind] = {k: v for k, v in old["corporate_action_events"].get(kind, {}).items()
                        if datetime.fromtimestamp(int(k), timezone.utc) < cutoff}
        merged[kind].update(fresh["corporate_action_events"].get(kind, {}))
    meta["corporate_action_events"] = merged
    expected, unsupported = expected_slots(meta["requested_range"])
    meta["missing_slots"] = [v.isoformat() for v in sorted(set(expected) - {v.start_at for v in bars})]
    meta["unsupported_sessions"] = unsupported
    meta["coverage_status"] = "UNAVAILABLE" if meta["missing_slots"] or unsupported else "COMPLETE_GRID"
    return MarketDataset(dataset_id, bars, JsonObject.of(meta))


def archive_capture(capture, root):
    """Content-addressed raw JSON; collisions cannot overwrite an old capture."""
    path = Path(root) / "raw" / (digest(capture) + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = canonical(capture)
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise ValueError("Raw capture identity collision")
    else:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(text)
    return path


def write_coverage(dataset, root):
    body = coverage(dataset)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / (dataset.dataset_id + ".coverage.json")
    text = canonical(body)
    if path.exists() and path.read_text(encoding="utf-8") != text:
        raise ValueError("Coverage identity collision")
    path.write_text(text, encoding="utf-8")
    markdown = (f"# {dataset.dataset_id}\n\n"
                f"Provider: {body['provider']} / {body['adapter_version']}\n\n"
                f"Content hash: `{dataset.content_hash}`\n\n"
                f"Observed/expected: {body['observed_bars']}/{body['expected_15m_bars']}; "
                f"missing: {body['missing_bars']}; status: {body['coverage_status']}\n\n"
                f"Pre/RTH/post: {body['premarket_count']}/{body['rth_count']}/{body['after_hours_count']}\n\n"
                + "\n".join("- " + v for v in body["known_limitations"]) + "\n")
    path.with_suffix(".md").write_text(markdown, encoding="utf-8")
    return body
