from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
from unittest.mock import Mock,patch

import pytest

from richping.core import digest,timestamp
from richping.research_v2.sessions import NY
from richping.research_v2.strategy.h0003_leadership import CONTRACT,Specification
from richping.research_v2.strategy.h0003_experiment import scheduled_window,DEADLINE
from richping.research_v2.strategy import h0003_efficacy as ev
from scripts import h0003_first_efficacy as runner


def event(at='2026-05-06T12:00:00-04:00',episode='synthetic-episode'):
    at = timestamp(at)
    local = at.astimezone(NY)
    # Selected synthetic dates have the preceding official session below.
    prior = {'2026-05-06':'2026-05-05','2026-08-13':'2026-08-12'}[local.date().isoformat()]
    anchor = timestamp(prior+'T'+local.strftime('%H:%M:%S')+local.strftime('%z'))
    body = dict(episode_id=episode,at=at.isoformat(),session=local.date().isoformat(),
        spec_hash=Specification().hash,datasets=['own-test','bench-test'],own_return=.01,
        benchmark_return=0.,relative_return=.01,anchor_at=anchor.isoformat())
    return dict(id=digest(body),**body)


def binding(events):
    return dict(protocol_hash=ev.PROTOCOL_HASH,signal_freeze_hash=ev.FREEZE_HASH,
        dataset_ids=['own-test','bench-test'],candidate_stream_hash=digest(events))


def bar(at,symbol='SOXX',close=100):
    at = timestamp(at)
    return ev.OutcomeBar('own-test' if symbol=='SOXX' else 'bench-test',symbol,
        at-timedelta(minutes=15),at,at,at.astimezone(NY).date().isoformat(),
        close,close+1,close-1,close,CONTRACT,True)


def source(e=None,own_end=105,bench_end=102,horizon=16):
    e = e or event()
    window,_ = scheduled_window(e['at'],horizon)
    slots = [timestamp(e['at']),*window]
    own = [bar(t,close=own_end if i==len(slots)-1 else 100) for i,t in enumerate(slots)]
    bench = [bar(t,'QQQ',bench_end if i==len(slots)-1 else 100) for i,t in enumerate(slots)]
    certified = sorted({b.session for b in own if ev.START<=b.session<=ev.END})
    return own,bench,[e],certified


def reader(own,bench,events,certified):
    return ev.DiscoveryLabels(own,bench,events,binding(events),certified,'2026-10-04T20:00:00Z')


def test_exact_paired_16_slot_return_and_access_counters():
    data = source()
    r = reader(*data)
    label = r.label(data[2][0]['id'],16)
    assert label['status']=='COMPLETE'
    assert timestamp(label['target_at'])==timestamp('2026-05-06T16:00:00-04:00')
    assert label['own_return']==pytest.approx(.05)
    assert label['benchmark_return']==pytest.approx(.02)
    assert label['relative_excess']==pytest.approx(.03)
    assert r.audit['discovery_path_lookup_requests']==34
    assert r.audit['discovery_endpoint_close_reads']==2
    assert r.audit['discovery_anchor_close_reads']==2
    assert r.audit['confirmation_label_requests']==r.audit['confirmation_price_reads']==0
    assert r.trace[0]['expected_path'][-1]==label['target_at']


@pytest.mark.parametrize('h',[4,16,64])
def test_registered_horizons_use_scheduled_endpoint(h):
    data = source(horizon=h)
    r = reader(*data)
    label = r.label(data[2][0]['id'],h)
    assert label['status']=='COMPLETE' and label['horizon_slots']==h
    assert label['target_at']==scheduled_window(data[2][0]['at'],h)[0][-1].isoformat()


def test_cross_session_exact_endpoint_both_assets():
    data = source(event('2026-05-06T19:00:00-04:00'))
    label = reader(*data).label(data[2][0]['id'],16)
    assert label['status']=='COMPLETE'
    assert timestamp(label['target_at'])==timestamp('2026-05-07T07:00:00-04:00')


def test_missing_middle_slot_with_later_existing_row_never_compresses():
    own,bench,events,cert = source()
    bench.pop(5)
    extra = bar(own[-1].end_at+timedelta(minutes=15),'QQQ',110)
    r = reader(own,bench+[extra],events,cert)
    label = r.label(events[0]['id'],16)
    assert label['status']=='UNRESOLVED' and label['reason']=='missing_scheduled_slot_no_compression'
    assert label['relative_excess'] is None and r.audit['discovery_endpoint_close_reads']==0
    assert label['target_at']==own[-1].end_at.isoformat()


