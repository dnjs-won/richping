"""Recommendation/cohort diagnostics; deliberately not a portfolio NAV ledger."""

from collections import defaultdict
import math

import numpy as np


def cohort_returns(rows):
    dates = defaultdict(list)
    for r in rows:
        dates[r["session"]].append(r["net_return"])
    return [(day, float(np.mean(values))) for day, values in sorted(dates.items())]


def block_ci(rows, samples=500, seed=7, alpha=0.05, block=5):
    """Resample contiguous signal-date clusters, keeping same-date stocks together."""
    x = np.array([value for _, value in cohort_returns(rows)])
    if len(x) < 2:
        return None
    rng = np.random.default_rng(seed)
    block = min(block, len(x))
    starts = rng.integers(0, len(x), size=(samples, math.ceil(len(x) / block)))
    indices = (starts[..., None] + np.arange(block)) % len(x)
    means = x[indices.reshape(samples, -1)[:, :len(x)]].mean(axis=1)
    return [float(v) for v in np.quantile(means, [alpha / 2, 1 - alpha / 2])]


def metrics(rows):
    x = np.array([r["net_return"] for r in rows])
    if len(x) == 0:
        return {"samples": 0, "expectancy": None, "win_rate": None, "profit_factor": None,
                "cohort_drawdown": None, "sharpe": None, "sortino": None, "calmar": None}
    wins, losses = x[x > 0], x[x < 0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(-losses.mean()) if len(losses) else None
    curve = np.cumprod(1 + np.array([v for _, v in cohort_returns(rows)]))
    peaks = np.maximum.accumulate(np.r_[1.0, curve])[1:]
    cutoff = float(np.quantile(x, 0.05))
    return {"samples": len(x), "signal_dates": len(cohort_returns(rows)), "win_rate": float(np.mean(x > 0)),
            "average_win": avg_win, "average_loss": avg_loss,
            "payoff_ratio": avg_win / avg_loss if avg_loss else None,
            "profit_factor": float(wins.sum() / -losses.sum()) if len(losses) else None,
            "expectancy": float(x.mean()), "expected_return": float(x.mean()),
            "expected_shortfall": float(x[x <= cutoff].mean()), "tail_loss": float(x.min()),
            "cohort_drawdown": float(np.min(curve / peaks - 1)),
            "sharpe": None, "sortino": None, "calmar": None,
            "portfolio_max_drawdown": None,
            "metric_basis": "recommendation returns; drawdown is sequential signal-date cohort diagnostic, not portfolio NAV"}


def estimate(rows, config):
    m = metrics(rows)
    dates = len(cohort_returns(rows))
    if len(rows) < config.min_samples or dates < config.min_dates:
        return {"eligible": False, "reason": "insufficient_calibration", "samples": len(rows),
                "signal_dates": dates, "expected_return": None, "expected_loss": None,
                "expected_rr": None, "confidence": None, "edge_ci": None}
    ci = block_ci(rows, config.bootstrap_samples, config.seed, block=max(5, config.horizon))
    mean = float(np.mean([x for _, x in cohort_returns(rows)]))
    eligible = ci[0] > config.min_edge and m["average_loss"] is not None
    return {"eligible": eligible, "reason": "edge_supported" if eligible else "edge_not_supported",
            "samples": len(rows), "signal_dates": dates, "expected_return": mean,
            "expected_loss": m["average_loss"], "expected_rr": m["payoff_ratio"],
            "confidence": m["win_rate"], "confidence_basis": "historical candidate win frequency, not calibrated forecast probability",
            "edge_ci": ci}


def risk_decision(rows, previous="NORMAL"):
    if previous == "PAUSED":
        return "PAUSED", "performance_pause_latched"
    if len(rows) < 30:
        return "NORMAL", "risk_sample_warmup"
    recent = sorted(rows, key=lambda r: (r["session"], r.get("ticker", "")))[-30:]
    m = metrics(recent)
    if m["expectancy"] <= -0.02 or m["cohort_drawdown"] <= -0.15:
        return "PAUSED", "recent_edge_or_drawdown_breach"
    if m["expectancy"] < 0:
        return "REDUCED_EXPOSURE", "recent_negative_expectancy"
    return "NORMAL", "recent_edge_nonnegative"


def promotion_gate(evidence):
    """Fail closed. No promotion writer or live-order authority exists in MVP."""
    reasons = []
    required = {"point_in_time_data": True, "complete_outcomes": True,
                "regime_stable": True, "parameter_stable": True,
                "fresh_shadow": True, "multiple_testing_corrected": True}
    for key, value in required.items():
        if evidence.get(key) is not value:
            reasons.append(key)
    thresholds = {"oos_samples": 200, "signal_dates": 60, "folds": 3, "profit_factor": 1.1}
    for key, minimum in thresholds.items():
        value = evidence.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
            reasons.append(key)
    for key in ("paired_improvement_ci_low", "stress_expectancy"):
        value = evidence.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            reasons.append(key)
    for key in ("drawdown_noninferior", "tail_noninferior"):
        if evidence.get(key) is not True:
            reasons.append(key)
    return {"decision": "ELIGIBLE_FOR_SHADOW_REVIEW" if not reasons else "REJECT", "reasons": reasons}


def evaluate_outcome_eligibility(snapshot, outcome, dataset=None, as_of=None, mode="research"):
    """Evaluate whether an outcome is eligible under CASH_ACTION_REVIEW_POLICY ("cash_action_review_v1").

    Pure policy function: does not modify snapshot or outcome.
    Returns: (is_eligible: bool, reason: str | None)
    """
    import math
    from .core import (
        LEGACY_OUTCOME_VERSION,
        OUTCOME_VERSION_V1,
        OUTCOME_VERSION_V2,
        OUTCOME_VERSION_V3,
        SUPPORTED_OUTCOME_VERSIONS,
        next_sessions,
    )
    from .data import inspect_action_capture

    if outcome.get("status") != "COMPLETE":
        return False, outcome.get("reason", "status_not_complete")

    snap_version = snapshot.get("outcome_version", LEGACY_OUTCOME_VERSION)
    outcome_version = outcome.get("outcome_version", LEGACY_OUTCOME_VERSION)

    # 1. Snapshot and outcome version mismatch
    if snap_version != outcome_version:
        return False, "outcome_version_mismatch"

    # 2. Unsupported version
    if outcome_version not in SUPPORTED_OUTCOME_VERSIONS:
        return False, "unsupported_outcome_version"

    # 3. v2 contract is unconditionally excluded under cash_action_review_v1
    if outcome_version == OUTCOME_VERSION_V2:
        return False, "legacy_v2_unverified_contract"

    # 4. v1 and v3 contract verification:
    # Defend against historical buggy stored outcomes by verifying point-in-time known-at,
    # corporate actions, and action-capture confirmation at observed_at.
    if outcome_version in (OUTCOME_VERSION_V1, OUTCOME_VERSION_V3):
        if dataset is None:
            return False, "action_capture_unknown"
        symbol = snapshot["ticker"]
        horizon = outcome.get("horizon") or snapshot.get("holding_period", 5)
        days = next_sessions(snapshot["session"], horizon)
        bars = [dataset.by_ticker.get(symbol, {}).get(s) for s in days]
        if any(b is None for b in bars):
            return False, "missing_or_delisted_session"
        if any(b.split for b in bars):
            return False, "stock_split_requires_accounting"

        obs_at = outcome.get("observed_at") or as_of
        ac = inspect_action_capture(dataset, symbol, days, as_of=obs_at, mode=mode)
        if mode == "shadow" and ac.is_pending:
            return False, ac.reason or "data_not_yet_known"
        if ac.has_capital_gains:
            return False, "unsupported_capital_gains_distribution"
        if any(b.dividend > 0 for b in bars):
            return False, "unverified_cash_dividend_event"
        if not ac.is_confirmed:
            return False, "action_capture_unknown"

        origin = dataset.by_ticker.get(symbol, {}).get(snapshot["session"])
        if origin is None or not math.isclose(origin.close, snapshot["entry_reference"], rel_tol=1e-8):
            return False, "price_vintage_changed"

        return True, None

    return False, "unsupported_outcome_version"
