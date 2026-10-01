"""Semantic declaration/fixture tests. No real action transform or selector.

Calendar calculations verify fixture boundaries using existing primitives only;
these tests do not implement or attest to H0001 runtime data eligibility.
"""

from pathlib import Path
import subprocess

import pytest
import yaml

from richping.core import calendar, timestamp, digest
from richping.research_v2.contracts import JsonObject, StrategyState, payload
from richping.research_v2.sessions import RTH, EXTENDED, session_bounds, session_date, bar_profile
from richping.research_v2.strategy.capabilities import current_engine, require_daily_session_capability
from richping.research_v2.strategy.h0001_spec import H0001Specification, load_h0001
from richping.research_v2.strategy.specification import C1, PERFORMANCE, OPTIONAL
from test_research_v2 import Observer, fixture_data
from test_research_v2_extended import bars, dataset
from richping.research_v2.replay import replay
from test_research_v2_specification import input_audit_draft

ROOT = Path(__file__).resolve().parents[1]
BASE = "382bd202ed394fbe5b2247af0752a4d29efaaa26"
DRAFT = ROOT / "research/strategy_specs/H0001-r03-draft.yaml"
RECORD = ROOT / "research/decision_records/H0001-daily-input-freeze-v1.yaml"
CHOICES = {
    "H1-DAILY-SESSION": ("timeframe_contracts", "daily_session_policy", "RTH_DAILY"),
    "H1-DAILY-PRICE-BASIS": ("feature_contracts", "daily_price_basis", "PIT_SPLIT_ADJUSTED_OHLC"),
    "H1-DAILY-FRESHNESS": ("timeframe_contracts", "daily_freshness", "LATEST_EXPECTED_COMPLETED_SESSION_REQUIRED"),
}


def input_freeze_draft():
    return H0001Specification.loads(subprocess.check_output([
        "git", "show", "f517374f66b75c84a0ea025ced91cacf866b2b8a:" + DRAFT.relative_to(ROOT).as_posix(),
    ], cwd=ROOT).decode("utf-8"))


def record():
    return yaml.safe_load(RECORD.read_text(encoding="utf-8"))


def parameters(field, section):
    contract = input_freeze_draft().unpack()[section][field]["value"]
    assert contract["version"] == "v1"
    return {k: v["value"] for k, v in contract["parameters"].items()}


def test_only_three_root_decisions_resolve_without_inventory_manipulation():
    before, after = input_audit_draft(), input_freeze_draft()
    old, new = before.unpack(), after.unpack()
    assert old["specification_version"] == "h0001_r03_spec_v6"
    assert new["specification_version"] == "h0001_r03_spec_v7"
    assert len(old["decisions"]) == len(new["decisions"]) == 78
    assert new["decisions"] == old["decisions"]  # No new IDs/reclassification.
    expected_removed = {section + "." + field for section, field, _ in CHOICES.values()}
    assert set(before.unresolved_fields) - set(after.unresolved_fields) == expected_removed
    assert not (set(after.unresolved_fields) - set(before.unresolved_fields))
    assert len(before.unresolved_fields) == 100 and len(after.unresolved_fields) == 97
    assert [len(before.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)] == [49, 17, 7]
    assert [len(after.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)] == [46, 17, 7]
    assert sum(len(after.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)) == 70
    assert set(before.blockers(C1)) - set(after.blockers(C1)) == set(CHOICES)
    for decision, (section, field, selected) in CHOICES.items():
        declaration = new[section][field]["value"]
        choice = declaration if isinstance(declaration, str) else declaration["parameters"]["semantic_choice"]["value"]
        assert choice == record()["decisions"][decision]["selected"] == selected
        assert record()["decisions"][decision]["status"] == "RESOLVED"
        old[section][field]["value"] = declaration
    old["specification_version"] = new["specification_version"]
    assert old == new  # All other strategy/engine/chart contracts untouched.
    assert after.specification_hash != before.specification_hash
    assert after.specification_hash == record()["executable_spec"]["canonical_sha256"]
    assert H0001Specification.loads(after.text, format="json").specification_hash == after.specification_hash


def test_rth_selection_keeps_generic_extended_daily_and_unverified_chart():
    spec = input_freeze_draft()
    assert require_daily_session_capability(spec.unpack()) == current_engine(RTH)
    value = spec.unpack()
    value["timeframe_contracts"]["daily_session_policy"]["value"] = "EXTENDED_DAILY"
    assert require_daily_session_capability(value) == current_engine(EXTENDED)
    observed = record()["series_roles"]["OBSERVED_CHART_SERIES"]
    assert {observed[k] for k in ("provider", "session", "price_adjustment")} == {"UNRESOLVED"}
    assert observed["chart_parity"] == spec.unpack()["chart_parity"]["parity_status"]["value"] == "UNVERIFIED"
    decision = record()["decisions"]["H1-DAILY-SESSION"]
    assert not decision["predictive_superiority_claim"] and not decision["chart_parity_claim"]


def test_pit_split_contract_excludes_total_return_and_future_action_knowledge():
    p = parameters("daily_price_basis", "feature_contracts")
    s = record()["pit_split_semantics"]
    assert p["split_eligibility"] == "split_effective_at_lte_as_of_AND_required_action_evidence_known_at_lte_as_of"
    assert s["eligible_action"] == "effective_at_lte_as_of_AND_required_action_evidence_known_at_lte_as_of"
    assert s["announced_but_not_effective"] == "forbidden_until_effective"
    assert s["effective_but_not_known"] == "forbidden_until_required_evidence_is_known"
    assert s["future_known_factor_on_past_as_of"] == s["old_state_snapshot_rewrite"] == "forbidden"
    assert s["split_types"] == ["stock_split", "reverse_split"]
    assert p["ohlc_basis"] == "all_OHLC_consistently_rebased_to_as_of_split_units"
    assert p["history_rebase"] == "causal_rebase_after_effective_using_only_then_known_factors_no_past_snapshot_rewrite"
    assert p["total_return_series"] is s["total_return_adjustment"] is s["reinvestment_adjustment"] is False
    assert p["cash_distribution_treatment"] == "preserve_actual_ex_date_price_gap_no_total_return_reinvestment_adjustment"
    assert s["dividend_distribution"] == "preserve_actual_underlying_ex_date_gap"
    assert s["future_total_return_variant"] == "separate_hypothesis_or_experiment"


