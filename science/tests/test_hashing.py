"""Body hash computation: header-aware, deterministic."""

import hashlib

from science_tool.project_artifacts.hashing import body_hash
from science_tool.project_artifacts.registry_schema import HeaderKind, HeaderProtocol


SHEBANG = HeaderProtocol(kind=HeaderKind.SHEBANG_COMMENT, comment_prefix="#")


def _build(body: bytes, header_hash: str = "f" * 64) -> bytes:
    return (
        b"#!/usr/bin/env bash\n"
        b"# science-managed-artifact: x\n"
        b"# science-managed-version: 2026.04.26\n" + f"# science-managed-source-sha256: {header_hash}\n".encode() + body
    )


def test_body_hash_is_deterministic() -> None:
    raw = _build(b"echo hi\n")
    assert body_hash(raw, SHEBANG) == body_hash(raw, SHEBANG)


def test_body_hash_strips_header() -> None:
    body = b"echo hi\n"
    expected = hashlib.sha256(body).hexdigest()
    assert body_hash(_build(body), SHEBANG) == expected


def test_body_hash_insensitive_to_header_value_changes() -> None:
    body = b"echo hi\n"
    h1 = body_hash(_build(body, "a" * 64), SHEBANG)
    h2 = body_hash(_build(body, "b" * 64), SHEBANG)
    assert h1 == h2


def test_body_hash_sensitive_to_body_changes() -> None:
    h1 = body_hash(_build(b"echo a\n"), SHEBANG)
    h2 = body_hash(_build(b"echo b\n"), SHEBANG)
    assert h1 != h2


def test_body_hash_when_no_header_uses_full_bytes() -> None:
    raw = b"#!/usr/bin/env bash\necho hi\n"
    expected = hashlib.sha256(raw).hexdigest()
    assert body_hash(raw, SHEBANG) == expected
