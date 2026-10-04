"""Explicit network-only capture for the owner-selected, signal-blind scope."""
from datetime import datetime, timezone
from hashlib import sha256

from scripts.h0001_alpaca_admission import Client, encode, ProviderFailure
from scripts.h0001_long_history_audit import write_new
from pathlib import Path

ROOT = Path('research/data_evidence/h0001-alpaca-70-20261004')
START, END = '2026-05-05', '2026-08-14'
DAILY_START = '2024-10-04'


def capture():
    client = Client(ROOT)
    report = {'schema': 'alpaca_70_selected_capture_v1', 'role': 'DISCOVERY_ONLY',
              'anchor_start': START, 'anchor_end_inclusive': '2026-08-13',
              'daily_origin': DAILY_START, 'cases': {}, 'outcome_queries': 0}
    try:
        # Same fixed prices captured using different page limits, before signals.
        for identity, timeframe, adjustment, start, limit in (
            ('m15-raw', '15Min', 'raw', START, 10000),
            ('m15-repeat', '15Min', 'raw', START, 317),
            ('m15-split', '15Min', 'split', START, 10000),
            ('daily-raw', '1Day', 'raw', DAILY_START, 10000),
            ('daily-repeat', '1Day', 'raw', DAILY_START, 37),
            ('daily-split', '1Day', 'split', DAILY_START, 10000),
            ('minute-volume', '1Min', 'raw', START, 10000)):
            end = '2026-05-06' if identity == 'minute-volume' else END
            report['cases'][identity] = client.bars(identity, start+'T04:00:00Z',
                end+'T03:59:59Z', timeframe, adjustment, limit)
        params = {'symbols': 'SOXX', 'start': DAILY_START, 'end': '2026-08-13', 'limit': 7}
        groups, ids, tokens, current, pages = {}, set(), set(), dict(params), 0
        while True:
            p = client.get('selected-actions', '/v1/corporate-actions', current)
            if not isinstance(p.get('corporate_actions'), dict) or 'next_page_token' not in p:
                raise ProviderFailure('Malformed interval action capture')
            for kind, rows in p['corporate_actions'].items():
                for row in rows:
                    if row['symbol'] != 'SOXX' or row['id'] in ids:
                        raise ProviderFailure('Action symbol/identity mismatch')
                    ids.add(row['id'])
                    groups.setdefault(kind, []).append(row)
            pages += 1
            token = p['next_page_token']
            if token is None: break
            if not isinstance(token, str) or not token or token in tokens:
                raise ProviderFailure('Action token cycle')
            tokens.add(token)
            current = {**params, 'page_token': token}
        report['actions'] = {'corporate_actions': groups, 'pages': pages, 'terminal_token': None}
        report['actions-repeat'] = client.get('selected-actions-repeat', '/v1/corporate-actions',
                                             {**params, 'limit': 1000})
    except ProviderFailure as exc:
        report['failure'] = str(exc)
    finally:
        report['requests'] = client.records
        report['captured_at'] = datetime.now(timezone.utc).isoformat()
        body = encode(report)
        write_new(ROOT / ('capture-'+sha256(body).hexdigest()+'.json'), body)
    if report.get('failure'):
        raise SystemExit(2)


if __name__ == '__main__':
    capture()
