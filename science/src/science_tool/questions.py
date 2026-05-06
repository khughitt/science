"""Atomic reservation of question file numbers under ``doc/questions/``.

Parallel subagents creating questions used to collide on q-numbers because
each read the directory listing before writing. This module makes the
destination file itself the lock: ``O_CREAT|O_EXCL`` guarantees only one
process succeeds at any given path, and a retry loop bumps the number on
collision until a free slot is found.

The numbering policy is ``max-existing + 1`` (gap-tolerant): retired
numbers stay retired so historical references don't shift. Padding width
is inferred from the widest existing file (default 2).
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

_QUESTION_FILE_RE = re.compile(r"^q(?P<num>\d+)-")
_DEFAULT_PADDING = 2
_MAX_SLUG_LENGTH = 50
_TITLE_PLACEHOLDER = "<Question>"

_DEFAULT_TEMPLATE_BODY = """\
# {title}

## Summary

<What is being asked and why it is important.>

## Why It Matters

- <decision this question affects>
- <risk if unanswered>

## Current Evidence

- <supporting evidence>
- <conflicting evidence>

## Thoughts

- <best current interpretation>
- <major uncertainty>

## Connections to Project

- Related hypotheses:
- Required data or analyses:
- Priority level:

## Related

- Topic notes:
- Article notes:
- Methods/Datasets:
"""


@dataclass(frozen=True)
class Reservation:
    """Result of atomically reserving a question slot on disk."""

    number: int
    padded: str
    slug: str
    id: str
    path: Path


def slugify(text: str, *, max_length: int = _MAX_SLUG_LENGTH) -> str:
    """Convert text to kebab-case, ASCII-safe, length-capped."""
    if not text:
        raise ValueError("slug cannot be empty")
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    if not cleaned:
        raise ValueError(f"slug {text!r} produced empty result after normalization")
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip("-")
    return cleaned


def _scan_existing(questions_dir: Path) -> tuple[int, int]:
    """Return ``(max_number, padding_width)`` for q-files in the directory."""
    max_n = 0
    width = _DEFAULT_PADDING
    if not questions_dir.is_dir():
        return max_n, width
    for entry in questions_dir.iterdir():
        m = _QUESTION_FILE_RE.match(entry.name)
        if not m:
            continue
        digits = m.group("num")
        n = int(digits)
        max_n = max(max_n, n)
        width = max(width, len(digits))
    return max_n, width


def _render_stub(
    *,
    qid: str,
    title: str,
    related: Iterable[str],
    ontology_terms: Iterable[str],
    source_refs: Iterable[str],
    datasets: Iterable[str],
    template_body: str,
) -> str:
    today = date.today().isoformat()
    frontmatter = {
        "id": qid,
        "type": "question",
        "title": title,
        "status": "active",
        "ontology_terms": list(ontology_terms),
        "datasets": list(datasets),
        "source_refs": list(source_refs),
        "related": list(related),
        "created": today,
        "updated": today,
    }
    fm_yaml = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).rstrip("\n")
    body = template_body.replace("{title}", title)
    return f"---\n{fm_yaml}\n---\n\n{body}"


def reserve_question(
    questions_dir: Path,
    slug: str,
    *,
    title: str | None = None,
    related: Iterable[str] = (),
    ontology_terms: Iterable[str] = (),
    source_refs: Iterable[str] = (),
    datasets: Iterable[str] = (),
    template_body: str | None = None,
    max_attempts: int = 100,
) -> Reservation:
    """Atomically claim the next q-number for a new question file.

    Writes a stub with frontmatter pre-filled and the standard section
    scaffold; the caller (typically a subagent) then fills the body.
    """
    normalized_slug = slugify(slug)
    body_template = template_body if template_body is not None else _DEFAULT_TEMPLATE_BODY
    questions_dir.mkdir(parents=True, exist_ok=True)

    for _ in range(max_attempts):
        max_n, width = _scan_existing(questions_dir)
        next_n = max_n + 1
        padded = f"{next_n:0{width}d}"
        path = questions_dir / f"q{padded}-{normalized_slug}.md"
        qid = f"question:{padded}-{normalized_slug}"
        rendered_title = title if title else _TITLE_PLACEHOLDER
        content = _render_stub(
            qid=qid,
            title=rendered_title,
            related=related,
            ontology_terms=ontology_terms,
            source_refs=source_refs,
            datasets=datasets,
            template_body=body_template,
        )
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            continue  # someone else took this slot; recompute max and retry
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        return Reservation(number=next_n, padded=padded, slug=normalized_slug, id=qid, path=path)

    raise RuntimeError(f"failed to reserve question slot in {questions_dir} after {max_attempts} attempts")
