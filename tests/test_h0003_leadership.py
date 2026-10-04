from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path

import pytest

from richping.core import timestamp
from richping.research_v2.contracts import payload
from richping.research_v2.strategy.h0003_leadership import (
    CloseBar, CONTRACT, LeadershipStream, Specification, validate_pair)


def pair(index, own=100, benchmark=100):
    start = timestamp('2026-05-05T08:00:00Z')+timedelta(minutes=15*index)
    end = start+timedelta(minutes=15)
    return (CloseBar('soxx-test', 'SOXX', start, end, end, '2026-05-05', own,
                     split_identity_admitted=True),
            CloseBar('qqq-test', 'QQQ', start, end, end, '2026-05-05', benchmark,
                     split_identity_admitted=True))


def accept(stream, index, own=100, benchmark=100):
    a,b = pair(index, own, benchmark)
    return stream.accept(a,b,a.end_at)


def test_exact_alignment_and_return_math_and_lookback_boundary():
    s = LeadershipStream(Specification(2, 1))
    assert not accept(s, 0).rs_ready
    assert not accept(s, 1, 102, 101).rs_ready
    step = accept(s, 2, 110, 104)
    assert step.pair_ready and step.rs_ready
    assert step.own_return == pytest.approx(.10)
    assert step.benchmark_return == pytest.approx(.04)
    assert step.relative_return == pytest.approx(.06)
    assert step.event is not None
    assert step.event.unpack()['anchor_at'] == pair(0)[0].end_at.isoformat()


@pytest.mark.parametrize('side', [0,1])
def test_one_side_missing_is_unavailable(side):
    a,b = pair(0)
    values = [a,b]
    values[side] = None
    step = LeadershipStream().accept(*values, a.end_at)
    assert not step.pair_ready and not step.rs_ready and step.event is None
    assert step.reason == 'one_side_missing'


@pytest.mark.parametrize('change,reason', [
    ({'end_at': timestamp('2026-05-05T08:00:00Z')}, 'stale_or_clock_mismatch'),
    ({'end_at': timestamp('2026-05-05T08:30:00Z')}, 'future_or_unavailable_bar'),
    ({'known_at': timestamp('2026-05-05T08:30:00Z')}, 'future_or_unavailable_bar'),
    ({'start_at': timestamp('2026-05-05T08:01:00Z')}, 'slot_mismatch'),
    ({'session': '2026-05-04'}, 'session_mismatch'),
    ({'symbol': 'SPY'}, 'symbol_or_identity_mismatch'),
    ({'split_identity_admitted': False}, 'provider_feed_unit_action_mismatch'),
    ({'close': 0}, 'invalid_price'),
    ({'close': -1}, 'invalid_price'),
    ({'close': float('nan')}, 'invalid_price'),
    ({'close': float('inf')}, 'invalid_price'),
])
def test_pair_fail_closed(change, reason):
    a,b = pair(0)
    b = replace(b, **change)
    result = LeadershipStream().accept(a,b,a.end_at)
    assert result.reason == reason and result.event is None and not result.rs_ready


@pytest.mark.parametrize('position', range(len(CONTRACT)))
def test_mixed_provider_feed_adjustment_currency_units_actions_clock_timeframe_session(position):
    a,b = pair(0)
    contract = list(CONTRACT)
    contract[position] = 'incompatible'
    assert validate_pair(a, replace(b, contract=tuple(contract)), a.end_at) == 'provider_feed_unit_action_mismatch'


def test_duplicate_prevention_rearm_and_guard_does_not_rearm():
    s = LeadershipStream(Specification(1, 2))
    steps = [accept(s,0), accept(s,1,101), accept(s,2,102), accept(s,3,103),
             accept(s,4,102,98), accept(s,5,104,98), accept(s,6,100,98),
             accept(s,7,101,98), accept(s,8,102,98)]
    events = [r.event for r in steps if r.event]
    assert len(events) == 2
    assert steps[2].event and not steps[3].event
    assert steps[4].relative_return > 0 and not steps[4].guard and not steps[4].event
    assert steps[5].leadership and not steps[5].event  # guard returning does not rearm
    assert steps[6].relative_return < 0 and steps[6].episode_id is None
    assert steps[8].event and steps[8].episode_id != steps[2].episode_id


