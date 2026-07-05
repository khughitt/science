"""Validation check for entity origin references.

Each project entity may carry a list of ``origins`` (provenance-only originator
claims). Literature origins reference a bibliography key (``cite:<key>``) or a
paper entity (``paper:<slug>``); those references must resolve, just like
``related`` refs and ``[@cite]`` bibliography citations elsewhere. An origin
marked ``independent: true`` is only meaningful when the entity has 2+ origins
(independence is *relative to the other originators*), so a lone independent
origin is a likely authoring mistake.

Severities mirror the existing reference/bibliography checks: an unresolved
``cite:``/``paper:`` origin ref is a WARN (same as a broken ``related`` ref in
``cross_references`` and a broken bibliography ref in ``references``); a lone
``independent`` origin is a WARN.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from science_tool.entity_scan import iter_entity_markdown
from science_tool.validate._helpers import resolve_reference
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, message: str) -> Result:
    return Result(severity, None, None, message, "origins", None)


def _known_entity_ids(ctx: ValidateContext) -> set[str]:
    """Ids of every project entity plus archive-resolvable ids, for resolving
    ``paper:<slug>`` origin refs against the modern ``entities/`` layout."""
    ids: set[str] = set()
    entities_dir = ctx.project_root / "entities"
    for path in iter_entity_markdown(entities_dir):
        doc_id = ctx.frontmatter(path).get("id")
        if isinstance(doc_id, str) and doc_id:
            ids.add(doc_id)

    from science_tool.archive import load_archive_index

    ids.update(load_archive_index(ctx.project_root).resolvable_ids())
    return ids


def _cite_unresolved(ctx: ValidateContext, ref: str) -> bool:
    # `_resolve_bibliography_reference` (via resolve_reference) returns the
    # references.bib path when the key is present, else None.
    from science_tool.validate._helpers import _resolve_bibliography_reference

    return _resolve_bibliography_reference(ctx, ref) is None


def _paper_unresolved(ctx: ValidateContext, ref: str, known_ids: set[str]) -> bool:
    if ref in known_ids:
        return False
    # resolve_reference also covers bibliography-backed literature references.
    return resolve_reference(ctx, ref) is None


@Check(section="entity origin references...", order=22)
def check_origin_refs(ctx: ValidateContext) -> Iterator[Result]:
    entities_dir = ctx.project_root / "entities"
    if not entities_dir.is_dir():
        return

    known_ids = _known_entity_ids(ctx)

    for path in iter_entity_markdown(entities_dir):
        origins = ctx.frontmatter(path).get("origins")
        if not isinstance(origins, list) or not origins:
            continue

        records = [record for record in origins if isinstance(record, dict)]

        for record in records:
            if record.get("type") != "literature":
                continue
            ref = record.get("ref")
            if not isinstance(ref, str):
                continue
            if ref.startswith("cite:") and _cite_unresolved(ctx, ref):
                yield _result(
                    Severity.WARN,
                    f"Unresolved origin citation '{ref}' in {path.name}: "
                    "bibliography key not found in papers/references.bib",
                )
            elif ref.startswith("paper:") and _paper_unresolved(ctx, ref, known_ids):
                yield _result(
                    Severity.WARN,
                    f"Unresolved origin reference '{ref}' in {path.name}: no matching paper/entity",
                )

        if len(records) == 1 and _is_truthy(records[0].get("independent")):
            yield _result(
                Severity.WARN,
                f"Lone origin marked independent in {path.name}: "
                "'independent' is only meaningful with 2+ origins",
            )


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return False
