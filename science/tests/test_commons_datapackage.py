"""Tests for science_tool.commons.datapackage."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.datapackage import (
    DatapackageDescriptor,
    DataResource,
    parse_resource_hash,
    read_datapackage,
    validate_logical_path,
)
from science_tool.commons.errors import CommonsDatapackageError, DataLogicalPathError

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


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_read_datapackage_parses_valid(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "name: rnaseq-example\n"
        'profile: "data-package"\n'
        "resources:\n"
        "  - name: counts\n"
        "    path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n'
        "  - name: meta\n"
        "    path: raw/meta.csv\n"
        f'    hash: "{_GOOD_HASH}"\n',
    )
    descriptor = read_datapackage(dp)
    assert isinstance(descriptor, DatapackageDescriptor)
    assert descriptor.source_path == dp
    assert descriptor.resources == (
        DataResource(path="counts.parquet", name="counts", hash=_GOOD_HASH),
        DataResource(path="raw/meta.csv", name="meta", hash=_GOOD_HASH),
    )


def test_resource_lookup_hit_and_miss(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n',
    )
    descriptor = read_datapackage(dp)
    assert descriptor.resource("counts.parquet").path == "counts.parquet"
    with pytest.raises(CommonsDatapackageError, match="no resource"):
        descriptor.resource("missing.parquet")


def test_resource_lookup_accepts_name_or_path(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - name: variants\n"
        "    path: data/variants.csv\n"
        f'    hash: "{_GOOD_HASH}"\n',
    )
    descriptor = read_datapackage(dp)
    assert descriptor.resource("variants").path == "data/variants.csv"
    assert descriptor.resource("data/variants.csv").name == "variants"


def test_read_datapackage_rejects_ambiguous_resource_alias(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - name: data/variants.csv\n"
        "    path: other.csv\n"
        f'    hash: "{_GOOD_HASH}"\n'
        "  - name: variants\n"
        "    path: data/variants.csv\n"
        f'    hash: "{_GOOD_HASH}"\n',
    )
    with pytest.raises(CommonsDatapackageError, match="ambiguous resource alias"):
        read_datapackage(dp)


def test_read_datapackage_rejects_malformed_yaml(tmp_path: Path) -> None:
    dp = _write(tmp_path / "datapackage.yaml", "resources: [unclosed\n")
    with pytest.raises(CommonsDatapackageError, match="YAML"):
        read_datapackage(dp)


def test_read_datapackage_rejects_missing_resources(tmp_path: Path) -> None:
    dp = _write(tmp_path / "datapackage.yaml", "name: x\n")
    with pytest.raises(CommonsDatapackageError, match="resources"):
        read_datapackage(dp)


def test_read_datapackage_rejects_empty_resources(tmp_path: Path) -> None:
    dp = _write(tmp_path / "datapackage.yaml", "resources: []\n")
    with pytest.raises(CommonsDatapackageError, match="resources"):
        read_datapackage(dp)


def test_read_datapackage_rejects_duplicate_path(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n'
        "  - path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n',
    )
    with pytest.raises(CommonsDatapackageError, match="duplicate"):
        read_datapackage(dp)


def test_read_datapackage_rejects_invalid_resource_path(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: ../escape.tsv\n"
        f'    hash: "{_GOOD_HASH}"\n',
    )
    with pytest.raises(CommonsDatapackageError, match="invalid path"):
        read_datapackage(dp)


def test_read_datapackage_rejects_missing_hash(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n  - path: counts.parquet\n",
    )
    with pytest.raises(CommonsDatapackageError, match="hash"):
        read_datapackage(dp)


def test_read_datapackage_rejects_malformed_hash(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: counts.parquet\n"
        '    hash: "md5:abc"\n',
    )
    with pytest.raises(CommonsDatapackageError, match="invalid hash"):
        read_datapackage(dp)


def test_read_datapackage_captures_bytes_format_mediatype(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n'
        "    bytes: 12345678\n"
        '    format: "parquet"\n'
        '    mediatype: "application/vnd.apache.parquet"\n',
    )
    descriptor = read_datapackage(dp)
    resource = descriptor.resources[0]
    assert resource.bytes == 12345678
    assert resource.format == "parquet"
    assert resource.mediatype == "application/vnd.apache.parquet"


def test_read_datapackage_optional_fields_default_to_none(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n  - path: counts.parquet\n" f'    hash: "{_GOOD_HASH}"\n',
    )
    resource = read_datapackage(dp).resources[0]
    assert resource.bytes is None
    assert resource.format is None
    assert resource.mediatype is None


def test_read_datapackage_rejects_non_int_bytes(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n'
        '    bytes: "lots"\n',
    )
    with pytest.raises(CommonsDatapackageError, match="bytes"):
        read_datapackage(dp)


def test_read_datapackage_rejects_bool_bytes(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n'
        "    bytes: true\n",
    )
    with pytest.raises(CommonsDatapackageError, match="bytes"):
        read_datapackage(dp)


def test_read_datapackage_rejects_non_str_format(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n'
        "    format: 5\n",
    )
    with pytest.raises(CommonsDatapackageError, match="format"):
        read_datapackage(dp)


def test_read_datapackage_rejects_non_str_mediatype(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n'
        "    mediatype: 5\n",
    )
    with pytest.raises(CommonsDatapackageError, match="mediatype"):
        read_datapackage(dp)
