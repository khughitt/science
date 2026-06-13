"""Pydantic v2 schema for ``<patch>.workbench.yaml`` files (Task 5a).

A workbench file is the editable normalized projection an author edits.
``compile`` (Task 5b) turns rows into PropositionEntity + EvidenceLineEntity
records in the knowledge graph.

Structural contract
-------------------
- ``WorkbenchRow`` is an *input-only* projection — it carries only authored
  fields.  Post-compile derived/aggregated fields (``edge_status``, ``belief``,
  ``posterior``, ``support``/``dispute`` arrays, ``massed_support``) are
  **not** allowed here.  ``model_config = ConfigDict(extra="forbid")`` enforces
  the allowlist: any unlisted key (including every forbidden key) raises
  ``ValidationError``.
- ``EvidenceStub`` allows an optional ``quantitative_result`` *inside* the
  stub.  Placing ``quantitative_result`` at row level is forbidden by the same
  extra="forbid" rule.
- ``WorkbenchFile`` wraps ``rows: list[WorkbenchRow]`` with a minimal header.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from science_model.entities import EntityType, EvidenceLineEntity, QuantitativeResult
from science_model.propositions import PropositionEntity


# ---------------------------------------------------------------------------
# Layout models (Task 5e) — cosmetic / non-epistemic state
# ---------------------------------------------------------------------------


class NodeLayout(BaseModel):
    """Cosmetic position for a single proposition node in a DAG view.

    Carries only cosmetic coordinates.  ``extra="forbid"`` prevents unknown
    keys (e.g. color, label) from silently passing through.
    """

    model_config = ConfigDict(extra="forbid")

    x: float = 0.0
    y: float = 0.0
    pinned: bool = False


class LayoutFile(BaseModel):
    """Top-level structure of a ``<patch>.layout.yaml`` sibling file.

    Keyed by proposition id; values are node cosmetic positions.
    This model is entirely separate from the workbench epistemic content:
    ``compile_workbench`` and ``serialize_canonical`` do NOT read it.
    ``extra="forbid"`` keeps the file model strict.
    """

    model_config = ConfigDict(extra="forbid")

    nodes: dict[str, NodeLayout] = Field(default_factory=dict)


def load_layout(path: Path | str) -> LayoutFile:
    """Parse a ``<patch>.layout.yaml`` sibling file into a ``LayoutFile``.

    Tolerates a missing file — returns an empty ``LayoutFile()`` so callers
    need not guard for existence.  Uses the same ``yaml.safe_load`` +
    ``model_validate`` idiom as the path-load branch of ``compile_workbench``.
    """
    p = Path(path)
    if not p.exists():
        return LayoutFile()
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return LayoutFile.model_validate(raw)


class EvidenceStub(BaseModel):
    """Input-only evidence shape authored inside a WorkbenchRow.

    ``quantitative_result`` lifts to the EvidenceLineEntity at compile time.
    All other fields are optional qualifiers on the stub.

    ``extra="forbid"`` prevents undeclared keys from silently passing through.
    """

    model_config = ConfigDict(extra="forbid")

    stance: str | None = None
    source: str | None = None
    evidence_type: str | None = None
    dataset_usage: str | None = None
    quantitative_result: QuantitativeResult | None = None


class WorkbenchRow(BaseModel):
    """One relational proposition the author is editing in a workbench file.

    Allowed fields are the authored inputs only.  All post-compile derived
    fields are structurally forbidden via ``extra="forbid"``, meaning any key
    not listed here raises ``ValidationError`` at parse time.  This includes:

    - ``edge_status`` — derived projection of belief state
    - ``belief`` — computed aggregate
    - ``posterior`` — fitted-model block on a rendered edge
    - ``support`` / ``dispute`` / ``massed_support`` — computed evidence arrays

    ``quantitative_result`` is forbidden at row level; it belongs inside an
    ``EvidenceStub`` in the ``evidence`` list.
    """

    model_config = ConfigDict(extra="forbid")

    # Identity — optional; id-less rows get minted at compile (Task 5b).
    id: str | None = None

    # Core triple.
    subject: str
    predicate: str
    object: str

    # Patch membership.
    patch: str

    # Authored epistemic metadata (all optional).
    claim_layer: str | None = None
    identification_strength: str | None = None
    epistemic_role: str | None = None  # t034 verbatim taxonomy (D-005)
    polarity: str | None = None  # sole sign carrier; authored axis
    legacy_relation_label: str | None = None
    legacy_patch: str | None = None
    legacy_edge_id: int | None = None

    # Evidence: authored inline as ``EvidenceStub``; after ``compile`` the
    # normalized row holds evidence-line *references* (ids) instead of inline
    # substance. The union keeps both shapes parseable — a bare string is an
    # ``evidence-line:<id>`` reference; a mapping is an authored stub.
    evidence: list[EvidenceStub | str] = Field(default_factory=list)


class WorkbenchFile(BaseModel):
    """Top-level structure of a ``<patch>.workbench.yaml`` file.

    ``patch`` is an optional file-level header (rows carry their own ``patch``
    field; the header is a convenience for single-patch files).
    ``extra="forbid"`` keeps the file model strict too.
    """

    model_config = ConfigDict(extra="forbid")

    patch: str | None = None
    rows: list[WorkbenchRow] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# compile (Task 5b)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompileResult:
    """Result of compiling a workbench into graph entities.

    - ``propositions`` / ``evidence_lines`` are the upserted typed entities.
    - ``workbench`` is the NORMALIZED workbench: every row carries its (minted
      or authored) id, and each inline evidence stub has been replaced by an
      evidence-line *reference* (its id). Task 5c (`serialize_canonical`) and
      Task 5d (the CI fixpoint gate) consume this normalized form.
    """

    propositions: list[PropositionEntity]
    evidence_lines: list[EvidenceLineEntity]
    workbench: WorkbenchFile


def _slug_for_triple(subject: str | None, predicate: str | None, obj: str | None) -> str:
    """Deterministic slug from a row's triple (`<subject>-<predicate>-<object>`).

    Reuses the entity-layer slug helpers so a workbench-minted id is shaped
    exactly like any other slug-strategy entity id.
    """
    from science_tool.entities import (
        DERIVED_SLUG_MAX_LENGTH,
        EntityCommandError,
        normalize_to_slug,
        truncate_slug_on_word_boundary,
    )

    raw = "-".join(part for part in (subject, predicate, obj) if part)
    slug = truncate_slug_on_word_boundary(normalize_to_slug(raw), DERIVED_SLUG_MAX_LENGTH)
    if len(slug) < 2:
        raise EntityCommandError(
            "row triple cannot derive a stable proposition slug; set an explicit id"
        )
    return slug


def _proposition_for_row(row: WorkbenchRow) -> PropositionEntity:
    """Build a ``PropositionEntity`` from a row, minting a deterministic id if id-less.

    The proposition's canonical IRI (`proposition:<slug>`) is its edge-node /
    belief-target IRI directly (Task 0, no shim).
    """
    entity_id = row.id or f"proposition:{_slug_for_triple(row.subject, row.predicate, row.object)}"
    return PropositionEntity(
        id=entity_id,
        subject=row.subject,
        object=row.object,
        predicate=row.predicate,
        polarity=row.polarity,
        legacy_relation_label=row.legacy_relation_label,
        legacy_patch=row.legacy_patch,
        legacy_edge_id=row.legacy_edge_id,
        claim_layer=row.claim_layer,
        identification_strength=row.identification_strength,
    )


def _evidence_line_for_stub(
    stub: EvidenceStub, *, target_id: str, index: int
) -> EvidenceLineEntity:
    """Lift an inline ``EvidenceStub`` to a typed ``EvidenceLineEntity``.

    ``target`` is the proposition id (edge-node IRI). Empirical evidence with no
    ``dataset_usage`` is staged ``belief_eligible=False`` (design §8.6); a
    literature stub, or an empirical stub WITH ``dataset_usage``, stays eligible.
    """
    target_slug = target_id.split(":", 1)[1]
    line_id = f"evidence-line:{target_slug}-ev{index}"
    is_staged_empirical = (
        stub.evidence_type == "empirical_data_evidence" and not stub.dataset_usage
    )
    return EvidenceLineEntity(
        id=line_id,
        kind="evidence-line",
        type=EntityType.EVIDENCE_LINE,
        # Base-required fields that have no value at lift time — safe empties
        # (mirrors the minimal-construction pattern in the entity model tests).
        title="",
        project="",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="",
        stance=stub.stance,
        target=target_id,
        source=stub.source,
        evidence_type=stub.evidence_type,
        quantitative_result=stub.quantitative_result,
        belief_eligible=not is_staged_empirical,
    )


def _write_entity_file(entity: PropositionEntity | EvidenceLineEntity, *, project_root: Path) -> None:
    """Write a typed entity to its canonical ``entities/<kind>/<slug>.md`` file.

    Reuses the entity-layer path policy and markdown writer primitives so this
    is not a parallel writer: the path comes from ``resolve_path_policy`` and the
    bytes from the same frontmatter dump + atomic replace used by ``create_entity``.
    Frontmatter is the typed model's ``model_dump`` (the flat key/value shape the
    validate checks and ``parse_entity_file`` consume).
    """
    from science_tool.entities import (
        _atomic_replace_text,
        _render_markdown,
        default_status,
        resolve_path_policy,
    )

    kind = entity.kind
    assert entity.id is not None
    local_part = entity.id.split(":", 1)[1]
    policy = resolve_path_policy(kind, project_root=project_root)
    dest = project_root / policy.root / f"{local_part}.md"

    frontmatter = entity.model_dump(mode="json", exclude_none=True, exclude_defaults=False)
    # Identity/typing the loaders key on; status from the per-kind default.
    frontmatter["id"] = entity.id
    frontmatter["kind"] = kind
    frontmatter.setdefault("status", default_status(kind))
    # Drop fields that are not authored frontmatter (defaults that re-derive on load).
    for derived in ("canonical_id", "type", "content_preview", "content", "file_path"):
        frontmatter.pop(derived, None)

    body = f"# {entity.title or local_part}\n\n## Summary\n\n\n## Notes\n"
    text = _render_markdown(frontmatter, body)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _atomic_replace_text(dest, text)


def compile_workbench(
    workbench: WorkbenchFile | str | Path, *, project_root: Path
) -> CompileResult:
    """Upsert proposition/evidence-line entities from a workbench; return the result.

    For each row: upsert a ``PropositionEntity`` (minting a deterministic id for
    id-less rows and writing it back into the normalized row), then lift each
    inline evidence stub to an ``EvidenceLineEntity`` (target = proposition id).
    The normalized workbench replaces inline stubs with evidence-line references.

    ``compile`` is the only writer of these entities from the workbench, so all
    entity files are (re)written via the canonical entity-layer writer.
    """
    if isinstance(workbench, (str, Path)):
        import yaml

        wb = WorkbenchFile.model_validate(
            yaml.safe_load(Path(workbench).read_text(encoding="utf-8")) or {}
        )
    else:
        wb = workbench

    propositions: list[PropositionEntity] = []
    evidence_lines: list[EvidenceLineEntity] = []
    normalized_rows: list[WorkbenchRow] = []

    for row in wb.rows:
        prop = _proposition_for_row(row)
        _write_entity_file(prop, project_root=project_root)
        propositions.append(prop)

        evidence_refs: list[EvidenceStub | str] = []
        ev_index = 0
        for item in row.evidence:
            if isinstance(item, str):
                # Already-normalized reference: carry it through unchanged.
                evidence_refs.append(item)
                continue
            line = _evidence_line_for_stub(item, target_id=prop.id, index=ev_index)
            _write_entity_file(line, project_root=project_root)
            evidence_lines.append(line)
            evidence_refs.append(line.id)
            ev_index += 1

        normalized_rows.append(row.model_copy(update={"id": prop.id, "evidence": evidence_refs}))

    return CompileResult(
        propositions=propositions,
        evidence_lines=evidence_lines,
        workbench=wb.model_copy(update={"rows": normalized_rows}),
    )


# ---------------------------------------------------------------------------
# serialize_canonical (Task 5c)
# ---------------------------------------------------------------------------

# Canonical key order for a serialized WorkbenchRow.  Fields that are None or
# empty-list are omitted entirely (lean output rule).  This fixed ordering
# guarantees that two logically identical rows produce bit-identical YAML.
_ROW_KEY_ORDER: tuple[str, ...] = (
    "id",
    "subject",
    "predicate",
    "object",
    "patch",
    "polarity",
    "claim_layer",
    "identification_strength",
    "epistemic_role",
    "legacy_relation_label",
    "legacy_patch",
    "legacy_edge_id",
    "evidence",
)

# Canonical key order for the top-level WorkbenchFile mapping.
_FILE_KEY_ORDER: tuple[str, ...] = ("patch", "rows")


def _row_to_dict(row: WorkbenchRow) -> dict[str, Any]:
    """Convert a normalized ``WorkbenchRow`` to an ordered dict for serialization.

    Rules:
    - Keys emitted in ``_ROW_KEY_ORDER`` order.
    - None values and empty lists are omitted (lean output).
    - ``evidence`` items must all be bare strings (refs) in the normalized row;
      any residual ``EvidenceStub`` is skipped with an assertion to catch bugs.
    - Evidence refs are sorted deterministically.
    """
    evidence_refs: list[str] = []
    for item in row.evidence:
        assert isinstance(item, str), (
            f"serialize_canonical: normalized row still contains an inline EvidenceStub; "
            f"call compile_workbench first.  Row id={row.id!r}"
        )
        evidence_refs.append(item)
    evidence_refs.sort()

    raw: dict[str, Any] = {
        "id": row.id,
        "subject": row.subject,
        "predicate": row.predicate,
        "object": row.object,
        "patch": row.patch,
        "polarity": row.polarity,
        "claim_layer": row.claim_layer,
        "identification_strength": row.identification_strength,
        "epistemic_role": row.epistemic_role,
        "legacy_relation_label": row.legacy_relation_label,
        "legacy_patch": row.legacy_patch,
        "legacy_edge_id": row.legacy_edge_id,
        "evidence": evidence_refs if evidence_refs else None,
    }

    result: dict[str, Any] = {}
    for key in _ROW_KEY_ORDER:
        value = raw.get(key)
        if value is None:
            continue
        result[key] = value
    return result


def serialize_canonical(result: CompileResult) -> str:
    """Produce the canonical YAML text of a compiled workbench.

    Takes a ``CompileResult`` (whose ``.workbench`` is the NORMALIZED form —
    every row has its minted/authored id and inline stubs replaced by id
    reference strings) and returns deterministic, lean YAML text.

    Ordering rules
    --------------
    - Rows sorted by proposition ``id`` (lexicographic, stable).
    - Within each row, keys emitted in ``_ROW_KEY_ORDER``; None/empty-list
      fields omitted.
    - Evidence refs sorted lexicographically within each row.
    - Top-level ``patch`` header omitted when None.

    Fixed-point guarantee
    ---------------------
    ``serialize_canonical(compile(serialize_canonical(compile(W))))``
    is bit-identical to ``serialize_canonical(compile(W))`` because:
    - The normalized workbench is already fully minted (no id-less rows).
    - Evidence items are already references (no inline stubs).
    - Sorted ordering is idempotent.

    Pure: does not write any files.
    """
    wb = result.workbench

    # Sort rows by their minted/authored proposition id.
    sorted_rows = sorted(wb.rows, key=lambda r: (r.id or ""))

    row_dicts = [_row_to_dict(row) for row in sorted_rows]

    doc: dict[str, Any] = {}
    for key in _FILE_KEY_ORDER:
        if key == "patch":
            if wb.patch is not None:
                doc["patch"] = wb.patch
        elif key == "rows":
            doc["rows"] = row_dicts

    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