def test_guard_can_delay_first_emission_within_same_episode():
    s = LeadershipStream(Specification(1,1))
    accept(s,0)
    bad = accept(s,1,95,90)
    assert bad.leadership and not bad.guard and not bad.event
    good = accept(s,2,96,90)
    assert good.event and good.episode_id == bad.episode_id and not good.episode_started


def test_zero_rs_rearms_and_flat_own_direction_passes_guard():
    s = LeadershipStream(Specification(1,1))
    accept(s,0)
    first = accept(s,1,100,99)
    assert first.guard and first.event
    flat = accept(s,2,100,99)
    assert flat.relative_return == 0 and flat.episode_id is None
    assert accept(s,3,100,98).event


def test_gap_and_missing_reset_warmup_without_inventing_another_episode():
    s = LeadershipStream(Specification(2,1))
    accept(s,0)
    accept(s,1,101)
    initial = accept(s,2,102)
    a,b = pair(3,103)
    missing = s.accept(a,None,a.end_at)
    assert missing.episode_id == initial.episode_id
    assert not accept(s,4,104).rs_ready
    assert not accept(s,5,105).rs_ready
    resumed = accept(s,6,106)
    assert resumed.leadership and not resumed.event
    gap = accept(s,8,108)
    assert gap.reason == 'gap_warmup' and not gap.rs_ready
    accept(s,9,109)
    assert not accept(s,10,110).event


def test_calendar_session_boundary_continuity_and_no_session_rearm():
    s = LeadershipStream(Specification(1,1))
    accept(s,62)
    first = accept(s,63,101)
    a,b = pair(0,102)
    shift = timedelta(days=1)
    a,b = (replace(bar, start_at=bar.start_at+shift, end_at=bar.end_at+shift,
                   known_at=bar.known_at+shift, session='2026-05-06') for bar in (a,b))
    result = s.accept(a,b,a.end_at)
    assert result.rs_ready and result.leadership and not result.event
    assert result.episode_id == first.episode_id


def test_duplicate_and_reversed_slot_rejected_without_revising_prior():
    s = LeadershipStream(Specification(1,1))
    accept(s,0)
    first = accept(s,1,101)
    old = payload(first)
    with pytest.raises(ValueError, match='Duplicate'):
        accept(s,1,1000)
    assert payload(first) == old
    with pytest.raises(ValueError, match='Duplicate'):
        accept(s,0)


def test_mixed_vintage_rejected_and_nonfinite_math_fails_closed():
    s = LeadershipStream(Specification(1,1))
    accept(s,0)
    a,b = pair(1,101)
    result = s.accept(a, replace(b,dataset_id='other'), a.end_at)
    assert result.reason == 'mixed_vintage' and not result.event
    s = LeadershipStream(Specification(1,1))
    accept(s,0,1e-300)
    result = accept(s,1,1e300)
    assert result.reason == 'nonfinite_return' and not result.event


def test_deterministic_replay_same_prefix_future_suffix_invariant():
    def replay(values):
        s = LeadershipStream(Specification(2,2))
        return [payload(accept(s,i,own,bench)) for i,(own,bench) in enumerate(values)]
    prefix = [(100,100),(101,100),(102,100),(103,100),(104,100)]
    published = replay(prefix)
    assert published == replay(prefix)
    assert published == replay(prefix+[(200,50),(50,200)])[:len(prefix)]
    assert published == replay(prefix+[(10,500),(1000,5)])[:len(prefix)]


@pytest.mark.parametrize('args', [(0,1),(1,0),(True,1),(1,1.5)])
def test_invalid_spec(args):
    with pytest.raises(ValueError):
        Specification(*args)
