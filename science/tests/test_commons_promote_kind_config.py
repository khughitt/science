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
