"""Proposal preservation and causal primitive evidence, never performance tests."""

from pathlib import Path
import subprocess

import pytest
import yaml

from richping.research_v2.contracts import JsonObject, ReplayContext, StrategyState
from richping.research_v2.features import (
    MACDSpec, PercentileSpec, ZScoreSpec, macd_series,
    rolling_percentile, rolling_zscore,
)
from richping.research_v2.sessions import EXTENDED_CONTINUITY as EC
from richping.research_v2.strategy.h0001_spec import H0001Specification
from richping.research_v2.strategy.specification import C1, PERFORMANCE, OPTIONAL
from test_research_v2_extended import bars

ROOT = Path(__file__).resolve().parents[1]
BASE = "58e67178113b757a675858af1b4f31fca8508c60"
SPEC_PATH = "research/strategy_specs/H0001-r03-draft.yaml"
PROPOSAL_PATH = "research/decision_proposals/H0001-15m-entry-trigger-v1.yaml"


def proposal():
    return yaml.safe_load((ROOT / PROPOSAL_PATH).read_text(encoding="utf-8"))


def basis(path):
    return subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT)


@pytest.mark.parametrize("path", [
    "research/hypotheses/H0001-r03.yaml",
    "research/decision_records/H0001-daily-input-freeze-v1.yaml",
    "research/decision_records/H0001-daily-trend-freeze-v1.yaml",
    "research/decision_records/H0001-daily-trend-readiness-remediation-v1.yaml",
    "research/decision_records/H0001-daily-blocker-freeze-v1.yaml",
    "research/decision_records/H0001-1h-relative-setup-freeze-v1.yaml",
    "docs/H0001_DAILY_INPUT_CONTRACT.md",
    "docs/H0001_DAILY_PRICE_RESEARCH.md",
    "docs/H0001_DAILY_BLOCKER_RESEARCH.md",
    "docs/H0001_1H_RELATIVE_SETUP_RESEARCH.md",
])
def test_frozen_upstream_and_r03_preserved(path):
    assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == basis(path)


def test_canonical_v11_payload_hash_inventory_and_admission_preserved():
    p = proposal()
    before = H0001Specification.loads(basis(SPEC_PATH).decode())
    # Immutable proposal v11 evidence; v12 has its own exact nine-root delta test.
    after = H0001Specification.loads(subprocess.check_output(
        ["git", "show", "8f0611f:" + SPEC_PATH], cwd=ROOT).decode())
    assert before.unpack() == after.unpack()
    assert after.specification_hash == p["executable_spec"]["canonical_sha256"]
    assert after.unpack()["specification_version"] == p["executable_spec"]["version"]
    assert after.unpack()["status"] == p["hypothesis_status"] == "DRAFT"
    assert p["profitability"] == "NOT_TESTED"
    assert p["execution_readiness"] == "BLOCKED_ON_DECISIONS"
    assert p["chart_parity"] == "UNVERIFIED"
    inv = p["inventory_at_basis_and_after"]
    counts = [len(after.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)]
    assert counts == [inv["C1"], inv["performance"], inv["optional"]] == [38, 17, 7]
    assert sum(counts) == inv["unresolved_ids"] == 62
    assert len(after.unpack()["decisions"]) == inv["decisions"] == 78
    assert 78 - sum(counts) == inv["resolved_ids"] == 16
    assert len(after.unresolved_fields) == inv["unresolved_paths"] == 89
    assert len(p["ownership"]["target_UNRESOLVED"]) == 8
    assert set(p["ownership"]["target_UNRESOLVED"] + p["ownership"]["other_UNRESOLVED"]) <= set(after.blockers(C1))
    assert p["new_executable_decision_ids"] == p["new_executable_unresolved_paths"] == []
    for gate in (after.require_c1_ready, after.require_profitability_ready, after.plugin_specification):
        with pytest.raises(ValueError):
            gate()


