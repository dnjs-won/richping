"""Proposal/transport tests only; no evaluated regime, chosen threshold or alpha."""

from dataclasses import replace
from datetime import timedelta
from itertools import product
from pathlib import Path
import subprocess

import pytest
import yaml

from richping.core import digest
from richping.research_v2.contracts import JsonObject, StrategyState
from richping.research_v2.replay import replay
from richping.research_v2.strategy.h0001_spec import load_h0001
from richping.research_v2.strategy.specification import C1, PERFORMANCE, OPTIONAL
from test_research_v2 import Observer, fixture_data
from test_research_v2_extended import bars, dataset
from test_research_v2_specification import at

ROOT = Path(__file__).resolve().parents[1]
BASE = "63b815598576c2bd8a865adb503e193ff9e9f664"
PROPOSAL = ROOT / "research/decision_proposals/H0001-daily-price-regime-v1.yaml"
AXES = ("daily_trend_permission", "daily_exhaustion_state", "daily_price_shock_state")


def proposal():
    return yaml.safe_load(PROPOSAL.read_text(encoding="utf-8"))


def test_proposal_is_bounded_and_cannot_silently_resolve_executable_decisions():
    body = proposal()
    assert body["status"] == "PROPOSED_NOT_FROZEN"
    assert body["basis_commit"] == BASE
    assert body["profitability"] == "NOT_TESTED" and body["chart_parity"] == "UNVERIFIED"
    assert body["daily_session_selection"] == body["selected_trend_candidate"] == "UNRESOLVED"
    assert body["family_freeze"] == "UNRESOLVED"
    assert body["parameter_sweep"] == "NONE_AUTHORIZED"
    assert body["daily_session_candidates"] == ["RTH_DAILY", "EXTENDED_DAILY"]
    assert body["intraday_session_selection"] == "RTH_EXTENDED"
    assert set(body["candidates"]) == {"DLP-A", "DLP-B", "DLP-C"}
    assert body["candidates"]["DLP-B"]["shares_ema_parameters_with"] == "DLP-A"
    for record in body["candidates"].values():
        assert set(record["parameters"].values()) == {"UNRESOLVED"}
        assert record["calculation_available"] and not record["rule_evaluator_implemented"]
        assert "VARIANT" in record["evidence_status"]
    assert body["early_close_blocker"] == "V2-D_BLOCKER"
    assert body["new_executable_decision_ids"] == body["new_executable_unresolved_paths"] == []
    for path in (body["hypothesis_path"], body["executable_spec_path"]):
        original = subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT)
        assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == original
    source_bytes = subprocess.check_output([
        "git", "cat-file", "--filters", BASE + ":" + body["hypothesis_path"]], cwd=ROOT)
    assert (ROOT / body["hypothesis_path"]).read_bytes() == source_bytes
    spec = load_h0001(ROOT / body["executable_spec_path"])
    assert len(spec.unpack()["decisions"]) == 76 and len(spec.unresolved_fields) == 98
    assert [len(spec.blockers(c)) for c in (C1, PERFORMANCE, OPTIONAL)] == [47, 17, 7]
    assert spec.specification_hash == "ab0c1136d47bf1ce6b46ff7e46824b59cf715d28db93bf665b77477a8f0a50e6"
    with pytest.raises(ValueError):
        spec.require_c1_ready()


def test_decision_bundles_reference_real_decisions_and_explicit_proposal_unknowns():
    body = proposal()
    spec = load_h0001(ROOT / body["executable_spec_path"])
    assert set(body["decision_bundles"]) == {"DAILY-INPUT", "DAILY-TREND", "DAILY-AXES-POLICY"}
    for bundle in body["decision_bundles"].values():
        assert set(bundle["existing_decisions"]) <= set(spec.unpack()["decisions"])
        for path in bundle["unresolved_paths"]:
            assert at(body, path) == "UNRESOLVED"
    # Freezing later must hash the whole proposal including an unknown parameter;
    # editing a tuple or a session cannot keep the same canonical proposal identity.
    before = digest(body)
    changed = proposal()
    changed["candidates"]["DLP-A"]["parameters"]["ema_span_n"] = "synthetic_test_only"
    assert digest(changed) != before


