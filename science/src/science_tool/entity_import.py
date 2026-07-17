# science/src/science_tool/entity_import.py
"""Import a loose markdown document as a canonical entity.

`create_entity` mints an entity from a title and a TEMPLATE; import takes a file
that already has content, proposes an id for it, gives it frontmatter, relocates
it, and repoints every reference in both directions.

Three properties the naive version does not have:

  * The preview is READ-ONLY. Id proposal goes through `propose_number`, not
    `reserve_entity` -- the latter commits the .md, so a dry run would leave an
    empty entity and the apply would mint a different number than the preview
    showed.
  * The preview VALIDATES. It renders the exact final text and runs it through
    `_validate_prospective_write`, the same boundary `create_entity` uses. A
    standalone `entities import --apply` must not depend on a later external
    validator to discover it wrote an invalid entity.
  * References move BOTH ways. Inbound refs are repointed at the new id/path, and
    the document's own relative links are rebased -- they resolve against its
    directory, which the move changes.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel

from science_tool.entities import (
    LOCAL_PART_WIDTH,
    _render_markdown,
    _validate_prospective_write,
    default_status,
    derive_slug,
    resolve_path_policy,
    valid_statuses,
    validate_slug,
)
from science_tool.entity_reservation import propose_number
from science_tool.reference_rewrite import RewriteReport, plan_reference_rewrite, rewrite_outbound_links
from science_model.frontmatter import split_frontmatter  # single-read frontmatter parse

_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


class EntityImportError(Exception):
    """A loose-file import could not be planned or applied."""


class ImportPlan(BaseModel):
    """What an import would do. Produced read-only; consumed by apply_import."""

    # The resolved project root the plan was DERIVED against. A plan is an
    # approval of edits to one specific corpus; two checkouts can hold identical
    # bytes, so nothing else in the plan would notice being replayed against the
    # wrong one -- drift detection compares the plan to the corpus, and both
    # corpora agree. Path identity is the right test: a moved or copied checkout
    # SHOULD force a fresh preview.
    project_root: str
    source_rel: str
    # sha256 of the source bytes the plan was rendered from. apply verifies the
    # source still hashes to this before it moves it: a plan carries a fixed
    # `rendered_text`, so an edit to the source made while the preview is reviewed
    # would otherwise be silently discarded -- apply would write the stale render
    # and unlink the newer source. Path-existence is not enough; content is.
    source_sha256: str
    entity_id: str
    kind: str  # claim_number_in_dir needs it to re-check the archive at apply time
    number: int
    dest_rel: str
    title: str
    status: str
    frontmatter: dict[str, Any]
    rendered_text: str
    ref_report: RewriteReport
    warnings: list[str] = []


def _derive_title(text: str, source: Path) -> str:
    match = _HEADING_RE.search(text)
    if match is not None:
        return match.group(1).strip()
    raise EntityImportError(f"{source} has no level-1 heading to derive a title from; pass --title explicitly")


def plan_import(
    project_root: Path,
    source: Path,
    *,
    kind: str,
    title: str | None = None,
    status: str | None = None,
    slug: str | None = None,
    today: date | None = None,
    exclude: frozenset[Path] = frozenset(),
) -> ImportPlan:
    """Plan the import of a loose markdown file. Touches nothing."""
    project_root = Path(project_root).resolve()
    source = Path(source).resolve()

    if not source.is_file():
        raise EntityImportError(f"source not found: {source}")

    # ONE read of the source. `_parse_markdown_file` re-opened the path, so a
    # source changing between the two reads produced a plan whose title/body and
    # whose hash described different bytes. split_frontmatter parses the text we
    # already hold, and that same text is what the hash below commits to.
    text = source.read_text(encoding="utf-8")
    source_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    frontmatter, body = split_frontmatter(text)
    if frontmatter:
        raise EntityImportError(
            f"{source} already has frontmatter; import is for loose documents. "
            "An entity that already carries an id needs a move, not an import."
        )

    resolved_title = title if title is not None else _derive_title(text, source)

    resolved_status = status if status is not None else default_status(kind, project_root=project_root)
    allowed = valid_statuses(kind, project_root=project_root)
    # None is an OPEN set (entities.py:1697), not an empty one -- do not refuse on it.
    if allowed is not None and resolved_status not in allowed:
        raise EntityImportError(f"status {resolved_status!r} is not in the {kind} vocabulary {sorted(allowed)}")

    number = propose_number(project_root, kind)
    slug_value = validate_slug(slug) if slug is not None else derive_slug(resolved_title)
    local_part = f"{number:0{LOCAL_PART_WIDTH}d}-{slug_value}"
    entity_id = f"{kind}:{local_part}"

    policy = resolve_path_policy(kind)
    dest = project_root / policy.root / f"{local_part}.md"
    source_rel = source.relative_to(project_root).as_posix()
    dest_rel = dest.relative_to(project_root).as_posix()

    body_rebased, _outbound_hits = rewrite_outbound_links(
        body, PurePosixPath(source_rel).parent, PurePosixPath(dest_rel).parent
    )

    stamp = (today or date.today()).isoformat()
    new_frontmatter: dict[str, Any] = {
        "kind": kind,
        "title": resolved_title,
        "status": resolved_status,
        "created": stamp,
        "updated": stamp,
        "id": entity_id,
    }
    rendered_text = _render_markdown(new_frontmatter, body_rebased)

    warnings, _sources = _validate_prospective_write(
        project_root=project_root,
        rel_path=Path(dest_rel),
        text=rendered_text,
        target_entity_id=entity_id,
    )

    # Exclude the moved source from the INBOUND scan. Its own links are rebased by
    # rewrite_outbound_links above; scanning it again as an inbound referrer would
    # turn a prose mention of its own path into a ManualHit that, come apply, has
    # vanished (apply unlinks the source before the fresh scan) -- so a
    # self-referential document would drift against its own plan every time.
    ref_report = plan_reference_rewrite(
        project_root,
        id_substitutions={source_rel: entity_id},
        path_substitutions={source_rel: dest_rel},
        exclude=exclude | frozenset({source}),
    )

    return ImportPlan(
        project_root=str(project_root),
        source_rel=source_rel,
        source_sha256=source_sha256,
        entity_id=entity_id,
        kind=kind,
        number=number,
        dest_rel=dest_rel,
        title=resolved_title,
        status=resolved_status,
        frontmatter=new_frontmatter,
        rendered_text=rendered_text,
        ref_report=ref_report,
        warnings=list(warnings),
    )
