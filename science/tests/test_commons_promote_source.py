"""Tests for source-aware promote: default trust, --verify-digests, validation."""
from __future__ import annotations

import pytest


def test_digest_mismatch_error_names_resource_and_values():
    from science_tool.commons.errors import (
        CommonsError,
        PromoteResourceDigestMismatchError,
    )

    err = PromoteResourceDigestMismatchError(
        slug="walker",
        resource_name="walker-h5ad",
        expected=("sha256:" + "a" * 64, 10),
        actual=("sha256:" + "b" * 64, 11),
        path=None,
    )
    assert isinstance(err, CommonsError)
    assert err.slug == "walker"
    assert err.resource_name == "walker-h5ad"
    assert "walker-h5ad" in str(err)
    assert ("sha256:" + "a" * 64) in str(err)
