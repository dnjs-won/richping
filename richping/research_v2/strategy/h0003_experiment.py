"""H0003 frozen evaluation metadata. No prices, label accessor or statistics."""
from datetime import datetime, time, timedelta
import math

from ...core import digest, sessions, next_sessions, timestamp
from ..sessions import NY, EXTENDED, session_bounds
from .h0003_leadership import Specification

VERSION = 'H0003_RELATIVE_LEADERSHIP_EFFICACY_V1'
PRIMARY = 16
SECONDARY = (4, 64)
DEADLINE = '2027-10-21T20:00:00-04:00'
EXPECTED_KEYS = {'id','episode_id','at','session','spec_hash','datasets','own_return',
                 'benchmark_return','relative_return','anchor_at'}


def calendar_contract():
    embargo = sessions('2026-10-05','2026-10-16')
    anchors = sessions('2026-10-19','2027-10-19')
    followup = next_sessions(anchors[-1],1)
    if len(embargo) != 10 or len(anchors) != 252 or followup != ['2027-10-20']:
        raise ValueError('Frozen XNYS calendar changed; pre-outcome operational amendment required')
    unsupported = []
    for day in anchors:
        try:
            session_bounds(day,EXTENDED)
        except ValueError:
            unsupported.append(day)
    return dict(embargo=embargo,anchors=anchors,followup=followup,unsupported_sessions=unsupported)


def scheduled_window(anchor,horizon):
    """Timestamp-only nominal grid, including unsupported days; no price query."""
    if type(horizon) is not int or horizon not in (PRIMARY,*SECONDARY):
        raise ValueError('Unregistered horizon')
    at = timestamp(anchor)
    local = at.astimezone(NY)
    day = local.date().isoformat()
    minutes = local.hour*60+local.minute-240
    if not sessions(day,day) or local.second or local.microsecond or not 15 <= minutes <= 960 or minutes%15:
        raise ValueError('Exact official completed extended slot required')
    index = minutes//15-1
    days = [day,*next_sessions(day,(index+horizon)//64)]
    values = []
    for delta in range(1,horizon+1):
        offset,slot = divmod(index+delta,64)
        opened = datetime.combine(datetime.fromisoformat(days[offset]).date(),time(4),NY)
        values.append(timestamp(opened+timedelta(minutes=15*(slot+1))))
    unsupported = []
    for date in dict.fromkeys([day,*(v.astimezone(NY).date().isoformat() for v in values)]):
        try:
            session_bounds(date,EXTENDED)
        except ValueError:
            unsupported.append(date)
    return tuple(values),tuple(unsupported)


def validate_events(events,datasets,expected_hash):
    """Validate immutable signal metadata only; never read reference/future prices."""
    if digest(events) != expected_hash:
        raise ValueError('Event stream hash mismatch')
    seen,episodes = set(),set()
    previous = None
    for event in events:
        if set(event) != EXPECTED_KEYS or event['datasets'] != list(datasets) or event['spec_hash'] != Specification().hash:
            raise ValueError('Candidate schema/dataset/spec mismatch')
        if event['id'] in seen or event['episode_id'] in episodes or not event['episode_id']:
            raise ValueError('Event collision or duplicate episode candidate')
        if event['id'] != digest({k:v for k,v in event.items() if k != 'id'}):
            raise ValueError('Candidate identity/body mismatch')
        at = timestamp(event['at'])
        if previous is not None and at <= previous:
            raise ValueError('Nonmonotone event stream')
        scheduled_window(at,PRIMARY)
        if event['session'] != (at-timedelta(microseconds=1)).astimezone(NY).date().isoformat():
            raise ValueError('Candidate session mismatch')
        anchor = timestamp(event['anchor_at'])
        if anchor >= at or scheduled_window(anchor,64)[0][-1] != at:
            raise ValueError('Candidate t-64 scheduled identity mismatch')
        values = [event[k] for k in ('own_return','benchmark_return','relative_return')]
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
            raise ValueError('Nonfinite signal metadata')
        if values[0] < 0 or values[2] <= 0 or values[2] != values[0]-values[1]:
            raise ValueError('Frozen leadership/guard/formula mismatch')
        seen.add(event['id'])
        episodes.add(event['episode_id'])
        previous = at
    return dict(events=len(events),sessions=len({e['session'] for e in events}),hash=digest(events))


def disposition(*,valid=True,terminal=False,resolved=True,events=0,event_sessions=0,
                occupied_blocks=0,relative_interval=None):
    """Already-certified metadata only. PASS is relative leadership, not profitability."""
    for value in (events,event_sessions,occupied_blocks):
        if type(value) is not int or value < 0:
            raise ValueError('Nonnegative integer denominators required')
    if event_sessions > events or occupied_blocks > event_sessions or occupied_blocks > 26:
        raise ValueError('Inconsistent calendar denominators')
    if not valid:
        return 'INVALID_FAIL_CLOSED'
    if not terminal:
        return 'PENDING'
    if not resolved:
        return 'UNRESOLVED'
    if not events:
        return 'ZERO_SIGNAL'
    if events < 40 or event_sessions < 20 or occupied_blocks < 8:
        return 'INSUFFICIENT_EVIDENCE'
    if relative_interval is None:
        return 'UNRESOLVED'
    if (not isinstance(relative_interval,(tuple,list)) or len(relative_interval) != 2
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in relative_interval)
            or relative_interval[0] > relative_interval[1]):
        raise ValueError('Certified finite ordered relative interval required')
    if relative_interval[0] > 0:
        return 'PASS'
    if relative_interval[1] < 0:
        return 'REJECT'
    return 'INCONCLUSIVE'


def terminal_gate(as_of,*,identity_verified,coverage_complete,resolved=True,
                  events=0,event_sessions=0,occupied_blocks=0):
    """No loader accepted. First gate for a separately implemented future adapter."""
    if not identity_verified:
        return 'INVALID_FAIL_CLOSED'
    if timestamp(as_of) <= timestamp(DEADLINE):
        return 'PENDING'
    return disposition(valid=True,terminal=True,resolved=coverage_complete and resolved,
        events=events,event_sessions=event_sessions,occupied_blocks=occupied_blocks)
