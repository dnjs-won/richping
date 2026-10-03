"""Execute the frozen current empty-stream disposition, without reading outcomes.

Nonempty streams require a separately implemented exact protocol adapter. This
runner fails closed rather than manufacturing labels or a numeric efficacy result.
"""
from argparse import ArgumentParser
from contextlib import ExitStack, contextmanager
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

import yaml

from richping.core import canonical, digest, timestamp
from scripts import h0001_entry_efficacy_preregister as prereg
from scripts.h0001_entry_freeze import immutable

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path('research/data_evidence/h0001-first-entry-efficacy-20261003')
VERSION = 'H0001_FIXED_EMPTY_STREAM_DISPOSITION_V1'
BASIS_COMMIT = '13f719b56980a43fbace2a003b8c78331fa0c210'
SOURCES = ('scripts/h0001_first_entry_efficacy.py',
           'scripts/h0001_entry_efficacy_preregister.py',
           'scripts/h0001_entry_freeze.py', 'richping/core.py')


def source_hashes(root):
    return {p: sha256((root / p).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            for p in SOURCES}


@contextmanager
def no_market_access():
    """Abort attempted network, database or market-loader access; count attempts."""
    audit = dict.fromkeys(('network_calls', 'database_reads', 'market_dataset_loads',
                          'outcome_queries', 'returns_calculated'), 0)

    def blocked(category):
        def reject(*args, **kwargs):
            audit[category] += 1
            raise AssertionError('empty-stream disposition forbids ' + category)
        return reject

    with ExitStack() as guards:
        for target, category in (
            ('socket.socket.connect', 'network_calls'),
            ('socket.create_connection', 'network_calls'),
            ('urllib.request.urlopen', 'network_calls'),
            ('sqlite3.connect', 'database_reads'),
            ('richping.research_v2.daily_data.load_daily', 'market_dataset_loads'),
            ('richping.research_v2.daily_data.fetch_daily', 'market_dataset_loads'),
            ('richping.research_v2.real_data.fetch_capture', 'market_dataset_loads'),
        ):
            guards.enter_context(patch(target, blocked(category)))
        yield audit


def inputs(root):
    record = yaml.safe_load((root / prereg.RECORD).read_text(encoding='utf-8'))
    verified = prereg.verify(record, root)
    composition = record['dependencies']['composition']
    stream = json.loads((root / composition['stream_path']).read_text(encoding='utf-8'))
    contract = json.loads((root / prereg.COMPOSITION / 'composition-contract.json').read_text(encoding='utf-8'))
    freeze = yaml.safe_load((root / composition['record']).read_text(encoding='utf-8'))
    if contract['hash'] != composition['contract_hash'] or freeze['composer_contract_hash'] != contract['hash']:
        raise ValueError('composer dependency mismatch')
    if stream['version'] != contract['version']:
        raise ValueError('stream composer version mismatch')
    denominator = json.loads((root / prereg.COMPOSITION / 'denominator-report.json').read_text(encoding='utf-8'))
    if denominator['denominators']['candidate_emitted'] != len(stream['events']):
        raise ValueError('candidate denominator mismatch')
    return record, verified, stream, denominator


def manifest_hash(value):
    return digest({k: v for k, v in value.items() if k != 'manifest_hash'})


def make_manifest(evaluation_as_of, root=ROOT):
    record, verified, _, _ = inputs(root)
    as_of = timestamp(evaluation_as_of)
    if as_of < timestamp(record['registered_at']):
        raise ValueError('evaluation predates preregistration')
    manifest = {
        'version': VERSION, 'basis_commit': BASIS_COMMIT,
        'evaluation_as_of': as_of.isoformat(), 'symbol': 'SOXX',
        'partition': 'DISCOVERY', 'scope': 'FIXED_CURRENT_EMPTY_STREAM_ONLY',
        'protocol_hash': verified['protocol_hash'],
        'specification_hash': verified['specification_hash'],
        'composer_contract_hash': record['dependencies']['composition']['contract_hash'],
        'signal_stream_hash': verified['signal_stream_hash'],
        'fixed_inputs': record['dependencies']['fixed_inputs'],
        'source_LF_sha256': source_hashes(root),
        'nonempty_behavior': 'FAIL_CLOSED_EXACT_LABEL_ADAPTER_NOT_IMPLEMENTED',
        'outcome_access': 'FORBIDDEN', 'profitability': 'NOT_RUN',
    }
    manifest['manifest_hash'] = manifest_hash(manifest)
    return manifest


def evaluate(manifest, root=ROOT):
    """No price/action/control loader or return calculation exists in this path."""
    if manifest.get('manifest_hash') != manifest_hash(manifest):
        raise ValueError('evaluation manifest hash mismatch')
    expected = make_manifest(manifest['evaluation_as_of'], root)
    if manifest != expected:
        raise ValueError('evaluation manifest dependency mismatch')
    record, verified, stream, denominator = inputs(root)
    if stream['events']:
        raise ValueError('nonempty stream requires exact frozen label adapter; fail closed')
    horizons = record['label_contract']['forward_horizons']
    labels = {str(h): {'total': 0, 'complete': 0, 'pending': 0, 'unresolved': 0,
                      'reason': 'NO_CANDIDATE_EVENTS'} for h in horizons}
    report = {
        'version': VERSION, 'manifest_hash': manifest['manifest_hash'],
        'evaluation_as_of': manifest['evaluation_as_of'],
        'protocol_hash': verified['protocol_hash'],
        'specification_hash': verified['specification_hash'],
        'composer_contract_hash': manifest['composer_contract_hash'],
        'signal_stream_hash': verified['signal_stream_hash'],
        'status': 'ZERO_SIGNAL', 'reason': 'NO_IMMUTABLE_INITIAL_ENTRY_CANDIDATE_EVENTS',
        'scope': 'INITIAL_ENTRY_OPPORTUNITY_DISCOVERY_ONLY',
        'candidate_count': 0, 'candidate_timestamps': [],
        'candidate_event_ids': [], 'candidate_payload_hashes': [],
        'label_denominators_by_horizon': labels,
        'control_cohort': {'status': 'NOT_EVALUATED_NO_CANDIDATES',
                           'eligible_count': None, 'labels_read': 0},
        'confirmation': {'status': 'NOT_STARTED_NOT_EVALUATED',
                         **record['chronology']['confirmation']},
        'metrics': {'primary_excess': None, 'primary_CI': None,
                    'forward_returns': None, 'MFE': None, 'MAE': None,
                    'benchmark': None, 'excess': None},
        'inference': 'NOT_RUN_ZERO_SIGNAL_IS_NEITHER_PASS_NOR_REJECT',
        'profitability': 'NOT_RUN', 'outcome_lookup': 'NONE',
        'phase_exit_6': 'INCOMPLETE_NO_INFORMATIVE_EFFICACY',
        'signal_denominators': denominator,
    }
    report['report_id'] = digest(report)
    return report


def execute(root=ROOT, evidence=EVIDENCE):
    with no_market_access() as audit:
        directory = root / evidence
        manifest = json.loads((directory / 'evaluation-manifest.json').read_text(encoding='utf-8'))
        first, second = evaluate(manifest, root), evaluate(manifest, root)
        if canonical(first) != canonical(second) or any(audit.values()):
            raise ValueError('nondeterministic or forbidden-access disposition')
        record, verified, _, _ = inputs(root)
        proof = {
            'version': VERSION, 'status': 'COMPLETE_FIXED_STREAM_ZERO_SIGNAL_DISPOSITION',
            'manifest_hash': manifest['manifest_hash'], 'report_id': first['report_id'],
            'report_hash': digest(first), 'repeat_equal': True, 'offline_runs': 2,
            **verified, **audit, 'network_disabled': True,
            'market_action_benchmark_outcome_reads': 0,
            'profitability': 'NOT_RUN', 'outcome_lookup': 'NONE',
            'frozen_primitives_mutated': False, 'specification_mutated': False,
            'evidence_basis': 'EXISTING_COMMITTED_REAL_REPLAY_METADATA_NO_NEW_MARKET_REPLAY',
            'phase_exit_6': first['phase_exit_6'],
        }
        immutable(directory / 'evaluation-contract.json', record)
        immutable(directory / 'disposition-report.json', first)
        immutable(directory / 'denominator-report.json', {
            'signal': first['signal_denominators'],
            'candidate_count': 0, 'labels_by_horizon': first['label_denominators_by_horizon'],
            'control_cohort': first['control_cohort'],
        })
        immutable(directory / 'offline-proof.json', proof)
        immutable(directory / 'smoke.json', proof)
        return proof


def main(argv=None):
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--register-as-of', help='Seal immutable evaluation manifest before disposition.')
    args = parser.parse_args(argv)
    if args.register_as_of:
        with no_market_access():
            manifest = make_manifest(args.register_as_of)
            immutable(ROOT / EVIDENCE / 'evaluation-manifest.json', manifest)
        print(canonical(manifest))
    else:
        print(canonical(execute()))


if __name__ == '__main__':
    main()
