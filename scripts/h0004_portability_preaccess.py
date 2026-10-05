"""H0004 portability P0: immutable inputs and causal candidates, never outcomes.

The frozen generator has a SOXX namespace check. This adapter uses that SAME
namespace for every detached input, retaining the actual symbol in an outer
binding and candidate identity. No price, clock, feature or episode logic changes.
"""
from argparse import ArgumentParser
from contextlib import contextmanager, ExitStack
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
from unittest.mock import patch
import yaml

from richping.core import canonical, digest, sessions, timestamp
from richping.research_v2.contracts import payload
from richping.research_v2.sessions import NY, EXTENDED, session_bounds, segment
from richping.research_v2.sessions import EXTENDED_CONTINUITY
from richping.research_v2.features.continuity import slot_bounds
from richping.research_v2.strategy.h0004_segment_compression import Specification, CompressionStream, OHLCBar
from scripts.h0004_frequency_audit import fingerprint, preserved_raw, preserved_bytes, write_new

ID = 'H0004_PORTABILITY_V1'
BRANCH = 'v2-h0004-portability-v1-preaccess'
BASE = '9ad3546d6d0d273fa916d63da43d00a6a33131ad'
PM_BASE = '1789f7be7e3bbea298fb8984d2a9d5a072e14000'
ROOT = Path('research/data_evidence/h0004-portability-v1-preaccess')
UNIVERSE = Path('research/decision_records/H0004-portability-v1-universe.json')
PROTOCOL = Path('research/decision_records/H0004-portability-v1-protocol.json')
FREEZE = Path('research/decision_records/H0004-signal-freeze-v1.json')
OLD_PROTOCOL = Path('research/decision_records/H0004-efficacy-preregistration-v1.yaml')
SOURCE_URL = 'https://www.blackrock.com/mx/intermediarios/literature/annual-financial-statements/afs-j-ishares-nasdaq-s-and-p-phlx-etfs-03-31-en.pdf'
SOURCE_HASH = 'd6e66e38115d84822d03c350ba158ea0a600e7d8091e1b7af800895d5a5e8ec4'
SOURCE = ROOT/'sources'/('blackrock-'+SOURCE_HASH+'.pdf.bin')
START, END = '2026-05-05', '2026-08-13'
NET_ASSETS = 20230810498
# Official Schedule of Investments, printed page19, dated2026-03-31.
# Original holding value USD and symbol mapping; not market-return data.
HOLDINGS = (
    ('AMD',1308186519),('ADI',771871268),('AMAT',1181958696),('ARM',114830597),
    ('ASX',199086833),('ASML',721006755),('ALAB',265667770),('AVGO',1672601944),
    ('CRDO',270699772),('ENTG',315757451),('INTC',835216472),('KLAC',833718297),
    ('LRCX',788554748),('MTSI',265931934),('MRVL',1046576365),('MCHP',611637931),
    ('MU',1414414458),('MPWR',825925337),('NVMI',246516436),('NVDA',1699272677),
    ('NXPI',748575111),('ON',433124889),('QCOM',780952183),('RMBS',164288050),
    ('SWKS',143086296),('STM',124301468),('TSM',714400278),('TER',799648970),
    ('TXN',790089422),('UMC',114654476))


def git(*args):
    return subprocess.run(['git',*args],check=True,capture_output=True).stdout


def encode(body):
    """Canonical UTF8 JSON, sorted keys, compact separators, no terminal newline."""
    return canonical(body).encode('utf-8')


def read(path):
    return json.loads(Path(path).read_bytes())


def put(path, body):
    write_new(Path(path), encode(body))
    return sha256(encode(body)).hexdigest()


def bound_contract():
    frozen = read(FREEZE)
    for name, expected in ((frozen['spec_path'],frozen['spec_sha256']),
                           (frozen['implementation'],frozen['implementation_sha256'])):
        if fingerprint(name) != expected:
            raise ValueError('Frozen H0004 source mismatch: '+name)
    spec = Specification(**frozen['parameters'])
    if spec.content_hash != frozen['spec_hash']:
        raise ValueError('Effective configuration hash differs from frozen H0004')
    protocol = yaml.safe_load(OLD_PROTOCOL.read_bytes())
    if protocol['discovery']['interval'] != [START,END]:
        raise ValueError('Frozen discovery interval mismatch')
    # Protocol canonical hash uses the existing H0004 convention.
    result = dict(signal_freeze_sha256=fingerprint(FREEZE),
                  specification_hash=spec.content_hash,
                  protocol_hash=digest(protocol),protocol_file_sha256=fingerprint(OLD_PROTOCOL),
                  generator_sha256=frozen['implementation_sha256'],signal_trials=frozen['signal_trials'])
    if result['protocol_hash'] != '09e8202e4edd3a06c3b7907d7aafa70c93c05155d5f1d902c5d07798540d8d1f':
        raise ValueError('Frozen protocol hash mismatch')
    return spec,result


