from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import pytest

from richping.core import sessions, digest
from richping.research_v2.sessions import EXTENDED,session_bounds,segment
from richping.research_v2.contracts import payload
from richping.research_v2.strategy.h0004_segment_compression import (
    OHLCBar,Specification,CompressionStream,previous_official_sessions,Range,SEGMENTS)
from scripts import h0004_segment_frequency as runner


def make_bars(days=13):
    result = []
    for index,day in enumerate(sessions('2026-05-05','2026-08-13')[:days]):
        opened,closed = session_bounds(day,EXTENDED)
        end = opened+timedelta(minutes=15)
        while end<=closed:
            part = segment(end-timedelta(minutes=15),end)
            width = {'PREMARKET':2,'RTH':4,'AFTER_HOURS':1}[part]
            width *= 1+(index%3)/10
            result.append(OHLCBar('fixture','SOXX',end,end,day,100,100+width,100-width,100))
            end += timedelta(minutes=15)
    return result


@pytest.mark.parametrize('slot,expected',[(21,'PREMARKET'),(22,'RTH'),(47,'RTH'),(48,'AFTER_HOURS'),(63,'AFTER_HOURS')])
def test_segment_exact_boundaries(slot,expected):
    b = make_bars(1)[slot]
    assert segment(b.end_at-timedelta(minutes=15),b.end_at)==expected


@pytest.mark.parametrize('part,slot,reference_count',[('PREMARKET',0,205),('RTH',22,260),('AFTER_HOURS',48,160)])
def test_same_segment_previous_ten_completed_sessions_only(part,slot,reference_count):
    data = make_bars(12)
    stream = CompressionStream()
    for b in data[:640+slot+1]: step = stream.accept(b)
    feature = step.feature
    assert feature.status=='READY' and feature.segment==part
    assert feature.reference_count==reference_count
    reference = stream._reference[part]
    assert len(reference)==reference_count
    assert {d for d,_,_ in reference}==set(previous_official_sessions(data[640].session))
    assert all(d<data[640].session and segment(at-timedelta(minutes=15),at)==part for d,at,_ in reference)
    assert feature.percentile==sum(v<=feature.normalized_range for _,_,v in reference)/len(reference)
    assert feature.reference_hash==digest(payload(reference))
    # Independent manual price-window construction, grouped by endpoint segment.
    expected = []
    for i in range(15,640):
        b = data[i]
        if segment(b.end_at-timedelta(minutes=15),b.end_at)!=part: continue
        window = data[i-15:i+1]
        expected.append((b.session,b.end_at,(max(x.high for x in window)-min(x.low for x in window))/b.close))
    assert tuple(expected)==reference


def test_current_session_earlier_measurements_never_enter_reference():
    data = make_bars(12)
    stream = CompressionStream()
    for b in data[:640]: stream.accept(b)
    references = {}
    for b in data[640:704]:
        result = stream.accept(replace(b,high=200,low=50))
        f = result.feature
        if f.segment in references:
            assert (f.reference_hash,f.reference_count)==references[f.segment]
        references[f.segment]=(f.reference_hash,f.reference_count)
        assert all(d!=b.session for d,_,_ in stream._reference[f.segment])
    assert sum(len(v) for v in stream._measurements.values())==64


def test_exact_previous_ten_official_sessions_drop_oldest_not_last_available():
    data = make_bars(12)
    stream = CompressionStream()
    for b in data[:705]: step = stream.accept(b)
    expected = tuple(data[i*64].session for i in range(1,11))
    assert step.feature.reference_sessions==expected
    assert step.feature.reference_count==220
    assert data[0].session not in stream._past


def test_readiness_boundary_and_initial_eligible_warmup_denominator():
    data = make_bars(11)
    stream = CompressionStream()
    results = [stream.accept(b) for b in data]
    assert all(x.feature.status=='UNAVAILABLE' for x in results[:640])
    assert results[0].feature.reason=='window_warmup'
    assert results[15].feature.reason=='reference_sessions_unavailable'
    assert all(x.feature.status=='READY' for x in results[640:])
    assert results[640].feature.reference_count==205


def test_future_suffix_cannot_alter_published_prior_feature_range_or_event():
    data = make_bars(13)
    cutoff = 730
    def run(seq):
        stream = CompressionStream()
        return [payload(stream.accept(b)) for b in seq]
    prefix = run(data[:cutoff])
    future = [replace(b,open=1000,high=2000,low=500,close=1500) for b in data[cutoff:]]
    assert run(data)[:cutoff]==prefix==run(data[:cutoff]+future)[:cutoff]


