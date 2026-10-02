"""Design preservation and synthetic primitive audit; no economic evaluation."""

from itertools import product
from pathlib import Path
import subprocess

import pytest
import yaml

from richping.research_v2.aggregation import CompletedAggregator
from richping.research_v2.contracts import JsonObject, ReplayContext, StrategyState
from richping.research_v2.features import (
    MACDSpec, PercentileSpec, ZScoreSpec, macd_series,
    rolling_percentile, rolling_zscore,
)
from richping.research_v2.sessions import EXTENDED, EXTENDED_CONTINUITY as EC
from richping.research_v2.strategy.h0001_spec import load_h0001
from richping.research_v2.strategy.specification import C1, PERFORMANCE, OPTIONAL
from test_research_v2_extended import bars

ROOT = Path(__file__).resolve().parents[1]
BASE = "3a046021939b24068f4c95526496814c983af713"
PROPOSAL = ROOT / "research/decision_proposals/H0001-1h-relative-setup-v1.yaml"
SPEC = ROOT / "research/strategy_specs/H0001-r03-draft.yaml"


def proposal():
    return yaml.safe_load(PROPOSAL.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", [
    "research/hypotheses/H0001-r03.yaml",
    "research/strategy_specs/H0001-r03-draft.yaml",
    "research/decision_records/H0001-daily-input-freeze-v1.yaml",
    "research/decision_records/H0001-daily-trend-freeze-v1.yaml",
    "research/decision_records/H0001-daily-trend-readiness-remediation-v1.yaml",
    "research/decision_records/H0001-daily-blocker-freeze-v1.yaml",
    "docs/RESEARCH_PHILOSOPHY.md",
    "docs/H0001_DAILY_INPUT_CONTRACT.md",
    "docs/H0001_DAILY_PRICE_RESEARCH.md",
    "docs/H0001_DAILY_BLOCKER_RESEARCH.md",
])
def test_upstream_contracts_remain_identical_to_basis(path):
    original = subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT)
    assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == original


def test_v10_daily_payload_hash_inventory_and_draft_admission_unchanged():
    body = proposal()
    spec = load_h0001(SPEC)
    draft = spec.unpack()
    assert draft["specification_version"] == body["executable_spec_version"] == "h0001_r03_spec_v10"
    assert spec.specification_hash == body["executable_spec_sha256"]
    assert draft["status"] == body["hypothesis_status"] == "DRAFT"
    assert body["execution_readiness"] == "BLOCKED_ON_DECISIONS"
    assert body["profitability"] == "NOT_TESTED"
    assert draft["chart_parity"]["parity_status"]["value"] == body["chart_parity"] == "UNVERIFIED"
    for decision in ("H1-DAILY-LONG", "H1-DAILY-BLOCKER"):
        assert decision not in spec.blockers(C1)
    assert set(body["ownership"]["remain_UNRESOLVED"]) <= set(spec.blockers(C1))
    assert set(body["ownership"]["untouched_15m"]) <= set(spec.blockers(C1))
    inv = body["inventory_at_basis_and_after"]
    counts = [len(spec.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)]
    assert counts == [inv["C1"], inv["performance"], inv["optional"]] == [44, 17, 7]
    assert sum(counts) == inv["unresolved_ids"] == 68
    assert len(draft["decisions"]) == inv["decisions"] == 78
    assert len(draft["decisions"]) - sum(counts) == inv["resolved_ids"] == 10
    assert len(spec.unresolved_fields) == inv["unresolved_paths"] == 95
    assert body["new_executable_decision_ids"] == body["new_executable_unresolved_paths"] == []
    assert not inv["proposal_questions_enter_executable_inventory"]
    for gate in (spec.require_c1_ready, spec.require_profitability_ready, spec.plugin_specification):
        with pytest.raises(ValueError):
            gate()


