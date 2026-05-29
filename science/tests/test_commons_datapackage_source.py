"""Tests for the datapackage `source` descriptor (ResourceSource + validate_source)."""
from __future__ import annotations

import pytest

from science_tool.commons.datapackage import (
    OUTPUT_ROOT_TOKEN,
    SOURCE_TYPES,
    ResourceSource,
    validate_source,
)


def test_source_types_enum():
    assert SOURCE_TYPES == frozenset({"local", "zenodo", "github", "url", "daemon"})
    assert OUTPUT_ROOT_TOKEN == "${OUTPUT_ROOT}"


@pytest.mark.parametrize(
    "ref",
    [
        "/data/proj/mm30/8.0/scrna/walker2024.h5ad",  # absolute
        "${OUTPUT_ROOT}",                              # bare token
        "${OUTPUT_ROOT}/scrna/walker2024.h5ad",        # token + subpath
    ],
)
def test_validate_source_accepts_local_ref(ref):
    src = validate_source({"type": "local", "ref": ref})
    assert src == ResourceSource(type="local", ref=ref)


@pytest.mark.parametrize(
    "ref",
    [
        "scrna/walker2024.h5ad",        # plain relative
        "",                             # empty
        "   ",                          # whitespace
        "${OUTPUT_ROOT}foo",            # token not followed by '/' or end
        "${SCRATCH}/x.h5ad",            # a different token
        "${OUTPUT_ROOT/x",              # syntactically broken token
        "${OUTPUT_ROOT}/",              # bare token + trailing slash, no subpath
    ],
)
def test_validate_source_rejects_bad_local_ref(ref):
    with pytest.raises(ValueError):
        validate_source({"type": "local", "ref": ref})


def test_validate_source_accepts_url():
    src = validate_source({"type": "url", "ref": "https://example.org/x.h5ad"})
    assert src == ResourceSource(type="url", ref="https://example.org/x.h5ad")


@pytest.mark.parametrize(
    "ref",
    [
        "ftp://example.org/x",  # wrong scheme
        "example.org/x",        # no scheme
        "",                     # empty
        "https://",             # scheme but no host
        "https:///x.h5ad",      # scheme + path but empty host
    ],
)
def test_validate_source_rejects_bad_url(ref):
    with pytest.raises(ValueError):
        validate_source({"type": "url", "ref": ref})


@pytest.mark.parametrize("type_", ["zenodo", "github", "daemon"])
def test_validate_source_accepts_opaque_remote(type_):
    src = validate_source({"type": type_, "ref": "10.5281/zenodo.123"})
    assert src.type == type_ and src.ref == "10.5281/zenodo.123"


@pytest.mark.parametrize("type_", ["zenodo", "github", "daemon"])
def test_validate_source_rejects_blank_opaque_remote(type_):
    with pytest.raises(ValueError):
        validate_source({"type": type_, "ref": "   "})


def test_validate_source_rejects_unknown_type():
    with pytest.raises(ValueError, match="type"):
        validate_source({"type": "s3", "ref": "/x"})


def test_validate_source_rejects_non_mapping():
    with pytest.raises(ValueError):
        validate_source("local")


def test_validate_source_rejects_missing_or_nonstring_ref():
    with pytest.raises(ValueError):
        validate_source({"type": "local"})
    with pytest.raises(ValueError):
        validate_source({"type": "local", "ref": 123})


def test_validate_source_rejects_missing_type():
    with pytest.raises(ValueError, match="type"):
        validate_source({"ref": "/data/x.h5ad"})
