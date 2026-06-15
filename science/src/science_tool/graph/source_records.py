"""Leaf source-record types emitted by storage adapters during load.

Lives below ``sources.py`` (which imports the adapter modules) so adapters can
return these types without an import cycle. Slice B's ``SourceRecord`` /
``SourceSnapshot`` will join this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class MarkdownSourceDocument(BaseModel):
    path: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    body: str = ""


@dataclass(frozen=True, slots=True)
class AggregateRowMeta:
    """Row-level triage metadata for one aggregate (`entities.yaml`) entry.

    Captured at load time — before non-strict dedup can drop a shadowed entry's
    Entity (sources.py emit point) — so the §B5 triage classifier can bucket every
    aggregate row. Joined to its IdentityDeclaration by (path, line), which
    AggregateAdapter always populates.
    """

    path: str
    line: int
    canonical_id: str
    kind: str
    source_path: str | None
    # 4c: the row's external authority identifier, captured from the VALIDATED
    # entity. `entity.primary_external_id` is a typed ExternalId (or None); a
    # malformed value never reaches capture (it fails ExternalId validation and the
    # row is skipped). So this is the full {source, id, curie, provenance} dump or
    # None — never a half-filled mapping that could masquerade as a backed ref.
    primary_external_id: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class SourceChange:
    """A freshness-origin event: a source's observed content identity changed.

    Emitted only when a current content hash differs from the persisted baseline
    (the first-ever observation establishes the baseline and is NOT a change).
    """

    sha256: str
    observed_on: date


class SourceSnapshot(BaseModel):
    """A pinned observation of a local source's content identity.

    Durable: carried forward verbatim across builds when the content is unchanged
    (`latest_change` and `observed_on` must not drift on an unchanged rebuild).
    `latest_change` stays None until a change is first observed against a baseline.
    """

    source_path: str  # relative, posix
    sha256: str  # sha256 of raw file bytes
    latest_change: SourceChange | None = None
