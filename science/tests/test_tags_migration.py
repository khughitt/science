"""Tests for tags→related physical migration of on-disk files."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from science_tool.cli import main
from science_tool.graph.tags_migration import (
    migrate_tags_to_related,
    rewrite_frontmatter,
    rewrite_task_file,
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
        # Default is meta: (safe, no KG pollution)
        assert migration.added_to_related == ["meta:genomics", "meta:ml"]
        assert "tags:" not in new_text
        # Quotes are normalized away — refs appear unquoted after merge
        assert "related: [question:q01, meta:genomics, meta:ml]" in new_text

    def test_creates_related_when_missing(self) -> None:
        text = _entity_md(tags="genomics")
        new_text, migration = rewrite_frontmatter(text)
        assert migration is not None
        assert "tags:" not in new_text
        assert "related: [meta:genomics]" in new_text

    def test_dedups_against_existing_meta_ref(self) -> None:
        text = _entity_md(tags="genomics", related="meta:genomics")
        new_text, migration = rewrite_frontmatter(text)
        assert migration is not None
        # No new addition since it's already there
        assert migration.added_to_related == []
        assert "tags:" not in new_text
        # related should remain as-is
        assert "related: [meta:genomics]" in new_text

    def test_preserves_typed_refs_in_tags(self) -> None:
        """A tag value with a colon is treated as an already-typed reference."""
        text = _entity_md(tags="hypothesis:h02")
        new_text, _ = rewrite_frontmatter(text)
        assert "related: [hypothesis:h02]" in new_text

    def test_strips_quotes_from_tag_values(self) -> None:
        """YAML list items with surrounding quotes should be unquoted so that
        `tags: ["chromatin-3d"]` becomes `meta:chromatin-3d`, not `meta:"chromatin-3d"`."""
        text = _entity_md(tags='"chromatin-3d", "hi-c"')
        new_text, migration = rewrite_frontmatter(text)
        assert migration is not None
        assert migration.tag_values == ["chromatin-3d", "hi-c"]
        assert "related: [meta:chromatin-3d, meta:hi-c]" in new_text
        assert '"' not in new_text.split("related:")[1].split("]")[0]

    def test_as_topic_flag_uses_topic_prefix(self) -> None:
        """When as_topic=True, tags become topic: refs (legacy behavior)."""
        text = _entity_md(tags="genomics")
        new_text, migration = rewrite_frontmatter(text, as_topic=True)
        assert migration is not None
        assert "related: [topic:genomics]" in new_text

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


class TestRewriteFrontmatterBlockForm:
    """Block-form `related:` (multi-line list) must merge tags in-place, not
    append a duplicate key — see regression in tags_migration.py."""

    def _entity_md_block_related(self, tags: str, block_items: list[str]) -> str:
        """Build a doc with tags: plus a block-form related: list."""
        lines = [
            "---",
            'id: "hypothesis:h01-test"',
            'type: "hypothesis"',
            'title: "Test"',
            'status: "proposed"',
            f"tags: [{tags}]",
            "related:",
        ]
        lines.extend(f'  - "{ref}"' for ref in block_items)
        lines.extend(['created: "2026-03-01"', "---", "", "Body text."])
        return "\n".join(lines) + "\n"

    def test_merges_into_block_form_related(self) -> None:
        text = self._entity_md_block_related(tags="genomics, ml", block_items=["question:q01", "task:t001"])
        new_text, migration = rewrite_frontmatter(text)
        assert migration is not None
        assert migration.added_to_related == ["meta:genomics", "meta:ml"]
        # Exactly one `related:` key — no duplicate
        assert new_text.count("\nrelated:") == 1
        # Existing block items preserved
        assert '  - "question:q01"' in new_text
        assert '  - "task:t001"' in new_text
        # New items appended in block form
        assert '  - "meta:genomics"' in new_text
        assert '  - "meta:ml"' in new_text
        # YAML parses cleanly — no stray keys
        import yaml

        fm = new_text.split("---\n", 2)[1]
        parsed = yaml.safe_load(fm)
        assert parsed["related"] == [
            "question:q01",
            "task:t001",
            "meta:genomics",
            "meta:ml",
        ]
        assert "tags" not in parsed

    def test_block_form_dedups_existing_refs(self) -> None:
        text = self._entity_md_block_related(tags="genomics", block_items=["meta:genomics", "question:q01"])
        new_text, migration = rewrite_frontmatter(text)
        assert migration is not None
        assert migration.added_to_related == []  # Already present
        assert new_text.count("meta:genomics") == 1
        assert new_text.count("\nrelated:") == 1

    def test_block_form_as_topic(self) -> None:
        text = self._entity_md_block_related(tags="genomics", block_items=["question:q01"])
        new_text, migration = rewrite_frontmatter(text, as_topic=True)
        assert migration is not None
        assert '  - "topic:genomics"' in new_text
        assert new_text.count("\nrelated:") == 1


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
        assert "meta:genomics" in h01_text
        assert "meta:ml" in h01_text
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
        assert "meta:lens-system" in new_text
        assert "meta:umap" in new_text


class TestRewriteTaskFile:
    def test_preserves_header_and_unknown_fields(self) -> None:
        """The migration must preserve the file header and any custom fields that
        aren't recognized by the task parser (e.g. `- depends-on:`)."""
        text = (
            "# Active Tasks\n"
            "\n"
            "## [t001] Legacy task\n"
            "- type: dev\n"
            "- priority: P2\n"
            "- status: proposed\n"
            "- related: [hypothesis:h01]\n"
            "- depends-on: [task:t002]\n"
            "- tags: [lens-system, umap]\n"
            "- created: 2026-04-01\n"
            "\n"
            "Task description.\n"
        )
        new_text, added = rewrite_task_file(text)
        # Header preserved
        assert new_text.startswith("# Active Tasks\n")
        # Unknown field preserved verbatim
        assert "- depends-on: [task:t002]" in new_text
        # Tags line removed
        assert "- tags:" not in new_text
        # Tags merged into existing related
        assert "- related: [hypothesis:h01, meta:lens-system, meta:umap]" in new_text
        # Description preserved
        assert "Task description." in new_text
        assert added == [["meta:lens-system", "meta:umap"]]

    def test_creates_related_when_missing_in_task(self) -> None:
        text = (
            "## [t001] Task\n"
            "- type: dev\n"
            "- priority: P2\n"
            "- status: proposed\n"
            "- tags: [foo]\n"
            "- created: 2026-04-01\n"
            "\n"
            "Desc.\n"
        )
        new_text, _ = rewrite_task_file(text)
        assert "- tags:" not in new_text
        assert "- related: [meta:foo]" in new_text

    def test_as_topic_flag_in_task_file(self) -> None:
        text = (
            "## [t001] Task\n- type: dev\n- priority: P1\n- status: active\n"
            "- tags: [foo]\n- created: 2026-04-13\n\nDesc.\n"
        )
        new_text, _ = rewrite_task_file(text, as_topic=True)
        assert "- related: [topic:foo]" in new_text

    def test_multiple_task_blocks_independent(self) -> None:
        """Each task block's tags merge only into its own related line."""
        text = (
            "## [t001] First\n"
            "- type: dev\n"
            "- priority: P1\n"
            "- status: active\n"
            "- related: [hypothesis:h01]\n"
            "- tags: [foo]\n"
            "- created: 2026-04-01\n"
            "\n"
            "Desc 1.\n"
            "\n"
            "## [t002] Second\n"
            "- type: dev\n"
            "- priority: P2\n"
            "- status: proposed\n"
            "- related: [hypothesis:h02]\n"
            "- tags: [bar]\n"
            "- created: 2026-04-02\n"
            "\n"
            "Desc 2.\n"
        )
        new_text, added = rewrite_task_file(text)
        assert new_text.count("- tags:") == 0
        # t001 gets meta:foo merged, not meta:bar
        assert "- related: [hypothesis:h01, meta:foo]" in new_text
        assert "- related: [hypothesis:h02, meta:bar]" in new_text
        assert len(added) == 2

    def test_no_tags_is_noop(self) -> None:
        text = (
            "## [t001] Task\n"
            "- type: dev\n"
            "- priority: P2\n"
            "- status: proposed\n"
            "- related: [hypothesis:h01]\n"
            "- created: 2026-04-01\n"
            "\n"
            "Desc.\n"
        )
        new_text, added = rewrite_task_file(text)
        assert new_text == text
        assert added == []

    def test_handles_missing_directories(self, tmp_path: Path) -> None:
        (tmp_path / "science.yaml").write_text("name: test\n")
        # No doc/, specs/, or tasks/ directories
        report = migrate_tags_to_related(tmp_path, apply=True)
        assert report.entity_files == []
        assert report.task_files == []
        assert report.errors == []

    def test_migrated_entity_file_parses_correctly(self, tmp_path: Path) -> None:
        """After migration, the file should still parse via parse_entity_file, with
        tag values surfacing in entity.related as meta: refs (default)."""
        from science_model.frontmatter import parse_entity_file

        (tmp_path / "science.yaml").write_text("name: test\n")
        doc_dir = tmp_path / "doc" / "hypotheses"
        doc_dir.mkdir(parents=True)
        md_path = doc_dir / "h01.md"
        md_path.write_text(_entity_md(tags="genomics, ml", related='"question:q01"'))

        migrate_tags_to_related(tmp_path, apply=True)

        entity = parse_entity_file(md_path, "test")
        assert entity is not None
        assert "meta:genomics" in entity.related
        assert "meta:ml" in entity.related
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
        result = runner.invoke(main, ["graph", "migrate-tags", "--project-root", str(tmp_path), "--apply"])

        assert result.exit_code == 0
        assert "Migrated 1 file" in result.output
        assert "tags:" not in md.read_text()
        assert "meta:genomics" in md.read_text()

    def test_no_changes_message(self, tmp_path: Path) -> None:
        (tmp_path / "science.yaml").write_text("name: test\n")
        doc = tmp_path / "doc" / "hypotheses"
        doc.mkdir(parents=True)
        (doc / "h01.md").write_text(_entity_md(tags=None, related='"question:q01"'))

        runner = CliRunner()
        result = runner.invoke(main, ["graph", "migrate-tags", "--project-root", str(tmp_path)])

        assert result.exit_code == 0
        assert "No legacy tags found" in result.output

    def test_as_topic_cli_flag(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        (tmp_path / "science.yaml").write_text("name: test\n")
        doc = tmp_path / "doc" / "hypotheses"
        doc.mkdir(parents=True)
        md = doc / "h01.md"
        md.write_text(_entity_md(tags="genomics"))

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["graph", "migrate-tags", "--project-root", str(tmp_path), "--apply", "--as-topic"],
        )

        assert result.exit_code == 0
        assert "topic:genomics" in md.read_text()
