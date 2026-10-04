"""Admitted Alpaca SIP historical discovery snapshots; no live PIT assertion."""
from datetime import timedelta

from ..core import digest, timestamp, sessions
from .contracts import CONTRACT_VERSION, JsonObject, MarketBar
from .sessions import EXTENDED, NY, RTH, extended_bar_metadata, session_profile, session_bounds
from .real_data import expected_slots, request
from .daily_data import DailyVintage, SCHEMA, BAR_CLOCK, daily_request

PROVIDER = 'alpaca_sip'
ADAPTER = 'alpaca_sip_raw_15m_v1'
PRICE = 'ALPACA_SIP_RAW_USD_PER_AS_TRADED_SHARE'
ACTION = 'INTERVAL_CERTIFIED_SPLIT_IDENTITY_DIVIDENDS_NOT_REINVESTED'
CLOCK = 'historical_snapshot_bar_end_assumed_v1'


def validate_manifest(meta):
    expected = {'provider': PROVIDER, 'adapter_version': ADAPTER, 'feed': 'sip',
                'price_basis': PRICE, 'corporate_actions': ACTION,
                'known_at_policy': CLOCK, 'session_policy': 'RTH_EXTENDED',
                'role': 'DISCOVERY_ONLY', 'adjustment': 'raw', 'currency': 'USD'}
    if any(meta.get(k) != v for k, v in expected.items()):
        raise ValueError('Alpaca provenance/units/discovery mismatch')
    req = meta['requested_range']
    if req != request(req['symbol'], req['start'], req['end']) or meta['symbols'] != [req['symbol']]:
        raise ValueError('Alpaca interval mismatch')
    cert = meta['admission']
    if cert['status'] != 'PASS' or cert['role'] != 'DISCOVERY_ONLY' or cert['capture_hash'] != meta['raw_capture_hash']:
        raise ValueError('Alpaca immutable admission required')
    if (cert['anchor_start'], cert['anchor_end_exclusive']) != (req['start'], req['end']):
        raise ValueError('Alpaca certificate interval mismatch')
    if cert['grid']['missing_count'] or cert['grid']['unsupported_sessions'] or cert['grid']['offgrid']:
        raise ValueError('Exact complete supported Alpaca grid required')
    if not meta['known_limitations'] or len(meta['raw_capture_hash']) != 64:
        raise ValueError('Capture evidence and limitations required')


def validate_bar(bar, meta):
    p = bar.provenance.unpack()
    keys = ('quality', 'provider', 'adapter_version', 'provider_version', 'timezone',
            'price_basis', 'corporate_actions', 'known_at_policy', 'raw_capture_hash', 'feed')
    if any(p.get(k) != meta[k] for k in keys) or bar.source != PROVIDER:
        raise ValueError('Mixed Alpaca bar provenance')
    if bar.corporate_action != 'UNKNOWN' or bar.known_at != bar.end_at:
        raise ValueError('Alpaca assumed historical clock/action status required')
    if timestamp(p['captured_at']) != timestamp(meta['captured_at']) or bar.end_at > timestamp(p['captured_at']):
        raise ValueError('Alpaca capture clock mismatch')


def is_snapshot(bar):
    p = bar.provenance.unpack()
    return (bar.corporate_action == 'UNKNOWN' and p.get('quality') == 'REAL_HISTORICAL_RESEARCH'
            and p.get('provider') == PROVIDER and p.get('adapter_version') == ADAPTER
            and p.get('feed') == 'sip' and p.get('price_basis') == PRICE
            and p.get('corporate_actions') == ACTION and p.get('known_at_policy') == CLOCK)