def select_universe(holdings=HOLDINGS):
    if len({s for s,_ in holdings}) != len(holdings):
        raise ValueError('Duplicate issuer/share-class mapping requires preregistration')
    if any(s=='SOXX' or type(v) is not int or v<=0 for s,v in holdings):
        raise ValueError('Only verified positive-weight constituent equities allowed')
    ordered = sorted(holdings,key=lambda row:(-row[1],row[0]))
    return [dict(symbol=s,original_rank=i+1,original_holding_value_usd=v,
                 weight_fraction=dict(numerator=v,denominator=NET_ASSETS),
                 weight_percent=str(Decimal(v)*100/Decimal(NET_ASSETS)),
                 asset_class='COMMON_STOCK_OR_ADR',issuer_key=s,
                 inclusion_status='INCLUDED' if i<10 else 'EXCLUDED',
                 exclusion_reason=None if i<10 else 'BELOW_TOP10_WEIGHT_RANK')
            for i,(s,v) in enumerate(ordered)]


def freeze():
    """Must run BEFORE capture or any signal replay."""
    if fingerprint(SOURCE) != SOURCE_HASH:
        raise ValueError('BLOCKED_UNIVERSE_SOURCE: official original not verified')
    if sum(v for _,v in HOLDINGS)!=20202553403:
        raise ValueError('Official equity total mismatch')
    _,binding = bound_contract()
    rows = select_universe()
    universe = dict(schema='h0004_portability_universe_v1',research_id=ID,
        status='FROZEN',universe_policy_version='HISTORICAL_SOXX_WEIGHT_TOP10_V1',
        constituent_snapshot_effective_date='2026-03-31',
        source_identity=dict(publisher='BlackRock / iShares Trust',url=SOURCE_URL,
            original_path=SOURCE.as_posix(),original_sha256=SOURCE_HASH,printed_page=19,
            selection='Verified complete official historical equity snapshot preceding discovery origin',
            weight_basis='Original holding value / original net assets; no rounded-weight ranking',
            delivery='Retrospectively published annual statement; no contemporaneous availability claim',
            rejected_sources=['Current iShares CSV endpoint returned current HTML, not historical CSV',
                              'Rolling fact-sheet URL is now2026-06-30, after discovery origin',
                              'Unverified2026-04-30 secondary table not used']),
        ordering='holding value DESC (identical to weight DESC), symbol ASC for exact ties',
        exclusions='Equity constituents only; SOXX/leveraged/inverse ETFs, cash, collateral and derivatives excluded. One issuer/share class; duplicate mapping blocks rather than discretionary replacement.',
        rows=rows,ordered_symbols=[r['symbol'] for r in rows if r['inclusion_status']=='INCLUDED'],
        symbol_count=10,replacement='FORBIDDEN_REGARDLESS_OF_COVERAGE_OR_SIGNAL',
        canonical_serialization='richping.core.canonical UTF8 JSON; SHA256 of exact file bytes')
    universe_hash = put(UNIVERSE,universe)
    protocol = dict(schema='h0004_portability_protocol_v1',research_id=ID,
        scope='INTRA_SECTOR_CROSS_SYMBOL_PORTABILITY',status='FROZEN_BEFORE_SIGNAL_AND_OUTCOMES',
        question='Does the SOXX-frozen H0004 signal occur on other semiconductor constituents without parameter changes?',
        base_implementation_commit=BASE,main_pm_reference=PM_BASE,h0004_binding=binding,
        frozen_contract_reference=[FREEZE.as_posix(),OLD_PROTOCOL.as_posix()],
        universe_manifest=UNIVERSE.as_posix(),universe_manifest_sha256=universe_hash,
        interval=[START,END],provider='Alpaca SIP',adjustment='RAW',currency='USD/share',
        session='Frozen nominal04-20ET official XNYS15m slots; completed end=assumed publication; unsupported sessions and gaps never filled',
        configuration='Load frozen Specification directly; effective hash exact match required. No symbol override interface.',
        adapter='Every actual symbol mapped identically to internal SOXX namespace in detached OHLCBar. Actual symbol/source binding retained in outer record/id. Frozen source and semantics unchanged.',
        coverage='READY only full4480 supported slots with original raw/split identity and complete no-split unit evidence. Missing inputs UNAVAILABLE; ambiguous actions/units/source UNRESOLVED. No provider/adjusted fallback.',
        candidate_semantics='Inherited immutable first-breakout episode, strict close, prior completed-session same-segment reference, rearm and expiry. No boundary reset, thinning or new trial.',
        opportunity_denominator='Eligible completed input observations: frozen Step.input_status==READY, including reference warmup; additionally disclose feature READY observations/sessions separately. At most one candidate per eligible decision opportunity.',
        signal_frequency_A='candidate_count / eligible_decision_opportunities; zero denominator=>null',
        signal_frequency_B='candidate_sessions / eligible_sessions; zero denominator=>null',
        zero_signal='READY with zero candidates retained; future returns and direction null, never0',
        unavailable='Retained in full universe; counts/frequency not observed=>null, empty sealed stream is NOT ZERO_SIGNAL',
        denominators=dict(full='All10 preregistered symbols, never reduced',ready='Coverage READY symbols',
            informative='READY symbols with candidate_count>0',
            complete_outcome='Informative symbols whose ENTIRE emitted cohort is COMPLETE; ZERO_SIGNAL excluded'),
        future_report=dict(status='SCHEMA_ONLY_NOT_EXECUTED',
            inherited='Exact scheduled t+16, all-path compatible raw units, missing/unsupported retention and equal-event-within-session/equal-occupied-session weighting directly from frozen H0004 protocol; price-only gross opportunity, not profitability',
            per_symbol=['candidate_count','candidate_sessions','signal_frequency_A','signal_frequency_B',
                'coverage','COMPLETE','PENDING','UNRESOLVED','ZERO_SIGNAL','session_balanced_gross_return',
                'median','positive_events','negative_events','zero_events'],
            cross_symbol=['full_universe_count','READY_symbol_count','informative_symbol_count',
                'COMPLETE_outcome_universe_count','direction_positive_symbol_count','direction_negative_symbol_count',
                'direction_zero_symbol_count','same_direction_as_SOXX_count','full_universe_direction_ratio',
                'informative_universe_direction_ratio','equal_symbol_weight_summary'],
            direction='Sign of complete full-cohort session-balanced mean; missing/no-signal direction null. SOXX reference is existing frozen owner-supplied disposition, no reevaluation.',
            ratios='positive_direction_symbols/full_preregistered_N AND positive_direction_symbols/informative_N; zero denominator=>null; analogous same-direction ratios',
            equal_symbol_weight='Mean of complete informative per-symbol session-balanced means ONLY if every informative symbol is COMPLETE; otherwise primary full-informative mean null. Report contributing N and full N. No ZERO_SIGNAL return assignment.',
            pooled_event='DIAGNOSTIC_ONLY_NEVER_PRIMARY',
            concentration=dict(candidate_count='N_s / sum(N_s), largest/top2 shares and HHI=sum(shares squared); unavailable counts unknown disclosed, not imputed',
                return_contribution='Equal-symbol signed contributions r_s / informative_N; largest/top2 ABSOLUTE contribution shares abs(r_s)/sum(abs(r)); all-zero denominator=>null; incomplete cohort=>null',
                policy='DIAGNOSTIC_ONLY; no exclusions, retuning or symbol replacement')),
        access_gate=['protocol/universe frozen','frozen contract hash exact match','all symbol streams sealed',
            'aggregate sealed','real outcome calls0','no symbol override','clean Git/source binding'],
        stop='P0_STOP_AFTER_CANDIDATE_SEAL; this action cannot issue runtime outcome authorization',
        outcomes='NOT_ACCESSED',profitability='NOT_ESTIMATED',H0004_signal_trials_unchanged=2,
        interpretation='Shared semiconductor factor; not10 independent replications, independent-asset confirmation or general-market generalization',
        later_scope='Cross-sector/independent-asset protocol separately; control-layer remediation P2; no main integration')
    return dict(universe_hash=universe_hash,protocol_hash=put(PROTOCOL,protocol),symbols=universe['ordered_symbols'])


