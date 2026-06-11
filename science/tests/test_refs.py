"""Tests for cross-reference validation (science refs check)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from science_tool.cli import main
from science_tool.refs import check_refs
from science_tool.refs_cli import refs_group


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


def test_cell_line_token_not_flagged_as_hypothesis_ref() -> None:
    """Three-or-more-digit ``H<n>`` tokens are cell-line/clone names (e.g. NCI-H929),
    not hypothesis references, and must not be reported as broken hypothesis refs."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nThe NCI-H929 and H1975 cell lines were profiled.\n"
        )
        issues = check_refs(root)
        hyp_issues = [i for i in issues if i.ref_type == "hypothesis"]
        assert hyp_issues == []


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


def test_v3_hypothesis_ref_resolves_from_entities_dir_via_heading() -> None:
    """After the v2->v3 layout migration hypotheses live in entities/hypotheses/.
    An HNN mention resolves against a file whose heading carries the HNN label."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "specs" / "hypotheses" / "h01-test.md").unlink()
        (root / "entities" / "hypotheses").mkdir(parents=True)
        (root / "entities" / "hypotheses" / "0001-rhythms.md").write_text(
            "---\n"
            "id: hypothesis:0001-rhythms\n"
            "type: hypothesis\n"
            "title: Rhythms\n"
            "---\n\n"
            "# H01: Rhythms are control structure\n"
        )
        (root / "doc" / "background" / "topics" / "test.md").write_text("# Test\nThis relates to H01 strongly.\n")

        issues = check_refs(root)
        hyp_issues = [i for i in issues if i.ref_type == "hypothesis"]
        assert hyp_issues == []


def test_v3_hypothesis_ref_resolves_from_numeric_id_prefix_without_heading_label() -> None:
    """The hard case: a v3 file numbered 0003 whose heading is a generic
    '# Hypothesis: ...' (no H03 label) and whose id has no legacy 'h' prefix.
    The HNN alias must be derived from the 4-digit numeric id/filename prefix."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "specs" / "hypotheses" / "h01-test.md").unlink()
        (root / "entities" / "hypotheses").mkdir(parents=True)
        (root / "entities" / "hypotheses" / "0003-menstrual-cycle.md").write_text(
            "---\n"
            "id: hypothesis:0003-menstrual-cycle\n"
            "type: hypothesis\n"
            "title: Menstrual cycle\n"
            "---\n\n"
            "# Hypothesis: The menstrual cycle is a systemic control rhythm\n"
        )
        (root / "doc" / "background" / "topics" / "test.md").write_text("# Test\nThis relates to H03 strongly.\n")

        issues = check_refs(root)
        hyp_issues = [i for i in issues if i.ref_type == "hypothesis"]
        assert hyp_issues == []


def test_broken_ref_inside_entities_dir_is_scanned() -> None:
    """After the v2->v3 migration entity bodies live under entities/<kind>/.
    A broken cross-reference in such a body must be detected (regression: the
    refs source scanner only walked doc/ + specs/, so entities/ bodies were
    never scanned for broken refs)."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "entities" / "papers").mkdir(parents=True)
        (root / "entities" / "papers" / "Foo2024.md").write_text(
            "---\nid: paper:Foo2024\ntype: paper\ntitle: Foo\n---\n\nAs shown by [@Ghost2099], this holds.\n"
        )
        issues = check_refs(root)
        cite_issues = [i for i in issues if i.ref_type == "citation" and "Foo2024.md" in i.file]
        assert len(cite_issues) == 1


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


def test_valid_frontmatter_cite_ref() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "---\n"
            'id: "topic:test"\n'
            'type: "topic"\n'
            'title: "Test"\n'
            'source_refs: ["cite:Smith2024"]\n'
            "---\n"
            "# Test\n",
            encoding="utf-8",
        )

        issues = check_refs(root)

        assert [i for i in issues if i.ref_type == "citation"] == []


def test_missing_frontmatter_cite_ref_is_flagged() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "---\n"
            'id: "topic:test"\n'
            'type: "topic"\n'
            'title: "Test"\n'
            'source_refs: ["cite:Jones2023"]\n'
            "---\n"
            "# Test\n",
            encoding="utf-8",
        )

        issues = check_refs(root)

        cite_issues = [i for i in issues if i.ref_type == "citation"]
        assert len(cite_issues) == 1
        assert cite_issues[0].ref_value == "cite:Jones2023"
        assert cite_issues[0].message == "cite:Jones2023 — not in papers/references.bib"


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


def test_bracketed_math_not_flagged_as_link() -> None:
    """Inline math like [x](x') has a non-path destination and must not be
    resolved as a file reference."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nThe deviation [x](x') and the prime [x'](x) appear in the cost.\n"
        )
        issues = check_refs(root)
        link_issues = [i for i in issues if i.ref_type == "link"]
        assert link_issues == []


