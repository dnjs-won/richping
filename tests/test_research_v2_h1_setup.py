"""Ex-ante contract and synthetic causality/lifecycle tests; no market outcomes."""

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from pathlib import Path
import subprocess

import pytest
import yaml

from richping.core import sessions
from richping.research_v2.aggregation import CompletedAggregator
from richping.research_v2.contracts import StrategyState, ReplayContext, JsonObject, payload
from richping.research_v2.features import macd_series, rolling_percentile, ScalarSeries, ScalarPoint
from richping.research_v2.sessions import EXTENDED, EXTENDED_CONTINUITY as EC
from richping.research_v2.strategy.h1_setup import (
    CANONICAL, LIFETIME, PreparedH1Prefix, H1RelativeSetupRawState, H1SetupEpisode,
    SetupDailyPermission, classify_h1_relative_setup, downside_label,
    evaluate_h1_setup_lifetime, setup_trace,
)
from richping.research_v2.strategy.h0001_spec import H0001Specification, load_h0001
from richping.research_v2.strategy.specification import C1, PERFORMANCE, OPTIONAL
from test_research_v2_extended import bars

ROOT = Path(__file__).resolve().parents[1]
BASE = 'f7123b63d76501ac740f7c5369344f26325e26be'
DRAFT = 'research/strategy_specs/H0001-r03-draft.yaml'
RECORD = 'research/decision_records/H0001-1h-relative-setup-freeze-v1.yaml'


def record():
    return yaml.safe_load((ROOT / RECORD).read_text(encoding='utf-8'))


def basis():
    return H0001Specification.loads(subprocess.check_output(['git', 'show', BASE+':'+DRAFT], cwd=ROOT).decode())


def test_six_root_delta_only_with_Daily_payload_and_ownership_preserved():
    before, after = basis(), load_h0001(ROOT / DRAFT)
    old, new = before.unpack(), after.unpack()
    frozen = record()
    assert new['specification_version'] == 'h0001_r03_spec_v11'
    assert before.specification_hash == frozen['executable_spec']['canonical_sha256_before']
    assert after.specification_hash == frozen['executable_spec']['canonical_sha256']
    removed = set(before.unresolved_fields) - set(after.unresolved_fields)
    assert removed == set(frozen['inventory']['removed_roots'])
    assert len(removed) == 6 and not set(after.unresolved_fields) - set(before.unresolved_fields)
    assert [len(after.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)] == [38, 17, 7]
    assert len(after.unresolved_fields) == 89 and len(new['decisions']) == 78
    assert len(before.blockers(C1)) == 44
    assert set(frozen['decisions']) == {
        'H1-RELATIVE-METHOD', 'H1-LOOKBACK', 'H1-RELATIVE-CONVENTIONS',
        'H1-DOWNSIDE', 'H1-COMPARATOR', 'H1-SETUP-LIFETIME'}
    assert not set(frozen['decisions']) & set(after.blockers(C1))
    assert set(frozen['remaining_ownership']) <= set(after.blockers(C1))
    for section in ('execution_requirements', 'optional_extensions', 'chart_parity', 'state_machine', 'decisions'):
        assert old[section] == new[section]
    for path in removed:
        section, key = path.split('.')
        new[section][key] = old[section][key]
    new['specification_version'], new['updated_at'] = old['specification_version'], old['updated_at']
    assert new == old
    assert new['status'] == 'DRAFT' and frozen['profitability'] == 'NOT_TESTED'
    assert frozen['chart_parity'] == 'UNVERIFIED'
    for gate in (after.require_c1_ready, after.require_profitability_ready, after.plugin_specification):
        with pytest.raises(ValueError):
            gate()