def frozen_context():
    _,binding = bound_contract()
    u,p = read(UNIVERSE),read(PROTOCOL)
    if (u['status']!='FROZEN' or p['status']!='FROZEN_BEFORE_SIGNAL_AND_OUTCOMES'
            or p['universe_manifest_sha256']!=fingerprint(UNIVERSE) or p['h0004_binding']!=binding
            or u['rows']!=select_universe() or u['ordered_symbols']!=[r['symbol'] for r in u['rows'][:10]]):
        raise ValueError('Frozen universe/protocol/config mismatch')
    return u,p


def capture():
    """Only fixed causal-input capture, before candidates exist. No endpoint query."""
    from curl_cffi import requests
    from scripts.h0001_alpaca_admission import credentials, HOST, validate_bar, ProviderFailure
    u,_ = frozen_context()
    headers = credentials()
    for symbol in u['ordered_symbols']:
        target = ROOT/'inputs'/symbol/'capture.json'
        if target.exists():
            raise ValueError('Capture immutable; no refresh/replacement: '+symbol)
        records=[]
        def fetch(endpoint,params):
            if endpoint not in (f'/v2/stocks/{symbol}/bars','/v1/corporate-actions'):
                raise ValueError('Causal input read-only allowlist')
            response=requests.get(HOST+endpoint,params=params,headers=headers,timeout=40,impersonate='chrome')
            raw=response.content
            if any(v.encode() in raw for v in headers.values()):
                raise ValueError('Unsafe credential echo; do not persist')
            h=sha256(raw).hexdigest()
            write_new(ROOT/'inputs'/symbol/'raw'/(h+'.json'),raw)
            records.append(dict(endpoint=endpoint,params=dict(params),sha256=h,bytes=len(raw),
                status=response.status_code,received_at=datetime.now(timezone.utc).isoformat()))
            if response.status_code!=200:
                raise ProviderFailure('HTTP'+str(response.status_code))
            body=json.loads(raw)
            if not isinstance(body,dict) or any(k in body for k in ('error','message','code')):
                raise ProviderFailure('Malformed provider payload')
            return body
        result=dict(symbol=symbol,universe_sha256=fingerprint(UNIVERSE),
            protocol_sha256=fingerprint(PROTOCOL),provider='Alpaca SIP',outcome_access_count=0)
        try:
            result['bars']={}
            for adjustment in ('raw','split'):
                params=dict(start=START+'T08:00:00Z',end='2026-08-14T00:00:00Z',
                    timeframe='15Min',feed='sip',adjustment=adjustment,sort='asc',limit=10000,asof='-',currency='USD')
                current=dict(params); rows=[]; tokens=set()
                while True:
                    body=fetch(f'/v2/stocks/{symbol}/bars',current)
                    if body.get('symbol')!=symbol or not isinstance(body.get('bars'),list):
                        raise ProviderFailure('Symbol or bar schema mismatch')
                    for row in body['bars']:
                        validate_bar(row)
                        t=timestamp(row['t'])
                        if not timestamp(params['start'])<=t<timestamp(params['end']) or (rows and t<=timestamp(rows[-1]['t'])):
                            raise ProviderFailure('Off-interval/reversed/duplicate input')
                        rows.append(row)
                    if 'next_page_token' not in body: raise ProviderFailure('No pagination completion marker')
                    token=body['next_page_token']
                    if token is None: break
                    if not isinstance(token,str) or not token or token in tokens or not body['bars']:
                        raise ProviderFailure('Pagination cycle')
                    tokens.add(token);current={**params,'page_token':token}
                result['bars'][adjustment]=rows
            params=dict(symbols=symbol,start=START,end=END,limit=1000)
            current=dict(params);tokens=set();actions={};seen=set()
            while True:
                body=fetch('/v1/corporate-actions',current)
                if not isinstance(body.get('corporate_actions'),dict) or 'next_page_token' not in body:
                    raise ProviderFailure('Ambiguous action schema')
                for kind,rows in body['corporate_actions'].items():
                    if not isinstance(rows,list): raise ProviderFailure('Malformed action list')
                    for row in rows:
                        if row.get('symbol')!=symbol or not row.get('id') or row['id'] in seen:
                            raise ProviderFailure('Ambiguous action identity')
                        seen.add(row['id']);actions.setdefault(kind,[]).append(row)
                token=body['next_page_token']
                if token is None: break
                if not isinstance(token,str) or not token or token in tokens:
                    raise ProviderFailure('Action pagination cycle')
                tokens.add(token);current={**params,'page_token':token}
            result['actions']=actions
        except Exception as exc:
            # Never log provider exception text (may contain sensitive headers).
            result['failure_type']=type(exc).__name__
        result['requests']=records
        put(target,result)
        print(json.dumps(dict(symbol=symbol,capture='SAVED',failure=result.get('failure_type'),requests=len(records))),flush=True)


