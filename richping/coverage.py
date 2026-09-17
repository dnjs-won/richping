"""Read-only v3 coverage diagnostics; research selections are not live evidence."""

from collections import Counter

from .core import CASH_ACTION_REVIEW_POLICY, DEFAULT_OUTCOME_VERSION, cutoff_at, timestamp
from .data import inspect_action_capture
from .engine import Engine, observe
from .evaluation import cohort_returns, evaluate_outcome_eligibility, metrics


WINDOW_REASONS = ("missing_or_unknown_history", "data_not_yet_known", "dividend",
                  "split", "capital_gains", "action_capture_unknown")
CANDIDATE_REASONS = ("not_in_asof_universe",) + WINDOW_REASONS + (
    "price_or_liquidity", "weak_signal", "invalid_risk_reference")


def metric(count, denominator, unit):
    """A zero denominator is unmeasured, never a fabricated zero rate."""
    return {"count": count, "denominator": denominator, "denominator_unit": unit,
            "rate": count / denominator if denominator else None}


def reason_metrics(counts, denominator, unit, reasons=()):
    return {key: metric(counts[key], denominator, unit) for key in sorted(set(counts) | set(reasons))}


def window_reasons(dataset, symbol, session, cutoff=None, mode="research"):
    """Inspect both benchmarks independently, retaining overlapping action reasons.

    Timing follows Dataset.window / inspect_action_capture. Unknown future bars or
    sidecar events never become dated dividend/Capital Gains evidence in shadow.
    Missing windows cannot establish action absence.
    """
    if mode not in {"research", "shadow"}:
        raise ValueError("Invalid diagnostic mode")
    cutoff = cutoff or cutoff_at(session).isoformat()
    bars = dataset.window(symbol, session, 61, cutoff, "research")
    if bars is None:
        return ["missing_or_unknown_history"]
    if mode == "shadow" and any(timestamp(b.known_at) > timestamp(cutoff) for b in bars):
        return ["data_not_yet_known"]
    reasons = []
    if any(b.dividend for b in bars):
        reasons.append("dividend")
    if any(b.split for b in bars):
        reasons.append("split")
    capture = inspect_action_capture(dataset, symbol, [b.session for b in bars], cutoff, mode)
    if capture.is_pending:
        reasons.append("data_not_yet_known")
    else:
        if capture.has_capital_gains:
            reasons.append("capital_gains")
        if not capture.is_confirmed:
            reasons.append("action_capture_unknown")
    return reasons


def candidate_reasons(dataset, config, session, signals, cutoff=None, mode="research"):
    """Preflight every configured ticker, even when benchmark gates stop Engine.

    Price/strength/risk filters are taken from production results only. A clean
    preflight on a blocked benchmark day is NOT a supported raw candidate.
    """
    cutoff = cutoff or cutoff_at(session).isoformat()
    results = {}
    for symbol in config.tickers:
        if not dataset.active(symbol, session, cutoff, mode):
            results[symbol] = ["not_in_asof_universe"]
            continue
        reasons = window_reasons(dataset, symbol, session, cutoff, mode)
        if not reasons and signals is not None and symbol in signals["excluded"]:
            reasons = [signals["excluded"][symbol]]
        results[symbol] = reasons
    return results


def select_candidates(engine, signals, boundary=None, state="NORMAL"):
    """Pure diagnostic replay of scan's calibration/top-k gates (no risk latch).

    The report uses NORMAL. REDUCED_EXPOSURE is an explicit library scenario,
    never inferred from historical returns or used to change production state.
    """
    if state not in {"NORMAL", "REDUCED_EXPOSURE"}:
        raise ValueError("Diagnostic state must be NORMAL or REDUCED_EXPOSURE")
    chosen, rejected = [], Counter()
    if not signals["supported"]:
        return chosen, rejected
    limit = 1 if state == "REDUCED_EXPOSURE" else engine.config.top_k
    for signal in signals["candidates"]:
        estimate = engine.calibration(signal, boundary)
        if not estimate["eligible"]:
            rejected[estimate["reason"]] += 1
        elif state == "REDUCED_EXPOSURE" and estimate["edge_ci"][0] <= max(0.002, engine.config.min_edge):
            rejected["reduced_exposure_edge_threshold"] += 1
        elif len(chosen) >= limit:
            rejected["below_top_k"] += 1
        else:
            chosen.append(signal)
    return chosen, rejected


