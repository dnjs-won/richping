from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock,patch
import json
import math
import pytest

from richping.core import digest,timestamp
from richping.research_v2.contracts import payload
from richping.research_v2.strategy.h0004_directional_evaluator import (
    Binding,Anchor,Scope,DirectionalEvaluator,PRICE_CONTRACT,close_identity,DATASET_ID)
from richping.research_v2.strategy.h0004_experiment import scheduled_window,DEADLINE
from scripts.h0004_preaccess_fixtures import fixture
from scripts.h0004_preaccess import zero_real_outcomes,DiscoveryPermit,frozen_binding


def rebuild(e,*,metadata=None,binding=None,anchors=None,as_of=None):
    return DirectionalEvaluator(e.anchors if anchors is None else anchors,binding or e.binding,
        metadata or e.metadata,as_of or e.as_of)


def slots_changed(e,index,**kwargs):
    slots = list(e.metadata.slots)
    slots[index] = replace(slots[index],**kwargs)
    return replace(e.metadata,slots=tuple(slots))


@pytest.mark.parametrize('field',['protocol_hash','signal_freeze_hash','calendar_hash','semantics_hash','anchor_metadata_hash'])
def test_binding_mismatch_fail_closed_before_reader(field):
    e,r = fixture()
    with pytest.raises(ValueError): rebuild(e,binding=replace(e.binding,**{field:'wrong'}))


def test_real_dataset_stream_and_synthetic_namespace_guards():
    e,r = fixture()
    for field in ('dataset_hash','candidate_stream_hash'):
        b = replace(e.binding,synthetic=False,dataset_id=DATASET_ID,**{field:'bad'})
        with pytest.raises(ValueError): b.validate()
    with pytest.raises(PermissionError): replace(e.binding,dataset_id=DATASET_ID).validate()
    with pytest.raises(ValueError): replace(e.binding,scope='DISCOVERY_EXPLORATORY').validate()


def test_exact_target_and_known_formula_reads_only_anchor_and_exact_endpoint():
    e,r = fixture()
    tracked = Mock(side_effect=r)
    state = e.readiness(e.anchors[0].event_id)
    assert state['status']=='READY_TO_EVALUATE'
    assert not any(e.audit.values())
    row = e.label(e.anchors[0].event_id,tracked)
    assert row['gross_return']==pytest.approx(.1) and row['status']=='COMPLETE'
    assert [c.args[0] for c in tracked.call_args_list]==[
        timestamp('2026-05-06T10:00:00-04:00'),timestamp('2026-05-06T14:00:00-04:00')]
    assert e.audit['forward_price_queries']==1 and e.audit['return_calculations']==1


@pytest.mark.parametrize('at,first,last',[
    ('2026-05-08T20:00:00-04:00','2026-05-11T04:15:00-04:00','2026-05-11T08:00:00-04:00'),
    ('2026-05-22T20:00:00-04:00','2026-05-26T04:15:00-04:00','2026-05-26T08:00:00-04:00'),
    ('2026-05-06T19:45:00-04:00','2026-05-06T20:00:00-04:00','2026-05-07T07:45:00-04:00')])
def test_closures_consume_no_slots(at,first,last):
    path,_ = scheduled_window(at)
    assert len(path)==16 and path[0]==timestamp(first) and path[-1]==timestamp(last)


@pytest.mark.parametrize('missing',[1,7,16])
def test_any_missing_expected_slot_never_compresses_horizon(missing):
    e,r = fixture()
    metadata = replace(e.metadata,slots=tuple(m for i,m in enumerate(e.metadata.slots) if i!=missing))
    e = rebuild(e,metadata=metadata)
    row = e.label(e.anchors[0].event_id,Mock(side_effect=AssertionError('Must not read')))
    assert row['status']=='UNRESOLVED' and row['reason']=='missing_expected_supported_slot'
    assert row['target_at']==timestamp('2026-05-06T14:00:00-04:00').isoformat()
    assert not any(e.audit.values())


def test_missing_before_maturity_pending_then_unresolved():
    e,r = fixture(as_of='2026-05-06T13:59:59-04:00')
    meta = replace(e.metadata,slots=e.metadata.slots[:-1])
    e = rebuild(e,metadata=meta)
    assert e.readiness(e.anchors[0].event_id)['status']=='PENDING'
    e = rebuild(e,as_of='2026-05-06T14:00:00-04:00')
    assert e.readiness(e.anchors[0].event_id)['status']=='UNRESOLVED'


