from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from science_model.correspondence import Correspondence


def test_nonverified_correspondence_requires_a_code() -> None:
    for status in ("violated", "unwired"):
        with pytest.raises(ValidationError, match="code"):
            Correspondence(status=status)


def test_verified_correspondence_has_no_code() -> None:
    with pytest.raises(ValidationError, match="verified"):
        Correspondence(status="verified", code="NOT_CLEAN")


def test_correspondence_is_frozen_and_forbids_extras() -> None:
    result = Correspondence(status="verified")
    with pytest.raises(ValidationError):
        result.status = "violated"
    with pytest.raises(ValidationError):
        Correspondence(status="verified", correspondence=True)


def test_running_correspondence_leaf_does_not_load_audit() -> None:
    leaf = Path(__file__).parents[1] / "src" / "science_model" / "correspondence.py"
    script = """
import runpy
import sys
runpy.run_path(sys.argv[1])
assert "science_model.audit" not in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(leaf)], capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stderr