def test_unverified_and_legacy_needs_citation_tracked() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "doc").mkdir()
        (root / "doc" / "test.md").write_text(
            "# Test\nSome fact [UNVERIFIED] and another [NEEDS CITATION].\n"
        )
        issues = check_refs(root)
        marker_issues = [i for i in issues if i.ref_type == "marker"]
        assert len(marker_issues) == 2
        markers = {i.ref_value for i in marker_issues}
        # Legacy [NEEDS CITATION] is normalized to canonical [MISSING_CITATION].
        assert markers == {"[UNVERIFIED]", "[MISSING_CITATION]"}
        # Both default to warn severity.
        assert {i.severity for i in marker_issues} == {"warn"}


def test_speculation_and_inaccessible_default_to_info() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "doc").mkdir()
        (root / "doc" / "test.md").write_text(
            "# Test\nMaybe [SPECULATION] and [INACCESSIBLE] paywalled.\n"
        )
        issues = check_refs(root)
        marker_issues = [i for i in issues if i.ref_type == "marker"]
        severities = {i.ref_value: i.severity for i in marker_issues}
        assert severities == {"[SPECULATION]": "info", "[INACCESSIBLE]": "info"}


def test_backticked_marker_excluded_from_check_refs() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "doc").mkdir()
        (root / "doc" / "test.md").write_text(
            "# Test\nUse `[UNVERIFIED]` per convention. Bare [UNVERIFIED] flagged.\n"
        )
        issues = check_refs(root)
        marker_issues = [i for i in issues if i.ref_type == "marker"]
        assert len(marker_issues) == 1


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


def test_cli_refs_check_reports_peer_config_error() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        peer_a = root / "peer-a"
        peer_b = root / "peer-b"
        for peer, project_id in ((peer_a, "peer-a"), (peer_b, "peer-b")):
            peer.mkdir()
            (peer / "science.yaml").write_text(
                f"""
name: {project_id}
id: {project_id}
profile: research
research_question: "..."
""",
                encoding="utf-8",
            )
        (root / "science.yaml").write_text(
            f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer_a}
  - id: peer
    path: {peer_b}
