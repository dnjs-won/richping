"""Repeat real-snapshot Daily/join proof with all provider/network paths blocked."""

from contextlib import ExitStack
from functools import lru_cache
from pathlib import Path
import json
import socket
import sys
from unittest.mock import patch

from richping.core import canonical, digest
from richping.research_v2.daily_data import load_daily, daily_coverage
from richping.research_v2.strategy.daily_input import prepare_daily, expected_daily_session
from richping.research_v2.strategy.daily_proof import readiness_proof
from richping.research_v2.strategy.mixed_profile import mixed_proof
from richping.research_v2.store import ResearchStore


def forbidden(*args, **kwargs):
    raise AssertionError("Offline proof cannot call provider/network")


def write(root, name, body):
    (root/name).write_text(canonical(body), encoding="utf-8")


def main():
    daily_root, intraday_store, evidence = map(Path, sys.argv[1:4])
    daily_id = "soxx-yahoo-rth-daily-20261003-v1"
    intraday_id = "soxx-yahoo-15m-20261003-v1"
    evidence.mkdir(parents=True, exist_ok=True)
    with ExitStack() as guards:
        for target in ("socket.socket.connect", "socket.create_connection", "urllib.request.urlopen",
                       "richping.research_v2.daily_data.fetch_daily", "richping.research_v2.real_data.fetch_capture"):
            guards.enter_context(patch(target, forbidden))
        # Memoize only the exact existing pure official-calendar functions.
        # Repeated scalar windows resolve the same slots millions of times;
        # there is no replacement calendar, adjusted boundary or cached state.
        from richping.research_v2.features.continuity import slot_bounds
        from richping.research_v2.sessions import session_bounds
        cached_slots = lru_cache(maxsize=10000)(slot_bounds)
        cached_sessions = lru_cache(maxsize=2000)(session_bounds)
        for target in ("richping.research_v2.features.continuity.slot_bounds",
                       "richping.research_v2.features.contracts.slot_bounds",
                       "richping.research_v2.strategy.h1_setup.slot_bounds",
                       "richping.research_v2.strategy.entry_15m.slot_bounds"):
            guards.enter_context(patch(target, cached_slots))
        for target in ("richping.research_v2.features.continuity.session_bounds",
                       "richping.research_v2.aggregation.session_bounds",
                       "richping.research_v2.strategy.daily_input.session_bounds",
                       "richping.research_v2.strategy.mixed_profile.session_bounds"):
            guards.enter_context(patch(target, cached_sessions))
        daily = load_daily(daily_id, daily_root)
        with ResearchStore(intraday_store, read_only=True) as store:
            intraday = store.load_dataset(intraday_id)
        write(evidence, "daily-coverage.json", daily_coverage(daily))
        first = readiness_proof(daily)
        assert first == readiness_proof(load_daily(daily_id, daily_root))
        write(evidence, "daily-readiness.json", first)
        latest = prepare_daily(daily, daily.bars[-1].known_at)
        write(evidence, "pit-transform-proof.json", {"real_vintage": latest.transform.unpack(),
              "historical_identity_transform_certified": False,
              "reason": "Current split-free table cannot supply past no-action coverage known_at or certify raw share units.",
              "fixture_proof": "tests/test_research_v2_daily_pit.py",
              "fixture_is_actual_provider_evidence": False})
        joined = mixed_proof(daily, intraday)
        with ResearchStore(intraday_store, read_only=True) as store:
            repeated = mixed_proof(load_daily(daily_id, daily_root), store.load_dataset(intraday_id))
        assert joined == repeated
        write(evidence, "mixed-profile-join-proof.json", joined)
        dates = ["2026-10-01T15:59:59-04:00", "2026-10-01T16:00:00-04:00",
                 "2026-10-04T12:00:00-04:00", "2026-09-07T12:00:00-04:00",
                 "2024-11-29T12:59:59-05:00", "2024-11-29T13:00:00-05:00"]
        write(evidence, "daily-freshness.json", {"calendar_facts": [
            {"as_of": t, "expected_completed_RTH_session": expected_daily_session(t)} for t in dates],
            "delivery_boundary_fixtures": "tests/test_research_v2_daily_pit.py",
            "historical_actual_provider_delivery_measured": False})
        write(evidence, "smoke.json", {"status": "BLOCKED_REAL_HISTORICAL_PIT_EVIDENCE",
            "daily_id": daily_id, "daily_hash": daily.content_hash, "intraday_id": intraday_id,
            "intraday_hash": intraday.content_hash, "repeat_equal": True,
            "readiness_hash": digest(first), "join_hash": digest(joined),
            "network_blocked": True, "network_calls": 0,
            "calendar_memoization": "EXACT_EXISTING_PURE_FUNCTIONS_ONLY_NO_STATE_CACHE",
            "upstream_all_usable": False, "profitability": "NOT_RUN", "entry_outcome": "NOT_EVALUATED"})
    # Portable saved inputs for reruns in a fresh checkout; no network needed.
    (evidence/"daily-vintage.json").write_text(daily.dumps(), encoding="utf-8")
    m = daily.manifest.unpack()
    (evidence/"daily-provider-capture.json").write_bytes((daily_root/"raw"/(m["raw_capture_hash"]+".json")).read_bytes())
    intraday_hash = intraday.manifest.unpack()["raw_capture_hash"]
    (evidence/"intraday-provider-capture.json").write_bytes((intraday_store.parent/"raw"/(intraday_hash+".json")).read_bytes())
    print(canonical({"status": "BLOCKED", "sessions": len(daily.bars), "repeat_equal": True,
                     "daily_state_hash": first["state_stream_hash"], "join_hash": joined["joined_event_hash"]}))


if __name__ == "__main__":
    main()
