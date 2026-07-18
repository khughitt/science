from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.validate.checks.correspondence_drift import check_correspondence_drift
from science_tool.validate.context import ValidateContext

_MM = Path.home() / "d" / "cancer" / "cancer-types" / "multiple-myeloma"


@pytest.mark.real_projects
def test_detector_fires_on_multiple_myeloma():
    if not (_MM / "science.yaml").is_file():
        pytest.skip(f"multiple-myeloma not present at {_MM}")
    ctx = ValidateContext.from_project_root(_MM, strict=False, verbose=False)
    results = [r for r in check_correspondence_drift(ctx) if r.rule == "plan.correspondence-drift"]
    assert len(results) >= 1
    assert all(r.severity.value == "warn" for r in results)
    assert all(not r.path.is_absolute() for r in results)
