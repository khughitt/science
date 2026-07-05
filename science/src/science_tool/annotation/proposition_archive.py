from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.annotation.io import read_sidecar, sidecar_for_markdown
from science_tool.annotation.model import Status
from science_tool.annotation.query import entity_relpath_for_sidecar
from science_tool.archive import (
    ArchiveRow,
    _inbound_live_refs,
    _relocate_rows,
    archive_index_path,
    derive_archive_path,
    load_archive_index,
)
from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.entity_scan import iter_entity_markdown
from science_tool.graph.sources import load_project_sources


_ACTIVE_ANNOTATION_STATUSES = frozenset({Status.OPEN.value, Status.ACK.value})


class PropositionArchiveError(ValueError):
    """Raised when superseded proposition archive cannot proceed safely."""


@dataclass(frozen=True)
class _RawEntity:
    id: str
    kind: str
    path: Path
    relpath: str
    frontmatter: dict[str, Any]


def _raw_entities(project_root: Path) -> dict[str, _RawEntity]:
    rows: dict[str, _RawEntity] = {}
    entities_root = project_root / "entities"
    if not entities_root.is_dir():
        return rows
    for path in iter_entity_markdown(entities_root):
        fm = read_frontmatter(path)
        if not isinstance(fm, dict):
            continue
        raw_id = fm.get("id")
        if not isinstance(raw_id, str) or not raw_id:
            continue
        kind = fm.get("kind")
        if not isinstance(kind, str) or not kind:
            continue
        rows[raw_id] = _RawEntity(
            id=raw_id,
            kind=kind,
            path=path,
            relpath=path.relative_to(project_root).as_posix(),
            frontmatter=dict(fm),
        )
    return rows


def _annotation_status_value(status: object) -> str:
    if isinstance(status, Status):
        return status.value
    return str(status)


def _annotation_ref_for_sidecar(project_root: Path, sidecar_path: Path, annotation_id: str) -> str:
    return f"annotation:{entity_relpath_for_sidecar(sidecar_path, project_root)}#{annotation_id}"


def _live_promoted_backlinks(project_root: Path, candidate_owners: dict[str, set[str]]) -> dict[str, list[str]]:
    candidate_ids = {candidate_id for owners in candidate_owners.values() for candidate_id in owners}
    backlinks: dict[str, set[str]] = {candidate_id: set() for candidate_id in candidate_ids}
    entities_root = project_root / "entities"
    if not entities_root.is_dir():
        return {candidate_id: [] for candidate_id in candidate_ids}
    for markdown_path in iter_entity_markdown(entities_root):
        sidecar_path = sidecar_for_markdown(markdown_path)
        if not sidecar_path.is_file():
            continue
        try:
            sidecar = read_sidecar(sidecar_path)
        except Exception as exc:
            raise PropositionArchiveError(f"could not read sidecar {sidecar_path}: {exc}") from exc
        for ann in sidecar.annotations:
            if ann.annotation_type != "proposition":
                continue
            promoted_to = ann.promoted_to
            if not isinstance(promoted_to, str):
                continue
            owners = candidate_owners.get(promoted_to, set())
            if not owners:
                continue
            if _annotation_status_value(ann.status) not in _ACTIVE_ANNOTATION_STATUSES:
                continue
            ref = _annotation_ref_for_sidecar(project_root, sidecar_path, ann.id)
            for owner in owners:
                backlinks[owner].add(ref)
    return {candidate_id: sorted(refs) for candidate_id, refs in backlinks.items()}


def _alias_tokens(entity_id: str, frontmatter: dict[str, Any]) -> set[str]:
    tokens = {entity_id}
    for field in ("aliases", "same_as"):
        tokens.update(t for t in (frontmatter.get(field) or []) if isinstance(t, str) and t)
    return tokens


def _collision_owner_index(raw: dict[str, _RawEntity], archive: Any) -> dict[str, set[str]]:
    """Map id/alias token to owning ids across live entities and active archive rows."""
    owners: dict[str, set[str]] = {}
    for entity_id, entity in raw.items():
        for token in _alias_tokens(entity_id, entity.frontmatter):
            owners.setdefault(token, set()).add(entity_id)
    for archived_id, archived_row in archive.active_by_id.items():
        for token in (archived_id, *archived_row.aliases, *archived_row.same_as):
            owners.setdefault(token, set()).add(archived_id)
    return owners


def _successor_owner_index(live_ids: set[str], archive: Any) -> dict[str, set[str]]:
    owners: dict[str, set[str]] = {entity_id: {entity_id} for entity_id in live_ids}
    for archived_id, archived_row in archive.active_by_id.items():
        for token in (archived_id, *archived_row.aliases, *archived_row.same_as):
            owners.setdefault(token, set()).add(archived_id)
    return owners