@pytest.mark.parametrize('path', [
    'research/hypotheses/H0001-r03.yaml',
    'research/decision_proposals/H0001-1h-relative-setup-v1.yaml',
    'research/decision_records/H0001-daily-input-freeze-v1.yaml',
    'research/decision_records/H0001-daily-trend-freeze-v1.yaml',
    'research/decision_records/H0001-daily-trend-readiness-remediation-v1.yaml',
    'research/decision_records/H0001-daily-blocker-freeze-v1.yaml',
    'richping/research_v2/strategy/daily_trend.py',
    'richping/research_v2/strategy/daily_exhaustion.py',
    'richping/cli.py', 'richping/paper.py', 'richping/pipeline.py',
])
def test_immutable_sources_and_production_paper_modules(path):
    original = subprocess.check_output(['git', 'show', BASE+':'+path], cwd=ROOT)
    if path == 'richping/cli.py':
        # Preserve the freeze's historical evidence; later ingestion CLI is
        # covered separately and does not connect this strategy to orders.
        assert subprocess.check_output(['git', 'show', '7197fe3:'+path], cwd=ROOT) == original
        return
    assert (ROOT / path).read_bytes().replace(b'\r\n', b'\n') == original


@pytest.mark.parametrize('section,key,value', [
    ('rule_parameters', 'setup_1h_relative_transform', 'ROLLING_ZSCORE'),
    ('rule_parameters', 'setup_1h_rolling_lookback', 319),
    ('rule_parameters', 'setup_1h_downside_threshold', .10),
    ('rule_parameters', 'setup_1h_downside_comparator', 'LT'),
    ('feature_contracts', 'setup_1h_relative_conventions', 'UNRESOLVED'),
    ('state_machine_parameters', 'setup_persistence_expiry', 'UNRESOLVED'),
])
def test_v11_freeze_cannot_reopen_or_change_six_roots(section, key, value):
    body = load_h0001(ROOT / DRAFT).unpack()
    body[section][key]['value'] = value
    with pytest.raises(ValueError, match='Frozen 1H setup'):
        H0001Specification.of(body)


@pytest.mark.parametrize('root,key,value', [
    ('relative', 'field', 'histogram'), ('relative', 'min_history', 319),
    ('relative', 'include_current', False), ('relative', 'ties', 'minimum'),
    ('relative', 'macd_line_lt_zero', False), ('lifetime', 'K', 3),
    ('lifetime', 'UNAVAILABLE', 'KEEP_ACTIVE'), ('lifetime', 'blocked_trigger_queue', 'ENABLED'),
])
def test_nested_freeze_mutations_require_revision(root, key, value):
    body = load_h0001(ROOT / DRAFT).unpack()
    section, field = (('feature_contracts', 'setup_1h_relative_conventions') if root == 'relative'
                      else ('state_machine_parameters', 'setup_persistence_expiry'))
    body[section][field]['value']['parameters'][key]['value'] = value
    with pytest.raises(ValueError, match='Frozen 1H setup'):
        H0001Specification.of(body)


def test_frozen_parameters_and_semantic_family_not_performance():
    spec = CANONICAL
    assert (spec.macd_spec.fast, spec.macd_spec.slow, spec.macd_spec.signal, spec.macd_spec.min_history) == (12, 26, 9, 130)
    assert spec.macd_spec.seed == 'first_observation' and spec.macd_spec.signal_start == 'first_macd_observation'
    assert (spec.percentile_spec.window, spec.percentile_spec.min_history) == (320, 320)
    assert spec.percentile_spec.include_current and spec.percentile_spec.ties == 'midrank'
    assert spec.percentile_spec.continuity == EC and spec.first_ready_count == 449
    assert spec.semantics['field'] == 'MACD_LINE'
    frozen = record()
    family = frozen['initial_family']
    assert family['members'] == {'S0': 'NO_1H_DOWNSIDE_SETUP_FILTER', 'S1': 'FROZEN_PERCENTILE_SETUP'}
    assert family['comparison_candidate'] == 'S0' and family['primary_comparisons'] == 1
    assert family['R2'] == family['R3'] == 'DEFERRED_SEPARATE_RESEARCH_VARIANT'
    assert family['parameter_grid'] == 'FORBIDDEN'
    assert frozen['performance_information_used'] == 'NONE'
    assert frozen['outcome_lookup'] == frozen['performance_backtest'] == frozen['current_SOXX_NOK_analysis'] == 'NOT_RUN'
    assert frozen['production_paper_order_connection'] == 'NONE'
    assert frozen['prior_only_engine'] == 'NOT_IMPLEMENTED_NOT_USED'
    assert not frozen['implementation']['new_indicator_engine']


