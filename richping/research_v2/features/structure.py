"""Confirmed price geometry. No position, valid-HL, BOS, or exit semantics."""

from dataclasses import dataclass, replace
from datetime import datetime
import math
from typing import ClassVar, Protocol

from ...core import digest, timestamp
from ..contracts import JsonObject, ReplayContext, payload
from .contracts import FeatureResult, FeatureSpec, Spec, completed_bars, positive_int, result
from .continuity import is_contiguous


@dataclass(frozen=True, slots=True)
class FractalSpec(Spec):
    left: int
    right: int
    ties: str = "strict"
    continuity: str = "xnys_completed_grid"
    name: ClassVar[str] = "confirmed_swings"
    version: ClassVar[str] = "fractal_k_right_strict_v1"

    def __post_init__(self):
        positive_int(self.left)
        positive_int(self.right)
        if self.ties != "strict" or self.continuity != "xnys_completed_grid":
            raise ValueError("Unsupported fractal convention")


@dataclass(frozen=True, slots=True)
class SwingEvent:
    kind: str
    pivot_at: datetime
    confirmed_at: datetime
    pivot_price: float
    confirmation_version: str
    specification_hash: str

    def __post_init__(self):
        if self.kind not in {"SWING_HIGH_CONFIRMED", "SWING_LOW_CONFIRMED"}:
            raise ValueError("Unsupported swing kind")
        for name in ("pivot_at", "confirmed_at"):
            object.__setattr__(self, name, timestamp(getattr(self, name)))
        if self.pivot_at >= self.confirmed_at:
            raise ValueError("Right-bar confirmation must follow pivot")
        if type(self.pivot_price) not in (int, float) or not math.isfinite(self.pivot_price) or self.pivot_price <= 0:
            raise ValueError("Positive finite pivot price required")
        if not self.confirmation_version or not self.specification_hash:
            raise ValueError("Swing confirmation provenance required")


class SwingDetector(Protocol):
    def __call__(self, context: ReplayContext, symbol: str, timeframe: str,
                 spec: FractalSpec) -> FeatureResult: ...


def confirmed_swings(context, symbol, timeframe, spec: FractalSpec):
    bars = completed_bars(context, symbol, timeframe)
    events, complete_windows = [], 0
    for i in range(spec.left, len(bars) - spec.right):
        window = bars[i - spec.left:i + spec.right + 1]
        if not is_contiguous(window, timeframe):
            continue
        complete_windows += 1
        pivot = bars[i]
        neighbors = window[:spec.left] + window[spec.left + 1:]
        confirmed_at = max(b.known_at for b in window)
        for kind, field, compare in (("SWING_HIGH_CONFIRMED", "high", max),
                                     ("SWING_LOW_CONFIRMED", "low", min)):
            price = getattr(pivot, field)
            extreme = compare(getattr(b, field) for b in neighbors)
            strict = price > extreme if field == "high" else price < extreme
            if strict:
                events.append(SwingEvent(kind, pivot.end_at, confirmed_at, price, spec.version, spec.hash))
    events.sort(key=lambda e: (e.confirmed_at, e.pivot_at, e.kind))
    if not complete_windows:
        reason = "insufficient_history" if len(bars) < spec.left + spec.right + 1 else "insufficient_contiguous_history"
        return result(spec, symbol, timeframe, context.as_of, bars, status="NOT_READY", reason=reason)
    return result(spec, symbol, timeframe, context.as_of, bars, {"events": payload(events)})


def classify_swings(swings: FeatureResult):
    """Compare same-kind swings in (confirmed_at,pivot_at,kind) order.

    Equal confirmed highs/lows are EQH/EQL, not HH/HL/LH/LL. A first swing has
    classification null. Both kinds may confirm on one outside candle.
    """
    definition = FeatureSpec("swing_classification", "confirmed_same_kind_comparison_v1",
        JsonObject.of({"source": payload(swings.specification), "equal": "EQH_EQL",
                       "first": "null", "order": "confirmed_at,pivot_at,kind"}))
    if swings.status != "READY":
        return replace(swings, specification=definition, input_hash=swings.hash)
    raw = swings.values.unpack().get("events")
    if not isinstance(raw, list):
        raise ValueError("Confirmed swing events required")
    events = tuple(SwingEvent(**e) for e in raw)
    if any(e.confirmed_at > swings.as_of for e in events):
        raise ValueError("Future swing confirmation")
    if events != tuple(sorted(events, key=lambda e: (e.confirmed_at, e.pivot_at, e.kind))):
        raise ValueError("Confirmed swing order required")
    if len({(e.kind, e.pivot_at) for e in events}) != len(events):
        raise ValueError("Duplicate confirmed swing")
    previous, output = {}, []
    for event in events:
        prior = previous.get(event.kind)
        high = event.kind == "SWING_HIGH_CONFIRMED"
        label = None
        if prior is not None:
            if event.pivot_price == prior.pivot_price:
                label = "EQH" if high else "EQL"
            elif event.pivot_price > prior.pivot_price:
                label = "HH" if high else "HL"
            else:
                label = "LH" if high else "LL"
        output.append({**payload(event), "classification": label,
                       "previous_pivot_at": payload(prior.pivot_at) if prior else None})
        previous[event.kind] = event
    return replace(swings, specification=definition, values=JsonObject.of({"events": output}),
                   input_hash=digest(payload(swings)))
