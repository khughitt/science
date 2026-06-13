from __future__ import annotations

from pathlib import Path

from science_tool.entities import (
    default_status,
    is_markdown_entity_kind,
    resolve_path_policy,
    valid_statuses,
)


def test_book_is_markdown_entity_kind() -> None:
    assert is_markdown_entity_kind("book") is True


def test_book_path_policy_home_and_strategy() -> None:
    policy = resolve_path_policy("book")
    assert policy.root == Path("entities/books")
    assert policy.strategy == "citekey"


def test_book_default_status_and_valid_statuses() -> None:
    # create_entity indexes _DEFAULT_STATUS[kind] and _STATUS_VALUES[kind] directly,
    # so both maps must carry "book" or entity creation KeyErrors.
    assert default_status("book") == "active"
    assert valid_statuses("book") == frozenset({"active", "retired"})
