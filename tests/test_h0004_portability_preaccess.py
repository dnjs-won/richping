"""Offline portability invariants; fixture prices are synthetic, never outcomes."""
from dataclasses import replace
import inspect
import json
from pathlib import Path
import subprocess
from unittest.mock import Mock, patch
import pytest

from scripts import h0004_portability_preaccess as p
from tests.test_h0004_segment_compression import make_bars


@pytest.fixture(autouse=True)
def network_disabled(monkeypatch):
    def denied(*args,**kwargs): raise AssertionError('Unit tests have no network')
    monkeypatch.setattr('socket.create_connection',denied)
    monkeypatch.setattr('socket.socket.connect',denied)
    monkeypatch.setattr('curl_cffi.requests.get',denied)


def synthetic(symbol='NVDA'):
    bars=[replace(b,symbol=symbol,dataset_id='synthetic-portability') for b in make_bars(12)]
    for i in range(640,len(bars)):
        bars[i]=replace(bars[i],high=100.1,low=99.9)
    bars[656]=replace(bars[656],high=103,close=102)
    return tuple(bars)


def test_original_frozen_lineage_soxx48_29_evidence_and_confirmation_unchanged():
    proof=p.preservation()
    assert proof['all_preserved'] and len(proof['protected_files'])>600
    assert proof['SOXX']['candidate_count']==48 and proof['SOXX']['candidate_sessions']==29
    assert proof['SOXX']['stream_sha256']=='c5c236e995b7adf5f646057b64e2f7895b01635b54252de834ba6a534c1d8ead'
    assert proof['discovery_evidence']=='HASH_ONLY_NOT_PARSED'


def test_config_exact_hash_and_original_protocol_no_reentered_parameters():
    spec,binding=p.bound_contract()
    assert spec.content_hash=='0a4ebc7f1b793380cea11df0604e7faeee06679b2c56d3024b886aab56ef82e2'
    assert binding['signal_trials']==2
    assert binding['protocol_hash']=='09e8202e4edd3a06c3b7907d7aafa70c93c05155d5f1d902c5d07798540d8d1f'


def test_config_mutation_fail_closed(monkeypatch):
    original=p.read
    def changed(path):
        result=original(path)
        if path==p.FREEZE:
            result['parameters']['window_bars']=17
        return result
    monkeypatch.setattr(p,'read',changed)
    with pytest.raises(ValueError,match='configuration hash'): p.bound_contract()


def test_symbol_override_interface_impossible_and_unregistered_fail_closed():
    assert list(inspect.signature(p.generate).parameters)==['symbol','bars','source_binding']
    with pytest.raises(TypeError): p.generate('NVDA',(),{},threshold=.1)
    with pytest.raises(ValueError,match='Unregistered'): p.generate('SPY',(),{})


def test_universe_deterministic_ordering_hash_and_source_precedes_interval():
    rows=p.select_universe()
    assert rows==p.select_universe(tuple(reversed(p.HOLDINGS)))
    assert p.encode(rows)==p.encode(p.select_universe())
    u,protocol=p.frozen_context()
    assert u['ordered_symbols']==['NVDA','AVGO','MU','AMD','AMAT','MRVL','INTC','KLAC','MPWR','TER']
    assert u['symbol_count']==10 and len(u['rows'])==30
    assert u['constituent_snapshot_effective_date']<p.START
    assert protocol['universe_manifest_sha256']==p.fingerprint(p.UNIVERSE)
    assert p.fingerprint(p.SOURCE)==p.SOURCE_HASH


def test_duplicate_share_class_requires_explicit_exclusion_not_silent_drop():
    with pytest.raises(ValueError,match='Duplicate'): p.select_universe((('NVDA',1),('NVDA',2)))


def test_candidate_determinism_repeatability_and_no_real_outcomes():
    with p.no_real_outcomes() as calls:
        a=p.generate('NVDA',synthetic(),{'synthetic':True})
        b=p.generate('NVDA',synthetic(),{'synthetic':True})
    assert a==b and p.encode(a)==p.encode(b)
    assert a['candidate_count']>0
    assert not any(calls['real'].values()) and not any(calls['shared'].values())
    assert a['outcome_access_count']==0


def test_future_publication_and_mixed_symbol_rejected():
    bars=synthetic()
    with pytest.raises(ValueError,match='causal'):
        p.generate('NVDA',(replace(bars[0],known_at=bars[1].known_at),),{})
    with pytest.raises(ValueError,match='Symbol'):
        p.generate('NVDA',(replace(bars[0],symbol='AMD'),),{})


def test_prefix_causality_matches_full_stream():
    bars=synthetic()
    with p.no_real_outcomes():
        full=p.generate('NVDA',bars,{'synthetic':True})
        prefix=p.generate('NVDA',bars[:700],{'synthetic':True})
    assert prefix['events']==[e for e in full['events'] if p.timestamp(e['causal_timestamp'])<=bars[699].known_at]


def test_identical_generator_soxx_semantic_equivalence_on_fixture():
    from scripts.h0004_segment_frequency import replay
    bars=synthetic('SOXX')
    with p.no_real_outcomes():
        original=replay(bars)
        adapted=p.generate('SOXX',bars,{'synthetic':True})
    assert [e['frozen_event'] for e in adapted['events']]==original['events']
    assert adapted['frozen_event_stream_hash']==original['event_stream_hash']
    assert adapted['candidate_count']==original['counts']['candidates']


def test_zero_signal_retained_with_no_invented_return():
    with p.no_real_outcomes(): r=p.generate('NVDA',synthetic()[:10],{})
    assert r['coverage']=='READY' and r['signal_state']=='ZERO_SIGNAL'
    assert r['candidate_count']==0 and r['signal_frequency_A']==0
    assert 'gross_return' not in r
    assert 'NVDA' in p.read(p.UNIVERSE)['ordered_symbols']


