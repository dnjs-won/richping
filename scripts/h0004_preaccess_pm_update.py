"""Publish completed outcome-free adapter and route one bounded discovery P0."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo
import yaml

from scripts.h0004_preaccess import ROOT,BASE,run
from scripts.h0004_frequency_audit import encode,write_new,fingerprint

MAIN = Path('var/pm-action-unit-main')
BRANCH = 'v2-h0004-preaccess-evaluator'
NEXT = 'H0004_DISCOVERY_EFFICACY_EXECUTION'
RECORD = 'research/decision_records/H0004-preaccess-evaluator-v1.yaml'
STATUS = 'docs/H0004_PREACCESS_RESULTS.md'


def update():
    receipt = run()
    def git(*args):
        return subprocess.run(['git',*args],check=True,capture_output=True,text=True).stdout.strip()
    if git('branch','--show-current')!=BRANCH or git('status','--porcelain') or git('-C',str(MAIN),'status','--porcelain'):
        raise ValueError('Clean committed research and canonical main required')
    before_main = git('-C',str(MAIN),'rev-parse','HEAD')
    if before_main!=git('rev-parse','origin/main'): raise ValueError('Canonical main changed; bootstrap again')
    commit = git('rev-parse','HEAD')
    paths = [MAIN/n for n in ('PROJECT_CONTROL.yaml','project/DECISION_INDEX.yaml','project/BACKLOG.yaml','project/USER_IDEAS.yaml')]
    control,index,backlog,ideas = [yaml.safe_load(p.read_text(encoding='utf-8')) for p in paths]
    if control['next_action']['id']!='H0004_FIRST_EFFICACY': raise ValueError('Canonical P0 changed')
    prior_tracks = deepcopy({h:v for h,v in control['hypothesis_tracks'].items() if h!='H0004'})
    prior_frozen = deepcopy(index['frozen_major_decisions'])
    prior_sources = deepcopy({k:v for k,v in index['canonical_sources'].items()
                             if k not in ('H0004','active_hypothesis','current_status')})
    old_h4 = deepcopy(control['hypothesis_tracks']['H0004'])
    before = {p.relative_to(MAIN).as_posix():fingerprint(p) for p in paths}
    day = datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
    for body in (control,index,backlog,ideas): body['updated_at']=day
    left,right = git('rev-list','--left-right','--count','origin/main...HEAD').split()
    relation = dict(ahead_by=int(right),behind_by=int(left),main_commit=before_main)
    control['source_of_truth']['active_workstream_status'].update(branch=BRANCH,path=STATUS)
    control['active_workstream']=dict(branch=BRANCH,base_branch='v2-h0004-segment-freeze-preregistration',
        base_commit=BASE,implementation_commit=commit,status='DIVERGED_FROM_MAIN',observed_relation_to_main=relation,
        note='Registered exact16-slot directional adapter implemented/tested/sealed with SYNTHETIC fixtures; real H0004 outcomes/endpoint probes0. Next separate bounded discovery execution. Prior tracks/trials/freeze/protocol unchanged.')
    control['current_phase']['status']='H0004_PREACCESS_ADAPTER_COMPLETE_DISCOVERY_EXECUTION_PENDING'
    control['current_phase']['progress'].update(evaluation_adapter='IMPLEMENTED_SYNTHETIC_TESTED_SEALED_INDEPENDENT_PASS',
        outcome_evaluation='NOT_RUN_H0004',satisfied_exit_criteria=[1,2],remaining_exit_criteria=[3])
    track = control['hypothesis_tracks']['H0004']
    track.update(branch=BRANCH,commit=commit,evaluation_adapter='EXACT16_SLOT_DIRECTIONAL_IMPLEMENTED_TESTED_SEALED; REAL_OUTCOMES_NOT_RUN',
        evaluator='richping/research_v2/strategy/h0004_directional_evaluator.py',
        preaccess_manifest=(ROOT/'manifest.json').as_posix(),preaccess_verification=(ROOT/'verification.json').as_posix(),
        preaccess_record=RECORD,preaccess_manifest_sha256=receipt['manifest_sha256'],
        preaccess_verification_sha256=fingerprint(ROOT/'verification.json'),
        preaccess_outcome_access=0,real_endpoint_readiness_probes=0,confirmation_terminal_adapter='FUTURE_ADMISSION_AND_TERMINAL_SEAL_REQUIRED')
    # All prior H0004 frozen contract/evidence identifiers stay byte-for-byte/value-identical.
    changed = {'branch','commit','evaluation_adapter'}
    if any(track[k]!=v for k,v in old_h4.items() if k not in changed):
        raise ValueError('Existing H0004 frozen fields changed')
    control['completed_actions'].append(dict(id='H0004_FIRST_EFFICACY',status='COMPLETE_PREACCESS_ONLY',
        completed_at=day,branch=BRANCH,commit=commit,record=RECORD,
        implementation_state='IMPLEMENTED_SYNTHETIC_TESTED_SEALED_EVIDENCE_PRODUCED_NOT_MAIN_CODE_INTEGRATED',
        manifest=(ROOT/'manifest.json').as_posix(),verification=(ROOT/'verification.json').as_posix(),
        outcome_audit=(ROOT/'outcome-access-audit.json').as_posix(),tests=receipt['tests'],
        candidate_denominator=48,candidate_sessions=29,signal_trials=2,outcome_access=0,
        future_price_queries=0,efficacy_calculations=0,profitability_calculations=0,confirmation_outcome_access=0,
        actual_endpoint_readiness_probes=0,protected_files=receipt['protected_files']))
    control['next_action']=dict(id=NEXT,priority='P0',status='READY_FOR_BOUNDED_DISCOVERY_EXPLORATORY_EXECUTION',
        hypothesis_id='H0004',blocks_phase_exit_criteria=[3],evidence_branch=BRANCH,record=RECORD,
        preaccess_manifest=(ROOT/'manifest.json').as_posix(),
        preaccess_verification_sha256=fingerprint(ROOT/'verification.json'),
        objective='In a separate bounded action, first execute exact16-slot labels for all48 frozen discovery candidates and session-balanced directional summary; retain unresolved full denominator.',
        constraints=['Verify immutable pre-access PASS/source/bindings before first price access; no signal regeneration or extra capture.',
                    'Discovery only: sealed70 sessions, no confirmation values, benchmark, controls, CI/PASS/REJECT, MFE/MAE or profitability.',
                    'No tuning or third signal variant. Preserve all48 candidates; unsupported/missing/unit-ambiguous labels remain unresolved.',
                    'All earlier frozen hypotheses/trials/evidence/preregistrations unchanged; confirmation PENDING/ASYNCHRONOUS.'])
    index['default_research_branch']=BRANCH
    index['canonical_sources']['current_status'].update(branch=BRANCH,path=STATUS)
    index['canonical_sources']['H0004']=deepcopy(track)
    index['canonical_sources']['active_hypothesis'].update(branch=BRANCH,status='FROZEN_PREREGISTERED_PREACCESS_SEALED_OUTCOMES_NOT_RUN')
    for group in index['current_open_decision_groups']:
        if group['id']=='H0004_FIRST_EFFICACY':
            group.update(priority='COMPLETE',status='RESOLVED_PREACCESS_ADAPTER_SEALED_VERIFIED_NO_OUTCOMES',
                blocks_phase_exit_criteria=[],evidence_branch=BRANCH,record=RECORD,
                note='Exact16-slot adapter, synthetic tests and independent pre-access PASS complete; real outcomes/endpoint probes0.')
    index['current_open_decision_groups'].append(dict(id=NEXT,priority='P0',
        status='READY_FOR_BOUNDED_DISCOVERY_EXPLORATORY_EXECUTION',blocks_phase_exit_criteria=[3],
        evidence_branch=BRANCH,record=RECORD,
        note='Separate first discovery outcome action only;48 frozen candidates, exact16-slot labels, equal sessions; no confirmation access or CI.'))
    index['schema_revision']='H0004 pre-access exact16-slot adapter sealed/independent PASS, outcomes0;48/29 denominator and trials2 preserved. Single next P0 bounded discovery execution; confirmations asynchronous.'
    for item in backlog['items']:
        if item['id']=='V2_MAIN_INTEGRATION_LANE': item.update(active_branch=BRANCH,observed_relation_to_main=relation)
        if item['id']=='H0004_FIRST_EFFICACY':
            item.update(priority='COMPLETE',status='COMPLETE_PREACCESS_ADAPTER_SEALED_NO_OUTCOMES',
                blocks_phase_exit_criteria=[],evidence_branch=BRANCH,record=RECORD,
                summary='Exact16-slot directional label/readiness/weighting/scopes implemented and sealed; no real labels/readiness probes.')
    backlog['items'].append(dict(id=NEXT,priority='P0',status='READY_FOR_BOUNDED_DISCOVERY_EXPLORATORY_EXECUTION',
        blocks_phase_exit_criteria=[3],evidence_branch=BRANCH,record=RECORD,
        summary='First sealed70 discovery labels and session-balanced directional summary;48 full denominator, no extra capture or confirmation values.'))
    for item in ideas['items']:
        if item['id']=='USER-H0004-COMPRESSION-001':
            item.update(preaccess_evaluator='SEALED_VERIFIED_REAL_OUTCOMES_NOT_RUN',preaccess_record=RECORD)
    if any(control['hypothesis_tracks'][h]!=v for h,v in prior_tracks.items()) or index['frozen_major_decisions']!=prior_frozen:
        raise ValueError('Prior hypotheses/frozen decisions changed')
    if any(index['canonical_sources'][k]!=v for k,v in prior_sources.items()): raise ValueError('Prior frozen canonical sources changed')
    if [g['id'] for g in index['current_open_decision_groups'] if g['priority']=='P0']!=[NEXT]:
        raise ValueError('Exactly one canonical P0 required')
    for path,body in zip(paths,(control,index,backlog,ideas)):
        path.write_text(yaml.safe_dump(body,sort_keys=False,allow_unicode=True),encoding='utf-8')
    status = MAIN/'PROJECT_STATUS.md'
    prefix = (f'# Richping PM - H0004 pre-access evaluator complete\n\n'
        f'Workstream `{BRANCH}` / `{commit}`, code not merged into main. '
        'Exact scheduled16-slot directional labels and session-balanced full-denominator aggregation implemented, synthetic-tested, source/binding-sealed and independently verified. '
        'Real H0004 forward-price/discovery/confirmation/return/efficacy/profitability access0; real candidate endpoint readiness NOT_PROBED. '
        'Frozen48 candidates/29 sessions and trials2 unchanged. Prior H0001~3 and H0004 pooled/segment/freeze/protocol evidence protected. '
        'Missing/unsupported/outside-scope/unit ambiguity retained, no adjusted fallback/extra capture. '
        'Confirmation PENDING/ASYNCHRONOUS; future interval admission and terminal seal still required.\n\n'
        f'NEXT_ACTION **{NEXT} / READY_FOR_BOUNDED_DISCOVERY_EXPLORATORY_EXECUTION**. '
        'This is a separate future action for first discovery labels; none executed here.\n\n'
        'Entries below are historical reports.\n\n')
    status.write_text(prefix+status.read_text(encoding='utf-8'),encoding='utf-8')
    proof = dict(schema='h0004_preaccess_pm_update_proof_v1',canonical_main_before=before_main,research_commit=commit,
        files_before=before,prior_H0001_H0002_H0003_tracks_preserved=True,H0004_frozen_fields_preserved=True,
        prior_canonical_sources_and_frozen_major_decisions_preserved=True,active_P0=NEXT,
        completed_P0='H0004_FIRST_EFFICACY_PREACCESS_ONLY',real_outcome_access=0)
    write_new(ROOT/'pm-update-proof.json',encode(proof))
    return proof


if __name__=='__main__':
    print(json.dumps(update(),indent=2))
