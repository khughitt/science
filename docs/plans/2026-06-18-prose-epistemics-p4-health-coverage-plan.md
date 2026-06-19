# P4 Prose Health Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the P4 framework-only prose-health layer: an explicit manifest, one project-level `data/prose-health/prose-health.json` artifact, a builder CLI, and a `science health` reader section.

**Architecture:** Add a focused `science_tool.annotation.prose_health` module that reads a manifest, joins P2 latest decomposition state with P3 grounding reports by fingerprint, computes coverage-ramp metrics, and writes canonical JSON. Add an `annotate build-prose-health` command to produce the artifact, then add a read-only `prose_epistemics` health check that summarizes the artifact or reports manifest/artifact gaps without rebuilding.

**Tech Stack:** Python 3.13, Click, pytest, existing P2 `ProseDecompositionStore`, existing P3 `prose_grounding_path`/grounding report schema, existing `science_tool.graph.health` check registry.

---

## References

- Design: `docs/plans/2026-06-18-prose-epistemics-p4-health-coverage-design.md`
- P2 design: `docs/plans/2026-06-18-prose-epistemics-p2-internal-prose-design.md`
- P3 design: `docs/plans/2026-06-18-prose-epistemics-p3-domain-grounding-design.md`
- Existing P2 code: `science/src/science_tool/annotation/prose_decomposition.py`
- Existing P3 code: `science/src/science_tool/annotation/prose_grounding.py`
- Existing annotate CLI: `science/src/science_tool/annotation/cli.py`
- Existing health registry: `science/src/science_tool/graph/health.py`

## Precondition

P2 and P3 must be present before implementing this plan. Before Task 1, verify these symbols exist:

```bash
cd science
PYTHONPATH=src:model/src rtk uv run --frozen python - <<'PY'
from science_tool.annotation.prose_decomposition import ProseDecompositionStore, artifact_unit_ref
from science_tool.annotation.prose_grounding import prose_grounding_path, write_prose_grounding_report
print(ProseDecompositionStore, artifact_unit_ref, prose_grounding_path, write_prose_grounding_report)
PY
```

Expected: exits 0 and prints imported objects. If this fails, reconcile P4 against shipped P2/P3 before continuing.

## File Structure

- Create: `science/src/science_tool/annotation/prose_health.py`
  - Owns manifest parsing, P2/P3 artifact joining, source-state precedence, coverage metrics, canonical P4 artifact writing, and artifact loading for health.
- Create: `science/tests/test_prose_health.py`
  - Unit tests for manifest validation, complete source projection, missing/stale/invalid states, undeclared reports, coverage math, fingerprint joins, and writer churn.
- Modify: `science/src/science_tool/annotation/cli.py`
  - Add `build-prose-health` command to the existing P2/P3 annotate command family.
- Modify: `science/tests/test_annotate_prose_decomposition_cli.py`
  - Add CLI tests for `build-prose-health`.
- Modify: `science/src/science_tool/graph/health.py`
  - Add `prose_epistemics` health check and include its issue count in `total_issues`.
- Modify: `science/src/science_tool/cli.py`
  - Add compact table rendering for prose epistemics findings/coverage.
- Modify: `science/tests/test_health.py`
  - Add health JSON/table/list-checks tests for `prose_epistemics`.

## Task 1: Prose Health Core - Manifest, Paths, Complete Projection

**Files:**
- Create: `science/src/science_tool/annotation/prose_health.py`
- Create: `science/tests/test_prose_health.py`

- [ ] **Step 1: Write failing core tests**

Create `science/tests/test_prose_health.py` with this content:

