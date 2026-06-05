from __future__ import annotations

import json
import os
import re
from pathlib import Path

from click.testing import CliRunner
import yaml

from _fixtures.entity_helpers import seed_project, write_markdown_entity
from science_model.contracts.inventory_v2 import InventoryPayload as InventoryPayloadV2
from science_model.entities import EntityClass
from science_model.profiles.schema import ProfileManifest
from science_tool.cli import main
from science_tool.graph.sources import load_project_sources

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def test_entity_create_question_writes_source() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-existing.md",
            {"id": "question:0001-existing", "type": "question", "title": "Existing", "status": "open"},
        )

        result = runner.invoke(main, ["entity", "create", "question", "New Question"])

        assert result.exit_code == 0, result.output
        assert "question:0002-new-question" in result.output
        assert Path("entities/questions/0002-new-question.md").is_file()


def test_questions_create_uses_plural_group_and_singular_is_removed() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-existing.md",
            {"id": "question:0001-existing", "type": "question", "title": "Existing", "status": "active"},
        )

        result = runner.invoke(main, ["questions", "create", "New Question"])
        removed = runner.invoke(main, ["question", "--help"])

        assert result.exit_code == 0, result.output
        assert "question:0002-new-question" in result.output
        assert Path("entities/questions/0002-new-question.md").is_file()
        assert removed.exit_code != 0
        assert "No such command 'question'" in removed.output


def test_questions_show_rejects_other_entity_kinds() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/hypotheses/0001-alpha.md",
            {"id": "hypothesis:0001-alpha", "type": "hypothesis", "title": "Alpha", "status": "proposed"},
        )

        result = runner.invoke(main, ["questions", "show", "h1"])

        assert result.exit_code != 0
        assert "Expected question entity, got hypothesis:0001-alpha" in result.output


def test_questions_show_accepts_q_shortform_for_numbered_question_id() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-alpha.md",
            {"id": "question:0001-alpha", "type": "question", "title": "Alpha", "status": "active"},
        )

        result = runner.invoke(main, ["questions", "show", "q1"])

        assert result.exit_code == 0, result.output
        assert "question:0001-alpha" in result.output
        assert "Alpha" in result.output


def test_plural_entity_list_and_show_commands() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-alpha.md",
            {"id": "question:0001-alpha", "type": "question", "title": "Alpha", "status": "active"},
            "# Alpha\n\n## Summary\n\nBody content.\n",
        )
        write_markdown_entity(
            root,
            "entities/hypotheses/0001-beta.md",
            {"id": "hypothesis:0001-beta", "type": "hypothesis", "title": "Beta", "status": "proposed"},
        )
        write_markdown_entity(
            root,
            "entities/discussions/0001-gamma.md",
            {
                "id": "discussion:0001-gamma",
                "type": "discussion",
                "title": "Gamma",
                "status": "active",
            },
        )

        questions_show = runner.invoke(main, ["questions", "show", "q1"])
        hypotheses_list = runner.invoke(main, ["hypotheses", "list", "--format", "json"])
        discussions_list = runner.invoke(main, ["discussions", "list"])

        assert questions_show.exit_code == 0, questions_show.output
        assert "question:0001-alpha" in questions_show.output
        assert "Body content." in questions_show.output
        assert hypotheses_list.exit_code == 0, hypotheses_list.output
        assert [row["id"] for row in json.loads(hypotheses_list.output)["rows"]] == ["hypothesis:0001-beta"]
        assert discussions_list.exit_code == 0, discussions_list.output
        assert "discussion:0001-gamma" in discussions_list.output


def test_plural_entity_list_uses_shared_color_styles() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "doc/questions/q01-alpha.md",
            {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "active"},
        )

        result = runner.invoke(main, ["--color", "always", "questions", "list"])

        assert result.exit_code == 0, result.output
        assert "question:q01-alpha" in ANSI_RE.sub("", result.output)
        assert ANSI_RE.search(result.output) is not None