""",
            encoding="utf-8",
        )

        result = runner.invoke(main, ["refs", "check"])

        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "duplicate_peer_id [peer]" in result.output
        assert result.exception is not None


def test_cli_refs_check_id_mismatch_names_offending_science_yaml() -> None:
    """A peer id_mismatch must give an actionable message naming the file.

    Regression for fb-2026-05-29-004: the abort message named neither the
    offending science.yaml nor declared-vs-found ids, so root-causing required
    manually diffing files. The error now names the peer's science.yaml path.
    """
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        peer = root / "peer-dir"
        peer.mkdir()
        (peer / "science.yaml").write_text(
            'name: actual\nid: actual-id\nprofile: research\nresearch_question: "..."\n',
            encoding="utf-8",
        )
        (root / "science.yaml").write_text(
            f'name: host\nid: host\nprofile: research\nresearch_question: "..."\n'
            f"peers:\n  - id: declared-id\n    path: {peer}\n",
            encoding="utf-8",
        )

        result = runner.invoke(main, ["refs", "check"])

        assert result.exit_code == 1
        assert "id_mismatch" in result.output
        assert str(peer / "science.yaml") in result.output
        assert "declared-id" in result.output and "actual-id" in result.output


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


def test_citation_like_tokens_in_fenced_code_are_ignored() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\n"
            "```markdown\n"
            "Broken example [@Missing2024], t99, and [missing](nope.md).\n"
            "```\n",
            encoding="utf-8",
        )

        issues = check_refs(root)

        assert issues == []


def test_citation_like_tokens_in_inline_code_are_ignored() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nUse `[@Missing2024]` as a placeholder example.\n",
            encoding="utf-8",
        )

        issues = check_refs(root)

        assert [issue for issue in issues if issue.ref_type == "citation"] == []


def test_namespaced_semantic_refs_are_not_bibtex_citations() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nThe [@model:gray-scott] model uses [@param:feed-rate].\n",
            encoding="utf-8",
        )

        issues = check_refs(root)

        assert [issue for issue in issues if issue.ref_type == "citation"] == []


def test_placeholder_citation_keys_are_ignored() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nTemplate examples use [@AuthorYear] and [@<key>].\n",
            encoding="utf-8",
        )

        issues = check_refs(root)

        assert [issue for issue in issues if issue.ref_type == "citation"] == []


def test_cli_refs_check_summarizes_broken_refs_by_type() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nH99 is broken and [@Nobody2099] too.\n",
            encoding="utf-8",
        )

        result = runner.invoke(main, ["refs", "check"])

        assert result.exit_code == 1
        assert "By type:" in result.output
        assert "citation: 1" in result.output
        assert "hypothesis: 1" in result.output


def test_cli_refs_check_json_includes_summary() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nH99 is broken, [@Nobody2099] is missing, and [MISSING_CITATION].\n",
            encoding="utf-8",
        )

        result = runner.invoke(main, ["refs", "check", "--format", "json"])

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["summary"] == {
            "broken": 2,
            "markers": 1,
            "by_type": {"citation": 1, "hypothesis": 1},
        }
        assert len(payload["broken"]) == 2
        assert len(payload["markers"]) == 1


def test_cli_refs_check_summary_only_omits_table_details() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nH99 is broken, [@Nobody2099] is missing, and [MISSING_CITATION].\n",
            encoding="utf-8",
        )

        result = runner.invoke(main, ["refs", "check", "--summary-only"])

        assert result.exit_code == 1
        assert "refs check: 2 broken, 1 unresolved markers" in result.output
        assert "By type:" in result.output
        assert "citation: 1" in result.output
        assert "hypothesis: 1" in result.output
        assert "Unresolved markers:" in result.output
        assert "doc/background/topics/test.md:1" not in result.output
        assert "@Nobody2099" not in result.output


def test_cli_refs_check_json_summary_only_omits_details() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nH99 is broken, [@Nobody2099] is missing, and [MISSING_CITATION].\n",
            encoding="utf-8",
        )

        result = runner.invoke(main, ["refs", "check", "--format", "json", "--summary-only"])

        assert result.exit_code == 1
        assert json.loads(result.output) == {
            "summary": {
                "broken": 2,
                "markers": 1,
                "by_type": {"citation": 1, "hypothesis": 1},
            }
        }


def test_cli_refs_check_type_filters_broken_refs() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "tasks").mkdir(parents=True, exist_ok=True)
        (root / "tasks" / "active.md").write_text("## [t05] Build pipeline\n- status: proposed\n")
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nH99 is broken, [@Nobody2099] is missing, and t99 is missing.\n",
            encoding="utf-8",
        )

        result = runner.invoke(main, ["refs", "check", "--type", "task", "--summary-only"])

        assert result.exit_code == 1
        assert "refs check: 1 broken, 0 unresolved markers" in result.output
        assert "task: 1" in result.output
        assert "citation:" not in result.output
        assert "hypothesis:" not in result.output


def test_cli_refs_check_by_value_groups_filtered_refs() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "tasks").mkdir(parents=True, exist_ok=True)
        (root / "tasks" / "active.md").write_text("## [t05] Build pipeline\n- status: proposed\n")
        (root / "doc" / "background" / "topics" / "one.md").write_text(
            "# One\nMissing t99 appears twice: t99.\n",
            encoding="utf-8",
        )
        (root / "doc" / "background" / "topics" / "two.md").write_text(
            "# Two\nMissing t42 appears once.\n",
            encoding="utf-8",
        )

        result = runner.invoke(main, ["refs", "check", "--type", "task", "--by-value", "--summary-only"])

        assert result.exit_code == 1
        assert "By value:" in result.output
        assert "task:t99: 2" in result.output
        assert "task:t42: 1" in result.output


def test_cli_refs_check_json_by_value_groups_filtered_refs() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "tasks").mkdir(parents=True, exist_ok=True)
        (root / "tasks" / "active.md").write_text("## [t05] Build pipeline\n- status: proposed\n")
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nMissing t99 appears twice: t99. H99 is separate.\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            main,
            ["refs", "check", "--type", "task", "--by-value", "--format", "json", "--summary-only"],
        )

        assert result.exit_code == 1
        assert json.loads(result.output) == {
            "summary": {
                "broken": 2,
                "markers": 0,
                "by_type": {"task": 2},
                "by_value": {"task:t99": 2},
            }
        }


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
        (root / "doc" / "background" / "topics" / "pipeline.md").write_text("# Pipeline\nCompleted in t05.\n")
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


def test_task_ref_in_archive_file_resolves() -> None:
    """Historical task IDs declared in tasks/archive.md should resolve."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "tasks").mkdir(parents=True, exist_ok=True)
        (root / "tasks" / "active.md").write_text("## [t05] Active task\n- status: active\n")
        (root / "tasks" / "archive.md").write_text(
            "# Historical task aliases\n\n"
            "## [t27] Diffusion ratio audit\n"
            "- status: archived\n"
            "- replacement: task:t227\n",
            encoding="utf-8",
        )
        (root / "doc" / "background" / "topics" / "x.md").write_text("# X\nFollows t27.\n")

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
            "## [t05] Build pipeline\n- status: proposed\n\n## [t99] Later task\n- status: proposed\n"
        )
        (root / "doc" / "background" / "topics" / "pipeline.md").write_text("# Pipeline\nDriven by t99.\n")

        issues = check_refs(root)
        task_issues = [i for i in issues if i.ref_type == "task"]
        assert task_issues == []


