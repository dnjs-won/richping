"""Owner-authorized H0003 signal freeze and metadata-only efficacy preregistration."""
from argparse import ArgumentParser
from contextlib import ExitStack,contextmanager
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import yaml

from richping.core import digest
from richping.research_v2.strategy.h0003_leadership import Specification,CONTRACT
from richping.research_v2.strategy.h0003_experiment import VERSION,calendar_contract,validate_events
from scripts.h0003_frequency_audit import ROOT as DISCOVERY,GUARDS,encode,fingerprint,preservation_fingerprint
from scripts.h0003_verify import verify_state
from scripts.h0001_long_history_audit import write_new

BASE = '934f8f8036dcf7bc073e779d33827154428b08b4'
ROOT = Path('research/data_evidence/h0003-freeze-preregistration-20261005')
PROVISIONAL = Path('research/strategy_specs/H0003-r01-candidate.yaml')
HYPOTHESIS = Path('research/hypotheses/H0003-r01.yaml')
SPEC = Path('research/strategy_specs/H0003-r01-frozen-v1.yaml')
FREEZE = Path('research/decision_records/H0003-signal-freeze-v1.json')
PROTOCOL = Path('research/decision_records/H0003-efficacy-preregistration-v1.yaml')
BOUND = (SPEC,FREEZE,PROTOCOL,Path('scripts/h0003_signal_preregister.py'),
         Path('richping/research_v2/strategy/h0003_experiment.py'),
         Path('tests/test_h0003_preregistration.py'),Path('docs/H0003_SIGNAL_FREEZE_PREREGISTRATION.md'))


def runtime_identity():
    return dict(python=sys.version.split()[0],exchange_calendars=version('exchange_calendars'),PyYAML=version('PyYAML'))


@contextmanager
def metadata_only():
    targets = {**GUARDS,'sqlite3.connect':'database',
        'scripts.h0003_frequency_audit.paired_inputs':'market_load',
        'scripts.h0003_frequency_audit.replay':'signal_replay',
        'scripts.h0003_verify.verify':'market_revalidation',
        'richping.research_v2.market_data.MarketDataset.from_records':'market_load',
        'richping.research_v2.strategy.h0003_leadership.LeadershipStream.accept':'signal_replay',
        'richping.research_v2.strategy.h0002_efficacy.DiscoveryLabels.label':'outcome_accessor',
        'richping.research_v2.strategy.h0002_efficacy._registered_bootstrap':'efficacy_calculation'}
    counts = {k:0 for k in targets.values()}
    def reject(category):
        def denied(*args,**kwargs):
            counts[category] += 1
            raise AssertionError('H0003 freeze forbids '+category)
        return denied
    with ExitStack() as stack:
        for target,category in targets.items():
            stack.enter_context(patch(target,side_effect=reject(category)))
        yield counts


def validate_protocol(body):
    required = {'sample','horizons','label','baseline','absolute_relevance','costs','discovery',
                'confirmation','evidence_floor','uncertainty','multiple_testing','disposition'}
    if not required <= body.keys() or body.get('version') != VERSION or body.get('outcome_access_this_action') != 'FORBIDDEN':
        raise ValueError('Incomplete/incorrect preregistration')
    if body['horizons']['primary_slots'] != 16 or body['horizons']['secondary_slots'] != [4,64]:
        raise ValueError('Horizon identity changed')
    if body['comparators'] != [] or body['primary_family'] != 'RELATIVE_STRENGTH_LEADERSHIP_CONTINUATION':
        raise ValueError('Primary-only family required')
    if (body['label']['name'],body['baseline']['name'],body['baseline']['matched_controls']) != (
            'DIRECT_PAIRED_FORWARD_CLOSE_PRICE_EXCESS','DIRECT_CONTEMPORANEOUS_QQQ_EXCESS_ZERO_NULL','NONE; QQQ is the direct comparison, no non-event search/fallback engine.'):
        raise ValueError('Relative estimand/baseline changed')
    if body['absolute_relevance']['role'] != 'SECONDARY_DESCRIPTIVE_SOXX_PRICE_RETURN':
        raise ValueError('No silently added absolute primary gate')
    if body['costs']['profitability'] != 'NOT_ESTIMATED' or body['costs']['costs_bps'] is not None or body['costs']['net_return'] is not None:
        raise ValueError('Gross non-profitability scope required')
    grid = calendar_contract()
    c = body['confirmation']
    if (c['anchor_start'],c['anchor_end'],c['official_sessions'],c['followup_end'],c['terminal_receipt_deadline'],
            c['embargo_start'],c['embargo_end'],c['prefix_origin']) != (
            grid['anchors'][0],grid['anchors'][-1],252,grid['followup'][-1],'2027-10-21T20:00:00-04:00',
            grid['embargo'][0],grid['embargo'][-1],'2026-05-05') or not c['asynchronous'] or c['project_blocker']:
        raise ValueError('Fixed asynchronous calendar/prefix identity changed')
    floor,u,m = body['evidence_floor'],body['uncertainty'],body['multiple_testing']
    if (floor['complete_events'],floor['distinct_candidate_sessions'],floor['occupied_fixed_10_session_blocks'],
            u['block_sessions'],u['replicates'],u['seed'],m['primary_families'],m['alpha']) != (40,20,8,10,10000,20261005,1,.05):
        raise ValueError('Floor/dependence/multiplicity identity changed')
    return grid


