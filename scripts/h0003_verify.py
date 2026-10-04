"""Supplemental verification; retain pre-frequency evidence and intake-test history."""
from argparse import ArgumentParser
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from scripts import h0003_frequency_audit as runner
from scripts.h0001_long_history_audit import write_new
from richping.research_v2.strategy.h0003_leadership import Specification, LeadershipStream
from richping.research_v2.contracts import payload

def verify_state():
    m = json.loads((runner.ROOT/'preexecution-manifest.json').read_bytes())
    baseline = json.loads((runner.ROOT/'frequency-audit.json').read_bytes())
    if (m['base_commit'] != runner.BASE or m['parameter_trials'] != 1 or m['outcomes'] != 'FORBIDDEN'
            or runner.fingerprint(runner.ROOT/'preexecution-manifest.json') != baseline['manifest_sha256']):
        raise ValueError('Original manifest identity/hash mismatch')
    for group in ('execution_files','input_files','preserved_files'):
        for p,expected in m[group].items():
            actual = runner.preservation_fingerprint(p) if group == 'preserved_files' else runner.fingerprint(p)
            if actual != expected:
                raise ValueError('Sealed/frozen dependency changed: '+p)
    return m


def junit(path):
    body = Path(path).read_bytes()
    tree = ET.fromstring(body)
    suites = [tree] if tree.tag == 'testsuite' else list(tree.iter('testsuite'))
    return dict(path=Path(path).as_posix(),sha256=sha256(body).hexdigest(),
                **{key:sum(int(s.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')})


def verify():
    manifest = verify_state()
    baseline = json.loads((runner.ROOT/'frequency-audit.json').read_bytes())
    expected_events = json.loads((runner.ROOT/'candidate-events.json').read_bytes())['events']
    raw_before = {p:runner.fingerprint(p) for p in manifest['preserved_files']}
    with runner.no_outcomes() as calls:
        own,benchmark,metadata = runner.paired_inputs()
        spec = Specification()
        first = runner.replay(own,benchmark,spec)
        own2,benchmark2,metadata2 = runner.paired_inputs()
        second = runner.replay(own2,benchmark2,spec)
        if first != second or metadata != metadata2 or first['events'] != expected_events:
            raise ValueError('Original signal/frequency changed')
        for k,v in first.items():
            if k != 'events' and baseline[k] != v:
                raise ValueError('Original frequency denominator changed: '+k)
        # Episode-level guard explanations use only current features, never labels.
        stream,episodes = LeadershipStream(spec),{}
        for a,b in zip(own,benchmark):
            step = stream.accept(a,b,a.end_at)
            if step.episode_started:
                episodes[step.episode_id] = dict(started_at=payload(step.at), first_guard=step.guard,
                                               emitted_at=None, leadership_bars=0,guard_pass_bars=0)
            if step.leadership:
                episode = episodes[step.episode_id]
                episode['leadership_bars'] += 1
                episode['guard_pass_bars'] += step.guard is True
                if step.event:
                    episode['emitted_at'] = payload(step.at)
        if any(calls.values()):
            raise ValueError('Forbidden access')
    if manifest != verify_state() or raw_before != {p:runner.fingerprint(p) for p in raw_before}:
        raise ValueError('Evidence changed during supplemental verification')
    tests = [junit(runner.ROOT/name) for name in ('tests-targeted-v3.xml','tests-full-v3.xml')]
    if any(t[k] for t in tests for k in ('failures','errors','skipped')):
        raise ValueError('Final targeted/full regression must pass without skips')
    result = dict(schema='h0003_supplemental_verification_v1',verified_at=datetime.now(timezone.utc).isoformat(),
                  original_frequency_sha256=runner.fingerprint(runner.ROOT/'frequency-audit.json'),
                  original_manifest_sha256=runner.fingerprint(runner.ROOT/'preexecution-manifest.json'),
                  original_event_stream_hash=baseline['event_stream_hash'], repeat_equal=True,
                  all_original_signal_denominators_equal=True, outcome_access=0, forbidden_call_counts=calls,
                  H0001_H0002_frozen_sources_and_evidence_unchanged=True,
                  original_protected_files=len(manifest['preserved_files']),
                  prior_tracked_tests_unchanged=True,
                  historical_test_fixture=dict(path='conftest.py',sha256=runner.fingerprint('conftest.py'),
                      reason='Original sealed intake test keeps its H0001/H0002 registry case; a new test validates current H0003 registry and next H0004.'),
                  tests=tests, initial_full_attempt=junit(runner.ROOT/'tests-full-v1.xml'),
                  second_full_attempt=junit(runner.ROOT/'tests-full-v2.xml'),
                  initial_intake_diagnostic=junit(runner.ROOT/'tests-intake-diagnostic-v1.xml'),
                  initial_targeted=junit(runner.ROOT/'tests-targeted-v1.xml'),
                  guard_diagnostics=dict(episodes=len(episodes),
                      emitted=sum(e['emitted_at'] is not None for e in episodes.values()),
                      delayed=sum(e['emitted_at'] is not None and not e['first_guard'] for e in episodes.values()),
                      un_emitted={k:v for k,v in episodes.items() if v['emitted_at'] is None}),
                  verification_source_sha256=runner.fingerprint(__file__))
    existing = runner.ROOT/'verification.json'
    if existing.exists():
        result['verified_at'] = json.loads(existing.read_bytes())['verified_at']
    write_new(existing,runner.encode(result))
    write_new(runner.ROOT/'leadership-episodes.json',runner.encode(episodes))
    return result


if __name__ == '__main__':
    result = verify()
    print(json.dumps({k:result[k] for k in ('tests','guard_diagnostics','outcome_access')}))
