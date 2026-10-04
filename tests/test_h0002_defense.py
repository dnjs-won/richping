from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import ast
import json

import pytest

from richping.core import digest
from richping.research_v2.contracts import payload
from richping.research_v2.sessions import session_bounds, EXTENDED
from richping.research_v2.strategy.h0002_defense import (
    Specification, PriceBar, DefenseStream, PRIMARY, COMPARATOR,
    rejection_geometry, volume_confirmation)
from scripts.h0002_frequency_audit import ROOT, verify_manifest, audit, no_outcomes


SMALL = Specification(8, 2, 12, 3, 1.0)  # Synthetic edge fixtures only, never real-data trials.


def bars(lows=(104, 100, 104, 104, 100.5, 104, 104, 104, 97, 97, 104, 97), volume=10):
    start, _ = session_bounds('2026-05-05', EXTENDED)
    return tuple(PriceBar('fixture', 'SOXX', start+timedelta(minutes=15*(i+1)),
                         start+timedelta(minutes=15*(i+1)), '2026-05-05', 106, 108, low, 106, volume)
                 for i, low in enumerate(lows))


def run(inputs, spec=SMALL):
    stream = DefenseStream(spec)
    return stream, tuple(stream.accept(b) for b in inputs)


def primary(steps):
    return [e for s in steps for e in s.events if e.family == PRIMARY]


def test_prefix_equivalence_and_future_suffix_cannot_change_published_zone():
    sample = bars()
    _, prefix = run(sample[:8])
    _, entire = run(sample)
    _, changed_future = run((*sample[:8], *(replace(b, low=50) for b in sample[8:])))
    assert prefix == entire[:8] == changed_future[:8]
    zone = prefix[-1].zone_published
    assert zone and zone.source_pair[-1][0] == 4
    assert all(p[1] < zone.created_at for p in zone.source_pair)
    assert not prefix[-1].events  # publication bar cannot use newly formed zone
    assert entire[8].zone_before == zone
    with pytest.raises(FrozenInstanceError):
        zone.lower = 1


def test_right_confirmation_is_required_and_tied_lows_are_not_strict_pivots():
    # Last bar low has no right neighbor. Equal neighbor excludes a pivot.
    _, steps = run(bars((104, 100, 100, 104, 100.5, 104, 104, 99)))
    assert steps[-1].construction.status == 'READY'
    assert steps[-1].zone_published is None


def test_past_revision_and_duplicate_cannot_mutate_active_zone_or_future_decision():
    sample = bars()
    stream, _ = run(sample[:8])
    original_zone = stream.zone
    with pytest.raises(ValueError, match='revision'):
        stream.accept(replace(sample[1], low=90))
    with pytest.raises(ValueError, match='Duplicate'):
        stream.accept(sample[7])
    assert stream.zone == original_zone
    next_step = stream.accept(sample[8])
    assert next_step == run(sample[:9])[1][-1]


def test_one_candidate_per_visit_and_rearm_after_whole_bar_above():
    _, steps = run(bars())
    assert [s.interaction.flag for s in steps[8:]] == [True, False, False, True]
    assert [len(s.events) for s in steps[8:]] == [2, 0, 0, 2]
    assert steps[9].rejection.flag is True  # occurrence differs from deduplicated event
    events = primary(steps)
    assert len({e.id for e in events}) == len(events) == 2
    assert events[0].visit_id != events[1].visit_id
    with pytest.raises(FrozenInstanceError):
        events[0].session = 'changed'


@pytest.mark.parametrize('which', ['touch', 'lower_equality', 'close_equality', 'strict_reclaim'])
def test_exact_reentry_and_reclaim_boundaries(which):
    sample = bars()
    stream, _ = run(sample[:8])
    zone = stream.zone
    b = sample[8]
    if which == 'touch':
        b = replace(b, low=zone.upper)
    elif which == 'lower_equality':
        b = replace(b, low=zone.lower)
    elif which == 'close_equality':
        b = replace(b, close=zone.upper)
    s = stream.accept(b)
    assert s.interaction.flag is True
    assert s.touch == (which == 'touch')
    assert s.penetration == (which != 'touch')
    assert s.rejection.flag == (which == 'strict_reclaim')


def test_flat_bar_wick_and_reclaim_math():
    stream, _ = run(bars()[:8])
    zone = stream.zone
    flat = replace(bars()[8], open=106, high=106, low=106, close=106)
    assert rejection_geometry(flat, zone) == (False, None)
    b = replace(bars()[8], close=104)
    rejection, wick = rejection_geometry(b, zone)
    assert rejection and wick == pytest.approx(7/11)


@pytest.mark.parametrize('current,history,status,reason,ratio', [
    (0, 10, 'READY', 'relative_volume', 0),
    (None, 10, 'UNAVAILABLE', 'missing_volume', None),
    (10, None, 'UNAVAILABLE', 'missing_volume', None),
    (10, 0, 'UNAVAILABLE', 'zero_volume_baseline', None),
    (-1, 10, 'INVALID', 'invalid_volume', None),
    (float('nan'), 10, 'INVALID', 'invalid_volume', None),
    (10, 10, 'READY', 'relative_volume', 1),
])
def test_volume_zero_missing_invalid_distinct(current, history, status, reason, ratio):
    sample = bars(volume=history)
    stage, value = volume_confirmation(replace(sample[8], volume=current), sample[:8], SMALL)
    assert (stage.status, stage.reason, value) == (status, reason, ratio)


