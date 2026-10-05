"""Independent causal OHLC-only compression/breakout stream; no label access."""
from collections import deque
from dataclasses import dataclass
from datetime import datetime
import math

from ...core import digest, timestamp
from ..contracts import JsonObject, payload
from ..features.continuity import is_contiguous, slot_bounds
from ..sessions import EXTENDED_CONTINUITY, NY

FAMILY = 'VOLATILITY_COMPRESSION_BREAKOUT_CONTINUATION'
VERSION = 'h0004_compression_breakout_v1'


@dataclass(frozen=True, slots=True)
class Specification:
    window_bars: int = 16
    history_observations: int = 640
    low_percentile: float = 0.20
    expiration_bars: int = 16

    def __post_init__(self):
        for name in ('window_bars', 'history_observations', 'expiration_bars'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError('Positive integer parameter required')
        if self.window_bars < 2:
            raise ValueError('Compression requires a multi-bar window')
        if (type(self.low_percentile) not in (int, float)
                or not math.isfinite(self.low_percentile) or not 0 < self.low_percentile < 1):
            raise ValueError('Finite percentile strictly between zero and one required')

    @property
    def content_hash(self):
        return digest(dict(version=VERSION, parameters=payload(self)))


@dataclass(frozen=True, slots=True)
class OHLCBar:
    dataset_id: str
    symbol: str
    end_at: datetime
    known_at: datetime
    session: str
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self):
        object.__setattr__(self, 'end_at', timestamp(self.end_at))
        object.__setattr__(self, 'known_at', timestamp(self.known_at))

    @classmethod
    def from_market(cls, bar):
        if bar.timeframe != '15m':
            raise ValueError('H0004 accepts 15m only')
        return cls(bar.dataset_id, bar.symbol, bar.end_at, bar.known_at, bar.session,
                   bar.open, bar.high, bar.low, bar.close)

    @property
    def identity(self):
        return self.dataset_id, self.symbol, self.end_at


@dataclass(frozen=True, slots=True)
class Feature:
    status: str
    reason: str
    normalized_range: float | None = None
    percentile: float | None = None
    compressed: bool | None = None
    high: float | None = None
    low: float | None = None


@dataclass(frozen=True, slots=True)
class Range:
    id: str
    high: float
    low: float
    published_at: datetime
    window_start: datetime
    published_index: int
    last_valid_index: int
    prefix_hash: str
    feature: Feature


@dataclass(frozen=True, slots=True)
class Candidate:
    id: str
    episode_id: str
    at: datetime
    session: str
    snapshot: JsonObject


@dataclass(frozen=True, slots=True)
class Step:
    at: datetime
    input_status: str
    input_reason: str
    feature: Feature
    range_before: Range | None = None
    range_published: Range | None = None
    breakout_evaluated: bool = False
    retirement: str | None = None
    events: tuple[Candidate, ...] = ()


