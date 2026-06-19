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


def test_manifest_validation_rejects_absolute_manifest_path_outside_project(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import ProseHealthError, load_prose_health_manifest

    outside = tmp_path.parent / "outside-prose-health-manifest.json"
    outside.write_text(
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

    with pytest.raises(ProseHealthError, match="manifest path must stay under project root"):
        load_prose_health_manifest(tmp_path, outside)


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


def test_malformed_grounding_unit_row_degrades_source_to_invalid_grounding(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    artifact, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path))
    grounding_path = _write_grounding(tmp_path, artifact=artifact, status="grounded")
    report = json.loads(grounding_path.read_text(encoding="utf-8"))
    report["units"].append("not a row")
    grounding_path.write_text(json.dumps(report), encoding="utf-8")
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "invalid_grounding"
    assert report["units"] == []
    assert report["findings"][0]["code"] == "invalid_grounding"
    assert "grounding report unit[2] must be an object" in report["findings"][0]["message"]


def test_duplicate_grounding_fingerprint_degrades_source_to_invalid_grounding(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    artifact, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path))
    grounding_path = _write_grounding(tmp_path, artifact=artifact, status="grounded")
    report = json.loads(grounding_path.read_text(encoding="utf-8"))
    report["units"].append(dict(report["units"][0]))
    grounding_path.write_text(json.dumps(report), encoding="utf-8")
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "invalid_grounding"
    assert report["units"] == []
    assert report["findings"][0]["code"] == "invalid_grounding"
    assert "duplicate grounding report unit fingerprint" in report["findings"][0]["message"]


def test_grounding_schema_version_mismatch_degrades_source_to_invalid_grounding(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    artifact, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path))
    grounding_path = _write_grounding(tmp_path, artifact=artifact, status="grounded")
    report = json.loads(grounding_path.read_text(encoding="utf-8"))
    report["schema_version"] = 2
    grounding_path.write_text(json.dumps(report), encoding="utf-8")
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "invalid_grounding"
    assert report["units"] == []
    assert report["findings"][0]["code"] == "invalid_grounding"
    assert "grounding report schema_version must be 1" in report["findings"][0]["message"]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("unit_id", "other-unit", "grounding report unit_id mismatch"),
        (
            "artifact_ref",
            "annotation:data/prose-decompositions/example/generations/decomp-1.json#other-unit",
            "grounding report artifact_ref mismatch",
        ),
        ("disposition", "skip", "grounding report disposition mismatch"),
    ],
)
def test_grounding_identity_mismatch_degrades_source_to_invalid_grounding(
    tmp_path: Path, field: str, value: str, message: str
) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    artifact, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path))
    grounding_path = _write_grounding(tmp_path, artifact=artifact, status="grounded")
    report = json.loads(grounding_path.read_text(encoding="utf-8"))
    report["units"][0][field] = value
    grounding_path.write_text(json.dumps(report), encoding="utf-8")
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "invalid_grounding"
    assert report["units"] == []
    assert report["findings"][0]["code"] == "invalid_grounding"
    assert message in report["findings"][0]["message"]


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
            "path": "docs/example.md",
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
    assert report["summary"]["current_candidate_units"] == 1
    assert report["summary"]["skipped_units"] == 1
    assert report["summary"]["unpromoted_units"] == 1
    assert report["findings"][0]["code"] == "missing_grounding"
    assert report["findings"][0]["counts_as_issue"] is True


def test_missing_grounding_counts_p2_promotions_in_denominator(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    artifact, store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path))
    store.record_promotion("example", artifact.units[0].fingerprint, "proposition:basalt-cooling")
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "missing_grounding"
    assert report["summary"]["current_candidate_units"] == 1
    assert report["summary"]["promoted_units"] == 1
    assert report["summary"]["grounded_units"] == 0
    assert report["summary"]["unpromoted_units"] == 0
    assert report["coverage"]["grounding"] == {"numerator": 0, "denominator": 1, "ratio": 0.0}
    assert report["coverage"]["strict_grounding"] == {"numerator": 0, "denominator": 1, "ratio": 0.0}


def test_stale_grounding_uses_precedence_and_counts_as_issue(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    first, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path, artifact_id="decomp-1"))
    _write_grounding(tmp_path, artifact=first, status="grounded")
    _persist_decomposition(tmp_path, _artifact_payload(tmp_path, artifact_id="decomp-2", unit_id="u777"))
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "stale_grounding"
    assert report["sources"][0]["summary"]["current_candidate_units"] == 1
    assert report["summary"]["current_candidate_units"] == 1
    assert report["summary"]["sources_with_grounding"] == 1
    assert report["findings"][0]["code"] == "stale_grounding"
    assert report["findings"][0]["counts_as_issue"] is True


def test_stale_grounding_with_invalid_unit_structure_is_invalid_grounding(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    first, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path, artifact_id="decomp-1"))
    grounding_path = _write_grounding(tmp_path, artifact=first, status="grounded")
    _persist_decomposition(tmp_path, _artifact_payload(tmp_path, artifact_id="decomp-2", unit_id="u777"))
    report = json.loads(grounding_path.read_text(encoding="utf-8"))
    report["units"].append(dict(report["units"][0]))
    grounding_path.write_text(json.dumps(report), encoding="utf-8")
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "invalid_grounding"
    assert report["summary"]["sources_with_grounding"] == 0
    assert report["findings"][0]["code"] == "invalid_grounding"
    assert "duplicate grounding report unit fingerprint" in report["findings"][0]["message"]


