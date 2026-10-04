from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from unittest.mock import patch

import pytest
import yaml

from richping.core import digest, sessions
from richping.research_v2.contracts import payload
from richping.research_v2.sessions import EXTENDED, session_bounds
from richping.research_v2.strategy.h0002_defense import (
    Specification, DefenseStream, PriceBar, PRIMARY, volume_confirmation)
from richping.research_v2.strategy.h0002_experiment import (
    ControlAnchor, select_controls, calendar_contract, disposition)
from scripts import h0002_signal_preregister as sealed


def production_bars():
    values = []
    for day in sessions('2026-05-05', '2026-05-08'):
        start, _ = session_bounds(day, EXTENDED)
        for i in range(64):
            n = len(values)
            low = {120: 100, 124: 100.5, 255: 97}.get(n, 104)
            end = start + timedelta(minutes=15*(i+1))
            values.append(PriceBar('fixture', 'SOXX', end, end, day, 106, 108, low, 106, 10))
    return values


def test_actual_128_slot_expiration_publication_and_immutable_boundaries():
    stream = DefenseStream()
    steps = [stream.accept(b) for b in production_bars()]
    zone = steps[127].zone_published
    assert zone and zone.created_index == 127 and zone.expires_index == 255
    assert not steps[127].events and steps[127].zone_before is None
    assert all(s.zone_before == zone for s in steps[128:255])
    assert steps[255].zone_before is None and steps[255].retired_reason == 'expired'
    assert not steps[255].events  # strict reclaim on exact expiration cannot use old zone
    assert stream._index == 255  # overnight closure consumes no slot


def test_multibar_recovery_is_not_same_bar_reclaim():
    values = production_bars()
    stream = DefenseStream()
    for bar in values[:128]:
        stream.accept(bar)
    zone = stream.zone
    first = stream.accept(replace(values[128], low=97, open=101, close=101))
    later = stream.accept(replace(values[129], low=100, close=106))
    assert first.interaction.flag and first.events == later.events == ()
    assert first.zone_before == later.zone_before == zone
    assert not later.rejection.flag  # prior bar's break cannot be carried into recovery
    stream.accept(values[130])  # whole bar above rearms
    assert stream.accept(replace(values[131], low=97)).events[0].family == PRIMARY


@pytest.mark.parametrize('offset,valid', [(0, False), (1, True), (22, True), (48, True), (64, True), (65, False)])
def test_exact_full_extended_session_edges(offset, valid):
    bar = production_bars()[0]
    start, _ = session_bounds(bar.session, EXTENDED)
    end = start + timedelta(minutes=15*offset)
    step = DefenseStream().accept(replace(bar, end_at=end, known_at=end))
    assert (step.input.status == 'READY') is valid


def test_production_volume_baseline_excludes_current_and_zero_is_not_missing():
    values = production_bars()
    spec = Specification()
    stage, ratio = volume_confirmation(replace(values[20], volume=1000), values[:20], spec)
    assert stage.flag and ratio == 100
    assert volume_confirmation(replace(values[20], volume=0), values[:20], spec)[1] == 0
    assert volume_confirmation(replace(values[20], volume=None), values[:20], spec)[0].status == 'UNAVAILABLE'


def test_default_price_event_hash_independent_of_all_volume():
    values = production_bars()[:130]
    values[128] = replace(values[128], low=97)
    def replay(inputs):
        stream = DefenseStream()
        return [e for b in inputs for e in stream.accept(b).events if e.family == PRIMARY]
    assert replay(values) == replay([replace(b, volume=None) for b in values])
    assert digest(payload(replay(values))) == digest(payload(replay(values)))


def anchors():
    event = ControlAnchor('2026-10-19', '10:00', -1, True, True)
    prior = sessions('2026-09-21', '2026-10-16')
    return event, [ControlAnchor(day, '10:00', -1, True, False) for day in prior]


def test_baseline_selection_is_prior_only_exact_slot_state_and_non_event():
    event, inputs = anchors()
    selected = select_controls(event, inputs)
    assert len(selected) == 5 and list(selected) == sorted(inputs, key=lambda a: a.session, reverse=True)[:5]
    changed = [replace(a, primary_event=True) for a in inputs[-2:]]
    extras = [event, replace(event, session='2026-10-20'), replace(inputs[-1], local_slot='10:15'),
              replace(inputs[-1], prior_four_sign=1), replace(inputs[-1], ready=False)]
    actual = select_controls(event, inputs[:-2] + changed + extras)
    assert actual == tuple(reversed(inputs[-7:-2]))
    assert select_controls(event, inputs[:4]) is None  # no fallback
    with pytest.raises(ValueError, match='Duplicate'):
        select_controls(event, inputs + [inputs[-1]])


def test_invalid_causal_sign_rejected():
    with pytest.raises(ValueError):
        ControlAnchor('2026-10-19', '10:00', 2, True, False)


