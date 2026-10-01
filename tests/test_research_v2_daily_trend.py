"""Synthetic semantics only: no provider, actions transform or performance run."""

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from pathlib import Path
import subprocess

import pytest
import yaml

from richping.core import calendar
from richping.research_v2.contracts import JsonObject, MarketBar, ReplayContext, payload
from richping.research_v2.features.moving import ema, recursive_ema
from richping.research_v2.sessions import RTH, session_bounds
from richping.research_v2.strategy.daily_trend import (
    CANONICAL, ABLATION, DailyTrendSpec, PreparedDailyPrefix,
    classify_daily_trend, minimum_history,
)
from richping.research_v2.strategy.h0001_spec import H0001Specification, load_h0001
from richping.research_v2.strategy.specification import C1, PERFORMANCE, OPTIONAL

ROOT = Path(__file__).resolve().parents[1]
BASE = 'f517374f66b75c84a0ea025ced91cacf866b2b8a'
DRAFT = ROOT / 'research/strategy_specs/H0001-r03-draft.yaml'
RECORD = ROOT / 'research/decision_records/H0001-daily-trend-freeze-v1.yaml'
REMEDIATION_BASE = '8ad1297a4dcd2e9787d62a78fa2866884dbbc41a'
REMEDIATION = ROOT / 'research/decision_records/H0001-daily-trend-readiness-remediation-v1.yaml'


def record():
    return yaml.safe_load(RECORD.read_text(encoding='utf-8'))


def remediation():
    return yaml.safe_load(REMEDIATION.read_text(encoding='utf-8'))


def daily(values, ending='2024-09-06'):
    sessions = calendar().sessions_in_range('2023-01-01', ending)[-len(values):]
    result = []
    for session, value in zip(sessions, values):
        day = session.date().isoformat()
        opened, closed = session_bounds(day, RTH)
        result.append(MarketBar('fixture-prepared-v1', 'ALFA', 'Daily', opened, closed,
            day, value, value+1, value-1, value, 100, closed, 'synthetic',
            JsonObject.of({'fixture': 'already_transformed_eligible_not_real_PIT_transform'}),
            'NONE_CONFIRMED'))
    return tuple(result)


def prepared(values=None, *, ending='2024-09-06'):
    values = list(range(100, 280)) if values is None else values
    bars = daily(values, ending)
    return PreparedDailyPrefix('ALFA', bars, bars[-1].known_at, bars[-1].session,
                               'synthetic-eligible-v1', bars[-1].known_at)


def classify(prefix, spec=CANONICAL):
    return classify_daily_trend(prefix, prefix.eligibility_as_of, spec)


def test_canonical_contract_hash_and_inventory_exactly_one_root_resolves():
    before = H0001Specification.loads(subprocess.check_output([
        'git', 'show', BASE+':'+DRAFT.relative_to(ROOT).as_posix()], cwd=ROOT).decode())
    after = load_h0001(DRAFT)
    old, new = before.unpack(), after.unpack()
    assert new['specification_version'] == 'h0001_r03_spec_v9'
    assert new['rule_parameters']['daily_long_permission']['value'] == CANONICAL.contract
    assert CANONICAL.version == 'DAILY_TREND_EMA_LEVEL_SLOPE_V1'
    assert len(new['decisions']) == 78
    assert old['decisions'] == new['decisions']
    assert set(before.unresolved_fields) - set(after.unresolved_fields) == {'rule_parameters.daily_long_permission'}
    assert not set(after.unresolved_fields) - set(before.unresolved_fields)
    assert (len(before.unresolved_fields), len(after.unresolved_fields)) == (97, 96)
    assert [len(after.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)] == [45, 17, 7]
    assert sum(len(after.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)) == 69
    assert 'H1-DAILY-LONG' not in after.blockers(C1)
    assert 'H1-DAILY-BLOCKER' in after.blockers(C1)
    old['specification_version'] = new['specification_version']
    old['rule_parameters']['daily_long_permission'] = new['rule_parameters']['daily_long_permission']
    assert old == new
    assert after.specification_hash == remediation()['executable_spec']['canonical_sha256']
    assert CANONICAL.hash == remediation()['executable_spec']['rule_sha256']
    assert CANONICAL.ema_spec.hash == remediation()['executable_spec']['ema_feature_specification_sha256']
    for gate in (after.require_c1_ready, after.require_profitability_ready, after.plugin_specification):
        with pytest.raises(ValueError):
            gate()


