"""Versioned research session contracts, independent of venues and providers.

Extended v1 intentionally has no availability claim for nonstandard XNYS days.
These are research grids, not statements about executions or liquidity.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from ..core import calendar, close_at, open_at, timestamp

RTH = "XNYS_RTH"
EXTENDED = "US_EQUITY_EXTENDED_04_20"
EXTENDED_CONTINUITY = "us_equity_extended_04_20_completed_grid_v1"
EXTENDED_AGGREGATION = "us_equity_extended_04_anchored_full_session_v1"
EXTENDED_SESSION = "us_equity_extended_04_20_standard_days_v1"
NY = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class SessionProfile:
    name: str
    availability: str
    continuity: str
    aggregation: str
    session_definition: str

    @property
    def metadata(self):
        return {
            "profile": self.name, "availability": self.availability,
            "continuity": self.continuity, "aggregation": self.aggregation,
            "session_definition": self.session_definition,
            "timezone": "America/New_York", "calendar": "XNYS",
            "start": "04:00" if self.name == EXTENDED else "official_open",
            "end": "20:00" if self.name == EXTENDED else "official_close",
            "regular_start": "09:30", "regular_end": "16:00",
            "nonstandard_day": "UNSUPPORTED_FAIL_CLOSED" if self.name == EXTENDED else "official_schedule",
            "daily": "full_04_20_session" if self.name == EXTENDED else "official_rth_session",
        }


RTH_PROFILE = SessionProfile(RTH, "atomic_known_at_batch_v1", "xnys_completed_grid_v1",
                             "xnys_open_anchored_short_final_v1", "xnys_official_rth_v1")
EXTENDED_PROFILE = SessionProfile(EXTENDED, "atomic_known_at_batch_v1", EXTENDED_CONTINUITY,
                                  EXTENDED_AGGREGATION, EXTENDED_SESSION)


def session_profile(name=RTH):
    if name == RTH:
        return RTH_PROFILE
    if name == EXTENDED:
        return EXTENDED_PROFILE
    raise ValueError("Unsupported session capability profile")


def profile_for_continuity(version):
    for profile in (RTH_PROFILE, EXTENDED_PROFILE):
        if profile.continuity == version:
            return profile
    raise ValueError("Unsupported continuity version")


def session_date(instant):
    return timestamp(instant).astimezone(NY).date().isoformat()


def session_bounds(day, profile=RTH):
    profile = session_profile(profile)
    if not calendar().is_session(day):
        raise ValueError("Non-trading session")
    opened, closed = open_at(day), close_at(day)
    if profile.name == RTH:
        return opened, closed
    if (opened.astimezone(NY).time(), closed.astimezone(NY).time()) != (time(9, 30), time(16)):
        raise ValueError("Unsupported extended early-close/nonstandard session")
    date = datetime.fromisoformat(day).date()
    return tuple(timestamp(datetime.combine(date, t, NY)) for t in (time(4), time(20)))


def segment(start, end):
    """Half-open market-time intervals; boundary bars belong to their start segment."""
    day = session_date(start)
    regular_open, regular_close = open_at(day), close_at(day)
    if end <= regular_open:
        return "PREMARKET"
    if start >= regular_close:
        return "AFTER_HOURS"
    if regular_open <= start < end <= regular_close:
        return "RTH"
    return "MIXED"


def extended_bar_metadata(start, end):
    return {"session_profile": EXTENDED, "session_definition": EXTENDED_SESSION,
            "session_segment": segment(start, end)}


def bar_profile(bar):
    return session_profile(bar.provenance.unpack().get("session_profile", RTH)).name


def validate_extended_metadata(bar):
    expected = extended_bar_metadata(bar.start_at, bar.end_at)
    if any(bar.provenance.unpack().get(k) != v for k, v in expected.items()):
        raise ValueError("Extended bar session metadata mismatch")
    if bar.session != session_date(bar.start_at):
        raise ValueError("Extended bar local session date mismatch")


def validate_extended(bar):
    opened, closed = session_bounds(bar.session, EXTENDED)
    interval = timedelta(minutes=15)
    if not opened <= bar.start_at < bar.end_at <= closed:
        raise ValueError("Bar outside extended 04:00-20:00 session")
    if bar.timeframe != "15m" or bar.end_at - bar.start_at != interval:
        raise ValueError("Only 15m base input supported")
    if (bar.start_at - opened) % interval:
        raise ValueError("Unaligned base bar")
    validate_extended_metadata(bar)