```python
import json
from pathlib import Path

import pytest

from science_tool.annotation.prose_decomposition import (
    ProseDecompositionStore,
    compute_source_hash,
    parse_submitted_decomposition,
)
from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY


def _source(root: Path, slug: str = "example") -> Path:
    source = root / "docs" / f"{slug}.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "# Section\n\n"
        "Basalt flows record the cooling history. "
        "This framing orients the example.\n",
        encoding="utf-8",
    )
    return source


def _artifact_payload(
    root: Path,
    *,
    slug: str = "example",
    artifact_id: str = "decomp-1",
    unit_id: str = "u001",
    quote: str = "Basalt flows record the cooling history.",
) -> dict:
    source = _source(root, slug)
    return {
        "schema_version": 1,
        "source": {
            "kind": "prose-source",
            "slug": slug,
            "path": str(source),
            "title": slug.title(),
            "content_hash": compute_source_hash(source),
        },
        "artifact": {
            "id": artifact_id,
            "generated_at": "2026-06-18T12:00:00Z",
            "producer": "offline-agent",
        },
        "units": [
            {
                "unit_id": unit_id,
                "disposition": "candidate",
                "locator": {"regime": "markdown-heading-path", "value": ["Section"]},
                "payload": {
                    "type": "proposition",
                    "exact": quote,
                    "prefix": "",
                    "suffix": "",
                    "stance": "asserted",
                },
            },
            {
                "unit_id": "s001",
                "disposition": "skip",
                "locator": {
                    "regime": "markdown-heading-path-with-quote",
                    "value": ["Section"],
                    "quote": {
                        "exact": "This framing orients the example.",
                        "prefix": "",
                        "suffix": "",
                    },
                },
                "reason": {"code": "not_a_claim", "detail": "Framing sentence."},
            },
        ],
    }


def _persist_decomposition(root: Path, payload: dict):
    artifact = parse_submitted_decomposition(json.dumps(payload), project_root=root)
    store = ProseDecompositionStore(root)
    store.persist(artifact)
    return artifact, store


def _write_grounding(root: Path, *, artifact, status: str = "grounded") -> Path:
    unit_rows = []
    for unit in artifact.units:
        if unit.disposition == "candidate":
            unit_rows.append(
                {
                    "unit_id": unit.unit_id,
                    "fingerprint": unit.fingerprint,
                    "disposition": "candidate",
                    "artifact_ref": f"annotation:data/prose-decompositions/{artifact.source.slug}/generations/{artifact.artifact.artifact_id}.json#{unit.unit_id}",
                    "status": status,
                    "proposition_ref": "proposition:basalt-cooling" if status != "unpromoted" else None,
                    "grounding": (
                        {
                            "target_uri": "https://example.invalid/proposition/basalt-cooling",
                            "belief_magnitude": "supported" if status == "grounded" else "fragile",
                            "support_count": 2 if status == "grounded" else 1,
                            "dispute_count": 0,
                            "contested": False,
                            "capped_by_refutation": False,
                            "authored_capped": False,
                            "qa_dataset_capped": False,
                            "belief_policy_id": DEFAULT_BELIEF_POLICY.policy_id,
                            "belief_policy_version": DEFAULT_BELIEF_POLICY.version,
                        }
                        if status != "unpromoted"
                        else None
                    ),
                }
            )
        elif unit.disposition == "skip":
            unit_rows.append(
                {
                    "unit_id": unit.unit_id,
                    "fingerprint": unit.fingerprint,
                    "disposition": "skip",
                    "artifact_ref": f"annotation:data/prose-decompositions/{artifact.source.slug}/generations/{artifact.artifact.artifact_id}.json#{unit.unit_id}",
                    "status": "skipped",
                    "proposition_ref": None,
                    "grounding": None,
                    "skip_reason": unit.reason_code,
                    "skip_detail": unit.reason_detail,
                }
            )
    candidate_count = sum(1 for unit in artifact.units if unit.disposition == "candidate")
    skip_count = sum(1 for unit in artifact.units if unit.disposition == "skip")
    report = {
        "schema_version": 1,
        "source_ref": artifact.source_ref,
        "decomposition_artifact_id": artifact.artifact.artifact_id,
        "graph_path": "knowledge/graph.trig",
        "generated_at": "2026-06-18T13:00:00Z",
        "grounding_policy": {
            "floor": "supported",
            "belief_policy_id": DEFAULT_BELIEF_POLICY.policy_id,
            "belief_policy_version": DEFAULT_BELIEF_POLICY.version,
        },
        "summary": {
            "current_candidate_units": candidate_count,
            "promoted_units": 0 if status == "unpromoted" else candidate_count,
            "grounded_units": candidate_count if status == "grounded" else 0,
            "below_floor_units": candidate_count if status == "below_floor" else 0,
            "unbacked_units": candidate_count if status == "unbacked" else 0,
            "unpromoted_units": candidate_count if status == "unpromoted" else 0,
            "skipped_units": skip_count,
            "stale_units": 0,
            "contested_units": 0,
        },
        "units": unit_rows,
    }
    path = root / "data" / "prose-grounding" / artifact.source.slug / "grounding.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_manifest(root: Path, *, slug: str = "example") -> Path:
    path = root / "data" / "prose-health" / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sources": [
                    {
                        "source_ref": f"prose-source:{slug}",
                        "path": f"docs/{slug}.md",
                        "title": slug.title(),
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_manifest_validation_rejects_duplicate_source_refs(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import ProseHealthError, load_prose_health_manifest

    _source(tmp_path)
    path = tmp_path / "data" / "prose-health" / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sources": [
                    {"source_ref": "prose-source:example", "path": "docs/example.md", "title": "Example"},
                    {"source_ref": "prose-source:example", "path": "docs/example.md", "title": "Example"},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ProseHealthError, match="duplicate prose health manifest source"):
        load_prose_health_manifest(tmp_path)


def test_manifest_validation_rejects_path_traversal(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import ProseHealthError, load_prose_health_manifest

    path = tmp_path / "data" / "prose-health" / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sources": [
                    {"source_ref": "prose-source:example", "path": "../outside.md", "title": "Example"}
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ProseHealthError, match="manifest source path must stay under project root"):
        load_prose_health_manifest(tmp_path)


def test_build_prose_health_report_projects_complete_source(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    artifact, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path))
    _write_grounding(tmp_path, artifact=artifact, status="grounded")
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["schema_version"] == 1
    assert report["manifest_path"] == "data/prose-health/manifest.json"
    assert report["summary"] == {
        "declared_sources": 1,
        "sources_with_decomposition": 1,
        "sources_with_grounding": 1,
        "current_candidate_units": 1,
        "promoted_units": 1,
        "grounded_units": 1,
        "below_floor_units": 0,
        "unbacked_units": 0,
        "unpromoted_units": 0,
        "skipped_units": 1,
        "stale_units": 0,
        "contested_units": 0,
    }
    assert report["coverage"] == {
        "promotion": {"numerator": 1, "denominator": 1, "ratio": 1.0},
        "grounding": {"numerator": 1, "denominator": 1, "ratio": 1.0},
        "strict_grounding": {"numerator": 1, "denominator": 1, "ratio": 1.0},
    }
    assert report["sources"][0]["state"] == "complete"
    assert report["findings"] == []
    candidate = report["units"][0]
    assert candidate["source_ref"] == "prose-source:example"
    assert candidate["source_path"] == "docs/example.md"
    assert candidate["heading_path"] == ["Section"]
    assert candidate["quote"] == {
        "exact": "Basalt flows record the cooling history.",
        "prefix": "",
        "suffix": "",
    }
    assert candidate["fingerprint"] == artifact.units[0].fingerprint
    assert candidate["status"] == "grounded"
    assert candidate["proposition_ref"] == "proposition:basalt-cooling"
    assert candidate["skip_reason"] is None
    assert candidate["skip_detail"] is None
    skip = report["units"][1]
    assert skip["status"] == "skipped"
    assert skip["quote"] == {
        "exact": "This framing orients the example.",
        "prefix": "",
        "suffix": "",
    }
    assert skip["skip_reason"] == "not_a_claim"
    assert skip["skip_detail"] == "Framing sentence."


def test_zero_denominator_coverage_ratios_are_null(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    artifact_payload = _artifact_payload(tmp_path)
    artifact_payload["units"] = [artifact_payload["units"][1]]
    artifact, _store = _persist_decomposition(tmp_path, artifact_payload)
    _write_grounding(tmp_path, artifact=artifact, status="grounded")
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["summary"]["current_candidate_units"] == 0
    assert report["coverage"] == {
        "promotion": {"numerator": 0, "denominator": 0, "ratio": None},
        "grounding": {"numerator": 0, "denominator": 0, "ratio": None},
        "strict_grounding": {"numerator": 0, "denominator": 0, "ratio": None},
    }
```

