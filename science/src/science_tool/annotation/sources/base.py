# science/src/science_tool/annotation/sources/base.py
"""Source adapter protocol and shared dataclasses.

A SourceAdapter scans a single markdown file and returns an iterable
of PlannedAnnotation records. The audit orchestrator calls
adapters per file, then hands the planned rows to merge_planned for
idempotent persistence.

See docs/conventions/annotation-tokens.md for the marker-token
source behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Protocol

from science_tool.annotation.model import (
    Body,
    Motivation,
    SpecificResource,
)


class IdCollisionError(RuntimeError):
    """Raised when mint_id encounters an unrelated 4-tuple at a base ID.

    This is a structural problem (hash slice too short for the
    sidecar size); the operator should bump the slice length.
    Distinct from the same-finding-superseded-predecessor case,
    which mint_id resolves by appending `-N`.
    """


@dataclass(frozen=True)
class PlannedAnnotation:
    """A would-be annotation, before idempotence + ID minting.

    `match_text` is the per-finding identity token (the specific
    substring or token literal the source flagged). It distinguishes
    multiple findings within the same target sentence.

    `source_name` is the full source-version string (e.g.,
    "lint:bare-author-year-v2026-05-11"). All planned rows for a
    single merge_planned call MUST share this value.
    """

    target: SpecificResource
    annotation_type: str
    motivation: Motivation
    body: Body
    match_text: str
    source_name: str
    lifted_from: Optional[str] = None


class SourceAdapter(Protocol):
    """Protocol every annotation source implements.

    `name` is the full source-version string written into the
    `sci:source` field on persisted rows. `short_name` is the
    user-facing CLI value accepted by `--source`.
    """

    @property
    def name(self) -> str: ...

    @property
    def short_name(self) -> str: ...

    def scan(self, md_path: Path) -> Iterable[PlannedAnnotation]: ...
