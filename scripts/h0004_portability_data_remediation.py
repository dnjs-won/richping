"""Outcome-blind admission revision; reuses frozen capture and signal code verbatim."""
from argparse import ArgumentParser
from contextlib import contextmanager, ExitStack
from datetime import timedelta
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import tarfile
from unittest.mock import patch

from scripts import h0004_portability_preaccess as p
from scripts import h0004_frequency_audit as f
from richping.core import digest, timestamp
from richping.research_v2.real_data import expected_slots, request
from richping.research_v2.sessions import NY, segment

BASE = 'f3090a23123279cf0f9a506a526224cce7909e61'
BRANCH = 'v2-h0004-portability-v1-data-remediation'
PREDECESSOR = p.ROOT
ROOT = Path('research/data_evidence/h0004-portability-v1-data-remediation')
POLICY = Path('research/decision_records/H0004-portability-v1-remediation-policy.json')
PREDECESSOR_HASH = 'c84353e456627a07bf7f3139272a0e1dad119172f2fc230f3a2bd5518269f1e8'


def predecessor():
    p.frozen_context()
    if p.fingerprint(PREDECESSOR/'candidate-manifest.json') != PREDECESSOR_HASH:
        raise ValueError('Predecessor aggregate mutated')
    m = p.read(PREDECESSOR/'candidate-manifest.json')
    for r in m['symbols']:
        folder = PREDECESSOR/'streams'/r['symbol']
        for name, key in (('candidates.json','candidate_stream_sha256'),
                          ('input-manifest.json','input_manifest_sha256'),('seal.json','seal_sha256')):
            if p.fingerprint(folder/name) != r[key]:
                raise ValueError('Predecessor stream mutated')
    return m


def preserve():
    """Hash-only archive check, including all predecessor outcome evidence."""
    result = {}
    with tarfile.open(fileobj=io.BytesIO(p.git('archive','--format=tar',BASE))) as archive:
        for member in archive.getmembers():
            if member.isfile():
                h = f.preserved_raw(member.name, archive.extractfile(member).read())
                if f.preserved_bytes(member.name) != h:
                    raise ValueError('Immutable predecessor changed: '+member.name)
                result[member.name] = h
    return dict(predecessor_commit=BASE, protected_files=result,
                h0004=p.preservation(), outcome_evidence='HASH_ONLY_NOT_DECODED')


def policy_body():
    m = predecessor()
    return dict(schema='h0004_portability_data_remediation_policy_v1',research_id=p.ID,
        status='FROZEN_BEFORE_RETRY',predecessor_commit=BASE,predecessor_manifest_sha256=PREDECESSOR_HASH,
        universe_sha256=p.fingerprint(p.UNIVERSE),h0004_binding=p.bound_contract()[1],
        ordered_symbols=[r['symbol'] for r in m['symbols']],
        retry_symbols=[r['symbol'] for r in m['symbols'] if r['coverage']!='READY'],
        retry='ONE_COMPLETE_PAGINATED_CAPTURE_PER_NON_READY_SYMBOL; no second refresh',
        provider='Alpaca SIP',host='https://data.alpaca.markets',
        endpoints=['/v2/stocks/{symbol}/bars','/v1/corporate-actions'],
        capture_implementation='scripts/h0004_portability_preaccess.py:capture',
        capture_sha256=p.fingerprint('scripts/h0004_portability_preaccess.py'),
        bars=dict(start=p.START+'T08:00:00Z',end='2026-08-14T00:00:00Z',timeframe='15Min',
            feed='sip',sort='asc',limit=10000,asof='-',currency='USD',adjustments=['raw','split']),
        actions=dict(start=p.START,end=p.END,limit=1000),
        admission='Only exact provider observations at original missing slots may be added. Previously present raw OR split observations must be byte/semantic equal; no lost observations. Source revisions or action changes => UNRESOLVED, keep predecessor input, no silent refresh.',
        compatibility='Existing generic raw/split identity and cash-dividend-only contract. No new action interpretation; missing historical known_at is disclosed, never inferred from receipt time.',
        missing='All 4480 original scheduled slots retained; absence is UNKNOWN, never no-trade/halt proof.',
        ready_predecessors='Never retry or rewrite unchanged READY streams; reference their immutable seals.',
        forbidden=['alternate_provider','adjusted_signal_input','interpolation','forward_fill','backward_fill',
            'synthetic_bars','RTH_substitution','slot_deletion','symbol_overrides','parameter_changes','outcomes','returns'],
        stop='PORTABILITY_DATA_ADMISSION_FINALIZED; runtime outcome authorization DENIED',
        next_action='H0004_PORTABILITY_V1_OUTCOME_EVALUATION')