def _candidate_owner_index(raw: dict[str, _RawEntity], candidate_ids: set[str]) -> dict[str, set[str]]:
    owners: dict[str, set[str]] = {}
    for candidate_id in candidate_ids:
        candidate = raw[candidate_id]
        for token in _alias_tokens(candidate_id, candidate.frontmatter):
            owners.setdefault(token, set()).add(candidate_id)
    return owners


def _resolve_successor(target: str, owner_index: dict[str, set[str]]) -> tuple[str, list[str]]:
    owners = owner_index.get(target, set())
    if not owners:
        return target, [f"unknown successor {target}"]
    if len(owners) > 1:
        return target, [f"ambiguous successor {target}: {sorted(owners)}"]
    return next(iter(owners)), []


def _lineage_for_candidate(
    candidate: _RawEntity, successor_owners: dict[str, set[str]]
) -> tuple[str | None, list[str], list[str]]:
    fm = candidate.frontmatter
    has_scalar = "superseded_by" in fm
    has_multi = "resynthesized_into" in fm
    blockers: list[str] = []
    if has_scalar and has_multi:
        return None, [], ["declares both superseded_by and resynthesized_into"]
    if not has_scalar and not has_multi:
        return None, [], ["missing lineage"]

    if has_scalar:
        target = fm.get("superseded_by")
        if not isinstance(target, str) or not target:
            return "superseded_by", [], ["malformed superseded_by"]
        successors = [target]
        lineage_kind = "superseded_by"
    else:
        raw_targets = fm.get("resynthesized_into")
        if not isinstance(raw_targets, list) or not raw_targets:
            return "resynthesized_into", [], ["malformed resynthesized_into"]
        successors = []
        for target in raw_targets:
            if not isinstance(target, str) or not target:
                return "resynthesized_into", [], ["malformed resynthesized_into"]
            successors.append(target)
        lineage_kind = "resynthesized_into"

    canonical_successors: list[str] = []
    seen: set[str] = set()
    for target in successors:
        canonical_target, target_blockers = _resolve_successor(target, successor_owners)
        blockers.extend(target_blockers)
        if canonical_target == candidate.id:
            blockers.append("lineage points to itself")
        if canonical_target in seen:
            blockers.append(f"duplicate successor {canonical_target}")
        seen.add(canonical_target)
        canonical_successors.append(canonical_target)
    return lineage_kind, sorted(canonical_successors), blockers


def _row_for_candidate(candidate: _RawEntity, lineage_kind: str, successors: list[str]) -> ArchiveRow:
    return ArchiveRow(
        op="archive",
        id=candidate.id,
        kind=candidate.kind,
        title=candidate.frontmatter.get("title") if isinstance(candidate.frontmatter.get("title"), str) else None,
        aliases=[a for a in (candidate.frontmatter.get("aliases") or []) if isinstance(a, str)],
        same_as=[s for s in (candidate.frontmatter.get("same_as") or []) if isinstance(s, str)],
        status="superseded",
        superseded_by=successors[0] if lineage_kind == "superseded_by" else None,
        resynthesized_into=successors if lineage_kind == "resynthesized_into" else [],
        original_path=candidate.relpath,
        reason="status:superseded",
    )


def _rows_for_ready_candidates(project_root: Path, report: dict) -> list[ArchiveRow]:
    current_report = build_superseded_proposition_archive_report(project_root)
    current_by_id = {candidate["id"]: candidate for candidate in current_report["candidates"]}
    raw = _raw_entities(project_root)
    rows: list[ArchiveRow] = []
    for candidate in report["candidates"]:
        if candidate["status"] != "ready":
            continue
        candidate_id = candidate["id"]
        current = current_by_id.get(candidate_id)
        raw_entity = raw.get(candidate_id)
        if current is None:
            if raw_entity is None:
                raise PropositionArchiveError(f"{candidate_id} disappeared before archive apply")
            if raw_entity.frontmatter.get("status") != "superseded":
                raise PropositionArchiveError(f"{candidate_id} is no longer superseded before archive apply")
            raise PropositionArchiveError(f"{candidate_id} is no longer an archive candidate before archive apply")
        if current["status"] != "ready":
            blockers = current.get("blockers") or []
            details = f": {', '.join(blockers)}" if blockers else f": current status is {current['status']}"
            raise PropositionArchiveError(f"{candidate_id} is no longer ready before archive apply{details}")
        if raw_entity is None:
            raise PropositionArchiveError(f"{candidate_id} disappeared before archive apply")
        for field in ("original_path", "archive_path"):
            if current[field] != candidate[field]:
                raise PropositionArchiveError(
                    f"{candidate_id} {field} changed before archive apply: {candidate[field]} -> {current[field]}"
                )
        lineage_kind = current["lineage_kind"]
        successors = current["successors"]
        if lineage_kind not in {"superseded_by", "resynthesized_into"}:
            raise PropositionArchiveError(f"{candidate_id} has invalid lineage kind at apply")
        if lineage_kind != candidate["lineage_kind"] or successors != candidate["successors"]:
            raise PropositionArchiveError(f"{candidate_id} lineage changed before archive apply")
        rows.append(_row_for_candidate(raw_entity, lineage_kind, successors))
    return rows


