from copy import deepcopy
from datetime import datetime,time,timedelta
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from richping.core import digest,timestamp
from richping.research_v2.contracts import payload
from richping.research_v2.sessions import NY
from richping.research_v2.strategy.h0003_leadership import CloseBar,LeadershipStream
from richping.research_v2.strategy.h0003_experiment import (
    calendar_contract,scheduled_window,validate_events,disposition,terminal_gate,DEADLINE)
from scripts import h0003_signal_preregister as runner


def events():
    return json.loads((runner.DISCOVERY/'candidate-events.json').read_bytes())['events']


def pair(index,own=100,benchmark=100):
    offset,slot = divmod(index,64)
    day = ['2026-05-05','2026-05-06','2026-05-07'][offset]
    start = datetime.combine(datetime.fromisoformat(day).date(),time(4),NY)+timedelta(minutes=15*slot)
    end = start+timedelta(minutes=15)
    return (CloseBar('soxx-test','SOXX',start,end,end,day,own,split_identity_admitted=True),
            CloseBar('qqq-test','QQQ',start,end,end,day,benchmark,split_identity_admitted=True))


def test_exact_64_slot_identity_math_persistence_guard_equality_and_future_suffix():
    s = LeadershipStream()
    published = []
    for i in range(68):
        own,bench = pair(i,100,100 if i < 64 else 99)
        step = s.accept(own,bench,own.end_at)
        if i < 64:
            assert not step.rs_ready
        else:
            assert step.own_return == 0 and step.guard is True
            assert step.relative_return == pytest.approx(.01)
            assert step.positive_run == i-63
            assert step.leadership is (i == 67)
        published.append(payload(step))
    event = step.event.unpack()
    assert event['anchor_at'] == timestamp(pair(3)[0].end_at).isoformat()
    assert scheduled_window(event['anchor_at'],64)[0][-1] == timestamp(event['at'])
    old = deepcopy(published)
    for i in range(68,75):
        own,bench = pair(i,100,98)
        assert s.accept(own,bench,own.end_at).event is None
    assert published == old


def test_zero_rs_terminates_and_gap_does_not_rearm_consumed_epoch():
    s = LeadershipStream()
    for i in range(68):
        a,b = pair(i,101 if i >= 64 else 100)
        last = s.accept(a,b,a.end_at)
    assert last.event
    episode = last.episode_id
    a,b = pair(68,102)
    assert s.accept(a,None,a.end_at).episode_id == episode
    a,b = pair(69,102)
    step = s.accept(a,b,a.end_at)
    assert not step.rs_ready and not step.event and step.episode_id == episode


def test_schedule_cross_session_weekend_dst_and_unsupported_is_not_compressed():
    window,_ = scheduled_window('2026-05-08T20:00:00-04:00',16)
    assert window[0] == timestamp('2026-05-11T04:15:00-04:00')
    assert window[-1] == timestamp('2026-05-11T08:00:00-04:00')
    window,_ = scheduled_window('2026-03-06T20:00:00-05:00',16)
    assert window[-1] == timestamp('2026-03-09T08:00:00-04:00')
    window,unsupported = scheduled_window('2026-11-25T20:00:00-05:00',16)
    assert window[-1] == timestamp('2026-11-27T08:00:00-05:00')
    assert unsupported == ('2026-11-27',)


@pytest.mark.parametrize('at,h', [('2026-05-05T04:00:00-04:00',16),('2026-05-05T09:01:00-04:00',16),
    ('2026-05-09T10:00:00-04:00',16),('2026-05-05T10:00:00-04:00',192),('2026-05-05T10:00:00-04:00',True)])
def test_invalid_or_unregistered_schedule_rejected(at,h):
    with pytest.raises(ValueError):
        scheduled_window(at,h)


def test_current_candidate_hash_and_29_sessions_are_preserved():
    stream = events()
    result = validate_events(stream,stream[0]['datasets'],digest(stream))
    assert result['events'] == 35 and result['sessions'] == 29


@pytest.mark.parametrize('kind',['duplicate_id','duplicate_episode','body','slot','anchor','guard','zero_rs','dataset','nan'])
def test_candidate_identity_collision_and_semantic_mutations_fail_closed(kind):
    stream = events()
    event = stream[0]
    if kind == 'duplicate_id':
        stream.append(deepcopy(event))
    elif kind == 'duplicate_episode':
        stream[1]['episode_id'] = event['episode_id']
        stream[1]['id'] = digest({k:v for k,v in stream[1].items() if k != 'id'})
    else:
        if kind == 'body': event['relative_return'] += .01
        if kind == 'slot': event['at'] = '2026-05-06T09:01:00+00:00'
        if kind == 'anchor': event['anchor_at'] = '2026-05-05T09:15:00+00:00'
        if kind == 'guard': event['own_return'] = -.01
        if kind == 'zero_rs': event['own_return'] = event['benchmark_return']; event['relative_return'] = 0
        if kind == 'dataset': event['datasets'][1] = 'mixed'
        if kind == 'nan': event['relative_return'] = float('nan')
        if kind != 'body': event['id'] = digest({k:v for k,v in event.items() if k != 'id'}) if kind != 'nan' else event['id']
    with pytest.raises((ValueError,TypeError)):
        validate_events(stream,events()[0]['datasets'],digest(stream))


