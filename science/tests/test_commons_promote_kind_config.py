"""Tests for the kind-config types in science_tool.commons.promote."""

from __future__ import annotations

import re
from pathlib import Path


def test_promote_kind_config_is_frozen_dataclass() -> None:
    from science_tool.commons.promote import PromoteKindConfig

    assert PromoteKindConfig.__dataclass_params__.frozen  # pyright: ignore[reportAttributeAccessIssue]


def test_promote_kind_config_required_fields() -> None:
    from science_model.entity_schema import default_profile_for_kind

    from science_tool.commons.promote import PromoteKindConfig

    cfg = PromoteKindConfig(
        kind="paper",
        source_subdirs=("doc/papers",),
        overlay_dest_subdir="doc/papers",
        commons_subdir="papers",
        id_prefix="paper:",
        slug_regex=re.compile(r"^[A-Za-z][A-Za-z0-9-]{1,63}$"),
        slug_match="casefold",
        mixin_schema_id="https://schemas.science/mixin-paper-2.0.json",
        default_profile=default_profile_for_kind("paper"),
        eligibility_filter=None,
    )
    assert cfg.kind == "paper"
    assert cfg.source_subdirs == ("doc/papers",)
    assert cfg.overlay_dest_subdir == "doc/papers"
    assert cfg.commons_subdir == "papers"
    assert cfg.id_prefix == "paper:"
    assert cfg.slug_regex.pattern == r"^[A-Za-z][A-Za-z0-9-]{1,63}$"
    assert cfg.slug_match == "casefold"
    assert cfg.mixin_schema_id == "https://schemas.science/mixin-paper-2.0.json"
    assert cfg.default_profile == default_profile_for_kind("paper")
    assert cfg.eligibility_filter is None
    assert not hasattr(cfg, "__dict__")


def test_paper_topic_theme_have_no_side_channel_apply() -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        PROMOTE_KIND_THEME,
        PROMOTE_KIND_TOPIC,
    )

    assert PROMOTE_KIND_PAPER.side_channel_apply is None
    assert PROMOTE_KIND_TOPIC.side_channel_apply is None
    assert PROMOTE_KIND_THEME.side_channel_apply is None


def test_dataset_kind_has_side_channel_apply() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_DATASET

    assert callable(PROMOTE_KIND_DATASET.side_channel_apply)


