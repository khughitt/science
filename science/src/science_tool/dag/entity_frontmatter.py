"""Which frontmatter keys the workbench writers own, and how they render them.

Governs every writer of `proposition` / `evidence-line`: the workbench (create + update via
`workbench.compile_workbench` and `workbench_apply._entity_edit`) and the two annotation
writers (`annotation/promote.py` creates, `annotation/synthesize.py` updates). Each supplies
its own `Ownership`; there is no uncontained full-model dump left on these paths.

It lives in its own module because `workbench_apply` imports `workbench`, so neither can host
code the other needs.

The owned sets are POSITIVE allowlists. `render_entity_text` full-dumps the model
(`exclude_defaults=False`), which is what wrote `datapackage: ''` and `accessions: []` onto 391
evidence lines; rendering from an allowlist is what stops it.

`exclude_defaults=True` would NOT stop it. The skeleton fields are **required** on the model, not
defaulted -- a required field has no default to be excluded by -- so the flag emits them anyway.
No dump-mode flag can express "required for the model, not for the file"; only an allowlist can.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from science_model.entities import EvidenceLineEntity
from science_model.entity_schema import EntityValidationError, EntityValidator
from science_model.frontmatter import split_frontmatter
from science_model.propositions import PropositionEntity

from science_tool.entities import render_entity_text

WorkbenchEntity = PropositionEntity | EvidenceLineEntity


class FrontmatterRenderError(ValueError):
    """The entity's frontmatter could not be rendered."""


RENDERER_DERIVED_KEYS: frozenset[str] = frozenset(
    ("canonical_id", "content_preview", "content", "file_path", "type")
)

PROPOSITION_OWNED_KEYS: frozenset[str] = frozenset(
    (
        "id", "kind", "subject", "object", "predicate", "polarity",
        "legacy_relation_label", "legacy_patch", "legacy_edge_id", "discusses",
        "claim_layer", "identification_strength", "created", "updated",
    )
)

EVIDENCE_LINE_OWNED_KEYS: frozenset[str] = frozenset(
    (
        "id", "kind", "stance", "target", "source", "evidence_type",
        "quantitative_result", "belief_eligible", "created", "updated",
    )
)

# Keys the workbench owns ONLY when it creates a file. `title` is derived at lift and is a
# create-time default; on update the author's value wins, which is why it is absent from both
# per-kind sets above. `status` is likewise seeded once and then owned by the author.
CREATE_ONLY_KEYS: frozenset[str] = frozenset(("title", "status"))


@dataclass(frozen=True)
class Ownership:
    """Which frontmatter keys ONE writer owns.

    Per-writer, not per-kind: three writers mint propositions and each owns a different set.
    Widening a shared per-kind allowlist to their union would give the workbench ownership of
    `source_refs` -- so every `compile_workbench` recompile would overwrite an author's curated
    value on a path this design does not otherwise touch.

    `create_only` defaults to EMPTY, not to CREATE_ONLY_KEYS: an update-only writer creates
    nothing and must not claim `title`.
    """

    owned: frozenset[str]
    create_only: frozenset[str] = frozenset()


WORKBENCH_PROPOSITION = Ownership(PROPOSITION_OWNED_KEYS, CREATE_ONLY_KEYS)
WORKBENCH_EVIDENCE_LINE = Ownership(EVIDENCE_LINE_OWNED_KEYS, CREATE_ONLY_KEYS)


def workbench_ownership(kind: str) -> Ownership:
    """Workbench two-kind dispatch. Retains today's fail-early raise on an unsupported kind."""
    if kind == "proposition":
        return WORKBENCH_PROPOSITION
    if kind == "evidence-line":
        return WORKBENCH_EVIDENCE_LINE
    raise FrontmatterRenderError(f"unsupported workbench entity kind: {kind}")


