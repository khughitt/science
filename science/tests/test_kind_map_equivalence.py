"""Equivalence-before-flip guard for Task 4 (and Task 5).

Frozen copies of the original tool-map literals are pasted here verbatim. The
tests assert the live ``science_tool.entities`` maps equal these frozen copies,
so the flip from ``CORE_KINDS`` to ``CORE_PROFILE`` derivation is proven to be
value-for-value identical. The status fixtures are pasted now (unused until
Task 5) so Task 5 can assert against them without re-deriving the literals.
"""

from __future__ import annotations

from pathlib import Path

from science_model.templates import MIGRATED_KINDS

from science_tool.entities import (
    _BUILTIN_MARKDOWN_POLICIES,
    _DEFAULT_STATUS,
    _SHORTFORM_ENTITY_KINDS,
    _STATUS_VALUES,
    EntityPathPolicy,
)
from science_tool.graph.entity_registry import EntityRegistry

# --- Frozen copies of the original literals (do not edit to match drift) ---

FROZEN_MARKDOWN_POLICIES = {
    "question": EntityPathPolicy(Path("entities/questions"), "numeric"),
    "hypothesis": EntityPathPolicy(Path("entities/hypotheses"), "numeric"),
    "patch-definition": EntityPathPolicy(Path("entities/patches"), "slug"),
    "proposition": EntityPathPolicy(Path("entities/propositions"), "slug"),
    "interpretation": EntityPathPolicy(Path("entities/interpretations"), "numeric"),
    "discussion": EntityPathPolicy(Path("entities/discussions"), "numeric"),
    "finding": EntityPathPolicy(Path("entities/findings"), "numeric"),
    "inquiry": EntityPathPolicy(Path("entities/inquiries"), "numeric"),
    "theme": EntityPathPolicy(Path("entities/themes"), "numeric"),
    "topic": EntityPathPolicy(Path("entities/topics"), "slug"),
    "evidence-line": EntityPathPolicy(Path("entities/evidence-lines"), "slug"),
    "observation": EntityPathPolicy(Path("entities/observations"), "slug"),
    "falsification": EntityPathPolicy(Path("entities/falsifications"), "slug"),
    "mechanism": EntityPathPolicy(Path("entities/mechanisms"), "numeric"),
    "synthesis": EntityPathPolicy(Path("entities/synthesis"), "numeric"),
    "story": EntityPathPolicy(Path("entities/stories"), "slug"),
    "report": EntityPathPolicy(Path("entities/reports"), "numeric"),
    "plan": EntityPathPolicy(Path("entities/plans"), "numeric"),
    "spec": EntityPathPolicy(Path("entities/specs"), "numeric"),
    "search": EntityPathPolicy(Path("entities/searches"), "numeric"),
    "method": EntityPathPolicy(Path("entities/methods"), "slug"),
    "pre-registration": EntityPathPolicy(Path("entities/pre-registrations"), "numeric"),
    "concept": EntityPathPolicy(Path("entities/concepts"), "slug"),
    "construct": EntityPathPolicy(Path("entities/constructs"), "slug"),
    "decision": EntityPathPolicy(Path("entities/decision"), "verbatim"),
    "paper": EntityPathPolicy(Path("entities/papers"), "citekey"),
    "prose-source": EntityPathPolicy(Path("entities/prose-sources"), "slug"),
    "book": EntityPathPolicy(Path("entities/books"), "citekey"),
    "talk": EntityPathPolicy(Path("entities/talks"), "citekey"),
    "outcome": EntityPathPolicy(Path("entities/outcomes"), "slug"),
    "dataset": EntityPathPolicy(Path("entities/datasets"), "id-local"),
    "workflow": EntityPathPolicy(Path("entities/workflows"), "id-local"),
    "workflow-run": EntityPathPolicy(Path("entities/workflow-runs"), "id-local"),
    "workflow-step": EntityPathPolicy(Path("entities/workflow-steps"), "id-local"),
    "research-question": EntityPathPolicy(Path("entities/research-question.md"), "singleton"),
    "claim-registry": EntityPathPolicy(Path("entities/claim-registry.yaml"), "singleton"),
}

