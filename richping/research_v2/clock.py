"""A monotone availability clock, independent of wall time."""

from ..core import timestamp


class ReplayClock:
    def __init__(self, start_at):
        self._as_of = timestamp(start_at)

    @property
    def as_of(self):
        return self._as_of

    def advance(self, known_at):
        instant = timestamp(known_at)
        if instant < self._as_of:
            raise ValueError("Replay clock cannot move backwards")
        self._as_of = instant
        return instant
