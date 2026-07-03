from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from _fixtures.entity_helpers import seed_project, write_markdown_entity
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.registry import RegistryBuilder
from science_tool.graph.sources import load_project_sources


_COMMONS_FIXTURE = Path(__file__).parent / "fixtures" / "commons" / "valid"


def _read_terms(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _copy_commons_fixture(tmp_path: Path) -> Path:
    commons_root = tmp_path / "commons"
    shutil.copytree(_COMMONS_FIXTURE, commons_root)
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()
    return commons_root


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


def test_terms_add_rejects_duplicate_target_row_without_rewrite() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        terms_path = root / "knowledge" / "sources" / "local" / "terms.yaml"
        terms_path.parent.mkdir(parents=True)
        original = "terms:\n  - id: concept:treatment-response\n    title: Treatment response\n"
        terms_path.write_text(original, encoding="utf-8")

        result = runner.invoke(
            main,
            ["terms", "add", "concept:treatment-response", "--title", "Treatment response"],
        )

        assert result.exit_code != 0
        assert "already exists in the target terms.yaml" in result.output
        assert terms_path.read_text(encoding="utf-8") == original


def test_terms_add_rejects_malformed_and_empty_ids_before_writing() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        for term_id in ("treatment-response", "concept:", ":treatment-response"):
            result = runner.invoke(
                main,
                ["terms", "add", term_id, "--title", "Treatment response"],
            )
            assert result.exit_code != 0, result.output

        assert not (root / "knowledge" / "sources" / "local" / "terms.yaml").exists()


def test_terms_add_rejects_unsupported_prefix_and_external_ontology_prefix() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        unsupported = runner.invoke(
            main,
            ["terms", "add", "notakind:treatment-response", "--title", "Treatment response"],
        )
        external = runner.invoke(
            main,
            [
                "terms",
                "add",
                "HP:0001250",
                "--title",
                "Seizure",
                "--ontology-term",
                "HP:0001250",
            ],
        )

        assert unsupported.exit_code != 0
        assert "Unsupported term id prefix 'notakind'" in unsupported.output
        assert "registered entity kind" in unsupported.output
        assert external.exit_code != 0
        assert "Unsupported term id prefix 'HP'" in external.output
        assert "--ontology-term" in external.output
        assert not (root / "knowledge" / "sources" / "local" / "terms.yaml").exists()


def test_terms_add_rejects_existing_markdown_owner() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/concepts/treatment-response.md",
            {
                "id": "concept:treatment-response",
                "type": "concept",
                "title": "Treatment Response",
                "status": "active",
            },
        )

        result = runner.invoke(
            main,
            ["terms", "add", "concept:treatment-response", "--title", "Treatment response"],
        )

        assert result.exit_code != 0
        assert "concept:treatment-response already resolves to an existing owner" in result.output
        assert "markdown:entities/concepts/treatment-response.md" in result.output
        assert not (root / "knowledge" / "sources" / "local" / "terms.yaml").exists()


def test_terms_add_rejects_malformed_terms_yaml_without_rewrite() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        terms_path = root / "knowledge" / "sources" / "local" / "terms.yaml"
        terms_path.parent.mkdir(parents=True)
        original = "terms: [\n"
        terms_path.write_text(original, encoding="utf-8")

        result = runner.invoke(
            main,
            ["terms", "add", "concept:treatment-response", "--title", "Treatment response"],
        )

        assert result.exit_code != 0
        assert "terms.yaml is not valid YAML" in result.output
        assert terms_path.read_text(encoding="utf-8") == original


def test_terms_add_rejects_existing_non_list_terms_key_without_rewrite() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        terms_path = root / "knowledge" / "sources" / "local" / "terms.yaml"
        terms_path.parent.mkdir(parents=True)
        original = "terms: {}\n"
        terms_path.write_text(original, encoding="utf-8")

        result = runner.invoke(
            main,
            ["terms", "add", "concept:treatment-response", "--title", "Treatment response"],
        )

        assert result.exit_code != 0
        assert "list-valued 'terms' key" in result.output
        assert terms_path.read_text(encoding="utf-8") == original


def test_terms_add_rejects_loaded_aggregate_owner() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        local_sources = root / "knowledge" / "sources" / "local"
        local_sources.mkdir(parents=True)
        (local_sources / "entities.yaml").write_text(
            yaml.safe_dump(
                {
                    "entities": [
                        {
                            "id": "concept:treatment-response",
                            "kind": "concept",
                            "title": "Treatment response aggregate",
                        }
                    ]
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            main,
            ["terms", "add", "concept:treatment-response", "--title", "Treatment response"],
        )

        assert result.exit_code != 0
        assert "concept:treatment-response already resolves to an existing owner" in result.output
        assert "aggregate:knowledge/sources/local/entities.yaml" in result.output
        assert not (local_sources / "terms.yaml").exists()


def test_terms_add_rejects_existing_commons_owner(tmp_path: Path, monkeypatch) -> None:
    commons_root = _copy_commons_fixture(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")

    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/concepts/local-context.md",
            {
                "id": "concept:local-context",
                "type": "concept",
                "title": "Local context",
                "status": "active",
                "related": ["topic:single-cell-foundation-models"],
            },
        )

        result = runner.invoke(
            main,
            [
                "terms",
                "add",
                "topic:single-cell-foundation-models",
                "--title",
                "Single-cell foundation models",
            ],
        )

        assert result.exit_code != 0
        assert (
            "topic:single-cell-foundation-models already resolves to an existing owner"
            in result.output
        )
        assert "commons-merged:commons://topics/single-cell-foundation-models.md" in result.output
        assert not (root / "knowledge" / "sources" / "local" / "terms.yaml").exists()


def test_terms_add_reports_unrelated_genuine_identity_collision_distinctly() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/concepts/one.md",
            {
                "id": "concept:duplicate",
                "type": "concept",
                "title": "Duplicate One",
                "status": "active",
            },
        )
        write_markdown_entity(
            root,
            "entities/concepts/two.md",
            {
                "id": "concept:duplicate",
                "type": "concept",
                "title": "Duplicate Two",
                "status": "active",
            },
        )

        result = runner.invoke(
            main,
            ["terms", "add", "concept:new-term", "--title", "New term"],
        )

        assert result.exit_code != 0
        assert "Project already contains identity collision(s) unrelated to this term" in result.output
        assert "concept:duplicate" in result.output
        assert "concept:new-term already resolves" not in result.output
        assert not (root / "knowledge" / "sources" / "local" / "terms.yaml").exists()


def test_terms_add_identity_precheck_loads_non_strict_with_commons_default(
    tmp_path: Path, monkeypatch
) -> None:
    import science_tool.terms as terms_module

    seed_project(tmp_path)
    calls: list[dict[str, object]] = []

    class StopAfterLoad(Exception):
        pass

    def fake_load_project_sources(project_root: Path, **kwargs: object):
        calls.append(kwargs)
        raise StopAfterLoad

    monkeypatch.setattr(terms_module, "load_project_sources", fake_load_project_sources)

    try:
        terms_module.add_term(
            project_root=tmp_path,
            term_id="concept:commons-owned",
            title="Commons owned",
        )
    except StopAfterLoad:
        pass
    else:
        raise AssertionError("expected fake loader to stop the command")

    assert calls == [{"strict_identity": False}]
