"""H0002 causal discovery only. No outcome, position, MACD or H0001 dependency."""
from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from statistics import median

from ...core import digest, timestamp
from ..contracts import JsonObject, payload
from ..features.continuity import is_contiguous, slot_bounds
from ..sessions import EXTENDED_CONTINUITY, NY

PRIMARY = 'PRICE_DEFENSE_REVERSAL_V1'
COMPARATOR = 'PRICE_DEFENSE_REVERSAL_VOLUME_CONFIRM_V1'


@dataclass(frozen=True, slots=True)
class Specification:
    lookback_bars: int = 128
    minimum_pivot_separation: int = 4
    expiration_bars: int = 128
    volume_lookback_bars: int = 20
    volume_ratio_threshold: float = 1.0

    def __post_init__(self):
        for name in ('lookback_bars', 'minimum_pivot_separation', 'expiration_bars', 'volume_lookback_bars'):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError('Positive integer parameter required')
        if self.lookback_bars < 3 or self.minimum_pivot_separation >= self.lookback_bars - 2:
            raise ValueError('Insufficient low-pair window')
        if (type(self.volume_ratio_threshold) not in (int, float)
                or not math.isfinite(self.volume_ratio_threshold) or self.volume_ratio_threshold <= 0):
            raise ValueError('Positive finite volume comparator required')

    @property
    def price_hash(self):
        return digest({'version': PRIMARY, **{k: v for k, v in payload(self).items() if not k.startswith('volume_')}})


@dataclass(frozen=True, slots=True)
class PriceBar:
    """Detached immutable price input; optional volume never blocks price-only."""
    dataset_id: str
    symbol: str
    end_at: datetime
    known_at: datetime
    session: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None

    def __post_init__(self):
        object.__setattr__(self, 'end_at', timestamp(self.end_at))
        object.__setattr__(self, 'known_at', timestamp(self.known_at))

    @classmethod
    def from_market(cls, bar):
        if bar.timeframe != '15m':
            raise ValueError('H0002 accepts 15m only')
        return cls(bar.dataset_id, bar.symbol, bar.end_at, bar.known_at, bar.session,
                   bar.open, bar.high, bar.low, bar.close, bar.volume)

    @property
    def identity(self):
        return self.dataset_id, self.symbol, self.end_at

    @property
    def price_payload(self):
        return {k: v for k, v in payload(self).items() if k != 'volume'}


@dataclass(frozen=True, slots=True)
class Stage:
    status: str
    reason: str
    flag: bool | None = None


@dataclass(frozen=True, slots=True)
class Zone:
    id: str
    center: float
    lower: float
    upper: float
    created_at: datetime
    created_index: int
    expires_index: int
    source_pair: tuple[tuple[int, datetime, float], ...]
    prefix_hash: str


@dataclass(frozen=True, slots=True)
class Candidate:
    id: str
    family: str
    at: datetime
    session: str
    zone_id: str
    visit_id: str
    snapshot: JsonObject


@dataclass(frozen=True, slots=True)
class Step:
    at: datetime
    input: Stage
    construction: Stage
    interaction: Stage
    rejection: Stage
    volume: Stage
    zone_before: Zone | None = None
    zone_published: Zone | None = None
    touch: bool = False
    penetration: bool = False
    wick_fraction: float | None = None
    close_recovery: bool | None = None
    volume_ratio: float | None = None
    retired_reason: str | None = None
    events: tuple[Candidate, ...] = ()


def rejection_geometry(bar, zone):
    """Exact boundary tests; a flat bar has unavailable wick, not infinity."""
    span = bar.high - bar.low
    wick = (min(bar.open, bar.close) - bar.low) / span if span > 0 else None
    return bar.low < zone.lower and bar.close > zone.upper, wick


def volume_confirmation(bar, previous, spec):
    if len(previous) < spec.volume_lookback_bars:
        return Stage('UNAVAILABLE', 'volume_warmup'), None
    values = [b.volume for b in previous[-spec.volume_lookback_bars:]]
    if bar.volume is None or any(v is None for v in values):
        return Stage('UNAVAILABLE', 'missing_volume'), None
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in [bar.volume, *values]):
        return Stage('INVALID', 'invalid_volume'), None
    baseline = median(values)
    if baseline == 0:
        return Stage('UNAVAILABLE', 'zero_volume_baseline'), None
    ratio = bar.volume / baseline
    return Stage('READY', 'relative_volume', ratio >= spec.volume_ratio_threshold), ratio


def construct_zone(history, spec, last_seed):
    """Called only after current bar processing; no current-bar candidate."""
    if len(history) < spec.lookback_bars:
        return Stage('UNAVAILABLE', 'price_warmup'), None
    window = history[-spec.lookback_bars:]
    half = median(b.high - b.low for _, b in window) / 2
    if half <= 0:
        return Stage('UNAVAILABLE', 'zero_price_range'), None
    pivots = [(index, b.end_at, b.low) for i, (index, b) in enumerate(window[1:-1], 1)
              if b.low < window[i-1][1].low and b.low < window[i+1][1].low]
    index, current = window[-1]
    for newer in reversed(pivots):
        if newer[0] <= last_seed:
            continue
        for older in reversed(pivots):
            if newer[0] - older[0] < spec.minimum_pivot_separation:
                continue
            if abs(newer[2] - older[2]) > 2 * half:
                continue
            center = (newer[2] + older[2]) / 2
            if current.close <= center + half:
                continue
            prefix_hash = digest([b.price_payload for _, b in window])
            body = dict(center=center, lower=center-half, upper=center+half,
                        created_at=current.known_at, created_index=index,
                        expires_index=index+spec.expiration_bars,
                        source_pair=(older, newer), prefix_hash=prefix_hash)
            zone = Zone(digest({'spec': spec.price_hash, **payload(body)}), **body)
            return Stage('READY', 'zone_published', True), zone
    return Stage('READY', 'no_compatible_new_pair', False), None


