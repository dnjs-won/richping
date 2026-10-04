"""First H0002 exploratory discovery efficacy, with controls sealed before labels."""
from contextlib import ExitStack, contextmanager
from collections import Counter
import json
from pathlib import Path
from unittest.mock import patch

import yaml

from richping.core import digest, calendar, sessions
from richping.research_v2.contracts import payload
from richping.research_v2.sessions import NY
from richping.research_v2.strategy.h0002_defense import DefenseStream, PriceBar, Specification, PRIMARY, COMPARATOR
from richping.research_v2.strategy.h0002_experiment import ControlAnchor, select_controls
from richping.research_v2.strategy.h0002_efficacy import (
    PROTOCOL_HASH, FREEZE_HASH, validate_events, DiscoveryLabels, evaluate_membership,
    family_metrics, exploratory_disposition)
from scripts import h0002_signal_preregister as frozen
from scripts.h0002_frequency_audit import (
    ROOT as FREQUENCY, SOURCE, DATASET_ID, DATASET_HASH, FORBIDDEN,
    load_admitted, encode, fingerprint, preservation_fingerprint)

ROOT = Path('research/data_evidence/h0002-first-efficacy-20261004/verification-v2')
FILES = ('richping/research_v2/strategy/h0002_efficacy.py', 'scripts/h0002_first_efficacy.py',
         'tests/test_h0002_efficacy.py', 'docs/H0002_FIRST_EFFICACY.md')


def verify_contract():
    with frozen.metadata_only() as counts:
        result = frozen.verify()
    if any(counts.values()) or result['protocol_hash'] != PROTOCOL_HASH or result['signal_freeze_sha256'] != FREEZE_HASH:
        raise ValueError('Protocol or signal freeze hash mismatch')
    freeze = json.loads(frozen.FREEZE.read_bytes())
    if (fingerprint(SOURCE/'intraday-vintage.json') != freeze['dataset_receipt_sha256']
            or fingerprint(FREQUENCY/'candidate-events.json') != freeze['discovery_events_sha256']):
        raise ValueError('Source/event raw receipt hash mismatch')
    events = json.loads((FREQUENCY/'candidate-events.json').read_bytes())['events']
    validate_events(events, DATASET_ID, Specification().price_hash, freeze['discovery_event_stream_hash'])
    historical = json.loads((frozen.ROOT/'verification.json').read_bytes())
    if historical['outcome_access'] != 0 or historical['profitability_calculations'] != 0:
        raise ValueError('Prior outcome exposure inconsistent')
    return result


@contextmanager
def guarded(*, preparation=False):
    targets = dict(FORBIDDEN)
    targets['sqlite3.connect'] = 'database'
    targets['richping.research_v2.strategy.h0002_efficacy.terminal_inference'] = 'confirmation_inference'
    if preparation:
        targets['richping.research_v2.strategy.h0002_efficacy.DiscoveryLabels.label'] = 'label_access_before_control_seal'
    counts = {name: 0 for name in targets.values()}
    def reject(category):
        def denied(*args, **kwargs):
            counts[category] += 1
            raise AssertionError('Efficacy action forbids ' + category)
        return denied
    with ExitStack() as stack:
        for target, category in targets.items():
            stack.enter_context(patch(target, side_effect=reject(category)))
        yield counts


