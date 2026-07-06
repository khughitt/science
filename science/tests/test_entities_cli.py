from __future__ import annotations

import json
import os
import re
from pathlib import Path

import yaml
from _fixtures.entity_helpers import seed_project, write_markdown_entity
from click.testing import CliRunner
from science_model.contracts.inventory_v2 import InventoryPayload as InventoryPayloadV2
from science_model.identity import EntityClass
from science_model.profiles.schema import ProfileManifest

from science_tool.cli import main
from science_tool.graph.materialize import materialize_graph
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
            {"id": "question:0001-existing", "kind": "question", "title": "Existing", "status": "open"},
        )

        result = runner.invoke(main, ["entity", "create", "question", "New Question"])

        assert result.exit_code == 0, result.output
        assert "question:0002-new-question" in result.output
        assert Path("entities/questions/0002-new-question.md").is_file()


def test_entity_create_accepts_local_numeric_id_part() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            ["entity", "create", "hypothesis", "Local ID", "--id", "0005-local-id", "--status", "proposed"],
        )

        assert result.exit_code == 0, result.output
        assert "hypothesis:0005-local-id" in result.output
        path = Path("entities/hypotheses/0005-local-id.md")
        assert path.is_file()
        frontmatter = yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])
        assert frontmatter["id"] == "hypothesis:0005-local-id"


def test_entity_create_concept_writes_source() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["entity", "create", "concept", "Treatment Response"])

        assert result.exit_code == 0, result.output
        assert "concept:treatment-response" in result.output
        path = Path("entities/concepts/treatment-response.md")
        assert path.is_file()
        frontmatter = yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])
        assert frontmatter["id"] == "concept:treatment-response"
        assert frontmatter["kind"] == "concept"
        assert frontmatter["title"] == "Treatment Response"
        assert frontmatter["status"] == "active"


def test_entity_create_concept_accepts_deprecated_status_and_rejects_invalid_status() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        deprecated = runner.invoke(
            main,
            ["entity", "create", "concept", "Legacy Concept", "--status", "deprecated"],
        )
        invalid = runner.invoke(
            main,
            ["entity", "create", "concept", "Bad Concept", "--status", "retired"],
        )

        assert deprecated.exit_code == 0, deprecated.output
        path = Path("entities/concepts/legacy-concept.md")
        frontmatter = yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])
        assert frontmatter["status"] == "deprecated"
        assert invalid.exit_code != 0
        assert "Invalid status for concept: retired" in invalid.output


def test_entity_create_concept_loads_and_resolves_in_graph_build() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["entity", "create", "concept", "Treatment Response"])
        assert result.exit_code == 0, result.output
        write_markdown_entity(
            root,
            "entities/hypotheses/h1.md",
            {
                "id": "hypothesis:h1",
                "kind": "hypothesis",
                "title": "H1",
                "status": "proposed",
                "related": ["concept:treatment-response"],
            },
        )

        sources = load_project_sources(root)
        by_id = {entity.canonical_id: entity for entity in sources.entities}
        assert "concept:treatment-response" in by_id
        assert sources.entity_source_adapters["concept:treatment-response"] == "markdown"

        trig_path = materialize_graph(root, strict=False)
        assert trig_path.is_file()


def test_entity_create_mechanism_writes_model_valid_scaffold() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["entity", "create", "mechanism", "Test Mechanism"])

        assert result.exit_code == 0, result.output
        assert "mechanism:0001-test-mechanism" in result.output
        path = Path("entities/mechanisms/0001-test-mechanism.md")
        assert path.is_file()
        frontmatter = yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])
        assert frontmatter["id"] == "mechanism:0001-test-mechanism"
        assert frontmatter["kind"] == "mechanism"
        assert frontmatter["title"] == "Test Mechanism"
        assert frontmatter["summary"] == "Placeholder mechanism summary; replace before relying on this mechanism."
        assert frontmatter["participants"] == [
            "concept:placeholder-participant-a",
            "concept:placeholder-participant-b",
        ]
        assert frontmatter["propositions"] == ["proposition:placeholder-proposition"]


