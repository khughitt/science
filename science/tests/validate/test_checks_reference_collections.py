from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.validate.checks.reference_collections import _member_defect, check_reference_collections
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
kind: dataset
title: Reference Collection
status: active
tier: use-now
"""

_MEMBER_DP = """\
profiles: [science-pkg-entity-1.0]
id: dataset:member-a
kind: dataset
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
kind: dataset
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
kind: dataset
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
kind: dataset
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
kind: dataset
title: Workflow Output
status: active
tier: use-now
"""

# Top-level parent_dataset disagrees with derivation.parent_dataset; derivation's
# parent (dataset:parent-collection) IS present so only a WARN should fire.
_MEMBER_PARENT_MISMATCH_DP = """\
profiles: [science-pkg-entity-1.0]
id: dataset:member-mismatch
kind: dataset
title: Member Mismatch
status: active
origin: derived
tier: use-now
parent_dataset: dataset:some-other-collection
derivation:
  kind: member_of
  parent_dataset: dataset:parent-collection
  member_key: row-m
"""

_PARENT_COLLECTION_FOR_MISMATCH_DP = """\
profiles: [science-pkg-entity-1.0]
id: dataset:parent-collection
kind: dataset
title: Parent Collection
status: active
tier: use-now
"""

# Member whose member_of derivation is MISSING its required member_key. The
# entity-profile fields (id/type/title) stay valid so DatapackageAdapter.discover
# accepts the package — only the derivation is malformed (F1 regression guard).
_MEMBER_MALFORMED_DP = """\
profiles: [science-pkg-entity-1.0]
id: dataset:member-malformed
kind: dataset
title: Member Malformed
status: active
origin: derived
tier: use-now
parent_dataset: dataset:parent-collection
derivation:
  kind: member_of
  parent_dataset: dataset:parent-collection
"""

# Member whose derivation.parent_dataset is hosted only in the commons.
_MEMBER_COMMONS_PARENT_DP = """\
profiles: [science-pkg-entity-1.0]
id: dataset:member-commons
kind: dataset
title: Member Commons Parent
status: active
origin: derived
tier: use-now
parent_dataset: dataset:commons-parent
derivation:
  kind: member_of
  parent_dataset: dataset:commons-parent
  member_key: row-c
"""

# Commons-hosted parent collection entity.md (mirrors
# tests/fixtures/commons/refcoll/datasets/parent-collection/entity.md).
_COMMONS_PARENT_ENTITY_MD = """\
---
schema_profile: "science-entity-base/1.0+dataset/1.0"
id: "dataset:commons-parent"
kind: "dataset"
title: "Commons parent reference collection"
version: "1.0.0"
status: "active"
created: "2026-05-26"
updated: "2026-05-26"
datapackage: "datapackage.yaml"
origin: "external"
tier: "use-now"
access:
  level: "public"
  verified: true
  source_url: "https://example.org/collection"
---

# Commons parent reference collection

A reference collection whose members are addressed by key.
"""

_COMMONS_PARENT_DATAPACKAGE_YAML = """\
name: commons-parent
profile: "data-package"
resources:
  - name: members
    path: members.parquet
    hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    bytes: 1024
    format: "parquet"
    mediatype: "application/vnd.apache.parquet"
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