@pytest.mark.parametrize('parameter,value', [('ema_span', 20), ('slope_lag_observations', 1),
    ('minimum_history', 173), ('seed_residual_limit', 0.002),
    ('readiness_definition', 'update_count'),
    ('operand_readiness', 'current_only'), ('level_equality', True), ('rule_hash', 'changed')])
def test_v9_frozen_payload_cannot_be_silently_mutated(parameter, value):
    body = load_h0001(DRAFT).unpack()
    body['rule_parameters']['daily_long_permission']['value']['parameters'][parameter]['value'] = value
    with pytest.raises(ValueError, match='Frozen Daily trend'):
        H0001Specification.of(body)


def test_actual_first_seed_residual_formula_derives_readiness():
    alpha = 2/51
    assert alpha == 2 / (CANONICAL.ema_spec.span + 1)
    assert CANONICAL.ema_spec.span == 50 and CANONICAL.ema_spec.min_history == 174
    assert minimum_history() == 174
    assert CANONICAL.semantics['seed_residual_limit'] == 0.001
    assert (1-alpha)**172 > 0.001 >= (1-alpha)**173
    assert (1-alpha)**(minimum_history()-2) > 0.001
    assert (1-alpha)**(minimum_history()-1) <= 0.001
    # Independent perturbation check of the actual primitive's N-1 updates.
    seeded = recursive_ema([1.0] + [0.0]*172, 50)[-1]
    assert seeded == pytest.approx((1-alpha)**172)
    assert seeded > 0.001
    assert recursive_ema([1.0] + [0.0]*173, 50)[-1] <= 0.001
    assert 'N-1' in record()['readiness']['off_by_one_audit']
    for count in (173, 174):
        boundary = remediation()['readiness'][f'N_{count}']
        assert boundary['seed_residual'] == (1-alpha)**(count-1)
        assert boundary['seed_residual_percent'] == pytest.approx(100*boundary['seed_residual'])


@pytest.mark.parametrize('count,reason,lag_count', [
    (172, 'current_ema:insufficient_history', 167),
    (173, 'current_ema:insufficient_history', 168),
    (174, 'lag_ema:insufficient_history', 169),
    (177, 'lag_ema:insufficient_history', 172),
    (178, 'lag_ema:insufficient_history', 173), (179, None, 174)])
def test_readiness_checks_each_actual_operand_prefix(count, reason, lag_count):
    prefix = prepared(list(range(100, 100+count)))
    state = classify(prefix)
    assert state.input_count == count and state.lag_input_count == lag_count
    assert state.reason == reason
    assert state.state == ('UNAVAILABLE' if reason else 'BULLISH')
    assert classify(prefix, ABLATION).status == state.status
    # A's underlying primitive alone is ready at 174; matched experiment gates
    # both arms on the same operands, removing only a boolean predicate.
    primitive = ema(ReplayContext(prefix.eligibility_as_of, prefix.bars), 'ALFA', 'Daily', CANONICAL.ema_spec)
    assert (primitive.status == 'READY') == (count >= 174)


@pytest.mark.parametrize('count,expected', [(173, 'UNAVAILABLE'), (174, 'READY')])
def test_standalone_a_boundary_does_not_expand_matched_sample(count, expected):
    prefix = prepared(list(range(100, 100+count)))
    standalone = classify_daily_trend(prefix, prefix.eligibility_as_of, ABLATION,
                                      matched_comparison=False)
    assert standalone.status == expected
    assert standalone.state == ('BULLISH' if expected == 'READY' else 'UNAVAILABLE')
    assert standalone.lag_ema is None
    assert classify(prefix, ABLATION).status == classify(prefix).status == 'UNAVAILABLE'
    # Turning off matched mode never removes B's lagged operand gate.
    assert classify_daily_trend(prefix, prefix.eligibility_as_of,
                                matched_comparison=False).status == 'UNAVAILABLE'


