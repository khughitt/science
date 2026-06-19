from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.annotation.internal_prose_adapter import InternalProseAdapter
from science_tool.annotation.prose_decomposition import (
    DecompositionArtifact,
    DecompositionError,
    DecompositionUnit,
    ProseDecompositionStore,
    Quote,
    compute_source_hash,
    parse_submitted_decomposition,
)

_SUMMARY_KEYS = ("units", "resolved", "unresolved", "ambiguous", "stale", "hard_failures")


@dataclass(frozen=True)
class ProseValidationReport:
    source_ref: str
    artifact_id: str
    rows: list[dict[str, object]]

    def to_json(self) -> dict[str, object]:
        return {
            "source_ref": self.source_ref,
            "artifact_id": self.artifact_id,
            "summary": _summarize_units(self.rows),
            "units": self.rows,
        }


def validate_submitted_decomposition_artifact(
    artifact_path: Path,
    *,
    project_root: Path,
    allow_changed: bool = False,
) -> tuple[DecompositionArtifact, ProseValidationReport]:
    artifact = parse_submitted_decomposition(
        artifact_path.read_text(encoding="utf-8"),
        project_root=project_root,
    )
    current_hash = compute_source_hash(artifact.source.path)
    if current_hash != artifact.source.content_hash and not allow_changed:
        raise DecompositionError(
            "content hash mismatch: "
            f"artifact has {artifact.source.content_hash}; current source is {current_hash}"
        )
    rows = validate_decomposition_units(artifact, None)
    return artifact, ProseValidationReport(
        source_ref=artifact.source_ref,
        artifact_id=artifact.artifact.artifact_id,
        rows=rows,
    )


def validate_latest_decomposition(
    project_root: Path,
    source_slug: str,
) -> tuple[DecompositionArtifact, ProseValidationReport]:
    store = ProseDecompositionStore(project_root)
    index = store.load_index(source_slug)
    artifact = store.load_latest(source_slug)
    rows = validate_decomposition_units(artifact, index)
    return artifact, ProseValidationReport(
        source_ref=artifact.source_ref,
        artifact_id=artifact.artifact.artifact_id,
        rows=rows,
    )


def validate_decomposition_units(
    artifact: DecompositionArtifact,
    index: dict[str, Any] | None,
) -> list[dict[str, object]]:
    units_index = _units_index(index)
    use_index = index is not None
    adapter = InternalProseAdapter()
    rows: list[dict[str, object]] = []
    current_fingerprints = {unit.fingerprint for unit in artifact.units}

    for unit in artifact.units:
        index_row = _index_row_for_current_unit(units_index, unit) if use_index else {"promoted_to": None, "stale": False}
        quote = quote_for_decomposition_unit(unit)
        resolution = adapter.resolve_unit(artifact.source.path, unit.locator, quote)
        stale = index_row.get("stale", False)
        if not isinstance(stale, bool):
            raise DecompositionError(f"prose decomposition index stale must be a bool: {unit.fingerprint}")
        rows.append(
            {
                "unit_id": unit.unit_id,
                "disposition": unit.disposition,
                "status": "stale" if stale else unit.disposition,
                "fingerprint": unit.fingerprint,
                "locator_status": resolution.status.value,
                "message": resolution.message,
                "promoted_to": index_row.get("promoted_to"),
                "stale": stale,
            }
        )

    for fingerprint, index_row in units_index.items():
        if fingerprint in current_fingerprints:
            continue
        if not isinstance(index_row, dict):
            raise DecompositionError(f"prose decomposition index row must be an object: {fingerprint}")
        if index_row.get("stale") is True:
            rows.append(_stale_prose_decomposition_check_row(fingerprint, index_row))

    return rows


def quote_for_decomposition_unit(unit: DecompositionUnit) -> Quote:
    if unit.disposition == "candidate":
        if unit.candidate is None:
            raise DecompositionError(f"candidate unit {unit.unit_id} is missing candidate payload")
        return Quote(unit.candidate.exact, unit.candidate.prefix, unit.candidate.suffix)
    if unit.disposition == "skip":
        if unit.locator.quote is None:
            raise DecompositionError(f"skip unit {unit.unit_id} is missing locator quote")
        return unit.locator.quote
    raise DecompositionError(f"unknown unit disposition: {unit.disposition}")


def _summarize_units(rows: list[dict[str, object]]) -> dict[str, int]:
    summary = dict.fromkeys(_SUMMARY_KEYS, 0)
    summary["units"] = len(rows)
    for row in rows:
        if row.get("stale") is True:
            summary["stale"] += 1
            continue
        locator_status = row.get("locator_status")
        if locator_status in {"resolved", "unresolved", "ambiguous"}:
            summary[str(locator_status)] += 1
        else:
            summary["hard_failures"] += 1
    return summary


def _units_index(index: dict[str, Any] | None) -> dict[str, Any]:
    if index is None:
        return {}
    units_index = index.get("units")
    if not isinstance(units_index, dict):
        raise DecompositionError("prose decomposition index units must be an object")
    return units_index


def _index_row_for_current_unit(units_index: dict[str, Any], unit: DecompositionUnit) -> dict[str, object]:
    index_row = units_index.get(unit.fingerprint)
    if not isinstance(index_row, dict):
        raise DecompositionError(f"prose decomposition index row must be an object: {unit.fingerprint}")
    return index_row


def _stale_prose_decomposition_check_row(
    fingerprint: str,
    index_row: dict[str, object],
) -> dict[str, object]:
    return {
        "unit_id": index_row.get("latest_unit_id", ""),
        "disposition": index_row.get("latest_disposition", ""),
        "status": "stale",
        "fingerprint": fingerprint,
        "locator_status": "stale",
        "message": "unit is stale in latest decomposition",
        "promoted_to": index_row.get("promoted_to"),
        "stale": True,
    }
