"""Detached feature values. No dataset, store, loader, or cache capability."""

from dataclasses import asdict, dataclass
from datetime import datetime
import math

from ...core import digest, ticker, timestamp
from ..contracts import JsonObject, ReplayContext, TIMEFRAMES, nonempty, payload
from .continuity import CONTINUITY_VERSION, is_contiguous, slot_bounds
from ..sessions import (EXTENDED, bar_profile, profile_for_continuity, session_date,
                        validate_extended_metadata, EXTENDED_AGGREGATION)


def positive_int(value):
    if type(value) is not int or value < 1:
        raise ValueError("Positive integer required")


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    name: str
    version: str
    parameters: JsonObject

    def __post_init__(self):
        nonempty(self.name)
        nonempty(self.version)
        if not isinstance(self.parameters, JsonObject):
            raise ValueError("Immutable parameters required")

    @property
    def hash(self):
        return digest(payload(self))


class Spec:
    """Small value adapter shared by frozen parameter dataclasses."""

    __slots__ = ()

    @property
    def definition(self):
        return FeatureSpec(self.name, self.version, JsonObject.of(asdict(self)))

    @property
    def hash(self):
        return self.definition.hash


def validate_status(status, reason, value_present):
    if status not in {"READY", "NOT_READY", "UNDEFINED"}:
        raise ValueError("Invalid feature status")
    if status == "READY":
        if reason is not None or not value_present:
            raise ValueError("READY requires values and no reason")
    elif value_present or not isinstance(reason, str) or not reason:
        raise ValueError("Unavailable result requires a reason and no values")


@dataclass(frozen=True, slots=True)
class FeatureResult:
    specification: FeatureSpec
    symbol: str
    timeframe: str
    as_of: datetime
    values: JsonObject
    status: str
    reason: str | None
    input_end_at: datetime | None
    input_count: int
    input_hash: str

    def __post_init__(self):
        identity(self.symbol, self.timeframe)
        if not isinstance(self.specification, FeatureSpec) or not isinstance(self.values, JsonObject):
            raise ValueError("Immutable feature specification/values required")
        object.__setattr__(self, "as_of", timestamp(self.as_of))
        if type(self.input_count) is not int or self.input_count < 0:
            raise ValueError("Nonnegative input count required")
        if self.input_end_at is not None:
            object.__setattr__(self, "input_end_at", timestamp(self.input_end_at))
            if self.input_end_at > self.as_of:
                raise ValueError("Future feature input")
        if (self.input_end_at is None) != (self.input_count == 0):
            raise ValueError("Input end/count mismatch")
        nonempty(self.input_hash)
        validate_status(self.status, self.reason, bool(self.values.unpack()))

    @property
    def specification_hash(self):
        return self.specification.hash

    @property
    def hash(self):
        return digest(payload(self))


def identity(symbol, timeframe):
    if ticker(symbol) != symbol or timeframe not in TIMEFRAMES:
        raise ValueError("Unsupported symbol/timeframe")


def completed_bars(context, symbol, timeframe, continuity=CONTINUITY_VERSION):
    if not isinstance(context, ReplayContext):
        raise ValueError("Detached ReplayContext required")
    identity(symbol, timeframe)
    profile = profile_for_continuity(continuity)
    if any(bar_profile(b) != profile.name for b in context.bars):
        raise ValueError("Feature/session continuity mismatch")
    bars = tuple(sorted(context.query(symbol, timeframe), key=lambda b: b.end_at))
    if len({b.end_at for b in bars}) != len(bars) or len({b.dataset_id for b in bars}) > 1:
        raise ValueError("Duplicate or mixed input vintage")
    if any(b.corporate_action != "NONE_CONFIRMED" for b in bars):
        raise ValueError("Unsupported corporate action")
    if any((b.start_at, b.end_at) != slot_bounds(b.end_at, timeframe, continuity)
           or b.session != session_date(b.end_at) for b in bars):
        raise ValueError("Invalid completed bar grid")
    if profile.name == EXTENDED:
        for bar in bars:
            validate_extended_metadata(bar)
            if timeframe != "15m" and bar.provenance.unpack().get("aggregation") != EXTENDED_AGGREGATION:
                raise ValueError("Extended aggregate provenance required")
    return bars


def result(spec, symbol, timeframe, as_of, inputs, values=None,
           status="READY", reason=None, *, input_end_at=None):
    """Hash only the causal inputs actually supplied, never a full dataset ID hash."""
    inputs = tuple(inputs)
    definition = spec if isinstance(spec, FeatureSpec) else spec.definition
    end = input_end_at if input_end_at is not None else (inputs[-1].end_at if inputs else None)
    def finite(item):
        if isinstance(item, dict):
            return all(finite(v) for v in item.values())
        if isinstance(item, (list, tuple)):
            return all(finite(v) for v in item)
        return not isinstance(item, float) or math.isfinite(item)
    if values is not None and not finite(values):
        values, status, reason = None, "UNDEFINED", "nonfinite_result"
    return FeatureResult(definition, symbol, timeframe, as_of, JsonObject.of(values or {}),
                         status, reason, end, len(inputs), digest(payload(inputs)))


@dataclass(frozen=True, slots=True)
class ScalarPoint:
    end_at: datetime
    known_at: datetime
    value: float | None
    status: str
    reason: str | None

    def __post_init__(self):
        for name in ("end_at", "known_at"):
            object.__setattr__(self, name, timestamp(getattr(self, name)))
        if self.end_at > self.known_at:
            raise ValueError("Scalar known_at precedes end")
        validate_status(self.status, self.reason, self.value is not None)
        if self.value is not None:
            if type(self.value) not in (int, float) or not math.isfinite(self.value):
                raise ValueError("Finite scalar required")
            object.__setattr__(self, "value", float(self.value))


@dataclass(frozen=True, slots=True)
class ScalarSeries:
    """Sparse scalar observations; numeric points do not certify continuity."""
    symbol: str
    timeframe: str
    as_of: datetime
    source: FeatureSpec
    points: tuple[ScalarPoint, ...]
    input_hash: str

    def __post_init__(self):
        identity(self.symbol, self.timeframe)
        object.__setattr__(self, "as_of", timestamp(self.as_of))
        object.__setattr__(self, "points", tuple(self.points))
        if not isinstance(self.source, FeatureSpec) or any(type(p) is not ScalarPoint for p in self.points):
            raise ValueError("Immutable scalar inputs required")
        nonempty(self.input_hash)
        if any(p.known_at > self.as_of for p in self.points):
            raise ValueError("Future scalar input")
        if any(a.end_at >= b.end_at for a, b in zip(self.points, self.points[1:])):
            raise ValueError("Scalar end times must strictly increase")

    @property
    def contiguous(self):
        return is_contiguous(self.points, self.timeframe, self.continuity)

    @property
    def continuity(self):
        params = self.source.parameters.unpack()
        version = params.get("continuity", CONTINUITY_VERSION)
        profile_for_continuity(version)
        return version


def close_series(context, symbol, timeframe, *, continuity=CONTINUITY_VERSION):
    bars = completed_bars(context, symbol, timeframe, continuity)
    return ScalarSeries(symbol, timeframe, context.as_of,
        FeatureSpec("close", "completed_close_v1", JsonObject.of({
            "field": "close", "continuity": continuity, "missing_policy": "sparse_explicit_grid"})),
        tuple(ScalarPoint(b.end_at, b.known_at, b.close, "READY", None) for b in bars),
        digest(payload(bars)))
