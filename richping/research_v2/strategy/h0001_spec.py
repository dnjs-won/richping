"""H0001-r03 mandatory contract inventory; no event handler or trading logic."""

from pathlib import Path
from hashlib import sha256

from .specification import StrategySpecification, UNRESOLVED, exact
from .capabilities import current_engine, require_current_engine

REQUIRED = {
    ('timeframe_contracts', 'session_policy'): ('enum', 'H1-SESSION', 'C1_IMPLEMENTATION_BLOCKER', ('RTH', 'RTH_EXTENDED')),
    ('timeframe_contracts', 'base'): ('timeframe', 'H1-BASE', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('feature_contracts', 'macd_ema_seed'): ('contract', 'H1-EMA-SEED', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('feature_contracts', 'macd_signal_start'): ('contract', 'H1-EMA-SEED', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('feature_contracts', 'macd_price_field'): ('contract', 'H1-EMA-SEED', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('feature_contracts', 'macd_feature_version'): ('contract', 'H1-EMA-SEED', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('feature_contracts', 'macd_min_history_daily'): ('integer', 'H1-MACD-HISTORY', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('feature_contracts', 'macd_min_history_1h'): ('integer', 'H1-MACD-HISTORY', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('feature_contracts', 'macd_min_history_15m'): ('integer', 'H1-MACD-HISTORY', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('feature_contracts', 'history_origin'): ('contract', 'H1-HISTORY-ORIGIN', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'daily_long_permission'): ('contract', 'H1-DAILY-LONG', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'daily_exhaustion_blocker'): ('contract', 'H1-DAILY-BLOCKER', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'setup_1h_relative_transform'): ('enum', 'H1-RELATIVE-METHOD', 'C1_IMPLEMENTATION_BLOCKER', ('MACD_ATR', 'ROLLING_PERCENTILE', 'ROLLING_ZSCORE')),
    ('rule_parameters', 'setup_1h_rolling_lookback'): ('integer', 'H1-LOOKBACK', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('feature_contracts', 'setup_1h_relative_conventions'): ('contract', 'H1-RELATIVE-CONVENTIONS', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'setup_1h_downside_threshold'): ('number', 'H1-DOWNSIDE', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'setup_1h_downside_comparator'): ('enum', 'H1-COMPARATOR', 'C1_IMPLEMENTATION_BLOCKER', ('LE', 'LT')),
    ('rule_parameters', 'entry_15m_relative_transform'): ('enum', 'H1-M15-RELATIVE-METHOD', 'C1_IMPLEMENTATION_BLOCKER', ('MACD_ATR', 'ROLLING_PERCENTILE', 'ROLLING_ZSCORE')),
    ('rule_parameters', 'entry_15m_rolling_lookback'): ('integer', 'H1-M15-LOOKBACK', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('feature_contracts', 'entry_15m_relative_conventions'): ('contract', 'H1-M15-RELATIVE-CONVENTIONS', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'entry_15m_downside_threshold'): ('number', 'H1-M15-DOWNSIDE', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'entry_15m_downside_comparator'): ('enum', 'H1-M15-COMPARATOR', 'C1_IMPLEMENTATION_BLOCKER', ('LE', 'LT')),
    ('state_machine_parameters', 'setup_persistence_expiry'): ('contract', 'H1-SETUP-LIFETIME', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'entry_15m_gc'): ('contract', 'H1-M15-GC', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'entry_15m_price_reversal'): ('contract', 'H1-M15-REVERSAL', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'entry_15m_trigger_conjunction'): ('contract', 'H1-M15-CONJUNCTION', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('state_machine_parameters', 'reentry_add_policy'): ('contract', 'H1-ADD-POLICY', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'failed_first_reversal'): ('contract', 'H1-FAILED-REVERSAL', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'deeper_extreme'): ('contract', 'H1-DEEPER-EXTREME', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('state_machine_parameters', 'max_adds'): ('integer', 'H1-MAX-ADDS', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('execution_requirements', 'initial_sizing'): ('contract', 'H1-SIZING', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('execution_requirements', 'tranche_sizing'): ('contract', 'H1-SIZING', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('execution_requirements', 'total_risk_cap'): ('contract', 'H1-EXPOSURE', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('execution_requirements', 'exposure_cap'): ('contract', 'H1-EXPOSURE', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('rule_parameters', 'role_of_1h_gc'): ('contract', 'H1-GC-ROLE', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'exit_1h_relative_transform'): ('enum', 'H1-EXIT-RELATIVE', 'C1_IMPLEMENTATION_BLOCKER', ('MACD_ATR', 'ROLLING_PERCENTILE', 'ROLLING_ZSCORE')),
    ('rule_parameters', 'exit_1h_rolling_lookback'): ('integer', 'H1-EXIT-LOOKBACK', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('feature_contracts', 'exit_1h_relative_conventions'): ('contract', 'H1-EXIT-CONVENTIONS', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'exit_upper_relative_extreme'): ('number', 'H1-UPPER-EXTREME', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'exit_upper_comparator'): ('enum', 'H1-UPPER-COMPARATOR', 'C1_IMPLEMENTATION_BLOCKER', ('GE', 'GT')),
    ('rule_parameters', 'histogram_contraction'): ('contract', 'H1-HISTOGRAM', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'macd_slope'): ('contract', 'H1-MACD-SLOPE', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'signal_slope'): ('contract', 'H1-SIGNAL-SLOPE', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'exit_dead_cross'): ('contract', 'H1-DEAD-CROSS', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'weak_watch'): ('contract', 'H1-WEAK-WATCH', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'strong_watch'): ('contract', 'H1-STRONG-WATCH', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'watch_price_confirmation'): ('contract', 'H1-WATCH-CONFIRMATION', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'swing_detector'): ('enum', 'H1-SWING-DETECTOR', 'C1_IMPLEMENTATION_BLOCKER', ('ATR_REVERSAL', 'DIRECTIONAL_CHANGE', 'FRACTAL')),
    ('rule_parameters', 'swing_parameters'): ('contract', 'H1-SWING-PARAMETERS', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'reference_hh'): ('contract', 'H1-REFERENCE-HH', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'lh_definition'): ('contract', 'H1-LH', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'hl_definition'): ('contract', 'H1-VALID-HL', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'valid_hl_semantics'): ('contract', 'H1-VALID-HL', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('rule_parameters', 'hl_break_confirmation'): ('contract', 'H1-HL-BREAK', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('state_machine_parameters', 'new_hh_reset'): ('contract', 'H1-NEW-HH-RESET', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('state_machine_parameters', 'stop_loss'): ('contract', 'H1-STOP-LOSS', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('state_machine_parameters', 'trailing_stop'): ('contract', 'H1-TRAILING', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('state_machine_parameters', 'max_holding'): ('contract', 'H1-MAX-HOLDING', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('state_machine_parameters', 'overnight'): ('contract', 'H1-OVERNIGHT', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('state_machine_parameters', 'decision_timing'): ('contract', 'H1-DECISION-TIMING', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('state_machine_parameters', 'transition_priority_and_resets'): ('contract', 'H1-STATE-TRANSITIONS', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('state_machine_parameters', 'initial_state'): ('contract', 'H1-STATE-TRANSITIONS', 'C1_IMPLEMENTATION_BLOCKER', ()),
    ('execution_requirements', 'order_timing'): ('contract', 'H1-ORDER-TIMING', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('execution_requirements', 'fill_price_contract'): ('contract', 'H1-FILL', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('execution_requirements', 'transaction_cost'): ('contract', 'H1-COSTS', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('execution_requirements', 'slippage'): ('contract', 'H1-COSTS', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('research_requirements', 'universe'): ('contract', 'H1-UNIVERSE', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('research_requirements', 'discovery_period'): ('contract', 'H1-DISCOVERY', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('research_requirements', 'confirmatory_period'): ('contract', 'H1-CONFIRMATORY', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('research_requirements', 'baseline'): ('contract', 'H1-BASELINE', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('research_requirements', 'primary_metric'): ('contract', 'H1-PRIMARY-METRIC', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('research_requirements', 'decision_rule'): ('contract', 'H1-DECISION-RULE', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('research_requirements', 'null_hypothesis'): ('contract', 'H1-DECISION-RULE', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('research_requirements', 'sample_unit'): ('enum', 'H1-SAMPLE-UNIT', 'PERFORMANCE_EXPERIMENT_BLOCKER', ('COMPLETED_TRADE', 'SIGNAL_EVENT')),
    ('research_requirements', 'multiple_testing_family'): ('contract', 'H1-MULTIPLE-TESTING', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('chart_parity', 'observed_chart_provider'): ('text', 'H1-CHART-PROVIDER', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('chart_parity', 'observed_1h_boundary'): ('text', 'H1-CHART-1H', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('chart_parity', 'observed_ema_seed'): ('text', 'H1-CHART-EMA', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('chart_parity', 'observed_history_origin'): ('text', 'H1-CHART-EMA', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('chart_parity', 'observed_min_history'): ('text', 'H1-CHART-EMA', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('chart_parity', 'parity_evidence'): ('text', 'H1-CHART-VERIFICATION', 'PERFORMANCE_EXPERIMENT_BLOCKER', ()),
    ('optional_extensions', 'four_hour_filter'): ('contract', 'H1-4H', 'OPTIONAL_FUTURE_EXTENSION', ()),
    ('optional_extensions', 'weekly_monthly_filter'): ('contract', 'H1-WEEKLY-MONTHLY', 'OPTIONAL_FUTURE_EXTENSION', ()),
    ('optional_extensions', 'five_one_minute'): ('contract', 'H1-FINE-EXECUTION', 'OPTIONAL_FUTURE_EXTENSION', ()),
    ('optional_extensions', 'volume'): ('contract', 'H1-VOLUME-PA', 'OPTIONAL_FUTURE_EXTENSION', ()),
    ('optional_extensions', 'divergence'): ('contract', 'H1-VOLUME-PA', 'OPTIONAL_FUTURE_EXTENSION', ()),
    ('optional_extensions', 'obv'): ('contract', 'H1-VOLUME-PA', 'OPTIONAL_FUTURE_EXTENSION', ()),
    ('optional_extensions', 'vwap'): ('contract', 'H1-VOLUME-PA', 'OPTIONAL_FUTURE_EXTENSION', ()),
    ('optional_extensions', 'volume_profile'): ('contract', 'H1-VOLUME-PA', 'OPTIONAL_FUTURE_EXTENSION', ()),
    ('optional_extensions', 'order_block'): ('contract', 'H1-VOLUME-PA', 'OPTIONAL_FUTURE_EXTENSION', ()),
    ('optional_extensions', 'options_chain'): ('contract', 'H1-OPTIONS', 'OPTIONAL_FUTURE_EXTENSION', ()),
    ('optional_extensions', 'zero_dte_flow'): ('contract', 'H1-OPTIONS', 'OPTIONAL_FUTURE_EXTENSION', ()),
    ('optional_extensions', 'gex'): ('contract', 'H1-OPTIONS', 'OPTIONAL_FUTURE_EXTENSION', ()),
    ('optional_extensions', 'max_pain'): ('contract', 'H1-OPTIONS', 'OPTIONAL_FUTURE_EXTENSION', ()),
    ('optional_extensions', 'short_strategy'): ('contract', 'H1-SHORT', 'OPTIONAL_FUTURE_EXTENSION', ()),
    ('optional_extensions', 'price_macd_gc_lag_distribution'): ('contract', 'H1-LAG-STUDY', 'OPTIONAL_FUTURE_EXTENSION', ()),
}

FIXED = {('feature_contracts', 'macd_fast'): ('integer', 12),
 ('feature_contracts', 'macd_slow'): ('integer', 26),
 ('feature_contracts', 'macd_signal'): ('integer', 9),
 ('timeframe_contracts', 'regime'): ('timeframe', 'Daily'),
 ('timeframe_contracts', 'setup'): ('timeframe', '1H'),
 ('timeframe_contracts', 'confirmation'): ('timeframe', '15m'),
 ('timeframe_contracts', 'execution'): ('timeframe', '15m'),
 ('chart_parity', 'engine_1h_boundary'): ('text',
                                          'XNYS open anchored; America/New_York 09:30-10:30, 10:30-11:30, '
                                          '..., 15:30-16:00; early close final bucket ends at official '
                                          'close'),
 ('chart_parity', 'engine_ema_seed'): ('text', 'first_observation_recursive_v1')}

ENGINE_FIELDS = tuple(current_engine())

STATES = ('DISABLED', 'DAILY_LONG_ALLOWED', 'SETUP_1H_DOWNSIDE', 'ENTRY_READY', 'ACTIVE_SIGNAL', 'ADD_READY', 'EXIT_WATCH_WEAK', 'EXIT_WATCH_STRONG', 'INACTIVE_SIGNAL')

TRANSITIONS = {'daily_permission': ('DISABLED',
                      'DAILY_LONG_ALLOWED',
                      ('H1-DAILY-BLOCKER', 'H1-DAILY-LONG', 'H1-STATE-TRANSITIONS')),
 'downside_setup': ('DAILY_LONG_ALLOWED',
                    'SETUP_1H_DOWNSIDE',
                    ('H1-DOWNSIDE', 'H1-RELATIVE-METHOD', 'H1-SETUP-LIFETIME', 'H1-STATE-TRANSITIONS')),
 'entry_candidate': ('SETUP_1H_DOWNSIDE',
                     'ENTRY_READY',
                     ('H1-M15-CONJUNCTION',
                      'H1-M15-DOWNSIDE',
                      'H1-M15-GC',
                      'H1-M15-RELATIVE-METHOD',
                      'H1-M15-REVERSAL',
                      'H1-STATE-TRANSITIONS')),
 'enter_intent_emitted': ('ENTRY_READY',
                          'ACTIVE_SIGNAL',
                          ('H1-DECISION-TIMING', 'H1-STATE-TRANSITIONS')),
 'failed_reversal_add_candidate': ('ACTIVE_SIGNAL',
                                   'ADD_READY',
                                   ('H1-ADD-POLICY',
                                    'H1-DEEPER-EXTREME',
                                    'H1-FAILED-REVERSAL',
                                    'H1-GC-ROLE',
                                    'H1-MAX-ADDS',
                                    'H1-STATE-TRANSITIONS')),
 'add_intent_emitted': ('ADD_READY',
                     'ACTIVE_SIGNAL',
                     ('H1-ADD-POLICY',
                      'H1-DECISION-TIMING',
                      'H1-STATE-TRANSITIONS')),
 'weak_watch_candidate': ('ACTIVE_SIGNAL',
                          'EXIT_WATCH_WEAK',
                          ('H1-DEAD-CROSS',
                           'H1-HISTOGRAM',
                           'H1-MACD-SLOPE',
                           'H1-SIGNAL-SLOPE',
                           'H1-STATE-TRANSITIONS',
                           'H1-WEAK-WATCH')),
 'strong_watch_candidate': ('ACTIVE_SIGNAL',
                            'EXIT_WATCH_STRONG',
                            ('H1-STATE-TRANSITIONS', 'H1-STRONG-WATCH', 'H1-UPPER-EXTREME')),
 'weak_structure_exit_candidate': ('EXIT_WATCH_WEAK',
                                   'INACTIVE_SIGNAL',
                                   ('H1-HL-BREAK',
                                    'H1-LH',
                                    'H1-REFERENCE-HH',
                                    'H1-STATE-TRANSITIONS',
                                    'H1-VALID-HL',
                                    'H1-WATCH-CONFIRMATION')),
 'strong_structure_exit_candidate': ('EXIT_WATCH_STRONG',
                                     'INACTIVE_SIGNAL',
                                     ('H1-HL-BREAK',
                                      'H1-LH',
                                      'H1-REFERENCE-HH',
                                      'H1-STATE-TRANSITIONS',
                                      'H1-VALID-HL',
                                      'H1-WATCH-CONFIRMATION')),
 'hold_or_new_hh_candidate': ('ACTIVE_SIGNAL',
                              'ACTIVE_SIGNAL',
                              ('H1-NEW-HH-RESET', 'H1-REFERENCE-HH', 'H1-STATE-TRANSITIONS', 'H1-VALID-HL')),
 'inactive_daily_permission': ('INACTIVE_SIGNAL', 'DAILY_LONG_ALLOWED',
                               ('H1-DAILY-BLOCKER', 'H1-DAILY-LONG', 'H1-STATE-TRANSITIONS')),
 'inactive_daily_disabled': ('INACTIVE_SIGNAL', 'DISABLED',
                             ('H1-DAILY-BLOCKER', 'H1-DAILY-LONG', 'H1-STATE-TRANSITIONS'))}

# These edges reuse the existing unresolved contract, not two new decisions or
# two resolved guards. The target is already validated and counted by the base
# specification; FROZEN/C1 admission still requires that target to be resolved.
LIFECYCLE_RETURNS = ('inactive_daily_permission', 'inactive_daily_disabled')
LIFECYCLE_CONDITION = {
    'kind': 'contract',
    'value': {
        'name': 'existing_contract_reference', 'version': 'v1',
        'parameters': {
            'path': {'kind': 'text',
                     'value': 'state_machine_parameters.transition_priority_and_resets',
                     'choices': [], 'decision_id': None},
        },
    },
    'choices': [], 'decision_id': 'H1-STATE-TRANSITIONS',
}


def validate_signal_lifecycle(machine):
    """Check possible signal cycles, not guard truth or runtime progress.

    All H0001 states are nonterminal. DISABLED is a graph entry anchor, not a
    choice of the still-unresolved runtime initial state. A future causal setup
    must be able to start another episode after either exit-watch branch.
    """
    states = set(machine['states'])
    edges = {(t['from'], t['to']) for t in machine['transitions'].values()}

    def reachable(start, excluded=()):
        seen, pending = set(), [start]
        while pending:
            state = pending.pop()
            if state in seen:
                continue
            seen.add(state)
            pending.extend(b for a, b in edges if a == state and (a, b) not in excluded)
        return seen

    for state in states:
        if not any(a == state and b != state for a, b in edges):
            raise ValueError(f'H0001 lifecycle dead-end: {state}')
    if reachable('DISABLED') != states:
        raise ValueError('H0001 lifecycle contains unreachable states')
    for state in states:
        if not {'ENTRY_READY', 'INACTIVE_SIGNAL'} <= reachable(state):
            raise ValueError(f'H0001 lifecycle cannot complete/restart a cycle: {state}')
    if {b for a, b in edges if a == 'INACTIVE_SIGNAL'} != {'DAILY_LONG_ALLOWED', 'DISABLED'}:
        raise ValueError('H0001 lifecycle must return through Daily permission evaluation')
    # Every first activation from either inactive state must cross these edges
    # in order. Removing any one must cut all routes to ACTIVE_SIGNAL, including
    # indirect shortcuts through add/watch states.
    for gate in (('DAILY_LONG_ALLOWED', 'SETUP_1H_DOWNSIDE'),
                 ('SETUP_1H_DOWNSIDE', 'ENTRY_READY'),
                 ('ENTRY_READY', 'ACTIVE_SIGNAL')):
        for start in ('DISABLED', 'INACTIVE_SIGNAL'):
            if 'ACTIVE_SIGNAL' in reachable(start, (gate,)):
                raise ValueError('H0001 lifecycle bypasses Daily permission/setup/entry')

SOURCE_SHA256 = "35e13276056a36d6a06de04611720fd286113f0e5db1e4255af6ceeb6a0f0bc2"


class H0001Specification(StrategySpecification):
    """Validate the r03 profile in addition to the generic serialization contract."""

    __slots__ = ()

    def __post_init__(self):
        super().__post_init__()
        value = self.unpack()
        if (value["strategy_id"], value["hypothesis_id"], value["hypothesis_revision"], value["direction"]) != (
                "H0001", "H0001", 3, "LONG_ONLY"):
            raise ValueError("Unsupported H0001-r03 identity")
        if value["specification_version"] != "h0001_r03_spec_v3":
            raise ValueError("Unsupported H0001 specification version")
        if value["source"] != {"path": "research/hypotheses/H0001-r03.yaml", "sha256": SOURCE_SHA256}:
            raise ValueError("H0001 source provenance mismatch")
        expected = {section: set() for section, _ in REQUIRED}
        for section, field in (*REQUIRED, *FIXED):
            expected.setdefault(section, set()).add(field)
        expected["engine_capabilities"] = set(ENGINE_FIELDS)
        expected["chart_parity"].add("parity_status")
        for section, fields in expected.items():
            exact(value[section], fields, section)
        exact(value["decisions"], {entry[1] for entry in REQUIRED.values()}, "H0001 decisions")
        for (section, field), (kind, decision, category, choices) in REQUIRED.items():
            record = value[section][field]
            if (record["kind"], record["decision_id"], tuple(record["choices"])) != (kind, decision, choices):
                raise ValueError(f"H0001 field contract changed: {section}.{field}")
            if value["decisions"][decision]["classification"] != category:
                raise ValueError("H0001 blocker classification cannot be downgraded")
            if kind == "integer" and field != "max_adds" and record["value"] != UNRESOLVED and record["value"] < 1:
                raise ValueError("H0001 history/lookback must be positive")
        for (section, field), (kind, known) in FIXED.items():
            if value[section][field] != {"kind": kind, "value": known, "choices": [], "decision_id": None}:
                raise ValueError("Explicit r03/engine fact changed")
        for field in ENGINE_FIELDS:
            record = value["engine_capabilities"][field]
            expected_kind = "timeframe" if field == "base_timeframe" else "text"
            if (record["kind"] != expected_kind or record["value"] == UNRESOLVED
                    or record["decision_id"] is not None or record["choices"]):
                raise ValueError("Explicit engine capability provenance required")
        parity = value["chart_parity"]
        status = parity["parity_status"]
        if (status["kind"], status["choices"], status["decision_id"]) != (
                "enum", ["MISMATCH", "UNVERIFIED", "VERIFIED"], None):
            raise ValueError("Invalid chart parity status contract")
        if status["value"] != "UNVERIFIED" and any(parity[k]["value"] == UNRESOLVED for k in (
                "observed_chart_provider", "observed_1h_boundary", "observed_ema_seed",
                "observed_history_origin", "observed_min_history", "parity_evidence")):
            raise ValueError("Chart parity claim requires observed conventions and evidence")
        machine = value["state_machine"]
        if set(machine["states"]) != set(STATES):
            raise ValueError("H0001 state inventory mismatch")
        validate_signal_lifecycle(machine)
        exact(machine["transitions"], TRANSITIONS, "H0001 transition inventory")
        for key, (a, b, refs) in TRANSITIONS.items():
            transition = machine["transitions"][key]
            condition = transition["condition"]
            if (transition["from"], transition["to"], tuple(transition["prerequisites"])) != (a, b, refs):
                raise ValueError("H0001 candidate transition prerequisites changed")
            if (condition["kind"], condition["decision_id"], condition["choices"]) != (
                    "contract", "H1-STATE-TRANSITIONS", []):
                raise ValueError("Transition must retain its implementation blocker")
            if key in LIFECYCLE_RETURNS and condition != LIFECYCLE_CONDITION:
                raise ValueError("Lifecycle return must reference the existing transition contract")
        for prefix in ("setup_1h", "entry_15m", "exit_1h"):
            method = value["rule_parameters"][prefix + "_relative_transform"]["value"]
            threshold = value["rule_parameters"][prefix + "_downside_threshold" if prefix != "exit_1h"
                                                   else "exit_upper_relative_extreme"]["value"]
            if method == "ROLLING_PERCENTILE" and threshold != UNRESOLVED and not 0 <= threshold <= 1:
                raise ValueError("Percentile threshold must be in [0,1]")

    def _require_engine_compatibility(self, value):
        require_current_engine(value)

    def require_historical_reproduction_ready(self):
        self.require_c1_ready()
        if self.unpack()["chart_parity"]["parity_status"]["value"] != "VERIFIED":
            raise ValueError("Historical reproduction blocked by unverified/mismatched chart parity")

    def require_profitability_ready(self):
        super().require_profitability_ready()
        self.require_historical_reproduction_ready()


def load_h0001(path, *, hypothesis_path=None):
    """Explicit file loader; never rewrite or auto-revise the hypothesis."""
    spec = H0001Specification.load(path)
    if hypothesis_path is not None and sha256(Path(hypothesis_path).read_bytes().replace(b"\r\n", b"\n")).hexdigest() != SOURCE_SHA256:
        raise ValueError("Source hypothesis bytes changed")
    return spec
