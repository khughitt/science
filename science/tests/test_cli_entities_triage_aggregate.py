from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main

_MANIFEST = "name: demo-project\nprofile: research\nprofiles: {local: local}\n"


def _write_project(root: Path) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    agg = root / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    entries = [
        {
            "canonical_id": "concept:coined",
            "kind": "concept",
            "title": "Coined",
            "source_path": "knowledge/sources/local/entities.yaml",
        },
        # `article:lit` is canonicalized to `paper:lit` at load (kind stays "article").
        {
            "canonical_id": "article:lit",
            "kind": "article",
            "title": "Lit",
            "source_path": "knowledge/sources/local/entities.yaml",
        },
    ]
    (agg / "entities.yaml").write_text(yaml.safe_dump({"entities": entries}), encoding="utf-8")


def test_triage_aggregate_json(tmp_path: Path) -> None:
    _write_project(tmp_path)
    result = CliRunner().invoke(
        main,
        ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    by_id = {row["canonical_id"]: row for row in payload}
    assert by_id["concept:coined"]["bucket"] == "coined"
    assert by_id["paper:lit"]["bucket"] == "external-ref"  # article: -> paper: at load


def test_triage_aggregate_text(tmp_path: Path) -> None:
    _write_project(tmp_path)
    result = CliRunner().invoke(main, ["entities", "triage-aggregate", "--project-root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "coined" in result.output
    assert "external-ref" in result.output
    assert "concept:coined" in result.output