@pytest.mark.parametrize('kwargs,expected', [
    ({'valid':False},'INVALID_FAIL_CLOSED'),({},'PENDING'),
    ({'terminal':True,'resolved':False},'UNRESOLVED'),({'terminal':True},'ZERO_SIGNAL'),
    ({'terminal':True,'events':39,'event_sessions':20,'occupied_blocks':8},'INSUFFICIENT_EVIDENCE'),
    ({'terminal':True,'events':40,'event_sessions':19,'occupied_blocks':8},'INSUFFICIENT_EVIDENCE'),
    ({'terminal':True,'events':40,'event_sessions':20,'occupied_blocks':7},'INSUFFICIENT_EVIDENCE'),
    ({'terminal':True,'events':40,'event_sessions':20,'occupied_blocks':8},'UNRESOLVED'),
    ({'terminal':True,'events':40,'event_sessions':20,'occupied_blocks':8,'relative_interval':[.001,.01]},'PASS'),
    ({'terminal':True,'events':40,'event_sessions':20,'occupied_blocks':8,'relative_interval':[-.02,-.001]},'REJECT'),
    ({'terminal':True,'events':40,'event_sessions':20,'occupied_blocks':8,'relative_interval':[0,.01]},'INCONCLUSIVE'),
    ({'terminal':True,'events':40,'event_sessions':20,'occupied_blocks':8,'relative_interval':[-.01,0]},'INCONCLUSIVE'),
])
def test_relative_only_disposition_and_equality(kwargs,expected):
    assert disposition(**kwargs) == expected


@pytest.mark.parametrize('value', [[.1,-.1],[float('inf'),.1],[0],['0',1]])
def test_invalid_interval_metadata_fails_closed(value):
    with pytest.raises(ValueError):
        disposition(terminal=True,events=40,event_sessions=20,occupied_blocks=8,relative_interval=value)


def test_terminal_deadline_is_strict_and_no_accessor_accepted():
    gates = dict(identity_verified=True,coverage_complete=True,events=40,event_sessions=20,occupied_blocks=8)
    assert terminal_gate(DEADLINE,**gates) == 'PENDING'
    assert terminal_gate(timestamp(DEADLINE)+timedelta(seconds=1),**gates) == 'UNRESOLVED'
    assert terminal_gate(DEADLINE,identity_verified=False,coverage_complete=True) == 'INVALID_FAIL_CLOSED'
    assert 'loader' not in __import__('inspect').signature(terminal_gate).parameters


def test_confirmation_is_fixed_annual_calendar_and_independent_identity():
    grid = calendar_contract()
    assert len(grid['anchors']) == 252 and len(grid['embargo']) == 10
    assert grid['anchors'][0] == '2026-10-19' and grid['anchors'][-1] == '2027-10-19'
    assert grid['followup'] == ['2027-10-20']
    assert grid['unsupported_sessions'] == ['2026-11-27','2026-12-24']
    body = yaml.safe_load(runner.PROTOCOL.read_bytes())
    assert body['uncertainty']['seed'] == 20261005 and body['uncertainty']['block_sessions'] == 10
    assert body['multiple_testing']['primary_families'] == 1 and body['comparators'] == []


@pytest.mark.parametrize('kind',['horizon','absolute','comparator','baseline','costs','calendar','floor','seed','async','missing'])
def test_mutated_preregistration_rejected_before_outcomes(kind):
    body = yaml.safe_load(runner.PROTOCOL.read_bytes())
    if kind == 'horizon': body['horizons']['primary_slots'] = 64
    if kind == 'absolute': body['absolute_relevance']['role'] = 'JOINT_PRIMARY'
    if kind == 'comparator': body['comparators'] = ['SPY']
    if kind == 'baseline': body['baseline']['name'] = 'ABSOLUTE_ONLY'
    if kind == 'costs': body['costs']['costs_bps'] = 0
    if kind == 'calendar': body['confirmation']['anchor_end'] = '2027-10-20'
    if kind == 'floor': body['evidence_floor']['complete_events'] = 35
    if kind == 'seed': body['uncertainty']['seed'] = 7
    if kind == 'async': body['confirmation']['project_blocker'] = True
    if kind == 'missing': del body['label']
    with pytest.raises(ValueError):
        runner.validate_protocol(body)


def test_metadata_guards_block_actual_outcome_calculation_and_market_access():
    import richping.engine
    from scripts.h0003_frequency_audit import paired_inputs
    from richping.research_v2.strategy.h0002_efficacy import DiscoveryLabels
    with runner.metadata_only() as calls:
        with pytest.raises(AssertionError,match='outcome_accessor'):
            richping.engine.observe(None)
        # Import inside context so the patched loader itself is invoked.
        import scripts.h0003_frequency_audit as source
        with pytest.raises(AssertionError,match='market_load'):
            source.paired_inputs()
        with pytest.raises(AssertionError,match='outcome_accessor'):
            DiscoveryLabels.label(None,None,None,None,None)
    assert calls['outcome_accessor'] == 2 and calls['market_load'] == 1


def test_sealed_metadata_repeatable_and_all_old_sources_preserved_without_prices():
    before = runner.FREEZE.read_bytes(),(runner.DISCOVERY/'candidate-events.json').read_bytes()
    with runner.metadata_only() as calls:
        first,second = runner.verify(),runner.verify()
    assert first == second and not any(calls.values())
    assert first['discovery_events'] == 35 and first['discovery_sessions'] == 29
    assert first['outcome_access'] == first['future_price_queries'] == first['efficacy_calculations'] == 0
    assert first['profitability'] == 'NOT_ESTIMATED' and first['next_P0'] == 'H0003_FIRST_EFFICACY'
    assert before == (runner.FREEZE.read_bytes(),(runner.DISCOVERY/'candidate-events.json').read_bytes())


def test_bound_source_mutation_detected_without_market_access():
    original = runner.preservation_fingerprint
    def changed(path):
        return '0'*64 if str(path) == 'richping/research_v2/strategy/h0003_leadership.py' else original(path)
    with runner.metadata_only() as calls,patch.object(runner,'preservation_fingerprint',changed):
        with pytest.raises(ValueError,match='Frozen/preserved'):
            runner.verify()
    assert not any(calls.values())
