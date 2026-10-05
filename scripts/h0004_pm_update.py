"""Publish H0004 frequency routing on canonical PM main, preserving prior tracks."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo
import yaml
from scripts.h0004_verify import verify
from scripts.h0004_frequency_audit import ROOT, BASE, encode, write_new, fingerprint

MAIN = Path('var/pm-action-unit-main')
BRANCH = 'v2-h0004-compression-frequency'
RECORD = 'research/decision_records/H0004-hypothesis-frequency-v1.yaml'
EVIDENCE = (ROOT/'frequency-audit.json').as_posix()
P0 = 'H0004_SIGNAL_FREEZE_PREREGISTRATION'


def update():
    checked = verify()
    def git(*args):
        return subprocess.run(['git',*args],check=True,capture_output=True,text=True).stdout.strip()
    if git('branch','--show-current') != BRANCH or git('-C',str(MAIN),'status','--porcelain'):
        raise ValueError('Expected research branch and clean canonical PM main')
    canonical = git('-C',str(MAIN),'rev-parse','HEAD')
    if canonical != git('rev-parse','origin/main'):
        raise ValueError('Canonical main is stale; bootstrap again')
    commit = git('rev-parse','HEAD')
    if commit == BASE or git('status','--porcelain'):
        raise ValueError('Commit verified research deliverables first')
    names = ('PROJECT_CONTROL.yaml','project/DECISION_INDEX.yaml','project/BACKLOG.yaml','project/USER_IDEAS.yaml')
    paths = [MAIN/n for n in names]
    control,index,backlog,ideas = [yaml.safe_load(p.read_text(encoding='utf-8')) for p in paths]
    before = {p.relative_to(MAIN).as_posix():fingerprint(p) for p in paths}
    if control['next_action']['id']!='INDEPENDENT_HYPOTHESIS_GENERATION_SELECTION' or control['active_research_track']!='H0004':
        raise ValueError('Canonical action changed')
    tracks = deepcopy(control['hypothesis_tracks'])
    major = deepcopy(index['frozen_major_decisions'])
    prior_sources = deepcopy({k:v for k,v in index['canonical_sources'].items()
                             if k not in ('active_hypothesis','current_status')})
    day = datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
    for body in (control,index,backlog,ideas): body['updated_at']=day
    left,right = git('rev-list','--left-right','--count','origin/main...HEAD').split()
    relation = dict(ahead_by=int(right),behind_by=int(left),main_commit=canonical)
    track = dict(status=['THESIS_SELECTED','PROVISIONAL_SIGNAL','FREQUENCY_EXECUTED','OWNER_FREEZE_PENDING'],
                 family='VOLATILITY_COMPRESSION_BREAKOUT_CONTINUATION',direction='LONG',branch=BRANCH,commit=commit,
                 hypothesis='research/hypotheses/H0004-r01.yaml',spec='research/strategy_specs/H0004-r01-candidate.yaml',
                 record=RECORD,frequency_evidence=EVIDENCE,verification=(ROOT/'verification.json').as_posix(),
                 candidate_events=39,candidate_sessions=26,parameter_trials=1,comparators=0,outcome_access=0,
                 spec_hash=checked['spec_hash'],candidate_stream_hash=checked['candidate_stream_hash'],
                 signal_freeze='USER_DECISION_REQUIRED',efficacy_preregistration='NOT_STARTED',
                 outcome_evaluation='NOT_RUN',confirmation_is_project_blocker=False)
    control['source_of_truth']['active_workstream_status'].update(branch=BRANCH,path='docs/H0004_FREQUENCY_RESULTS.md')
    control['active_workstream']=dict(branch=BRANCH,base_branch='v2-h0003-first-efficacy',base_commit=BASE,
                                    implementation_commit=commit,status='DIVERGED_FROM_MAIN',observed_relation_to_main=relation,
                                    note='H0004 pure compression frequency39/26, outcome0. Owner final freeze/preregistration pending; prior frozen tracks unchanged.')
    phase = control['current_phase']
    phase['status']='H0004_CAUSAL_FREQUENCY_COMPLETE_OWNER_FREEZE_REQUIRED'
    phase['progress'].update(strategy_meaning='COMPLETE_OWNER_THESIS_SELECTION',
                            next_available_hypothesis='H0005',
                            causal_frequency='IMPLEMENTED_EXECUTED_REAL_DATA_EVIDENCE_PRODUCED',
                            signal_freeze='USER_DECISION_REQUIRED',efficacy_preregistration='NOT_STARTED',
                            outcome_evaluation='NOT_RUN_H0004',satisfied_exit_criteria=[1],remaining_exit_criteria=[2,3])
    control['completed_actions'].append(dict(id='H0004_HYPOTHESIS_CAUSAL_FREQUENCY',status='COMPLETE',completed_at=day,
        branch=BRANCH,commit=commit,record=RECORD,evidence=EVIDENCE,verification=track['verification'],
        tests=checked['tests'],candidate_events=39,candidate_sessions=26,parameter_trials=1,outcome_access=0,
        implementation_state='IMPLEMENTED_EXECUTED_REAL_DATA_EVIDENCE_PRODUCED_NOT_MAIN_INTEGRATED',
        acceptance_criteria=dict(causal_definition=True,immutable_input_reused=True,episodes_deduplicated=True,
            repeat_prefix_equal=True,outcomes_zero=True,prior_evidence_unchanged=True,targeted_full_pass=True)))
    control['next_action']=dict(id=P0,priority='P0',status='USER_DECISION_REQUIRED',hypothesis_id='H0004',
        blocks_phase_exit_criteria=[2],evidence_branch=BRANCH,record=RECORD,evidence=EVIDENCE,
        objective='Owner approves final compression/breakout/episode/session semantics; then preregister evaluation before outcomes.',
        owner_decision='Approve range/own-history percentile16/640/20%, window-only persistence, frozen boundaries, strict close, rearm, inclusive16-slot expiry, downside cancellation and pooled extended cross-session semantics.',
        constraints=['No H0004 outcomes before final freeze and efficacy preregistration.',
                     'No changes to prior frozen tracks/evidence or outcome-based threshold tuning.'])
    control['hypothesis_tracks']['H0004']=track
    future = dict(id='H0005',meaning='NOT_SELECTED',routing='FUTURE_UNUSED_REGISTRY_ID_NOT_CURRENT_P0',
                  H0001_future_confirmation_dependency=False,H0002_future_confirmation_dependency=False,
                  H0003_future_confirmation_dependency=False)
    control['next_independent_hypothesis']=future
    index['default_research_branch']=BRANCH
    index['canonical_sources']['current_status'].update(branch=BRANCH,path='docs/H0004_FREQUENCY_RESULTS.md')
    index['canonical_sources']['H0004']=deepcopy(track)
    index['canonical_sources']['active_hypothesis']=dict(id='H0004',status='PROVISIONAL_OWNER_FREEZE_PENDING',branch=BRANCH,
                                                       path=track['hypothesis'])
    for group in index['current_open_decision_groups']:
        if group['id']=='H0004_INDEPENDENT_HYPOTHESIS_SELECTION':
            group.update(priority='COMPLETE',status='RESOLVED_OWNER_THESIS_AND_FREQUENCY',blocks_phase_exit_criteria=[],
                         evidence_branch=BRANCH,record=RECORD,evidence=EVIDENCE)
    index['current_open_decision_groups'].append(dict(id=P0,priority='P0',status='USER_DECISION_REQUIRED',
        blocks_phase_exit_criteria=[2],evidence_branch=BRANCH,record=RECORD,evidence=EVIDENCE,
        note='Executable39/26 frequency only; owner final semantics/freeze before outcome preregistration.'))
    index['next_independent_hypothesis']=deepcopy(future)
    index['schema_revision']='H0004 owner thesis selected; single provisional pure compression tuple executable39/26 with outcomes0. Prior H0001~3 unchanged; one P0 H0004 final signal freeze/preregistration.'
    for item in backlog['items']:
        if item['id']=='V2_MAIN_INTEGRATION_LANE': item.update(active_branch=BRANCH,observed_relation_to_main=relation)
        if item['id']=='H0004_INDEPENDENT_HYPOTHESIS_INTAKE':
            item.update(priority='COMPLETE',status='COMPLETE_OWNER_THESIS_AND_CAUSAL_FREQUENCY',blocks_phase_exit_criteria=[],
                        evidence_branch=BRANCH,record=RECORD,summary='Pure compression/breakout,39 candidates/26 sessions, outcomes0.')
    backlog['items'].append(dict(id=P0,priority='P0',status='USER_DECISION_REQUIRED',blocks_phase_exit_criteria=[2],
                                evidence_branch=BRANCH,record=RECORD,summary='Approve complete provisional tuple and episode/session semantics; then preregister without outcomes.'))
    backlog['items'].append(dict(id='H0004_OPTIONAL_VARIANTS',priority='DEFERRED',status='NOT_AUTHORIZED_NOT_RUN',
        summary='ATR, segment conditioning, buffer/retest, RTH, extra persistence or thresholds require separate semantic revision; no grid.'))
    ideas['items'].append(dict(id='USER-H0004-COMPRESSION-001',status='THESIS_SELECTED_FREQUENCY_COMPLETE_FREEZE_PENDING',
                              family=track['family'],idea='Quiet own-history normalized SOXX range followed by upside completed-close breakout may continue upward.',
                              evidence_branch=BRANCH,record=RECORD))
    if any(control['hypothesis_tracks'][k]!=v for k,v in tracks.items()) or index['frozen_major_decisions']!=major:
        raise ValueError('Prior frozen tracks/decisions changed')
    if any(index['canonical_sources'][k]!=v for k,v in prior_sources.items()):
        raise ValueError('Prior canonical evidence sources changed')
    if len([g for g in index['current_open_decision_groups'] if g['priority']=='P0'])!=1:
        raise ValueError('Exactly one active P0 required')
    for path,body in zip(paths,(control,index,backlog,ideas)):
        path.write_text(yaml.safe_dump(body,sort_keys=False,allow_unicode=True),encoding='utf-8')
    status = MAIN/'PROJECT_STATUS.md'
    prefix = (f'# Richping PM - H0004 compression frequency; owner freeze pending\n\n'
              f'Workstream `{BRANCH}` / `{commit}`, not code-merged into main. '
              'OHLC/time-only SOXX16-bar normalized range, previous640 bottom20%, frozen range, strict upside close, next16 slots inclusive. '
              'Admitted sealed70 reused:4480 eligible,3825 READY,875 compressed,83 ranges,39 candidates/26 sessions. '
              '39 consumed+33 downside-cancelled+10 expired+1 pending. Trials1/comparators0/outcomes0. '
              'Targeted/full regression passed; initial preservation fixture overwrite restored and corrected Git-BASE seal supersedes initial audit claim; all prior598 files preserved. '
              'H0001~3 frozen and asynchronous confirmations unchanged.\n\n'
              f'NEXT_ACTION **{P0} / USER_DECISION_REQUIRED**. '
              'Approve full provisional semantics then preregister efficacy before any outcome.\n\n'
              'Entries below are historical reports.\n\n')
    status.write_text(prefix+status.read_text(encoding='utf-8'),encoding='utf-8')
    proof = dict(schema='h0004_pm_update_proof_v1',canonical_main_before=canonical,research_commit=commit,
                 files_before=before,prior_tracks_preserved=True,prior_canonical_evidence_preserved=True,
                 prior_major_decisions_preserved=True,active_P0=P0,owner_freeze_pending=True,outcome_access=0)
    write_new(ROOT/'pm-update-proof.json',encode(proof))
    return proof


if __name__=='__main__':
    print(json.dumps(update(),indent=2))
