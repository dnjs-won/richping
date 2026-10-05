"""Preserve the historical sealed H0003 registry case with its original inputs."""
from functools import partial
from pathlib import Path
import shutil
import pytest


@pytest.fixture(autouse=True)
def sealed_h0003_intake_case(request):
    if (request.node.name != 'test_current_registry_advances_to_h0004_without_future_confirmation_dependency'
            or Path(request.node.path).name != 'test_h0003_admission_frequency.py'):
        return
    from scripts.prepare_independent_research import prepare
    tmp_path = request.getfixturevalue('tmp_path')
    registry = tmp_path/'h0003-historical'/'research/hypotheses'
    registry.mkdir(parents=True)
    for pattern in ('H0001-r*.yaml', 'H0002-r*.yaml', 'H0003-r*.yaml'):
        for source in Path('research/hypotheses').glob(pattern):
            shutil.copyfile(source, registry/source.name)
    request.getfixturevalue('monkeypatch').setattr(
        'scripts.prepare_independent_research.prepare', partial(prepare, root=tmp_path/'h0003-historical'))
