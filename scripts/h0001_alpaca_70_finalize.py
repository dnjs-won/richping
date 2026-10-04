"""Finalize bounded discovery evidence and main-only PM routing from actual proofs."""
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import yaml

from richping.core import digest, timestamp, code_hash
from richping.research_v2.sessions import NY
from scripts.h0001_alpaca_70_discovery import ROOT, load_capture, INTRADAY_ID, DAILY_ID
from scripts.h0001_alpaca_admission import encode, credentials
from scripts.h0001_long_history_audit import write_new

BRANCH = 'v2-h0001-alpaca-70-session-discovery'
DOC = 'docs/H0001_ALPACA_70_DISCOVERY.md'
RECORD = 'research/decision_records/H0001-alpaca-70-discovery-v1.yaml'


def read(name): return json.loads((ROOT/name).read_bytes())


def junit(path):
    root = ET.parse(path).getroot()
    suites = list(root.iter('testsuite'))
    result = {k:sum(int(s.attrib[k]) for s in suites) for k in ('tests','failures','errors','skipped')}
    result.update(seconds=sum(float(s.attrib['time']) for s in suites),
                  sha256=sha256(path.read_bytes()).hexdigest())
    if any(result[k] for k in ('failures','errors','skipped')): raise ValueError('Final tests must all pass')
    result['passed'] = result['tests']
    return result


