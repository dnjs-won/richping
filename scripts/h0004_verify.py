"""Verify H0004 evidence and tests using metadata only, with no price replay."""
import ast
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from richping.core import digest
from scripts import h0004_frequency_audit as runner


def junit(path):
    tree = ET.parse(path)
    totals = {k:sum(int(s.attrib.get(k,0)) for s in tree.findall('.//testsuite'))
              for k in ('tests','failures','errors','skipped')}
    if not totals['tests'] or any(totals[k] for k in ('failures','errors','skipped')):
        raise ValueError('Complete passing regression required')
    return dict(path=path.name, sha256=runner.fingerprint(path), **totals)


def verify(root=runner.ROOT, tests=True):
    manifest = runner.verify_manifest(root)
    report = json.loads((root/'frequency-audit.json').read_bytes())
    events = json.loads((root/'candidate-events.json').read_bytes())['events']
    ranges = json.loads((root/'frozen-ranges.json').read_bytes())['ranges']
    audit = json.loads((root/'independence-audit.json').read_bytes())
    original_events = json.loads((runner.ORIGINAL/'candidate-events.json').read_bytes())['events']
    original_ranges = json.loads((runner.ORIGINAL/'frozen-ranges.json').read_bytes())['ranges']
    if events != original_events or ranges != original_ranges:
        raise ValueError('Preservation repair changed initial signal evidence')
    if (digest(events)!=report['candidate_stream_hash'] or digest(ranges)!=report['frozen_range_stream_hash']
            or any(report['forbidden_call_counts'].values()) or report['outcome_access']
            or report['parameter_trials']!=1 or report['comparators']!=0
            or not report['repeat_equal'] or not report['prefix_equal']):
        raise ValueError('Published hashes/access/trial mismatch')
    counts = report['denominators']
    if (len(events)!=counts['final_candidate_events'] or len(ranges)!=counts['frozen_ranges']
            or len({e['episode_id'] for e in events})!=len(events)
            or len({e['id'] for e in events})!=len(events)
            or len({r['id'] for r in ranges})!=len(ranges)
            or len({e['session'] for e in events})!=counts['distinct_candidate_sessions']
            or len(ranges)!=sum(counts[k] for k in ('expired_episodes','cancelled_episodes',
                                                   'consumed_episodes','pending_episodes_at_scope_end'))):
        raise ValueError('Denominator/episode reconciliation failed')
    indexed = {r['id']:r for r in ranges}
    for event in events:
        snapshot = event['snapshot']
        if (snapshot['range'] != indexed[event['episode_id']]
                or snapshot['bar']['close'] <= snapshot['range']['high']
                or event['at'] <= snapshot['range']['published_at']):
            raise ValueError('Event detached from original frozen range')
    if audit['outcome_access'] or any(audit['forbidden_call_counts'].values()) or audit['imported_strategy_states']:
        raise ValueError('Independence audit mismatch')
    for path in (runner.EXECUTION[3],runner.EXECUTION[4]):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        imports = [n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        imports += [a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
        if any(any(x in name for x in ('h0001','h0002','h0003','efficacy','outcome')) for name in imports):
            raise ValueError('Forbidden import dependency')
    result = dict(schema='h0004_frequency_verification_v1', report_hash=digest(report),
                  candidate_stream_hash=report['candidate_stream_hash'], spec_hash=report['spec_hash'],
                  counts=counts, prior_files_preserved=len(manifest['preserved_files']),
                  H0001_H0002_H0003_preserved=True, outcome_access=0, verification_price_queries=0,
                  parameter_trials=1, comparators=0, next_P0='H0004_SIGNAL_FREEZE_PREREGISTRATION')
    if tests:
        result['tests'] = [junit(root/name) for name in ('tests-targeted.xml','tests-full.xml')]
        runner.write_new(root/'verification.json',runner.encode(result))
    return result


if __name__ == '__main__':
    print(json.dumps(verify(),indent=2))