def test_namespace_first_cross_project_task_ref_is_accepted_when_peer_declared() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "science.yaml").write_text(
            "name: meta\n"
            "id: meta\n"
            "role: meta\n"
            "peers:\n"
            "  - id: natural-systems\n"
            f"    path: {root / 'natural-systems'}\n",
            encoding="utf-8",
        )
        (root / "doc" / "questions" / "x.md").write_text(
            "---\nid: question:x\ntype: question\nrelated: [natural-systems:task:t335]\n---\n\n# X\n",
            encoding="utf-8",
        )

        issues = check_refs(root)

        assert [issue for issue in issues if issue.ref_value == "natural-systems:task:t335"] == []
        assert [issue for issue in issues if issue.ref_type == "task" and issue.ref_value == "t335"] == []


def test_refs_check_surfaces_removed_children_config() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "science.yaml").write_text(
            f"name: meta\nid: meta\nchildren:\n  - id: natural-systems\n    path: {root / 'natural-systems'}\n",
            encoding="utf-8",
        )

        with pytest.raises(ValidationError, match=r"Run `science peers migrate` to migrate to `peers:`"):
            check_refs(root)


def test_load_project_ids_includes_peers(tmp_path: Path) -> None:
    """`_load_project_ids` should pick up peers via the resolver."""
    from science_tool.refs import _load_project_ids

    peer = tmp_path / "peer"
    peer.mkdir()
    (peer / "science.yaml").write_text(
        """
name: peer
id: peer
profile: research
research_question: "..."
""",
        encoding="utf-8",
    )
    host = tmp_path / "host"
    host.mkdir()
    (host / "science.yaml").write_text(
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer}
""",
        encoding="utf-8",
    )
    ids = _load_project_ids(host)
    assert "host" in ids
    assert "peer" in ids


def test_load_project_ids_surfaces_peer_config_errors(tmp_path: Path) -> None:
    """Resolver construction failures should not be downgraded to unknown namespaces."""
    from science_tool.peers import PeerUnresolved
    from science_tool.refs import _load_project_ids

    peer_a = tmp_path / "peer-a"
    peer_b = tmp_path / "peer-b"
    for peer, project_id in ((peer_a, "peer-a"), (peer_b, "peer-b")):
        peer.mkdir()
        (peer / "science.yaml").write_text(
            f"""
name: {project_id}
id: {project_id}
profile: research
research_question: "..."
""",
            encoding="utf-8",
        )
    host = tmp_path / "host"
    host.mkdir()
    (host / "science.yaml").write_text(
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer_a}
  - id: peer
    path: {peer_b}
""",
        encoding="utf-8",
    )

    with pytest.raises(PeerUnresolved, match="duplicate_peer_id \\[peer\\]"):
        _load_project_ids(host)


def test_unknown_namespace_is_reported() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "science.yaml").write_text("name: demo\nid: demo\n", encoding="utf-8")
        (root / "doc" / "questions" / "x.md").write_text(
            "---\nid: question:x\ntype: question\nrelated: [natural-systems:task:t335]\n---\n\n# X\n",
            encoding="utf-8",
        )

        issues = check_refs(root)

        namespace_issues = [issue for issue in issues if issue.ref_type == "namespace"]
        assert len(namespace_issues) == 1
        assert namespace_issues[0].message == (
            "Unknown project namespace 'natural-systems' in ref 'natural-systems:task:t335'. "
            "Add it to science.yaml peers: or use a local ref."
        )


def test_legacy_two_part_cross_project_ref_reports_suggestion() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "science.yaml").write_text(
            f"name: meta\nid: meta\nrole: meta\npeers:\n  - id: cbioportal\n    path: {root / 'cbioportal'}\n",
            encoding="utf-8",
        )
        (root / "doc" / "questions" / "x.md").write_text(
            "---\nid: question:x\ntype: question\nrelated: [cbioportal:q014]\n---\n\n# X\n",
            encoding="utf-8",
        )

        issues = check_refs(root)

        legacy = [issue for issue in issues if issue.ref_type == "legacy-cross-project"]
        assert len(legacy) == 1
        assert legacy[0].message == (
            "Legacy cross-project ref 'cbioportal:q014' is missing an entity kind. "
            "Use 'cbioportal:question:q014' or another explicit <project-id>:<kind>:<slug> ref."
        )


# --- DOI / PMID validation (fb-2026-04-13-007) ---


def _scaffold_with_bib(root: Path, bib_body: str) -> None:
    _scaffold(root)
    (root / "papers" / "references.bib").write_text(bib_body)


def test_valid_doi_in_prose_is_accepted() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold_with_bib(
            root,
            "@article{Smith2024,\n  title={X},\n  doi={10.1038/s41586-024-00001-1},\n}\n",
        )
        (root / "doc" / "background" / "topics" / "x.md").write_text(
            "# X\nSee 10.1038/s41586-024-00001-1 for the full result.\n"
        )
        issues = check_refs(root)
        assert [i for i in issues if i.ref_type == "doi"] == []


