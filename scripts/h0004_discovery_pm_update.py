"""Route valid exploratory execution to H0005 without changing frozen decisions."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo
import yaml

from scripts.h0004_discovery_execution import ROOT,ACTION,git,verify_results
from scripts.h0004_frequency_audit import encode,write_new,fingerprint

MAIN=Path('var/pm-action-unit-main')
BRANCH='v2-h0004-discovery-efficacy'
NEXT='INDEPENDENT_HYPOTHESIS_GENERATION_SELECTION'
STATUS='docs/H0004_DISCOVERY_RESULTS.md'
RECORD='research/decision_records/H0004-discovery-efficacy-v1.yaml'


def update():
    receipt=verify_results(tests=True)
    if git('branch','--show-current').decode().strip()!=BRANCH or git('status','--porcelain') or git('-C',str(MAIN),'status','--porcelain'):
        raise ValueError('Clean committed research and canonical main required')
    before_main=git('-C',str(MAIN),'rev-parse','HEAD').decode().strip()
    if before_main!=git('rev-parse','origin/main').decode().strip():
        raise ValueError('Canonical main advanced; bootstrap required')
    commit=git('rev-parse','HEAD').decode().strip()
    paths=[MAIN/n for n in ('PROJECT_CONTROL.yaml','project/DECISION_INDEX.yaml','project/BACKLOG.yaml','project/USER_IDEAS.yaml')]
    bodies=[yaml.safe_load(p.read_text(encoding='utf-8')) for p in paths]
    control,index,backlog,ideas=bodies
    if control['next_action']['id']!=ACTION: raise ValueError('Canonical next action changed')
    prior_tracks=deepcopy({h:v for h,v in control['hypothesis_tracks'].items() if h!='H0004'})
    prior_frozen=deepcopy(index['frozen_major_decisions'])
    prior_sources=deepcopy({k:v for k,v in index['canonical_sources'].items() if k not in ('H0004','active_hypothesis','current_status')})
    old_h4=deepcopy(control['hypothesis_tracks']['H0004'])
    before={p.relative_to(MAIN).as_posix():fingerprint(p) for p in paths}
    day=datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
    for body in bodies: body['updated_at']=day
    left,right=git('rev-list','--left-right','--count','origin/main...HEAD').decode().split()
    relation=dict(ahead_by=int(right),behind_by=int(left),main_commit=before_main)
    control['source_of_truth']['active_workstream_status'].update(branch=BRANCH,path=STATUS)
    control['active_workstream']=dict(branch=BRANCH,base_branch='v2-h0004-preaccess-evaluator',
        base_commit=json.loads((ROOT/'manifest.json').read_bytes())['base_commit'],implementation_commit=commit,
        status='DIVERGED_FROM_MAIN',observed_relation_to_main=relation,
        note='First sealed70 discovery execution complete twice;48 full denominator retained. Exploratory only; frozen signal/protocol unchanged. Code not main-integrated. Next H0005 independent thesis selection.')
    control['current_phase']['status']='H0004_EXPLORATORY_COMPLETE_H0005_OWNER_THESIS_PENDING'
    control['current_phase']['progress']['completed_H0004_cycle']=deepcopy(control['current_phase']['progress'])
    control['current_phase']['progress'].update(active_hypothesis='H0005',next_available_hypothesis='H0005',
        strategy_meaning='H0005_OWNER_THESIS_SELECTION_REQUIRED',
        causal_frequency='H0005_NOT_RUN',signal_freeze='H0005_NOT_STARTED',
        efficacy_preregistration='H0005_NOT_STARTED',evaluation_adapter='H0005_NOT_IMPLEMENTED',
        outcome_evaluation='H0004_EXECUTED_DISCOVERY_EXPLORATORY_ONLY',
        H0004_discovery_disposition=receipt['disposition'],H0004_confirmation_wait='ASYNCHRONOUS_NOT_BLOCKING',
        satisfied_exit_criteria=[1,2,3],remaining_exit_criteria=[],
        next_cycle_exit_criteria_status='H0005_NOT_STARTED; owner thesis required before implementation')
    track=control['hypothesis_tracks']['H0004']
    changes=dict(status=['FROZEN','PREREGISTERED','EXPLORATORY_DISCOVERY_EVALUATED','AWAITING_FUTURE_CONFIRMATION'],
        branch=BRANCH,commit=commit,outcome_access='DISCOVERY_ONLY_EXECUTED; CONFIRMATION0',
        outcome_evaluation='EXECUTED_DISCOVERY_EXPLORATORY',efficacy_calculations='DISCOVERY_DESCRIPTIVE_ONLY',
        evaluation_adapter='FROZEN_EXACT16_SLOT_ADAPTER_EXECUTED_DISCOVERY; FUTURE_CONFIRMATION_ADMISSION_AND_TERMINAL_SEAL_REQUIRED')
    track.update(changes)
    track.update(discovery_record=RECORD,discovery_evidence=(ROOT/'run1/report.json').as_posix(),
        discovery_verification=(ROOT/'verification.json').as_posix(),discovery_report_sha256=receipt['report_sha256'],
        discovery_label_stream_sha256=receipt['label_stream_sha256'],discovery_disposition=receipt['disposition'],
        discovery_aggregate=receipt['aggregate'],discovery_metrics=receipt['metrics'],
        discovery_uncertainty='NOT_CONFIRMATORY',discovery_label_reads_total=receipt['discovery_label_reads_total'],
        discovery_forward_price_queries_total=receipt['discovery_forward_price_queries_total'],
        discovery_independent_executions=2,discovery_outcome_access_namespace='SEALED70_DISCOVERY_ONLY')
    if any(track[k]!=v for k,v in old_h4.items() if k not in changes):
        raise ValueError('Existing H0004 frozen field changed')
    control['completed_actions'].append(dict(id=ACTION,status='COMPLETE_VALID_EXPLORATORY_DISCOVERY',
        completed_at=day,branch=BRANCH,commit=commit,record=RECORD,verification=(ROOT/'verification.json').as_posix(),
        implementation_state='IMPLEMENTED_EXECUTED_ON_REAL_DISCOVERY_EVIDENCE_PRODUCED_NOT_MAIN_CODE_INTEGRATED',
        candidate_denominator=48,candidate_sessions=29,signal_trials=2,aggregate=receipt['aggregate'],
        descriptive_disposition=receipt['disposition'],uncertainty='NOT_CONFIRMATORY',profitability='NOT_ESTIMATED',
        confirmation_outcome_access=0,deterministic_executions=2,tests=receipt['tests']))
    control['next_action']=dict(id=NEXT,priority='P0',status='USER_DECISION_REQUIRED',hypothesis_id='H0005',
        blocks_phase_exit_criteria=[1],objective='Select one independent H0005 falsifiable market mechanism and causal inputs; record prior exposure before implementation.',
        constraints=['Preserve H0001~H0004 frozen hypotheses and asynchronous confirmation; no interim outcomes.',
            'No H0004 parameter/session/horizon or segment tuning; discovery direction does not control routing.',
            'H0005 selection is not completed by this routing action.',
            'Cross-instrument validation policy remains a separate future project action; no external capture here.'])
    index['default_research_branch']=BRANCH
    index['canonical_sources']['current_status'].update(branch=BRANCH,path=STATUS)
    index['canonical_sources']['H0004']=deepcopy(track)
    index['canonical_sources']['active_hypothesis']=dict(id='H0005',status='OWNER_THESIS_SELECTION_REQUIRED_NOT_IMPLEMENTED',
        branch=BRANCH,note='No H0005 hypothesis artifact or signal exists yet; registry intake is the next action.')
    for group in index['current_open_decision_groups']:
        if group['id']==ACTION:
            group.update(priority='COMPLETE',status='RESOLVED_VALID_EXPLORATORY_DISCOVERY',
                blocks_phase_exit_criteria=[],evidence_branch=BRANCH,record=RECORD,
                note='All48 retained; deterministic first outcomes. No confirmation inference/profitability or tuning.')
    index['current_open_decision_groups'].append(dict(id=NEXT,hypothesis_id='H0005',priority='P0',
        status='USER_DECISION_REQUIRED',blocks_phase_exit_criteria=[1],evidence_branch=BRANCH,
        note='Independent next mechanism selection. Frozen future confirmation waits do not block research.'))
    index['schema_revision']='H0004 discovery exploratory executed with immutable48/29 denominator, trials2 and zero confirmation access. H0005 independent owner thesis is the sole active P0.'
    for item in backlog['items']:
        if item['id']=='V2_MAIN_INTEGRATION_LANE': item.update(active_branch=BRANCH,observed_relation_to_main=relation)
        if item['id']==ACTION:
            item.update(priority='COMPLETE',status='COMPLETE_VALID_EXPLORATORY_DISCOVERY',blocks_phase_exit_criteria=[],
                evidence_branch=BRANCH,record=RECORD,summary='Frozen exact16-slot discovery executed twice; full48 denominator preserved, no CI/tuning/confirmation/profitability.')
    backlog['items'].append(dict(id='H0005_INDEPENDENT_HYPOTHESIS_SELECTION',action_id=NEXT,priority='P0',
        status='USER_DECISION_REQUIRED',blocks_phase_exit_criteria=[1],summary='Choose independent H0005 thesis; no signal or implementation yet.'))
    backlog['items'].append(dict(id='CROSS_INSTRUMENT_VALIDATION_POLICY',priority='P2',status='OPEN_FUTURE_PROJECT_ACTION',
        blocks_phase_exit_criteria=[],after='H0005 independent thesis selection or separate project-level research action',
        summary='Define untouched external-instrument validation of frozen signals on SMH/QQQ/SPY without condition changes; record prior exposure and multiplicity.',
        constraints='No external instrument added/captured/evaluated in H0004 discovery; no outcome-driven external parameters. QQQ already exposed in H0003 is not certified untouched by naming it.',
        implementation='NOT_IMPLEMENTED_NOT_EXECUTED'))
    for item in ideas['items']:
        if item['id']=='USER-H0004-COMPRESSION-001':
            item.update(status='FROZEN_EXPLORATORY_DISCOVERY_EVALUATED_CONFIRMATION_ASYNC_PENDING',
                efficacy_record=RECORD,efficacy_branch=BRANCH,disposition=receipt['disposition'])
    if any(control['hypothesis_tracks'][h]!=v for h,v in prior_tracks.items()) or index['frozen_major_decisions']!=prior_frozen:
        raise ValueError('Prior tracks/frozen decisions changed')
    if any(index['canonical_sources'][k]!=v for k,v in prior_sources.items()): raise ValueError('Prior canonical source changed')
    if [g['id'] for g in index['current_open_decision_groups'] if g['priority']=='P0']!=[NEXT]:
        raise ValueError('Exactly one active canonical P0 required')
    for path,body in zip(paths,bodies): path.write_text(yaml.safe_dump(body,sort_keys=False,allow_unicode=True),encoding='utf-8')
    status=MAIN/'PROJECT_STATUS.md'
    prefix=(f'# Richping PM - H0004 first discovery execution complete\n\n'
        f'Workstream `{BRANCH}` / `{commit}`, code not merged into main. '
        f'Frozen48 candidates/29 sessions, trials2. Complete{receipt["aggregate"]["complete"]}/unresolved{receipt["aggregate"]["unresolved"]}. '
        f'Disposition {receipt["disposition"]}; exploratory descriptive only, uncertainty NOT_CONFIRMATORY; profitability NOT_ESTIMATED. '
        'Two independent processes produce identical labels/paths/reports. All prior frozen sources/evidence and H0001~3 tracks preserved; H0004 signal/protocol unchanged. '
        'Confirmation outcome access0; fixed252 sessions2026-10-19..2027-10-19, terminal after2027-10-21 20:00ET remains PENDING/ASYNCHRONOUS.\n\n'
        f'NEXT_ACTION **{NEXT} / H0005 / USER_DECISION_REQUIRED**. Owner independent thesis selection is next; H0005 not implemented. '
        'Cross-instrument policy P2 backlog only; no external instrument or tuning in this action.\n\nEntries below are historical reports.\n\n')
    status.write_text(prefix+status.read_text(encoding='utf-8'),encoding='utf-8')
    proof=dict(schema='h0004_discovery_pm_update_proof_v1',canonical_main_before=before_main,research_commit=commit,
        files_before=before,prior_H0001_H0002_H0003_tracks_preserved=True,H0004_frozen_fields_preserved=True,
        prior_canonical_sources_and_frozen_major_decisions_preserved=True,completed_P0=ACTION,active_P0=NEXT,
        active_hypothesis='H0005',confirmation_outcome_access=0,profitability='NOT_ESTIMATED')
    write_new(ROOT/'pm-update-proof.json',encode(proof))
    return proof


if __name__=='__main__': print(json.dumps(update(),indent=2))