def test_missing_required_split_evidence_forbids_raw_fallback_and_backdated_known_at():
    p = parameters("daily_price_basis", "feature_contracts")
    s = record()["pit_split_semantics"]
    assert s["required_action_evidence_unavailable"] == "Daily_input_and_state_UNAVAILABLE"
    assert s["raw_fallback"] == "forbidden"
    assert p["required_action_evidence_unavailable"] == "Daily_input_and_state_UNAVAILABLE_no_raw_fallback"
    assert p["state_input_known_at"] == s["state_input_known_at"] == "maximum_bar_action_and_other_actual_transform_input_known_at"
    assert s["synthetic_unadjusted_implements_this_choice"] is False


@pytest.mark.parametrize("example", record()["freshness_semantics"]["fixtures_only_not_runtime_selector"])
def test_strict_freshness_calendar_contract_fixtures(example):
    instant = timestamp(example["as_of"])
    local_date = session_date(instant)
    dates = calendar().sessions_in_range("2024-11-20" if local_date < "2025-01-01" else "2026-09-01", local_date)
    completed = [s.date().isoformat() for s in dates if session_bounds(s.date().isoformat(), RTH)[1] <= instant]
    assert completed[-1] == example["expected"]
    # Assert the recorded contract outcomes; no production selector is invoked.
    assert (example["delivered"] == example["expected"]) == (example["input_status"] == "FRESH")
    p = parameters("daily_freshness", "timeframe_contracts")
    assert p["expected_session"] == "latest_RTH_DAILY_calendar_trading_session_with_official_close_lte_as_of"
    assert p["eligibility"] == "latest_causally_delivered_Daily_session_date_equals_expected_session"
    assert p["previous_daily_fallback"] is False
    assert p["numeric_lag_or_grace"] == "NONE_strict_calendar_session_equality"
    assert "not_NOT_BULLISH" in p["mismatch_or_absent"]


def test_mixed_timeframe_identity_is_separate_transport_only_and_join_is_missing():
    regular, extended = Observer(), Observer()
    replay(fixture_data(), regular)
    replay(dataset(bars()), extended)
    separate = {"Daily": regular.views[-1].query(timeframe="Daily")[0],
                "1H": extended.views[-1].query(timeframe="1H")[-1],
                "15m": extended.views[-1].query(timeframe="15m")[-1]}
    identity = {tf: {"session_profile": bar_profile(bar),
                     "known_at": bar.known_at.isoformat(), "hash": digest(payload(bar))}
                for tf, bar in separate.items()}
    transported = StrategyState("separate_series_fixture_not_join_adapter", JsonObject.of(identity))
    assert StrategyState.loads(transported.dumps()).data.unpack() == identity
    assert len({item["hash"] for item in identity.values()}) == 3
    assert identity["Daily"]["session_profile"] == RTH
    assert identity["1H"]["session_profile"] == identity["15m"]["session_profile"] == EXTENDED
    mixed = record()["mixed_timeframe_semantics"]
    assert mixed["series"]["Daily"]["session_profile"] == RTH
    assert mixed["series"]["1H"]["session_profile"] == mixed["series"]["15m"]["session_profile"] == EXTENDED
    assert mixed["concatenated_candle_stream"] == "forbidden"
    assert mixed["join"] == "as_of_only_preserving_each_series_identity_known_at_and_causal_hash"
    assert record()["capability_blockers"]["V2-D_MIXED_PROFILE_AS_OF_JOIN"]["status"] == "NOT_IMPLEMENTED"


def test_preserved_draft_proposals_independent_axes_and_capability_blockers():
    spec, body = input_freeze_draft(), record()
    assert spec.unpack()["status"] == body["hypothesis"]["status"] == "DRAFT"
    assert body["hypothesis"]["profitability"] == "NOT_TESTED"
    for gate in (spec.require_c1_ready, spec.require_profitability_ready, spec.plugin_specification):
        with pytest.raises(ValueError):
            gate()
    for path in ("research/hypotheses/H0001-r03.yaml", "docs/RESEARCH_PHILOSOPHY.md",
                 "research/decision_proposals/H0001-daily-input-v1.yaml",
                 "research/decision_proposals/H0001-daily-price-regime-v1.yaml"):
        assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT)
    trend = yaml.safe_load((ROOT / body["trend_proposal"]["path"]).read_text(encoding="utf-8"))
    assert trend["selected_trend_candidate"] == trend["family_freeze"] == "UNRESOLVED"
    assert all(set(c["parameters"].values()) == {"UNRESOLVED"} for c in trend["candidates"].values())
    assert body["independent_axes"]["resolved_scope"] == "daily_trend_permission_input_series_semantics_only"
    assert body["capability_ids_are_strategy_decision_ids"] is False
    gaps = body["capability_blockers"]
    assert all(g["status"] == "NOT_IMPLEMENTED" for k, g in gaps.items() if k != "early_close")
    assert gaps["early_close"]["status"] == "V2-D_BLOCKER"
    with pytest.raises(ValueError, match="early-close"):
        session_bounds("2024-11-29", EXTENDED)