def test_entity_create_and_sections_falsification() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        created = runner.invoke(main, ["entity", "create", "falsification", "Refuted prediction"])
        assert created.exit_code == 0, created.output
        assert Path("entities/falsifications/refuted-prediction.md").is_file()

        sections = runner.invoke(main, ["entity", "sections", "falsification"])
        assert sections.exit_code == 0, sections.output
        assert "What was predicted" in sections.output
        assert "Decision" in sections.output


def test_entity_create_and_sections_story() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        created = runner.invoke(main, ["entity", "create", "story", "The X-Y regulation arc"])
        assert created.exit_code == 0, created.output
        assert Path("entities/stories/the-x-y-regulation-arc.md").is_file()

        sections = runner.invoke(main, ["entity", "sections", "story"])
        assert sections.exit_code == 0, sections.output


def test_entity_create_construct_still_uses_generic_slug_path() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["entity", "create", "construct", "Treatment Response Construct"])

        assert result.exit_code == 0, result.output
        assert "construct:treatment-response-construct" in result.output
        path = Path("entities/constructs/treatment-response-construct.md")
        assert path.is_file()
        frontmatter = yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])
        assert frontmatter["id"] == "construct:treatment-response-construct"
        assert frontmatter["kind"] == "construct"


def test_questions_create_uses_plural_group_and_singular_is_removed() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-existing.md",
            {"id": "question:0001-existing", "kind": "question", "title": "Existing", "status": "active"},
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
            {"id": "hypothesis:0001-alpha", "kind": "hypothesis", "title": "Alpha", "status": "proposed"},
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
            {"id": "question:0001-alpha", "kind": "question", "title": "Alpha", "status": "active"},
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
            {"id": "question:0001-alpha", "kind": "question", "title": "Alpha", "status": "active"},
            "# Alpha\n\n## Summary\n\nBody content.\n",
        )
        write_markdown_entity(
            root,
            "entities/hypotheses/0001-beta.md",
            {"id": "hypothesis:0001-beta", "kind": "hypothesis", "title": "Beta", "status": "proposed"},
        )
        write_markdown_entity(
            root,
            "entities/discussions/0001-gamma.md",
            {
                "id": "discussion:0001-gamma",
                "kind": "discussion",
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
            "entities/questions/q01-alpha.md",
            {"id": "question:q01-alpha", "kind": "question", "title": "Alpha", "status": "active"},
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
            {"id": "question:0001-existing", "kind": "question", "title": "Existing", "status": "open"},
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
            {"id": "question:0001-alpha", "kind": "question", "title": "Alpha", "status": "open"},
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
            {"id": "question:0001-alpha", "kind": "question", "title": "Alpha", "status": "open"},
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
            {"id": "question:0001-alpha", "kind": "question", "title": "Alpha", "status": "open"},
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


def test_entity_remove_dry_run_reports_safe_and_manual_references() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/reports/0001-target-report.md",
            {"id": "report:0001-target-report", "kind": "report", "title": "Target", "status": "complete"},
        )
        write_markdown_entity(
            root,
            "entities/questions/0001-alpha.md",
            {
                "id": "question:0001-alpha",
                "kind": "question",
                "title": "Alpha",
                "status": "open",
                "related": ["report:0001-target-report"],
            },
        )
        task_path = root / "tasks" / "done" / "2026-06.md"
        task_path.parent.mkdir(parents=True)
        task_path.write_text(
            "- archived entities/reports/0001-target-report.md after review\n",
            encoding="utf-8",
        )

        result = runner.invoke(main, ["entity", "remove", "entities/reports/0001-target-report.md"])

        assert result.exit_code == 0, result.output
        assert "DRY RUN" in result.output
        assert "delete entities/reports/0001-target-report.md" in result.output
        assert "safe structured reference" in result.output
        assert "entities/questions/0001-alpha.md" in result.output
        assert "manual reference" in result.output
        assert "tasks/done/2026-06.md" in result.output
        assert Path("entities/reports/0001-target-report.md").is_file()


def test_entity_remove_apply_deletes_file_and_rewrites_safe_frontmatter_refs() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/reports/0001-target-report.md",
            {"id": "report:0001-target-report", "kind": "report", "title": "Target", "status": "complete"},
        )
        dependent = write_markdown_entity(
            root,
            "entities/questions/0001-alpha.md",
            {
                "id": "question:0001-alpha",
                "kind": "question",
                "title": "Alpha",
                "status": "open",
                "related": ["report:0001-target-report", "hypothesis:0001-other"],
                "source_refs": ["report:0001-target-report"],
            },
        )

        result = runner.invoke(main, ["entity", "remove", "report:0001-target-report", "--apply"])

        assert result.exit_code == 0, result.output
        assert "Removed report:0001-target-report" in result.output
        assert not Path("entities/reports/0001-target-report.md").exists()
        frontmatter = yaml.safe_load(dependent.read_text(encoding="utf-8").split("---")[1])
        assert frontmatter["related"] == ["hypothesis:0001-other"]
        assert "source_refs" not in frontmatter


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
                "kind": "question",
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
            {"id": "question:0001-alpha", "kind": "question", "title": "Alpha", "status": "open"},
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
            "entities/questions/q01-alpha.md",
            {"id": "question:q01-alpha", "kind": "question", "title": "Alpha", "status": "open"},
        )
        write_markdown_entity(
            root,
            "entities/questions/q02-beta.md",
            {"id": "question:q02-beta", "kind": "question", "title": "Beta", "status": "answered"},
        )

        result = runner.invoke(
            main, ["entity", "list", "--kind", "question", "--status", "answered", "--format", "json"]
        )

        assert result.exit_code == 0, result.output
        assert "question:q02-beta" in result.output
        assert "question:q01-alpha" not in result.output