def test_outside_discovery_scope_unresolved_no_supplement():
    e,r = fixture(times=('2026-08-13T20:00:00-04:00',))
    row = e.label(e.anchors[0].event_id,Mock(side_effect=AssertionError('Outside scope')))
    assert row['status']=='UNRESOLVED' and row['reason']=='outside_sealed_scope'


def test_unsupported_nominal_followup_not_replaced_by_rth_or_next_supported_date():
    e,r = fixture(times=('2026-11-25T20:00:00-05:00',),scope=Scope.CONFIRMATION_TERMINAL,
        start='2026-10-19',end='2027-10-20',as_of='2027-10-22T00:00:00-04:00')
    row = e.label(e.anchors[0].event_id,Mock(side_effect=AssertionError('Unsupported')))
    assert row['status']=='UNRESOLVED' and row['reason']=='unsupported_nominal_session'
    assert timestamp(row['target_at']).date().isoformat()=='2026-11-27'


@pytest.mark.parametrize('changes',[{'action':'SPLIT'},{'action':'UNKNOWN'},
    {'action':'AMBIGUOUS'},{'unit_segment':'raw_unit_2'},{'unit_certified':False}])
def test_action_and_share_unit_boundary_unresolved_without_adjusted_fallback(changes):
    e,r = fixture()
    e = rebuild(e,metadata=slots_changed(e,8,**changes))
    row = e.label(e.anchors[0].event_id,Mock(side_effect=AssertionError('No transform')))
    assert row['status']=='UNRESOLVED' and row['reason']=='action_or_raw_unit_ambiguity'
    assert not any(e.audit.values())


def test_cash_dividend_disclosed_but_price_only_label_unchanged():
    e,r = fixture()
    e = rebuild(e,metadata=slots_changed(e,8,action='CASH_DIVIDEND',cash_dividend=True))
    row = e.label(e.anchors[0].event_id,r)
    assert row['gross_return']==pytest.approx(.1) and row['cash_dividend_disclosed']


@pytest.mark.parametrize('changes',[{'known_at':'2026-05-06T10:01:00-04:00'},
    {'contract':('ADJUSTED',)},{'close_identity':'wrong'}])
def test_clock_feed_adjustment_anchor_identity_fail_closed(changes):
    e,r = fixture()
    e = rebuild(e,metadata=slots_changed(e,0,**changes))
    assert e.readiness(e.anchors[0].event_id)['status']=='INVALID_FAIL_CLOSED'


@pytest.mark.parametrize('which',['event','episode'])
def test_duplicate_event_or_episode_fail_closed(which):
    e,r = fixture(times=('2026-05-06T10:00:00-04:00','2026-05-06T10:15:00-04:00'),returns=(.1,.1))
    anchors = (e.anchors[0],replace(e.anchors[1],**{which+'_id':getattr(e.anchors[0],which+'_id')}))
    b = replace(e.binding,anchor_metadata_hash=digest(payload(anchors)))
    with pytest.raises(ValueError,match='duplicate'): rebuild(e,anchors=anchors,binding=b)


def test_session_balancing_unequal_events_full_denominator_and_no_complete_case():
    e,r = fixture(times=('2026-05-06T10:00:00-04:00','2026-05-06T10:15:00-04:00',
        '2026-05-06T10:30:00-04:00','2026-05-07T10:00:00-04:00'),returns=(.1,.1,.1,-.1))
    rows = e.evaluate(r)
    result = e.aggregate(rows)
    assert result['full_cohort_session_balanced_mean']==pytest.approx(0)
    assert result['total_emitted']==result['complete']==4 and result['candidate_sessions']==2
    for status in ('PENDING','UNRESOLVED','INVALID_FAIL_CLOSED'):
        partial = [dict(x) for x in rows]
        partial[-1].update(status=status,gross_return=None)
        result = e.aggregate(partial)
        assert result['full_cohort_session_balanced_mean'] is None and result['total_emitted']==4
        assert result[{'PENDING':'pending','UNRESOLVED':'unresolved','INVALID_FAIL_CLOSED':'invalid'}[status]]==1
    with pytest.raises(ValueError): e.aggregate(rows[:-1])
    with pytest.raises(ValueError): e.aggregate(rows[::-1])