def test_dataset_side_channel_apply_writes_data_yaml_and_reports_absent_backup(
    tmp_path, monkeypatch
) -> None:
    import yaml

    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        CanonicalArtifact,
        PromoteDecision,
        PromotePlan,
        SideChannelContext,
    )

    cfg_dir = tmp_path / "cfg"
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    override_path = tmp_path / "bulk" / "fixture-ds"
    decision = PromoteDecision(
        slug="fixture-ds",
        canonical_artifacts=[
            CanonicalArtifact(
                path=Path("datasets/fixture-ds/entity.md"),
                content="",
                validator="entity-mixin",
            )
        ],
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    plan = PromotePlan(
        decisions=[decision],
        failed_candidates=[],
        kind=PROMOTE_KIND_DATASET,
        dataset_audit_extras={
            "fixture-ds": {"override_path": str(override_path)},
        },
    )

    side_channel_apply = PROMOTE_KIND_DATASET.side_channel_apply
    assert side_channel_apply is not None
    result = side_channel_apply(
        SideChannelContext(
            decision=decision,
            plan=plan,
            commons_root=tmp_path / "commons",
            op_id="opSIDE",
        )
    )

    yaml_path = cfg_dir / "data.yaml"
    absent_backup = cfg_dir / "data.yaml.bak.opSIDE.absent"
    assert result.artifact_paths == [yaml_path]
    assert result.backup_paths == [absent_backup]
    assert yaml.safe_load(yaml_path.read_text(encoding="utf-8")) == {
        "fixture-ds": str(override_path)
    }
    assert absent_backup.is_file()


def test_dataset_side_channel_apply_reports_existing_file_backup(
    tmp_path, monkeypatch
) -> None:
    import yaml

    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        PromoteDecision,
        PromotePlan,
        SideChannelContext,
    )

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    existing_content = "other: /data/other\n"
    (cfg_dir / "data.yaml").write_text(existing_content, encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    override_path = tmp_path / "bulk" / "fixture-ds"
    decision = PromoteDecision(
        slug="fixture-ds",
        canonical_artifacts=[],
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    plan = PromotePlan(
        decisions=[decision],
        failed_candidates=[],
        kind=PROMOTE_KIND_DATASET,
        dataset_audit_extras={
            "fixture-ds": {"override_path": str(override_path)},
        },
    )
    side_channel_apply = PROMOTE_KIND_DATASET.side_channel_apply
    assert side_channel_apply is not None

    result = side_channel_apply(
        SideChannelContext(
            decision=decision,
            plan=plan,
            commons_root=tmp_path / "commons",
            op_id="opBACKUP",
        )
    )

    yaml_path = cfg_dir / "data.yaml"
    backup_path = cfg_dir / "data.yaml.bak.opBACKUP"
    assert result.artifact_paths == [yaml_path]
    assert result.backup_paths == [backup_path]
    assert backup_path.read_text(encoding="utf-8") == existing_content
    assert yaml.safe_load(yaml_path.read_text(encoding="utf-8")) == {
        "fixture-ds": str(override_path),
        "other": "/data/other",
    }


def test_dataset_side_channel_apply_allows_multiple_decisions_per_op(
    tmp_path, monkeypatch
) -> None:
    import yaml

    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        PromoteDecision,
        PromotePlan,
        SideChannelContext,
    )

    cfg_dir = tmp_path / "cfg"
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    first = PromoteDecision(
        slug="fixture-a",
        canonical_artifacts=[],
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    second = PromoteDecision(
        slug="fixture-b",
        canonical_artifacts=[],
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    plan = PromotePlan(
        decisions=[first, second],
        failed_candidates=[],
        kind=PROMOTE_KIND_DATASET,
        dataset_audit_extras={
            "fixture-a": {"override_path": str(tmp_path / "bulk" / "a")},
            "fixture-b": {"override_path": str(tmp_path / "bulk" / "b")},
        },
    )
    side_channel_apply = PROMOTE_KIND_DATASET.side_channel_apply
    assert side_channel_apply is not None

    first_result = side_channel_apply(
        SideChannelContext(
            decision=first,
            plan=plan,
            commons_root=tmp_path / "commons",
            op_id="opBATCH",
        )
    )
    second_result = side_channel_apply(
        SideChannelContext(
            decision=second,
            plan=plan,
            commons_root=tmp_path / "commons",
            op_id="opBATCH",
        )
    )

    yaml_path = cfg_dir / "data.yaml"
    absent_backup = cfg_dir / "data.yaml.bak.opBATCH.absent"
    assert first_result.backup_paths == [absent_backup]
    assert second_result.backup_paths == [absent_backup]
    assert yaml.safe_load(yaml_path.read_text(encoding="utf-8")) == {
        "fixture-a": str(tmp_path / "bulk" / "a"),
        "fixture-b": str(tmp_path / "bulk" / "b"),
    }
    assert absent_backup.is_file()


def test_dataset_side_channel_apply_rejects_malformed_override_path(tmp_path) -> None:
    import pytest

    from science_tool.commons.errors import PromoteCandidateError
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        PromoteDecision,
        PromotePlan,
        SideChannelContext,
    )

    decision = PromoteDecision(
        slug="fixture-ds",
        canonical_artifacts=[],
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    plan = PromotePlan(
        decisions=[decision],
        failed_candidates=[],
        kind=PROMOTE_KIND_DATASET,
        dataset_audit_extras={"fixture-ds": {"override_path": None}},
    )
    side_channel_apply = PROMOTE_KIND_DATASET.side_channel_apply
    assert side_channel_apply is not None

    with pytest.raises(PromoteCandidateError, match="string override_path"):
        side_channel_apply(
            SideChannelContext(
                decision=decision,
                plan=plan,
                commons_root=tmp_path / "commons",
                op_id="opBAD",
            )
        )


def test_eligibility_verdict_enum_values() -> None:
    from science_tool.commons.promote import EligibilityVerdict

    assert EligibilityVerdict.ELIGIBLE.value == "eligible"
    assert EligibilityVerdict.SKIP_SILENT.value == "skip_silent"
    assert EligibilityVerdict.FAIL.value == "fail"
    assert len(list(EligibilityVerdict)) == 3


def test_promote_kind_paper_constant() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER

    assert PROMOTE_KIND_PAPER.kind == "paper"
    assert PROMOTE_KIND_PAPER.source_subdirs == ("entities/papers",)
    assert PROMOTE_KIND_PAPER.overlay_dest_subdir == "overlays/papers"
    assert PROMOTE_KIND_PAPER.commons_subdir == "papers"
    assert PROMOTE_KIND_PAPER.id_prefix == "paper:"
    assert PROMOTE_KIND_PAPER.slug_match == "casefold"
    assert PROMOTE_KIND_PAPER.eligibility_filter is None
    assert "paper" in PROMOTE_KIND_PAPER.mixin_schema_id


def test_promote_kind_topic_constant() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC

    assert PROMOTE_KIND_TOPIC.kind == "topic"
    assert PROMOTE_KIND_TOPIC.source_subdirs == ("entities/topics",)
    assert PROMOTE_KIND_TOPIC.overlay_dest_subdir == "overlays/topics"
    assert PROMOTE_KIND_TOPIC.commons_subdir == "topics"
    assert PROMOTE_KIND_TOPIC.id_prefix == "topic:"
    assert PROMOTE_KIND_TOPIC.slug_match == "exact"
    assert PROMOTE_KIND_TOPIC.eligibility_filter is None
    assert "topic" in PROMOTE_KIND_TOPIC.mixin_schema_id


def test_promote_kind_theme_constant() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_THEME

    assert PROMOTE_KIND_THEME.kind == "theme"
    assert PROMOTE_KIND_THEME.source_subdirs == ("entities/themes",)
    assert PROMOTE_KIND_THEME.overlay_dest_subdir == "overlays/themes"
    assert PROMOTE_KIND_THEME.commons_subdir == "themes"
    assert PROMOTE_KIND_THEME.id_prefix == "theme:"
    assert PROMOTE_KIND_THEME.slug_match == "exact"
    # eligibility_filter is set in Task 3; this test only checks the constant
    # exists with the kind-specific structural fields.
    assert PROMOTE_KIND_THEME.mixin_schema_id == "https://schemas.science/mixin-theme-2.0.json"


def test_promote_kind_dataset_constant_shape():
    from science_tool.commons.promote import PROMOTE_KIND_DATASET

    assert PROMOTE_KIND_DATASET.kind == "dataset"
    assert PROMOTE_KIND_DATASET.source_subdirs == ("entities/datasets",)
    assert PROMOTE_KIND_DATASET.overlay_dest_subdir == "overlays/datasets"
    assert PROMOTE_KIND_DATASET.commons_subdir == "datasets"
    assert PROMOTE_KIND_DATASET.id_prefix == "dataset:"
    # Dataset slug rule: lowercase-kebab
    assert PROMOTE_KIND_DATASET.slug_regex.match("ccle-proteomics-nusinow-2020")
    assert not PROMOTE_KIND_DATASET.slug_regex.match("NotKebab")
    assert PROMOTE_KIND_DATASET.slug_match == "exact"
    assert "mixin-dataset" in PROMOTE_KIND_DATASET.mixin_schema_id


def test_four_kinds_have_distinct_id_prefixes() -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        PROMOTE_KIND_PAPER,
        PROMOTE_KIND_THEME,
        PROMOTE_KIND_TOPIC,
    )

    prefixes = {
        PROMOTE_KIND_DATASET.id_prefix,
        PROMOTE_KIND_PAPER.id_prefix,
        PROMOTE_KIND_TOPIC.id_prefix,
        PROMOTE_KIND_THEME.id_prefix,
    }
    assert prefixes == {"dataset:", "paper:", "topic:", "theme:"}


def test_theme_eligibility_cross_project_is_eligible() -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_THEME,
        EligibilityVerdict,
    )

    f = PROMOTE_KIND_THEME.eligibility_filter
    assert f is not None
    verdict = f({"theme_scope": "cross-project"})
    assert verdict == EligibilityVerdict.ELIGIBLE


def test_theme_eligibility_project_scope_is_skip_silent() -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_THEME,
        EligibilityVerdict,
    )

    f = PROMOTE_KIND_THEME.eligibility_filter
    assert f is not None
    verdict = f({"theme_scope": "project"})
    assert verdict == EligibilityVerdict.SKIP_SILENT