@pytest.fixture(scope='module')
def hour_prefix():
    agg, output, n = CompletedAggregator(('1H',), profile=EXTENDED), [], 0
    for day in sessions('2024-03-11', '2024-04-23'):
        for original in bars(day):
            # Accelerating synthetic decline keeps the spread distinct from a
            # steady-slope plateau; this is a hand fixture, not parameter fitting.
            price = 500 - n * .02 - n * n * .00005
            b = replace(original, open=price, close=price, high=price+1, low=price-1)
            output.extend(x for x in agg.accept(b, b.known_at) if x.timeframe == '1H')
            n += 1
    assert len(output) >= 460
    selected = tuple(output[:460])
    return PreparedH1Prefix('ALFA', selected, selected[-1].known_at,
                            selected[-1].end_at, 'synthetic-v1', selected[-1].known_at)


def prefix_count(prefix, N):
    items = prefix.bars[:N]
    return replace(prefix, bars=items, eligibility_as_of=items[-1].known_at,
                   expected_completed_end=items[-1].end_at, evidence_known_at=items[-1].known_at)


@pytest.mark.parametrize('N,ready_count,status', [(129, 0, 'UNAVAILABLE'), (130, 1, 'UNAVAILABLE'),
    (448, 319, 'UNAVAILABLE'), (449, 320, 'READY')])
def test_actual_extended_1H_readiness_and_current_inclusive_midrank(hour_prefix, N, ready_count, status):
    prepared = prefix_count(hour_prefix, N)
    raw = classify_h1_relative_setup(prepared, prepared.eligibility_as_of)
    series = macd_series(ReplayContext(raw.as_of, prepared.bars), 'ALFA', '1H', CANONICAL.macd_spec, field='macd_line')
    assert all(point.status == 'NOT_READY' for point in series.points[:129])
    if N >= 130:
        assert series.points[129].status == 'READY'
    reference = series.points[-320:]
    assert sum(point.status == 'READY' for point in reference) == ready_count == raw.ready_reference_count
    assert raw.status == status
    if N == 448:
        assert reference[0] is series.points[128] and raw.state == 'UNAVAILABLE'
        assert raw.reason == 'percentile:unavailable_input'
    if N == 449:
        assert reference[0] is series.points[129]
        xs = [p.value for p in reference]
        rank = (sum(x < xs[-1] for x in xs) + .5*sum(x == xs[-1] for x in xs))/320
        assert raw.percentile == rank == rolling_percentile(series, CANONICAL.percentile_spec).values.unpack()['percentile']
        assert raw.macd_line < 0 and raw.state == 'DOWNSIDE_EXTREME'


@pytest.mark.parametrize('line,rank,expected', [
    (-1,.050001,'INACTIVE'), (-1,.05,'DOWNSIDE_EXTREME'), (-1,.049999,'DOWNSIDE_EXTREME'),
    (0,.01,'INACTIVE'), (1,.01,'INACTIVE'), (-1,.5,'INACTIVE'),
])
def test_inclusive_rank_and_strict_negative_polarity(line, rank, expected):
    # Exact .05 can occur with ties; LE and strict sign are independently explicit.
    assert downside_label(line, rank) == expected
    assert expected not in {'BUY', 'PRICE_BOTTOM', 'BEARISH'}


@pytest.mark.parametrize('line,rank', [(float('inf'), .01), (-1, float('nan')), (True,.01), (-1,1.1)])
def test_nonfinite_unready_values_are_not_measured_INACTIVE(line, rank):
    with pytest.raises(ValueError):
        downside_label(line, rank)