def test_one_event_and_multiple_equal_session_events():
    for times,returns,expected in [(('2026-05-06T10:00:00-04:00',),(.1,),.1),
        (('2026-05-06T10:00:00-04:00','2026-05-06T10:15:00-04:00'),(.1,.3),.2)]:
        e,r = fixture(times=times,returns=returns)
        assert e.aggregate(e.evaluate(r))['full_cohort_session_balanced_mean']==pytest.approx(expected)


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-float('inf'),0,-1,True])
def test_nonfinite_or_invalid_close_fails_closed(value):
    e,r = fixture()
    row = e.label(e.anchors[0].event_id,lambda *a:value)
    assert row['status']=='INVALID_FAIL_CLOSED' and row['gross_return'] is None


def test_nonfinite_label_or_value_exposure_cannot_aggregate():
    e,r = fixture()
    rows = [dict(x) for x in e.evaluate(r)]
    rows[0]['gross_return']=float('nan')
    with pytest.raises(ValueError): e.aggregate(rows)
    rows[0].update(status='UNRESOLVED',gross_return=.1)
    with pytest.raises(ValueError): e.aggregate(rows)


def test_discovery_cannot_access_confirmation_identity_or_source():
    e,r = fixture()
    anchors = (replace(e.anchors[0],at='2026-10-19T14:00:00+00:00',session='2026-10-19'),)
    b = replace(e.binding,anchor_metadata_hash=digest(payload(anchors)))
    with pytest.raises(PermissionError): rebuild(e,anchors=anchors,binding=b)
    with pytest.raises(PermissionError): rebuild(e,metadata=replace(e.metadata,end_session='2026-10-19'))


@pytest.mark.parametrize('as_of',['2026-10-19T20:00:00-04:00',DEADLINE])
def test_confirmation_preterminal_label_and_aggregation_blocked(as_of):
    e,r = fixture(times=('2026-10-19T10:00:00-04:00',),scope=Scope.CONFIRMATION_TERMINAL,
        start='2026-10-19',end='2027-10-20',as_of=as_of)
    rows = e.evaluate(Mock(side_effect=AssertionError('No confirmation outcome')))
    assert rows[0]['status']=='PENDING' and rows[0]['gross_return'] is None
    assert not any(e.audit.values())
    with pytest.raises(PermissionError): e.aggregate(rows)


def test_confirmation_exact_after_deadline_synthetic_only():
    e,r = fixture(times=('2026-10-19T10:00:00-04:00',),scope=Scope.CONFIRMATION_TERMINAL,
        start='2026-10-19',end='2027-10-20',as_of=timestamp(DEADLINE)+timedelta(microseconds=1))
    assert e.evaluate(r)[0]['status']=='COMPLETE'
    with pytest.raises(PermissionError): replace(e.binding,synthetic=False).validate()


def test_real_access_cannot_activate_from_this_action():
    with pytest.raises(PermissionError): DiscoveryPermit('H0004_FIRST_EFFICACY')
    with pytest.raises(PermissionError): DiscoveryPermit('CONFIRMATION_TERMINAL')
    from scripts.h0004_discovery_access import open_discovery
    with patch('scripts.h0004_discovery_access.load_admitted',side_effect=AssertionError('No real load')):
        with pytest.raises(PermissionError): open_discovery(lambda *a:True)


def test_synthetic_repeat_and_zero_real_outcome_guard():
    with zero_real_outcomes() as calls:
        e,r = fixture()
        first = e.aggregate(e.evaluate(r))
        e,r = fixture()
        second = e.aggregate(e.evaluate(r))
    assert first==second
    assert not any(calls['real_H0004'].values())
    assert not any(v for group in calls['shared_forbidden'].values() for v in group.values())


def test_frozen48_metadata_preserved_without_endpoint_probes():
    with zero_real_outcomes() as calls:
        binding,anchors = frozen_binding()
    assert len(anchors)==48 and len({a.session for a in anchors})==29
    assert binding.candidate_stream_hash=='8e64aecd6fa26261bf5735126f3615427427bbe5ae34b0d242b8d14dd513d14d'
    assert not any(calls['real_H0004'].values())


