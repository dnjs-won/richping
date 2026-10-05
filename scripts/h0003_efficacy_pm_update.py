"""Preserve frozen tracks and route valid H0003 discovery to H0004 owner intake."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo
import yaml

from scripts.h0003_efficacy_verify import verify
from scripts.h0003_first_efficacy import ROOT,BASE
from scripts.h0002_frequency_audit import encode,fingerprint
from scripts.h0001_long_history_audit import write_new

MAIN = Path('var/pm-action-unit-main')
BRANCH = 'v2-h0003-first-efficacy'
RECORD = Path('research/decision_records/H0003-first-efficacy-v1.yaml')


def result_record():
    checked = verify()
    report = json.loads((ROOT/'discovery-report.json').read_bytes())
    record = dict(schema='h0003_first_exploratory_disposition_v1',hypothesis='H0003-r01',
        status='FROZEN_EXPLORATORY_DISCOVERY_EVALUATED_AWAITING_FUTURE_CONFIRMATION',
        disposition=report['disposition'],evidence=(ROOT/'discovery-report.json').as_posix(),
        report_hash=checked['report_hash'],protocol_hash=checked['protocol_hash'],
        signal_freeze_hash=checked['signal_freeze_hash'],event_stream_hash=checked['event_stream_hash'],
        candidate_events=35,candidate_sessions=29,primary_horizon=16,
        primary_estimand='Session-balanced SOXX forward raw price return minus paired QQQ return',
        metrics=report['metrics'],uncertainty_status=report['uncertainty_status'],
        discovery_outcome_access='AUTHORIZED_EXECUTED_SEALED70_ONLY',
        actual_executions=checked['actual_executions'],access_counts=checked['actual_access_counts'],
        confirmation_outcome_access=0,confirmation_status='PENDING_ASYNCHRONOUS',
        profitability='NOT_ESTIMATED',signal_semantics_changed=False,
        no_confirmation_PASS_REJECT_alpha_or_promotion=True,
        H0001_H0002_and_prior_H0003_source_evidence_preserved=True,
        next_P0='INDEPENDENT_HYPOTHESIS_GENERATION_SELECTION',next_hypothesis='H0004',
        interpretation='Primary relative point mean positive, median negative; mean SOXX and QQQ absolute price returns negative. No CI or inferential conclusion.64-slot subset descriptive only.')
    write_new(RECORD,yaml.safe_dump(record,sort_keys=False,allow_unicode=True).encode())
    return checked,report


def update():
    checked,report = result_record()
    def git(*args):
        return subprocess.run(['git',*args],check=True,capture_output=True,text=True).stdout.strip()
    if git('branch','--show-current')!=BRANCH or git('-C',str(MAIN),'status','--porcelain'):
        raise ValueError('Expected research branch and clean main PM worktree')
    if git('-C',str(MAIN),'rev-parse','HEAD')!=git('rev-parse','origin/main'):
        raise ValueError('Canonical main not current remote main; reread bootstrap')
    commit = git('rev-parse','HEAD')
    names = ('PROJECT_CONTROL.yaml','project/DECISION_INDEX.yaml','project/BACKLOG.yaml','project/USER_IDEAS.yaml')
    paths = [MAIN/n for n in names]
    control,index,backlog,ideas = [yaml.safe_load(p.read_text(encoding='utf-8')) for p in paths]
    if control['next_action']['id']!='H0003_FIRST_EFFICACY':
        raise ValueError('Canonical action changed')
    frozen_tracks = deepcopy({k:control['hypothesis_tracks'][k] for k in ('H0001','H0002')})
    frozen_major = deepcopy(index['frozen_major_decisions'])
    frozen_sources = deepcopy({k:v for k,v in index['canonical_sources'].items() if k not in ('H0003','active_hypothesis','current_status')})
    frozen_groups = deepcopy([g for g in index['current_open_decision_groups'] if not g['id'].startswith(('H0003','H0004'))])
    day = datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
    for body in (control,index,backlog,ideas): body['updated_at']=day
    left,right = git('rev-list','--left-right','--count','origin/main...HEAD').split()
    relation = dict(ahead_by=int(right),behind_by=int(left),main_commit=git('rev-parse','origin/main'))
    control['source_of_truth']['active_workstream_status']['branch']=BRANCH
    control['active_workstream']=dict(branch=BRANCH,base_branch='v2-h0003-signal-freeze-preregistration',
        base_commit=BASE,implementation_commit=commit,status='DIVERGED_FROM_MAIN',observed_relation_to_main=relation,
        note='H0003 paired first discovery executed and valid exploratory disposition recorded; frozen definitions unchanged. H0004 owner thesis intake is active P0; all confirmations asynchronous.')
    old_phase = deepcopy(control['current_phase'])
    old_phase['status']='COMPLETE_VALID_H0003_DISCOVERY_DISPOSITION_CONFIRMATION_ASYNC_PENDING'
    old_phase['progress'].update(outcome_evaluation='IMPLEMENTED_EXECUTED_DISCOVERY_EVIDENCE_PRODUCED',
        H0003_discovery_disposition=report['disposition'],satisfied_exit_criteria=[1,2,3],remaining_exit_criteria=[])
    control.setdefault('research_cycle_history',[]).append(dict(hypothesis='H0003',
        status='COMPLETE_VALID_DISCOVERY_DISPOSITION_CONFIRMATION_ASYNC_PENDING',
        satisfied_exit_criteria=[1,2,3],record=RECORD.as_posix(),branch=BRANCH,commit=commit,
        disposition=report['disposition'],confirmation_is_project_blocker=False,phase=old_phase))
    phase = control['current_phase']
    phase['status']='AWAITING_H0004_OWNER_THESIS_SELECTION'
    phase['progress']=dict(intake_infrastructure='IMPLEMENTED_TESTED',next_available_hypothesis='H0004',
        active_hypothesis='H0004',strategy_meaning='USER_DECISION_REQUIRED',causal_frequency='NOT_STARTED_H0004',
        signal_freeze='NOT_STARTED_H0004',efficacy_preregistration='NOT_STARTED_H0004',outcome_evaluation='NOT_RUN_H0004',
        H0001_confirmation_wait='ASYNCHRONOUS_NOT_BLOCKING',H0002_confirmation_wait='ASYNCHRONOUS_NOT_BLOCKING',
        H0003_confirmation_wait='ASYNCHRONOUS_NOT_BLOCKING',H0003_discovery_disposition=report['disposition'],
        satisfied_exit_criteria=[],remaining_exit_criteria=[1,2,3])
    control['completed_actions'].append(dict(id='H0003_FIRST_EFFICACY',status='COMPLETE_VALID_EXPLORATORY_DISCOVERY',
        completed_at=day,branch=BRANCH,commit=commit,record=RECORD.as_posix(),evidence=(ROOT/'discovery-report.json').as_posix(),
        verification=(ROOT/'verification.json').as_posix(),report_hash=checked['report_hash'],tests=checked['tests'],
        disposition=report['disposition'],candidate_events=35,candidate_sessions=29,confirmation_outcome_access=0,
        frozen_contracts_changed=False,profitability='NOT_ESTIMATED',
        acceptance_criteria=dict(pre_access_binding_validated=True,adapter_sealed_and_tested_before_outcomes=True,
            all35_candidates_retained=True,paired_scheduled_paths=True,no_discovery_inference=True,
            deterministic_repeated_real_execution=True,prior_tracks_preserved=True,confirmation_access_zero=True)))
    control['next_action']=dict(id='INDEPENDENT_HYPOTHESIS_GENERATION_SELECTION',priority='P0',status='USER_DECISION_REQUIRED',
        hypothesis_id='H0004',blocks_phase_exit_criteria=[1],evidence_branch=BRANCH,record=RECORD.as_posix(),
        objective='Select a new independent falsifiable market mechanism for H0004 before feature/signal work or outcomes.',
        why_now='H0003 valid discovery disposition recorded regardless of sign; future confirmations are asynchronous.',
        owner_decision='Choose H0004 thesis, universe and intended market mechanism; implementation follows only after thesis selection.',
        constraints=['Do not reopen frozen H0001/H0002/H0003 or tune them from discovery outcomes.',
            'No dependence on confirmation wait; preserve each protocol/window/stopping identity.',
            'Any H0003 improvement is a separate authorized revision/trial, never a v1 rewrite.'])
    h3 = control['hypothesis_tracks']['H0003']
    h3.update(status=['FROZEN','PREREGISTERED','EXPLORATORY_DISCOVERY_EVALUATED','AWAITING_FUTURE_CONFIRMATION'],
        freeze_branch=h3['branch'],freeze_commit=h3['commit'],branch=BRANCH,commit=commit,
        efficacy_record=RECORD.as_posix(),efficacy_evidence=(ROOT/'discovery-report.json').as_posix(),
        discovery_disposition=report['disposition'],discovery_metrics=report['metrics'],
        outcome_access='DISCOVERY_ONLY_AUTHORIZED_EXECUTED; CONFIRMATION0',
        evaluation_adapter='IMPLEMENTED_EXECUTED_DISCOVERY; NO_DISCOVERY_CI; FUTURE_PAIRED_ADMISSION_AND_TERMINAL_ADAPTER_SEPARATE',
        efficacy_calculations='DISCOVERY_DESCRIPTIVE_ONLY',confirmation_outcome_access=0,profitability_calculations=0,
        report_hash=checked['report_hash'])
    control['active_research_track']='H0004'
    control['next_independent_hypothesis']=dict(id='H0004',meaning='NOT_SELECTED',routing='CURRENT_P0_OWNER_THESIS_SELECTION',
        H0001_future_confirmation_dependency=False,H0002_future_confirmation_dependency=False,H0003_future_confirmation_dependency=False)
    index['default_research_branch']=BRANCH
    index['canonical_sources']['current_status']['branch']=BRANCH
    index['canonical_sources']['H0003']=deepcopy(h3)
    index['canonical_sources']['active_hypothesis']=dict(id='H0004',status='NOT_SELECTED_USER_DECISION_REQUIRED',branch=BRANCH,path=None)
    for group in index['current_open_decision_groups']:
        if group['id']=='H0003_FIRST_EFFICACY':
            group.update(status='RESOLVED_VALID_EXPLORATORY_DISCOVERY',priority='COMPLETE',blocks_phase_exit_criteria=[],
                record=RECORD.as_posix(),evidence=(ROOT/'discovery-report.json').as_posix(),evidence_branch=BRANCH,
                note='35 primary16 labels complete; positive relative mean with negative absolute SOXX/QQQ means. Descriptive only; confirmation PENDING/access0.')
    index['current_open_decision_groups'].append(dict(id='H0004_INDEPENDENT_HYPOTHESIS_SELECTION',priority='P0',
        status='USER_DECISION_REQUIRED',blocks_phase_exit_criteria=[1],evidence_branch=BRANCH,
        note='Owner chooses independent next market mechanism; all prior frozen hypotheses retain asynchronous confirmation.'))
    index['next_independent_hypothesis'].update(control['next_independent_hypothesis'])
    index['active_research_track']='H0004'
    index['schema_revision']='H0003 first paired exploratory efficacy valid; definitions/35-event stream unchanged, confirmation0. Active P0 independent H0004 owner thesis selection; H0001/H0002/H0003 confirmations asynchronous.'
    for item in backlog['items']:
        if item['id']=='V2_MAIN_INTEGRATION_LANE': item.update(active_branch=BRANCH,observed_relation_to_main=relation)
        if item['id']=='H0003_FIRST_EFFICACY':
            item.update(priority='COMPLETE',status='COMPLETE_VALID_EXPLORATORY_DISCOVERY',blocks_phase_exit_criteria=[],
                record=RECORD.as_posix(),evidence_branch=BRANCH,
                summary='35/35 primary complete; registered relative point mean positive but absolute SOXX/QQQ means negative. No inferential claims; next independent H0004.')
        if item['id']=='H0003_FUTURE_CONFIRMATION':
            item.update(evidence_branch=BRANCH,confirmation_outcome_access=0,
                infrastructure='METADATA_READINESS_GUARD_ONLY; FUTURE_PAIRED_ADMISSION_AND_TERMINAL_ADAPTER_NOT_IMPLEMENTED')
    backlog['items'].append(dict(id='H0004_INDEPENDENT_HYPOTHESIS_INTAKE',priority='P0',status='USER_DECISION_REQUIRED',
        blocks_phase_exit_criteria=[1],evidence_branch=BRANCH,
        summary='Select independent H0004 thesis without revising prior frozen trials or waiting for confirmations.'))
    for item in ideas['items']:
        if item['id']=='USER-H0003-LEADERSHIP-001':
            item.update(status='FROZEN_EXPLORATORY_DISCOVERY_EVALUATED_CONFIRMATION_ASYNC_PENDING',
                efficacy_record=RECORD.as_posix(),disposition=report['disposition'],evidence_branch=BRANCH)
    if frozen_tracks!={k:control['hypothesis_tracks'][k] for k in ('H0001','H0002')} or frozen_major!=index['frozen_major_decisions']:
        raise ValueError('Frozen prior hypothesis tracks/major decisions changed')
    if any(index['canonical_sources'][k]!=v for k,v in frozen_sources.items()) or frozen_groups!=[
            g for g in index['current_open_decision_groups'] if not g['id'].startswith(('H0003','H0004'))]:
        raise ValueError('Prior canonical sources/decision groups changed')
    if len([g for g in index['current_open_decision_groups'] if g['priority']=='P0'])!=1:
        raise ValueError('Exactly one active P0 required')
    for path,body in zip(paths,(control,index,backlog,ideas)):
        path.write_text(yaml.safe_dump(body,allow_unicode=True,sort_keys=False),encoding='utf-8')
    status = MAIN/'PROJECT_STATUS.md'
    prefix = (f'# Richping PM - H0003 exploratory outcomes complete; H0004 intake\n\n'
        f'Implementation `{BRANCH}` / `{commit}`; code not merged into main. Frozen H0003 contracts unchanged. '
        '35/35 primary16-slot labels complete,29 sessions; session-balanced SOXX minus QQQ +0.011824%p, median -0.005942%p, positive17/35. '
        'SOXX mean -0.096169%, QQQ -0.107993%; relative outperformance does not validate LONG profit. '
        '4-slot excess +0.012245%p (35 complete);64-slot resolved subset +0.579305%p (34 complete/1 outside-scope unresolved), full64 mean unknown. '
        'DISCOVERY_POSITIVE_RELATIVE_DIRECTION is a point description only; no CI, PASS/REJECT, alpha proof or promotion. '
        'H0003 confirmation252 sessions2026-10-19..2027-10-19 remains PENDING/asynchronous, outcome access0; profitability NOT_ESTIMATED. '
        'Two real executions identical; targeted178/full1687 pass, prior586 files preserved. H0001/H0002 frozen evidence/state unchanged.\n\n'
        'NEXT_ACTION **INDEPENDENT_HYPOTHESIS_GENERATION_SELECTION / H0004 / USER_DECISION_REQUIRED**. '
        'Owner selects next independent market mechanism; confirmation waits do not block research. '
        'Future H0003 paired capture/admission/unit-segment/terminal inference adapters remain separate future work.\n\n'
        'Entries below are preserved historical reports.\n\n')
    status.write_text(prefix+status.read_text(encoding='utf-8'),encoding='utf-8')
    return dict(implementation_commit=commit,next_P0=control['next_action']['id'],hypothesis='H0004')


if __name__=='__main__':
    print(json.dumps(update()))
