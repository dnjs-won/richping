from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from richping.core import digest
from richping.research_v2.alpaca_data import intraday_dataset, daily_parent
from richping.research_v2.daily_data import DailyVintage
from richping.research_v2.daily_identity import admit_identity_interval
from richping.research_v2.contracts import JsonObject
from richping.research_v2.store import ResearchStore
from richping.research_v2.real_data import expected_slots, request
from richping.research_v2.strategy.daily_input import prepare_daily
from scripts.h0001_alpaca_70_discovery import ROOT, load_capture, audit, INTRADAY_ID, DAILY_ID
from scripts.h0001_entry_efficacy_preregister import verify
from scripts.h0001_long_history_audit import write_new


@pytest.fixture(scope='module')
def inputs():
    capture = load_capture()
    admission, action, unit = audit(capture)
    daily = admit_identity_interval(daily_parent(capture, DAILY_ID+'-parent'), DAILY_ID, action, unit)
    intraday = intraday_dataset(capture, admission, INTRADAY_ID)
    return capture, admission, action, unit, daily, intraday


def test_real_separate_admission_recomputed_offline(inputs):
    capture, admission, action, unit, daily, intraday = inputs
    with patch('socket.socket.connect', side_effect=AssertionError('network')), patch('curl_cffi.requests.get', side_effect=AssertionError('network')):
        assert (admission, action, unit) == audit(load_capture())
    assert admission == json.loads((ROOT/'admission.json').read_bytes())
    assert admission['sessions'] == 70 and admission['daily_sessions'] == 465
    assert admission['old_certificate_inherited'] is False
    assert admission['volume']['zero_volume_bars'] == 0
    assert daily.dataset_id.startswith('soxx-alpaca-sip')
    assert intraday.manifest.unpack()['feed'] == 'sip'


def test_exact_grid_dst_and_no_synthetic_filling(inputs):
    intraday = inputs[-1]
    slots, unsupported = expected_slots(request('SOXX','2026-05-05','2026-08-14'))
    assert tuple(b.start_at for b in intraday.bars) == slots
    assert len(slots) == 4480 and not unsupported
    assert all(b.start_at.hour == 8 for b in intraday.bars[::64])
    assert all(b.source == 'alpaca_sip' for b in intraday.bars)
    with pytest.raises(ValueError, match='grid'):
        replace(intraday, bars=intraday.bars[:-1])


def test_immutable_sqlite_and_offline_reload(tmp_path, inputs):
    intraday = inputs[-1]
    path = tmp_path/'independent.sqlite'
    with ResearchStore(path) as store:
        store.save_dataset(intraday)
        store.save_dataset(intraday)
        with pytest.raises(ValueError, match='collision'):
            store.save_dataset(replace(intraday, bars=(replace(intraday.bars[0], volume=intraday.bars[0].volume+1), *intraday.bars[1:])))
    with patch('socket.socket.connect', side_effect=AssertionError('network')):
        with ResearchStore(path, read_only=True) as store:
            first = store.load_dataset(INTRADAY_ID)
            second = store.load_dataset(INTRADAY_ID)
    assert first.content_hash == second.content_hash == intraday.content_hash


@pytest.mark.parametrize('key,value', [('feed','iex'),('role','CONFIRMATION'),('adjustment','split'),
    ('price_basis','yahoo_chart_snapshot_ohlc_no_local_adjustment'),('provider','yahoo_chart')])
def test_fail_closed_on_provider_or_unit_relabel(inputs, key, value):
    intraday = inputs[-1]
    meta = intraday.manifest.unpack()
    meta[key] = value
    with pytest.raises(ValueError): replace(intraday, manifest=JsonObject.of(meta))


def test_admission_precedes_dataset_identity(inputs):
    capture, admission = inputs[:2]
    altered = deepcopy(admission)
    altered['status'] = 'BLOCKED'
    with pytest.raises(ValueError, match='Admission'): intraday_dataset(capture, altered, 'new-id')
    altered = deepcopy(capture)
    altered['cases']['m15-raw']['rows'][0]['v'] += 1
    with pytest.raises(ValueError, match='Admission'): intraday_dataset(altered, admission, 'new-id')


