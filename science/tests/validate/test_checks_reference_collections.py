from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.validate.checks.reference_collections import check_reference_collections
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_MANIFEST = (
    "name: demo\ncreated: 2026-01-01\nlast_modified: 2026-01-02\nstatus: active\n"
    "summary: demo\nprofile: research\nlayout_version: 1\n"
    "knowledge_profiles:\n  local: knowledge/local\n"
)

_PARENT_DP = """\
profiles: [science-pkg-entity-1.0]
id: dataset:ref-collection
type: dataset
title: Reference Collection
status: active
tier: use-now
"""

_MEMBER_DP = """\
profiles: [science-pkg-entity-1.0]
id: dataset:member-a
type: dataset
title: Member A
status: active
origin: derived
tier: use-now
parent_dataset: dataset:ref-collection
derivation:
  kind: member_of
  parent_dataset: dataset:ref-collection
  member_key: row-a
"""

_MEMBER_DECLARED_UNRESOLVED_DP = """\
profiles: [science-pkg-entity-1.0]
id: dataset:member-b
type: dataset
title: Member B
status: active
origin: derived
tier: use-now
parent_dataset: dataset:ref-collection
resolution_status: declared_unresolved
derivation:
  kind: member_of
  parent_dataset: dataset:ref-collection
  member_key: row-b
"""

_MEMBER_MISSING_PARENT_DP = """\
profiles: [science-pkg-entity-1.0]
id: dataset:member-orphan
type: dataset
title: Member Orphan
status: active
origin: derived
tier: use-now
parent_dataset: dataset:no-such-collection
derivation:
  kind: member_of
  parent_dataset: dataset:no-such-collection
  member_key: row-x
"""

_MEMBER_DECLARED_UNRESOLVED_MISSING_PARENT_DP = """\
profiles: [science-pkg-entity-1.0]
id: dataset:member-orphan-dec
type: dataset
title: Member Orphan Declared
status: active
origin: derived
tier: use-now
parent_dataset: dataset:no-such-collection
resolution_status: declared_unresolved
derivation:
  kind: member_of
  parent_dataset: dataset:no-such-collection
  member_key: row-x
"""

_WORKFLOW_DATASET_DP = """\
profiles: [science-pkg-entity-1.0]
id: dataset:workflow-out
type: dataset
title: Workflow Output
status: active
tier: use-now
"""


def _scaffold(tmp_path: Path) -> None:
    """Write the minimal project layout load_project_sources requires."""
    tmp_path.joinpath("science.yaml").write_text(_MANIFEST, encoding="utf-8")
    (tmp_path / "knowledge" / "local").mkdir(parents=True)


def _ctx(project_root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(project_root, strict=False, verbose=False)


def _write_dp(tmp_path: Path, subdir: str, name: str, content: str) -> None:
    dp_dir = tmp_path / "data" / subdir
    dp_dir.mkdir(parents=True, exist_ok=True)
    (dp_dir / "datapackage.yaml").write_text(content, encoding="utf-8")


@pytest.fixture
def refcoll_project(tmp_path: Path) -> Path:
    """Parent-collection dataset present + a member_of dataset pointing at it."""
    _scaffold(tmp_path)
    _write_dp(tmp_path, "ref-collection", "ref-collection", _PARENT_DP)
    _write_dp(tmp_path, "member-a", "member-a", _MEMBER_DP)
    return tmp_path


@pytest.fixture
def refcoll_project_missing_parent(tmp_path: Path) -> Path:
    """Member only; its derivation.parent_dataset names a dataset not in the project."""
    _scaffold(tmp_path)
    _write_dp(tmp_path, "member-orphan", "member-orphan", _MEMBER_MISSING_PARENT_DP)
    return tmp_path


@pytest.fixture
def refcoll_project_declared_unresolved(tmp_path: Path) -> Path:
    """Parent collection present + member with resolution_status: declared_unresolved."""
    _scaffold(tmp_path)
    _write_dp(tmp_path, "ref-collection", "ref-collection", _PARENT_DP)
    _write_dp(tmp_path, "member-b", "member-b", _MEMBER_DECLARED_UNRESOLVED_DP)
    return tmp_path


@pytest.fixture
def refcoll_project_declared_unresolved_missing_parent(tmp_path: Path) -> Path:
    """Member with resolution_status: declared_unresolved but NO parent present."""
    _scaffold(tmp_path)
    _write_dp(tmp_path, "member-orphan-dec", "member-orphan-dec", _MEMBER_DECLARED_UNRESOLVED_MISSING_PARENT_DP)
    return tmp_path


@pytest.fixture
def refcoll_project_workflow_only(tmp_path: Path) -> Path:
    """Single ordinary origin: derived dataset with a WORKFLOW derivation (no member_of)."""
    _scaffold(tmp_path)
    _write_dp(tmp_path, "workflow-out", "workflow-out", _WORKFLOW_DATASET_DP)
    return tmp_path


def test_member_with_existing_parent_passes(refcoll_project: Path) -> None:
    results = list(check_reference_collections(_ctx(refcoll_project)))
    assert not [r for r in results if r.severity is Severity.ERROR]


def test_member_with_missing_parent_errors(refcoll_project_missing_parent: Path) -> None:
    results = list(check_reference_collections(_ctx(refcoll_project_missing_parent)))
    errors = [r for r in results if r.severity is Severity.ERROR]
    assert len(errors) == 1
    assert "parent_dataset" in errors[0].message
    assert errors[0].rule == "reference-collection.unresolved-parent"


def test_declared_unresolved_with_present_parent_infos(refcoll_project_declared_unresolved: Path) -> None:
    # Parent EXISTS + member declares declared_unresolved → no ERROR, one INFO.
    results = list(check_reference_collections(_ctx(refcoll_project_declared_unresolved)))
    assert not [r for r in results if r.severity is Severity.ERROR]
    infos = [r for r in results if r.rule == "reference-collection.declared-unresolved"]
    assert len(infos) == 1


def test_declared_unresolved_does_not_bypass_missing_parent(
    refcoll_project_declared_unresolved_missing_parent: Path,
) -> None:
    results = list(check_reference_collections(_ctx(refcoll_project_declared_unresolved_missing_parent)))
    errors = [r for r in results if r.severity is Severity.ERROR]
    assert len(errors) == 1
    assert errors[0].rule == "reference-collection.unresolved-parent"


def test_non_member_datasets_ignored(refcoll_project_workflow_only: Path) -> None:
    results = list(check_reference_collections(_ctx(refcoll_project_workflow_only)))
    assert results == []