def test_exact_eight_r03_statements_and_no_new_setup_evidence():
    body = proposal()["source_boundary"]
    source = yaml.safe_load((ROOT / proposal()["hypothesis_path"]).read_text(encoding="utf-8"))
    assert body["direct_refs"] == [
        "rules.setup[0]", "rules.setup[1]", "rules.setup[2]",
        "rules.trigger[0]", "rules.trigger[1]", "unknowns[4]", "unknowns[5]", "unknowns[6]",
    ]
    assert [s["ref"] for s in body["direct_statements"]] == body["direct_refs"]
    for statement in body["direct_statements"]:
        path, index = statement["ref"].rstrip("]").split("[")
        value = source
        for part in path.split("."):
            value = value[part]
        assert value[int(index)] == statement["text"]
    assert {"1H_GC_required", "MACD_minimum_confirmation", "price_low_confirmation", "RSI_oversold",
            "volume_spike", "divergence", "4H_filter", "macro_condition", "options_flow",
            "price_structure_trigger"} == set(body["unsupported_setup_rules"])


def test_independent_setup_context_is_not_entry_or_price_bottom():
    body = proposal()
    assert body["role"]["raw"] == "SETUP_CONTEXT"
    assert not any(body["role"][k] for k in ("entry_signal", "BUY_on_setup", "same_predicate_as_15m_trigger"))
    state = body["raw_state_contract"]
    assert state["vocabulary"] == ["INACTIVE", "DOWNSIDE_EXTREME", "UNAVAILABLE"]
    assert state["non_equivalences"] == {"DOWNSIDE_EXTREME": ["BUY", "PRICE_BOTTOM"],
                                        "INACTIVE": ["BEARISH"], "UNAVAILABLE": ["INACTIVE"]}
    assert state["materialization_proposal"] == "independent_raw_1H_record_before_Daily_policy_join"
    assert not any(state[k] for k in ("classifier_implemented_here", "Daily_change_resets_raw_state",
                                     "lifecycle_is_raw_state", "unresolved_definition_is_measured_state"))
    assert {"daily_trend_permission", "daily_exhaustion_state", "macro", "options", "sector",
            "fundamentals", "volume", "outcomes"} <= set(body["input_boundary"]["excluded"])


@pytest.mark.parametrize("trend,exhaustion,raw", list(product(
    ("BULLISH", "UNAVAILABLE"), ("NORMAL", "EXTENDED"),
    ("INACTIVE", "DOWNSIDE_EXTREME", "UNAVAILABLE"))))
def test_ungated_raw_state_survives_immutable_product_transport(trend, exhaustion, raw):
    # Assigned labels only; no classifier/lifecycle evaluator implied.
    axes = {"daily_trend_permission": trend, "daily_exhaustion_state": exhaustion, "raw_1H": raw}
    before = StrategyState("1h_setup_design_transport_v1", JsonObject.of(axes))
    restored = StrategyState.loads(before.dumps())
    assert restored == before and restored.data.unpack() == axes
    updated = restored.data.unpack()
    updated["daily_trend_permission"] = "NOT_BULLISH"
    after = StrategyState(before.version, JsonObject.of(updated))
    assert after.data.unpack()["raw_1H"] == raw
    assert before.data.unpack() == axes


def test_exact_field_method_and_conceptual_families_no_ranking():
    body = proposal()
    assert body["status"] == "PROPOSED_NOT_FROZEN" and body["basis_commit"] == BASE
    fields = body["field_boundary"]
    assert fields["initial_fields"] == {"F1": "MACD_LINE"}
    assert "normalization_not_independent_field" in fields["F2_review_only"]
    assert {"histogram", "signal_line", "MACD_slope", "price_return", "RSI", "volume", "OBV", "divergence"} == set(fields["excluded"])
    candidates = body["method_candidates"]
    assert [candidates[r]["method"] for r in ("R1", "R2", "R3")] == ["ROLLING_PERCENTILE", "ROLLING_ZSCORE", "MACD_ATR"]
    required = {"field", "units", "window_meaning", "readiness", "scale_semantics",
                "outlier_behavior", "cross_symbol_meaning", "threshold_form", "leakage_risk"}
    for key in ("R1", "R2", "R3"):
        assert required <= set(candidates[key])
        assert candidates[key]["field"] == "MACD_LINE"
    assert candidates["R2"]["Gaussian_tail_probability_interpretation"] == "FORBIDDEN"
    assert not candidates["R3"]["own_historical_distribution_rank"]
    assert candidates["selected_canonical"] == candidates["selected_comparison_candidate"] == "UNRESOLVED"
    matrix = body["conceptual_matrix"]
    assert {key for key in matrix if len(key) == 2 and key.startswith("S")} == {"S0", "S1", "S2", "S3"}
    assert required <= set(matrix["S0"])
    assert "not_live_strategy_candidate" in matrix["S0"]["role"]
    assert [matrix[s]["method_ref"] for s in ("S1", "S2", "S3")] == ["R1", "R2", "R3"]
    assert matrix["ranking"] == "NONE" and matrix["selected_tuple"] == "UNRESOLVED"
    assert not matrix["S0_fabricates_READY_or_INACTIVE"]