def frozen_policy():
    body = p.read(POLICY)
    if body != policy_body():
        raise ValueError('Remediation policy mutation')
    return body


@contextmanager
def capture_guard():
    """Same outcome/return denial as P0, permitting only its frozen HTTP capture."""
    counts = dict(outcome_accessor_calls=0, return_calculations=0)
    def denied(category):
        def call(*args,**kwargs):
            counts[category] += 1
            raise AssertionError('Remediation real outcomes and return calculations forbidden')
        return call
    with ExitStack() as stack:
        for name, category in f.GUARDS.items():
            if category != 'network_calls':
                stack.enter_context(patch(name,side_effect=denied('return_calculations' if category=='return_calculations' else 'outcome_accessor_calls')))
        for module,names in f.OUTCOME_MODULES.items():
            for name in names:
                stack.enter_context(patch(module+'.'+name,side_effect=denied('outcome_accessor_calls')))
        for name in ('open_discovery','load_admitted'):
            stack.enter_context(patch('scripts.h0004_discovery_access.'+name,side_effect=denied('outcome_accessor_calls')))
        for name in ('label','aggregate','readiness'):
            stack.enter_context(patch('richping.research_v2.strategy.h0004_directional_evaluator.DirectionalEvaluator.'+name,side_effect=denied('outcome_accessor_calls')))
        yield counts


def capture():
    policy = frozen_policy()
    if p.git('status','--porcelain').strip():
        raise ValueError('Commit frozen policy and pre-retry audit before HTTP retry')
    if p.git('branch','--show-current').decode().strip()!=BRANCH:
        raise ValueError('Wrong remediation branch')
    if sha256(p.git('show','HEAD:'+POLICY.as_posix())).hexdigest()!=p.fingerprint(POLICY):
        raise ValueError('Policy not committed before retry')
    u, protocol = p.frozen_context()
    subset = {**u,'ordered_symbols':policy['retry_symbols']}
    if any((ROOT/'inputs'/s/'capture.json').exists() for s in subset['ordered_symbols']):
        raise ValueError('One-pass retry already captured; immutable')
    original_context = p.frozen_context
    with capture_guard() as counts, patch.object(p,'ROOT',ROOT), patch.object(p,'frozen_context',return_value=(subset,protocol)):
        p.capture()  # EXACT predecessor implementation, no endpoint/parser/representation change.
    assert original_context()[0]['ordered_symbols']==policy['ordered_symbols']
    if any(counts.values()): raise ValueError('Forbidden access during retry')
    p.put(ROOT/'capture-access-audit.json',dict(**counts,policy_sha256=p.fingerprint(POLICY),
        policy_commit=p.git('rev-parse','HEAD').decode().strip(),network='FROZEN_CAUSAL_INPUT_ENDPOINTS_ONLY'))


def capture_audit(symbol, root):
    with patch.object(p,'ROOT',root):
        return p.audit_capture(symbol)


def missing_records(symbol, audit, capture_body):
    """Every absent bar start, completed clock, session slot and contiguous run."""
    grid, unsupported = expected_slots(request(symbol,p.START,'2026-08-14'))
    if unsupported: raise ValueError('Unexpected calendar mismatch')
    missing = set(audit['coverage']['missing_slots'])
    raw_times = {timestamp(r['t']).isoformat() for r in capture_body['bars']['raw']}
    records=[]; previous=None; run=-1
    for start in grid:
        if start.isoformat() not in missing: continue
        session = start.astimezone(NY).date().isoformat()
        if previous is None or start!=previous+timedelta(minutes=15) or previous.astimezone(NY).date()!=start.astimezone(NY).date():
            run += 1
        end = start+timedelta(minutes=15)
        records.append(dict(session=session,expected_timestamp=start.isoformat(),
            expected_completed_at=end.isoformat(),scheduled_slot=int((start.astimezone(NY).hour*60+start.astimezone(NY).minute-240)/15),
            segment=segment(start,end),gap_run=run,raw_source_bar_present=start.isoformat() in raw_times,
            ingestion_omission=False,calendar_expectation='VALID_FROZEN_EXTENDED_SESSION_SLOT',
            underlying_halt_or_no_eligible_trade='NOT_ESTABLISHED_BY_BAR_ABSENCE'))
        previous=start
    sizes={i:sum(r['gap_run']==i for r in records) for i in range(run+1)}
    for r in records:
        r['gap_run_length']=sizes[r['gap_run']];r['contiguous_gap']=sizes[r['gap_run']]>1
    return records