@pytest.mark.parametrize('unready', ['current_ema', 'lag_ema'])
def test_each_operand_readiness_is_independent_even_if_other_is_ready(monkeypatch, unready):
    # A real lagged prefix cannot be longer than current. Inject feature
    # readiness independently to verify neither operand can mask the other's
    # unavailable result (including the otherwise impossible reversed case).
    import richping.research_v2.strategy.daily_trend as module
    prefix = prepared()
    def operand(context, symbol, timeframe, spec):
        label = 'current_ema' if len(context.bars) == len(prefix.bars) else 'lag_ema'
        count = 173 if label == unready else 174
        return ema(ReplayContext(context.as_of, prefix.bars[:count]), symbol, timeframe, spec)
    monkeypatch.setattr(module, 'ema', operand)
    state = classify(prefix)
    assert state.state == state.status == 'UNAVAILABLE'
    assert state.reason == unready + ':insufficient_history'


def test_v8_history_remains_readable_immutable_and_inventory_is_unchanged():
    historical = H0001Specification.loads(subprocess.check_output([
        'git', 'show', REMEDIATION_BASE+':'+DRAFT.relative_to(ROOT).as_posix()], cwd=ROOT).decode())
    current = load_h0001(DRAFT)
    old, new = historical.unpack(), current.unpack()
    assert historical.specification_hash == record()['executable_spec']['canonical_sha256']
    assert old['rule_parameters']['daily_long_permission']['value']['parameters']['minimum_history']['value'] == 173
    assert old['decisions'] == new['decisions']
    assert historical.unresolved_fields == current.unresolved_fields
    assert [len(current.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)] == [45, 17, 7]
    assert len(new['decisions']) == 78 and len(current.unresolved_fields) == 96
    old['specification_version'] = new['specification_version']
    old['rule_parameters']['daily_long_permission'] = new['rule_parameters']['daily_long_permission']
    assert old == new
    # A v8 payload cannot acquire the corrected readiness under its old version.
    new['specification_version'] = 'h0001_r03_spec_v8'
    with pytest.raises(ValueError, match='Frozen Daily trend v8'):
        H0001Specification.of(new)
    for path in (RECORD.relative_to(ROOT).as_posix(),):
        assert (ROOT/path).read_bytes().replace(b'\r\n', b'\n') == subprocess.check_output([
            'git', 'show', REMEDIATION_BASE+':'+path], cwd=ROOT)
    body = remediation()
    assert body['basis_commit'] == REMEDIATION_BASE
    assert body['classification'] == 'MATHEMATICAL_CONTRACT_REMEDIATION'
    assert body['performance_information_used'] == 'NONE'
    assert body['unchanged']['H1_DAILY_LONG'] == 'RESOLVED'
    assert body['unchanged']['H1_DAILY_BLOCKER'] == 'UNRESOLVED'


def test_close_equality_and_ready_false_are_not_unavailable_or_short_permission():
    state = classify(prepared([100.0]*180))
    assert state.current_ema == 100 and state.lag_ema == 100
    assert state.state == 'NOT_BULLISH' and state.status == 'READY' and state.reason is None


def test_slope_equality_with_price_above_ema_is_not_bullish():
    values = [100.0]*175 + [90.0]*4
    previous = recursive_ema(values, 50)[-1]
    alpha = 2/51
    values.append((100.0 - (1-alpha)*previous)/alpha)
    prefix = prepared(values)
    state = classify(prefix)
    assert prefix.bars[-1].close > state.current_ema
    assert state.current_ema == state.lag_ema == 100.0
    assert state.state == 'NOT_BULLISH'
    assert classify(prefix, ABLATION).state == 'BULLISH'


def test_level_reclaim_above_falling_ema_is_only_bullish_for_ablation():
    values = [200 - i*0.4 for i in range(179)] + [145.0]
    prefix = prepared(values)
    state = classify(prefix)
    assert prefix.bars[-1].close > state.current_ema
    assert state.current_ema < state.lag_ema
    assert state.state == 'NOT_BULLISH' and classify(prefix, ABLATION).state == 'BULLISH'


def test_rising_level_and_slope_are_bullish_using_existing_ema_on_same_origin():
    prefix = prepared()
    state = classify(prefix)
    current = ema(ReplayContext(prefix.eligibility_as_of, prefix.bars), 'ALFA', 'Daily', CANONICAL.ema_spec)
    lag = ema(ReplayContext(prefix.eligibility_as_of, prefix.bars[:-5]), 'ALFA', 'Daily', CANONICAL.ema_spec)
    assert state.state == 'BULLISH'
    assert state.current_ema == current.values.unpack()['ema']
    assert state.lag_ema == lag.values.unpack()['ema']
    assert state.rule_version == CANONICAL.version and state.rule_hash == CANONICAL.hash
    assert state.ema_feature_specification_hash == CANONICAL.ema_spec.hash
    assert state.input_end_at == state.known_at == prefix.bars[-1].end_at
    assert state.session_date == prefix.expected_session
    assert state.price_basis == 'PIT_SPLIT_ADJUSTED_OHLC' and state.session_profile == RTH
    assert state.source_vintage == prefix.source_vintage and state.input_hash
    assert classify(prefix) == state
    with pytest.raises(FrozenInstanceError):
        state.state = 'NOT_BULLISH'