def test_unknown_doi_in_prose_is_flagged() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold_with_bib(
            root,
            "@article{Smith2024,\n  title={X},\n  doi={10.1038/s41586-024-00001-1},\n}\n",
        )
        (root / "doc" / "background" / "topics" / "x.md").write_text(
            "# X\nSee https://doi.org/10.9999/fake.123 for the full result.\n"
        )
        issues = check_refs(root)
        doi_issues = [i for i in issues if i.ref_type == "doi"]
        assert len(doi_issues) == 1
        assert doi_issues[0].ref_value == "10.9999/fake.123"


def test_markdown_emphasis_after_doi_is_not_part_of_doi() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold_with_bib(
            root,
            "@article{Smith2024,\n  title={X},\n  doi={10.1007/s10853-019-04261-6},\n}\n",
        )
        (root / "doc" / "background" / "topics" / "x.md").write_text(
            "# X\nThe highlighted DOI is **10.1007/s10853-019-04261-6**.\n"
        )

        issues = check_refs(root)

        assert [i for i in issues if i.ref_type == "doi"] == []


def test_doi_check_skipped_in_doc_papers() -> None:
    """Paper notes are corpus contributors, not consumers — don't flag DOIs there."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold_with_bib(
            root,
            "@article{Smith2024,\n  title={X},\n  doi={10.1038/s41586-024-00001-1},\n}\n",
        )
        (root / "doc" / "papers").mkdir(parents=True, exist_ok=True)
        (root / "doc" / "papers" / "Smith2024.md").write_text(
            "# Smith 2024\n- DOI: 10.1038/s41586-024-00001-1\n- Newly added not yet in bib: 10.1234/new.5678\n"
        )
        issues = check_refs(root)
        assert [i for i in issues if i.ref_type == "doi"] == []


def test_doi_with_internal_parentheses_is_matched() -> None:
    """Legacy Elsevier DOIs contain parens (e.g. 10.1016/0197-2456(86)90046-2);
    a prose citation must resolve against the bib, not truncate at the first ')'."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold_with_bib(
            root,
            "@article{DerSimonian1986,\n  title={X},\n  doi={10.1016/0197-2456(86)90046-2},\n}\n",
        )
        (root / "doc" / "background" / "topics" / "x.md").write_text(
            "# X\nRandom-effects meta-analysis via 10.1016/0197-2456(86)90046-2 here.\n"
        )
        issues = check_refs(root)
        assert [i for i in issues if i.ref_type == "doi"] == []


def test_doi_wrapped_in_parentheses_trims_trailing_paren() -> None:
    """A parenthesis-wrapped DOI in prose reports the bare DOI, not a trailing ')'."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold_with_bib(
            root,
            "@article{Smith2024,\n  title={X},\n  doi={10.1038/s41586-024-00001-1},\n}\n",
        )
        (root / "doc" / "background" / "topics" / "x.md").write_text(
            "# X\nA candidate result (10.9999/fake.123) was noted.\n"
        )
        issues = check_refs(root)
        doi_issues = [i for i in issues if i.ref_type == "doi"]
        assert len(doi_issues) == 1
        assert doi_issues[0].ref_value == "10.9999/fake.123"


def test_doi_pmid_check_skipped_in_doc_searches_by_default() -> None:
    """Search docs are literature-discovery logs (candidate identifiers), not
    citation sites — exempt from DOI/PMID bib-completeness by default."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold_with_bib(
            root,
            "@article{Smith2024,\n  title={X},\n  doi={10.1038/s41586-024-00001-1},\n}\n",
        )
        (root / "doc" / "searches").mkdir(parents=True, exist_ok=True)
        (root / "doc" / "searches" / "2026-survey.md").write_text(
            "# Survey\nCandidate found: PMID: 99999999 / DOI: 10.9999/fake.123 (not adopted).\n"
        )
        issues = check_refs(root)
        assert [i for i in issues if i.ref_type in ("doi", "pmid")] == []


def test_doi_pmid_exempt_dirs_is_configurable() -> None:
    """A project can override the exempt-dir list; dropping doc/searches re-enables
    the check there."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold_with_bib(
            root,
            "@article{Smith2024,\n  title={X},\n  doi={10.1038/s41586-024-00001-1},\n}\n",
        )
        (root / "science.yaml").write_text(
            "name: demo\nid: demo\nrefs:\n  doi_pmid_exempt_dirs: [doc/papers]\n",
            encoding="utf-8",
        )
        (root / "doc" / "searches").mkdir(parents=True, exist_ok=True)
        (root / "doc" / "searches" / "2026-survey.md").write_text(
            "# Survey\nCandidate DOI: 10.9999/fake.123 (not adopted).\n"
        )
        issues = check_refs(root)
        doi_issues = [i for i in issues if i.ref_type == "doi"]
        assert len(doi_issues) == 1
        assert doi_issues[0].ref_value == "10.9999/fake.123"


def test_doi_check_silent_when_no_bib_or_paper_notes() -> None:
    """No corpus → no DOI claims to validate against → no false positives."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        # remove the auto-scaffolded bib
        (root / "papers" / "references.bib").unlink()
        (root / "doc" / "background" / "topics" / "x.md").write_text("# X\nDOI: 10.1234/anything.goes here\n")
        issues = check_refs(root)
        assert [i for i in issues if i.ref_type == "doi"] == []


