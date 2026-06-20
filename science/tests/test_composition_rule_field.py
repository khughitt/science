# science/tests/test_composition_rule_field.py
from __future__ import annotations

import pytest
from science_model.entities import Entity, EntityType
from science_model.reasoning import RESERVED_COMPOSITION_RULES, WEAKEST_LINK_COMPOSITION_RULES, CompositionRule


def _entity(**kw):
    # type MUST match core_entity_type_for_kind(kind) — Entity._validate_kind_type_consistency
    # (entities.py:343) rejects a mismatch, so direct construction requires an explicit type=.
    base = dict(
        id="hypothesis:h1", kind="hypothesis", type=EntityType.HYPOTHESIS, title="H1", project="p",
        ontology_terms=[], related=[], source_refs=[], content_preview="",
        file_path="x.md",
    )
    base.update(kw)
    return Entity(**base)


def test_default_is_none():
    assert _entity().composition_rule is None


def test_accepts_weakest_link_rules():
    for rule in ("all_steps", "conjunctive"):
        assert _entity(composition_rule=rule).composition_rule == CompositionRule(rule)


@pytest.mark.parametrize("rule", ["evidence_union", "faceted_support"])
def test_reserved_rules_rejected_at_model_layer(rule):
    with pytest.raises(ValueError, match="reserved"):
        _entity(composition_rule=rule)


def test_composition_rule_rejected_on_non_bundle_kind():
    with pytest.raises(ValueError, match="bundle kinds"):
        _entity(id="proposition:p1", kind="proposition", type=EntityType.PROPOSITION, composition_rule="conjunctive")


def test_enum_partitions_are_disjoint_and_complete():
    assert RESERVED_COMPOSITION_RULES.isdisjoint(WEAKEST_LINK_COMPOSITION_RULES)
    assert RESERVED_COMPOSITION_RULES | WEAKEST_LINK_COMPOSITION_RULES == set(CompositionRule)
