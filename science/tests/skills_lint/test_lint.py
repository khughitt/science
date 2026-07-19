from pathlib import Path
from shutil import copytree

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.skills_lint.lint import (
    SkillIssue,
    check_companion_skills,
    check_frontmatter,
    check_halt_on_conditions,
    check_index_coverage,
    check_relative_links,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_good_frontmatter_returns_no_issues() -> None:
    issues = check_frontmatter(FIXTURES / "good.md")
    assert issues == []


def test_no_frontmatter_returns_issue() -> None:
    issues = check_frontmatter(FIXTURES / "bad-no-frontmatter.md")
    assert len(issues) == 1
    assert issues[0].kind == "missing-frontmatter"


def test_missing_name_returns_issue() -> None:
    issues = check_frontmatter(FIXTURES / "bad-missing-name.md")
    assert len(issues) == 1
    assert issues[0].kind == "missing-field"
    assert issues[0].field == "name"


def test_missing_description_returns_issue() -> None:
    issues = check_frontmatter(FIXTURES / "bad-missing-description.md")
    assert len(issues) == 1
    assert issues[0].kind == "missing-field"
    assert issues[0].field == "description"


def test_deep_reference_type_is_valid() -> None:
    issues = check_frontmatter(FIXTURES / "good-deep-reference.md")
    assert issues == []


def test_invalid_type_returns_issue() -> None:
    issues = check_frontmatter(FIXTURES / "bad-invalid-type.md")
    assert len(issues) == 1
    assert issues[0].kind == "invalid-field"
    assert issues[0].field == "type"


def test_missing_companion_skills_section_returns_issue() -> None:
    issues = check_companion_skills(FIXTURES / "bad-no-companion-skills.md")
    assert any(issue.kind == "missing-section" and issue.detail == "Companion Skills" for issue in issues)


def test_required_halt_on_leaf_with_section_returns_no_issues() -> None:
    path = FIXTURES / "data" / "embeddings-manifold-qa.md"

    issues = check_halt_on_conditions(path, FIXTURES)

    assert issues == []


def test_required_halt_on_leaf_without_section_returns_issue() -> None:
    path = FIXTURES / "data" / "functional-genomics-qa.md"

    issues = check_halt_on_conditions(path, FIXTURES)

    assert len(issues) == 1
    assert issues[0].kind == "missing-section"
    assert issues[0].detail == "Halt-On Conditions"


def test_valid_relative_link_returns_no_issues() -> None:
    issues = check_relative_links(FIXTURES / "good-with-companion.md")
    assert issues == []


def test_broken_relative_link_returns_issue() -> None:
    issues = check_relative_links(FIXTURES / "bad-broken-relative-link.md")
    assert len(issues) == 1
    assert issues[0].kind == "broken-relative-link"
    assert issues[0].detail == "missing.md"


def test_index_coverage_reports_unindexed_markdown(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    (skills_root / "INDEX.md").write_text("`skills/indexed.md`\n", encoding="utf-8")
    (skills_root / "indexed.md").write_text("# Indexed\n", encoding="utf-8")
    (skills_root / "unindexed.md").write_text("# Unindexed\n", encoding="utf-8")

    issues = check_index_coverage(skills_root)

    assert len(issues) == 1
    assert issues[0].kind == "missing-index-entry"
    assert issues[0].detail == "unindexed.md"


def test_index_coverage_accepts_markdown_links(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    (skills_root / "INDEX.md").write_text("[Indexed](indexed.md)\n", encoding="utf-8")
    (skills_root / "indexed.md").write_text("# Indexed\n", encoding="utf-8")

    issues = check_index_coverage(skills_root)

    assert issues == []


def test_lint_cli_against_fixtures(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    copytree(FIXTURES, skills_root)

    result = CliRunner().invoke(main, ["skills", "lint", "--root", str(skills_root)])

    assert result.exit_code == 1
    assert "bad-no-frontmatter.md" in result.output
    assert "bad-missing-name.md" in result.output
    assert "bad-missing-description.md" in result.output
    assert "bad-invalid-type.md" in result.output
    assert "bad-no-companion-skills.md" in result.output
    assert "bad-broken-relative-link.md" in result.output
    assert "data/functional-genomics-qa.md" in result.output
    assert "good.md" not in result.output
    assert "good-with-companion.md" not in result.output
    assert "good-deep-reference.md" not in result.output
    assert "data/embeddings-manifold-qa.md" not in result.output


def test_skill_issue_json_uses_posix_path() -> None:
    issue = SkillIssue(Path("nested") / "bad.md", "missing-frontmatter")

    assert issue.to_json() == {
        "path": "nested/bad.md",
        "kind": "missing-frontmatter",
        "field": None,
        "detail": "",
        "severity": "error",
    }


def test_skill_issue_defaults_to_error_severity() -> None:
    assert SkillIssue(Path("x.md"), "missing-frontmatter").severity == "error"


def test_relative_issues_preserves_severity() -> None:
    from science_tool.skills_lint.lint import _relative_issues
    root = Path("/root")
    warn = SkillIssue(root / "leaf.md", "missing-provenance", severity="warn")
    out = _relative_issues([warn], root)
    assert out[0].severity == "warn"
    assert out[0].path == Path("leaf.md")


def test_has_error_is_severity_aware() -> None:
    from science_tool.skills_lint.cli import _has_error
    warn = SkillIssue(Path("a.md"), "missing-provenance", severity="warn")
    err = SkillIssue(Path("b.md"), "missing-frontmatter")
    assert _has_error([]) is False
    assert _has_error([warn]) is False
    assert _has_error([warn, err]) is True


def test_text_render_leads_with_severity() -> None:
    from science_tool.skills_lint.cli import _format_text_issue
    warn = SkillIssue(Path("leaf.md"), "missing-provenance", severity="warn")
    assert _format_text_issue(warn) == "warn: leaf.md: missing-provenance"


def test_unknown_source_ref_flagged(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    (skills_root / "sources.yaml").write_text(
        "known:\n  title: K\n  authors: [A]\n  url: https://doi.org/x\n"
        "  kind: paper\n  last_checked: 2026-07-18\n",
        encoding="utf-8",
    )
    (skills_root / "INDEX.md").write_text("`skills/leaf.md`\n", encoding="utf-8")
    (skills_root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nsources: [known, missing]\n---\n"
        "# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    from science_tool.skills_lint.lint import check_skills

    kinds = {(i.kind, i.detail) for i in check_skills(skills_root)}
    assert ("unknown-source-ref", "missing") in kinds
    assert ("unknown-source-ref", "known") not in kinds


def test_declared_but_invalid_source_is_not_also_unknown_ref(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    (skills_root / "sources.yaml").write_text(
        "brokensrc:\n  title: B\n  authors: [A]\n  kind: paper\n  last_checked: 2026-07-18\n",  # missing url
        encoding="utf-8",
    )
    (skills_root / "INDEX.md").write_text("`skills/leaf.md`\n", encoding="utf-8")
    (skills_root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nsources: [brokensrc]\n---\n"
        "# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    from science_tool.skills_lint.lint import check_skills

    issues = check_skills(skills_root)
    invalid = [i for i in issues if i.kind == "invalid-source-record" and i.field == "brokensrc"]
    unknown = [i for i in issues if i.kind == "unknown-source-ref"]
    assert len(invalid) == 1  # aggregated: exactly one record report
    assert unknown == []      # not double-flagged as a missing ref


def test_sources_not_a_list_flagged_as_invalid_field(tmp_path: Path) -> None:
    from science_tool.skills_lint.lint import check_source_refs
    from science_tool.skills_lint.sources import SourcesRegistry

    leaf = tmp_path / "leaf.md"
    leaf.write_text("---\nname: x\ndescription: d\nsources: oops\n---\n# X\n", encoding="utf-8")
    issues = check_source_refs(leaf, SourcesRegistry(records={}, errors={}, declared_ids=frozenset()))
    assert len(issues) == 1
    assert issues[0].kind == "invalid-field"
    assert issues[0].field == "sources"
