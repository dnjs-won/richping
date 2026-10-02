"""Bounded design and transport only; no exhaustion calculation or outcomes."""

from itertools import product
from pathlib import Path
import subprocess

import pytest
import yaml

from richping.research_v2.contracts import JsonObject, StrategyState
from richping.research_v2.features import PercentileSpec, ZScoreSpec
from richping.research_v2.strategy.daily_trend import CANONICAL, minimum_history
from richping.research_v2.strategy.h0001_spec import H0001Specification, load_h0001
from richping.research_v2.strategy.specification import C1, PERFORMANCE, OPTIONAL

ROOT = Path(__file__).resolve().parents[1]
BASE = "819e6ffebb11e9cb0b5f08bc7d98e4523c98249a"
PROPOSAL = ROOT / "research/decision_proposals/H0001-daily-blocker-v1.yaml"


def proposal():
    return yaml.safe_load(PROPOSAL.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", [
    "research/hypotheses/H0001-r03.yaml",
    "research/strategy_specs/H0001-r03-draft.yaml",
    "research/decision_records/H0001-daily-input-freeze-v1.yaml",
    "research/decision_records/H0001-daily-trend-freeze-v1.yaml",
    "research/decision_records/H0001-daily-trend-readiness-remediation-v1.yaml",
    "research/decision_proposals/H0001-daily-price-regime-v1.yaml",
    "docs/RESEARCH_PHILOSOPHY.md",
])
def test_existing_canonical_sources_are_immutable_at_proposal_basis(path):
    original = subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT)
    # Executable v9 is the immutable proposal-basis snapshot; current v10 has
    # an independent freeze/delta test. Other source artifacts stay unchanged.
    current = (subprocess.check_output(["git", "show", "a25b43a:" + path], cwd=ROOT)
               if path == "research/strategy_specs/H0001-r03-draft.yaml"
               else (ROOT / path).read_bytes().replace(b"\r\n", b"\n"))
    assert current == original


def test_canonical_v9_trend_readiness_inventory_and_blocker_remain_unchanged():
    body = proposal()
    spec = H0001Specification.loads(subprocess.check_output([
        "git", "show", BASE + ":" + body["executable_spec_path"]], cwd=ROOT).decode("utf-8"))
    draft = spec.unpack()
    assert draft["specification_version"] == body["executable_spec_version"] == "h0001_r03_spec_v9"
    assert spec.specification_hash == body["executable_spec_sha256"]
    assert draft["rule_parameters"]["daily_long_permission"]["value"] == CANONICAL.contract
    assert CANONICAL.ema_spec.span == 50
    assert CANONICAL.ema_spec.min_history == minimum_history() == 174
    assert CANONICAL.contract["parameters"]["slope_lag_observations"]["value"] == 5
    assert "H1-DAILY-LONG" not in spec.blockers(C1)
    assert "H1-DAILY-BLOCKER" in spec.blockers(C1)
    assert draft["rule_parameters"]["daily_exhaustion_blocker"]["value"] == "UNRESOLVED"
    assert draft["status"] == body["hypothesis_status"] == "DRAFT"
    assert body["profitability"] == "NOT_TESTED"
    assert draft["chart_parity"]["parity_status"]["value"] == body["chart_parity"] == "UNVERIFIED"
    counts = [len(spec.blockers(category)) for category in (C1, PERFORMANCE, OPTIONAL)]
    inventory = body["inventory_at_basis_and_after"]
    assert len(draft["decisions"]) == inventory["decisions"] == 78
    assert counts == [45, 17, 7]
    assert sum(counts) == inventory["unresolved_ids"] == 69
    assert len(draft["decisions"]) - sum(counts) == inventory["resolved_ids"] == 9
    assert len(spec.unresolved_fields) == inventory["unresolved_paths"] == 96
    assert not inventory["proposal_unknowns_in_executable_count"]
    for gate in (spec.require_c1_ready, spec.require_profitability_ready, spec.plugin_specification):
        with pytest.raises(ValueError):
            gate()


def test_source_extraction_is_exact_and_context_does_not_select_a_daily_rule():
    body = proposal()["source_boundary"]
    hypothesis = yaml.safe_load((ROOT / proposal()["hypothesis_path"]).read_text(encoding="utf-8"))
    for item in body["direct_statements"]:
        path, index = item["ref"].rstrip("]").split("[")
        source = hypothesis
        for part in path.split("."):
            source = source[part]
        assert item["text"] == source[int(index)]
    assert len(body["direct_statements"]) == 4
    assert body["B1_B2_provenance"] == "NEW_BOUNDED_RESEARCH_OPERATIONALIZATIONS_NOT_RECOVERED_HISTORICAL_RULES"
    assert set(body["unsupported_as_existing_blocker_evidence"]) == {
        "rising_rates", "rising_oil", "dollar", "VIX", "NQ_reversal", "option_strike_GEX",
        "sector_rotation", "fundamental_deterioration", "single_Daily_drop", "news_event",
    }


