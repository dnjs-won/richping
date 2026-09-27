"""Completed-only XNYS RTH views, fed exclusively by delivered base bars."""

from datetime import timedelta

from ..core import close_at, digest, open_at, timestamp
from .contracts import JsonObject, MarketBar, payload
from .market_data import BASE_INTERVAL, validate_rth

AGGREGATION_VERSION = "xnys_open_anchored_short_final_v1"


def bucket(bar, timeframe):
    opened, closed = open_at(bar.session), close_at(bar.session)
    if timeframe == "Daily":
        return opened, closed
    if timeframe == "1H":
        hour = timedelta(hours=1)
        start = opened + ((bar.start_at - opened) // hour) * hour
        return start, min(start + hour, closed)
    raise ValueError("Unsupported aggregation timeframe")


class CompletedAggregator:
    def __init__(self, timeframes=("1H", "Daily")):
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
        validate_rth(bar)
        if bar.corporate_action != "NONE_CONFIRMED":
            raise ValueError("Unsupported corporate action")
        if bar.identity in self._seen:
            raise ValueError("Duplicate aggregation input")
        self._seen.add(bar.identity)
        self._as_of = as_of
        completed = [bar]
        for timeframe in self.timeframes:
            start, end = bucket(bar, timeframe)
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
                "derived:" + AGGREGATION_VERSION,
                JsonObject.of({"aggregation": AGGREGATION_VERSION,
                               "input_hash": digest(payload(ordered)), "input_count": len(ordered)}),
                "NONE_CONFIRMED")
            completed.append(derived)
            self._emitted.add(key)
        return tuple(completed)

    def incomplete(self):
        """Pending intervals and elapsed intervals with missing evidence stay explicit."""
        return tuple({"symbol": key[1], "timeframe": key[2], "end_at": key[3].isoformat(),
                      "status": "PENDING" if key[3] > self._as_of else "UNRESOLVED",
                      "known_inputs": len(inputs)}
                     for key, inputs in sorted(self._inputs.items()) if key not in self._emitted)
