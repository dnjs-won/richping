"""QQQ-only read-only SIP capture and offline receipt admission; no signals."""
from argparse import ArgumentParser
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from richping.core import digest, timestamp
from richping.research_v2.real_data import expected_slots, request
from scripts.h0001_alpaca_admission import credentials, encode, validate_bar, ProviderFailure, grid
from scripts.h0001_long_history_audit import write_new

ROOT = Path('research/data_evidence/h0003-qqq-admission-20261004')
START, END = '2026-05-05', '2026-08-14'
HOST = 'https://data.alpaca.markets'


class Client:
    def __init__(self, root=ROOT):
        self.root, self.headers, self.records = root, credentials(), []

    def get(self, identity, endpoint, params):
        from curl_cffi import requests
        if endpoint not in ('/v2/stocks/QQQ/bars', '/v1/corporate-actions'):
            raise ValueError('QQQ read-only endpoint allowlist')
        if endpoint.endswith('corporate-actions') and params.get('symbols') != 'QQQ':
            raise ValueError('QQQ action scope only')
        record = dict(id=identity, endpoint=endpoint, params=dict(params),
                      requested_at=datetime.now(timezone.utc).isoformat())
        try:
            response = requests.get(HOST+endpoint, params=params, headers=self.headers,
                                    timeout=40, impersonate='chrome')
        except Exception as exc:
            self.records.append({**record, 'http_status': None, 'exception_type': type(exc).__name__})
            raise ProviderFailure('Transport failure; capability unknown') from None
        body = response.content
        if any(v.encode() in body for v in self.headers.values()):
            raise ProviderFailure('Unsafe response not persisted')
        hashed = sha256(body).hexdigest()
        write_new(self.root/'raw'/(hashed+'.json'), body)
        self.records.append({**record, 'http_status': response.status_code, 'sha256': hashed,
                             'bytes': len(body), 'captured_at': datetime.now(timezone.utc).isoformat()})
        print(json.dumps({'id': identity, 'status': response.status_code, 'bytes': len(body)}), flush=True)
        if response.status_code != 200:
            raise ProviderFailure('Provider HTTP '+str(response.status_code))
        value = json.loads(body)
        if not isinstance(value, dict) or any(k in value for k in ('error', 'message', 'code')):
            raise ProviderFailure('Malformed/error provider payload')
        return value


def bars(fetch, params):
    rows, tokens, current = [], set(), dict(params)
    pages = 0
    while True:
        p = fetch(current)
        if p.get('symbol') != 'QQQ' or not isinstance(p.get('bars'), list) or 'next_page_token' not in p:
            raise ProviderFailure('QQQ bar page schema/symbol mismatch')
        for row in p['bars']:
            validate_bar(row)
            at = timestamp(row['t'])
            if not timestamp(params['start']) <= at <= timestamp(params['end']):
                raise ProviderFailure('Out of requested range')
            if rows and at <= timestamp(rows[-1]['t']):
                raise ProviderFailure('Duplicate/reversed rows')
            rows.append(row)
        pages += 1
        token = p['next_page_token']
        if token is None:
            return {'rows': rows, 'pages': pages, 'terminal_token': None}
        if not isinstance(token, str) or not token or token in tokens or not p['bars']:
            raise ProviderFailure('Pagination cycle/empty page')
        tokens.add(token)
        current = {**params, 'page_token': token}


def actions(fetch, params):
    groups, ids, tokens, pages, current = {}, set(), set(), 0, dict(params)
    while True:
        p = fetch(current)
        if not isinstance(p.get('corporate_actions'), dict) or 'next_page_token' not in p:
            raise ProviderFailure('Action page schema')
        for kind, rows in p['corporate_actions'].items():
            if not isinstance(rows, list):
                raise ProviderFailure('Action rows schema')
            for row in rows:
                if row.get('symbol') != 'QQQ' or not row.get('id') or row['id'] in ids:
                    raise ProviderFailure('Action symbol/identity mismatch')
                ids.add(row['id'])
                groups.setdefault(kind, []).append(row)
        pages += 1
        token = p['next_page_token']
        if token is None:
            return {'corporate_actions': groups, 'pages': pages, 'terminal_token': None}
        if not isinstance(token, str) or not token or token in tokens:
            raise ProviderFailure('Action token cycle')
        tokens.add(token)
        current = {**params, 'page_token': token}


def capture(root=ROOT):
    client = Client(root)
    report = dict(schema='h0003_qqq_capture_v1', role='DISCOVERY_ONLY',
                  start=START, end_exclusive=END, cases={}, outcome_access=0)
    try:
        for identity, adj, limit in (('raw', 'raw', 10000), ('repeat', 'raw', 317), ('split', 'split', 10000)):
            params = dict(start=START+'T04:00:00Z', end=END+'T03:59:59Z', timeframe='15Min',
                          feed='sip', adjustment=adj, sort='asc', limit=limit, asof='-', currency='USD')
            report['cases'][identity] = bars(lambda p: client.get(identity, '/v2/stocks/QQQ/bars', p), params)
        for identity, limit in (('actions', 7), ('actions-repeat', 1000)):
            params = dict(symbols='QQQ', start=START, end='2026-08-13', limit=limit)
            report['cases'][identity] = actions(lambda p: client.get(identity, '/v1/corporate-actions', p), params)
    except (ProviderFailure, ValueError) as exc:
        report['failure'] = str(exc)
    report.update(requests=client.records, captured_at=datetime.now(timezone.utc).isoformat())
    body = encode(report)
    write_new(root/('capture-'+sha256(body).hexdigest()+'.json'), body)
    if report.get('failure'):
        raise SystemExit(2)
    return report


