"""Admission invariants: no network, real outcomes or return computation."""
import copy
import inspect
import subprocess
from pathlib import Path
from unittest.mock import Mock
import pytest
from scripts import h0004_portability_data_remediation as r
from scripts import h0004_portability_preaccess as p


@pytest.fixture(autouse=True)
def network_disabled(monkeypatch):
    def denied(*args,**kwargs): raise AssertionError('No network in unit tests')
    for name in ('socket.socket.connect','socket.create_connection','curl_cffi.requests.get'):
        monkeypatch.setattr(name,denied)


def fixture_capture():
    row=dict(t='2026-05-05T08:00:00Z',o=100,h=101,l=99,c=100,v=100,n=10,vw=100)
    return dict(bars=dict(raw=[row],split=[copy.deepcopy(row)]),actions={})


def test_predecessor_and_original_soxx_48_29_untouched():
    proof=r.preserve()
    assert proof['h0004']['SOXX']['candidate_count']==48
    assert proof['h0004']['SOXX']['candidate_sessions']==29
    assert proof['h0004']['all_preserved']
    assert proof['outcome_evidence']=='HASH_ONLY_NOT_DECODED'
    assert p.fingerprint(r.PREDECESSOR/'candidate-manifest.json')==r.PREDECESSOR_HASH


def test_policy_same_provider_no_fill_no_override_and_frozen_order():
    policy=r.policy_body()
    assert r.frozen_policy()==policy
    assert policy['provider']=='Alpaca SIP'
    assert policy['ordered_symbols']==['NVDA','AVGO','MU','AMD','AMAT','MRVL','INTC','KLAC','MPWR','TER']
    assert policy['retry_symbols']==['AVGO','AMD','AMAT','MRVL','KLAC','MPWR','TER']
    assert policy['h0004_binding']==p.bound_contract()[1]
    assert policy['universe_sha256']=='f81c673dd26c4aced735f9fbddd018a0a8c954a154e475cd5088742d3bab1474'
    assert all(k in policy['forbidden'] for k in ('alternate_provider','interpolation','forward_fill','backward_fill','synthetic_bars','parameter_changes'))
    assert list(inspect.signature(r.compare_capture).parameters)==['old','new']
    with pytest.raises(TypeError): p.generate('NVDA',(),{},threshold=1)


@pytest.mark.parametrize('symbol,count',[('AVGO',2),('AMD',3),('AMAT',54),('MRVL',1),('KLAC',182),('MPWR',1071),('TER',491)])
def test_exact_missing_slots_and_ingestion_raw_comparison(symbol,count):
    a=r.exact_audit(symbol,r.PREDECESSOR)
    assert a['missing_count']==len(a['missing_observations'])==count
    assert a==r.exact_audit(symbol,r.PREDECESSOR)
    assert all(not x['ingestion_omission'] and not x['raw_source_bar_present'] and x['segment']!='RTH' for x in a['missing_observations'])
    assert all(0<=x['scheduled_slot']<64 and x['expected_completed_at']>x['expected_timestamp'] for x in a['missing_observations'])
    assert a['input_audit']['coverage']['segments']['RTH']==1820
    assert all(x['status']==200 for x in a['provider_responses'])


def test_missing_calendar_gap_run_determinism():
    a=r.exact_audit('MPWR',r.PREDECESSOR)['missing_observations']
    groups={}
    for x in a: groups.setdefault(x['gap_run'],[]).append(x)
    for values in groups.values():
        assert all(x['gap_run_length']==len(values) for x in values)
        assert len({x['session'] for x in values})==1
        assert all(x['contiguous_gap']==(len(values)>1) for x in values)


def test_split_dividend_clocks_generic_no_new_interpretation():
    u=r.unit_audit(p.read(r.PREDECESSOR/'inputs'/'KLAC'/'capture.json'))
    assert not u['contract_compatible'] and u['differing_observations']==1550
    assert u['actions']['forward_splits'][0]['new_rate']==10
    assert u['actions']['forward_splits'][0]['ex_date']=='2026-06-12'
    assert 'NOT_SUPPLIED' in u['known_at']
    assert r.unit_audit(fixture_capture())['contract_compatible']


