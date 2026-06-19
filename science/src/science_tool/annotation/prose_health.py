"""Project-level prose epistemics health artifact from P2/P3 read models."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from science_tool.annotation.prose_decomposition import (
    DecompositionArtifact,
    DecompositionError,
    DecompositionUnit,
    ProseDecompositionStore,
    artifact_unit_ref,
)
from science_tool.annotation.prose_grounding import prose_grounding_path


DEFAULT_MANIFEST_REL = Path("data") / "prose-health" / "manifest.json"
DEFAULT_ARTIFACT_REL = Path("data") / "prose-health" / "prose-health.json"
SUMMARY_KEYS = (
    "current_candidate_units",
    "promoted_units",
    "grounded_units",
    "below_floor_units",
    "unbacked_units",
    "unpromoted_units",
    "skipped_units",
    "stale_units",
    "contested_units",
)
SOURCE_STATE_PRECEDENCE = (
    "missing_decomposition",
    "invalid_decomposition",
    "missing_grounding",
    "invalid_grounding",
    "stale_grounding",
    "complete",
)
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


class ProseHealthError(ValueError):
    """Raised when the P4 prose-health artifact cannot be built or read."""


@dataclass(frozen=True)
class ManifestSource:
    source_ref: str
    slug: str
    path: Path
    title: str


@dataclass(frozen=True)
class ProseHealthManifest:
    path: Path
    sources: tuple[ManifestSource, ...]


@dataclass(frozen=True)
class ProseHealthReport:
    payload: dict[str, object]

    def to_json(self) -> dict[str, object]:
        return self.payload


def prose_health_manifest_path(project_root: Path) -> Path:
    return Path(project_root) / DEFAULT_MANIFEST_REL


def prose_health_path(project_root: Path) -> Path:
    return Path(project_root) / DEFAULT_ARTIFACT_REL


def load_prose_health_manifest(project_root: Path, manifest_path: Path | None = None) -> ProseHealthManifest:
    project_root = Path(project_root).resolve()
    path = _resolve_manifest_path(project_root, manifest_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProseHealthError(f"prose health manifest is missing: {_project_relative_path(project_root, path)}") from exc
    except json.JSONDecodeError as exc:
        raise ProseHealthError(f"invalid prose health manifest JSON: {_project_relative_path(project_root, path)}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProseHealthError("prose health manifest must be a JSON object")
    if raw.get("schema_version") != 1:
        raise ProseHealthError("prose health manifest schema_version must be 1")
    sources_raw = raw.get("sources")
    if not isinstance(sources_raw, list):
        raise ProseHealthError("prose health manifest sources must be an array")

    sources: list[ManifestSource] = []
    seen_refs: set[str] = set()
    for index, item in enumerate(sources_raw):
        if not isinstance(item, dict):
            raise ProseHealthError(f"prose health manifest source[{index}] must be an object")
        source_ref = _required_string(item, f"source[{index}].source_ref")
        slug = _source_slug(source_ref)
        if source_ref in seen_refs:
            raise ProseHealthError(f"duplicate prose health manifest source: {source_ref}")
        seen_refs.add(source_ref)
        path_text = _required_string(item, f"source[{index}].path")
        title = _required_string(item, f"source[{index}].title")
        sources.append(
            ManifestSource(
                source_ref=source_ref,
                slug=slug,
                path=_resolve_source_path(path_text, project_root=project_root),
                title=title,
            )
        )
    return ProseHealthManifest(path=path, sources=tuple(sources))


def build_prose_health_report(
    project_root: Path,
    *,
    manifest_path: Path | None = None,
    generated_at: str,
) -> ProseHealthReport:
    project_root = Path(project_root).resolve()
    manifest = load_prose_health_manifest(project_root, manifest_path)
    store = ProseDecompositionStore(project_root)
    source_rows: list[dict[str, object]] = []
    unit_rows: list[dict[str, object]] = []
    findings: list[dict[str, object]] = []

    declared_slugs = {source.slug for source in manifest.sources}
    for source in manifest.sources:
        source_result = _build_source_rows(project_root=project_root, store=store, source=source)
        source_rows.append(source_result["source"])
        unit_rows.extend(source_result["units"])
        finding = source_result["finding"]
        if finding is not None:
            findings.append(finding)

    findings.extend(_undeclared_grounding_findings(project_root, declared_slugs))

    summary = _summary(source_rows)
    return ProseHealthReport(
        {
            "schema_version": 1,
            "generated_at": generated_at,
            "manifest_path": _project_relative_path(project_root, manifest.path),
            "summary": summary,
            "coverage": _coverage(summary),
            "sources": source_rows,
            "units": unit_rows,
            "findings": findings,
        }
    )


def write_prose_health_report(project_root: Path, report: ProseHealthReport) -> bool:
    path = prose_health_path(Path(project_root))
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


def load_prose_health_artifact(project_root: Path) -> dict[str, object]:
    path = prose_health_path(Path(project_root))
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProseHealthError(f"prose health artifact is missing: {_project_relative_path(Path(project_root), path)}") from exc
    except json.JSONDecodeError as exc:
        raise ProseHealthError(f"invalid prose health artifact JSON: {_project_relative_path(Path(project_root), path)}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProseHealthError("prose health artifact must be a JSON object")
    if raw.get("schema_version") != 1:
        raise ProseHealthError("prose health artifact schema_version must be 1")
    return raw


def _build_source_rows(
    *,
    project_root: Path,
    store: ProseDecompositionStore,
    source: ManifestSource,
) -> dict[str, object]:
    source_base = {
        "source_ref": source.source_ref,
        "title": source.title,
        "path": _project_relative_path(project_root, source.path),
        "decomposition_artifact_id": None,
        "grounding_report_path": _project_relative_path(project_root, prose_grounding_path(project_root, source.slug)),
        "summary": _empty_summary(),
    }
    try:
        artifact = store.load_latest(source.slug)
    except DecompositionError as exc:
        state = "missing_decomposition" if "missing latest decomposition artifact" in str(exc) else "invalid_decomposition"
        row = {**source_base, "state": state}
        return {"source": row, "units": [], "finding": _finding(state, source, str(exc), project_root=project_root)}

    grounding_path = prose_grounding_path(project_root, source.slug)
    if not grounding_path.exists():
        state = "missing_grounding"
        row = {
            **source_base,
            "state": state,
            "decomposition_artifact_id": artifact.artifact.artifact_id,
        }
        return {
            "source": row,
            "units": [],
            "finding": _finding(
                state,
                source,
                f"missing grounding report: {_project_relative_path(project_root, grounding_path)}",
                project_root=project_root,
            ),
        }
    try:
        grounding = _load_grounding_report(grounding_path, project_root=project_root)
    except ProseHealthError as exc:
        state = "invalid_grounding"
        row = {
            **source_base,
            "state": state,
            "decomposition_artifact_id": artifact.artifact.artifact_id,
        }
        return {"source": row, "units": [], "finding": _finding(state, source, str(exc), project_root=project_root)}

    state = _grounding_state(source=source, artifact=artifact, grounding=grounding)
    if state != "complete":
        row = {
            **source_base,
            "state": state,
            "decomposition_artifact_id": artifact.artifact.artifact_id,
        }
        return {
            "source": row,
            "units": [],
            "finding": _finding(state, source, f"grounding report is {state}", project_root=project_root),
        }

    try:
        rows = _unit_rows(project_root=project_root, source=source, artifact=artifact, grounding=grounding)
    except ProseHealthError as exc:
        state = "invalid_grounding"
        row = {
            **source_base,
            "state": state,
            "decomposition_artifact_id": artifact.artifact.artifact_id,
        }
        return {"source": row, "units": [], "finding": _finding(state, source, str(exc), project_root=project_root)}
    source_summary = _summary_from_units(rows)
    source_row = {
        **source_base,
        "state": "complete",
        "decomposition_artifact_id": artifact.artifact.artifact_id,
        "summary": source_summary,
    }
    return {"source": source_row, "units": rows, "finding": None}


def _load_grounding_report(path: Path, *, project_root: Path) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProseHealthError(f"missing grounding report: {_project_relative_path(project_root, path)}") from exc
    except json.JSONDecodeError as exc:
        raise ProseHealthError(f"invalid grounding report JSON: {_project_relative_path(project_root, path)}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProseHealthError(f"invalid grounding report: {_project_relative_path(project_root, path)}")
    if raw.get("schema_version") != 1:
        raise ProseHealthError("grounding report schema_version must be 1")
    return raw


def _grounding_state(*, source: ManifestSource, artifact: DecompositionArtifact, grounding: dict[str, object]) -> str:
    if grounding.get("source_ref") != source.source_ref:
        return "invalid_grounding"
    if not isinstance(grounding.get("units"), list):
        return "invalid_grounding"
    if grounding.get("decomposition_artifact_id") != artifact.artifact.artifact_id:
        return "stale_grounding"
    return "complete"


def _unit_rows(
    *,
    project_root: Path,
    source: ManifestSource,
    artifact: DecompositionArtifact,
    grounding: dict[str, object],
) -> list[dict[str, object]]:
    grounding_units = grounding.get("units")
    if not isinstance(grounding_units, list):
        raise ProseHealthError("grounding report units must be an array")
    grounding_by_fingerprint: dict[str, dict[str, object]] = {}
    for index, row in enumerate(grounding_units):
        if not isinstance(row, dict):
            raise ProseHealthError(f"grounding report unit[{index}] must be an object")
        fingerprint = row.get("fingerprint")
        if not isinstance(fingerprint, str) or not fingerprint:
            raise ProseHealthError(f"grounding report unit[{index}].fingerprint must be a non-empty string")
        if fingerprint in grounding_by_fingerprint:
            raise ProseHealthError(f"duplicate grounding report unit fingerprint: {fingerprint}")
        grounding_by_fingerprint[fingerprint] = row
    rows: list[dict[str, object]] = []
    for unit in artifact.units:
        grounding_row = grounding_by_fingerprint.get(unit.fingerprint)
        if not isinstance(grounding_row, dict):
            raise ProseHealthError(f"grounding report missing unit fingerprint: {unit.fingerprint}")
        rows.append(_unit_row(project_root=project_root, source=source, artifact=artifact, unit=unit, grounding_row=grounding_row))
    for grounding_row in grounding_units:
        if not isinstance(grounding_row, dict):
            continue
        if grounding_row.get("status") == "stale":
            rows.append(_stale_unit_row(project_root=project_root, source=source, grounding_row=grounding_row))
    return rows


def _unit_row(
    *,
    project_root: Path,
    source: ManifestSource,
    artifact: DecompositionArtifact,
    unit: DecompositionUnit,
    grounding_row: dict[str, object],
) -> dict[str, object]:
    expected_artifact_ref = artifact_unit_ref(artifact, unit)
    if grounding_row.get("unit_id") != unit.unit_id:
        raise ProseHealthError(f"grounding report unit_id mismatch for fingerprint: {unit.fingerprint}")
    if grounding_row.get("artifact_ref") != expected_artifact_ref:
        raise ProseHealthError(f"grounding report artifact_ref mismatch for fingerprint: {unit.fingerprint}")
    if grounding_row.get("disposition") != unit.disposition:
        raise ProseHealthError(f"grounding report disposition mismatch for fingerprint: {unit.fingerprint}")
    return {
        "source_ref": source.source_ref,
        "source_path": _project_relative_path(project_root, source.path),
        "unit_id": unit.unit_id,
        "fingerprint": unit.fingerprint,
        "artifact_ref": expected_artifact_ref,
        "heading_path": list(unit.locator.heading_path),
        "quote": _quote_payload(unit),
        "status": grounding_row.get("status"),
        "disposition": unit.disposition,
        "proposition_ref": grounding_row.get("proposition_ref"),
        "grounding": grounding_row.get("grounding"),
        "skip_reason": unit.reason_code,
        "skip_detail": unit.reason_detail if unit.disposition == "skip" else None,
    }


def _stale_unit_row(*, project_root: Path, source: ManifestSource, grounding_row: dict[str, object]) -> dict[str, object]:
    return {
        "source_ref": source.source_ref,
        "source_path": _project_relative_path(project_root, source.path),
        "unit_id": grounding_row.get("unit_id"),
        "fingerprint": grounding_row.get("fingerprint"),
        "artifact_ref": grounding_row.get("artifact_ref"),
        "heading_path": None,
        "quote": None,
        "status": "stale",
        "disposition": grounding_row.get("disposition"),
        "proposition_ref": grounding_row.get("proposition_ref"),
        "grounding": None,
        "skip_reason": None,
        "skip_detail": None,
    }


def _quote_payload(unit: DecompositionUnit) -> dict[str, str]:
    if unit.disposition == "candidate" and unit.candidate is not None:
        quote = unit.candidate
        return {"exact": quote.exact, "prefix": quote.prefix, "suffix": quote.suffix}
    if unit.disposition == "skip" and unit.locator.quote is not None:
        quote = unit.locator.quote
        return {"exact": quote.exact, "prefix": quote.prefix, "suffix": quote.suffix}
    raise ProseHealthError(f"unit is missing quote data: {unit.unit_id}")


def _summary(source_rows: list[dict[str, object]]) -> dict[str, int]:
    summary = {
        "declared_sources": len(source_rows),
        "sources_with_decomposition": sum(1 for row in source_rows if row.get("decomposition_artifact_id") is not None),
        # This is an existence count: stale reports exist but are flagged separately by source state/findings.
        "sources_with_grounding": sum(1 for row in source_rows if row.get("state") in {"complete", "stale_grounding"}),
        **_empty_summary(),
    }
    for row in source_rows:
        row_summary = row.get("summary")
        if not isinstance(row_summary, dict):
            continue
        for key in SUMMARY_KEYS:
            value = row_summary.get(key, 0)
            if isinstance(value, int):
                summary[key] += value
    return summary


def _summary_from_units(rows: list[dict[str, object]]) -> dict[str, int]:
    current = [row for row in rows if row.get("status") != "stale"]
    candidates = [row for row in current if row.get("disposition") == "candidate"]
    return {
        "current_candidate_units": len(candidates),
        "promoted_units": sum(1 for row in candidates if row.get("proposition_ref") is not None),
        "grounded_units": sum(1 for row in current if row.get("status") == "grounded"),
        "below_floor_units": sum(1 for row in current if row.get("status") == "below_floor"),
        "unbacked_units": sum(1 for row in current if row.get("status") == "unbacked"),
        "unpromoted_units": sum(1 for row in current if row.get("status") == "unpromoted"),
        "skipped_units": sum(1 for row in current if row.get("status") == "skipped"),
        "stale_units": sum(1 for row in rows if row.get("status") == "stale"),
        "contested_units": sum(
            1
            for row in current
            if isinstance(row.get("grounding"), dict) and row["grounding"].get("contested") is True
        ),
    }


def _empty_summary() -> dict[str, int]:
    return {key: 0 for key in SUMMARY_KEYS}


def _coverage(summary: dict[str, int]) -> dict[str, dict[str, float | int | None]]:
    candidates = summary["current_candidate_units"]
    promoted = summary["promoted_units"]
    grounded = summary["grounded_units"]
    return {
        "promotion": _coverage_metric(promoted, candidates),
        "grounding": _coverage_metric(grounded, promoted),
        "strict_grounding": _coverage_metric(grounded, candidates),
    }


def _coverage_metric(numerator: int, denominator: int) -> dict[str, float | int | None]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "ratio": None if denominator == 0 else numerator / denominator,
    }


def _finding(code: str, source: ManifestSource, message: str, *, project_root: Path) -> dict[str, object]:
    return {
        "code": code,
        "severity": "error" if code in {"invalid_decomposition", "invalid_grounding"} else "warning",
        "counts_as_issue": True,
        "source_ref": source.source_ref,
        "path": _project_relative_path(project_root, source.path),
        "message": message,
    }


def _undeclared_grounding_findings(project_root: Path, declared_slugs: set[str]) -> list[dict[str, object]]:
    root = project_root / "data" / "prose-grounding"
    if not root.exists():
        return []
    findings: list[dict[str, object]] = []
    for path in sorted(root.glob("*/grounding.json")):
        slug = path.parent.name
        if slug in declared_slugs:
            continue
        findings.append(
            {
                "code": "undeclared_grounding_report",
                "severity": "warning",
                "counts_as_issue": False,
                "source_ref": f"prose-source:{slug}",
                "path": _project_relative_path(project_root, path),
                "message": "P3 grounding report exists for a source not declared in the prose health manifest.",
            }
        )
    return findings


def _resolve_manifest_path(project_root: Path, manifest_path: Path | None) -> Path:
    if manifest_path is None:
        return project_root / DEFAULT_MANIFEST_REL
    manifest_path = Path(manifest_path)
    resolved = manifest_path.resolve() if manifest_path.is_absolute() else (project_root / manifest_path).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise ProseHealthError("manifest path must stay under project root") from exc
    return resolved


def _resolve_source_path(value: str, *, project_root: Path) -> Path:
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (project_root / path).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise ProseHealthError("manifest source path must stay under project root") from exc
    return resolved


def _source_slug(source_ref: str) -> str:
    if not isinstance(source_ref, str) or not source_ref.startswith("prose-source:"):
        raise ProseHealthError(f"invalid prose source ref: {source_ref!r}")
    slug = source_ref.split(":", 1)[1]
    if not _SLUG_RE.fullmatch(slug):
        raise ProseHealthError(f"invalid prose source ref: {source_ref!r}")
    return slug


def _required_string(raw: dict[str, object], key: str) -> str:
    field = key.split(".")[-1]
    value = raw.get(field)
    if not isinstance(value, str) or not value:
        raise ProseHealthError(f"{key} must be a non-empty string")
    return value


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