def test_calendar_and_confirmation_are_fixed_independent_of_h0001():
    grid = calendar_contract()
    assert len(grid['anchors']) == 252 and len(grid['embargo']) == 10
    assert grid['anchors'][0] == '2026-10-19' and grid['anchors'][-1] == '2027-10-19'
    assert grid['followup'][-1] == '2027-10-22'
    body = yaml.safe_load(sealed.PROTOCOL.read_bytes())
    assert sealed.validate_protocol(body) == grid
    assert body['confirmation']['warmup_controls_start'] == anchors()[1][0].session
    assert not body['confirmation']['project_blocker']


@pytest.mark.parametrize('kwargs,expected', [
    ({'valid': False}, 'INVALID_FAIL_CLOSED'),
    ({}, 'PENDING'),
    ({'terminal': True, 'resolved': False}, 'UNRESOLVED'),
    ({'terminal': True}, 'ZERO_SIGNAL'),
    ({'terminal': True, 'events': 14, 'event_sessions': 12, 'occupied_blocks': 8}, 'INSUFFICIENT_EVIDENCE'),
    ({'terminal': True, 'events': 40, 'event_sessions': 20, 'occupied_blocks': 7}, 'INSUFFICIENT_EVIDENCE'),
    ({'terminal': True, 'events': 40, 'event_sessions': 20, 'occupied_blocks': 8}, 'INCONCLUSIVE'),
    ({'terminal': True, 'events': 40, 'event_sessions': 20, 'occupied_blocks': 8, 'positive_lower_bounds': True}, 'PASS'),
    ({'terminal': True, 'events': 40, 'event_sessions': 20, 'occupied_blocks': 8, 'negative_upper_bound': True}, 'REJECT'),
])
def test_disposition_metadata_only_gates(kwargs, expected):
    assert disposition(**kwargs) == expected


def test_invalid_disposition_inputs_fail_closed():
    with pytest.raises(ValueError):
        disposition(events=1, event_sessions=2)
    with pytest.raises(ValueError):
        disposition(positive_lower_bounds=True, negative_upper_bound=True)


@pytest.mark.parametrize('change', ['missing', 'horizon', 'baseline', 'costs', 'calendar', 'async', 'family', 'access'])
def test_incomplete_or_changed_protocol_is_rejected(change):
    body = deepcopy(yaml.safe_load(sealed.PROTOCOL.read_bytes()))
    if change == 'missing':
        body.pop('uncertainty')
    elif change == 'horizon':
        body['horizons']['primary_slots'] = 64
    elif change == 'baseline':
        body['baseline']['controls_per_event'] = 1
    elif change == 'costs':
        body['costs']['costs_bps'] = 0
    elif change == 'calendar':
        body['confirmation']['official_sessions'] = 126
    elif change == 'async':
        body['confirmation']['project_blocker'] = True
    elif change == 'family':
        body['multiple_testing']['family'].reverse()
    else:
        body['outcome_access_this_action'] = 'ALLOWED'
    with pytest.raises(ValueError):
        sealed.validate_protocol(body)


def test_preregistration_is_metadata_only_repeatable_and_preserves_all_original_sources():
    before = sealed.FREEZE.read_bytes(), (sealed.DISCOVERY/'candidate-events.json').read_bytes()
    first = sealed.run()
    assert first == sealed.run()
    assert before == (sealed.FREEZE.read_bytes(), (sealed.DISCOVERY/'candidate-events.json').read_bytes())
    assert first['primary_events'] == 14 and first['comparator_events'] == 11
    assert first['outcome_access'] == first['profitability_calculations'] == 0
    assert not any(first['forbidden_call_counts'].values())
    assert first['confirmation_disposition'] == 'PENDING'
    manifest = json.loads((sealed.ROOT/'manifest.json').read_bytes())
    assert 'richping/research_v2/strategy/h0002_defense.py' in manifest['preserved_files']
    assert any('H0001' in p for p in manifest['preserved_files'])
    assert first['event_stream_hash'] == '65174fa89f16e69f373bef0a4ea655f42b19594389d6bb9e1c472c9d47a6ae45'


def test_frozen_file_mutation_is_detected_without_market_access():
    with sealed.metadata_only() as calls:
        with patch.object(sealed, 'preservation_fingerprint', return_value='bad'):
            with pytest.raises(ValueError, match='changed'):
                sealed.verify()
    assert not any(calls.values())


def test_outcome_and_market_access_guard_fail_closed_and_count_attempt():
    with sealed.metadata_only() as calls:
        import richping.engine
        with pytest.raises(AssertionError, match='outcome_accessor'):
            richping.engine.observe(None)
        with pytest.raises(AssertionError, match='signal_replay'):
            DefenseStream().accept(production_bars()[0])
    assert calls['outcome_accessor'] == calls['signal_replay'] == 1
