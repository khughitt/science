"""The generation matrix: one generation number selects a whole mixin-version row.

`default_profile_for_kind` no longer hard-codes a single default mixin version per kind. It reads
a `generation` -- gen 2 is the D5 baseline, gen 3 is the data-product row -- and the two must not
bleed into each other: gen 3 moves `dataset` and `hypothesis` forward and leaves every other kind
where gen 2 left it. The default generation stays 2 so every existing caller is byte-identical.
"""

from __future__ import annotations

import pytest

from science_model.entity_schema.profile import ProfileParseError, default_profile_for_kind


def test_generation_2_defaults_unchanged():
    assert default_profile_for_kind("dataset", generation=2).render().endswith("+dataset/2.0")
    assert default_profile_for_kind("hypothesis", generation=2).render().endswith("+hypothesis/1.0")


def test_generation_3_selects_new_mixins():
    assert default_profile_for_kind("dataset", generation=3).render().endswith("+dataset/3.0")
    assert default_profile_for_kind("hypothesis", generation=3).render().endswith("+hypothesis/2.0")


def test_generation_3_leaves_other_kinds_at_2_0():
    assert default_profile_for_kind("paper", generation=3).render().endswith("+paper/2.0")
    assert default_profile_for_kind("topic", generation=3).render().endswith("+topic/2.0")
    assert default_profile_for_kind("theme", generation=3).render().endswith("+theme/2.0")


def test_default_generation_is_2():
    assert default_profile_for_kind("dataset").render().endswith("+dataset/2.0")
    assert default_profile_for_kind("hypothesis").render().endswith("+hypothesis/1.0")


def test_unknown_generation_is_rejected():
    with pytest.raises(ProfileParseError, match="unknown entity-schema generation"):
        default_profile_for_kind("dataset", generation=99)


def test_unknown_kind_is_rejected():
    with pytest.raises(ProfileParseError, match="unknown kind"):
        default_profile_for_kind("nonesuch", generation=2)
