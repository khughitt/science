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
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator
from science_model.entities import EntityType, EvidenceLineEntity, QuantitativeResult
from science_model.propositions import DiscussesMembership, PropositionEntity
from science_model.reasoning import (
    ClaimLayer,
    EvidenceStance,
    EvidenceType,
    IdentificationStrength,
    Polarity,
    Predicate,
    canonical_evidence_type_token,
)

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
    evidence_type: EvidenceType | None = None
    dataset_usage: str | None = None
    quantitative_result: QuantitativeResult | None = None

    @field_validator("evidence_type", mode="before")
    @classmethod
    def _canonicalize_evidence_type(cls, value: object) -> object:
        if isinstance(value, str):
            return canonical_evidence_type_token(value)
        return value


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

    # Core triple. `min_length=1`: these feed the derived proposition title, which must satisfy
    # base 2.0's `minLength: 1`. `predicate` is separately protected by the `Predicate(...)`
    # conversion; subject and object were protected by nothing, so an empty term reached the
    # persisted title. Failing here names the row, not the rendered file.
    subject: str = Field(min_length=1)
    predicate: str
    object: str = Field(min_length=1)

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

    # Bundle routing: an explicit per-row override of the file-level
    # ``focal_hypothesis``.  ``None`` inherits ``focal_hypothesis`` (the simple
    # single-focal path); a list routes this row's proposition to EXACTLY those
    # hypothesis bundles (supports bridge patches spanning multiple bundles).
    # For migrated DAG rows (``legacy_edge_id`` set) compile fails if neither
    # this nor ``focal_hypothesis`` is present — every migrated edge-proposition
    # must declare its bundle membership.
    # A bare string means role=core; an object carries an explicit MembershipRole
    # (same contract as PropositionEntity.discusses — spec §5).
    discusses: list[str | DiscussesMembership] | None = None

    # Evidence: authored inline as ``EvidenceStub``; after ``compile`` the
    # normalized row holds evidence-line *references* (ids) instead of inline
    # substance. The union keeps both shapes parseable — a bare string is an
    # ``evidence-line:<id>`` reference; a mapping is an authored stub.
    evidence: list[EvidenceStub | str] = Field(default_factory=list)


class WorkbenchFile(BaseModel):
    """Top-level structure of a ``<patch>.workbench.yaml`` file.

    ``patch`` is an optional file-level header (rows carry their own ``patch``
    field; the header is a convenience for single-patch files).
    ``focal_hypothesis`` declares the bundle this workbench's propositions
    discuss — compile stamps each minted proposition's ``discusses`` list with
    it, and materialize emits ``cito:discusses`` to the knowledge graph so
    ``bundle_members`` can find the edge-propositions.
    ``extra="forbid"`` keeps the file model strict too.
    """

    model_config = ConfigDict(extra="forbid")

    patch: str | None = None
    focal_hypothesis: str | None = None
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
    """Deterministic slug from a row's triple (`<subject>-<predicate>-<object>`)."""
    from science_tool.entities import EntityCommandError, slug_from_raw

    raw = "-".join(part for part in (subject, predicate, obj) if part)
    slug = slug_from_raw(raw)
    if len(slug) < 2:
        raise EntityCommandError("row triple cannot derive a stable proposition slug; set an explicit id")
    return slug


def _resolve_row_discusses(row: WorkbenchRow, focal_hypothesis: str | None) -> list[str | DiscussesMembership] | None:
    """Resolve a row's bundle membership (``cito:discusses`` targets).

    Routing rule (patch-level ``focal_hypothesis`` is a convenience default, not a
    semantic truth — a row may override it):

    - row has ``discusses``                -> use it EXACTLY (may name multiple bundles).
    - row lacks it, ``focal_hypothesis`` set -> inherit ``[focal_hypothesis]``.
    - neither, and the row is a migrated DAG row (``legacy_edge_id`` set) -> FAIL: every
      migrated edge-proposition must declare its bundle membership.
    - neither, ordinary (non-migrated) row -> ``None`` (no bundle membership).
    """
    if row.discusses is not None:
        return list(row.discusses)
    if focal_hypothesis is not None:
        return [focal_hypothesis]
    if row.legacy_edge_id is not None:
        from science_tool.entities import EntityCommandError

        raise EntityCommandError(
            f"migrated DAG row {row.subject}->{row.object} (legacy edge "
            f"{row.legacy_patch}#{row.legacy_edge_id}) has neither a row-level `discusses` nor a "
            f"file-level `focal_hypothesis`; every migrated edge-proposition must declare its "
            f"bundle membership (set row.discusses for bridge rows, focal_hypothesis otherwise)"
        )
    return None


