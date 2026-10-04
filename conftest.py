"""Preserve sealed historical intake tests and test the current registry separately."""
from functools import partial
from pathlib import Path
import shutil

import pytest


@pytest.fixture(autouse=True)
def historical_intake_registry(request):
    # H0002 sealed this test's bytes and its original H0001/H0002 registry case.
    # New hypotheses must not rewrite that sealed test or its old evidence.
    # H0003 separately tests the actual current registry and next unused H0004.
    if (request.node.name != 'test_real_intake_is_deterministic_and_not_gated_by_h0001_confirmation'
            or Path(request.node.path).name != 'test_independent_research_intake.py'):
        return
    from scripts.prepare_independent_research import prepare
    tmp_path = request.getfixturevalue('tmp_path')
    monkeypatch = request.getfixturevalue('monkeypatch')
    registry = tmp_path/'historical-intake'/'research'/'hypotheses'
    registry.mkdir(parents=True)
    for pattern in ('H0001-r*.yaml','H0002-r*.yaml'):
        for source in Path('research/hypotheses').glob(pattern):
            shutil.copyfile(source,registry/source.name)
    monkeypatch.setattr(request.module,'prepare',partial(prepare,root=tmp_path/'historical-intake'))
