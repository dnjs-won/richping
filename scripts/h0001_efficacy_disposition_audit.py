"""Independently audit the committed ZERO_SIGNAL disposition without price access."""
from contextlib import ExitStack, contextmanager
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from richping.core import canonical, digest
from scripts import h0001_first_entry_efficacy as runner
from scripts.h0001_entry_freeze import immutable

ROOT = runner.ROOT
EVIDENCE = Path('research/data_evidence/h0001-entry-efficacy-audit-20261003')
VERSION = 'H0001_ZERO_SIGNAL_DISPOSITION_AUDIT_V1'
SOURCE = 'scripts/h0001_efficacy_disposition_audit.py'

# observe owns outcome return, MFE and MAE calculations. Dataset.window serves
# both instrument and benchmark prices. Deny all windows, including SOXX controls.
GUARDS = {
    'richping.engine.observe': ('outcome_queries', 'return_calculations', 'mfe_mae_calculations'),
    'richping.evaluation.evaluate_outcome_eligibility': ('outcome_queries',),
    'richping.data.Dataset.window': ('market_price_queries', 'benchmark_queries'),
    'richping.store.Store.load_dataset': ('market_dataset_loads',),
    'richping.research_v2.store.ResearchStore.load_dataset': ('market_dataset_loads',),
    'richping.engine.features': ('return_calculations', 'benchmark_calculations'),
    'richping.evaluation.cohort_returns': ('return_calculations',),
    'richping.evaluation.metrics': ('return_calculations',),
    'richping.evaluation.estimate': ('return_calculations', 'uncertainty_calculations'),
    'richping.evaluation.block_ci': ('uncertainty_calculations',),
}


@contextmanager
def forbidden_calculations():
    counts = {category: 0 for categories in GUARDS.values() for category in categories}

    def forbidden(categories):
        def reject(*args, **kwargs):
            for category in categories:
                counts[category] += 1
            raise AssertionError('ZERO_SIGNAL forbids ' + ','.join(categories))
        return reject

    with ExitStack() as stack:
        for target, categories in GUARDS.items():
            stack.enter_context(patch(target, side_effect=forbidden(categories)))
        yield counts


def read_json(root, path):
    return json.loads((root / path).read_text(encoding='utf-8'))


def audit(root=ROOT):
    # Reuse the frozen evaluator; validate the protocol before independent count
    # and cross-proof checks. No old evidence is written by this audit.
    with runner.no_market_access() as access, forbidden_calculations() as calculations:
        record, verified, _, _ = runner.inputs(root)
        manifest = read_json(root, runner.EVIDENCE / 'evaluation-manifest.json')
        first, second = runner.evaluate(manifest, root), runner.evaluate(manifest, root)
        if canonical(first) != canonical(second):
            raise ValueError('disposition repeat mismatch')
        original = read_json(root, runner.EVIDENCE / 'disposition-report.json')
        original_proof = read_json(root, runner.EVIDENCE / 'offline-proof.json')
        if (first != original or digest(first) != original_proof['report_hash']
                or first['report_id'] != digest({k: v for k, v in first.items() if k != 'report_id'})):
            raise ValueError('committed disposition identity mismatch')
        stream = read_json(root, record['dependencies']['composition']['stream_path'])
        smoke = read_json(root, runner.prereg.COMPOSITION / 'smoke.json')
        fixed = record['dependencies']['fixed_inputs']
        for name in ('daily_id', 'daily_hash', 'intraday_id', 'intraday_hash'):
            if fixed[name] != smoke[name] or fixed[name] != manifest['fixed_inputs'][name]:
                raise ValueError('fixed dataset identity mismatch: ' + name)
        count = len(stream['events'])
        if (count != 0 or count != smoke['candidate_count']
                or smoke['candidate_timestamps'] != [] or first['candidate_timestamps'] != []
                or digest(stream) != first['signal_stream_hash']):
            raise ValueError('independent candidate identity/count mismatch')
        if first['status'] != 'ZERO_SIGNAL' or not all(v is None for v in first['metrics'].values()):
            raise ValueError('ZERO_SIGNAL must have null metrics')
        if any(access.values()) or any(calculations.values()):
            raise ValueError('forbidden outcome/benchmark/calculation access')
        result = {
            'version': VERSION, 'basis_implementation_commit': 'fbef043bbbcded3fe3e80c0fa47fa7ff4c103d68',
            'status': 'COMPLETE_INDEPENDENT_ZERO_SIGNAL_REVALIDATION',
            'protocol_version': record['protocol_version'], 'protocol_hash': verified['protocol_hash'],
            'specification_version': record['dependencies']['executable_spec']['version'],
            'specification_hash': verified['specification_hash'],
            'composer_contract_hash': manifest['composer_contract_hash'],
            'event_stream_hash': digest(stream), 'fixed_inputs': fixed,
            'evaluation_as_of': manifest['evaluation_as_of'], 'candidate_count': count,
            'candidate_timestamps': [], 'disposition': first['status'],
            'reason': first['reason'], 'evaluated_outcomes': 0,
            'label_denominators_by_horizon': first['label_denominators_by_horizon'],
            'signal_denominators': first['signal_denominators'],
            'control_cohort': first['control_cohort'], 'return_metrics': None,
            'MFE': None, 'MAE': None, 'uncertainty': None,
            'profitability': 'NOT_RUN', **access, **calculations,
            'repeat_equal': True, 'runs': 2, 'report_id': first['report_id'],
            'report_hashes': [digest(first), digest(second)],
            'frozen_dependency_files_verified': verified['dependencies_verified'],
            'frozen_strategy_semantics_changed': False,
            'evidence_kind': 'COMMITTED_REAL_SIGNAL_METADATA_AND_FROZEN_DISPOSITION_NO_NEW_MARKET_REPLAY',
            'phase_exit_6': 'INCOMPLETE_NO_INFORMATIVE_EFFICACY',
            'next_P0': 'LONG_HISTORY_PROVIDER_AND_VOLUME_EVIDENCE',
            'forbidden_callable_sites': list(GUARDS),
            'audit_source_LF_sha256': sha256((root / SOURCE).read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
        }
        return result, first


def main():
    proof, report = audit()
    immutable(ROOT / EVIDENCE / 'execution-audit.json', proof)
    immutable(ROOT / EVIDENCE / 'disposition-report.json', report)
    immutable(ROOT / EVIDENCE / 'denominator-report.json', {
        'candidate_count': proof['candidate_count'], 'signal': proof['signal_denominators'],
        'labels_by_horizon': proof['label_denominators_by_horizon'],
        'control_cohort': proof['control_cohort'],
    })
    print(canonical({k: proof[k] for k in ('status', 'candidate_count', 'disposition',
                                         'report_hashes', 'outcome_queries', 'benchmark_queries',
                                         'return_calculations', 'mfe_mae_calculations')}))


if __name__ == '__main__':
    main()
