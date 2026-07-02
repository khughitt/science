from __future__ import annotations

from pathlib import Path

import yaml
from _fixtures.entity_helpers import seed_project, write_markdown_entity
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.graph.sources import load_project_sources


def _read_terms(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_terms_add_creates_minimal_local_terms_yaml_and_reloads() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "terms",
                "add",
                "concept:treatment-response",
                "--title",
                "Treatment response",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Added concept:treatment-response" in result.output
        assert "knowledge/sources/local/terms.yaml" in result.output

        terms_path = root / "knowledge" / "sources" / "local" / "terms.yaml"
        assert terms_path.is_file()
        payload = _read_terms(terms_path)
        assert payload == {
            "terms": [
                {
                    "id": "concept:treatment-response",
                    "title": "Treatment response",
                }
            ]
        }

        sources = load_project_sources(root)
        by_id = {entity.canonical_id: entity for entity in sources.entities}
        entity = by_id["concept:treatment-response"]
        assert entity.kind == "concept"
        assert entity.title == "Treatment response"
        assert entity.file_path == "knowledge/sources/local/terms.yaml"


def test_terms_add_rejects_schema_incompatible_registered_kind_without_writing() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "terms",
                "add",
                "mechanism:minimal",
                "--title",
                "Minimal mechanism",
            ],
        )

        assert result.exit_code != 0, result.output
        assert "mechanism:minimal" in result.output
        assert "cannot be represented as a lightweight term" in result.output
        assert not (root / "knowledge" / "sources" / "local" / "terms.yaml").exists()


def test_terms_add_rejects_ids_that_canonicalize_before_writing() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/papers/Smith2024.md",
            {"kind": "paper", "id": "paper:Smith2024", "title": "Smith 2024"},
        )

        result = runner.invoke(
            main,
            [
                "terms",
                "add",
                "article:Smith2024",
                "--title",
                "Smith 2024",
            ],
        )

        assert result.exit_code != 0, result.output
        assert "article:Smith2024 canonicalizes to paper:Smith2024" in result.output
        assert not (root / "knowledge" / "sources" / "local" / "terms.yaml").exists()


def test_terms_add_serializes_only_populated_optional_fields() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "terms",
                "add",
                "method:cox-regression",
                "--title",
                "Cox proportional-hazards regression",
                "--description",
                "Survival model with proportional hazards.",
                "--alias",
                "Cox model",
                "--alias",
                "Cox PH",
                "--same-as",
                "wikidata:Q1132755",
                "--ontology-term",
                "biolink:StatisticalMethod",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = _read_terms(root / "knowledge" / "sources" / "local" / "terms.yaml")
        assert payload == {
            "terms": [
                {
                    "id": "method:cox-regression",
                    "title": "Cox proportional-hazards regression",
                    "description": "Survival model with proportional hazards.",
                    "aliases": ["Cox model", "Cox PH"],
                    "same_as": ["wikidata:Q1132755"],
                    "ontology_terms": ["biolink:StatisticalMethod"],
                }
            ]
        }


def test_terms_add_uses_configured_local_profile() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        (root / "science.yaml").write_text(
            "name: term-cli-test\nknowledge_profiles: {local: lab}\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            main,
            ["terms", "add", "concept:lab-term", "--title", "Lab term"],
        )

        assert result.exit_code == 0, result.output
        assert "knowledge/sources/lab/terms.yaml" in result.output
        assert (root / "knowledge" / "sources" / "lab" / "terms.yaml").is_file()
        assert not (root / "knowledge" / "sources" / "local" / "terms.yaml").exists()


def test_terms_add_preserves_existing_order_and_unrelated_top_level_keys() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        terms_path = root / "knowledge" / "sources" / "local" / "terms.yaml"
        terms_path.parent.mkdir(parents=True)
        terms_path.write_text(
            yaml.safe_dump(
                {
                    "metadata": {"curator": "science"},
                    "terms": [
                        {"id": "concept:first", "title": "First"},
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            main,
            ["terms", "add", "concept:second", "--title", "Second"],
        )

        assert result.exit_code == 0, result.output
        payload = _read_terms(terms_path)
        assert payload["metadata"] == {"curator": "science"}
        assert payload["terms"] == [
            {"id": "concept:first", "title": "First"},
            {"id": "concept:second", "title": "Second"},
        ]


def test_terms_add_rejects_flags_that_would_write_ignored_or_unloaded_fields() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        for flag in ("--body", "--content", "--name", "--profile"):
            result = runner.invoke(
                main,
                [
                    "terms",
                    "add",
                    "concept:treatment-response",
                    "--title",
                    "Treatment response",
                    flag,
                    "value",
                ],
            )
            assert result.exit_code != 0, result.output
            assert f"No such option: {flag}" in result.output
