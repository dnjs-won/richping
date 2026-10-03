"""Frozen boundaries/causality only; no market outcomes or parameter selection."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import subprocess

import pytest
import yaml

from richping.core import digest
from richping.research_v2.contracts import JsonObject, ReplayContext
from richping.research_v2.strategy.entry_15m import (
    FIRST_READY_COUNT, M15Observation, M15Memory, classify_15m, contract_hash, downside_label,
    evaluate_temporal, frozen_values, gc_event, measure_completed_15m, price_confirmation,
)
from richping.research_v2.strategy.h0001_spec import H0001Specification
from richping.research_v2.strategy.specification import C1, PERFORMANCE, OPTIONAL
from test_research_v2_extended import bars

ROOT = Path(__file__).resolve().parents[1]
SPEC = 'research/strategy_specs/H0001-r03-draft.yaml'


@pytest.mark.parametrize('line,rank,state', [(-1, .1, 'DOWNSIDE_EXTREME'),
    (-1, .1000001, 'INACTIVE'), (-1, .0999999, 'DOWNSIDE_EXTREME'),
    (0, .01, 'INACTIVE'), (1, .01, 'INACTIVE'), (-.00001, .01, 'DOWNSIDE_EXTREME')])
def test_exact_threshold_equality_and_polarity(line, rank, state):
    assert downside_label(line, rank) == state


@pytest.mark.parametrize('line,rank', [(None, .1), (float('nan'), .1), (-1, float('inf')), (-1, -.1), (-1, 1.1)])
def test_no_malformed_READY_operands(line, rank):
    with pytest.raises(ValueError):
        downside_label(line, rank)


@pytest.mark.parametrize('prior,current,result', [(-1, 1, True), (0, 1, True),
    (1, 1, False), (-1, 0, False), (0, 0, False), (-1, -1, False)])
def test_gc_cross_event_not_persistent_relation(prior, current, result):
    assert gc_event(prior, 0, current, 0) is result
    assert gc_event(None, 0, current, 0) is None


def test_price_direction_only_strict_completed_close():
    assert price_confirmation(10, 11) is True
    assert price_confirmation(10, 10) is False
    assert price_confirmation(10, 9) is False
    assert price_confirmation(None, 11) is None


@pytest.fixture(scope='module')
def inputs():
    return sum((bars(day) for day in ('2024-03-11', '2024-03-12', '2024-03-13',
                                    '2024-03-14', '2024-03-15', '2024-03-18')), ())


def test_first_readiness_ties_and_deterministic_prefix_no_lookahead(inputs):
    selected = inputs[:FIRST_READY_COUNT]
    results = measure_completed_15m(ReplayContext(selected[-1].known_at, selected), 'ALFA')
    assert all(o.raw == 'UNAVAILABLE' for o in results[:-1])
    assert results[-2].ready_reference_count == 191
    assert results[-1].ready_reference_count == 192
    assert results[-1].raw != 'UNAVAILABLE'
    assert results[128].line is None and results[129].line is not None
    extended = measure_completed_15m(ReplayContext(inputs[-1].known_at, inputs), 'ALFA')
    assert tuple(replace(o, as_of=selected[-1].known_at) for o in extended[:321]) == results
    assert results == measure_completed_15m(ReplayContext(selected[-1].known_at, selected), 'ALFA')
    constant = tuple(replace(b, open=100, high=100, low=100, close=100) for b in selected)
    current = classify_15m(ReplayContext(constant[-1].known_at, constant), 'ALFA', expected_completed_end=constant[-1].end_at)
    assert current.percentile == .5 and current.raw == 'INACTIVE'


def test_missing_continuity_and_stale_completion_are_UNAVAILABLE(inputs):
    selected = inputs[:330]
    broken = selected[:310] + selected[311:]
    result = classify_15m(ReplayContext(broken[-1].known_at, broken), 'ALFA', expected_completed_end=broken[-1].end_at)
    assert result.raw == 'UNAVAILABLE' and result.gc is None
    stale = classify_15m(ReplayContext(selected[-1].known_at, selected[:-1]), 'ALFA', expected_completed_end=selected[-1].end_at)
    assert stale.raw == 'UNAVAILABLE' and 'missing' in stale.reason


def test_mixed_provenance_fail_closed(inputs):
    selected = inputs[:330]
    changed = replace(selected[-1], source='other-provider')
    result = classify_15m(ReplayContext(changed.known_at, selected[:-1]+(changed,)), 'ALFA', expected_completed_end=changed.end_at)
    assert result.raw == 'UNAVAILABLE' and 'mixed_provider' in result.reason
    meta = changed.provenance.unpack()
    meta['price_basis'] = 'unmatched-price-basis'
    changed = replace(selected[-1], provenance=JsonObject.of(meta))
    result = classify_15m(ReplayContext(changed.known_at, selected[:-1]+(changed,)), 'ALFA', expected_completed_end=changed.end_at)
    assert result.raw == 'UNAVAILABLE'


def test_delayed_prefix_dependency_known_at_not_backdated(inputs):
    selected = inputs[:321]
    delayed_at = selected[-1].end_at+timedelta(minutes=10)
    delayed = selected[:100] + (replace(selected[100], known_at=delayed_at),) + selected[101:]
    result = measure_completed_15m(ReplayContext(delayed_at, delayed), 'ALFA')
    assert result[99].known_at == selected[99].known_at
    assert all(o.known_at == delayed_at for o in result[100:])
    assert result[-1].raw != 'UNAVAILABLE'
    with pytest.raises(ValueError, match='Future'):
        ReplayContext(selected[-1].end_at, delayed)


def observation(i=0, *, extreme=False, gc=False, price=True, unavailable=False):
    source = bars(count=1, offset=i)[0]
    return M15Observation('ALFA', source.end_at, source.known_at, source.known_at,
        i, bars(count=1)[0].end_at, 'fixture-only', digest(['fixture', i, extreme, gc, price, unavailable]),
        'UNAVAILABLE' if unavailable else 'DOWNSIDE_EXTREME' if extreme else 'INACTIVE',
        'missing_input' if unavailable else None, -1., -2., None if unavailable else .1 if extreme else .5,
        0 if unavailable else 192, None if unavailable else gc, None if unavailable else price)


@pytest.mark.parametrize('K,trigger', [(0, True), (4, True), (5, False)])
def test_fixed_grace_boundary_including_same_observation(K, trigger):
    memory = None
    for i in range(K+1):
        memory = evaluate_temporal(memory, observation(i, extreme=i==0, gc=i==K), scope_ref='eligible-fixture-episode')
    assert memory.trigger is trigger


def test_extremes_do_not_refresh_or_indefinitely_rearm():
    memory = None
    for i in range(10):
        memory = evaluate_temporal(memory, observation(i, extreme=True, gc=i==9), scope_ref='episode')
        assert not memory.trigger
        if i < 5:
            assert memory.arm_index == 0
    assert memory.locked
    memory = evaluate_temporal(memory, observation(10), scope_ref='episode')
    assert not memory.locked
    memory = evaluate_temporal(memory, observation(11, extreme=True, gc=True), scope_ref='episode')
    assert memory.trigger


def test_first_cross_price_failure_consumes_no_later_cross_shopping():
    memory = evaluate_temporal(None, observation(extreme=True), scope_ref='episode')
    memory = evaluate_temporal(memory, observation(1, extreme=True, gc=True, price=False), scope_ref='episode')
    assert not memory.trigger and memory.event == 'FIRST_GC_REJECTED_CONSUMED'
    memory = evaluate_temporal(memory, observation(2, extreme=True, gc=True), scope_ref='episode')
    assert not memory.trigger


def test_same_batch_current_episode_allowed_outside_extreme_not_carried():
    # Upstream publication has produced a current eligible ref in this batch.
    assert evaluate_temporal(None, observation(extreme=True, gc=True), scope_ref='new-active-this-batch').trigger
    outside = evaluate_temporal(None, observation(extreme=True), scope_ref=None)
    assert not evaluate_temporal(outside, observation(1, gc=True), scope_ref='new-active').trigger
    old = evaluate_temporal(None, observation(extreme=True), scope_ref='old-active')
    assert not evaluate_temporal(old, observation(1, gc=True), scope_ref='different-active').trigger


def test_new_episode_poll_resets_old_consumption_without_reusing_current_bar():
    consumed = evaluate_temporal(None, observation(extreme=True, gc=True), scope_ref='old-episode')
    changed = evaluate_temporal(consumed, consumed.observation, scope_ref='new-episode')
    assert not changed.trigger and not changed.locked and changed.arm_index is None
    assert evaluate_temporal(changed, observation(1, extreme=True, gc=True), scope_ref='new-episode').trigger


def test_unavailable_upstream_loss_cancels_no_same_identity_recovery():
    memory = evaluate_temporal(None, observation(extreme=True), scope_ref='episode')
    lost = evaluate_temporal(memory, observation(1, unavailable=True), scope_ref='episode')
    assert lost.event == 'UNAVAILABLE_CANCEL' and lost.arm_index is None
    assert not evaluate_temporal(lost, observation(1, extreme=True, gc=True), scope_ref='episode').trigger
    lost = evaluate_temporal(memory, observation(1, extreme=True, gc=True), scope_ref=None)
    assert not evaluate_temporal(lost, lost.observation, scope_ref='recovered').trigger
    assert not evaluate_temporal(lost, observation(2, gc=True), scope_ref='recovered').trigger


def test_clock_skip_origin_and_vintage_change_cancel():
    memory = evaluate_temporal(None, observation(extreme=True), scope_ref='episode')
    assert evaluate_temporal(memory, observation(2, gc=True), scope_ref='episode').event == 'UNAVAILABLE_CANCEL'
    for key, value in [('history_origin', memory.observation.end_at + timedelta(minutes=15)), ('source_vintage', 'changed')]:
        current = replace(observation(1, gc=True), **{key: value})
        assert evaluate_temporal(memory, current, scope_ref='episode').event == 'UNAVAILABLE_CANCEL'


def test_repeated_poll_and_correction_never_repeat_trigger():
    current = observation(extreme=True, gc=True)
    first = evaluate_temporal(None, current, scope_ref='episode')
    assert first.trigger
    repeated = evaluate_temporal(first, current, scope_ref='episode')
    assert not repeated.trigger and repeated.event == 'DUPLICATE_NO_EVENT'
    correction = replace(current, input_hash='different-research-vintage')
    assert evaluate_temporal(first, correction, scope_ref='episode').event == 'UNAVAILABLE_CANCEL'
    assert evaluate_temporal(None, current, scope_ref='episode') == first


def test_delayed_batch_old_cross_rejected_never_deferred():
    memory = evaluate_temporal(None, observation(extreme=True), scope_ref='episode')
    memory = evaluate_temporal(memory, observation(1, gc=True), scope_ref='episode', emit_eligible=False)
    assert not memory.trigger and memory.locked
    assert not evaluate_temporal(memory, observation(2, extreme=True, gc=True), scope_ref='episode').trigger


def test_future_inputs_and_nonmonotone_evaluation_rejected():
    current = observation()
    with pytest.raises(ValueError):
        replace(current, known_at=current.as_of+timedelta(seconds=1))
    memory = evaluate_temporal(None, observation(2), scope_ref='episode')
    with pytest.raises(ValueError):
        evaluate_temporal(memory, observation(1), scope_ref='episode')


def test_forged_future_memory_and_calendar_grid_skip_rejected():
    with pytest.raises(ValueError):
        M15Memory(observation(), 'episode', 5, observation(5).end_at, False, False, 'ARMED')
    memory = evaluate_temporal(None, observation(extreme=True), scope_ref='episode')
    skipped = replace(observation(2, gc=True), index=1)
    assert evaluate_temporal(memory, skipped, scope_ref='episode').event == 'UNAVAILABLE_CANCEL'


def test_network_disabled_immutable_fixture_store_reload(tmp_path):
    from scripts.h0001_15m_mechanical_check import offline_check
    from richping.research_v2.store import ResearchStore
    from test_research_v2_real_data import data
    dataset = data()  # mocked provider prices, no external API or market evidence
    path = tmp_path/'market.sqlite'
    with ResearchStore(path) as store:
        store.save_dataset(dataset)
    result = offline_check(path, dataset.dataset_id)
    assert result['network_disabled'] and result['network_calls'] == 0
    assert result['deterministic_repeated_exercise'] and result['read_only_store']
    assert result['content_hash'] == dataset.content_hash
    assert result['counts']['relative_UNAVAILABLE'] == 64
    assert result['counts']['ENTRY_CANDIDATE_count'] is None


def test_exact_nine_root_spec_delta_inventory_and_remaining_owners():
    before = H0001Specification.loads(subprocess.check_output(['git', 'show', '8f0611f:'+SPEC], cwd=ROOT).decode())
    # Historical v12 delta; v13 composition has a separate exact scope test.
    after = H0001Specification.loads(subprocess.check_output(['git', 'show', 'ffabeaf9:'+SPEC], cwd=ROOT).decode())
    removed = set(before.unresolved_fields) - set(after.unresolved_fields)
    assert removed == {f'{s}.{k}' for s,k in frozen_values()}
    assert len(removed) == 9 and len(after.unresolved_fields) == 80
    assert [len(after.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)] == [29, 17, 7]
    assert len(after.unpack()['decisions']) == 78
    old, new = before.unpack(), after.unpack()
    for s,k in frozen_values():
        new[s][k] = old[s][k]
    new['specification_version'], new['updated_at'] = old['specification_version'], old['updated_at']
    assert new == old
    assert 'H1-STATE-TRANSITIONS' in after.blockers(C1)
    with pytest.raises(ValueError):
        after.require_c1_ready()


@pytest.mark.parametrize('root', list(frozen_values()))
def test_frozen_roots_cannot_reopen(root):
    spec = H0001Specification.load(ROOT/SPEC).unpack()
    s,k = root
    spec[s][k]['value'] = 'UNRESOLVED'
    with pytest.raises(ValueError, match='Frozen 15m entry'):
        H0001Specification.of(spec)


@pytest.mark.parametrize('s,k,param,new_value', [
    ('feature_contracts','entry_15m_relative_conventions','include_current',False),
    ('feature_contracts','entry_15m_relative_conventions','min_history',191),
    ('rule_parameters','entry_15m_trigger_conjunction','K',5),
    ('rule_parameters','entry_15m_gc','current','macd_GE_signal'),
    ('state_machine_parameters','decision_timing','same_batch','NEXT_OBSERVATION')])
def test_nested_frozen_conventions_cannot_silently_change(s,k,param,new_value):
    spec = H0001Specification.load(ROOT/SPEC).unpack()
    spec[s][k]['value']['parameters'][param]['value'] = new_value
    with pytest.raises(ValueError, match='Frozen 15m entry'):
        H0001Specification.of(spec)


def test_immutable_freeze_record_matches_executable_and_offline_evidence():
    import json
    record = yaml.safe_load((ROOT/'research/decision_records/H0001-15m-entry-freeze-v1.yaml').read_text(encoding='utf-8'))
    prereg = yaml.safe_load((ROOT/record['preregistration']['path']).read_text(encoding='utf-8'))
    evidence = json.loads((ROOT/record['mechanical_evidence']['path']).read_text(encoding='utf-8'))
    spec = H0001Specification.loads(subprocess.check_output(['git', 'show', 'ffabeaf9:'+SPEC], cwd=ROOT).decode())
    assert spec.specification_hash == record['executable_spec']['canonical_sha256']
    assert record['selected_primary'] == prereg['primary']
    assert record['definition']['hash'] == evidence['counts']['contract_hash'] == contract_hash()
    normalized = (ROOT/record['preregistration']['path']).read_bytes().replace(b'\r\n',b'\n')
    assert sha256(normalized).hexdigest() == evidence['preregistration_sha256'] == record['preregistration']['normalized_sha256']
    assert len(record['resolved_decision_ids']) == 9
    assert record['remaining_unresolved_decision_ids'] == {c:list(spec.blockers(c)) for c in (C1,PERFORMANCE,OPTIONAL)}
    assert evidence['counts']['ENTRY_CANDIDATE_count'] is None and evidence['counts']['profitability'] == 'NOT_RUN'
    assert evidence['deterministic_repeated_exercise'] and evidence['network_calls'] == 0
    for name in ('MACD_READY','MACD_UNAVAILABLE','relative_READY','relative_UNAVAILABLE','extreme_count','GC_count','ungated_15m_trigger_count'):
        assert record['mechanical_evidence'][name] == evidence['counts'][name]
    assert record['comparator'] == prereg['comparator'] == 'NONE'
    assert record['remaining_prerequisite']['exhaustion_minimum_joint_count'] == 381


@pytest.mark.parametrize('path', ['research/hypotheses/H0001-r03.yaml',
    'research/decision_proposals/H0001-15m-entry-trigger-v1.yaml',
    'research/decision_records/H0001-daily-input-freeze-v1.yaml',
    'research/decision_records/H0001-daily-trend-freeze-v1.yaml',
    'research/decision_records/H0001-daily-trend-readiness-remediation-v1.yaml',
    'research/decision_records/H0001-daily-blocker-freeze-v1.yaml',
    'research/decision_records/H0001-1h-relative-setup-freeze-v1.yaml',
    'richping/research_v2/strategy/daily_trend.py', 'richping/research_v2/strategy/daily_exhaustion.py',
    'richping/research_v2/strategy/h1_setup.py'])
def test_upstream_source_and_records_unchanged(path):
    assert (ROOT/path).read_bytes().replace(b'\r\n', b'\n') == subprocess.check_output(['git','show','8f0611f:'+path],cwd=ROOT)