class DefenseStream:
    """One immutable vintage, append only; revisions require a separate replay.

    The stream receives one completed bar, never a dataset, loader or forward query.
    Accepted history is detached and bounded. Past-identity updates/duplicates are
    rejected before mutation. A price/clock defect poisons the stream fail-closed.
    """
    def __init__(self, spec=Specification()):
        self.spec = spec
        self._history = ()
        self._seen = set()
        self._identity = None
        self._index = -1
        self.zone = None
        self._last_seed = -1
        self._away = False
        self._visit = None
        self._consumed = False
        self._invalid = False

    def _invalid_step(self, bar, reason):
        self._invalid = True
        invalid = Stage('INVALID', reason)
        return Step(bar.known_at, invalid, invalid, invalid, invalid, invalid)

    def accept(self, bar, as_of=None):
        if not isinstance(bar, PriceBar):
            raise ValueError('Detached PriceBar required')
        at = timestamp(as_of) if as_of is not None else bar.known_at
        if bar.identity in self._seen:
            raise ValueError('Duplicate or historical revision forbidden; use new vintage/replay')
        if self._invalid:
            return self._invalid_step(bar, 'stream_invalid')
        values = (bar.open, bar.high, bar.low, bar.close)
        if (not bar.dataset_id or bar.symbol != 'SOXX'
                or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in values)
                or not bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high):
            return self._invalid_step(bar, 'invalid_price_or_symbol')
        if bar.end_at > bar.known_at or bar.known_at > at or at != bar.known_at:
            return self._invalid_step(bar, 'unavailable_or_future_clock')
        if self._identity is not None and self._identity != (bar.dataset_id, bar.symbol):
            return self._invalid_step(bar, 'mixed_vintage')
        try:
            slot_bounds(bar.end_at, '15m', EXTENDED_CONTINUITY)
            if (bar.end_at - timedelta(microseconds=1)).astimezone(NY).date().isoformat() != bar.session:
                raise ValueError('Session mismatch')
        except ValueError:
            return self._invalid_step(bar, 'invalid_session_slot')
        previous = self._history[-1][1] if self._history else None
        if previous and (bar.end_at <= previous.end_at or bar.known_at < previous.known_at):
            return self._invalid_step(bar, 'nonmonotone_input')
        gap = previous is not None and not is_contiguous((previous, bar), '15m', EXTENDED_CONTINUITY)
        if gap:
            self._history, self.zone, self._last_seed = (), None, -1
            self._away, self._visit, self._consumed = False, None, False
            previous = None
        self._identity = (bar.dataset_id, bar.symbol)
        self._seen.add(bar.identity)
        self._index += 1
        volume, ratio = volume_confirmation(bar, [b for _, b in self._history], self.spec)
        retired = 'gap_reset' if gap else None
        if self.zone and self._index >= self.zone.expires_index:
            self.zone = None
            retired = 'expired'
        active = self.zone
        unavailable = Stage('UNAVAILABLE', 'no_active_zone')
        interaction, rejection = unavailable, unavailable
        touch = penetration = False
        wick = None
        events = []
        if active:
            reentry = self._away and bar.low <= active.upper
            interaction = Stage('READY', 'reentry' if reentry else 'active_zone', reentry)
            touch = reentry and bar.low == active.upper
            penetration = reentry and bar.low < active.upper
            if reentry:
                self._visit = digest([active.id, payload(bar.end_at)])
                self._consumed = False
                self._away = False
            if bar.low > active.upper:
                self._away, self._visit, self._consumed = True, None, False
            rejected, wick = rejection_geometry(bar, active)
            eligible = self._visit is not None and rejected
            rejection = Stage('READY', 'failed_breakdown_reclaim' if eligible else 'no_rejection', eligible)
            if eligible and not self._consumed:
                snapshot = {'zone': payload(active), 'bar': bar.price_payload,
                            'wick_fraction': wick, 'close_recovery': previous is not None and bar.close > previous.close}
                body = dict(family=PRIMARY, at=bar.known_at, session=bar.session,
                            zone_id=active.id, visit_id=self._visit, snapshot=JsonObject.of(snapshot))
                price = Candidate(digest({'price_spec': self.spec.price_hash, **payload(body)}), **body)
                events.append(price)
                if volume.status == 'READY' and volume.flag:
                    body.update(family=COMPARATOR, snapshot=JsonObject.of({**snapshot,
                        'volume_ratio': ratio, 'volume_lookback_bars': self.spec.volume_lookback_bars,
                        'volume_ratio_threshold': self.spec.volume_ratio_threshold,
                        'price_event_id': price.id}))
                    events.append(Candidate(digest(payload(body)), **body))
                self._consumed = True  # Volume can never add a later unmatched visit event.
            if bar.close < active.lower:
                self.zone = None
                self._away, self._visit, self._consumed = False, None, False
                retired = 'close_below_lower'
        capacity = max(self.spec.lookback_bars, self.spec.volume_lookback_bars)
        self._history = (*self._history, (self._index, bar))[-capacity:]
        published = None
        if self.zone is None:
            construction, published = construct_zone(self._history, self.spec, self._last_seed)
            if published:
                self.zone = published
                self._last_seed = published.source_pair[-1][0]
                self._away, self._visit, self._consumed = True, None, False
        else:
            construction = Stage('READY', 'immutable_active_zone', True)
        return Step(bar.known_at, Stage('READY', 'gap_reset' if gap else 'valid_completed_price'),
                    construction, interaction, rejection, volume, active, published, touch,
                    penetration, wick, previous is not None and bar.close > previous.close,
                    ratio, retired, tuple(events))
