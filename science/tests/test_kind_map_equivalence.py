"""Equivalence-before-flip guard for Task 4 (and Task 5).

Frozen copies of the original tool-map literals are pasted here verbatim. The
tests assert the live ``science_tool.entities`` maps equal these frozen copies,
so the flip from ``CORE_KINDS`` to ``CORE_PROFILE`` derivation is proven to be
value-for-value identical. The status fixtures are pasted now (unused until
Task 5) so Task 5 can assert against them without re-deriving the literals.
"""

from __future__ import annotations

from pathlib import Path

from science_tool.entities import (
    EntityPathPolicy,
    _BUILTIN_MARKDOWN_POLICIES,
    _SHORTFORM_ENTITY_KINDS,
)

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
    "mechanism": EntityPathPolicy(Path("entities/mechanisms"), "numeric"),
    "synthesis": EntityPathPolicy(Path("entities/synthesis"), "numeric"),
    "report": EntityPathPolicy(Path("entities/reports"), "numeric"),
    "plan": EntityPathPolicy(Path("entities/plans"), "numeric"),
    "search": EntityPathPolicy(Path("entities/searches"), "numeric"),
    "method": EntityPathPolicy(Path("entities/methods"), "slug"),
    "pre-registration": EntityPathPolicy(Path("entities/pre-registrations"), "numeric"),
    "concept": EntityPathPolicy(Path("entities/concepts"), "slug"),
    "construct": EntityPathPolicy(Path("entities/constructs"), "slug"),
    "decision": EntityPathPolicy(Path("entities/decision"), "verbatim"),
    "paper": EntityPathPolicy(Path("entities/papers"), "citekey"),
    "book": EntityPathPolicy(Path("entities/books"), "citekey"),
    "talk": EntityPathPolicy(Path("entities/talks"), "citekey"),
    "outcome": EntityPathPolicy(Path("entities/outcomes"), "slug"),
    "research-question": EntityPathPolicy(Path("entities/research-question.md"), "singleton"),
    "claim-registry": EntityPathPolicy(Path("entities/claim-registry.yaml"), "singleton"),
}

FROZEN_DEFAULT_STATUS = {
    "evidence-line": "draft",
    "question": "active",
    "hypothesis": "proposed",
    "discussion": "active",
    "interpretation": "active",
    "theme": "active",
    "patch-definition": "active",
    "proposition": "draft",
    "finding": "active",
    "inquiry": "active",
    "topic": "active",
    "observation": "active",
    "mechanism": "active",
    "synthesis": "active",
    "report": "active",
    "plan": "active",
    "search": "active",
    "method": "active",
    "pre-registration": "active",
    "paper": "active",
    "book": "active",
    "talk": "active",
    "concept": "active",
    "construct": "active",
    "decision": "active",
    "outcome": "active",
}

FROZEN_STATUS_VALUES = {
    "evidence-line": frozenset({"draft", "active", "retired"}),
    "question": frozenset({"active", "partially-answered", "answered", "deferred", "retired"}),
    "hypothesis": frozenset(
        {"proposed", "under-investigation", "partially-supported", "supported", "weakened", "refuted"}
    ),
    "discussion": frozenset({"active", "complete", "superseded"}),
    "interpretation": frozenset({"active", "complete", "superseded"}),
    "theme": frozenset({"draft", "active", "superseded", "retired"}),
    "patch-definition": frozenset({"active", "retired"}),
    "proposition": frozenset({"draft", "active", "supported", "contested", "weakened", "retired", "superseded"}),
    "finding": frozenset({"active", "superseded", "retired"}),
    "inquiry": frozenset({"active", "complete", "superseded"}),
    "topic": frozenset({"active", "superseded", "retired"}),
    "observation": frozenset({"active", "superseded", "retired"}),
    "mechanism": frozenset({"active", "superseded", "retired"}),
    "synthesis": frozenset({"active", "superseded", "retired"}),
    "report": frozenset({"active", "superseded", "retired"}),
    "plan": frozenset({"active", "complete", "superseded", "retired"}),
    "search": frozenset({"active", "complete", "retired"}),
    "method": frozenset({"active", "superseded", "retired"}),
    "pre-registration": frozenset({"active", "amended", "superseded", "retired"}),
    "paper": frozenset({"active", "retired"}),
    "book": frozenset({"active", "retired"}),
    "talk": frozenset({"active", "retired"}),
    "concept": frozenset({"active", "deprecated"}),
    "construct": frozenset({"active", "retired"}),
    "decision": frozenset({"active", "superseded", "abandoned"}),
    "outcome": frozenset({"active", "retired"}),
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
