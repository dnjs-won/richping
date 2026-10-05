"""Seal/verify H0004 directional infrastructure without opening any real prices."""
from argparse import ArgumentParser
from contextlib import contextmanager, ExitStack
import io
import json
from pathlib import Path
import subprocess
import tarfile
from unittest.mock import patch
import yaml

from richping.core import digest
from richping.research_v2.contracts import payload
from richping.research_v2.strategy import h0004_directional_evaluator as adapter
from richping.research_v2.strategy.h0004_experiment import calendar_contract
from scripts.h0004_frequency_audit import encode,write_new,fingerprint,preserved_raw,preserved_bytes,SOURCE
from scripts.h0004_signal_preregister import verify as verify_frozen, metadata_only, FREEZE,PROTOCOL,SPEC
from scripts.h0004_segment_frequency import ROOT as FREQUENCY
from scripts.h0004_verify import junit

BASE = '292dd6767b8da950eb8b15ee4e413f0e5ba32e6a'
ROOT = Path('research/data_evidence/h0004-preaccess-20261005')
EVENTS = FREQUENCY/'candidate-events.json'
BOUND = [Path('richping/research_v2/strategy/h0004_directional_evaluator.py'),
         Path('scripts/h0004_discovery_access.py'),Path('scripts/h0004_preaccess.py'),
         Path('scripts/h0004_preaccess_verify.py'),Path('scripts/h0004_preaccess_fixtures.py'),
         Path('tests/test_h0004_directional_evaluator.py'),
         Path('docs/H0004_PREACCESS_EVALUATOR.md')]


def frozen_binding():
    frozen = verify_frozen()
    # Already-published anchors only. No schedule mapping or endpoint checking.
    events = json.loads(EVENTS.read_bytes())['events']
    anchors = adapter.anchors_from_frozen(events)
    binding = adapter.Binding(adapter.Scope.DISCOVERY_EXPLORATORY,adapter.DATASET_ID,adapter.DATASET_HASH,
        frozen['event_stream_hash'],digest(payload(anchors)),fingerprint(SOURCE/'admission.json'),
        calendar_hash=digest(calendar_contract()),semantics_hash=digest(adapter.semantics()))
    binding.validate()
    if len(anchors)!=48 or len({a.session for a in anchors})!=29:
        raise ValueError('Frozen denominator changed')
    return binding,anchors


@contextmanager
def zero_real_outcomes():
    """Reject real adapter/source access, while fixture arithmetic is allowed."""
    counters = dict(forward_price_queries=0,discovery_label_reads=0,confirmation_label_reads=0,
        return_calculations=0,efficacy_aggregations=0,profitability_calculations=0,
        real_dataset_loads=0,real_endpoint_readiness_probes=0)
    original_label = adapter.DirectionalEvaluator.label
    original_aggregate = adapter.DirectionalEvaluator.aggregate
    original_ready = adapter.DirectionalEvaluator.readiness
    def guard(original,category):
        def wrapped(self,*args,**kwargs):
            if not self.binding.synthetic:
                counters[category] += 1
                raise AssertionError('Pre-access action forbids real '+category)
            return original(self,*args,**kwargs)
        return wrapped
    def forbid(*args,**kwargs):
        counters['real_dataset_loads'] += 1
        raise AssertionError('Pre-access action forbids real discovery loader')
    with metadata_only() as common,ExitStack() as stack:
        stack.enter_context(patch.object(adapter.DirectionalEvaluator,'label',guard(original_label,'discovery_label_reads')))
        stack.enter_context(patch.object(adapter.DirectionalEvaluator,'aggregate',guard(original_aggregate,'efficacy_aggregations')))
        stack.enter_context(patch.object(adapter.DirectionalEvaluator,'readiness',guard(original_ready,'real_endpoint_readiness_probes')))
        stack.enter_context(patch('scripts.h0004_discovery_access.open_discovery',side_effect=forbid))
        stack.enter_context(patch('scripts.h0004_discovery_access.load_admitted',side_effect=forbid))
        yield dict(real_H0004=counters,shared_forbidden=common)


