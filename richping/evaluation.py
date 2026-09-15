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