def test_unknown_pmid_in_prose_is_flagged() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold_with_bib(
            root,
            "@article{Smith2024,\n  title={X},\n  pmid={12345678},\n}\n",
        )
        (root / "doc" / "background" / "topics" / "x.md").write_text(
            "# X\nSee PMID: 99999999 for the missing reference, and PMID: 12345678 for the known one.\n"
        )
        issues = check_refs(root)
        pmid_issues = [i for i in issues if i.ref_type == "pmid"]
        assert len(pmid_issues) == 1
        assert pmid_issues[0].ref_value == "PMID:99999999"


def test_legacy_needs_citation_recognized_in_cli_output() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "doc").mkdir()
        (root / "doc" / "test.md").write_text("Old [NEEDS CITATION] in prose.\n")
        result = runner.invoke(refs_group, ["check", "--root", str(root)])
        assert "[MISSING_CITATION]" in result.output


def test_check_cli_strict_promotes_speculation_to_blocking() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "doc").mkdir()
        (root / "doc" / "test.md").write_text("Just [SPECULATION] here.\n")
        # Without --strict: SPECULATION is info, exit 0.
        result = runner.invoke(refs_group, ["check", "--root", str(root)])
        assert result.exit_code == 0
        # With --strict: SPECULATION promoted to warn, exit 1.
        result = runner.invoke(refs_group, ["check", "--root", str(root), "--strict"])
        assert result.exit_code == 1


def test_check_cli_renders_per_token_counts_with_severity_tag() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "doc").mkdir()
        (root / "doc" / "test.md").write_text(
            "[UNVERIFIED] and [SPECULATION] and [INACCESSIBLE]\n"
        )
        result = runner.invoke(refs_group, ["check", "--root", str(root)])
        assert "[UNVERIFIED]" in result.output
        assert "[SPECULATION]" in result.output
        assert "[INACCESSIBLE]" in result.output
        # Info-severity tokens are tagged.
        assert "(info)" in result.output


def test_check_cli_strict_drops_info_tag() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "doc").mkdir()
        (root / "doc" / "test.md").write_text("[SPECULATION]\n")
        result = runner.invoke(refs_group, ["check", "--root", str(root), "--strict"])
        # Under --strict, the info tag should not appear (severity promoted to warn).
        assert "(info)" not in result.output


def test_load_entity_index_collects_kind_id_pairs(tmp_path):
    """`_load_entity_index` returns the set of <kind>:<id> values discovered in frontmatter."""
    from science_tool.refs import _load_entity_index

    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "q01.md").write_text(
        "---\n"
        "id: question:q01-foo\n"
        "type: question\n"
        "---\n"
        "Body.\n"
    )
    (tmp_path / "doc" / "t050.md").write_text(
        "---\n"
        "id: task:t050\n"
        "type: task\n"
        "---\n"
        "Body.\n"
    )
    (tmp_path / "doc" / "no-id.md").write_text(
        "---\n"
        "type: discussion\n"
        "---\n"
        "Body.\n"
    )

    index = _load_entity_index(tmp_path)
    assert "question:q01-foo" in index
    assert "task:t050" in index
    assert len(index) == 2  # no-id.md contributes nothing


def test_load_entity_index_from_graph_parses_schema_identifiers(tmp_path):
    """`_load_entity_index_from_graph` extracts <kind>:<slug> from schema:identifier triples."""
    from science_tool.refs import _load_entity_index_from_graph

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "graph.trig").write_text(
        "@prefix schema: <https://schema.org/> .\n"
        "<http://example.org/project/graph/knowledge> {\n"
        '    <http://example.org/project/task/t100>\n'
        '        schema:identifier "task:t100" .\n'
        '    <http://example.org/project/question/q42-foo>\n'
        '        schema:identifier "question:q42-foo" .\n'
        '    <http://example.org/project/unknown/info>\n'
        '        schema:identifier "unknown-kind:info" .\n'  # not in _LOCAL_ENTITY_KINDS
        '}\n',
        encoding="utf-8",
    )
    index = _load_entity_index_from_graph(tmp_path)
    assert "task:t100" in index
    assert "question:q42-foo" in index
    assert "unknown-kind:info" not in index  # filtered: kind not in _LOCAL_ENTITY_KINDS


