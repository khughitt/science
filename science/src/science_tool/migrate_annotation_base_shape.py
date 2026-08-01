"""Repair proposition / evidence-line records the durable base shape refuses.

Piece 3 of the schema-first closure program. Writer containment stopped the debt growing and
backfilled nothing; this is the backfill. Design:
`docs/plans/2026-08-01-annotation-base-shape-remediation-design.md`.

Two properties are load-bearing and easy to lose:

- **Preflight atomicity.** Every candidate is planned and every refusal collected BEFORE any
  file is written. A per-file loop that repairs as it goes satisfies the per-record guards and
  still leaves a half-migrated corpus on the first unsupported record.
- **`title == ""` exactly, not falsiness.** A missing key, an explicit null, or a non-string
  title are unsupported, not repairable. The parsed-value allowlist cannot enforce this -- all
  three would satisfy it -- so the condition lives here and is tested directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from science_model.entity_schema import EntityValidationError, EntityValidator
from science_model.frontmatter import atomic_write_text, render_frontmatter, split_frontmatter

from science_tool.dag.entity_frontmatter import (
    derive_evidence_line_title,
    derive_proposition_title,
)
from science_tool.entities import parse_markdown_entity_file_preserving_body

ANNOTATION_KIND_DIRS: tuple[str, ...] = ("propositions", "evidence-lines")

_DATE_KEYS: frozenset[str] = frozenset({"created", "updated"})


class BaseShapeMigrationRefused(Exception):
    """An in-scope record has no available repair, so the whole batch is refused."""


@dataclass(frozen=True)
class PlannedRepair:
    path: Path
    postimage: str
    title: str | None


@dataclass(frozen=True)
class Refusal:
    path: Path
    reason: str


@dataclass(frozen=True)
class RepairPlan:
    repairs: tuple[PlannedRepair, ...]
    refusals: tuple[Refusal, ...]
    skipped: int


def _normalized(mapping: dict[str, Any]) -> dict[str, Any]:
    """`created`/`updated` compare equal whether stored as a YAML date or an ISO string.

    Raw YAML changes those values' TYPE across the render -- `datetime.date` in, `str` out --
    so without this the date-only repairs would read as semantic changes and the guard would
    reject its own correct output.

    `datetime` is deliberately NOT normalized. The measured corpus defect is a bare
    `datetime.date`; a `datetime` carries a time component that the canonical renderer would
    discard, and normalizing it here would declare that discard semantics-free. Leaving it
    alone makes the guard REFUSE such a record instead, which is the correct outcome for a
    value this migration was never measured against.
    """
    out: dict[str, Any] = {}
    for key, value in mapping.items():
        if key in _DATE_KEYS and isinstance(value, date) and not isinstance(value, datetime):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def _derived_title(frontmatter: dict[str, Any], kind_dir: str) -> str:
    if kind_dir == "propositions":
        return derive_proposition_title(
            subject=frontmatter["subject"],
            predicate=frontmatter["predicate"],
            object=frontmatter["object"],
        )
    return derive_evidence_line_title(
        stance=frontmatter.get("stance"),
        target_id=frontmatter["target"],
        source=frontmatter.get("source"),
        evidence_type=frontmatter.get("evidence_type"),
    )


def _plan_one(path: Path, kind_dir: str, validator: EntityValidator) -> PlannedRepair | Refusal | None:
    """Plan one candidate. `None` means base-valid: skip it byte for byte."""
    frontmatter, body = parse_markdown_entity_file_preserving_body(path)
    try:
        validator.validate_persisted_base_shape(frontmatter)
    except EntityValidationError:
        pass
    else:
        return None

    planned = dict(frontmatter)
    title: str | None = None
    if "title" in planned and isinstance(planned["title"], str) and planned["title"] == "":
        try:
            title = _derived_title(planned, kind_dir)
        except (KeyError, ValueError) as exc:
            return Refusal(path, f"title cannot be derived: {exc}")
        planned["title"] = title

    postimage = render_frontmatter(planned, body)
    post_frontmatter, post_body = split_frontmatter(postimage)

    if set(post_frontmatter) != set(frontmatter):
        return Refusal(path, "render changed the frontmatter key set")
    if post_body != body:
        return Refusal(path, "render changed the body bytes")
    pre_values, post_values = _normalized(frontmatter), _normalized(post_frontmatter)
    changed = {k for k in pre_values if post_values[k] != pre_values[k]}
    if changed - {"title"}:
        return Refusal(path, f"render changed keys outside the allowlist: {sorted(changed)}")
    try:
        validator.validate_persisted_base_shape(post_frontmatter)
    except EntityValidationError as exc:
        return Refusal(path, f"still refused after repair: {exc}")

    return PlannedRepair(path, postimage, title)


def plan_repairs(project_root: Path) -> RepairPlan:
    """Plan every repair and collect every refusal. Writes nothing."""
    validator = EntityValidator()
    repairs: list[PlannedRepair] = []
    refusals: list[Refusal] = []
    skipped = 0
    for kind_dir in ANNOTATION_KIND_DIRS:
        directory = project_root / "entities" / kind_dir
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            outcome = _plan_one(path, kind_dir, validator)
            if outcome is None:
                skipped += 1
            elif isinstance(outcome, Refusal):
                refusals.append(outcome)
            else:
                repairs.append(outcome)
    return RepairPlan(tuple(repairs), tuple(refusals), skipped)


def _refusal_message(refusals: tuple[Refusal, ...]) -> str:
    listed = "\n".join(f"  {r.path}: {r.reason}" for r in refusals)
    return f"{len(refusals)} in-scope record(s) have no available repair; nothing was written:\n{listed}"


def apply_plan(plan: RepairPlan) -> int:
    """Write every planned post-image, or none of them."""
    if plan.refusals:
        raise BaseShapeMigrationRefused(_refusal_message(plan.refusals))
    for repair in plan.repairs:
        atomic_write_text(repair.path, repair.postimage)
    return len(plan.repairs)


def migrate(project_root: Path, *, apply: bool) -> dict[str, object]:
    """Plan, optionally apply, and report.

    Refusals raise whether or not `apply` was requested. A dry run exists to tell the caller
    what the apply WOULD do, and what it would do is refuse -- reporting "would repair N" while
    silently omitting the records that block the run is the opposite of report-first.
    """
    plan = plan_repairs(project_root)
    if plan.refusals:
        raise BaseShapeMigrationRefused(_refusal_message(plan.refusals))
    written = apply_plan(plan) if apply else 0
    # No `refusals` key: this line is unreachable unless the plan had none, so reporting an
    # always-empty list would imply the command can succeed while refusing something.
    return {
        "applied": apply,
        "repairs": [{"path": str(r.path.relative_to(project_root)), "title": r.title} for r in plan.repairs],
        "skipped": plan.skipped,
        "written": written,
    }
