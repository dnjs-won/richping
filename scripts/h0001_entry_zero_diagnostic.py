"""Explain zero initial opportunities with frozen inputs; never read outcomes."""
from collections import Counter
from contextlib import ExitStack
from unittest.mock import patch

from richping.core import canonical
from richping.research_v2.daily_data import load_daily
from richping.research_v2.store import ResearchStore
from richping.research_v2.strategy.daily_input import prepare_daily, expected_daily_session
from richping.research_v2.strategy.daily_trend import classify_daily_trend
from richping.research_v2.strategy.daily_exhaustion import classify_daily_exhaustion
from richping.research_v2.strategy.h1_setup import PreparedH1Prefix, classify_h1_relative_setup
from richping.research_v2.strategy.mixed_profile import intraday_as_of
from scripts.h0001_action_unit_offline_proof import calendar_guards, forbidden, DAILY_ROOT, STORE, DAILY_ID, INTRADAY_ID
from scripts.h0001_entry_freeze import ROOT, immutable


def main():
    with ExitStack() as guards:
        for target in ("socket.socket.connect", "socket.create_connection", "urllib.request.urlopen"):
            guards.enter_context(patch(target, forbidden))
        calendar_guards(guards)
        daily = load_daily(DAILY_ID, DAILY_ROOT)
        with ResearchStore(STORE, read_only=True) as store:
            intraday = store.load_dataset(INTRADAY_ID)
        hours = tuple(b for b in intraday_as_of(intraday, intraday.bars[-1].known_at) if b.timeframe == "1H")
        counts = Counter({k: 0 for k in ("completed_H1", "H1_raw_READY", "H1_downside_extreme",
            "H1_extreme_Daily_BULLISH_NORMAL", "H1_extreme_Daily_NOT_BULLISH")})
        daily_states, extreme_times = {}, []
        for index, bar in enumerate(hours):
            counts["completed_H1"] += 1
            if index + 1 < 449:
                continue  # Frozen actual READY boundary; classifier still checks.
            raw = classify_h1_relative_setup(PreparedH1Prefix("SOXX", hours[:index+1], bar.known_at,
                bar.end_at, intraday.dataset_id, max(b.known_at for b in hours[:index+1]),
                price_basis=intraday.manifest.unpack()["price_basis"]), bar.known_at)
            counts["H1_raw_READY"] += raw.status == "READY"
            session = expected_daily_session(bar.known_at)
            if session not in daily_states:
                prefix = prepare_daily(daily, bar.known_at).prefix
                daily_states[session] = (classify_daily_trend(prefix, bar.known_at).state,
                                        classify_daily_exhaustion(prefix, bar.known_at).state)
            trend, exhaustion = daily_states[session]
            if raw.state == "DOWNSIDE_EXTREME":
                counts["H1_downside_extreme"] += 1
                counts["H1_extreme_Daily_BULLISH_NORMAL"] += trend == "BULLISH" and exhaustion == "NORMAL"
                counts["H1_extreme_Daily_NOT_BULLISH"] += trend == "NOT_BULLISH"
                extreme_times.append({"source_H1_end_at": bar.end_at.isoformat(), "Daily_session": session,
                                      "Daily_trend": trend, "exhaustion": exhaustion})
        report = {"version": "H0001_ZERO_SIGNAL_INPUT_DIAGNOSTIC_V1", "count_unit": "completed_1H_publications_NOT_atomic_batch_occupancy",
            "counts": dict(counts), "extreme_publications": extreme_times,
            "daily_hash": daily.content_hash, "intraday_hash": intraday.content_hash,
            "network_calls": 0, "outcome_queries": 0, "outcomes": "NOT_RUN", "threshold_changes": False}
        immutable(ROOT / "zero-signal-diagnostic.json", report)
        print(canonical(report), flush=True)


if __name__ == "__main__":
    main()
