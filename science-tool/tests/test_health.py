"""Tests for the science-tool health command and its component checks."""

from __future__ import annotations

from pathlib import Path


class TestCollectUnresolvedRefs:
    def test_groups_by_target_with_mention_counts(self, tmp_path: Path) -> None:
        from science_tool.graph.health import collect_unresolved_refs

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "specs" / "hypotheses"
        spec.mkdir(parents=True)
        # Two hypotheses both reference topic:foo (which doesn't exist)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\nrelated: [topic:foo]\nsource_refs: []\n'
            'created: "2026-04-13"\n---\nBody.\n'
        )
        (spec / "h02.md").write_text(
            '---\nid: "hypothesis:h02"\ntype: "hypothesis"\ntitle: "H2"\n'
            'status: "proposed"\nrelated: [topic:foo, topic:bar]\nsource_refs: []\n'
            'created: "2026-04-13"\n---\nBody.\n'
        )

        unresolved = collect_unresolved_refs(tmp_path)

        # Sorted by mention count desc
        assert unresolved[0]["target"] == "topic:foo"
        assert unresolved[0]["mention_count"] == 2
        assert sorted(unresolved[0]["sources"]) == ["hypothesis:h01", "hypothesis:h02"]
        assert unresolved[1]["target"] == "topic:bar"
        assert unresolved[1]["mention_count"] == 1
        assert unresolved[1]["sources"] == ["hypothesis:h02"]

    def test_meta_refs_not_reported_as_unresolved(self, tmp_path: Path) -> None:
        from science_tool.graph.health import collect_unresolved_refs

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "specs" / "hypotheses"
        spec.mkdir(parents=True)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\nrelated: [meta:phase3b]\nsource_refs: []\n'
            'created: "2026-04-13"\n---\nBody.\n'
        )

        unresolved = collect_unresolved_refs(tmp_path)
        assert unresolved == []

    def test_looks_like_heuristic_for_task_ids(self, tmp_path: Path) -> None:
        from science_tool.graph.health import collect_unresolved_refs

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "specs" / "hypotheses"
        spec.mkdir(parents=True)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\nrelated: [topic:t143]\nsource_refs: []\n'
            'created: "2026-04-13"\n---\nBody.\n'
        )

        unresolved = collect_unresolved_refs(tmp_path)
        assert unresolved[0]["target"] == "topic:t143"
        assert unresolved[0]["looks_like"] == "task"


class TestCollectLingeringTags:
    def test_finds_tags_lines_in_entity_files(self, tmp_path: Path) -> None:
        from science_tool.graph.health import collect_lingering_tags

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "specs" / "hypotheses"
        spec.mkdir(parents=True)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\ntags: [legacy-tag]\nrelated: []\n'
            'source_refs: []\ncreated: "2026-04-13"\n---\nBody.\n'
        )
        (spec / "h02.md").write_text(  # No tags line
            '---\nid: "hypothesis:h02"\ntype: "hypothesis"\ntitle: "H2"\n'
            'status: "proposed"\nrelated: []\nsource_refs: []\n'
            'created: "2026-04-13"\n---\nBody.\n'
        )

        results = collect_lingering_tags(tmp_path)

        assert len(results) == 1
        assert results[0]["file"].endswith("h01.md")
        assert results[0]["values"] == ["legacy-tag"]

    def test_finds_tags_lines_in_task_files(self, tmp_path: Path) -> None:
        from science_tool.graph.health import collect_lingering_tags

        (tmp_path / "science.yaml").write_text("name: test\n")
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "active.md").write_text(
            "## [t001] Task\n"
            "- type: dev\n"
            "- priority: P1\n"
            "- status: active\n"
            "- tags: [foo, bar]\n"
            "- created: 2026-04-13\n"
            "\nDesc.\n"
        )

        results = collect_lingering_tags(tmp_path)

        assert len(results) == 1
        assert results[0]["file"].endswith("active.md")
        assert results[0]["values"] == ["foo", "bar"]


class TestBuildHealthReport:
    def test_aggregates_all_checks(self, tmp_path: Path) -> None:
        from science_tool.graph.health import build_health_report

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "specs" / "hypotheses"
        spec.mkdir(parents=True)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\ntags: [legacy]\nrelated: [topic:foo]\n'
            'source_refs: []\ncreated: "2026-04-13"\n---\nBody.\n'
        )

        report = build_health_report(tmp_path)

        assert "unresolved_refs" in report
        assert "lingering_tags_lines" in report
        assert len(report["unresolved_refs"]) >= 1
        assert len(report["lingering_tags_lines"]) >= 1

    def test_empty_project_has_clean_report(self, tmp_path: Path) -> None:
        from science_tool.graph.health import build_health_report

        (tmp_path / "science.yaml").write_text("name: test\n")
        report = build_health_report(tmp_path)

        assert report["unresolved_refs"] == []
        assert report["lingering_tags_lines"] == []


class TestHealthCLI:
    def test_table_output_default(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "specs" / "hypotheses"
        spec.mkdir(parents=True)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\nrelated: [topic:missing]\n'
            'source_refs: []\ncreated: "2026-04-13"\n---\nBody.\n'
        )

        runner = CliRunner()
        result = runner.invoke(main, ["health", "--project-root", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert "topic:missing" in result.output

    def test_json_output(self, tmp_path: Path) -> None:
        import json
        from click.testing import CliRunner
        from science_tool.cli import main

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "specs" / "hypotheses"
        spec.mkdir(parents=True)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\nrelated: [topic:missing]\n'
            'source_refs: []\ncreated: "2026-04-13"\n---\nBody.\n'
        )

        runner = CliRunner()
        result = runner.invoke(
            main, ["health", "--project-root", str(tmp_path), "--format", "json"]
        )

        assert result.exit_code == 0, result.output
        report = json.loads(result.output)
        assert "unresolved_refs" in report
        assert report["unresolved_refs"][0]["target"] == "topic:missing"

    def test_clean_project_exits_zero(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        (tmp_path / "science.yaml").write_text("name: test\n")
        runner = CliRunner()
        result = runner.invoke(main, ["health", "--project-root", str(tmp_path)])

        assert result.exit_code == 0
        assert "no issues" in result.output.lower() or "clean" in result.output.lower()
