"""Conditionally owner-approved H0004 final signal freeze; metadata-only protocol."""
from argparse import ArgumentParser
from contextlib import contextmanager,ExitStack
from importlib.metadata import version
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
from unittest.mock import patch
import yaml

from richping.core import digest
from richping.research_v2.contracts import payload
from richping.research_v2.strategy.h0004_segment_compression import Specification
from richping.research_v2.strategy.h0004_experiment import VERSION,calendar_contract,validate_events
from scripts.h0004_segment_frequency import ROOT as FREQUENCY,BASE,SPEC as PROPOSED,verify_manifest
from scripts.h0004_segment_verify import verify as verify_frequency
from scripts.h0004_frequency_audit import encode,write_new,fingerprint,preserved_bytes,preserved_raw,no_outcomes

ROOT = Path('research/data_evidence/h0004-freeze-preregistration-20261005')
SPEC = Path('research/strategy_specs/H0004-r01-frozen-v1.yaml')
FREEZE = Path('research/decision_records/H0004-signal-freeze-v1.json')
PROTOCOL = Path('research/decision_records/H0004-efficacy-preregistration-v1.yaml')
BOUND = [SPEC,FREEZE,PROTOCOL,Path('scripts/h0004_signal_preregister.py'),
         Path('richping/research_v2/strategy/h0004_experiment.py'),
         Path('scripts/h0004_segment_verify.py')]


def runtime_identity():
    return dict(python=sys.version.split()[0],exchange_calendars=version('exchange_calendars'),PyYAML=version('PyYAML'))


@contextmanager
def metadata_only():
    counts = {k:0 for k in ('price_load','signal_replay','database')}
    def reject(category):
        def denied(*args,**kwargs):
            counts[category] += 1
            raise AssertionError('H0004 registration forbids '+category)
        return denied
    with no_outcomes() as outcome_calls,ExitStack() as stack:
        for target,category in {
            'scripts.h0004_segment_frequency.load_admitted':'price_load',
            'scripts.h0004_segment_frequency.replay':'signal_replay',
            'richping.research_v2.market_data.MarketDataset.from_records':'price_load',
            'richping.research_v2.strategy.h0004_segment_compression.CompressionStream.accept':'signal_replay',
            'sqlite3.connect':'database'}.items():
            stack.enter_context(patch(target,side_effect=reject(category)))
        yield dict(metadata=counts,outcomes=outcome_calls)


def validate_protocol(body):
    required = {'sample','horizons','label','baseline','costs','discovery','confirmation',
                'evidence_floor','uncertainty','multiple_testing','disposition'}
    if not required<=body.keys() or body.get('version')!=VERSION or body.get('outcome_access_this_action')!='FORBIDDEN':
        raise ValueError('Incomplete protocol')
    if (body['horizons']['primary_slots'],body['horizons']['secondary_slots'],body['comparators'],
            body['baseline']['name'],body['costs']['profitability'])!=(16,[],[],'ZERO_DIRECTION_NULL','NOT_ESTIMATED'):
        raise ValueError('Primary directional scope changed')
    grid = calendar_contract()
    c = body['confirmation']
    if (c['embargo_start'],c['embargo_end'],c['anchor_start'],c['anchor_end'],c['official_sessions'],
            c['followup_end'],c['terminal_receipt_deadline'],c['prefix_origin'],c['asynchronous'],c['project_blocker'])!=(
            grid['embargo'][0],grid['embargo'][-1],grid['anchors'][0],grid['anchors'][-1],252,
            grid['followup'][-1],'2027-10-21T20:00:00-04:00','2026-05-05',True,False):
        raise ValueError('Confirmation/stopping calendar changed')
    f,u,m = body['evidence_floor'],body['uncertainty'],body['multiple_testing']
    if (f['complete_events'],f['distinct_candidate_sessions'],f['occupied_fixed_10_session_blocks'],
            u['block_sessions'],u['replicates'],u['seed'],m['primary_families'],m['alpha'],m['signal_trials'])!=(
            40,20,8,20,10000,202610054,1,.05,2):
        raise ValueError('Floor/dependence/multiplicity changed')
    return grid


