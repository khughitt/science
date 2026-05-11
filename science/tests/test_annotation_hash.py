# science/tests/test_annotation_hash.py
"""Unit tests for science_tool.annotation.hash."""
from science_tool.annotation.hash import content_hash


def test_content_hash_format() -> None:
    h = content_hash("hello world", "llm-audit:gap-d-v1")
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 64  # 32-byte hex


def test_content_hash_deterministic() -> None:
    a = content_hash("the same sentence", "llm-audit:gap-d-v1")
    b = content_hash("the same sentence", "llm-audit:gap-d-v1")
    assert a == b


def test_content_hash_changes_with_text() -> None:
    a = content_hash("text one", "llm-audit:gap-d-v1")
    b = content_hash("text two", "llm-audit:gap-d-v1")
    assert a != b


def test_content_hash_changes_with_source_version() -> None:
    a = content_hash("same text", "llm-audit:gap-d-v1")
    b = content_hash("same text", "llm-audit:gap-d-v2")
    assert a != b


def test_content_hash_separator_prevents_collisions() -> None:
    # "abc" + "def" must differ from "ab" + "cdef" if naive concat were used.
    a = content_hash("abc", "def")
    b = content_hash("ab", "cdef")
    assert a != b
