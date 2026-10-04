from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import h0003_benchmark_admission as data
from scripts import h0003_frequency_audit as frequency
from richping.research_v2.strategy.h0003_leadership import Specification


def test_current_registry_advances_to_h0004_without_future_confirmation_dependency():
    from scripts.prepare_independent_research import prepare
    with patch('socket.socket.connect',side_effect=AssertionError('network')):
        first = prepare()
        assert first == prepare()
    assert first['next_hypothesis_id'] == 'H0004'
    assert any(e['id'] == 'H0003' and e['revision'] == 1 for e in first['registered_hypotheses'])
    assert first['candidate_outcome_access'] is False
    assert first['future_confirmation_dependency'] is False


def capture():
    return data.load_capture()


def test_real_admission_receipt_reconstruction_and_exact_pair_alignment():
    c = capture()
    admitted = data.admission(c)
    assert admitted == json.loads((data.ROOT/'admission.json').read_bytes())
    assert admitted['status'] == 'PASS' and admitted['grid']['observed'] == 4480
    assert admitted['grid']['missing_count'] == 0
    with frequency.no_outcomes() as calls:
        own,benchmark,_ = frequency.paired_inputs()
    assert not any(calls.values())
    assert len(own) == len(benchmark) == 4480
    assert [(b.start_at,b.end_at,b.session) for b in own] == [(b.start_at,b.end_at,b.session) for b in benchmark]


@pytest.mark.parametrize('case', ['repeat','split'])
def test_repeated_or_unit_mismatch_blocks_admission(case):
    c = capture()
    c['cases'][case]['rows'][0]['c'] += .001
    assert data.admission(c)['status'] == 'BLOCKED'


def test_missing_benchmark_bar_blocks_admission_without_fill():
    c = capture()
    for key in ('raw','repeat','split'):
        del c['cases'][key]['rows'][40]
    result = data.admission(c)
    assert result['status'] == 'BLOCKED' and result['grid']['missing_count'] == 1


def test_unknown_unit_action_blocks_admission():
    c = capture()
    for key in ('actions','actions-repeat'):
        c['cases'][key]['corporate_actions']['forward_splits'] = [{'symbol':'QQQ','id':'test'}]
    assert data.admission(c)['status'] == 'BLOCKED'


@pytest.mark.parametrize('field,value', [('feed','iex'),('currency','EUR'),('adjustment','all'),('timeframe','1Hour')])
def test_mixed_capture_contract_rejected(field,value):
    c = capture()
    c['requests'][0]['params'][field] = value
    with pytest.raises(ValueError, match='Mixed'):
        data.admission(c)


def test_wrong_action_interval_rejected():
    c = capture()
    next(r for r in c['requests'] if r['id'] == 'actions')['params']['start'] = '2026-06-01'
    with pytest.raises(ValueError, match='Action interval'):
        data.admission(c)


def test_capture_collision_and_raw_receipt_tamper_rejected(tmp_path):
    from scripts.h0001_long_history_audit import write_new
    path = tmp_path/'a.json'
    write_new(path,b'a')
    write_new(path,b'a')
    with pytest.raises(ValueError,match='collision'):
        write_new(path,b'b')
    # Mock only the immutable byte read; no network or fixture manufacture.
    old = Path.read_bytes
    def bad_read(p):
        body = old(p)
        return body+b' ' if p.parent == data.ROOT/'raw' else body
    with patch.object(Path,'read_bytes',bad_read), pytest.raises(ValueError,match='receipt hash'):
        data.load_capture()


def test_outcome_accessor_and_forward_queries_are_guarded_and_counted():
    import richping.engine
    import richping.research_v2.strategy.h0002_efficacy as efficacy
    with frequency.no_outcomes() as calls:
        with pytest.raises(AssertionError,match='outcome_accessor'):
            richping.engine.observe(None)
        with pytest.raises(AssertionError,match='forward_window'):
            efficacy.scheduled_window(None,4)
    assert calls['outcome_accessor'] == 1 and calls['forward_window'] == 1


def test_frozen_h0001_h0002_evidence_unchanged_and_real_frequency_outcome_access_zero():
    from scripts.h0003_verify import verify_state
    manifest = verify_state()
    assert any('H0001-' in p for p in manifest['preserved_files'])
    assert any('H0002-' in p for p in manifest['preserved_files'])
    assert any('h0002-first-efficacy' in p for p in manifest['preserved_files'])
    report = json.loads((frequency.ROOT/'frequency-audit.json').read_bytes())
    assert report['outcome_access'] == 0 and not any(report['forbidden_call_counts'].values())
    assert report['repeat_equal'] and report['prefix_equal'] and report['frozen_evidence_unchanged']
    assert report['parameter_trials'] == 1 and report['comparators'] == 0
    assert report['economic_effect'] is None and report['efficacy'] == 'NOT_RUN'
    events = json.loads((frequency.ROOT/'candidate-events.json').read_bytes())['events']
    assert len({e['episode_id'] for e in events}) == len(events)
    assert len(events) == report['denominators']['candidate_event_count']


def test_real_prefix_and_suffix_causality_without_outcomes():
    with frequency.no_outcomes() as calls:
        own,benchmark,_ = frequency.paired_inputs()
        short = frequency.replay(own[:192],benchmark[:192],Specification())
        longer = frequency.replay(own[:256],benchmark[:256],Specification())
    assert not any(calls.values())
    cutoff = own[191].end_at.isoformat()
    assert short['events'] == [e for e in longer['events'] if e['at'] <= cutoff]


def test_alignment_audit_records_one_side_absence_and_resets_ready_window():
    with frequency.no_outcomes() as calls:
        own,benchmark,_ = frequency.paired_inputs()
        result = frequency.replay(own[:100],benchmark[:30]+benchmark[31:100],Specification())
    assert not any(calls.values())
    assert result['reasons']['one_side_missing'] == 1
    assert result['denominators']['both_series_READY_bars'] == 99
    assert result['denominators']['data_session_mismatch_count'] == 1
    assert result['denominators']['relative_strength_READY_bars'] == 5