def test_exact_r03_source_statements_and_related_evidence_paths():
    source = yaml.safe_load((ROOT / proposal()["hypothesis_path"]).read_text(encoding="utf-8"))
    boundary = proposal()["source_boundary"]
    assert boundary["direct_refs"] == ["rules.trigger[1]", "observations[0]", "observations[2]", "unknowns[6]", "unknowns[9]"]
    def lookup(ref):
        path, index = ref.rstrip("]").split("[")
        value = source
        for key in path.split("."):
            value = value[key]
        return value[int(index)]
    assert [s["ref"] for s in boundary["direct_statements"]] == boundary["direct_refs"]
    for statement in boundary["direct_statements"]:
        assert lookup(statement["ref"]) == statement["text"]
    for key in ("related_required_data_refs", "related_leakage_risk_refs"):
        assert boundary[key] and all(lookup(ref) for ref in boundary[key])
    assert len(boundary["unsupported_frozen_rules"]) == 6
    assert boundary["literal_T3"] == "semantic_observation_only_not_selection"


def test_raw_layers_methods_and_no_numeric_selection():
    p = proposal()
    assert list(p["role_layers"].values()) == ["RAW_RELATIVE_STATE", "REVERSAL_EVIDENCE", "TEMPORAL_COMPOSITION", "ENTRY_CANDIDATE"]
    assert p["raw_state"]["vocabulary"] == ["INACTIVE", "DOWNSIDE_EXTREME", "UNAVAILABLE"]
    assert p["raw_state"]["non_equivalences"] == {"DOWNSIDE_EXTREME": ["BUY", "PRICE_BOTTOM", "REVERSAL"], "UNAVAILABLE": ["INACTIVE"]}
    assert p["field_boundary"]["primary_candidate"] == "MACD_LINE"
    assert set(p["field_boundary"]["excluded"]) == {"histogram", "signal_line", "MACD_slope", "RSI", "stochastic", "volume", "OBV", "divergence", "price_return"}
    methods = p["method_candidates"]
    assert [methods[r]["method"] for r in ("R1", "R2", "R3")] == ["ROLLING_PERCENTILE", "ROLLING_ZSCORE", "MACD_ATR"]
    required = {"units", "current_inclusive", "readiness", "ties_ddof", "outlier_sensitivity", "scale_invariance", "own_history_distribution", "known_at", "continuity", "feature_hash"}
    for key in ("R1", "R2", "R3"):
        assert required <= set(methods[key])
    assert methods["R3"]["own_history_distribution"] is False
    assert methods["selected"] == p["polarity_candidates"]["selected"] == "UNRESOLVED"
    assert p["session_lookback"]["selected_W"] == p["session_lookback"]["selected_m"] == "UNRESOLVED"
    assert p["threshold"]["value"] == p["threshold"]["comparator"] == "UNRESOLVED"
    assert p["readiness"]["selected_final_N"] == "UNRESOLVED"
    assert p["readiness"]["M"] == p["inherited_MACD"]["min_history"] == 130
    assert p["session_lookback"]["standard_completed_15m_per_session"] == len(bars()) == 64
    assert p["session_lookback"]["unit"] == "completed_selected_15m_observations"
    assert p["session_lookback"]["inherit_1H_method_W_cutoff_polarity_K"] == "FORBIDDEN"


