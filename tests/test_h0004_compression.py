import ast
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
import json
from pathlib import Path
from unittest.mock import patch
import pytest

from richping.core import sessions
from richping.research_v2.sessions import EXTENDED, session_bounds
from richping.research_v2.contracts import payload
from richping.research_v2.strategy.h0004_compression import (
    CompressionStream, Specification, OHLCBar)
from scripts import h0004_frequency_audit as runner


def bars(count=40, day='2026-05-05'):
    result = []
    for session in sessions(day, '2026-08-13'):
        try:
            opened, closed = session_bounds(session, EXTENDED)
        except ValueError:
            break
        at = opened+timedelta(minutes=15)
        while at <= closed and len(result) < count:
            # Wide baseline, then quiet range [99.5,100.5].
            width = 4 if len(result) < 6 else 0.5
            result.append(OHLCBar('fixture', 'SOXX', at, at, session,
                                  100, 100+width, 100-width, 100))
            at += timedelta(minutes=15)
        if len(result) == count:
            break
    return result


def setup(expiration=4):
    data = bars()
    stream = CompressionStream(Specification(2,4,0.25,expiration))
    steps = [stream.accept(b) for b in data[:8]]
    assert steps[-1].range_published
    return stream, data, steps


def test_exact_window_history_boundary_and_current_excluded():
    stream, data, steps = setup()
    assert steps[0].feature.reason == 'window_warmup'
    assert all(s.feature.reason == 'history_warmup' for s in steps[1:5])
    assert steps[5].feature.status == 'READY'
    assert steps[7].feature.normalized_range == 0.01
    assert steps[7].feature.percentile == 0  # All four previous ranges wide.
    assert steps[7].feature.high == 100.5 and steps[7].feature.low == 99.5
    # Next equal range has one historical equal observation; ties are included.
    assert stream.accept(data[8]).feature.percentile == 0.25


def test_price_scaling_does_not_change_compression():
    data = bars(14)
    original, scaled = CompressionStream(Specification(2,4,.25,4)), CompressionStream(Specification(2,4,.25,4))
    for b in data:
        a = original.accept(b).feature
        c = scaled.accept(replace(b,open=b.open*10,high=b.high*10,low=b.low*10,close=b.close*10)).feature
        assert a == c if a.high is None else (a.normalized_range,a.percentile,a.compressed) == (c.normalized_range,c.percentile,c.compressed)


def test_suffix_cannot_change_prior_features_ranges_events():
    data = bars(30)
    spec = Specification(2,4,.25,4)
    def run(seq):
        stream = CompressionStream(spec)
        return [payload(stream.accept(b)) for b in seq]
    before = run(data[:12])
    altered = data[:12]+[replace(b,open=500,high=600,low=400,close=550) for b in data[12:]]
    assert before == run(data)[:12] == run(altered)[:12]


@pytest.mark.parametrize('close,high,event', [(100.5,101,False),(100,101,False),(100.500001,101,True)])
def test_breakout_strict_completed_close_not_touch(close,high,event):
    stream,data,steps = setup()
    frozen = stream.range
    result = stream.accept(replace(data[8],high=high,close=close))
    assert bool(result.events) is event
    assert result.range_before == frozen
    assert frozen.high == 100.5 and frozen.low == 99.5
    with pytest.raises(FrozenInstanceError):
        frozen.high = 999
    assert not steps[-1].events  # Publication cannot be a breakout.


def test_one_candidate_and_duplicate_or_correction_before_mutation():
    stream,data,_ = setup()
    b = replace(data[8],high=102,close=101)
    event = stream.accept(b).events[0]
    state = stream._index, tuple(stream._window), tuple(stream._ranges), stream._armed
    for duplicate in (b, replace(b,high=103,close=102)):
        with pytest.raises(ValueError,match='Duplicate/correction'):
            stream.accept(duplicate)
        assert state == (stream._index,tuple(stream._window),tuple(stream._ranges),stream._armed)
    for b in data[9:13]:
        assert not stream.accept(replace(b,open=101,high=103,low=100.5,close=102)).events
    assert event.episode_id


@pytest.mark.parametrize('offset,expected', [(4,True),(5,False)])
def test_expiration_exact_boundary(offset,expected):
    stream,data,_ = setup(expiration=4)
    for b in data[8:7+offset]:
        assert not stream.accept(b).events
    result = stream.accept(replace(data[7+offset],high=102,close=101))
    assert bool(result.events) is expected
    assert result.retirement == ('consumed' if expected else 'expired')


@pytest.mark.parametrize('close,retired', [(99.5,None),(99.499999,'downside_cancelled')])
def test_downside_cancellation_strict_boundary(close,retired):
    stream,data,_ = setup()
    result = stream.accept(replace(data[8],low=99,close=close))
    assert result.retirement == retired and not result.events


def test_expiry_does_not_rearm_without_noncompression_then_new_compression():
    stream,data,_ = setup(expiration=1)
    stream.accept(data[8])
    result = stream.accept(data[9])
    assert result.retirement == 'expired' and result.range_published is None
    # Explicit wide window -> noncompression, followed by fresh quiet window.
    assert stream.accept(replace(data[10],high=104,low=96)).feature.compressed is False
    stream.accept(replace(data[11],high=100.1,low=99.9))
    result = stream.accept(replace(data[12],high=100.1,low=99.9))
    assert result.range_published and result.range_published.published_index == 12


