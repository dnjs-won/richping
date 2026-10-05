"""Registered H0003 paired discovery price labels; no confirmation inference."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import timedelta
import math
from statistics import mean, median

from ...core import digest, timestamp
from ..sessions import NY
from .h0003_leadership import CONTRACT, CloseBar, validate_pair
from .h0003_experiment import scheduled_window, validate_events, DEADLINE

PROTOCOL_HASH = 'b221efe766c4536717fde663fdc32e22fac136660fdb0278000e3d44c9d91f46'
FREEZE_HASH = 'e08f98578ecbb3742ccd02bc2a09df205d9b2a45146082051a68955b5262e39e'
HORIZONS = (4,16,64)
PRIMARY = 16
START, END = '2026-05-05', '2026-08-13'


@dataclass(frozen=True, slots=True)
class OutcomeBar:
    dataset_id: str
    symbol: str
    start_at: object
    end_at: object
    known_at: object
    session: str
    open: float
    high: float
    low: float
    close: float
    contract: tuple = CONTRACT
    unit_certified: bool = False

    def __post_init__(self):
        for name in ('start_at','end_at','known_at'):
            object.__setattr__(self,name,timestamp(getattr(self,name)))
        object.__setattr__(self,'contract',tuple(self.contract))

    def causal_close(self):
        return CloseBar(self.dataset_id,self.symbol,self.start_at,self.end_at,
            self.known_at,self.session,self.close,self.contract,self.unit_certified)


class DiscoveryLabels:
    """Exact paired labels limited to verified immutable discovery membership."""
    def __init__(self, own, benchmark, events, binding, certified_sessions, as_of):
        if (binding['protocol_hash'],binding['signal_freeze_hash']) != (PROTOCOL_HASH,FREEZE_HASH):
            raise ValueError('INVALID_FAIL_CLOSED: frozen protocol/signal binding mismatch')
        validate_events(events,binding['dataset_ids'],binding['candidate_stream_hash'])
        self.binding = binding
        self.events = {e['id']:e for e in events}
        self.certified = frozenset(certified_sessions)
        if any(not START <= d <= END for d in self.certified):
            raise ValueError('Discovery certificate outside sealed scope')
        self.as_of = timestamp(as_of)
        self.audit = Counter(discovery_label_requests=0,discovery_path_lookup_requests=0,
            discovery_present_path_bar_reads=0,discovery_endpoint_close_reads=0,
            discovery_anchor_close_reads=0,outside_scope_labels=0,
            confirmation_label_requests=0,confirmation_price_reads=0,
            uncertainty_calculations=0,profitability_calculations=0)
        self.trace = []
        self.rows = []
        for symbol,bars,identity in zip(('SOXX','QQQ'),(own,benchmark),binding['dataset_ids']):
            lookup = {}
            for bar in bars:
                local_day = bar.end_at.astimezone(NY).date().isoformat()
                if not START <= local_day <= END or not START <= bar.session <= END:
                    raise PermissionError('Confirmation/non-discovery source forbidden before price access')
                if bar.symbol != symbol or bar.dataset_id != identity or bar.end_at in lookup:
                    raise ValueError('INVALID_FAIL_CLOSED: duplicate or wrong paired source identity')
                lookup[bar.end_at] = bar
            self.rows.append(lookup)

    def label(self,event_id,horizon):
        if event_id not in self.events:
            raise PermissionError('Anchor not in sealed discovery candidate stream')
        event = self.events[event_id]
        at = timestamp(event['at'])
        if not START <= at.astimezone(NY).date().isoformat() <= END:
            self.audit['confirmation_label_requests'] += 1
            raise PermissionError('Confirmation label access forbidden')
        window,unsupported = scheduled_window(at,horizon)
        target = window[-1]
        self.audit['discovery_label_requests'] += 1
        result = dict(status='UNRESOLVED',reason=None,event_id=event_id,session=event['session'],
            horizon_slots=horizon,anchor_at=at.isoformat(),target_at=target.isoformat(),
            own_reference=None,benchmark_reference=None,own_return=None,benchmark_return=None,relative_excess=None)
        path = (at,*window)
        days = {t.astimezone(NY).date().isoformat() for t in path}
        # Bounds are checked before looking up either asset, never opportunistic capture.
        if any(not START <= day <= END for day in days):
            result['reason'] = 'outside_admitted_discovery_scope'
            self.audit['outside_scope_labels'] += 1
        elif unsupported:
            result['reason'] = 'unsupported_scheduled_session'
        elif not days <= self.certified:
            result['reason'] = 'action_unit_certificate_unavailable'
        elif target > self.as_of:
            result['reason'] = 'sealed_capture_does_not_cover_mature_label'
        else:
            missing,invalid = [],[]
            for slot in path:
                self.audit['discovery_path_lookup_requests'] += 2
                pair = [lookup.get(slot) for lookup in self.rows]
                self.audit['discovery_present_path_bar_reads'] += sum(b is not None for b in pair)
                if any(b is None for b in pair):
                    missing.append(slot.isoformat())
                    continue
                a,b = pair
                reason = validate_pair(a.causal_close(),b.causal_close(),slot)
                if reason is None:
                    for row in pair:
                        values = (row.open,row.high,row.low,row.close)
                        if (any(type(v) not in (int,float) or not math.isfinite(v) or v <= 0 for v in values)
                                or not row.low <= min(row.open,row.close) <= max(row.open,row.close) <= row.high):
                            reason = 'invalid_or_nonfinite_ohlc'
                            break
                if reason:
                    invalid.append(dict(at=slot.isoformat(),reason=reason))
            result['missing_slots'] = missing
            result['invalid_slots'] = invalid
            if invalid:
                result['reason'] = 'invalid_paired_path'
            elif missing:
                result['reason'] = 'missing_scheduled_slot_no_compression'
            else:
                a,b = [lookup[at] for lookup in self.rows]
                x,y = [lookup[target] for lookup in self.rows]
                self.audit['discovery_anchor_close_reads'] += 2
                self.audit['discovery_endpoint_close_reads'] += 2
                own,benchmark = x.close/a.close-1,y.close/b.close-1
                if not all(math.isfinite(v) for v in (own,benchmark,own-benchmark)):
                    result['reason'] = 'nonfinite_return_math'
                else:
                    result.update(status='COMPLETE',reason='exact_paired_scheduled_path',
                        own_reference=a.close,benchmark_reference=b.close,
                        own_return=own,benchmark_return=benchmark,relative_excess=own-benchmark)
        self.trace.append(dict(event_id=event_id,horizon_slots=horizon,
            expected_path=[t.isoformat() for t in path],**{k:v for k,v in result.items() if k != 'event_id' and k != 'horizon_slots'}))
        return result


def evaluate(events,source):
    if list(source.events.values()) != events:
        raise ValueError('Candidate order/membership changed')
    return [dict(event_id=e['id'],episode_id=e['episode_id'],session=e['session'],at=e['at'],
        labels={str(h):source.label(e['id'],h) for h in HORIZONS}) for e in events]


def session_mean(rows,key,column):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['session']].append(row['labels'][key][column])
    return mean(mean(v) for v in grouped.values()) if grouped else None


def metrics(rows):
    if len({r['event_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate candidate denominator')
    results = {}
    for h in HORIZONS:
        key = str(h)
        complete = [r for r in rows if r['labels'][key]['status'] == 'COMPLETE']
        if any(r['labels'][key]['status'] not in ('COMPLETE','UNRESOLVED') for r in rows):
            raise ValueError('Discovery labels must preserve complete/unresolved denominator')
        for row in complete:
            label = row['labels'][key]
            values = [label[k] for k in ('own_return','benchmark_return','relative_excess')]
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in values) or values[2] != values[0]-values[1]:
                raise ValueError('Invalid paired return formula')
        body = dict(events=len(rows),candidate_sessions=len({r['session'] for r in rows}),
            complete=len(complete),unresolved=len(rows)-len(complete),
            complete_sessions=len({r['session'] for r in complete}),
            estimate_scope='FULL_COHORT' if len(complete)==len(rows) else 'RESOLVED_SUBSET_ONLY_FULL_COHORT_UNKNOWN',
            unresolved_reasons=dict(Counter(r['labels'][key]['reason'] for r in rows if r not in complete)),
            uncertainty_status='DISCOVERY_UNCERTAINTY_NOT_PREREGISTERED',bootstrap_interval=None,p_value=None)
        for name,column in (('SOXX','own_return'),('QQQ','benchmark_return'),('excess','relative_excess')):
            values = [r['labels'][key][column] for r in complete]
            avg = session_mean(complete,key,column)
            body[name] = dict(session_balanced_mean_resolved=avg,
                full_cohort_session_balanced_mean=avg if len(complete)==len(rows) else None,
                event_median_resolved=median(values) if values else None,
                positive_count=sum(v>0 for v in values),
                positive_rate_resolved=sum(v>0 for v in values)/len(values) if values else None,
                resolved_denominator=len(values))
        results[key] = body
    return results


def exploratory_disposition(results):
    primary = results[str(PRIMARY)]
    if primary['complete'] != primary['events'] or not primary['events']:
        return 'DISCOVERY_INSUFFICIENT_RESOLVED_LABELS'
    excess = primary['excess']['full_cohort_session_balanced_mean']
    if excess > 0:
        return 'DISCOVERY_POSITIVE_RELATIVE_DIRECTION'
    if excess < 0:
        return 'DISCOVERY_NEGATIVE_RELATIVE_DIRECTION'
    return 'DISCOVERY_MIXED'


def confirmation_readiness(as_of,loader=None):
    """No interim label/performance access; future admission adapter remains separate."""
    if timestamp(as_of) <= timestamp(DEADLINE):
        return dict(status='PENDING',confirmation_outcome_access=0,performance=None)
    return dict(status='UNRESOLVED',reason='FUTURE_PAIRED_ADMISSION_AND_TERMINAL_ADAPTER_REQUIRED',
        confirmation_outcome_access=0,performance=None)