def unit_audit(c):
    raw = {timestamp(r['t']).isoformat():r for r in c.get('bars',{}).get('raw',[])}
    split = {timestamp(r['t']).isoformat():r for r in c.get('bars',{}).get('split',[])}
    differing=[t for t in sorted(raw.keys() & split.keys()) if raw[t]!=split[t]]
    return dict(actions=c.get('actions'),effective_at='Provider ex_date is effective DATE only; no intraday effective clock inferred',
        known_at='NOT_SUPPLIED_BY_PROVIDER; received_at is current capture knowledge, not historical announcement',
        symbol_history='Captured action symbols validated; lifecycle/halt history not supplied by these endpoints',
        raw_unit='USD_PER_SHARE_RAW',split_unit='DIAGNOSTIC_ONLY_NEVER_SIGNAL_INPUT',
        differing_observations=len(differing),first_difference=differing[0] if differing else None,
        last_difference=differing[-1] if differing else None,
        differing_fields=sorted({k for t in differing for k in raw[t] if raw[t].get(k)!=split[t].get(k)}),
        contract_compatible=(not differing and raw.keys()==split.keys() and 'actions' in c and
            not any(v for k,v in c['actions'].items() if k!='cash_dividends')),
        action_clock_policy='No new normalization, announcement reconstruction or share-unit interpretation allowed')


def exact_audit(symbol, root):
    audit,_=capture_audit(symbol,root)
    c=p.read(root/'inputs'/symbol/'capture.json')
    return dict(symbol=symbol,input_audit=audit,missing_count=audit['coverage']['missing_count'],
        missing_observations=missing_records(symbol,audit,c),
        provider_responses=c['requests'],parser_comparison='EXACT_PROVIDER_PAGES_EQUAL_LOCAL_PARSED_ROWS',
        calendar_error=False,unit_action_audit=unit_audit(c),
        cause='PROVIDER_COMPLETED_BAR_ABSENT; ingestion did not omit any returned bar',
        lifecycle_halt_cause='UNKNOWN; full RTH coverage; no halt/lifecycle feed in frozen input contract')


def before():
    p.put(POLICY,policy_body())
    with p.no_real_outcomes() as counts:
        for symbol in frozen_policy()['retry_symbols']:
            p.put(ROOT/'before'/symbol/'audit.json',exact_audit(symbol,PREDECESSOR))
        p.put(ROOT/'predecessor-preservation.json',preserve())
    if any(counts['real'].values()) or any(counts['shared'].values()): raise ValueError('Forbidden access')
    return dict(policy_sha256=p.fingerprint(POLICY),outcome_accessor_calls=0)


def compare_capture(old, new):
    """Strategy-neutral admission: only exact newly returned observations, no replacements."""
    result={}
    for adjustment in ('raw','split'):
        a={timestamp(r['t']).isoformat():r for r in old['bars'][adjustment]}
        b={timestamp(r['t']).isoformat():r for r in new.get('bars',{}).get(adjustment,[])}
        result[adjustment]=dict(added=sorted(b.keys()-a.keys()),lost=sorted(a.keys()-b.keys()),
            changed=[t for t in sorted(a.keys() & b.keys()) if a[t]!=b[t]])
    result['actions_changed']=old.get('actions')!=new.get('actions')
    result['compatible']=not result['actions_changed'] and not new.get('failure_type') and all(
        not result[k]['lost'] and not result[k]['changed'] for k in ('raw','split'))
    return result