@pytest.mark.parametrize('kind',['anchor_missing','endpoint_missing','endpoint_shift','stale','future','feed','unit','action','nan','zero','ohlc'])
def test_entire_paired_path_failures_unresolved_without_zero_substitution(kind):
    own,bench,events,cert = source()
    if kind=='anchor_missing': bench.pop(0)
    if kind=='endpoint_missing': bench.pop()
    if kind=='endpoint_shift': bench[-1]=bar(bench[-1].end_at+timedelta(minutes=15),'QQQ',102)
    if kind=='stale': bench[3]=replace(bench[3],known_at=bench[3].end_at-timedelta(minutes=15))
    if kind=='future': bench[3]=replace(bench[3],known_at=bench[3].end_at+timedelta(minutes=15))
    if kind=='feed': bench[3]=replace(bench[3],contract=(CONTRACT[0],'iex',*CONTRACT[2:]))
    if kind=='unit': bench[3]=replace(bench[3],contract=(*CONTRACT[:2],'split',*CONTRACT[3:]))
    if kind=='action': bench[3]=replace(bench[3],unit_certified=False)
    if kind=='nan': bench[3]=replace(bench[3],high=float('nan'))
    if kind=='zero': bench[3]=replace(bench[3],close=0)
    if kind=='ohlc': bench[3]=replace(bench[3],high=90)
    r = reader(own,bench,events,cert)
    label = r.label(events[0]['id'],16)
    assert label['status']=='UNRESOLVED'
    assert label['own_return'] is label['benchmark_return'] is label['relative_excess'] is None
    assert r.audit['discovery_endpoint_close_reads']==0


def test_outside_scope_detected_before_either_asset_lookup():
    e = event('2026-08-13T19:00:00-04:00')
    at = timestamp(e['at'])
    own,bench = [bar(at)],[bar(at,'QQQ')]
    r = reader(own,bench,[e],['2026-08-13'])
    for h in (16,64):
        label = r.label(e['id'],h)
        assert label['status']=='UNRESOLVED' and label['reason']=='outside_admitted_discovery_scope'
    assert r.audit['discovery_path_lookup_requests']==r.audit['discovery_endpoint_close_reads']==0
    assert r.audit['outside_scope_labels']==2


def test_unsupported_grid_session_not_compressed_or_read():
    data = source()
    expected = scheduled_window(data[2][0]['at'],16)[0]
    with patch.object(ev,'scheduled_window',return_value=(expected,('2026-05-06',))):
        r = reader(*data)
        label = r.label(data[2][0]['id'],16)
    assert label['reason']=='unsupported_scheduled_session'
    assert r.audit['discovery_path_lookup_requests']==0


def test_missing_interval_certificate_and_immature_capture_unresolved():
    own,bench,events,cert = source()
    r = reader(own,bench,events,[])
    assert r.label(events[0]['id'],16)['reason']=='action_unit_certificate_unavailable'
    r = ev.DiscoveryLabels(own,bench,events,binding(events),cert,events[0]['at'])
    assert r.label(events[0]['id'],16)['status']=='UNRESOLVED'
    assert r.audit['discovery_endpoint_close_reads']==0


@pytest.mark.parametrize('kind',['protocol','freeze','candidate_hash','candidate_body','candidate_duplicate'])
def test_binding_mismatch_precedes_any_source_iteration(kind):
    events = [event()]
    b = binding(events)
    if kind=='protocol': b['protocol_hash']='bad'
    if kind=='freeze': b['signal_freeze_hash']='bad'
    if kind=='candidate_hash': b['candidate_stream_hash']='bad'
    if kind=='candidate_body': events[0]['own_return']=0
    if kind=='candidate_duplicate': events=events*2; b['candidate_stream_hash']=digest(events)
    class NeverRead:
        def __iter__(self):
            raise AssertionError('Market source inspected before failed binding')
    with pytest.raises(ValueError):
        ev.DiscoveryLabels(NeverRead(),NeverRead(),events,b,['2026-05-06'],'2026-10-04T20:00:00Z')