- [ ] **Step 2: Run the core tests to verify they fail**

Run:

```bash
cd science
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p4-core-red tests/test_prose_health.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.annotation.prose_health'`.

- [ ] **Step 3: Implement the core module**

Create `science/src/science_tool/annotation/prose_health.py` with this content:

```python
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
    "stale_grounding",
    "missing_grounding",
    "invalid_grounding",
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

    for source in manifest.sources:
        source_result = _build_source_rows(project_root=project_root, store=store, source=source)
        source_rows.append(source_result["source"])
        unit_rows.extend(source_result["units"])
        finding = source_result["finding"]
        if finding is not None:
            findings.append(finding)

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
        return {"source": row, "units": [], "finding": _finding(state, source, str(exc))}

    grounding_path = prose_grounding_path(project_root, source.slug)
    try:
        grounding = _load_grounding_report(grounding_path, project_root=project_root)
    except ProseHealthError as exc:
        state = "missing_grounding" if "missing" in str(exc) else "invalid_grounding"
        row = {
            **source_base,
            "state": state,
            "decomposition_artifact_id": artifact.artifact.artifact_id,
        }
        return {"source": row, "units": [], "finding": _finding(state, source, str(exc))}

    state = _grounding_state(source=source, artifact=artifact, grounding=grounding)
    if state != "complete":
        row = {
            **source_base,
            "state": state,
            "decomposition_artifact_id": artifact.artifact.artifact_id,
        }
        return {"source": row, "units": [], "finding": _finding(state, source, f"grounding report is {state}")}

    rows = _unit_rows(project_root=project_root, source=source, artifact=artifact, grounding=grounding)
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
    return raw


def _grounding_state(*, source: ManifestSource, artifact: DecompositionArtifact, grounding: dict[str, object]) -> str:
    if grounding.get("source_ref") != source.source_ref:
        return "invalid_grounding"
    if grounding.get("decomposition_artifact_id") != artifact.artifact.artifact_id:
        return "stale_grounding"
    if not isinstance(grounding.get("units"), list):
        return "invalid_grounding"
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
    grounding_by_fingerprint = {
        row.get("fingerprint"): row for row in grounding_units if isinstance(row, dict) and isinstance(row.get("fingerprint"), str)
    }
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
    return {
        "source_ref": source.source_ref,
        "source_path": _project_relative_path(project_root, source.path),
        "unit_id": unit.unit_id,
        "fingerprint": unit.fingerprint,
        "artifact_ref": artifact_unit_ref(artifact, unit),
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


def _finding(code: str, source: ManifestSource, message: str) -> dict[str, object]:
    return {
        "code": code,
        "severity": "warning" if code != "invalid_decomposition" and code != "invalid_grounding" else "error",
        "counts_as_issue": True,
        "source_ref": source.source_ref,
        "path": source.path.as_posix(),
        "message": message,
    }


def _resolve_manifest_path(project_root: Path, manifest_path: Path | None) -> Path:
    if manifest_path is None:
        return project_root / DEFAULT_MANIFEST_REL
    manifest_path = Path(manifest_path)
    return manifest_path if manifest_path.is_absolute() else project_root / manifest_path


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
```

- [ ] **Step 4: Run core tests**

Run:

```bash
cd science
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p4-core-green tests/test_prose_health.py
```

Expected: PASS for all tests in `tests/test_prose_health.py`.

- [ ] **Step 5: Commit Task 1**

```bash
cd science
rtk git add src/science_tool/annotation/prose_health.py tests/test_prose_health.py
rtk git commit -m "feat(prose): add prose health core"
```

## Task 2: Source-State Failures, Undeclared Reports, Fingerprint Joins, Writer

**Files:**
- Modify: `science/src/science_tool/annotation/prose_health.py`
- Modify: `science/tests/test_prose_health.py`

- [ ] **Step 1: Append failing source-state and writer tests**

Append this content to `science/tests/test_prose_health.py`:

