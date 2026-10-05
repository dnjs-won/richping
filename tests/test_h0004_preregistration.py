from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from unittest.mock import patch
import pytest
import yaml

from richping.core import digest,timestamp
from richping.research_v2.strategy.h0004_experiment import (
    scheduled_window,calendar_contract,terminal_gate,validate_events,DEADLINE)
from scripts import h0004_signal_preregister as sealed
from scripts import h0004_segment_frequency as frequency
from scripts.h0004_segment_verify import verify


def events():
    return json.loads((frequency.ROOT/'candidate-events.json').read_bytes())['events']


def test_frozen_final_semantics_and_trial1_preservation_metadata_only():
    with sealed.metadata_only() as calls:
        first,second = sealed.verify(),sealed.verify()
    assert first==second and not any(v for group in calls.values() for v in group.values())
    assert first['primary_horizon_slots']==16 and first['parameter_trials']==2
    assert first['status']=='FROZEN_PREREGISTERED_OUTCOMES_NOT_RUN'
    assert first['outcome_access']==first['future_price_queries']==first['efficacy_calculations']==0
    assert first['profitability']=='NOT_ESTIMATED'
    spec = yaml.safe_load(sealed.SPEC.read_bytes())
    assert spec['parameters']==dict(window_bars=16,history_sessions=10,low_percentile=.20,expiration_bars=16)
    assert spec['selected_trial']=='TRIAL_2_SEGMENT_CONDITIONED_REFERENCE'
    assert spec['status']=='FROZEN_OWNER_APPROVED_BEFORE_OUTCOMES'
    assert verify()['trial1_and_H0001_H0002_H0003_preserved']


@pytest.mark.parametrize('field',['horizon','secondary','comparator','floor','block','seed','calendar','version'])
def test_protocol_mutations_rejected_before_outcomes(field):
    body = yaml.safe_load(sealed.PROTOCOL.read_bytes())
    if field=='horizon': body['horizons']['primary_slots']=4
    if field=='secondary': body['horizons']['secondary_slots']=[64]
    if field=='comparator': body['comparators']=['QQQ']
    if field=='floor': body['evidence_floor']['complete_events']=20
    if field=='block': body['uncertainty']['block_sessions']=10
    if field=='seed': body['uncertainty']['seed']=1
    if field=='calendar': body['confirmation']['anchor_start']='2026-10-20'
    if field=='version': body['version']='other'
    with pytest.raises(ValueError): sealed.validate_protocol(body)


def test_exact_four_trading_hour_path_crosses_weekend_without_slot_consumption():
    path,unsupported = scheduled_window('2026-05-08T20:00:00-04:00')
    assert len(path)==16 and not unsupported
    assert path[0]==timestamp('2026-05-11T04:15:00-04:00')
    assert path[-1]==timestamp('2026-05-11T08:00:00-04:00')


def test_unsupported_nominal_followup_day_not_skipped():
    path,unsupported = scheduled_window('2026-11-25T20:00:00-05:00')
    assert path[0]==timestamp('2026-11-27T04:15:00-05:00')
    assert unsupported==('2026-11-27',)


@pytest.mark.parametrize('horizon',[4,64,True,0])
def test_unregistered_horizon_fail_closed(horizon):
    with pytest.raises(ValueError): scheduled_window('2026-05-05T10:00:00-04:00',horizon)


def test_fixed_confirmation_annual_calendar_and_strict_receipt_gate():
    grid = calendar_contract()
    assert len(grid['embargo'])==10 and len(grid['anchors'])==252
    assert grid['anchors'][0]=='2026-10-19' and grid['anchors'][-1]=='2027-10-19'
    assert grid['followup']==['2027-10-20'] and grid['unsupported_sessions']
    assert terminal_gate(DEADLINE,identity_verified=True,coverage_complete=True)=='PENDING'
    assert terminal_gate(timestamp(DEADLINE)+timedelta(microseconds=1),identity_verified=True,
                         coverage_complete=True)=='READY_FOR_SEPARATELY_SEALED_TERMINAL_ADAPTER'
    assert terminal_gate(DEADLINE,identity_verified=False,coverage_complete=True)=='INVALID_FAIL_CLOSED'


@pytest.mark.parametrize('kind',['duplicate','episode','clock','reference','range','buffer'])
def test_candidate_collision_or_snapshot_mutation_fail_closed(kind):
    rows = deepcopy(events())
    if kind=='duplicate': rows.append(deepcopy(rows[0]))
    elif kind=='episode': rows[1]['episode_id']=rows[0]['episode_id']
    elif kind=='clock': rows[0]['at']=rows[0]['snapshot']['range']['published_at']
    elif kind=='reference': rows[0]['snapshot']['range']['feature']['reference_sessions'][-1]=rows[0]['session']
    elif kind=='range': rows[0]['snapshot']['range']['high']+=1
    else: rows[0]['snapshot']['bar']['close']=rows[0]['snapshot']['range']['high']
    with pytest.raises(ValueError): validate_events(rows,digest(rows),frequency.DATASET_ID)


def test_guard_rejects_market_replay_database_and_outcome_queries():
    import richping.engine
    import sqlite3
    with sealed.metadata_only() as calls:
        for action in (lambda:frequency.load_admitted(),lambda:frequency.replay(()),
                       lambda:sqlite3.connect(':memory:'),lambda:richping.engine.observe(None)):
            with pytest.raises(AssertionError): action()
    assert calls['metadata']==dict(price_load=1,signal_replay=1,database=1)
    assert calls['outcomes']['future_return_queries']==1


def test_bound_file_mutation_detected_before_market_or_outcome_access():
    original = Path.read_bytes
    def read(path):
        raw = original(path)
        return raw+b' ' if path==sealed.PROTOCOL else raw
    with sealed.metadata_only() as calls,patch.object(Path,'read_bytes',read),pytest.raises(ValueError,match='dependency changed'):
        sealed.verify()
    assert not any(v for group in calls.values() for v in group.values())
