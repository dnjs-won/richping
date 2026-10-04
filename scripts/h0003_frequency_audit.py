"""Outcome-free sealed paired-stream frequency evidence for H0003."""
from argparse import ArgumentParser
from collections import Counter
from contextlib import contextmanager, ExitStack
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
from unittest.mock import patch
import yaml

from richping.core import digest, timestamp
from richping.research_v2.contracts import payload
from richping.research_v2.strategy.h0003_leadership import CloseBar, LeadershipStream, Specification, CONTRACT
from richping.research_v2.sessions import NY
from scripts.h0003_benchmark_admission import ROOT as QQQ_ROOT, load_capture, admission
from scripts.h0002_frequency_audit import load_admitted, FORBIDDEN, fingerprint, preservation_fingerprint, encode
from scripts.h0001_long_history_audit import write_new

ROOT = Path('research/data_evidence/h0003-frequency-20261004')
SPEC = Path('research/strategy_specs/H0003-r01-candidate.yaml')
BASE = '62992b202e37856a112ee45cc178a15dfd0c8899'
EXECUTION = [SPEC, Path('research/hypotheses/H0003-r01.yaml'),
             Path('docs/H0003_RELATIVE_STRENGTH_RESEARCH.md'),
             Path('richping/research_v2/strategy/h0003_leadership.py'),
             Path('scripts/h0003_benchmark_admission.py'), Path('scripts/h0003_frequency_audit.py')]
GUARDS = {**FORBIDDEN,
          'richping.research_v2.strategy.h0002_efficacy.scheduled_window': 'forward_window',
          'richping.research_v2.strategy.h0002_efficacy.evaluate_membership': 'outcome_accessor',
          'richping.research_v2.strategy.h0002_efficacy.family_metrics': 'efficacy_statistics',
          'richping.research_v2.strategy.h0002_efficacy.terminal_inference': 'confirmation_outcomes'}


@contextmanager
def no_outcomes():
    counts = {key: 0 for key in GUARDS.values()}
    def reject(category):
        def forbidden(*args, **kwargs):
            counts[category] += 1
            raise AssertionError('H0003 frequency forbids '+category)
        return forbidden
    with ExitStack() as stack:
        for target, category in GUARDS.items():
            stack.enter_context(patch(target, side_effect=reject(category)))
        yield counts


def protected_paths():
    paths = subprocess.run(['git','ls-tree','-r','--name-only',BASE], check=True,
                           capture_output=True, text=True).stdout.splitlines()
    return [p for p in paths if p.startswith(('richping/', 'research/', 'scripts/', 'tests/', 'docs/'))]


def seal(root=ROOT):
    body = yaml.safe_load(SPEC.read_text(encoding='utf-8'))
    if body['outcomes'] != 'FORBIDDEN' or body['status'] != 'PROVISIONAL_FREQUENCY_ONLY_NOT_SIGNAL_FREEZE':
        raise ValueError('Frequency-only provisional spec required')
    Specification(**body['parameters'])
    capture_paths = sorted(QQQ_ROOT.glob('capture-*.json'))
    receipt_paths = sorted((QQQ_ROOT/'raw').glob('*.json'))
    if not capture_paths or not (QQQ_ROOT/'admission.json').exists():
        raise ValueError('QQQ admission must precede signal sealing')
    inputs = [*capture_paths, *receipt_paths, QQQ_ROOT/'admission.json', QQQ_ROOT/'offline-proof.json']
    manifest = dict(schema='h0003_pre_frequency_manifest_v1', base_commit=BASE,
                    sealed_at=datetime.now(timezone.utc).isoformat(), parameter_trials=1,
                    outcomes='FORBIDDEN', final_freeze='USER_DECISION_REQUIRED',
                    execution_files={p.as_posix(): fingerprint(p) for p in EXECUTION},
                    input_files={p.as_posix(): fingerprint(p) for p in inputs},
                    preserved_files={p: preservation_fingerprint(p) for p in protected_paths()})
    path = root/'preexecution-manifest.json'
    if path.exists():
        manifest['sealed_at'] = json.loads(path.read_bytes())['sealed_at']
    write_new(path, encode(manifest))
    return manifest


