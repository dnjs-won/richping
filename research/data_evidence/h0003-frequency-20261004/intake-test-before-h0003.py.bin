from pathlib import Path
import shutil
from unittest.mock import patch

import pytest
import yaml

from scripts.prepare_independent_research import prepare, capture_observation


def test_real_intake_is_deterministic_and_not_gated_by_h0001_confirmation():
    with patch('socket.socket.connect', side_effect=AssertionError('network')):
        first = prepare()
        assert first == prepare()
    assert first['next_hypothesis_id'] == 'H0003'
    assert any(e['id'] == 'H0002' and e['revision'] == 1 for e in first['registered_hypotheses'])
    assert first['next_action_status'] == 'USER_DECISION_REQUIRED'
    assert first['candidate_outcome_access'] is False
    assert first['future_confirmation_dependency'] is False


def test_new_draft_preserves_originals_and_does_not_invent_rules(tmp_path):
    (tmp_path/'research/hypotheses').mkdir(parents=True)
    (tmp_path/'research/templates').mkdir()
    source = Path('research/templates/hypothesis.yaml')
    shutil.copy(source, tmp_path/'research/templates/hypothesis.yaml')
    original = Path('research/hypotheses/H0001-r03.yaml').read_bytes()
    (tmp_path/'research/hypotheses/H0001-r03.yaml').write_bytes(original)
    path = capture_observation(tmp_path, 'Explicit observation', 'Explicit independent thesis', '2026-10-04T00:00:00Z')
    body = yaml.safe_load(path.read_text(encoding='utf-8'))
    assert body['hypothesis_id'] == 'H0002' and body['status'] == 'DRAFT'
    assert body['rules']['trigger'] == ['UNKNOWN_NOT_SELECTED']
    assert body['experiment_refs'] == body['evidence_refs'] == []
    assert (tmp_path/'research/hypotheses/H0001-r03.yaml').read_bytes() == original
    assert prepare(tmp_path)['next_hypothesis_id'] == 'H0003'


@pytest.mark.parametrize('observation,thesis', [('', 'thesis'), ('observation','')])
def test_no_strategy_meaning_is_fabricated(tmp_path, observation, thesis):
    with pytest.raises(ValueError, match='Explicit'): capture_observation(tmp_path, observation, thesis, '2026-10-04T00:00:00Z')


def test_filename_identity_mismatch_fails_closed(tmp_path):
    (tmp_path/'research/hypotheses').mkdir(parents=True)
    (tmp_path/'research/hypotheses/H0002-r01.yaml').write_text('hypothesis_id: H0001\nrevision: 1\nstatus: DRAFT\n')
    with pytest.raises(ValueError, match='mismatch'): prepare(tmp_path)
