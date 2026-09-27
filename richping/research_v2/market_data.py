"""Immutable synthetic input. This host-side dataset is never a strategy context."""

from dataclasses import dataclass
from datetime import timedelta

from ..core import calendar, close_at, digest, open_at, sessions, timestamp
from .contracts import CONTRACT_VERSION, TIMEFRAMES, JsonObject, MarketBar, nonempty, payload

BASE_INTERVAL = timedelta(minutes=15)


def validate_rth(bar):
    if not calendar().is_session(bar.session):
        raise ValueError("Non-trading session")
    opened, closed = open_at(bar.session), close_at(bar.session)
    if not opened <= bar.start_at < bar.end_at <= closed:
        raise ValueError("Bar outside XNYS RTH session")
    if bar.timeframe != "15m" or bar.end_at - bar.start_at != BASE_INTERVAL:
        raise ValueError("Only 15m base input supported")
    if (bar.start_at - opened) % BASE_INTERVAL:
        raise ValueError("Unaligned base bar")


def market_order(bar):
    return bar.end_at, bar.symbol, bar.timeframe


def availability_order(bar):
    return bar.known_at, *market_order(bar)


@dataclass(frozen=True, slots=True)
class MarketDataset:
    """Input end_at must never decrease; equal-end ties are canonicalized.

    dataset_id is an explicit vintage label; content_hash is a separate complete
    content fingerprint, avoiding a bar/dataset recursive hash definition.
    """

    dataset_id: str
    bars: tuple[MarketBar, ...]
    manifest: JsonObject

    def __post_init__(self):
        nonempty(self.dataset_id)
        object.__setattr__(self, "bars", tuple(self.bars))
        if not self.bars or not isinstance(self.manifest, JsonObject):
            raise ValueError("Nonempty dataset and immutable manifest required")
        meta = self.manifest.unpack()
        required = {"schema_version", "quality", "provider", "adapter_version", "symbols",
                    "membership_limitations", "base_timeframe", "timezone", "calendar",
                    "session_policy", "captured_at", "price_basis", "corporate_actions",
                    "known_at_policy"}
        if not required <= meta.keys():
            raise ValueError("Incomplete dataset provenance")
        expected = {"schema_version": CONTRACT_VERSION, "quality": "SYNTHETIC",
                    "base_timeframe": "15m", "timezone": "America/New_York", "calendar": "XNYS",
                    "session_policy": "RTH", "price_basis": "synthetic_unadjusted",
                    "corporate_actions": "NONE_CONFIRMED", "known_at_policy": "explicit_per_bar"}
        if any(meta[k] != v for k, v in expected.items()):
            raise ValueError("Unsupported dataset contract (V2-A accepts synthetic only)")
        for key in ("provider", "adapter_version", "membership_limitations"):
            nonempty(meta[key])
        captured = timestamp(meta["captured_at"])
        if captured < max(b.known_at for b in self.bars):
            raise ValueError("Capture precedes bar known_at")
        if meta["symbols"] != sorted({b.symbol for b in self.bars}):
            raise ValueError("Manifest symbols mismatch")
        seen, prior = set(), None
        for bar in self.bars:
            if bar.dataset_id != self.dataset_id:
                raise ValueError("Mixed dataset identity")
            if bar.identity in seen:
                raise ValueError("Duplicate bar identity")
            seen.add(bar.identity)
            if prior is not None and bar.end_at < prior:
                raise ValueError("Invalid bar input ordering")
            prior = bar.end_at
            validate_rth(bar)
            if bar.corporate_action != "NONE_CONFIRMED":
                raise ValueError("Unsupported or unknown corporate action")
        # Tie order has no temporal meaning. Canonicalize only after validating
        # chronology and identities, so a time reversal can never be repaired.
        object.__setattr__(self, "bars", tuple(sorted(self.bars, key=market_order)))

    @property
    def content_hash(self):
        return digest(payload(self))

    @property
    def gaps(self):
        """Missing slots through each symbol's last supplied close; never filled.

        The final session may be a prefix. The trailing unsupplied interval is
        intentionally not asserted complete or inferred to be a trading halt.
        """
        missing = []
        for symbol in sorted({b.symbol for b in self.bars}):
            bars = [b for b in self.bars if b.symbol == symbol]
            present = {b.end_at for b in bars}
            for day in sessions(bars[0].session, bars[-1].session):
                end = min(close_at(day), bars[-1].end_at)
                slot = open_at(day) + BASE_INTERVAL
                while slot <= end:
                    if slot not in present:
                        missing.append((symbol, slot.isoformat()))
                    slot += BASE_INTERVAL
        return tuple(missing)

    def query(self, symbol=None, timeframe=None, start_at=None, end_at=None):
        """Host-only import/inspection query. Never passed to a strategy."""
        if timeframe is not None and timeframe not in TIMEFRAMES:
            raise ValueError("Unsupported query timeframe")
        start = timestamp(start_at) if start_at is not None else None
        end = timestamp(end_at) if end_at is not None else None
        if start is not None and end is not None and start > end:
            raise ValueError("Inverted query")
        return tuple(b for b in self.bars if (symbol is None or b.symbol == symbol)
                     and (timeframe is None or b.timeframe == timeframe)
                     and (start is None or b.end_at >= start) and (end is None or b.end_at <= end))

    @classmethod
    def from_records(cls, dataset_id, records, manifest):
        """Fixture/import boundary; validate chronology, canonicalize equal-end ties."""
        bars = tuple(MarketBar(**{**r, "provenance": JsonObject.of(r["provenance"])}) for r in records)
        return cls(dataset_id, bars, JsonObject.of(manifest))
