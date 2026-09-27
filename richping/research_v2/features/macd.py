"""Price-unit MACD only. No crosses, thresholds, regimes, or decisions."""

from dataclasses import dataclass
from typing import ClassVar

from ...core import digest
from ..contracts import JsonObject, payload
from .contracts import (FeatureSpec, ScalarPoint, ScalarSeries, Spec, completed_bars,
                        positive_int, result)
from .moving import recursive_ema


@dataclass(frozen=True, slots=True)
class MACDSpec(Spec):
    fast: int
    slow: int
    signal: int
    min_history: int
    seed: str = "first_observation"
    signal_start: str = "first_macd_observation"
    field: str = "close"
    name: ClassVar[str] = "macd"
    version: ClassVar[str] = "macd_first_observation_recursive_v1"

    def __post_init__(self):
        for value in (self.fast, self.slow, self.signal, self.min_history):
            positive_int(value)
        if self.fast >= self.slow:
            raise ValueError("MACD requires fast < slow")
        if (self.seed, self.signal_start, self.field) != (
                "first_observation", "first_macd_observation", "close"):
            raise ValueError("Unsupported MACD convention")


def _values(bars, spec):
    closes = tuple(b.close for b in bars)
    lines = tuple(f - s for f, s in zip(recursive_ema(closes, spec.fast),
                                      recursive_ema(closes, spec.slow)))
    signals = recursive_ema(lines, spec.signal)
    return tuple({"macd_line": m, "signal_line": s, "histogram": m - s}
                 for m, s in zip(lines, signals))


def macd(context, symbol, timeframe, spec: MACDSpec):
    bars = completed_bars(context, symbol, timeframe)
    if len(bars) < spec.min_history:
        return result(spec, symbol, timeframe, context.as_of, bars,
                      status="NOT_READY", reason="insufficient_history")
    return result(spec, symbol, timeframe, context.as_of, bars, _values(bars, spec)[-1])


def macd_series(context, symbol, timeframe, spec: MACDSpec, *, field):
    """Causal scalar projection, with unavailable warmup points retained.

    A delayed input may recompute this current vintage. Each historical point's
    known_at is the maximum arrival of its entire EMA prefix, never its end alone.
    Previously returned series/results remain immutable.
    """
    if field not in {"macd_line", "signal_line", "histogram"}:
        raise ValueError("Unknown MACD field")
    bars = completed_bars(context, symbol, timeframe)
    points, known = [], None
    for count, (bar, values) in enumerate(zip(bars, _values(bars, spec)), 1):
        known = max(known, bar.known_at) if known is not None else bar.known_at
        ready = count >= spec.min_history
        points.append(ScalarPoint(bar.end_at, known, values[field] if ready else None,
                                  "READY" if ready else "NOT_READY",
                                  None if ready else "insufficient_history"))
    source = FeatureSpec("scalar_projection", "feature_field_v1",
                         JsonObject.of({"source": payload(spec.definition), "field": field}))
    return ScalarSeries(symbol, timeframe, context.as_of, source, tuple(points), digest(payload(bars)))
