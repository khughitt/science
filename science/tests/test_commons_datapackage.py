"""Tests for science_tool.commons.datapackage."""
from __future__ import annotations

import pytest

from science_tool.commons.datapackage import (
    parse_resource_hash,
    validate_logical_path,
)
from science_tool.commons.errors import DataLogicalPathError

_GOOD_HASH = "sha256:" + "a" * 64


def test_validate_logical_path_accepts_plain_and_nested() -> None:
    assert validate_logical_path("domains.tsv") == "domains.tsv"
    assert validate_logical_path("raw/chains.csv") == "raw/chains.csv"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        ".",
        "/etc/passwd",
        "raw\\chains.csv",
        "C:/data/x.tsv",
        "C:x.tsv",
        "\\\\server\\share\\x",
        "../escape.tsv",
        "raw/../../escape.tsv",
        "./relative.tsv",
        "raw//double.tsv",
        "trailing/",
    ],
)
def test_validate_logical_path_rejects_unsafe(bad: str) -> None:
    with pytest.raises(DataLogicalPathError):
        validate_logical_path(bad)


def test_parse_resource_hash_accepts_sha256() -> None:
    assert parse_resource_hash(_GOOD_HASH) == ("sha256", "a" * 64)


@pytest.mark.parametrize(
    "bad",
    [
        "a" * 64,                       # bare hex, no prefix
        "md5:" + "a" * 32,              # unsupported algorithm
        "sha1:" + "a" * 40,             # unsupported algorithm
        "sha256:" + "a" * 63,           # too short
        "sha256:" + "a" * 65,           # too long
        "sha256:" + "a" * 64 + "\n",     # trailing newline
        "sha256:" + "a" * 64 + " ",      # trailing space
        "sha256:" + "A" * 64,           # uppercase not allowed
        "sha256:" + "g" * 64,           # non-hex
        "sha256:",                      # empty digest
    ],
)
def test_parse_resource_hash_rejects_bad(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_resource_hash(bad)