def test_daily_new_units_and_identity_clock_not_backdated(inputs):
    daily = inputs[-2]
    loaded = DailyVintage.loads(daily.dumps())
    assert loaded == daily
    at = inputs[-1].bars[0].end_at
    resolution = prepare_daily(loaded, at)
    assert resolution.prefix.input_status == 'READY'
    assert resolution.transform.unpack()['applied_actions'] == []
    assert all(b.known_at <= at for b in resolution.prefix.bars)
    assert resolution.transform.unpack()['dataset_admission_metadata']['causal_feature'] is False


def test_unknown_effective_split_fails_closed(inputs):
    capture = deepcopy(inputs[0])
    capture['actions']['corporate_actions']['forward_splits'] = [{'id':'unknown','ex_date':'2026-06-01'}]
    with pytest.raises(ValueError, match='known_at'): audit(capture)


def test_no_inheritance_from_old_yahoo_unit_certificate(inputs):
    capture, admission, action, unit = inputs[:4]
    altered = deepcopy(unit)
    altered['raw_capture_hash'] = '0'*64
    with pytest.raises(ValueError, match='source vintage'):
        admit_identity_interval(daily_parent(capture, 'alpaca-parent'), 'alpaca-child', action, altered)


def test_frozen_strategy_protocol_and_original_zero_signal_preserved():
    record = yaml.safe_load(Path('research/decision_records/H0001-entry-efficacy-preregistration-v1.yaml').read_text(encoding='utf-8'))
    proof = verify(record)
    assert proof['prior_candidate_count'] == 0 and proof['confirmation_sessions'] == 126
    assert proof['specification_hash'] == 'bf8134733bacee17542240e53a8ec30223c1550b5bedbaa6d3994ba1444acc19'


def test_capture_manifest_collision_does_not_overwrite(tmp_path):
    p = tmp_path/'immutable.json'
    write_new(p, b'original')
    with pytest.raises(ValueError, match='collision'): write_new(p, b'changed')
    assert p.read_bytes() == b'original'


def test_credential_values_never_in_new_evidence():
    from scripts.h0001_alpaca_admission import credentials
    # A fresh offline checkout has no private credential file. Live finalization
    # separately requires actual credentials and scans every captured artifact.
    try:
        secrets = tuple(credentials().values())
    except ValueError:
        secrets = ('APCA-API-SECRET-KEY', 'APCA-API-KEY-ID')
    for path in ROOT.rglob('*'):
        if path.is_file():
            body = path.read_bytes()
            assert all(value.encode() not in body for value in secrets)


def test_derived_h1_retains_sip_provenance_and_frozen_readiness(inputs):
    from richping.research_v2.aggregation import CompletedAggregator
    from richping.research_v2.sessions import EXTENDED
    from richping.research_v2.real_data import is_research_snapshot
    from richping.research_v2.strategy.h1_setup import PreparedH1Prefix, classify_h1_relative_setup
    intraday = inputs[-1]
    agg = CompletedAggregator(('1H',), profile=EXTENDED)
    hours = []
    for bar in intraday.bars[:449*4]:
        hours.extend(b for b in agg.accept(bar, bar.known_at) if b.timeframe == '1H')
    assert len(hours) == 449
    assert all(is_research_snapshot(b) and b.provenance.unpack()['feed'] == 'sip' for b in hours)
    at = hours[-1].known_at
    state = classify_h1_relative_setup(PreparedH1Prefix('SOXX', tuple(hours), at, hours[-1].end_at,
        intraday.dataset_id, at, price_basis=intraday.manifest.unpack()['price_basis']), at)
    assert state.status == 'READY'


def test_immutable_hash_cache_preserves_content_fingerprints(inputs):
    from scripts.h0001_alpaca_70_discovery import immutable_hash_cache
    daily, intraday = inputs[-2:]
    before = daily.content_hash, intraday.content_hash
    with immutable_hash_cache():
        assert (daily.content_hash, intraday.content_hash) == before
        assert (daily.content_hash, intraday.content_hash) == before
    assert (daily.content_hash, intraday.content_hash) == before
