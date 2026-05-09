"""Tests for cross-reference validation (science refs check)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

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
            "# Test\nH99 is broken, [@Nobody2099] is missing, and [NEEDS CITATION].\n",
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
            "# Test\nH99 is broken, [@Nobody2099] is missing, and [NEEDS CITATION].\n",
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
            "# Test\nH99 is broken, [@Nobody2099] is missing, and [NEEDS CITATION].\n",
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
