"""Verify `talk` is registered as a core OPERATIONAL kind backed by TalkEntity.

A talk (recorded seminar / conference presentation) is a source that *provides*
evidence to epistemic entities but is never itself a belief-bearing claim — so it
is OPERATIONAL, mirroring `paper`.
"""

from __future__ import annotations

from science_model.entities import EntityClass, TalkEntity
from science_model.profiles.core import CORE_PROFILE
from science_tool.entities import default_status, resolve_path_policy, valid_statuses
from science_tool.graph.entity_registry import EntityRegistry

# TalkEntity field/coercion behaviour (scalar speakers, recording fields) is
# covered alongside the other typed entities in model/tests/test_typed_entities.py.


def test_talk_in_core_profile():
    kinds = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "talk" in kinds


def test_talk_kind_class_is_operational():
    registry = EntityRegistry.with_core_types()
    assert registry.kind_class("talk") == EntityClass.OPERATIONAL


def test_talk_resolves_to_talk_entity():
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("talk") is TalkEntity


def test_talk_path_policy_and_status():
    policy = resolve_path_policy("talk")
    assert policy.root.name == "talks"
    assert policy.strategy == "citekey"
    assert default_status("talk") == "active"
    assert valid_statuses("talk") == frozenset({"active", "retired"})
