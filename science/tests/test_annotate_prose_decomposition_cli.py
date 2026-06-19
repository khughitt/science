import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import Dataset, Literal, RDF

import science_tool.annotation.cli as annotation_cli
from science_tool.annotation.cli import annotate_group
from science_tool.annotation.prose_decomposition import ProseDecompositionStore, compute_source_hash
from science_tool.annotation.prose_validation import ProseValidationReport
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS
from science_tool.graph.store import _graph_uri


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        source.write_text("# Section\n\nBasalt flows record the cooling history.\n", encoding="utf-8")
    return source


def _artifact_file(
    tmp_path: Path,
    *,
    artifact_id="decomp-1",
    content_hash=None,
    quote="Basalt flows record the cooling history.",
) -> Path:
    source = _source(tmp_path)
    payload = {
        "schema_version": 1,
        "source": {
            "kind": "prose-source",
            "slug": "example",
            "path": str(source),
            "title": "Example",
            "content_hash": content_hash or compute_source_hash(source),
        },
        "artifact": {"id": artifact_id, "generated_at": "2026-06-18T12:00:00Z", "producer": "offline-agent"},
        "units": [
            {
                "unit_id": "u001",
                "disposition": "candidate",
                "locator": {"regime": "markdown-heading-path", "value": ["Section"]},
                "payload": {
                    "type": "proposition",
                    "exact": quote,
                    "prefix": "",
                    "suffix": "",
                    "stance": "asserted",
                },
            }
        ],
    }
    path = tmp_path / f"{artifact_id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_grounding_graph(root: Path, *, supports: int) -> Path:
    dataset = Dataset()
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    target = PROJECT_NS["proposition/basalt-cooling"]
    knowledge.add((target, RDF.type, SCI_NS.Proposition))
    for index in range(supports):
        evidence_line = PROJECT_NS[f"evidence-line/basalt-cooling-{index + 1}"]
        knowledge.add((evidence_line, RDF.type, SCI_NS.EvidenceLine))
        knowledge.add((evidence_line, CITO_NS.supports, target))
        provenance.add((evidence_line, SCI_NS.evidenceStrength, Literal("strong")))
        provenance.add((evidence_line, SCI_NS.evidenceIndependence, Literal("independent")))
        provenance.add((evidence_line, SCI_NS.independenceGroup, Literal(f"g{index + 1}")))
        provenance.add((evidence_line, SCI_NS.evidenceRole, Literal("proxy")))
        provenance.add((evidence_line, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
    graph_path = root / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.serialize(destination=str(graph_path), format="trig")
    return graph_path


def _ingest_and_mark_promoted(root: Path) -> None:
    result = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(_artifact_file(root)), "--root", str(root)],
    )
    assert result.exit_code == 0, result.output
    artifact = ProseDecompositionStore(root).load_latest("example")
    ProseDecompositionStore(root).record_promotion(
        source_slug="example",
        fingerprint=artifact.units[0].fingerprint,
        promoted_to="proposition:basalt-cooling",
    )


def test_ingest_creates_source_entity_and_artifact(tmp_path):
    path = _artifact_file(tmp_path)
    result = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(path), "--root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["source_ref"] == "prose-source:example"
    assert payload["artifact_id"] == "decomp-1"
    assert payload["stale"] == []
    assert payload["source_entity_created"] is True
    assert (tmp_path / "entities" / "prose-sources" / "example.md").exists()
    assert (tmp_path / "data" / "prose-decompositions" / "example" / "index.json").exists()


def test_ingest_hash_mismatch_fails_without_allow_changed(tmp_path):
    path = _artifact_file(tmp_path, content_hash="sha256:" + "0" * 64)
    result = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(path), "--root", str(tmp_path)],
    )
    assert result.exit_code != 0
    assert "content hash mismatch" in result.output
    assert not (tmp_path / "entities" / "prose-sources" / "example.md").exists()
    assert not (tmp_path / "data" / "prose-decompositions" / "example" / "index.json").exists()