def audit_capture(symbol):
    """No signal/outcome evaluation. Exact same input grid; no adjustment fallback."""
    from scripts.h0001_alpaca_admission import grid
    u,_=frozen_context()
    if symbol not in u['ordered_symbols']: raise ValueError('Symbol not preregistered')
    path=ROOT/'inputs'/symbol/'capture.json'
    if not path.exists():
        return dict(symbol=symbol,status='UNAVAILABLE',reason='NO_PROVIDER_CAPTURE',input_sha256=None),()
    c=read(path)
    if (c['symbol']!=symbol or c['universe_sha256']!=fingerprint(UNIVERSE)
            or c['protocol_sha256']!=fingerprint(PROTOCOL) or c['outcome_access_count']!=0):
        raise ValueError('Capture binding mismatch')
    raw_hashes={}
    for record in c['requests']:
        p=path.parent/'raw'/(record['sha256']+'.json')
        if fingerprint(p)!=record['sha256'] or p.stat().st_size!=record['bytes']:
            raise ValueError('Input raw mutation')
        raw_hashes[p.as_posix()]=record['sha256']
        params=record['params']
        if record['endpoint'].endswith('/bars') and (
                record['endpoint']!=f'/v2/stocks/{symbol}/bars'
                or params.get('feed')!='sip' or params.get('timeframe')!='15Min'
                or params.get('adjustment') not in ('raw','split')
                or params.get('start')!=START+'T08:00:00Z'
                or params.get('end')!='2026-08-14T00:00:00Z'
                or params.get('currency')!='USD' or params.get('asof')!='-'):
            raise ValueError('Causal provider contract mismatch')
    status,reason='READY','COMPLETE_CAUSAL_INPUT_GRID_RAW_IDENTITY'
    rows=c.get('bars',{}).get('raw',[])
    coverage=grid(rows,START,'2026-08-14') if rows else None
    # Capture raw rows AND original provider pages must agree; no substituted copy.
    for adjustment,values in c.get('bars',{}).items():
        original=[]
        for rec in c['requests']:
            if rec['status']==200 and rec['endpoint'].endswith('/bars') and rec['params']['adjustment']==adjustment:
                original.extend(read(path.parent/'raw'/(rec['sha256']+'.json'))['bars'])
        if original!=values: raise ValueError('Parsed/raw input mismatch')
    original_actions={}
    for rec in c['requests']:
        if rec['endpoint']=='/v1/corporate-actions' and rec['status']==200:
            if (rec['params'].get('symbols')!=symbol or rec['params'].get('start')!=START
                    or rec['params'].get('end')!=END):
                raise ValueError('Action interval binding mismatch')
            for kind,values in read(path.parent/'raw'/(rec['sha256']+'.json'))['corporate_actions'].items():
                original_actions.setdefault(kind,[]).extend(values)
    if 'actions' in c and original_actions!=c['actions']:
        raise ValueError('Parsed/raw action mismatch')
    if c.get('failure_type') or 'actions' not in c or 'split' not in c.get('bars',{}):
        status,reason='UNRESOLVED','INCOMPLETE_PROVIDER_OR_UNIT_EVIDENCE'
    elif rows!=c['bars']['split'] or any(v for k,v in c['actions'].items() if k not in ('cash_dividends',)):
        status,reason='UNRESOLVED','RAW_SPLIT_OR_CORPORATE_ACTION_UNIT_AMBIGUITY'
    elif coverage is None or coverage['missing_count'] or coverage['offgrid'] or coverage['unsupported_sessions']:
        status,reason='UNAVAILABLE','INCOMPLETE_FROZEN_INPUT_GRID'
    if status=='READY' and (coverage['expected_supported_slots']!=4480 or coverage['observed']!=4480):
        raise ValueError('Original grid contract not reproduced')
    result=dict(symbol=symbol,status=status,reason=reason,input_sha256=fingerprint(path),
        raw_files=raw_hashes,content_hash=digest(rows),coverage=coverage,
        action_evidence_sha256=digest(c.get('actions')),provider='Alpaca SIP',adjustment='raw',
        corporate_action_contract='Interval raw/split identity + complete no-share-unit-action capture. Cash dividends disclosed, no feature transform and no outcome dividend accounting claimed.')
    if status!='READY': return result,()
    dataset_id=f'{symbol.lower()}-alpaca-sip-15m-h0004-portability-v1'
    bars=tuple(OHLCBar(dataset_id,symbol,timestamp(r['t'])+timedelta(minutes=15),
        timestamp(r['t'])+timedelta(minutes=15),timestamp(r['t']).astimezone(NY).date().isoformat(),
        r['o'],r['h'],r['l'],r['c']) for r in rows)
    return result,bars