```python
def test_missing_decomposition_produces_state_and_finding(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    _source(tmp_path)
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "missing_decomposition"
    assert report["summary"]["declared_sources"] == 1
    assert report["summary"]["sources_with_decomposition"] == 0
    assert report["findings"] == [
        {
            "code": "missing_decomposition",
            "severity": "warning",
            "counts_as_issue": True,
            "source_ref": "prose-source:example",
            "path": str(tmp_path / "docs" / "example.md"),
            "message": "missing latest decomposition artifact for source slug: example",
        }
    ]


def test_missing_grounding_produces_state_and_finding(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    _persist_decomposition(tmp_path, _artifact_payload(tmp_path))
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "missing_grounding"
    assert report["summary"]["sources_with_decomposition"] == 1
    assert report["summary"]["sources_with_grounding"] == 0
    assert report["findings"][0]["code"] == "missing_grounding"
    assert report["findings"][0]["counts_as_issue"] is True


def test_stale_grounding_uses_precedence_and_counts_as_issue(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    first, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path, artifact_id="decomp-1"))
    _write_grounding(tmp_path, artifact=first, status="grounded")
    _persist_decomposition(tmp_path, _artifact_payload(tmp_path, artifact_id="decomp-2", unit_id="u777"))
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "stale_grounding"
    assert report["sources"][0]["summary"]["current_candidate_units"] == 0
    assert report["findings"][0]["code"] == "stale_grounding"
    assert report["findings"][0]["counts_as_issue"] is True


def test_invalid_grounding_json_produces_state_and_finding(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report
    from science_tool.annotation.prose_grounding import prose_grounding_path

    _persist_decomposition(tmp_path, _artifact_payload(tmp_path))
    _write_manifest(tmp_path)
    path = prose_grounding_path(tmp_path, "example")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "invalid_grounding"
    assert report["findings"][0]["code"] == "invalid_grounding"
    assert report["findings"][0]["severity"] == "error"


def test_undeclared_grounding_report_is_finding_excluded_from_denominators(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    artifact, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path, slug="extra"))
    _write_grounding(tmp_path, artifact=artifact, status="grounded")
    _source(tmp_path, "example")
    _write_manifest(tmp_path, slug="example")

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["summary"]["declared_sources"] == 1
    assert report["summary"]["current_candidate_units"] == 0
    codes = [row["code"] for row in report["findings"]]
    assert codes == ["missing_decomposition", "undeclared_grounding_report"]
    undeclared = report["findings"][1]
    assert undeclared["source_ref"] == "prose-source:extra"
    assert undeclared["counts_as_issue"] is False


def test_fingerprint_join_survives_unit_renumber(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    first, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path, unit_id="u001"))
    _persist_decomposition(tmp_path, _artifact_payload(tmp_path, artifact_id="decomp-2", unit_id="u777"))
    latest = ProseDecompositionStore(tmp_path).load_latest("example")
    _write_grounding(tmp_path, artifact=latest, status="grounded")
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    candidate = report["units"][0]
    assert candidate["unit_id"] == "u777"
    assert candidate["fingerprint"] == first.units[0].fingerprint
    assert candidate["status"] == "grounded"


def test_non_complete_source_state_has_exactly_one_matching_finding(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    _persist_decomposition(tmp_path, _artifact_payload(tmp_path))
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    source = report["sources"][0]
    source_findings = [
        row for row in report["findings"] if row.get("source_ref") == source["source_ref"] and row.get("code") == source["state"]
    ]
    assert source["state"] == "missing_grounding"
    assert len(source_findings) == 1


def test_write_prose_health_report_skips_timestamp_only_rewrite(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report, prose_health_path, write_prose_health_report

    artifact, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path))
    _write_grounding(tmp_path, artifact=artifact, status="grounded")
    _write_manifest(tmp_path)
    first = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z")
    second = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:01:00Z")

    assert write_prose_health_report(tmp_path, first) is True
    path = prose_health_path(tmp_path)
    before = path.read_text(encoding="utf-8")
    assert write_prose_health_report(tmp_path, second) is False
    assert path.read_text(encoding="utf-8") == before
```

- [ ] **Step 2: Run tests to verify new failures**

Run:

```bash
cd science
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p4-state-red tests/test_prose_health.py
```

Expected: FAIL on `test_undeclared_grounding_report_is_finding_excluded_from_denominators` because undeclared report discovery is not implemented.

- [ ] **Step 3: Implement undeclared grounding report discovery and tighten findings**

Patch `science/src/science_tool/annotation/prose_health.py`:

```python
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
```

Also replace `_finding` so `path` is project-readable and severity is stable:

```python
def _finding(code: str, source: ManifestSource, message: str) -> dict[str, object]:
    return {
        "code": code,
        "severity": "error" if code in {"invalid_decomposition", "invalid_grounding"} else "warning",
        "counts_as_issue": True,
        "source_ref": source.source_ref,
        "path": source.path.as_posix(),
        "message": message,
    }
```

- [ ] **Step 4: Run source-state tests**

Run:

```bash
cd science
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p4-state-green tests/test_prose_health.py
```

Expected: PASS for all tests in `tests/test_prose_health.py`.

- [ ] **Step 5: Commit Task 2**

```bash
cd science
rtk git add src/science_tool/annotation/prose_health.py tests/test_prose_health.py
rtk git commit -m "feat(prose): complete prose health artifact states"
```

## Task 3: Annotate CLI Builder

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Modify: `science/tests/test_annotate_prose_decomposition_cli.py`

- [ ] **Step 1: Append failing CLI tests**

Append this content to `science/tests/test_annotate_prose_decomposition_cli.py`:

