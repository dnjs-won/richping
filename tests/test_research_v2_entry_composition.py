"""Candidate causality/lifecycle only; fixtures are never market efficacy."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json

import pytest
import yaml

from richping.core import digest
from richping.research_v2.contracts import JsonObject
from richping.research_v2.sessions import RTH, EXTENDED, NY, session_bounds
from richping.research_v2.strategy.entry_15m import evaluate_temporal, VERSION as M15_VERSION
from richping.research_v2.strategy.entry_composition import (
    compose_initial_entry, flat_research_evidence, save_candidate_stream, contract_hash,
    Consumption, specification_root)
from richping.research_v2.strategy.h1_setup import (
    H1RelativeSetupRawState, SetupDailyPermission, evaluate_h1_setup_lifetime, CANONICAL as H1)
from richping.research_v2.strategy.daily_trend import CANONICAL as TREND
from richping.research_v2.strategy.daily_exhaustion import CANONICAL as EXHAUSTION
from richping.research_v2.strategy.h0001_spec import H0001Specification
from richping.research_v2.strategy.mixed_profile import _reference, VERSION as JOIN_VERSION, expected_extended_end
from richping.research_v2.strategy.daily_input import expected_daily_session
from test_research_v2_entry_15m import observation

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "research/data_evidence/h0001-entry-composition-20261003"
SPEC = ROOT / "research/strategy_specs/H0001-r03-draft.yaml"


@pytest.fixture(scope="module")
def spec():
    return H0001Specification.load(SPEC)


def inputs(i=3, *, previous_episode=None, raw_state="DOWNSIDE_EXTREME", trend="BULLISH", exhaustion="NORMAL", gc=True, price=True):
    obs = observation(i, extreme=True, gc=gc, price=price)
    at = obs.as_of
    hour = expected_extended_end(at, "1H")
    ready = raw_state != "UNAVAILABLE"
    raw = H1RelativeSetupRawState("ALFA", at, hour, hour, observation(3).end_at,
        i // 4, raw_state, "READY" if ready else "UNAVAILABLE", None if ready else "fixture_missing",
        digest([i // 4, raw_state]), "fixture-only", "fixture_basis", H1.version, H1.hash,
        i // 4 + 1, 320, -1 if ready else None,
        (.01 if raw_state == "DOWNSIDE_EXTREME" else .5) if ready else None)
    day = expected_daily_session(at)
    daily_end = session_bounds(day, RTH)[1]
    refs = [
        _reference("DAILY_TREND_PERMISSION", "Daily", RTH, "pit_fixture", "daily_fixture", daily_end, daily_end, "tr-input", trend, TREND.version, "tr-state", "READY" if trend != "UNAVAILABLE" else "UNAVAILABLE"),
        _reference("DAILY_EXHAUSTION", "Daily", RTH, "pit_fixture", "daily_fixture", daily_end, daily_end, "ex-input", exhaustion, EXHAUSTION.version, "ex-state", "READY" if exhaustion != "UNAVAILABLE" else "UNAVAILABLE"),
        _reference("H1_RELATIVE_SETUP_RAW", "1H", EXTENDED, "fixture_basis", "fixture-only", hour, hour, raw.input_hash, raw.state, H1.version, raw.hash, raw.status),
        _reference("M15_INITIAL_ENTRY_PRIMITIVE", "15m", EXTENDED, "fixture_basis", "fixture-only", obs.end_at, obs.known_at, obs.input_hash, obs.raw, M15_VERSION, obs.identity_hash, "READY")]
    for ref in refs:
        ref["symbol"] = "ALFA"
    daily = SetupDailyPermission("ALFA", at, daily_end, trend, exhaustion, "tr-state", "ex-state")
    episode = evaluate_h1_setup_lifetime(previous_episode, raw, daily)
    trigger = evaluate_temporal(None, obs, scope_ref=episode.episode_id if episode.status == "ACTIVE" else None)
    joined = {"as_of": at.isoformat(), "references": refs, "version": JOIN_VERSION,
              "publication": "atomic_known_at_batch_v1", "Daily_input_status": "READY", "expected_Daily_session": day}
    position = flat_research_evidence("ALFA", at, daily_hash="daily-fixture-hash", intraday_hash="intraday-fixture-hash")
    return joined, episode, trigger, position


def run(spec, args, previous=None, **kwargs):
    return compose_initial_entry(*args, previous, specification=spec, **kwargs)


@pytest.mark.parametrize("fault,reason", [("trend", "DAILY_NOT_BULLISH"), ("exhaustion", "EXHAUSTION_EXTENDED"),
    ("h1", "H1_NOT_ACTIVE"), ("trigger", "M15_TRIGGER_FALSE"), ("position", "INELIGIBLE_FOR_INITIAL_ENTRY_POSITION_OPEN")])
def test_each_gate_required(spec, fault, reason):
    args = list(inputs(**({"trend": "NOT_BULLISH"} if fault == "trend" else
        {"exhaustion": "EXTENDED"} if fault == "exhaustion" else
        {"raw_state": "INACTIVE"} if fault == "h1" else {"gc": False} if fault == "trigger" else {})))
    if fault == "position":
        args[3] = replace(args[3], state="OPEN")
    result = run(spec, args)
    assert result.status == "INELIGIBLE" and result.reason == reason and result.event is None


@pytest.mark.parametrize("role", range(4))
@pytest.mark.parametrize("fault", ["missing", "unavailable", "future", "stale", "wrong_symbol", "missing_hash"])
def test_each_missing_future_stale_or_incompatible_role_fails_closed(spec, role, fault):
    args = list(inputs())
    refs = args[0]["references"]
    if fault == "missing":
        refs.pop(role)
    elif fault == "unavailable":
        refs[role]["status"] = "UNAVAILABLE"
    elif fault == "future":
        refs[role]["source_known_at"] = (args[1].as_of + timedelta(seconds=1)).isoformat()
    elif fault == "stale":
        refs[role]["source_end_at"] = (args[1].as_of - timedelta(days=10)).isoformat()
    elif fault == "wrong_symbol":
        refs[role]["symbol"] = "BETA"
    else:
        refs[role]["state_hash"] = None
    assert run(spec, args).status == "UNAVAILABLE"


@pytest.mark.parametrize("fault", ["missing", "unavailable", "future", "old", "symbol"])
def test_explicit_position_evidence(spec, fault):
    args = list(inputs())
    p = args[3]
    args[3] = None if fault == "missing" else replace(p, **{
        "unavailable": {"state": "UNAVAILABLE"}, "future": {"known_at": (args[1].as_of + timedelta(seconds=1)).isoformat()},
        "old": {"as_of": (args[1].as_of - timedelta(minutes=15)).isoformat()}, "symbol": {"symbol": "BETA"}}[fault])
    assert run(spec, args).status == "UNAVAILABLE"


@pytest.mark.parametrize("index", [1, 2])
def test_missing_evaluator_output_is_unavailable(spec, index):
    args = list(inputs())
    args[index] = None
    assert run(spec, args).status == "UNAVAILABLE"


def test_same_atomic_activation_emits_and_consumes_only_episode(spec):
    args = inputs()
    assert args[1].event == "ACTIVATED" and args[2].trigger
    first = run(spec, args)
    assert first.status == "ENTRY_CANDIDATE" and first.memory.consumed
    assert args[3].state == "FLAT" and first.event.unpack()["candidate_is_order_fill_position"] is False
    assert first.event.unpack()["M15"]["age"] == 0
    assert run(spec, args, first.memory).reason == "INITIAL_ENTRY_CONSUMED"
    refreshed = inputs(7, previous_episode=args[1])
    assert refreshed[1].event == "EXTREME_REFRESH" and refreshed[1].episode_id == args[1].episode_id
    assert run(spec, refreshed, first.memory).reason == "INITIAL_ENTRY_CONSUMED"


def test_expiry_then_new_activation_resets_initial_right(spec):
    args = inputs()
    first = run(spec, args)
    ep = args[1]
    for i in (7, 11, 15):
        expired = inputs(i, previous_episode=ep, raw_state="INACTIVE", gc=False)
        ep = expired[1]
        result = run(spec, expired, first.memory)
    assert ep.status == "EXPIRED" and result.memory.episode_id is None and not result.memory.consumed
    new = inputs(19, previous_episode=ep)
    assert new[1].episode_id != args[1].episode_id
    assert run(spec, new, result.memory).status == "ENTRY_CANDIDATE"


@pytest.mark.parametrize("cause", ["trend", "exhaustion", "unavailable", "origin"])
def test_cancellation_clears_consumption_and_requires_new_activation(spec, cause):
    args = inputs()
    first = run(spec, args)
    kwargs = {"trend": "NOT_BULLISH"} if cause == "trend" else {"exhaustion": "EXTENDED"} if cause == "exhaustion" else {"raw_state": "UNAVAILABLE"} if cause == "unavailable" else {}
    ep = replace(args[1], history_origin=args[1].history_origin - timedelta(days=1)) if cause == "origin" else args[1]
    lost = inputs(7, previous_episode=ep, **kwargs)
    assert lost[1].status == "CANCELLED"
    result = run(spec, lost, first.memory)
    if cause in {"origin", "unavailable"}:
        assert result.status == "UNAVAILABLE"
    assert not result.memory.consumed and result.memory.episode_id is None and result.event is None
    fresh = inputs(11, previous_episode=lost[1])
    assert run(spec, fresh, result.memory).status == "ENTRY_CANDIDATE"


def test_poll_and_correction_no_duplicate_and_no_revival_after_missing_daily(spec):
    args = inputs()
    unavailable = deepcopy(args[0])
    unavailable["references"][0]["status"] = "UNAVAILABLE"
    missed = run(spec, (unavailable, *args[1:]))
    assert missed.status == "UNAVAILABLE"
    restored = run(spec, args, missed.memory)
    assert restored.reason == "POLL_OR_CORRECTION_NO_EVENT" and restored.event is None
    corrected = list(args)
    corrected[2] = evaluate_temporal(args[2], replace(args[2].observation, input_hash="correction"), scope_ref=args[1].episode_id)
    corrected[0]["references"][3]["state_hash"] = corrected[2].observation.identity_hash
    assert run(spec, corrected, missed.memory).event is None


def test_delayed_old_trigger_cannot_emit(spec):
    args = list(inputs())
    args[0]["as_of"] = (args[1].as_of + timedelta(minutes=15)).isoformat()
    assert run(spec, args).status == "UNAVAILABLE"
    args = list(inputs())
    args[2] = evaluate_temporal(None, args[2].observation, scope_ref=args[1].episode_id, emit_eligible=False)
    assert args[2].event == "FIRST_GC_REJECTED_CONSUMED" and not args[2].trigger
    assert run(spec, args).event is None


def test_frozen_first_gc_price_failure_still_consumes_arm(spec):
    args = inputs(gc=False)
    armed = args[2]
    failed = replace(observation(4, extreme=True, gc=True, price=False), as_of=observation(4).as_of)
    consumed = evaluate_temporal(armed, failed, scope_ref=args[1].episode_id)
    assert consumed.event == "FIRST_GC_REJECTED_CONSUMED" and consumed.arm_index is None
    assert not evaluate_temporal(consumed, observation(5, extreme=True, gc=True), scope_ref=args[1].episode_id).trigger


def test_m15_continuity_gap_is_unavailable_not_false(spec):
    args = list(inputs())
    armed = evaluate_temporal(None, observation(1, extreme=True), scope_ref=args[1].episode_id)
    args[2] = evaluate_temporal(armed, args[2].observation, scope_ref=args[1].episode_id)
    assert args[2].event == "UNAVAILABLE_CANCEL"
    assert run(spec, args).status == "UNAVAILABLE"


def test_event_identity_dependency_hash_and_immutable_collision(spec, tmp_path):
    args = inputs()
    first = run(spec, args)
    assert run(spec, inputs()).event == first.event
    changed = list(inputs())
    changed[3] = replace(changed[3], provenance=JsonObject.of({"admission": "changed explicit fixture"}))
    second = run(spec, changed)
    assert second.event.unpack()["event_id"] != first.event.unpack()["event_id"]
    p = tmp_path / "events.json"
    assert save_candidate_stream(p, [first.event, first.event]) == save_candidate_stream(p, [first.event])
    collision = first.event.unpack()
    collision["reason"] = "mutated"
    with pytest.raises(ValueError, match="collision"):
        save_candidate_stream(tmp_path / "bad.json", [first.event, collision])
    with pytest.raises(ValueError, match="collision"):
        save_candidate_stream(p, [collision])


@pytest.mark.parametrize("age", [1, 2, 3, 4])
def test_consumed_trigger_preserves_first_extreme_ref_and_age(spec, age):
    args = list(inputs(3 + age, gc=False))
    scope = args[1].episode_id
    memory = evaluate_temporal(None, observation(3, extreme=True), scope_ref=scope)
    for i in range(4, 3 + age):
        memory = evaluate_temporal(memory, observation(i), scope_ref=scope)
    obs = observation(3 + age, gc=True)
    args[2] = evaluate_temporal(memory, obs, scope_ref=scope)
    args[0]["references"][3]["state_hash"] = obs.identity_hash
    result = run(spec, args, previous_trigger=memory)
    assert result.status == "ENTRY_CANDIDATE"
    body = result.event.unpack()["M15"]
    assert body["age"] == age and body["extreme_end"] == observation(3).end_at.isoformat()
    assert run(spec, args).status == "UNAVAILABLE"


def test_composer_contract_cannot_silently_change(spec):
    value = spec.unpack()
    value["state_machine_parameters"]["transition_priority_and_resets"]["value"]["parameters"]["consumption"]["value"] = "refresh_resets_consumption"
    with pytest.raises(ValueError, match="Frozen initial-entry composition"):
        H0001Specification.of(value)


def test_ex_ante_freeze_exact_spec_delta_and_preservation(spec):
    record = yaml.safe_load((ROOT / "research/decision_records/H0001-entry-composition-freeze-v1.yaml").read_text(encoding="utf-8"))
    old = H0001Specification.of(json.loads((EVIDENCE / "specification-v12.json").read_text(encoding="utf-8")))
    before, after = old.unpack(), spec.unpack()
    assert record["specification"]["old_hash"] == old.specification_hash
    assert record["specification"]["new_hash"] == spec.specification_hash
    assert after["state_machine_parameters"]["transition_priority_and_resets"]["value"] == specification_root()
    after["state_machine_parameters"]["transition_priority_and_resets"] = before["state_machine_parameters"]["transition_priority_and_resets"]
    after["specification_version"], after["updated_at"] = before["specification_version"], before["updated_at"]
    assert after == before and len(spec.unresolved_fields) == 84
    assert record["H1_STATE_TRANSITIONS"]["overall"] == "PARTIALLY_RESOLVED"
    assert not record["outcomes_queried"] and record["composer_contract_hash"] == contract_hash()
    for path, expected in record["source_LF_sha256"].items():
        assert sha256((ROOT / path).read_bytes().replace(b"\r\n", b"\n")).hexdigest() == expected
    with pytest.raises(ValueError):
        spec.require_c1_ready()


def test_real_saved_two_network_disabled_replays_and_no_outcome_reads():
    # Executed proof separately, with socket/provider guards and SQLite read
    # authorizer. Assert all artifacts and exact independent replay hashes.
    smoke = json.loads((EVIDENCE / "smoke.json").read_text(encoding="utf-8"))
    proof = json.loads((EVIDENCE / "offline-proof.json").read_text(encoding="utf-8"))
    denominator = json.loads((EVIDENCE / "denominator-report.json").read_text(encoding="utf-8"))
    events = json.loads((EVIDENCE / "candidate-events.json").read_text(encoding="utf-8"))
    assert smoke["total_batches"] == denominator["denominators"]["total_atomic_batches"] == 2624
    assert smoke["joint_READY"] == 829 and proof["runs"] == 2 and proof["repeat_equal"]
    assert proof["network_disabled"] and proof["network_calls"] == proof["outcome_queries"] == 0
    assert proof["SQL_reads_whitelist"] == ["v2_bars", "v2_datasets"]
    assert digest(events) == proof["event_stream_hash"]
    assert proof["event_ids"] == [e["event_id"] for e in events["events"]]
    assert proof["event_payload_hashes"] == [digest(e) for e in events["events"]]
    assert proof["denominator_hash"] == digest(denominator["denominators"])
    assert proof["join_stream_hash"] == "6de4730cb3abfaaf701d9fda0a212d5df0ad5f16dcc0e0cf4714f844d0cac57a"
    assert smoke["profitability"] == proof["outcomes"] == "NOT_RUN"
    assert all(e["candidate_status"] == "ENTRY_CANDIDATE" for e in events["events"])


def test_daily_cache_preserves_uncached_join_and_freshness():
    from contextlib import ExitStack
    from unittest.mock import patch
    from scripts.h0001_action_unit_offline_proof import calendar_guards, DAILY_ROOT, STORE, DAILY_ID, INTRADAY_ID
    from richping.research_v2.daily_data import load_daily
    from richping.research_v2.store import ResearchStore
    from richping.research_v2.strategy.mixed_profile import join_as_of
    from richping.research_v2.strategy.daily_input import prepare_daily
    with ExitStack() as guards:
        calendar_guards(guards)
        daily = load_daily(DAILY_ID, DAILY_ROOT)
        with ResearchStore(STORE, read_only=True) as store:
            intraday = store.load_dataset(INTRADAY_ID)
        cache = {}
        for at in ("2026-10-01T19:45:00+00:00", "2026-10-01T20:00:00+00:00", "2026-10-01T20:15:00+00:00"):
            cached = join_as_of(daily, intraday, at, daily_cache=cache, return_states=True)
            uncached = join_as_of(daily, intraday, at, return_states=True)
            assert cached == uncached
        # Retaining an older delivered Daily must not use the cached READY gate
        # once a newer Daily session is expected.
        # Fault injection on detached caller facts, never mutate/certify a
        # shortened real immutable vintage or its admission evidence.
        def missing(vintage, at):
            resolution = prepare_daily(vintage, at)
            prefix = replace(resolution.prefix,
                bars=tuple(b for b in resolution.prefix.bars if b.session < "2026-10-01"),
                input_status="UNAVAILABLE", input_reason="latest_expected_completed_Daily_missing")
            return replace(resolution, prefix=prefix)
        with patch("richping.research_v2.strategy.mixed_profile.prepare_daily", missing):
            result = join_as_of(daily, intraday, "2026-10-01T20:30:00+00:00", daily_cache=cache)
        assert result["Daily_input_status"] == "UNAVAILABLE"
        assert all(r["status"] == "UNAVAILABLE" for r in result["references"][:2])