def test_only_B0_B1_B2_exist_with_distinct_fields_and_no_selected_tuple():
    body = proposal()
    assert body["status"] == "PROPOSED_NOT_FROZEN"
    assert body["basis_commit"] == BASE
    assert body["executable_decision_status"] == "UNRESOLVED"
    assert body["new_executable_decision_ids"] == body["new_executable_unresolved_paths"] == []
    candidates = body["candidate_family"]
    assert set(candidates) == set(body["family_boundary"]["only_initial_members"]) == {"B0", "B1", "B2"}
    assert candidates["B0"]["field"] == "NONE" and candidates["B0"]["policy_correspondence"] == "P0"
    assert candidates["B1"]["field"] == "macd_line"
    assert candidates["B2"]["field"] == "histogram"
    assert candidates["B1"]["field"] != candidates["B2"]["field"]
    assert candidates["B2"]["polarity_scope"] == "positive_histogram_no_histogram_absolute_threshold_selected"
    for key in ("B1", "B2"):
        assert set(candidates[key]["parameters"].values()) == {"UNRESOLVED"}
    assert body["family_boundary"]["ranking"] == "NONE"
    assert body["family_boundary"]["extra_indicators_or_conjunctions"] == "FORBIDDEN"
    assert body["family_boundary"]["DLP_C"] == "DEFERRED_SEPARATE_TREND_GEOMETRY_NOT_BLOCKER_MEMBER"
    assert {"RSI", "HH_HL", "macro", "options", "price_shock"} <= set(body["family_boundary"]["excluded"])


def test_raw_vocabulary_and_policy_are_separate_with_no_implicit_safe_or_sell():
    body = proposal()
    state = body["independent_state_contract"]
    assert state["raw_vocabulary"] == ["NORMAL", "EXTENDED", "UNAVAILABLE"]
    assert state["non_equivalences"] == {
        "EXTENDED": ["BEARISH", "SELL"], "NORMAL": ["SAFE"], "UNAVAILABLE": ["NORMAL"],
    }
    assert not state["classifiers_implemented_here"]
    assert state["overwrite_other_axis"] == state["forced_reset_on_trend_change"] == "FORBIDDEN"
    nested = body["decision_contract_proposal"]
    assert nested["existing_id"] == "H1-DAILY-BLOCKER" and not nested["split_IDs_now"]
    assert set(nested["state_definition"].values()) == {"UNRESOLVED"}
    assert set(nested["policy"].values()) == {"UNRESOLVED"}
    assert "separate_nested_state_and_policy" in nested["provenance_tracking"]


def axis_record(axis, label):
    """Assigned illustrative labels, never a classifier or policy evaluator."""
    return {"state": label, "status": "NOT_READY" if label == "UNAVAILABLE" else "READY",
            "reason": "unavailable_fixture_only" if label == "UNAVAILABLE" else None,
            "known_at": "2024-03-11T20:00:00+00:00", "input_hash": "fixture:" + axis}


@pytest.mark.parametrize("trend,exhaustion", list(product(
    ("BULLISH", "NOT_BULLISH", "UNAVAILABLE"), ("NORMAL", "EXTENDED", "UNAVAILABLE"))))
def test_all_trend_exhaustion_combinations_and_axis_updates_survive_transport(trend, exhaustion):
    contract = proposal()["independent_state_contract"]
    labels = dict(zip(contract["axes"], (trend, exhaustion, "NORMAL", "HOSTILE", "STRONG", "UNKNOWN", "UNKNOWN")))
    records = {axis: axis_record(axis, label) for axis, label in labels.items()}
    state = StrategyState("blocker_proposal_transport_fixture_v1", JsonObject.of({"axes": records}))
    restored = StrategyState.loads(state.dumps())
    assert restored == state
    assert {axis: record["state"] for axis, record in restored.data.unpack()["axes"].items()} == labels
    # Every axis is independently mutable in a new snapshot; the others survive.
    for axis in contract["axes"]:
        updated = restored.data.unpack()
        updated["axes"][axis] = axis_record(axis, "UNAVAILABLE")
        after = StrategyState(state.version, JsonObject.of(updated))
        for other in contract["axes"]:
            if other != axis:
                assert after.data.unpack()["axes"][other] == records[other]
        assert restored == state
    assert records["daily_exhaustion_state"]["state"] == exhaustion


