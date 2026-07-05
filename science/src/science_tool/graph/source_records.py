"""Leaf source-record types emitted by storage adapters during load.

Lives below ``sources.py`` (which imports the adapter modules) so adapters can
return these types without an import cycle. Slice B's ``SourceSnapshot`` /
``SourceChange`` source-observation primitives also live here for the same reason.
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