def test_gc_zero_line_price_composition_and_temporal_boundaries():
    p = proposal()
    assert [p["gc_candidates"][g]["name"] for g in ("G1", "G2")] == ["STRICT_CROSS", "PRIOR_EQUALITY_ALLOWED"]
    assert p["gc_candidates"]["event"] != p["gc_candidates"]["persistent_relation"]
    assert p["gc_candidates"]["event_persistence"] == "FORBIDDEN"
    assert {"Z0", "Z1", "Z2"} <= set(p["zero_line_candidates"])
    assert [p["price_reversal_candidates"][r]["name"] for r in ("PR0", "PR1", "PR2")] == ["UNUSED", "COMPLETED_PRICE_RECLAIM", "CAUSAL_CONFIRMED_SWING_REVERSAL"]
    assert p["price_reversal_candidates"]["PR1"]["reference_level_formula"] == "UNRESOLVED"
    assert p["price_reversal_candidates"]["PR2"]["exact_reversal_mapping"] == "UNRESOLVED"
    assert p["price_reversal_candidates"]["exit_HH_HL_LH_valid_HL_auto_inheritance"] == "FORBIDDEN"
    assert {"T1", "T2", "T3", "T4"} <= set(p["conjunction_candidates"])
    assert [p["temporal_candidates"][c]["name"] for c in ("C0", "C1", "C2")] == ["CONTEMPORANEOUS", "EXTREME_ARMED_THEN_REVERSAL", "LAST_EXTREME_REFRESH_GRACE"]
    assert not p["temporal_candidates"]["same_bar_requirement_automatic"]
    for key in ("gc_candidates", "zero_line_candidates", "price_reversal_candidates", "conjunction_candidates", "temporal_candidates"):
        assert p[key]["selected"] == "UNRESOLVED"
    for key in ("C1", "C2"):
        assert p["temporal_candidates"][key]["K"] == "UNRESOLVED"
    assert p["temporal_candidates"]["inherit_1H_K2"] == "FORBIDDEN"


@pytest.mark.parametrize("previous,current,G1,G2", [
    (-1, 1, True, True), (0, 1, False, True), (1, 1, False, False),
    (-1, 0, False, False), (0, 0, False, False), (-1, -1, False, False),
])
def test_candidate_cross_algebra_not_a_strategy_predicate(previous, current, G1, G2):
    # Hand-assigned MACD-minus-signal spreads; no prices, signals or strategy.
    assert (previous < 0 and current > 0) == G1
    assert (previous <= 0 and current > 0) == G2


@pytest.mark.parametrize("method", ["percentile", "zscore"])
@pytest.mark.parametrize("W", [4, 7])
def test_actual_completed_15m_generic_readiness_indexing(method, W):
    inputs = bars("2024-03-11") + bars("2024-03-12") + bars("2024-03-13")
    M = proposal()["inherited_MACD"]["min_history"]
    spec = MACDSpec(12, 26, 9, M, continuity=EC)
    for N, status in ((M + W - 2, "NOT_READY"), (M + W - 1, "READY")):
        selected = inputs[:N]
        series = macd_series(ReplayContext(selected[-1].known_at, selected), "ALFA", "15m", spec, field="macd_line")
        assert series.points[M - 2].status == "NOT_READY"
        assert series.points[M - 1].status == "READY"
        assert sum(p.status == "READY" for p in series.points[-W:]) == W - (status == "NOT_READY")
        result = (rolling_percentile(series, PercentileSpec(W, W, continuity=EC)) if method == "percentile"
                  else rolling_zscore(series, ZScoreSpec(W, W, 0, continuity=EC)))
        assert result.status == status
        assert result.input_count == W
    assert proposal()["readiness"]["current_inclusive_full_window"] == "M_plus_W_minus_1"


