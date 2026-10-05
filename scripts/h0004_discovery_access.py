"""Dormant sealed H0004 discovery adapter; no CLI or automatic execution.

Only the next separately authorized action may call open_discovery. This file is
hashed before that access. Pre-access verification imports definitions only.
"""
import json
from pathlib import Path
from types import MappingProxyType

from richping.core import digest, timestamp
from richping.research_v2.contracts import payload
from richping.research_v2.alpaca_data import PROVIDER,PRICE,ACTION,CLOCK
from richping.research_v2.strategy.h0004_directional_evaluator import (
    DirectionalEvaluator, DatasetMetadata, SlotMetadata, close_identity, Scope)
from scripts.h0004_frequency_audit import SOURCE, load_admitted, fingerprint


def open_discovery(permit):
    # Gate/identity before any vintage parsing or price loading.
    from scripts.h0004_preaccess import DiscoveryPermit
    if type(permit) is not DiscoveryPermit:
        raise PermissionError('Verified pre-access permit required before price loading')
    binding,anchors = permit.authorize()
    if binding.synthetic or binding.scope is not Scope.DISCOVERY_EXPLORATORY:
        raise PermissionError('Only separately permitted immutable discovery scope')
    data = load_admitted()
    manifest = data.manifest.unpack()
    admission = manifest['admission']
    if (manifest['provider'],manifest['price_basis'],manifest['corporate_actions'],manifest['known_at_policy'])!=(
            PROVIDER,PRICE,ACTION,CLOCK):
        raise ValueError('Alpaca SIP/raw historical clock contract mismatch')
    if fingerprint(SOURCE/'admission.json')!=binding.admission_hash:
        raise ValueError('Admission identity changed')
    action = json.loads((SOURCE/'action-history-audit.json').read_bytes())
    units = json.loads((SOURCE/'ohlc-unit-crosscheck.json').read_bytes())
    if (digest(action)!=admission['action_audit_hash'] or digest(units)!=admission['daily_unit_audit_hash']
            or not action['interval_start']<='2026-05-05'<='2026-08-13'<=action['interval_end']):
        raise ValueError('No admitted action/unit certificate identity')
    unit_ok = not action['splits_inside_interval'] and admission['raw_split_identical_selected_intraday_and_daily'] is True
    cash = []
    for source in action['dataset_completeness_sources']:
        if source['identity']=='alpaca-selected-actions':
            cash = json.loads(Path(source['path']).read_bytes())['corporate_actions'].get('cash_dividends',[])
    ex_dates = {r.get('ex_date',r.get('ex_dividend_date','')) for r in cash}
    # No transforms: share-unit audit is ex-post admission, never a historical
    # causal absence receipt. Cash distributions do not turn price into total return.
    lookup = MappingProxyType({b.end_at:b for b in data.bars})
    metadata = DatasetMetadata(data.dataset_id,data.content_hash,binding.admission_hash,
        '2026-05-05','2026-08-13',tuple(SlotMetadata(b.end_at.isoformat(),b.known_at.isoformat(),
            close_identity(data.dataset_id,b.end_at,b.close),unit_segment='admitted_sip_raw_70',
            action='NONE_CONFIRMED',unit_certified=(unit_ok and b.corporate_action in ('NONE_CONFIRMED','UNKNOWN')
                and b.provenance.unpack().get('price_basis')==PRICE
                and b.provenance.unpack().get('corporate_actions')==ACTION),
            cash_dividend=b.session in ex_dates) for b in data.bars))
    def reader(at,identity):
        permit.authorize()
        bar = lookup.get(timestamp(at))
        if bar is None or close_identity(data.dataset_id,at,bar.close)!=identity:
            raise ValueError('No immutable admitted exact close')
        return bar.close
    evaluator = DirectionalEvaluator(anchors,binding,metadata,manifest['captured_at'],permit)
    return evaluator,reader
