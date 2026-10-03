"""Frozen Daily freshness and causal split transforms, detached from strategy."""

from dataclasses import dataclass, replace
from datetime import datetime

from ...core import calendar, digest, timestamp
from ..contracts import JsonObject, payload
from ..daily_data import DailyVintage
from ..sessions import NY, RTH, session_bounds
from .daily_trend import PreparedDailyPrefix

TRANSFORM = "CAUSAL_RTH_OHLC_SPLIT_TRANSFORM_V1"


def expected_daily_session(as_of):
    instant = timestamp(as_of)
    day = instant.astimezone(NY).date().isoformat()
    cal = calendar()
    if not cal.first_session.date().isoformat() <= day <= cal.last_session.date().isoformat():
        raise ValueError("Unsupported calendar date")
    session = cal.date_to_session(day, direction="previous")
    selected = session.date().isoformat()
    if session_bounds(selected, RTH)[1] > instant:
        selected = cal.previous_session(session).date().isoformat()
    return selected


@dataclass(frozen=True, slots=True)
class DailyResolution:
    prefix: PreparedDailyPrefix
    transform: JsonObject


def prepare_daily(vintage: DailyVintage, as_of):
    """No raw/stale fallback. Only evidence available at this as_of enters hashes.

    Negative action evidence is a required transform input too: a capture today
    cannot attest to action-free status known during an earlier replay session.
    """
    instant = timestamp(as_of)
    meta, actions = vintage.manifest.unpack(), vintage.actions.unpack()
    symbol = meta["requested_range"]["symbol"]
    expected = None

    def unavailable(reason):
        return DailyResolution(PreparedDailyPrefix(symbol, (), instant, expected,
            vintage.dataset_id, None, input_status="UNAVAILABLE", input_reason=reason),
            JsonObject.of({"transform_version": TRANSFORM, "as_of": instant.isoformat(),
                           "status": "UNAVAILABLE", "reason": reason, "applied_actions": [],
                           "raw_fallback": False}))

    try:
        expected = expected_daily_session(instant)
    except (ValueError, OverflowError):
        return unavailable("unsupported_calendar_date")
    selected = tuple(b for b in vintage.bars if b.session <= expected)
    if not selected or selected[-1].session != expected:
        return unavailable("latest_expected_completed_session_missing")
    if any(b.known_at > instant or b.end_at > instant for b in selected):
        return unavailable("expected_Daily_not_yet_delivered")
    if any(s <= expected for s in meta["missing_sessions"]):
        return unavailable("missing_Daily_session_in_required_prefix")
    if actions["status"] == "CROSS_CHECK_ONLY":
        return unavailable("historical_action_availability_and_coverage_unverified")
    if meta["raw_unit_status"] == "UNVERIFIED":
        return unavailable("raw_OHLC_share_units_unverified")
    if (meta["raw_unit_status"] == "VERIFIED_AS_TRADED"
            and timestamp(meta["unit_known_at"]) > instant):
        return unavailable("raw_OHLC_unit_evidence_not_yet_known")
    cover = [c for c in actions["coverage"] if timestamp(c["start_at"]) <= selected[0].start_at
             and timestamp(c["through_at"]) >= instant and timestamp(c["known_at"]) <= instant]
    if not cover:
        return unavailable("causal_action_coverage_unavailable")
    coverage = max(cover, key=lambda c: timestamp(c["known_at"]))
    versions = {}
    relevant_ids = set()
    for event in actions["events"]:
        if selected[0].start_at < timestamp(event["effective_at"]) <= instant:
            relevant_ids.add(event["event_id"])
        if timestamp(event["known_at"]) <= instant:
            prior = versions.get(event["event_id"])
            if prior is None or timestamp(event["known_at"]) > timestamp(prior["known_at"]):
                versions[event["event_id"]] = event
    if any(key not in versions for key in relevant_ids):
        return unavailable("effective_split_required_evidence_not_yet_known")
    applied = sorted((e for e in versions.values()
                      if selected[0].start_at < timestamp(e["effective_at"]) <= instant),
                     key=lambda e: (timestamp(e["effective_at"]), e["event_id"]))
    if any(b.start_at < timestamp(e["effective_at"]) < b.end_at for b in selected for e in applied):
        return unavailable("split_effective_inside_Daily_share_unit_interval")
    known = max([timestamp(coverage["known_at"]),
                 *(timestamp(e["known_at"]) for e in applied),
                 *([timestamp(meta["unit_known_at"])] if meta["raw_unit_status"] == "VERIFIED_AS_TRADED" else [])])
    # Do not hash the full vintage (which may contain future events/receipts).
    causal_inputs = {"raw_prefix": payload(selected), "coverage": coverage,
                     "actions": applied, "source_vintage": vintage.dataset_id,
                     "action_source_vintage": actions["source_vintage"], "transform_version": TRANSFORM}
    input_hash = digest(causal_inputs)
    transformed, factors = [], []
    for b in selected:
        factor = 1.0
        for event in applied:
            if b.end_at <= timestamp(event["effective_at"]):
                factor *= event["old_shares"] / event["new_shares"]
        factors.append(factor)
        transformed.append(replace(b, **{k: getattr(b, k)*factor for k in ("open", "high", "low", "close")},
            known_at=max(b.known_at, known), corporate_action="NONE_CONFIRMED",
            provenance=JsonObject.of({**b.provenance.unpack(),
                "price_basis": "PIT_SPLIT_ADJUSTED_OHLC", "transform_version": TRANSFORM,
                "transform_input_hash": input_hash, "split_factor": factor,
                "action_evidence_ref": coverage["evidence_ref"],
                "action_source_vintage": actions["source_vintage"],
                "corporate_actions": "CAUSALLY_NORMALIZED_NOT_RAW_FALLBACK"})))
    prefix = PreparedDailyPrefix(symbol, tuple(transformed), instant, expected, vintage.dataset_id,
        known, tuple(timestamp(e["effective_at"]) for e in applied))
    return DailyResolution(prefix, JsonObject.of({"transform_version": TRANSFORM,
        "as_of": instant.isoformat(), "status": "READY", "source_vintage": vintage.dataset_id,
        "source_price_basis": meta["raw_price_basis"], "price_basis": prefix.price_basis,
        "input_hash": input_hash, "transform_known_at": known.isoformat(),
        "action_evidence_ref": coverage["evidence_ref"], "action_source_vintage": actions["source_vintage"],
        "applied_actions": applied, "factors": factors, "raw_fallback": False,
        "result": "SPLITS_APPLIED" if applied else "NO_APPLIED_SPLIT_IN_CAUSAL_PREFIX"}))