def test_ingest_hash_mismatch_can_be_allowed(tmp_path):
    artifact_hash = "sha256:" + "0" * 64
    path = _artifact_file(tmp_path, content_hash=artifact_hash)
    result = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(path), "--root", str(tmp_path), "--allow-changed"],
    )
    assert result.exit_code == 0, result.output
    generation = tmp_path / "data" / "prose-decompositions" / "example" / "generations" / "decomp-1.json"
    stored = json.loads(generation.read_text(encoding="utf-8"))
    assert stored["source"]["content_hash"] == artifact_hash


def test_check_reports_candidate(tmp_path):
    ingest = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(_artifact_file(tmp_path)), "--root", str(tmp_path)],
    )
    assert ingest.exit_code == 0, ingest.output
    result = CliRunner().invoke(
        annotate_group,
        ["check-prose-decomposition", "--source", "prose-source:example", "--root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["source_ref"] == "prose-source:example"
    assert set(payload["units"][0]) == {
        "unit_id",
        "disposition",
        "status",
        "fingerprint",
        "locator_status",
        "message",
        "promoted_to",
        "stale",
    }
    assert payload["units"][0]["unit_id"] == "u001"
    assert payload["units"][0]["disposition"] == "candidate"
    assert payload["units"][0]["status"] == "candidate"
    assert payload["units"][0]["locator_status"] == "resolved"
    assert payload["units"][0]["promoted_to"] is None
    assert payload["units"][0]["stale"] is False


def test_check_reports_unresolved_when_repeated_heading_lacks_quote(tmp_path):
    source = _source(tmp_path)
    source.write_text("# A\n\n## Repeat\n\nOne.\n\n# B\n\n## Repeat\n\nTwo.\n", encoding="utf-8")
    path = _artifact_file(tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["source"]["content_hash"] = compute_source_hash(source)
    raw["units"][0]["locator"]["value"] = ["Repeat"]
    path.write_text(json.dumps(raw), encoding="utf-8")
    ingest = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(path), "--root", str(tmp_path)],
    )
    assert ingest.exit_code == 0, ingest.output
    result = CliRunner().invoke(
        annotate_group,
        ["check-prose-decomposition", "--source", "prose-source:example", "--root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["units"][0]["locator_status"] == "unresolved"
    assert "quote not found" in payload["units"][0]["message"]


def test_check_reports_stale_prior_units(tmp_path):
    source = _source(tmp_path)
    source.write_text(
        "# Section\n\n"
        "Basalt flows record the cooling history.\n\n"
        "Ash layers date the eruption sequence.\n",
        encoding="utf-8",
    )
    first = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(_artifact_file(tmp_path)), "--root", str(tmp_path)],
    )
    assert first.exit_code == 0, first.output
    second = CliRunner().invoke(
        annotate_group,
        [
            "ingest-prose-decomposition",
            str(_artifact_file(tmp_path, artifact_id="decomp-2", quote="Ash layers date the eruption sequence.")),
            "--root",
            str(tmp_path),
        ],
    )
    assert second.exit_code == 0, second.output

    result = CliRunner().invoke(
        annotate_group,
        ["check-prose-decomposition", "--source", "prose-source:example", "--root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload["units"]) == 2
    assert payload["units"][0]["status"] == "candidate"
    stale = payload["units"][1]
    assert stale["unit_id"] == "u001"
    assert stale["disposition"] == "candidate"
    assert stale["status"] == "stale"
    assert stale["locator_status"] == "stale"
    assert stale["message"] == "unit is stale in latest decomposition"
    assert stale["promoted_to"] is None
    assert stale["stale"] is True


def test_check_reports_skip_unit(tmp_path):
    path = _artifact_file(tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["units"][0] = {
        "unit_id": "s001",
        "disposition": "skip",
        "reason": {"code": "not_a_claim", "detail": "Background context."},
        "locator": {
            "regime": "markdown-heading-path-with-quote",
            "value": ["Section"],
            "quote": {
                "exact": "Basalt flows record the cooling history.",
                "prefix": "",
                "suffix": "",
            },
        },
    }
    path.write_text(json.dumps(raw), encoding="utf-8")
    ingest = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(path), "--root", str(tmp_path)],
    )
    assert ingest.exit_code == 0, ingest.output
    result = CliRunner().invoke(
        annotate_group,
        ["check-prose-decomposition", "--source", "prose-source:example", "--root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["units"][0]["disposition"] == "skip"
    assert payload["units"][0]["status"] == "skip"
    assert payload["units"][0]["locator_status"] == "resolved"


def test_check_reports_promoted_target(tmp_path):
    ingest = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(_artifact_file(tmp_path)), "--root", str(tmp_path)],
    )
    assert ingest.exit_code == 0, ingest.output
    index = ProseDecompositionStore(tmp_path).load_index("example")
    fingerprint = next(iter(index["units"]))
    ProseDecompositionStore(tmp_path).record_promotion(
        source_slug="example",
        fingerprint=fingerprint,
        promoted_to="proposition:basalt-cooling",
    )
    result = CliRunner().invoke(
        annotate_group,
        ["check-prose-decomposition", "--source", "prose-source:example", "--root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["units"][0]["promoted_to"] == "proposition:basalt-cooling"


@pytest.mark.parametrize(
    ("source_ref", "message"),
    [
        ("paper:x", "--source must use prose-source:<slug>"),
        ("prose-source:", "source slug"),
        ("prose-source:BadSlug", "source slug"),
    ],
)
def test_check_rejects_invalid_source_ref(tmp_path, source_ref, message):
    result = CliRunner().invoke(
        annotate_group,
        ["check-prose-decomposition", "--source", source_ref, "--root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code != 0
    assert message in result.output


def test_validate_prose_decomposition_artifact_reports_units_before_ingest(tmp_path):
    artifact_path = _artifact_file(tmp_path)

    result = CliRunner().invoke(
        annotate_group,
        [
            "validate-prose-decomposition-artifact",
            str(artifact_path),
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["source_ref"] == "prose-source:example"
    assert payload["artifact_id"] == "decomp-1"
    assert payload["summary"] == {
        "units": 1,
        "resolved": 1,
        "unresolved": 0,
        "ambiguous": 0,
        "stale": 0,
        "hard_failures": 0,
    }
    assert payload["units"][0]["unit_id"] == "u001"
    assert payload["units"][0]["locator_status"] == "resolved"
    assert payload["units"][0]["promoted_to"] is None
    assert payload["units"][0]["stale"] is False
    assert not (tmp_path / "entities" / "prose-sources" / "example.md").exists()
    assert not (
        tmp_path / "data" / "prose-decompositions" / "example" / "generations" / "decomp-1.json"
    ).exists()
    assert not (tmp_path / "data" / "prose-decompositions" / "example" / "index.json").exists()


def test_validate_prose_decomposition_artifact_accepts_relative_source_path_under_root(tmp_path):
    artifact_path = _artifact_file(tmp_path)
    raw = json.loads(artifact_path.read_text(encoding="utf-8"))
    raw["source"]["path"] = "docs/example.md"
    artifact_path.write_text(json.dumps(raw), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "validate-prose-decomposition-artifact",
            str(artifact_path),
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["source_ref"] == "prose-source:example"
    assert payload["summary"]["resolved"] == 1
    assert payload["units"][0]["locator_status"] == "resolved"
    assert not (tmp_path / "entities" / "prose-sources" / "example.md").exists()


def test_validate_prose_decomposition_artifact_hash_mismatch_fails(tmp_path):
    artifact_path = _artifact_file(tmp_path, content_hash="sha256:" + "0" * 64)

    result = CliRunner().invoke(
        annotate_group,
        [
            "validate-prose-decomposition-artifact",
            str(artifact_path),
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code != 0
    assert "content hash mismatch" in result.output
    assert not (tmp_path / "entities" / "prose-sources" / "example.md").exists()


def test_validate_prose_decomposition_artifact_rejects_source_outside_root(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside_source = tmp_path / "outside.md"
    outside_source.write_text("# Section\n\nBasalt flows record the cooling history.\n", encoding="utf-8")
    artifact_path = _artifact_file(root, content_hash=compute_source_hash(outside_source))
    raw = json.loads(artifact_path.read_text(encoding="utf-8"))
    raw["source"]["path"] = str(outside_source)
    artifact_path.write_text(json.dumps(raw), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "validate-prose-decomposition-artifact",
            str(artifact_path),
            "--root",
            str(root),
        ],
    )

    assert result.exit_code != 0
    assert "source path is outside project root" in result.output
    assert str(outside_source) in result.output
    assert "content hash mismatch" not in result.output


def test_validate_prose_decomposition_artifact_missing_source_fails_without_traceback(tmp_path):
    artifact_path = _artifact_file(tmp_path)
    raw = json.loads(artifact_path.read_text(encoding="utf-8"))
    missing_source = tmp_path / "docs" / "missing.md"
    raw["source"]["path"] = str(missing_source)
    artifact_path.write_text(json.dumps(raw), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "validate-prose-decomposition-artifact",
            str(artifact_path),
            "--root",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "could not read source for hash" in result.output
    assert str(missing_source) in result.output
    assert "Traceback" not in result.output


def test_prose_validation_report_summary_counts_stale_separately_from_hard_failures():
    report = ProseValidationReport(
        source_ref="prose-source:example",
        artifact_id="decomp-1",
        rows=[
            {
                "unit_id": "u001",
                "disposition": "candidate",
                "status": "stale",
                "fingerprint": "fp-stale",
                "locator_status": "stale",
                "message": "unit is stale in latest decomposition",
                "promoted_to": None,
                "stale": True,
            },
            {
                "unit_id": "u002",
                "disposition": "candidate",
                "status": "candidate",
                "fingerprint": "fp-hard-failure",
                "locator_status": "invalid",
                "message": "unexpected locator state",
                "promoted_to": None,
                "stale": False,
            },
        ],
    )

    summary = report.to_json()["summary"]
    assert isinstance(summary, dict)
    assert summary["stale"] == 1
    assert summary["hard_failures"] == 1


def test_validate_and_check_share_per_unit_findings_after_ingest(tmp_path):
    artifact_path = _artifact_file(tmp_path)
    validate = CliRunner().invoke(
        annotate_group,
        [
            "validate-prose-decomposition-artifact",
            str(artifact_path),
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )
    assert validate.exit_code == 0, validate.output

    ingest = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(artifact_path), "--root", str(tmp_path)],
    )
    assert ingest.exit_code == 0, ingest.output

    check = CliRunner().invoke(
        annotate_group,
        [
            "check-prose-decomposition",
            "--source",
            "prose-source:example",
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )
    assert check.exit_code == 0, check.output

    validate_payload = json.loads(validate.output)
    check_payload = json.loads(check.output)
    # Fresh ingest has no stale/promoted state, so raw-artifact validation and
    # latest-artifact check should produce identical per-unit findings.
    assert validate_payload["units"] == check_payload["units"]


def test_check_prose_decomposition_reports_unreadable_latest_generation(tmp_path):
    ingest = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(_artifact_file(tmp_path)), "--root", str(tmp_path)],
    )
    assert ingest.exit_code == 0, ingest.output
    generation = tmp_path / "data" / "prose-decompositions" / "example" / "generations" / "decomp-1.json"
    generation.unlink()
    generation.mkdir()

    result = CliRunner().invoke(
        annotate_group,
        ["check-prose-decomposition", "--source", "prose-source:example", "--root", str(tmp_path)],
    )

    assert result.exit_code != 0
    assert "could not read latest prose decomposition for source slug example" in result.output
    assert str(generation) in result.output
    assert "Traceback" not in result.output


def test_check_prose_decomposition_reports_unreadable_index(tmp_path):
    ingest = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(_artifact_file(tmp_path)), "--root", str(tmp_path)],
    )
    assert ingest.exit_code == 0, ingest.output
    index_path = tmp_path / "data" / "prose-decompositions" / "example" / "index.json"
    index_path.unlink()
    index_path.mkdir()

    result = CliRunner().invoke(
        annotate_group,
        ["check-prose-decomposition", "--source", "prose-source:example", "--root", str(tmp_path)],
    )

    assert result.exit_code != 0
    assert "could not read prose decomposition index for source slug example" in result.output
    assert str(index_path) in result.output
    assert "Traceback" not in result.output


def test_promote_prose_decomposition_apply_mints(tmp_path):
    ingest = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(_artifact_file(tmp_path)), "--root", str(tmp_path)],
    )
    assert ingest.exit_code == 0, ingest.output
    result = CliRunner().invoke(
        annotate_group,
        [
            "promote-prose-decomposition",
            "--source",
            "prose-source:example",
            "--unit",
            "u001",
            "--root",
            str(tmp_path),
            "--apply",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["minted"] == 1
    assert (tmp_path / "entities" / "propositions" / "basalt-flows-record-the-cooling-history.md").exists()


def test_promote_prose_decomposition_rejects_unresolved_locator(tmp_path):
    path = _artifact_file(tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["units"][0]["payload"]["exact"] = "Not present."
    path.write_text(json.dumps(raw), encoding="utf-8")
    ingest = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(path), "--root", str(tmp_path)],
    )
    assert ingest.exit_code == 0, ingest.output
    result = CliRunner().invoke(
        annotate_group,
        [
            "promote-prose-decomposition",
            "--source",
            "prose-source:example",
            "--unit",
            "u001",
            "--root",
            str(tmp_path),
            "--apply",
        ],
    )
    assert result.exit_code != 0
    assert "locator" in result.output


def test_ground_prose_decomposition_json_output(tmp_path):
    _ingest_and_mark_promoted(tmp_path)
    graph_path = _write_grounding_graph(tmp_path, supports=2)

    result = CliRunner().invoke(
        annotate_group,
        [
            "ground-prose-decomposition",
            "--source",
            "prose-source:example",
            "--root",
            str(tmp_path),
            "--graph",
            str(graph_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["source_ref"] == "prose-source:example"
    assert payload["summary"]["grounded_units"] == 1
    assert payload["units"][0]["status"] == "grounded"


def test_ground_prose_decomposition_resolves_relative_graph_under_root(tmp_path):
    _ingest_and_mark_promoted(tmp_path)
    _write_grounding_graph(tmp_path, supports=2)

    result = CliRunner().invoke(
        annotate_group,
        [
            "ground-prose-decomposition",
            "--source",
            "prose-source:example",
            "--root",
            str(tmp_path),
            "--graph",
            "knowledge/graph.trig",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["graph_path"] == "knowledge/graph.trig"
    assert payload["summary"]["grounded_units"] == 1


def test_ground_prose_decomposition_write_persists_artifact(tmp_path):
    _ingest_and_mark_promoted(tmp_path)
    graph_path = _write_grounding_graph(tmp_path, supports=2)

    result = CliRunner().invoke(
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

    assert result.exit_code == 0, result.output
    path = tmp_path / "data" / "prose-grounding" / "example" / "grounding.json"
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["summary"]["grounded_units"] == 1
    assert "wrote prose grounding" in result.output


def test_ground_prose_decomposition_table_requires_summary_keys(tmp_path, monkeypatch):
    _write_grounding_graph(tmp_path, supports=0)

    class Report:
        def to_json(self):
            return {
                "source_ref": "prose-source:example",
                "summary": {
                    "below_floor_units": 0,
                    "unbacked_units": 0,
                    "unpromoted_units": 0,
                    "skipped_units": 0,
                    "stale_units": 0,
                },
                "units": [],
            }

    monkeypatch.setattr(annotation_cli, "build_prose_grounding_report", lambda *args, **kwargs: Report())

    result = CliRunner().invoke(
        annotate_group,
        [
            "ground-prose-decomposition",
            "--source",
            "prose-source:example",
            "--root",
            str(tmp_path),
            "--graph",
            "knowledge/graph.trig",
        ],
    )

    assert result.exit_code != 0
    assert "missing prose grounding summary key: grounded_units" in result.output


def test_ground_prose_decomposition_rejects_bad_source_ref(tmp_path):
    result = CliRunner().invoke(
        annotate_group,
        ["ground-prose-decomposition", "--source", "paper:x", "--root", str(tmp_path)],
    )

    assert result.exit_code != 0
    assert "--source must use prose-source:<slug>" in result.output


def test_ground_prose_decomposition_missing_graph_fails(tmp_path):
    _ingest_and_mark_promoted(tmp_path)

    result = CliRunner().invoke(
        annotate_group,
        [
            "ground-prose-decomposition",
            "--source",
            "prose-source:example",
            "--root",
            str(tmp_path),
            "--graph",
            str(tmp_path / "knowledge" / "missing.trig"),
        ],
    )

    assert result.exit_code != 0
    assert "graph file is missing" in result.output


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