def test_actual_midrank_ties_can_equal_P05_at_W320(hour_prefix):
    p = prefix_count(hour_prefix,449)
    source = macd_series(ReplayContext(p.eligibility_as_of,p.bars), 'ALFA', '1H', CANONICAL.macd_spec,field='macd_line')
    slots = source.points[-320:]
    # Fifteen less, two equal (including current): (15 + .5*2)/320=.05.
    values = [-10]*15 + [-1]*303 + [-5,-5]
    points = tuple(ScalarPoint(slot.end_at,slot.known_at,value,'READY',None) for slot,value in zip(slots,values))
    series = ScalarSeries('ALFA','1H',p.eligibility_as_of,source.source,points,'assigned_ties_fixture')
    rank = rolling_percentile(series,CANONICAL.percentile_spec).values.unpack()['percentile']
    assert rank == .05 and downside_label(-5,rank) == 'DOWNSIDE_EXTREME'


@pytest.mark.parametrize('fault', ['future_bar', 'future_evidence', 'missing_evidence', 'missing_latest',
                                  'gap', 'incomplete', 'unsupported_action', 'unordered', 'reversed', 'wrong_symbol'])
def test_input_failures_are_UNAVAILABLE(hour_prefix, fault):
    p = prefix_count(hour_prefix, 449)
    if fault == 'future_bar':
        p = replace(p, eligibility_as_of=p.eligibility_as_of-timedelta(seconds=1))
    elif fault == 'future_evidence':
        p = replace(p, evidence_known_at=p.eligibility_as_of+timedelta(seconds=1))
    elif fault == 'missing_evidence':
        p = replace(p, evidence_known_at=None)
    elif fault == 'missing_latest':
        p = replace(p, bars=p.bars[:-1])
    elif fault == 'gap':
        p = replace(p, bars=p.bars[:200]+p.bars[201:])
    elif fault == 'incomplete':
        last = p.bars[-1]
        p = replace(p, bars=p.bars[:-1]+(replace(last, start_at=last.start_at+timedelta(minutes=15)),))
    elif fault == 'unsupported_action':
        p = replace(p, bars=p.bars[:-1]+(replace(p.bars[-1], corporate_action='UNKNOWN'),))
    elif fault == 'unordered':
        p = replace(p, bars=(p.bars[1], p.bars[0])+p.bars[2:])
    elif fault == 'reversed':
        p = replace(p,bars=tuple(reversed(p.bars)))
    else:
        p = replace(p,bars=p.bars[:-1]+(replace(p.bars[-1],symbol='BETA'),))
    raw = classify_h1_relative_setup(p, p.eligibility_as_of)
    assert raw.state == raw.status == 'UNAVAILABLE' and raw.reason
    assert raw.macd_line is None and raw.percentile is None


def assigned_raw(prefix, index=448, state='DOWNSIDE_EXTREME', delay=0):
    """Symbolic READY operands for lifecycle unit tests; not calculated evidence."""
    bar = prefix.bars[index]
    instant = bar.known_at+timedelta(minutes=delay)
    ready = state != 'UNAVAILABLE'
    return H1RelativeSetupRawState('ALFA', instant, bar.end_at, instant, prefix.bars[0].end_at,
        index, state, 'READY' if ready else 'UNAVAILABLE', None if ready else 'fixture_unavailable',
        'synthetic:'+str(index), 'synthetic-v1', 'synthetic_unadjusted', CANONICAL.version, CANONICAL.hash,
        index+1, 320, -1 if ready else None, (.01 if state == 'DOWNSIDE_EXTREME' else .5) if ready else None)


def permission(raw, trend='BULLISH', exhaustion='NORMAL'):
    return SetupDailyPermission(raw.symbol, raw.as_of, raw.as_of, trend, exhaustion, 'trend-v9', 'blocker-v10')


def step(prefix, previous=None, index=448, state='DOWNSIDE_EXTREME', trend='BULLISH', exhaustion='NORMAL', delay=0):
    raw = assigned_raw(prefix, index, state, delay)
    return evaluate_h1_setup_lifetime(previous, raw, permission(raw, trend, exhaustion))


