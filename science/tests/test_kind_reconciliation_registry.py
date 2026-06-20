from __future__ import annotations

from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.schema import KindCategory

from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.sources import known_kinds

PRE_EXPANSION_CORE_KINDS = frozenset(
    {
        "book",
        "chain-audit",
        "code-file",
        "data-package",
        "evidence-line",
        "experiment",
        "finding",
        "hypothesis",
        "interpretation",
        "mechanism",
        "method",
        "observation",
        "paper",
        "proposition",
        "question",
        "story",
        "structural-chain",
        "talk",
        "task",
        "theme",
        "workflow",
        "workflow-run",
        "workflow-step",
    }
)

INTENDED_ADDITIONS = frozenset(
    {
        "dataset",
        "variable",
        "assumption",
        "transformation",
        "article",
        "spec",
        "research-package",
        "validation-report",
        "curation-sweep",
        "concept",
        "construct",
        "outcome",
        "pre-registration",
        "research-question",
        "topic",
        "discussion",
        "inquiry",
        "plan",
        "report",
        "synthesis",
        "search",
        "patch-definition",
        "decision",
        "claim-registry",
        "prose-source",
        "unknown",
    }
)

RESERVED = frozenset({"unknown"})


def test_core_kind_recognition_delta_is_exactly_the_intended_additions() -> None:
    now = known_kinds()
    assert PRE_EXPANSION_CORE_KINDS <= now, "lost a previously-core kind"
    assert now - PRE_EXPANSION_CORE_KINDS == INTENDED_ADDITIONS, "unexpected core-kind delta"


def test_assertion4_authored_core_equals_registry_core() -> None:
    registry = EntityRegistry.with_core_types()
    registered_core = registry.core_kinds()
    authored_core = {ek.name for ek in CORE_PROFILE.entity_kinds if ek.category == KindCategory.AUTHORED_CORE}
    assert registered_core - RESERVED == authored_core