def _collapse(text: str) -> str:
    """Collapse all runs of whitespace to single spaces. Titles are durable authored source."""
    return " ".join(text.split())


def _proposition_title(row: WorkbenchRow) -> str:
    """THE derived proposition title (design §5.2). Deterministic, not good prose.

    Mechanical on purpose: it must be stable and reconstructible from the row. An author may
    replace it afterwards, and the update path will preserve the replacement because `title` is
    not in the per-kind workbench key set.
    """
    return _collapse(f"{row.subject} {row.predicate} {row.object}")


def _evidence_line_title(stub: EvidenceStub, *, target_id: str) -> str:
    """THE derived evidence-line title (design §5.2).

    `target_id` is computed by the caller and always present, so the head alone is non-empty.
    `stance` defaults to SUPPORTS at lift, matching the entity field's own default.
    """
    stance = stub.stance or "supports"
    head = f"{stance} {target_id}"
    tail = stub.source or (stub.evidence_type.value if stub.evidence_type else None)
    return _collapse(f"{head} — {tail}" if tail else head)


def _proposition_for_row(row: WorkbenchRow) -> PropositionEntity:
    """Build a ``PropositionEntity`` from a row, minting a deterministic id if id-less.

    The proposition's canonical IRI (`proposition:<slug>`) is its edge-node /
    belief-target IRI directly (Task 0, no shim).
    """
    entity_id = row.id or f"proposition:{_slug_for_triple(row.subject, row.predicate, row.object)}"
    return PropositionEntity(
        id=entity_id,
        title=_proposition_title(row),
        subject=row.subject,
        object=row.object,
        predicate=Predicate(row.predicate),
        polarity=Polarity(row.polarity) if row.polarity is not None else None,
        legacy_relation_label=row.legacy_relation_label,
        legacy_patch=row.legacy_patch,
        legacy_edge_id=row.legacy_edge_id,
        claim_layer=ClaimLayer(row.claim_layer) if row.claim_layer is not None else None,
        identification_strength=(
            IdentificationStrength(row.identification_strength)
            if row.identification_strength is not None
            else None
        ),
    )


def _evidence_line_for_stub(stub: EvidenceStub, *, target_id: str, index: int) -> EvidenceLineEntity:
    """Lift an inline ``EvidenceStub`` to a typed ``EvidenceLineEntity``.

    ``target`` is the proposition id (edge-node IRI). Empirical evidence with no
    ``dataset_usage`` is staged ``belief_eligible=False`` (design §8.6); a
    literature stub, or an empirical stub WITH ``dataset_usage``, stays eligible.
    """
    target_slug = target_id.split(":", 1)[1]
    line_id = f"evidence-line:{target_slug}-ev{index}"
    is_staged_empirical = stub.evidence_type == EvidenceType.EMPIRICAL_DATA and not stub.dataset_usage
    return EvidenceLineEntity(
        id=line_id,
        kind="evidence-line",
        type=EntityType.EVIDENCE_LINE,
        title=_evidence_line_title(stub, target_id=target_id),
        # These are REQUIRED by the model and must keep being supplied. They are not persisted --
        # Task 3's owned-key allowlist is what keeps them out of the file. Deleting them here
        # raises `Field required` for all six.
        project="",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="",
        stance=EvidenceStance(stub.stance) if stub.stance is not None else EvidenceStance.SUPPORTS,
        target=target_id,
        source=stub.source,
        evidence_type=stub.evidence_type,
        quantitative_result=stub.quantitative_result,
        belief_eligible=not is_staged_empirical,
    )


def workbench_entity_body(entity: PropositionEntity | EvidenceLineEntity) -> str:
    """Default body used for new entities compiled from a workbench."""
    assert entity.id is not None
    local_part = entity.id.split(":", 1)[1]
    return f"# {entity.title or local_part}\n\n## Summary\n\n\n## Notes\n"