@contextmanager
def no_real_outcomes():
    """Allow fixture arithmetic in regression, deny ALL actual outcome loaders."""
    from scripts.h0004_frequency_audit import no_outcomes
    from richping.research_v2.strategy import h0004_directional_evaluator as evaluator
    counts=dict(real_outcome_access=0,endpoint_probes=0)
    def forbidden(*args,**kwargs):
        counts['real_outcome_access']+=1
        raise AssertionError('P0 real outcome access forbidden')
    def guard(original,category):
        def wrapped(self,*args,**kwargs):
            if not self.binding.synthetic:
                counts[category]+=1
                raise AssertionError('P0 real outcome access forbidden')
            return original(self,*args,**kwargs)
        return wrapped
    with no_outcomes() as shared,ExitStack() as stack:
        for name in ('open_discovery','load_admitted'):
            stack.enter_context(patch('scripts.h0004_discovery_access.'+name,side_effect=forbidden))
        for name in ('label','aggregate','readiness'):
            original=getattr(evaluator.DirectionalEvaluator,name)
            stack.enter_context(patch.object(evaluator.DirectionalEvaluator,name,
                guard(original,'endpoint_probes' if name=='readiness' else 'real_outcome_access')))
        yield dict(real=counts,shared=shared)


def generate(symbol,bars,source_binding):
    """No callable outcome accessor or parameter argument; frozen generator only."""
    u,_=frozen_context()
    if symbol not in u['ordered_symbols'] and symbol!='SOXX':
        raise ValueError('Unregistered symbol')
    spec,_=bound_contract()
    stream=CompressionStream(spec)
    events=[];old_events=[];eligible=0;ready=0;eligible_sessions=set();ready_sessions=set()
    prior=None
    for actual in bars:
        if actual.symbol!=symbol or actual.known_at!=actual.end_at or (prior and actual.end_at<=prior):
            raise ValueError('Symbol/causal publication/order mismatch')
        # The only generic adaptation; uses the same namespace for EVERY symbol.
        bar=replace(actual,symbol='SOXX')
        step=stream.accept(bar,bar.known_at)
        if step.input_status=='INVALID': raise ValueError('Frozen signal input rejected')
        if step.input_status=='READY':
            eligible+=1;eligible_sessions.add(actual.session)
        if step.feature.status=='READY':
            ready+=1;ready_sessions.add(actual.session)
        for event in step.events:
            original=payload(event);old_events.append(original)
            start,end=slot_bounds(actual.end_at,'15m',EXTENDED_CONTINUITY)
            body=dict(symbol=symbol,frozen_event=original,causal_timestamp=original['at'],
                session_id=original['session'],scheduled_slot_identity=dict(start=start.isoformat(),end=end.isoformat()),
                segment=segment(start,end),readiness_state='READY',source_input_binding=source_binding,
                frozen_config_hash=spec.content_hash,internal_symbol_namespace='SOXX')
            events.append(dict(candidate_id=digest(body),**body))
        prior=actual.end_at
    n=len(events);days=len({e['session_id'] for e in events})
    return dict(symbol=symbol,coverage='READY',signal_state='ZERO_SIGNAL' if n==0 else 'NONZERO_SIGNAL',
        eligible_decision_opportunities=eligible,eligible_sessions=len(eligible_sessions),
        feature_ready_observations=ready,feature_ready_sessions=len(ready_sessions),
        candidate_count=n,candidate_sessions=days,signal_frequency_A=n/eligible if eligible else None,
        signal_frequency_B=days/len(eligible_sessions) if eligible_sessions else None,
        events=events,frozen_event_stream_hash=digest(old_events),outcome_access_count=0)


