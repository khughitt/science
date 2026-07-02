from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.annotation.io import read_sidecar, sidecar_for_markdown
from science_tool.annotation.model import Status
from science_tool.annotation.query import entity_relpath_for_sidecar
from science_tool.archive import ArchiveRow, _inbound_live_refs, derive_archive_path, load_archive_index
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
        kind = fm.get("type") or fm.get("kind")
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


def _live_promoted_backlinks(project_root: Path, candidate_ids: set[str]) -> dict[str, list[str]]:
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
            if promoted_to not in candidate_ids:
                continue
            if _annotation_status_value(ann.status) not in _ACTIVE_ANNOTATION_STATUSES:
                continue
            backlinks[promoted_to].add(_annotation_ref_for_sidecar(project_root, sidecar_path, ann.id))
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


def _lineage_for_candidate(candidate: _RawEntity, resolvable_ids: set[str]) -> tuple[str | None, list[str], list[str]]:
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

    seen: set[str] = set()
    for target in successors:
        if target == candidate.id:
            blockers.append("lineage points to itself")
        if target in seen:
            blockers.append(f"duplicate successor {target}")
        seen.add(target)
        if target not in resolvable_ids:
            blockers.append(f"unknown successor {target}")
    return lineage_kind, sorted(successors), blockers


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


def build_superseded_proposition_archive_report(project_root: Path) -> dict:
    project_root = Path(project_root).resolve()
    sources = load_project_sources(project_root)
    live_ids = {entity.canonical_id or entity.id for entity in sources.entities}
    archive = load_archive_index(project_root)
    resolvable_ids = live_ids | set(archive.resolvable_ids())
    raw = _raw_entities(project_root)
    candidate_ids = {
        ref
        for ref in live_ids
        if ref.startswith("proposition:")
        and ref in raw
        and raw[ref].frontmatter.get("status") == "superseded"
    }
    backlinks = _live_promoted_backlinks(project_root, candidate_ids)
    inbound = _inbound_live_refs(project_root, candidate_ids)
    collision_owners = _collision_owner_index(raw, archive)

    candidates: list[dict[str, Any]] = []
    for ref in sorted(live_ids):
        if not ref.startswith("proposition:"):
            continue
        row = raw.get(ref)
        if row is None or row.frontmatter.get("status") != "superseded":
            continue

        lineage_kind, successors, blockers = _lineage_for_candidate(row, resolvable_ids)
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
    report = build_superseded_proposition_archive_report(project_root)
    if not apply:
        return report
    raise PropositionArchiveError("apply is implemented in Task 5")
