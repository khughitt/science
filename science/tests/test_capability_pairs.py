from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli
from science_tool.datasets.capability_pairs import enumerate_pairs


def test_distinct_shapes_counted_with_examples():
    records = [
        {
            "id": "dataset:aa",
            "kind": "dataset",
            "provided_capabilities": [{"assay": "gene-expression", "modality": "microarray"}],
        },
        {
            "id": "dataset:bb",
            "kind": "dataset",
            "provided_capabilities": [{"assay": "gene-expression", "modality": "microarray"}],
        },
        {
            "id": "hypothesis:1",
            "kind": "hypothesis",
            "required_capabilities": [{"case_definition": "who-lc"}],
        },
    ]
    shapes = enumerate_pairs(records)
    micro = next(s for s in shapes if s.raw == {"assay": "gene-expression", "modality": "microarray"})
    assert micro.count == 2
    assert set(micro.example_ids) == {"dataset:aa", "dataset:bb"}
    assert any(s.raw == {"case_definition": "who-lc"} for s in shapes)


def test_cli_requires_exactly_one_input(tmp_path: Path) -> None:
    res = CliRunner().invoke(science_cli, ["dataset", "capability-pairs"])
    assert res.exit_code != 0

    (tmp_path / "a.md").write_text('---\nid: "dataset:a"\nkind: "dataset"\n---\n', encoding="utf-8")
    res = CliRunner().invoke(
        science_cli,
        [
            "dataset",
            "capability-pairs",
            "--project-root",
            str(tmp_path),
            "--file",
            str(tmp_path / "a.md"),
        ],
    )
    assert res.exit_code != 0


def test_cli_project_root_enumerates_shapes(tmp_path: Path) -> None:
    entities = tmp_path / "entities" / "datasets"
    entities.mkdir(parents=True)
    (entities / "a.md").write_text(
        '---\nid: "dataset:a"\nkind: "dataset"\ntitle: "A"\n'
        'provided_capabilities: [{assay: "gene-expression", modality: "bulk-rna"}]\n---\n',
        encoding="utf-8",
    )
    res = CliRunner().invoke(
        science_cli,
        ["dataset", "capability-pairs", "--project-root", str(tmp_path)],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload == [
        {
            "raw": {"assay": "gene-expression", "modality": "bulk-rna"},
            "count": 1,
            "example_ids": ["dataset:a"],
        }
    ]


def test_cli_file_input_enumerates_shapes(tmp_path: Path) -> None:
    entity_file = tmp_path / "entity.md"
    entity_file.write_text(
        '---\nid: "dataset:x"\nkind: "dataset"\n'
        'provided_capabilities: [{assay: "wgs"}]\n---\n',
        encoding="utf-8",
    )
    res = CliRunner().invoke(
        science_cli,
        ["dataset", "capability-pairs", "--file", str(entity_file)],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload == [{"raw": {"assay": "wgs"}, "count": 1, "example_ids": ["dataset:x"]}]


def test_cli_commons_root_enumerates_shapes(tmp_path: Path) -> None:
    commons_entity = tmp_path / "datasets" / "cc" / "entity.md"
    commons_entity.parent.mkdir(parents=True)
    commons_entity.write_text(
        '---\nid: "dataset:cc"\nkind: "dataset"\n'
        'provided_capabilities: [{assay: "rna-seq"}]\n---\n',
        encoding="utf-8",
    )
    res = CliRunner().invoke(
        science_cli,
        ["dataset", "capability-pairs", "--commons-root", str(tmp_path)],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload == [{"raw": {"assay": "rna-seq"}, "count": 1, "example_ids": ["dataset:cc"]}]