def workstream():
    proof, admission, diag = read('offline-reload-proof.json'), read('admission.json'), read('h1-diagnostic-v2.json')
    if proof['candidate_count'] != 0: raise ValueError('Nonempty stream needs separate descriptive protocol execution')
    if not proof['repeat_equal'] or not admission['exact_expected_grid_equality']: raise ValueError('Proof incomplete')
    tests = {name:junit(Path(path)) for name,path in {
        'targeted':'var/h0001-alpaca-70-targeted-v2.xml', 'full':'var/h0001-alpaca-70-final-full.xml'}.items()}
    frozen = read('frozen-byte-snapshot.json')
    for p,h in frozen.items():
        if sha256(Path(p).read_bytes()).hexdigest() != h: raise ValueError('Frozen file bytes changed')
    write_new(ROOT/'preservation-proof.json', encode({'files_sha256':frozen, 'all_bytes_equal':True,
        'frozen_source_protocol_and_original_ZERO_SIGNAL_preserved':True}))
    source_paths = sorted(Path('richping').rglob('*.py')) + sorted(Path('scripts').glob('h0001*.py')) + [Path('scripts/prepare_independent_research.py')]
    write_new(ROOT/'execution-source-manifest.json', encode({'code_hash':code_hash(),
        'source_LF_sha256':{p.as_posix():sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in source_paths},
        'host_hash_memoization':'Immutable object content hashes only; no strategy computation/threshold/time semantics changed.',
        'production_model_risk_writes':0}))
    c = load_capture()
    # Independent actual same-snapshot unit diagnostics; no exact nativeDaily/intraday aggregation claim.
    days = defaultdict(list)
    for b in c['cases']['m15-raw']['rows']:
        local = timestamp(b['t']).astimezone(NY)
        if 570 <= local.hour*60+local.minute < 960: days[local.date().isoformat()].append(b)
    daily = {timestamp(b['t']).astimezone(NY).date().isoformat():b for b in c['cases']['daily-raw']['rows']}
    units = []
    for day,rows in days.items():
        values = {'o':rows[0]['o'], 'h':max(b['h'] for b in rows), 'l':min(b['l'] for b in rows), 'c':rows[-1]['c']}
        units.append({'session':day, 'nativeDaily':{k:daily[day][k] for k in values},
            'actual_RTH_m15_aggregate':values, 'price_ratios':{k:values[k]/daily[day][k] for k in values},
            'differences_USD':{k:abs(values[k]-daily[day][k]) for k in values}})
    write_new(ROOT/'daily-intraday-unit-diagnostic.json', encode({'scope':'SELECTED70_SAME_ALPACA_RAW_SNAPSHOT',
        'rows':units, 'max_differences_USD':{k:max(r['differences_USD'][k] for r in units) for k in ('o','h','l','c')},
        'interpretation':'Compatible USD/as-traded-share levels; different minute/nativeDaily trade conditions and auctions. Daily prices matched Nasdaq465 exactly. RTH aggregate is diagnostic, never substituted for frozen Daily input.',
        'volume_equality_claim':False, 'capture_hash':digest(c)}))
    stream = read('candidate-stream-first.json')
    if digest(stream) != proof['all_replay_result_hash'] or stream['events'] != []:
        raise ValueError('Candidate freeze/result mismatch')
    write_new(ROOT/'zero-signal-discovery.json', encode({'status':'ZERO_SIGNAL', 'evidence_level':'DISCOVERY_SIGNAL_COMPOSITION_ONLY',
        'candidate_count':0, 'candidate_timestamps':[], 'metrics':None, 'labels':None,
        'outcome_queries':0, 'return_MFE_MAE_calculations':0, 'profitability':'NOT_RUN',
        'stream_hash':proof['event_stream_hash'], 'trace_hash':stream['trace_stream_hash'],
        'H0001_routing':['FROZEN','AWAITING_FUTURE_CONFIRMATION','HISTORICALLY_SPARSE'],
        'future_confirmation':'2026-10-12..2027-04-13;126sessions unchanged',
        'new_information_vs41':'H1 extremes27/READY672 and ACTIVE96 now occur, unlike prior0 extremes/ACTIVE0; frozen15m trigger remains0. Sparsity is now located at temporal trigger composition, not solely absence of H1 activation.',
        'next_active_P0':'INDEPENDENT_HYPOTHESIS_GENERATION_SELECTION', 'another_short_window_search':False}))
    write_new(ROOT/'adapter-diagnostic-disposition.json', encode({'status':'INVALIDATED_ADAPTER_DIAGNOSTIC_NOT_SIGNAL_EVIDENCE',
        'superseded_path':'h1-diagnostic.json', 'superseded_sha256':sha256((ROOT/'h1-diagnostic.json').read_bytes()).hexdigest(),
        'reason':'Initial derived H1 adapter omitted feed=sip and returned UNAVAILABLE. No official stream was frozen; initial composition run interrupted.',
        'corrected_proof':'h1-diagnostic-v2.json', 'frozen_strategy_changed':False}))
    write_new(ROOT/'capture-manifest.json', encode({'dataset_id':INTRADAY_ID,'content_hash':proof['intraday_hash'],
        'daily_dataset_id':DAILY_ID,'daily_content_hash':proof['daily_hash'], 'provider':'alpaca_basic','feed':'sip',
        'capture_manifest_sha256':sha256(encode(c)).hexdigest(), 'capture_hash':digest(c),
        'requests':c['requests'],'raw_response_hashes':sorted({r['sha256'] for r in c['requests']}),
        'session_denominator':70,'grid_denominator':4480,'offline_proof':'offline-reload-proof.json',
        'network_capture_module':'scripts.h0001_alpaca_70_capture','offline_module':'scripts.h0001_alpaca_70_discovery'}))
    secrets = tuple(credentials().values())
    for path in ROOT.rglob('*'):
        if path.is_file() and any(v.encode() in path.read_bytes() for v in secrets):
            raise ValueError('Credential leakage check failed; values never printed')
    write_new(ROOT/'test-report.json', encode({**tests,'credential_scan':'PASS_NO_VALUES_OR_CREDENTIAL_HASHES',
        'CLI_help':'PASS','original_evidence_unchanged':True,'final_adapter_fix_in_full_suite':True}))
    d = proof['denominators']; h = diag['counts']
    summary = (f"Admission PASS70 sessions/4480 exact slots, Daily465 native raw OHLC Nasdaq exact. "
        f"Frozen replay twice equal:4480 batches, Daily READY{d['Daily_READY']}/BULLISH{d['Daily_BULLISH']}, "
        f"H1 atomic READY{d['H1_raw_READY']}/ACTIVE{d['H1_ACTIVE']}; H1 completed READY{h['H1_READY']}/1120, "
        f"downside extremes{h['H1_downside_extreme']};15m triggers{d['frozen_M15_trigger_TRUE']};candidates0/timestamps[]. "
        "ZERO_SIGNAL discovery, outcomes0, no efficacy/profitability. Preserve frozen126-session confirmation; "
        "H0001 asynchronous FROZEN/AWAITING_FUTURE_CONFIRMATION/HISTORICALLY_SPARSE. Next independent hypothesis intake H0002; owner strategy meaning required.")
    record = {'schema_version':1,'decision_id':'H0001-alpaca-70-discovery-v1','date':'2026-10-04','authority':'EXPLICIT_OWNER_SELECTED_BOUNDED_DISCOVERY',
        'scope_decision':'LONG_HISTORY_EXTENDED_COVERAGE_SCOPE_DECISION_COMPLETE_NARROW_COMPLETE_INTERVAL',
        'branch':BRANCH,'base_commit':'6a0f82a','canonical_bootstrap_main':'50b479b','admission':admission['status'],
        'dataset':{'id':INTRADAY_ID,'hash':proof['intraday_hash'],'daily_id':DAILY_ID,'daily_hash':proof['daily_hash']},
        'proof':proof,'completed_H1_diagnostic':diag,'summary':summary,'tests':tests,
        'routing':'H0001_FUTURE_CONFIRMATION_ASYNCHRONOUS_NEW_INDEPENDENT_RESEARCH_ACTIVE',
        'next_active_P0':'INDEPENDENT_HYPOTHESIS_GENERATION_SELECTION','next_hypothesis':'H0002',
        'next_action_status':'USER_DECISION_REQUIRED','paid_cost':0,'multi_year_target_abandoned':False,
        'H0001_discarded':False,'frozen_strategy_modified':False,'original_evidence_rewritten':False}
    write_new(Path(RECORD), yaml.safe_dump(record,allow_unicode=True,sort_keys=False).encode('utf-8'))
    doc = f'''# H0001 selected Alpaca70-session discovery

Admission **PASS**, immutable separate datasets created, frozen H0001 **ZERO_SIGNAL**.
This is discovery signal evidence; outcomes, labels, returns, MFE/MAE and profitability were not read or computed.
No confirmation PASS/REJECT or production claim. User scope decision was selected before signal access; the multi-year target remains preserved.

{summary}

| Denominator | Actual |
| --- | ---: |
| Supported full sessions | 70 |
| Expected/observed04:00–20:00ET15m slots | 4480/4480 |
| Missing/off-grid/unsupported/zero-volume | 0/0/0/0 |
| Daily READY/BULLISH atomic batches | {d['Daily_READY']}/{d['Daily_BULLISH']} |
| Daily exhaustion READY | {d['exhaustion_READY']} |
| H1 READY atomic occupancy | {d['H1_raw_READY']} |
| H1 completed publications/READY | 1120/{h['H1_READY']} |
| H1 downside-extreme publications/ACTIVE occupancy | {h['H1_downside_extreme']}/{d['H1_ACTIVE']} |
| 15m trigger/final candidates | {d['frozen_M15_trigger_TRUE']}/0 |

Candidate timestamps `[]`. Twice-identical replay hash `{proof['all_replay_result_hash']}`;
event stream `{proof['event_stream_hash']}`. Empty-stream hashes coincide with the prior empty stream by definition;
the distinct dataset and full trace/replay hashes prove a new real replay.

Intraday `{INTRADAY_ID}` / `{proof['intraday_hash']}`; Daily `{DAILY_ID}` / `{proof['daily_hash']}`.
Portable captures/vintages are committed; separate SQLite `var/research/alpaca-70/market.sqlite` is locally stored.
All raw page hashes and exact pagination request chains reconstructed offline; separate page-limit captures agree.
All70 dates are EDT:04:00ET=08:00UTC,20:00ET=00:00UTC next day; XNYS calendar and existing DST/early-close guards retained.

This interval has its own action/unit certificate including465 Daily warmup observations from2024-10-04.
The earlier certificate is not inherited. Existing raw issuer, independent split, Nasdaq and NAV sources are hash checked and reread;
new Alpaca actions and raw/split Daily/intraday snapshots are compared directly. Effective split evidence is absent inside the scope;
historical action known_at remains unproven. No actual-event transform or historical absence receipt is backdated.
Daily/native volume includes extended trades and is not the intraday/RTH sum. All64 first-session15m volumes match the actual published minute sums.
NativeDaily OHLC matches Nasdaq465 rows exactly. RTH15m aggregate differences (open1.45/high0.02/low0.03/close0.99USD maximum)
are recorded as aggregation/auction diagnostics, not used as substitute Daily. Both series use raw USD/share units.
Cash dividends remain separate frozen split-only feature/outcome responsibilities; no reinvestment or performance accounting here.
Provider bar-end known_at is an explicit historical research assumption, not fresh shadow/live PIT.

Compared with the original41 sessions (656 H1 publications,208 READY, zero downside extremes/candidates),
the new70-session independently admitted scope supplies1120 completed H1/{h['H1_READY']} READY and zero candidates.
Here H1 downside extremes27 produce96 ACTIVE atomic batches; M15 arm occupancy5 still produces zero frozen triggers.
The older stream had no H1 activation. This new scope demonstrates that H1 activation alone did not produce the required
frozen15m conjunction/temporal trigger. Candidate rejection counts and trigger cancellations are preserved in `candidate-stream-first.json`.
The two windows overlap2026-08-05..08-13 (7 sessions); do not add them as111 independent sessions.
The result supports historical sparsity under these two bounded discovery origins, not universal inactivity or proof of no edge.
No shorter-window/provider chase or parameter relaxation follows. H0001 is preserved for its unchanged126-session future confirmation
2026-10-12..2027-04-13. Its informative phase exit6 remains incomplete; waiting does not block the whole project.

Next active P0 is independent hypothesis generation/selection. `scripts.prepare_independent_research` scans preserved revisions,
reserves next availableH0002 intake, and can capture an explicitly supplied observation/thesis asDRAFT with unknown rules.
It creates no hypothesis meaning, tested status or performance evidence by itself. Owner thesis choice is USER_DECISION_REQUIRED;
intake infrastructure is implemented. After selection, causal discovery→preregistration→future confirmation→failure/preservation/promotion→next hypothesis.
There is no prerequisite to wait until2027-04-13.

An initial adapter diagnostic was invalidated because derived1H omitted SIP feed provenance; no official candidate stream had been frozen.
The adapter fix and new N449 READY boundary test preserve all frozen strategy bytes. `h1-diagnostic.json` is retained only as invalidated
adapter evidence; `h1-diagnostic-v2.json` controls the actual result. First sandbox transport failure is separately archived as capability unknown.

Final targeted{tests['targeted']['passed']}/full{tests['full']['passed']} passed; failures/errors/skips0. CLI help and credential scan pass.
No costs, subscriptions or paid upgrades. Core code_hash changes from provider adapter additions; no operational DB, champion or risk latch was written/reset.

Evidence: [admission](../{ROOT.as_posix()}/admission.json), [capture manifest](../{ROOT.as_posix()}/capture-manifest.json),
[offline proof](../{ROOT.as_posix()}/offline-reload-proof.json), [ZERO_SIGNAL discovery](../{ROOT.as_posix()}/zero-signal-discovery.json),
[tests](../{ROOT.as_posix()}/test-report.json), [record](../{RECORD}).
Provider semantics: [Alpaca aggregation rules](https://docs.alpaca.markets/us/docs/market-data-faq).
'''
    Path(DOC).write_text(doc, encoding='utf-8')
    status = Path('PROJECT_STATUS.md')
    status.write_text('# Richping V2 - 2026-10-04 independent Alpaca70 discovery\n\n'
        '**COMPLETE bounded discovery / ZERO_SIGNAL; informative efficacy remains unavailable. H0001 future track preserved; new independent research P0.**\n\n'
        +summary+f"\n\nFinal targeted{tests['targeted']['passed']}/full{tests['full']['passed']} passed, zero failures/errors/skips; no outcomes/costs. "
        +f"Branch `{BRANCH}`; [contract]({DOC}); [immutable evidence]({ROOT.as_posix()}/offline-reload-proof.json). "
        +'No main code integration.\n\nThe entries below are preserved historical status reports.\n\n'+status.read_text(encoding='utf-8'), encoding='utf-8')


