"""Phase 3a: agent statement-extraction persistence.

Turn an LLM agent's candidate proposition/question/hypothesis spans into
oa:TextQuoteSelector annotations anchored in an existing `<citekey>.source.md`,
written to its `.source.anno.trig` sidecar via the existing annotation machinery.
The agent decides; this module owns anchoring, section derivation, grounding
verification, dedup, and document-level idempotency.

See docs/plans/2026-06-15-paper-annotate-phase3a-design.md.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from science_tool.annotation.audit import merge_planned
from science_tool.annotation.io import (
    atomic_write_text,
    read_sidecar,
    serialize_sidecar,
    sidecar_for_markdown,
)
from science_tool.annotation.ledger import (
    find_or_create_ledger,
    ledger_set_source_text_hash,
)
from science_tool.annotation.model import (
    IriBody,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.pubtator_seed import (
    PersistedPassage,
    load_persisted_passages,
    _CONTEXT,
)
from science_tool.annotation.source_text import SourceTextError
from science_tool.annotation.sources.base import PlannedAnnotation
from science_tool.commons.frontmatter import raw_frontmatter

# --- Section normalization ----------------------------------------------------

CANONICAL_SECTIONS: frozenset[str] = frozenset({
    "title", "abstract", "introduction", "methods", "results",
    "discussion", "conclusion", "figure", "table", "other",
})

# Raw BioC `infons.type` (lowercased) -> canonical section. Anything absent -> "other".
_SECTION_NORMALIZE: dict[str, str] = {
    "title": "title",
    "abstract": "abstract",
    "intro": "introduction",
    "introduction": "introduction",
    "methods": "methods",
    "method": "methods",
    "materials and methods": "methods",
    "results": "results",
    "result": "results",
    "discuss": "discussion",
    "discussion": "discussion",
    "concl": "conclusion",
    "conclusion": "conclusion",
    "conclusions": "conclusion",
    "fig": "figure",
    "figure": "figure",
    "table": "table",
}


def normalize_section(raw: str) -> str:
    """Map a raw `.source.md` passage section to the closed canonical vocabulary."""
    return _SECTION_NORMALIZE.get(raw.strip().lower(), "other")


def _containing_passage(
    persisted: list[PersistedPassage], file_idx: int, length: int
) -> PersistedPassage | None:
    """The persisted passage wholly containing [file_idx, file_idx+length), or None.

    None means the span anchored outside every passage body (e.g. a heading or
    frontmatter) or straddles a passage boundary — the caller skips it.
    """
    end = file_idx + length
    for pp in persisted:
        if pp.file_char_base <= file_idx and end <= pp.file_char_base + pp.length:
            return pp
    return None