def freeze():
    verify_state()
    proposed = yaml.safe_load(PROVISIONAL.read_bytes())
    if proposed['parameters'] != {'window_slots':64,'persistence_slots':4}:
        raise ValueError('Owner selected existing definition unchanged')
    spec = dict(proposed)
    spec.update(schema_version='h0003_frozen_signal_v1',version='H0003_RELATIVE_LEADERSHIP_SIGNAL_V1',
                status='FROZEN_OWNER_APPROVED_BEFORE_OUTCOMES',outcomes='ONLY_UNDER_SEPARATELY_REGISTERED_EFFICACY',
                owner_approved_on='2026-10-05',
                identity='episode_id=digest(spec_hash,ordered_vintage_ids,first_positive_at); candidate_id=digest(snapshot_without_id)',
                episode_publication='First persistent positive READY observation; id anchors first positive run observation.',
                missing='UNAVAILABLE resets numeric history/persistence; retains episode/consumed lock until observed READY RS<=0.',
                selection_policy='No parameter, benchmark, guard, session, threshold or rearm change from sealed frequency definition.')
    write_new(SPEC,yaml.safe_dump(spec,sort_keys=False,allow_unicode=True).encode())
    report = json.loads((DISCOVERY/'frequency-audit.json').read_bytes())
    events = json.loads((DISCOVERY/'candidate-events.json').read_bytes())['events']
    datasets = [report['own_dataset_id'],report['benchmark_dataset_id']]
    validated = validate_events(events,datasets,report['event_stream_hash'])
    if validated['events'] != 35 or validated['sessions'] != 29 or report['outcome_access'] != 0 or report['paired_contract'] != list(CONTRACT):
        raise ValueError('Original discovery/paired contract mismatch')
    record = dict(schema='h0003_signal_freeze_v1',status='IMMUTABLE_OWNER_APPROVED',registered_on='2026-10-05',
        base_commit=BASE,hypothesis='H0003-r01',hypothesis_sha256=fingerprint(HYPOTHESIS),
        historical_hypothesis='Original DRAFT retained; this decision resolves v1 signal semantics only.',
        spec_path=SPEC.as_posix(),spec_sha256=fingerprint(SPEC),spec_canonical_hash=digest(spec),
        provisional_sha256=fingerprint(PROVISIONAL),parameters=proposed['parameters'],signal_spec_hash=Specification().hash,
        implementation='richping/research_v2/strategy/h0003_leadership.py',
        implementation_sha256=fingerprint('richping/research_v2/strategy/h0003_leadership.py'),
        datasets=dict(SOXX=dict(id=report['own_dataset_id'],hash=report['own_dataset_hash']),
                      QQQ=dict(id=report['benchmark_dataset_id'],hash=report['benchmark_vintage_hash'],
                        hash_domain='digest(canonical detached paired QQQ CloseBar sequence)',
                        capture_hash=report['benchmark_capture_hash'],admission_hash=report['benchmark_admission_hash'],
                        vintage_path=(DISCOVERY/'benchmark-vintage.json').as_posix(),
                        vintage_sha256=fingerprint(DISCOVERY/'benchmark-vintage.json'))),
        paired_contract=list(CONTRACT),benchmark_meaning='QQQ technology/growth benchmark; not entire market',
        window_slots=64,persistence_slots=4,leadership='RS64>0',guard='SOXX_R64>=0',rearm='Observed READY RS64<=0 only',
        episode=spec['episode'],episode_publication=spec['episode_publication'],identity=spec['identity'],missing=spec['missing'],
        discovery_events_path=(DISCOVERY/'candidate-events.json').as_posix(),
        discovery_events_sha256=fingerprint(DISCOVERY/'candidate-events.json'),
        discovery_event_stream_hash=validated['hash'],discovery_frequency_sha256=fingerprint(DISCOVERY/'frequency-audit.json'),
        discovery_trace_chain=report['trace_chain_hash'],discovery_denominators=report['denominators'],
        outcome_access=0,efficacy_calculations=0,profitability='NOT_ESTIMATED',H0001_H0002_modified=False)
    write_new(FREEZE,encode(record))
    protocol = yaml.safe_load(PROTOCOL.read_bytes())
    grid = validate_protocol(protocol)
    paths = subprocess.run(['git','ls-tree','-r','--name-only',BASE],check=True,capture_output=True,text=True).stdout.splitlines()
    preserved = {p:preservation_fingerprint(p) for p in paths if p not in ('.gitattributes','PROJECT_STATUS.md')}
    manifest = dict(schema='h0003_preregistration_manifest_v1',base_commit=BASE,runtime=runtime_identity(),
        bound_files={p.as_posix():preservation_fingerprint(p) for p in BOUND},preserved_files=preserved,
        calendar=grid,calendar_hash=digest(grid),protocol_hash=digest(protocol),freeze_sha256=fingerprint(FREEZE),
        outcome_access=0,efficacy_calculations=0)
    write_new(ROOT/'manifest.json',encode(manifest))
    return manifest