def test_theme_eligibility_missing_or_malformed_is_fail() -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_THEME,
        EligibilityVerdict,
    )

    f = PROMOTE_KIND_THEME.eligibility_filter
    assert f is not None
    assert f({}) == EligibilityVerdict.FAIL
    assert f({"theme_scope": None}) == EligibilityVerdict.FAIL
    assert f({"theme_scope": "global"}) == EligibilityVerdict.FAIL
    assert f({"theme_scope": ""}) == EligibilityVerdict.FAIL


def test_paper_and_topic_have_no_eligibility_filter() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, PROMOTE_KIND_TOPIC

    assert PROMOTE_KIND_PAPER.eligibility_filter is None
    assert PROMOTE_KIND_TOPIC.eligibility_filter is None


def test_canonical_artifact_is_frozen_and_holds_three_fields() -> None:
    from science_tool.commons.promote import CanonicalArtifact

    art = CanonicalArtifact(
        path=Path("datasets/foo/entity.md"),
        content="---\nid: dataset:foo\n---\n",
        validator="entity-mixin",
    )
    assert art.path == Path("datasets/foo/entity.md")
    assert art.content.startswith("---")
    assert art.validator == "entity-mixin"
    import dataclasses

    assert dataclasses.is_dataclass(art)
    # frozen - direct attr assignment should raise
    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(art, "content", "mutated")


