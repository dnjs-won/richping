"""Rolling transforms of arbitrary causal scalars; no indicator-specific rules."""

from dataclasses import dataclass, replace
import math
from typing import ClassVar

from ...core import digest
from ..contracts import JsonObject, payload
from .contracts import FeatureSpec, ScalarSeries, Spec, positive_int, result
from .continuity import CONTINUITY_VERSION, is_contiguous


@dataclass(frozen=True, slots=True)
class PercentileSpec(Spec):
    window: int
    min_history: int
    include_current: bool = True
    ties: str = "midrank"
    continuity: str = CONTINUITY_VERSION
    name: ClassVar[str] = "rolling_percentile"
    version: ClassVar[str] = "rolling_empirical_midrank_v1"

    def __post_init__(self):
        _window(self.window, self.min_history)
        if (self.include_current is not True or self.ties != "midrank"
                or self.continuity != CONTINUITY_VERSION):
            raise ValueError("Unsupported percentile convention")


@dataclass(frozen=True, slots=True)
class ZScoreSpec(Spec):
    window: int
    min_history: int
    ddof: int
    include_current: bool = True
    zero_variance: str = "undefined"
    continuity: str = CONTINUITY_VERSION
    name: ClassVar[str] = "rolling_zscore"
    version: ClassVar[str] = "rolling_zscore_ddof_v1"

    def __post_init__(self):
        _window(self.window, self.min_history)
        if type(self.ddof) is not int or self.ddof not in (0, 1) or self.min_history <= self.ddof:
            raise ValueError("ddof must be 0/1 and min_history > ddof")
        if (self.include_current is not True or self.zero_variance != "undefined"
                or self.continuity != CONTINUITY_VERSION):
            raise ValueError("Unsupported z-score convention")


def _window(window, min_history):
    positive_int(window)
    positive_int(min_history)
    if min_history > window:
        raise ValueError("min_history exceeds window")


def _transform(series, spec, calculate):
    if not isinstance(series, ScalarSeries):
        raise ValueError("Immutable causal ScalarSeries required")
    points = series.points[-spec.window:]
    definition = FeatureSpec(spec.name, spec.version, JsonObject.of({
        **spec.definition.parameters.unpack(), "source": payload(series.source),
        "missing_policy": "retain_slots_fail_closed"}))
    status, reason, output = "READY", None, None
    if not is_contiguous(points, series.timeframe):
        status, reason = "NOT_READY", "noncontiguous_history"
    elif len(points) < spec.min_history:
        status, reason = "NOT_READY", "insufficient_history"
    elif any(p.status != "READY" for p in points):
        status = "UNDEFINED" if any(p.status == "UNDEFINED" for p in points) else "NOT_READY"
        reason = "unavailable_input"
    else:
        try:
            output, reason = calculate(tuple(p.value for p in points))
        except (OverflowError, ValueError):
            reason = "nonfinite_result"
        if reason:
            status = "UNDEFINED"
    r = result(definition, series.symbol, series.timeframe, series.as_of, points,
               output, status, reason)
    return replace(r, input_hash=digest({"points": payload(points),
                                        "source_input_hash": series.input_hash}))


def rolling_percentile(series: ScalarSeries, spec: PercentileSpec):
    def calculate(xs):
        current = xs[-1]
        rank = (sum(x < current for x in xs) + .5 * sum(x == current for x in xs)) / len(xs)
        return {"percentile": rank}, None
    return _transform(series, spec, calculate)


def rolling_zscore(series: ScalarSeries, spec: ZScoreSpec):
    def calculate(xs):
        mean = math.fsum(x / len(xs) for x in xs)
        variance = math.fsum((x - mean) ** 2 for x in xs) / (len(xs) - spec.ddof)
        if variance == 0:
            return None, "zero_variance"
        value = (xs[-1] - mean) / math.sqrt(variance)
        if not math.isfinite(variance) or not math.isfinite(value):
            return None, "nonfinite_result"
        return {"zscore": value}, None
    return _transform(series, spec, calculate)


@dataclass(frozen=True, slots=True)
class NormalizeSpec(Spec):
    numerator_field: str
    denominator_field: str
    alignment: str = "same_symbol_timeframe_as_of_end"
    denominator_policy: str = "strictly_positive"
    name: ClassVar[str] = "scale_normalization"
    version: ClassVar[str] = "positive_causal_scale_v1"

    def __post_init__(self):
        if not self.numerator_field or not self.denominator_field:
            raise ValueError("Explicit scalar fields required")
        if (self.alignment, self.denominator_policy) != (
                "same_symbol_timeframe_as_of_end", "strictly_positive"):
            raise ValueError("Unsupported normalization convention")


def normalize(numerator, denominator, spec: NormalizeSpec):
    """Require aligned causal snapshots; unavailable/nonpositive scales fail closed."""
    if (numerator.symbol, numerator.timeframe, numerator.as_of, numerator.input_end_at) != (
            denominator.symbol, denominator.timeframe, denominator.as_of, denominator.input_end_at):
        raise ValueError("Unaligned causal operands")
    definition = FeatureSpec(spec.name, spec.version, JsonObject.of({
        **spec.definition.parameters.unpack(), "numerator": payload(numerator.specification),
        "denominator": payload(denominator.specification)}))
    status, reason, output = "READY", None, None
    if numerator.status != "READY" or denominator.status != "READY":
        status = "UNDEFINED" if "UNDEFINED" in (numerator.status, denominator.status) else "NOT_READY"
        reason = "unavailable_input"
    else:
        n = numerator.values.unpack().get(spec.numerator_field)
        d = denominator.values.unpack().get(spec.denominator_field)
        if any(type(x) not in (int, float) for x in (n, d)):
            raise ValueError("Named numeric scalar fields required")
        if d <= 0:
            status, reason = "UNDEFINED", "nonpositive_scale"
        else:
            quotient = n / d
            if not math.isfinite(quotient):
                status, reason = "UNDEFINED", "nonfinite_result"
            else:
                output = {"normalized": quotient}
    # Count operands, rather than incorrectly adding overlapping bar histories.
    inputs = (numerator, denominator) if numerator.input_end_at is not None else ()
    r = result(definition, numerator.symbol, numerator.timeframe, numerator.as_of,
               inputs, output, status, reason, input_end_at=numerator.input_end_at)
    return replace(r, input_hash=digest(payload((numerator, denominator))))
