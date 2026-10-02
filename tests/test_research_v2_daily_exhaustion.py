"""Synthetic causal contract fixtures only; no market data or outcome lookup."""

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
import inspect
from pathlib import Path
import subprocess

import pytest
import yaml

from richping.core import digest
from richping.research_v2.contracts import JsonObject, ReplayContext, StrategyState, payload
from richping.research_v2.features.macd import macd, macd_series
from richping.research_v2.features.relative import rolling_percentile
from richping.research_v2.strategy.daily_exhaustion import (
    CANONICAL, POLICY, blocker_contract, classify_daily_exhaustion,
    evaluate_exhaustion_policy, exhaustion_label,
)
from richping.research_v2.strategy.daily_trend import CANONICAL as TREND
from richping.research_v2.strategy.h0001_spec import H0001Specification, load_h0001
from richping.research_v2.strategy.specification import C1, PERFORMANCE, OPTIONAL
from test_research_v2_daily_trend import prepared, classify as trend

ROOT = Path(__file__).resolve().parents[1]
BASE = 'a25b43a59498cb3a149048dc8f206d7322cac93b'
DRAFT = 'research/strategy_specs/H0001-r03-draft.yaml'
RECORD = 'research/decision_records/H0001-daily-blocker-freeze-v1.yaml'


def frozen_record():
    return yaml.safe_load((ROOT / RECORD).read_text(encoding='utf-8'))


def classify(prefix):
    return classify_daily_exhaustion(prefix, prefix.eligibility_as_of)


@pytest.fixture(scope='module')
def prefix():
    return prepared(list(range(100, 481)))


def test_canonical_spec_resolves_exactly_the_blocker_root_and_preserves_v9():
    before = H0001Specification.loads(subprocess.check_output(
        ['git', 'show', BASE+':'+DRAFT], cwd=ROOT).decode('utf-8'))
    # Immutable v10 freeze snapshot; the later six-root v11 delta is tested separately.
    after = H0001Specification.loads(subprocess.check_output([
        'git', 'show', 'f7123b63d76501ac740f7c5369344f26325e26be:'+DRAFT], cwd=ROOT).decode())
    old, new = before.unpack(), after.unpack()
    assert old['specification_version'] == 'h0001_r03_spec_v9'
    assert before.specification_hash == frozen_record()['executable_spec']['canonical_sha256_before']
    assert new['specification_version'] == 'h0001_r03_spec_v10'
    assert after.specification_hash == frozen_record()['executable_spec']['canonical_sha256']
    assert new['rule_parameters']['daily_exhaustion_blocker']['value'] == blocker_contract()
    assert new['rule_parameters']['daily_long_permission']['value'] == TREND.contract
    assert old['rule_parameters']['daily_long_permission'] == new['rule_parameters']['daily_long_permission']
    assert len(new['decisions']) == 78 and old['decisions'] == new['decisions']
    assert (len(before.unresolved_fields), len(after.unresolved_fields)) == (96, 95)
    assert set(before.unresolved_fields) - set(after.unresolved_fields) == {'rule_parameters.daily_exhaustion_blocker'}
    assert not set(after.unresolved_fields) - set(before.unresolved_fields)
    assert [len(after.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)] == [44, 17, 7]
    assert sum(len(after.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)) == 68
    assert not {'H1-DAILY-BLOCKER', 'H1-DAILY-LONG'} & set(after.blockers(C1))
    assert new['status'] == 'DRAFT'
    assert new['chart_parity']['parity_status']['value'] == 'UNVERIFIED'
    for gate in (after.require_c1_ready, after.require_profitability_ready, after.plugin_specification):
        with pytest.raises(ValueError):
            gate()
    old['specification_version'] = new['specification_version']
    old['updated_at'] = new['updated_at']
    old['rule_parameters']['daily_exhaustion_blocker'] = new['rule_parameters']['daily_exhaustion_blocker']
    assert old == new  # no other strategy, input, timing or execution contract changed


