"""Prove admitted real Daily and all current mixed batches twice, offline."""

from contextlib import ExitStack
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import json
import sqlite3
from unittest.mock import patch

from richping.core import canonical, digest, timestamp
from richping.research_v2.daily_data import load_daily, daily_coverage
from richping.research_v2.strategy.daily_input import prepare_daily
from richping.research_v2.strategy.daily_proof import readiness_proof
from richping.research_v2.strategy.mixed_profile import mixed_proof, join_as_of
from richping.research_v2.store import ResearchStore
from scripts.h0001_action_unit_audit import immutable, ROOT

DAILY_ROOT = Path("var/research/v2-daily-pit")
STORE = Path("var/research/v2-real/market.sqlite")
DAILY_ID = "soxx-yahoo-rth-daily-pit-20261003-v2"
INTRADAY_ID = "soxx-yahoo-15m-20261003-v1"


def forbidden(*args, **kwargs):
    raise AssertionError("Network/provider/outcome lookup forbidden in offline evidence")


def calendar_guards(stack):
    from richping.research_v2.features.continuity import slot_bounds
    from richping.research_v2.sessions import session_bounds
    cached_slots = lru_cache(maxsize=10000)(slot_bounds)
    cached_sessions = lru_cache(maxsize=2000)(session_bounds)
    for module in ("features.continuity", "features.contracts", "strategy.h1_setup", "strategy.entry_15m"):
        stack.enter_context(patch("richping.research_v2." + module + ".slot_bounds", cached_slots))
    for module in ("features.continuity", "aggregation", "strategy.daily_input", "strategy.mixed_profile"):
        stack.enter_context(patch("richping.research_v2." + module + ".session_bounds", cached_sessions))


def main():
    tables_read = set()

    def authorizer(action, first, second, db, trigger):
        if action == sqlite3.SQLITE_READ:
            tables_read.add(first)
            return sqlite3.SQLITE_OK if first in {"v2_datasets", "v2_bars"} else sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    with ExitStack() as guards:
        for target in ("socket.socket.connect", "socket.create_connection", "urllib.request.urlopen",
                       "richping.research_v2.daily_data.fetch_daily", "richping.research_v2.real_data.fetch_capture"):
            guards.enter_context(patch(target, forbidden))
        calendar_guards(guards)
        parent = load_daily("soxx-yahoo-rth-daily-20261003-v1", DAILY_ROOT)
        parent_text = parent.dumps()
        parent_path = DAILY_ROOT / "daily" / (parent.dataset_id + ".json")
        parent_bytes = parent_path.read_bytes()
        daily = load_daily(DAILY_ID, DAILY_ROOT)
        with ResearchStore(STORE, read_only=True) as store:
            store.db.set_authorizer(authorizer)
            intraday = store.load_dataset(INTRADAY_ID)
        immutable("daily-coverage.json", daily_coverage(daily))
        first = readiness_proof(daily)
        repeated = readiness_proof(load_daily(DAILY_ID, DAILY_ROOT))
        assert first == repeated
        assert first["eligible_input_observations"] == 500
        assert first["trend_READY"] == 322 and first["exhaustion_READY"] == 120
        assert first["first_trend_READY_session"] == daily.bars[178].session
        assert first["first_exhaustion_READY_session"] == daily.bars[380].session
        immutable("daily-readiness.json", first)
        print(canonical({"stage": "Daily", "eligible": 500, "trend_READY": 322, "exhaustion_READY": 120}), flush=True)
        transform = prepare_daily(daily, daily.bars[-1].known_at).transform.unpack()
        assert transform["applied_actions"] == [] and set(transform["factors"]) == {1.0}
        immutable("pit-transform-proof.json", {"real_vintage": transform, "historical_identity_transform_certified": True,
            "strategy_frozen_decisions_changed": False, "negative_receipt_backdated": False,
            "event_receipt_reconstructed": False, "bar_clock_policy": daily.manifest.unpack()["known_at_policy"]})
        joined = mixed_proof(daily, intraday)
        print(canonical({"stage": "mixed-first", "events": joined["events"], "joint_READY": joined["joint_READY_evaluations"]}), flush=True)
        with ResearchStore(STORE, read_only=True) as store:
            store.db.set_authorizer(authorizer)
            repeated = mixed_proof(load_daily(DAILY_ID, DAILY_ROOT), store.load_dataset(INTRADAY_ID))
        assert joined == repeated and joined["events"] == 2624 and joined["joint_READY_evaluations"] > 0
        immutable("mixed-profile-join-proof.json", joined)
        # Independent uncached classification paths for two actual saved-data joins.
        for local in ("06:00", "16:00"):
            sample = joined["examples"][local]
            assert join_as_of(daily, intraday, sample["as_of"]) == sample
        assert load_daily(parent.dataset_id, DAILY_ROOT).dumps() == parent_text and parent_path.read_bytes() == parent_bytes
        immutable("smoke.json", {"status": "COMPLETE_HISTORICAL_CAUSAL_RESEARCH_ADMISSION",
            "daily_id": DAILY_ID, "daily_hash": daily.content_hash, "parent_hash": parent.content_hash,
            "parent_file_sha256_before_after": sha256(parent_bytes).hexdigest(), "parent_preserved": True,
            "intraday_id": INTRADAY_ID, "intraday_hash": intraday.content_hash,
            "repeat_equal": True, "readiness_hash": digest(first), "join_proof_hash": digest(joined),
            "join_stream_hash": joined["joined_event_hash"], "events": joined["events"],
            "joint_READY": joined["joint_READY_evaluations"], "network_blocked": True, "network_calls": 0,
            "SQL_reads_whitelist": sorted(tables_read), "outcome_queries": 0,
            "uncached_sample_joins_equal": ["06:00", "16:00"],
            "profitability": "NOT_RUN", "ENTRY_CANDIDATE": None, "entry_outcome": "NOT_EVALUATED"})
    path = ROOT / "daily-vintage.json"
    if path.exists():
        assert path.read_text(encoding="utf-8") == daily.dumps()
    else:
        with path.open("x", encoding="utf-8") as f:
            f.write(daily.dumps())
    print(canonical({"status": "COMPLETE", "joint_READY": joined["joint_READY_evaluations"],
                     "daily_hash": daily.content_hash, "join_hash": joined["joined_event_hash"]}), flush=True)


if __name__ == "__main__":
    main()
