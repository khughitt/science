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