def seal():
    binding,anchors = frozen_binding()
    protected = {}
    archive = subprocess.run(['git','archive','--format=tar',BASE],check=True,capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        for member in tree.getmembers():
            if not member.isfile() or member.name in ('.gitattributes','PROJECT_STATUS.md'): continue
            expected = preserved_raw(member.name,tree.extractfile(member).read())
            if preserved_bytes(member.name)!=expected: raise ValueError('Protected BASE file changed: '+member.name)
            protected[member.name] = expected
    manifest = dict(schema='h0004_preaccess_manifest_v1',status='SEALED_BEFORE_REAL_OUTCOMES',
        base_commit=BASE,binding=payload(binding),signal_freeze_sha256=fingerprint(FREEZE),
        efficacy_protocol_sha256=fingerprint(PROTOCOL),signal_spec_sha256=fingerprint(SPEC),
        candidate_file_sha256=fingerprint(EVENTS),candidate_count=48,candidate_sessions=29,signal_trials=2,
        dataset_files={str(SOURCE/n).replace('\\','/'):fingerprint(SOURCE/n) for n in ('intraday-vintage.json','admission.json')},
        source_hashes={p.as_posix():fingerprint(p) for p in BOUND},protected_files=protected,
        calendar=calendar_contract(),calendar_hash=digest(calendar_contract()),semantics=adapter.semantics(),
        semantics_hash=digest(adapter.semantics()),real_outcome_access=0,actual_endpoint_probe=0,
        authorization='Separate H0004_DISCOVERY_EFFICACY_EXECUTION action only after independent PASS receipt',
        confirmation='PENDING_ASYNCHRONOUS; future terminal admission/seal required',
        runtime=__import__('scripts.h0004_signal_preregister',fromlist=['runtime_identity']).runtime_identity())
    write_new(ROOT/'manifest.json',encode(manifest))
    return manifest


def verify_manifest():
    manifest = json.loads((ROOT/'manifest.json').read_bytes())
    for group in ('source_hashes','dataset_files','protected_files'):
        for path,expected in manifest[group].items():
            actual = preserved_bytes(path) if group=='protected_files' else fingerprint(path)
            if actual!=expected: raise ValueError('Pre-access sealed dependency changed: '+path)
    binding,anchors = frozen_binding()
    if (manifest['binding'],manifest['calendar_hash'],manifest['semantics_hash'],manifest['calendar'],
            manifest['semantics'],manifest['signal_freeze_sha256'],manifest['efficacy_protocol_sha256'],
            manifest['candidate_file_sha256'])!=(payload(binding),digest(calendar_contract()),digest(adapter.semantics()),
            calendar_contract(),adapter.semantics(),fingerprint(FREEZE),fingerprint(PROTOCOL),fingerprint(EVENTS)):
        raise ValueError('Frozen pre-access binding changed')
    if manifest['base_commit']!=BASE or manifest['candidate_count']!=48 or manifest['real_outcome_access']!=0:
        raise ValueError('Pre-access manifest identity changed')
    from scripts.h0004_signal_preregister import runtime_identity
    if manifest['runtime']!=runtime_identity(): raise ValueError('Sealed runtime changed')
    return manifest,binding,anchors


class DiscoveryPermit:
    """Rechecks the immutable independent PASS and action before every real access."""
    def __init__(self, action):
        if action!='H0004_DISCOVERY_EFFICACY_EXECUTION':
            raise PermissionError('This action cannot open discovery outcomes')
        self.action = action

    def authorize(self):
        manifest,binding,anchors = verify_manifest()
        proof = json.loads((ROOT/'verification.json').read_bytes())
        if (proof['status']!='PASS_PREACCESS_NO_REAL_OUTCOMES' or proof['manifest_sha256']!=fingerprint(ROOT/'manifest.json')
                or proof['source_hashes']!=manifest['source_hashes'] or proof['real_outcome_access']!=0):
            raise PermissionError('Independent pre-access PASS missing or mismatched')
        # Control-plane assertion prevents this pre-access action activating itself.
        main = subprocess.run(['git','show','main:PROJECT_CONTROL.yaml'],check=True,capture_output=True).stdout
        control = yaml.safe_load(main)
        if control['next_action']['id']!=self.action:
            raise PermissionError('Canonical action is not discovery execution')
        return binding,anchors


def run(create=False):
    with zero_real_outcomes() as calls:
        if create: seal()
        from scripts.h0004_preaccess_verify import verify
        result = verify()
    if any(v for v in calls['real_H0004'].values()) or any(v for g in calls['shared_forbidden'].values() for v in g.values()):
        raise ValueError('Forbidden real research access')
    write_new(ROOT/'outcome-access-audit.json',encode(dict(schema='h0004_preaccess_zero_access_v1',
        counters=calls,real_outcome_access=0,synthetic_arithmetic='Separate SYNTHETIC: namespaces only',
        real_candidate_endpoint_readiness='NOT_PROBED',real_candidate_count=48)))
    return result


if __name__=='__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--seal',action='store_true')
    print(json.dumps(run(parser.parse_args().seal),indent=2))