def axis_record(label, axis):
    """Illustrative values only; no threshold/classification is computed."""
    available = label != "UNAVAILABLE"
    return {"state": label, "status": "READY" if available else "NOT_READY",
            "reason": None if available else "definition_unresolved_fixture_only",
            "input_end_at": "2024-03-11T20:00:00+00:00" if available else None,
            "known_at": "2024-03-11T20:00:00+00:00" if available else None,
            "input_hash": "fixture:" + axis,
            "feature_specification_hash": "proposal_fixture_no_classifier",
            "session_profile": "XNYS_RTH"}


@pytest.mark.parametrize("labels", list(product(
    ("BULLISH", "NOT_BULLISH", "UNAVAILABLE"),
    ("NORMAL", "EXTENDED", "UNAVAILABLE"),
    ("NORMAL", "ADVERSE_SHOCK", "UNAVAILABLE"),
)))
def test_product_state_transport_preserves_every_combination_and_independent_updates(labels):
    body = proposal()["state_representation"]
    assert set(body["axes"]) == set(AXES)
    assert body["status"] == "PROPOSED_VOCABULARY_NOT_CLASSIFIERS"
    assert body["implementation"] == "NONE"
    assert set(body["policy"].values()) == {"UNRESOLVED"}
    records = {axis: axis_record(label, axis) for axis, label in zip(AXES, labels)}
    for axis, record in records.items():
        assert record["state"] in body["axes"][axis]["proposed_values"]
        assert set(record) == set(body["per_axis_provenance"])
    raw = {"symbol": "ALFA", "as_of": "2024-03-11T20:00:00+00:00",
           "daily_series_profile": "XNYS_RTH", "axes": records}
    state = StrategyState("daily_axes_proposal_fixture_v1", JsonObject.of(raw))
    restored = StrategyState.loads(state.dumps())
    assert restored == state
    assert tuple(restored.data.unpack()["axes"][axis]["state"] for axis in AXES) == labels
    # Shock updates cannot overwrite ready bullish/exhaustion or their reasons.
    updated = restored.data.unpack()
    new_shock = "NORMAL" if labels[2] != "NORMAL" else "ADVERSE_SHOCK"
    updated["axes"][AXES[2]] = axis_record(new_shock, AXES[2])
    after = StrategyState(state.version, JsonObject.of(updated))
    for axis in AXES[:2]:
        assert after.data.unpack()["axes"][axis] == state.data.unpack()["axes"][axis]
    assert restored == state and raw["axes"][AXES[2]]["state"] == labels[2]
    assert after.data.unpack()["axes"][AXES[2]]["state"] == new_shock


@pytest.mark.parametrize("profile", ["RTH_DAILY", "EXTENDED_DAILY"])
@pytest.mark.parametrize("defect", ["missing", "delayed"])
def test_last_daily_constituent_never_leaks_a_partial_or_early_candle(profile, defect):
    source = fixture_data() if profile == "RTH_DAILY" else dataset(bars())
    inputs = source.bars
    if defect == "missing":
        changed = replace(source, bars=inputs[:-1])
    else:
        repaired = (*inputs[:-1], replace(inputs[-1], known_at=inputs[-1].known_at + timedelta(hours=1)))
        meta = source.manifest.unpack()
        meta["captured_at"] = repaired[-1].known_at.isoformat()
        changed = replace(source, bars=repaired, manifest=JsonObject.of(meta))
    observer = Observer()
    result = replay(changed, observer)
    if defect == "missing":
        assert all(not view.query(timeframe="Daily") for view in observer.views)
        assert result.summary.unpack()["incomplete"]
    else:
        assert all(not view.query(timeframe="Daily") for view in observer.views[:-1])
        daily = observer.views[-1].query(timeframe="Daily")[0]
        assert daily.end_at == inputs[-1].end_at
        assert daily.known_at == inputs[-1].known_at + timedelta(hours=1)
        assert daily.provenance.unpack()["input_count"] == len(inputs)
