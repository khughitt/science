"""Implementation of `entity review` and `entity needs-review` commands.

`entity review <id>` updates the review_state.last_reviewed (and optional
last_review_note) frontmatter on the named entity. It is the only command
in Phase 1 that mutates entity frontmatter from the freshness pipeline.

Reuses `science_tool.entities` for frontmatter parsing, rendering, and
atomic writes — those are the canonical helpers used by `edit_entity` and
`append_entity_note`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from rdflib import Dataset
from science_model.entities import EntityClass

from science_tool.entities import (
    EntityCommandError,
    _atomic_replace_text,
    _render_markdown,
    find_entity,
)
from science_tool.graph.entity_registry import EntityKindNotRegisteredError, EntityRegistry
from science_tool.graph.store import (
    DEFAULT_GRAPH_PATH,
    PROJECT_NS,
    SCI_NS,
    canonical_id_from_entity_uri,
)


class ReviewError(Exception):
    pass


def review_entity(
    project_root: Path,
    entity_ref: str,
    *,
    note: str | None = None,
    today: date | None = None,
    require_artifact: bool = False,
) -> tuple[Path, bool]:
    """Set review_state.last_reviewed = today on the entity's frontmatter.

    Preserves any existing review_state fields. Note semantics: `note=None`
    keeps any existing `last_review_note`; `note=""` clears it; a non-empty
    string replaces it.

    When `require_artifact` is True, a missing/blank `note` is rejected (the
    review-theater guard): the review must record a concrete artifact. The check
    runs only after the entity resolves and passes the epistemic-kind gate, so
    lookup and kind errors still take precedence.

    Returns (path, changed) — `changed` is True iff the file was rewritten.
    Raises ReviewError on lookup failure, non-epistemic target, or (when
    require_artifact) a missing artifact.
    """
    today = today or date.today()
    try:
        location = find_entity(project_root, entity_ref)
    except EntityCommandError as exc:
        raise ReviewError(str(exc)) from exc

    registry = EntityRegistry.with_core_types()
    try:
        kind_class = registry.kind_class(location.kind)
    except EntityKindNotRegisteredError:
        kind_class = None  # extension kinds default to allowed
    if kind_class is not None and kind_class != EntityClass.EPISTEMIC:
        raise ReviewError(
            f"entity {entity_ref!r} has kind {location.kind!r} "
            f"({kind_class.value}); review_state is only meaningful on epistemic entities"
        )

    if require_artifact and (note is None or not note.strip()):
        raise ReviewError(
            "review requires a recorded artifact: pass a note with the finding, "
            "prose diff, created task, or a reasoned 'no change'. "
            "A bare timestamp bump is not a review."
        )

    path = project_root / location.rel_path
    frontmatter = dict(location.frontmatter)

    rs_raw = frontmatter.get("review_state")
    rs: dict = dict(rs_raw) if isinstance(rs_raw, dict) else {}
    rs["last_reviewed"] = today.isoformat()
    if note is not None:
        if note == "":
            rs.pop("last_review_note", None)
        else:
            rs["last_review_note"] = note
    frontmatter["review_state"] = rs

    new_text = _render_markdown(frontmatter, location.body)
    old_text = path.read_text()
    if new_text == old_text:
        return path, False
    _atomic_replace_text(path, new_text)
    return path, True


def list_needs_review(project_root: Path) -> list[dict[str, str]]:
    """Read the materialized graph and return rows for needs-review/stale entities.

    Each row: {"id": "<entity-id>", "kind": "<kind>", "state": "<state>"}.
    Returns an empty list if the graph file doesn't exist yet.
    """
    trig = project_root / DEFAULT_GRAPH_PATH
    if not trig.exists():
        return []
    ds = Dataset()
    ds.parse(trig, format="trig")
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])

    rows: list[dict[str, str]] = []
    for s, _, o in knowledge.triples((None, SCI_NS.freshnessState, None)):
        state = str(o)
        if state not in {"needs-review", "stale"}:
            continue
        canonical_id = canonical_id_from_entity_uri(str(s))
        if canonical_id is None:
            continue
        kind, _, _ = canonical_id.partition(":")
        rows.append({"id": canonical_id, "kind": kind, "state": state})
    rows.sort(key=lambda r: (r["state"], r["kind"], r["id"]))
    return rows
