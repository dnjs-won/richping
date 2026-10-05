"""Execution orchestration invariants; all arithmetic inputs explicitly synthetic."""
from dataclasses import replace
import json
from unittest.mock import Mock, patch
import pytest

from richping.core import sessions
from scripts import h0004_discovery_execution as runner
from scripts.h0004_preaccess_fixtures import fixture
from richping.research_v2.strategy.h0004_directional_evaluator import DirectionalEvaluator


def cohort():
    days=sessions('2026-05-05','2026-06-16')[:29]
    times=[]
    for i,day in enumerate(days):
        times.append(day+'T10:00:00-04:00')
        if i<19: times.append(day+'T10:15:00-04:00')
    return fixture(times=tuple(times),returns=tuple(.1 if i<38 else -.1 for i in range(48)))


def test_complete48_correct_session_weighting_and_descriptive_distribution():
    e,r=cohort()
    rows=e.evaluate(r)
    result=e.aggregate(rows)
    desc=runner.describe(result,rows)
    assert result['total_emitted']==result['complete']==48
    assert result['candidate_sessions']==29
    assert result['full_cohort_session_balanced_mean']==pytest.approx((19*.1-10*.1)/29)
    assert desc['metrics']['positive_count']==38 and desc['metrics']['negative_count']==10
    assert desc['metrics']['positive_rate']==38/48
    assert desc['metrics']['zero_count']==0
    assert desc['metrics']['event_median_R16']==pytest.approx(.1)


@pytest.mark.parametrize('state',['PENDING','UNRESOLVED','INVALID_FAIL_CLOSED'])
@pytest.mark.parametrize('index',[0,23,47])
def test_any_one_noncomplete_blocks_all_cohort_descriptive_metrics(state,index):
    e,r=cohort()
    rows=[dict(x) for x in e.evaluate(r)]
    rows[index].update(status=state,gross_return=None)
    result=e.aggregate(rows)
    desc=runner.describe(result,rows)
    assert result['total_emitted']==48 and result['complete']==47
    assert result['full_cohort_session_balanced_mean'] is None
    assert desc['metrics'] is None and not desc['full_cohort_aggregate_available']


def test_candidate_deletion_or_noncomplete_zero_substitution_rejected():
    e,r=cohort()
    rows=[dict(x) for x in e.evaluate(r)]
    with pytest.raises(ValueError): e.aggregate(rows[:-1])
    rows[-1].update(status='UNRESOLVED',gross_return=0)
    with pytest.raises(ValueError): e.aggregate(rows)


@pytest.mark.parametrize('change',['missing','unit'])
def test_middle_path_problem_blocks_label_even_with_valid_endpoints(change):
    e,r=fixture()
    slots=list(e.metadata.slots)
    if change=='missing': del slots[8]
    else: slots[8]=replace(slots[8],unit_certified=False)
    e=DirectionalEvaluator(e.anchors,e.binding,replace(e.metadata,slots=tuple(slots)),e.as_of)
    never=Mock(side_effect=AssertionError('Incomplete path must not access endpoint'))
    rows=e.evaluate(never)
    assert rows[0]['status']=='UNRESOLVED' and rows[0]['gross_return'] is None
    never.assert_not_called()


def test_execution_gate_failure_precedes_real_dataset_access(monkeypatch):
    monkeypatch.setattr(runner,'verify_seal',Mock(side_effect=ValueError('mismatch')))
    loader=Mock(side_effect=AssertionError('Price accessed before gate'))
    monkeypatch.setattr(runner,'open_discovery',loader)
    with pytest.raises(ValueError,match='mismatch'): runner.execute('run1')
    loader.assert_not_called()


@pytest.mark.parametrize('target,args',[
    ('socket.create_connection',(('example.invalid',443),)),
    ('scripts.h0004_frequency_audit.replay',((),None)),
    ('scripts.h0004_segment_frequency.replay',((),None)),
    ('richping.evaluation.block_ci',((),)),
    ('sqlite3.connect',(':memory:',))])
def test_execution_guard_rejects_network_signal_statistics_and_database(target,args):
    import importlib
    module,name=target.rsplit('.',1)
    function_module=importlib.import_module(module)
    with runner.execution_guard() as calls,pytest.raises(AssertionError):
        getattr(function_module,name)(*args)
    assert sum(v for group in calls.values() for v in group.values())==1


def test_independent_replay_mismatch_fails_closed(monkeypatch,tmp_path):
    monkeypatch.setattr(runner,'ROOT',tmp_path)
    monkeypatch.setattr(runner,'verify_seal',lambda:{})
    for name,value in [('run1',b'[]'),('run2',b'[{}]')]:
        (tmp_path/name).mkdir()
        (tmp_path/name/'labels.json').write_bytes(value)
    with pytest.raises(ValueError,match='independent replay differs'): runner.verify_results()


def test_evidence_is_write_once(tmp_path):
    p=tmp_path/'labels.json'
    runner.write_new(p,b'original')
    runner.write_new(p,b'original')
    with pytest.raises(ValueError,match='Immutable artifact collision'): runner.write_new(p,b'changed')
    assert p.read_bytes()==b'original'


def test_synthetic_repeat_has_equal_labels_report_and_zero_confirmation():
    results=[]
    for _ in range(2):
        e,r=cohort()
        rows=e.evaluate(r)
        aggregate=e.aggregate(rows)
        results.append(runner.encode(dict(labels=rows,aggregate=aggregate,description=runner.describe(aggregate,rows))))
        assert e.audit['confirmation_label_reads']==0 and e.audit['profitability_calculations']==0
    assert results[0]==results[1]


def test_no_inference_or_segment_return_fields():
    e,r=cohort()
    desc=runner.describe(e.aggregate(e.evaluate(r)),e.evaluate(r))
    keys=set(desc)|set(desc['metrics'])
    assert not keys & {'CI','bootstrap','p_value','significance','power','segment_returns','event_weighted_mean'}
