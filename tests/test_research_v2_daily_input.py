"""DAILY-INPUT proposal/admission tests, not a classifier or freshness policy."""

from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import subprocess

import pytest
import yaml

from richping.core import calendar, timestamp
from richping.research_v2.contracts import JsonObject, ReplayContext, StrategyState
from richping.research_v2.replay import replay
from richping.research_v2.sessions import EXTENDED, RTH, session_bounds, session_date
from richping.research_v2.strategy.h0001_spec import H0001Specification, load_h0001
from richping.research_v2.strategy.specification import C1, UNRESOLVED
from test_research_v2 import Observer, fixture_data
from test_research_v2_extended import bars, dataset, select_extended_fixture
from test_research_v2_specification import resolve_fixture

ROOT = Path(__file__).resolve().parents[1]
BASE = "4d5d74f716d013e89536955ebe25c2e2c81b43f5"
PHILOSOPHY = "91eff1f2ef9943c9077f79811c651a1455803e67"
DRAFT = ROOT / "research/strategy_specs/H0001-r03-draft.yaml"
PROPOSAL = ROOT / "research/decision_proposals/H0001-daily-input-v1.yaml"
NEW = {"H1-DAILY-PRICE-BASIS": ("feature_contracts", "daily_price_basis"),
       "H1-DAILY-FRESHNESS": ("timeframe_contracts", "daily_freshness")}


def proposal():
    return yaml.safe_load(PROPOSAL.read_text(encoding="utf-8"))


def git_blob(commit, path):
    return subprocess.check_output(["git", "show", commit + ":" + path], cwd=ROOT)


def test_original_philosophy_is_imported_without_semantic_rewriting():
    body = proposal()
    # Pin the fetched original blob's digest without requiring an unrelated
    # commit object to exist in a fresh checkout of this branch.
    original = (ROOT / body["philosophy"]["path"]).read_bytes().replace(b"\r\n", b"\n")
    assert sha256(original).hexdigest() == body["philosophy"]["sha256"] == (
        "e5a88b9d89273591a0655c116ee38b6e1ae7059ed7c39e9248408f4cf64429c8")
    assert body["philosophy"]["source_commit"] == PHILOSOPHY
    assert body["philosophy"]["import"] == "exact_git_blob_no_merge_no_cherry_pick"
    text = original.decode("utf-8")
    for term in ("PRICE_REGIME", "MARKET_REGIME", "MACRO STATE", "point-in-time",
                 "incremental value", "narrative", "2026"):
        assert term in text


def test_only_two_input_decisions_change_the_v5_executable_contract():
    before = H0001Specification.loads(git_blob(BASE, DRAFT.relative_to(ROOT).as_posix()).decode())
    current = load_h0001(DRAFT)
    value = current.unpack()
    assert value["specification_version"] == "h0001_r03_spec_v6"
    assert set(value["decisions"]) - set(before.unpack()["decisions"]) == set(NEW)
    assert len(value["decisions"]) == 78
    assert len(current.unresolved_fields) == 100
    for decision, (section, field) in NEW.items():
        assert current.unresolved_fields[section + "." + field] == {
            "decision_id": decision, "classification": C1}
        assert value["decisions"][decision]["required_for_c1"]
        assert value["decisions"][decision]["required_for_profitability"]
        del value[section][field]
        del value["decisions"][decision]
    value["specification_version"] = "h0001_r03_spec_v5"
    assert value == before.unpack()
    for path in ("research/hypotheses/H0001-r03.yaml",
                 "research/decision_proposals/H0001-daily-price-regime-v1.yaml"):
        assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == git_blob(BASE, path)


@pytest.mark.parametrize("decision", NEW)
def test_each_unresolved_input_contract_independently_blocks_freeze_and_c1(decision):
    value = select_extended_fixture(resolve_fixture(load_h0001(DRAFT), {C1}))
    section, field = NEW[decision]
    value[section][field]["value"] = UNRESOLVED
    spec = H0001Specification.of(value)
    assert spec.blockers(C1) == (decision,)
    with pytest.raises(ValueError, match="C1"):
        spec.require_c1_ready()
    value["status"] = "FROZEN"
    with pytest.raises(ValueError, match="unresolved C1"):
        H0001Specification.of(value)


