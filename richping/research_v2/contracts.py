"""Immutable values at the strategy boundary. JSON state is explicit and portable."""

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
import json
import math
from typing import Protocol

from ..core import canonical, digest, ticker, timestamp
from .sessions import bar_profile

CONTRACT_VERSION = "research_v2_a_v1"
AVAILABILITY_VERSION = "atomic_known_at_batch_v1"
TIMEFRAMES = ("15m", "1H", "Daily")


def nonempty(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Non-empty string required")


@dataclass(frozen=True, slots=True)
class JsonObject:
    """Store canonical text, never a mutable dict supplied by a caller."""

    text: str = "{}"

    def __post_init__(self):
        value = json.loads(self.text)
        if not isinstance(value, dict):
            raise ValueError("JSON object required")
        object.__setattr__(self, "text", canonical(value))

    @classmethod
    def of(cls, value):
        def check(item):
            if isinstance(item, dict):
                if any(not isinstance(k, str) for k in item):
                    raise ValueError("JSON string keys required")
                for v in item.values():
                    check(v)
            elif isinstance(item, (list, tuple)):
                for v in item:
                    check(v)
        check(value)
        return cls(canonical(value))

    def unpack(self):
        return json.loads(self.text)


def payload(value):
    if isinstance(value, JsonObject):
        return value.unpack()
    if isinstance(value, datetime):
        return timestamp(value).isoformat()
    if is_dataclass(value):
        return {f.name: payload(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, (tuple, list)):
        return [payload(v) for v in value]
    if isinstance(value, dict):
        return {k: payload(v) for k, v in value.items()}
    return value


@dataclass(frozen=True, slots=True)
class MarketBar:
    dataset_id: str
    symbol: str
    timeframe: str
    start_at: datetime
    end_at: datetime
    session: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    known_at: datetime
    source: str
    provenance: JsonObject
    corporate_action: str  # NONE_CONFIRMED / UNKNOWN / PRESENT

    def __post_init__(self):
        nonempty(self.dataset_id)
        nonempty(self.source)
        if ticker(self.symbol) != self.symbol or self.timeframe not in TIMEFRAMES:
            raise ValueError("Unsupported symbol/timeframe")
        if not isinstance(self.provenance, JsonObject):
            raise ValueError("Immutable provenance required")
        for name in ("start_at", "end_at", "known_at"):
            object.__setattr__(self, name, timestamp(getattr(self, name)))
        if not self.start_at < self.end_at <= self.known_at:
            raise ValueError("Invalid interval or known_at before completion")
        for name in ("open", "high", "low", "close", "volume"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Finite OHLCV required")
            object.__setattr__(self, name, float(value))
        if min(self.open, self.low, self.high, self.close) <= 0 or self.volume < 0:
            raise ValueError("Invalid OHLC/volume")
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("Inconsistent OHLC")
        if self.corporate_action not in {"NONE_CONFIRMED", "UNKNOWN", "PRESENT"}:
            raise ValueError("Explicit corporate action state required")

    @property
    def identity(self):
        return (self.dataset_id, self.symbol, self.timeframe, self.end_at.isoformat())


@dataclass(frozen=True, slots=True)
class StrategyState:
    version: str
    data: JsonObject = JsonObject()

    def __post_init__(self):
        nonempty(self.version)
        if not isinstance(self.data, JsonObject):
            raise ValueError("Immutable state required")

    def dumps(self):
        return canonical(payload(self))

    @classmethod
    def loads(cls, text):
        value = json.loads(text)
        if set(value) != {"version", "data"}:
            raise ValueError("Invalid serialized state")
        return cls(value["version"], JsonObject.of(value["data"]))


@dataclass(frozen=True, slots=True)
class Intent:
    """Request only. Timing/spec/state provenance is supplied by DecisionTrace."""

    kind: str
    symbol: str
    reason_codes: tuple[str, ...]
    requested_quantity: float | None = None
    input_snapshot: JsonObject = JsonObject()

    def __post_init__(self):
        if self.kind not in {"ENTER", "ADD", "REDUCE", "EXIT", "HOLD", "NO_ACTION"}:
            raise ValueError("Unsupported intent")
        if ticker(self.symbol) != self.symbol:
            raise ValueError("Unnormalized symbol")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        if not self.reason_codes or any(not isinstance(r, str) or not r for r in self.reason_codes):
            raise ValueError("Intent reasons required")
        q = self.requested_quantity
        if q is not None and (type(q) not in (int, float) or not math.isfinite(q) or q <= 0):
            raise ValueError("Positive requested quantity required")
        if not isinstance(self.input_snapshot, JsonObject):
            raise ValueError("Immutable input snapshot required")


@dataclass(frozen=True, slots=True)
class Fill:
    """Reserved for a separately versioned executor; never a callback result."""

    intent_id: str
    execution_contract: str
    executed_at: datetime
    known_at: datetime
    quantity: float
    price: float
    cost: float

    def __post_init__(self):
        nonempty(self.intent_id)
        nonempty(self.execution_contract)
        for name in ("executed_at", "known_at"):
            object.__setattr__(self, name, timestamp(getattr(self, name)))
        if self.known_at < self.executed_at:
            raise ValueError("Fill known_at precedes execution")
        if any(type(v) not in (int, float) or not math.isfinite(v)
               for v in (self.quantity, self.price, self.cost)):
            raise ValueError("Invalid fill numbers")
        if min(self.quantity, self.price) <= 0 or self.cost < 0:
            raise ValueError("Invalid fill price/quantity/cost")


@dataclass(frozen=True, slots=True)
class ReplayEvent:
    run_id: str
    sequence: int
    as_of: datetime
    base_bars: tuple[MarketBar, ...]
    completed: tuple[MarketBar, ...]

    def __post_init__(self):
        nonempty(self.run_id)
        if type(self.sequence) is not int or self.sequence < 0:
            raise ValueError("Nonnegative event sequence required")
        object.__setattr__(self, "as_of", timestamp(self.as_of))
        object.__setattr__(self, "base_bars", tuple(self.base_bars))
        object.__setattr__(self, "completed", tuple(self.completed))
        if not self.base_bars or any(b.known_at != self.as_of for b in self.base_bars):
            raise ValueError("Event requires a nonempty batch with identical known_at")
        if len({b.identity for b in self.base_bars}) != len(self.base_bars):
            raise ValueError("Duplicate bar in availability batch")
        if any(b not in self.completed for b in self.base_bars):
            raise ValueError("Event must expose every base bar in its batch")
        if any(b.known_at > self.as_of for b in self.completed):
            raise ValueError("Future bar in replay event")

    @property
    def id(self):
        return digest(payload(self))


@dataclass(frozen=True, slots=True)
class ReplayContext:
    """A detached prefix snapshot; no loader, iterator, store or engine reference."""

    as_of: datetime
    bars: tuple[MarketBar, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "as_of", timestamp(self.as_of))
        object.__setattr__(self, "bars", tuple(self.bars))
        if any(b.known_at > self.as_of or b.end_at > self.as_of for b in self.bars):
            raise ValueError("Future bar in causal context")
        if len({bar_profile(b) for b in self.bars}) > 1:
            raise ValueError("Mixed session capability profiles in causal context")

    def query(self, symbol=None, timeframe=None, start_at=None, end_at=None):
        if timeframe is not None and timeframe not in TIMEFRAMES:
            raise ValueError("Unsupported query timeframe")
        start = timestamp(start_at) if start_at is not None else None
        end = timestamp(end_at) if end_at is not None else self.as_of
        if end > self.as_of or (start is not None and start > end):
            raise ValueError("Future or inverted query")
        return tuple(b for b in self.bars if (symbol is None or b.symbol == symbol)
                     and (timeframe is None or b.timeframe == timeframe)
                     and (start is None or b.end_at >= start) and b.end_at <= end)


@dataclass(frozen=True, slots=True)
class Decision:
    state: StrategyState
    intents: tuple[Intent, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "intents", tuple(self.intents))
        if not isinstance(self.state, StrategyState) or any(type(i) is not Intent for i in self.intents):
            raise ValueError("Strategy must return state and intents, never fills")


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    event: ReplayEvent
    strategy_id: str
    specification_hash: str
    state_before: StrategyState
    decision: Decision
    visible_hash: str
    previous_hash: str | None

    def __post_init__(self):
        for value in (self.strategy_id, self.specification_hash, self.visible_hash):
            nonempty(value)
        if not isinstance(self.state_before, StrategyState) or not isinstance(self.decision, Decision):
            raise ValueError("Immutable decision states required")

    @property
    def hash(self):
        return digest(payload(self))

    @property
    def intent_records(self):
        """Canonical evidence envelopes; the strategy only supplies the request."""
        return tuple({"id": digest([self.event.id, index, payload(intent)]),
                      "event_id": self.event.id, "strategy_id": self.strategy_id,
                      "specification_hash": self.specification_hash,
                      "decision_at": self.event.as_of.isoformat(),
                      "known_at": self.event.as_of.isoformat(),
                      "state_before": payload(self.state_before),
                      "state_after": payload(self.decision.state), "request": payload(intent)}
                     for index, intent in enumerate(self.decision.intents))


@dataclass(frozen=True, slots=True)
class Checkpoint:
    run_id: str
    sequence: int
    as_of: datetime
    state: StrategyState
    trace_hash: str
    visible_hash: str

    def __post_init__(self):
        for value in (self.run_id, self.trace_hash, self.visible_hash):
            nonempty(value)
        object.__setattr__(self, "as_of", timestamp(self.as_of))
        if type(self.sequence) is not int or self.sequence < 0 or not isinstance(self.state, StrategyState):
            raise ValueError("Invalid checkpoint")


class Strategy(Protocol):
    strategy_id: str
    specification: JsonObject

    def initialize(self, context: ReplayContext) -> StrategyState: ...

    def on_event(self, context: ReplayContext, state: StrategyState,
                 event: ReplayEvent) -> Decision: ...
