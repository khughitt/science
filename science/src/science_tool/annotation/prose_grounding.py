"""Project graph grounding results back onto P2 prose decomposition units."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.annotation.prose_decomposition import (
    DecompositionArtifact,
    DecompositionError,
    DecompositionUnit,
    ProseDecompositionStore,
    artifact_unit_ref,
)
from science_tool.graph.belief import BeliefMagnitude
from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY
from science_tool.graph.grounding import (
    DEFAULT_GROUNDING_FLOOR,
    GroundingError,
    GroundingResult,
    GroundingStatus,
    ground_proposition,
    load_grounding_graphs,
)


_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


class ProseGroundingError(ValueError):
    pass


@dataclass(frozen=True)
class ProseGroundingReport:
    payload: dict[str, object]

    def to_json(self) -> dict[str, object]:
        return self.payload


def prose_grounding_path(project_root: Path, source_slug: str) -> Path:
    return project_root / "data" / "prose-grounding" / _validate_source_slug(source_slug) / "grounding.json"


def build_prose_grounding_report(
    project_root: Path,
    source_ref: str,
    graph_path: Path,
    generated_at: str,
    floor: str = DEFAULT_GROUNDING_FLOOR,
) -> ProseGroundingReport:
    project_root = Path(project_root)
    graph_path = Path(graph_path)
    slug = _source_slug(source_ref)
    try:
        floor = BeliefMagnitude(floor).value
    except ValueError as exc:
        raise ProseGroundingError(f"unknown grounding floor: {floor}") from exc
    store = ProseDecompositionStore(project_root)
    try:
        artifact = store.load_latest(slug)
        index = store.load_index(slug)
        knowledge, provenance = load_grounding_graphs(graph_path)
    except (DecompositionError, GroundingError) as exc:
        raise ProseGroundingError(str(exc)) from exc

    index_units = index.get("units")
    if not isinstance(index_units, dict):
        raise ProseGroundingError("prose decomposition index units must be an object")

    rows: list[dict[str, object]] = []
    grounding_results: list[GroundingResult] = []
    current_fingerprints = {unit.fingerprint for unit in artifact.units}
    for unit in artifact.units:
        if unit.fingerprint not in index_units:
            raise ProseGroundingError(f"missing current decomposition index row: {unit.fingerprint}")
        row, result = _row_for_current_unit(
            artifact,
            unit,
            index_units[unit.fingerprint],
            knowledge=knowledge,
            provenance=provenance,
            floor=floor,
        )
        rows.append(row)
        if result is not None:
            grounding_results.append(result)

    for fingerprint, index_row in sorted(index_units.items()):
        if fingerprint not in current_fingerprints and isinstance(index_row, dict) and index_row.get("stale") is True:
            rows.append(_stale_row(fingerprint, index_row))

    grounding_policy = (
        _policy_from_grounding(grounding_results[0])
        if grounding_results
        else {
            "floor": floor,
            "belief_policy_id": DEFAULT_BELIEF_POLICY.policy_id,
            "belief_policy_version": DEFAULT_BELIEF_POLICY.version,
        }
    )
    return ProseGroundingReport(
        {
            "schema_version": 1,
            "source_ref": source_ref,
            "decomposition_artifact_id": artifact.artifact.artifact_id,
            "graph_path": _project_relative_path(project_root, graph_path),
            "generated_at": generated_at,
            "grounding_policy": grounding_policy,
            "summary": _summary(rows),
            "units": rows,
        }
    )


def write_prose_grounding_report(project_root: Path, report: ProseGroundingReport) -> bool:
    source_ref = report.payload.get("source_ref")
    if not isinstance(source_ref, str):
        raise ProseGroundingError("prose grounding report source_ref must be a string")
    path = prose_grounding_path(Path(project_root), _source_slug(source_ref))
    text = _canonical_json_text(report.payload)
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = None
        if isinstance(existing, dict) and _without_generated_at(existing) == _without_generated_at(report.payload):
            return False

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)
    return True


def _row_for_current_unit(
    artifact: DecompositionArtifact,
    unit: DecompositionUnit,
    index_row: object,
    *,
    knowledge,
    provenance,
    floor: str,
) -> tuple[dict[str, object], GroundingResult | None]:
    if not isinstance(index_row, dict):
        raise ProseGroundingError(f"prose decomposition index unit row must be an object: {unit.fingerprint}")
    row: dict[str, object] = {
        "unit_id": unit.unit_id,
        "fingerprint": unit.fingerprint,
        "disposition": unit.disposition,
        "artifact_ref": artifact_unit_ref(artifact, unit),
    }
    if unit.disposition == "skip":
        row.update(
            {
                "status": "skipped",
                "proposition_ref": None,
                "grounding": None,
                "skip_reason": unit.reason_code,
                "skip_detail": unit.reason_detail,
            }
        )
        return row, None

    promoted_to = index_row.get("promoted_to")
    if promoted_to is None:
        row.update({"status": "unpromoted", "proposition_ref": None, "grounding": None})
        return row, None
    if not isinstance(promoted_to, str) or not promoted_to.startswith("proposition:"):
        raise ProseGroundingError(f"invalid promoted proposition ref for unit {unit.fingerprint}: {promoted_to!r}")

    try:
        result = ground_proposition(promoted_to, knowledge, provenance, floor=floor)
    except GroundingError as exc:
        raise ProseGroundingError(str(exc)) from exc
    row.update(
        {
            "status": result.status.value,
            "proposition_ref": promoted_to,
            "grounding": _grounding_payload(result),
        }
    )
    return row, result


def _grounding_payload(result: GroundingResult) -> dict[str, object]:
    payload = result.to_json()
    payload.pop("target_ref", None)
    payload.pop("status", None)
    payload["belief_policy_id"] = payload.pop("policy_id")
    payload["belief_policy_version"] = payload.pop("policy_version")
    return payload


def _policy_from_grounding(result: GroundingResult) -> dict[str, object]:
    return {
        "floor": result.floor,
        "belief_policy_id": result.policy_id,
        "belief_policy_version": result.policy_version,
    }


def _stale_row(fingerprint: str, index_row: dict[str, Any]) -> dict[str, object]:
    promoted_to = index_row.get("promoted_to")
    return {
        "unit_id": index_row.get("latest_unit_id"),
        "fingerprint": fingerprint,
        "disposition": index_row.get("latest_disposition"),
        "artifact_ref": index_row.get("artifact_unit_ref"),
        "status": "stale",
        "proposition_ref": promoted_to if isinstance(promoted_to, str) else None,
        "grounding": None,
    }


def _summary(rows: list[dict[str, object]]) -> dict[str, int]:
    current_rows = [row for row in rows if row.get("status") != "stale"]
    current_candidates = [row for row in current_rows if row.get("disposition") == "candidate"]
    return {
        "current_candidate_units": len(current_candidates),
        "promoted_units": sum(1 for row in current_candidates if row.get("proposition_ref") is not None),
        "grounded_units": sum(1 for row in current_rows if row.get("status") == GroundingStatus.GROUNDED.value),
        "below_floor_units": sum(1 for row in current_rows if row.get("status") == GroundingStatus.BELOW_FLOOR.value),
        "unbacked_units": sum(1 for row in current_rows if row.get("status") == GroundingStatus.UNBACKED.value),
        "unpromoted_units": sum(1 for row in current_rows if row.get("status") == "unpromoted"),
        "skipped_units": sum(1 for row in current_rows if row.get("status") == "skipped"),
        "stale_units": sum(1 for row in rows if row.get("status") == "stale"),
        "contested_units": sum(
            1
            for row in current_rows
            if isinstance(row.get("grounding"), dict) and row["grounding"].get("contested") is True
        ),
    }


def _source_slug(source_ref: str) -> str:
    if not isinstance(source_ref, str) or not source_ref.startswith("prose-source:"):
        raise ProseGroundingError(f"invalid prose source ref: {source_ref!r}")
    slug = source_ref.removeprefix("prose-source:")
    if not _SLUG_RE.fullmatch(slug):
        raise ProseGroundingError(f"invalid prose source ref: {source_ref!r}")
    return slug


def _validate_source_slug(source_slug: str) -> str:
    if not isinstance(source_slug, str) or not _SLUG_RE.fullmatch(source_slug):
        raise ProseGroundingError(f"invalid prose source slug: {source_slug!r}")
    return source_slug


def _project_relative_path(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _canonical_json_text(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _without_generated_at(payload: dict[str, object]) -> dict[str, object]:
    copy = dict(payload)
    copy.pop("generated_at", None)
    return copy
