"""Atomic reservation of question files under ``entities/questions/``.

Parallel subagents creating questions used to collide on numbers because
each read the directory listing before writing. Numbering and atomicity are
now delegated to :func:`science_tool.entity_reservation.reserve_entity`,
which locks on the NUMBER (via a per-number sentinel) rather than the
slugged filename — so concurrent reservers with different slugs can never
share a number. This module keeps the question-specific concerns: slug
normalization (kebab-case, length-capped) and the rich stub body.

Questions live at ``entities/questions/NNNN-slug.md`` (canonical width-4
numbering, no ``q`` prefix). The numbering policy is ``max-existing + 1``
(gap-tolerant): retired numbers stay retired so historical references
don't shift.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from science_tool.entities import LOCAL_PART_WIDTH, truncate_slug_on_word_boundary
from science_tool.entity_reservation import reserve_number_in_dir

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
    """Result of atomically reserving a question slot on disk.

    ``number``/``padded``/``slug``/``id`` are reconstructed from the local
    part assigned by :func:`reserve_entity` so existing callers (and the CLI
    ``--json`` contract) keep their fields.
    """

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
    return truncate_slug_on_word_boundary(cleaned, max_length)


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
    project_root: Path,
    slug: str,
    *,
    title: str | None = None,
    related: Iterable[str] = (),
    ontology_terms: Iterable[str] = (),
    source_refs: Iterable[str] = (),
    datasets: Iterable[str] = (),
    template_body: str | None = None,
    questions_dir: Path | None = None,
    max_attempts: int = 100,
) -> Reservation:
    """Atomically reserve the next question number under ``entities/questions/``.

    Numbering and the atomic number-claim are delegated to
    :func:`science_tool.entity_reservation.reserve_number_in_dir` (the
    NUMBER is the lock unit, so concurrent reservers with different slugs
    never share a number). Questions get a canonical ``NNNN-slug.md`` name
    (width 4, no ``q`` prefix).

    Slug normalization stays question-specific via :func:`slugify`
    (kebab-case, capped at ``_MAX_SLUG_LENGTH``). A stub with frontmatter
    and the standard section scaffold is written; the caller (typically a
    subagent) then fills the body.

    ``questions_dir`` is a deprecated override: when omitted the destination
    resolves to ``entities/questions/`` under ``project_root``. When given,
    it is used verbatim as the destination directory.
    """
    normalized_slug = slugify(slug)
    body_template = template_body if template_body is not None else _DEFAULT_TEMPLATE_BODY
    directory = questions_dir if questions_dir is not None else project_root / "entities" / "questions"

    # Claim the number+path atomically with an empty stub, then render the
    # full stub now that the assigned id is known and write it into the
    # already-committed (number-locked) file.
    number, local_part, path = reserve_number_in_dir(
        directory, normalized_slug, label="question", max_attempts=max_attempts
    )
    qid = f"question:{local_part}"
    padded = f"{number:0{LOCAL_PART_WIDTH}d}"
    content = _render_stub(
        qid=qid,
        title=title if title else _TITLE_PLACEHOLDER,
        related=related,
        ontology_terms=ontology_terms,
        source_refs=source_refs,
        datasets=datasets,
        template_body=body_template,
    )
    path.write_text(content, encoding="utf-8")
    return Reservation(number=number, padded=padded, slug=normalized_slug, id=qid, path=path)
