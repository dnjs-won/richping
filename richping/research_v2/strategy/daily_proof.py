"""Offline readiness denominators; price-only diagnostics never certify PIT."""

from collections import Counter
from hashlib import sha256

from ...core import canonical
from ..contracts import payload
from .daily_input import prepare_daily
from ..features.moving import recursive_ema
from .daily_trend import CANONICAL as TREND, classify_daily_trend
from .daily_exhaustion import CANONICAL as EXHAUSTION, classify_daily_exhaustion, exhaustion_label


def readiness_proof(vintage):
    counts, reasons, joint = Counter(), Counter(), []
    first_trend = first_exhaustion = None
    fingerprint = sha256()
    for bar in vintage.bars:
        resolution = prepare_daily(vintage, bar.known_at)
        p = resolution.prefix
        trend, exhaustion = classify_daily_trend(p, bar.known_at), classify_daily_exhaustion(p, bar.known_at)
        counts.update(["trend:"+trend.status, "exhaustion:"+exhaustion.status,
                       "trend_state:"+trend.state, "exhaustion_state:"+exhaustion.state])
        if p.input_reason:
            reasons.update([p.input_reason])
        if trend.status == "READY" and first_trend is None:
            first_trend = bar.session
        if exhaustion.status == "READY" and first_exhaustion is None:
            first_exhaustion = bar.session
        if trend.status == exhaustion.status == "READY":
            joint.append(bar.session)
        fingerprint.update(canonical({"transform": resolution.transform.unpack(),
                                      "trend": payload(trend), "exhaustion": payload(exhaustion)}).encode())
    return {"schema_version": "daily_readiness_proof_v1", "dataset_id": vintage.dataset_id,
            "content_hash": vintage.content_hash, "observations": len(vintage.bars),
            "eligible_input_observations": len(vintage.bars)-sum(reasons.values()),
            "trend_READY": counts["trend:READY"], "trend_UNAVAILABLE": counts["trend:UNAVAILABLE"],
            "exhaustion_READY": counts["exhaustion:READY"],
            "exhaustion_UNAVAILABLE": counts["exhaustion:UNAVAILABLE"],
            "first_trend_READY_session": first_trend, "first_exhaustion_READY_session": first_exhaustion,
            "joint_READY_count": len(joint), "joint_READY_range": [joint[0], joint[-1]] if joint else None,
            "BULLISH": counts["trend_state:BULLISH"], "NOT_BULLISH": counts["trend_state:NOT_BULLISH"],
            "NORMAL": counts["exhaustion_state:NORMAL"], "EXTENDED": counts["exhaustion_state:EXTENDED"],
            "input_UNAVAILABLE_reasons": dict(reasons), "state_stream_hash": fingerprint.hexdigest(),
            "network_calls": 0, "profitability": "NOT_RUN", "entry_outcome": "NOT_EVALUATED",
            "price_only_diagnostic": price_only_diagnostic(vintage)}


def price_only_diagnostic(vintage):
    """Arithmetic on captured prices, not PreparedDailyPrefix or real READY states.

    It answers whether enough observations exist if units/action evidence can
    eventually be certified. No fabricated action fixture admits these prices.
    """
    closes = [b.close for b in vintage.bars]
    ema50 = recursive_ema(closes, TREND.ema_spec.span)
    macd = EXHAUSTION.macd_spec
    lines = [a-b for a, b in zip(recursive_ema(closes, macd.fast), recursive_ema(closes, macd.slow))]
    counts = Counter()
    trend_n = TREND.ema_spec.min_history+TREND.semantics["slope_lag_observations"]
    exhaustion_n = EXHAUSTION.first_ready_count
    for index, close in enumerate(closes):
        n = index+1
        if n >= trend_n:
            counts["BULLISH" if close > ema50[index] and ema50[index] > ema50[index-5] else "NOT_BULLISH"] += 1
        if n >= exhaustion_n:
            xs = lines[index+1-EXHAUSTION.percentile_spec.window:index+1]
            rank = (sum(x < xs[-1] for x in xs)+.5*sum(x == xs[-1] for x in xs))/len(xs)
            counts[exhaustion_label(lines[index], rank)] += 1
    return {"evidence": "PRICE_ONLY_ARITHMETIC_NOT_ELIGIBLE_DAILY_STATES_NOT_PIT",
            "trend_required_N": trend_n, "exhaustion_required_N": exhaustion_n,
            "trend_numeric_boundary_session": vintage.bars[trend_n-1].session if len(closes) >= trend_n else None,
            "exhaustion_numeric_boundary_session": vintage.bars[exhaustion_n-1].session if len(closes) >= exhaustion_n else None,
            "observations_with_joint_numeric_warmup": max(0, len(closes)-exhaustion_n+1),
            "conditional_labels": dict(counts), "eligible_READY_claim": False}
