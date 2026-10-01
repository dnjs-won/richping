"""H0001 session scope regressions; synthetic evidence, no strategy decisions."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import subprocess

import pytest

from richping.core import open_at, close_at
from richping.research_v2.contracts import JsonObject
from richping.research_v2.features import MACDSpec, macd_series
from richping.research_v2.replay import replay
from richping.research_v2.sessions import RTH, EXTENDED
from richping.research_v2.strategy.capabilities import (
    current_engine, require_session_capability, require_daily_session_capability,
)
from richping.research_v2.strategy.h0001_spec import H0001Specification, load_h0001
from richping.research_v2.strategy.specification import C1, PERFORMANCE, OPTIONAL, UNRESOLVED
from test_research_v2 import Observer, fixture_data
from test_research_v2_extended import bars, dataset, select_extended_fixture
from test_research_v2_specification import resolve_fixture, prior_decision_inventory

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "research/strategy_specs/H0001-r03-draft.yaml"
BASE = "1b3361a5f7c84765210f4f8b627ed87cbb977a7b"


def test_session_scope_changes_only_one_decision_and_one_unresolved_path():
    before = H0001Specification.loads(subprocess.check_output([
        "git", "show", BASE + ":research/strategy_specs/H0001-r03-draft.yaml",
    ], cwd=ROOT).decode("utf-8"))
    current = load_h0001(DRAFT)
    old, new = before.unpack(), current.unpack()
    assert prior_decision_inventory(old) == prior_decision_inventory(new)
    assert set(new["decisions"]) - set(old["decisions"]) == {"H1-DAILY-SESSION"}
    assert len(new["decisions"]) == 76
    assert current.unresolved_fields == {
        **before.unresolved_fields,
        "timeframe_contracts.daily_session_policy": {
            "decision_id": "H1-DAILY-SESSION", "classification": C1},
    }
    assert [len(current.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)] == [47, 17, 7]
    frames = dict(new["timeframe_contracts"])
    daily = frames.pop("daily_session_policy")
    assert frames == old["timeframe_contracts"]
    assert daily == {"kind": "enum", "value": UNRESOLVED,
                     "choices": ["EXTENDED_DAILY", "RTH_DAILY"], "decision_id": "H1-DAILY-SESSION"}
    decision = new["decisions"]["H1-DAILY-SESSION"]
    assert decision["candidate_choices"] == ["EXTENDED_DAILY", "RTH_DAILY"]
    assert decision["required_for_c1"] and decision["required_for_profitability"]
    for section in ("feature_contracts", "engine_capabilities", "rule_parameters", "state_machine",
                    "state_machine_parameters", "execution_requirements", "research_requirements",
                    "optional_extensions", "chart_parity", "source"):
        assert new[section] == old[section]
    assert new["chart_parity"]["parity_status"]["value"] == "UNVERIFIED"
    assert new["status"] == "DRAFT"
    assert current.specification_hash != before.specification_hash
    original = subprocess.check_output([
        "git", "cat-file", "--filters", BASE + ":research/hypotheses/H0001-r03.yaml"], cwd=ROOT)
    assert (ROOT / "research/hypotheses/H0001-r03.yaml").read_bytes() == original


def test_intraday_extended_and_daily_unresolved_are_valid_but_not_c1_ready():
    spec = load_h0001(DRAFT)
    assert require_session_capability(spec.unpack()) == current_engine(EXTENDED)
    with pytest.raises(ValueError, match="H1-DAILY-SESSION"):
        require_daily_session_capability(spec.unpack())
    # Isolate Daily as the sole remaining C1 blocker; other choices are ephemeral.
    value = select_extended_fixture(resolve_fixture(spec, {C1}))
    value["timeframe_contracts"]["daily_session_policy"]["value"] = UNRESOLVED
    isolated = H0001Specification.of(value)
    assert isolated.blockers(C1) == ("H1-DAILY-SESSION",)
    assert require_session_capability(isolated.unpack()) == current_engine(EXTENDED)
    with pytest.raises(ValueError, match="C1"):
        isolated.require_c1_ready()
    value["status"] = "FROZEN"
    with pytest.raises(ValueError, match="unresolved C1"):
        H0001Specification.of(value)


@pytest.mark.parametrize("daily,profile", [("RTH_DAILY", RTH), ("EXTENDED_DAILY", EXTENDED)])
def test_daily_choice_is_independent_of_extended_intraday_admission(daily, profile):
    value = select_extended_fixture(resolve_fixture(load_h0001(DRAFT), {C1}))
    value["timeframe_contracts"]["daily_session_policy"]["value"] = daily
    value["status"] = "FROZEN"
    spec = H0001Specification.of(value)
    assert require_session_capability(spec.unpack()) == current_engine(EXTENDED)
    assert require_daily_session_capability(spec.unpack()) == current_engine(profile)
    spec.require_c1_ready()


def test_legacy_frozen_spec_cannot_infer_daily_from_intraday():
    value = select_extended_fixture(resolve_fixture(load_h0001(DRAFT), {C1}))
    value["status"] = "FROZEN"
    value["specification_version"] = "h0001_r03_spec_v4"
    del value["timeframe_contracts"]["daily_session_policy"]
    del value["decisions"]["H1-DAILY-SESSION"]
    legacy = H0001Specification.of(value)
    require_session_capability(legacy.unpack())
    with pytest.raises(ValueError, match="H1-DAILY-SESSION"):
        legacy.require_c1_ready()


def test_daily_series_have_independent_ohlcv_availability_and_causal_prefixes():
    inputs = bars()
    day = inputs[0].session
    regular_inputs = tuple(replace(b, dataset_id="fixture-v1", provenance=JsonObject())
                           for b in inputs if b.start_at >= open_at(day) and b.end_at <= close_at(day))
    extended, regular = Observer(), Observer()
    replay(dataset(inputs), extended)
    replay(fixture_data(bars=regular_inputs), regular)
    e = extended.views[-1].query(timeframe="Daily")[0]
    r = regular.views[-1].query(timeframe="Daily")[0]
    # Identical prices in the overlapping RTH inputs, distinct series semantics.
    assert (r.open, r.high, r.low, r.close, r.volume) == (122, 150, 120, 148, 1157)
    assert (e.open, e.high, e.low, e.close, e.volume) == (100, 166, 98, 164, 2656)
    assert r.start_at == open_at(day) and r.end_at == r.known_at == close_at(day)
    assert e.start_at == inputs[0].start_at and e.end_at == e.known_at == inputs[-1].end_at
    assert all(not v.query(timeframe="Daily") for v in extended.views[:-1])
    assert all(not v.query(timeframe="Daily") for v in regular.views[:-1])
    series_by_profile = {}
    for observer, profile in ((regular, RTH), (extended, EXTENDED)):
        assert all(b.known_at <= v.as_of for v in observer.views for b in v.bars)
        spec = MACDSpec(12, 26, 9, 1, continuity=current_engine(profile)["continuity"])
        series = macd_series(observer.views[-1], "ALFA", "Daily", spec, field="macd_line")
        assert series.points[-1].status == "READY"
        assert series.input_hash
        series_by_profile[profile] = series
    assert series_by_profile[RTH].input_hash != series_by_profile[EXTENDED].input_hash
    assert series_by_profile[RTH].source != series_by_profile[EXTENDED].source
    # Future after-hours price changes affect only Extended Daily; no prefix rewrite.
    changed = Observer()
    replay(dataset((*inputs[:-1], replace(inputs[-1], high=900, close=800))), changed)
    assert changed.views[:-1] == extended.views[:-1]
    assert changed.views[-1].query(timeframe="Daily")[0].close == 800
    assert regular.views[-1].query(timeframe="Daily")[0] == r
    # A delayed last constituent cannot make Extended Daily available at 20:00.
    delayed = Observer()
    replay(dataset((*inputs[:-1], replace(inputs[-1], known_at=inputs[-1].known_at + timedelta(hours=1)))), delayed)
    assert delayed.views[:-1] == extended.views[:-1]
    final = delayed.views[-1].query(timeframe="Daily")[0]
    assert final.known_at == e.known_at + timedelta(hours=1)
    assert final.end_at == e.end_at