```python
def _write_prose_health_manifest(root: Path) -> Path:
    path = root / "data" / "prose-health" / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sources": [
                    {"source_ref": "prose-source:example", "path": "docs/example.md", "title": "Example"}
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_build_prose_health_cli_json_outputs_payload(tmp_path: Path) -> None:
    _ingest_and_mark_promoted(tmp_path)
    graph_path = _write_grounding_graph(tmp_path, supports=2)
    ground = CliRunner().invoke(
        annotate_group,
        [
            "ground-prose-decomposition",
            "--source",
            "prose-source:example",
            "--root",
            str(tmp_path),
            "--graph",
            str(graph_path),
            "--write",
        ],
    )
    assert ground.exit_code == 0, ground.output
    _write_prose_health_manifest(tmp_path)

    result = CliRunner().invoke(
        annotate_group,
        ["build-prose-health", "--root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"]["declared_sources"] == 1
    assert payload["summary"]["grounded_units"] == 1
    assert payload["coverage"]["strict_grounding"]["ratio"] == 1.0


def test_build_prose_health_cli_write_persists_artifact(tmp_path: Path) -> None:
    _ingest_and_mark_promoted(tmp_path)
    graph_path = _write_grounding_graph(tmp_path, supports=2)
    ground = CliRunner().invoke(
        annotate_group,
        [
            "ground-prose-decomposition",
            "--source",
            "prose-source:example",
            "--root",
            str(tmp_path),
            "--graph",
            str(graph_path),
            "--write",
        ],
    )
    assert ground.exit_code == 0, ground.output
    _write_prose_health_manifest(tmp_path)

    result = CliRunner().invoke(
        annotate_group,
        ["build-prose-health", "--root", str(tmp_path), "--write"],
    )

    assert result.exit_code == 0, result.output
    assert "built prose health" in result.output
    assert "wrote prose health artifact" in result.output
    path = tmp_path / "data" / "prose-health" / "prose-health.json"
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["summary"]["grounded_units"] == 1


def test_build_prose_health_cli_reports_manifest_errors(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        annotate_group,
        ["build-prose-health", "--root", str(tmp_path)],
    )

    assert result.exit_code != 0
    assert "prose health manifest is missing" in result.output
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
cd science
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p4-cli-red tests/test_annotate_prose_decomposition_cli.py -k build_prose_health
```

Expected: FAIL with `Error: No such command 'build-prose-health'`.

- [ ] **Step 3: Add CLI imports and summary keys**

Patch `science/src/science_tool/annotation/cli.py` imports:

```python
from science_tool.annotation.prose_health import (
    ProseHealthError,
    build_prose_health_report,
    write_prose_health_report,
)
```

Add this constant near `_GROUNDING_SUMMARY_KEYS`:

```python
_PROSE_HEALTH_SUMMARY_KEYS = (
    "declared_sources",
    "sources_with_decomposition",
    "sources_with_grounding",
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
```

- [ ] **Step 4: Add `build-prose-health` command**

Insert this command after `ground_prose_decomposition_cmd` and before `_required_prose_grounding_summary` in `science/src/science_tool/annotation/cli.py`:

```python
@annotate_group.command("build-prose-health")
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option(
    "--manifest",
    "manifest_path",
    default=Path("data/prose-health/manifest.json"),
    type=click.Path(dir_okay=False, path_type=Path),
)
@click.option("--write", "do_write", is_flag=True, default=False)
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def build_prose_health_cmd(
    root: Path | None,
    manifest_path: Path,
    do_write: bool,
    fmt: str,
) -> None:
    """Build the project-level prose epistemics health artifact."""
    project_root = (root or Path.cwd()).resolve()
    if not manifest_path.is_absolute():
        manifest_path = project_root / manifest_path
    try:
        report = build_prose_health_report(
            project_root,
            manifest_path=manifest_path,
            generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        )
        payload = report.to_json()
        written = write_prose_health_report(project_root, report) if do_write else False
    except ProseHealthError as exc:
        raise click.ClickException(str(exc)) from exc

    if fmt == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    summary = _required_prose_health_summary(payload)
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {}
    strict = coverage.get("strict_grounding") if isinstance(coverage, dict) else {}
    strict_ratio = strict.get("ratio") if isinstance(strict, dict) else None
    strict_text = "n/a" if strict_ratio is None else f"{strict_ratio:.1%}"
    click.echo(
        "built prose health: "
        f"sources={summary['declared_sources']} "
        f"candidates={summary['current_candidate_units']} "
        f"promoted={summary['promoted_units']} "
        f"grounded={summary['grounded_units']} "
        f"strict_grounding={strict_text} "
        f"findings={len(payload.get('findings') or [])}"
    )
    if do_write:
        click.echo("wrote prose health artifact" if written else "unchanged prose health artifact")
```

Add this helper after `_required_prose_grounding_summary`:

```python
def _required_prose_health_summary(payload: dict[str, object]) -> dict[str, object]:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise click.ClickException("prose health report summary must be an object")
    for key in _PROSE_HEALTH_SUMMARY_KEYS:
        if key not in summary:
            raise click.ClickException(f"missing prose health summary key: {key}")
    return summary
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
cd science
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p4-cli-green tests/test_annotate_prose_decomposition_cli.py -k build_prose_health
```

Expected: PASS for the three `build_prose_health` tests.

- [ ] **Step 6: Commit Task 3**

```bash
cd science
rtk git add src/science_tool/annotation/cli.py tests/test_annotate_prose_decomposition_cli.py
rtk git commit -m "feat(annotate): add prose health builder command"
```

## Task 4: Health Check Integration

