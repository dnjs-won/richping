"""H0004 trial 2: completed-session, same-segment own-history compression."""
from collections import deque
from dataclasses import dataclass
import math

from ...core import calendar, digest, timestamp
from ..contracts import JsonObject, payload
from ..features.continuity import is_contiguous, slot_bounds
from ..sessions import EXTENDED, EXTENDED_CONTINUITY, NY, segment, session_bounds
from .h0004_compression import OHLCBar, Feature, Range, Candidate, Step, FAMILY

VERSION = 'h0004_segment_conditioned_compression_v2'
SEGMENTS = ('PREMARKET', 'RTH', 'AFTER_HOURS')


@dataclass(frozen=True, slots=True)
class Specification:
    window_bars: int = 16
    history_sessions: int = 10
    low_percentile: float = 0.20
    expiration_bars: int = 16

    def __post_init__(self):
        for name in ('window_bars', 'history_sessions', 'expiration_bars'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError('Positive integer parameter required')
        if self.window_bars < 2:
            raise ValueError('Compression requires a multi-bar window')
        if (type(self.low_percentile) not in (int,float) or not math.isfinite(self.low_percentile)
                or not 0 < self.low_percentile < 1):
            raise ValueError('Finite percentile strictly between zero and one required')

    @property
    def content_hash(self):
        return digest(dict(version=VERSION, parameters=payload(self)))


def previous_official_sessions(day, count=10):
    """Calendar metadata only. Never selects the last ten available price days."""
    grid = calendar().sessions
    position = grid.get_loc(day)
    if position < count:
        raise ValueError('Insufficient official calendar prefix')
    return tuple(x.date().isoformat() for x in grid[position-count:position])


@dataclass(frozen=True, slots=True)
class SegmentFeature(Feature):
    segment: str | None = None
    reference_status: str = 'UNAVAILABLE'
    reference_count: int = 0
    reference_sessions: tuple[str, ...] = ()
    reference_hash: str | None = None


class CompressionStream:
    """Same episode logic as trial 1, separate immutable signal/version namespace.

    A completed input session needs every scheduled price slot. Its eligible
    measurements need only a valid contiguous N-bar price window, not percentile
    readiness. Current session is accumulated separately and never referenced.
    Initial window warmup legitimately reduces first-session eligible measures.
    Gaps clear all numeric/session reference history and cancel/disarm episodes.
    """
    def __init__(self, spec=Specification()):
        self.spec = spec
        self._window = deque(maxlen=spec.window_bars)
        self._past = {}
        self._day = None
        self._measurements = {s:[] for s in SEGMENTS}
        self._day_bars = 0
        self._day_started_at_open = False
        self._reference_days = ()
        self._reference = {s:() for s in SEGMENTS}
        self._reference_complete = False
        self._reference_hashes = {}
        self._reference_readiness = {}
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
        return Step(bar.known_at, 'INVALID', reason, SegmentFeature('INVALID',reason),
                    active, retirement='invalid_input' if active else None)

    def _begin_session(self, bar, start):
        if self._day is not None:
            opened, closed = session_bounds(self._day,EXTENDED)
            full = self._day_started_at_open and self._day_bars == 64 and self._last.end_at == closed
            self._past[self._day] = (full,{s:tuple(v) for s,v in self._measurements.items()})
        self._day = bar.session
        self._day_bars = 0
        self._day_started_at_open = start == session_bounds(bar.session,EXTENDED)[0]
        self._measurements = {s:[] for s in SEGMENTS}
        self._reference_days = previous_official_sessions(bar.session,self.spec.history_sessions)
        self._past = {d:v for d,v in self._past.items() if d in self._reference_days}
        self._reference_complete = all(d in self._past and self._past[d][0] for d in self._reference_days)
        self._reference = {s:tuple((d,at,value) for d in self._reference_days
                                  if d in self._past for at,value in self._past[d][1][s])
                           for s in SEGMENTS}
        self._reference_hashes = {s:digest(payload(v)) for s,v in self._reference.items()}
        self._reference_readiness = {s:self._reference_complete and bool(v) and max(x for _,_,x in v)>0
                                     for s,v in self._reference.items()}

    def accept(self, bar, as_of=None):
        if not isinstance(bar,OHLCBar):
            raise ValueError('Detached OHLCBar required')
        if bar.identity in self._seen:
            raise ValueError('Duplicate/correction forbidden; use a new vintage and replay')
        if self._invalid:
            return self._reject(bar,'stream_invalid')
        values = (bar.open,bar.high,bar.low,bar.close)
        if (not bar.dataset_id or bar.symbol != 'SOXX'
                or any(type(v) not in (float,int) or not math.isfinite(v) or v <= 0 for v in values)
                or not bar.low <= min(bar.open,bar.close) <= max(bar.open,bar.close) <= bar.high):
            return self._reject(bar,'invalid_price_or_symbol')
        at = timestamp(as_of) if as_of is not None else bar.known_at
        if bar.end_at > bar.known_at or bar.known_at != at:
            return self._reject(bar,'uncompleted_or_unavailable_clock')
        if self._vintage is not None and self._vintage != (bar.dataset_id,bar.symbol):
            return self._reject(bar,'mixed_vintage')
        try:
            start,_ = slot_bounds(bar.end_at,'15m',EXTENDED_CONTINUITY)
            if bar.end_at.astimezone(NY).date().isoformat() != bar.session:
                raise ValueError('Session mismatch')
        except ValueError:
            return self._reject(bar,'unsupported_session_or_slot')
        if self._last and (bar.end_at <= self._last.end_at or bar.known_at < self._last.known_at):
            return self._reject(bar,'nonmonotone_input')
        gap = self._last is not None and not is_contiguous((self._last,bar),'15m',EXTENDED_CONTINUITY)
        retired = None
        before = self.range
        if gap:
            self._window.clear()
            self._past.clear()
            self._day = None
            retired = 'gap_cancelled' if self.range else None
            self.range = None
            self._armed = False
        if self._day != bar.session:
            self._begin_session(bar,start)
        self._day_bars += 1
        self._index += 1
        self._seen.add(bar.identity)
        self._vintage = (bar.dataset_id,bar.symbol)
        self._last = bar
        self._window.append(bar)
        part = segment(start,bar.end_at)
        reference = self._reference[part]
        metadata = dict(segment=part,reference_count=len(reference),reference_sessions=self._reference_days,
                        reference_hash=self._reference_hashes[part])
        reference_ready = self._reference_readiness[part]
        metadata['reference_status'] = 'READY' if reference_ready else 'UNAVAILABLE'
        feature = SegmentFeature('UNAVAILABLE','window_warmup',**metadata)
        if len(self._window) == self.spec.window_bars:
            high,low = max(b.high for b in self._window),min(b.low for b in self._window)
            value = (high-low)/bar.close
            if not math.isfinite(value):
                return self._reject(bar,'nonfinite_normalized_range')
            reason = 'reference_sessions_unavailable' if not self._reference_complete else 'zero_or_empty_reference'
            feature = SegmentFeature('UNAVAILABLE',reason,value,high=high,low=low,**metadata)
            if reference_ready:
                rank = sum(v<=value for _,_,v in reference)/len(reference)
                feature = SegmentFeature('READY','same_segment_prior_sessions_rank',value,rank,
                                         rank<=self.spec.low_percentile,high,low,**metadata)
            # Accumulate current-session measurements only after classifying.
            self._measurements[part].append((bar.end_at,value))
        active = self.range
        events = ()
        evaluated = False
        if active:
            if self._index > active.last_valid_index:
                retired,self.range = 'expired',None
            elif bar.close < active.low:
                retired,self.range = 'downside_cancelled',None
            else:
                evaluated = True
                if bar.close > active.high:
                    body = dict(episode_id=active.id,at=bar.known_at,session=bar.session,
                                snapshot=JsonObject.of(dict(range=payload(active),bar=payload(bar),feature=payload(feature))))
                    events = (Candidate(digest(dict(spec=self.spec.content_hash,**payload(body))),**body),)
                    retired,self.range = 'consumed',None
        published = None
        if self.range is None and feature.status == 'READY':
            if not feature.compressed:
                self._armed = True
            elif self._armed:
                body = dict(high=feature.high,low=feature.low,published_at=bar.known_at,
                            window_start=self._window[0].end_at,published_index=self._index,
                            last_valid_index=self._index+self.spec.expiration_bars,
                            prefix_hash=digest([payload(b) for b in self._window]),feature=feature)
                published = Range(digest(dict(spec=self.spec.content_hash,vintage=self._vintage,**payload(body))),**body)
                self.range,self._armed = published,False
        return Step(bar.known_at,'READY','gap_reset' if gap else 'completed_price',feature,
                    before,published,evaluated,retired,events)
