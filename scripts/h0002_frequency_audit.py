"""Sealed H0002 frequency-only replay on the previously admitted immutable vintage."""
from argparse import ArgumentParser
from collections import Counter
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from unittest.mock import patch
import yaml

from richping.core import canonical, digest
from richping.research_v2.contracts import payload
from richping.research_v2.market_data import MarketDataset
from richping.research_v2.strategy.h0002_defense import (
    Specification, DefenseStream, PriceBar, PRIMARY, COMPARATOR)
from scripts.h0001_long_history_audit import write_new

ORIGINAL = Path('research/data_evidence/h0002-frequency-20261004')
ROOT = ORIGINAL/'verification-v2'
SOURCE = Path('research/data_evidence/h0001-alpaca-70-20261004')
SPEC = Path('research/strategy_specs/H0002-r01-candidate.yaml')
HYPOTHESIS = Path('research/hypotheses/H0002-r01.yaml')
BASE = 'a014d4704b551ed80b9eb38fb57bac0308bb1e7c'
DATASET_ID = 'soxx-alpaca-sip-15m-discovery-20260505-20260813-v1'
DATASET_HASH = '4b39f109e8cffce8a7e680e773b560b307e21dd5a92dcad6d06fcd47bb0aa8bd'
EXECUTION_FILES = [SPEC, HYPOTHESIS, Path('richping/research_v2/strategy/h0002_defense.py'),
                   Path('scripts/h0002_frequency_audit.py'), Path('docs/H0002_PRICE_DEFENSE_RESEARCH.md')]
FORBIDDEN = {
    'richping.engine.observe': 'outcome_accessor',
    'richping.evaluation.evaluate_outcome_eligibility': 'outcome_accessor',
    'richping.data.Dataset.window': 'forward_or_benchmark_window',
    'richping.store.Store.load_dataset': 'operational_store',
    'richping.research_v2.store.ResearchStore.load_dataset': 'store_accessor',
    'richping.research_v2.market_data.MarketDataset.query': 'market_query',
    'richping.engine.features': 'return_calculation',
    'richping.evaluation.cohort_returns': 'return_calculation',
    'richping.evaluation.metrics': 'profitability_calculation',
    'richping.evaluation.estimate': 'profitability_calculation',
    'richping.evaluation.block_ci': 'uncertainty_calculation',
    'socket.socket.connect': 'network',
    'socket.create_connection': 'network',
    'urllib.request.urlopen': 'network',
    'curl_cffi.requests.get': 'network',
}


def encode(body):
    return (json.dumps(body, indent=2, sort_keys=True) + '\n').encode()


