"""Adaptive rotation: rank a project's reviewable corpus least-recently-reviewed
first and compute this sweep's adaptive budget. Stateless and read-only."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from science_model.identity import CurationScope

from science_tool.entities import CLOSED_LIFECYCLE_STATUSES, load_markdown_entities
from science_tool.graph.sources import registry_for_project

from rdflib import Dataset

from science_tool.entities import graph_is_stale
from science_tool.graph.store import (
    DEFAULT_GRAPH_PATH,
    PROJECT_NS,
    SCI_NS,
    canonical_id_from_entity_uri,
)

ROTATION_A = 12.57
ROTATION_B = 11.53
N_FULL = 25

DATE_MIN = date.min


class RotationError(Exception):
    """A rotation input could not be interpreted (e.g. a malformed date)."""


@dataclass(frozen=True)
class EligibleEntity:
    id: str
    kind: str
    scope: CurationScope
    last_reviewed: date | None
    created: date | None


def rotation_budget(pool_size: int) -> int:
    """Per-sweep budget n(N). Full-read up to N_FULL, then a sublinear taper,
    clamped to [1, pool_size]; 0 for an empty corpus."""
    if pool_size < 0:
        raise ValueError(f"pool_size must be non-negative, got {pool_size}")
    if pool_size <= N_FULL:
        return pool_size  # covers 0..N_FULL, so n(0)=0
    raw = math.ceil(ROTATION_B * math.log(pool_size) - ROTATION_A)
    return min(pool_size, max(1, raw))


def _coerce_date(value: object, *, entity_id: str, path: Path, field: str) -> date | None:
    """Accept only a YAML date object or a canonical YYYY-MM-DD string. A datetime,
    or a noncanonical string that date.fromisoformat happens to accept (basic
    "20260718", week "2026-W29-6"), fails early with entity/path/field context."""
    if value is None:
        return None
    if isinstance(value, date):
        # datetime is a subclass of date; reject it explicitly (fail early).
        if type(value) is not date:
            raise RotationError(
                f"{entity_id} ({path}): field {field!r} must be a date, not a datetime: {value!r}"
            )
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise RotationError(
                f"{entity_id} ({path}): field {field!r} is not a valid YYYY-MM-DD date: {value!r}"
            ) from exc
        if parsed.isoformat() != value:
            raise RotationError(
                f"{entity_id} ({path}): field {field!r} must be canonical YYYY-MM-DD, got {value!r}"
            )
        return parsed
    raise RotationError(
        f"{entity_id} ({path}): field {field!r} must be a date or YYYY-MM-DD string, got {type(value).__name__}"
    )


def eligible_corpus(project_root: Path) -> list[EligibleEntity]:
    """Every locally reviewable, source-authored entity: the load_markdown_entities
    domain, minus none-scoped kinds and terminal-lifecycle statuses."""
    registry = registry_for_project(project_root)
    corpus: list[EligibleEntity] = []
    for record in load_markdown_entities(project_root):
        kind = record["kind"]
        scope = registry.curation_scope_for_kind(kind)
        if scope is CurationScope.NONE:
            continue
        frontmatter = record["frontmatter"]
        status = frontmatter.get("status")
        if isinstance(status, str) and status in CLOSED_LIFECYCLE_STATUSES:
            continue
        entity_id = record["id"]
        path = record["path"]
        review_state = frontmatter.get("review_state")
        last_reviewed_raw = review_state.get("last_reviewed") if isinstance(review_state, dict) else None
        corpus.append(
            EligibleEntity(
                id=entity_id,
                kind=kind,
                scope=scope,
                last_reviewed=_coerce_date(
                    last_reviewed_raw, entity_id=entity_id, path=path, field="review_state.last_reviewed"
                ),
                created=_coerce_date(frontmatter.get("created"), entity_id=entity_id, path=path, field="created"),
            )
        )
    return corpus


def graph_freshness(project_root: Path) -> tuple[str, dict[str, str]]:
    """Best-effort read of freshness states from the materialized graph.

    Returns (graph_source, states). graph_source has first-match precedence
    absent -> invalid -> stale -> current. states maps canonical entity id to its
    freshnessState literal, and is non-empty only when graph_source == "current".

    Every step is best-effort: a successful `exists()` returning False yields
    "absent", but if ANY operation raises — including the existence probe itself,
    the parse, the staleness check, or triple extraction — the result degrades to
    ("invalid", {}) rather than blocking selection. A stale graph is a normal
    result, not a failure, so it returns before the extraction block.
    """
    graph_path = project_root / DEFAULT_GRAPH_PATH
    try:
        if not graph_path.exists():
            return "absent", {}
        dataset = Dataset()
        dataset.parse(graph_path, format="trig")
        if graph_is_stale(project_root, graph_path):
            return "stale", {}
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        states: dict[str, str] = {}
        for subject, _, obj in knowledge.triples((None, SCI_NS.freshnessState, None)):
            canonical_id = canonical_id_from_entity_uri(str(subject))
            if canonical_id is not None:
                states[canonical_id] = str(obj)
        return "current", states
    except Exception:
        return "invalid", {}