def prepare_membership(dataset, events):
    """Chronological causal features only, never label/forward-window selection."""
    stream, history, anchors, anchor_rows, replayed = DefenseStream(), [], [], {}, []
    for bar in dataset.bars:
        step = stream.accept(PriceBar.from_market(bar))
        if step.input.status != 'READY':
            raise ValueError('Invalid causal input')
        if step.input.reason == 'gap_reset':
            history = []
        if len(history) >= 4:
            change = bar.close-history[-4].close
            anchor = ControlAnchor(bar.session, bar.end_at.astimezone(NY).strftime('%H:%M'),
                (change > 0)-(change < 0), step.construction.status == 'READY',
                any(e.family == PRIMARY for e in step.events))
            anchors.append(anchor)
            anchor_rows[(anchor.session, anchor.local_slot)] = bar
        history = [*history, bar][-4:]
        replayed.extend(payload(e) for e in step.events)
    if replayed != events:
        raise ValueError('Frozen replay/event identity mismatch')
    lookup = {(a.session, a.local_slot): a for a in anchors}
    items = []
    comparator_by_parent = {e['snapshot']['price_event_id']: e['id'] for e in events if e['family'] == COMPARATOR}
    for event in (e for e in events if e['family'] == PRIMARY):
        bar = event['snapshot']['bar']
        key = (bar['session'], PriceBar(**bar).end_at.astimezone(NY).strftime('%H:%M'))
        current = lookup[key]
        selected = select_controls(current, anchors)
        prior = sessions(str(calendar().first_session.date()), current.session)[:-1][-20:]
        eligible = [a for a in anchors if a.session in prior and a.local_slot == current.local_slot
                    and a.prior_four_sign == current.prior_four_sign and a.ready and not a.primary_event]
        controls = []
        for anchor in selected or ():
            source = anchor_rows[(anchor.session, anchor.local_slot)]
            controls.append({'session': anchor.session, 'local_slot': anchor.local_slot,
                'prior_four_sign': anchor.prior_four_sign, 'anchor_end_at': source.end_at.isoformat(),
                'reference_mark': source.close, 'dataset_id': source.dataset_id,
                'anchor_identity_hash': digest([source.dataset_id, source.symbol, '15m', source.end_at.isoformat()])})
        items.append({'event_id': event['id'], 'zone_id': event['zone_id'], 'visit_id': event['visit_id'],
            'session': event['session'], 'anchor_end_at': bar['end_at'], 'known_at': event['at'],
            'dataset_id': DATASET_ID, 'dataset_hash': DATASET_HASH, 'signal_contract_hash': FREEZE_HASH,
            'anchor_identity_hash': digest([DATASET_ID, 'SOXX', '15m', bar['end_at']]),
            'reference_mark': bar['close'], 'local_slot': current.local_slot,
            'prior_four_sign': current.prior_four_sign, 'eligible_control_count': len(eligible),
            'control_status': 'READY' if selected else 'UNRESOLVED',
            'control_reason': 'most_recent_five' if selected else 'fewer_than_five_causal_controls',
            'controls': controls, 'comparator_event_id': comparator_by_parent.get(event['id'])})
    return {'schema': 'h0002_discovery_control_membership_v1', 'protocol_hash': PROTOCOL_HASH,
            'signal_freeze_hash': FREEZE_HASH, 'dataset_id': DATASET_ID, 'dataset_hash': DATASET_HASH,
            'candidate_stream_hash': digest(events), 'selection_uses_outcomes': False,
            'search_official_sessions': 20, 'required_controls': 5, 'events': items}


def certificate_sessions(dataset):
    admission = json.loads((SOURCE/'admission.json').read_bytes())
    action = json.loads((SOURCE/'action-history-audit.json').read_bytes())
    units = json.loads((SOURCE/'ohlc-unit-crosscheck.json').read_bytes())
    if digest(action) != admission['action_audit_hash'] or digest(units) != admission['daily_unit_audit_hash']:
        raise ValueError('Action/unit certificate hash mismatch')
    if action['splits_inside_interval'] or not admission['raw_split_identical_selected_intraday_and_daily']:
        raise ValueError('Discovery split identity not certified')
    first, last = dataset.bars[0].session, dataset.bars[-1].session
    if not action['interval_start'] <= first <= last <= action['interval_end']:
        raise ValueError('Action certificate outside interval')
    if dataset.manifest.unpack()['price_basis'] != 'ALPACA_SIP_RAW_USD_PER_AS_TRADED_SHARE':
        raise ValueError('Frozen raw units required')
    return sessions(first, last)