def test_prior_only_gap_matches_actual_spec_admission():
    conventions = proposal()["window_conventions"]
    assert conventions["CURRENT_INCLUSIVE"]["supported"]
    assert not conventions["PRIOR_ONLY"]["supported"]
    assert not conventions["PRIOR_ONLY"]["new_engine_implemented_here"]
    assert conventions["selected"] == "UNRESOLVED"
    assert conventions["future_observations"] == "FORBIDDEN"
    # Small fixture windows check generic support, not H1 parameters.
    assert PercentileSpec(4, 4).include_current is True
    assert PercentileSpec(4, 4).ties == "midrank"
    for ddof in (0, 1):
        assert ZScoreSpec(4, 4, ddof).zero_variance == "undefined"
        with pytest.raises(ValueError):
            ZScoreSpec(4, 4, ddof, include_current=False)
    with pytest.raises(ValueError):
        PercentileSpec(4, 4, include_current=False)


def test_session_bands_polarity_cutoff_equality_and_lifetime_remain_choices():
    body = proposal()
    session = body["session_observations"]
    assert session["session"] == "RTH_EXTENDED" and session["base"] == "15m"
    assert session["standard_day_completed_1H_count"] == 16
    assert session["completed_only"] and session["current_incomplete_1H"] == "FORBIDDEN"
    assert session["lookback_unit"] == "completed_selected_1H_observations"
    assert session["calendar_hours_or_days_substitution"] == "FORBIDDEN"
    assert "V2-D_BLOCKER_UNCHANGED" in session["unsupported_early_close"]
    bands = body["lookback_bands"]
    assert {"SHORT", "MEDIUM", "LONG"} <= set(bands)
    assert bands["selected_W"] == bands["selected_m"] == "UNRESOLVED"
    assert not bands["calendar_band_is_runtime_window"]
    polarity = body["polarity_candidates"]
    assert polarity["POL0"] == "relative_downside_predicate_only"
    assert polarity["POL1"] == "relative_downside_predicate_AND_MACD_LINE_LT_zero"
    assert polarity["selected"] == "UNRESOLVED"
    threshold = body["threshold_comparator"]
    assert threshold["STRICT"] == "LT" and threshold["INCLUSIVE"] == "LE"
    assert threshold["selected_cutoff"] == threshold["selected_comparator"] == "UNRESOLVED"
    assert threshold["rolling_minimum_as_threshold"] == threshold["final_future_extrema_or_price_bottom_matching"] == "FORBIDDEN"
    for key in ("R1", "R2", "R3"):
        assert "no_numeric_value" in threshold[key]
    lifetimes = body["lifetime_candidates"]
    assert [lifetimes[l]["name"] for l in ("L0", "L1", "L2")] == [
        "CONTEMPORANEOUS_ONLY", "LATCH_UNTIL_1H_RECOVERY", "FIXED_EXPIRY"]
    assert lifetimes["champion"] == lifetimes["L1"]["recovery_boundary"] == lifetimes["L2"]["K"] == "UNRESOLVED"
    assert not lifetimes["price_low_MACD_low_15m_reversal_same_timestamp_required"]
    assert not body["ownership"]["H1_GC_required_entry"]


@pytest.fixture(scope="module")
def extended_hour_inputs():
    aggregator = CompletedAggregator(("1H",), profile=EXTENDED)
    hours = []
    # Nine consecutive standard sessions; only synthetic prices, no outcomes.
    for day in ("2024-03-11", "2024-03-12", "2024-03-13", "2024-03-14", "2024-03-15",
                "2024-03-18", "2024-03-19", "2024-03-20", "2024-03-21"):
        for bar in bars(day):
            hours.extend(b for b in aggregator.accept(bar, bar.known_at) if b.timeframe == "1H")
    assert len(hours) == 9 * 16
    return tuple(hours)