@pytest.mark.parametrize('kind',['duplicate','wrong_dataset','wrong_symbol','confirmation_source'])
def test_bad_source_identity_or_scope_rejected(kind):
    own,bench,events,cert = source()
    if kind=='duplicate': own.append(own[0])
    if kind=='wrong_dataset': own[0]=replace(own[0],dataset_id='other')
    if kind=='wrong_symbol': own[0]=replace(own[0],symbol='SPY')
    if kind=='confirmation_source': own.append(bar('2026-10-19T12:00:00-04:00'))
    with pytest.raises((ValueError,PermissionError)):
        reader(own,bench,events,cert)


def test_unknown_event_and_horizon_cannot_open_window():
    data = source()
    r = reader(*data)
    with pytest.raises(PermissionError): r.label('confirmation-unsealed',16)
    with pytest.raises(ValueError): r.label(data[2][0]['id'],192)
    assert r.audit['discovery_label_requests']==r.audit['confirmation_price_reads']==0


def metric_row(identity,session,own,bench,status='COMPLETE'):
    label = dict(status=status,reason='synthetic' if status=='COMPLETE' else 'outside_admitted_discovery_scope',
        own_return=own,benchmark_return=bench,relative_excess=own-bench if status=='COMPLETE' else None)
    return dict(event_id=identity,session=session,labels={str(h):dict(label) for h in ev.HORIZONS})


def test_session_balanced_same_session_multi_event_exact_weighting():
    rows = [metric_row('a','2026-05-06',.02,0),metric_row('b','2026-05-06',.04,0),
            metric_row('c','2026-05-07',0,0)]
    primary = ev.metrics(rows)['16']
    assert primary['excess']['session_balanced_mean_resolved']==pytest.approx(.015)
    assert primary['excess']['event_median_resolved']==pytest.approx(.02)
    assert primary['excess']['positive_count']==2
    assert primary['excess']['positive_rate_resolved']==pytest.approx(2/3)
    assert primary['complete_sessions']==2
    assert primary['bootstrap_interval'] is primary['p_value'] is None


def test_all35_denominator_retained_and_subset_not_claimed_whole_cohort():
    rows = [metric_row(str(i),'2026-05-06',.01,0) for i in range(34)]
    rows.append(metric_row('34','2026-05-07',None,None,'UNRESOLVED'))
    results = ev.metrics(rows)
    assert all(m['events']==35 and m['complete']==34 and m['unresolved']==1 for m in results.values())
    assert results['16']['excess']['full_cohort_session_balanced_mean'] is None
    assert results['16']['excess']['resolved_denominator']==34
    assert results['16']['estimate_scope']=='RESOLVED_SUBSET_ONLY_FULL_COHORT_UNKNOWN'
    assert ev.exploratory_disposition(results)=='DISCOVERY_INSUFFICIENT_RESOLVED_LABELS'


@pytest.mark.parametrize('own,bench,expected',[(.02,.01,'DISCOVERY_POSITIVE_RELATIVE_DIRECTION'),
    (-.02,-.04,'DISCOVERY_POSITIVE_RELATIVE_DIRECTION'),(-.02,.01,'DISCOVERY_NEGATIVE_RELATIVE_DIRECTION'),
    (.02,.02,'DISCOVERY_MIXED')])
def test_relative_disposition_does_not_claim_absolute_long_profit(own,bench,expected):
    results = ev.metrics([metric_row('a','2026-05-06',own,bench)])
    assert ev.exploratory_disposition(results)==expected
    assert results['16']['SOXX']['session_balanced_mean_resolved']==own
    assert all(m['uncertainty_status']=='DISCOVERY_UNCERTAINTY_NOT_PREREGISTERED' for m in results.values())


def test_secondary_cannot_rescue_or_replace_registered_primary():
    row = metric_row('a','2026-05-06',-.01,.01)
    for h in ('4','64'):
        row['labels'][h].update(own_return=.1,benchmark_return=0.,relative_excess=.1)
    assert ev.exploratory_disposition(ev.metrics([row]))=='DISCOVERY_NEGATIVE_RELATIVE_DIRECTION'