def outcome_summary(records, dataset, as_of):
    """One holding-period outcome per selection; retain every status and exclusion."""
    statuses, reasons, exclusions, versions = Counter(), Counter(), Counter(), Counter()
    eligible_rows = []
    eligible = 0
    for signal, result in records:
        statuses[result["status"]] += 1
        if result["status"] != "COMPLETE":
            reasons[result.get("reason", "unknown")] += 1
            continue
        accepted, reason = evaluate_outcome_eligibility(signal, result, dataset, as_of, "research")
        if accepted:
            eligible += 1
            eligible_rows.append({**result, "session": signal["session"]})
        else:
            exclusions[reason] += 1
            versions[result.get("outcome_version", "v1_price_only")] += 1
    total, complete = len(records), statuses["COMPLETE"]
    outcomes = {"total": total, **reason_metrics(statuses, total, "holding_period_outcomes",
                                                ("COMPLETE", "PENDING", "UNRESOLVED")),
                "by_reason": reason_metrics(reasons, total, "holding_period_outcomes")}
    evaluation = {"policy": CASH_ACTION_REVIEW_POLICY,
                  "eligible_complete": metric(eligible, complete, "complete_holding_period_outcomes"),
                  "excluded_complete": metric(complete - eligible, complete, "complete_holding_period_outcomes"),
                  "by_reason": reason_metrics(exclusions, complete, "complete_holding_period_outcomes"),
                  "by_version": reason_metrics(versions, complete, "complete_holding_period_outcomes")}
    return outcomes, evaluation, eligible_rows


def pairing_summary(attempted, candidate_dates, spy_dates):
    paired = candidate_dates & spy_dates
    groups = {"attempted_signal_dates": attempted, "paired_signal_dates": paired,
              "candidate_only_signal_dates": candidate_dates - spy_dates,
              "spy_only_signal_dates": spy_dates - candidate_dates,
              "unmatched_signal_dates": attempted - paired}
    return {key: {**metric(len(days), len(attempted), "attempted_recommendation_dates"),
                  "dates": sorted(days)} for key, days in groups.items()}


