"""Frozen H0002 gross opportunity labels. Discovery and terminal inference are separate."""
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
import math
from random import Random
from statistics import mean, median

from ...core import digest, next_sessions, sessions, timestamp, utcnow
from ..sessions import EXTENDED, NY, session_bounds
from .h0002_defense import PRIMARY, COMPARATOR
from .h0002_experiment import calendar_contract, disposition

PROTOCOL_HASH = 'a6e16e57bee2e26860f6989c88fdaeac707ecfc91a6326f54a8d754cfe327e8d'
FREEZE_HASH = 'd6c9c80834eebbc5a06c157e4289c59d50e5b887e6ba540e9a8ad467dcae97ea'
HORIZONS = (4, 64, 192)
DISCOVERY_START, DISCOVERY_END = '2026-05-05', '2026-08-13'
DEADLINE = '2027-10-23T20:00:00-04:00'


def scheduled_window(anchor, horizon):
    """Nominal 64-slot official-day grid; unsupported days never disappear."""
    if horizon not in HORIZONS:
        raise ValueError('Unregistered horizon')
    anchor = timestamp(anchor)
    local = anchor.astimezone(NY)
    day = local.date().isoformat()
    if not sessions(day, day) or local.second or local.microsecond:
        raise ValueError('Not an official completed slot')
    minutes = local.hour*60 + local.minute - 240
    if not 15 <= minutes <= 960 or minutes % 15:
        raise ValueError('Not a 04:00-20:00 completed slot')
    index = minutes//15 - 1
    days = [day, *next_sessions(day, (index+horizon)//64)]
    window = []
    for delta in range(1, horizon+1):
        offset, position = divmod(index+delta, 64)
        opened = datetime.combine(datetime.fromisoformat(days[offset]).date(), time(4), NY)
        window.append(timestamp(opened + timedelta(minutes=15*(position+1))))
    unsupported = []
    for value in dict.fromkeys([day, *(t.astimezone(NY).date().isoformat() for t in window)]):
        try:
            session_bounds(value, EXTENDED)
        except ValueError:
            unsupported.append(value)
    return tuple(window), tuple(unsupported)


def validate_events(events, dataset_id, price_spec_hash, expected_hash):
    if digest(events) != expected_hash:
        raise ValueError('Candidate stream hash mismatch')
    seen, visits, primaries, comparators = set(), set(), {}, []
    for event in events:
        if event['id'] in seen:
            raise ValueError('Candidate identity collision')
        seen.add(event['id'])
        if event['family'] not in (PRIMARY, COMPARATOR):
            raise ValueError('Unexpected family')
        bar, zone = event['snapshot']['bar'], event['snapshot']['zone']
        if (bar['dataset_id'] != dataset_id or bar['symbol'] != 'SOXX'
                or bar['session'] != event['session'] or bar['known_at'] != event['at']
                or zone['id'] != event['zone_id'] or timestamp(zone['created_at']) >= timestamp(bar['end_at'])):
            raise ValueError('Candidate source/zone/clock identity mismatch')
        scheduled_window(bar['end_at'], 4)
        body = {k: v for k, v in event.items() if k != 'id'}
        expected = digest({'price_spec': price_spec_hash, **body}) if event['family'] == PRIMARY else digest(body)
        if event['id'] != expected:
            raise ValueError('Candidate body hash mismatch')
        if event['family'] == PRIMARY:
            visit = event['zone_id'], event['visit_id']
            if visit in visits:
                raise ValueError('Duplicate primary in same visit')
            visits.add(visit)
            primaries[event['id']] = event
        else:
            comparators.append(event)
    linked = set()
    for event in comparators:
        parent = primaries.get(event['snapshot']['price_event_id'])
        if parent is None or parent['id'] in linked:
            raise ValueError('Unmatched/duplicate comparator')
        if any(event[k] != parent[k] for k in ('at', 'session', 'zone_id', 'visit_id')):
            raise ValueError('Comparator identity mismatch')
        if any(event['snapshot'][k] != parent['snapshot'][k] for k in parent['snapshot']):
            raise ValueError('Comparator price snapshot mismatch')
        linked.add(parent['id'])
    return tuple(primaries.values()), tuple(comparators)


class DiscoveryLabels:
    """Only manifest-selected anchors/horizons, within admitted discovery scope."""
    def __init__(self, bars, membership, membership_hash, certified_sessions, as_of, *, interval_certificate=None):
        if digest(membership) != membership_hash or membership['protocol_hash'] != PROTOCOL_HASH:
            raise ValueError('Control membership/protocol hash mismatch')
        self.membership_hash = membership_hash
        self.dataset_hash = membership.get('dataset_hash')
        self.as_of = timestamp(as_of)
        self.certified = frozenset(certified_sessions)
        self.interval_certificate = interval_certificate
        self.rows = {}
        for bar in bars:
            if not DISCOVERY_START <= bar.session <= DISCOVERY_END:
                raise PermissionError('Confirmation/non-discovery price source forbidden')
            if bar.end_at in self.rows or bar.symbol != 'SOXX':
                raise ValueError('Duplicate/wrong-symbol label source')
            self.rows[bar.end_at] = bar
        self.allowed = set()
        for item in membership['events']:
            self.allowed.add(('event', item['anchor_end_at']))
            self.allowed.update(('control', c['anchor_end_at']) for c in item['controls'])
        self.audit = Counter(discovery_label_requests=0, discovery_forward_close_reads=0,
                             confirmation_outcome_access=0, profitability_calculations=0)
        self.trace = []

    def _unit_known(self, bar):
        if bar.corporate_action == 'NONE_CONFIRMED':
            return True
        if bar.corporate_action != 'UNKNOWN' or not self.interval_certificate:
            return False
        # UNKNOWN is immutable bar-time PIT knowledge, not an ex-post unit verdict.
        # Only the independently hash-verified dataset admission may resolve it.
        certificate = self.interval_certificate
        if not hasattr(bar, 'provenance'):
            return False
        provenance = bar.provenance.unpack()
        return (certificate['dataset_id'] == bar.dataset_id
                and certificate['dataset_hash'] == self.dataset_hash
                and certificate['interval_start'] <= bar.session <= certificate['interval_end']
                and certificate['splits_inside_interval'] == []
                and provenance.get('corporate_actions') == 'INTERVAL_CERTIFIED_SPLIT_IDENTITY_DIVIDENDS_NOT_REINVESTED'
                and provenance.get('price_basis') == 'ALPACA_SIP_RAW_USD_PER_AS_TRADED_SHARE')

    def label(self, anchor, reference, horizon, role):
        anchor = timestamp(anchor)
        day = anchor.astimezone(NY).date().isoformat()
        if not DISCOVERY_START <= day <= DISCOVERY_END:
            raise PermissionError('Confirmation outcome access forbidden')
        if (role, anchor.isoformat()) not in self.allowed:
            raise PermissionError('Anchor not in sealed control membership')
        window, unsupported = scheduled_window(anchor, horizon)
        target = window[-1]
        self.audit['discovery_label_requests'] += 1
        result = {'status': 'COMPLETE', 'reason': 'exact_scheduled_endpoint',
                  'anchor_end_at': anchor.isoformat(), 'target_end_at': target.isoformat(),
                  'horizon_slots': horizon, 'reference_mark': reference, 'return': None}
        anchor_row = self.rows.get(anchor)
        days = {day, *(t.astimezone(NY).date().isoformat() for t in window)}
        if anchor_row is None or anchor_row.close != reference:
            raise ValueError('Signal/control reference mismatch')
        if unsupported:
            result.update(status='UNRESOLVED', reason='unsupported_scheduled_session')
        elif not days <= self.certified or any(
                not self._unit_known(self.rows[t]) for t in (anchor, *window) if t in self.rows):
            result.update(status='UNRESOLVED', reason='action_unit_ambiguity_or_split')
        elif target > self.as_of:
            result.update(status='PENDING', reason='scheduled_label_not_mature')
        elif any(t not in self.rows or self.rows[t].known_at > self.as_of for t in window):
            result.update(status='UNRESOLVED', reason='missing_scheduled_slot_no_compression')
        elif not DISCOVERY_START <= target.astimezone(NY).date().isoformat() <= DISCOVERY_END:
            result.update(status='UNRESOLVED', reason='outside_admitted_discovery_scope')
        else:
            self.audit['discovery_forward_close_reads'] += 1
            result['return'] = self.rows[target].close/reference - 1
        self.trace.append({'role': role, **result})
        return result


def evaluate_membership(membership, source):
    rows = []
    for item in membership['events']:
        labels, controls, excess = {}, {}, {}
        for horizon in HORIZONS:
            key = str(horizon)
            label = source.label(item['anchor_end_at'], item['reference_mark'], horizon, 'event')
            selected = [source.label(c['anchor_end_at'], c['reference_mark'], horizon, 'control') for c in item['controls']]
            labels[key] = label
            controls[key] = selected
            if len(selected) != 5:
                state, reason = 'UNRESOLVED', 'fewer_than_five_causal_controls'
            elif label['status'] == 'PENDING' or any(c['status'] == 'PENDING' for c in selected):
                state, reason = 'PENDING', 'immature_event_or_control_label'
            elif label['status'] != 'COMPLETE' or any(c['status'] != 'COMPLETE' for c in selected):
                state, reason = 'UNRESOLVED', 'unresolved_event_or_control_label'
            else:
                state, reason = 'COMPLETE', 'five_matched_controls'
            excess[key] = {'status': state, 'reason': reason, 'value':
                label['return'] - mean(c['return'] for c in selected) if state == 'COMPLETE' else None}
        rows.append({**item, 'labels': labels, 'control_labels': controls, 'excess': excess})
    return rows


def session_mean(rows, value):
    grouped = defaultdict(list)
    for row in rows:
        if value(row) is not None:
            grouped[row['session']].append(value(row))
    return mean(mean(v) for v in grouped.values()) if grouped else None


def family_metrics(rows):
    results = {}
    for horizon in HORIZONS:
        key = str(horizon)
        resolved = [r for r in rows if r['labels'][key]['status'] == 'COMPLETE']
        paired = [r for r in rows if r['excess'][key]['status'] == 'COMPLETE']
        values = [r['labels'][key]['return'] for r in resolved]
        results[key] = {
            'events': len(rows), 'distinct_sessions': len({r['session'] for r in rows}),
            'label_status': dict(Counter(r['labels'][key]['status'] for r in rows)),
            'paired_status': dict(Counter(r['excess'][key]['status'] for r in rows)),
            'complete_label_sessions': len({r['session'] for r in resolved}),
            'complete_pair_sessions': len({r['session'] for r in paired}),
            'session_balanced_mean_return_resolved': session_mean(resolved, lambda r: r['labels'][key]['return']),
            'full_cohort_mean_return': session_mean(resolved, lambda r: r['labels'][key]['return']) if len(resolved) == len(rows) else None,
            'median_return_resolved': median(values) if values else None,
            'positive_events': sum(v > 0 for v in values),
            'positive_rate_resolved': sum(v > 0 for v in values)/len(values) if values else None,
            'session_balanced_mean_excess_resolved_subset': session_mean(paired, lambda r: r['excess'][key]['value']),
            'full_cohort_mean_excess': session_mean(paired, lambda r: r['excess'][key]['value']) if len(paired) == len(rows) else None,
            'resolved_pair_denominator': len(paired),
            'uncertainty_status': 'DISCOVERY_UNCERTAINTY_NOT_PREREGISTERED', 'bootstrap_interval': None,
            'unresolved_reasons': dict(Counter(r['excess'][key]['reason'] for r in rows if r['excess'][key]['status'] != 'COMPLETE'))}
    return results


def exploratory_disposition(metrics):
    primary = metrics['4']
    if primary['label_status'].get('COMPLETE', 0) != primary['events'] or primary['paired_status'].get('COMPLETE', 0) != primary['events']:
        return 'DISCOVERY_INSUFFICIENT_RESOLVED_LABELS'
    absolute, excess = primary['full_cohort_mean_return'], primary['full_cohort_mean_excess']
    if absolute > 0 and excess > 0:
        return 'DISCOVERY_POSITIVE_DIRECTION'
    if absolute < 0 and excess < 0:
        return 'DISCOVERY_NEGATIVE_DIRECTION'
    return 'DISCOVERY_MIXED'


def _percentile(values, q):
    x = sorted(values)
    position = (len(x)-1)*q
    low = int(position)
    high = math.ceil(position)
    return x[low] + (x[high]-x[low])*(position-low)


def _registered_bootstrap(series):
    """Pure mechanics; only terminal_inference may expose real confirmation output."""
    if set(series) != {PRIMARY, COMPARATOR} or any(len(v) != 252 for v in series.values()):
        raise ValueError('Exact registered 252-session two-family grid required')
    rng = Random(20261004)
    replicates = {family: [[], []] for family in series}
    empty = Counter()
    chain = None
    for _ in range(10000):
        starts = [rng.randrange(252) for _ in range(math.ceil(252/25))]
        indices = [(start+i) % 252 for start in starts for i in range(25)][:252]
        chain = digest([chain, starts])
        for family, grid in series.items():
            values = [grid[i] for i in indices if grid[i] is not None]
            if not values:
                empty[family] += 1
                continue
            for column in (0, 1):
                replicates[family][column].append(mean(v[column] for v in values))
    return {family: {'status': 'UNRESOLVED' if empty[family] > 100 else 'COMPLETE',
        'empty_resamples': empty[family], 'intervals': [[_percentile(v, .0125), _percentile(v, .9875)] if v and empty[family] <= 100 else None for v in columns],
        'resampling_chain_hash': chain, 'block_sessions': 25, 'grid_sessions': 252,
        'replicates': 10000, 'seed': 20261004} for family, columns in replicates.items()}


def terminal_inference(series_loader, *, identity_verified, coverage_complete, denominators):
    """Deadline check precedes invoking any outcome loader. Never called by discovery."""
    if timestamp(utcnow()) <= timestamp(DEADLINE):
        return {'status': 'PENDING', 'confirmation_outcome_access': 0}
    if not identity_verified:
        return {'status': 'INVALID_FAIL_CLOSED', 'confirmation_outcome_access': 0}
    if not coverage_complete:
        return {'status': 'UNRESOLVED', 'confirmation_outcome_access': 0}
    calendar_contract()
    gates = {family: disposition(terminal=True, **denominators[family]) for family in (PRIMARY, COMPARATOR)}
    if gates[PRIMARY] in ('ZERO_SIGNAL', 'INSUFFICIENT_EVIDENCE', 'UNRESOLVED'):
        return {'status': gates[PRIMARY], 'confirmation_outcome_access': 0}
    intervals = _registered_bootstrap(series_loader())
    result = {}
    for family in (PRIMARY, COMPARATOR):
        if gates[family] != 'INCONCLUSIVE':
            result[family] = {'status': gates[family]}
            continue
        ci = intervals[family]
        bounds = ci['intervals']
        state = disposition(terminal=True, resolved=ci['status'] == 'COMPLETE',
            positive_lower_bounds=all(b and b[0] > 0 for b in bounds),
            negative_upper_bound=any(b and b[1] < 0 for b in bounds), **denominators[family])
        result[family] = {'status': state, **ci, 'uncertainty_status': ci['status']}
        result[family]['status'] = state
    return {'status': result[PRIMARY]['status'], 'families': result, 'comparator_can_replace_primary': False}
