import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.annotation.prose_decomposition import compute_source_hash


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir(parents=True, exist_ok=True)
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


def test_ingest_hash_mismatch_can_be_allowed(tmp_path):
    path = _artifact_file(tmp_path, content_hash="sha256:" + "0" * 64)
    result = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(path), "--root", str(tmp_path), "--allow-changed"],
    )
    assert result.exit_code == 0, result.output
