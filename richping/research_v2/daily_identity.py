"""Narrow, ex-post dataset admission for an audited split-free Daily interval.

Certification is data-quality metadata, never historical event availability.
It certifies this exact snapshot's units, not all Yahoo history or live PIT.
"""

from dataclasses import replace
from datetime import date
import math

from ..core import digest, timestamp
from .contracts import JsonObject

IDENTITY = "PIT_SPLIT_ADJUSTED_IDENTITY_INTERVAL_V1"
COMPLETENESS = "EX_POST_SPLIT_HISTORY_COMPLETENESS_V1"
UNIT = "INTERVAL_SHARE_UNIT_CROSSCHECK_V1"
FIELDS = ("open", "high", "low", "close")
MARKET_TOLERANCE = 0.02  # USD; cent rounding plus float32 transport
NAV_TOLERANCE = 0.02  # relative; NAV is a distinct valuation, not OHLC


def unit_comparison(quote, market, *, future_ratio=3.0):
    """Compare same-session market OHLC; detect an early future unit rebase."""
    if type(future_ratio) not in (int, float) or not math.isfinite(future_ratio) or future_ratio <= 1:
        raise ValueError("Positive forward split ratio required")
    for row in (quote, market):
        if any(type(row.get(k)) not in (int, float) or not math.isfinite(row[k]) or row[k] <= 0 for k in FIELDS):
            raise ValueError("Finite positive OHLC required")
        if not row["low"] <= min(row["open"], row["close"]) <= max(row["open"], row["close"]) <= row["high"]:
            raise ValueError("Invalid reference OHLC")
    differences = {k: abs(quote[k] - market[k]) for k in FIELDS}
    early = all(abs(quote[k] * future_ratio - market[k]) <= MARKET_TOLERANCE * future_ratio for k in FIELDS)
    return {"absolute_differences_USD": differences, "absolute_tolerance_USD": MARKET_TOLERANCE,
            "future_split_preadjustment_detected": early,
            "unit_certification_result": "PASS" if not early and max(differences.values()) <= MARKET_TOLERANCE else "FAIL"}


def _refs(values):
    if not isinstance(values, list) or not values:
        raise ValueError("Audited source references required")
    for ref in values:
        if not ref.get("identity") or not ref.get("url", "").startswith("https://") or len(ref.get("sha256", "")) != 64:
            raise ValueError("Content-bound source references required")


