"""First bounded H0004 discovery execution. Never regenerates the frozen signal."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
from contextlib import contextmanager, ExitStack
from datetime import timedelta
import io
import json
from pathlib import Path
from statistics import mean, median
import subprocess
import tarfile
from unittest.mock import patch
import yaml

from richping.core import digest, timestamp
from richping.research_v2.contracts import payload
from richping.research_v2.sessions import segment
from richping.research_v2.strategy.h0004_experiment import scheduled_window
from scripts.h0004_frequency_audit import encode, write_new, fingerprint, preserved_bytes, preserved_raw, no_outcomes
from scripts.h0004_preaccess import DiscoveryPermit, ROOT as PREACCESS, zero_real_outcomes
from scripts.h0004_discovery_access import open_discovery

ACTION = 'H0004_DISCOVERY_EFFICACY_EXECUTION'
ROOT = Path('research/data_evidence/h0004-discovery-efficacy-20261005')
BOUND = ('scripts/h0004_discovery_execution.py', 'tests/test_h0004_discovery_execution.py')


def git(*args):
    return subprocess.run(['git', *args], check=True, capture_output=True).stdout


def gate():
    """All checks run without opening a vintage or mapping real endpoints."""
    with zero_real_outcomes() as calls:
        binding, anchors = DiscoveryPermit(ACTION).authorize()
        control = yaml.safe_load(git('show', 'main:PROJECT_CONTROL.yaml'))
        track = control['hypothesis_tracks']['H0004']
        manifest = json.loads((PREACCESS/'manifest.json').read_bytes())
        proof = json.loads((PREACCESS/'verification.json').read_bytes())
        clean = json.loads((PREACCESS/'clean-checkout-proof.json').read_bytes())
        if git('rev-parse','main') != git('rev-parse','origin/main'):
            raise ValueError('Canonical main is not the fetched origin/main')
        if (track['preaccess_manifest_sha256'] != fingerprint(PREACCESS/'manifest.json')
                or track['preaccess_verification_sha256'] != fingerprint(PREACCESS/'verification.json')
                or clean['exit_code'] != 0 or not clean['clean_archive'] or clean['result'] != proof
                or (proof['real_candidate_count'], proof['real_candidate_sessions'], proof['signal_trials']) != (48,29,2)
                or (manifest['candidate_count'],manifest['candidate_sessions'],manifest['signal_trials']) != (48,29,2)
                or track['candidate_stream_hash'] != binding.candidate_stream_hash
                or track['signal_freeze_sha256'] != binding.signal_freeze_hash
                or track['protocol_hash'] != binding.protocol_hash
                or len(anchors) != 48 or len({a.session for a in anchors}) != 29):
            raise ValueError('Canonical/pre-access/independent receipt/denominator mismatch')
    if any(calls['real_H0004'].values()) or any(v for g in calls['shared_forbidden'].values() for v in g.values()):
        raise ValueError('Pre-access gate opened real outcomes')
    return dict(status='VERIFIED_BEFORE_PRICE_ACCESS', action=ACTION,
        canonical_main_commit=git('rev-parse','main').decode().strip(),
        preaccess_manifest_sha256=fingerprint(PREACCESS/'manifest.json'),
        independent_verification_sha256=fingerprint(PREACCESS/'verification.json'),
        clean_verification_sha256=fingerprint(PREACCESS/'clean-checkout-proof.json'),
        binding=payload(binding), candidate_count=48, candidate_sessions=29, signal_trials=2,
        exact_candidates=payload(anchors), dataset_files=manifest['dataset_files'],
        frozen_sources=manifest['source_hashes'],
        frozen_records={p:fingerprint(p) for p in (
            'research/decision_records/H0004-signal-freeze-v1.json',
            'research/decision_records/H0004-efficacy-preregistration-v1.yaml',
            'research/decision_records/H0004-segment-remediation-v2.yaml',
            'research/decision_records/H0004-preaccess-evaluator-v1.yaml')},
        preaccess_outcome_counters=calls)


def protected_snapshot(commit):
    archive = git('archive','--format=tar',commit)
    result = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        for member in tree.getmembers():
            if member.isfile() and member.name not in ('.gitattributes','PROJECT_STATUS.md'):
                expected = preserved_raw(member.name,tree.extractfile(member).read())
                if preserved_bytes(member.name) != expected:
                    raise ValueError('Prior tracked file changed: '+member.name)
                result[member.name] = expected
    return result


def seal():
    checked = gate()
    # Parent is the already-published canonical workstream; all its bytes protected.
    base = git('rev-parse','v2-h0004-preaccess-evaluator').decode().strip()
    manifest = dict(schema='h0004_discovery_execution_manifest_v1', gate=checked,
        base_commit=base, protected_files=protected_snapshot(base),
        execution_sources={p:fingerprint(p) for p in BOUND},
        scope='DISCOVERY_EXPLORATORY', confirmation_outcome_access=0,
        uncertainty='NOT_CONFIRMATORY', profitability='NOT_ESTIMATED',
        authorization='Explicit owner H0004 discovery execution; no capture or tuning')
    write_new(ROOT/'manifest.json',encode(manifest))
    return checked


def verify_seal():
    manifest = json.loads((ROOT/'manifest.json').read_bytes())
    if manifest['gate'] != gate(): raise ValueError('Execution gate changed')
    for group in ('protected_files','execution_sources'):
        for p,expected in manifest[group].items():
            actual = preserved_bytes(p) if group=='protected_files' else fingerprint(p)
            if actual != expected: raise ValueError('Execution sealed file changed: '+p)
    return manifest


@contextmanager
def execution_guard():
    """Reuse existing no-network/no-statistics audit; reject signal and database use."""
    counts = dict(signal_regeneration=0, database=0, confirmation_accessor_calls=0)
    def reject(category):
        def denied(*args,**kwargs):
            counts[category] += 1
            raise AssertionError('Discovery execution forbids '+category)
        return denied
    with no_outcomes() as common, ExitStack() as stack:
        for target,category in {
            'richping.research_v2.strategy.h0004_compression.CompressionStream.accept':'signal_regeneration',
            'richping.research_v2.strategy.h0004_segment_compression.CompressionStream.accept':'signal_regeneration',
            'scripts.h0004_frequency_audit.replay':'signal_regeneration',
            'scripts.h0004_segment_frequency.replay':'signal_regeneration',
            'sqlite3.connect':'database'}.items():
            stack.enter_context(patch(target,side_effect=reject(category)))
        yield dict(common_forbidden=common, execution_forbidden=counts)


def describe(aggregate, rows):
    """No statistics of a resolved subset are produced, even as diagnostics."""
    if aggregate['status'] != 'COMPLETE':
        return dict(descriptive_disposition='DISCOVERY_INSUFFICIENT_RESOLVED_LABELS',
                    full_cohort_aggregate_available=False, metrics=None)
    values = [r['gross_return'] for r in rows]
    direction = aggregate['full_cohort_session_balanced_mean']
    disposition = ('DISCOVERY_POSITIVE_DIRECTION' if direction>0 else
                   'DISCOVERY_NEGATIVE_DIRECTION' if direction<0 else 'DISCOVERY_MIXED_DIRECTION')
    return dict(descriptive_disposition=disposition,full_cohort_aggregate_available=True,
        metrics=dict(candidate_count=len(rows),candidate_sessions=aggregate['candidate_sessions'],
            session_balanced_mean_R16=direction,event_median_R16=median(values),
            positive_count=sum(v>0 for v in values),positive_rate=sum(v>0 for v in values)/len(values),
            negative_count=sum(v<0 for v in values),negative_rate=sum(v<0 for v in values)/len(values),
            zero_count=sum(v==0 for v in values),min_R16=min(values),max_R16=max(values)))


def execute(name):
    if name not in ('run1','run2'): raise ValueError('Exactly two independent executions')
    manifest = verify_seal()  # BEFORE the first vintage parse or forward price read.
    with execution_guard() as forbidden:
        evaluator,reader = open_discovery(DiscoveryPermit(ACTION))
        rows = evaluator.evaluate(reader)
        aggregate = evaluator.aggregate(rows)
        paths = []
        segments = defaultdict(Counter)
        for anchor,row in zip(evaluator.anchors,rows):
            window,unsupported = scheduled_window(anchor.at)
            path = (timestamp(anchor.at),*window)
            paths.append(dict(event_id=anchor.event_id, target_at=window[-1].isoformat(),
                unsupported=unsupported, scheduled_slots=[dict(at=t.isoformat(),
                    metadata=payload(evaluator.slots[t]) if t in evaluator.slots else None) for t in path]))
            part = segment(timestamp(anchor.at)-timedelta(minutes=15),timestamp(anchor.at))
            segments[part]['candidates'] += 1
            segments[part][row['status']] += 1
        report = dict(schema='h0004_discovery_exploratory_report_v1',scope='DISCOVERY_EXPLORATORY',
            input_gate=manifest['gate'],aggregate=aggregate,**describe(aggregate,rows),
            noncomplete_events=[r for r in rows if r['status']!='COMPLETE'],
            anchor_segment_denominators={k:dict(v) for k,v in segments.items()},
            label_stream_hash=digest(payload(rows)),path_stream_hash=digest(payload(paths)),
            uncertainty='NOT_CONFIRMATORY',profitability='NOT_ESTIMATED',
            confirmation='PENDING_ASYNCHRONOUS',confirmation_outcome_access=0,
            confirmation_accessor='NOT_OPENED; separate future interval admission/terminal seal required',
            interpretation='Gross completed-close directional opportunity only; no timing alpha, fill, spread, slippage, commissions, sizing or dividend reinvestment',
            audit=dict(evaluator=evaluator.audit,**forbidden,sealed_dataset_loads=1,
                sealed_slot_close_identities_materialized=len(evaluator.slots),
                discovery_candidates_evaluated=len(rows),confirmation_candidates_evaluated=0))
    write_new(ROOT/name/'labels.json',encode(payload(rows)))
    write_new(ROOT/name/'paths.json',encode(payload(paths)))
    write_new(ROOT/name/'report.json',encode(payload(report)))
    if aggregate['invalid'] or any(v for g in forbidden.values() for v in g.values()):
        raise ValueError('INVALID_FAIL_CLOSED: evaluator integrity or forbidden access')
    return dict(status='EXECUTED_DISCOVERY_EXPLORATORY',run=name,aggregate=aggregate,
                report_sha256=fingerprint(ROOT/name/'report.json'),label_sha256=fingerprint(ROOT/name/'labels.json'))


def verify_results(tests=False):
    manifest = verify_seal()
    for name in ('labels.json','paths.json','report.json'):
        if (ROOT/'run1'/name).read_bytes() != (ROOT/'run2'/name).read_bytes():
            raise ValueError('INVALID_FAIL_CLOSED: independent replay differs: '+name)
    rows = json.loads((ROOT/'run1/labels.json').read_bytes())
    paths = json.loads((ROOT/'run1/paths.json').read_bytes())
    report = json.loads((ROOT/'run1/report.json').read_bytes())
    anchors = manifest['gate']['exact_candidates']
    if len(rows)!=48 or len({r['session'] for r in rows})!=29:
        raise ValueError('Full frozen denominator lost')
    for a,r,p in zip(anchors,rows,paths):
        if (r['event_id'],r['episode_id'],r['anchor_at'],r['session']) != (a['event_id'],a['episode_id'],a['at'],a['session']):
            raise ValueError('Frozen candidate identity changed')
        expected = [timestamp(a['at']),*scheduled_window(a['at'])[0]]
        if [s['at'] for s in p['scheduled_slots']] != [t.isoformat() for t in expected] or r['target_at'] != expected[-1].isoformat():
            raise ValueError('Exact full scheduled path changed')
        if r['status']!='COMPLETE' and r['gross_return'] is not None:
            raise ValueError('Unresolved value exposed')
    grouped = defaultdict(list)
    if all(r['status']=='COMPLETE' for r in rows):
        for r in rows: grouped[r['session']].append(r['gross_return'])
        reference = mean(mean(v) for v in grouped.values())
    else: reference = None
    if reference != report['aggregate']['full_cohort_session_balanced_mean'] or describe(report['aggregate'],rows)['metrics'] != report['metrics']:
        raise ValueError('Official mean/descriptive completeness mismatch')
    audit = report['audit']
    if (report['confirmation_outcome_access'] or audit['evaluator']['confirmation_label_reads']
            or any(v for g in ('common_forbidden','execution_forbidden') for v in audit[g].values())
            or report['uncertainty']!='NOT_CONFIRMATORY' or report['profitability']!='NOT_ESTIMATED'):
        raise ValueError('Forbidden discovery inference/access')
    result = dict(schema='h0004_discovery_execution_verification_v1',status='VALID_EXPLORATORY_EXECUTION',
        deterministic_independent_processes=2,report_sha256=fingerprint(ROOT/'run1/report.json'),
        label_stream_sha256=fingerprint(ROOT/'run1/labels.json'),path_stream_sha256=fingerprint(ROOT/'run1/paths.json'),
        replay_hashes={name:{p:fingerprint(ROOT/name/p) for p in ('labels.json','paths.json','report.json')} for name in ('run1','run2')},
        protected_prior_files=len(manifest['protected_files']),prior_evidence_preserved=True,
        aggregate=report['aggregate'],metrics=report['metrics'],disposition=report['descriptive_disposition'],
        discovery_label_reads_total=2*audit['evaluator']['discovery_label_reads'],
        discovery_forward_price_queries_total=2*audit['evaluator']['forward_price_queries'],
        confirmation_outcome_access=0,profitability='NOT_ESTIMATED',uncertainty='NOT_CONFIRMATORY',
        next_P0='INDEPENDENT_HYPOTHESIS_GENERATION_SELECTION',next_hypothesis='H0005')
    if tests:
        from scripts.h0004_verify import junit
        result['tests']=[junit(ROOT/p) for p in ('tests-targeted.xml','tests-full.xml')]
        write_new(ROOT/'verification.json',encode(result))
    return result


if __name__=='__main__':
    parser=ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('seal','run1','run2','verify','verify-tests'))
    mode=parser.parse_args().mode
    try:
        result = seal() if mode=='seal' else execute(mode) if mode.startswith('run') else verify_results(mode=='verify-tests')
    except Exception as exc:
        write_new(ROOT/('failure-'+mode+'.json'),encode(dict(status='INVALID_FAIL_CLOSED',reason=str(exc),mode=mode)))
        raise
    print(json.dumps(result,indent=2))
