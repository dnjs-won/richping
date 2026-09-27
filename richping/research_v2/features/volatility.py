"""True range and SMA-seeded Wilder ATR over completed observations."""

from dataclasses import dataclass
import math
from typing import ClassVar

from .contracts import Spec, completed_bars, positive_int, result


@dataclass(frozen=True, slots=True)
class TRSpec(Spec):
    first_bar: str = "high_minus_low"
    name: ClassVar[str] = "true_range"
    version: ClassVar[str] = "true_range_first_high_low_v1"

    def __post_init__(self):
        if self.first_bar != "high_minus_low":
            raise ValueError("Unsupported first TR convention")


@dataclass(frozen=True, slots=True)
class ATRSpec(Spec):
    period: int
    min_history: int
    smoothing: str = "wilder"
    seed: str = "sma_first_period_tr"
    first_bar: str = "high_minus_low"
    name: ClassVar[str] = "atr"
    version: ClassVar[str] = "atr_wilder_sma_seed_first_high_low_v1"

    def __post_init__(self):
        positive_int(self.period)
        positive_int(self.min_history)
        if self.min_history < self.period:
            raise ValueError("ATR min_history must cover seed period")
        if (self.smoothing, self.seed, self.first_bar) != (
                "wilder", "sma_first_period_tr", "high_minus_low"):
            raise ValueError("Unsupported ATR convention")


def _ranges(bars):
    return tuple(max(b.high - b.low, abs(b.high - bars[i - 1].close),
                     abs(b.low - bars[i - 1].close)) if i else b.high - b.low
                 for i, b in enumerate(bars))


def true_range(context, symbol, timeframe, spec: TRSpec):
    bars = completed_bars(context, symbol, timeframe)[-2:]
    if not bars:
        return result(spec, symbol, timeframe, context.as_of, bars,
                      status="NOT_READY", reason="insufficient_history")
    return result(spec, symbol, timeframe, context.as_of, bars, {"true_range": _ranges(bars)[-1]})


def atr(context, symbol, timeframe, spec: ATRSpec):
    bars = completed_bars(context, symbol, timeframe)
    if len(bars) < spec.min_history:
        return result(spec, symbol, timeframe, context.as_of, bars,
                      status="NOT_READY", reason="insufficient_history")
    ranges = _ranges(bars)
    value = math.fsum(x / spec.period for x in ranges[:spec.period])
    for tr in ranges[spec.period:]:
        value = (1 - 1 / spec.period) * value + tr / spec.period
    return result(spec, symbol, timeframe, context.as_of, bars, {"atr": value})
