"""`science entity migrate-specs` (S3b) — canonicalize legacy/loose spec docs to numeric entities.

Ships the migration; does NOT flip `spec:` resolution (`_ANNOTATION_REF_PREFIXES` is untouched).
ONE planning authority (`_plan_all`) produces both the flip-readiness report AND the frozen
transaction, so a dry run exercises every refusal a `--apply` would. The design is
`docs/plans/2026-07-18-specs-plans-as-entities-s3b-design.md`.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

JOURNAL_PATH: Path = Path(".science/spec-migration.journal")

# The load-derived keys, enumerated EXACTLY. `canonical_id` OVERRIDES the id-derived value at load,
# so an authored one would disagree with the freshly minted numeric id.
RUNTIME_ONLY: frozenset[str] = frozenset(
    {"project", "file_path", "content", "content_preview", "canonical_id"}
)

LEGACY_ALIAS: frozenset[str] = frozenset({"type", "date", "related_questions", "related_specs"})

CANONICAL_SPEC_STATUS: frozenset[str] = frozenset(
    {"draft", "active", "complete", "superseded", "retired", "archived"}
)

# Unambiguous legacy -> canonical only. Anything else refuses (the operator pre-edits the status).
_STATUS_MAP: dict[str, str] = {
    "draft": "draft",
    "proposed": "draft",
    "design": "draft",
    "active": "active",
    "in-progress": "active",
    "current": "active",
    "complete": "complete",
    "completed": "complete",
    "implemented": "complete",
}


class SpecMigrationRefused(RuntimeError):
    """The migration will not proceed. NOTHING has been written."""


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _dedup(items: list[Any]) -> list[Any]:
    """Order-preserving dedup (first occurrence wins)."""
    seen: set[Any] = set()
    out: list[Any] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def project_legacy_frontmatter(frontmatter: Mapping[str, Any], *, source_rel: str) -> tuple[str, dict]:
    """Project ONE legacy spec doc's frontmatter to the canonical spec schema.

    Returns ``(old_id, projected_frontmatter)``; keeps ``id: <old_id>`` and ``kind: spec``. The old id
    is appended to ``aliases`` only by the coordinator's mint step. Refuses, naming the file, on any
    ambiguity — it never invents a value.
    """
    fm = dict(frontmatter)

    present_runtime = sorted(RUNTIME_ONLY & set(fm))
    if present_runtime:
        raise SpecMigrationRefused(
            f"{source_rel}: authors load-derived key(s) {present_runtime!r}, which are not "
            "authorable frontmatter (they are derived at load)."
        )

    declared_kind = fm.get("kind")
    declared_type = fm.get("type")
    if declared_kind is not None and declared_type is not None and declared_kind != declared_type:
        raise SpecMigrationRefused(f"{source_rel}: kind {declared_kind!r} and type {declared_type!r} disagree.")
    kind = declared_kind if declared_kind is not None else declared_type
    if kind != "spec":
        raise SpecMigrationRefused(f"{source_rel}: not a spec (kind/type {kind!r}).")
    fm["kind"] = "spec"
    fm.pop("type", None)

    old_id = fm.get("id")
    if not isinstance(old_id, str) or not old_id.startswith("spec:"):
        raise SpecMigrationRefused(
            f"{source_rel}: a spec doc without a declared `spec:` id; identity is authoritative "
            "and never guessed from a filename."
        )
    title = fm.get("title")
    if not isinstance(title, str) or not title.strip():
        raise SpecMigrationRefused(f"{source_rel}: missing `title:`.")

    date = fm.pop("date", None)
    for field in ("created", "updated"):
        if fm.get(field):
            continue
        if date:
            fm[field] = date
        else:
            raise SpecMigrationRefused(f"{source_rel}: `{field}` is absent and there is no `date:` to seed it.")

    status = fm.get("status")
    if status is not None:
        if status in CANONICAL_SPEC_STATUS:
            pass
        elif status in _STATUS_MAP:
            fm["status"] = _STATUS_MAP[status]
        else:
            raise SpecMigrationRefused(
                f"{source_rel}: status {status!r} maps to no canonical spec status. "
                "Pre-edit the doc's status; the migration will not guess."
            )

    related = _dedup(
        [
            *_as_list(fm.get("related")),
            *_as_list(fm.pop("related_questions", None)),
            *_as_list(fm.pop("related_specs", None)),
        ]
    )
    if related:
        fm["related"] = related

    return old_id, fm