def test_load_entity_index_from_graph_returns_empty_when_missing(tmp_path):
    """Missing graph.trig returns empty set without raising."""
    from science_tool.refs import _load_entity_index_from_graph

    index = _load_entity_index_from_graph(tmp_path)
    assert index == set()


class TestBodyTypedRefScan:
    def _project(self, tmp_path):
        (tmp_path / "doc").mkdir()
        (tmp_path / "doc" / "q01.md").write_text(
            "---\nid: question:q01-foo\ntype: question\n---\nBody.\n"
        )
        (tmp_path / "doc" / "t050.md").write_text(
            "---\nid: task:t050\ntype: task\n---\nBody.\n"
        )
        return tmp_path

    def test_flags_unknown_typed_ref_in_body(self, tmp_path):
        from science_tool.refs import check_refs

        root = self._project(tmp_path)
        (root / "doc" / "report.md").write_text(
            "---\ntype: report\n---\nSee task:t999 for the gap.\n"
        )
        issues = check_refs(root, include_body=True)
        body_issues = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert len(body_issues) == 1
        assert body_issues[0].ref_value == "task:t999"
        assert "doc/report.md" in body_issues[0].file
        assert body_issues[0].line == 4

    def test_no_flag_for_resolved_typed_ref(self, tmp_path):
        from science_tool.refs import check_refs

        root = self._project(tmp_path)
        (root / "doc" / "report.md").write_text(
            "---\ntype: report\n---\nSee task:t050 for the work.\n"
        )
        issues = check_refs(root, include_body=True)
        assert [i for i in issues if i.ref_type == "body-entity-ref"] == []

    def test_skips_typed_refs_in_fenced_code(self, tmp_path):
        from science_tool.refs import check_refs

        root = self._project(tmp_path)
        (root / "doc" / "report.md").write_text(
            "---\ntype: report\n---\n```\nExample: task:t999\n```\n"
        )
        issues = check_refs(root, include_body=True)
        assert [i for i in issues if i.ref_type == "body-entity-ref"] == []

    def test_skips_typed_refs_in_inline_code(self, tmp_path):
        from science_tool.refs import check_refs

        root = self._project(tmp_path)
        (root / "doc" / "report.md").write_text(
            "---\ntype: report\n---\nUse the `task:tNN` placeholder.\n"
        )
        issues = check_refs(root, include_body=True)
        assert [i for i in issues if i.ref_type == "body-entity-ref"] == []

    def test_default_off_when_include_body_false(self, tmp_path):
        from science_tool.refs import check_refs

        root = self._project(tmp_path)
        (root / "doc" / "report.md").write_text(
            "---\ntype: report\n---\nSee task:t999 for the gap.\n"
        )
        issues = check_refs(root)  # include_body=False default
        assert [i for i in issues if i.ref_type == "body-entity-ref"] == []

    def test_skips_cross_project_refs(self, tmp_path):
        from science_tool.refs import check_refs

        root = self._project(tmp_path)
        # Triple-segment refs like `mm30:task:t050` are cross-project; not our concern.
        (root / "doc" / "report.md").write_text(
            "---\ntype: report\n---\nSee mm30:task:t050.\n"
        )
        issues = check_refs(root, include_body=True)
        assert [i for i in issues if i.ref_type == "body-entity-ref"] == []


def test_refs_check_include_body_flag_emits_typed_ref_issues(tmp_path):
    """The CLI `--include-body` flag enables body-typed-ref scanning."""
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "t050.md").write_text(
        "---\nid: task:t050\ntype: task\n---\nBody.\n"
    )
    (tmp_path / "doc" / "report.md").write_text(
        "---\ntype: report\n---\nSee task:t999 for the gap.\n"
    )

    runner = CliRunner()
    result_no_body = runner.invoke(refs_group, ["check", "--root", str(tmp_path), "--format", "json"])
    result_with_body = runner.invoke(
        refs_group, ["check", "--root", str(tmp_path), "--include-body", "--format", "json"]
    )

    payload_no = json.loads(result_no_body.output)
    payload_yes = json.loads(result_with_body.output)
    # The JSON output shape has "broken" and "markers" keys at the top level.
    # broken is a list of issue dicts with keys like "type", "value", "file", "line", etc.
    issues_no = payload_no.get("broken", [])
    issues_yes = payload_yes.get("broken", [])
    types_no = {h["type"] for h in issues_no}
    types_yes = {h["type"] for h in issues_yes}
    assert "body-entity-ref" not in types_no
    assert "body-entity-ref" in types_yes


