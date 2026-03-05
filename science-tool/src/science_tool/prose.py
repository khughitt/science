from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict

import yaml

# Pattern: `term [`CURIE`]` — captures the preceding word(s) and the CURIE
_INLINE_CURIE_RE = re.compile(r"([\w][\w\s\-]*?)\s+\[`([A-Za-z][\w\-]*:[^\]`]+)`\]")


class InlineAnnotation(TypedDict):
    term: str
    curie: str
    line: int


class ProseFileResult(TypedDict):
    path: str
    frontmatter_terms: list[str]
    inline_annotations: list[InlineAnnotation]


def scan_prose(root: Path) -> list[ProseFileResult]:
    """Scan markdown files under *root* for ontology annotations.

    Returns a list of file records, each containing:
    - path: relative path from root
    - frontmatter_terms: list of CURIE strings from YAML frontmatter ``ontology_terms``
    - inline_annotations: list of {term, curie, line} dicts
    """
    results: list[ProseFileResult] = []

    for md_path in sorted(root.rglob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        frontmatter_terms = _extract_frontmatter_terms(text)
        inline_annotations = _extract_inline_annotations(text)

        if not frontmatter_terms and not inline_annotations:
            continue

        results.append(
            ProseFileResult(
                path=md_path.relative_to(root).as_posix(),
                frontmatter_terms=frontmatter_terms,
                inline_annotations=inline_annotations,
            )
        )

    return results


def _extract_frontmatter_terms(text: str) -> list[str]:
    """Extract ontology_terms from YAML frontmatter delimited by ``---``."""
    if not text.startswith("---"):
        return []

    end = text.find("---", 3)
    if end == -1:
        return []

    frontmatter_text = text[3:end]
    try:
        data = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError:
        return []

    if not isinstance(data, dict):
        return []

    terms = data.get("ontology_terms", [])
    if not isinstance(terms, list):
        return []

    return [str(t) for t in terms if t]


def _extract_inline_annotations(text: str) -> list[InlineAnnotation]:
    """Extract inline ``term [`CURIE`]`` annotations with line numbers."""
    annotations: list[InlineAnnotation] = []

    for line_num, line in enumerate(text.splitlines(), start=1):
        for match in _INLINE_CURIE_RE.finditer(line):
            term = match.group(1).strip()
            curie = match.group(2)
            annotations.append(InlineAnnotation(term=term, curie=curie, line=line_num))

    return annotations