def intraday_dataset(capture, admission, dataset_id):
    from .market_data import MarketDataset
    if admission['status'] != 'PASS' or admission['capture_hash'] != digest(capture):
        raise ValueError('Admission must precede dataset creation')
    req = request('SOXX', admission['anchor_start'], admission['anchor_end_exclusive'])
    common = {'quality': 'REAL_HISTORICAL_RESEARCH', 'provider': PROVIDER,
              'adapter_version': ADAPTER, 'provider_version': 'market_data_rest_v2',
              'feed': 'sip', 'captured_at': capture['captured_at'], 'timezone': 'America/New_York',
              'price_basis': PRICE, 'corporate_actions': ACTION, 'known_at_policy': CLOCK,
              'raw_capture_hash': digest(capture)}
    bars = []
    for i, row in enumerate(capture['cases']['m15-raw']['rows']):
        start = timestamp(row['t'])
        end = start + timedelta(minutes=15)
        bars.append(MarketBar(dataset_id, 'SOXX', '15m', start, end, start.astimezone(NY).date().isoformat(),
            *(row[k] for k in ('o', 'h', 'l', 'c', 'v')), end, PROVIDER,
            JsonObject.of({**common, 'provider_row': i, **extended_bar_metadata(start, end)}), 'UNKNOWN'))
    expected, unsupported = expected_slots(req)
    if tuple(b.start_at for b in bars) != expected or unsupported:
        raise ValueError('Alpaca observed grid must equal expected grid exactly')
    meta = {'schema_version': CONTRACT_VERSION, **common, 'symbols': ['SOXX'],
            'membership_limitations': 'Fixed SOXX only; no historical universe claim',
            'base_timeframe': '15m', 'calendar': 'XNYS', 'session_policy': 'RTH_EXTENDED',
            'session_contract': session_profile(EXTENDED).metadata, 'requested_range': req,
            'role': 'DISCOVERY_ONLY', 'adjustment': 'raw', 'currency': 'USD',
            'corporate_action_events': capture['actions']['corporate_actions'],
            'coverage_status': 'COMPLETE_GRID', 'missing_slots': [], 'unsupported_sessions': [],
            'known_limitations': admission['limitations'], 'admission': admission}
    return MarketDataset(dataset_id, tuple(bars), JsonObject.of(meta))


def daily_parent(capture, dataset_id):
    # Input range ends after the final trading date, with independent nativeDaily capture provenance.
    req = daily_request('SOXX', capture['daily_origin'], '2026-08-14')
    common = {'session_profile': RTH, 'raw_price_basis': 'ALPACA_SIP_NATIVE_RTH_PRICE_RAW_USD_SHARE',
              'raw_capture_hash': digest(capture), 'known_at_policy': BAR_CLOCK}
    bars = []
    for i, row in enumerate(capture['cases']['daily-raw']['rows']):
        day = timestamp(row['t']).astimezone(NY).date().isoformat()
        start, end = session_bounds(day, RTH)
        bars.append(MarketBar(dataset_id, 'SOXX', 'Daily', start, end, day,
            *(row[k] for k in ('o', 'h', 'l', 'c', 'v')), end, PROVIDER,
            JsonObject.of({**common, 'native_timestamp': row['t'], 'feed': 'sip',
                           'provider_row': i, 'volume_domain': 'DAILY_ELIGIBLE_SHARES_INCLUDES_EXTENDED'}), 'UNKNOWN'))
    missing = sorted(set(sessions(req['start'], '2026-08-13')) - {b.session for b in bars})
    meta = {'schema_version': SCHEMA, **common, 'requested_range': req,
            'provider': PROVIDER, 'captured_at': capture['captured_at'], 'raw_unit_status': 'UNVERIFIED',
            'missing_sessions': missing, 'role': 'DISCOVERY_ONLY',
            'transport_requests': [r for r in capture['requests'] if r['id'] == 'daily-raw'],
            'limitations': ['NativeDaily price eligibility differs from intraday; volume is not RTH-only.',
                            'Bar-end assumed historical availability, not live PIT.']}
    actions = {'schema_version': 'split_evidence_v1', 'provider': PROVIDER,
               'source_vintage': digest(capture), 'symbol': 'SOXX', 'captured_at': capture['captured_at'],
               'status': 'CROSS_CHECK_ONLY', 'events': [], 'coverage': []}
    return DailyVintage(dataset_id, tuple(bars), JsonObject.of(meta), JsonObject.of(actions))
