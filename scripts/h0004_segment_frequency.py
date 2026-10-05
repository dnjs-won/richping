"""H0004 trial2 frequency only; prior-session same-segment reference."""
from argparse import ArgumentParser
from collections import Counter
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import subprocess
import tarfile
import yaml

from richping.core import digest
from richping.research_v2.contracts import payload
from richping.research_v2.sessions import segment
from richping.research_v2.strategy.h0004_segment_compression import (
    Specification,CompressionStream,OHLCBar,SEGMENTS)
from scripts.h0004_frequency_audit import (
    ROOT as TRIAL1, SOURCE, DATASET_HASH, DATASET_ID, encode, fingerprint,
    preserved_raw,preserved_bytes,write_new,no_outcomes,load_admitted)

BASE = '9560d57d4c049324727cdd9dde5c124d05b7c2d6'
ROOT = Path('research/data_evidence/h0004-segment-frequency-20261005')
SPEC = Path('research/strategy_specs/H0004-r01-candidate-segment-v2.yaml')
EXECUTION = [SPEC,Path('richping/research_v2/strategy/h0004_segment_compression.py'),
             Path('scripts/h0004_segment_frequency.py'),Path('docs/H0004_SEGMENT_REFERENCE_REMEDIATION.md')]


def seal(root=ROOT):
    spec = yaml.safe_load(SPEC.read_bytes())
    if (spec['parameters'] != payload(Specification()) or spec['outcomes']!='FORBIDDEN'
            or spec['trial']!='TRIAL_2_SEGMENT_CONDITIONED_REFERENCE'):
        raise ValueError('Owner-authorized final tuple required')
    # Archive supplies Git BASE bytes, not a potentially changed working tree.
    raw = subprocess.run(['git','archive','--format=tar',BASE],check=True,capture_output=True).stdout
    protected = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as tree:
        for member in tree.getmembers():
            if not member.isfile() or member.name in ('.gitattributes','PROJECT_STATUS.md'):
                continue
            expected = preserved_raw(member.name,tree.extractfile(member).read())
            if preserved_bytes(member.name)!=expected:
                raise ValueError('Prior Git BASE file changed: '+member.name)
            protected[member.name] = expected
    body = dict(schema='h0004_trial2_pre_frequency_manifest_v1',base_commit=BASE,
        sealed_at=datetime.now(timezone.utc).isoformat(),trial='TRIAL_2_SEGMENT_CONDITIONED_REFERENCE',
        parameter_trials=2,new_parameter_trials=1,comparators=0,outcomes='FORBIDDEN',
        owner_conditional_final_freeze=True,last_pre_outcome_trial=True,
        execution_files={p.as_posix():fingerprint(p) for p in EXECUTION},preserved_files=protected,
        inputs={str(SOURCE/n).replace('\\','/'):fingerprint(SOURCE/n) for n in ('intraday-vintage.json','admission.json')},
        trial1=dict(identity='TRIAL_1_POOLED_SEGMENT_REFERENCE',report_path=(TRIAL1/'frequency-audit.json').as_posix(),
                    report_sha256=fingerprint(TRIAL1/'frequency-audit.json'),candidate_events=39,candidate_sessions=26,
                    outcome_access=0))
    if (root/'preexecution-manifest.json').exists():
        body['sealed_at'] = json.loads((root/'preexecution-manifest.json').read_bytes())['sealed_at']
    write_new(root/'preexecution-manifest.json',encode(body))
    return body


def verify_manifest(root=ROOT):
    manifest = json.loads((root/'preexecution-manifest.json').read_bytes())
    if manifest['base_commit']!=BASE or manifest['parameter_trials']!=2 or manifest['outcomes']!='FORBIDDEN':
        raise ValueError('Trial2 manifest identity changed')
    for group in ('execution_files','inputs','preserved_files'):
        for path,expected in manifest[group].items():
            actual = preserved_bytes(path) if group=='preserved_files' else fingerprint(path)
            if actual!=expected: raise ValueError('Sealed/prior file changed: '+path)
    return manifest