def _postflight(project_root: Path, rows: list[ArchiveRow]) -> None:
    from science_tool.graph.materialize import materialize_graph

    index = load_archive_index(project_root)
    for row in rows:
        if row.id not in index.active_by_id:
            raise PropositionArchiveError(f"{row.id} missing from archive index after apply")
        if row.original_path is None:
            raise PropositionArchiveError(f"{row.id} archive row missing original_path after apply")
        active = index.active_by_id[row.id]
        fields = (
            "op",
            "id",
            "kind",
            "title",
            "aliases",
            "same_as",
            "status",
            "superseded_by",
            "resynthesized_into",
            "original_path",
            "archived_at",
            "reason",
        )
        for field in fields:
            if getattr(active, field) != getattr(row, field):
                raise PropositionArchiveError(f"{row.id} archive index mismatch: {field}")
        live_path = project_root / row.original_path
        archive_path = project_root / derive_archive_path(row.original_path)
        if live_path.exists():
            raise PropositionArchiveError(f"{row.id} live file still exists after archive apply")
        if not archive_path.exists():
            raise PropositionArchiveError(f"{row.id} archived file missing after archive apply")
    try:
        materialize_graph(project_root, strict=False)
    except Exception as exc:
        raise PropositionArchiveError(f"postflight materialization failed: {exc}") from exc


def build_superseded_proposition_archive_report(project_root: Path) -> dict:
    project_root = Path(project_root).resolve()
    sources = load_project_sources(project_root)
    live_ids = {entity.canonical_id or entity.id for entity in sources.entities}
    archive = load_archive_index(project_root)
    successor_owners = _successor_owner_index(live_ids, archive)
    raw = _raw_entities(project_root)
    candidate_ids = {
        ref
        for ref in live_ids
        if ref.startswith("proposition:") and ref in raw and raw[ref].frontmatter.get("status") == "superseded"
    }
    candidate_owners = _candidate_owner_index(raw, candidate_ids)
    backlinks = _live_promoted_backlinks(project_root, candidate_owners)
    inbound = _inbound_live_refs(project_root, candidate_ids)
    collision_owners = _collision_owner_index(raw, archive)

    candidates: list[dict[str, Any]] = []
    for ref in sorted(live_ids):
        if not ref.startswith("proposition:"):
            continue
        row = raw.get(ref)
        if row is None or row.frontmatter.get("status") != "superseded":
            continue

        lineage_kind, successors, blockers = _lineage_for_candidate(row, successor_owners)
        archive_path = derive_archive_path(row.relpath)
        if (project_root / archive_path).exists():
            blockers.append(f"archive destination exists: {archive_path}")
        if row.id in archive.active_by_id:
            blockers.append(f"archive id already active: {row.id}")
        annotation_refs = backlinks.get(row.id, [])
        if annotation_refs:
            blockers.append(f"live annotation backlink(s): {', '.join(annotation_refs)}")
        for token in sorted(_alias_tokens(row.id, row.frontmatter)):
            colliding = collision_owners.get(token, set()) - {row.id}
            if colliding:
                blockers.append(f"id/alias collision on {token}: {sorted(colliding)}")
        status = "ready" if not blockers else "blocked"
        candidates.append(
            {
                "id": row.id,
                "original_path": row.relpath,
                "archive_path": archive_path,
                "lineage_kind": lineage_kind,
                "successors": successors,
                "status": status,
                "blockers": sorted(blockers),
                "blocking_annotation_refs": annotation_refs,
                "inbound_live_refs": inbound.get(row.id, []),
            }
        )

    summary = {
        "ready": sum(1 for candidate in candidates if candidate["status"] == "ready"),
        "blocked": sum(1 for candidate in candidates if candidate["status"] == "blocked"),
        "skipped": 0,
    }
    return {"summary": summary, "candidates": candidates, "applied": [], "skipped": []}


def archive_superseded_propositions(
    project_root: Path,
    *,
    apply: bool = False,
    now: str | None = None,
) -> dict:
    project_root = Path(project_root).resolve()
    report = build_superseded_proposition_archive_report(project_root)
    if not apply:
        return report

    rows = _rows_for_ready_candidates(project_root, report)
    if not rows:
        return report

    result = _relocate_rows(archive_index_path(project_root), project_root, rows, now=now)
    report["applied"] = result["applied"]
    report["skipped"] = result["skipped"]
    postflight_rows = [row.model_copy(update={"archived_at": now}) for row in rows] if now is not None else rows
    _postflight(project_root, postflight_rows)
    return report
