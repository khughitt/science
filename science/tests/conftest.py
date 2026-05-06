from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make `_fixtures.*` importable as a top-level package: tests/ has no
# __init__.py (cross-project pytest collection treats it as a rootdir),
# so we add the tests directory to sys.path here.
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))


@pytest.fixture(autouse=True)
def isolate_science_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / ".science-config"))