@pytest.mark.parametrize('section,parameter,value', [
    ('state_definition', 'field', 'HISTOGRAM'), ('state_definition', 'window', 100),
    ('state_definition', 'min_history', 200), ('state_definition', 'upper_percentile', .90),
    ('state_definition', 'convention', 'PRIOR_ONLY'), ('state_definition', 'macd_line_gt_zero', False),
    ('state_definition', 'comparator', 'GREATER_THAN'), ('policy', 'UNAVAILABLE', 'ALLOW'),
    ('policy', 'existing_position', 'SELL_EXISTING_POSITION'),
    ('policy', 'blocked_signal_queue', 'ENABLED'), ('policy', 'reentry_is_new_exposure', False),
])
def test_frozen_contract_changes_require_new_revision(section, parameter, value):
    body = load_h0001(ROOT / DRAFT).unpack()
    params = body['rule_parameters']['daily_exhaustion_blocker']['value']['parameters']
    params[section]['value']['parameters'][parameter]['value'] = value
    with pytest.raises(ValueError, match='Frozen Daily blocker'):
        H0001Specification.of(body)


@pytest.mark.parametrize('root', ['daily_exhaustion_blocker', 'daily_long_permission'])
def test_v10_cannot_reopen_frozen_daily_root(root):
    body = load_h0001(ROOT / DRAFT).unpack()
    body['rule_parameters'][root]['value'] = 'UNRESOLVED'
    with pytest.raises(ValueError, match='Frozen Daily'):
        H0001Specification.of(body)


def test_macd_field_and_full_current_inclusive_percentile_contract():
    spec = CANONICAL
    assert (spec.macd_spec.fast, spec.macd_spec.slow, spec.macd_spec.signal, spec.macd_spec.min_history) == (12, 26, 9, 130)
    assert (spec.macd_spec.seed, spec.macd_spec.signal_start, spec.macd_spec.field) == (
        'first_observation', 'first_macd_observation', 'close')
    assert spec.percentile_spec.version == 'rolling_empirical_midrank_v1'
    assert (spec.percentile_spec.window, spec.percentile_spec.min_history) == (252, 252)
    assert spec.percentile_spec.include_current and spec.percentile_spec.ties == 'midrank'
    assert spec.semantics['field'] == 'MACD_LINE'
    assert spec.first_ready_count == spec.macd_spec.min_history + spec.percentile_spec.window - 1 == 381
    assert TREND.ema_spec.span == 50 and TREND.ema_spec.min_history == 174
    assert frozen_record()['profitability'] == 'NOT_TESTED'


@pytest.mark.parametrize('count,ready_count,status', [(129, 0, 'UNAVAILABLE'),
    (130, 1, 'UNAVAILABLE'), (252, 123, 'UNAVAILABLE'),
    (380, 251, 'UNAVAILABLE'), (381, 252, 'READY')])
def test_actual_macd_series_indexing_and_composed_readiness(count, ready_count, status, prefix):
    bars = prefix.bars[:count]
    p = replace(prefix, bars=bars, eligibility_as_of=bars[-1].known_at,
                expected_session=bars[-1].session, transform_known_at=bars[-1].known_at)
    context = ReplayContext(p.eligibility_as_of, bars)
    series = macd_series(context, p.symbol, 'Daily', CANONICAL.macd_spec, field='macd_line')
    assert len(series.points) == count
    assert all(pt.status == 'NOT_READY' and pt.value is None for pt in series.points[:129])
    if count >= 130:
        assert series.points[129].status == 'READY'  # one-based observation 130
        assert all(pt.status == 'READY' for pt in series.points[129:])
    selected = series.points[-252:]
    assert sum(pt.status == 'READY' for pt in selected) == ready_count
    rank = rolling_percentile(series, CANONICAL.percentile_spec)
    state = classify(p)
    assert state.status == status
    assert (rank.status == 'READY') == (count >= CANONICAL.first_ready_count)
    if count == 380:
        assert len(selected) == 252 and selected[0] is series.points[128]
        assert rank.reason == 'unavailable_input'
        assert state.ready_reference_count == 251 and state.state == 'UNAVAILABLE'
    if status == 'READY':
        assert selected[0] is series.points[129]
        assert state.ready_reference_count == 252
        assert state.macd_line == macd(context, p.symbol, 'Daily', CANONICAL.macd_spec).values.unpack()['macd_line']
        xs = [pt.value for pt in selected]
        expected = (sum(x < xs[-1] for x in xs) + .5 * sum(x == xs[-1] for x in xs)) / 252
        assert state.percentile == expected == rank.values.unpack()['percentile']
        assert state.percentile == pytest.approx(1 - 1/(2*252))  # unique maximum includes self
    else:
        assert state.state == 'UNAVAILABLE' and state.macd_line is None and state.percentile is None


