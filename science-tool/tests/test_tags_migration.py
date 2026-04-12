"""Tests for tags→related physical migration of on-disk files."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from science_tool.cli import main
from science_tool.graph.tags_migration import (
    migrate_tags_to_related,
    rewrite_frontmatter,
)


def _entity_md(tags: str | None, related: str | None = None) -> str:
    lines = [
        "---",
        'id: "hypothesis:h01-test"',
        'type: "hypothesis"',
        'title: "Test"',
        'status: "proposed"',
    ]
    if tags is not None:
        lines.append(f"tags: [{tags}]")
    if related is not None:
        lines.append(f"related: [{related}]")
    lines.append('created: "2026-03-01"')
    lines.append("---")
    lines.append("")
    lines.append("Body text.")
    return "\n".join(lines) + "\n"


class TestRewriteFrontmatter:
    def test_merges_tags_into_existing_related(self) -> None:
        text = _entity_md(tags="genomics, ml", related='"question:q01"')
        new_text, migration = rewrite_frontmatter(text)
        assert migration is not None
        assert migration.tag_values == ["genomics", "ml"]
        assert migration.added_to_related == ["topic:genomics", "topic:ml"]
        assert "tags:" not in new_text
        # Quotes are normalized away — refs appear unquoted after merge
        assert "related: [question:q01, topic:genomics, topic:ml]" in new_text

    def test_creates_related_when_missing(self) -> None:
        text = _entity_md(tags="genomics")
        new_text, migration = rewrite_frontmatter(text)
        assert migration is not None
        assert "tags:" not in new_text
        assert "related: [topic:genomics]" in new_text

    def test_dedups_against_existing_topic_ref(self) -> None:
        text = _entity_md(tags="genomics", related="topic:genomics")
        new_text, migration = rewrite_frontmatter(text)
        assert migration is not None
        # No new addition since it's already there
        assert migration.added_to_related == []
        assert "tags:" not in new_text
        # related should remain as-is
        assert "related: [topic:genomics]" in new_text

    def test_preserves_typed_refs_in_tags(self) -> None:
        """A tag value with a colon is treated as an already-typed reference."""
        text = _entity_md(tags="hypothesis:h02")
        new_text, _ = rewrite_frontmatter(text)
        assert "related: [hypothesis:h02]" in new_text

    def test_strips_quotes_from_tag_values(self) -> None:
        """YAML list items with surrounding quotes should be unquoted so that
        `tags: ["chromatin-3d"]` becomes `topic:chromatin-3d`, not `topic:"chromatin-3d"`."""
        text = _entity_md(tags='"chromatin-3d", "hi-c"')
        new_text, migration = rewrite_frontmatter(text)
        assert migration is not None
        assert migration.tag_values == ["chromatin-3d", "hi-c"]
        assert "related: [topic:chromatin-3d, topic:hi-c]" in new_text
        assert '"' not in new_text.split("related:")[1].split("]")[0]

    def test_empty_tags_just_removed(self) -> None:
        text = _entity_md(tags="", related='"question:q01"')
        new_text, migration = rewrite_frontmatter(text)
        assert migration is not None
        assert migration.tag_values == []
        assert "tags:" not in new_text
        # Existing related is preserved (no new refs to merge since tags was empty)
        assert "question:q01" in new_text

    def test_no_tags_line_is_noop(self) -> None:
        text = _entity_md(tags=None, related='"question:q01"')
        new_text, migration = rewrite_frontmatter(text)
        assert migration is None
        assert new_text == text

    def test_no_frontmatter_is_noop(self) -> None:
        text = "# Just markdown\n\nNo frontmatter here.\n"
        new_text, migration = rewrite_frontmatter(text)
        assert migration is None
        assert new_text == text


class TestMigrateTagsToRelated:
    def _write_project(self, root: Path) -> None:
        (root / "science.yaml").write_text("name: test\n")
        doc_dir = root / "doc" / "hypotheses"
        doc_dir.mkdir(parents=True)
        (doc_dir / "h01.md").write_text(_entity_md(tags="genomics, ml"))
        (doc_dir / "h02.md").write_text(_entity_md(tags=None, related='"question:q01"'))

    def test_dry_run_reports_without_writing(self, tmp_path: Path) -> None:
        self._write_project(tmp_path)
        h01_before = (tmp_path / "doc/hypotheses/h01.md").read_text()

        report = migrate_tags_to_related(tmp_path, apply=False)

        assert report.applied is False
        assert len(report.entity_files) == 1
        assert report.entity_files[0].path.name == "h01.md"
        assert report.entity_files[0].tag_values == ["genomics", "ml"]
        # File untouched
        assert (tmp_path / "doc/hypotheses/h01.md").read_text() == h01_before

    def test_apply_writes_changes(self, tmp_path: Path) -> None:
        self._write_project(tmp_path)

        report = migrate_tags_to_related(tmp_path, apply=True)

        assert report.applied is True
        h01_text = (tmp_path / "doc/hypotheses/h01.md").read_text()
        assert "tags:" not in h01_text
        assert "topic:genomics" in h01_text
        assert "topic:ml" in h01_text
        # h02 has no tags, so unchanged
        assert len(report.entity_files) == 1

    def test_is_idempotent(self, tmp_path: Path) -> None:
        self._write_project(tmp_path)
        migrate_tags_to_related(tmp_path, apply=True)
        h01_first = (tmp_path / "doc/hypotheses/h01.md").read_text()

        report2 = migrate_tags_to_related(tmp_path, apply=True)
        h01_second = (tmp_path / "doc/hypotheses/h01.md").read_text()

        assert report2.entity_files == []
        assert h01_first == h01_second

    def test_migrates_task_files(self, tmp_path: Path) -> None:
        (tmp_path / "science.yaml").write_text("name: test\n")
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "active.md").write_text(
            "## [t001] Legacy task\n"
            "- type: dev\n"
            "- priority: P2\n"
            "- status: proposed\n"
            "- tags: [lens-system, umap]\n"
            "- created: 2026-04-01\n"
            "\n"
            "A task with legacy tags.\n"
        )

        report = migrate_tags_to_related(tmp_path, apply=True)

        assert len(report.task_files) == 1
        new_text = (tasks_dir / "active.md").read_text()
        assert "- tags:" not in new_text
        assert "topic:lens-system" in new_text
        assert "topic:umap" in new_text

    def test_handles_missing_directories(self, tmp_path: Path) -> None:
        (tmp_path / "science.yaml").write_text("name: test\n")
        # No doc/, specs/, or tasks/ directories
        report = migrate_tags_to_related(tmp_path, apply=True)
        assert report.entity_files == []
        assert report.task_files == []
        assert report.errors == []

    def test_migrated_entity_file_parses_correctly(self, tmp_path: Path) -> None:
        """After migration, the file should still parse via parse_entity_file, with
        tag values surfacing in entity.related as topic: refs."""
        from science_model.frontmatter import parse_entity_file

        (tmp_path / "science.yaml").write_text("name: test\n")
        doc_dir = tmp_path / "doc" / "hypotheses"
        doc_dir.mkdir(parents=True)
        md_path = doc_dir / "h01.md"
        md_path.write_text(_entity_md(tags="genomics, ml", related='"question:q01"'))

        migrate_tags_to_related(tmp_path, apply=True)

        entity = parse_entity_file(md_path, "test")
        assert entity is not None
        assert "topic:genomics" in entity.related
        assert "topic:ml" in entity.related
        assert "question:q01" in entity.related


class TestCLI:
    def test_dry_run_default(self, tmp_path: Path) -> None:
        (tmp_path / "science.yaml").write_text("name: test\n")
        doc = tmp_path / "doc" / "hypotheses"
        doc.mkdir(parents=True)
        md = doc / "h01.md"
        md.write_text(_entity_md(tags="genomics"))
        original = md.read_text()

        runner = CliRunner()
        result = runner.invoke(main, ["graph", "migrate-tags", "--project-root", str(tmp_path)])

        assert result.exit_code == 0
        assert "Would migrate" in result.output
        assert "Re-run with --apply" in result.output
        # File unchanged
        assert md.read_text() == original

    def test_apply_writes(self, tmp_path: Path) -> None:
        (tmp_path / "science.yaml").write_text("name: test\n")
        doc = tmp_path / "doc" / "hypotheses"
        doc.mkdir(parents=True)
        md = doc / "h01.md"
        md.write_text(_entity_md(tags="genomics"))

        runner = CliRunner()
        result = runner.invoke(
            main, ["graph", "migrate-tags", "--project-root", str(tmp_path), "--apply"]
        )

        assert result.exit_code == 0
        assert "Migrated 1 file" in result.output
        assert "tags:" not in md.read_text()
        assert "topic:genomics" in md.read_text()

    def test_no_changes_message(self, tmp_path: Path) -> None:
        (tmp_path / "science.yaml").write_text("name: test\n")
        doc = tmp_path / "doc" / "hypotheses"
        doc.mkdir(parents=True)
        (doc / "h01.md").write_text(_entity_md(tags=None, related='"question:q01"'))

        runner = CliRunner()
        result = runner.invoke(main, ["graph", "migrate-tags", "--project-root", str(tmp_path)])

        assert result.exit_code == 0
        assert "No legacy tags found" in result.output