def test_activation_refresh_grace_expiry_and_new_episode(hour_prefix):
    first = step(hour_prefix)
    assert first.status == 'ACTIVE' and first.event == 'ACTIVATED' and first.age_since_last_extreme == 0
    refreshed = step(hour_prefix, first, 449)
    assert refreshed.activation_at == first.activation_at and refreshed.episode_id == first.episode_id
    assert refreshed.event == 'EXTREME_REFRESH' and refreshed.last_extreme_at > first.last_extreme_at
    one = step(hour_prefix, refreshed, 450, 'INACTIVE')
    two = step(hour_prefix, one, 451, 'INACTIVE')
    expired = step(hour_prefix, two, 452, 'INACTIVE')
    assert (one.status,one.age_since_last_extreme) == ('ACTIVE',1)
    assert (two.status,two.age_since_last_extreme) == ('ACTIVE',2)
    assert expired.status == 'EXPIRED' and expired.age_since_last_extreme == 3 and expired.expiry_at == expired.as_of
    assert expired.reason == 'EXPIRE_GRACE'
    assert step(hour_prefix, expired, 452, 'INACTIVE', delay=15).status == 'EXPIRED'
    new = step(hour_prefix, expired, 453)
    assert new.status == 'ACTIVE' and new.episode_id != first.episode_id


@pytest.mark.parametrize('age', [1, 2])
def test_extreme_during_grace_resets_clock(hour_prefix, age):
    episode = step(hour_prefix)
    for offset in range(1, age+1):
        episode = step(hour_prefix, episode, 448+offset, 'INACTIVE')
    refreshed = step(hour_prefix, episode, 449+age)
    assert refreshed.status == 'ACTIVE' and refreshed.age_since_last_extreme == 0
    assert refreshed.event == 'EXTREME_REFRESH'


@pytest.mark.parametrize('state,trend,exhaustion,reason', [
    ('UNAVAILABLE','BULLISH','NORMAL','SETUP_CANCELLED_1H_UNAVAILABLE'),
    ('DOWNSIDE_EXTREME','NOT_BULLISH','NORMAL','SETUP_CANCELLED_DAILY_PERMISSION'),
    ('DOWNSIDE_EXTREME','UNAVAILABLE','NORMAL','SETUP_CANCELLED_DAILY_PERMISSION'),
    ('DOWNSIDE_EXTREME','BULLISH','EXTENDED','SETUP_CANCELLED_DAILY_EXHAUSTION'),
    ('DOWNSIDE_EXTREME','BULLISH','UNAVAILABLE','SETUP_CANCELLED_DAILY_EXHAUSTION'),
])
def test_cancellation_is_immediate_and_restoration_alone_cannot_reactivate(hour_prefix, state, trend, exhaustion, reason):
    active = step(hour_prefix)
    cancelled = step(hour_prefix, active, 449, state, trend, exhaustion)
    assert cancelled.status == 'CANCELLED' and cancelled.cancellation_reason == reason
    assert cancelled.cancellation_at == cancelled.as_of
    restored = step(hour_prefix, cancelled, 449, 'DOWNSIDE_EXTREME', delay=15)
    assert restored.status == 'CANCELLED' and restored.event == 'UNCHANGED'
    assert restored.cancellation_at == cancelled.cancellation_at
    inactive = step(hour_prefix, restored, 450, 'INACTIVE')
    assert inactive.status == 'CANCELLED'
    new = step(hour_prefix, inactive, 451)
    assert new.status == 'ACTIVE' and new.episode_id != active.episode_id


@pytest.mark.parametrize('trend,exhaustion', [('NOT_BULLISH','NORMAL'), ('UNAVAILABLE','NORMAL'),
                                             ('BULLISH','EXTENDED'), ('BULLISH','UNAVAILABLE')])
def test_first_blocked_extreme_is_not_queued(hour_prefix, trend, exhaustion):
    blocked = step(hour_prefix, trend=trend, exhaustion=exhaustion)
    assert blocked.status == 'INACTIVE'
    assert step(hour_prefix, blocked, delay=15).status == 'INACTIVE'
    assert step(hour_prefix, blocked, 449).status == 'ACTIVE'


