"""Which frontmatter keys the workbench owns, and how it renders them.

Shared by the two writers -- `workbench.compile_workbench` (create) and
`workbench_apply._entity_edit` (create + update). It lives in its own module because
`workbench_apply` imports `workbench`, so neither can host code the other needs.

The owned sets are POSITIVE allowlists. `render_entity_text` full-dumps the model
(`exclude_defaults=False`), which is what wrote `datapackage: ''` and `accessions: []` onto 391
evidence lines; rendering from an allowlist is what stops it.

`exclude_defaults=True` would NOT stop it. The skeleton fields are **required** on the model, not
defaulted -- a required field has no default to be excluded by -- so the flag emits them anyway.
No dump-mode flag can express "required for the model, not for the file"; only an allowlist can.
"""

from __future__ import annotations

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


def owned_keys(kind: str) -> frozenset[str]:
    if kind == "proposition":
        return PROPOSITION_OWNED_KEYS
    if kind == "evidence-line":
        return EVIDENCE_LINE_OWNED_KEYS
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


def certify_persisted(entity: WorkbenchEntity, text: str, *, path: Path | None = None) -> None:
    """Refuse to render or plan a write whose result would fail the durable base shape.

    On create this catches a writer regression; on update it catches a record that predates
    containment -- deliberately a REJECTION, not a backfill (design §5.4): a workbench update must
    not silently migrate a record the author did not ask to touch.
    """
    frontmatter = yaml.safe_load(text.split("---\n", 2)[1]) or {}
    try:
        EntityValidator().validate_persisted_base_shape(frontmatter)
    except EntityValidationError as exc:
        where = f"{path}: " if path is not None else ""
        raise PersistedShapeError(
            f"{where}{entity.id} would not satisfy the durable base shape and was NOT written\n"
            f"  {exc}\n"
            f"  If this record predates writer containment, repair it directly; the workbench "
            f"will not backfill it."
        ) from exc


def render_create(entity: WorkbenchEntity, *, body: str, created: str, updated: str) -> str:
    """Render a NEW entity file from the owned allowlist plus the create-only keys."""
    generated = generated_frontmatter(entity, created=created, updated=updated)
    allowed = owned_keys(entity.kind) | CREATE_ONLY_KEYS
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
    existing_frontmatter: dict[str, object],
    body: str,
    created: str,
    updated: str,
) -> str:
    """Render an EXISTING entity file: overwrite only owned keys, preserve everything else.

    `CREATE_ONLY_KEYS` is deliberately NOT applied here -- that is what makes `title` create-only
    and lets an author's replacement survive. Both writers use this, so the compile path and the
    apply path cannot diverge on what an update means.
    """
    final = {
        key: value
        for key, value in existing_frontmatter.items()
        if key not in RENDERER_DERIVED_KEYS
    }
    generated = generated_frontmatter(entity, created=created, updated=updated)
    for key in owned_keys(entity.kind):
        if key in generated:
            final[key] = generated[key]
    final["created"] = created
    final["updated"] = updated
    text = render_from_frontmatter(final, body)
    certify_persisted(entity, text)
    return text
