"""Completed H1 publication denominators, independently of atomic occupancy."""
from collections import Counter
from contextlib import ExitStack
from dataclasses import replace
import json
from unittest.mock import patch

from richping.core import canonical, digest
from richping.research_v2.aggregation import CompletedAggregator
from richping.research_v2.sessions import EXTENDED
from richping.research_v2.strategy.h1_setup import PreparedH1Prefix, classify_h1_relative_setup
from scripts.h0001_alpaca_70_discovery import ROOT, load_capture, audit, intraday_dataset, INTRADAY_ID, forbidden
from scripts.h0001_action_unit_offline_proof import calendar_guards
from scripts.h0001_long_history_audit import write_new
from scripts.h0001_alpaca_admission import encode


def diagnostic(intraday):
    agg = CompletedAggregator(('1H',), profile=EXTENDED)
    hours = []
    for bar in intraday.bars:
        hours.extend(b for b in agg.accept(bar, bar.known_at) if b.timeframe == '1H')
    counts = Counter({'completed_H1':len(hours), 'H1_READY':0, 'H1_downside_extreme':0})
    extremes = []
    for i, b in enumerate(hours):
        if i+1 < 449: continue
        state = classify_h1_relative_setup(PreparedH1Prefix('SOXX', tuple(hours[:i+1]), b.known_at,
            b.end_at, intraday.dataset_id, b.known_at, price_basis=intraday.manifest.unpack()['price_basis']), b.known_at)
        counts['H1_READY'] += state.status == 'READY'
        counts['H1_downside_extreme'] += state.state == 'DOWNSIDE_EXTREME'
        if state.state == 'DOWNSIDE_EXTREME': extremes.append(b.end_at.isoformat())
    return {'schema':'H0001_SELECTED_DISCOVERY_H1_DIAGNOSTIC_V1', 'count_unit':'COMPLETED_H1_PUBLICATIONS',
        'counts':dict(counts), 'extreme_timestamps':extremes, 'intraday_hash':intraday.content_hash,
        'outcome_queries':0, 'network_calls':0, 'thresholds_changed':False}


def main():
    with ExitStack() as stack:
        for target in ('socket.socket.connect','curl_cffi.requests.get','urllib.request.urlopen'):
            stack.enter_context(patch(target, forbidden))
        calendar_guards(stack)
        capture = load_capture()
        admission, _, _ = audit(capture)
        data = intraday_dataset(capture, admission, INTRADAY_ID)
        first = diagnostic(data)
        second = diagnostic(data)
        if first != second: raise ValueError('H1 diagnostic repeat mismatch')
        write_new(ROOT/'h1-diagnostic-v2.json', encode(first))
        print(canonical(first))


if __name__ == '__main__': main()
