"""Read-only migration planning for retired ``*.edges.yaml`` DAG rows.

This module is the explicit Phase 5g migration surface. Default DAG render,
validate, audit, number, init, and inventory code must not import it.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Sequence
import warnings

import yaml
from pydantic import ValidationError

from science_model.propositions import PropositionEntity
from science_tool.dag.paths import load_dag_paths
from science_tool.dag.proposition_edges import load_relational_propositions
from science_tool.dag.schema import EdgeRecord, EdgeStatus, Identification, SchemaError
from science_tool.dag.workbench import WorkbenchFile
from science_tool.entities import is_default_visible


MigrationStatus = Literal["ready", "blocked", "skipped", "closed"]


@dataclass(frozen=True)
class LegacyEdgeClosureClaim:
    proposition: str
    subject: str
    object: str
    file_path: str

    def to_json(self) -> dict[str, str]:
        return {
            "proposition": self.proposition,
            "subject": self.subject,
            "object": self.object,
            "file_path": self.file_path,
        }


@dataclass(frozen=True)
class RetiredEdgeMigrationRow:
    path: str
    dag: str
    edge_id: int | None
    source: str
    target: str
    status: MigrationStatus
    description: str = ""
    raw_support: tuple[dict[str, str], ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)
    predicate_review_required: bool = False
    membership_required: bool = False
    evidence_warnings: tuple[str, ...] = field(default_factory=tuple)
    matching_propositions: tuple[str, ...] = field(default_factory=tuple)
    closed_by: tuple[str, ...] = field(default_factory=tuple)
    closure_reason: str = ""
    closure_conflicts: tuple[LegacyEdgeClosureClaim, ...] = field(default_factory=tuple)
    proposed_row: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "dag": self.dag,
            "edge_id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "description": self.description,
            "raw_support": [dict(entry) for entry in self.raw_support],
            "status": self.status,
            "blockers": list(self.blockers),
            "notes": list(self.notes),
            "predicate_review_required": self.predicate_review_required,
            "membership_required": self.membership_required,
            "evidence_warnings": list(self.evidence_warnings),
            "matching_propositions": list(self.matching_propositions),
            "closed_by": list(self.closed_by),
            "closure_reason": self.closure_reason,
            "closure_conflicts": [claim.to_json() for claim in self.closure_conflicts],
            "proposed_row": self.proposed_row,
        }


@dataclass(frozen=True)
class RetiredEdgeMigrationPlan:
    project_root: str
    focal_hypothesis: str | None
    rows: tuple[RetiredEdgeMigrationRow, ...] = field(default_factory=tuple)

    def to_json(self) -> dict[str, Any]:
        counts = Counter(row.status for row in self.rows)
        return {
            "project_root": self.project_root,
            "focal_hypothesis": self.focal_hypothesis,
            "summary": {
                "files": len({row.path for row in self.rows}),
                "rows": len(self.rows),
                "ready": counts["ready"],
                "blocked": counts["blocked"],
                "skipped": counts["skipped"],
                "closed": counts["closed"],
                "predicate_review_required": sum(1 for row in self.rows if row.predicate_review_required),
                "membership_required": sum(1 for row in self.rows if row.membership_required),
                "evidence_warnings": sum(len(row.evidence_warnings) for row in self.rows),
            },
            "rows": [row.to_json() for row in self.rows],
        }


ScaffoldStatus = Literal["written", "no-op", "complete"]


@dataclass(frozen=True)
class RetiredEdgeWorkbenchScaffoldResult:
    project_root: str
    dag: str
    focal_hypothesis: str
    output_path: str
    status: ScaffoldStatus
    row_count: int
    total_row_count: int
    closed_row_count: int
    predicate_review_required: int
    evidence_stub_count: int
    byte_count: int
    closed_by: tuple[str, ...] = field(default_factory=tuple)

    @property
    def written(self) -> bool:
        return self.status == "written"

    def to_json(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "dag": self.dag,
            "focal_hypothesis": self.focal_hypothesis,
            "output": self.output_path,
            "status": self.status,
            "written": self.written,
            "rows": self.row_count,
            "written_rows": self.row_count,
            "total_rows": self.total_row_count,
            "closed_rows": self.closed_row_count,
            "closed_by": list(self.closed_by),
            "predicate_review_required": self.predicate_review_required,
            "evidence_stubs": self.evidence_stub_count,
            "byte_count": self.byte_count,
        }


def build_retired_edge_migration_plan(
    project_root: Path,
    *,
    dag: str | None = None,
    focal_hypothesis: str | None = None,
) -> RetiredEdgeMigrationPlan:
    project_root = project_root.resolve()
    dag_dir = load_dag_paths(project_root).dag_dir
    yaml_paths = [dag_dir / f"{dag}.edges.yaml"] if dag else sorted(dag_dir.glob("*.edges.yaml"))

    if dag is not None and not yaml_paths[0].exists():
        raise ValueError(f"retired DAG edge file does not exist for dag {dag!r}: {yaml_paths[0]}")

    propositions_by_pair = _propositions_by_pair(project_root)
    closure_claims_by_edge = _closure_claims_by_legacy_edge(project_root)
    rows: list[RetiredEdgeMigrationRow] = []
    for yaml_path in yaml_paths:
        if not yaml_path.exists():
            continue
        payload = _load_edges_yaml_payload(yaml_path)
        dag_slug = str(payload.get("dag") or yaml_path.name.removesuffix(".edges.yaml"))
        dot_path = _resolve_dot_path(project_root, yaml_path, payload, dag_slug)
        dot_exists = bool(dot_path and dot_path.exists())
        rel_path = yaml_path.relative_to(project_root).as_posix()
        raw_edges = [] if "edges" not in payload else payload["edges"]
        if not isinstance(raw_edges, list):
            raise ValueError(f"invalid retired DAG edge file {yaml_path}: edges must be a list")
        seen_pairs: set[tuple[str, str]] = set()
        for index, raw_edge in enumerate(raw_edges, start=1):
            if not isinstance(raw_edge, dict):
                raise ValueError(f"invalid retired DAG edge file {yaml_path}: edge {index} must be a mapping")
            try:
                edge = _validate_edge_record(rel_path, raw_edge, index)
            except _MissingEdgeIdentity as exc:
                rows.append(_plan_missing_identity_edge(rel_path=rel_path, dag=dag_slug, raw_edge=raw_edge, exc=exc))
                continue
            except _InvalidEdgeIdentification:
                _record_raw_pair_or_raise(yaml_path=yaml_path, dag=dag_slug, raw_edge=raw_edge, seen_pairs=seen_pairs)
                rows.append(_plan_invalid_identification_edge(rel_path=rel_path, dag=dag_slug, raw_edge=raw_edge))
                continue

            pair = (edge.source, edge.target)
            _record_pair_or_raise(yaml_path=yaml_path, dag=dag_slug, pair=pair, seen_pairs=seen_pairs)
            rows.append(
                _plan_edge(
                    project_root=project_root,
                    rel_path=rel_path,
                    dag=dag_slug,
                    edge=edge,
                    missing_identification="identification" not in raw_edge,
                    dot_exists=dot_exists,
                    focal_hypothesis=focal_hypothesis,
                    propositions_by_pair=propositions_by_pair,
                    closure_claims_by_edge=closure_claims_by_edge,
                )
            )

    return RetiredEdgeMigrationPlan(
        project_root=project_root.as_posix(),
        focal_hypothesis=focal_hypothesis,
        rows=tuple(rows),
    )


def _record_raw_pair_or_raise(
    *,
    yaml_path: Path,
    dag: str,
    raw_edge: dict[str, Any],
    seen_pairs: set[tuple[str, str]],
) -> None:
    source = _raw_text(raw_edge.get("source"))
    target = _raw_text(raw_edge.get("target"))
    if not source or not target:
        return
    _record_pair_or_raise(yaml_path=yaml_path, dag=dag, pair=(source, target), seen_pairs=seen_pairs)


def _record_pair_or_raise(
    *,
    yaml_path: Path,
    dag: str,
    pair: tuple[str, str],
    seen_pairs: set[tuple[str, str]],
) -> None:
    if pair in seen_pairs:
        source, target = pair
        raise ValueError(
            f"invalid retired DAG edge file {yaml_path}: "
            f"duplicate edge (source={source!r}, target={target!r}) in DAG {dag!r}"
        )
    seen_pairs.add(pair)


def _load_edges_yaml_payload(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError("top-level YAML document must be a mapping")
        return payload
    except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
        raise ValueError(f"invalid retired DAG edge file {path}: {exc}") from exc


def _validate_edge_record(path: str, raw_edge: dict[str, Any], row_index: int) -> EdgeRecord:
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message=r"Edge is missing 'identification'.*", category=DeprecationWarning
            )
            return EdgeRecord.model_validate(_edge_record_payload_for_migration(raw_edge))
    except (SchemaError, TypeError, ValueError, ValidationError) as exc:
        if _invalid_identification_error(exc):
            raise _InvalidEdgeIdentification() from exc
        missing = _missing_required_fields(exc)
        if missing <= {"id", "source", "target"} and missing:
            raise _MissingEdgeIdentity(missing) from exc
        raise ValueError(f"invalid retired DAG edge file {path}: edge {row_index}: {exc}") from exc


def _edge_record_payload_for_migration(raw_edge: dict[str, Any]) -> dict[str, Any]:
    payload = dict(raw_edge)
    payload.setdefault("description", "")

    raw_lit_support = payload.get("lit_support")
    if isinstance(raw_lit_support, list):
        payload["lit_support"] = [
            _lit_support_payload_for_migration(entry) if isinstance(entry, dict) else entry for entry in raw_lit_support
        ]

    return payload


def _lit_support_payload_for_migration(raw_entry: dict[str, Any]) -> dict[str, Any]:
    if any(raw_entry.get(key) is not None for key in _REF_SOURCE_KEYS):
        return raw_entry
    return {**raw_entry, "paper": ""}


_MISSING_IDENTITY_BLOCKERS = {
    "id": "missing-edge-id",
    "source": "missing-source",
    "target": "missing-target",
}


class _MissingEdgeIdentity(ValueError):
    def __init__(self, fields: set[str]) -> None:
        super().__init__(",".join(sorted(fields)))
        self.fields = fields


class _InvalidEdgeIdentification(ValueError):
    pass


def _missing_required_fields(exc: BaseException) -> set[str]:
    if not isinstance(exc, ValidationError):
        return set()
    identity_fields = set(_MISSING_IDENTITY_BLOCKERS)
    result: set[str] = set()
    for error in exc.errors():
        loc = error.get("loc")
        if (
            error.get("type") != "missing"
            or not isinstance(loc, tuple)
            or len(loc) != 1
            or not isinstance(loc[0], str)
            or loc[0] not in identity_fields
        ):
            return set()
        result.add(loc[0])
    return result


def _invalid_identification_error(exc: BaseException) -> bool:
    if not isinstance(exc, ValidationError):
        return False
    errors = exc.errors()
    return len(errors) == 1 and errors[0].get("type") == "enum" and errors[0].get("loc") == ("identification",)


def _resolve_dot_path(project_root: Path, yaml_path: Path, payload: dict[str, Any], dag_slug: str) -> Path | None:
    source_dot = payload.get("source_dot")
    if isinstance(source_dot, str) and source_dot.strip():
        candidate = project_root / source_dot
        return candidate if candidate.exists() else yaml_path.parent / source_dot
    return yaml_path.parent / f"{dag_slug}.dot"


def _propositions_by_pair(project_root: Path) -> dict[tuple[str, str], list[PropositionEntity]]:
    result: dict[tuple[str, str], list[PropositionEntity]] = {}
    for prop in load_relational_propositions(project_root):
        if not is_default_visible(prop.status):
            continue
        if prop.subject is None or prop.object is None:
            continue
        result.setdefault((prop.subject, prop.object), []).append(prop)
    return result


def _closure_claims_by_legacy_edge(project_root: Path) -> dict[tuple[str, int], list[LegacyEdgeClosureClaim]]:
    result: dict[tuple[str, int], list[LegacyEdgeClosureClaim]] = {}
    for prop in load_relational_propositions(project_root):
        if not is_default_visible(prop.status):
            continue
        if prop.id is None or prop.legacy_patch is None or prop.legacy_edge_id is None:
            continue
        if prop.subject is None or prop.object is None:
            continue
        key = (prop.legacy_patch, prop.legacy_edge_id)
        result.setdefault(key, []).append(
            LegacyEdgeClosureClaim(
                proposition=prop.id,
                subject=prop.subject,
                object=prop.object,
                file_path=_project_relative_entity_path(project_root, prop.file_path),
            )
        )
    for claims in result.values():
        claims.sort(key=lambda claim: claim.proposition)
    return result


def _project_relative_entity_path(project_root: Path, file_path: str) -> str:
    path = Path(file_path)
    if not path.is_absolute():
        return file_path
    return _project_relative_or_absolute(project_root, path)


def _plan_missing_identity_edge(
    *,
    rel_path: str,
    dag: str,
    raw_edge: dict[str, Any],
    exc: _MissingEdgeIdentity,
) -> RetiredEdgeMigrationRow:
    blockers = tuple(_MISSING_IDENTITY_BLOCKERS[field] for field in sorted(exc.fields))
    return RetiredEdgeMigrationRow(
        path=rel_path,
        dag=dag,
        edge_id=_raw_int(raw_edge.get("id")),
        source=_raw_text(raw_edge.get("source")),
        target=_raw_text(raw_edge.get("target")),
        description=_raw_text(raw_edge.get("description")),
        raw_support=_raw_support_entries_from_raw(raw_edge),
        status="blocked",
        blockers=blockers,
    )


def _plan_invalid_identification_edge(
    *,
    rel_path: str,
    dag: str,
    raw_edge: dict[str, Any],
) -> RetiredEdgeMigrationRow:
    return RetiredEdgeMigrationRow(
        path=rel_path,
        dag=dag,
        edge_id=_raw_int(raw_edge.get("id")),
        source=_raw_text(raw_edge.get("source")),
        target=_raw_text(raw_edge.get("target")),
        description=_raw_text(raw_edge.get("description")),
        raw_support=_raw_support_entries_from_raw(raw_edge),
        status="blocked",
        blockers=("invalid-identification",),
    )


def _raw_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _raw_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _blocked_row(
    *,
    rel_path: str,
    dag: str,
    edge: EdgeRecord,
    source: str,
    target: str,
    description: str,
    raw_support: tuple[dict[str, str], ...],
    blockers: Sequence[str],
    notes: Sequence[str] = (),
    closure_conflicts: Sequence[LegacyEdgeClosureClaim] = (),
) -> RetiredEdgeMigrationRow:
    return RetiredEdgeMigrationRow(
        path=rel_path,
        dag=dag,
        edge_id=edge.id,
        source=source,
        target=target,
        description=description,
        raw_support=raw_support,
        status="blocked",
        blockers=tuple(blockers),
        notes=tuple(notes),
        closure_conflicts=tuple(closure_conflicts),
    )


def _closure_row_or_blocker(
    *,
    rel_path: str,
    dag: str,
    edge: EdgeRecord,
    source: str,
    target: str,
    description: str,
    raw_support: tuple[dict[str, str], ...],
    notes: Sequence[str],
    claims: Sequence[LegacyEdgeClosureClaim],
) -> RetiredEdgeMigrationRow | None:
    if not claims:
        return None
    if len(claims) > 1:
        return _blocked_row(
            rel_path=rel_path,
            dag=dag,
            edge=edge,
            source=source,
            target=target,
            description=description,
            raw_support=raw_support,
            blockers=("duplicate-legacy-edge-claim",),
            notes=notes,
            closure_conflicts=claims,
        )

    claim = claims[0]
    if claim.subject != source or claim.object != target:
        return _blocked_row(
            rel_path=rel_path,
            dag=dag,
            edge=edge,
            source=source,
            target=target,
            description=description,
            raw_support=raw_support,
            blockers=("legacy-edge-claim-mismatch",),
            notes=notes,
            closure_conflicts=(claim,),
        )

    return RetiredEdgeMigrationRow(
        path=rel_path,
        dag=dag,
        edge_id=edge.id,
        source=source,
        target=target,
        description=description,
        raw_support=raw_support,
        status="closed",
        notes=(*notes, "derived-closure"),
        closed_by=(claim.proposition,),
        closure_reason="derived-legacy-edge-lineage",
    )


def _plan_edge(
    *,
    project_root: Path,
    rel_path: str,
    dag: str,
    edge: EdgeRecord,
    missing_identification: bool,
    dot_exists: bool,
    focal_hypothesis: str | None,
    propositions_by_pair: dict[tuple[str, str], list[PropositionEntity]],
    closure_claims_by_edge: dict[tuple[str, int], list[LegacyEdgeClosureClaim]],
) -> RetiredEdgeMigrationRow:
    del project_root
    source = edge.source.strip()
    target = edge.target.strip()
    description = edge.description.strip()
    raw_support = _raw_support_entries(edge)
    blockers: list[str] = []
    notes: list[str] = []

    if not source:
        blockers.append("missing-source")
    if not target:
        blockers.append("missing-target")
    if missing_identification:
        notes.append("missing-identification-defaulted-to-none")
    if blockers:
        return _blocked_row(
            rel_path=rel_path,
            dag=dag,
            edge=edge,
            source=source,
            target=target,
            description=description,
            raw_support=raw_support,
            blockers=blockers,
            notes=notes,
        )

    closure_row = _closure_row_or_blocker(
        rel_path=rel_path,
        dag=dag,
        edge=edge,
        source=source,
        target=target,
        description=description,
        raw_support=raw_support,
        notes=notes,
        claims=closure_claims_by_edge.get((dag, edge.id), []),
    )
    if closure_row is not None:
        return closure_row

    if not dot_exists:
        blockers.append("dot-missing")
    if edge.edge_status == EdgeStatus.eliminated:
        blockers.append("eliminated-edge")

    if not _has_claim_support_content(edge):
        return RetiredEdgeMigrationRow(
            path=rel_path,
            dag=dag,
            edge_id=edge.id,
            source=source,
            target=target,
            description=description,
            raw_support=raw_support,
            status="skipped",
            notes=(*notes, "no-claim-support-content"),
        )

    matches = propositions_by_pair.get((source, target), [])
    if matches:
        missing_legacy = [
            prop.id
            for prop in matches
            if getattr(prop, "legacy_patch", None) is None or getattr(prop, "legacy_edge_id", None) is None
        ]
        if missing_legacy:
            notes.append("matching proposition lacks legacy_patch/legacy_edge_id")
        return RetiredEdgeMigrationRow(
            path=rel_path,
            dag=dag,
            edge_id=edge.id,
            source=source,
            target=target,
            description=description,
            raw_support=raw_support,
            status="skipped",
            blockers=("matching-proposition-exists",),
            notes=tuple(notes),
            matching_propositions=tuple(sorted(prop.id for prop in matches if prop.id is not None)),
        )

    membership_required = focal_hypothesis is None
    if membership_required:
        blockers.append("membership-required")

    proposed_row, evidence_warnings = _proposed_workbench_row(
        dag=dag,
        edge=edge,
        focal_hypothesis=focal_hypothesis,
    )
    status: MigrationStatus = "blocked" if blockers else "ready"
    return RetiredEdgeMigrationRow(
        path=rel_path,
        dag=dag,
        edge_id=edge.id,
        source=source,
        target=target,
        description=description,
        raw_support=raw_support,
        status=status,
        blockers=tuple(blockers),
        notes=tuple(notes),
        predicate_review_required=True,
        membership_required=membership_required,
        evidence_warnings=tuple(evidence_warnings),
        proposed_row=proposed_row,
    )


def _proposed_workbench_row(
    *,
    dag: str,
    edge: EdgeRecord,
    focal_hypothesis: str | None,
) -> tuple[dict[str, Any], list[str]]:
    row: dict[str, Any] = {
        "subject": edge.source.strip(),
        "predicate": "affects",
        "object": edge.target.strip(),
        "patch": dag,
        "polarity": "positive",
        "claim_layer": _claim_layer(edge),
        "identification_strength": _identification_strength(edge.identification),
        "legacy_relation_label": edge.relation or edge.original_label,
        "legacy_patch": dag,
        "legacy_edge_id": edge.id,
    }
    if focal_hypothesis is not None:
        row["discusses"] = [focal_hypothesis]

    evidence, warnings = _evidence_stubs(edge)
    if evidence:
        row["evidence"] = evidence
    return _drop_none(row), warnings


def _has_claim_support_content(edge: EdgeRecord) -> bool:
    return (
        bool(edge.description.strip())
        or bool(edge.data_support)
        or bool(edge.lit_support)
        or bool(edge.eliminated_by)
        or bool(edge.caveats)
    )


def _claim_layer(edge: EdgeRecord) -> str:
    if edge.edge_status == EdgeStatus.structural or edge.identification == Identification.structural:
        return "structural_claim"
    return "causal_effect"


def _identification_strength(value: Identification) -> str:
    return value.value


def _evidence_stubs(edge: EdgeRecord) -> tuple[list[dict[str, str]], list[str]]:
    evidence: list[dict[str, str]] = []
    warnings: list[str] = []
    for entry in edge.data_support:
        source = _ref_source(entry)
        if source is None:
            warnings.append("unmapped-data-support")
            continue
        evidence.append({"source": source, "evidence_type": "empirical_data", "stance": "supports"})
    for entry in edge.lit_support:
        source = _ref_source(entry)
        if source is None:
            warnings.append("unmapped-lit-support")
            continue
        evidence.append({"source": source, "evidence_type": "literature", "stance": "supports"})
    return evidence, warnings


def _raw_support_entries(edge: EdgeRecord) -> tuple[dict[str, str], ...]:
    entries: list[dict[str, str]] = []
    for section, support_entries in (
        ("data_support", edge.data_support),
        ("lit_support", edge.lit_support),
        ("eliminated_by", edge.eliminated_by or []),
    ):
        for entry in support_entries:
            source = _ref_source(entry)
            entries.append(
                {
                    "section": section,
                    "source": source or "",
                    "description": entry.description,
                }
            )
    return tuple(entries)


def _raw_support_entries_from_raw(raw_edge: dict[str, Any]) -> tuple[dict[str, str], ...]:
    entries: list[dict[str, str]] = []
    for section in ("data_support", "lit_support", "eliminated_by"):
        raw_entries = raw_edge.get(section)
        if not isinstance(raw_entries, list):
            continue
        for raw_entry in raw_entries:
            if not isinstance(raw_entry, dict):
                continue
            source = _raw_ref_source(raw_entry)
            description = raw_entry.get("description")
            entries.append(
                {
                    "section": section,
                    "source": source or "",
                    "description": description.strip() if isinstance(description, str) else "",
                }
            )
    return tuple(entries)


_REF_SOURCE_KEYS = ("task", "dataset", "accession", "paper", "doi", "proposition", "interpretation", "discussion")


def _ref_source(entry: object) -> str | None:
    extra = getattr(entry, "__pydantic_extra__", None) or {}
    for key in _REF_SOURCE_KEYS:
        value = extra.get(key)
        if isinstance(value, str) and value.strip():
            return f"{key}:{value.strip()}"
    return None


def _raw_ref_source(entry: dict[str, Any]) -> str | None:
    for key in _REF_SOURCE_KEYS:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return f"{key}:{value.strip()}"
    return None


def _drop_none(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None and value != []}


def migration_plan_to_workbench_yaml(plan: RetiredEdgeMigrationPlan) -> str:
    ready_rows = [row.proposed_row for row in plan.rows if row.status == "ready" and row.proposed_row is not None]
    if not ready_rows:
        raise ValueError(
            "no compile-compatible retired edge migration rows; pass --focal-hypothesis or inspect blockers"
        )
    doc: dict[str, Any] = {}
    if plan.focal_hypothesis is not None:
        doc["focal_hypothesis"] = plan.focal_hypothesis
    doc["rows"] = ready_rows
    WorkbenchFile.model_validate(doc)
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def _project_relative_or_absolute(project_root: Path, path: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _validate_scaffold_output_path(project_root: Path, output_path: Path, *, require_parent: bool) -> Path:
    candidate = output_path if output_path.is_absolute() else project_root / output_path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"output path escapes project root: {output_path}") from exc
    if require_parent and not resolved.parent.exists():
        raise ValueError(f"output parent directory does not exist: {resolved.parent}")
    if resolved.name.endswith(".edges.yaml"):
        raise ValueError("output path must not be a retired .edges.yaml file")
    if resolved.suffix == ".dot":
        raise ValueError("output path must not be a DOT file")
    return resolved


def _resolve_scaffold_output_path(project_root: Path, output_path: Path) -> Path:
    return _validate_scaffold_output_path(project_root, output_path, require_parent=True)


def _ready_scaffold_rows(plan: RetiredEdgeMigrationPlan) -> Sequence[RetiredEdgeMigrationRow]:
    return tuple(row for row in plan.rows if row.status == "ready" and row.proposed_row is not None)


def _evidence_stub_count(rows: Sequence[RetiredEdgeMigrationRow]) -> int:
    return sum(len(row.proposed_row.get("evidence", [])) for row in rows if row.proposed_row is not None)


def scaffold_retired_edge_workbench(
    project_root: Path,
    *,
    dag: str,
    focal_hypothesis: str,
    output_path: Path,
) -> RetiredEdgeWorkbenchScaffoldResult:
    project_root = project_root.resolve()
    if not dag.strip():
        raise ValueError("--dag is required")
    if not focal_hypothesis.strip():
        raise ValueError("--focal-hypothesis is required")

    plan = build_retired_edge_migration_plan(project_root, dag=dag, focal_hypothesis=focal_hypothesis)
    if not plan.rows:
        raise ValueError(f"retired DAG edge file for dag {dag!r} contains no migration rows")

    closed = [row for row in plan.rows if row.status == "closed"]
    blocked = [row for row in plan.rows if row.status == "blocked"]
    skipped = [row for row in plan.rows if row.status == "skipped"]
    evidence_warnings = [warning for row in plan.rows for warning in row.evidence_warnings]
    if blocked:
        details = ", ".join(f"{row.dag}#{row.edge_id}: {'/'.join(row.blockers)}" for row in blocked)
        raise ValueError(f"cannot scaffold blocked retired edge rows: {details}")
    if skipped:
        details = ", ".join(f"{row.dag}#{row.edge_id}: {'/'.join(row.blockers or row.notes)}" for row in skipped)
        raise ValueError(f"cannot scaffold skipped retired edge rows: {details}")
    if evidence_warnings:
        raise ValueError(f"cannot scaffold rows with evidence warnings: {', '.join(sorted(evidence_warnings))}")

    ready_rows = _ready_scaffold_rows(plan)
    ready_count = sum(1 for row in plan.rows if row.status == "ready")
    if len(ready_rows) != ready_count:
        raise AssertionError("Phase 5g invariant violated: ready row lacks proposed_row")
    closed_by = tuple(closed_id for row in closed for closed_id in row.closed_by)
    if closed and not ready_rows:
        resolved_output = _validate_scaffold_output_path(project_root, output_path, require_parent=False)
        return RetiredEdgeWorkbenchScaffoldResult(
            project_root=project_root.as_posix(),
            dag=dag,
            focal_hypothesis=focal_hypothesis,
            output_path=_project_relative_or_absolute(project_root, resolved_output),
            status="complete",
            row_count=0,
            total_row_count=len(plan.rows),
            closed_row_count=len(closed),
            closed_by=closed_by,
            predicate_review_required=0,
            evidence_stub_count=0,
            byte_count=0,
        )
    if not ready_rows:
        raise ValueError("no ready retired edge migration rows to scaffold")

    resolved_output = _resolve_scaffold_output_path(project_root, output_path)
    rendered = migration_plan_to_workbench_yaml(plan)
    # Write-boundary honesty check: persist only YAML accepted by the strict workbench schema.
    WorkbenchFile.model_validate(yaml.safe_load(rendered) or {})
    rendered_byte_count = len(rendered.encode("utf-8"))

    status: ScaffoldStatus = "written"
    if resolved_output.exists():
        current = resolved_output.read_text(encoding="utf-8")
        if current != rendered:
            raise ValueError(f"output path already exists with different content: {resolved_output}")
        status = "no-op"
    else:
        resolved_output.write_text(rendered, encoding="utf-8")

    return RetiredEdgeWorkbenchScaffoldResult(
        project_root=project_root.as_posix(),
        dag=dag,
        focal_hypothesis=focal_hypothesis,
        output_path=_project_relative_or_absolute(project_root, resolved_output),
        status=status,
        row_count=len(ready_rows),
        total_row_count=len(plan.rows),
        closed_row_count=len(closed),
        closed_by=closed_by,
        predicate_review_required=sum(1 for row in ready_rows if row.predicate_review_required),
        evidence_stub_count=_evidence_stub_count(ready_rows),
        byte_count=rendered_byte_count,
    )


def render_migration_plan_table(plan: RetiredEdgeMigrationPlan) -> str:
    payload = plan.to_json()
    lines = [
        "Retired edge migration plan: "
        f"{payload['summary']['ready']} ready, "
        f"{payload['summary']['blocked']} blocked, "
        f"{payload['summary']['skipped']} skipped, "
        f"{payload['summary']['closed']} closed."
    ]
    for row in payload["rows"]:
        if row["status"] == "closed":
            closed_by = ",".join(row["closed_by"]) if row["closed_by"] else "-"
            lines.append(
                f"  {row['dag']}#{row['edge_id']}: {row['source']} -> {row['target']} "
                f"closed by {closed_by}"
            )
            continue
        blockers = ",".join(row["blockers"]) if row["blockers"] else "-"
        notes = ",".join(row["notes"]) if row["notes"] else "-"
        lines.append(
            f"  {row['dag']}#{row['edge_id']}: {row['source']} -> {row['target']} "
            f"{row['status']} blockers={blockers} notes={notes}"
        )
    return "\n".join(lines) + "\n"


def render_retired_edge_workbench_scaffold_table(result: RetiredEdgeWorkbenchScaffoldResult) -> str:
    if result.status == "complete":
        return (
            f"Retired edge workbench scaffold complete: {result.dag}\n"
            f"  status: {result.status}\n"
            f"  focal_hypothesis: {result.focal_hypothesis}\n"
            f"  written_rows: {result.row_count}\n"
            f"  total_rows: {result.total_row_count}\n"
            f"  closed_rows: {result.closed_row_count}\n"
        )
    action = "Wrote" if result.written else "No-op"
    return (
        f"{action} retired edge workbench scaffold: {result.output_path}\n"
        f"  status: {result.status}\n"
        f"  dag: {result.dag}\n"
        f"  focal_hypothesis: {result.focal_hypothesis}\n"
        f"  rows: {result.row_count}\n"
        f"  total_rows: {result.total_row_count}\n"
        f"  closed_rows: {result.closed_row_count}\n"
        f"  predicate_review_required: {result.predicate_review_required}\n"
        f"  evidence_stubs: {result.evidence_stub_count}\n"
    )