def preservation():
    """Only hashes of discovery evidence; never decode outcome/report/label bytes."""
    raw=git('archive','--format=tar',BASE)
    result={}
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive.getmembers():
            if not member.isfile(): continue
            if member.name.startswith(('research/','richping/','scripts/','tests/','docs/')):
                expected=preserved_raw(member.name,archive.extractfile(member).read())
                if preserved_bytes(member.name)!=expected: raise ValueError('Frozen lineage changed: '+member.name)
                result[member.name]=expected
    frozen=read(FREEZE)
    raw_events=Path(frozen['candidate_events']).read_bytes()
    if sha256(raw_events).hexdigest()!=frozen['candidate_events_sha256']:
        raise ValueError('Original SOXX stream bytes changed')
    events=json.loads(raw_events)['events']
    if len(events)!=48 or len({e['session'] for e in events})!=29 or digest(events)!=frozen['event_stream_hash']:
        raise ValueError('Original SOXX48/29 semantic stream changed')
    return dict(base_commit=BASE,protected_files=result,all_preserved=True,
        SOXX=dict(candidate_count=48,candidate_sessions=29,stream_sha256=frozen['candidate_events_sha256'],
                  semantic_hash=frozen['event_stream_hash']),discovery_evidence='HASH_ONLY_NOT_PARSED',
        confirmation='FROZEN_PENDING_ASYNCHRONOUS_UNCHANGED')


