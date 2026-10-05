"""Verify published exploratory results/test receipts without rereading market prices."""
import json
from pathlib import Path
from collections import Counter

from richping.core import digest
from richping.research_v2.strategy import h0003_efficacy as evaluator
from scripts import h0003_first_efficacy as runner
from scripts.h0003_verify import junit
from scripts.h0002_frequency_audit import encode,fingerprint
from scripts.h0001_long_history_audit import write_new


def published():
    with runner.frozen.metadata_only() as calls:
        manifest,record,events,binding = runner.verify_manifest()
    if any(calls.values()):
        raise ValueError('Market access during metadata validation')
    report = json.loads((runner.ROOT/'discovery-report.json').read_bytes())
    rows = json.loads((runner.ROOT/'event-results.json').read_bytes())['events']
    proof = json.loads((runner.ROOT/'repeat-proof.json').read_bytes())
    audit = json.loads((runner.ROOT/'outcome-access-audit.json').read_bytes())
    if (report['binding'] != binding or [r['event_id'] for r in rows] != binding['candidate_ids']
            or report['metrics'] != evaluator.metrics(rows)
            or report['disposition'] != evaluator.exploratory_disposition(report['metrics'])
            or digest(report) != proof['report_hash'] or not proof['repeat_equal'] or proof['runs'] != 2):
        raise ValueError('Published result/denominator/repeat mismatch')
    if (report['profitability']!='NOT_ESTIMATED' or report['confirmation_status']!='PENDING'
            or report['confirmation_outcome_access'] or report['bootstrap_interval'] is not None
            or report['p_value'] is not None or report['uncertainty_status']!='DISCOVERY_UNCERTAINTY_NOT_PREREGISTERED'
            or not report['disposition'].startswith('DISCOVERY_')):
        raise ValueError('Confirmation/profitability/uncertainty scope changed')
    for path,expected in proof['result_hashes'].items():
        if fingerprint(runner.ROOT/path)!=expected:
            raise ValueError('Immutable published result hash changed')
    if audit['counts']!=report['outcome_access_per_execution']:
        raise ValueError('Access audit/report mismatch')
    actual_plan = [(r['event_id'],r['horizon_slots'],r['expected_path']) for r in audit['trace']]
    plan = json.loads((runner.ROOT/'outcome-access-plan.json').read_bytes())
    if actual_plan != [(r['event_id'],r['horizon'],r['scheduled_path']) for r in plan['labels']]:
        raise ValueError('Published label access differs from sealed plan')
    ledger = sorted((runner.ROOT/'execution-audits').glob('run-*.json'))
    total = Counter()
    for ordinal,path in enumerate(ledger,1):
        run = json.loads(path.read_bytes())
        if run['execution']!=ordinal or run['report_hash']!=proof['report_hash'] or run['result_hashes']!=proof['result_hashes'] or run['access_counts']!=audit['counts']:
            raise ValueError('Per-execution audit identity mismatch')
        total.update(run['access_counts'])
    if len(ledger)<2 or any(total[k] for k in ('confirmation_label_requests','confirmation_price_reads','uncertainty_calculations','profitability_calculations')):
        raise ValueError('Insufficient repeats or forbidden actual access')
    if any(report['forbidden_calls'].values()) or any(report['preparation_forbidden_calls'].values()):
        raise ValueError('Forbidden preparation/execution calls')
    return dict(report_hash=proof['report_hash'],result_hashes=proof['result_hashes'],
        protocol_hash=binding['protocol_hash'],signal_freeze_hash=binding['signal_freeze_hash'],
        event_stream_hash=binding['candidate_stream_hash'],preserved_files=len(manifest['preserved_files']),
        actual_executions=len(ledger),actual_access_counts=dict(total),
        metadata_verification_forbidden_calls=calls,verification_price_queries=0,
        confirmation_outcome_access=0,disposition=report['disposition'])


def verify():
    first,second = published(),published()
    if first!=second:
        raise ValueError('Published verification not deterministic')
    tests = [junit(runner.ROOT/name) for name in ('tests-targeted-v1.xml','tests-full-v1.xml')]
    if tests[0]['tests']!=178 or tests[1]['tests']!=1687 or any(t[k] for t in tests for k in ('failures','errors','skipped')):
        raise ValueError('Complete passing targeted/full regression required')
    result = dict(schema='h0003_first_efficacy_verification_v1',**first,tests=tests,
        prior_source_evidence_and_H0001_H0002_tracks_preserved=True,
        frozen_H0003_contracts_and_35_candidates_unchanged=True,repeat_verification_equal=True,
        profitability='NOT_ESTIMATED',next_P0='INDEPENDENT_HYPOTHESIS_GENERATION_SELECTION',next_hypothesis='H0004')
    write_new(runner.ROOT/'verification.json',encode(result))
    return result


if __name__=='__main__':
    print(json.dumps(verify(),indent=2))