def load_capture(root=ROOT):
    good = []
    for path in sorted(root.glob('capture-*.json')):
        body = path.read_bytes()
        if path.stem != 'capture-'+sha256(body).hexdigest():
            raise ValueError('Capture hash mismatch')
        capture = json.loads(body)
        for record in capture['requests']:
            if record['http_status'] is None:
                continue
            raw = (root/'raw'/(record['sha256']+'.json')).read_bytes()
            if sha256(raw).hexdigest() != record['sha256'] or len(raw) != record['bytes']:
                raise ValueError('Raw receipt hash/length mismatch')
        if capture.get('failure'):
            continue
        if (capture['start'], capture['end_exclusive'], capture['role']) != (START, END, 'DISCOVERY_ONLY'):
            raise ValueError('Fixed discovery scope mismatch')
        for identity, case in capture['cases'].items():
            records = [r for r in capture['requests'] if r['id'] == identity]
            pages = iter(records)
            def fetch(params):
                r = next(pages)
                if r['params'] != params or r['http_status'] != 200:
                    raise ValueError('Page request chain mismatch')
                expected_endpoint = '/v1/corporate-actions' if identity.startswith('actions') else '/v2/stocks/QQQ/bars'
                if r['endpoint'] != expected_endpoint:
                    raise ValueError('Receipt endpoint mismatch')
                return json.loads((root/'raw'/(r['sha256']+'.json')).read_bytes())
            restored = (actions if identity.startswith('actions') else bars)(fetch, records[0]['params'])
            if restored != case or next(pages, None) is not None:
                raise ValueError('Reconstructed pages mismatch')
        good.append(capture)
    if len(good) != 1:
        raise ValueError('Exactly one successful capture required')
    return good[0]


def admission(capture):
    cases = capture['cases']
    if set(cases) != {'raw', 'repeat', 'split', 'actions', 'actions-repeat'}:
        raise ValueError('Incomplete capture cases')
    for r in capture['requests']:
        if r['id'].startswith('actions'):
            expected = dict(symbols='QQQ',start=START,end='2026-08-13',
                            limit=7 if r['id'] == 'actions' else 1000)
            if {k:v for k,v in r['params'].items() if k != 'page_token'} != expected:
                raise ValueError('Action interval/symbol mismatch')
        else:
            expected = dict(start=START+'T04:00:00Z', end=END+'T03:59:59Z', timeframe='15Min', feed='sip',
                            adjustment='split' if r['id'] == 'split' else 'raw', sort='asc',
                            limit=317 if r['id'] == 'repeat' else 10000, asof='-', currency='USD')
            if {k:v for k,v in r['params'].items() if k != 'page_token'} != expected:
                raise ValueError('Mixed feed/adjustment/unit request')
    rows = cases['raw']['rows']
    diag = grid(rows, START, END)
    expected, unsupported = expected_slots(request('QQQ', START, END))
    repeats = rows == cases['repeat']['rows']
    split_equal = rows == cases['split']['rows']
    action_groups = cases['actions']['corporate_actions']
    action_equal = action_groups == cases['actions-repeat']['corporate_actions']
    no_unit_actions = not any(v for k,v in action_groups.items() if k != 'cash_dividends')
    exact = tuple(timestamp(r['t']) for r in rows) == expected and not unsupported
    passed = all((exact, repeats, split_equal, action_equal, no_unit_actions))
    return dict(schema='h0003_qqq_admission_v1', status='PASS' if passed else 'BLOCKED',
                provider='alpaca_sip', feed='sip', adjustment='raw', currency='USD',
                role='DISCOVERY_ONLY', start=START, end_exclusive=END, capture_hash=digest(capture),
                grid=diag, exact_grid=exact, pagination_repeat_equal=repeats, raw_split_equal=split_equal,
                action_repeat_equal=action_equal, split_identity=no_unit_actions,
                known_at_policy='historical_snapshot_bar_end_assumed_v1',
                outcome_access=0, signal_replay='NOT_RUN_BEFORE_ADMISSION',
                limitations=['Ex-post no-unit-action admission; no historical event known_at backdating.',
                             'Same-provider raw/split/action checks; no independent exchange price certificate.',
                             'Raw cash dividends not normalized/reinvested; outcome accounting separate.',
                             'Complete slot observations do not certify extended liquidity or live availability.'])


def admit(root=ROOT):
    first = admission(load_capture(root))
    second = admission(load_capture(root))
    if first != second:
        raise ValueError('Admission not deterministic')
    write_new(root/'admission.json', encode(first))
    write_new(root/'offline-proof.json', encode(dict(admission_hash=digest(first), repeat_equal=True,
                                                     raw_receipts_reconstructed=True, outcome_access=0)))
    return first


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--capture', action='store_true')
    args = parser.parse_args()
    result = capture() if args.capture else admit()
    print(json.dumps({k: result[k] for k in ('status', 'grid', 'outcome_access') if k in result}))
