"""Completed-only versioned session views, fed exclusively by delivered base bars."""

from datetime import timedelta

from ..core import digest, timestamp
from .contracts import JsonObject, MarketBar, payload
from .market_data import BASE_INTERVAL, validate_rth
from .real_data import is_research_snapshot
from .sessions import (RTH, EXTENDED, session_profile, session_bounds, bar_profile,
                       validate_extended, extended_bar_metadata)

AGGREGATION_VERSION = "xnys_open_anchored_short_final_v1"


def bucket(bar, timeframe, profile=RTH):
    opened, closed = session_bounds(bar.session, profile)
    if timeframe == "Daily":
        return opened, closed
    if timeframe == "1H":
        hour = timedelta(hours=1)
        start = opened + ((bar.start_at - opened) // hour) * hour
        return start, min(start + hour, closed)
    raise ValueError("Unsupported aggregation timeframe")


class CompletedAggregator:
    def __init__(self, timeframes=("1H", "Daily"), *, profile=RTH):
        self.profile = session_profile(profile)
        self.timeframes = tuple(timeframes)
        if len(set(self.timeframes)) != len(self.timeframes) or any(
                t not in {"1H", "Daily"} for t in self.timeframes):
            raise ValueError("Unsupported or duplicate aggregation timeframe")
        self._inputs = {}
        self._emitted = set()
        self._seen = set()
        self._as_of = None

    def accept(self, bar, as_of):
        as_of = timestamp(as_of)
        if bar.known_at > as_of or (self._as_of is not None and as_of < self._as_of):
            raise ValueError("Noncausal aggregation input")
        if bar_profile(bar) != self.profile.name:
            raise ValueError("Aggregation session profile mismatch")
        (validate_extended if self.profile.name == EXTENDED else validate_rth)(bar)
        research_snapshot = is_research_snapshot(bar)
        if bar.corporate_action != "NONE_CONFIRMED" and not research_snapshot:
            raise ValueError("Unsupported corporate action")
        if bar.identity in self._seen:
            raise ValueError("Duplicate aggregation input")
        self._seen.add(bar.identity)
        self._as_of = as_of
        completed = [bar]
        for timeframe in self.timeframes:
            start, end = bucket(bar, timeframe, self.profile.name)
            key = (bar.dataset_id, bar.symbol, timeframe, end)
            inputs = self._inputs.setdefault(key, {})
            inputs[bar.start_at] = bar
            expected = tuple(start + i * BASE_INTERVAL for i in range((end - start) // BASE_INTERVAL))
            if key in self._emitted or end > as_of or set(inputs) != set(expected):
                continue
            ordered = [inputs[s] for s in expected]
            known = max(b.known_at for b in ordered)
            if known > as_of:
                raise ValueError("Future aggregate input")
            derived = MarketBar(bar.dataset_id, bar.symbol, timeframe, start, end, bar.session,
                ordered[0].open, max(b.high for b in ordered), min(b.low for b in ordered),
                ordered[-1].close, sum(b.volume for b in ordered), known,
                "derived:" + self.profile.aggregation,
                JsonObject.of({"aggregation": self.profile.aggregation,
                               "input_hash": digest(payload(ordered)), "input_count": len(ordered),
                               **({k: bar.provenance.unpack()[k] for k in (
                                   "quality", "provider", "adapter_version", "provider_version",
                                   "captured_at", "timezone", "price_basis", "corporate_actions",
                                   "known_at_policy", "raw_capture_hash")} if research_snapshot else {}),
                               **({"feed": bar.provenance.unpack()["feed"]}
                                  if research_snapshot and bar.provenance.unpack().get("provider") == "alpaca_sip" else {}),
                               **(extended_bar_metadata(start, end) if self.profile.name == EXTENDED else {})}),
                "UNKNOWN" if research_snapshot else "NONE_CONFIRMED")
            completed.append(derived)
            self._emitted.add(key)
        return tuple(completed)

    def incomplete(self):
        """Pending intervals and elapsed intervals with missing evidence stay explicit."""
        return tuple({"symbol": key[1], "timeframe": key[2], "end_at": key[3].isoformat(),
                      "status": "PENDING" if key[3] > self._as_of else "UNRESOLVED",
                      "known_inputs": len(inputs)}
                     for key, inputs in sorted(self._inputs.items()) if key not in self._emitted)