@pytest.mark.parametrize("exhaustion,shock", [("EXTENDED", "NORMAL"), ("NORMAL", "ADVERSE_SHOCK"), ("EXTENDED", "ADVERSE_SHOCK")])
def test_shock_and_macro_examples_do_not_override_exhaustion(exhaustion, shock):
    # Transport requirement only: the future classifier does not exist.
    axes = {axis: axis_record(axis, label) for axis, label in {
        "daily_trend_permission": "BULLISH", "daily_exhaustion_state": exhaustion,
        "daily_price_shock_state": shock, "macro_state": "HOSTILE",
    }.items()}
    raw = {"axes": axes, "external_research_context": {"daily_return": -0.08, "rates_bp": 30, "oil_return": 0.05, "VIX": "spike"}}
    state = StrategyState("non_classifier_shock_fixture_v1", JsonObject.of(raw))
    assert StrategyState.loads(state.dumps()).data.unpack()["axes"] == axes
    inputs = proposal()["input_contract"]
    assert inputs["economic_inputs"] == ["completed_Daily_close_history"]
    assert inputs["scale_inputs_if_ATR"] == ["completed_Daily_high_low_close_history"]
    assert {"daily_price_shock_state", "macro_state", "sector_leadership_state", "options_flow_state", "fundamental_state"} <= set(inputs["excluded_inputs"])
    assert "no_direct_shock_override" in inputs["shock_price_effect"]
    assert proposal()["independent_state_contract"]["price_shock_definition"] == "DEFERRED_SEPARATE_DECISION_RESEARCH"


def test_transform_audit_pins_actual_generic_conventions_without_selecting_H1():
    body = proposal()
    audit = body["transform_audit"]
    assert set(audit) >= {"ROLLING_PERCENTILE", "ROLLING_ZSCORE", "MACD_ATR"}
    required = {"scale_invariance", "cross_symbol", "outliers", "distribution_assumption",
                "current_observation", "ties", "min_history", "rolling_window", "known_at", "readiness"}
    for method in ("ROLLING_PERCENTILE", "ROLLING_ZSCORE", "MACD_ATR"):
        assert required <= set(audit[method])
    assert not audit["audit_is_selection"]
    assert audit["selected_canonical"] == audit["selected_comparator"] == "UNRESOLVED"
    assert PercentileSpec(4, 4).include_current is True
    assert PercentileSpec(4, 4).ties == "midrank"
    assert audit["ROLLING_PERCENTILE"]["version"] == PercentileSpec(4, 4).version
    assert audit["ROLLING_ZSCORE"]["version"] == ZScoreSpec(4, 4, 0).version
    # Small numbers here check generic API admission, not a H0001 parameter tuple.
    for make in (lambda: PercentileSpec(4, 4, include_current=False),
                 lambda: ZScoreSpec(4, 4, 0, include_current=False)):
        with pytest.raises(ValueError):
            make()
    window = body["window_convention_audit"]
    assert window["current_inclusive"]["V2_B_supported"]
    assert not window["prior_only"]["V2_B_supported"]
    assert window["selected_for_H1_blocker"] == "UNRESOLVED"
    assert window["future_observations"] == "FORBIDDEN"
    assert "does_not_answer" in audit["MACD_ATR"]["semantic_gap"]


def test_MACD_inherited_readiness_is_not_trend_or_relative_window_selection():
    body = proposal()
    draft = load_h0001(ROOT / body["executable_spec_path"]).unpack()
    macd = body["inherited_MACD_capability"]
    assert [macd[k] for k in ("fast", "slow", "signal")] == [12, 26, 9]
    assert macd["min_history"] == draft["feature_contracts"]["macd_min_history_daily"]["value"] == 130
    assert "unchanged_EMA50" in macd["minimum_history_174"]
    counts = body["history_count_audit"]
    assert "129_plus_W" in counts["current_MACD_series_full_window"]
    assert "not_implemented" in counts["prior_only_full_window_proposed"]
    assert not counts["computational_readiness_is_economic_evidence"]