class CompressionStream:
    """Append-only immutable vintage. Host supplies one completed OHLC bar.

    Range features include current completed bar. Their baseline excludes current
    observation, includes the immediately preceding H observations, and is never
    fit on a whole dataset. Window/bar baselines overlap; no independence claim.
    No episode crosses a missing slot. Calendar closures preserve history/age.
    Invalid input permanently poisons this stream; new vintage needs new replay.
    """
    def __init__(self, spec=Specification()):
        self.spec = spec
        self._window = deque(maxlen=spec.window_bars)
        self._ranges = deque(maxlen=spec.history_observations)
        self._seen = set()
        self._vintage = None
        self._last = None
        self._index = -1
        self._invalid = False
        self._armed = True
        self.range = None

    def _reject(self, bar, reason):
        self._invalid = True
        active, self.range = self.range, None
        return Step(bar.known_at, 'INVALID', reason, Feature('INVALID', reason),
                    active, retirement='invalid_input' if active else None)

    def accept(self, bar, as_of=None):
        if not isinstance(bar, OHLCBar):
            raise ValueError('Detached OHLCBar required')
        if bar.identity in self._seen:
            raise ValueError('Duplicate/correction forbidden; use a new vintage and replay')
        if self._invalid:
            return self._reject(bar, 'stream_invalid')
        values = (bar.open, bar.high, bar.low, bar.close)
        if (not bar.dataset_id or bar.symbol != 'SOXX'
                or any(type(v) not in (float, int) or not math.isfinite(v) or v <= 0 for v in values)
                or not bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high):
            return self._reject(bar, 'invalid_price_or_symbol')
        at = timestamp(as_of) if as_of is not None else bar.known_at
        if bar.end_at > bar.known_at or bar.known_at != at:
            return self._reject(bar, 'uncompleted_or_unavailable_clock')
        if self._vintage is not None and self._vintage != (bar.dataset_id, bar.symbol):
            return self._reject(bar, 'mixed_vintage')
        try:
            slot_bounds(bar.end_at, '15m', EXTENDED_CONTINUITY)
            if bar.end_at.astimezone(NY).date().isoformat() != bar.session:
                raise ValueError('Session mismatch')
        except ValueError:
            return self._reject(bar, 'unsupported_session_or_slot')
        if self._last and (bar.end_at <= self._last.end_at or bar.known_at < self._last.known_at):
            return self._reject(bar, 'nonmonotone_input')
        gap = self._last is not None and not is_contiguous((self._last, bar), '15m', EXTENDED_CONTINUITY)
        retired = None
        before = self.range
        if gap:
            self._window.clear()
            self._ranges.clear()
            retired = 'gap_cancelled' if self.range else None
            self.range = None
            # Missing data cannot be the noncompression observation that rearms.
            self._armed = False
        self._index += 1
        self._seen.add(bar.identity)
        self._vintage = (bar.dataset_id, bar.symbol)
        self._last = bar
        self._window.append(bar)
        feature = Feature('UNAVAILABLE', 'window_warmup')
        value = None
        if len(self._window) == self.spec.window_bars:
            high, low = max(b.high for b in self._window), min(b.low for b in self._window)
            value = (high - low) / bar.close
            if not math.isfinite(value):
                return self._reject(bar, 'nonfinite_normalized_range')
            feature = Feature('UNAVAILABLE', 'history_warmup', value, high=high, low=low)
            if len(self._ranges) == self.spec.history_observations:
                if max(self._ranges) == 0:
                    feature = Feature('UNAVAILABLE', 'zero_history_range', value, high=high, low=low)
                else:
                    rank = sum(v <= value for v in self._ranges) / self.spec.history_observations
                    feature = Feature('READY', 'own_history_rank', value, rank,
                                      rank <= self.spec.low_percentile, high, low)
        # The baseline above cannot see the current measurement.
        if value is not None:
            self._ranges.append(value)
        active = self.range
        events = ()
        evaluated = False
        if active:
            if self._index > active.last_valid_index:
                retired, self.range = 'expired', None
            elif bar.close < active.low:
                retired, self.range = 'downside_cancelled', None
            else:
                evaluated = True
                if bar.close > active.high:
                    body = dict(episode_id=active.id, at=bar.known_at, session=bar.session,
                                snapshot=JsonObject.of(dict(range=payload(active), bar=payload(bar),
                                                            feature=payload(feature))))
                    events = (Candidate(digest(dict(spec=self.spec.content_hash, **payload(body))), **body),)
                    retired, self.range = 'consumed', None
        published = None
        if self.range is None and feature.status == 'READY':
            if not feature.compressed:
                self._armed = True
            elif self._armed:
                body = dict(high=feature.high, low=feature.low, published_at=bar.known_at,
                            window_start=self._window[0].end_at, published_index=self._index,
                            last_valid_index=self._index+self.spec.expiration_bars,
                            prefix_hash=digest([payload(b) for b in self._window]), feature=feature)
                published = Range(digest(dict(spec=self.spec.content_hash, vintage=self._vintage,
                                              **payload(body))), **body)
                self.range, self._armed = published, False
        return Step(bar.known_at, 'READY', 'gap_reset' if gap else 'completed_price', feature,
                    before, published, evaluated, retired, events)