def verify():
    manifest = json.loads((ROOT/'manifest.json').read_bytes())
    if manifest['base_commit'] != BASE or manifest['runtime'] != runtime_identity():
        raise ValueError('Base/runtime mismatch')
    for group in ('bound_files','preserved_files'):
        for p,expected in manifest[group].items():
            if preservation_fingerprint(p) != expected:
                raise ValueError('Frozen/preserved file changed: '+p)
    verify_state()
    protocol = yaml.safe_load(PROTOCOL.read_bytes())
    grid = validate_protocol(protocol)
    record = json.loads(FREEZE.read_bytes())
    spec = yaml.safe_load(SPEC.read_bytes())
    report = json.loads((DISCOVERY/'frequency-audit.json').read_bytes())
    if (digest(protocol),grid,digest(grid),fingerprint(FREEZE),fingerprint(SPEC),digest(spec),fingerprint(HYPOTHESIS),
            fingerprint(record['implementation'])) != (
            manifest['protocol_hash'],manifest['calendar'],manifest['calendar_hash'],manifest['freeze_sha256'],
            record['spec_sha256'],record['spec_canonical_hash'],record['hypothesis_sha256'],record['implementation_sha256']):
        raise ValueError('Freeze/protocol/calendar/source identity mismatch')
    if (record['datasets']['SOXX']['id'],record['datasets']['SOXX']['hash'],record['datasets']['QQQ']['id'],record['datasets']['QQQ']['hash'],
            fingerprint(record['datasets']['QQQ']['vintage_path'])) != (
            report['own_dataset_id'],report['own_dataset_hash'],report['benchmark_dataset_id'],report['benchmark_vintage_hash'],
            record['datasets']['QQQ']['vintage_sha256']):
        raise ValueError('Paired immutable dataset binding mismatch')
    events = json.loads((DISCOVERY/'candidate-events.json').read_bytes())['events']
    validated = validate_events(events,[record['datasets'][k]['id'] for k in ('SOXX','QQQ')],record['discovery_event_stream_hash'])
    if validated['events'] != 35 or validated['sessions'] != 29 or record['signal_spec_hash'] != Specification().hash:
        raise ValueError('Frozen discovery identity mismatch')
    return dict(status='FROZEN_PREREGISTERED_OUTCOMES_NOT_RUN',protocol_hash=manifest['protocol_hash'],
        signal_freeze_sha256=fingerprint(FREEZE),signal_spec_sha256=fingerprint(SPEC),
        discovery_events=validated['events'],discovery_sessions=validated['sessions'],event_stream_hash=validated['hash'],
        calendar_hash=manifest['calendar_hash'],confirmation_sessions=252,confirmation_disposition='PENDING',
        preserved_files=len(manifest['preserved_files']),outcome_access=0,future_price_queries=0,efficacy_calculations=0,
        profitability='NOT_ESTIMATED',next_P0='H0003_FIRST_EFFICACY',
        evaluation_adapter='METADATA_CONTRACT_GATES_ONLY; PAIRED_LABEL_AND_BOOTSTRAP_ADAPTER_NOT_IMPLEMENTED_NOT_EXECUTED')


def run(seal=False):
    with metadata_only() as calls:
        if seal:
            freeze()
        before = {p:fingerprint(p) for p in json.loads((ROOT/'manifest.json').read_bytes())['preserved_files']}
        first,second = verify(),verify()
        if first != second or any(calls.values()) or before != {p:fingerprint(p) for p in before}:
            raise ValueError('Metadata/preservation mismatch or forbidden access')
    report = dict(**first,repeat_equal=True,runs=2,forbidden_call_counts=calls)
    write_new(ROOT/'verification.json',encode(report))
    return report


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--seal',action='store_true')
    print(json.dumps(run(parser.parse_args().seal),indent=2))