@pytest.mark.parametrize('mutation,reason', [
    ('empty', 'no_completed_input'), ('no_action', 'action_evidence_unavailable'),
    ('input', 'required_action_coverage_missing'), ('freshness', 'freshness_evidence_unavailable'),
    ('expected', 'latest_expected_completed_session_missing'),
    ('gap', 'current_ema:noncontiguous_history'),
    ('basis', 'input_contract_mismatch'), ('profile', 'input_contract_mismatch'),
    ('eligibility', 'eligibility_as_of_mismatch'),
    ('duplicate', 'invalid_Daily_prefix'),
    ('bar_profile', 'invalid_or_unsupported_Daily_input'),
    ('action', 'invalid_or_unsupported_Daily_input')])
def test_unavailable_inputs_never_become_not_bullish(mutation, reason):
    prefix = prepared()
    changes = {
        'empty': {'bars': ()}, 'no_action': {'transform_known_at': None},
        'input': {'input_status': 'UNAVAILABLE', 'input_reason': reason},
        'freshness': {'expected_session': None}, 'expected': {'expected_session': '2024-09-09'},
        'gap': {'bars': prefix.bars[:30] + prefix.bars[31:]},
        'basis': {'price_basis': 'raw'}, 'profile': {'session_profile': 'US_EQUITY_EXTENDED_04_20'},
        'eligibility': {'eligibility_as_of': prefix.eligibility_as_of-timedelta(seconds=1)},
        'duplicate': {'bars': prefix.bars + (prefix.bars[-1],)},
        'bar_profile': {'bars': prefix.bars[:-1]+(replace(prefix.bars[-1], provenance=JsonObject.of({'session_profile': 'UNKNOWN'})),)},
        'action': {'bars': prefix.bars[:-1]+(replace(prefix.bars[-1], corporate_action='UNKNOWN'),)},
    }[mutation]
    state = classify_daily_trend(replace(prefix, **changes), prefix.eligibility_as_of)
    assert state.state == state.status == 'UNAVAILABLE' and state.reason == reason
    assert state.state != 'NOT_BULLISH'


@pytest.mark.parametrize('future', ['bar', 'delivery', 'action_known', 'action_effective'])
def test_future_daily_and_action_evidence_cannot_leak(future):
    prefix = prepared()
    instant = prefix.eligibility_as_of
    if future == 'bar':
        new = daily([500], '2024-09-09')[-1]
        prefix = replace(prefix, bars=prefix.bars+(new,))
    elif future == 'delivery':
        prefix = replace(prefix, bars=prefix.bars[:-1]+(replace(prefix.bars[-1], known_at=instant+timedelta(seconds=1)),))
    elif future == 'action_known':
        prefix = replace(prefix, transform_known_at=instant+timedelta(seconds=1))
    else:
        prefix = replace(prefix, transform_effective_at=(instant+timedelta(seconds=1),))
    state = classify_daily_trend(prefix, instant)
    assert state.state == 'UNAVAILABLE' and state.reason == 'future_Daily_or_action_evidence'
    assert state.current_ema is None and state.known_at is None and state.input_end_at is None
    assert state.input_count == 0


def test_lag_counts_trading_observations_across_weekend_and_holiday():
    prefix = prepared(ending='2024-09-09')
    state = classify(prefix)
    assert prefix.bars[-6].session == '2024-08-30'
    assert prefix.bars[-1].session == '2024-09-09'
    assert len(prefix.bars[-5:]) == 5  # Labor Day / weekends have no bar.
    assert state.lag_ema == recursive_ema([b.close for b in prefix.bars[:-5]], 50)[-1]