def replay(bars,spec=Specification()):
    stream = CompressionStream(spec)
    counts = Counter({k:0 for k in ('eligible_bars','compression_READY','compressed','compression_runs',
        'unique_compression_episodes','frozen_ranges','breakout_evaluations','candidates',
        'expired','downside_cancelled','gap_cancelled','invalid_cancelled','consumed','gap_resets')})
    segments = {s:Counter(eligible_bars=0,reference_READY=0,compression_READY=0,compressed=0,candidates=0,ranges=0)
                for s in SEGMENTS}
    ref_sizes = {s:Counter() for s in SEGMENTS}
    unavailable,sessions = Counter(),{}
    events,ranges = [],[]
    chain = None
    prior_compressed = False
    for item in bars:
        bar = item if isinstance(item,OHLCBar) else OHLCBar.from_market(item)
        step = stream.accept(bar,bar.known_at)
        feature = step.feature
        part = segment(bar.end_at-timedelta(minutes=15),bar.end_at)
        seg = segments[part]
        day = sessions.setdefault(bar.session,Counter(eligible_bars=0,candidates=0))
        eligible,ready,compressed = step.input_status=='READY',feature.status=='READY',feature.compressed is True
        counts['eligible_bars'] += eligible
        counts['compression_READY'] += ready
        counts['compressed'] += compressed
        counts['compression_runs'] += compressed and not prior_compressed
        prior_compressed = compressed
        counts['breakout_evaluations'] += step.breakout_evaluated
        counts['gap_resets'] += step.input_reason=='gap_reset'
        seg['eligible_bars'] += eligible
        seg['reference_READY'] += feature.reference_status=='READY'
        seg['compression_READY'] += ready
        seg['compressed'] += compressed
        day['eligible_bars'] += eligible
        if ready: ref_sizes[part][str(feature.reference_count)] += 1
        if not eligible: unavailable['input:'+step.input_reason] += 1
        if not ready: unavailable['feature:'+feature.reason] += 1
        if step.range_published:
            ranges.append(payload(step.range_published))
            counts['unique_compression_episodes'] += 1
            counts['frozen_ranges'] += 1
            seg['ranges'] += 1
        if step.retirement:
            key = {'invalid_input':'invalid_cancelled'}.get(step.retirement,step.retirement)
            counts[key] += 1
        for event in step.events:
            events.append(payload(event))
            counts['candidates'] += 1
            seg['candidates'] += 1
            day['candidates'] += 1
        chain = digest([chain,payload(step)])
    counts['pending'] = int(stream.range is not None)
    counts['candidate_sessions'] = sum(v['candidates']>0 for v in sessions.values())
    for value in segments.values():
        value['compression_rate'] = value['compressed']/value['compression_READY'] if value['compression_READY'] else None
    return dict(counts=dict(counts),segments={s:dict(v) for s,v in segments.items()},
        reference_counts={s:dict(v) for s,v in ref_sizes.items()},unavailable=dict(unavailable),
        sessions={s:dict(v) for s,v in sessions.items()},events=events,ranges=ranges,
        event_stream_hash=digest(events),range_stream_hash=digest(ranges),trace_hash=chain)


def audit(root=ROOT):
    manifest = verify_manifest(root)
    with no_outcomes() as calls:
        data = load_admitted()
        first,second = replay(data.bars),replay(data.bars)
        prefix = replay(data.bars[:2240])
    at = data.bars[2239].known_at.isoformat()
    if (first!=second or prefix['events']!=[e for e in first['events'] if e['at']<=at]
            or prefix['ranges']!=[r for r in first['ranges'] if r['published_at']<=at] or any(calls.values())):
        raise ValueError('Causality/repeat/outcome guard failed')
    if len({e['episode_id'] for e in first['events']})!=len(first['events']):
        raise ValueError('Duplicate episode candidate')
    verify_manifest(root)
    report = dict(schema='h0004_trial2_frequency_v1',trial='TRIAL_2_SEGMENT_CONDITIONED_REFERENCE',
        **{k:v for k,v in first.items() if k not in ('events','ranges')},parameter_trials=2,new_parameter_trials=1,
        comparators=0,dataset_id=DATASET_ID,dataset_hash=DATASET_HASH,spec_hash=Specification().content_hash,
        repeat_equal=True,prefix_equal=True,full_replays=2,prefix_replays=1,
        forbidden_call_counts=calls,outcome_access=0,forward_returns=0,efficacy_calculations=0,
        profitability='NOT_ESTIMATED',confirmation_outcome_access=0,
        protected_files=len(manifest['preserved_files']),trial1_preserved=True,H0001_H0002_H0003_preserved=True,
        final_owner_authority='PREAUTHORIZED_IF_CAUSAL_DETERMINISTIC_NONZERO_MECHANICALLY_VALID',
        last_pre_outcome_trial=True,no_threshold_window_or_count_target_tuning=True)
    write_new(root/'frequency-audit.json',encode(report))
    write_new(root/'candidate-events.json',encode(dict(events=first['events'])))
    write_new(root/'frozen-ranges.json',encode(dict(ranges=first['ranges'])))
    write_new(root/'trial-ledger.json',encode(dict(schema='h0004_two_trial_ledger_v1',parameter_trials=2,
        trials=[manifest['trial1'],dict(identity=report['trial'],report_path=(root/'frequency-audit.json').as_posix(),
            report_sha256=fingerprint(root/'frequency-audit.json'),outcome_access=0,forward_returns=0,
            efficacy=0,profitability='NOT_ESTIMATED',spec_hash=report['spec_hash'])],
        reason='Owner time-of-day semantic correction before outcomes; not performance selection',
        third_variant='FORBIDDEN_ABSENT_IMPLEMENTATION_OR_SEMANTIC_BLOCKER')))
    return report


if __name__=='__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--seal',action='store_true')
    args = parser.parse_args()
    result = seal() if args.seal else audit()
    print(json.dumps({k:v for k,v in result.items() if k in ('trial','counts','segments','parameter_trials','forbidden_call_counts')},indent=2))