def seal():
    frequency = verify_frequency()
    if not frequency['mechanically_executable']:
        raise ValueError('Zero signal requires blocker routing, not final freeze')
    proposed = yaml.safe_load(PROPOSED.read_bytes())
    spec = {**proposed,'schema_version':'h0004_frozen_signal_v1','version':'H0004_COMPRESSION_BREAKOUT_SIGNAL_V1',
        'status':'FROZEN_OWNER_APPROVED_BEFORE_OUTCOMES','outcomes':'ONLY_UNDER_SEPARATELY_REGISTERED_EFFICACY',
        'owner_approved_on':'2026-10-05','selected_trial':'TRIAL_2_SEGMENT_CONDITIONED_REFERENCE',
        'signal_spec_hash':Specification().content_hash,
        'implementation':'richping/research_v2/strategy/h0004_segment_compression.py',
        'owner_authority':'Explicit user semantic correction and conditional final freeze; conditions verified without outcomes.'}
    write_new(SPEC,yaml.safe_dump(spec,sort_keys=False,allow_unicode=True).encode())
    record = dict(schema='h0004_signal_freeze_v1',status='IMMUTABLE_OWNER_APPROVED',registered_on='2026-10-05',
        hypothesis='H0004-r01',hypothesis_sha256=fingerprint('research/hypotheses/H0004-r01.yaml'),
        historical_hypothesis='Original hypothesis DRAFT retained; this decision resolves final v1 signal reference.',
        spec_path=SPEC.as_posix(),spec_sha256=fingerprint(SPEC),spec_hash=Specification().content_hash,
        implementation=spec['implementation'],implementation_sha256=fingerprint(spec['implementation']),
        selected_trial=spec['selected_trial'],signal_trials=2,trial1_preserved=True,
        parameters=payload(Specification()),frequency_report=(FREQUENCY/'frequency-audit.json').as_posix(),
        frequency_report_sha256=fingerprint(FREQUENCY/'frequency-audit.json'),
        candidate_events=(FREQUENCY/'candidate-events.json').as_posix(),candidate_events_sha256=fingerprint(FREQUENCY/'candidate-events.json'),
        event_stream_hash=frequency['event_stream_hash'],range_stream_hash=frequency['range_stream_hash'],
        counts=frequency['counts'],segments=frequency['segments'],outcome_access=0,efficacy_calculations=0,
        profitability='NOT_ESTIMATED',owner_conditional_requirements_satisfied=True,
        market_closure='H0004 v1 studies compression and breakout across consecutive admitted trading slots, not continuous wall-clock hours. A range may therefore span or survive a market closure.')
    write_new(FREEZE,encode(record))
    protocol = yaml.safe_load(PROTOCOL.read_bytes())
    grid = validate_protocol(protocol)
    protected = {}
    raw = subprocess.run(['git','archive','--format=tar',BASE],check=True,capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(raw)) as tree:
        for member in tree.getmembers():
            if not member.isfile() or member.name in ('.gitattributes','PROJECT_STATUS.md'): continue
            expected = preserved_raw(member.name,tree.extractfile(member).read())
            if preserved_bytes(member.name)!=expected: raise ValueError('Prior Git file changed: '+member.name)
            protected[member.name] = expected
    manifest = dict(schema='h0004_preregistration_manifest_v1',base_commit=BASE,runtime=runtime_identity(),
        bound_files={p.as_posix():fingerprint(p) for p in BOUND},preserved_files=protected,
        calendar=grid,calendar_hash=digest(grid),protocol_hash=digest(protocol),signal_freeze_sha256=fingerprint(FREEZE),
        outcome_access=0,efficacy_calculations=0)
    write_new(ROOT/'manifest.json',encode(manifest))
    return manifest


def verify():
    manifest = json.loads((ROOT/'manifest.json').read_bytes())
    if manifest['base_commit']!=BASE or manifest['runtime']!=runtime_identity(): raise ValueError('Runtime/base changed')
    for group in ('bound_files','preserved_files'):
        for path,expected in manifest[group].items():
            actual = preserved_bytes(path) if group=='preserved_files' else fingerprint(path)
            if actual!=expected: raise ValueError('Frozen/preserved dependency changed: '+path)
    frequency = verify_frequency()
    protocol = yaml.safe_load(PROTOCOL.read_bytes())
    grid = validate_protocol(protocol)
    record = json.loads(FREEZE.read_bytes())
    spec = yaml.safe_load(SPEC.read_bytes())
    events = json.loads(Path(record['candidate_events']).read_bytes())['events']
    report = json.loads(Path(record['frequency_report']).read_bytes())
    validated = validate_events(events,record['event_stream_hash'],report['dataset_id'])
    if (digest(protocol),grid,digest(grid),fingerprint(FREEZE),fingerprint(SPEC),fingerprint(record['implementation']),
            fingerprint(record['candidate_events']),fingerprint(record['frequency_report']),record['parameters'],
            spec['signal_spec_hash'],validated['hash'])!=(
            manifest['protocol_hash'],manifest['calendar'],manifest['calendar_hash'],manifest['signal_freeze_sha256'],
            record['spec_sha256'],record['implementation_sha256'],record['candidate_events_sha256'],
            record['frequency_report_sha256'],payload(Specification()),frequency['spec_hash'],frequency['event_stream_hash']):
        raise ValueError('Freeze/protocol/input-stream identity mismatch')
    return dict(schema='h0004_signal_preregistration_verification_v1',status='FROZEN_PREREGISTERED_OUTCOMES_NOT_RUN',
        protocol_hash=manifest['protocol_hash'],signal_freeze_sha256=fingerprint(FREEZE),
        signal_spec_sha256=fingerprint(SPEC),event_stream_hash=validated['hash'],counts=frequency['counts'],
        parameter_trials=2,primary_horizon_slots=16,confirmation_sessions=252,confirmation_status='PENDING_ASYNCHRONOUS',
        outcome_access=0,future_price_queries=0,efficacy_calculations=0,profitability='NOT_ESTIMATED',
        preserved_files=len(manifest['preserved_files']),next_P0='H0004_FIRST_EFFICACY',
        evaluation_adapter='METADATA_GATES_ONLY; NONEMPTY_LABEL_AND_TERMINAL_STATISTICS_ADAPTER_NOT_IMPLEMENTED_NOT_EXECUTED')


def run(create=False):
    with metadata_only() as calls:
        if create: seal()
        first,second = verify(),verify()
        if first!=second or any(v for group in calls.values() for v in group.values()):
            raise ValueError('Forbidden access or nondeterministic metadata verification')
    result = dict(**first,repeat_equal=True,forbidden_call_counts=calls)
    write_new(ROOT/'verification.json',encode(result))
    return result


if __name__=='__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--seal',action='store_true')
    print(json.dumps(run(parser.parse_args().seal),indent=2))
