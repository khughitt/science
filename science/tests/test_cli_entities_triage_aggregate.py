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


def _write_v3(root: Path, entries: list[dict]) -> None:
    (root / "science.yaml").write_text(
        "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n", encoding="utf-8"
    )
    agg = root / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "entities.yaml").write_text(yaml.safe_dump({"entities": entries}), encoding="utf-8")


def test_bucket_flag_alone_is_dry_run_plan(tmp_path: Path) -> None:
    _write_v3(
        tmp_path,
        [
            {
                "canonical_id": "concept:1q-gain",
                "kind": "concept",
                "title": "x",
                "source_path": "knowledge/sources/local/entities.yaml",
            }
        ],
    )
    result = CliRunner().invoke(
        main, ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--promote-coined", "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert payload["promoted"] == ["concept:1q-gain"]
    assert not (tmp_path / "entities/concepts/1q-gain.md").exists()  # dry-run wrote nothing


def test_apply_executes(tmp_path: Path) -> None:
    _write_v3(
        tmp_path,
        [
            {
                "canonical_id": "concept:1q-gain",
                "kind": "concept",
                "title": "x",
                "source_path": "knowledge/sources/local/entities.yaml",
            }
        ],
    )
    result = CliRunner().invoke(
        main, ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--promote-coined", "--apply"]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "entities/concepts/1q-gain.md").exists()


def test_apply_without_bucket_flag_is_usage_error(tmp_path: Path) -> None:
    _write_v3(tmp_path, [])
    result = CliRunner().invoke(main, ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--apply"])
    assert result.exit_code == 2


def test_apply_refused_on_v2(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 2\n", encoding="utf-8"
    )
    agg = tmp_path / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "entities.yaml").write_text(yaml.safe_dump({"entities": []}), encoding="utf-8")
    result = CliRunner().invoke(
        main, ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--delete-cruft", "--apply"]
    )
    assert result.exit_code == 1
    assert "layout_version" in result.output


def test_delete_cruft_apply_removes_entry(tmp_path: Path) -> None:
    keep = {
        "canonical_id": "concept:keep",
        "kind": "concept",
        "title": "x",
        "source_path": "knowledge/sources/local/entities.yaml",
    }
    cruft = {
        "canonical_id": "concept:drop",
        "kind": "concept",
        "title": "x",
        "source_path": "migration:audit",
    }
    _write_v3(tmp_path, [keep, cruft])
    result = CliRunner().invoke(
        main,
        ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--delete-cruft", "--apply"],
    )
    assert result.exit_code == 0, result.output
    data = yaml.safe_load((tmp_path / "knowledge/sources/local/entities.yaml").read_text(encoding="utf-8"))
    assert [e["canonical_id"] for e in data["entities"]] == ["concept:keep"]
    assert not (tmp_path / "entities/concepts/drop.md").exists()


def test_bare_command_is_unchanged_3a_report(tmp_path: Path) -> None:
    # Regression: no bucket flags, no --apply → the original 3a triage report.
    _write_v3(
        tmp_path,
        [
            {
                "canonical_id": "concept:coined",
                "kind": "concept",
                "title": "x",
                "source_path": "knowledge/sources/local/entities.yaml",
            }
        ],
    )
    result = CliRunner().invoke(
        main, ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert isinstance(payload, list)  # 3a report is a list of rows, not a report object
    assert payload[0]["bucket"] == "coined"