def verify_manifest(root=ROOT):
    m = json.loads((root/'preexecution-manifest.json').read_bytes())
    if m['base_commit'] != BASE or m['parameter_trials'] != 1 or m['outcomes'] != 'FORBIDDEN':
        raise ValueError('Manifest identity mismatch')
    for group in ('execution_files', 'input_files', 'preserved_files'):
        for p, expected in m[group].items():
            actual = preservation_fingerprint(p) if group == 'preserved_files' else fingerprint(p)
            if actual != expected:
                raise ValueError('Sealed/preserved file changed: '+p)
    return m


def paired_inputs():
    own_dataset = load_admitted()
    qqq_capture = load_capture()
    qqq_admission = admission(qqq_capture)
    if qqq_admission != json.loads((QQQ_ROOT/'admission.json').read_bytes()) or qqq_admission['status'] != 'PASS':
        raise ValueError('QQQ immutable admission mismatch or blocked')
    own_meta = own_dataset.manifest.unpack()
    if (own_meta['feed'], own_meta['adjustment'], own_meta['currency'], own_meta['known_at_policy']) != (
            'sip', 'raw', 'USD', qqq_admission['known_at_policy']):
        raise ValueError('Paired provider/feed/adjustment/unit/clock mismatch')
    own = [CloseBar(b.dataset_id,b.symbol,b.start_at,b.end_at,b.known_at,b.session,b.close,
                    CONTRACT,True) for b in own_dataset.bars]
    qqq_id = 'qqq-alpaca-sip-15m-discovery-20260505-20260813-'+digest(qqq_capture)[:16]
    benchmark = []
    for row in qqq_capture['cases']['raw']['rows']:
        start = timestamp(row['t'])
        end = start+timedelta(minutes=15)
        if end > timestamp(qqq_capture['captured_at']):
            raise ValueError('Benchmark captured before completion')
        benchmark.append(CloseBar(qqq_id,'QQQ',start,end,end,start.astimezone(NY).date().isoformat(),
                                  row['c'],CONTRACT,True))
    metadata = dict(own_dataset_id=own_dataset.dataset_id, own_dataset_hash=own_dataset.content_hash,
                    benchmark_dataset_id=qqq_id, benchmark_capture_hash=digest(qqq_capture),
                    benchmark_admission_hash=digest(qqq_admission), paired_contract=list(CONTRACT),
                    benchmark_vintage_hash=digest(payload(benchmark)))
    return own, benchmark, metadata


def replay(own, benchmark, spec):
    own_map = {b.end_at:b for b in own}
    bench_map = {b.end_at:b for b in benchmark}
    if len(own_map) != len(own) or len(bench_map) != len(benchmark):
        raise ValueError('Duplicate slot identity')
    stream = LeadershipStream(spec)
    counts = Counter({k:0 for k in ('both_series_READY_bars','relative_strength_READY_bars',
                                   'leadership_state_count','leadership_episode_count','candidate_event_count',
                                   'data_session_mismatch_count','absolute_guard_pass_bars',
                                   'positive_relative_return_bars','positive_RS_guard_fail_bars')})
    reasons, sessions, segments, events, chain = Counter(), {}, {}, [], None
    for at in sorted(set(own_map)|set(bench_map)):
        a,b = own_map.get(at),bench_map.get(at)
        step = stream.accept(a,b,at)
        counts['both_series_READY_bars'] += step.pair_ready
        counts['relative_strength_READY_bars'] += step.rs_ready
        counts['leadership_state_count'] += step.leadership
        counts['leadership_episode_count'] += step.episode_started
        counts['absolute_guard_pass_bars'] += step.guard is True
        counts['positive_relative_return_bars'] += step.rs_ready and step.relative_return > 0
        counts['positive_RS_guard_fail_bars'] += step.rs_ready and step.relative_return > 0 and not step.guard
        counts['data_session_mismatch_count'] += not step.pair_ready
        reasons[step.reason] += 1
        day = (a or b).session
        session = sessions.setdefault(day, Counter(pairs=0,rs_ready=0,candidates=0))
        session['pairs'] += step.pair_ready
        session['rs_ready'] += step.rs_ready
        local_start = (a or b).start_at.astimezone(NY)
        minute = local_start.hour*60+local_start.minute
        segment = 'PREMARKET' if minute < 570 else 'RTH' if minute < 960 else 'AFTER_HOURS'
        part = segments.setdefault(segment,Counter(pairs=0,rs_ready=0,candidates=0))
        part['pairs'] += step.pair_ready
        part['rs_ready'] += step.rs_ready
        if step.event:
            event = step.event.unpack()
            events.append(event)
            session['candidates'] += 1
            part['candidates'] += 1
        chain = digest([chain,payload(step)])
    if len({e['id'] for e in events}) != len(events) or len({e['episode_id'] for e in events}) != len(events):
        raise ValueError('Duplicate leadership episode emission')
    counts.update(candidate_event_count=len(events), distinct_sessions=len(sessions),
                  candidate_sessions=len({e['session'] for e in events}),
                  scheduled_pair_slots=len(set(own_map)|set(bench_map)))
    return dict(denominators=dict(counts), reasons=dict(reasons),
                session_denominators={k:dict(v) for k,v in sessions.items()},
                segment_denominators={k:dict(v) for k,v in segments.items()},
                candidate_timestamps=[e['at'] for e in events], events=events,
                event_stream_hash=digest(events), trace_chain_hash=chain)