def test_exact_provider_recovery_not_interpolation_or_revision():
    old=fixture_capture();new=copy.deepcopy(old)
    extra={**old['bars']['raw'][0],'t':'2026-05-05T08:15:00Z'}
    for k in ('raw','split'): new['bars'][k].append(copy.deepcopy(extra))
    comparison=r.compare_capture(old,new)
    assert comparison['compatible'] and len(comparison['raw']['added'])==1
    assert old==fixture_capture()  # predecessor never modified
    assert new['bars']['raw'][-1]==extra
    for k in ('raw','split'):
        revised=copy.deepcopy(new);revised['bars'][k][0]['v']=101
        assert not r.compare_capture(old,revised)['compatible']
        removed=copy.deepcopy(new);removed['bars'][k].pop(0)
        assert not r.compare_capture(old,removed)['compatible']
    changed=copy.deepcopy(new);changed['actions']={'cash_dividends':[{'rate':1}]}
    assert not r.compare_capture(old,changed)['compatible']


def test_real_outcome_and_return_spies_zero_on_audit():
    with r.capture_guard() as calls:
        r.exact_audit('AVGO',r.PREDECESSOR)
    assert calls==dict(outcome_accessor_calls=0,return_calculations=0)
    with r.capture_guard() as calls:
        from richping.engine import observe,features
        with pytest.raises(AssertionError): observe(None)
        with pytest.raises(AssertionError): features(None)
    assert calls==dict(outcome_accessor_calls=1,return_calculations=1)
    with pytest.raises(PermissionError): r.authorize_real_outcomes()


def test_policy_mutation_fail_closed(monkeypatch):
    original=p.read
    def changed(path):
        body=original(path)
        if path==r.POLICY: body['bars']['feed']='iex'
        return body
    monkeypatch.setattr(p,'read',changed)
    with pytest.raises(ValueError,match='policy mutation'): r.frozen_policy()


def test_raw_parser_omission_detected(monkeypatch):
    original=p.read
    def changed(path):
        body=original(path)
        if path==r.PREDECESSOR/'inputs'/'AVGO'/'capture.json': body['bars']['raw'].pop()
        return body
    monkeypatch.setattr(p,'read',changed)
    with pytest.raises(ValueError,match='Parsed/raw input mismatch'): r.capture_audit('AVGO',r.PREDECESSOR)


def test_stream_freeze_write_once_rejects_mutation(tmp_path):
    path=tmp_path/'stream.json';p.put(path,dict(events=[],signal_state='ZERO_SIGNAL'))
    p.put(path,dict(events=[],signal_state='ZERO_SIGNAL'))
    with pytest.raises(ValueError,match='Immutable artifact collision'): p.put(path,dict(events=[1]))


def test_final_freeze_binding_and_denominators_if_present():
    path=r.ROOT/'admission-manifest.json'
    if not path.exists(): return  # pre-retry source check; final run requires this artifact
    m=p.read(path)
    assert len(m['symbols'])==m['full_universe_count']==10
    assert m['outcome_accessor_calls']==m['return_calculations']==0
    assert m['predecessor_manifest_sha256']==r.PREDECESSOR_HASH
    assert [s['symbol'] for s in m['symbols']]==r.policy_body()['ordered_symbols']
    assert m==r.build()
    for row in m['symbols']:
        assert p.fingerprint(row['candidate_stream_path'])==row['candidate_stream_sha256']
        if row['status']!='READY': assert row['candidate_count'] is None
        if row['symbol'] in ('NVDA','MU','INTC'): assert row['predecessor_stream_reused']


def test_independent_process_repeat_equality_if_captured():
    if not (r.ROOT/'capture-access-audit.json').exists(): return
    cmd=[__import__('sys').executable,'-m','scripts.h0004_portability_data_remediation','digest']
    a=subprocess.run(cmd,check=True,capture_output=True).stdout
    b=subprocess.run(cmd,check=True,capture_output=True).stdout
    assert a==b and len(a.strip())==64


def test_final_seal_mutation_detection_if_present(monkeypatch):
    if not (r.ROOT/'admission-manifest.json').exists(): return
    original=p.read
    def changed(path):
        body=original(path)
        if path==r.ROOT/'admission-manifest.seal.json': body['manifest_sha256']='0'*64
        return body
    monkeypatch.setattr(p,'read',changed)
    with pytest.raises(ValueError,match='seal mutation'): r.verify()
