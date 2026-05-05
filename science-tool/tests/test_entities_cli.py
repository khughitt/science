from __future__ import annotations

import json
import os
from pathlib import Path

from click.testing import CliRunner

from _fixtures.entity_helpers import seed_project, write_markdown_entity
from science_tool.cli import main


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
        assert "WARNING" in result.output
        assert "[]" in result.output


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


def test_discussion_create_unknown_section_key_errors() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["discussion", "create", "Test discussion", "--with", "bogus"])

        assert result.exit_code != 0
        assert "bogus" in result.output
        assert "double-blind-addendum" in result.output