def audit(root=ROOT):
    manifest = verify_manifest(root)
    raw_before = {p:fingerprint(p) for p in manifest['preserved_files']}
    spec = Specification(**yaml.safe_load(SPEC.read_text(encoding='utf-8'))['parameters'])
    with no_outcomes() as calls:
        own,benchmark,metadata = paired_inputs()
        first = replay(own,benchmark,spec)
        second_own,second_bench,second_meta = paired_inputs()
        second = replay(second_own,second_bench,spec)
        if first != second or metadata != second_meta or any(calls.values()):
            raise ValueError('Replay mismatch or forbidden access')
        # Independently reproduce a causal prefix; future suffix never revises it.
        cutoff = len(own)//2
        prefix = replay(own[:cutoff],benchmark[:cutoff],spec)
        prefix_events = [e for e in first['events'] if timestamp(e['at']) <= own[cutoff-1].end_at]
        if prefix['events'] != prefix_events:
            raise ValueError('Published prefix changed by future suffix')
    if manifest != verify_manifest(root) or raw_before != {p:fingerprint(p) for p in raw_before}:
        raise ValueError('Frozen evidence changed during replay')
    report = dict(schema='h0003_frequency_audit_v1', status='COMPLETE_FREQUENCY_ONLY',
                  hypothesis='H0003-r01', interval=['2026-05-05','2026-08-13'],
                  **metadata, **{k:v for k,v in first.items() if k != 'events'},
                  parameter_trials=1, comparators=0, repeat_equal=True, runs=2,
                  prefix_equal=True, forbidden_call_counts=calls, outcome_access=0,
                  profitability='NOT_RUN', efficacy='NOT_RUN', economic_effect=None,
                  preserved_files=len(manifest['preserved_files']), frozen_evidence_unchanged=True,
                  specification_hash=spec.hash, specification_sha256=fingerprint(SPEC),
                  manifest_sha256=fingerprint(root/'preexecution-manifest.json'),
                  frequency_disposition='NONZERO_MECHANICALLY_EXECUTABLE' if first['events'] else 'ZERO_REQUIRES_CAUSE_DECOMPOSITION',
                  final_signal_freeze='USER_DECISION_REQUIRED', next_P0='H0003_SIGNAL_FREEZE_PREREGISTRATION',
                  limitations=['Frequency is not performance or independent sample-size evidence.',
                               'QQQ technology/growth comparator; no broad-market generalization.',
                               'Historical assumed availability; not fresh shadow/live PIT.',
                               'Trailing price return only; dividend outcome accounting separate.',
                               'Complete extended grid does not prove extended liquidity equivalence.'])
    write_new(root/'frequency-audit.json',encode(report))
    write_new(root/'candidate-events.json',encode({'events':first['events']}))
    write_new(root/'benchmark-vintage.json',encode({'bars':payload(benchmark),**metadata}))
    return report


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--seal',action='store_true')
    args = parser.parse_args()
    r = seal() if args.seal else audit()
    print(json.dumps({k:r[k] for k in ('status','denominators','forbidden_call_counts') if k in r}))