def test_same_observation_is_idempotent_and_intrahour_Daily_loss_cancels(hour_prefix):
    first = step(hour_prefix)
    later = step(hour_prefix, first, delay=15)
    assert later.event == 'UNCHANGED' and later.last_extreme_at == first.last_extreme_at
    assert later.age_since_last_extreme == 0
    cancelled = step(hour_prefix, later, delay=30, exhaustion='EXTENDED')
    assert cancelled.status == 'CANCELLED'
    assert step(hour_prefix, cancelled, delay=45).status == 'CANCELLED'


def test_observation_grace_carries_overnight_without_wall_time_steps(hour_prefix):
    last_hour = step(hour_prefix,index=447)
    next_session = step(hour_prefix,last_hour,448,'INACTIVE')
    assert next_session.as_of-last_hour.as_of > timedelta(hours=2)
    assert next_session.status == 'ACTIVE' and next_session.age_since_last_extreme == 1


def test_skipped_identity_origin_change_and_backward_input_do_not_infer_refresh(hour_prefix):
    first = step(hour_prefix)
    assert step(hour_prefix, first, 450).status == 'CANCELLED'
    raw = assigned_raw(hour_prefix, 449)
    changed = replace(raw, history_origin=hour_prefix.bars[1].end_at)
    assert evaluate_h1_setup_lifetime(first, changed, permission(changed)).status == 'CANCELLED'
    with pytest.raises(ValueError):
        step(hour_prefix, step(hour_prefix, first, 449), 448)


def test_activation_known_at_trace_and_portable_immutable_transport(hour_prefix):
    raw = assigned_raw(hour_prefix, delay=20)
    episode = evaluate_h1_setup_lifetime(None, raw, permission(raw))
    assert episode.activation_at == raw.as_of == raw.source_1h_known_at
    assert episode.activation_at > raw.source_1h_end
    state = StrategyState.loads(episode.transport.dumps())
    assert H1SetupEpisode.from_transport(state) == episode
    trace = setup_trace(raw, episode).unpack()
    assert set(record()['trace']['fields']) <= set(trace)
    assert trace['downstream_trigger_ref'] is None
    assert trace['Daily_refs']['trend_ref_hash'] == 'trend-v9'
    assert trace['setup_contract_hash'] == LIFETIME.hash
    with pytest.raises(FrozenInstanceError):
        episode.status = 'EXPIRED'
    assert not hasattr(episode, 'intents') and not hasattr(raw, 'fills')


def test_incomplete_bucket_and_equal_known_at_publication_boundary(hour_prefix):
    p = prefix_count(hour_prefix, 448)
    # Delay one constituent of the next completed hour; no derived hour until all arrive.
    target = hour_prefix.bars[448]
    original = bars(target.session)
    constituent = [b for b in original if target.start_at <= b.start_at < target.end_at]
    arrival = target.end_at+timedelta(minutes=7)
    agg = CompletedAggregator(('1H',), profile=EXTENDED)
    visible = []
    for b in constituent[:3]:
        visible.extend(x for x in agg.accept(b, b.known_at) if x.timeframe == '1H')
    assert not visible
    missing = replace(p, eligibility_as_of=target.end_at, expected_completed_end=target.end_at,
                      evidence_known_at=target.end_at)
    assert classify_h1_relative_setup(missing, missing.eligibility_as_of).state == 'UNAVAILABLE'
    final = replace(constituent[-1], known_at=arrival)
    outputs = agg.accept(final, arrival)
    hour = next(x for x in outputs if x.timeframe == '1H')
    assert hour.known_at == arrival and hour.provenance.unpack()['input_count'] == 4
    delivered = replace(p, bars=p.bars+(hour,), eligibility_as_of=arrival,
                        expected_completed_end=hour.end_at, evidence_known_at=arrival)
    raw = classify_h1_relative_setup(delivered, arrival)
    assert raw.status == 'READY' and raw.source_1h_known_at == arrival
    before = replace(delivered, eligibility_as_of=arrival-timedelta(microseconds=1))
    assert classify_h1_relative_setup(before, before.eligibility_as_of).state == 'UNAVAILABLE'


