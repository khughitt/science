"""Tests for `_active_profile` -- builds the runtime ProfileString from
PromoteKindConfig + mixin extensions tuple.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from science_model.entity_schema.profile import ProfileComponent
from science_tool.commons.promote import (
    PROMOTE_KIND_DATASET,
    PROMOTE_KIND_PAPER,
    _active_profile,
)


def _project_tree_with_rnaseq(tmp_path: Path) -> Path:
    """Build a minimal source project with one data-mockrna.md dataset
    carrying bio.matrix + bio.rnaseq fields in its frontmatter, plus a
    JSON datapackage and the resource file the datapackage references."""
    proj = tmp_path / "proj-rnaseq"
    (proj / "doc" / "datasets").mkdir(parents=True)
    (proj / "data" / "mockrna").mkdir(parents=True)

    (proj / "doc" / "datasets" / "data-mockrna.md").write_text(
        """---
id: dataset:mockrna
type: dataset
title: Mock RNA-seq dataset
description: Synthetic fixture for Phase H integration tests.
datapackage: data/mockrna/datapackage.json
origin: external
tier: use-now
access:
  level: public
  verified: true
created: "2026-05-19"
updated: "2026-05-19"
species: ["Homo sapiens"]
assay: bulk-rnaseq
n_rows: 20530
n_cols: 100
value_dtype: int32
feature_axis: rows
---

# Mock RNA-seq

Body content.
""",
        encoding="utf-8",
    )

    (proj / "data" / "mockrna" / "datapackage.json").write_text(
        json.dumps(
            {
                "name": "mockrna",
                "resources": [
                    {
                        "name": "counts",
                        "path": "counts.tsv",
                        "format": "tsv",
                        "mediatype": "text/tab-separated-values",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (proj / "data" / "mockrna" / "counts.tsv").write_text("gene\ts1\n", encoding="utf-8")

    # Discovery walks `git ls-files`, so the project must be a committed git repo.
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(proj),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "-m",
            "init",
        ],
        check=True,
    )
    return proj


def test_no_extensions_returns_kind_default() -> None:
    profile = _active_profile(PROMOTE_KIND_PAPER, ())
    assert profile.base.name == "science-entity-base"
    assert profile.mixin is not None
    assert profile.mixin.name == "paper"
    assert profile.extensions == ()


def test_dataset_with_matrix_and_rnaseq() -> None:
    extensions = (
        ProfileComponent(name="bio.matrix", version="1.0"),
        ProfileComponent(name="bio.rnaseq", version="1.0"),
    )
    profile = _active_profile(PROMOTE_KIND_DATASET, extensions)
    assert profile.mixin is not None
    assert profile.mixin.name == "dataset"
    assert profile.extensions == extensions
    rendered = profile.render()
    assert rendered.endswith("+bio.matrix/1.0+bio.rnaseq/1.0")
    assert rendered.startswith("science-entity-base/1.0+dataset/1.0")


def test_returned_profile_is_a_new_object() -> None:
    """Doesn't mutate the PromoteKindConfig's frozen default_profile."""
    extensions = (ProfileComponent(name="bio.matrix", version="1.0"),)
    profile = _active_profile(PROMOTE_KIND_DATASET, extensions)
    assert PROMOTE_KIND_DATASET.default_profile.extensions == ()
    assert profile.extensions == extensions


def test_plan_promote_with_mixin_extensions_emits_extended_schema_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: invoking plan_promote with non-empty mixin_extensions
    routes bio fields to canonical (via merge_policy from the active
    profile) and emits the full schema_profile in the rendered entity."""
    from science_tool.commons.bootstrap import init_commons
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        discover_candidates,
        plan_promote,
    )

    proj = _project_tree_with_rnaseq(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda _slug: proj,
    )

    commons = tmp_path / "commons"
    init_commons(commons)

    discovery = discover_candidates(["proj-rnaseq"], PROMOTE_KIND_DATASET)
    assert "mockrna" in discovery.candidates_by_slug
    assert discovery.failed_candidates == []

    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_DATASET,
        mixin_extensions=(
            ProfileComponent(name="bio.matrix", version="1.0"),
            ProfileComponent(name="bio.rnaseq", version="1.0"),
        ),
    )

    assert len(plan.decisions) == 1
    canonical = plan.decisions[0].canonical_artifacts[0]
    assert "+bio.matrix/1.0+bio.rnaseq/1.0" in canonical.content
    # Bio fields routed to canonical, not overlay:
    assert "assay: bulk-rnaseq" in canonical.content
    assert "value_dtype: int32" in canonical.content
    assert "feature_axis: rows" in canonical.content
    assert "Homo sapiens" in canonical.content


def test_plan_promote_enforces_stacking_for_direct_callers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """plan_promote is callable directly (not just through the CLI), so the
    stacking-rule guard must fire there too. Direct call with two
    structural mixins raises PromoteMixinStackingError before any I/O."""
    from science_tool.commons.bootstrap import init_commons
    from science_tool.commons.errors import PromoteMixinStackingError
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        discover_candidates,
        plan_promote,
    )

    proj = _project_tree_with_rnaseq(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda _slug: proj,
    )

    commons = tmp_path / "commons"
    init_commons(commons)

    discovery = discover_candidates(["proj-rnaseq"], PROMOTE_KIND_DATASET)

    with pytest.raises(PromoteMixinStackingError, match="structural"):
        plan_promote(
            discovery,
            commons_root=commons,
            kind=PROMOTE_KIND_DATASET,
            mixin_extensions=(
                ProfileComponent(name="bio.matrix", version="1.0"),
                ProfileComponent(name="bio.table", version="1.0"),
            ),
        )


def test_plan_promote_with_unknown_explicit_mixin_raises_resolution_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit-form unknown extension (--mixin bio.bogus/1.0) reaches
    plan_promote, where read_merge_policy(active_profile) immediately
    tries to load the missing schema. The SchemaNotFoundError raised by
    the loader must be caught and rewrapped as
    PromoteMixinResolutionError so the CLI surfaces a consistent error
    for both sugar and explicit forms."""
    from science_tool.commons.bootstrap import init_commons
    from science_tool.commons.errors import PromoteMixinResolutionError
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        discover_candidates,
        plan_promote,
    )

    proj = _project_tree_with_rnaseq(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda _slug: proj,
    )

    commons = tmp_path / "commons"
    init_commons(commons)

    discovery = discover_candidates(["proj-rnaseq"], PROMOTE_KIND_DATASET)

    with pytest.raises(PromoteMixinResolutionError, match="bio.bogus"):
        plan_promote(
            discovery,
            commons_root=commons,
            kind=PROMOTE_KIND_DATASET,
            mixin_extensions=(ProfileComponent(name="bio.bogus", version="1.0"),),
        )
