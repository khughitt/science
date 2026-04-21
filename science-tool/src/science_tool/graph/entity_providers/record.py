"""EntityRecord — normalized input shape for format-driven providers.

All three providers (MarkdownProvider, DatapackageDirectoryProvider, AggregateProvider)
extract raw records into this shape, then funnel them through `_normalize_record` to
produce SourceEntity. This keeps paper-ID canonicalization, alias derivation, profile
defaulting, and kind validation in ONE place rather than duplicated per provider.
"""

from __future__ import annotations

import re
import sys
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from science_model.reasoning import (
    ClaimLayer,
    EvidenceRole,
    IdentificationStrength,
    ProxyDirectness,
    SupportScope,
)

from science_tool.big_picture.literature_prefix import canonical_paper_id
from science_tool.graph.entity_providers.base import EntityDiscoveryContext
from science_tool.graph.source_types import SourceEntity

_ENUM_FIELDS: dict[str, type[StrEnum]] = {
    "claim_layer": ClaimLayer,
    "identification_strength": IdentificationStrength,
    "proxy_directness": ProxyDirectness,
    "supports_scope": SupportScope,
    "evidence_role": EvidenceRole,
}

_REASONING_FIELDS = (
    "claim_layer",
    "identification_strength",
    "proxy_directness",
    "supports_scope",
    "independence_group",
    "evidence_role",
    "measurement_model",
    "rival_model_packet",
)


def load_reasoning_metadata(
    raw: dict[str, object] | None,
    *,
    source_path: Path | None = None,
) -> dict[str, object]:
    """Extract and validate reasoning metadata fields from a raw frontmatter dict.

    Returns a dict of validated field→value pairs ready for use as **kwargs to
    SourceEntity. Unknown enum values are dropped with a stderr warning.
    """
    if not isinstance(raw, dict):
        return {}

    metadata: dict[str, object] = {}
    for field in _REASONING_FIELDS:
        value = raw.get(field)
        if value is None:
            continue
        enum_type = _ENUM_FIELDS.get(field)
        if enum_type is not None and isinstance(value, str):
            try:
                enum_type(value)
            except ValueError:
                allowed = ", ".join(member.value for member in enum_type)
                where = f" in {source_path}" if source_path is not None else ""
                print(
                    f"warning: unknown {field} value {value!r}{where}; dropping field. Allowed values: {allowed}",
                    file=sys.stderr,
                )
                continue
        metadata[field] = value
    return metadata


_SHORT_ID_RE = re.compile(r"^(?P<token>[a-z]\d+)(?:[-_].*)?$", re.IGNORECASE)


class EntityRecord(BaseModel):
    """Normalized input record produced by a provider's extraction step.

    Required: canonical_id, kind, title, source_path. Everything else optional.
    The `extra` field is a dict for provider-specific passthrough fields (reasoning
    metadata, dataset access blocks, etc.) that the normalizer can lift selectively.
    """

    canonical_id: str
    kind: str
    title: str
    source_path: str
    description: str = ""
    profile: str | None = None
    domain: str | None = None
    related: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    ontology_terms: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    same_as: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    status: str | None = None
    confidence: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


def _derive_aliases(canonical_id: str, kind: str, explicit_aliases: list[str]) -> list[str]:
    """Mirror the existing _derive_aliases logic from graph/sources.py.

    Only generates short-form token aliases for hypothesis/question/task kinds.
    Does NOT add canonical_id itself to the aliases list.
    """
    aliases: list[str] = []
    seen: set[str] = set()

    def add(alias: str) -> None:
        cleaned = alias.strip()
        if not cleaned or cleaned == canonical_id or cleaned in seen:
            return
        seen.add(cleaned)
        aliases.append(cleaned)

    for alias in explicit_aliases:
        add(alias)

    if kind not in {"hypothesis", "question", "task"}:
        return aliases

    slug = canonical_id.split(":", 1)[1] if ":" in canonical_id else canonical_id
    match = _SHORT_ID_RE.match(slug)
    if match is None:
        head = slug.split("-", 1)[0]
        match = _SHORT_ID_RE.match(head)
    if match is not None:
        token = match.group("token")
        add(f"{kind}:{token.lower()}")
        add(f"{kind}:{token.upper()}")
        add(token.lower())
        add(token.upper())

    return aliases


def _default_profile_for_kind(
    kind: str,
    *,
    local_profile: str,
    active_kinds: frozenset[str] | None,
    ontology_catalogs: list | None,
) -> str:
    """Default profile resolution: core kinds → 'core'; ontology kinds → catalog.ontology; else local."""
    from science_model.profiles import CORE_PROFILE

    core_kind_names = frozenset(k.name for k in CORE_PROFILE.entity_kinds)
    if kind in core_kind_names:
        return "core"
    for catalog in ontology_catalogs or []:
        if any(et.name == kind for et in catalog.entity_types):
            return catalog.ontology
    return local_profile


def _normalize_record(
    record: EntityRecord,
    ctx: EntityDiscoveryContext,
    *,
    provider_name: str,
) -> SourceEntity:
    """Apply shared normalization rules and produce a SourceEntity.

    Single source of truth for:
    - Paper-ID canonicalization (kind == "paper" → canonical_paper_id)
    - Profile defaulting (uses ctx.local_profile + ctx.active_kinds + ctx.ontology_catalogs)
    - Alias derivation
    - provider field set to provider_name
    """
    canonical_id = record.canonical_id
    if record.kind == "paper":
        canonical_id = canonical_paper_id(canonical_id)

    profile = record.profile or _default_profile_for_kind(
        record.kind,
        local_profile=ctx.local_profile,
        active_kinds=ctx.active_kinds,
        ontology_catalogs=ctx.ontology_catalogs,
    )

    # Lift reasoning metadata from extra (provider sets these via load_reasoning_metadata).
    reasoning_kwargs: dict[str, object] = {k: v for k, v in record.extra.items() if k in _REASONING_FIELDS}

    return SourceEntity(
        canonical_id=canonical_id,
        kind=record.kind,
        title=record.title,
        profile=profile,
        source_path=record.source_path,
        provider=provider_name,
        description=record.description,
        domain=record.domain,
        confidence=record.confidence,
        status=record.status,
        related=record.related,
        blocked_by=record.blocked_by,
        source_refs=record.source_refs,
        ontology_terms=record.ontology_terms,
        same_as=record.same_as,
        aliases=_derive_aliases(canonical_id, record.kind, record.aliases),
        **reasoning_kwargs,
    )
