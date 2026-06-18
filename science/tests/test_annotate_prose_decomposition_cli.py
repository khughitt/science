import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.annotation.prose_decomposition import compute_source_hash


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        source.write_text("# Section\n\nBasalt flows record the cooling history.\n", encoding="utf-8")
    return source


def _artifact_file(tmp_path: Path, *, artifact_id="decomp-1", content_hash=None) -> Path:
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
                    "exact": "Basalt flows record the cooling history.",
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
    assert payload["units"][0]["unit_id"] == "u001"
    assert payload["units"][0]["status"] == "candidate"
    assert payload["units"][0]["locator_status"] == "resolved"


def test_check_reports_ambiguous_heading_path(tmp_path):
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
    assert payload["units"][0]["locator_status"] == "ambiguous"