def test_intraday_stability_expiration_and_actual_atomic_delivery_recompute():
    prefix = prepared(ending='2024-09-05')
    old = classify(prefix)
    opened, close = session_bounds('2024-09-06', RTH)
    for instant in (opened-timedelta(hours=3, minutes=30), opened+timedelta(minutes=30), close-timedelta(minutes=30)):
        state = classify(replace(prefix, eligibility_as_of=instant))
        assert state.state == old.state and state.current_ema == old.current_ema
        assert state.input_hash == old.input_hash and state.known_at == old.known_at
    unavailable = replace(prefix, eligibility_as_of=close, expected_session='2024-09-06')
    assert classify(unavailable).state == 'UNAVAILABLE'
    delivered = close+timedelta(minutes=2)
    new_bar = replace(daily([400], '2024-09-06')[-1], known_at=delivered)
    pending = replace(unavailable, bars=prefix.bars+(new_bar,))
    assert classify(pending).state == 'UNAVAILABLE'
    # Required action evidence is later still; no backdating to bar delivery.
    action_time = delivered+timedelta(seconds=5)
    pending = replace(pending, eligibility_as_of=delivered, transform_known_at=action_time)
    assert classify(pending).state == 'UNAVAILABLE'
    new = classify(replace(pending, eligibility_as_of=action_time))
    assert new.state == 'BULLISH' and new.known_at == action_time
    assert new.session_date == '2024-09-06' and new.input_hash != old.input_hash
    assert new.current_ema != old.current_ema and old.session_date == '2024-09-05'


def test_ablation_changes_only_slope_predicate_with_identical_operand_availability():
    a, b = ABLATION.semantics, CANONICAL.semantics
    assert {k for k in a if a[k] != b[k]} == {'require_positive_slope'}
    assert ABLATION.ema_spec == CANONICAL.ema_spec
    for prefix in (prepared(), prepared([100.0]*173), prepared([100.0]*180)):
        t0, t1 = classify(prefix, ABLATION), classify(prefix)
        for field in ('status', 'reason', 'input_hash', 'input_count', 'lag_input_count',
                      'known_at', 'current_ema', 'lag_ema', 'ema_feature_specification_hash'):
            assert getattr(t0, field) == getattr(t1, field)


def test_preserved_sources_family_protocol_and_no_runtime_connection():
    for path in ('research/hypotheses/H0001-r03.yaml',
                 'research/decision_records/H0001-daily-input-freeze-v1.yaml',
                 'research/decision_proposals/H0001-daily-price-regime-v1.yaml',
                 'docs/RESEARCH_PHILOSOPHY.md', 'richping/paper.py', 'richping/pipeline.py',
                 'richping/cli.py', 'richping/research_v2/replay.py'):
        assert (ROOT/path).read_bytes().replace(b'\r\n', b'\n') == subprocess.check_output(['git', 'show', BASE+':'+path], cwd=ROOT)
    body = record()
    assert body['hypothesis']['status'] == load_h0001(DRAFT).unpack()['status'] == 'DRAFT'
    assert body['hypothesis']['profitability'] == 'NOT_TESTED'
    assert body['observed_chart_parity'] == load_h0001(DRAFT).unpack()['chart_parity']['parity_status']['value'] == 'UNVERIFIED'
    assert body['candidates']['DLP-A']['status'] == 'PREDECLARED_ABLATION_COMPARATOR'
    assert body['candidates']['DLP-C']['status'] == 'DEFERRED_SEPARATE_RESEARCH_VARIANT'
    with pytest.raises(ValueError, match='deferred'):
        DailyTrendSpec('DLP-C')
    assert body['experiment_family']['members'] == {'T0': 'DLP-A', 'T1': 'DLP-B'}
    assert len(body['experiment_family']['diagnostics']) == 13
    assert body['experiment_family']['parameter_sweeps'] == 'FORBIDDEN'
    assert body['independent_axes']['H1-DAILY-BLOCKER'] == 'UNRESOLVED'
    protocol = body['confirmatory_protocol']
    assert protocol['chronological_only'] and protocol['discovery_confirmatory_separate']
    assert protocol['exposed_cases_independent_confirmation'] == 'FORBIDDEN'
    assert protocol['dataset_id'] == protocol['date_splits'] == 'NOT_YET_FROZEN'
    assert protocol['retain_trials'] == ['failed', 'null', 'inconclusive']
    assert body['implementation']['runtime_paper_order_connection'] == 'NONE'
    assert body['implementation']['end_to_end_real_market_replay'] == 'NOT_IMPLEMENTED'
