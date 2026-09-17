import os
from pathlib import Path
import tempfile
import uuid

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    # Ensure temporary directories are safely isolated per test execution,
    # avoiding shared fixed basetemp deletion issues and Windows temp ACL quirks.
    if config.option.basetemp is None:
        temp_root = Path(tempfile.gettempdir()) / f"richping_pytest_{os.getpid()}_{uuid.uuid4().hex[:8]}"
        temp_root.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = temp_root
