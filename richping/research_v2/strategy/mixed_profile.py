"""As-of references to separate Daily and extended streams; no entry composer.

One join per complete known_at batch. The generic replay's groupby and completed
aggregator publication rules are reused; no mixed-profile ReplayContext exists.
"""

from collections import Counter
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from itertools import groupby

from ...core import calendar, canonical, digest, timestamp
from ..aggregation import CompletedAggregator
from ..contracts import ReplayContext, payload
from .daily_input import prepare_daily
from ..market_data import availability_order, market_order
from ..sessions import EXTENDED, RTH, NY, session_bounds
from .daily_trend import classify_daily_trend
from .daily_exhaustion import classify_daily_exhaustion
from .h1_setup import PreparedH1Prefix, classify_h1_relative_setup
from .entry_15m import classify_15m, measure_completed_15m, contract_hash

VERSION = "H0001_MIXED_PROFILE_AS_OF_JOIN_V1"


def expected_extended_end(as_of, timeframe):
    instant = timestamp(as_of)
    day = instant.astimezone(NY).date().isoformat()
    cal = calendar()
    if not cal.first_session.date().isoformat() <= day <= cal.last_session.date().isoformat():
        raise ValueError("Unsupported calendar date")
    session = cal.date_to_session(day, direction="previous")
    opened, closed = session_bounds(session.date().isoformat(), EXTENDED)
    interval = timedelta(minutes=15) if timeframe == "15m" else timedelta(hours=1)
    if instant < opened+interval:
        session = cal.previous_session(session)
        return session_bounds(session.date().isoformat(), EXTENDED)[1]
    return opened+((min(instant, closed)-opened)//interval)*interval


def atomic_intraday_batches(dataset):
    """Yield detached snapshots only after ALL equal-known-at members publish."""
    if dataset.session_profile != EXTENDED:
        raise ValueError("Extended intraday dataset required")
    if dataset.manifest.unpack().get("coverage_status", "COMPLETE_GRID") != "COMPLETE_GRID":
        raise ValueError("Incomplete intraday source coverage")
    aggregator = CompletedAggregator(("1H",), profile=EXTENDED)
    visible = []
    for known, members in groupby(sorted(dataset.bars, key=availability_order), key=lambda b: b.known_at):
        batch = tuple(members)
        completed = tuple(sorted((c for b in batch for c in aggregator.accept(b, known)), key=market_order))
        visible.extend(completed)
        yield known, tuple(sorted(visible, key=market_order)), completed


def intraday_as_of(dataset, as_of):
    instant = timestamp(as_of)
    last = ()
    for known, visible, _ in atomic_intraday_batches(dataset):
        if known > instant:
            break
        last = visible
    return last


def _reference(role, timeframe, profile, basis, vintage, source, known, input_hash, state, version, state_hash, status):
    return {"role": role, "symbol": "", "timeframe": timeframe, "session_profile": profile,
            "price_basis": basis, "source_vintage": vintage,
            "source_end_at": source.isoformat() if source else None,
            "source_known_at": known.isoformat() if known else None,
            "causal_input_hash": input_hash, "state": state, "state_version": version,
            "state_hash": state_hash, "status": status}


def join_as_of(daily, intraday, as_of, *, published=None, m15_measurements=None, h1_cache=None, return_states=False, daily_cache=None):
    """Resolve each role independently from one immutable pair of vintages.

    published is supplied by atomic_intraday_batches, never a strategy partial
    publication. Public callers should omit it to materialize the causal prefix.
    """
    instant = timestamp(as_of)
    symbol = daily.manifest.unpack()["requested_range"]["symbol"]
    if intraday.manifest.unpack()["symbols"] != [symbol]:
        raise ValueError("Mixed-profile symbol identity mismatch")
    bars = intraday_as_of(intraday, instant) if published is None else published
    if any(b.dataset_id != intraday.dataset_id or b.symbol != symbol for b in bars):
        raise ValueError("Mixed intraday source vintage")
    if len({b.identity for b in bars}) != len(bars):
        raise ValueError("Joined source identity collision")
    if any(b.known_at > instant or b.end_at > instant for b in bars):
        raise ValueError("Future bar in mixed-profile source publication")
    if {b for b in bars if b.timeframe == "15m"} != {b for b in intraday.bars if b.known_at <= instant}:
        raise ValueError("Partial or modified atomic intraday publication")
    hour_members = {}
    for bar in bars:
        if bar.timeframe == "15m":
            hour_end = bar.end_at+timedelta(minutes=(-bar.end_at.minute) % 60)
            hour_members.setdefault(hour_end, []).append(bar)
    expected_hours = {end for end, members in hour_members.items() if len(members) == 4 and end <= instant}
    hourly_bars = [b for b in bars if b.timeframe == "1H"]
    if {b.end_at for b in hourly_bars} != expected_hours or any(b.timeframe not in {"15m", "1H"} for b in bars):
        raise ValueError("Partial atomic completed 1H publication")
    for bar in hourly_bars:
        members = sorted(hour_members[bar.end_at], key=lambda b: b.end_at)
        if ((bar.open, bar.high, bar.low, bar.close, bar.volume, bar.known_at)
                != (members[0].open, max(b.high for b in members), min(b.low for b in members),
                    members[-1].close, sum(b.volume for b in members), max(b.known_at for b in members))):
            raise ValueError("Modified aggregate source identity")
    context = ReplayContext(instant, bars)  # Extended only, never concatenated Daily.
    resolution = prepare_daily(daily, instant)
    # The authoritative selector/transform still runs at every atomic as_of.
    # Cache only identical prepared causal inputs, never an older fresh state
    # across an expected-session change or an availability/evidence failure.
    p = resolution.prefix
    daily_key = (p.symbol, p.bars, p.expected_session, p.source_vintage,
                 p.transform_known_at, p.transform_effective_at, p.input_status,
                 p.input_reason, p.session_profile, p.price_basis)
    cached_daily = daily_cache.get(daily_key) if daily_cache is not None else None
    if cached_daily is None:
        trend = classify_daily_trend(p, instant)
        exhaustion = classify_daily_exhaustion(p, instant)
        if daily_cache is not None:
            daily_cache.clear()
            daily_cache[daily_key] = trend, exhaustion
    else:
        trend = replace(cached_daily[0], as_of=instant)
        exhaustion = replace(cached_daily[1], as_of=instant,
            macd_feature=replace(cached_daily[1].macd_feature, as_of=instant) if cached_daily[1].macd_feature else None,
            percentile_feature=replace(cached_daily[1].percentile_feature, as_of=instant) if cached_daily[1].percentile_feature else None)
    references = []
    for role, state, version, rule_hash in (
        ("DAILY_TREND_PERMISSION", trend, trend.rule_version, trend.rule_hash),
        ("DAILY_EXHAUSTION", exhaustion, exhaustion.state_version, exhaustion.state_definition_hash)):
        state_body = {k: v for k, v in payload(state).items() if k not in {"as_of", "macd_feature", "percentile_feature"}}
        references.append(_reference(role, "Daily", RTH, resolution.prefix.price_basis,
            daily.dataset_id, state.input_end_at, state.known_at, state.input_hash,
            state.state, version, digest({"state": state_body, "rule": rule_hash}), state.status))
    basis = intraday.manifest.unpack()["price_basis"]
    try:
        expected_h1 = expected_extended_end(instant, "1H")
        expected_m15 = expected_extended_end(instant, "15m")
    except ValueError:
        expected_h1 = expected_m15 = None
    hourly = context.query(symbol, "1H")
    h1_key = (expected_h1, hourly)
    cached = h1_cache.get(h1_key) if h1_cache is not None else None
    if cached is not None:
        h1 = replace(cached, as_of=instant)
    else:
        h1 = classify_h1_relative_setup(PreparedH1Prefix(symbol, hourly, instant, expected_h1,
            intraday.dataset_id, max((b.known_at for b in hourly), default=None), price_basis=basis), instant)
        if h1_cache is not None:
            h1_cache.clear()  # One current immutable prefix, not a growing cache.
            h1_cache[h1_key] = h1
    references.append(_reference("H1_RELATIVE_SETUP_RAW", "1H", EXTENDED, basis,
        intraday.dataset_id, h1.source_1h_end, h1.source_1h_known_at, h1.input_hash,
        h1.state, h1.contract_version, h1.hash, h1.status))
    current = context.query(symbol, "15m")
    if not current:
        m15 = None
    elif m15_measurements is None:
        m15 = classify_15m(context, symbol, expected_completed_end=expected_m15)
    else:
        # Precomputed scalar prefixes have per-point causal hashes/known_at; the
        # current prefix must match authoritative completed identity and count.
        candidate = m15_measurements[len(current)-1]
        if (candidate.end_at != current[-1].end_at or candidate.known_at > instant
                or candidate.source_vintage != intraday.dataset_id):
            raise ValueError("Mismatched precomputed causal 15m state")
        m15 = replace(candidate, as_of=instant)
        if m15.end_at != expected_m15:
            m15 = replace(m15, raw="UNAVAILABLE", reason="latest_expected_completed_15m_missing", percentile=None)
    references.append(_reference("M15_INITIAL_ENTRY_PRIMITIVE", "15m", EXTENDED, basis,
        intraday.dataset_id, m15.end_at if m15 else None, m15.known_at if m15 else None,
        m15.input_hash if m15 else digest({"missing_15m": True}), m15.raw if m15 else "UNAVAILABLE",
        "M15_INITIAL_EXTREME_GC_PRICE_V1", m15.identity_hash if m15 else contract_hash(),
        "READY" if m15 and m15.raw != "UNAVAILABLE" else "UNAVAILABLE"))
    for r in references:
        r["symbol"] = symbol
        r["input_contract_version"] = "H0001_DAILY_INPUT_FREEZE_V1" if r["timeframe"] == "Daily" else "research_v2_a_v1"
        if r["source_known_at"] and timestamp(r["source_known_at"]) > instant:
            raise ValueError("Future-known joined state")
    body = {"version": VERSION, "as_of": instant.isoformat(), "references": references,
            "expected_Daily_session": resolution.prefix.expected_session,
            "Daily_input_status": resolution.prefix.input_status,
            "Daily_input_reason": resolution.prefix.input_reason,
            "Daily_transform": resolution.transform.unpack(),
            "constituent_state_hash": digest(references),
            "publication": "atomic_known_at_batch_v1", "concatenated_stream": False,
            "ENTRY_CANDIDATE": None, "entry_outcome": "NOT_EVALUATED", "profitability": "NOT_RUN"}
    return (body, trend, exhaustion, h1, m15) if return_states else body


def mixed_proof(daily, intraday):
    """Network-free executable proof, including honest unavailable denominators."""
    full_context = ReplayContext(max(b.known_at for b in intraday.bars), intraday.bars)
    m15 = measure_completed_15m(full_context, daily.bars[0].symbol)
    fingerprint, counts, reasons, examples = sha256(), Counter(), Counter(), {}
    events, joint_ready, h1_cache = 0, 0, {}
    for as_of, visible, _ in atomic_intraday_batches(intraday):
        joined = join_as_of(daily, intraday, as_of, published=visible, m15_measurements=m15, h1_cache=h1_cache)
        fingerprint.update(canonical(joined).encode())
        counts.update(r["role"]+":"+r["status"] for r in joined["references"])
        if joined["Daily_input_reason"]:
            reasons.update([joined["Daily_input_reason"]])
        if all(r["status"] == "READY" for r in joined["references"]):
            joint_ready += 1
        local = as_of.astimezone(NY).strftime("%H:%M")
        if local in {"06:00", "15:45", "16:00", "16:15", "20:00"}:
            examples.setdefault(local, joined)
        events += 1
    return {"schema_version": VERSION, "daily_dataset_id": daily.dataset_id,
            "daily_content_hash": daily.content_hash, "intraday_dataset_id": intraday.dataset_id,
            "intraday_content_hash": intraday.content_hash, "events": events,
            "joined_event_hash": fingerprint.hexdigest(), "role_status_counts": dict(counts),
            "Daily_unavailable_reasons": dict(reasons), "examples": examples,
            "network_calls": 0, "joint_READY_evaluations": joint_ready,
            "composition_inputs_mechanically_usable": joint_ready > 0,
            "ENTRY_CANDIDATE": None, "entry_outcome": "NOT_EVALUATED", "profitability": "NOT_RUN"}
