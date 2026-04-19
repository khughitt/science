"""Tests for cross-reference validation (science-tool refs check)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.refs import check_refs


def _scaffold(root: Path) -> None:
    """Create a minimal project scaffold for testing."""
    (root / "specs" / "hypotheses").mkdir(parents=True)
    (root / "doc" / "background" / "topics").mkdir(parents=True)
    (root / "doc" / "background" / "papers").mkdir(parents=True)
    (root / "doc" / "questions").mkdir(parents=True)
    (root / "papers").mkdir(parents=True)

    # Create hypothesis file
    (root / "specs" / "hypotheses" / "h01-test.md").write_text("# Hypothesis H01\nStatus: proposed\n")
    # Create bib file
    (root / "papers" / "references.bib").write_text(
        "% references.bib\n@article{Smith2024,\n  title={Test},\n  author={Smith},\n  year={2024}\n}\n"
    )
    # Create RESEARCH_PLAN.md
    (root / "RESEARCH_PLAN.md").write_text("# Research Plan\n")


def test_valid_hypothesis_ref() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text("# Test\nThis relates to H01 strongly.\n")
        issues = check_refs(root)
        hyp_issues = [i for i in issues if i.ref_type == "hypothesis"]
        assert len(hyp_issues) == 0


def test_broken_hypothesis_ref() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nThis relates to H03 which doesn't exist.\n"
        )
        issues = check_refs(root)
        hyp_issues = [i for i in issues if i.ref_type == "hypothesis"]
        assert len(hyp_issues) == 1
        assert hyp_issues[0].ref_value == "H03"


def test_hypothesis_ref_in_own_file_ignored() -> None:
    """H01 referenced inside h01-test.md should not be flagged."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "specs" / "hypotheses" / "h01-test.md").write_text("# Hypothesis H01\nH01 is about testing.\n")
        issues = check_refs(root)
        hyp_issues = [i for i in issues if i.ref_type == "hypothesis"]
        assert len(hyp_issues) == 0


def test_slug_named_hypothesis_file_resolves_legacy_h_alias_and_self_reference() -> None:
    """Slug-based files with canonical frontmatter IDs should still resolve HNN aliases."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        legacy = root / "specs" / "hypotheses" / "h01-test.md"
        legacy.unlink()
        (root / "specs" / "hypotheses" / "higher-order-topology.md").write_text(
            "---\n"
            "id: hypothesis:h03-higher-order-topology\n"
            "type: hypothesis\n"
            "title: Higher-order topology\n"
            "---\n\n"
            "# H03: Higher-order topology\n\n"
            "H03 remains under evaluation.\n"
        )
        (root / "doc" / "background" / "topics" / "test.md").write_text("# Test\nThis relates to H03 strongly.\n")

        issues = check_refs(root)
        hyp_issues = [i for i in issues if i.ref_type == "hypothesis"]
        assert hyp_issues == []


def test_slug_named_hypothesis_file_uses_heading_alias_for_self_reference() -> None:
    """A slug-only hypothesis file should not flag its own HNN heading label in prose."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        legacy = root / "specs" / "hypotheses" / "h01-test.md"
        legacy.unlink()
        (root / "specs" / "hypotheses" / "higher-order-topology.md").write_text(
            "---\n"
            "id: hypothesis:higher-order-topology\n"
            "type: hypothesis\n"
            "title: Higher-order topology\n"
            "---\n\n"
            "# H03: Higher-order topology\n\n"
            "H03 remains under evaluation.\n"
        )

        issues = check_refs(root)
        hyp_issues = [i for i in issues if i.ref_type == "hypothesis"]
        assert hyp_issues == []


def test_valid_citation_ref() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nAs shown by [@Smith2024], this works.\n"
        )
        issues = check_refs(root)
        cite_issues = [i for i in issues if i.ref_type == "citation"]
        assert len(cite_issues) == 0


def test_broken_citation_ref() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nAs shown by [@Jones2023], this works.\n"
        )
        issues = check_refs(root)
        cite_issues = [i for i in issues if i.ref_type == "citation"]
        assert len(cite_issues) == 1
        assert cite_issues[0].ref_value == "Jones2023"


def test_broken_markdown_link() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nSee [this doc](doc/background/topics/nonexistent.md) for details.\n"
        )
        issues = check_refs(root)
        link_issues = [i for i in issues if i.ref_type == "link"]
        assert len(link_issues) == 1
        assert "nonexistent" in link_issues[0].ref_value


