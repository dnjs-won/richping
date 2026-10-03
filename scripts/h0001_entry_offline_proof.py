"""Actual fixed SOXX candidate replay, twice; network and outcomes denied."""
from collections import Counter
from contextlib import ExitStack
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import sqlite3
from unittest.mock import patch
import yaml

from richping.core import canonical, digest
from richping.research_v2.contracts import ReplayContext, payload
from richping.research_v2.daily_data import load_daily
from richping.research_v2.store import ResearchStore
from richping.research_v2.strategy.entry_15m import measure_completed_15m, evaluate_temporal
from richping.research_v2.strategy.entry_composition import (
    compose_initial_entry, flat_research_evidence, contract_hash, save_candidate_stream)
from richping.research_v2.strategy.h1_setup import SetupDailyPermission, evaluate_h1_setup_lifetime
from richping.research_v2.strategy.h0001_spec import H0001Specification
from richping.research_v2.strategy.mixed_profile import atomic_intraday_batches, join_as_of, expected_extended_end
from scripts.h0001_action_unit_offline_proof import calendar_guards, forbidden, DAILY_ROOT, STORE, DAILY_ID, INTRADAY_ID
from scripts.h0001_entry_freeze import ROOT, RECORD, SPEC, immutable

DENOMINATORS = ("total_atomic_batches", "joint_READY", "Daily_READY", "Daily_BULLISH",
    "exhaustion_READY", "exhaustion_NORMAL", "H1_raw_READY", "H1_ACTIVE", "M15_primitive_READY",
    "M15_armed", "GC_events", "price_confirmation_pass", "price_confirmation_fail",
    "frozen_M15_trigger_TRUE", "position_FLAT", "setup_episode_already_consumed",
    "candidate_emitted", "candidate_unavailable", "candidate_ineligible")


def replay(daily, intraday, specification):
    # Each point has its own prefix hash/known_at. No future measurement is
    # attached or read by the decision; only the currently completed point.
    measurements = measure_completed_15m(ReplayContext(max(b.known_at for b in intraday.bars), intraday.bars), "SOXX")
    episode = trigger = consumption = None
    measurement_by_end = {point.end_at: point for point in measurements}
    print(canonical({"stage": "causal_15m_measurements", "count": len(measurements)}), flush=True)
    counts = Counter({k: 0 for k in DENOMINATORS})
    cancellations, cancel_evaluations, reasons, events, h1_cache, daily_cache = Counter(), Counter(), Counter(), [], {}, {}
    trace_hash, join_hash = sha256(), sha256()
    for at, visible, completed in atomic_intraday_batches(intraday):
        joined, trend, exhaustion, raw, obs = join_as_of(daily, intraday, at,
            published=visible, m15_measurements=measurements, h1_cache=h1_cache, return_states=True, daily_cache=daily_cache)
        join_hash.update(canonical(joined).encode())
        refs = {r["role"]: r for r in joined["references"]}
        tr, ex = refs["DAILY_TREND_PERMISSION"], refs["DAILY_EXHAUSTION"]
        daily_permission = SetupDailyPermission("SOXX", at, max(trend.known_at, exhaustion.known_at),
            trend.state, exhaustion.state, tr["state_hash"], ex["state_hash"])
        episode = evaluate_h1_setup_lifetime(episode, raw, daily_permission)
        scope = episode.episode_id if episode.status == "ACTIVE" else None
        before_trigger = trigger
        # Complete atomic publication first; earlier delayed members can only
        # advance frozen arm memory, never emit historical queued triggers.
        for bar in sorted((b for b in completed if b.timeframe == "15m"), key=lambda b: b.end_at):
            point = replace(measurement_by_end[bar.end_at], as_of=at)
            before_trigger = trigger
            trigger = evaluate_temporal(trigger, point, scope_ref=scope,
                                        emit_eligible=point.end_at == expected_extended_end(at, "15m"))
        evidence = flat_research_evidence("SOXX", at, daily_hash=daily.content_hash, intraday_hash=intraday.content_hash)
        result = compose_initial_entry(joined, episode, trigger, evidence, consumption,
                                       specification=specification, previous_trigger=before_trigger)
        consumption = result.memory
        flags = {"total_atomic_batches": True, "joint_READY": all(r["status"] == "READY" for r in refs.values()),
            "Daily_READY": trend.status == "READY", "Daily_BULLISH": trend.state == "BULLISH",
            "exhaustion_READY": exhaustion.status == "READY", "exhaustion_NORMAL": exhaustion.state == "NORMAL",
            "H1_raw_READY": raw.status == "READY", "H1_ACTIVE": episode.status == "ACTIVE",
            "M15_primitive_READY": obs.raw != "UNAVAILABLE", "M15_armed": trigger.arm_index is not None,
            "GC_events": obs.gc is True, "price_confirmation_pass": obs.gc is True and obs.price is True,
            "price_confirmation_fail": obs.gc is True and obs.price is False,
            "frozen_M15_trigger_TRUE": trigger.trigger, "position_FLAT": evidence.state == "FLAT",
            "setup_episode_already_consumed": result.reason == "INITIAL_ENTRY_CONSUMED",
            "candidate_emitted": result.status == "ENTRY_CANDIDATE", "candidate_unavailable": result.status == "UNAVAILABLE",
            "candidate_ineligible": result.status == "INELIGIBLE"}
        counts.update(k for k, yes in flags.items() if yes)
        reasons.update([result.reason])
        if episode.event in {"CANCELLED", "EXPIRE_GRACE"}:
            cancellations.update([episode.reason])
        if trigger.event in {"UNAVAILABLE_CANCEL", "UPSTREAM_CANCEL", "EXPIRED", "FIRST_GC_REJECTED_CONSUMED"}:
            cancel_evaluations.update(["M15:" + trigger.event])
            if (before_trigger is not None and before_trigger.arm_index is not None
                    or trigger.event == "FIRST_GC_REJECTED_CONSUMED"):
                cancellations.update(["M15:" + trigger.event])
        if result.event:
            events.append(result.event)
        trace_hash.update(canonical({"as_of": at.isoformat(), "join_hash": digest(joined),
            "episode": payload(episode), "trigger": payload(trigger), "consumption": payload(consumption),
            "status": result.status, "reason": result.reason,
            "event_id": result.event.unpack()["event_id"] if result.event else None}).encode())
        if counts["total_atomic_batches"] % 512 == 0:
            print(canonical({"stage": "replay_progress", "batches": counts["total_atomic_batches"]}), flush=True)
    return {"denominators": dict(counts), "cancellation_counts_by_reason": dict(cancellations),
            "trigger_cancel_evaluation_counts": dict(cancel_evaluations),
            "candidate_reasons": dict(reasons), "events": [e.unpack() for e in events],
            "trace_stream_hash": trace_hash.hexdigest(),
            "join_stream_hash": join_hash.hexdigest(),
            "event_stream_hash": digest({"version": "H0001_INITIAL_ENTRY_COMPOSER_V1", "events": [e.unpack() for e in events]}),
            "event_payload_hashes": [digest(e.unpack()) for e in events]}