def test_future_Daily_reference_alignment_and_no_raw_Daily_dependency(hour_prefix):
    raw = assigned_raw(hour_prefix)
    with pytest.raises(ValueError):
        replace(permission(raw), known_at=raw.as_of+timedelta(seconds=1))
    with pytest.raises(ValueError):
        evaluate_h1_setup_lifetime(None, raw, replace(permission(raw), as_of=raw.as_of+timedelta(seconds=1)))
    p = prefix_count(hour_prefix,449)
    before = classify_h1_relative_setup(p,p.eligibility_as_of)
    evaluate_h1_setup_lifetime(None,before,permission(before,exhaustion='EXTENDED'))
    assert classify_h1_relative_setup(p,p.eligibility_as_of) == before


def test_intrahour_completed_prefix_hash_is_stable_and_next_in_progress_value_forbidden(hour_prefix):
    p = prefix_count(hour_prefix,449)
    first = classify_h1_relative_setup(p,p.eligibility_as_of)
    instant = p.eligibility_as_of+timedelta(minutes=37)
    later = classify_h1_relative_setup(replace(p,eligibility_as_of=instant),instant)
    assert later.status == 'READY' and later.source_1h_end == first.source_1h_end
    assert later.hash == first.hash and later.input_hash == first.input_hash
    future = replace(p,bars=p.bars+(hour_prefix.bars[449],),eligibility_as_of=instant)
    assert classify_h1_relative_setup(future,instant).state == 'UNAVAILABLE'


@pytest.mark.parametrize('fault', ['empty', 'unavailable_evidence', 'missing_expected'])
def test_no_input_and_eligibility_failures_remain_unavailable(hour_prefix,fault):
    p = prefix_count(hour_prefix,449)
    if fault == 'empty':
        p = replace(p,bars=())
    elif fault == 'missing_expected':
        p = replace(p,expected_completed_end=None)
    else:
        p = replace(p,input_status='UNAVAILABLE',input_reason='required_input_evidence_unavailable')
    raw = classify_h1_relative_setup(p,p.eligibility_as_of)
    assert raw.state == 'UNAVAILABLE' and raw.reason


def test_unavailable_nonfinite_operand_is_not_INACTIVE(hour_prefix,monkeypatch):
    import richping.research_v2.strategy.h1_setup as module
    p = prefix_count(hour_prefix,449)
    original = classify_h1_relative_setup(p,p.eligibility_as_of).macd_feature
    monkeypatch.setattr(module,'macd',lambda *args: replace(original,status='UNDEFINED',reason='nonfinite_result',values=JsonObject()))
    raw = classify_h1_relative_setup(p,p.eligibility_as_of)
    assert raw.state == 'UNAVAILABLE' and raw.reason == 'macd:nonfinite_result'


def test_v11_c1_admission_preserves_setup_while_future_fixture_resolves_other_owners():
    # This is fake admission, not actual resolution of remaining strategy choices.
    from test_research_v2_specification import resolve_fixture, feature_contract
    from richping.research_v2.strategy.capabilities import current_engine
    from richping.research_v2.strategy.h0001_spec import ENGINE_BOUNDARIES
    from richping.research_v2.features import PercentileSpec, FractalSpec
    current = load_h0001(ROOT / DRAFT).unpack()
    fake = resolve_fixture(basis(), {C1})
    fake['specification_version'] = current['specification_version']
    for path in record()['inventory']['removed_roots']:
        section,key = path.split('.')
        fake[section][key] = current[section][key]
    for key,value in current_engine(EXTENDED).items():
        fake['engine_capabilities'][key]['value'] = value
    fake['timeframe_contracts']['session_policy']['value'] = 'RTH_EXTENDED'
    fake['chart_parity']['engine_1h_boundary']['value'] = ENGINE_BOUNDARIES[EXTENDED]
    for prefix in ('entry_15m','exit_1h'):
        fake['feature_contracts'][prefix+'_relative_conventions']['value'] = feature_contract(PercentileSpec(1,1,continuity=EC),field='macd_line')
    fake['rule_parameters']['swing_parameters']['value'] = feature_contract(FractalSpec(1,1,continuity=EC))
    fake['status'] = 'FROZEN'
    H0001Specification.of(fake).require_c1_ready()