def test_unavailable_retained_with_unknown_counts(tmp_path,monkeypatch):
    monkeypatch.setattr(p,'ROOT',tmp_path)
    r,bars=p.audit_capture('NVDA')
    assert r['status']=='UNAVAILABLE' and bars==()
    assert 'NVDA' in p.read(p.UNIVERSE)['ordered_symbols']


def test_postfreeze_writer_rejects_mutation(tmp_path):
    path=tmp_path/'sealed.json'
    h=p.put(path,{'events':[]})
    assert p.put(path,{'events':[]})==h
    with pytest.raises(ValueError,match='collision'): p.put(path,{'events':[1]})
    assert p.read(path)=={'events':[]}


def test_gate_rejects_unsealed_before_any_accessor(monkeypatch,tmp_path):
    accessor=Mock(side_effect=AssertionError('No outcome'))
    monkeypatch.setattr(p,'ROOT',tmp_path)
    with patch('scripts.h0004_discovery_access.open_discovery',accessor):
        with pytest.raises(FileNotFoundError): p.authorize_real_outcomes()
    accessor.assert_not_called()


def test_p0_gate_cannot_authorize_even_ready(monkeypatch):
    monkeypatch.setattr(p,'verify_preaccess',lambda:{'status':'READY_FOR_PORTABILITY_OUTCOME_ACCESS'})
    with pytest.raises(PermissionError,match='P0 STOP'): p.authorize_real_outcomes()


def test_independent_processes_same_candidate_hash():
    code="from scripts import h0004_portability_preaccess as p; from tests.test_h0004_portability_preaccess import synthetic; print(p.digest(p.generate('NVDA',synthetic(),{'synthetic':True})))"
    a=subprocess.run([p.sys.executable,'-c',code],check=True,capture_output=True).stdout
    b=subprocess.run([p.sys.executable,'-c',code],check=True,capture_output=True).stdout
    assert a==b


def test_future_schema_is_definition_only_preserves_denominators():
    schema=p.read(p.PROTOCOL)
    assert schema['outcomes']=='NOT_ACCESSED'
    assert set(schema['denominators'])=={'full','ready','informative','complete_outcome'}
    assert schema['future_report']['pooled_event']=='DIAGNOSTIC_ONLY_NEVER_PRIMARY'
    assert schema['profitability']=='NOT_ESTIMATED'


def test_nonempty_candidate_path_accessor_spy_is_zero():
    spy=Mock(side_effect=AssertionError('No endpoint accessor in generator'))
    with p.no_real_outcomes() as calls,patch('scripts.h0004_discovery_access.open_discovery',spy):
        stream=p.generate('NVDA',synthetic(),{'synthetic':True})
    assert stream['candidate_count']>0
    spy.assert_not_called()
    assert not any(calls['real'].values()) and not any(calls['shared'].values())


@pytest.mark.parametrize('change',['stream','aggregate','input','source'])
def test_seal_mutation_detection(change,monkeypatch):
    # Runs against new P0 artifacts once they exist; before sealing use a detached
    # synthetic gate setup without touching frozen repository files.
    symbol='NVDA'; d=p.ROOT/'streams'/symbol
    u,protocol=p.frozen_context()
    audit={'symbol':symbol,'status':'UNAVAILABLE'}
    stream={'symbol':symbol,'outcome_access_count':0}
    sealed={'status':'SEALED','protocol_sha256':'p','universe_sha256':'u',
        'frozen_h0004_binding':protocol['h0004_binding'],'code_commit':'code',
        'candidate_stream_sha256':'s','input_manifest_sha256':'i'}
    row={'symbol':symbol,'candidate_stream_sha256':'s','input_manifest_sha256':'i','seal_sha256':'z'}
    code_hash=p.sha256(b'sourcebytes').hexdigest()
    manifest={'status':'SEALED','protocol_sha256':'p','universe_sha256':'u',
        'h0004_binding':protocol['h0004_binding'],'code_commit':'code','source_files':{'code.py':code_hash},
        'symbols':[row],'outcome_access_count':0,'symbol_overrides':False}
    objects={p.ROOT/'candidate-manifest.json':manifest,
        p.ROOT/'candidate-manifest.seal.json':{'status':'SEALED','manifest_sha256':'m',
            'protocol_sha256':'p','universe_sha256':'u','code_commit':'code'},
        d/'seal.json':sealed,d/'candidates.json':stream,d/'input-manifest.json':audit}
    hashes={p.PROTOCOL:'p',p.UNIVERSE:'u',p.ROOT/'candidate-manifest.json':'m',
        d/'seal.json':'z',d/'candidates.json':'s',d/'input-manifest.json':'i','code.py':code_hash}
    target={'stream':d/'candidates.json','aggregate':p.ROOT/'candidate-manifest.json',
        'input':d/'input-manifest.json','source':'code.py'}[change]
    hashes[target]='MUTATED'
    monkeypatch.setattr(p,'read',lambda path:objects[path])
    monkeypatch.setattr(p,'frozen_context',lambda:({**u,'ordered_symbols':[symbol]},protocol))
    monkeypatch.setattr(p,'fingerprint',lambda path:hashes[path])
    monkeypatch.setattr(p,'git',lambda *args:p.BRANCH.encode() if args[0]=='branch' else b'sourcebytes' if args[0]=='show' else b'')
    monkeypatch.setattr(p,'audit_capture',lambda s:(audit,()))
    with pytest.raises(ValueError,match='mutation|mismatch'): p.verify_preaccess()