def fingerprint(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def preservation_fingerprint(path):
    # Source text is Git newline portable; archived evidence remains byte exact.
    raw = Path(path).read_bytes()
    if not str(path).replace('\\', '/').startswith('research/data_evidence/'):
        raw = raw.replace(b'\r\n', b'\n')
    return sha256(raw).hexdigest()


def protected_paths():
    paths = subprocess.run(['git', 'ls-tree', '-r', '--name-only', BASE],
                           check=True, capture_output=True, text=True).stdout.splitlines()
    return [p for p in paths if p.startswith(('richping/research_v2/', 'research/', 'scripts/h0001_'))
            or p.startswith('docs/') and ('H0001' in p or 'V2_' in p)]


def seal(root=ROOT):
    """No market file is opened: bind one proposal before observing its frequency."""
    body = yaml.safe_load(SPEC.read_text(encoding='utf-8'))
    if body['status'] != 'PROVISIONAL_FREQUENCY_ONLY_NOT_SIGNAL_FREEZE' or body['outcomes'] != 'FORBIDDEN':
        raise ValueError('Frequency-only contract required')
    Specification(**body['parameters'])
    manifest = {'schema': 'h0002_pre_frequency_manifest_v1', 'base_commit': BASE,
                'sealed_at': datetime.now(timezone.utc).isoformat(), 'parameter_trials': 1,
                'families': [PRIMARY, COMPARATOR], 'outcomes': 'FORBIDDEN',
                'execution_files': {p.as_posix(): fingerprint(p) for p in EXECUTION_FILES},
                'preserved_files': {p: preservation_fingerprint(p) for p in protected_paths()},
                'dataset_id': DATASET_ID, 'dataset_hash': DATASET_HASH,
                'predecessor': {'manifest': (ORIGINAL/'preexecution-manifest.json').as_posix(),
                    'report_sha256': fingerprint(ORIGINAL/'frequency-audit.json'),
                    'original_runner_sha256': fingerprint(ORIGINAL/'frequency-audit-source-v1.py.bin'),
                    'reason': 'Host preservation portability: Git source newline canonicalization only; signal module/spec unchanged.',
                    'prior_frequency_exposure': {'primary': 14, 'comparator': 11},
                    'new_parameter_trials': 0},
                'owner_final_freeze': 'PENDING_NOT_AUTHORIZED_BY_FREQUENCY_EXECUTION'}
    original = json.loads((ORIGINAL/'preexecution-manifest.json').read_bytes())
    for p in EXECUTION_FILES:
        if p.as_posix() != 'scripts/h0002_frequency_audit.py' and fingerprint(p) != original['execution_files'][p.as_posix()]:
            raise ValueError('Portability verification cannot change signal contract/source')
    if manifest['predecessor']['original_runner_sha256'] != original['execution_files']['scripts/h0002_frequency_audit.py']:
        raise ValueError('Original execution source not preserved')
    path = root/'preexecution-manifest.json'
    if path.exists():
        old = json.loads(path.read_bytes())
        # Preserve the original sealing time; all other content must match.
        manifest['sealed_at'] = old['sealed_at']
    write_new(path, encode(manifest))
    return manifest


def verify_manifest(root=ROOT):
    manifest = json.loads((root/'preexecution-manifest.json').read_bytes())
    if (manifest['base_commit'], manifest['dataset_id'], manifest['dataset_hash']) != (BASE, DATASET_ID, DATASET_HASH):
        raise ValueError('Manifest identity changed')
    for group in ('execution_files', 'preserved_files'):
        for p, expected in manifest[group].items():
            actual = preservation_fingerprint(p) if group == 'preserved_files' else fingerprint(p)
            if actual != expected:
                raise ValueError('Sealed/preserved source changed: ' + p)
    return manifest


@contextmanager
def no_outcomes():
    counts = {category: 0 for category in FORBIDDEN.values()}
    def reject(category):
        def forbidden(*args, **kwargs):
            counts[category] += 1
            raise AssertionError('H0002 frequency forbids ' + category)
        return forbidden
    with ExitStack() as stack:
        for target, category in FORBIDDEN.items():
            stack.enter_context(patch(target, side_effect=reject(category)))
        yield counts


def load_admitted():
    # Portable full vintage is a host input, never passed to the signal module.
    # No event-conditioned future/label window or Daily/1H prices are read.
    vintage = json.loads((SOURCE/'intraday-vintage.json').read_bytes())
    dataset = MarketDataset.from_records(vintage['dataset_id'], vintage['bars'], vintage['manifest'])
    admission = json.loads((SOURCE/'admission.json').read_bytes())
    if (dataset.dataset_id, dataset.content_hash, vintage['content_hash']) != (DATASET_ID, DATASET_HASH, DATASET_HASH):
        raise ValueError('Immutable vintage/hash mismatch')
    if dataset.manifest.unpack()['admission'] != admission or admission['status'] != 'PASS':
        raise ValueError('Admission mismatch')
    if dataset.gaps or len(dataset.bars) != 4480 or {b.symbol for b in dataset.bars} != {'SOXX'}:
        raise ValueError('Exact admitted SOXX grid required')
    return dataset


def replay(bars, spec):
    stream = DefenseStream(spec)
    counts, reasons, sessions, zones, events = Counter(), Counter(), {}, [], []
    chain = None
    for bar in bars:
        step = stream.accept(PriceBar.from_market(bar), bar.known_at)
        counts['total_eligible_15m_bars'] += step.input.status == 'READY'
        counts['zone_READY_count'] += step.construction.status == 'READY'
        counts['active_zone_bar_count'] += step.zone_before is not None
        counts['zone_reentry_count'] += step.interaction.flag is True
        counts['touch_only_reentry_count'] += step.touch
        counts['penetration_reentry_count'] += step.penetration
        counts['rejection_primitive_count'] += step.rejection.flag is True
        counts['volume_READY_count'] += step.volume.status == 'READY'
        counts['volume_confirmed_count'] += step.rejection.flag is True and step.volume.flag is True
        for stage in ('input', 'construction', 'interaction', 'rejection', 'volume'):
            state = getattr(step, stage)
            reasons[f'{stage}:{state.status}:{state.reason}'] += 1
        if step.zone_published:
            zones.append(payload(step.zone_published))
        if step.retired_reason:
            counts['retired_' + step.retired_reason] += 1
        day = sessions.setdefault(bar.session, Counter(eligible_bars=0, primary=0, comparator=0, reentries=0))
        day['eligible_bars'] += step.input.status == 'READY'
        day['reentries'] += step.interaction.flag is True
        for event in step.events:
            events.append(payload(event))
            day['primary' if event.family == PRIMARY else 'comparator'] += 1
        chain = digest([chain, payload(step)])
    primary = [e for e in events if e['family'] == PRIMARY]
    comparator = [e for e in events if e['family'] == COMPARATOR]
    primary_ids = {e['id'] for e in primary}
    comparator_prices = {e['snapshot']['price_event_id'] for e in comparator}
    if len({e['id'] for e in events}) != len(events) or not comparator_prices <= primary_ids:
        raise ValueError('Duplicate or unmatched comparator event')
    counts.update(active_zone_count=len(zones), final_candidate_count=len(primary),
                  volume_final_candidate_count=len(comparator),
                  distinct_sessions_with_candidates=len({e['session'] for e in primary}),
                  distinct_sessions_with_volume_candidates=len({e['session'] for e in comparator}))
    return {'denominators': dict(sorted(counts.items())), 'stage_reasons': dict(sorted(reasons.items())),
            'session_denominators': {k: dict(v) for k, v in sorted(sessions.items())},
            'overlap': {'both': len(comparator_prices), 'price_only': len(primary_ids-comparator_prices),
                        'comparator_only': len(comparator_prices-primary_ids)},
            'trace_chain_hash': chain, 'event_stream_hash': digest(events),
            'zones_hash': digest(zones), 'events': events, 'zones': zones}


def audit(root=ROOT):
    manifest = verify_manifest(root)
    raw_before = {p: fingerprint(p) for p in manifest['preserved_files']}
    body = yaml.safe_load(SPEC.read_text(encoding='utf-8'))
    spec = Specification(**body['parameters'])
    with no_outcomes() as calls:
        first_dataset = load_admitted()
        first = replay(first_dataset.bars, spec)
        second_dataset = load_admitted()
        second = replay(second_dataset.bars, spec)
        if first != second or any(calls.values()):
            raise ValueError('Non-deterministic replay or forbidden access')
    if manifest != verify_manifest(root) or raw_before != {p: fingerprint(p) for p in raw_before}:
        raise ValueError('Source changed during audit')
    report = {'schema': 'h0002_frequency_audit_v1', 'hypothesis_id': 'H0002',
              'status': 'COMPLETE_FREQUENCY_ONLY', 'specification_sha256': fingerprint(SPEC),
              'preexecution_manifest_sha256': fingerprint(root/'preexecution-manifest.json'),
              'dataset_id': DATASET_ID, 'dataset_hash': DATASET_HASH,
              'interval': ['2026-05-05', '2026-08-13'], 'sessions': 70,
              'primary': PRIMARY, 'comparator': COMPARATOR, 'parameter_trials': 1,
              **{k: v for k, v in first.items() if k not in ('events', 'zones')},
              'candidate_timestamps': {family: [e['at'] for e in first['events'] if e['family'] == family]
                                       for family in (PRIMARY, COMPARATOR)},
              'runs': 2, 'repeat_equal': True, 'forbidden_call_counts': calls,
              'outcome_access': 0, 'profitability_calculations': 0, 'outcomes': 'NOT_RUN',
              'H0001_preserved_files': len(manifest['preserved_files']),
              'H0001_frozen_hashes_unchanged': True,
              'preservation_policy': 'Archived evidence byte exact; source LF canonical for Git portability; all actual bytes identical before/after replay.',
              'H0001_status': ['FROZEN', 'AWAITING_FUTURE_CONFIRMATION', 'HISTORICALLY_SPARSE'],
              'volume_integrity': {'missing': sum(b.volume is None for b in first_dataset.bars),
                                   'zero': sum(b.volume == 0 for b in first_dataset.bars),
                                   'meaning': 'Admitted condition-eligible SIP bar shares; no buying-intent inference.'},
              'frequency_disposition': 'NONZERO_MECHANICALLY_EXECUTABLE' if first['denominators']['final_candidate_count'] else 'ZERO_DECOMPOSE_READINESS_BEFORE_SEMANTIC_CHANGE',
              'final_signal_freeze': 'USER_DECISION_REQUIRED',
              'next_P0': 'H0002_SIGNAL_FREEZE_PREREGISTRATION',
              'economic_effect': None,
              'limitations': ['Discovery, not efficacy/alpha or independent event sample-size certification.',
                             'Immutable historical bar-end assumed availability, not live/shadow PIT.',
                             'No event-conditioned future price, label, return, MFE or MAE query.',
                             'Full admitted intraday vintage read twice only as chronological causal input.',
                             'Extended/RTH volume seasonality not normalized; no count-based relaxation.']}
    original_report = json.loads((ORIGINAL/'frequency-audit.json').read_bytes())
    if any(report[k] != original_report[k] for k in ('denominators', 'event_stream_hash', 'zones_hash', 'trace_chain_hash')):
        raise ValueError('Host-only verification changed frequency')
    for name, result in [('frequency-audit.json', report), ('candidate-events.json', {'events': first['events']}),
                         ('published-zones.json', {'zones': first['zones']})]:
        write_new(root/name, encode(result))
    return report


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--seal', action='store_true')
    args = parser.parse_args()
    result = seal() if args.seal else audit()
    print(canonical({k: result[k] for k in ('status', 'denominators', 'overlap', 'forbidden_call_counts') if k in result}))


if __name__ == '__main__':
    main()