def test_valid_markdown_link() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "other.md").write_text("# Other\n")
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nSee [other topic](other.md) for details.\n"
        )
        issues = check_refs(root)
        link_issues = [i for i in issues if i.ref_type == "link"]
        assert len(link_issues) == 0


def test_unverified_markers_tracked() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nSome fact [UNVERIFIED] and another [NEEDS CITATION].\n"
        )
        issues = check_refs(root)
        marker_issues = [i for i in issues if i.ref_type == "marker"]
        assert len(marker_issues) == 2
        markers = {i.ref_value for i in marker_issues}
        assert "[UNVERIFIED]" in markers
        assert "[NEEDS CITATION]" in markers


def test_no_bib_file_skips_citation_check() -> None:
    """If references.bib doesn't exist, citation refs should all be flagged."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "papers" / "references.bib").unlink()
        (root / "doc" / "background" / "topics" / "test.md").write_text("# Test\nAs shown by [@Smith2024].\n")
        issues = check_refs(root)
        cite_issues = [i for i in issues if i.ref_type == "citation"]
        assert len(cite_issues) == 1


def test_cli_refs_check() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nH99 is broken and [@Nobody2099] too.\n"
        )
        result = runner.invoke(main, ["refs", "check"])
        assert result.exit_code == 1
        assert "H99" in result.output
        assert "Nobody2099" in result.output


def test_cli_refs_check_clean() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nH01 is valid and [@Smith2024] is cited.\n"
        )
        result = runner.invoke(main, ["refs", "check"])
        assert result.exit_code == 0


def test_multiple_citations_in_one_bracket() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text("# Test\nAs shown [@Smith2024; @Jones2023].\n")
        issues = check_refs(root)
        cite_issues = [i for i in issues if i.ref_type == "citation"]
        # Smith2024 is valid, Jones2023 is not
        assert len(cite_issues) == 1
        assert cite_issues[0].ref_value == "Jones2023"


def test_external_url_links_ignored() -> None:
    """Links starting with http(s) or # should not be checked."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nSee [site](https://example.com) and [anchor](#section).\n"
        )
        issues = check_refs(root)
        link_issues = [i for i in issues if i.ref_type == "link"]
        assert len(link_issues) == 0


def test_valid_task_ref() -> None:
    """A doc citing t05 is fine when [t05] is declared in tasks/active.md."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "tasks").mkdir(parents=True, exist_ok=True)
        (root / "tasks" / "active.md").write_text("## [t05] Build pipeline\n- status: proposed\n")
        (root / "doc" / "background" / "topics" / "pipeline.md").write_text(
            "# Pipeline\nCompleted in t05.\n"
        )
        issues = check_refs(root)
        task_issues = [i for i in issues if i.ref_type == "task"]
        assert task_issues == []


def test_broken_task_ref() -> None:
    """A doc citing t99 must flag when no such task is declared."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "tasks").mkdir(parents=True, exist_ok=True)
        (root / "tasks" / "active.md").write_text("## [t05] Build pipeline\n- status: proposed\n")
        (root / "doc" / "background" / "topics" / "pipeline.md").write_text(
            "# Pipeline\nDriven by t99 which does not exist.\n"
        )
        issues = check_refs(root)
        task_issues = [i for i in issues if i.ref_type == "task"]
        assert len(task_issues) == 1
        assert task_issues[0].ref_value == "t99"


def test_task_ref_in_done_file_resolves() -> None:
    """Task IDs declared only in tasks/done/*.md should still resolve."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "tasks" / "done").mkdir(parents=True, exist_ok=True)
        (root / "tasks" / "active.md").write_text("")
        (root / "tasks" / "done" / "2026-04.md").write_text("## [t12] Completed work\n- status: done\n")
        (root / "doc" / "background" / "topics" / "x.md").write_text("# X\nFollows t12.\n")
        issues = check_refs(root)
        task_issues = [i for i in issues if i.ref_type == "task"]
        assert task_issues == []


def test_task_ref_resolves_when_declaration_is_not_first_header_in_tasks_file() -> None:
    """Task declarations should be found throughout multi-entry task markdown files."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "tasks").mkdir(parents=True, exist_ok=True)
        (root / "tasks" / "active.md").write_text(
            "## [t05] Build pipeline\n"
            "- status: proposed\n\n"
            "## [t99] Later task\n"
            "- status: proposed\n"
        )
        (root / "doc" / "background" / "topics" / "pipeline.md").write_text("# Pipeline\nDriven by t99.\n")

        issues = check_refs(root)
        task_issues = [i for i in issues if i.ref_type == "task"]
        assert task_issues == []
