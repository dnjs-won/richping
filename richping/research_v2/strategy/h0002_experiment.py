"""H0002 outcome-free experiment metadata and terminal gate, not a label evaluator."""
from dataclasses import dataclass

from ...core import calendar, next_sessions, sessions


@dataclass(frozen=True, slots=True)
class ControlAnchor:
    session: str
    local_slot: str
    prior_four_sign: int
    ready: bool
    primary_event: bool

    def __post_init__(self):
        if type(self.prior_four_sign) is not int or self.prior_four_sign not in (-1, 0, 1):
            raise ValueError('Exact causal sign required')


def select_controls(event, anchors):
    """Only metadata, known at candidate time. No market/label accessor accepted."""
    prior = sessions(str(calendar().first_session.date()), event.session)[:-1][-20:]
    eligible = [a for a in anchors if a.session in prior and a.local_slot == event.local_slot
                and a.prior_four_sign == event.prior_four_sign and a.ready and not a.primary_event]
    if len({(a.session, a.local_slot) for a in eligible}) != len(eligible):
        raise ValueError('Duplicate control anchor')
    chosen = tuple(sorted(eligible, key=lambda a: a.session, reverse=True)[:5])
    return chosen if len(chosen) == 5 else None


def calendar_contract():
    anchors = sessions('2026-10-19', '2027-10-19')
    if len(anchors) != 252 or next_sessions(anchors[-1], 3)[-1] != '2027-10-22':
        raise ValueError('Registered calendar changed; explicit pre-outcome amendment required')
    return {'anchors': anchors, 'embargo': sessions('2026-10-05', '2026-10-16'),
            'followup': next_sessions(anchors[-1], 3)}


def disposition(*, valid=True, terminal=False, resolved=True, events=0, event_sessions=0,
                occupied_blocks=0, positive_lower_bounds=False, negative_upper_bound=False):
    """Consume already-certified gates only. Never calculate outcomes or intervals."""
    if positive_lower_bounds and negative_upper_bound:
        raise ValueError('Contradictory interval gates')
    for value in (events, event_sessions, occupied_blocks):
        if type(value) is not int or value < 0:
            raise ValueError('Nonnegative integer denominator required')
    if event_sessions > events or occupied_blocks > event_sessions:
        raise ValueError('Inconsistent denominators')
    if not valid:
        return 'INVALID_FAIL_CLOSED'
    if not terminal:
        return 'PENDING'
    if not resolved:
        return 'UNRESOLVED'
    if not events:
        return 'ZERO_SIGNAL'
    if events < 40 or event_sessions < 20 or occupied_blocks < 8:
        return 'INSUFFICIENT_EVIDENCE'
    if positive_lower_bounds:
        return 'PASS'
    if negative_upper_bound:
        return 'REJECT'
    return 'INCONCLUSIVE'