def generate_all():
    u,p=frozen_context()
    preserved=preservation()
    existing=ROOT/'candidate-manifest.json'
    code_commit=read(existing)['code_commit'] if existing.exists() else git('rev-parse','HEAD').decode().strip()
    if git('status','--porcelain').strip():
        raise ValueError('Candidate execution requires committed clean working tree')
    source_files=[Path(__file__).relative_to(Path.cwd()),Path('tests/test_h0004_portability_preaccess.py'),
        Path('scripts/h0004_portability_test_guard.py'),UNIVERSE,PROTOCOL]
    source_hashes={x.as_posix():fingerprint(x) for x in source_files}
    for name,h in source_hashes.items():
        if sha256(git('show',code_commit+':'+name)).hexdigest()!=h:
            raise ValueError('Repeat replay source differs from original code commit')
    rows=[]
    with no_real_outcomes() as calls:
        for symbol in u['ordered_symbols']:
            audit,bars=audit_capture(symbol)
            h=put(ROOT/'streams'/symbol/'input-manifest.json',audit)
            if audit['status']=='READY':
                stream=generate(symbol,bars,dict(input_manifest_sha256=h,data_content_hash=audit['content_hash']))
            else:
                stream=dict(symbol=symbol,coverage=audit['status'],signal_state='NOT_OBSERVED',
                    eligible_decision_opportunities=None,eligible_sessions=None,candidate_count=None,
                    candidate_sessions=None,signal_frequency_A=None,signal_frequency_B=None,
                    events=[],outcome_access_count=0,reason=audit['reason'])
            stream_hash=put(ROOT/'streams'/symbol/'candidates.json',stream)
            seal=dict(symbol=symbol,status='SEALED',protocol_sha256=fingerprint(PROTOCOL),
                frozen_h0004_binding=p['h0004_binding'],universe_sha256=fingerprint(UNIVERSE),
                input_manifest_sha256=h,candidate_stream_sha256=stream_hash,code_commit=code_commit,
                generator_sha256=p['h0004_binding']['generator_sha256'],schema='h0004_portability_candidate_v1',
                environment=dict(python=sys.version.split()[0],exchange_calendars=__import__('importlib.metadata',fromlist=['version']).version('exchange_calendars')))
            put(ROOT/'streams'/symbol/'seal.json',seal)
            rows.append(dict(symbol=symbol,coverage=audit['status'],input_manifest_sha256=h,
                candidate_stream_sha256=stream_hash,seal_sha256=fingerprint(ROOT/'streams'/symbol/'seal.json'),
                **{k:stream[k] for k in ('signal_state','candidate_count','candidate_sessions',
                    'eligible_decision_opportunities','eligible_sessions','signal_frequency_A','signal_frequency_B')}))
        if any(calls['real'].values()) or any(calls['shared'].values()):
            raise ValueError('Nonzero forbidden access during candidate generation')
    manifest=dict(schema='h0004_portability_aggregate_manifest_v1',research_id=ID,status='SEALED',
        protocol_sha256=fingerprint(PROTOCOL),universe_sha256=fingerprint(UNIVERSE),
        h0004_binding=p['h0004_binding'],code_commit=code_commit,source_files=source_hashes,
        symbols=rows,full_universe_count=u['symbol_count'],outcome_access_count=0,
        guard_counts=calls,preservation_sha256=put(ROOT/'preservation.json',preserved),
        outcomes='NOT_ACCESSED',profitability='NOT_ESTIMATED',symbol_overrides=False)
    manifest_hash=put(ROOT/'candidate-manifest.json',manifest)
    put(ROOT/'candidate-manifest.seal.json',dict(schema='h0004_portability_aggregate_seal_v1',
        status='SEALED',manifest_sha256=manifest_hash,protocol_sha256=fingerprint(PROTOCOL),
        universe_sha256=fingerprint(UNIVERSE),code_commit=code_commit))
    return manifest