def test_invalid_grounding_precedes_stale_grounding(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report
    from science_tool.annotation.prose_grounding import prose_grounding_path

    first, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path, artifact_id="decomp-1"))
    _write_grounding(tmp_path, artifact=first, status="grounded")
    _persist_decomposition(tmp_path, _artifact_payload(tmp_path, artifact_id="decomp-2", unit_id="u777"))
    path = prose_grounding_path(tmp_path, "example")
    report = json.loads(path.read_text(encoding="utf-8"))
    report["source_ref"] = "prose-source:other"
    path.write_text(json.dumps(report), encoding="utf-8")
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "invalid_grounding"
    assert report["findings"][0]["code"] == "invalid_grounding"


def test_missing_grounding_artifact_id_is_invalid_not_stale(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    first, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path, artifact_id="decomp-1"))
    grounding_path = _write_grounding(tmp_path, artifact=first, status="grounded")
    _persist_decomposition(tmp_path, _artifact_payload(tmp_path, artifact_id="decomp-2", unit_id="u777"))
    report = json.loads(grounding_path.read_text(encoding="utf-8"))
    del report["decomposition_artifact_id"]
    grounding_path.write_text(json.dumps(report), encoding="utf-8")
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "invalid_grounding"
    assert report["findings"][0]["code"] == "invalid_grounding"
    assert "decomposition_artifact_id must be a non-empty string" in report["findings"][0]["message"]


def test_invalid_grounding_status_degrades_source_to_invalid_grounding(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    artifact, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path))
    grounding_path = _write_grounding(tmp_path, artifact=artifact, status="grounded")
    report = json.loads(grounding_path.read_text(encoding="utf-8"))
    report["units"][0]["status"] = "mystery"
    grounding_path.write_text(json.dumps(report), encoding="utf-8")
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "invalid_grounding"
    assert report["findings"][0]["code"] == "invalid_grounding"
    assert "status is invalid" in report["findings"][0]["message"]


def test_current_candidate_status_stale_is_invalid_grounding(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    artifact, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path))
    grounding_path = _write_grounding(tmp_path, artifact=artifact, status="grounded")
    report = json.loads(grounding_path.read_text(encoding="utf-8"))
    report["units"][0]["status"] = "stale"
    grounding_path.write_text(json.dumps(report), encoding="utf-8")
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "invalid_grounding"
    assert report["findings"][0]["code"] == "invalid_grounding"
    assert "status mismatch for candidate fingerprint" in report["findings"][0]["message"]


def test_skip_status_grounded_is_invalid_grounding(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    artifact, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path))
    grounding_path = _write_grounding(tmp_path, artifact=artifact, status="grounded")
    report = json.loads(grounding_path.read_text(encoding="utf-8"))
    report["units"][1]["status"] = "grounded"
    grounding_path.write_text(json.dumps(report), encoding="utf-8")
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "invalid_grounding"
    assert report["findings"][0]["code"] == "invalid_grounding"
    assert "status mismatch for skip fingerprint" in report["findings"][0]["message"]


def test_extra_non_stale_grounding_row_is_invalid_grounding(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    artifact, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path))
    grounding_path = _write_grounding(tmp_path, artifact=artifact, status="grounded")
    report = json.loads(grounding_path.read_text(encoding="utf-8"))
    extra = dict(report["units"][0])
    extra["fingerprint"] = "sha256:extra"
    extra["unit_id"] = "old"
    report["units"].append(extra)
    grounding_path.write_text(json.dumps(report), encoding="utf-8")
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "invalid_grounding"
    assert report["findings"][0]["code"] == "invalid_grounding"
    assert "non-stale extra unit fingerprint" in report["findings"][0]["message"]


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


def test_invalid_grounding_json_under_missing_slug_is_not_misclassified(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report
    from science_tool.annotation.prose_grounding import prose_grounding_path

    _persist_decomposition(tmp_path, _artifact_payload(tmp_path, slug="missing-data"))
    _write_manifest(tmp_path, slug="missing-data")
    path = prose_grounding_path(tmp_path, "missing-data")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "invalid_grounding"
    assert report["findings"][0]["code"] == "invalid_grounding"


def test_grounding_fingerprint_mismatch_degrades_one_source_to_invalid_grounding(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report
    from science_tool.annotation.prose_grounding import prose_grounding_path

    artifact, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path))
    _write_grounding(tmp_path, artifact=artifact, status="grounded")
    path = prose_grounding_path(tmp_path, "example")
    report = json.loads(path.read_text(encoding="utf-8"))
    report["units"][0]["fingerprint"] = "sha256:missing"
    path.write_text(json.dumps(report), encoding="utf-8")
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "invalid_grounding"
    assert report["sources"][0]["summary"]["current_candidate_units"] == 1
    assert report["units"] == []
    assert report["findings"][0]["code"] == "invalid_grounding"
    assert "missing unit fingerprint" in report["findings"][0]["message"]


def test_invalid_decomposition_finding_message_uses_relative_paths(tmp_path: Path) -> None:
    from science_tool.annotation.prose_health import build_prose_health_report

    artifact, _store = _persist_decomposition(tmp_path, _artifact_payload(tmp_path))
    generation = tmp_path / "data" / "prose-decompositions" / "example" / "generations" / f"{artifact.artifact.artifact_id}.json"
    generation.unlink()
    _write_manifest(tmp_path)

    report = build_prose_health_report(tmp_path, generated_at="2026-06-18T14:00:00Z").to_json()

    assert report["sources"][0]["state"] == "invalid_decomposition"
    assert str(tmp_path) not in report["findings"][0]["message"]
    assert "data/prose-decompositions/example/generations/decomp-1.json" in report["findings"][0]["message"]


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