def validate_identity(meta, actions, bars):
    """Recheck embedded evidence on every immutable vintage load, fail closed."""
    cert = meta["identity_interval_certification"]
    if cert["version"] != IDENTITY or cert["scope"] != "HISTORICAL_CAUSAL_RESEARCH_ONLY":
        raise ValueError("Narrow historical identity scope required")
    audit, unit = cert["action_history_audit"], cert["unit_audit"]
    if cert["action_audit_hash"] != digest(audit) or cert["unit_audit_hash"] != digest(unit):
        raise ValueError("Identity audit hash mismatch")
    if audit["schema_version"] != COMPLETENESS or unit["schema_version"] != UNIT:
        raise ValueError("Unsupported identity evidence version")
    if audit["certification_scope"] != "EX_POST_DATASET_ADMISSION_NOT_STRATEGY_KNOWN_AT":
        raise ValueError("Completeness audit must not be a causal receipt")
    origin, end = bars[0].session, bars[-1].session
    for body in (cert, audit, unit):
        if (body["symbol"], body["interval_start"], body["interval_end"]) != (bars[0].symbol, origin, end):
            raise ValueError("Identity interval/symbol mismatch")
    if cert["raw_capture_hash"] != meta["raw_capture_hash"] or unit["raw_capture_hash"] != meta["raw_capture_hash"]:
        raise ValueError("Unit certification must bind exact source vintage")
    if audit["splits_inside_interval"] != [] or audit["result"] != "PASS":
        raise ValueError("Identity requires audited no-event interval")
    previous, following = audit["previous_effective_split"], audit["next_effective_split"]
    if not previous["trading_date"] < origin <= end < following["trading_date"]:
        raise ValueError("Effective split overlaps identity interval")
    for event in (previous, following):
        date.fromisoformat(event["trading_date"])
        if event["factor_units"] != "NEW_SHARES_PER_OLD_SHARES" or not event["new_shares"] > event["old_shares"] > 0:
            raise ValueError("Audited boundary split units required")
        _refs(event["sources"])
    _refs(audit["dataset_completeness_sources"])
    kinds = {s["role"] for s in audit["dataset_completeness_sources"]}
    if not {"OFFICIAL_ISSUER", "CURRENT_PROVIDER_HISTORY", "INDEPENDENT_ACTION_HISTORY"} <= kinds:
        raise ValueError("Issuer/provider/independent completeness cross-check required")
    # Even a contradictory unknown event invalidates identity. Never erase the engine.
    for e in actions["events"]:
        if bars[0].start_at <= timestamp(e["effective_at"]) <= bars[-1].end_at:
            raise ValueError("Actual split event contradicts identity certification")
    if meta["raw_unit_status"] != "VERIFIED_IDENTITY_INTERVAL" or meta["raw_price_basis"] != unit["source_price_basis"]:
        raise ValueError("Interval certification cannot relabel all history raw/as-traded")
    if cert["applied_actions"] != [] or cert["factor"] != 1.0 or cert["transform"] != "IDENTITY":
        raise ValueError("Identity transform metadata mismatch")
    if meta["known_at_policy"] != "HISTORICAL_RESEARCH_BAR_END_AVAILABILITY_ASSUMPTION_V1":
        raise ValueError("Identity admission does not certify live bar availability")
    for body in (audit, unit):
        if timestamp(body["captured_at"]) > timestamp(meta["captured_at"]) or not body["limitations"]:
            raise ValueError("Capture provenance/limitations required")
    _refs(unit["market_sources"])
    indexed = {b.session: b for b in bars}
    seen = set()
    for row in unit["rows"]:
        if row["session"] in seen or row["session"] not in indexed:
            raise ValueError("Unit audit duplicate/out-of-range session")
        seen.add(row["session"])
        bar = indexed[row["session"]]
        quote_key = 'source_quote' if meta['provider'] == 'alpaca_sip' else 'yahoo_quote'
        if row[quote_key] != {k: getattr(bar, k) for k in FIELDS}:
            raise ValueError("Unit audit quote mismatch")
        result = unit_comparison(row[quote_key], row["market_ohlc"],
                                 future_ratio=following["new_shares"] / following["old_shares"])
        if result != row["comparison"] or result["unit_certification_result"] != "PASS":
            raise ValueError("Market OHLC share-unit cross-check failed")
        _refs(row["sources"])
        nav = row["issuer_NAV"]
        if type(nav) not in (float, int) or not math.isfinite(nav) or nav <= 0 or abs(bar.close / nav - 1) > NAV_TOLERANCE:
            raise ValueError("Issuer NAV unit sanity check failed")
    # This capability deliberately requires every captured session, not extrapolation.
    if seen != set(indexed) or unit["result"] != "PASS" or unit["nav_relative_tolerance"] != NAV_TOLERANCE:
        raise ValueError("Complete interval OHLC/NAV certification required")
    return cert


def admit_identity_interval(parent, dataset_id, action_audit, unit_audit):
    """Create a child; keep all original prices, raw basis and action receipts."""
    if dataset_id == parent.dataset_id:
        raise ValueError("Admission requires a new immutable Daily identity")
    meta = parent.manifest.unpack()
    meta.update(parent_dataset_id=parent.dataset_id, parent_content_hash=parent.content_hash,
                raw_unit_status="VERIFIED_IDENTITY_INTERVAL",
                captured_at=max(timestamp(meta["captured_at"]), timestamp(action_audit["captured_at"]),
                                timestamp(unit_audit["captured_at"])).isoformat())
    meta["identity_interval_certification"] = {
        "version": IDENTITY, "scope": "HISTORICAL_CAUSAL_RESEARCH_ONLY",
        "symbol": parent.bars[0].symbol, "interval_start": parent.bars[0].session,
        "interval_end": parent.bars[-1].session, "raw_capture_hash": meta["raw_capture_hash"],
        "action_history_audit": action_audit, "unit_audit": unit_audit,
        "action_audit_hash": digest(action_audit), "unit_audit_hash": digest(unit_audit),
        "action_audit_ref": action_audit["evidence_ref"], "unit_audit_ref": unit_audit["evidence_ref"],
        "applied_actions": [], "factor": 1.0, "transform": "IDENTITY"}
    return replace(parent, dataset_id=dataset_id,
                   bars=tuple(replace(b, dataset_id=dataset_id) for b in parent.bars), manifest=JsonObject.of(meta))
