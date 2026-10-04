"""Selected-scope admission, then separate immutable dataset and frozen replay."""
from argparse import ArgumentParser
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from unittest.mock import patch
import yaml
from bs4 import BeautifulSoup

from richping.core import digest, canonical, sessions, timestamp
from richping.research_v2.contracts import payload
from richping.research_v2.alpaca_data import intraday_dataset, daily_parent
from richping.research_v2.daily_identity import admit_identity_interval, FIELDS, unit_comparison, NAV_TOLERANCE
from richping.research_v2.daily_data import DailyVintage
from richping.research_v2.real_data import expected_slots, request
from richping.research_v2.sessions import NY
from richping.research_v2.store import ResearchStore
from richping.research_v2.market_data import MarketDataset
from richping.research_v2.strategy.h0001_spec import H0001Specification
from scripts.h0001_alpaca_admission import encode, grid, paginate
from scripts.h0001_alpaca_70_capture import ROOT, START, END, DAILY_START
from scripts.h0001_long_history_audit import write_new
from scripts.h0001_entry_offline_proof import replay
from scripts.h0001_entry_efficacy_preregister import verify
from scripts.h0001_action_unit_offline_proof import calendar_guards
from scripts.h0001_efficacy_disposition_audit import GUARDS

SOURCE_ROOT = Path('research/data_evidence/h0001-action-unit-20261003')
DB = Path('var/research/alpaca-70/market.sqlite')
INTRADAY_ID = 'soxx-alpaca-sip-15m-discovery-20260505-20260813-v1'
DAILY_ID = 'soxx-alpaca-sip-rth-daily-discovery-20261004-v1'


def forbidden(*args, **kwargs):
    raise AssertionError('Network/outcome/performance access forbidden during signal replay')


@contextmanager
def immutable_hash_cache():
    """Host-only memoization of immutable snapshot hashes; strategy code unchanged."""
    with ExitStack() as stack:
        for cls in (DailyVintage, MarketDataset):
            original = cls.content_hash.fget
            cache = {}
            def cached(obj, original=original, cache=cache):
                identity = id(obj)
                if identity not in cache: cache[identity] = (obj, original(obj))
                return cache[identity][1]
            stack.enter_context(patch.object(cls, 'content_hash', property(cached)))
        yield


def load_capture(root=ROOT):
    successful = []
    for path in sorted(root.glob('capture-*.json')):
        if not re.fullmatch(r'capture-[0-9a-f]{64}\.json', path.name):
            continue  # Descriptive capture-manifest.json is not a raw capture receipt.
        body = path.read_bytes()
        if sha256(body).hexdigest() != path.stem.removeprefix('capture-'):
            raise ValueError('Capture bytes/hash mismatch')
        report = json.loads(body)
        for record in report['requests']:
            if record['transport'] != 'HTTP_RESPONSE': continue
            body = (root / 'raw' / (record['sha256']+'.json')).read_bytes()
            if sha256(body).hexdigest() != record['sha256'] or len(body) != record['bytes']:
                raise ValueError('Raw response bytes/hash mismatch')
            if record['http_status'] != 200: raise ValueError('HTTP error, not empty prices')
        if report.get('failure'): continue  # Failed sandbox transport remains separate evidence.
        if (report['anchor_start'], report['anchor_end_inclusive'], report['daily_origin'], report['role']) != (START, '2026-08-13', DAILY_START, 'DISCOVERY_ONLY'):
            raise ValueError('Owner-selected scope mismatch')
        for identity, case in report['cases'].items():
            records = [r for r in report['requests'] if r['id'] == identity]
            pages = iter(records)
            def fetch(params):
                record = next(pages)
                if params != record['params'] or record['http_status'] != 200:
                    raise ValueError('Pagination request chain mismatch')
                return json.loads((root/'raw'/(record['sha256']+'.json')).read_bytes())
            restored = paginate(fetch, records[0]['params'])
            if restored != case or next(pages, None) is not None:
                raise ValueError('Pagination reconstruction mismatch')
        # Corporate action page chains are independently reconstructed, including explicit null termination.
        records = [r for r in report['requests'] if r['id'] == 'selected-actions']
        groups, seen, token = {}, set(), None
        base = records[0]['params']
        for i, r in enumerate(records):
            expected = base if i == 0 else {**base, 'page_token': token}
            if r['params'] != expected or (i and token is None):
                raise ValueError('Action page request chain mismatch')
            p = json.loads((root/'raw'/(r['sha256']+'.json')).read_bytes())
            for kind, rows in p['corporate_actions'].items():
                for row in rows:
                    if row['symbol'] != 'SOXX' or row['id'] in seen:
                        raise ValueError('Action identity/symbol mismatch')
                    seen.add(row['id'])
                    groups.setdefault(kind, []).append(row)
            token = p['next_page_token']
        if token is not None or {'corporate_actions': groups, 'pages': len(records), 'terminal_token': None} != report['actions']:
            raise ValueError('Action completion reconstruction mismatch')
        repeated = report['actions-repeat']
        repeat_receipt = next(r for r in report['requests'] if r['id'] == 'selected-actions-repeat')
        if repeated != json.loads((root/'raw'/(repeat_receipt['sha256']+'.json')).read_bytes()):
            raise ValueError('Repeated action receipt mismatch')
        if repeated['next_page_token'] is not None or repeated['corporate_actions'] != groups:
            raise ValueError('Action repeat mismatch')
        successful.append(report)
    if len(successful) != 1: raise ValueError('Exactly one complete selected capture required')
    return successful[0]


