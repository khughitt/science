"""Verify structural-chain and chain-audit are registered as core EPISTEMIC kinds."""

from __future__ import annotations

from science_model.entities import EntityClass
from science_model.profiles.core import CORE_PROFILE
from science_tool.graph.entity_registry import EntityRegistry


def test_structural_chain_in_core_profile():
    kinds = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "structural-chain" in kinds


def test_chain_audit_in_core_profile():
    kinds = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "chain-audit" in kinds


def test_structural_chain_kind_class_is_epistemic():
    registry = EntityRegistry.with_core_types()
    assert registry.kind_class("structural-chain") == EntityClass.EPISTEMIC


def test_chain_audit_kind_class_is_epistemic():
    registry = EntityRegistry.with_core_types()
    assert registry.kind_class("chain-audit") == EntityClass.EPISTEMIC