**Files:**
- Modify: `science/src/science_tool/graph/health.py`
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/tests/test_health.py`

- [ ] **Step 1: Append failing health tests**

Append this content to `science/tests/test_health.py`:

```python
def _write_prose_health_artifact(root: Path, *, findings: list[dict] | None = None) -> Path:
    path = root / "data" / "prose-health" / "prose-health.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-06-18T14:00:00Z",
                "manifest_path": "data/prose-health/manifest.json",
                "summary": {
                    "declared_sources": 1,
                    "sources_with_decomposition": 1,
                    "sources_with_grounding": 1,
                    "current_candidate_units": 2,
                    "promoted_units": 1,
                    "grounded_units": 1,
                    "below_floor_units": 0,
                    "unbacked_units": 0,
                    "unpromoted_units": 1,
                    "skipped_units": 1,
                    "stale_units": 0,
                    "contested_units": 0,
                },
                "coverage": {
                    "promotion": {"numerator": 1, "denominator": 2, "ratio": 0.5},
                    "grounding": {"numerator": 1, "denominator": 1, "ratio": 1.0},
                    "strict_grounding": {"numerator": 1, "denominator": 2, "ratio": 0.5},
                },
                "sources": [
                    {
                        "source_ref": "prose-source:example",
                        "title": "Example",
                        "path": "docs/example.md",
                        "state": "complete",
                        "decomposition_artifact_id": "decomp-1",
                        "grounding_report_path": "data/prose-grounding/example/grounding.json",
                        "summary": {
                            "current_candidate_units": 2,
                            "promoted_units": 1,
                            "grounded_units": 1,
                            "below_floor_units": 0,
                            "unbacked_units": 0,
                            "unpromoted_units": 1,
                            "skipped_units": 1,
                            "stale_units": 0,
                            "contested_units": 0,
                        },
                    }
                ],
                "units": [],
                "findings": findings or [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def test_health_report_includes_prose_epistemics_artifact(tmp_path: Path) -> None:
    from science_tool.graph.health import build_health_report

    _write_prose_health_artifact(tmp_path)

    report = build_health_report(tmp_path, checks={"prose_epistemics"})

    assert report["prose_epistemics"]["summary"]["declared_sources"] == 1
    assert report["prose_epistemics"]["coverage"]["strict_grounding"]["ratio"] == 0.5
    assert report["prose_epistemics"]["findings"] == []
    assert report["total_issues"] == 0


def test_health_report_counts_prose_epistemics_findings_as_issues(tmp_path: Path) -> None:
    from science_tool.graph.health import build_health_report

    _write_prose_health_artifact(
        tmp_path,
        findings=[
            {
                "code": "missing_grounding",
                "severity": "warning",
                "counts_as_issue": True,
                "source_ref": "prose-source:example",
                "path": "docs/example.md",
                "message": "Declared prose source has no P3 grounding report.",
            },
            {
                "code": "undeclared_grounding_report",
                "severity": "warning",
                "counts_as_issue": False,
                "source_ref": "prose-source:extra",
                "path": "data/prose-grounding/extra/grounding.json",
                "message": "Extra report.",
            },
        ],
    )

    report = build_health_report(tmp_path, checks={"prose_epistemics"})

    assert len(report["prose_epistemics"]["findings"]) == 2
    assert report["total_issues"] == 1


def test_health_report_manifest_without_artifact_surfaces_rebuild_finding(tmp_path: Path) -> None:
    from science_tool.graph.health import build_health_report

    manifest = tmp_path / "data" / "prose-health" / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"schema_version": 1, "sources": []}), encoding="utf-8")

    report = build_health_report(tmp_path, checks={"prose_epistemics"})

    assert report["prose_epistemics"]["findings"][0]["code"] == "prose_health_artifact_missing"
    assert report["prose_epistemics"]["findings"][0]["counts_as_issue"] is True
    assert report["total_issues"] == 1


def test_health_report_invalid_manifest_surfaces_manifest_invalid(tmp_path: Path) -> None:
    from science_tool.graph.health import build_health_report

    manifest = tmp_path / "data" / "prose-health" / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("{not json", encoding="utf-8")

    report = build_health_report(tmp_path, checks={"prose_epistemics"})

    assert report["prose_epistemics"]["findings"][0]["code"] == "manifest_invalid"
    assert report["prose_epistemics"]["findings"][0]["counts_as_issue"] is True
    assert report["total_issues"] == 1


def test_health_report_no_manifest_no_artifact_is_not_applicable(tmp_path: Path) -> None:
    from science_tool.graph.health import build_health_report

    report = build_health_report(tmp_path, checks={"prose_epistemics"})

    assert report["prose_epistemics"]["applicable"] is False
    assert report["prose_epistemics"]["findings"] == []
    assert report["total_issues"] == 0


def test_health_cli_json_includes_prose_epistemics(tmp_path: Path) -> None:
    from click.testing import CliRunner
    from science_tool.cli import main

    _write_prose_health_artifact(tmp_path)

    result = CliRunner().invoke(
        main,
        ["health", "--project-root", str(tmp_path), "--format", "json", "--check", "prose_epistemics"],
    )

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["prose_epistemics"]["summary"]["grounded_units"] == 1