def generated_frontmatter(entity: WorkbenchEntity, *, created: str, updated: str) -> dict[str, object]:
    generated_text = render_entity_text(entity, body="", created=created, updated=updated)
    try:
        _prefix, frontmatter_text, _body = generated_text.split("---\n", 2)
    except ValueError as exc:
        raise FrontmatterRenderError(f"could not render entity frontmatter for {entity.id}") from exc
    loaded = yaml.safe_load(frontmatter_text) or {}
    if not isinstance(loaded, dict):
        raise FrontmatterRenderError(f"could not render entity frontmatter for {entity.id}")
    return loaded


def render_from_frontmatter(frontmatter: dict[str, object], body: str) -> str:
    # allow_unicode + wide: this is a read-modify-write, so an escaping/folding dumper rewrites
    # authored fields the edit never touched. Same rule as `entities._dump_frontmatter`.
    dumped = yaml.safe_dump(
        frontmatter, sort_keys=False, allow_unicode=True, default_flow_style=False, width=10_000
    )
    return "---\n" + dumped + "---\n" + body


class PersistedShapeError(ValueError):
    """A write was refused because its result would not satisfy the durable base shape."""


def certify_persisted(entity: WorkbenchEntity, text: str) -> None:
    """Refuse to render or plan a write whose result would fail the durable base shape.

    On create this catches a writer regression; on update it catches a record that predates
    containment -- deliberately a REJECTION, not a backfill (design §5.4): a workbench update must
    not silently migrate a record the author did not ask to touch.

    Parses `text` with `split_frontmatter` -- the same parser `read_existing_target` uses for
    admission -- rather than a bare `split("---\\n", 2)`, so the two halves of "admit, then
    certify" agree on what frontmatter is. This still validates the ROUND-TRIPPED mapping (parsing
    the rendered text back), not the in-memory `dict` that was dumped: that is what catches an
    unquoted date the YAML dumper emitted as a bare scalar, which reloads as a `datetime.date`
    rather than the string the schema requires.
    """
    frontmatter, _body = split_frontmatter(text)
    try:
        EntityValidator().validate_persisted_base_shape(frontmatter)
    except EntityValidationError as exc:
        raise PersistedShapeError(
            f"{entity.id} would not satisfy the durable base shape and was NOT written\n"
            f"  {exc}\n"
            f"  If this record predates writer containment, repair it directly; the workbench "
            f"will not backfill it."
        ) from exc


def render_create(
    entity: WorkbenchEntity, *, ownership: Ownership, body: str, created: str, updated: str
) -> str:
    """Render a NEW entity file from the owned allowlist plus the writer's create-only keys."""
    generated = generated_frontmatter(entity, created=created, updated=updated)
    allowed = ownership.owned | ownership.create_only
    final = {key: value for key, value in generated.items() if key in allowed}
    final["created"] = created
    final["updated"] = updated
    text = render_from_frontmatter(final, body)
    certify_persisted(entity, text)
    return text


class MalformedTargetError(ValueError):
    """An existing destination cannot be updated: wrong identity, unparseable, or undated."""


def read_existing_target(path: Path, entity: WorkbenchEntity) -> tuple[dict[str, object], str, str]:
    """Admit an existing destination for update, or refuse it.

    MOVED from `workbench_apply._read_existing_target` so BOTH writers share it. It must run
    BEFORE `render_update`, because `render_update` overwrites `id`, `kind`, `created` and
    `updated` -- so a destination with the wrong identity or no dates would be REPAIRED into
    validity before `certify_persisted` ever saw it, and the certification would pass on a file
    that was never admissible. Validating after a repair is not validating.
    """
    expected_id, expected_kind = entity.id, entity.kind
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            current_text = handle.read()
        frontmatter, body = split_frontmatter(current_text)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise MalformedTargetError(f"malformed existing entity target {path}: {exc}") from exc
    if frontmatter.get("id") != expected_id or frontmatter.get("kind") != expected_kind:
        raise MalformedTargetError(
            f"malformed existing entity target {path}: expected {expected_kind} {expected_id}"
        )
    if frontmatter.get("created") is None or frontmatter.get("updated") is None:
        raise MalformedTargetError(f"malformed existing entity target {path}: missing created/updated")
    return frontmatter, body, current_text


