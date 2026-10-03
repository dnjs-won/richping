"""Empty real stream disposition and admission guards; no efficacy labels."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import socket
import sqlite3

import pytest
import yaml

from richping.core import digest
from scripts import h0001_first_entry_efficacy as runner
from scripts.h0001_entry_freeze import immutable

AS_OF = '2026-10-03T12:00:00+00:00'


@pytest.fixture
def manifest():
    return runner.make_manifest(AS_OF)


@pytest.fixture
def isolated_root(tmp_path):
    record = yaml.safe_load((runner.ROOT / runner.prereg.RECORD).read_text(encoding='utf-8'))
    paths = set(record['source_LF_sha256']) | set(runner.SOURCES) | {str(runner.prereg.RECORD)}
    for path in paths:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(runner.ROOT / path, target)
    return tmp_path


def test_real_empty_stream_twice_identical_and_null_not_zero_metrics(manifest):
    with runner.no_market_access() as audit:
        first, second = runner.evaluate(manifest), runner.evaluate(manifest)
    assert first == second and not any(audit.values())
    assert first['status'] == 'ZERO_SIGNAL'
    assert first['candidate_count'] == 0 and first['candidate_timestamps'] == []
    assert all(value is None for value in first['metrics'].values())
    assert first['control_cohort']['eligible_count'] is None
    assert first['inference'].startswith('NOT_RUN')
    assert first['confirmation']['status'] == 'NOT_STARTED_NOT_EVALUATED'
    assert first['phase_exit_6'].startswith('INCOMPLETE')
    assert first['profitability'] == 'NOT_RUN' and first['outcome_lookup'] == 'NONE'
    assert first['report_id'] == digest({k: v for k, v in first.items() if k != 'report_id'})
    assert set(first['label_denominators_by_horizon']) == {'4', '16', '64', '192', '320'}
    for counts in first['label_denominators_by_horizon'].values():
        assert [counts[k] for k in ('total', 'complete', 'pending', 'unresolved')] == [0, 0, 0, 0]


def test_reads_only_signal_metadata_contracts_and_source_files(manifest, monkeypatch):
    reads = []
    original = Path.open
    allowed = set(runner.prereg.dependency_manifest()) | set(runner.SOURCES) | {runner.prereg.RECORD.as_posix()}

    def checked(path, mode='r', *args, **kwargs):
        if 'r' in mode:
            relative = path.relative_to(runner.ROOT).as_posix()
            assert relative in allowed
            reads.append(relative)
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', checked)
    runner.evaluate(manifest)
    assert reads and not any(p.endswith('.sqlite') or p.startswith('var/') for p in reads)


@pytest.mark.parametrize('field,value', [
    ('protocol_hash', 'changed'), ('specification_hash', 'changed'),
    ('composer_contract_hash', 'changed'), ('signal_stream_hash', 'changed'),
    ('scope', 'FULL_STRATEGY'), ('partition', 'CONFIRMATION'),
    ('basis_commit', 'changed'), ('outcome_access', 'ALLOW'),
])
def test_rehashed_manifest_mutation_fail_closed(manifest, field, value):
    manifest[field] = value
    manifest['manifest_hash'] = runner.manifest_hash(manifest)
    with pytest.raises(ValueError, match='manifest dependency mismatch'):
        runner.evaluate(manifest)


def test_manifest_hash_and_future_confirmation_are_not_silently_reclassified(manifest):
    manifest['evaluation_as_of'] = '2027-05-01T00:00:00+00:00'
    with pytest.raises(ValueError, match='manifest hash mismatch'):
        runner.evaluate(manifest)


def test_evaluation_before_preregistration_or_naive_time_is_rejected():
    with pytest.raises(ValueError, match='predates preregistration'):
        runner.make_manifest('2026-10-02T00:00:00+00:00')
    with pytest.raises(ValueError, match='Timezone-aware'):
        runner.make_manifest('2026-10-03T12:00:00')


@pytest.mark.parametrize('relative', [
    'richping/research_v2/strategy/entry_15m.py',
    'research/data_evidence/h0001-entry-composition-20261003/candidate-events.json',
    'research/data_evidence/h0001-entry-composition-20261003/denominator-report.json',
])
def test_committed_dependency_mutation_rejected_before_disposition(isolated_root, relative):
    manifest = runner.make_manifest(AS_OF, isolated_root)
    with (isolated_root / relative).open('a', encoding='utf-8') as file:
        file.write('\nMUTATED')
    with pytest.raises(ValueError, match='frozen dependency mutation'):
        runner.evaluate(manifest, isolated_root)


def test_execution_source_mutation_requires_new_manifest(isolated_root):
    manifest = runner.make_manifest(AS_OF, isolated_root)
    with (isolated_root / runner.SOURCES[0]).open('a', encoding='utf-8') as file:
        file.write('\n# changed execution source\n')
    with pytest.raises(ValueError, match='manifest dependency mismatch'):
        runner.evaluate(manifest, isolated_root)


def test_nonempty_stream_cannot_report_zero_signal_or_access_labels(manifest, monkeypatch):
    record, verified, stream, denominator = runner.inputs(runner.ROOT)
    stream = deepcopy(stream)
    stream['events'] = [{'event_id': 'test-admission-only-no-prices'}]
    monkeypatch.setattr(runner, 'inputs', lambda root: (record, verified, stream, denominator))
    with runner.no_market_access() as audit:
        with pytest.raises(ValueError, match='nonempty stream requires exact frozen label adapter'):
            runner.evaluate(manifest)
    assert not any(audit.values())


def test_guards_abort_actual_database_and_network_attempts():
    with runner.no_market_access() as audit:
        with pytest.raises(AssertionError, match='database_reads'):
            sqlite3.connect(':memory:')
        with pytest.raises(AssertionError, match='network_calls'):
            socket.create_connection(('example.invalid', 443))
    assert audit['database_reads'] == audit['network_calls'] == 1


def test_saved_real_disposition_proof_and_artifacts_are_idempotent():
    proof = json.loads((runner.ROOT / runner.EVIDENCE / 'offline-proof.json').read_text(encoding='utf-8'))
    assert runner.execute() == proof == runner.execute()
    assert proof['offline_runs'] == 2 and proof['repeat_equal'] is True
    assert proof['market_action_benchmark_outcome_reads'] == proof['outcome_queries'] == proof['returns_calculated'] == 0
    assert proof['unresolved_paths'] == 84


def test_immutable_report_collision_and_failed_admission_write_nothing(manifest, tmp_path):
    report = runner.evaluate(manifest)
    path = tmp_path / 'report.json'
    immutable(path, report)
    before = path.read_bytes()
    report['metrics']['primary_excess'] = 0
    with pytest.raises(ValueError, match='immutable artifact collision'):
        immutable(path, report)
    assert path.read_bytes() == before
    bad = deepcopy(manifest)
    bad['protocol_hash'] = 'bad'
    immutable(tmp_path / 'evaluation-manifest.json', bad)
    with pytest.raises(ValueError, match='manifest hash mismatch'):
        runner.execute(evidence=tmp_path)
    assert not (tmp_path / 'disposition-report.json').exists()
