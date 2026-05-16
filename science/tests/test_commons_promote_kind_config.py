"""Tests for the kind-config types in science_tool.commons.promote."""
from __future__ import annotations

import re


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


def test_eligibility_verdict_enum_values() -> None:
    from science_tool.commons.promote import EligibilityVerdict

    assert EligibilityVerdict.ELIGIBLE.value == "eligible"
    assert EligibilityVerdict.SKIP_SILENT.value == "skip_silent"
    assert EligibilityVerdict.FAIL.value == "fail"
    assert len(list(EligibilityVerdict)) == 3


def test_promote_kind_paper_constant() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER

    assert PROMOTE_KIND_PAPER.kind == "paper"
    assert PROMOTE_KIND_PAPER.source_subdirs == ("doc/papers",)
    assert PROMOTE_KIND_PAPER.overlay_dest_subdir == "doc/papers"
    assert PROMOTE_KIND_PAPER.commons_subdir == "papers"
    assert PROMOTE_KIND_PAPER.id_prefix == "paper:"
    assert PROMOTE_KIND_PAPER.slug_match == "casefold"
    assert PROMOTE_KIND_PAPER.eligibility_filter is None
    assert "paper" in PROMOTE_KIND_PAPER.mixin_schema_id


def test_promote_kind_topic_constant() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC

    assert PROMOTE_KIND_TOPIC.kind == "topic"
    assert PROMOTE_KIND_TOPIC.source_subdirs == ("doc/topics", "doc/background/topics")
    assert PROMOTE_KIND_TOPIC.overlay_dest_subdir == "doc/topics"
    assert PROMOTE_KIND_TOPIC.commons_subdir == "topics"
    assert PROMOTE_KIND_TOPIC.id_prefix == "topic:"
    assert PROMOTE_KIND_TOPIC.slug_match == "exact"
    assert PROMOTE_KIND_TOPIC.eligibility_filter is None
    assert "topic" in PROMOTE_KIND_TOPIC.mixin_schema_id


def test_promote_kind_theme_constant() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_THEME

    assert PROMOTE_KIND_THEME.kind == "theme"
    assert PROMOTE_KIND_THEME.source_subdirs == ("doc/themes",)
    assert PROMOTE_KIND_THEME.overlay_dest_subdir == "doc/themes"
    assert PROMOTE_KIND_THEME.commons_subdir == "themes"
    assert PROMOTE_KIND_THEME.id_prefix == "theme:"
    assert PROMOTE_KIND_THEME.slug_match == "exact"
    # eligibility_filter is set in Task 3; this test only checks the constant
    # exists with the kind-specific structural fields.
    assert "theme" in PROMOTE_KIND_THEME.mixin_schema_id


def test_three_kinds_have_distinct_id_prefixes() -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        PROMOTE_KIND_THEME,
        PROMOTE_KIND_TOPIC,
    )

    prefixes = {
        PROMOTE_KIND_PAPER.id_prefix,
        PROMOTE_KIND_TOPIC.id_prefix,
        PROMOTE_KIND_THEME.id_prefix,
    }
    assert prefixes == {"paper:", "topic:", "theme:"}


def test_theme_eligibility_cross_project_is_eligible() -> None:
    from science_tool.commons.promote import (
        EligibilityVerdict,
        PROMOTE_KIND_THEME,
    )

    f = PROMOTE_KIND_THEME.eligibility_filter
    assert f is not None
    verdict = f({"theme_scope": "cross-project"})
    assert verdict == EligibilityVerdict.ELIGIBLE


def test_theme_eligibility_project_scope_is_skip_silent() -> None:
    from science_tool.commons.promote import (
        EligibilityVerdict,
        PROMOTE_KIND_THEME,
    )

    f = PROMOTE_KIND_THEME.eligibility_filter
    assert f is not None
    verdict = f({"theme_scope": "project"})
    assert verdict == EligibilityVerdict.SKIP_SILENT


def test_theme_eligibility_missing_or_malformed_is_fail() -> None:
    from science_tool.commons.promote import (
        EligibilityVerdict,
        PROMOTE_KIND_THEME,
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
