"""Independent committed-stream cross-checks and outcome-free callable guards."""
from pathlib import Path

import pytest

import richping.data
import richping.engine
import richping.evaluation
from scripts import h0001_efficacy_disposition_audit as audit


def test_actual_zero_disposition_matches_committed_report_twice_without_old_writes():
    old_files = list((audit.ROOT / audit.runner.EVIDENCE).iterdir())
    before = {p: p.read_bytes() for p in old_files}
    first, report1 = audit.audit()
    second, report2 = audit.audit()
    saved = audit.read_json(audit.ROOT, audit.EVIDENCE / 'execution-audit.json')
    assert first == second == saved and report1 == report2
    assert first['report_hashes'] == [first['report_hashes'][0]] * 2
    assert first['candidate_count'] == first['evaluated_outcomes'] == 0
    assert first['candidate_timestamps'] == []
    for category in ('outcome_queries', 'benchmark_queries', 'return_calculations',
                     'mfe_mae_calculations', 'benchmark_calculations', 'uncertainty_calculations'):
        assert first[category] == 0
    for metric in ('return_metrics', 'MFE', 'MAE', 'uncertainty'):
        assert first[metric] is None
    assert {p: p.read_bytes() for p in old_files} == before
    assert first['frozen_strategy_semantics_changed'] is False
    assert first['phase_exit_6'].startswith('INCOMPLETE')


@pytest.mark.parametrize('call,categories', [
    (lambda: richping.engine.observe(None, None, None, None),
     ('outcome_queries', 'return_calculations', 'mfe_mae_calculations')),
    (lambda: richping.data.Dataset.window(None, 'SOXX', None, None, None),
     ('market_price_queries', 'benchmark_queries')),
    (lambda: richping.evaluation.metrics([]), ('return_calculations',)),
    (lambda: richping.evaluation.block_ci([]), ('uncertainty_calculations',)),
])
def test_guard_aborts_before_real_outcome_benchmark_or_calculation(call, categories):
    with audit.forbidden_calculations() as counts:
        with pytest.raises(AssertionError, match='ZERO_SIGNAL forbids'):
            call()
    assert all(counts[name] == 1 for name in categories)
    assert all(value == 0 for name, value in counts.items() if name not in categories)


def test_independent_cross_proof_dataset_identity_mismatch_fail_closed(monkeypatch):
    original = audit.read_json

    def changed(root, path):
        value = original(root, path)
        if path == audit.runner.prereg.COMPOSITION / 'smoke.json':
            value['daily_hash'] = 'incompatible-vintage'
        return value

    monkeypatch.setattr(audit, 'read_json', changed)
    with pytest.raises(ValueError, match='fixed dataset identity mismatch'):
        audit.audit()


def test_modified_committed_disposition_zero_metric_fail_closed(monkeypatch):
    original = audit.read_json

    def changed(root, path):
        value = original(root, path)
        if path == audit.runner.EVIDENCE / 'disposition-report.json':
            value['metrics']['forward_returns'] = 0
        return value

    monkeypatch.setattr(audit, 'read_json', changed)
    with pytest.raises(ValueError, match='committed disposition identity mismatch'):
        audit.audit()


def test_audit_opens_metadata_and_sources_only(monkeypatch):
    audit.runner.make_manifest('2026-10-03T12:02:15+00:00')  # Warm the static calendar.
    allowed = set(audit.runner.prereg.dependency_manifest()) | set(audit.runner.SOURCES) | {
        audit.runner.prereg.RECORD.as_posix(), audit.SOURCE,
        (audit.runner.EVIDENCE / 'evaluation-manifest.json').as_posix(),
        (audit.runner.EVIDENCE / 'disposition-report.json').as_posix(),
        (audit.runner.EVIDENCE / 'offline-proof.json').as_posix(),
    }
    original = Path.open
    opened = []

    def checked(path, mode='r', *args, **kwargs):
        assert mode in ('r', 'rb')
        relative = path.relative_to(audit.ROOT).as_posix()
        assert relative in allowed
        opened.append(relative)
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', checked)
    proof, _ = audit.audit()
    assert opened and proof['market_price_queries'] == proof['market_dataset_loads'] == 0


def test_protocol_mismatch_fails_before_disposition_and_calculations(monkeypatch):
    monkeypatch.setattr(audit.runner.prereg, 'FROZEN_PROTOCOL_HASH', 'wrong-authority')
    with audit.forbidden_calculations() as calls:
        with pytest.raises(ValueError, match='protocol hash mismatch'):
            audit.audit()
    assert not any(calls.values())