def test_volume_baseline_excludes_current_and_comparator_is_nested():
    sample = bars()
    stage, ratio = volume_confirmation(replace(sample[8], volume=100), sample[:8], SMALL)
    assert stage.flag is True and ratio == 10
    _, steps = run((*sample[:8], replace(sample[8], volume=0), *sample[9:]))
    assert steps[8].volume.status == 'READY' and not steps[8].volume.flag
    assert len(steps[8].events) == 1
    assert steps[9].events == ()  # higher-volume later rejection cannot create unmatched comparator


def test_price_only_has_identical_events_without_volume_and_invalid_volume_only_blocks_comparator():
    sample = bars()
    _, present = run(sample)
    _, absent = run(tuple(replace(b, volume=None) for b in sample))
    _, invalid = run(tuple(replace(b, volume=-1) for b in sample))
    assert primary(present) == primary(absent) == primary(invalid)
    assert all(e.family == PRIMARY for s in absent for e in s.events)
    assert all(s.volume.status == 'UNAVAILABLE' for s in absent)
    assert any(s.volume.status == 'INVALID' for s in invalid)


def test_close_below_invalidates_and_used_seed_cannot_republish():
    sample = bars()
    stream, _ = run(sample[:8])
    step = stream.accept(replace(sample[8], close=97))
    assert step.retired_reason == 'close_below_lower'
    assert stream.zone is None and step.events == ()
    # Do not introduce a newly right-confirmed lower pivot while checking seed reuse.
    step = stream.accept(replace(sample[9], low=96))
    assert stream.zone is None and step.zone_published is None


def test_exact_expiration_and_gap_reset_warmup():
    sample = bars()
    _, steps = run(sample, replace(SMALL, expiration_bars=2))
    assert steps[8].zone_before and steps[9].zone_before is None
    assert steps[9].retired_reason == 'expired'
    stream, _ = run(sample[:8])
    s = stream.accept(sample[9])
    assert s.input.reason == 'gap_reset' and s.construction.status == 'UNAVAILABLE'
    assert s.zone_before is None and not s.events


@pytest.mark.parametrize('mutation', ['future', 'bad_price', 'mixed_vintage', 'wrong_symbol', 'off_grid'])
def test_invalid_input_fail_closed(mutation):
    sample = bars()
    stream, _ = run(sample[:8])
    b = sample[8]
    changes = {'future': {'known_at': b.end_at-timedelta(seconds=1)},
               'bad_price': {'low': 109}, 'mixed_vintage': {'dataset_id': 'revision'},
               'wrong_symbol': {'symbol': 'QQQ'}, 'off_grid': {'end_at': b.end_at-timedelta(seconds=1)}}
    step = stream.accept(replace(b, **changes[mutation]))
    assert step.input.status == 'INVALID' and not step.events
    assert stream.accept(sample[9]).input.status == 'INVALID'


def test_zero_range_is_unavailable_and_same_input_deterministic():
    sample = tuple(replace(b, low=106, high=106) for b in bars())
    _, first = run(sample)
    assert first == run(sample)[1]
    assert first[-1].construction.reason == 'zero_price_range'
    assert not primary(first)


def test_production_window_not_fixture_tuning():
    lows = [104]*128
    lows[120], lows[124] = 100, 100.5
    # Supply the actual 128 slots over two calendar sessions.
    source = []
    for day in ('2026-05-05', '2026-05-06', '2026-05-07'):
        start, _ = session_bounds(day, EXTENDED)
        for i in range(64):
            source.append(PriceBar('fixture', 'SOXX', start+timedelta(minutes=15*(i+1)),
                                  start+timedelta(minutes=15*(i+1)), day, 106, 108,
                                  lows[len(source)] if len(source) < 128 else 97, 106, 10))
    _, steps = run(source[:129], Specification())
    assert all(s.construction.status == 'UNAVAILABLE' for s in steps[:127])
    assert steps[127].zone_published and len(steps[128].events) == 2


def test_signal_module_does_not_import_h0001_macd_or_outcome_modules():
    path = Path('richping/research_v2/strategy/h0002_defense.py')
    tree = ast.parse(path.read_text(encoding='utf-8'))
    imports = [n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(set(m.split('.')) & {'h0001', 'macd', 'engine', 'evaluation', 'store', 'data'} for m in imports)


def test_guard_attempt_is_counted_and_fails_closed():
    with no_outcomes() as counts:
        # Resolve inside the patch, avoiding a pre-imported callable bypass.
        import richping.engine
        with pytest.raises(AssertionError, match='outcome_accessor'):
            richping.engine.observe(None)
        assert counts['outcome_accessor'] == 1


def test_real_sealed_frequency_evidence_outcome_access_zero_and_preservation():
    manifest = verify_manifest()
    before = (ROOT/'frequency-audit.json').read_bytes()
    report = audit()
    assert before == (ROOT/'frequency-audit.json').read_bytes()
    assert report == json.loads(before)
    assert report['runs'] == 2 and report['repeat_equal']
    assert report['denominators']['total_eligible_15m_bars'] == 4480
    assert report['denominators']['final_candidate_count'] > 0
    assert report['overlap']['comparator_only'] == 0
    assert not any(report['forbidden_call_counts'].values())
    assert report['outcome_access'] == report['profitability_calculations'] == 0
    assert report['H0001_preserved_files'] == len(manifest['preserved_files'])
    events = json.loads((ROOT/'candidate-events.json').read_bytes())['events']
    assert report['event_stream_hash'] == digest(events)
    assert all(e['snapshot']['zone']['created_at'] < e['at'] for e in events)
    assert report['H0001_frozen_hashes_unchanged']