@pytest.mark.parametrize('line,rank,label', [(1,.949999,'NORMAL'), (1,.95,'EXTENDED'),
    (1,.950001,'EXTENDED'), (0,.99,'NORMAL'), (-1,.99,'NORMAL'), (-1,.95,'NORMAL')])
def test_threshold_equality_and_strict_positive_polarity(line, rank, label):
    # With 252 midrank observations exact .95 is not attainable (rank steps
    # are half/252). The frozen comparison still explicitly admits equality.
    assert exhaustion_label(line, rank) == label


@pytest.mark.parametrize('line,rank', [(float('inf'), .95), (1, float('nan')),
    (1, 1.01), (1, -.01), (True, .95)])
def test_nonfinite_or_invalid_operands_cannot_be_normal(line, rank):
    with pytest.raises(ValueError):
        exhaustion_label(line, rank)


@pytest.mark.parametrize('prices,label', [([100]*381, 'NORMAL'),
    (list(range(100,481)), 'EXTENDED'), (list(range(600,219,-1)), 'NORMAL')])
def test_real_feature_composition_produces_raw_state(prices, label):
    state = classify(prepared(prices))
    assert state.status == 'READY' and state.state == label
    assert state.macd_feature.status == state.percentile_feature.status == 'READY'
    assert state.state_version == CANONICAL.version and state.state_definition_hash == CANONICAL.hash
    assert state.hash == classify(prepared(prices)).hash
    with pytest.raises(FrozenInstanceError):
        state.state = 'NORMAL'


@pytest.mark.parametrize('failure', ['stale', 'no_expected', 'no_bars', 'action_unknown',
    'future_action', 'future_effective', 'future_bar', 'wrong_basis', 'wrong_profile',
    'input_unavailable', 'gap', 'duplicate', 'unsupported_action', 'as_of_mismatch'])
def test_input_and_causal_failures_are_unavailable_with_reasons(prefix, failure):
    changes = {
        'stale': {'expected_session': '2024-09-09'}, 'no_expected': {'expected_session': None},
        'no_bars': {'bars': ()}, 'action_unknown': {'transform_known_at': None},
        'future_action': {'transform_known_at': prefix.eligibility_as_of+timedelta(seconds=1)},
        'future_effective': {'transform_effective_at': (prefix.eligibility_as_of+timedelta(seconds=1),)},
        'future_bar': {'bars': (*prefix.bars[:-1], replace(prefix.bars[-1], known_at=prefix.eligibility_as_of+timedelta(seconds=1)))},
        'wrong_basis': {'price_basis': 'raw'}, 'wrong_profile': {'session_profile': 'US_EQUITY_EXTENDED_04_20'},
        'input_unavailable': {'input_status': 'UNAVAILABLE', 'input_reason': 'PIT_action_coverage_missing'},
        'gap': {'bars': prefix.bars[:10]+prefix.bars[11:]},
        'duplicate': {'bars': prefix.bars[:10]+prefix.bars[9:]},
        'unsupported_action': {'bars': (replace(prefix.bars[0], corporate_action='UNKNOWN'), *prefix.bars[1:])},
        'as_of_mismatch': {'eligibility_as_of': prefix.eligibility_as_of+timedelta(seconds=1)},
    }[failure]
    state = classify_daily_exhaustion(replace(prefix, **changes), prefix.eligibility_as_of)
    assert state.state == state.status == 'UNAVAILABLE' and state.reason
    assert state.macd_line is None and state.percentile is None
    if failure in {'action_unknown', 'future_action', 'future_effective', 'future_bar'}:
        assert state.known_at is None and state.input_end_at is None and state.input_count == 0


