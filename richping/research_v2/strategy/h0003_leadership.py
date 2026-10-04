"""Append-only paired leadership mechanics. No dataset or outcome accessors."""
from dataclasses import dataclass
from datetime import datetime, timedelta
import math

from ...core import digest, timestamp
from ..contracts import JsonObject, payload
from ..features.continuity import is_contiguous, slot_bounds
from ..sessions import EXTENDED_CONTINUITY, NY
from ..alpaca_data import PROVIDER, PRICE, ACTION, CLOCK

CONTRACT = (PROVIDER, 'sip', 'raw', 'USD', PRICE, ACTION, CLOCK,
            '15m', '04:00-20:00 America/New_York')


@dataclass(frozen=True, slots=True)
class Specification:
    window_slots: int = 64
    persistence_slots: int = 4

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in (self.window_slots, self.persistence_slots)):
            raise ValueError('Positive integer windows required')

    @property
    def hash(self):
        return digest({'version': 'h0003_leadership_v1', **payload(self), 'guard': 'own_return>=0'})


@dataclass(frozen=True, slots=True)
class CloseBar:
    dataset_id: str
    symbol: str
    start_at: datetime
    end_at: datetime
    known_at: datetime
    session: str
    close: float
    contract: tuple = CONTRACT
    split_identity_admitted: bool = False

    def __post_init__(self):
        for name in ('start_at', 'end_at', 'known_at'):
            object.__setattr__(self, name, timestamp(getattr(self, name)))
        object.__setattr__(self, 'contract', tuple(self.contract))


@dataclass(frozen=True, slots=True)
class Step:
    at: datetime
    pair_ready: bool
    rs_ready: bool
    reason: str
    own_return: float | None = None
    benchmark_return: float | None = None
    relative_return: float | None = None
    positive_run: int = 0
    leadership: bool = False
    guard: bool | None = None
    episode_id: str | None = None
    episode_started: bool = False
    event: JsonObject | None = None


def validate_pair(own, benchmark, at):
    if own is None or benchmark is None:
        return 'one_side_missing'
    for bar, symbol in ((own, 'SOXX'), (benchmark, 'QQQ')):
        if not isinstance(bar, CloseBar) or not bar.dataset_id or bar.symbol != symbol:
            return 'symbol_or_identity_mismatch'
        if bar.contract != CONTRACT or not bar.split_identity_admitted:
            return 'provider_feed_unit_action_mismatch'
        if type(bar.close) not in (int, float) or not math.isfinite(bar.close) or bar.close <= 0:
            return 'invalid_price'
        if bar.end_at > at or bar.known_at > at:
            return 'future_or_unavailable_bar'
        if bar.end_at != at or bar.known_at != bar.end_at:
            return 'stale_or_clock_mismatch'
        try:
            start, end = slot_bounds(at, '15m', EXTENDED_CONTINUITY)
            if (bar.start_at, bar.end_at) != (start, end):
                return 'slot_mismatch'
            if bar.session != (end-timedelta(microseconds=1)).astimezone(NY).date().isoformat():
                return 'session_mismatch'
        except ValueError:
            return 'unsupported_session_slot'
    if (own.start_at, own.end_at, own.session) != (benchmark.start_at, benchmark.end_at, benchmark.session):
        return 'pair_alignment_mismatch'
    return None


class LeadershipStream:
    def __init__(self, spec=Specification()):
        self.spec = spec
        self._history = ()
        self._last_at = None
        self._identities = None
        self._run = 0
        self._run_start = None
        self._episode = None
        self._consumed = False

    def _unavailable(self, at, reason):
        self._history = ()
        self._run = 0
        self._run_start = None
        # Retain episode and consumed lock: unknown data cannot prove rearm.
        return Step(at, False, False, reason, episode_id=self._episode)

    def accept(self, own, benchmark, as_of):
        at = timestamp(as_of)
        if self._last_at is not None and at <= self._last_at:
            raise ValueError('Duplicate/revision/nonmonotone slot; new replay required')
        self._last_at = at
        reason = validate_pair(own, benchmark, at)
        if reason:
            return self._unavailable(at, reason)
        identities = (own.dataset_id, benchmark.dataset_id)
        if self._identities is not None and identities != self._identities:
            return self._unavailable(at, 'mixed_vintage')
        self._identities = identities
        gap = self._history and not is_contiguous((self._history[-1][0], own), '15m', EXTENDED_CONTINUITY)
        if gap:
            self._unavailable(at, 'gap_reset')
        self._history = (*self._history, (own, benchmark))[-(self.spec.window_slots+1):]
        if len(self._history) <= self.spec.window_slots:
            return Step(at, True, False, 'gap_warmup' if gap else 'lookback_warmup', episode_id=self._episode)
        first_own, first_benchmark = self._history[0]
        own_return = own.close/first_own.close-1
        benchmark_return = benchmark.close/first_benchmark.close-1
        relative = own_return-benchmark_return
        if not all(math.isfinite(v) for v in (own_return, benchmark_return, relative)):
            return self._unavailable(at, 'nonfinite_return')
        guard = own_return >= 0
        started = False
        if relative <= 0:
            self._run, self._run_start, self._episode, self._consumed = 0, None, None, False
        else:
            if not self._run:
                self._run_start = at
            self._run += 1
            if self._run >= self.spec.persistence_slots and self._episode is None:
                self._episode = digest([self.spec.hash, identities, payload(self._run_start)])
                started = True
        leadership = relative > 0 and self._run >= self.spec.persistence_slots
        event = None
        if leadership and guard and not self._consumed:
            snapshot = dict(episode_id=self._episode, at=payload(at), session=own.session,
                            spec_hash=self.spec.hash, datasets=list(identities),
                            own_return=own_return, benchmark_return=benchmark_return,
                            relative_return=relative, anchor_at=payload(first_own.end_at))
            event = JsonObject.of({'id': digest(snapshot), **snapshot})
            self._consumed = True
        return Step(at, True, True, 'ready', own_return, benchmark_return, relative,
                    self._run, leadership, guard, self._episode, started, event)