def build():
    policy=frozen_policy();old=predecessor();preserve()
    capture_calls=p.read(ROOT/'capture-access-audit.json')
    if (capture_calls['policy_sha256']!=p.fingerprint(POLICY) or
            capture_calls['outcome_accessor_calls'] or capture_calls['return_calculations']):
        raise ValueError('Capture access/policy audit mismatch')
    prior=ROOT/'admission-manifest.json'
    code_commit=p.read(prior)['code_commit'] if prior.exists() else p.git('rev-parse','HEAD').decode().strip()
    sources={name:p.fingerprint(name) for name in ('scripts/h0004_portability_data_remediation.py',
        'tests/test_h0004_portability_data_remediation.py','scripts/h0004_portability_preaccess.py',
        p.read(p.FREEZE)['implementation'],POLICY.as_posix())}
    for name,h in sources.items():
        if sha256(p.git('show',code_commit+':'+name)).hexdigest()!=h: raise ValueError('Uncommitted source')
    rows=[];files={POLICY.as_posix():p.fingerprint(POLICY),
        (ROOT/'capture-access-audit.json').as_posix():p.fingerprint(ROOT/'capture-access-audit.json')}
    def bind(path): files[path.as_posix()]=p.fingerprint(path)
    with p.no_real_outcomes() as calls:
        for r in old['symbols']:
            symbol=r['symbol'];folder=ROOT/'streams'/symbol
            oldaudit=p.read(PREDECESSOR/'streams'/symbol/'input-manifest.json')
            bind(PREDECESSOR/'streams'/symbol/'input-manifest.json')
            bind(PREDECESSOR/'streams'/symbol/'seal.json')
            selected=PREDECESSOR;comparison=None;after=None
            if symbol in policy['retry_symbols']:
                after=exact_audit(symbol,ROOT)
                before_path=ROOT/'before'/symbol/'audit.json';bind(before_path)
                if p.read(before_path)!=exact_audit(symbol,PREDECESSOR): raise ValueError('Before audit changed')
                comparison=compare_capture(p.read(PREDECESSOR/'inputs'/symbol/'capture.json'),p.read(ROOT/'inputs'/symbol/'capture.json'))
                audit_hash=p.put(ROOT/'after'/symbol/'audit.json',after);bind(ROOT/'after'/symbol/'audit.json')
                selected=ROOT if comparison['compatible'] else PREDECESSOR
                retry_audit,_=capture_audit(symbol,ROOT)
                for name,h in retry_audit['raw_files'].items(): files[name]=h
                bind(ROOT/'inputs'/symbol/'capture.json')
            audit,bars=capture_audit(symbol,selected)
            if comparison and not comparison['compatible']:
                audit={**audit,'status':'UNRESOLVED','reason':'PROVIDER_REVISION_OR_INCOMPLETE_RETRY_NOT_ADMITTED'}
            # Unchanged input => same immutable candidate file, regardless of new receipt times.
            unchanged=audit['content_hash']==oldaudit['content_hash'] and audit['status']==r['coverage']
            if unchanged:
                stream_path=PREDECESSOR/'streams'/symbol/'candidates.json'
                stream=p.read(stream_path)
            else:
                stream_path=folder/'candidates.json'
                input_hash=p.put(folder/'input-manifest.json',audit);bind(folder/'input-manifest.json')
                stream=p.generate(symbol,bars,dict(input_manifest_sha256=input_hash,data_content_hash=audit['content_hash'])) if audit['status']=='READY' else dict(
                    symbol=symbol,coverage=audit['status'],signal_state='NOT_OBSERVED',candidate_count=None,
                    candidate_sessions=None,eligible_decision_opportunities=None,eligible_sessions=None,
                    signal_frequency_A=None,signal_frequency_B=None,events=[],outcome_access_count=0,reason=audit['reason'])
                p.put(stream_path,stream)
            bind(stream_path)
            for name,h in audit['raw_files'].items(): files[name]=h
            bind(selected/'inputs'/symbol/'capture.json')
            rows.append(dict(symbol=symbol,status=audit['status'],reason=audit['reason'],
                data_content_sha256=audit['content_hash'],data_capture_path=(selected/'inputs'/symbol/'capture.json').as_posix(),
                data_capture_sha256=audit['input_sha256'],candidate_stream_path=stream_path.as_posix(),
                candidate_stream_sha256=p.fingerprint(stream_path),predecessor_stream_reused=unchanged,
                predecessor_input_manifest_sha256=r['input_manifest_sha256'],
                predecessor_candidate_seal_sha256=r['seal_sha256'],
                coverage=audit['coverage'],retry_comparison=comparison,
                **{k:stream[k] for k in ('candidate_count','candidate_sessions','eligible_decision_opportunities',
                    'eligible_sessions','signal_frequency_A','signal_frequency_B','signal_state')}))
        if any(calls['real'].values()) or any(calls['shared'].values()): raise ValueError('Forbidden outcome access')
    return dict(schema='h0004_portability_admission_revision_2',research_id=p.ID,
        status='PORTABILITY_DATA_ADMISSION_FINALIZED',predecessor_commit=BASE,
        predecessor_manifest_sha256=PREDECESSOR_HASH,remediation_policy_sha256=p.fingerprint(POLICY),
        universe_sha256=p.fingerprint(p.UNIVERSE),h0004_binding=p.bound_contract()[1],
        portability_protocol_sha256=p.fingerprint(p.PROTOCOL),code_commit=code_commit,source_files=sources,
        files=files,symbols=rows,full_universe_count=10,guard_counts=calls,capture_guard_counts=capture_calls,
        outcome_accessor_calls=0,return_calculations=0,outcomes='NOT_ACCESSED',profitability='NOT_ESTIMATED',
        runtime_outcome_authorization='DENIED_STOP',next_action='H0004_PORTABILITY_V1_OUTCOME_EVALUATION',
        environment=dict(python=sys.version.split()[0],schema='admission_revision_2'),
        ready_count=sum(r['status']=='READY' for r in rows),unavailable_count=sum(r['status']=='UNAVAILABLE' for r in rows),
        unresolved_count=sum(r['status']=='UNRESOLVED' for r in rows))


