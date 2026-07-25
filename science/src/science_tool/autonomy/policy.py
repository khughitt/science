"""Default-deny write policy for autonomous runs (design §4).

NOT project-overridable by construction: nothing in this module reads project
configuration, environment, or any file. A project needing a different autonomous
write surface is a design conversation, not a config key -- an override is a hole
that will be widened under pressure by the very agents it constrains.

Every entry below is covered by a Layer 3 perturbation case in
`tests/test_autonomy_perturbation_alarm.py`, which fails if an entry is added here
without one.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from science_model.frontmatter import PROJECT_CONFIG_FILENAME

#: Per-kind fields an autonomous run may write on a PRE-EXISTING entity. Every kind
#: absent from this mapping, and every field absent from a kind's entry, is DENIED
#: with no registration required.
#:
#: Neutrality arguments, in two tiers:
#:
#:   Tier A -- produces no graph triple at all, so it cannot reach any belief input:
#:     paper.venue, paper.pmid, book.publisher, book.isbn,
#:     talk.venue, talk.duration_minutes
#:
#:   Tier B -- materializes into graph/knowledge (`graph/materialize.py:700-710`) but
#:   emits no cito edge, no rdf:type, no evidence-line provenance metadata, and no
#:   target polarity, so neither the target closure nor any evidence unit reads it:
#:     paper.year, paper.url, book.year, book.url   (dcterms:date / dcat:downloadURL)
#:
#: DELIBERATELY ABSENT, with reasons:
#:   aliases  -- feeds reference resolution (`graph/sources.py:787-793`), so it can
#:               re-point a reference and move the target closure.
#:   doi      -- materializes to sci:doi and is identity-adjacent (xrefs, identity
#:               arbitration). Accepted overbreadth; promote only under design §5
#:               Layer 4 review.
#:   task.*   -- `task` has no markdown home (CORE_PROFILE: home=None), so no rule
#:               here could ever match it.
FIELD_ALLOWLIST: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "paper": frozenset({"venue", "pmid", "year", "url"}),
        "book": frozenset({"publisher", "isbn", "year", "url"}),
        "talk": frozenset({"venue", "duration_minutes"}),
    }
)

#: Kinds an autonomous run may CREATE, and the fields it may set at creation. EMPTY in
#: S1. Creation is not merely "editing a file with no before-value": a created entity
#: can change another entity's belief basis (design §4), and nothing in the envelope
#: needs creation yet. The table exists so Plan D has a place to argue for entries.
CREATION_ALLOWLIST: Mapping[str, frozenset[str]] = MappingProxyType({})

#: Named reasons for the notable denied paths of design §4. This table is
#: DOCUMENTATION, not the mechanism: the mechanism is that everything not explicitly
#: allowed is denied. Deleting a row here does not permit anything.
#:
#: Keys match a path exactly or as a leading directory segment.
DENIAL_REASONS: Mapping[str, str] = MappingProxyType(
    {
        "data": "payload boundary; autonomous runs never touch measurement payload",
        "knowledge/graph.trig": "source is its only durable writer (kernel closure)",
        PROJECT_CONFIG_FILENAME: "the schema-version pin is sole write authority",
        "core/decisions.md": "guard integrity -- belief machinery reads its flags",
        "runs": "supervisor-owned (design §0)",
        "pyproject.toml": "toolchain selection; high blast radius",
        "uv.lock": "toolchain selection; high blast radius",
    }
)

#: The reason every other path gets. Default-deny means this is the common case, not
#: the exception.
DEFAULT_DENY_REASON = "not on any allowlist (default-deny)"


def is_field_allowed(kind: str, field: str) -> bool:
    """True only when `kind` has an explicit entry that names `field`."""
    return field in FIELD_ALLOWLIST.get(kind, frozenset())


def is_creation_allowed(kind: str, field: str) -> bool:
    """True only when `kind` may be created and `field` set at creation."""
    return field in CREATION_ALLOWLIST.get(kind, frozenset())


def denial_reason(rel_path: str) -> str:
    """A named reason when the design gives one, else the default-deny reason."""
    for prefix, reason in DENIAL_REASONS.items():
        if rel_path == prefix or rel_path.startswith(f"{prefix}/"):
            return reason
    return DEFAULT_DENY_REASON