def test_duplicate_metadata_slot_and_wrong_dataset_or_admission_rejected():
    e,r = fixture()
    with pytest.raises(ValueError): rebuild(e,metadata=replace(e.metadata,slots=e.metadata.slots+(e.metadata.slots[0],)))
    for field in ('dataset_id','dataset_hash','admission_hash'):
        with pytest.raises(ValueError): rebuild(e,metadata=replace(e.metadata,**{field:'wrong'}))


def test_reader_identity_mismatch_cannot_compute_return():
    e,r = fixture()
    row = e.label(e.anchors[0].event_id,lambda *args:999.0)
    assert row['status']=='INVALID_FAIL_CLOSED' and e.audit['return_calculations']==0


def test_noncomplete_state_precedence_and_zero_signal_denominator():
    e,r = fixture(times=('2026-05-06T10:00:00-04:00','2026-05-07T10:00:00-04:00'),returns=(.1,.1))
    rows = [dict(x) for x in e.evaluate(r)]
    rows[0].update(status='PENDING',gross_return=None)
    rows[1].update(status='UNRESOLVED',gross_return=None)
    assert e.aggregate(rows)['status']=='PENDING'
    rows[1]['status']='INVALID_FAIL_CLOSED'
    assert e.aggregate(rows)['status']=='INVALID_FAIL_CLOSED'
    e,r = fixture(times=(),returns=())
    result = e.aggregate(())
    assert result['status']=='ZERO_SIGNAL' and result['total_emitted']==0
    assert result['full_cohort_session_balanced_mean'] is None


def test_unavailable_slot_before_availability_pending_no_reader():
    e,r = fixture(as_of='2026-05-06T14:00:00-04:00')
    e = rebuild(e,metadata=slots_changed(e,8,known_at='2026-05-06T14:01:00-04:00'))
    row = e.label(e.anchors[0].event_id,Mock(side_effect=AssertionError('Before known_at')))
    assert row['status']=='PENDING' and not any(e.audit.values())


def test_preaccess_manifest_mismatch_fail_closed_before_any_real_price(tmp_path,monkeypatch):
    from scripts import h0004_preaccess as seal
    e,r = fixture()
    bound = tmp_path/'bound.py'
    bound.write_bytes(b'original')
    fake = dict(source_hashes={str(bound):seal.fingerprint(bound)},dataset_files={},protected_files={})
    (tmp_path/'manifest.json').write_bytes(seal.encode(fake))
    monkeypatch.setattr(seal,'ROOT',tmp_path)
    bound.write_bytes(b'changed')
    with zero_real_outcomes() as calls,pytest.raises(ValueError,match='dependency changed'):
        seal.verify_manifest()
    assert not any(calls['real_H0004'].values())


def test_pass_receipt_and_separate_action_required_without_price_queries(tmp_path,monkeypatch):
    from scripts import h0004_preaccess as seal
    e,r = fixture()
    (tmp_path/'manifest.json').write_bytes(b'{}')
    manifest = dict(source_hashes={})
    monkeypatch.setattr(seal,'ROOT',tmp_path)
    monkeypatch.setattr(seal,'verify_manifest',lambda:(manifest,e.binding,e.anchors))
    permit = DiscoveryPermit('H0004_DISCOVERY_EFFICACY_EXECUTION')
    for status,hashvalue in [('FAIL',seal.fingerprint(tmp_path/'manifest.json')),('PASS_PREACCESS_NO_REAL_OUTCOMES','wrong')]:
        proof = dict(status=status,manifest_sha256=hashvalue,source_hashes={},real_outcome_access=0)
        (tmp_path/'verification.json').write_bytes(seal.encode(proof))
        with pytest.raises(PermissionError): permit.authorize()
    proof['manifest_sha256']=seal.fingerprint(tmp_path/'manifest.json')
    (tmp_path/'verification.json').write_bytes(seal.encode(proof))
    fake_process = Mock(stdout=b'next_action:\n  id: H0004_FIRST_EFFICACY\n')
    with patch.object(seal.subprocess,'run',return_value=fake_process),pytest.raises(PermissionError):
        permit.authorize()