def test_health_list_checks_includes_prose_epistemics(tmp_path: Path) -> None:
    from click.testing import CliRunner
    from science_tool.cli import main

    result = CliRunner().invoke(
        main,
        ["health", "--project-root", str(tmp_path), "--format", "json", "--list-checks"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert any(row["name"] == "prose_epistemics" for row in payload["checks"])


def test_health_cli_table_includes_prose_epistemics_findings(tmp_path: Path) -> None:
    from click.testing import CliRunner
    from science_tool.cli import main

    _write_prose_health_artifact(
        tmp_path,
        findings=[
            {
                "code": "missing_grounding",
                "severity": "warning",
                "counts_as_issue": True,
                "source_ref": "prose-source:example",
                "path": "docs/example.md",
                "message": "Declared prose source has no P3 grounding report.",
            }
        ],
    )

    result = CliRunner().invoke(main, ["health", "--project-root", str(tmp_path), "--check", "prose_epistemics"])

    assert result.exit_code == 0, result.output
    assert "Prose Epistemics" in result.output
    assert "missing_grounding" in result.output
    assert "prose-source:example" in result.output
```

- [ ] **Step 2: Run health tests to verify they fail**

Run:

```bash
cd science
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p4-health-red tests/test_health.py -k prose_epistemics
```

Expected: FAIL with `unknown health check(s): prose_epistemics`.

- [ ] **Step 3: Add health data collection**

Patch `science/src/science_tool/graph/health.py`:

Extend `HealthReport`:

```python
class HealthReport(TypedDict):
    unresolved_refs: list[UnresolvedRef]
    unregistered_ref_kinds: list[UnregisteredRefKind]
    lingering_tags_lines: list[LingeringTagsRecord]
    agent_context: list[AgentContextFinding]
    identity_policy: list["IdentityPolicyFinding"]
    entity_identity: list[EntityIdentityFinding]
    layered_claims: "LayeredClaimHealthReport"
    legacy_task_type: list["LegacyTaskTypeFinding"]
    invalid_entity_aspects: list["InvalidEntityAspectsFinding"]
    legacy_structured_literature_prefixes: list["LegacyStructuredLiteraturePrefixFinding"]
    dataset_anomalies: list[dict]
    schema_invalid: list[SchemaInvalidFinding]
    archive_lag: TaskArchiveLag
    managed_artifacts: list[dict]
    tooling_scaffold: list[ToolingScaffoldFinding]
    validation: list[ValidationFinding]
    prose_epistemics: dict[str, object]
    total_issues: int
    _meta: NotRequired["HealthMeta"]
```

Add this function near `_collect_managed_artifacts`:

```python
def _empty_prose_epistemics() -> dict[str, object]:
    return {
        "applicable": False,
        "summary": {},
        "coverage": {},
        "sources": [],
        "findings": [],
    }


def _collect_prose_epistemics(context: HealthContext) -> dict[str, object]:
    from science_tool.annotation.prose_health import (
        ProseHealthError,
        load_prose_health_manifest,
        load_prose_health_artifact,
        prose_health_manifest_path,
        prose_health_path,
    )

    manifest_path = prose_health_manifest_path(context.project_root)
    artifact_path = prose_health_path(context.project_root)
    if not manifest_path.exists() and not artifact_path.exists():
        return _empty_prose_epistemics()
    if manifest_path.exists():
        try:
            load_prose_health_manifest(context.project_root)
        except ProseHealthError as exc:
            return {
                "applicable": True,
                "summary": {},
                "coverage": {},
                "sources": [],
                "findings": [
                    {
                        "code": "manifest_invalid",
                        "severity": "error",
                        "counts_as_issue": True,
                        "source_ref": None,
                        "path": manifest_path.relative_to(context.project_root).as_posix(),
                        "message": str(exc),
                    }
                ],
            }
    if not artifact_path.exists():
        return {
            "applicable": True,
            "summary": {},
            "coverage": {},
            "sources": [],
            "findings": [
                {
                    "code": "prose_health_artifact_missing",
                    "severity": "warning",
                    "counts_as_issue": True,
                    "source_ref": None,
                    "path": artifact_path.relative_to(context.project_root).as_posix(),
                    "message": "Prose health manifest exists but prose-health.json is missing; run science annotate build-prose-health --write.",
                }
            ],
        }
    try:
        artifact = load_prose_health_artifact(context.project_root)
    except ProseHealthError as exc:
        return {
            "applicable": True,
            "summary": {},
            "coverage": {},
            "sources": [],
            "findings": [
                {
                    "code": "prose_health_artifact_invalid",
                    "severity": "error",
                    "counts_as_issue": True,
                    "source_ref": None,
                    "path": artifact_path.relative_to(context.project_root).as_posix(),
                    "message": str(exc),
                }
            ],
        }
    return {
        "applicable": True,
        "summary": artifact.get("summary", {}),
        "coverage": artifact.get("coverage", {}),
        "sources": artifact.get("sources", []),
        "findings": artifact.get("findings", []),
    }
```

Update `_empty_check_results`:

```python
def _empty_check_results(project_root: Path) -> dict[str, object]:
    return {
        "identity_policy": [],
        "entity_identity": [],
        "layered_claim_migration": _empty_layered_claim_migration_report(project_root),
        "archive_lag": {"done_in_active": 0, "retired_in_active": 0, "missing_completed": 0},
        "managed_artifacts": [],
        "tooling_scaffold": [],
        "validate": [],
        "unresolved_refs": [],
        "unregistered_ref_kinds": [],
        "lingering_tags": [],
        "agent_context": [],
        "legacy_structured_literature_prefixes": [],
        "dataset_anomalies": [],
        "legacy_task_type": [],
        "invalid_entity_aspects": [],
        "prose_epistemics": _empty_prose_epistemics(),
    }
```

Inside `build_health_report`, after `validation = ...`, add:

```python
    prose_epistemics = cast("dict[str, object]", check_results["prose_epistemics"])
    prose_epistemics_findings = prose_epistemics.get("findings") if isinstance(prose_epistemics, dict) else []
    prose_epistemics_issue_count = (
        sum(1 for row in prose_epistemics_findings if isinstance(row, dict) and row.get("counts_as_issue") is True)
        if isinstance(prose_epistemics_findings, list)
        else 0
    )
```

Add `+ prose_epistemics_issue_count` to the `total_issues` expression.

Add `"prose_epistemics": prose_epistemics,` to the returned `report` dict.

Add this `HealthCheck` to `HEALTH_CHECKS` before `agent_context`:

```python
    HealthCheck(
        name="prose_epistemics",
        description="Read the project-level prose epistemics health artifact.",
        requires_sources=False,
        run=_collect_prose_epistemics,
    ),
```

- [ ] **Step 4: Add CLI table rendering**

Patch `science/src/science_tool/cli.py` in `health_command`:

After `validation = report.get("validation") or []`, add:

```python
    prose_epistemics = report.get("prose_epistemics") or {}
    prose_epistemics_findings = (
        prose_epistemics.get("findings") if isinstance(prose_epistemics, dict) else []
    ) or []
```

Add this to the `total_issues` expression:

```python
        + sum(1 for f in prose_epistemics_findings if isinstance(f, dict) and f.get("counts_as_issue"))
```

Before the `if report["unresolved_refs"]:` block, add:

```python
    if prose_epistemics_findings:
        pe_table = Table(title=f"Prose Epistemics ({len(prose_epistemics_findings)})")
        pe_table.add_column("Code", style="bold")
        pe_table.add_column("Source")
        pe_table.add_column("Detail")
        for row in prose_epistemics_findings:
            pe_table.add_row(
                str(row.get("code", "")),
                str(row.get("source_ref") or ""),
                str(row.get("message", "")),
            )
        console.print(pe_table)
        console.print("\n[bold]Next:[/bold] run [cyan]science annotate build-prose-health --write[/cyan].")
```

- [ ] **Step 5: Run health tests**

Run:

```bash
cd science
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p4-health-green tests/test_health.py -k prose_epistemics
```

Expected: PASS for all `prose_epistemics` tests.

- [ ] **Step 6: Commit Task 4**

```bash
cd science
rtk git add src/science_tool/graph/health.py src/science_tool/cli.py tests/test_health.py
rtk git commit -m "feat(health): surface prose epistemics artifact"
```

## Task 5: Final Validation and Documentation Reconciliation

**Files:**
- Modify: `science/src/science_tool/annotation/prose_health.py`
- Modify: `science/src/science_tool/annotation/cli.py`
- Modify: `science/src/science_tool/graph/health.py`
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/tests/test_prose_health.py`
- Modify: `science/tests/test_annotate_prose_decomposition_cli.py`
- Modify: `science/tests/test_health.py`

- [ ] **Step 1: Run focused P4 suite**

Run:

```bash
cd science
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p4-focused tests/test_prose_health.py tests/test_annotate_prose_decomposition_cli.py tests/test_health.py -k "prose_health or prose_epistemics or build_prose_health"
```

Expected: PASS.

- [ ] **Step 2: Run P2/P3 regression suite**

Run:

```bash
cd science
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p4-p2-p3-regression tests/test_prose_decomposition.py tests/test_internal_prose_adapter.py tests/test_prose_source_entity.py tests/test_prose_promote.py tests/test_prose_grounding.py tests/test_annotate_prose_decomposition_cli.py
```

Expected: PASS.

- [ ] **Step 3: Run health regression suite**

Run:

```bash
cd science
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p4-health-regression tests/test_health.py tests/test_health_managed_artifacts.py tests/test_acceptance_managed_artifacts.py tests/test_cli_color_policy.py
```

Expected: PASS.

- [ ] **Step 4: Run lint**

Run:

```bash
cd science
rtk uv run --frozen ruff check src/science_tool/annotation/prose_health.py src/science_tool/annotation/cli.py src/science_tool/graph/health.py src/science_tool/cli.py tests/test_prose_health.py tests/test_annotate_prose_decomposition_cli.py tests/test_health.py
```

Expected: `All checks passed!`

- [ ] **Step 5: Inspect generated public command help**

Run:

```bash
cd science
PYTHONPATH=src:model/src rtk uv run --frozen science annotate build-prose-health --help
```

Expected: includes `--manifest`, `--write`, `--format [table|json]`, and the command description `Build the project-level prose epistemics health artifact.`

- [ ] **Step 6: Commit final reconciliation**

If the previous steps required no code changes, skip this commit. If they required small fixes, commit them:

```bash
cd science
rtk git add src/science_tool/annotation/prose_health.py src/science_tool/annotation/cli.py src/science_tool/graph/health.py src/science_tool/cli.py tests/test_prose_health.py tests/test_annotate_prose_decomposition_cli.py tests/test_health.py
rtk git commit -m "fix(prose): reconcile prose health implementation"
```

Expected: commit created only if files changed.

## Final Review Checklist

- `data/prose-health/manifest.json` is the denominator authority.
- P4 reads both P2 and P3 and joins by `fingerprint`, not `unit_id`.
- `state` precedence is deterministic.
- Each non-`complete` declared source produces exactly one same-code source-level finding.
- `stale_grounding` counts as an issue.
- `undeclared_grounding_report` does not count as an issue and is excluded from denominators.
- Empty denominators produce `ratio: null`.
- `science health` reads P4 and never rebuilds it.
- The TS/downstream consumer contract is `data/prose-health/prose-health.json`, not P2/P3 internals.

## Final Verification Commands

Run these before requesting review or merging:

```bash
cd science
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p4-final-focused tests/test_prose_health.py tests/test_annotate_prose_decomposition_cli.py tests/test_health.py -k "prose_health or prose_epistemics or build_prose_health"
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p4-final-regression tests/test_prose_decomposition.py tests/test_internal_prose_adapter.py tests/test_prose_source_entity.py tests/test_prose_promote.py tests/test_prose_grounding.py tests/test_annotate_prose_decomposition_cli.py
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p4-final-health tests/test_health.py tests/test_health_managed_artifacts.py tests/test_acceptance_managed_artifacts.py tests/test_cli_color_policy.py
rtk uv run --frozen ruff check src/science_tool/annotation/prose_health.py src/science_tool/annotation/cli.py src/science_tool/graph/health.py src/science_tool/cli.py tests/test_prose_health.py tests/test_annotate_prose_decomposition_cli.py tests/test_health.py
```

Expected:

- Focused tests pass.
- P2/P3 regressions pass.
- Health regressions pass.
- Ruff prints `All checks passed!`.