def _empty_commons(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point SCIENCE_COMMONS_ROOT at a fresh empty commons dir (present but irrelevant)."""
    commons = tmp_path / "empty-commons"
    commons.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    return commons


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


@pytest.fixture
def refcoll_project_malformed_member(tmp_path: Path) -> Path:
    """Member whose member_of derivation is missing its member_key (F1 guard)."""
    _scaffold(tmp_path)
    _write_dp(tmp_path, "member-malformed", "member-malformed", _MEMBER_MALFORMED_DP)
    return tmp_path


@pytest.fixture
def refcoll_project_commons_parent(tmp_path: Path) -> tuple[Path, Path]:
    """Project with only a member whose parent lives in a temp commons dir.

    Returns (project_root, commons_root). The commons parent is laid out exactly
    like tests/fixtures/commons/refcoll/datasets/parent-collection/ so
    CommonsEntityAdapter(commons_root).load("dataset:commons-parent") succeeds.
    """
    _scaffold(tmp_path)
    _write_dp(tmp_path, "member-commons", "member-commons", _MEMBER_COMMONS_PARENT_DP)

    commons_root = tmp_path / "commons"
    parent_dir = commons_root / "datasets" / "commons-parent"
    parent_dir.mkdir(parents=True)
    (parent_dir / "entity.md").write_text(_COMMONS_PARENT_ENTITY_MD, encoding="utf-8")
    (parent_dir / "datapackage.yaml").write_text(_COMMONS_PARENT_DATAPACKAGE_YAML, encoding="utf-8")
    return tmp_path, commons_root


def test_member_with_existing_parent_passes(
    refcoll_project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Parent is LOCAL; an empty commons is present but irrelevant.
    _empty_commons(tmp_path, monkeypatch)
    results = list(check_reference_collections(_ctx(refcoll_project)))
    assert not [r for r in results if r.severity is Severity.ERROR]


def test_member_with_missing_parent_errors(
    refcoll_project_missing_parent: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Parent is NON-local; empty commons is a dir but lacks the id → unresolved ERROR.
    _empty_commons(tmp_path, monkeypatch)
    results = list(check_reference_collections(_ctx(refcoll_project_missing_parent)))
    errors = [r for r in results if r.severity is Severity.ERROR]
    assert len(errors) == 1
    assert "parent_dataset" in errors[0].message
    assert errors[0].rule == "reference-collection.unresolved-parent"


def test_declared_unresolved_with_present_parent_infos(
    refcoll_project_declared_unresolved: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Parent EXISTS locally + member declares declared_unresolved → no ERROR, one INFO.
    _empty_commons(tmp_path, monkeypatch)
    results = list(check_reference_collections(_ctx(refcoll_project_declared_unresolved)))
    assert not [r for r in results if r.severity is Severity.ERROR]
    infos = [r for r in results if r.rule == "reference-collection.declared-unresolved"]
    assert len(infos) == 1


def test_declared_unresolved_does_not_bypass_missing_parent(
    refcoll_project_declared_unresolved_missing_parent: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Parent is NON-local; empty commons is a dir but lacks the id → unresolved ERROR.
    _empty_commons(tmp_path, monkeypatch)
    results = list(check_reference_collections(_ctx(refcoll_project_declared_unresolved_missing_parent)))
    errors = [r for r in results if r.severity is Severity.ERROR]
    assert len(errors) == 1
    assert errors[0].rule == "reference-collection.unresolved-parent"


def test_non_member_datasets_ignored(
    refcoll_project_workflow_only: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _empty_commons(tmp_path, monkeypatch)
    results = list(check_reference_collections(_ctx(refcoll_project_workflow_only)))
    assert results == []


def test_malformed_member_yields_error_not_crash(
    refcoll_project_malformed_member: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # F1: a member_of missing member_key must NOT crash the check; it yields one ERROR.
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "empty-commons"))
    (tmp_path / "empty-commons").mkdir()
    results = list(check_reference_collections(_ctx(refcoll_project_malformed_member)))  # must not raise
    malformed = [r for r in results if r.rule == "reference-collection.malformed-member"]
    assert len(malformed) == 1
    assert malformed[0].severity is Severity.ERROR


def test_commons_unavailable_yields_info_not_error(
    refcoll_project_missing_parent: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # F2: non-local parent + commons root that does not exist → INFO, never crash/ERROR.
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "does-not-exist"))
    results = list(check_reference_collections(_ctx(refcoll_project_missing_parent)))  # must not raise
    assert not [r for r in results if r.severity is Severity.ERROR]
    infos = [r for r in results if r.rule == "reference-collection.commons-unavailable"]
    assert len(infos) == 1


def test_commons_hosted_parent_resolves(
    refcoll_project_commons_parent: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Non-local parent that DOES exist in the configured commons → resolves, no ERROR.
    project_root, commons_root = refcoll_project_commons_parent
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    results = list(check_reference_collections(_ctx(project_root)))
    assert not [r for r in results if r.severity is Severity.ERROR]
    assert not [r for r in results if r.rule == "reference-collection.commons-unavailable"]


# ---------------------------------------------------------------------------
# _member_defect unit tests
# ---------------------------------------------------------------------------


def test_member_defect_flags_missing_parent_dataset() -> None:
    assert "parent_dataset" in _member_defect({"kind": "member_of", "member_key": "m-1"})


def test_member_defect_flags_non_dataset_parent() -> None:
    assert "parent_dataset" in _member_defect(
        {"kind": "member_of", "parent_dataset": "reactome-v89", "member_key": "m-1"}
    )


def test_member_defect_flags_blank_member_key() -> None:
    assert "member_key" in _member_defect({"kind": "member_of", "parent_dataset": "dataset:x", "member_key": "  "})


def test_member_defect_none_for_well_formed() -> None:
    assert _member_defect({"kind": "member_of", "parent_dataset": "dataset:x", "member_key": "m-1"}) is None


# ---------------------------------------------------------------------------
# parent-mismatch WARN integration test
# ---------------------------------------------------------------------------


@pytest.fixture
def refcoll_project_parent_mismatch(tmp_path: Path) -> Path:
    """Parent collection present + member whose top-level parent_dataset differs
    from derivation.parent_dataset (both valid dataset: refs). The derivation's
    parent IS present, so only the WARN fires — not an unresolved-parent ERROR."""
    _scaffold(tmp_path)
    _write_dp(tmp_path, "parent-collection", "parent-collection", _PARENT_COLLECTION_FOR_MISMATCH_DP)
    _write_dp(tmp_path, "member-mismatch", "member-mismatch", _MEMBER_PARENT_MISMATCH_DP)
    return tmp_path


def test_parent_mismatch_warns(
    refcoll_project_parent_mismatch: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # derivation.parent_dataset (dataset:parent-collection) is LOCAL → only the WARN fires.
    _empty_commons(tmp_path, monkeypatch)
    results = list(check_reference_collections(_ctx(refcoll_project_parent_mismatch)))
    warns = [r for r in results if r.rule == "reference-collection.parent-mismatch"]
    assert len(warns) == 1
    assert not [r for r in results if r.severity is Severity.ERROR]