def test_entity_create_theme_cli_round_trips() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "entity",
                "create",
                "theme",
                "Transportability Across Cancer Types",
            ],
        )

        assert result.exit_code == 0, result.output
        path = Path("entities/themes/0001-transportability-across-cancer-types.md")
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "theme:0001-transportability-across-cancer-types" in text
        assert "## Definition" in text


def test_entity_create_with_unresolved_related_prints_warning() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-existing.md",
            {"id": "question:0001-existing", "type": "question", "title": "Existing", "status": "open"},
        )

        result = runner.invoke(main, ["entity", "create", "question", "New Question", "--related", "hypothesis:h01"])

        assert result.exit_code == 0, result.output
        assert "WARNING" in result.output


def test_entity_show_finds_source_entity_by_shorthand() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-alpha.md",
            {"id": "question:0001-alpha", "type": "question", "title": "Alpha", "status": "open"},
        )

        result = runner.invoke(main, ["entity", "show", "q1"])

        assert result.exit_code == 0, result.output
        assert "question:0001-alpha" in result.output
        assert "Alpha" in result.output


def test_entity_show_emits_body_content() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-alpha.md",
            {"id": "question:0001-alpha", "type": "question", "title": "Alpha", "status": "open"},
            "# Alpha\n\n## Summary\n\nBody content.\n",
        )

        result = runner.invoke(main, ["entity", "show", "q1"])

        assert result.exit_code == 0, result.output
        assert "## Summary" in result.output
        assert "Body content." in result.output