@pytest.mark.parametrize('operand', ['macd', 'rolling_percentile'])
def test_nonfinite_calculation_maps_to_unavailable(prefix, monkeypatch, operand):
    import richping.research_v2.strategy.daily_exhaustion as module
    original = getattr(module, operand)
    def unavailable(*args, **kwargs):
        feature = original(*args, **kwargs)
        return replace(feature, values=JsonObject.of({}), status='UNDEFINED', reason='nonfinite_result')
    monkeypatch.setattr(module, operand, unavailable)
    state = classify(prefix)
    assert state.state == 'UNAVAILABLE' and state.reason


def test_intraday_same_fresh_input_hash_and_new_missing_daily_boundary(prefix):
    old = classify(prefix)
    for hours in (1, 12):
        later = prefix.eligibility_as_of+timedelta(hours=hours)
        current = classify_daily_exhaustion(replace(prefix, eligibility_as_of=later), later)
        assert current.state == old.state and current.hash == old.hash
        assert current.input_hash == old.input_hash and current.known_at == old.known_at
        assert current.macd_feature.values == old.macd_feature.values
        assert current.macd_feature.hash != old.macd_feature.hash  # distinct as_of envelope
    missing = replace(prefix, expected_session='2024-09-09')
    assert classify(missing).state == 'UNAVAILABLE'  # no stale EXTENDED fallback
    assert old.state == 'EXTENDED'


def test_late_dependency_arrival_and_new_daily_preserve_old_snapshot(prefix):
    old = classify(prefix)
    saved = payload(old)
    later = prefix.eligibility_as_of+timedelta(seconds=10)
    evidence = replace(prefix, transform_known_at=later)
    assert classify(evidence).state == 'UNAVAILABLE'
    arrived = classify_daily_exhaustion(replace(evidence, eligibility_as_of=later), later)
    assert arrived.known_at == later and arrived.hash != old.hash
    new = classify(prepared(list(range(100,482)), ending='2024-09-09'))
    assert new.input_count == 382 and new.session_date != old.session_date
    assert new.hash != old.hash and payload(old) == saved


def test_independence_and_no_direct_macro_or_shock_inputs(prefix):
    assert list(inspect.signature(classify_daily_exhaustion).parameters) == ['prefix', 'as_of', 'spec']
    assert trend(prefix).state == 'BULLISH' and classify(prefix).state == 'EXTENDED'
    # Volume carries generic bar provenance; it does not affect numeric state.
    changed = replace(prefix, bars=tuple(replace(b, volume=b.volume*1000) for b in prefix.bars))
    assert classify(changed).state == classify(prefix).state
    assert classify(changed).macd_line == classify(prefix).macd_line
    assert classify(changed).percentile == classify(prefix).percentile
    assert frozen_record()['independence']['raw_trend_input'] is False
    assert frozen_record()['independence']['shock_override'].startswith('FORBIDDEN')


@pytest.mark.parametrize('state,decision', [('NORMAL','ALLOW'), ('EXTENDED','BLOCK_EXTENDED'),
    ('UNAVAILABLE','BLOCK_UNAVAILABLE')])
@pytest.mark.parametrize('event', ['INITIAL_ENTRY', 'ADD', 'REENTRY'])
def test_policy_new_exposure_only(state, decision, event):
    assert evaluate_exhaustion_policy(state, event) == decision
    assert POLICY.semantics['existing_position'] == 'NO_FORCED_EXIT_existing_HOLD_EXIT_unchanged'
    assert POLICY.semantics['blocked_signal_queue'] == 'DISABLED'


@pytest.mark.parametrize('event', ['HOLD', 'EXIT', 'SELL_EXISTING_POSITION', 'ORDER'])
def test_existing_positions_and_orders_are_outside_policy(event):
    with pytest.raises(ValueError):
        evaluate_exhaustion_policy('EXTENDED', event)
    with pytest.raises(ValueError):
        evaluate_exhaustion_policy('UNAVAILABLE', event)