def main():
    record_bytes = RECORD.read_bytes()  # Must already exist before loading inputs.
    record = yaml.safe_load(record_bytes)
    spec = H0001Specification.load(SPEC)
    assert record["composer_contract_hash"] == contract_hash()
    assert record["specification"]["new_hash"] == spec.specification_hash
    reads = set()
    def authorizer(action, first, second, db, trigger):
        if action == sqlite3.SQLITE_READ:
            reads.add(first)
            return sqlite3.SQLITE_OK if first in {"v2_bars", "v2_datasets"} else sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    def inputs():
        with ResearchStore(STORE, read_only=True) as store:
            store.db.set_authorizer(authorizer)
            return load_daily(DAILY_ID, DAILY_ROOT), store.load_dataset(INTRADAY_ID)
    with ExitStack() as guards:
        for target in ("socket.socket.connect", "socket.create_connection", "urllib.request.urlopen",
                       "richping.research_v2.daily_data.fetch_daily", "richping.research_v2.real_data.fetch_capture"):
            guards.enter_context(patch(target, forbidden))
        calendar_guards(guards)
        daily, intraday = inputs()
        first = replay(daily, intraday, spec)
        print(canonical({"stage": "first", "denominators": first["denominators"]}), flush=True)
        daily2, intraday2 = inputs()
        second = replay(daily2, intraday2, spec)
        assert first == second and first["denominators"]["total_atomic_batches"] == 2624
        assert first["denominators"]["joint_READY"] == 829
        assert first["join_stream_hash"] == "6de4730cb3abfaaf701d9fda0a212d5df0ad5f16dcc0e0cf4714f844d0cac57a"
        assert RECORD.read_bytes() == record_bytes
        stream_hash = save_candidate_stream(ROOT / "candidate-events.json", first["events"])
        assert stream_hash == save_candidate_stream(ROOT / "candidate-events.json", second["events"])
        immutable(ROOT / "denominator-report.json", {k: first[k] for k in ("denominators", "cancellation_counts_by_reason", "trigger_cancel_evaluation_counts", "candidate_reasons")})
        proof = {"repeat_equal": True, "runs": 2, "network_disabled": True, "network_calls": 0,
            "SQL_reads_whitelist": sorted(reads), "outcome_queries": 0, "outcomes": "NOT_RUN", "profitability": "NOT_RUN",
            "freeze_before_dataset_load_and_replay": True, "freeze_record_sha256": sha256(record_bytes).hexdigest(),
            "daily_id": daily.dataset_id, "daily_hash": daily.content_hash, "intraday_id": intraday.dataset_id,
            "intraday_hash": intraday.content_hash, "specification_hash": spec.specification_hash,
            "composer_hash": contract_hash(), "all_replay_result_hash": digest(first),
            "denominator_hash": digest(first["denominators"]), "event_stream_hash": stream_hash,
            "event_ids": [e["event_id"] for e in first["events"]], "event_payload_hashes": first["event_payload_hashes"],
            "trace_stream_hash": first["trace_stream_hash"], "join_stream_hash": first["join_stream_hash"]}
        immutable(ROOT / "offline-proof.json", proof)
        smoke = {"status": "COMPLETE_INITIAL_ENTRY_COMPOSITION_ONLY", **proof,
            "total_batches": 2624, "joint_READY": 829, "candidate_count": len(first["events"]),
            "candidate_timestamps": [e["as_of"] for e in first["events"]],
            "denominators": first["denominators"], "phase_exit_5": "COMPLETE", "phase_exit_6": "INCOMPLETE",
            "next_action": "H0001_ENTRY_EFFICACY_PREREGISTRATION"}
        immutable(ROOT / "smoke.json", smoke)
        print(canonical(smoke), flush=True)


if __name__ == "__main__":
    main()
