from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from science_model.reasoning import MembershipRole

from science_tool.dag.workbench import (
    WorkbenchFile,
    WorkbenchRow,
    _resolve_row_discusses,
    compile_workbench,
)


def _row(discusses):
    # patch is a required WorkbenchRow field (workbench.py:134).
    # polarity="unsigned" required: "affects" is sign-meaningful so PropositionEntity
    # rejects polarity=None (error: must be positive/negative/unsigned).
    return WorkbenchRow(
        subject="gene:x", predicate="affects", object="outcome:y",
        patch="patch:p1", polarity="unsigned", discusses=discusses,
    )


def _seed(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    return tmp_path


def test_row_accepts_object_form_discusses():
    row = _row([{"frame": "hypothesis:h1", "role": "rival"}])
    resolved = _resolve_row_discusses(row, None)
    # The membership object round-trips through resolution.
    assert resolved is not None and len(resolved) == 1
    item = resolved[0]
    assert getattr(item, "frame", None) == "hypothesis:h1"
    assert getattr(item, "role", None) == MembershipRole.RIVAL


def test_bare_string_row_still_works():
    row = _row(["hypothesis:h1"])
    assert _resolve_row_discusses(row, None) == ["hypothesis:h1"]


def test_compile_workbench_preserves_role(tmp_path: Path):
    # Drives the real compile path end-to-end (not a manual stamp).
    wb = WorkbenchFile(rows=[_row([{"frame": "hypothesis:h1", "role": "background"}])])
    result = compile_workbench(wb, project_root=_seed(tmp_path))
    prop = result.propositions[0]
    assert ("hypothesis:h1", MembershipRole.BACKGROUND) in list(prop.iter_memberships())


def test_compile_workbench_rejects_conflicting_roles(tmp_path: Path):
    # Same frame, two roles. This raises ONLY if compile re-validates (model_validate);
    # a model_copy stamp would skip the validator and silently pass — so this test is
    # what forces the Step 4 change.
    wb = WorkbenchFile(
        rows=[_row(["hypothesis:h1", {"frame": "hypothesis:h1", "role": "rival"}])]
    )
    with pytest.raises(ValidationError):
        compile_workbench(wb, project_root=_seed(tmp_path))