def _write_entity_file(
    entity: PropositionEntity | EvidenceLineEntity,
    *,
    project_root: Path,
    as_of: date | None = None,
) -> None:
    """Workbench writer: owned-allowlist frontmatter, never a full model dump.

    An UPSERT. `compile_workbench` is re-run over the same rows routinely, so the destination
    usually exists; rendering it as a create would overwrite the author's title, status and body
    on every recompile. Deliberately NOT `entities.write_entity_file`, which renders the whole
    model and would re-introduce the skeleton dump on this path.
    """
    from science_tool.dag.entity_frontmatter import (
        read_existing_target,
        render_create,
        render_update,
        workbench_ownership,
    )
    from science_tool.entities import _atomic_replace_text, resolve_path_policy

    today = (as_of or date.today()).isoformat()
    assert entity.id is not None
    local_part = entity.id.split(":", 1)[1]
    dest = project_root / resolve_path_policy(entity.kind, project_root=project_root).root / f"{local_part}.md"

    if dest.exists():
        # ADMIT FIRST. `read_existing_target` refuses a wrong-identity, undated or unparseable
        # destination. Reading the file directly and defaulting `created` -- as an earlier draft
        # of this plan did -- lets `render_update` overwrite id/kind/created/updated and hand
        # `certify_persisted` a mapping that is valid only because it was just repaired.
        existing_frontmatter, existing_body, _current = read_existing_target(dest, entity)
        text = render_update(
            entity,
            ownership=workbench_ownership(entity.kind),
            existing_frontmatter=existing_frontmatter,
            body=existing_body,
            created=str(existing_frontmatter["created"]),
            updated=today,
        )
    else:
        text = render_create(
            entity,
            ownership=workbench_ownership(entity.kind),
            body=workbench_entity_body(entity),
            created=today,
            updated=today,
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    _atomic_replace_text(dest, text)


def compile_workbench(
    workbench: WorkbenchFile | str | Path,
    *,
    project_root: Path,
    as_of: date | None = None,
) -> CompileResult:
    """Upsert proposition/evidence-line entities from a workbench; return the result.

    For each row: upsert a ``PropositionEntity`` (minting a deterministic id for
    id-less rows and writing it back into the normalized row), then lift each
    inline evidence stub to an ``EvidenceLineEntity`` (target = proposition id).
    The normalized workbench replaces inline stubs with evidence-line references.

    ``compile`` is the only writer of these entities from the workbench, so all
    entity files are (re)written via the canonical entity-layer writer.

    ``as_of`` controls the ``created``/``updated`` timestamps written into each
    entity file.  Defaults to ``date.today()`` when None so existing callers
    need not change.
    """
    if isinstance(workbench, (str, Path)):
        import yaml

        wb = WorkbenchFile.model_validate(yaml.safe_load(Path(workbench).read_text(encoding="utf-8")) or {})
    else:
        wb = workbench

    propositions: list[PropositionEntity] = []
    evidence_lines: list[EvidenceLineEntity] = []
    normalized_rows: list[WorkbenchRow] = []

    for row in wb.rows:
        prop = _proposition_for_row(row)
        discusses = _resolve_row_discusses(row, wb.focal_hypothesis)
        if discusses is not None:
            # model_validate (not model_copy) so the membership-conflict validator
            # runs at compile time, not only on later load (spec §5 rule 3).
            prop = PropositionEntity.model_validate({**prop.model_dump(), "discusses": discusses})
        _write_entity_file(prop, project_root=project_root, as_of=as_of)
        propositions.append(prop)

        evidence_refs: list[EvidenceStub | str] = []
        ev_index = 0
        for item in row.evidence:
            if isinstance(item, str):
                # Already-normalized reference: carry it through unchanged.
                evidence_refs.append(item)
                continue
            line = _evidence_line_for_stub(item, target_id=prop.id, index=ev_index)
            _write_entity_file(line, project_root=project_root, as_of=as_of)
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
    "discusses",
    "evidence",
)

# Canonical key order for the top-level WorkbenchFile mapping.
_FILE_KEY_ORDER: tuple[str, ...] = ("patch", "focal_hypothesis", "rows")


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
    sorted_rows = sorted(wb.rows, key=lambda r: r.id or "")

    row_dicts = [_row_to_dict(row) for row in sorted_rows]

    doc: dict[str, Any] = {}
    for key in _FILE_KEY_ORDER:
        if key == "patch":
            if wb.patch is not None:
                doc["patch"] = wb.patch
        elif key == "focal_hypothesis":
            if wb.focal_hypothesis is not None:
                doc["focal_hypothesis"] = wb.focal_hypothesis
        elif key == "rows":
            doc["rows"] = row_dicts

    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