def test_gap_cancels_resets_all_warmup_and_cannot_rearm():
    stream,data,_ = setup()
    result = stream.accept(data[9])  # Missing scheduled slot 8.
    assert result.retirement == 'gap_cancelled' and not result.events
    assert result.feature.reason == 'window_warmup'
    assert stream.range is None and stream._armed is False
    later = [stream.accept(b) for b in data[10:15]]
    assert all(s.range_published is None for s in later)
    assert later[-2].feature.reason == 'history_warmup'
    assert later[-1].feature.status == 'READY'


@pytest.mark.parametrize('field,value', [('close',0),('close',float('nan')),('high',float('inf')),
                                        ('low',-1),('close',True),('symbol','QQQ')])
def test_invalid_prices_and_symbol_fail_closed(field,value):
    stream,data,_ = setup()
    result = stream.accept(replace(data[8],**{field:value}))
    assert result.input_status == 'INVALID' and not result.events and stream.range is None
    assert stream.accept(data[9]).input_reason == 'stream_invalid'


def test_zero_history_and_zero_current_range_are_finite():
    spec = Specification(2,4,.25,4)
    data = [replace(b,open=100,high=100,low=100,close=100) for b in bars(10)]
    stream = CompressionStream(spec)
    results = [stream.accept(b) for b in data]
    assert results[-1].feature.reason == 'zero_history_range'
    assert not any(s.range_published for s in results)
    stream,data,_ = setup()
    result = stream.accept(replace(data[8],high=100,low=100,close=100))
    assert result.feature.normalized_range >= 0


@pytest.mark.parametrize('kind', ['future','unavailable','offgrid','early_close','mixed','session'])
def test_clock_slot_and_vintage_fail_closed(kind):
    stream,data,_ = setup()
    b = data[8]
    if kind == 'future':
        b = replace(b,known_at=b.end_at-timedelta(seconds=1))
    elif kind == 'unavailable':
        assert stream.accept(b,b.known_at-timedelta(seconds=1)).input_status == 'INVALID'
        return
    elif kind == 'offgrid':
        b = replace(b,end_at=b.end_at+timedelta(seconds=1),known_at=b.known_at+timedelta(seconds=1))
    elif kind == 'early_close':
        at = b.end_at.replace(month=11,day=27)
        b = replace(b,end_at=at,known_at=at,session='2026-11-27')
    elif kind == 'mixed':
        b = replace(b,dataset_id='other')
    else:
        b = replace(b,session='2026-05-06')
    assert stream.accept(b).input_status == 'INVALID'


def test_next_official_session_is_contiguous_and_age_is_slots():
    data = bars(70)
    stream = CompressionStream(Specification(2,4,.25,100))
    steps = [stream.accept(b) for b in data]
    assert steps[64].input_reason == 'completed_price'
    assert steps[64].feature.status == 'READY'
    assert stream._index == 69


def test_missing_entire_session_is_gap_and_unsupported_session_not_holiday():
    data = bars(192)
    stream = CompressionStream(Specification(2,4,.25,100))
    for b in data[:64]: stream.accept(b)
    assert stream.accept(data[128]).input_reason == 'gap_reset'
    # An unsupported early close cannot be skipped as a normal calendar closure.
    before = OHLCBar('fixture','SOXX',*([session_bounds('2026-11-25',EXTENDED)[1]]*2),'2026-11-25',100,101,99,100)
    after = OHLCBar('fixture','SOXX',*([session_bounds('2026-11-30',EXTENDED)[0]+timedelta(minutes=15)]*2),'2026-11-30',100,101,99,100)
    stream = CompressionStream(Specification(2,4,.25,100))
    stream.accept(before)
    assert stream.accept(after).input_reason == 'gap_reset'


def test_deterministic_repeat_and_input_namespace_independence():
    spec = Specification(2,4,.25,4)
    data = bars(30)
    assert runner.replay(data,spec) == runner.replay(data,spec)
    for path in (Path('richping/research_v2/strategy/h0004_compression.py'),Path('scripts/h0004_frequency_audit.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        imports = [n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        imports += [a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
        assert all(not any(x in name for x in ('h0001','h0002','h0003','efficacy','outcome')) for name in imports)


def test_outcome_guard_counts_and_fails_before_query():
    import richping.engine
    with runner.no_outcomes() as calls:
        with pytest.raises(AssertionError,match='future_return_queries'):
            richping.engine.observe(None)
    assert calls['future_return_queries'] == 1


def test_real_registry_advances_to_h0005_with_h0004_selected():
    from scripts.prepare_independent_research import prepare
    result = prepare()
    assert result['next_hypothesis_id'] == 'H0005'
    assert any(e['id']=='H0004' for e in result['registered_hypotheses'])
    assert result['future_confirmation_dependency'] is False


def test_real_admission_frequency_evidence_and_prior_preservation():
    manifest = runner.verify_manifest()
    assert all(any(x in p for p in manifest['preserved_files']) for x in ('H0001','H0002','H0003'))
    with runner.no_outcomes() as calls:
        data = runner.load_admitted()
        prefix = runner.replay(data.bars[:700],Specification())
    assert not any(calls.values())
    assert prefix['denominators']['compression_feature_READY_bars'] == 45
    report = json.loads((runner.ROOT/'frequency-audit.json').read_bytes())
    assert report['outcome_access'] == 0 and not any(report['forbidden_call_counts'].values())
    assert report['parameter_trials'] == 1 and report['comparators'] == 0
    assert report['repeat_equal'] and report['prefix_equal'] and report['prior_evidence_unchanged']
    events = json.loads((runner.ROOT/'candidate-events.json').read_bytes())['events']
    assert len(events) == len({e['id'] for e in events}) == len({e['episode_id'] for e in events})
    assert len(events) == report['denominators']['final_candidate_events']
