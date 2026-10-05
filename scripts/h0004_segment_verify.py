"""Metadata-only validation of H0004 trial2 replay, preservation and test receipts."""
import json
from richping.core import digest
from scripts import h0004_segment_frequency as runner
from scripts.h0004_verify import junit
from richping.research_v2.strategy.h0004_experiment import validate_events


def verify(tests=False,root=runner.ROOT):
    manifest = runner.verify_manifest(root)
    report = json.loads((root/'frequency-audit.json').read_bytes())
    events = json.loads((root/'candidate-events.json').read_bytes())['events']
    ranges = json.loads((root/'frozen-ranges.json').read_bytes())['ranges']
    validated = validate_events(events,report['event_stream_hash'],report['dataset_id'])
    c = report['counts']
    if (digest(ranges)!=report['range_stream_hash'] or len(ranges)!=c['frozen_ranges']
            or c['frozen_ranges']!=sum(c[k] for k in ('consumed','expired','downside_cancelled',
                                                    'gap_cancelled','invalid_cancelled','pending'))
            or c['candidates']!=validated['events'] or c['candidate_sessions']!=validated['sessions']
            or report['parameter_trials']!=2 or not report['repeat_equal'] or not report['prefix_equal']
            or report['outcome_access'] or any(report['forbidden_call_counts'].values())):
        raise ValueError('Trial2 denominator/hash/access mismatch')
    indexed = {r['id']:r for r in ranges}
    if len(indexed)!=len(ranges) or any(e['snapshot']['range']!=indexed[e['episode_id']] for e in events):
        raise ValueError('Frozen range collision or snapshot mutation')
    if sum(v['compression_READY'] for v in report['segments'].values())!=c['compression_READY']:
        raise ValueError('Segment readiness mismatch')
    for s,v in report['segments'].items():
        if v['compression_rate']!=v['compressed']/v['compression_READY']:
            raise ValueError('Segment rate mismatch')
    result = dict(schema='h0004_trial2_verification_v1',report_hash=digest(report),
        event_stream_hash=validated['hash'],range_stream_hash=report['range_stream_hash'],spec_hash=report['spec_hash'],
        counts=c,segments=report['segments'],preserved_files=len(manifest['preserved_files']),
        trial1_and_H0001_H0002_H0003_preserved=True,parameter_trials=2,outcome_access=0,verification_price_queries=0,
        mechanically_executable=c['candidates']>0)
    if tests:
        result['tests'] = [junit(root/n) for n in ('tests-targeted.xml','tests-full.xml')]
        runner.write_new(root/'verification.json',runner.encode(result))
    return result


if __name__=='__main__':
    print(json.dumps(verify(tests=True),indent=2))