def seal():
    if p.git('status','--porcelain').strip(): raise ValueError('Seal requires clean committed sources and captures')
    result=build();h=p.put(ROOT/'admission-manifest.json',result)
    p.put(ROOT/'admission-manifest.seal.json',dict(status='SEALED',manifest_sha256=h,
        predecessor_manifest_sha256=PREDECESSOR_HASH,policy_sha256=p.fingerprint(POLICY),code_commit=result['code_commit']))
    return dict(status=result['status'],manifest_sha256=h,outcome_accessor_calls=0)


def verify():
    m=p.read(ROOT/'admission-manifest.json');s=p.read(ROOT/'admission-manifest.seal.json')
    if s!=dict(status='SEALED',manifest_sha256=p.fingerprint(ROOT/'admission-manifest.json'),
        predecessor_manifest_sha256=PREDECESSOR_HASH,policy_sha256=p.fingerprint(POLICY),code_commit=m['code_commit']):
        raise ValueError('Admission seal mutation')
    for name,h in m['files'].items():
        if p.fingerprint(name)!=h: raise ValueError('Sealed input/stream mutation: '+name)
    if build()!=m: raise ValueError('Deterministic admission/source mismatch')
    if p.git('status','--porcelain').strip(): raise ValueError('Working tree not clean')
    if p.git('branch','--show-current').decode().strip()!=BRANCH: raise ValueError('Wrong branch')
    p.git('merge-base','--is-ancestor',m['code_commit'],'HEAD')
    return dict(status=m['status'],manifest_sha256=s['manifest_sha256'],outcome_accessor_calls=0,
        return_calculations=0,next_action=m['next_action'],runtime_outcome_authorization='DENIED_STOP')


def authorize_real_outcomes():
    raise PermissionError('DATA ADMISSION STOP; outcome evaluation requires separate action')


if __name__=='__main__':
    parser=ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['freeze','capture','seal','verify','digest'])
    action=parser.parse_args().action
    if action=='capture': capture()
    elif action=='digest': print(sha256(p.encode(build())).hexdigest())
    else: print(json.dumps({'freeze':before,'seal':seal,'verify':verify}[action](),indent=2))