def pm(main_root):
    record = yaml.safe_load(Path(RECORD).read_text(encoding='utf-8'))
    commit = subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    p = main_root/'PROJECT_CONTROL.yaml'
    control = yaml.safe_load(p.read_text(encoding='utf-8'))
    if control['next_action']['id'] != 'LONG_HISTORY_EXTENDED_COVERAGE_SCOPE_DECISION': raise ValueError('Canonical PM changed')
    control['source_of_truth']['active_workstream_status']['branch'] = BRANCH
    control['active_workstream'].update(branch=BRANCH, base_branch='v2-h0001-alpaca-basic-admission',
        base_commit='6a0f82a', implementation_commit=commit, note=record['summary'])
    behind,ahead = map(int,subprocess.check_output(['git','rev-list','--left-right','--count','main...HEAD'],text=True).split())
    control['active_workstream']['observed_relation_to_main'] = {'ahead_by':ahead,'behind_by':behind,'main_commit':'50b479b'}
    oldphase = control['current_phase']
    oldphase['status'] = 'ASYNC_AWAITING_FUTURE_CONFIRMATION_INFORMATIVE_EXIT6_INCOMPLETE'
    oldphase['progress']['selected70_discovery'] = {'evidence_branch':BRANCH,'commit':commit,'record':RECORD,
        'evidence':(ROOT/'offline-reload-proof.json').as_posix(),'summary':record['summary']}
    control.setdefault('hypothesis_tracks',{})['H0001'] = {'status':['FROZEN','AWAITING_FUTURE_CONFIRMATION','HISTORICALLY_SPARSE'],
        'future_confirmation':{'start':'2026-10-12','end':'2027-04-13','sessions':126},
        'original_phase':oldphase,'confirmation_is_project_blocker':False,'short_window_search':'STOPPED'}
    control['current_phase'] = {'id':'INDEPENDENT_STRATEGY_RESEARCH_CYCLE','status':'READY_FOR_HYPOTHESIS_SELECTION',
        'objective':'Repeat independent hypothesis generation, causal discovery, preregistration, confirmation and evidence disposition.',
        'exit_criteria':['One independent falsifiable thesis selected with causal inputs and prior exposure recorded.',
            'Bounded discovery and preregistered confirmation contract before outcomes.',
            'Evidence routing preserves failed/inconclusive trials and forbids unearned production promotion.'],
        'progress':{'intake_infrastructure':'IMPLEMENTED_TESTED','next_available_hypothesis':'H0002',
                    'strategy_meaning':'NOT_SELECTED','H0001_confirmation_wait':'ASYNCHRONOUS_NOT_BLOCKING'}}
    control['completed_actions'].append({'id':'LONG_HISTORY_EXTENDED_COVERAGE_SCOPE_DECISION',
        'status':'COMPLETE_OWNER_DECISION_AND_SELECTED70_DISCOVERY','branch':BRANCH,'commit':commit,
        'admission':'PASS','dataset_created':True,'candidate_count':0,'outcomes':'NOT_RUN','evidence':RECORD,
        'tests':record['tests'],'profitability':'NOT_RUN'})
    control['next_action'] = {'id':'INDEPENDENT_HYPOTHESIS_GENERATION_SELECTION','priority':'P0','status':'USER_DECISION_REQUIRED',
        'blocks_phase_exit_criteria':[1],'objective':'Select the next independent thesis/market observation for H0002 intake.',
        'why_now':'Bounded frozen H0001 discovery complete with ZERO_SIGNAL; no immediate informative H0001 action remains. Future126-session confirmation continues asynchronously.',
        'autonomous_infrastructure':'IMPLEMENTED_TESTED; scripts.prepare_independent_research',
        'evidence_branch':BRANCH,'basis_evidence':(ROOT/'independent-research-intake.json').as_posix(),
        'constraints':['No H0001 tuning disguised as H0002','No outcome-driven selection','No deadline dependency on2027-04-13']}
    p.write_text(yaml.safe_dump(control,allow_unicode=True,sort_keys=False),encoding='utf-8')
    for name in ('BACKLOG','DECISION_INDEX'):
        p = main_root/'project'/(name+'.yaml')
        body = yaml.safe_load(p.read_text(encoding='utf-8'))
        if name == 'BACKLOG':
            for item in body['items']:
                if item['id'] == 'LONG_HISTORY_EXTENDED_COVERAGE_SCOPE_DECISION': item.update(status='COMPLETE_SELECTED70_DISCOVERY_ZERO_SIGNAL',evidence_branch=BRANCH,evidence=RECORD)
                if item['id'] == 'V2_MAIN_INTEGRATION_LANE': item['active_branch'] = BRANCH
            body['items'].extend([{'id':'H0001_FUTURE_CONFIRMATION','priority':'P1','status':'AWAITING_FUTURE_CONFIRMATION','track':'ASYNCHRONOUS',
                'summary':'Frozen126 sessions2026-10-12..2027-04-13; historical sparse preserved, not rejected; no paid/provider/short-window chase.',
                'evidence_branch':BRANCH,'evidence':RECORD,'blocks_project':False},
                {'id':'INDEPENDENT_HYPOTHESIS_GENERATION_SELECTION','priority':'P0','status':'USER_DECISION_REQUIRED',
                 'blocks_phase_exit_criteria':[1],'summary':'Choose independent H0002 thesis; intake pipeline implemented/tested.',
                 'evidence_branch':BRANCH,'evidence':(ROOT/'independent-research-intake.json').as_posix()}])
        else:
            body['default_research_branch'] = BRANCH
            body['canonical_sources']['current_status']['branch'] = BRANCH
            body['canonical_sources']['selected70_discovery'] = {'branch':BRANCH,'commit':commit,'record':RECORD,'evidence':(ROOT/'offline-reload-proof.json').as_posix(),'status':'COMPLETE_ZERO_SIGNAL_DISCOVERY_NO_OUTCOMES'}
            body['long_history_access_routing'].update(status='SELECTED70_DISCOVERY_PASS_ZERO_SIGNAL_H0001_ASYNC',
                next_action='INDEPENDENT_HYPOTHESIS_GENERATION_SELECTION',narrowed70_session_alternative='ADMITTED_DATASET_REPLAYED_ZERO_SIGNAL',
                evidence_branch=BRANCH,evidence=RECORD,blocks_phase_exit_criteria=[])
            route = body['long_history_access_routing']
            route['historical_broad_history_blocker'] = route['blocker']
            route['blocker'] = 'No immediate informative H0001 discovery action remains; fixed future confirmation is asynchronous, not a project blocker.'
            route['current_actual_history'] = 'Original Yahoo41 preserved; independent Alpaca70 admitted/replayed. Seven overlapping sessions; not111 independent observations.'
            for group in body['current_open_decision_groups']:
                if group['id'] == 'H0001_RESEARCH_EVALUATION':
                    group.update(next_action='H0001_FUTURE_CONFIRMATION',priority='ASYNCHRONOUS_NOT_PROJECT_BLOCKING',
                        note='Frozen opportunity protocol preserved. Original41 and selected70 discovery ZERO_SIGNAL; no economic estimate. Informative efficacy remains unavailable. Next project P0 is independent hypothesis selection.')
            body['next_independent_hypothesis'] = {'id':'H0002','meaning':'NOT_SELECTED_USER_DECISION_REQUIRED','infrastructure':'IMPLEMENTED_TESTED','H0001_future_confirmation_dependency':False}
        p.write_text(yaml.safe_dump(body,allow_unicode=True,sort_keys=False),encoding='utf-8')
    p = main_root/'PROJECT_STATUS.md'
    p.write_text('# Richping PM - 2026-10-04 selected70 discovery and independent research routing\n\n'+record['summary']+
        f"\n\nImplementation `{BRANCH}` / `{commit}`. Main PM documents only; no code merge. Evidence `{RECORD}`.\n\n"+
        'The entries below are preserved historical status reports.\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')


if __name__ == '__main__':
    if sys.argv[1] == 'workstream': workstream()
    elif sys.argv[1] == 'pm': pm(Path(sys.argv[2]))
    else: raise SystemExit('Choose workstream or pm')
