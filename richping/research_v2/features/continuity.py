"""XNYS completed slots shared by numeric features, scalar windows and swings."""

from datetime import timedelta

from ...core import close_at, next_sessions, open_at, timestamp


CONTINUITY_VERSION = "xnys_completed_grid_v1"


def slot_bounds(end_at, timeframe):
    """Official open-anchored slot, including the final short 1H bucket."""
    end = timestamp(end_at)
    session = end.date().isoformat()  # XNYS RTH stays within its UTC date.
    opened, closed = open_at(session), close_at(session)
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


def contiguous_prefix_length(observations, timeframe):
    """Length before the first internal missing slot; no leading/trailing claim.

    Inputs are market-end ordered bars or scalar points, not arrival ordered.
    Calendar closures consume no observation step. No price is filled or carried.
    """
    previous = None
    for index, item in enumerate(observations):
        start, end = slot_bounds(item.end_at, timeframe)
        if previous is not None and previous != start:
            prior_session, session = previous.date().isoformat(), end.date().isoformat()
            if not (previous == close_at(prior_session)
                    and next_sessions(prior_session, 1) == [session]
                    and start == open_at(session)):
                return index
        previous = end
    return len(observations)


def is_contiguous(observations, timeframe):
    return contiguous_prefix_length(observations, timeframe) == len(observations)
