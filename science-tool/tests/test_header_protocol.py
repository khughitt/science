"""Header protocol parse/write for shebang_comment."""

import pytest

from science_tool.project_artifacts.header import (
    ParsedHeader,
    header_bytes,
    parse_header,
)
from science_tool.project_artifacts.registry_schema import HeaderKind, HeaderProtocol


SHEBANG = HeaderProtocol(kind=HeaderKind.SHEBANG_COMMENT, comment_prefix="#")


def _rendered(name: str, version: str, h: str) -> bytes:
    return (
        b"#!/usr/bin/env bash\n"
        + f"# science-managed-artifact: {name}\n".encode()
        + f"# science-managed-version: {version}\n".encode()
        + f"# science-managed-source-sha256: {h}\n".encode()
        + b"echo body\n"
    )


def test_parse_round_trip() -> None:
    raw = _rendered("validate.sh", "2026.04.26", "a" * 64)
    parsed = parse_header(raw, SHEBANG)
    assert parsed == ParsedHeader(name="validate.sh", version="2026.04.26", hash="a" * 64)


def test_header_bytes_renders_correctly() -> None:
    out = header_bytes("validate.sh", "2026.04.26", "a" * 64, SHEBANG)
    assert out == (
        b"# science-managed-artifact: validate.sh\n"
        b"# science-managed-version: 2026.04.26\n"
        b"# science-managed-source-sha256: " + b"a" * 64 + b"\n"
    )


def test_parse_returns_none_when_no_header() -> None:
    raw = b"#!/usr/bin/env bash\necho hi\n"
    assert parse_header(raw, SHEBANG) is None


def test_parse_returns_none_when_no_shebang() -> None:
    raw = (
        b"# science-managed-artifact: x\n"
        b"# science-managed-version: 2026.04.26\n"
        b"# science-managed-source-sha256: " + b"a" * 64 + b"\n"
        b"echo body\n"
    )
    assert parse_header(raw, SHEBANG) is None


def test_parse_rejects_partial_header() -> None:
    raw = (
        b"#!/usr/bin/env bash\n"
        b"# science-managed-artifact: x\n"  # missing version + hash
        b"echo body\n"
    )
    assert parse_header(raw, SHEBANG) is None


def test_parse_rejects_malformed_hash() -> None:
    raw = _rendered("x", "2026.04.26", "not-hex").replace(b"not-hex", b"not-hex" + b" " * 56)
    assert parse_header(raw, SHEBANG) is None


def test_unsupported_kinds_raise_not_implemented() -> None:
    other = HeaderProtocol(kind=HeaderKind.COMMENT, comment_prefix=";")
    with pytest.raises(NotImplementedError, match="v1 supports shebang_comment only"):
        parse_header(b"; foo\n", other)
    with pytest.raises(NotImplementedError, match="v1 supports shebang_comment only"):
        header_bytes("x", "2026.04.26", "a" * 64, other)
