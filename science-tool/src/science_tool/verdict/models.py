"""Dataclass models for verdict frontmatter blocks and parse results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from science_tool.verdict.tokens import Token


@dataclass
class Context:
    """Per-context polarity + strength for a single claim (v1.1 `contexts` sub-block)."""

    context: str
    polarity: Token
    strength: str | None = None


@dataclass
class Claim:
    """A single atomic claim inside a verdict block.

    The `weight` field is only consulted when the parent rule is
    `weighted-majority`; for other rules it defaults to 1.0 and is
    ignored. `members` lists sub-claim IDs that this claim groups
    (v1.1 gap 4 addition).
    """

    id: str
    polarity: Token
    strength: str | None = None
    weight: float = 1.0
    evidence_summary: str = ""
    contexts: list[Context] = field(default_factory=list)
    members: list[str] = field(default_factory=list)


@dataclass
class VerdictBlock:
    """The `verdict:` frontmatter block, fully hydrated from YAML."""

    composite: Token
    rule: str
    claims: list[Claim] = field(default_factory=list)
    closure_terminal: str | None = None
    reframing_target: str | None = None
    reframing_reason: str | None = None


@dataclass
class ClaimRegistryEntry:
    """One canonical claim in the project-local registry."""

    id: str
    source: str
    definition: str
    predicted_direction: Token
    synonyms: list[str] = field(default_factory=list)
    members: list[str] = field(default_factory=list)
    cited_in: list[str] = field(default_factory=list)


@dataclass
class ClaimRegistry:
    """Project-local claim registry (`specs/claim-registry.yaml`)."""

    version: int
    project: str
    entries: list[ClaimRegistryEntry] = field(default_factory=list)
    conventions: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseResult:
    """Output of `parse_file(path)` - the spec's implementation contract for the parser.

    `closure_terminal`, `reframing_target`, `reframing_reason` are
    surfaced at the top level so `science-tool verdict parse` output
    includes them directly, per spec v1.1 acceptance criteria.
    """

    interpretation_id: str
    composite_token: Token
    composite_clause: str
    rule: str
    rule_derived_composite: Token
    rule_disagrees_with_body: bool
    closure_terminal: str | None = None
    reframing_target: str | None = None
    reframing_reason: str | None = None
    claims: list[Claim] = field(default_factory=list)
    unresolved_claim_ids: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