def source_bytes(ref):
    body = Path(ref['path']).read_bytes()
    if sha256(body).hexdigest() != ref['sha256']:
        raise ValueError('Referenced raw source changed')
    return body


def audit(capture):
    # Reuse raw sources and rerun their interpretation; NEVER inherit an old interval certificate.
    index = json.loads((SOURCE_ROOT/'action-history-audit.json').read_bytes())
    previous = deepcopy(index['previous_effective_split'])
    following = deepcopy(index['next_effective_split'])
    refs = index['dataset_completeness_sources']
    for ref in refs + previous['sources'] + following['sources']: source_bytes(ref)
    independent = next(r for r in refs if r['role'] == 'INDEPENDENT_ACTION_HISTORY')
    soup = BeautifulSoup(source_bytes(independent), 'html.parser')
    split_rows = [[c.get_text(strip=True) for c in r.find_all('td')] for r in soup.select('table tr') if r.find('td')]
    if split_rows != [['Mar 07, 2024', '3-for-1 split']]:
        raise ValueError('Independent split history contradicts no-event scope')
    filing_ref = next(r for r in following['sources'] if r['identity'] == 'issuer-2026-filing')
    filing = BeautifulSoup(source_bytes(filing_ref), 'html.parser').get_text(' ', strip=True)
    if not all(s in filing for s in ('3:1', 'November', '2026')):
        raise ValueError('Issuer boundary terms unverified')
    yahoo = next(r for r in refs if r['role'] == 'CURRENT_PROVIDER_HISTORY')
    history = json.loads(source_bytes(yahoo))['response']['chart']['result'][0]['events']['splits']
    if len(history) != 1 or list(history.values())[0]['splitRatio'] != '3:1':
        raise ValueError('Independent current history contradicts split-free interval')
    ex = datetime.fromtimestamp(list(history.values())[0]['date'], timestamp(capture['captured_at']).tzinfo).date().isoformat()
    if ex != '2024-03-07' or not previous['trading_date'] < DAILY_START < END <= following['trading_date']:
        raise ValueError('Selected interval overlaps split boundary')
    actions = capture['actions']['corporate_actions']
    if any(rows for kind, rows in actions.items() if kind != 'cash_dividends'):
        raise ValueError('Actual event known_at unproven: fail closed on required transformation')
    raw_ref = {'identity': 'alpaca-selected-actions', 'url': 'https://data.alpaca.markets/v1/corporate-actions',
               'sha256': next(r['sha256'] for r in capture['requests'] if r['id'] == 'selected-actions'),
               'path': (ROOT/'raw'/next(r['sha256']+'.json' for r in capture['requests'] if r['id'] == 'selected-actions')).as_posix(),
               'captured_at': capture['captured_at'], 'role': 'CURRENT_PROVIDER_HISTORY'}
    action = {'schema_version': 'EX_POST_SPLIT_HISTORY_COMPLETENESS_V1', 'symbol': 'SOXX',
        'evidence_ref': (ROOT/'action-history-audit.json').as_posix(),
        'interval_start': DAILY_START, 'interval_end': '2026-08-13', 'captured_at': capture['captured_at'],
        'certification_scope': 'EX_POST_DATASET_ADMISSION_NOT_STRATEGY_KNOWN_AT',
        'previous_effective_split': previous, 'next_effective_split': following, 'splits_inside_interval': [],
        'dataset_completeness_sources': [raw_ref, *refs], 'result': 'PASS',
        'historical_event_known_at_assigned': False,
        'revalidation': 'New Alpaca snapshot and selected Daily465 interval; independent raw history and issuer sources reread.',
        'limitations': ['Ex-post interval admission only; event known_at remains unproven.',
                        'No split transform; dividends remain unnormalized price features and separate outcome guards.']}
    # Parse exchange prices and issuer NAV directly from their archived raw bytes.
    source_index = json.loads((SOURCE_ROOT/'ohlc-unit-crosscheck.json').read_bytes())['market_sources']
    market_ref = next(r for r in source_index if r['identity'] == 'nasdaq-history')
    market_raw = json.loads(source_bytes(market_ref))
    market = {datetime.strptime(r['date'], '%m/%d/%Y').date().isoformat():
        {k: float(r[k].replace(',', '')) for k in FIELDS} for r in market_raw['data']['tradesTable']['rows']}
    nav_ref = next(r for r in source_index if r['identity'] == 'issuer-history')
    xml = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;#)', '&amp;', source_bytes(nav_ref).decode())
    ns = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}
    tree = ET.fromstring(xml)
    sheet = next(w for w in tree.findall('ss:Worksheet', ns) if w.attrib['{'+ns['ss']+'}Name'] == 'Historical')
    nav = {}
    for r in sheet.findall('.//ss:Row', ns)[1:]:
        cells = [d.text for d in r.findall('.//ss:Data', ns)]
        nav[datetime.strptime(cells[0], '%b %d, %Y').date().isoformat()] = float(cells[1])
    parent = daily_parent(capture, DAILY_ID+'-unadmitted')
    unit_rows = []
    for bar in parent.bars:
        quote = {k: getattr(bar, k) for k in FIELDS}
        comparison = unit_comparison(quote, market[bar.session])
        if comparison['unit_certification_result'] != 'PASS' or abs(bar.close/nav[bar.session]-1) > NAV_TOLERANCE:
            raise ValueError('Selected Alpaca Daily price/share-unit compatibility failed')
        unit_rows.append({'session': bar.session, 'source_quote': quote, 'market_ohlc': market[bar.session],
                         'issuer_NAV': nav[bar.session], 'comparison': comparison, 'sources': source_index})
    unit = {'schema_version': 'INTERVAL_SHARE_UNIT_CROSSCHECK_V1', 'symbol': 'SOXX',
        'evidence_ref': (ROOT/'ohlc-unit-crosscheck.json').as_posix(),
        'interval_start': DAILY_START, 'interval_end': '2026-08-13', 'captured_at': capture['captured_at'],
        'raw_capture_hash': digest(capture), 'source_price_basis': parent.manifest.unpack()['raw_price_basis'],
        'market_sources': source_index, 'rows': unit_rows, 'nav_relative_tolerance': NAV_TOLERANCE,
        'result': 'PASS', 'limitations': ['Certifies this Alpaca nativeDaily snapshot465 OHLC rows only.',
            'Daily USD/share OHLC matches RTH exchange reference; nativeDaily volume includes extended trades.',
            'Intraday eligible prices differ by segment; no exact RTH/intraday OHLC equivalence claimed.']}
    diag = grid(capture['cases']['m15-raw']['rows'], START, END)
    slots, unsupported = expected_slots(request('SOXX', START, END))
    raw = capture['cases']['m15-raw']['rows']
    equality = tuple(timestamp(b['t']) for b in raw) == slots and not unsupported
    repeats = all(capture['cases'][a]['rows'] == capture['cases'][b]['rows'] for a,b in (
        ('m15-raw','m15-repeat'), ('daily-raw','daily-repeat'), ('m15-raw','m15-split'), ('daily-raw','daily-split')))
    minute_bins = {}
    for b in capture['cases']['minute-volume']['rows']:
        t = timestamp(b['t'])
        key = t.replace(minute=t.minute//15*15, second=0, microsecond=0)
        minute_bins[key] = minute_bins.get(key, 0) + b['v']
    first_day = [b for b in raw if timestamp(b['t']).astimezone(NY).date().isoformat() == START]
    volume_equal = all(minute_bins.get(timestamp(b['t'])) == b['v'] for b in first_day)
    if not equality or not repeats or not volume_equal or parent.manifest.unpack()['missing_sessions']:
        raise ValueError('Exact grid/capture/volume/Daily admission failed')
    admission = {'schema': 'alpaca_70_independent_admission_v1', 'status': 'PASS', 'role': 'DISCOVERY_ONLY',
        'provider': 'alpaca_basic', 'feed': 'sip', 'anchor_start': START, 'anchor_end_exclusive': END,
        'sessions': len(sessions(START, '2026-08-13')), 'capture_hash': digest(capture), 'grid': diag,
        'exact_expected_grid_equality': equality, 'capture_repeat_equal': repeats,
        'daily_sessions': len(parent.bars), 'daily_origin': DAILY_START,
        'daily_unit_audit_hash': digest(unit), 'action_audit_hash': digest(action),
        'raw_split_identical_selected_intraday_and_daily': True,
        'volume': {'first_session_all64_m15_equals_published_minute_sum': volume_equal,
            'zero_volume_bars': sum(b['v'] == 0 for b in raw),
            'meaning': 'Condition-eligible SIP shares; present0 differs from missing; nativeDaily volume not substituted.'},
        'DST': {'actual_scope': 'All70 dates EDT;04:00ET=08:00UTC,20:00ET=00:00UTC next day',
                'winter_summer_engine': 'Frozen America/New_York calendar; separate prior actual probes retained, not interval certificate.'},
        'action_known_at': 'UNPROVEN_NO_BACKDATE; no-event identity audit is ex-post admission, not causal absence receipt',
        'outcome_queries': 0, 'candidate_replay': 'NOT_RUN_BEFORE_ADMISSION',
        'old_certificate_inherited': False,
        'limitations': ['Historical bar-end availability assumption; not fresh shadow/live PIT.',
            'Selected bounded discovery only; multi-year target remains pending without further immediate provider hunting.',
            'Price features use frozen split-only identity, no dividend reinvestment; outcome accounting separate.',
            'No RTH fallback, synthetic filling or provider bar mixing. NativeDaily independent RTH price reference audited.']}
    return admission, action, unit


def admit():
    capture = load_capture()
    try:
        admission, action, unit = audit(capture)
    except ValueError as exc:
        admission = {'status': 'BLOCKED', 'reason': str(exc), 'capture_hash': digest(capture),
                     'role': 'DISCOVERY_ONLY', 'dataset_created': False, 'candidate_count': None, 'outcome_queries': 0}
        write_new(ROOT/'admission.json', encode(admission))
        return admission
    for name, body in [('action-history-audit.json', action), ('ohlc-unit-crosscheck.json', unit), ('admission.json', admission)]:
        write_new(ROOT/name, encode(body))
    return admission


def create_and_replay():
    capture = load_capture()
    admission = json.loads((ROOT/'admission.json').read_bytes())
    calculated, action, unit = audit(capture)
    if admission != calculated: raise ValueError('Admission hash/content changed')
    daily = admit_identity_interval(daily_parent(capture, DAILY_ID+'-unadmitted'), DAILY_ID, action, unit)
    intraday = intraday_dataset(capture, admission, INTRADAY_ID)
    write_new(ROOT/'daily-vintage.json', daily.dumps().encode())
    write_new(ROOT/'intraday-vintage.json', canonical({'dataset_id': intraday.dataset_id,
        'content_hash': intraday.content_hash, 'bars': [payload(b) for b in intraday.bars],
        'manifest': intraday.manifest.unpack()}).encode())
    with ResearchStore(DB) as store: store.save_dataset(intraday)
    record = yaml.safe_load(Path('research/decision_records/H0001-entry-efficacy-preregistration-v1.yaml').read_text(encoding='utf-8'))
    verified = verify(record)
    spec = H0001Specification.load('research/strategy_specs/H0001-r03-draft.yaml')
    with ExitStack() as guards:
        for target in ('socket.socket.connect', 'socket.create_connection', 'curl_cffi.requests.get', 'urllib.request.urlopen'):
            guards.enter_context(patch(target, forbidden))
        for target in GUARDS:
            if target == 'richping.research_v2.store.ResearchStore.load_dataset': continue
            guards.enter_context(patch(target, forbidden))
        calendar_guards(guards)
        guards.enter_context(immutable_hash_cache())
        with ResearchStore(DB, read_only=True) as store:
            first_input = store.load_dataset(INTRADAY_ID)
        first_daily = DailyVintage.loads((ROOT/'daily-vintage.json').read_text(encoding='utf-8'))
        first = replay(first_daily, first_input, spec)
        write_new(ROOT/'candidate-stream-first.json', encode(first))  # freeze before ANY possible outcome path
        with ResearchStore(DB, read_only=True) as store:
            second_input = store.load_dataset(INTRADAY_ID)
        second_daily = DailyVintage.loads((ROOT/'daily-vintage.json').read_text(encoding='utf-8'))
        second = replay(second_daily, second_input, spec)
        if first != second: raise ValueError('Repeated candidate stream mismatch')
    verified_after = verify(record)
    if verified != verified_after: raise ValueError('Frozen strategy dependencies changed')
    proof = {'status': 'ZERO_SIGNAL' if not first['events'] else 'CANDIDATE_STREAM_FROZEN',
        'sessions': 70, 'role': 'DISCOVERY_ONLY', 'daily_id': DAILY_ID, 'daily_hash': daily.content_hash,
        'intraday_id': INTRADAY_ID, 'intraday_hash': intraday.content_hash,
        'capture_hash': digest(capture), 'admission_hash': digest(admission),
        'candidate_count': len(first['events']), 'candidate_timestamps': [e['as_of'] for e in first['events']],
        'denominators': first['denominators'], 'event_stream_hash': first['event_stream_hash'],
        'all_replay_result_hash': digest(first), 'repeat_equal': True, 'runs': 2,
        'network_disabled': True, 'network_calls': 0, 'outcome_queries': 0, 'outcomes': 'NOT_RUN',
        'frozen_dependencies': verified, 'frozen_strategy_bytes_preserved': True,
        'original_ZERO_SIGNAL_preserved': True, 'confirmation': '126_sessions_20261012_20270413_UNCHANGED'}
    write_new(ROOT/'offline-reload-proof.json', encode(proof))
    print(canonical(proof), flush=True)
    return proof


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    if args.replay: create_and_replay()
    else:
        with ExitStack() as guards:
            for target in ('socket.socket.connect', 'socket.create_connection', 'curl_cffi.requests.get', 'urllib.request.urlopen'):
                guards.enter_context(patch(target, forbidden))
            first = admit()
            second, _, _ = audit(load_capture()) if first['status'] == 'PASS' else (first, None, None)
            if first != second: raise ValueError('Admission offline repeat mismatch')
            write_new(ROOT/'admission-offline-proof.json', encode({'repeat_equal': True,
                'admission_hash': digest(first), 'network_disabled': True, 'outcome_queries': 0, 'dataset_created': False}))
            print(canonical({k:first.get(k) for k in ('status','sessions','daily_sessions','exact_expected_grid_equality')}))


if __name__ == '__main__': main()