def test_entity_list_accepts_positional_kind_filter() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/q01-alpha.md",
            {"id": "question:q01-alpha", "kind": "question", "title": "Alpha", "status": "open"},
        )
        write_markdown_entity(
            root,
            "entities/hypotheses/h01-beta.md",
            {"id": "hypothesis:h01-beta", "kind": "hypothesis", "title": "Beta", "status": "proposed"},
        )

        result = runner.invoke(main, ["entity", "list", "hypothesis", "--format", "json"])

        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)["rows"]
        assert [row["id"] for row in rows] == ["hypothesis:h01-beta"]


def test_entity_list_rejects_conflicting_positional_and_option_kind() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["entity", "list", "hypothesis", "--kind", "question"])

        assert result.exit_code != 0
        assert "positional kind 'hypothesis' conflicts with --kind 'question'" in result.output


def test_entity_list_filters_related_refs_with_alias_resolution() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/hypotheses/h01-anchor.md",
            {
                "id": "hypothesis:h01-anchor",
                "kind": "hypothesis",
                "title": "Anchor",
                "status": "proposed",
                "aliases": ["hypothesis:anchor-alias"],
            },
        )
        write_markdown_entity(
            root,
            "entities/questions/q01-alpha.md",
            {
                "id": "question:q01-alpha",
                "kind": "question",
                "title": "Alpha",
                "status": "open",
                "related": ["hypothesis:anchor-alias"],
            },
        )
        write_markdown_entity(
            root,
            "entities/questions/q02-beta.md",
            {
                "id": "question:q02-beta",
                "kind": "question",
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
    (project / "entities" / "findings").mkdir(parents=True)
    (project / "science.yaml").write_text("id: cli-project\n", encoding="utf-8")
    (project / "entities" / "findings" / "finding.md").write_text(
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
    (project / "entities" / "findings").mkdir(parents=True)
    (project / "science.yaml").write_text("id: cli-output-project\n", encoding="utf-8")
    (project / "entities" / "findings" / "finding.md").write_text(
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


def test_entities_audit_identifiers_emits_json_for_malformed_non_entity_markdown(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "notes").mkdir(parents=True)
    (project / "notes" / "command.md").write_text("---\nrun: [unterminated\n---\n", encoding="utf-8")
    runner = CliRunner()

    audit = runner.invoke(main, ["entities", "audit-identifiers", "--project", str(project)])

    assert audit.exit_code == 0, audit.output
    assert json.loads(audit.output) == {"missing_canonical_ids": [], "invalid_canonical_ids": []}


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
    (project / "entities" / "critiques").mkdir(parents=True)
    (project / "science.yaml").write_text(
        "id: kind-project\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    (project / "entities" / "critiques" / "critique.md").write_text(
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


def test_entities_register_kind_rejects_removed_profiles_config(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "entities" / "critiques").mkdir(parents=True)
    (project / "science.yaml").write_text(
        "id: kind-project\nprofiles: {local: lab}\n",
        encoding="utf-8",
    )
    (project / "entities" / "critiques" / "critique.md").write_text(
        "---\nkind: critique\nid: critique:c001\ntitle: Critique\n---\nBody.\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["entities", "register-kind", "critique", "--class", "epistemic", "--project", str(project)],
    )

    assert result.exit_code != 0
    assert "knowledge_profiles" in result.output
    assert not (project / "knowledge" / "sources" / "lab" / "manifest.yaml").exists()


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
            {"id": "question:0001-existing", "kind": "question", "title": "Existing", "status": "open"},
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


def test_graph_add_question_reports_retirement() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
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

        assert result.exit_code != 0
        assert "graph add question is retired" in result.output
        assert "science questions create" in result.output
        assert "science graph build" in result.output


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
        assert "kind: proposition" in text or 'kind: "proposition"' in text
        assert "## Claim" in text


def test_evidence_lines_create_writes_durable_source() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "evidence-lines",
                "create",
                "Cadence result supports switch proposition",
                "--target",
                "proposition:0001-switch-history",
                "--stance",
                "supports",
                "--source",
                "paper:doe-2026",
                "--strength",
                "moderate",
                "--evidence-type",
                "empirical_data",
                "--independence",
                "independent",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "evidence-line:cadence-result-supports-switch-proposition" in result.output
        path = Path("entities/evidence-lines/cadence-result-supports-switch-proposition.md")
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        frontmatter = yaml.safe_load(text.split("---")[1])
        assert frontmatter["id"] == "evidence-line:cadence-result-supports-switch-proposition"
        assert frontmatter["kind"] == "evidence-line"
        assert frontmatter["target"] == "proposition:0001-switch-history"
        assert frontmatter["stance"] == "supports"
        assert frontmatter["source"] == "paper:doe-2026"
        assert frontmatter["strength"] == "moderate"
        assert frontmatter["evidence_type"] == "empirical_data"
        assert frontmatter["independence"] == "independent"
        assert "# Evidence Line: Cadence result supports switch proposition" in text


def test_evidence_lines_create_requires_target() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "evidence-lines",
                "create",
                "Missing target",
                "--stance",
                "supports",
            ],
        )

        assert result.exit_code != 0
        assert "Missing option '--target'" in result.output


def test_evidence_lines_list_and_show_round_trip() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/evidence-lines/0001-line.md",
            {
                "id": "evidence-line:0001-line",
                "kind": "evidence-line",
                "title": "Line",
                "target": "proposition:0001-target",
                "stance": "supports",
                "status": "active",
            },
            "# Line\n\n## Evidence\n\nObserved support.\n",
        )

        listed = runner.invoke(main, ["evidence-lines", "list", "--format", "json"])
        shown = runner.invoke(main, ["evidence-lines", "show", "0001"])

        assert listed.exit_code == 0, listed.output
        assert [row["id"] for row in json.loads(listed.output)["rows"]] == ["evidence-line:0001-line"]
        assert shown.exit_code == 0, shown.output
        assert "evidence-line:0001-line" in shown.output
        assert "Observed support." in shown.output


def test_graph_add_proposition_reports_retirement() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
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

        assert result.exit_code != 0
        assert "graph add proposition is retired" in result.output
        assert "science propositions create" in result.output
        assert "science graph build" in result.output


def test_graph_add_observation_reports_retirement() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
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

        assert result.exit_code != 0
        assert "graph add observation is retired" in result.output
        assert "science entity create observation" in result.output
        assert "science graph build" in result.output


def test_graph_add_finding_reports_retirement() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
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

        assert result.exit_code != 0
        assert "graph add finding is retired" in result.output
        assert "science entity create finding" in result.output
        assert "science graph build" in result.output


def test_graph_add_evidence_reports_retirement() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
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

        assert result.exit_code != 0
        assert "graph add evidence is retired" in result.output
        assert "science evidence-lines create" in result.output
        assert "science graph build" in result.output


def test_entity_neighbors_source_only_warns_and_returns_no_rows() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-alpha.md",
            {"id": "question:0001-alpha", "kind": "question", "title": "Alpha", "status": "open"},
        )
        graph = Path("knowledge/graph.trig")
        graph.parent.mkdir(parents=True, exist_ok=True)
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
            {"id": "question:0001-alpha", "kind": "question", "title": "Alpha", "status": "open"},
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
            {"id": "question:0001-alpha", "kind": "question", "title": "Alpha", "status": "open"},
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


def test_entity_sections_lists_retired_graph_authoring_templates() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        seed_project(Path.cwd())

        expected = {
            "concept": {"definition", "notes"},
            "observation": {"observation", "source"},
            "mechanism": {"notes"},
        }

        for kind, keys in expected.items():
            result = runner.invoke(main, ["entity", "sections", kind, "--format", "json"])

            assert result.exit_code == 0, result.output
            payload = json.loads(result.output)
            assert {row["key"] for row in payload["rows"]} == keys


def test_entity_sections_non_renderable_kind_gives_actionable_error() -> None:
    """`entity sections topic` reports an actionable error, not a raw template-not-found.

    Regression for fb-2026-06-11-005: topic is a core kind but has no declared
    section template, so the command must name the kinds that do.
    """
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["entity", "sections", "topic"])
        assert result.exit_code != 0
        assert "no inspectable section template" in result.output
        assert "Packaged template not found" not in result.output
        # Names a supported kind so the user knows where sections do work.
        assert "hypothesis" in result.output


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
        result = runner.invoke(main, ["entity", "create", "outcome", "An Outcome"])
        assert result.exit_code == 0, result.output
        # outcome is a non-migrated slug identity kind, so the generic scaffold
        # names it by slug and renders the fixed Summary/Notes body.
        path = Path("entities/outcomes/an-outcome.md")
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        fm = yaml.safe_load(text.split("---")[1])
        assert fm["id"] == "outcome:an-outcome"
        assert fm["kind"] == "outcome"
        assert {"title", "status", "created", "updated"} <= set(fm)
        assert "## Summary" in text
        assert "## Notes" in text


def test_entities_dir_is_discovered_by_graph() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-loadable.md",
            {"id": "question:0001-loadable", "kind": "question", "title": "Loadable", "status": "active"},
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
            {"id": "question:0005-granularity", "kind": "question", "title": "Granularity", "status": "active"},
        )
        result = runner.invoke(main, ["entity", "show", "q5"])
        assert result.exit_code == 0, result.output
        assert "question:0005-granularity" in result.output