def render_update(
    entity: WorkbenchEntity,
    *,
    ownership: Ownership,
    existing_frontmatter: dict[str, object],
    body: str,
    created: str,
    updated: str,
) -> str:
    """Render an EXISTING entity file: overwrite only owned keys, preserve everything else.

    `ownership.create_only` is deliberately NOT applied here -- that is what makes `title`
    create-only and lets an author's replacement survive.
    """
    final = {
        key: value
        for key, value in existing_frontmatter.items()
        if key not in RENDERER_DERIVED_KEYS
    }
    generated = generated_frontmatter(entity, created=created, updated=updated)
    for key in ownership.owned:
        if key in generated:
            final[key] = generated[key]
    final["created"] = created
    final["updated"] = updated
    text = render_from_frontmatter(final, body)
    certify_persisted(entity, text)
    return text


class EntityWriteError(ValueError):
    """A write was refused because the destination's existence contradicts the operation."""


def _entity_dest(entity: WorkbenchEntity, project_root: Path) -> Path:
    from science_tool.entities import resolve_path_policy

    assert entity.id is not None
    local_part = entity.id.split(":", 1)[1]
    root = resolve_path_policy(entity.kind, project_root=project_root).root
    return project_root / root / f"{local_part}.md"


def _write(dest: Path, text: str) -> Path:
    from science_tool.entities import _atomic_replace_text

    dest.parent.mkdir(parents=True, exist_ok=True)
    _atomic_replace_text(dest, text)
    return dest


def _render_update_for(
    entity: WorkbenchEntity, dest: Path, *, ownership: Ownership, updated: str
) -> str:
    # ADMIT FIRST. `read_existing_target` refuses a wrong-identity, undated or unparseable
    # destination. Reading the file directly and defaulting `created` lets `render_update`
    # repair a record into validity before `certify_persisted` ever sees it.
    frontmatter, body, _current = read_existing_target(dest, entity)
    return render_update(
        entity,
        ownership=ownership,
        existing_frontmatter=frontmatter,
        body=body,
        created=str(frontmatter["created"]),
        updated=updated,
    )


def create_entity_file(
    entity: WorkbenchEntity,
    *,
    project_root: Path,
    ownership: Ownership,
    create_body: str,
    as_of: date | None = None,
) -> Path:
    """Write a NEW entity file. Refuses an existing destination."""
    dest = _entity_dest(entity, project_root)
    if dest.exists():
        raise EntityWriteError(f"refusing to create {dest}: it already exists")
    today = (as_of or date.today()).isoformat()
    return _write(dest, render_create(
        entity, ownership=ownership, body=create_body, created=today, updated=today
    ))


def update_entity_file(
    entity: WorkbenchEntity,
    *,
    project_root: Path,
    ownership: Ownership,
    as_of: date | None = None,
) -> Path:
    """Update an EXISTING entity file. Refuses a missing destination.

    Takes no `create_body`: an update-only writer has none to supply, and inventing one to
    satisfy a signature is how a stub body eventually reaches a real record.
    """
    dest = _entity_dest(entity, project_root)
    if not dest.exists():
        raise EntityWriteError(f"refusing to update {dest}: it does not exist")
    today = (as_of or date.today()).isoformat()
    return _write(dest, _render_update_for(entity, dest, ownership=ownership, updated=today))


def upsert_entity_file(
    entity: WorkbenchEntity,
    *,
    project_root: Path,
    ownership: Ownership,
    create_body: str,
    as_of: date | None = None,
) -> Path:
    """Create or update. Used ONLY by the workbench, which legitimately recompiles over rows."""
    dest = _entity_dest(entity, project_root)
    today = (as_of or date.today()).isoformat()
    if dest.exists():
        text = _render_update_for(entity, dest, ownership=ownership, updated=today)
    else:
        text = render_create(
            entity, ownership=ownership, body=create_body, created=today, updated=today
        )
    return _write(dest, text)