def coverage_report(dataset, config, start=None, end=None, boundary=None, state="NORMAL"):
    """Fixed-model research replay, rolling past-only calibration by default.

    Optional boundary reproduces a validation fold's frozen calibration. All
    outcomes use the target period's end, as in validation. No Store mutations,
    risk-state simulation, revised membership, or capture reconstruction.
    """
    if len(dataset.sessions) < 61 and start is None:
        raise ValueError("Insufficient sessions for 61-session feature coverage")
    start, end = start or dataset.sessions[60], end or dataset.end
    if start > end or start < dataset.start or end > dataset.end:
        raise ValueError("Coverage period must be within dataset bounds")
    days = [s for s in dataset.sessions if start <= s <= end]
    if not days or boundary is not None and (boundary not in dataset.positions or boundary > days[0]):
        raise ValueError("Invalid coverage period or calibration boundary")
    if state not in {"NORMAL", "REDUCED_EXPOSURE"}:
        raise ValueError("Invalid diagnostic state")
    engine = Engine(dataset, config)
    benchmark_counts = {symbol: Counter() for symbol in ("SPY", "QQQ")}
    blocks, candidates, funnel, categories = Counter(), Counter(), Counter(), Counter()
    candidate_counts = Counter()
    records, spy_records, attempted, daily = [], [], set(), []
    as_of = cutoff_at(days[-1]).isoformat()
    for day in days:
        reasons = {symbol: window_reasons(dataset, symbol, day) for symbol in benchmark_counts}
        for symbol, values in reasons.items():
            benchmark_counts[symbol].update(values)
            benchmark_counts[symbol]["feature_computable"] += not values
        combined = {reason for values in reasons.values() for reason in values}
        blocks.update(combined)
        # Engine remains authoritative; unclassified failures are visible.
        try:
            signals = engine.signals(day)
        except ValueError as exc:
            signals = None
            if not combined:
                blocks["unclassified_engine_failure"] += 1
            error = str(exc)
        else:
            error = None
            if combined:
                raise ValueError("Coverage diagnostics disagree with Engine benchmark contract")
        details = candidate_reasons(dataset, config, day, signals)
        for values in details.values():
            candidates.update(values)
            candidate_counts["excluded" if values else "not_evaluated_benchmark_blocked" if signals is None else "supported"] += 1
        chosen, rejected = select_candidates(engine, signals, boundary, state) if signals else ([], Counter())
        for reason in rejected:
            funnel[reason + "_dates"] += 1
            funnel[reason + "_candidates"] += rejected[reason]
        raw = len(signals["candidates"]) if signals else 0
        funnel["raw_candidate_dates"] += raw > 0
        funnel["raw_candidates"] += raw
        funnel["calibration_attempts"] += raw if signals and signals["supported"] else 0
        funnel["signal_supported"] += signals is not None
        funnel["unsupported_regime_dates"] += bool(signals and not signals["supported"])
        funnel["recommendation_dates"] += bool(chosen)
        funnel["recommendations"] += len(chosen)
        if signals is None:
            category = "integrity_data_blocked"
        elif not signals["supported"]:
            category = "unsupported_market_regime"
        elif not raw:
            integrity = {"not_in_asof_universe", *WINDOW_REASONS}
            category = "integrity_data_blocked" if all(set(v) & integrity for v in details.values()) else "no_raw_signal"
        elif chosen:
            category = "recommendation_available"
        elif rejected["reduced_exposure_edge_threshold"]:
            category = "reduced_exposure_threshold"
        elif rejected["edge_not_supported"]:
            category = "edge_unsupported"
        else:
            category = "calibration_insufficient"
        categories[category] += 1
        daily.append({"session": day, "benchmark_reasons": reasons, "engine_error": error,
                      "raw_candidates": raw, "decision_category": category, "recommendations": len(chosen)})
        if chosen:
            attempted.add(day)
            records.extend((s, observe(s, dataset, config.horizon, as_of)) for s in chosen)
            b = dataset.by_ticker["SPY"][day]
            spy = {**chosen[0], "ticker": "SPY", "entry_reference": b.close,
                   "stop_reference": b.close * 0.9, "target_reference": b.close * 1.2}
            spy_records.append((spy, observe(spy, dataset, config.horizon, as_of)))
    return _assemble_report(dataset, config, days, boundary, state, benchmark_counts, blocks,
                            candidates, candidate_counts, funnel, categories, records,
                            spy_records, attempted, daily, as_of)