def test_stateless_policy_never_queues_blocked_signal():
    assert evaluate_exhaustion_policy('EXTENDED', 'INITIAL_ENTRY') == 'BLOCK_EXTENDED'
    assert evaluate_exhaustion_policy('UNAVAILABLE', 'REENTRY') == 'BLOCK_UNAVAILABLE'
    assert evaluate_exhaustion_policy('NORMAL', 'INITIAL_ENTRY') == 'ALLOW'
    assert POLICY.semantics['blocked_signal_lifecycle'] == 'NO_DEFERRED_EXECUTION_OF_BLOCKED_SIGNAL'
    assert POLICY.semantics['subsequent_entry'] == 'requires_new_valid_downstream_H0001_signal_trigger'
    with pytest.raises(ValueError):
        evaluate_exhaustion_policy('BEARISH', 'INITIAL_ENTRY')


def test_family_logging_and_trial_budget_preregistered_without_outcomes(prefix):
    record = frozen_record()
    family = record['initial_trial_family']
    assert set(family['members']) == {'E0', 'E1'} and family['primary_comparison_count'] == 1
    assert record['candidates']['B0']['name'] == 'NO_BLOCKER'
    assert record['candidates']['B1']['status'] == 'CANONICAL'
    assert record['candidates']['B2']['status'] == 'DEFERRED_SEPARATE_RESEARCH_VARIANT'
    assert not record['candidates']['B2']['initial_family_member']
    assert {'B2', 'z_score', 'ATR_normalization', 'prior_only_percentile', 'P1', 'P3'} <= set(family['excluded'])
    assert family['sweeps'] == 'FORBIDDEN'
    assert record['performance_information_used'] == 'NONE'
    assert all(record[k] == 'NOT_RUN' for k in ('historical_outcome_lookup', 'current_outcome_lookup',
                                             'historical_performance_backtest', 'current_chart_analysis'))
    assert record['state_definition']['hash'] == CANONICAL.hash
    assert record['policy']['hash'] == POLICY.hash
    logging = record['counterfactual_logging']
    state = classify(prefix)
    trace = dict(zip(logging['required_fields'], [prefix.symbol, prefix.eligibility_as_of.isoformat(),
        'H0001', 'INITIAL_ENTRY', True, 'BULLISH', state.state, state.state_version, state.hash,
        POLICY.version, POLICY.hash, 'BLOCK_EXTENDED', {'setup': 'fixture', 'trigger': 'fixture'},
        digest({'fixture_signal': 1}), state.input_hash, state.known_at.isoformat(), 'PENDING', None]))
    envelope = StrategyState(logging['schema_version'], JsonObject.of(trace))
    assert StrategyState.loads(envelope.dumps()) == envelope
    assert not logging['blocked_event_is_order_or_fill']
    later = envelope.data.unpack()
    later['counterfactual_status'] = 'UNRESOLVED'
    assert envelope.data.unpack()['counterfactual_status'] == 'PENDING'
    assert {'BLOCK_UNAVAILABLE_count', 'sample_suppression_ratio', 'availability_suppression_ratio',
            'INITIAL_ENTRY_blocked_count', 'ADD_blocked_count', 'REENTRY_blocked_count'} <= set(record['required_diagnostics'])


@pytest.mark.parametrize('path', [
    'research/hypotheses/H0001-r03.yaml', 'docs/RESEARCH_PHILOSOPHY.md',
    'research/decision_proposals/H0001-daily-blocker-v1.yaml',
    'research/decision_records/H0001-daily-input-freeze-v1.yaml',
    'research/decision_records/H0001-daily-trend-freeze-v1.yaml',
    'research/decision_records/H0001-daily-trend-readiness-remediation-v1.yaml',
    'richping/research_v2/strategy/daily_trend.py', 'richping/research_v2/features/macd.py',
    'richping/research_v2/features/relative.py', 'richping/research_v2/replay.py',
    'richping/cli.py', 'richping/paper.py', 'richping/pipeline.py', 'richping/engine.py',
])
def test_basis_sources_primitives_and_production_are_unchanged(path):
    original = subprocess.check_output(['git', 'show', BASE+':'+path], cwd=ROOT)
    assert (ROOT/path).read_bytes().replace(b'\r\n', b'\n') == original
