"""Update canonical main control only after successful H0003 evidence verification."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import subprocess
import yaml
from zoneinfo import ZoneInfo

from scripts.h0003_verify import verify_state
from scripts.h0003_frequency_audit import ROOT

MAIN = Path('var/pm-action-unit-main')
BRANCH = 'v2-h0003-relative-strength-frequency'
RECORD = 'research/decision_records/H0003-hypothesis-frequency-v1.yaml'
EVIDENCE = (ROOT/'frequency-audit.json').as_posix()


def update():
    verify_state()
    verification = json.loads((ROOT/'verification.json').read_bytes())
    if verification['outcome_access'] != 0 or any(verification['forbidden_call_counts'].values()):
        raise ValueError('Outcome-free evidence required')
    if any(t[k] for t in verification['tests'] for k in ('failures','errors','skipped')):
        raise ValueError('Passing full regression required')
    commit = subprocess.run(['git','rev-parse','HEAD'],check=True,capture_output=True,text=True).stdout.strip()
    if subprocess.run(['git','branch','--show-current'],check=True,capture_output=True,text=True).stdout.strip() != BRANCH:
        raise ValueError('Unexpected implementation branch')
    control_path,index_path = MAIN/'PROJECT_CONTROL.yaml',MAIN/'project/DECISION_INDEX.yaml'
    control = yaml.safe_load(control_path.read_text(encoding='utf-8'))
    index = yaml.safe_load(index_path.read_text(encoding='utf-8'))
    update_day = datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
    control['updated_at'] = index['updated_at'] = update_day
    if control['next_action']['id'] != 'INDEPENDENT_HYPOTHESIS_GENERATION_SELECTION':
        raise ValueError('Canonical action changed; reread bootstrap')
    frozen_tracks = deepcopy({k:control['hypothesis_tracks'][k] for k in ('H0001','H0002')})
    frozen_h0002 = deepcopy(index['canonical_sources']['H0002'])
    left,right = subprocess.run(['git','rev-list','--left-right','--count','origin/main...HEAD'],
        check=True,capture_output=True,text=True).stdout.split()
    main_commit = subprocess.run(['git','rev-parse','origin/main'],check=True,capture_output=True,text=True).stdout.strip()
    relation = dict(ahead_by=int(right),behind_by=int(left),main_commit=main_commit)
    control['source_of_truth']['active_workstream_status']['branch'] = BRANCH
    control['active_workstream'] = dict(branch=BRANCH,base_branch='v2-h0002-first-efficacy',
        base_commit='62992b202e37856a112ee45cc178a15dfd0c8899',implementation_commit=commit,
        status='DIVERGED_FROM_MAIN',observed_relation_to_main=relation,
        note='H0003 independent relative leadership causal frequency complete: 35 candidates/29 sessions; outcomes0. Signal provisional, final owner freeze pending; H0001/H0002 frozen async tracks unchanged.')
    phase = control['current_phase']
    phase['status'] = 'AWAITING_H0003_SIGNAL_FREEZE'
    phase['progress'].update(strategy_meaning='COMPLETE_OWNER_THESIS_SELECTION',
        next_available_hypothesis='H0004',
        causal_frequency='IMPLEMENTED_EXECUTED_REAL_DATA_EVIDENCE_PRODUCED',
        signal_freeze='USER_DECISION_REQUIRED',outcome_evaluation='NOT_RUN_H0003',
        efficacy_preregistration='NOT_STARTED_H0003',satisfied_exit_criteria=[1],remaining_exit_criteria=[2,3])
    control['completed_actions'].append(dict(id='INDEPENDENT_HYPOTHESIS_GENERATION_SELECTION',
        hypothesis='H0003-r01',status='COMPLETE_CAUSAL_FREQUENCY_ONLY',completed_at=update_day,
        branch=BRANCH,commit=commit,record=RECORD,evidence=EVIDENCE,
        benchmark_admission='research/data_evidence/h0003-qqq-admission-20261004/admission.json',
        verification=(ROOT/'verification.json').as_posix(),candidate_events=35,candidate_sessions=29,
        outcome_access=0,signal_frozen=False,tests=verification['tests']))
    control['next_action'] = dict(id='H0003_SIGNAL_FREEZE_PREREGISTRATION',priority='P0',
        status='USER_DECISION_REQUIRED',blocks_phase_exit_criteria=[2],hypothesis_id='H0003',
        objective='Approve final recent-session positive-persistent leadership/own-nonnegative guard/extended episode semantics, then preregister efficacy before outcomes.',
        why_now='QQQ admission and causal paired mechanics pass; 35 events/29 sessions without outcomes or tuning.',
        evidence_branch=BRANCH,basis_evidence=EVIDENCE,owner_decision='Approve the concrete provisional definition; owner changes create a new sealed revision.',
        constraints=['No H0003 outcomes before freeze and efficacy preregistration.',
                     'Preserve H0001/H0002 frozen evidence and asynchronous confirmation windows.',
                     'No automatic numeric threshold/window/benchmark/session relaxation.'])
    control['hypothesis_tracks']['H0003'] = dict(status=['THESIS_SELECTED','CAUSAL_FREQUENCY_COMPLETE','SIGNAL_PROVISIONAL'],
        family='RELATIVE_STRENGTH_LEADERSHIP_CONTINUATION',hypothesis='research/hypotheses/H0003-r01.yaml',
        branch=BRANCH,commit=commit,spec='research/strategy_specs/H0003-r01-candidate.yaml',record=RECORD,
        frequency_evidence=EVIDENCE,benchmark='QQQ',candidate_events=35,candidate_sessions=29,
        outcome_access=0,confirmation='NOT_PREREGISTERED',signal_freeze='USER_DECISION_REQUIRED')
    control['active_research_track'] = 'H0003'
    if 'next_independent_hypothesis' in control:
        control['next_independent_hypothesis'] = dict(id='H0004',meaning='NOT_SELECTED',
            routing='FUTURE_REGISTRY_ID_NOT_CURRENT_P0',H0001_future_confirmation_dependency=False,
            H0002_future_confirmation_dependency=False)
    index['default_research_branch'] = BRANCH
    index['canonical_sources']['current_status']['branch'] = BRANCH
    index['canonical_sources']['H0003'] = deepcopy(control['hypothesis_tracks']['H0003'])
    pending = index['current_open_decision_groups']
    for item in pending:
        if item['id'] == 'H0003_INDEPENDENT_HYPOTHESIS_SELECTION':
            item.update(status='RESOLVED_OWNER_THESIS_SELECTED',priority='COMPLETE',blocks_phase_exit_criteria=[],
                        evidence_branch=BRANCH,record=RECORD,note='Owner selected SOXX/QQQ relative leadership continuation; signal freeze separate.')
    pending.append(dict(id='H0003_SIGNAL_FREEZE_PREREGISTRATION',status='USER_DECISION_REQUIRED',priority='P0',
                        blocks_phase_exit_criteria=[2],evidence_branch=BRANCH,record=RECORD,evidence=EVIDENCE,
                        note='Concrete causal proposal/frequency complete; owner final signal meaning and freeze precede efficacy preregistration.'))
    index['next_independent_hypothesis'].update(id='H0004',meaning='NOT_SELECTED',
        routing='FUTURE_INTAKE_AFTER_H0003_DISPOSITION_NOT_CURRENT_P0')
    index['schema_revision'] = 'H0001/H0002 frozen tracks preserved. H0003 owner thesis and causal frequency complete; next P0 H0003 final signal freeze/preregistration. Registry next unused ID H0004 is not active P0.'
    if frozen_tracks != {k:control['hypothesis_tracks'][k] for k in ('H0001','H0002')} or frozen_h0002 != index['canonical_sources']['H0002']:
        raise ValueError('Frozen canonical tracks changed')
    for p,body in ((control_path,control),(index_path,index)):
        p.write_text(yaml.safe_dump(body,allow_unicode=True,sort_keys=False),encoding='utf-8')
    backlog_path = MAIN/'project/BACKLOG.yaml'
    backlog = yaml.safe_load(backlog_path.read_text(encoding='utf-8'))
    backlog['updated_at'] = update_day
    for item in backlog['items']:
        if item['id'] == 'V2_MAIN_INTEGRATION_LANE':
            item['active_branch'] = BRANCH
            item['observed_relation_to_main'] = relation
        if item['id'] == 'H0003_INDEPENDENT_HYPOTHESIS_INTAKE':
            item.update(priority='COMPLETE',status='COMPLETE_OWNER_THESIS_AND_CAUSAL_FREQUENCY',
                summary='SOXX/QQQ independent leadership thesis selected; causal frequency35/29 sessions, outcomes0.',
                strategy_meaning='OWNER_THESIS_SELECTED_SIGNAL_FREEZE_PENDING',blocks_phase_exit_criteria=[],
                routing='COMPLETE_NEXT_H0003_SIGNAL_FREEZE_PREREGISTRATION',evidence_branch=BRANCH,record=RECORD)
    backlog['items'].append(dict(id='H0003_SIGNAL_FREEZE_PREREGISTRATION',priority='P0',status='USER_DECISION_REQUIRED',
        blocks_phase_exit_criteria=[2],summary='Approve provisional signal semantics/final freeze, then preregister before any outcomes.',
        evidence_branch=BRANCH,record=RECORD))
    backlog['items'].append(dict(id='H0003_OPTIONAL_COMPARATORS',priority='DEFERRED',status='NOT_AUTHORIZED_NOT_RUN',
        summary='192-slot/percentile/SPY/RTH-only/context alternatives change meaning; no immediate grid or performance ranking.',
        evidence_branch=BRANCH,record=RECORD))
    backlog_path.write_text(yaml.safe_dump(backlog,allow_unicode=True,sort_keys=False),encoding='utf-8')
    ideas_path = MAIN/'project/USER_IDEAS.yaml'
    ideas = yaml.safe_load(ideas_path.read_text(encoding='utf-8'))
    ideas['updated_at'] = update_day
    ideas['items'].append(dict(id='USER-H0003-LEADERSHIP-001',status='THESIS_SELECTED_CAUSAL_FREQUENCY_COMPLETE',priority='CURRENT_H0003',
        idea='SOXX leadership versus QQQ may continue over a later short horizon; LONG-only independent continuation research.',
        family='RELATIVE_STRENGTH_LEADERSHIP_CONTINUATION',evidence_branch=BRANCH,record=RECORD))
    ideas_path.write_text(yaml.safe_dump(ideas,allow_unicode=True,sort_keys=False),encoding='utf-8')
    status = MAIN/'PROJECT_STATUS.md'
    prefix = ('# Richping PM - H0003 causal relative leadership frequency\n\n'
              f'Implementation `{BRANCH}` / `{commit}`; code not merged to main. '
              'SOXX versus QQQ, 64-slot trailing price-return difference, four positive observations, own nonnegative direction, one candidate per episode. '
              'QQQ SIP admission PASS 4480 exact slots/70 sessions; RS READY4416, leadership37, candidates35/29 sessions, mismatches0. '
              'Outcome access0; no efficacy, profitability or promotion. Final targeted/full regression passed; see branch verification evidence. '
              'H0001 frozen/sparse126-session and H0002 frozen252-session confirmations remain asynchronous and unchanged.\n\n'
              'NEXT_ACTION **H0003_SIGNAL_FREEZE_PREREGISTRATION / USER_DECISION_REQUIRED**. '
              'Approve concrete signal proposal, then preregister evaluation before outcomes. H0004 is merely the next unused registry ID.\n\n'
              'The entries below are preserved historical status reports.\n\n')
    status.write_text(prefix+status.read_text(encoding='utf-8'),encoding='utf-8')
    return {'implementation_commit':commit,'next_P0':control['next_action']['id']}


if __name__ == '__main__':
    print(json.dumps(update()))