def _assemble_report(dataset, config, days, boundary, state, benchmarks, blocks, candidates,
                     candidate_counts, funnel, categories, records, spy_records, attempted, daily, as_of):
    total, ticker_total = len(days), len(days) * len(config.tickers)
    outcomes, evaluation, candidate_rows = outcome_summary(records, dataset, as_of)
    spy_outcomes, spy_evaluation, spy_rows = outcome_summary(spy_records, dataset, as_of)
    candidate_dates = {r["session"] for r in candidate_rows}
    spy_dates = {r["session"] for r in spy_rows}
    paired = candidate_dates & spy_dates
    matched_candidate = [{"session": day, "net_return": value}
                         for day, value in cohort_returns(candidate_rows) if day in paired]
    dividend_both = sum(all("dividend" in r for r in d["benchmark_reasons"].values()) for d in daily)
    date_keys = ("raw_candidate_dates", "unsupported_regime_dates", "insufficient_calibration_dates",
                 "edge_not_supported_dates", "reduced_exposure_edge_threshold_dates",
                 "below_top_k_dates", "recommendation_dates")
    decision = {key: metric(funnel[key], total, "target_trading_days") for key in date_keys}
    decision["no_trade_dates"] = metric(total - len(attempted), total, "target_trading_days")
    decision["recommendations"] = metric(len(records), total, "target_trading_days")
    decision["recommendations"]["rate_interpretation"] = "recommendations per trading day; not a probability"
    decision["by_category"] = reason_metrics(categories, total, "target_trading_days", (
        "integrity_data_blocked", "unsupported_market_regime", "no_raw_signal",
        "calibration_insufficient", "edge_unsupported", "reduced_exposure_threshold", "recommendation_available"))
    decision["calibration_attempts"] = metric(funnel["calibration_attempts"], funnel["raw_candidates"], "raw_candidates")
    decision["candidate_rejections"] = {
        r: metric(funnel[r + "_candidates"], funnel["calibration_attempts"], "calibration_attempts")
        for r in ("insufficient_calibration", "edge_not_supported", "reduced_exposure_edge_threshold", "below_top_k")}
    return {
        "schema": "coverage_diagnostic_v1", "period": {"start": days[0], "end": days[-1]},
        "dataset_period": {"start": dataset.start, "end": dataset.end,
                           "trading_days": len(dataset.sessions), "feature_window_sessions": 61},
        "dataset_id": dataset.id, "model_id": config.model_id, "config": config.payload(),
        "mode": "research", "quality": dataset.metadata["quality"], "source": dataset.metadata["source"],
        "outcome_contract": DEFAULT_OUTCOME_VERSION, "outcome_as_of": as_of,
        "calibration": {"boundary": boundary, "kind": "frozen" if boundary else "rolling_past_only"},
        "risk_state_scenario": state,
        "trading_days": {"total": total, "signal_attempted": metric(total, total, "target_trading_days"),
                         "signal_supported": metric(funnel["signal_supported"], total, "target_trading_days"),
                         "signal_blocked": metric(total - funnel["signal_supported"], total, "target_trading_days")},
        "signal_blocks": {"by_reason": reason_metrics(blocks, total, "target_trading_days", WINDOW_REASONS),
                          "both_benchmarks_dividend": metric(dividend_both, total, "target_trading_days"),
                          "counting": "union across SPY/QQQ per reason; reasons overlap"},
        "benchmark": {s: {"by_reason": reason_metrics(c, total, "target_trading_days", WINDOW_REASONS + ("feature_computable",))}
                      for s, c in benchmarks.items()},
        "candidate_evaluations": {"total": ticker_total,
            **reason_metrics(candidate_counts, ticker_total, "configured_ticker_sessions",
                             ("supported", "excluded", "not_evaluated_benchmark_blocked")),
            "by_reason": reason_metrics(candidates, ticker_total, "configured_ticker_sessions", CANDIDATE_REASONS),
            "counting": "all configured ticker-session preflights; reasons overlap; supported = Engine raw candidate; clean preflight on blocked benchmark is not evaluated"},
        "decision_funnel": decision, "outcomes": outcomes, "evaluation": evaluation,
        "pairing": pairing_summary(attempted, candidate_dates, spy_dates),
        "matched_SPY": {"outcomes": spy_outcomes, "evaluation": spy_evaluation,
                        "metrics": metrics([r for r in spy_rows if r["session"] in paired])},
        "matched_candidate": metrics(matched_candidate), "daily": daily,
        "limitations": [
            "Fixed-model research replay, not stored/live recommendations or untouched OOS alpha evidence",
            "Current Dataset membership is used as supplied; historical membership is not reconstructed",
            "Research assumes historical bar availability; shadow timing is not inferred from this replay",
            "No operational risk latch simulation; reduced exposure is only an explicit scenario",
            "Action reasons overlap and are not additive; removing a guard is not a measured counterfactual",
            "Zero observed Capital Gains with unknown capture does not establish no distributions",
            "Candidate market/strength filters are not evaluated when benchmarks block",
            "Outcomes are holding-period only; zero COMPLETE yields null evaluation rates",
            "Code and deterministic tests do not establish unattended multi-day production stability",
            "Synthetic coverage is not real alpha evidence"],
    }


def stored_run_evidence(store):
    """Read-only operational inventory, deliberately not a stability certification."""
    rows = store.db.execute("SELECT mode,status,COUNT(*) AS runs,COUNT(DISTINCT session) AS dates,"
                            "MIN(session) AS first_session,MAX(session) AS last_session "
                            "FROM runs GROUP BY mode,status ORDER BY mode,status").fetchall()
    return {"by_mode_status": [dict(row) for row in rows],
            "unattended_multi_day_stability": "NOT_ESTABLISHED",
            "basis": "stored run inventory cannot establish scheduler, lock, or unattended execution"}