def test_causal_scope_counterfactual_trace_and_ownership_requirements():
    p = proposal()
    causal = p["causality"]
    for key in ("incomplete_15m", "future_bars_features_pivots", "deferred_execution_of_past_reversal_event"):
        assert causal[key] == "FORBIDDEN"
    timing = causal["equal_known_at"]
    assert timing["owner"] == "H1-DECISION-TIMING" and timing["selected"] == "UNRESOLVED"
    assert {"A", "B"} <= set(timing)
    assert p["coupling"]["inactive_EXPIRED_CANCELLED_setup"] == "no_initial_entry_candidate"
    assert p["coupling"]["old_rejected_event_on_later_setup_activation"] == "FORBIDDEN"
    assert not p["coupling"]["candidate_is_order_or_fill"]
    assert p["scope"]["candidate_type"] == p["trace"]["candidate_type"] == "INITIAL_ENTRY"
    assert p["scope"]["position"] == "FLAT_only"
    assert {"failed_first_reversal", "deeper_extreme", "add", "re_entry", "1H_GC_role"} <= set(p["scope"]["excluded_design"])
    assert not p["ownership"]["temporal_new_ID_needed"]
    assert "nested_C_K" in p["ownership"]["H1-M15-CONJUNCTION"]
    for key in ("raw", "overlap", "reversal", "temporal", "candidate", "later"):
        assert p["denominators"][key]
    assert p["denominators"]["zero_denominator"] == "null"
    assert "preserve_PENDING_UNRESOLVED_missing" in p["denominators"]["missing_outcomes"]
    required = {"symbol", "as_of", "source_15m_end", "source_15m_known_at", "macd_line", "signal_line", "relative_value", "relative_method", "relative_version", "relative_hash", "threshold", "comparator", "raw_downside_state", "GC_event_state", "GC_definition_version", "GC_definition_hash", "price_reversal_state", "reversal_definition_version", "reversal_definition_hash", "temporal_armed_state", "last_extreme_at", "reversal_at", "latency_observations", "conjunction_result", "H1_setup_episode_ref", "H1_setup_episode_hash", "Daily_permission_refs", "candidate_type", "trigger_contract_version", "trigger_contract_hash", "input_hash", "source_vintage"}
    assert required <= set(p["trace"]["fields"])
    assigned = {"raw_state": "UNAVAILABLE", "candidate_type": "INITIAL_ENTRY", "Daily_ref": "fixture_only"}
    original = StrategyState("15m_design_transport_v1", JsonObject.of(assigned))
    restored = StrategyState.loads(original.dumps())
    changed = restored.data.unpack()
    changed["raw_state"] = "INACTIVE"
    assert StrategyState(original.version, JsonObject.of(changed)) != original
    assert original.data.unpack() == assigned


def test_no_strategy_implementation_outcome_search_or_execution_changes():
    p = proposal()
    assert p["status"] == "PROPOSED_NOT_FROZEN" and p["basis_commit"] == BASE
    for key in ("historical_outcome_lookup", "current_outcome_lookup", "performance_backtest", "current_SOXX_NOK_analysis"):
        assert p[key] == "NOT_RUN"
    assert p["performance_information_used"] == "NONE"
    assert p["production_paper_order_connection"] == "NONE"
    assert p["multiple_testing"]["Cartesian_product_search"] == "FORBIDDEN"
    assert p["multiple_testing"]["selected_tuple"] == "UNRESOLVED"
    assert p["conceptual_matrix"]["ranking"] == "NONE"
    required = {"r03_fidelity", "additional_parameters", "expected_delay", "causal_observability", "implementation_capability", "overfit_multiple_testing_cost"}
    for e in ("E0", "E1", "E2", "E3", "E4"):
        assert required <= set(p["conceptual_matrix"][e])
    assert p["conceptual_matrix"]["E0"]["role"] == "denominator_counterfactual_only"
    assert not p["capability_audit"]["strategy_implementation_added_here"]
    assert all((ROOT / path).is_file() for path in p["capability_audit"]["sources"])
    # This immutable proposal made no implementation change at its own head.
    # Subsequent authorized data work is tested separately, not retroactively
    # attributed to the proposal.
    assert subprocess.check_output(["git", "diff", BASE, "7197fe3", "--name-only", "--", "richping", "research/hypotheses", "research/experiments", "research/decision_records"], cwd=ROOT) == b""
    assert subprocess.check_output(["git", "diff", "7197fe3", "8f0611f", "--name-only", "--", "richping/research_v2/strategy", "research/hypotheses", "research/experiments", "research/decision_records"], cwd=ROOT) == b""
