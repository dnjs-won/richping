"""Separate versioned RTH/extended grids for numeric features and scalar windows."""

from datetime import timedelta

from ...core import next_sessions, timestamp
from ..sessions import (session_date, session_bounds, profile_for_continuity,
                        EXTENDED_CONTINUITY)


CONTINUITY_VERSION = "xnys_completed_grid_v1"
CONTINUITY_VERSIONS = (CONTINUITY_VERSION, EXTENDED_CONTINUITY)


def slot_bounds(end_at, timeframe, continuity=CONTINUITY_VERSION):
    """Selected session-anchored slot; only RTH permits a short final hour."""
    end = timestamp(end_at)
    profile = profile_for_continuity(continuity)
    session = session_date(end)
    opened, closed = session_bounds(session, profile.name)
    if timeframe == "Daily":
        if end != closed:
            raise ValueError("Invalid completed Daily slot")
        return opened, closed
    interval = {"15m": timedelta(minutes=15), "1H": timedelta(hours=1)}.get(timeframe)
    if interval is None or not opened < end <= closed:
        raise ValueError("Invalid completed timeframe slot")
    if end != closed and (end - opened) % interval:
        raise ValueError("Unaligned completed timeframe slot")
    start = opened + ((end - opened - timedelta(microseconds=1)) // interval) * interval
    return start, end


def contiguous_prefix_length(observations, timeframe, continuity=CONTINUITY_VERSION):
    """Length before the first internal missing slot; no leading/trailing claim.

    Inputs are market-end ordered bars or scalar points, not arrival ordered.
    Calendar closures consume no observation step. No price is filled or carried.
    """
    previous = None
    for index, item in enumerate(observations):
        start, end = slot_bounds(item.end_at, timeframe, continuity)
        if previous is not None and previous != start:
            prior_session, session = session_date(previous), session_date(end)
            profile = profile_for_continuity(continuity).name
            if not (previous == session_bounds(prior_session, profile)[1]
                    and next_sessions(prior_session, 1) == [session]
                    and start == session_bounds(session, profile)[0]):
                return index
        previous = end
    return len(observations)


def is_contiguous(observations, timeframe, continuity=CONTINUITY_VERSION):
    return contiguous_prefix_length(observations, timeframe, continuity) == len(observations)