def test_entity_show_json_outputs_machine_readable_payload() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-alpha.md",
            {"id": "question:0001-alpha", "type": "question", "title": "Alpha", "status": "open"},
        )

        result = runner.invoke(main, ["entity", "show", "q1", "--format", "json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload == {
            "id": "question:0001-alpha",
            "kind": "question",
            "title": "Alpha",
            "status": "open",
            "path": "entities/questions/0001-alpha.md",
            "related": [],
            "source_refs": [],
            "body": "",
        }


def test_entity_edit_adds_related_without_replacing_existing() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        path = write_markdown_entity(
            root,
            "entities/questions/0001-alpha.md",
            {
                "id": "question:0001-alpha",
                "type": "question",
                "title": "Alpha",
                "status": "open",
                "related": ["hypothesis:h01"],
            },
        )

        result = runner.invoke(main, ["entity", "edit", "q1", "--related", "hypothesis:h02"])

        assert result.exit_code == 0, result.output
        assert "WARNING" in result.output
        text = path.read_text(encoding="utf-8")
        assert "hypothesis:h01" in text
        assert "hypothesis:h02" in text


def test_entity_note_adds_dated_note() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        path = write_markdown_entity(
            root,
            "entities/questions/0001-alpha.md",
            {"id": "question:0001-alpha", "type": "question", "title": "Alpha", "status": "open"},
            "# Alpha\n",
        )

        result = runner.invoke(main, ["entity", "note", "q1", "Clarified.", "--date", "2026-04-28"])

        assert result.exit_code == 0, result.output
        assert "Added note to question:0001-alpha (2026-04-28)" in result.output
        assert "- 2026-04-28: Clarified." in path.read_text(encoding="utf-8")


def test_entity_list_filters_exact_status() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "doc/questions/q01-alpha.md",
            {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"},
        )
        write_markdown_entity(
            root,
            "doc/questions/q02-beta.md",
            {"id": "question:q02-beta", "type": "question", "title": "Beta", "status": "answered"},
        )

        result = runner.invoke(
            main, ["entity", "list", "--kind", "question", "--status", "answered", "--format", "json"]
        )

        assert result.exit_code == 0, result.output
        assert "question:q02-beta" in result.output
        assert "question:q01-alpha" not in result.output


def test_entity_list_filters_related_refs_with_alias_resolution() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "specs/hypotheses/h01-anchor.md",
            {
                "id": "hypothesis:h01-anchor",
                "type": "hypothesis",
                "title": "Anchor",
                "status": "proposed",
                "aliases": ["hypothesis:anchor-alias"],
            },
        )
        write_markdown_entity(
            root,
            "doc/questions/q01-alpha.md",
            {
                "id": "question:q01-alpha",
                "type": "question",
                "title": "Alpha",
                "status": "open",
                "related": ["hypothesis:anchor-alias"],
            },
        )
        write_markdown_entity(
            root,
            "doc/questions/q02-beta.md",
            {
                "id": "question:q02-beta",
                "type": "question",
                "title": "Beta",
                "status": "open",
                "related": ["hypothesis:h02-other"],
            },
        )

        result = runner.invoke(main, ["entity", "list", "--related", "hypothesis:h01-anchor", "--format", "json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert [row["id"] for row in payload["rows"]] == ["question:q01-alpha"]


def test_entities_inventory_cli_outputs_contract_json(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "science.yaml").write_text("id: cli-project\n", encoding="utf-8")
    (project / "doc" / "finding.md").write_text(
        "---\nkind: finding\nid: finding:f001\ntitle: Finding\n---\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(main, ["entities", "inventory", "--project", str(project), "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = InventoryPayloadV2.model_validate_json(result.output)
    assert payload.schema_version == "2"
    assert payload.project_id == "cli-project"
    assert payload.entities[0].id == "finding:f001"


def test_entities_inventory_cli_writes_contract_json_to_output_file(tmp_path) -> None:
    project = tmp_path / "project"
    output = tmp_path / "inventory.json"
    (project / "doc").mkdir(parents=True)
    (project / "science.yaml").write_text("id: cli-output-project\n", encoding="utf-8")
    (project / "doc" / "finding.md").write_text(
        "---\nkind: finding\nid: finding:f001\ntitle: Finding\n---\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["entities", "inventory", "--project", str(project), "--format", "json", "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert result.output == ""
    payload = InventoryPayloadV2.model_validate_json(output.read_text(encoding="utf-8"))
    assert payload.project_id == "cli-output-project"
    assert payload.entities[0].id == "finding:f001"


def test_entities_inventory_cli_rejects_schema_version_option(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "science.yaml").write_text("id: v1-cli-project\n", encoding="utf-8")
    (project / "doc" / "finding.md").write_text(
        "---\nkind: finding\nid: finding:f001\ntitle: Finding\n---\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "entities",
            "inventory",
            "--project",
            str(project),
            "--format",
            "json",
            "--schema-version",
            "1",
        ],
    )

    assert result.exit_code != 0
    assert "No such option: --schema-version" in result.output


def test_entities_audit_identifiers_cli_outputs_json(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "doc" / "finding.md").write_text("---\nkind: finding\ntitle: Finding\n---\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(main, ["entities", "audit-identifiers", "--project", str(project)])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "missing_canonical_ids": ["doc/finding.md"],
        "invalid_canonical_ids": [],
    }


def test_entities_migrate_identifiers_cli_dry_run_outputs_json(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    path = project / "doc" / "finding.md"
    path.write_text("---\nkind: finding\ntitle: Finding\n---\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(main, ["entities", "migrate-identifiers", "--project", str(project)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["planned_changes"] == [{"path": "doc/finding.md", "new_id": "finding:finding"}]
    assert "id: finding:finding" not in path.read_text(encoding="utf-8")


def test_entities_identifier_commands_emit_json_for_malformed_non_entity_markdown(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "notes").mkdir(parents=True)
    (project / "notes" / "command.md").write_text("---\nrun: [unterminated\n---\n", encoding="utf-8")
    runner = CliRunner()

    audit = runner.invoke(main, ["entities", "audit-identifiers", "--project", str(project)])
    migrate = runner.invoke(main, ["entities", "migrate-identifiers", "--project", str(project)])

    assert audit.exit_code == 0, audit.output
    assert migrate.exit_code == 0, migrate.output
    assert json.loads(audit.output) == {"missing_canonical_ids": [], "invalid_canonical_ids": []}
    assert json.loads(migrate.output)["planned_changes"] == []


def test_entities_register_kind_is_idempotent_with_same_metadata(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    first = runner.invoke(
        main,
        ["entities", "register-kind", "critique", "--class", "epistemic", "--project", str(project)],
    )
    second = runner.invoke(
        main,
        ["entities", "register-kind", "critique", "--class", "epistemic", "--project", str(project)],
    )

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert "already registered" in second.output
    manifest = yaml.safe_load(
        (project / "knowledge" / "sources" / "local" / "manifest.yaml").read_text(encoding="utf-8")
    )
    assert manifest["name"] == "local"
    assert manifest["imports"] == []
    assert manifest["strictness"] == "typed-extension"
    assert manifest["relation_kinds"] == []
    assert manifest["entity_kinds"] == [
        {
            "name": "critique",
            "canonical_prefix": "critique",
            "layer": "layer/local",
            "description": "Project-local critique entity kind.",
            "entity_class": "epistemic",
        }
    ]


def test_entities_register_kind_errors_on_changed_semantics(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    first = runner.invoke(
        main, ["entities", "register-kind", "critique", "--class", "epistemic", "--project", str(project)]
    )
    assert first.exit_code == 0, first.output

    result = runner.invoke(
        main, ["entities", "register-kind", "critique", "--class", "operational", "--project", str(project)]
    )

    assert result.exit_code != 0
    assert "already registered with different metadata" in result.output


def test_entities_register_kind_makes_markdown_kind_loadable(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    (project / "doc" / "critique.md").write_text(
        "---\nkind: critique\nid: critique:c001\ntitle: Critique\n---\nBody.\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["entities", "register-kind", "critique", "--class", "epistemic", "--project", str(project)],
    )

    assert result.exit_code == 0, result.output
    sources = load_project_sources(project)
    assert [entity.id for entity in sources.entities] == ["critique:c001"]
    assert sources.registry.kind_class("critique") == EntityClass.EPISTEMIC


def test_entities_register_kind_uses_legacy_profiles_local_fallback(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "science.yaml").write_text(
        "id: kind-project\nprofiles: {local: lab}\n",
        encoding="utf-8",
    )
    (project / "doc" / "critique.md").write_text(
        "---\nkind: critique\nid: critique:c001\ntitle: Critique\n---\nBody.\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["entities", "register-kind", "critique", "--class", "epistemic", "--project", str(project)],
    )

    assert result.exit_code == 0, result.output
    assert (project / "knowledge" / "sources" / "lab" / "manifest.yaml").is_file()
    assert not (project / "knowledge" / "sources" / "local" / "manifest.yaml").exists()
    sources = load_project_sources(project)
    assert [entity.id for entity in sources.entities] == ["critique:c001"]


def test_entities_register_kind_rejects_invalid_class_without_writing(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["entities", "register-kind", "critique", "--class", "interpretation", "--project", str(project)],
    )

    assert result.exit_code != 0
    assert "Invalid entity_class" in result.output
    assert not manifest_path.exists()


def test_entities_register_kind_rejects_core_kind_shadow_without_writing(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["entities", "register-kind", "hypothesis", "--class", "epistemic", "--project", str(project)],
    )

    assert result.exit_code != 0
    assert "built-in entity kind" in result.output
    assert not manifest_path.exists()


def test_entities_register_kind_rejects_builtin_local_kind_shadow_without_writing(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["entities", "register-kind", "model", "--class", "operational", "--project", str(project)],
    )

    assert result.exit_code != 0
    assert "built-in entity kind" in result.output
    assert not manifest_path.exists()


def test_entities_register_kind_rejects_parameter_alias_shadow_without_writing(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["entities", "register-kind", "parameter", "--class", "operational", "--project", str(project)],
    )

    assert result.exit_code != 0
    assert "normalizes to built-in entity kind" in result.output
    assert not manifest_path.exists()


def test_entities_register_kind_rejects_hyphenated_parameter_alias_shadow_without_writing(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["entities", "register-kind", "parameter-binding", "--class", "operational", "--project", str(project)],
    )

    assert result.exit_code != 0
    assert "normalizes to built-in entity kind" in result.output
    assert not manifest_path.exists()


def test_entities_register_kind_rejects_registry_core_kind_shadow_without_writing(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["entities", "register-kind", "concept", "--class", "reference", "--project", str(project)],
    )

    assert result.exit_code != 0
    assert "built-in entity kind" in result.output
    assert not manifest_path.exists()


def test_entities_register_kind_rejects_active_ontology_kind_shadow_without_writing(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles: {local: local}\nontologies: [biology]\n",
        encoding="utf-8",
    )
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["entities", "register-kind", "gene", "--class", "reference", "--project", str(project)],
    )

    assert result.exit_code != 0
    assert "active ontology entity kind" in result.output
    assert not manifest_path.exists()


def test_entities_register_kind_rejects_shared_profile_kind_shadow_without_writing(tmp_path, monkeypatch) -> None:
    shared_profile = ProfileManifest.model_validate(
        {
            "name": "shared",
            "imports": [],
            "strictness": "typed-extension",
            "entity_kinds": [
                {
                    "name": "shared-kind",
                    "canonical_prefix": "shared-kind",
                    "layer": "layer/shared",
                    "description": "Shared test kind.",
                    "entity_class": "epistemic",
                }
            ],
            "relation_kinds": [],
        }
    )
    monkeypatch.setattr("science_tool.entity_kinds.load_shared_profile", lambda: shared_profile, raising=False)
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["entities", "register-kind", "shared-kind", "--class", "epistemic", "--project", str(project)],
    )

    assert result.exit_code != 0
    assert "shared profile entity kind" in result.output
    assert not manifest_path.exists()


def test_entities_register_kind_preserves_existing_manifest_sections(tmp_path) -> None:
    project = tmp_path / "project"
    manifest_path = project / "knowledge" / "sources" / "lab" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles: {local: lab}\n",
        encoding="utf-8",
    )
    manifest_path.write_text(
        """
name: existing-name
imports:
  - shared
strictness: typed-extension
entity_kinds:
  - name: note-kind
    canonical_prefix: note
    layer: layer/existing
    description: Existing note kind.
    entity_class: operational
relation_kinds: []
x-extra:
  keep: true
""".lstrip(),
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["entities", "register-kind", "critique", "--class", "epistemic", "--project", str(project)],
    )

    assert result.exit_code == 0, result.output
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert manifest["name"] == "existing-name"
    assert manifest["imports"] == ["shared"]
    assert manifest["relation_kinds"] == []
    assert manifest["x-extra"] == {"keep": True}
    assert [entry["name"] for entry in manifest["entity_kinds"]] == ["note-kind", "critique"]


def test_entities_register_kind_errors_without_overwriting_malformed_manifest(tmp_path) -> None:
    project = tmp_path / "project"
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    original = "- not-a-manifest\n"
    manifest_path.write_text(original, encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["entities", "register-kind", "critique", "--class", "epistemic", "--project", str(project)],
    )

    assert result.exit_code != 0
    assert str(manifest_path) in result.output
    assert "must contain a YAML mapping" in result.output
    assert manifest_path.read_text(encoding="utf-8") == original


def test_entities_register_kind_errors_without_overwriting_non_list_imports(tmp_path) -> None:
    project = tmp_path / "project"
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    original = """
name: local
imports: core
strictness: typed-extension
entity_kinds: []
relation_kinds: []
""".lstrip()
    manifest_path.write_text(original, encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["entities", "register-kind", "critique", "--class", "epistemic", "--project", str(project)],
    )

    assert result.exit_code != 0
    assert str(manifest_path) in result.output
    assert "imports" in result.output
    assert manifest_path.read_text(encoding="utf-8") == original


def test_entities_register_kind_errors_without_overwriting_non_list_relation_kinds(tmp_path) -> None:
    project = tmp_path / "project"
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    original = """
name: local
imports: []
strictness: typed-extension
entity_kinds: []
relation_kinds: nope
""".lstrip()
    manifest_path.write_text(original, encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["entities", "register-kind", "critique", "--class", "epistemic", "--project", str(project)],
    )

    assert result.exit_code != 0
    assert str(manifest_path) in result.output
    assert "relation_kinds" in result.output
    assert manifest_path.read_text(encoding="utf-8") == original


def test_question_create_wrapper_delegates_to_entity_create() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-existing.md",
            {"id": "question:0001-existing", "type": "question", "title": "Existing", "status": "open"},
        )

        result = runner.invoke(main, ["questions", "create", "Wrapper Question", "--slug", "wrapper"])

        assert result.exit_code == 0, result.output
        assert "question:0002-wrapper" in result.output
        assert Path("entities/questions/0002-wrapper.md").is_file()


def test_discussion_focus_maps_to_related() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "discussions",
                "create",
                "Planning",
                "--id",
                "discussion:0001-planning",
                "--focus",
                "question:q01-alpha",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "question:q01-alpha" in Path("entities/discussions/0001-planning.md").read_text(encoding="utf-8")


def test_interpretation_input_maps_to_source_refs() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "interpretations",
                "create",
                "Result",
                "--id",
                "interpretation:0001-result",
                "--input",
                "results/run-1",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "results/run-1" in Path("entities/interpretations/0001-result.md").read_text(encoding="utf-8")


def test_graph_add_question_mentions_entity_create() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        init = runner.invoke(main, ["graph", "init"])
        assert init.exit_code == 0, init.output

        result = runner.invoke(
            main,
            [
                "graph",
                "add",
                "question",
                "q01-legacy",
                "--text",
                "Legacy question",
                "--source",
                "manual:test",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "entity create question" in result.output


def test_proposition_create_writes_source() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "propositions",
                "create",
                "Cadence shapes recovered switch history",
                "--id",
                "proposition:0001-cadence-shapes-switch-history",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "proposition:0001-cadence-shapes-switch-history" in result.output
        path = Path("entities/propositions/0001-cadence-shapes-switch-history.md")
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert "type: proposition" in text or 'type: "proposition"' in text
        assert "## Claim" in text


def test_graph_add_proposition_warns_about_ephemerality() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        init = runner.invoke(main, ["graph", "init"])
        assert init.exit_code == 0, init.output

        result = runner.invoke(
            main,
            [
                "graph",
                "add",
                "proposition",
                "Cadence shapes recovered switch history",
                "--source",
                "data-package:t015-baseline",
                "--id",
                "p01-cadence-shapes-switch-history",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "wiped on the next" in result.output
        assert "propositions create" in result.output


def test_graph_add_observation_warns_about_ephemerality() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        init = runner.invoke(main, ["graph", "init"])
        assert init.exit_code == 0, init.output

        result = runner.invoke(
            main,
            [
                "graph",
                "add",
                "observation",
                "Switch event count fell with cadence",
                "--data-source",
                "data-package:t015-baseline",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "wiped on the next" in result.output


def test_graph_add_finding_warns_about_ephemerality() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        init = runner.invoke(main, ["graph", "init"])
        assert init.exit_code == 0, init.output

        result = runner.invoke(
            main,
            [
                "graph",
                "add",
                "finding",
                "Cadence shapes switch history",
                "--confidence",
                "moderate",
                "--proposition",
                "proposition:p01-cadence",
                "--observation",
                "observation:t015-2026-05",
                "--source",
                "data-package:t015-baseline",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "wiped on the next" in result.output


def test_graph_add_evidence_warns_about_ephemerality() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        init = runner.invoke(main, ["graph", "init"])
        assert init.exit_code == 0, init.output

        result = runner.invoke(
            main,
            [
                "graph",
                "add",
                "evidence",
                "observation:t015-2026-05",
                "proposition:p01-cadence",
                "--stance",
                "supports",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "wiped on the next" in result.output


def test_entity_neighbors_source_only_warns_and_returns_no_rows() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-alpha.md",
            {"id": "question:0001-alpha", "type": "question", "title": "Alpha", "status": "open"},
        )
        graph = Path("knowledge/graph.trig")
        graph.parent.mkdir(parents=True)
        graph.write_text("@prefix sci: <http://example.org/science/vocab/> .\n", encoding="utf-8")
        os.utime(graph, (1, 1))
        os.utime(Path("entities/questions/0001-alpha.md"), (2, 2))

        result = runner.invoke(main, ["entity", "neighbors", "question:0001-alpha", "--format", "json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["rows"] == []
        assert "WARNING" in result.stderr
        assert "WARNING" not in result.stdout


def test_entity_neighbors_missing_graph_fails_cleanly() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-alpha.md",
            {"id": "question:0001-alpha", "type": "question", "title": "Alpha", "status": "open"},
        )

        result = runner.invoke(main, ["entity", "neighbors", "question:0001-alpha"])

        assert result.exit_code != 0
        assert "Graph file not found: knowledge/graph.trig" in result.output


def test_entity_note_without_date_prints_today() -> None:
    from datetime import date

    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-alpha.md",
            {"id": "question:0001-alpha", "type": "question", "title": "Alpha", "status": "open"},
            "# Alpha\n",
        )

        result = runner.invoke(main, ["entity", "note", "q1", "Clarified."])

        assert result.exit_code == 0, result.output
        assert f"Added note to question:0001-alpha ({date.today().isoformat()})" in result.output


def test_discussion_create_without_id_uses_today() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["discussions", "create", "Planning"])

        assert result.exit_code == 0, result.output
        assert "discussion:0001-planning" in result.output
        assert Path("entities/discussions/0001-planning.md").is_file()


def test_discussion_create_with_optional_section_includes_addendum() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["discussions", "create", "Test discussion", "--with", "double-blind-addendum"])

        assert result.exit_code == 0, result.output
        path = Path("entities/discussions/0001-test-discussion.md")
        assert path.is_file()
        assert "## Double-Blind Addendum" in path.read_text(encoding="utf-8")


def test_hypothesis_create_phase_candidate_sets_field_and_includes_promotion_criteria() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            ["hypotheses", "create", "Trial framing", "--id", "hypothesis:0001-trial-framing", "--phase", "candidate"],
        )

        assert result.exit_code == 0, result.output
        path = Path("entities/hypotheses/0001-trial-framing.md")
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert "phase: candidate" in text
        assert "## Promotion criteria" in text


def test_hypothesis_create_defaults_phase_active_without_promotion_criteria() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main, ["hypotheses", "create", "Committed frame", "--id", "hypothesis:0001-committed-frame"]
        )

        assert result.exit_code == 0, result.output
        path = Path("entities/hypotheses/0001-committed-frame.md")
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert "phase: active" in text
        assert "## Promotion criteria" not in text


def test_discussion_create_no_hints_strips_html_comments() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["discussions", "create", "Test discussion", "--no-hints"])

        assert result.exit_code == 0, result.output
        path = Path("entities/discussions/0001-test-discussion.md")
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert "<!--" not in text


def test_entity_sections_lists_template_sections() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["entity", "sections", "discussion"], env={"COLUMNS": "200"})
        assert result.exit_code == 0, result.output
        assert "double-blind-addendum" in result.output
        assert "optional" in result.output


def test_entity_sections_accepts_format_json() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["entity", "sections", "discussion", "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        keys = {row["key"] for row in payload["rows"]}
        assert "double-blind-addendum" in keys


def test_discussion_create_unknown_section_key_errors() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["discussions", "create", "Test discussion", "--with", "bogus"])

        assert result.exit_code != 0
        assert "bogus" in result.output
        assert "double-blind-addendum" in result.output


def test_entity_create_paper_uses_citekey() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        result = runner.invoke(
            main, ["entity", "create", "paper", "Some Paper", "--id", "paper:Adams2025"]
        )
        assert result.exit_code == 0, result.output
        assert Path("entities/papers/Adams2025.md").is_file()


def test_entity_create_newly_added_kind_uses_generic_scaffold() -> None:
    # A non-MIGRATED_KIND (no domain template) must still create successfully
    # with valid required frontmatter (generic scaffold).
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        result = runner.invoke(main, ["entity", "create", "observation", "An Observation"])
        assert result.exit_code == 0, result.output
        path = Path("entities/observations/0001-an-observation.md")
        assert path.is_file()
        fm = yaml.safe_load(path.read_text().split("---")[1])
        assert fm["id"] == "observation:0001-an-observation"
        assert fm["type"] == "observation"
        assert {"title", "status", "created", "updated"} <= set(fm)


def test_entities_dir_is_discovered_by_graph() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-loadable.md",
            {"id": "question:0001-loadable", "type": "question", "title": "Loadable", "status": "active"},
        )
        sources = load_project_sources(root)
        ids = {doc.frontmatter.get("id") for doc in sources.markdown_documents}
        assert "question:0001-loadable" in ids


def test_entity_show_resolves_shortform() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0005-granularity.md",
            {"id": "question:0005-granularity", "type": "question", "title": "Granularity", "status": "active"},
        )
        result = runner.invoke(main, ["entity", "show", "q5"])
        assert result.exit_code == 0, result.output
        assert "question:0005-granularity" in result.output


def test_entities_migrate_dry_run_emits_report() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        (root / "science.yaml").write_text("name: t\nlayout_version: 2\n", encoding="utf-8")
        write_markdown_entity(
            root, "specs/hypotheses/h01-alpha.md",
            {"id": "hypothesis:h01-alpha", "type": "hypothesis", "title": "Alpha", "status": "proposed",
             "created": "2026-01-01", "updated": "2026-01-01"},
        )
        result = runner.invoke(main, ["entities", "migrate"])
        assert result.exit_code == 0, result.output
        assert "hypothesis:0001-alpha" in result.output  # report shows planned id
        assert Path("specs/hypotheses/h01-alpha.md").is_file()  # dry run: unchanged


def test_entities_migrate_apply_blocks_with_clean_error() -> None:
    """--apply with a path collision must exit non-zero with a clean ClickException message."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        (root / "science.yaml").write_text("name: t\nlayout_version: 2\n", encoding="utf-8")
        # Two paper files with the same citekey from both legacy paper homes → both
        # would map to entities/papers/Adams2025.md, triggering a path collision.
        write_markdown_entity(
            root, "doc/papers/Adams2025.md",
            {"id": "paper:Adams2025", "type": "paper", "title": "Adams 2025", "status": "read",
             "created": "2025-01-01", "updated": "2025-01-01"},
        )
        write_markdown_entity(
            root, "specs/papers/Adams2025.md",
            {"id": "paper:Adams2025", "type": "paper", "title": "Adams 2025 (dup)", "status": "read",
             "created": "2025-01-01", "updated": "2025-01-01"},
        )

        result = runner.invoke(main, ["entities", "migrate", "--apply"])

        # Must exit non-zero.
        assert result.exit_code != 0
        # The error message must mention the collision — clean ClickException, not a traceback.
        assert "collision" in result.output
        # A ClickException produces a SystemExit, not a raw ValueError/Exception traceback.
        assert not isinstance(result.exception, ValueError)
        # No migration happened: source files still present, target absent.
        assert Path("doc/papers/Adams2025.md").is_file()
        assert Path("specs/papers/Adams2025.md").is_file()
        assert not Path("entities/papers/Adams2025.md").exists()