def test_canonical_artifact_validator_literal_rejects_unknown() -> None:
    # Literal typing isn't runtime-enforced, but document accepted values:
    from science_tool.commons.promote import CanonicalArtifact

    for v in ("entity-mixin", "frictionless-datapackage", "plain"):
        CanonicalArtifact(path=Path("x.md"), content="", validator=v)


def test_promote_decision_uses_canonical_artifacts_list():
    """Paper/topic/theme decisions carry a one-element artifact list (regression)."""
    from pathlib import Path

    from science_tool.commons.promote import CanonicalArtifact, PromoteDecision

    art = CanonicalArtifact(
        path=Path("papers/Adams2025.md"),
        content="---\nid: paper:Adams2025\n---\nbody\n",
        validator="entity-mixin",
    )
    d = PromoteDecision(
        slug="Adams2025",
        canonical_artifacts=[art],
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    assert len(d.canonical_artifacts) == 1
    assert d.canonical_artifacts[0].path == Path("papers/Adams2025.md")
    # The old singular attrs must be gone:
    assert not hasattr(d, "canonical_path")
    assert not hasattr(d, "canonical_content")


def test_promote_kind_dataset_filter_and_slug_source():
    from science_tool.commons.promote import PROMOTE_KIND_DATASET

    assert PROMOTE_KIND_DATASET.filename_prefix == ""
    assert PROMOTE_KIND_DATASET.slug_from_id is True


def test_paper_topic_theme_keep_filename_slug_semantics():
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        PROMOTE_KIND_THEME,
        PROMOTE_KIND_TOPIC,
    )

    for k in (PROMOTE_KIND_PAPER, PROMOTE_KIND_TOPIC, PROMOTE_KIND_THEME):
        assert k.filename_prefix == ""
        assert k.slug_from_id is False


def test_dataset_discovery_uses_id_slug_when_filename_stem_differs(tmp_path, monkeypatch):
    """data-ccle-proteomics.md with id dataset:ccle-proteomics-nusinow-2020 -> slug 'ccle-proteomics-nusinow-2020'."""
    import shutil
    import subprocess

    src = Path(__file__).parent / "fixtures" / "promote" / "proj-dataset"
    proj = tmp_path / "proj-dataset"
    shutil.copytree(src, proj)
    (proj / "entities/datasets/fixture-ds.md").rename(proj / "entities/datasets/fixture.md")
    f = proj / "entities/datasets/fixture.md"
    text = f.read_text(encoding="utf-8")
    text = text.replace("id: dataset:fixture-ds", "id: dataset:fixture-ds-2026-01")
    f.write_text(text, encoding="utf-8")
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
    monkeypatch.setattr("science_tool.commons.promote.resolve_project_by_id", lambda s: proj)
    from science_tool.commons.promote import PROMOTE_KIND_DATASET, discover_candidates

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    assert "fixture-ds-2026-01" in discovery.candidates_by_slug
    [candidate] = discovery.candidates_by_slug["fixture-ds-2026-01"]
    assert candidate.slug == "fixture-ds-2026-01"
    assert "fixture" not in discovery.candidates_by_slug