class TestEntityIndexSourceSelection:
    """`check_refs` honors `refs.entity_index_source` from science.yaml."""

    def test_graph_source_uses_trig_file(self, tmp_path):
        """When configured to `knowledge_graph`, refs in graph.trig are accepted
        even when missing from frontmatter `id:` index."""
        from science_tool.refs import check_refs

        (tmp_path / "science.yaml").write_text(
            "name: test-project\nprofile: research\n"
            "refs:\n  entity_index_source: knowledge_graph\n",
            encoding="utf-8",
        )
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "graph.trig").write_text(
            '<x> schema:identifier "task:t999" .\n', encoding="utf-8"
        )
        doc_dir = tmp_path / "doc"
        doc_dir.mkdir()
        # Body ref to task:t999 — exists in graph but no markdown file with id: task:t999.
        (doc_dir / "note.md").write_text(
            "---\nid: discussion:2026-05-10-note\n---\n\nReferences task:t999 in body.\n",
            encoding="utf-8",
        )
        issues = check_refs(tmp_path, include_body=True)
        body_issues = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert body_issues == [], f"Expected no body-entity-ref issues; got {body_issues}"

    def test_frontmatter_source_default_ignores_graph(self, tmp_path):
        """Default `frontmatter` source ignores graph.trig — same ref reports broken."""
        from science_tool.refs import check_refs

        (tmp_path / "science.yaml").write_text(
            "name: test-project\nprofile: research\n", encoding="utf-8"
        )
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "graph.trig").write_text(
            '<x> schema:identifier "task:t999" .\n', encoding="utf-8"
        )
        doc_dir = tmp_path / "doc"
        doc_dir.mkdir()
        (doc_dir / "note.md").write_text(
            "---\nid: discussion:2026-05-10-note\n---\n\nReferences task:t999 in body.\n",
            encoding="utf-8",
        )
        issues = check_refs(tmp_path, include_body=True)
        body_issues = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert any(i.ref_value == "task:t999" for i in body_issues)

    def test_graph_source_falls_back_when_trig_missing(self, tmp_path, capsys):
        """Configured `knowledge_graph` with missing trig falls back to frontmatter
        with a stderr warning."""
        from science_tool.refs import check_refs

        (tmp_path / "science.yaml").write_text(
            "name: test-project\nprofile: research\n"
            "refs:\n  entity_index_source: knowledge_graph\n",
            encoding="utf-8",
        )
        # No knowledge/graph.trig file exists.
        doc_dir = tmp_path / "doc"
        doc_dir.mkdir()
        (doc_dir / "note.md").write_text(
            "---\nid: discussion:2026-05-10-note\n---\n\nReferences task:t999 in body.\n",
            encoding="utf-8",
        )
        issues = check_refs(tmp_path, include_body=True)
        # Should report task:t999 as broken (frontmatter fallback, no file with that id).
        body_issues = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert any(i.ref_value == "task:t999" for i in body_issues)
        captured = capsys.readouterr()
        assert "knowledge/graph.trig" in captured.err
        assert "frontmatter" in captured.err.lower()


class TestRefsScanRoots:
    """`refs.scan_roots` config extends the default scan beyond doc/specs."""

    def test_extra_dir_scanned_when_configured(self, tmp_path):
        """A `tasks/` ref shows up only when `scan_roots: [tasks]` is configured."""
        from science_tool.refs import check_refs

        (tmp_path / "science.yaml").write_text(
            "name: test-project\nprofile: research\n"
            "refs:\n  scan_roots: [tasks]\n",
            encoding="utf-8",
        )
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "active.md").write_text(
            "# Active\n\nReferences task:t999 (does not exist).\n",
            encoding="utf-8",
        )
        issues = check_refs(tmp_path, include_body=True)
        body_issues = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert any(i.ref_value == "task:t999" for i in body_issues), (
            f"Expected task:t999 issue from tasks/active.md; got {body_issues}"
        )

    def test_root_markdown_scanned_when_dot_in_scan_roots(self, tmp_path):
        """`scan_roots: ['.']` includes root-level .md files."""
        from science_tool.refs import check_refs

        (tmp_path / "science.yaml").write_text(
            "name: test-project\nprofile: research\n"
            "refs:\n  scan_roots: ['.']\n",
            encoding="utf-8",
        )
        (tmp_path / "README.md").write_text(
            "# Project\n\nSee task:t999 (broken).\n",
            encoding="utf-8",
        )
        issues = check_refs(tmp_path, include_body=True)
        body_issues = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert any(
            i.file == "README.md" and i.ref_value == "task:t999"
            for i in body_issues
        ), f"Expected README.md/task:t999 issue; got {body_issues}"

    def test_extra_dir_not_scanned_by_default(self, tmp_path):
        """Without `scan_roots`, tasks/ refs are NOT detected — confirming default."""
        from science_tool.refs import check_refs

        (tmp_path / "science.yaml").write_text(
            "name: test-project\nprofile: research\n", encoding="utf-8"
        )
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "active.md").write_text(
            "# Active\n\nReferences task:t999.\n",
            encoding="utf-8",
        )
        issues = check_refs(tmp_path, include_body=True)
        body_issues = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert not any(i.ref_value == "task:t999" for i in body_issues)
