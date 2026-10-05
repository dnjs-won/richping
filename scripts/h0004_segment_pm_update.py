"""Route completed H0004 final signal/protocol on canonical main; preserve trials."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo
import yaml

from scripts.h0004_segment_frequency import ROOT as FREQUENCY,BASE,encode,write_new,fingerprint
from scripts.h0004_segment_verify import verify as verify_frequency
from scripts.h0004_signal_preregister import ROOT,FREEZE,SPEC,PROTOCOL,run

MAIN = Path('var/pm-action-unit-main')
BRANCH = 'v2-h0004-segment-freeze-preregistration'
DECISION = 'research/decision_records/H0004-segment-remediation-v2.yaml'
STATUS = 'docs/H0004_SEGMENT_FREQUENCY_RESULTS.md'


def update():
    frequency,registration = verify_frequency(tests=True),run()
    def git(*args):
        return subprocess.run(['git',*args],check=True,capture_output=True,text=True).stdout.strip()
    if git('branch','--show-current')!=BRANCH or git('status','--porcelain') or git('-C',str(MAIN),'status','--porcelain'):
        raise ValueError('Committed clean research branch and canonical main required')
    before_main = git('-C',str(MAIN),'rev-parse','HEAD')
    if before_main!=git('rev-parse','origin/main'): raise ValueError('Stale PM main; bootstrap again')
    commit = git('rev-parse','HEAD')
    paths = [MAIN/n for n in ('PROJECT_CONTROL.yaml','project/DECISION_INDEX.yaml','project/BACKLOG.yaml','project/USER_IDEAS.yaml')]
    control,index,backlog,ideas = [yaml.safe_load(p.read_text(encoding='utf-8')) for p in paths]
    if control['next_action']['id']!='H0004_SIGNAL_FREEZE_PREREGISTRATION': raise ValueError('Canonical P0 changed')
    prior_tracks = deepcopy({k:v for k,v in control['hypothesis_tracks'].items() if k!='H0004'})
    prior_sources = deepcopy({k:v for k,v in index['canonical_sources'].items()
                             if k not in ('H0004','active_hypothesis','current_status','last_frozen_candidate_spec')})
    prior_major = deepcopy(index['frozen_major_decisions'])
    old_track = deepcopy(control['hypothesis_tracks']['H0004'])
    before = {p.relative_to(MAIN).as_posix():fingerprint(p) for p in paths}
    day = datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
    for body in (control,index,backlog,ideas): body['updated_at']=day
    left,right = git('rev-list','--left-right','--count','origin/main...HEAD').split()
    relation = dict(ahead_by=int(right),behind_by=int(left),main_commit=before_main)
    control['source_of_truth']['active_workstream_status'].update(branch=BRANCH,path=STATUS)
    control['active_workstream']=dict(branch=BRANCH,base_branch='v2-h0004-compression-frequency',base_commit=BASE,
        implementation_commit=commit,status='DIVERGED_FROM_MAIN',observed_relation_to_main=relation,
        note='Owner corrected time-of-day reference; trial2 final signal frozen/preregistered,48/29, trials2/outcomes0. Prior tracks and trial1 immutable; next H0004 pre-access directional adapter.')
    phase = control['current_phase']
    phase['status']='H0004_FINAL_SIGNAL_FROZEN_PREREGISTERED_FIRST_EFFICACY_PENDING'
    phase['progress'].update(causal_frequency='TRIAL2_IMPLEMENTED_EXECUTED_REAL_EVIDENCE',
        signal_freeze='FROZEN_OWNER_APPROVED_SEGMENT_CONDITIONED',efficacy_preregistration='FROZEN_BEFORE_OUTCOMES',
        outcome_evaluation='NOT_RUN_H0004',satisfied_exit_criteria=[1,2],remaining_exit_criteria=[3])
    track = deepcopy(old_track)
    track.update(status=['FROZEN','PREREGISTERED','AWAITING_FIRST_DISCOVERY','AWAITING_FUTURE_CONFIRMATION'],
        branch=BRANCH,commit=commit,spec=SPEC.as_posix(),candidate_spec='research/strategy_specs/H0004-r01-candidate-segment-v2.yaml',
        record=FREEZE.as_posix(),remediation_record=DECISION,preregistration=PROTOCOL.as_posix(),
        frequency_evidence=(FREQUENCY/'frequency-audit.json').as_posix(),verification=(ROOT/'verification.json').as_posix(),
        selected_trial='TRIAL_2_SEGMENT_CONDITIONED_REFERENCE',signal_trials=2,parameter_trials=2,
        candidate_events=48,candidate_sessions=29,spec_hash=frequency['spec_hash'],candidate_stream_hash=frequency['event_stream_hash'],
        signal_freeze='FROZEN_OWNER_APPROVED',efficacy_preregistration='FROZEN_BEFORE_OUTCOMES',outcome_evaluation='NOT_RUN',
        protocol_hash=registration['protocol_hash'],signal_freeze_sha256=registration['signal_freeze_sha256'],
        spec_sha256=registration['signal_spec_sha256'],primary_horizon_slots=16,
        primary_estimand='Session-balanced SOXX gross16-slot directional price return; not timing Alpha/profitability',
        outcome_access=0,efficacy_calculations=0,profitability='NOT_ESTIMATED',confirmation_outcome_access=0,
        confirmation=dict(status='PENDING',start='2026-10-19',end='2027-10-19',sessions=252,
            followup_end='2027-10-20',receipt_deadline='2027-10-21T20:00:00-04:00',asynchronous=True),
        evaluation_adapter='METADATA_GATES_ONLY; NONEMPTY_LABEL_AND_TERMINAL_ADAPTER_NOT_IMPLEMENTED_NOT_EXECUTED',
        trial1=dict(identity='TRIAL_1_POOLED_SEGMENT_REFERENCE',immutable_prior_track=old_track,
                    candidate_events=39,candidate_sessions=26,outcome_access=0))
    control['hypothesis_tracks']['H0004']=track
    control['completed_actions'].append(dict(id='H0004_SEGMENT_REMEDIATION_SIGNAL_FREEZE_PREREGISTRATION',status='COMPLETE',
        completed_at=day,branch=BRANCH,commit=commit,record=DECISION,freeze=FREEZE.as_posix(),preregistration=PROTOCOL.as_posix(),
        frequency=(FREQUENCY/'frequency-audit.json').as_posix(),tests=frequency['tests'],
        signal_trials=2,candidate_events=48,candidate_sessions=29,outcome_access=0,prior_tracks_and_trial1_preserved=True,
        implementation_state='FINAL_SIGNAL_FROZEN_PROTOCOL_REGISTERED_EVIDENCE_PRODUCED_NOT_MAIN_CODE_INTEGRATED'))
    control['next_action']=dict(id='H0004_FIRST_EFFICACY',priority='P0',status='READY_FOR_PREACCESS_ADAPTER_IMPLEMENTATION_AND_SEAL',
        hypothesis_id='H0004',blocks_phase_exit_criteria=[3],evidence_branch=BRANCH,record=DECISION,
        objective='Implement, test and seal registered16-slot directional outcome adapter; only a later bounded exploratory action may execute discovery outcomes.',
        why_now='Owner semantic decision complete; causal trial2 nonzero and final signal/protocol frozen without outcomes.',
        constraints=['No third pre-outcome signal variant or post-outcome definition/threshold/window tuning.',
                    'Adapter binding/source/tests must be sealed before first outcome access.',
                    'Preserve trial1/H0001~3 and all immutable evidence; confirmations asynchronous.'])
    index['default_research_branch']=BRANCH
    index['canonical_sources']['current_status'].update(branch=BRANCH,path=STATUS)
    index['canonical_sources']['H0004']=deepcopy(track)
    index['canonical_sources']['active_hypothesis']=dict(id='H0004',status='FROZEN_PREREGISTERED_OUTCOMES_NOT_RUN',branch=BRANCH,path=track['hypothesis'])
    index['canonical_sources']['last_frozen_candidate_spec']=dict(branch=BRANCH,path=SPEC.as_posix(),status='FROZEN',sha256=registration['signal_spec_sha256'])
    for group in index['current_open_decision_groups']:
        if group['id']=='H0004_SIGNAL_FREEZE_PREREGISTRATION':
            group.update(priority='COMPLETE',status='RESOLVED_OWNER_CORRECTION_FROZEN_PREREGISTERED',blocks_phase_exit_criteria=[],
                         evidence_branch=BRANCH,record=DECISION,note='Same-segment prior10 completed sessions selected; final owner conditions passed; no further approval pending/outcomes0.')
    index['current_open_decision_groups'].append(dict(id='H0004_FIRST_EFFICACY',priority='P0',
        status='READY_FOR_PREACCESS_ADAPTER_IMPLEMENTATION_AND_SEAL',blocks_phase_exit_criteria=[3],
        evidence_branch=BRANCH,record=DECISION,note='Registered directional16-slot adapter must be tested/sealed before later exploratory outcomes.'))
    index['schema_revision']='H0004 final same-segment trial2 frozen/preregistered48/29; trials1+2 preserved/outcomes0. Owner decision complete; one P0 H0004_FIRST_EFFICACY pre-access adapter. Prior H0001~3 unchanged.'
    for item in backlog['items']:
        if item['id']=='V2_MAIN_INTEGRATION_LANE': item.update(active_branch=BRANCH,observed_relation_to_main=relation)
        if item['id']=='H0004_SIGNAL_FREEZE_PREREGISTRATION':
            item.update(priority='COMPLETE',status='COMPLETE_OWNER_SEGMENT_CORRECTION_FROZEN_PREREGISTERED',blocks_phase_exit_criteria=[],
                        evidence_branch=BRANCH,record=DECISION,summary='Trial2 same-segment prior10 sessions48/29; final signal/protocol frozen, outcome0.')
        if item['id']=='H0004_OPTIONAL_VARIANTS':
            item.update(status='DEFERRED_NO_THIRD_PRE_OUTCOME_VARIANT',
                        summary='Segment reference resolved by owner trial2. No further threshold/window/ATR/buffer/retest/RTH variant absent genuine blocker.')
    backlog['items'].append(dict(id='H0004_FIRST_EFFICACY',priority='P0',status='READY_FOR_PREACCESS_ADAPTER_IMPLEMENTATION_AND_SEAL',
        blocks_phase_exit_criteria=[3],evidence_branch=BRANCH,record=DECISION,
        summary='Implement/test/seal absolute directional16-slot outcome adapter before later discovery execution; confirmation remains PENDING.'))
    backlog['items'].append(dict(id='H0004_FUTURE_CONFIRMATION',priority='P1',status='ASYNC_PENDING_FIXED252_WINDOW',
        evidence_branch=BRANCH,record=PROTOCOL.as_posix(),outcome_access=0,project_blocker=False,
        summary='New interval-specific admission and eventual terminal adapter required; no interim outcomes/count extension.'))
    for item in ideas['items']:
        if item['id']=='USER-H0004-COMPRESSION-001':
            item.update(status='FROZEN_PREREGISTERED_OUTCOMES_NOT_RUN',evidence_branch=BRANCH,record=DECISION,
                        semantic_correction='Compare current segment against prior10 official completed sessions of same segment; current session excluded.')
    if any(control['hypothesis_tracks'][k]!=v for k,v in prior_tracks.items()) or index['frozen_major_decisions']!=prior_major:
        raise ValueError('Prior frozen tracks/decisions changed')
    if any(index['canonical_sources'][k]!=v for k,v in prior_sources.items()): raise ValueError('Prior canonical source changed')
    if [g['id'] for g in index['current_open_decision_groups'] if g['priority']=='P0']!=['H0004_FIRST_EFFICACY']:
        raise ValueError('Exactly one P0 required')
    for path,body in zip(paths,(control,index,backlog,ideas)):
        path.write_text(yaml.safe_dump(body,sort_keys=False,allow_unicode=True),encoding='utf-8')
    status = MAIN/'PROJECT_STATUS.md'
    prefix = (f'# Richping PM - H0004 final segment signal frozen/preregistered\n\n'
        f'Workstream `{BRANCH}` / `{commit}`, code not merged into main. '
        'Owner replaced pooled reference with exactly prior10 completed official sessions of current bar segment, current session excluded. '
        'SOXX normalized16-bar range,20%, strict completed close, frozen boundaries, one candidate, inclusive16-slot validity unchanged; cross-closure scheduled slots explicit. '
        'Trial2 READY3840, compressed925,101 ranges,48 candidates/29 sessions; segment rates24.62%/24.42%/22.81%, candidates19/20/9. '
        'Trial1 immutable39/26. Totaltrials2; no third variant. Final signal owner-approved/frozen; primary16-slot gross directional protocol registered, outcomes0/profitability NOT_ESTIMATED. '
        '252-session future confirmation2026-10-19..2027-10-19 remains async PENDING, no access. H0001~3 unchanged. '
        'Targeted/full pass; all646 prior files protected.\n\n'
        'NEXT_ACTION **H0004_FIRST_EFFICACY / READY_FOR_PREACCESS_ADAPTER_IMPLEMENTATION_AND_SEAL**. '
        'Test and seal directional adapter before later exploratory outcome action. Owner freeze decision complete.\n\n'
        'Entries below are historical reports.\n\n')
    status.write_text(prefix+status.read_text(encoding='utf-8'),encoding='utf-8')
    proof = dict(schema='h0004_segment_pm_update_proof_v1',canonical_main_before=before_main,research_commit=commit,
                 files_before=before,prior_H0001_H0002_H0003_tracks_preserved=True,trial1_retained_in_track_history=True,
                 prior_canonical_sources_and_frozen_decisions_preserved=True,owner_semantics_complete=True,
                 final_signal_frozen=True,preregistration_complete=True,active_P0='H0004_FIRST_EFFICACY',outcome_access=0)
    write_new(ROOT/'pm-update-proof.json',encode(proof))
    return proof


if __name__=='__main__':
    print(json.dumps(update(),indent=2))