def verify_preaccess():
    """Structural permit check ONLY; never grants outcome authorization in P0."""
    u,p=frozen_context();m=read(ROOT/'candidate-manifest.json')
    aggregate_seal=read(ROOT/'candidate-manifest.seal.json')
    if (aggregate_seal['status']!='SEALED'
            or aggregate_seal['manifest_sha256']!=fingerprint(ROOT/'candidate-manifest.json')
            or aggregate_seal['protocol_sha256']!=fingerprint(PROTOCOL)
            or aggregate_seal['universe_sha256']!=fingerprint(UNIVERSE)
            or aggregate_seal['code_commit']!=m['code_commit']):
        raise ValueError('Aggregate seal mutation detected')
    if git('status','--porcelain').strip(): raise ValueError('Working tree not clean')
    if (m['status']!='SEALED' or m['protocol_sha256']!=fingerprint(PROTOCOL)
            or m['universe_sha256']!=fingerprint(UNIVERSE) or m['h0004_binding']!=p['h0004_binding']
            or m['outcome_access_count']!=0 or m['symbol_overrides'] is not False
            or [r['symbol'] for r in m['symbols']]!=u['ordered_symbols']):
        raise ValueError('Aggregate preaccess gate mismatch')
    if git('branch','--show-current').decode().strip()!=BRANCH:
        raise ValueError('Wrong research branch')
    git('merge-base','--is-ancestor',m['code_commit'],'HEAD')
    for name,h in m['source_files'].items():
        if fingerprint(name)!=h or sha256(git('show',m['code_commit']+':'+name)).hexdigest()!=h:
            raise ValueError('Code/source binding mismatch: '+name)
    for row in m['symbols']:
        d=ROOT/'streams'/row['symbol']
        seal=read(d/'seal.json');stream=read(d/'candidates.json');audit=read(d/'input-manifest.json')
        if (seal['status']!='SEALED' or seal['protocol_sha256']!=m['protocol_sha256']
                or seal['universe_sha256']!=m['universe_sha256'] or seal['frozen_h0004_binding']!=m['h0004_binding']
                or seal['code_commit']!=m['code_commit']
                or seal['candidate_stream_sha256']!=fingerprint(d/'candidates.json')
                or row['candidate_stream_sha256']!=fingerprint(d/'candidates.json')
                or row['seal_sha256']!=fingerprint(d/'seal.json')
                or seal['input_manifest_sha256']!=fingerprint(d/'input-manifest.json')
                or row['input_manifest_sha256']!=fingerprint(d/'input-manifest.json')
                or stream['symbol']!=row['symbol'] or stream['outcome_access_count']!=0):
            raise ValueError('Symbol stream seal mismatch')
        current,_=audit_capture(row['symbol'])
        if current!=audit: raise ValueError('Input binding changed')
    if fingerprint(ROOT/'preservation.json')!=m['preservation_sha256'] or preservation()!=read(ROOT/'preservation.json'):
        raise ValueError('Frozen artifact preservation mismatch')
    if any(m['guard_counts']['real'].values()) or any(m['guard_counts']['shared'].values()):
        raise ValueError('Outcome guard audit not zero')
    return dict(status='READY_FOR_PORTABILITY_OUTCOME_ACCESS',research_id=ID,
        candidate_manifest_sha256=fingerprint(ROOT/'candidate-manifest.json'),outcome_access_count=0,
        runtime_outcome_authorization='DENIED_P0_STOP_REQUIRES_SEPARATE_ACTION')


def authorize_real_outcomes():
    verify_preaccess()
    raise PermissionError('P0 STOP: real outcome access requires a separate authorized phase')


if __name__=='__main__':
    parser=ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('freeze','capture','generate','verify'))
    action=parser.parse_args().action
    if action=='capture': capture()
    else:
        result={'freeze':freeze,'generate':generate_all,'verify':verify_preaccess}[action]()
        if action=='generate':
            result=dict(status='SEALED_AWAITING_CLEAN_COMMIT_VERIFICATION',symbols=result['symbols'],outcome_access_count=0)
        print(json.dumps(result,indent=2))
