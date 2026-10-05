"""Frozen H0004 evaluation metadata only: no price loader or outcome statistics."""
from datetime import datetime,time,timedelta
import math

from ...core import digest,sessions,next_sessions,timestamp
from ..sessions import NY,EXTENDED,session_bounds,segment
from ..features.continuity import slot_bounds
from .h0004_segment_compression import Specification,previous_official_sessions
from ..sessions import EXTENDED_CONTINUITY

VERSION = 'H0004_COMPRESSION_BREAKOUT_DIRECTIONAL_EFFICACY_V1'
PRIMARY = 16
DEADLINE = '2027-10-21T20:00:00-04:00'


def calendar_contract():
    embargo = sessions('2026-10-05','2026-10-16')
    anchors = sessions('2026-10-19','2027-10-19')
    followup = next_sessions(anchors[-1],1)
    if len(embargo)!=10 or len(anchors)!=252 or followup!=['2027-10-20']:
        raise ValueError('Frozen calendar changed; pre-outcome operational amendment required')
    unsupported = []
    for day in anchors:
        try: session_bounds(day,EXTENDED)
        except ValueError: unsupported.append(day)
    return dict(embargo=embargo,anchors=anchors,followup=followup,unsupported_sessions=unsupported)


def scheduled_window(anchor,horizon=PRIMARY):
    """Timestamp-only nominal grid; unsupported scheduled dates are never skipped."""
    if type(horizon) is not int or horizon!=PRIMARY:
        raise ValueError('Unregistered horizon')
    at = timestamp(anchor)
    slot_bounds(at,'15m',EXTENDED_CONTINUITY)
    local = at.astimezone(NY)
    if local.second or local.microsecond: raise ValueError('Exact slot required')
    day = local.date().isoformat()
    index = (local.hour*60+local.minute-240)//15-1
    days = [day,*next_sessions(day,(index+horizon)//64)]
    path = []
    for delta in range(1,horizon+1):
        offset,slot = divmod(index+delta,64)
        opened = datetime.combine(datetime.fromisoformat(days[offset]).date(),time(4),NY)
        path.append(timestamp(opened+timedelta(minutes=15*(slot+1))))
    unsupported = []
    for date in dict.fromkeys(v.astimezone(NY).date().isoformat() for v in path):
        try: session_bounds(date,EXTENDED)
        except ValueError: unsupported.append(date)
    return tuple(path),tuple(unsupported)


def validate_events(events,expected_hash,dataset_id):
    """Validate causal snapshot identity/strict breakout/reference, without prices."""
    if digest(events)!=expected_hash: raise ValueError('Event stream hash mismatch')
    ids,episodes = set(),set()
    prior = None
    spec = Specification().content_hash
    for event in events:
        if set(event)!={'id','episode_id','at','session','snapshot'}:
            raise ValueError('Event schema mismatch')
        if event['id'] in ids or event['episode_id'] in episodes:
            raise ValueError('Duplicate candidate/episode')
        body = {k:v for k,v in event.items() if k!='id'}
        if event['id']!=digest(dict(spec=spec,**body)):
            raise ValueError('Candidate identity mismatch')
        at = timestamp(event['at'])
        if prior is not None and at<=prior: raise ValueError('Nonmonotone candidates')
        scheduled_window(at)
        snapshot = event['snapshot']
        bar,frozen = snapshot['bar'],snapshot['range']
        if (bar['dataset_id']!=dataset_id or bar['symbol']!='SOXX' or bar['session']!=event['session']
                or bar['known_at']!=event['at'] or frozen['id']!=event['episode_id']
                or timestamp(frozen['published_at'])>=at):
            raise ValueError('Clock/vintage/episode mismatch')
        values = (bar['close'],frozen['high'],frozen['low'])
        if any(type(v) not in (float,int) or not math.isfinite(v) or v<=0 for v in values) or not bar['close']>frozen['high']>=frozen['low']:
            raise ValueError('Strict breakout/finite boundary mismatch')
        feature = frozen['feature']
        publication = timestamp(frozen['published_at'])
        frozen_day = publication.astimezone(NY).date().isoformat()
        start,_ = slot_bounds(publication,'15m',EXTENDED_CONTINUITY)
        if (frozen['id']!=digest(dict(spec=spec,vintage=[dataset_id,'SOXX'],
                                     **{k:v for k,v in frozen.items() if k!='id'}))
                or frozen['high']!=feature['high'] or frozen['low']!=feature['low']
                or frozen['last_valid_index']-frozen['published_index']!=16
                or scheduled_window(frozen['window_start'])[0][14]!=publication
                or at not in scheduled_window(publication)[0]
                or feature['segment']!=segment(start,publication)):
            raise ValueError('Range identity/window/expiry/segment mismatch')
        if (feature['status']!='READY' or feature['compressed'] is not True or feature['reference_status']!='READY'
                or feature['reference_sessions']!=list(previous_official_sessions(frozen_day))
                or type(feature['percentile']) not in (float,int) or not math.isfinite(feature['percentile'])
                or not 0<=feature['percentile']<=.20 or type(feature['reference_count']) is not int
                or feature['reference_count']<=0):
            raise ValueError('Frozen reference/percentile mismatch')
        ids.add(event['id']); episodes.add(event['episode_id']); prior=at
    return dict(events=len(events),sessions=len({e['session'] for e in events}),hash=digest(events))


def terminal_gate(as_of,*,identity_verified,coverage_complete):
    """Readiness only; accepts no loader, outcome, interval or metric."""
    if type(identity_verified) is not bool or type(coverage_complete) is not bool:
        raise ValueError('Boolean metadata gates required')
    if not identity_verified: return 'INVALID_FAIL_CLOSED'
    if timestamp(as_of)<=timestamp(DEADLINE): return 'PENDING'
    return 'READY_FOR_SEPARATELY_SEALED_TERMINAL_ADAPTER' if coverage_complete else 'UNRESOLVED'