@pytest.mark.parametrize("omitted", list(NEW.values()))
def test_legacy_v5_readability_does_not_impute_omitted_input_contracts(omitted):
    value = select_extended_fixture(resolve_fixture(load_h0001(DRAFT), {C1}))
    value["status"] = "FROZEN"
    value["specification_version"] = "h0001_r03_spec_v5"
    for decision, (section, field) in NEW.items():
        del value[section][field]
        del value["decisions"][decision]
    legacy = H0001Specification.of(value)
    with pytest.raises(ValueError, match="daily_price_basis"):
        legacy.require_c1_ready()
    # A v6 declaration must have each explicit field, even if all others resolve.
    value = select_extended_fixture(resolve_fixture(load_h0001(DRAFT), {C1}))
    del value[omitted[0]][omitted[1]]
    with pytest.raises(ValueError):
        H0001Specification.of(value)


def test_observed_parity_is_separate_from_a_future_research_choice():
    body = proposal()
    observed, research = (body["series_roles"][role] for role in
                          ("OBSERVED_CHART_SERIES", "RESEARCH_DAILY_SERIES"))
    assert observed["chart_parity"] == "UNVERIFIED"
    assert {observed[k] for k in ("provider", "session", "price_adjustment")} == {UNRESOLVED}
    assert research["observed_chart_parity_required_for_new_research_choice"] is False
    assert {research[k] for k in ("selected_session", "price_basis", "freshness_policy")} == {UNRESOLVED}
    assert "not_a_chart_reproduction_claim" in research["future_selection_provenance"]
    value = select_extended_fixture(resolve_fixture(load_h0001(DRAFT), {C1}))
    value["status"] = "FROZEN"
    spec = H0001Specification.of(value)
    spec.require_c1_ready()  # Ephemeral declarations only, never strategy choices.
    with pytest.raises(ValueError, match="parity"):
        spec.require_historical_reproduction_ready()


@pytest.mark.parametrize("profile", [RTH, EXTENDED])
@pytest.mark.parametrize("defect", ["incomplete", "delayed"])
def test_daily_state_input_is_only_a_complete_delivered_causal_prefix(profile, defect):
    source = fixture_data() if profile == RTH else dataset(bars())
    inputs = source.bars
    if defect == "incomplete":
        changed = replace(source, bars=inputs[:-1])
    else:
        repaired = (*inputs[:-1], replace(inputs[-1], known_at=inputs[-1].known_at + timedelta(hours=2)))
        meta = source.manifest.unpack()
        meta["captured_at"] = repaired[-1].known_at.isoformat()
        changed = replace(source, bars=repaired, manifest=JsonObject.of(meta))
    observer = Observer()
    replay(changed, observer)
    assert all(not v.query(timeframe="Daily") for v in observer.views[:-1])
    if defect == "incomplete":
        assert not observer.views[-1].query(timeframe="Daily")
    else:
        daily = observer.views[-1].query(timeframe="Daily")[0]
        assert daily.known_at == max(b.known_at for b in changed.bars)
        assert daily.end_at == inputs[-1].end_at < daily.known_at
        with pytest.raises(ValueError, match="Future"):
            ReplayContext(daily.end_at, (daily,))


@pytest.mark.parametrize("profile,as_of,expected", [
    (RTH, "2026-10-01T18:00:00+00:00", "2026-09-30"),
    (EXTENDED, "2026-10-01T18:00:00+00:00", "2026-09-30"),
    (RTH, "2026-10-01T20:01:00+00:00", "2026-10-01"),
    (EXTENDED, "2026-10-01T20:01:00+00:00", "2026-09-30"),
    (EXTENDED, "2026-10-02T00:01:00+00:00", "2026-10-01"),
    (RTH, "2026-10-04T18:00:00+00:00", "2026-10-02"),
])
def test_calendar_facts_distinguish_latest_completed_stale_and_absent_inputs(profile, as_of, expected):
    # Contract-level fact fixture, NOT a runtime selector/grace implementation.
    facts = proposal()["freshness_facts"]
    instant = timestamp(as_of)
    sessions = [s.date().isoformat() for s in calendar().sessions_in_range("2026-09-24", session_date(instant))]
    completed = [s for s in sessions if session_bounds(s, profile)[1] <= instant]
    assert completed[-1] == expected
    for available, relation in ((expected, "LATEST_EXPECTED_COMPLETED"),
                                (completed[-2], "BEHIND_EXPECTED_COMPLETED"),
                                (None, "NO_COMPLETED_INPUT")):
        lag = None if available is None else completed.index(expected) - completed.index(available)
        record = {"expected_completed_session": expected, "available_completed_session": available,
                  "freshness_relation": relation, "trading_session_lag": lag,
                  "eligibility_policy": facts["eligibility_policy"]}
        state = StrategyState("freshness_facts_fixture", JsonObject.of(record))
        assert StrategyState.loads(state.dumps()).data.unpack() == record
        assert relation in facts["relation_values"]
        assert lag == (0 if available == expected else None if available is None else 1)
        assert record["eligibility_policy"] == UNRESOLVED
    assert facts["pre_delivery_cause"] == "UNAVAILABLE_CAUSE_UNCONFIRMED"
    assert facts["tolerated_lag_or_grace"] == UNRESOLVED