@pytest.mark.parametrize("W,m", [(4, 4), (7, 7), (7, 3)])
@pytest.mark.parametrize("method", ["percentile", "zscore"])
def test_generic_extended_hour_readiness_indexing_without_selecting_W(extended_hour_inputs, W, m, method):
    inherited = proposal()["inherited_MACD"]
    M = inherited["min_history"]
    macd_spec = MACDSpec(12, 26, 9, M, continuity=EC)
    transform = (lambda s: rolling_percentile(s, PercentileSpec(W, m, continuity=EC))
                 if method == "percentile" else
                 rolling_zscore(s, ZScoreSpec(W, m, 0, continuity=EC)))
    for N, expected in ((M + W - 2, "NOT_READY"), (M + W - 1, "READY")):
        inputs = extended_hour_inputs[:N]
        context = ReplayContext(inputs[-1].known_at, inputs)
        series = macd_series(context, "ALFA", "1H", macd_spec, field="macd_line")
        assert all(p.status == "NOT_READY" for p in series.points[:M - 1])
        assert series.points[M - 1].status == "READY"
        assert series.points[M - 1].end_at == inputs[M - 1].end_at
        selected = series.points[-W:]
        assert sum(p.status == "READY" for p in selected) == W - (expected == "NOT_READY")
        result = transform(series)
        assert result.status == expected
        assert result.input_count == W
        if expected == "NOT_READY":
            assert result.reason == "unavailable_input"
        else:
            assert result.values.unpack()
    assert proposal()["readiness"]["current_inclusive_full_window_first_N"] == "M_plus_W_minus_1"
    assert proposal()["readiness"]["prior_only_full_window_first_N"].startswith("M_plus_W")
    assert proposal()["readiness"]["numeric_final_readiness"] == "UNRESOLVED"


def test_no_execution_search_or_outcome_work_and_complete_future_audit_requirements():
    body = proposal()
    for key in ("historical_outcome_lookup", "current_outcome_lookup", "historical_performance_backtest", "current_chart_analysis"):
        assert body[key] == "NOT_RUN"
    assert body["performance_information_used"] == "NONE"
    assert body["production_paper_order_connection"] == "NONE"
    assert body["multiple_testing"]["Cartesian_product_search"] == "FORBIDDEN"
    assert body["multiple_testing"]["max_canonical_tuples"] == body["multiple_testing"]["max_additional_comparison_candidates"] == 1
    assert "S0_is_counted" in body["multiple_testing"]["comparator_budget"]
    assert body["multiple_testing"]["current_SOXX_NOK_parameter_selection"] == "FORBIDDEN"
    assert body["required_denominators"] == [
        "total_eligible_completed_1H_observations", "MACD_READY_count", "relative_transform_READY_count",
        "UNAVAILABLE_count", "downside_extreme_count", "Daily_permission_active_count", "Daily_blocker_NORMAL_count",
        "Daily_allowed_AND_1H_extreme_count", "setup_activation_count", "setup_duration",
        "setup_expiry_cancellation_count", "15m_trigger_opportunities_inside_setup",
        "15m_trigger_opportunities_outside_setup", "completed_entries", "no_entry_setups",
        "later_MAE_MFE_forward_outcomes", "sample_suppression_ratio",
    ]
    assert body["denominator_semantics"]["zero_denominator"] == "null"
    assert body["trace_requirements"]["implementation"].startswith("NOT_IMPLEMENTED")
    assert len(body["trace_requirements"]["fields"]) == 17
    assert {"H0001_1H_setup_classifier", "setup_lifetime_evaluator", "setup_activation_cancellation_logger",
            "15m_trigger_coupling", "actual_H0001_transition_predicate", "prior_only_reference_query_engine"} <= set(body["capability_audit"]["missing"])
    # Checks changed source paths only; never loads a database or outcome artifact.
    assert subprocess.check_output(["git", "diff", BASE, "--name-only", "--", "richping", "research/hypotheses",
                                    "research/strategy_specs", "research/decision_records", "research/experiments"], cwd=ROOT) == b""
