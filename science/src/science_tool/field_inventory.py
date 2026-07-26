"""Count AUTHORED frontmatter keys per kind, across a project.

This reads each file's own bytes via ``split_frontmatter`` — **not** the enriched ``raw`` dict
the graph loader builds. Two facts make that distinction load-bearing:

- ``_enrich_raw`` (``graph/sources.py:713``) injects ``kind``, ``type``, ``canonical_id``,
  ``profile``, ``aliases`` and ``content_preview`` *before* Pydantic ever sees a record.
  Inventorying that dict would declare six fields no author has ever written — and closing a
  schema around them would then reject every real file.
- ``Entity`` is ``extra="allow"`` (D3.3): every *undeclared* authored key survives
  ``model_validate`` as an untyped extra, so the parsed entity is not blind to it in the sense of
  losing the value. It is blind in the sense this instrument targets: an untyped extra has no
  declared field, no schema constraint, and no graph predicate, so ``entities_inventory`` and
  every other consumer downstream of ``load_project_sources`` still cannot tell a core field from
  a project extension from typo debt without exactly this inventory.

This is the P0 "declare or delete" instrument (design §8). Its output must be adjudicated —
core / project-extension / rename-migrate / derived-delete — **before** any schema is closed
with ``unevaluatedProperties: false``.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from science_model.frontmatter import split_frontmatter

from science_tool.entity_scan import iter_entity_markdown


def field_inventory(project_root: Path, kind: str) -> dict[str, int]:
    """Map each authored frontmatter key of ``kind`` to the number of files that carry it.

    Archived entities are excluded: their meaning is already frozen, so they must not widen
    the vocabulary the live schema is closed around.
    """
    counts: Counter[str] = Counter()
    for path in iter_entity_markdown(project_root / "entities"):
        frontmatter, _body = split_frontmatter(path.read_text(encoding="utf-8"))
        if frontmatter.get("kind") != kind:
            continue
        counts.update(frontmatter.keys())
    return dict(counts)