def test_cross_session_price_window_and_market_closure_consume_no_slot():
    data = make_bars(12)
    stream = CompressionStream()
    for b in data[:704]: stream.accept(b)
    index = stream._index
    old = tuple(stream._window)
    feature = stream.accept(data[704]).feature
    assert stream._index==index+1
    assert tuple(stream._window)==(*old[1:],data[704])
    assert feature.high==max(b.high for b in (*old[1:],data[704]))
    assert feature.normalized_range==(max(b.high for b in (*old[1:],data[704]))-min(b.low for b in (*old[1:],data[704])))/100
    assert feature.status=='READY'


def test_episode_can_survive_closure_with_inclusive_slot_validity():
    data = make_bars(12)
    stream = CompressionStream()
    for b in data[:704]: step = stream.accept(b)
    anchor = stream._index
    stream.range = Range('fixture-episode',101,90,data[703].known_at,data[688].end_at,anchor,anchor+16,'fixture',step.feature)
    for b in data[704:719]: assert not stream.accept(b).events
    result = stream.accept(replace(data[719],high=103,close=102))
    assert result.events and result.events[0].episode_id=='fixture-episode'
    assert stream._index==anchor+16


def test_expiry_slot17_and_lower_equality_unchanged():
    data = make_bars(12)
    stream = CompressionStream()
    for b in data[:704]: step = stream.accept(b)
    anchor = stream._index
    stream.range = Range('fixture',150,100,data[703].known_at,data[688].end_at,anchor,anchor+16,'fixture',step.feature)
    for b in data[704:720]:
        assert stream.accept(b).retirement is None  # close == low never cancels.
    result = stream.accept(replace(data[720],high=200,close=151))
    assert result.retirement=='expired' and not result.events


def test_gap_clears_reference_cancels_disarms_and_incomplete_session_cannot_count():
    data = make_bars(13)
    stream = CompressionStream()
    for b in data[:645]: step = stream.accept(b)
    stream.range = Range('fixture',150,50,data[644].known_at,data[629].end_at,644,660,'fixture',step.feature)
    result = stream.accept(data[646])
    assert result.input_reason=='gap_reset' and result.retirement=='gap_cancelled'
    assert result.feature.reference_status=='UNAVAILABLE' and result.feature.reason=='window_warmup'
    assert not stream._armed and not stream._past
    for b in data[647:705]: step = stream.accept(b)
    assert not stream._past[data[640].session][0]
    assert step.feature.status=='UNAVAILABLE' and not step.events


def test_unsupported_input_fails_closed():
    b = make_bars(1)[0]
    at = b.end_at.replace(month=11,day=27)
    stream = CompressionStream()
    result = stream.accept(replace(b,end_at=at,known_at=at,session='2026-11-27'))
    assert result.input_status=='INVALID'
    assert stream.accept(b).input_reason=='stream_invalid'


def test_missing_entire_official_session_cannot_select_older_reference_days():
    data = make_bars(13)
    stream = CompressionStream()
    for b in data[:640]: stream.accept(b)
    result = stream.accept(data[704])
    assert result.input_reason=='gap_reset'
    assert result.feature.reference_sessions==previous_official_sessions(data[704].session)
    assert result.feature.reference_status=='UNAVAILABLE'


def test_duplicate_correction_cannot_retrigger_or_change_reference():
    data = make_bars(11)
    stream = CompressionStream()
    for b in data: stream.accept(b)
    state = stream._index,stream._reference,stream._measurements,stream.range
    with pytest.raises(ValueError,match='Duplicate/correction'): stream.accept(replace(data[-1],high=999))
    assert state==(stream._index,stream._reference,stream._measurements,stream.range)


@pytest.mark.parametrize('field,value',[('close',0),('high',float('inf')),('close',float('nan'))])
def test_invalid_normalization_fails_closed(field,value):
    stream = CompressionStream()
    result = stream.accept(replace(make_bars(1)[0],**{field:value}))
    assert result.input_status=='INVALID' and not result.events


def test_repeated_hashes_and_outcome_access_zero_on_fixture():
    data = make_bars(12)
    with runner.no_outcomes() as calls:
        first,second = runner.replay(data),runner.replay(data)
    assert first==second and not any(calls.values())


def test_real_sealed_trial2_and_immutable_trial1():
    manifest = runner.verify_manifest()
    report = json.loads((runner.ROOT/'frequency-audit.json').read_bytes())
    assert manifest['trial1']['identity']=='TRIAL_1_POOLED_SEGMENT_REFERENCE'
    assert report['parameter_trials']==2 and report['outcome_access']==0
    assert not any(report['forbidden_call_counts'].values())
    assert report['counts']['candidates']>0 and report['repeat_equal'] and report['prefix_equal']
    from scripts.h0004_verify import verify
    assert verify(tests=False)['counts']['final_candidate_events']==39
