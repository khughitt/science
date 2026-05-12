# science/src/science_tool/annotation/sources/marker_token.py
"""Marker-token source adapter.

Lifts the four phase-2 inline tokens ([UNVERIFIED], [MISSING_CITATION],
[SPECULATION], [INACCESSIBLE]) into PlannedAnnotation rows.

See spec docs/plans/2026-05-11-annotation-system-p3.2-spec.md
§sources/marker_token.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from science_tool.annotation.model import (
    Motivation,
    SpecificResource,
    TextualBody,
)
from science_tool.annotation.sources.base import PlannedAnnotation
from science_tool.annotation.text_segmentation import (
    build_quote_selector,
    sentence_range_containing_literal,
)
from science_tool.markers import scan_text as _scan_markers_text

TOKEN_SCANNER_VERSION = "phase-2"
TOKEN_SOURCE_NAME = f"marker-scanner:{TOKEN_SCANNER_VERSION}"

# Canonical token → (annotation_type, body_message).
TOKEN_TYPE_MAP: dict[str, tuple[str, str]] = {
    "UNVERIFIED":       ("unverified", "verifiable claim, not yet checked"),
    "MISSING_CITATION": ("missing-citation", "claim needs source pointer"),
    "SPECULATION":      ("speculation", "author conjecture / brainstorming"),
    "INACCESSIBLE":     ("inaccessible", "paywalled / image-only / private source"),
}


class MarkerTokenSource:
    name: str = TOKEN_SOURCE_NAME
    short_name: str = "marker-token"

    def scan(self, md_path: Path) -> Iterable[PlannedAnnotation]:
        text = md_path.read_text(encoding="utf-8")
        return self.scan_text(md_path, text)

    def scan_text(
        self, md_path: Path, text: str,
    ) -> Iterable[PlannedAnnotation]:
        # strict=False: severity is informational here; we only care
        # about hit positions and tokens.
        hits = _scan_markers_text(md_path, text, strict=False)
        out: list[PlannedAnnotation] = []
        for hit in hits:
            if hit.in_documentation:
                continue
            atype, body_msg = TOKEN_TYPE_MAP[hit.token]
            literal = f"[{hit.token}]"
            rng = sentence_range_containing_literal(text, hit.line, literal)
            if rng is None:
                continue
            sent_start, sent_end = rng
            selector = build_quote_selector(text, sent_start, sent_end, context=60)
            target = SpecificResource(
                source=md_path.name,
                selector=selector,
            )
            body = TextualBody(value=f"{body_msg} (lifted from {literal})")
            out.append(
                PlannedAnnotation(
                    target=target,
                    annotation_type=atype,
                    motivation=Motivation.CLASSIFYING,
                    body=body,
                    match_text=literal,
                    source_name=TOKEN_SOURCE_NAME,
                    lifted_from=literal,
                )
            )
        return out


