"""Protocol integrity/admission checks; no market labels or synthetic efficacy."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from scripts import h0001_entry_efficacy_preregister as prereg
from scripts.h0001_entry_freeze import immutable

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def record():
    return yaml.safe_load((ROOT / prereg.RECORD).read_text(encoding='utf-8'))


def test_frozen_protocol_and_saved_proof_agree_without_market_reads(record):
    with patch('sqlite3.connect', prereg.forbidden), patch('socket.socket.connect', prereg.forbidden), \
            patch('richping.research_v2.daily_data.load_daily', prereg.forbidden):
        first, second = prereg.verify(record), prereg.verify(record)
    proof = json.loads((ROOT / prereg.EVIDENCE / 'offline-proof.json').read_text(encoding='utf-8'))
    assert first == second
    assert all(proof[k] == v for k, v in first.items())
    assert proof['outcome_queries'] == proof['returns_calculated'] == proof['market_dataset_loads'] == 0
    assert proof['prior_candidate_count'] == 0 and proof['unresolved_paths'] == 84
    assert proof['specification_mutated'] is False and proof['phase_exit_6'].startswith('INCOMPLETE')


@pytest.mark.parametrize('section,field,value', [
    ('label_contract', 'primary_horizon', 16),
    ('scope', 'sample_unit', 'COMPLETED_TRADE'),
    ('comparison', 'minimum_control_sessions_per_event', 1),
    ('costs', 'applied', True),
    ('uncertainty', 'block_sessions', 1),
    ('uncertainty', 'samples', 100),
    ('multiple_testing', 'primary_tests', 5),
    ('missing_outcomes', 'no_signals', 'query prices anyway'),
])
def test_parameter_mutation_cannot_reseal_same_protocol(record, section, field, value):
    record[section][field] = value
    record['contract_hash'] = prereg.protocol_hash(record)
    with pytest.raises(ValueError, match='protocol hash'):
        prereg.verify(record)


def test_dependency_mutation_fail_closed_even_when_record_is_intact(record, monkeypatch):
    manifest = deepcopy(record['source_LF_sha256'])
    manifest['richping/research_v2/strategy/entry_15m.py'] = 'changed'
    monkeypatch.setattr(prereg, 'dependency_manifest', lambda root: manifest)
    with pytest.raises(ValueError, match='dependency mutation'):
        prereg.verify(record)


def test_protocol_artifact_collision_not_overwritten(record, tmp_path):
    path = tmp_path / 'protocol.json'
    immutable(path, record)
    before = path.read_bytes()
    immutable(path, record)
    changed = deepcopy(record)
    changed['outcome_lookup'] = 'ACCESSED'
    with pytest.raises(ValueError, match='immutable artifact collision'):
        immutable(path, changed)
    assert path.read_bytes() == before


def test_verification_command_is_idempotent_and_never_rewrites_record(record, capsys):
    before = (ROOT / prereg.RECORD).read_bytes()
    prereg.main([])
    first = json.loads(capsys.readouterr().out)
    prereg.main(['--freeze'])
    second = json.loads(capsys.readouterr().out)
    assert first == second and first['database_reads'] == 0
    assert (ROOT / prereg.RECORD).read_bytes() == before


def test_scoped_preregistration_does_not_admit_profitability(record):
    spec = prereg.H0001Specification.load(ROOT / record['dependencies']['executable_spec']['path'])
    with pytest.raises(ValueError):
        spec.require_profitability_ready()
    assert spec.unpack()['research_requirements']['sample_unit']['value'] == 'UNRESOLVED'
    assert record['scope']['candidate_is_trade_or_fill'] is False
    assert record['decision_scopes']['general_spec_roots'].startswith('Unchanged UNRESOLVED')