def test_research_daily_profiles_cannot_be_mixed_in_a_context():
    regular, extended = Observer(), Observer()
    replay(fixture_data(), regular)
    replay(dataset(bars()), extended)
    r, e = (o.views[-1].query(timeframe="Daily")[0] for o in (regular, extended))
    assert r.session == e.session and r.symbol == e.symbol
    assert r.end_at != e.end_at and r.close != e.close
    with pytest.raises(ValueError, match="profile"):
        ReplayContext(e.known_at, (r, e))


@pytest.mark.parametrize("basis", ["raw", "split_adjusted", "dividend_adjusted"])
def test_existing_synthetic_data_capability_does_not_claim_any_real_price_basis(basis):
    source = fixture_data()
    meta = source.manifest.unpack()
    meta["price_basis"] = basis
    with pytest.raises(ValueError, match="synthetic only"):
        replace(source, manifest=JsonObject.of(meta))
    assert proposal()["price_basis_candidates"]["current_engine"]["real_adjustment_adapter"] == "NOT_IMPLEMENTED"


def test_unavailable_input_and_conflicting_price_and_external_axes_keep_their_information():
    body = proposal()
    labels = {"daily_trend_permission": "BULLISH", "daily_exhaustion_state": "EXTENDED",
              "daily_price_shock_state": "ADVERSE_SHOCK", "macro_state": "HOSTILE",
              "sector_leadership_state": "STRONG", "options_flow_state": "UNAVAILABLE",
              "fundamental_state": "UNAVAILABLE"}
    assert set(labels) == set(body["independent_state_layers"])
    state = StrategyState("independent_layers_fixture", JsonObject.of({
        "dated_historical_axes": labels, "current_input_status": "UNAVAILABLE",
        "unavailable_reason": body["freshness_facts"]["pre_delivery_cause"],
        "trade_permission_policy": body["trade_permission_policy"]}))
    restored = StrategyState.loads(state.dumps()).data.unpack()
    assert restored["dated_historical_axes"] == labels
    assert restored["current_input_status"] == "UNAVAILABLE"
    assert restored["dated_historical_axes"]["daily_trend_permission"] != "NOT_BULLISH"
    restored["dated_historical_axes"]["macro_state"] = "UNAVAILABLE"
    assert state.data.unpack()["dated_historical_axes"] == labels
    assert all(restored["dated_historical_axes"][k] == v for k, v in labels.items() if k != "macro_state")
    assert body["unavailable_input_is_not_NOT_BULLISH"] is True
    assert body["trend_candidates"]["change_allowed"] is False
    assert set(body["trend_candidates"]["dependencies"]) == {"DLP-A", "DLP-B", "DLP-C"}


def test_input_proposal_preserves_provenance_and_early_close_blocker_without_classifier():
    body = proposal()
    assert body["status"] == "PROPOSED_NOT_FROZEN"
    assert body["profitability"] == "NOT_TESTED" and body["hypothesis_status"] == "DRAFT"
    assert body["intraday_session"] == "RTH_EXTENDED"
    assert body["early_close_blocker"] == "V2-D_BLOCKER"
    for profile in (RTH, EXTENDED):
        if profile == RTH:
            assert session_bounds("2024-11-29", profile)[1] == timestamp("2024-11-29T18:00:00+00:00")
        else:
            with pytest.raises(ValueError, match="early-close"):
                session_bounds("2024-11-29", profile)
    assert {"symbol", "session_date", "session_profile", "input_end_at", "known_at",
            "causal_input_hash", "source_vintage_id", "price_adjustment_convention",
            "feature_specification_hash", "daily_input_contract_hash"} <= set(body["provenance_fields"])
    assert body["provenance_boundary"]["mixed_series_profile_or_basis"] == "reject_not_coerce"
    assert body["provenance_boundary"]["past_state_or_snapshot_rewrite"] == "forbidden"
