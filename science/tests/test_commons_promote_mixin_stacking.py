"""Tests for `_validate_mixin_stacking` -- the rule guard for `--mixin`."""
from __future__ import annotations

import pytest

from science_model.entity_schema.profile import ProfileComponent
from science_tool.commons.errors import PromoteMixinStackingError
from science_tool.commons.promote import _validate_mixin_stacking


def _c(name: str, version: str = "1.0") -> ProfileComponent:
    return ProfileComponent(name=name, version=version)


def test_empty_tuple_ok() -> None:
    _validate_mixin_stacking(())


def test_single_structural_ok() -> None:
    _validate_mixin_stacking((_c("bio.matrix"),))
    _validate_mixin_stacking((_c("bio.table"),))


def test_single_domain_ok() -> None:
    _validate_mixin_stacking((_c("bio.rnaseq"),))
    _validate_mixin_stacking((_c("bio.scrna"),))
    _validate_mixin_stacking((_c("bio.cna"),))


def test_one_structural_plus_one_domain_ok() -> None:
    _validate_mixin_stacking((_c("bio.matrix"), _c("bio.rnaseq")))
    _validate_mixin_stacking((_c("bio.table"), _c("bio.scrna")))


def test_two_structural_rejected() -> None:
    with pytest.raises(PromoteMixinStackingError, match="structural"):
        _validate_mixin_stacking((_c("bio.matrix"), _c("bio.table")))


def test_two_domain_rejected() -> None:
    with pytest.raises(PromoteMixinStackingError, match="domain"):
        _validate_mixin_stacking((_c("bio.rnaseq"), _c("bio.cna")))


def test_three_with_two_domain_rejected() -> None:
    with pytest.raises(PromoteMixinStackingError, match="domain"):
        _validate_mixin_stacking(
            (_c("bio.matrix"), _c("bio.rnaseq"), _c("bio.cna"))
        )


def test_unknown_bio_extension_passes_stacking_check() -> None:
    """Unknown bio.* names are NOT rejected at the stacking-rule layer.
    Sugar form is caught earlier by _resolve_mixin_arg in cli.py;
    explicit form (e.g. --mixin bio.bogus/1.0) is expected to parse
    syntactically, pass stacking, and fail in plan_promote's
    read_merge_policy(active_profile) setup (where SchemaNotFoundError is
    caught and rewrapped as PromoteMixinResolutionError -- see Task 12).
    _validate_artifact (Task 13) also catches the same exception as
    belt-and-suspenders for the rare case where canonical content
    already cites a missing extension.
    """
    _validate_mixin_stacking((_c("bio.weird"),))  # no exception