def execute(root=ROOT):
    preflight = verify_contract()  # Must precede constructing any market object.
    frozen.immutable(root/'preflight.json', encode({**preflight,
        'prior_H0002_outcome_access': 0, 'prior_profitability_calculations': 0,
        'authorization': 'Owner explicitly authorized discovery only in H0002_FIRST_EFFICACY'}))
    implementation = {p: preservation_fingerprint(p) for p in FILES}
    frozen.immutable(root/'implementation-manifest.json', encode({'files': implementation,
        'protocol_hash': PROTOCOL_HASH, 'signal_freeze_hash': FREEZE_HASH,
        'uncertainty_audit': 'Discovery70 grid is not registered by fixed252/randrange252 rule; no discovery CI.'}))
    with guarded(preparation=True) as preparation_calls:
        dataset = load_admitted()
        events = json.loads((FREQUENCY/'candidate-events.json').read_bytes())['events']
        certified = certificate_sessions(dataset)
        membership = prepare_membership(dataset, events)
        frozen.immutable(root/'control-membership.json', encode(membership))
        frozen.immutable(root/'control-seal.json', encode({'membership_hash': digest(membership),
            'membership_raw_sha256': fingerprint(root/'control-membership.json'),
            'preflight_sha256': fingerprint(root/'preflight.json'),
            'outcome_access_before_control_seal': 0, 'preparation_forbidden_calls': preparation_calls}))
    # Recheck persisted identities after sealing, before creating an outcome accessor.
    verify_contract()
    persisted = json.loads((root/'control-membership.json').read_bytes())
    seal = json.loads((root/'control-seal.json').read_bytes())
    if persisted != membership or digest(persisted) != seal['membership_hash'] or fingerprint(root/'control-membership.json') != seal['membership_raw_sha256']:
        raise ValueError('Control membership seal mismatch')
    if any(preparation_calls.values()):
        raise ValueError('Outcome access before control seal')
    label_source = {'dataset_id': DATASET_ID, 'dataset_hash': DATASET_HASH,
        'dataset_receipt_sha256': fingerprint(SOURCE/'intraday-vintage.json'),
        'action_audit_sha256': fingerprint(SOURCE/'action-history-audit.json'),
        'unit_audit_sha256': fingerprint(SOURCE/'ohlc-unit-crosscheck.json'),
        'certified_sessions': certified, 'as_of': dataset.manifest.unpack()['captured_at'],
        'price_basis': dataset.manifest.unpack()['price_basis'], 'scope': 'EXPLORATORY_DISCOVERY_ONLY',
        'permitted_horizons': [4, 64, 192], 'control_membership_hash': seal['membership_hash'],
        'confirmation_outcome_access': 0, 'MFE_MAE': 'NOT_CALCULATED', 'net_profitability': 'NOT_ESTIMATED'}
    action = json.loads((SOURCE/'action-history-audit.json').read_bytes())
    label_source['interval_certificate'] = {'dataset_id': DATASET_ID, 'dataset_hash': DATASET_HASH,
        'interval_start': dataset.bars[0].session, 'interval_end': dataset.bars[-1].session,
        'splits_inside_interval': action['splits_inside_interval'],
        'action_canonical_hash': digest(action), 'unit_raw_sha256': fingerprint(SOURCE/'ohlc-unit-crosscheck.json'),
        'scope': 'EX_POST_GROSS_RAW_PRICE_LABEL_UNITS_NOT_BAR_TIME_ABSENCE_KNOWLEDGE'}
    frozen.immutable(root/'label-source-manifest.json', encode(label_source))
    with guarded() as forbidden:
        reader = DiscoveryLabels(dataset.bars, persisted, seal['membership_hash'], certified, label_source['as_of'],
                                 interval_certificate=label_source['interval_certificate'])
        rows = evaluate_membership(persisted, reader)
        primary_metrics = family_metrics(rows)
        comparator_rows = [{**r, 'primary_event_id': r['event_id'], 'event_id': r['comparator_event_id']}
                           for r in rows if r['comparator_event_id']]
        comparator_metrics = family_metrics(comparator_rows)
    if any(forbidden.values()):
        raise ValueError('Forbidden outcome/profitability/network access')
    report = {'schema': 'h0002_first_discovery_efficacy_v1', 'scope': 'EXPLORATORY_DISCOVERY_ONLY',
        'protocol_hash': PROTOCOL_HASH, 'signal_freeze_hash': FREEZE_HASH,
        'dataset_id': DATASET_ID, 'dataset_hash': DATASET_HASH, 'candidate_stream_hash': digest(events),
        'control_membership_hash': digest(persisted), 'label_source_manifest_hash': digest(label_source),
        'primary': PRIMARY, 'comparator': COMPARATOR, 'primary_metrics': primary_metrics,
        'comparator_metrics': comparator_metrics, 'disposition': exploratory_disposition(primary_metrics),
        'comparator_disposition': exploratory_disposition(comparator_metrics),
        'uncertainty_status': 'DISCOVERY_UNCERTAINTY_NOT_PREREGISTERED',
        'confirmation_status': 'PENDING', 'confirmation_outcome_access': 0,
        'outcome_accessor_audit': dict(reader.audit), 'forbidden_calls': forbidden,
        'preparation_forbidden_calls': preparation_calls, 'profitability_calculations': 0,
        'controls_complete': sum(r['control_status'] == 'READY' for r in rows),
        'controls_unresolved': sum(r['control_status'] != 'READY' for r in rows),
        'retained_primary_event_ids': [r['event_id'] for r in rows],
        'overlap_policy': 'All distinct visits retained; overlapping forward windows/control reuse allowed.',
        'not_a_confirmation_or_profitability_result': True, 'confirmation_terminal_deadline': '2027-10-23T20:00:00-04:00'}
    for name, body in [('event-results.json', {'primary': rows, 'comparator': comparator_rows}),
                       ('outcome-access-audit.json', {'scope': label_source['scope'], 'counts': dict(reader.audit), 'trace': reader.trace}),
                       ('discovery-report.json', report)]:
        frozen.immutable(root/name, encode(body))
    if implementation != {p: preservation_fingerprint(p) for p in FILES}:
        raise ValueError('Evaluator implementation changed during execution')
    verify_contract()
    return report


if __name__ == '__main__':
    first, second = execute(), execute()
    if first != second:
        raise ValueError('Non-deterministic discovery report')
    frozen.immutable(ROOT/'repeat-proof.json', encode({'runs': 2, 'repeat_equal': True,
        'report_hash': digest(first), 'control_hash': first['control_membership_hash'],
        'confirmation_outcome_access': 0, 'frozen_protocol_unchanged': True, 'H0001_preserved': True}))
    print(json.dumps(first, indent=2))
