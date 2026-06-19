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