def test_confirmation_before_or_at_deadline_never_calls_loader_or_exposes_performance():
    loader = Mock(side_effect=AssertionError('Confirmation outcome touched'))
    for at in ('2026-10-05T20:00:00Z',DEADLINE):
        result = ev.confirmation_readiness(at,loader)
        assert result==dict(status='PENDING',confirmation_outcome_access=0,performance=None)
    result = ev.confirmation_readiness(timestamp(DEADLINE)+timedelta(seconds=1),loader)
    assert result['status']=='UNRESOLVED' and result['performance'] is None
    loader.assert_not_called()


def test_synthetic_repeat_results_and_audit_hashes_identical():
    data = source(horizon=64)
    first,second = reader(*data),reader(*data)
    rows1,rows2 = ev.evaluate(data[2],first),ev.evaluate(data[2],second)
    assert rows1==rows2 and digest(rows1)==digest(rows2)
    assert first.trace==second.trace and dict(first.audit)==dict(second.audit)
    assert ev.metrics(rows1)==ev.metrics(rows2)


def test_execute_failed_preflight_cannot_call_market_loader():
    with patch.object(runner,'verify_contract',side_effect=ValueError('INVALID_FAIL_CLOSED')),patch.object(runner,'prepare_sources') as load:
        with pytest.raises(ValueError,match='INVALID_FAIL_CLOSED'): runner.execute()
    load.assert_not_called()


def test_real_frozen_protocol_metadata_hash_mismatch_fails_before_loading():
    with patch.object(ev,'PROTOCOL_HASH','bad'),patch.object(runner,'prepare_sources') as load:
        with pytest.raises(ValueError,match='INVALID_FAIL_CLOSED'): runner.execute()
    load.assert_not_called()


def test_guard_blocks_other_labels_inference_and_preparation_discovery_access():
    from richping.research_v2.strategy import h0002_efficacy
    with runner.guarded(preparation=True) as calls:
        with pytest.raises(AssertionError): ev.DiscoveryLabels.label(None,None,16)
        with pytest.raises(AssertionError): h0002_efficacy._registered_bootstrap({})
        with pytest.raises(AssertionError): h0002_efficacy.DiscoveryLabels.label(None,None,None,None,None)
    assert calls['label_before_seal_or_preparation_complete']==1
    assert calls['uncertainty_calculation']==1 and calls['other_hypothesis_labels']==1


def test_saved_real_discovery_preserves_all35_and_repeat_identity_without_market_reads():
    report = json.loads((runner.ROOT/'discovery-report.json').read_bytes())
    rows = json.loads((runner.ROOT/'event-results.json').read_bytes())['events']
    proof = json.loads((runner.ROOT/'repeat-proof.json').read_bytes())
    assert report['candidate_events']==len(rows)==35 and report['candidate_sessions']==29
    assert report['retained_candidate_ids']==[r['event_id'] for r in rows]
    assert report['metrics']==ev.metrics(rows) and report['disposition']==ev.exploratory_disposition(report['metrics'])
    assert proof['report_hash']==digest(report) and proof['repeat_equal']
    assert all(runner.fingerprint(runner.ROOT/p)==h for p,h in proof['result_hashes'].items())
    assert report['confirmation_outcome_access']==0 and report['confirmation_status']=='PENDING'
    assert report['profitability']=='NOT_ESTIMATED' and report['bootstrap_interval'] is report['p_value'] is None
    assert report['disposition'].startswith('DISCOVERY_')
    for m in report['metrics'].values():
        assert m['complete']+m['unresolved']==35
        assert m['uncertainty_status']=='DISCOVERY_UNCERTAINTY_NOT_PREREGISTERED'


def test_saved_real_all_prior_hashes_and_registered_access_plan_preserved():
    with runner.frozen.metadata_only() as counts:
        manifest,record,events,b = runner.verify_manifest()
    assert not any(counts.values())
    plan = json.loads((runner.ROOT/'outcome-access-plan.json').read_bytes())
    assert len(plan['labels'])==105 and plan['primary_horizon']==16
    assert plan['binding']==b and [e['id'] for e in events]==b['candidate_ids']
    audit = json.loads((runner.ROOT/'outcome-access-audit.json').read_bytes())
    assert audit['counts']['discovery_label_requests']==105
    assert audit['counts']['confirmation_label_requests']==audit['counts']['confirmation_price_reads']==0
    assert audit['counts']['uncertainty_calculations']==0
