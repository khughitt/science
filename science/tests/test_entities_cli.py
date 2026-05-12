from __future__ import annotations

import json
import os
from pathlib import Path

from click.testing import CliRunner
import yaml

from _fixtures.entity_helpers import seed_project, write_markdown_entity
from science_model.contracts.inventory_v1 import InventoryPayload
from science_model.entities import EntityClass
from science_tool.cli import main
from science_tool.graph.sources import load_project_sources


def test_entity_create_question_writes_source() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "doc/questions/q01-existing.md",
            {"id": "question:q01-existing", "type": "question", "title": "Existing", "status": "open"},
        )

        result = runner.invoke(main, ["entity", "create", "question", "New Question"])

        assert result.exit_code == 0, result.output
        assert "question:q02-new-question" in result.output
        assert Path("doc/questions/q02-new-question.md").is_file()


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
                "--id",
                "theme:transportability-across-cancer-types",
            ],
        )

        assert result.exit_code == 0, result.output
        path = Path("doc/themes/transportability-across-cancer-types.md")
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "theme:transportability-across-cancer-types" in text
        assert "## Definition" in text


def test_entity_create_with_unresolved_related_prints_warning() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "doc/questions/q01-existing.md",
            {"id": "question:q01-existing", "type": "question", "title": "Existing", "status": "open"},
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
            "doc/questions/q01-alpha.md",
            {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"},
        )

        result = runner.invoke(main, ["entity", "show", "q01"])

        assert result.exit_code == 0, result.output
        assert "question:q01-alpha" in result.output
        assert "Alpha" in result.output


def test_entity_show_emits_body_content() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "doc/questions/q01-alpha.md",
            {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"},
            "# Alpha\n\n## Summary\n\nBody content.\n",
        )

        result = runner.invoke(main, ["entity", "show", "q01"])

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
            "doc/questions/q01-alpha.md",
            {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"},
        )

        result = runner.invoke(main, ["entity", "show", "q01", "--format", "json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload == {
            "id": "question:q01-alpha",
            "kind": "question",
            "title": "Alpha",
            "status": "open",
            "path": "doc/questions/q01-alpha.md",
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
            "doc/questions/q01-alpha.md",
            {
                "id": "question:q01-alpha",
                "type": "question",
                "title": "Alpha",
                "status": "open",
                "related": ["hypothesis:h01"],
            },
        )

        result = runner.invoke(main, ["entity", "edit", "q01", "--related", "hypothesis:h02"])

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
            "doc/questions/q01-alpha.md",
            {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"},
            "# Alpha\n",
        )

        result = runner.invoke(main, ["entity", "note", "q01", "Clarified.", "--date", "2026-04-28"])

        assert result.exit_code == 0, result.output
        assert "Added note to question:q01-alpha (2026-04-28)" in result.output
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
    payload = InventoryPayload.model_validate_json(result.output)
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
    payload = InventoryPayload.model_validate_json(output.read_text(encoding="utf-8"))
    assert payload.project_id == "cli-output-project"
    assert payload.entities[0].id == "finding:f001"


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
    assert "core entity kind" in result.output
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
            "doc/questions/q01-existing.md",
            {"id": "question:q01-existing", "type": "question", "title": "Existing", "status": "open"},
        )

        result = runner.invoke(main, ["question", "create", "Wrapper Question", "--slug", "wrapper"])

        assert result.exit_code == 0, result.output
        assert "question:q02-wrapper" in result.output
        assert Path("doc/questions/q02-wrapper.md").is_file()


def test_discussion_focus_maps_to_related() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "discussion",
                "create",
                "Planning",
                "--id",
                "discussion:2026-04-28-planning",
                "--focus",
                "question:q01-alpha",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "question:q01-alpha" in Path("doc/discussions/2026-04-28-planning.md").read_text(encoding="utf-8")


def test_interpretation_input_maps_to_source_refs() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "interpretation",
                "create",
                "Result",
                "--id",
                "interpretation:2026-04-28-result",
                "--input",
                "results/run-1",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "results/run-1" in Path("doc/interpretations/2026-04-28-result.md").read_text(encoding="utf-8")


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
                "proposition",
                "create",
                "Cadence shapes recovered switch history",
                "--id",
                "proposition:p01-cadence-shapes-switch-history",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "proposition:p01-cadence-shapes-switch-history" in result.output
        path = Path("specs/propositions/p01-cadence-shapes-switch-history.md")
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
        assert "proposition create" in result.output


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
            "doc/questions/q01-alpha.md",
            {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"},
        )
        graph = Path("knowledge/graph.trig")
        graph.parent.mkdir(parents=True)
        graph.write_text("@prefix sci: <http://example.org/science/vocab/> .\n", encoding="utf-8")
        os.utime(graph, (1, 1))
        os.utime(Path("doc/questions/q01-alpha.md"), (2, 2))

        result = runner.invoke(main, ["entity", "neighbors", "question:q01-alpha", "--format", "json"])

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
            "doc/questions/q01-alpha.md",
            {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"},
        )

        result = runner.invoke(main, ["entity", "neighbors", "question:q01-alpha"])

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
            "doc/questions/q01-alpha.md",
            {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"},
            "# Alpha\n",
        )

        result = runner.invoke(main, ["entity", "note", "q01", "Clarified."])

        assert result.exit_code == 0, result.output
        assert f"Added note to question:q01-alpha ({date.today().isoformat()})" in result.output


def test_discussion_create_without_id_uses_today() -> None:
    from datetime import date

    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["discussion", "create", "Planning"])

        assert result.exit_code == 0, result.output
        today = date.today().isoformat()
        assert f"discussion:{today}-planning" in result.output
        assert Path(f"doc/discussions/{today}-planning.md").is_file()


def test_discussion_create_with_optional_section_includes_addendum() -> None:
    from datetime import date

    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["discussion", "create", "Test discussion", "--with", "double-blind-addendum"])

        assert result.exit_code == 0, result.output
        today = date.today().isoformat()
        path = Path(f"doc/discussions/{today}-test-discussion.md")
        assert path.is_file()
        assert "## Double-Blind Addendum" in path.read_text(encoding="utf-8")


def test_discussion_create_no_hints_strips_html_comments() -> None:
    from datetime import date

    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["discussion", "create", "Test discussion", "--no-hints"])

        assert result.exit_code == 0, result.output
        today = date.today().isoformat()
        path = Path(f"doc/discussions/{today}-test-discussion.md")
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

        result = runner.invoke(main, ["discussion", "create", "Test discussion", "--with", "bogus"])

        assert result.exit_code != 0
        assert "bogus" in result.output
        assert "double-blind-addendum" in result.output
