"""Route canonical PM main after verified, outcome-free H0003 preregistration."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo
import yaml

from scripts.h0003_signal_preregister import ROOT, BASE, FREEZE, SPEC, PROTOCOL, run
from scripts.h0003_verify import junit
from scripts.h0003_frequency_audit import encode, fingerprint
from scripts.h0001_long_history_audit import write_new

MAIN = Path('var/pm-action-unit-main')
BRANCH = 'v2-h0003-signal-freeze-preregistration'


def test_report():
    verified = run()
    tests = [junit(ROOT/name) for name in ('tests-targeted-v1.xml','tests-full-v1.xml')]
    if tests[0]['tests'] != 134 or tests[1]['tests'] != 1643 or any(
            row[key] for row in tests for key in ('errors','failures','skipped')):
        raise ValueError('Complete passing targeted/full regression required')
    result = dict(schema='h0003_freeze_test_verification_v1',tests=tests,
        design_tests=junit(ROOT/'tests-design-v1.xml'),metadata_verification_sha256=fingerprint(ROOT/'verification.json'),
        manifest_sha256=fingerprint(ROOT/'manifest.json'),
        frozen_source_and_evidence_preserved=verified['preserved_files'],
        H0001_H0002_and_H0003_discovery_unchanged=True,
        H0003_outcome_access=0,H0003_future_price_queries=0,H0003_efficacy_calculations=0,
        profitability='NOT_ESTIMATED',next_P0='H0003_FIRST_EFFICACY',
        scope='Market labels/statistics are not implemented or executed here. Historical H0002 regression fixtures are a separate scope.')
    write_new(ROOT/'test-verification.json',encode(result))
    return verified,result


def update():
    verified,checks = test_report()
    def git(*args):
        return subprocess.run(['git',*args],check=True,capture_output=True,text=True).stdout.strip()
    if git('branch','--show-current') != BRANCH or git('-C',str(MAIN),'status','--porcelain'):
        raise ValueError('Expected research branch and clean canonical main worktree')
    commit = git('rev-parse','HEAD')
    if git('-C',str(MAIN),'rev-parse','HEAD') != git('rev-parse','origin/main'):
        raise ValueError('Canonical main is not current remote main')
    paths = [MAIN/name for name in ('PROJECT_CONTROL.yaml','project/DECISION_INDEX.yaml','project/BACKLOG.yaml','project/USER_IDEAS.yaml')]
    control,index,backlog,ideas = [yaml.safe_load(p.read_text(encoding='utf-8')) for p in paths]
    if control['next_action']['id'] != 'H0003_SIGNAL_FREEZE_PREREGISTRATION':
        raise ValueError('Canonical next action changed; reread bootstrap')
    frozen_tracks = deepcopy({k:control['hypothesis_tracks'][k] for k in ('H0001','H0002')})
    frozen_index = deepcopy({k:v for k,v in index['canonical_sources'].items() if k not in ('H0003','active_hypothesis','last_frozen_candidate_spec','current_status')})
    frozen_major = deepcopy(index['frozen_major_decisions'])
    frozen_groups = deepcopy([g for g in index['current_open_decision_groups'] if not g['id'].startswith('H0003')])
    day = datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
    for body in (control,index,backlog,ideas):
        body['updated_at'] = day
    left,right = git('rev-list','--left-right','--count','origin/main...HEAD').split()
    relation = dict(ahead_by=int(right),behind_by=int(left),main_commit=git('rev-parse','origin/main'))
    control['source_of_truth']['active_workstream_status']['branch'] = BRANCH
    control['active_workstream'] = dict(branch=BRANCH,base_branch='v2-h0003-relative-strength-frequency',
        base_commit=BASE,implementation_commit=commit,status='DIVERGED_FROM_MAIN',observed_relation_to_main=relation,
        note='Owner-approved signal frozen unchanged; relative16-slot evaluation fully preregistered. H0003 outcomes0; paired-label/bootstrap execution still belongs to next separate action.')
    phase = control['current_phase']
    phase['status'] = 'H0003_PREREGISTERED_AWAITING_FIRST_EXPLORATORY_EFFICACY'
    phase['progress'].update(signal_freeze='FROZEN_OWNER_APPROVED',efficacy_preregistration='COMPLETE_FROZEN_BEFORE_OUTCOMES',
        outcome_evaluation='NOT_RUN_H0003',H0003_confirmation_wait='ASYNCHRONOUS_NOT_BLOCKING',
        satisfied_exit_criteria=[1,2],remaining_exit_criteria=[3])
    control['completed_actions'].append(dict(id='H0003_SIGNAL_FREEZE_PREREGISTRATION',hypothesis='H0003-r01',
        status='COMPLETE_SIGNAL_FROZEN_PROTOCOL_PREREGISTERED_OUTCOMES_NOT_RUN',completed_at=day,branch=BRANCH,commit=commit,
        record=FREEZE.as_posix(),preregistration=PROTOCOL.as_posix(),evidence=(ROOT/'verification.json').as_posix(),
        test_verification=(ROOT/'test-verification.json').as_posix(),tests=checks['tests'],
        acceptance_criteria=dict(owner_semantics_unchanged=True,immutable_signal_binding=True,
            full_relative_evaluation_protocol=True,future_chronological_confirmation_frozen=True,
            discovery_35_events_29_sessions_preserved=True,H0003_outcomes_zero=True,prior_tracks_preserved=True),
        outcome_access=0,efficacy_calculations=0,profitability='NOT_ESTIMATED'))
    control['next_action'] = dict(id='H0003_FIRST_EFFICACY',priority='P0',status='READY',hypothesis_id='H0003',
        blocks_phase_exit_criteria=[3],evidence_branch=BRANCH,basis_evidence=(ROOT/'verification.json').as_posix(),
        objective='Implement and validate the registered paired-label adapter, then first disclose sealed70-session exploratory H0003 forward outcomes under the frozen relative16-slot protocol.',
        why_now='Final signal approval, immutable binding, preregistration and regression complete; outcome access has remained0.',
        constraints=['Discovery exploratory only; no confirmation PASS/REJECT, CI, power or profitability claim.',
            'Bind and validate paired-label adapter source with synthetic tests before first H0003 discovery outcome query.',
            'Retain all35 immutable candidates including mature unavailable endpoints; no extra outcome-driven capture or complete-case deletion.',
            'No signal/horizon/benchmark/guard/session/episode tuning from outcomes.',
            'Confirmation stays asynchronous PENDING; no confirmation labels before fixed terminal deadline.',
            'Preserve H0001/H0002 and prior H0003 frozen source/evidence.'])
    track = control['hypothesis_tracks']['H0003']
    track['frequency_record'] = track['record']
    if 'verification_commit' in track:
        track['frequency_verification_commit'] = track.pop('verification_commit')
    track.update(status=['FROZEN','PREREGISTERED','AWAITING_FIRST_EXPLORATORY_EFFICACY','AWAITING_FUTURE_CONFIRMATION'],
        branch=BRANCH,commit=commit,spec=SPEC.as_posix(),record=FREEZE.as_posix(),signal_freeze='FROZEN_OWNER_APPROVED',
        preregistration=PROTOCOL.as_posix(),protocol_hash=verified['protocol_hash'],
        signal_freeze_sha256=verified['signal_freeze_sha256'],spec_sha256=verified['signal_spec_sha256'],
        freeze_evidence=(ROOT/'verification.json').as_posix(),event_stream_hash=verified['event_stream_hash'],
        confirmation=dict(status='PENDING',start='2026-10-19',end='2027-10-19',sessions=252,
            followup_end='2027-10-20',receipt_deadline='2027-10-21T20:00:00-04:00'),
        evidence_floor=dict(events=40,sessions=20,occupied_fixed_10_session_blocks=8),
        primary_horizon_slots=16,primary_estimand='Session-balanced future SOXX price return minus paired QQQ price return',
        absolute_SOXX_outcome='SECONDARY_DESCRIPTIVE',confirmation_is_project_blocker=False,
        owner_signal_semantics='FINAL_APPROVED_2026_10_05',confirmation_outcome_access=0,efficacy_calculations=0,
        evaluation_adapter=verified['evaluation_adapter'])
    index['default_research_branch'] = BRANCH
    index['canonical_sources']['current_status']['branch'] = BRANCH
    index['canonical_sources']['H0003'] = deepcopy(track)
    index['canonical_sources']['active_hypothesis'] = dict(id='H0003',status='FROZEN_PREREGISTERED_OUTCOMES_NOT_RUN',
        branch=BRANCH,path='research/hypotheses/H0003-r01.yaml',record=FREEZE.as_posix())
    index['canonical_sources']['last_frozen_candidate_spec'] = dict(branch=BRANCH,path=SPEC.as_posix(),status='FROZEN',sha256=verified['signal_spec_sha256'])
    index['frozen_major_decisions']['H0003_signal_and_efficacy'] = dict(status='FROZEN_BEFORE_OUTCOMES',branch=BRANCH,
        commit=commit,record=FREEZE.as_posix(),preregistration=PROTOCOL.as_posix(),
        protocol_hash=verified['protocol_hash'],signal_freeze_sha256=verified['signal_freeze_sha256'])
    for group in index['current_open_decision_groups']:
        if group['id'] == 'H0003_SIGNAL_FREEZE_PREREGISTRATION':
            group.update(status='RESOLVED_OWNER_APPROVED_AND_PREREGISTERED',priority='COMPLETE',blocks_phase_exit_criteria=[],
                evidence_branch=BRANCH,record=FREEZE.as_posix(),preregistration=PROTOCOL.as_posix(),
                evidence=(ROOT/'verification.json').as_posix(),note='Owner approved sealed provisional semantics unchanged; signal and efficacy contract frozen with outcomes0.')
    index['current_open_decision_groups'].append(dict(id='H0003_FIRST_EFFICACY',status='READY',priority='P0',
        blocks_phase_exit_criteria=[3],evidence_branch=BRANCH,record=FREEZE.as_posix(),preregistration=PROTOCOL.as_posix(),
        note='Separate first exploratory outcomes; build validated paired labels before accessing them. Confirmation remains PENDING/asynchronous.'))
    index['schema_revision'] = 'H0001/H0002 and discovery evidence preserved. H0003 signal/preregistration frozen before outcomes; next P0 H0003_FIRST_EFFICACY. H0004 remains the next unused registry id.'
    for item in backlog['items']:
        if item['id'] == 'V2_MAIN_INTEGRATION_LANE':
            item.update(active_branch=BRANCH,observed_relation_to_main=relation)
        if item['id'] == 'H0003_SIGNAL_FREEZE_PREREGISTRATION':
            item.update(priority='COMPLETE',status='COMPLETE_FROZEN_PREREGISTERED',blocks_phase_exit_criteria=[],
                summary='Final64-slot/four-observation/own>=0 signal unchanged; relative16-slot protocol frozen, H0003 outcomes0.',
                evidence_branch=BRANCH,record=FREEZE.as_posix(),preregistration=PROTOCOL.as_posix())
        if item['id'] == 'H0003_INDEPENDENT_HYPOTHESIS_INTAKE':
            item.update(strategy_meaning='OWNER_THESIS_AND_FINAL_SIGNAL_APPROVED',
                routing='COMPLETE_H0003_FREEZE_PREREGISTRATION_NOW_FIRST_EFFICACY',
                summary='Independent SOXX/QQQ thesis and causal frequency complete; separate final freeze/preregistration also completed with outcomes0.')
    backlog['items'].extend([
        dict(id='H0003_FIRST_EFFICACY',priority='P0',status='READY',blocks_phase_exit_criteria=[3],
            summary='First sealed35-event exploratory paired SOXX/QQQ outcomes after adapter validation; no confirmation inference.',
            evidence_branch=BRANCH,preregistration=PROTOCOL.as_posix()),
        dict(id='H0003_FUTURE_CONFIRMATION',priority='ASYNC',status='PENDING_FUTURE_FIXED_COHORT',blocks_phase_exit_criteria=[],
            summary='252 fixed sessions2026-10-19..2027-10-19; terminal after2027-10-21 20:00ET. New paired admission/prefix/unit-segment adapter required; no present label access.',
            evidence_branch=BRANCH,preregistration=PROTOCOL.as_posix(),project_blocker=False)])
    for item in ideas['items']:
        if item['id'] == 'USER-H0003-LEADERSHIP-001':
            item.update(status='FROZEN_PREREGISTERED_OUTCOMES_NOT_RUN',evidence_branch=BRANCH,
                record=FREEZE.as_posix(),preregistration=PROTOCOL.as_posix())
    if frozen_tracks != {k:control['hypothesis_tracks'][k] for k in ('H0001','H0002')}:
        raise ValueError('Frozen hypothesis tracks changed')
    if any(index['canonical_sources'][k] != v for k,v in frozen_index.items()) or any(index['frozen_major_decisions'][k] != v for k,v in frozen_major.items()):
        raise ValueError('Prior canonical frozen decisions changed')
    if frozen_groups != [g for g in index['current_open_decision_groups'] if not g['id'].startswith('H0003')]:
        raise ValueError('Prior decision groups changed')
    for path,body in zip(paths,(control,index,backlog,ideas)):
        path.write_text(yaml.safe_dump(body,allow_unicode=True,sort_keys=False),encoding='utf-8')
    status = MAIN/'PROJECT_STATUS.md'
    prefix = (f'# Richping PM - H0003 signal frozen and efficacy preregistered\n\n'
        f'Implementation `{BRANCH}` / `{commit}`; not merged into main. Owner-approved signal unchanged: '
        'SOXX versus technology/growth QQQ,64 scheduled15m-slot return difference,4 consecutive positive observations, '
        'SOXX return>=0, one candidate per episode; only observed READY RS<=0 rearms. Discovery35 events/29 sessions preserved. '
        'Relative16-slot session-balanced primary mean, zero-excess null; absolute direction and4/64 horizons descriptive. '
        'Confirmation252 sessions2026-10-19..2027-10-19, fixed deadline2027-10-21 20:00ET, floors40 events/20 sessions/8 fixed10-session bins. '
        '10-session circular calendar blocks,10000 draws, seed20261005,95% interval. '
        'H0003 outcomes/future queries/efficacy0; profitability NOT_ESTIMATED. Targeted134/full1643 tests passed;570 prior files preserved. '
        'H0001/H0002 frozen protocols/evidence/asynchronous tracks unchanged.\n\n'
        'NEXT_ACTION **H0003_FIRST_EFFICACY / READY**. Separately implement/validate registered paired labels then publish discovery exploratory outcomes; '
        'future confirmation remains PENDING, not a project blocker. Evaluation contract is frozen; real label/bootstrap adapter is not yet implemented or executed.\n\n'
        'Entries below are preserved historical reports.\n\n')
    status.write_text(prefix+status.read_text(encoding='utf-8'),encoding='utf-8')
    return dict(implementation_commit=commit,next_P0=control['next_action']['id'])


if __name__ == '__main__':
    print(json.dumps(update()))
