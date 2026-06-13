"""Verify `book` is registered as a core OPERATIONAL kind backed by BookEntity.

A book is a source that *provides* evidence to epistemic entities but is never
itself a belief-bearing claim — so it is OPERATIONAL, mirroring `paper` and
`talk`.
"""

from __future__ import annotations

from science_model.entities import BookEntity, EntityClass
from science_model.profiles.core import CORE_PROFILE
from science_tool.entities import default_status, resolve_path_policy, valid_statuses
from science_tool.graph.entity_registry import EntityRegistry

# BookEntity field/coercion behaviour is covered alongside other typed entities
# in model/tests/test_typed_entities.py.


def test_book_in_core_profile():
    kinds = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "book" in kinds


def test_book_kind_class_is_operational():
    registry = EntityRegistry.with_core_types()
    assert registry.kind_class("book") == EntityClass.OPERATIONAL


def test_book_resolves_to_book_entity():
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("book") is BookEntity


def test_book_path_policy_and_status():
    policy = resolve_path_policy("book")
    assert policy.root.name == "books"
    assert policy.strategy == "citekey"
    assert default_status("book") == "active"
    assert valid_statuses("book") == frozenset({"active", "retired"})