FROZEN_DEFAULT_STATUS = {
    "evidence-line": "draft",
    "question": "active",
    # ☠️ THE ONE DELIBERATE DIVERGENCE. Every other literal in this file is frozen to prove a
    # refactor changed no VALUES. `hypothesis` is different: its vocabulary was MEANT to change --
    # `status` was the epistemic verdict wearing the lifecycle's name, and the verdict now lives in
    # `verdict`. So this entry is re-frozen to the folded lifecycle ON PURPOSE, and the file keeps
    # doing its job for every other kind. Re-freezing a golden is only ever legitimate when the
    # change it records is the point of the commit; if you are here for any other reason, stop.
    "hypothesis": "active",
    "discussion": "active",
    "interpretation": "active",
    "theme": "active",
    "patch-definition": "active",
    "proposition": "draft",
    "finding": "active",
    "inquiry": "active",
    "topic": "active",
    "observation": "active",
    "falsification": "draft",
    "mechanism": "active",
    "synthesis": "active",
    "story": "draft",
    "report": "active",
    "plan": "active",
    "spec": "active",
    "search": "active",
    "method": "active",
    "pre-registration": "active",
    "paper": "active",
    "prose-source": "active",
    "book": "active",
    "talk": "active",
    "concept": "active",
    "construct": "active",
    "decision": "active",
    "outcome": "active",
    "dataset": "active",
    "workflow": "active",
    "workflow-run": "running",
    "workflow-step": "active",
    "validation-report": "active",
}

FROZEN_STATUS_VALUES = {
    "evidence-line": frozenset({"draft", "active", "retired", "archived"}),
    "question": frozenset({"active", "partially-answered", "answered", "deferred", "retired", "archived"}),
    # The folded LIFECYCLE -- see the note on FROZEN_DEFAULT_STATUS["hypothesis"] above. The old set
    # ({proposed, under-investigation, partially-supported, supported, weakened, refuted, archived})
    # was the VERDICT vocabulary, and it left `archived` as the only lifecycle word a hypothesis had.
    "hypothesis": frozenset(
        {"draft", "active", "complete", "superseded", "retired", "archived"}
    ),
    "discussion": frozenset({"active", "complete", "superseded", "archived"}),
    "interpretation": frozenset({"active", "complete", "superseded", "archived"}),
    "theme": frozenset({"draft", "active", "superseded", "retired", "archived"}),
    "patch-definition": frozenset({"active", "retired"}),
    "proposition": frozenset({"draft", "active", "supported", "contested", "weakened", "retired", "superseded", "archived"}),
    "finding": frozenset({"active", "superseded", "retired", "archived"}),
    "inquiry": frozenset({"active", "complete", "superseded", "archived"}),
    "topic": frozenset({"active", "superseded", "retired", "archived"}),
    "observation": frozenset({"active", "retired", "archived"}),
    "falsification": frozenset({"draft", "active", "retired", "archived"}),
    "mechanism": frozenset({"active", "superseded", "retired", "archived"}),
    "synthesis": frozenset({"active", "superseded", "retired", "archived"}),
    "story": frozenset({"draft", "developing", "mature", "superseded"}),
    # `draft`/`complete` added: pure-lifecycle kinds, and a report had no way to say it
    # was FINISHED. `plan: proposed` deliberately NOT minted -- it is drift toward `draft`.
    "report": frozenset({"draft", "active", "complete", "superseded", "retired", "archived"}),
    "plan": frozenset({"draft", "active", "complete", "superseded", "retired", "archived"}),
    "spec": frozenset({"draft", "active", "complete", "superseded", "retired", "archived"}),
    "search": frozenset({"active", "complete", "retired", "archived"}),
    "method": frozenset({"active", "superseded", "retired", "archived"}),
    # `committed` added: the freeze point, and the status both templates/pre-registration.md
    # and commands/pre-register.md tell authors to write. Its COMMITMENT axis
    # (committed/amended) is not a document lifecycle -- draft/complete stay out until the
    # lifecycle axis is split off.
    "pre-registration": frozenset(
        {"active", "committed", "amended", "retired"}
    ),
    "paper": frozenset({"active", "retired"}),
    "prose-source": frozenset({"active", "retired"}),
    "book": frozenset({"active", "retired"}),
    "talk": frozenset({"active", "retired"}),
    "concept": frozenset({"active", "deprecated"}),
    "construct": frozenset({"active", "retired"}),
    "decision": frozenset({"active", "superseded", "abandoned", "archived"}),
    "outcome": frozenset({"active", "retired"}),
    "dataset": frozenset({"proposed", "candidate", "active", "retired", "deprecated"}),
    "workflow": frozenset({"planned", "active", "deprecated", "retired"}),
    "workflow-run": frozenset({"running", "complete", "failed"}),
    "workflow-step": frozenset({"active", "superseded", "retired"}),
    "validation-report": frozenset(
        {"draft", "active", "complete", "superseded", "retired", "archived"}
    ),
}

