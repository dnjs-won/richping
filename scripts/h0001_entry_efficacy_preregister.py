"""Freeze/verify opportunity protocol using only committed contracts and signal metadata.

No evaluator, market input loader, label query or performance calculation lives here.
"""
from argparse import ArgumentParser
from contextlib import ExitStack
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

import yaml

from richping.core import canonical, digest, sessions, timestamp
from richping.research_v2.strategy.h0001_spec import H0001Specification
from scripts.h0001_entry_freeze import immutable

ROOT = Path(__file__).resolve().parents[1]
RECORD = Path('research/decision_records/H0001-entry-efficacy-preregistration-v1.yaml')
EVIDENCE = Path('research/data_evidence/h0001-entry-efficacy-preregistration-20261003')
COMPOSITION = Path('research/data_evidence/h0001-entry-composition-20261003')
FROZEN_PROTOCOL_HASH = '074255189630fa625c4d40eb2f344fb7767d2c8f305f22c9e4c2a608e93e944c'


def protocol_hash(record):
    value = deepcopy(record)
    value.pop('contract_hash')
    return digest(value)


def dependency_manifest(root=ROOT):
    old = yaml.safe_load((root / 'research/decision_records/H0001-entry-composition-freeze-v1.yaml').read_text(encoding='utf-8'))
    paths = set(old['source_LF_sha256']) | {
        'research/decision_records/H0001-entry-composition-freeze-v1.yaml',
        'research/hypotheses/H0001-r03.yaml',
        'research/strategy_specs/H0001-r03-draft.yaml',
        'richping/research_v2/strategy/h0001_spec.py',
        'richping/research_v2/strategy/entry_composition.py',
        'richping/evaluation.py',
    } | {str(COMPOSITION / name).replace('\\', '/') for name in (
        'composition-contract.json', 'candidate-events.json', 'denominator-report.json',
        'offline-proof.json', 'smoke.json', 'zero-signal-diagnostic.json')}
    return {p: sha256((root / p).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in sorted(paths)}


def verify(record, root=ROOT):
    """Fail closed on protocol/dependency changes, preserving the v13 signal identity."""
    if record['contract_hash'] != FROZEN_PROTOCOL_HASH or record['contract_hash'] != protocol_hash(record):
        raise ValueError('protocol hash mismatch')
    if record['source_LF_sha256'] != dependency_manifest(root):
        raise ValueError('frozen dependency mutation')
    required = {'scope', 'chronology', 'label_contract', 'comparison', 'costs',
                'uncertainty', 'disposition', 'missing_outcomes', 'multiple_testing',
                'execution_admission', 'decision_scopes'}
    if not required <= record.keys():
        raise ValueError('incomplete preregistration')
    if (record['outcome_lookup'], record['profitability'], record['performance_information_used']) != ('NONE', 'NOT_RUN', 'NONE'):
        raise ValueError('outcomes forbidden during preregistration')
    if record['scope']['sample_unit'] != 'IMMUTABLE_INITIAL_ENTRY_CANDIDATE_EVENT':
        raise ValueError('opportunity scope required')
    label = record['label_contract']
    if label['forward_horizons'] != [4, 16, 64, 192, 320] or label['primary_horizon'] != 64:
        raise ValueError('frozen horizons changed')
    if record['multiple_testing']['primary_tests'] != 1 or record['costs']['applied'] is not False:
        raise ValueError('single gross opportunity experiment required')
    start = record['chronology']['confirmation']['start_session']
    end = record['chronology']['confirmation']['end_session']
    if start <= timestamp(record['registered_at']).date().isoformat() or len(sessions(start, end)) != 126:
        raise ValueError('confirmation must be fixed future chronological window')
    expected = sessions('2026-10-05', end)
    if record['chronology']['embargo']['sessions'] != expected[:5] or start != expected[5]:
        raise ValueError('embargo/confirmation boundary mismatch')
    spec_ref = record['dependencies']['executable_spec']
    spec = H0001Specification.load(root / spec_ref['path'])
    if (spec.unpack()['specification_version'], spec.specification_hash) != (spec_ref['version'], spec_ref['canonical_hash']):
        raise ValueError('specification dependency mismatch')
    stream = json.loads((root / record['dependencies']['composition']['stream_path']).read_text(encoding='utf-8'))
    if digest(stream) != record['dependencies']['composition']['stream_hash']:
        raise ValueError('signal stream dependency mismatch')
    if len(stream['events']) != record['prior_exposure']['candidates']:
        raise ValueError('prior signal exposure mismatch')
    return {'protocol_hash': record['contract_hash'], 'specification_hash': spec.specification_hash,
            'unresolved_paths': len(spec.unresolved_fields), 'signal_stream_hash': digest(stream),
            'prior_candidate_count': len(stream['events']), 'confirmation_sessions': len(sessions(start, end)),
            'dependencies_verified': len(record['source_LF_sha256'])}


def forbidden(*args, **kwargs):
    raise AssertionError('market/network/outcome access forbidden during preregistration')


def main(argv=None):
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', action='store_true', help='Seal a pending draft once; frozen records are never overwritten.')
    args = parser.parse_args(argv)
    with ExitStack() as guards:
        for target in ('socket.socket.connect', 'socket.create_connection', 'urllib.request.urlopen',
                       'sqlite3.connect', 'richping.research_v2.daily_data.load_daily',
                       'richping.research_v2.daily_data.fetch_daily', 'richping.research_v2.real_data.fetch_capture'):
            guards.enter_context(patch(target, forbidden))
        path = ROOT / RECORD
        record = yaml.safe_load(path.read_text(encoding='utf-8'))
        if record['contract_hash'] == 'PENDING_FREEZE':
            if not args.freeze:
                raise ValueError('record is not yet frozen')
            record['registered_at'] = datetime.now(UTC).isoformat()
            record['source_LF_sha256'] = dependency_manifest()
            record['contract_hash'] = protocol_hash(record)
            verify(record)  # Validate complete protocol before replacing the draft.
            path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True), encoding='utf-8')
        original_bytes = path.read_bytes()
        first, second = verify(record), verify(record)
        if first != second or path.read_bytes() != original_bytes:
            raise ValueError('non-deterministic or mutated preregistration')
        immutable(ROOT / EVIDENCE / 'evaluation-contract.json', record)
        proof = {**first, 'status': 'COMPLETE_PREREGISTRATION_ONLY',
                 'record_LF_sha256': sha256(original_bytes.replace(b'\r\n', b'\n')).hexdigest(),
                 'repeat_equal': True, 'verification_runs': 2,
                 'network_calls': 0, 'network_disabled': True, 'database_reads': 0,
                 'market_dataset_loads': 0, 'outcome_queries': 0, 'returns_calculated': 0,
                 'outcomes': 'NOT_RUN', 'profitability': 'NOT_RUN',
                 'specification_mutated': False, 'frozen_primitives_mutated': False,
                 'next_action': 'H0001_FIRST_ENTRY_EFFICACY',
                 'phase_exit_6': 'INCOMPLETE_NO_EFFICACY_EXECUTION'}
        immutable(ROOT / EVIDENCE / 'offline-proof.json', proof)
        immutable(ROOT / EVIDENCE / 'smoke.json', proof)
        print(canonical(proof))


if __name__ == '__main__':
    main()