def test_P0_P1_P2_P3_policy_scope_excludes_forced_exit_and_defers_sizing():
    body = proposal()
    policies = body["policy_candidates"]
    assert {key: value["action"] for key, value in policies.items()} == {
        "P0": "OBSERVE_ONLY", "P1": "BLOCK_NEW_ENTRY_ONLY",
        "P2": "BLOCK_NEW_ENTRY_AND_ADD", "P3": "REDUCE_SIZE",
    }
    assert all(value["forced_exit"] is False for value in policies.values())
    assert policies["P1"]["existing_hold_exit"] == policies["P2"]["existing_hold_exit"] == "unaffected_by_exhaustion"
    assert policies["P3"]["initial_C1_feasibility"] == "DEFERRED_PERFORMANCE_PORTFOLIO_DEPENDENCY"
    assert {"H1-SIZING", "H1-EXPOSURE"} <= set(policies["P3"]["dependencies"])
    assert policies["P3"]["reduction_size"] == "UNRESOLVED"
    assert body["policy_boundary"]["champion"] == "UNRESOLVED"
    assert body["policy_boundary"]["forced_EXIT"] == "EXCLUDED_FROM_INITIAL_FAMILY"
    assert "1H_EXIT_WATCH_plus_15m_price_structure" in body["policy_boundary"]["existing_exit_owner"]


def test_conceptual_experiments_no_outcome_lookup_or_Cartesian_search():
    body = proposal()
    for field in ("historical_performance_backtest", "historical_outcome_lookup", "current_outcome_lookup", "current_chart_analysis"):
        assert body[field] == "NOT_RUN"
    assert body["performance_information_used"] == "NONE"
    assert body["production_paper_behavior_change"] == "NONE"
    experiment = body["conceptual_experiments"]
    assert experiment["status"] == "BOUNDED_DESIGN_ONLY_NOT_EXECUTABLE_REGISTRATION"
    assert experiment["experiment_refs"] == [] and experiment["selected_tuple"] == "UNRESOLVED"
    assert [experiment[e] for e in ("E0", "E1", "E2")] == [
        {"trend": "canonical_DLP_B", "blocker": b} for b in ("B0", "B1", "B2")]
    assert experiment["DLP_C_or_trend_sweep"] == "FORBIDDEN"
    multiple = body["multiple_testing"]
    assert multiple["Cartesian_product_search"] == "FORBIDDEN"
    assert multiple["dimensions"] == ["field", "transform", "lookback", "threshold", "action_policy"]
    assert multiple["retain_trials"] == ["failed", "null", "inconclusive"]
    assert not multiple["after_cost_win_rate_from_few_survivors_is_alpha"]
    # Actual proposal diff must not introduce a runtime/backtest/experiment writer.
    assert subprocess.check_output(["git", "diff", BASE, "a25b43a", "--name-only", "--", "richping", "research/experiments"], cwd=ROOT) == b""


def test_complete_denominator_and_counterfactual_requirements_remain_non_executable():
    body = proposal()
    assert set(body["required_future_diagnostics"]) == {
        "total_Daily_observations", "trend_BULLISH_observations", "exhaustion_NORMAL_count",
        "exhaustion_EXTENDED_count", "exhaustion_UNAVAILABLE_count", "H0001_setup_opportunities_before_blocker",
        "blocker_removed_setup_count", "actual_signal_count", "completed_trades", "capital_exposure_time",
        "turnover", "after_cost_return", "MAE", "MFE", "drawdown",
        "blocked_trades_counterfactual_forward_outcome", "sample_suppression_ratio",
    }
    counterfactual = body["counterfactual_requirements"]
    assert counterfactual["implementation"] == "NOT_IMPLEMENTED" and counterfactual["retain_blocked_opportunities"]
    assert counterfactual["decision_example"] == "BLOCKED_BY_DAILY_EXHAUSTION"
    assert counterfactual["counterfactual_signal_example"] == {"would_have_entered_without_blocker": True}
    assert "setup_only_not_necessarily" in counterfactual["stage_distinction"]
    assert "PENDING_UNRESOLVED" in counterfactual["missing_outcomes"]
    assert "no_future_label" in counterfactual["forward_label_timing"]
    assert "zero_denominator_null" in body["diagnostic_semantics"]["sample_suppression_ratio"]
    assert body["capability_audit"]["early_close"] == "V2-D_BLOCKER_UNCHANGED"
    assert not body["capability_audit"]["primitive_exists_means_H0001_rule_selected"]
    assert {"exhaustion_classifier", "blocker_policy_evaluator", "H0001_counterfactual_signal_logger"} <= set(body["capability_audit"]["absent"])