FROZEN_SHORTFORM = {
    "d": "discussion",
    "h": "hypothesis",
    "i": "interpretation",
    "p": "proposition",
    "q": "question",
    "t": "theme",
}


def test_markdown_policies_equal_prior_literal() -> None:
    assert _BUILTIN_MARKDOWN_POLICIES == FROZEN_MARKDOWN_POLICIES


def test_shortforms_equal_prior_literal() -> None:
    assert _SHORTFORM_ENTITY_KINDS == FROZEN_SHORTFORM


def test_default_status_equals_prior_literal() -> None:
    assert _DEFAULT_STATUS == FROZEN_DEFAULT_STATUS


def test_status_values_equal_prior_literal() -> None:
    assert _STATUS_VALUES == FROZEN_STATUS_VALUES


# --- Task 6: MIGRATED_KINDS + registry entity_class equivalence ---

FROZEN_MIGRATED_KINDS = frozenset(
    {
        "hypothesis",
        "question",
        "interpretation",
        "discussion",
        "theme",
        "proposition",
        "evidence-line",
        "finding",
        "method",
        "paper",
        "prose-source",
        "book",
        "pre-registration",
        "synthesis",
        "concept",
        "observation",
        "mechanism",
        "story",
        "falsification",
    }
)

# The FULL post-Task-2 registry class map (all core kinds incl. the two promoted),
# values as EntityClass.value strings. Captured live verbatim.
FROZEN_KIND_CLASSES = {
    "article": "reference",
    "assumption": "epistemic",
    "book": "operational",
    "chain-audit": "epistemic",
    "claim-registry": "operational",
    "code-file": "operational",
    "concept": "reference",
    "construct": "reference",
    "curation-sweep": "operational",
    "data-package": "operational",
    "dataset": "operational",
    "decision": "reference",
    "discussion": "epistemic",
    "evidence-line": "epistemic",
    "experiment": "operational",
    "falsification": "epistemic",
    "finding": "epistemic",
    "hypothesis": "epistemic",
    "inquiry": "epistemic",
    "interpretation": "epistemic",
    "mechanism": "epistemic",
    "method": "operational",
    "observation": "epistemic",
    "outcome": "reference",
    "paper": "operational",
    "prose-source": "operational",
    "patch-definition": "epistemic",
    "plan": "operational",
    "pre-registration": "operational",
    "proposition": "epistemic",
    "question": "epistemic",
    "report": "epistemic",
    "research-package": "operational",
    "research-question": "epistemic",
    "search": "operational",
    "spec": "operational",
    "story": "epistemic",
    "structural-chain": "epistemic",
    "synthesis": "epistemic",
    "talk": "operational",
    "task": "operational",
    "theme": "epistemic",
    "topic": "reference",
    "transformation": "operational",
    "unknown": "reference",
    "validation-report": "epistemic",
    "variable": "reference",
    "workflow": "operational",
    "workflow-run": "operational",
    "workflow-step": "operational",
}


def test_migrated_kinds_equal_prior_literal() -> None:
    assert set(MIGRATED_KINDS) == FROZEN_MIGRATED_KINDS


def test_registry_entity_class_equals_prior_literal() -> None:
    registry = EntityRegistry.with_core_types()
    live = {k: v.value for k, v in registry.all_kind_classes().items()}
    assert live == FROZEN_KIND_CLASSES
