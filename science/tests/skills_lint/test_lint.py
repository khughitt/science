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


def _leaf(dirpath: Path, name: str, body: str) -> Path:
    p = dirpath / name
    p.write_text(body, encoding="utf-8")
    return p


def test_classify_provenance_outcomes() -> None:
    from science_tool.skills_lint.lint import classify_provenance
    assert classify_provenance({"sources": ["a"]}) == "attributed"
    assert classify_provenance({"provenance": "internal"}) == "internal"
    assert classify_provenance({"name": "x"}) == "undeclared"
    assert classify_provenance({"sources": ["a"], "provenance": "internal"}) == "contradiction"
    assert classify_provenance({"provenance": "external"}) == "bad-marker"
    assert classify_provenance({"provenance": None}) == "bad-marker"  # null value, not the string "internal"
    assert classify_provenance({"provenance": ["internal"]}) == "bad-marker"  # non-string value
    # malformed sources is NOT "attributed" (design: sources: [] is invalid)
    assert classify_provenance({"sources": []}) == "malformed-sources"
    assert classify_provenance({"sources": ["  "]}) == "malformed-sources"
    assert classify_provenance({"sources": "oops"}) == "malformed-sources"


def test_undeclared_leaf_yields_error_and_nonzero_exit(tmp_path: Path) -> None:
    from click.testing import CliRunner
    from science_tool.cli import main
    from science_tool.skills_lint.lint import check_provenance
    leaf = _leaf(tmp_path, "leaf.md", "---\nname: x\ndescription: d\n---\n# X\n")
    issues = check_provenance(leaf)
    assert issues[0].kind == "missing-provenance"
    assert issues[0].severity == "error"

    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    # INDEX.md is error-free so the ONLY error is the ratcheted missing-provenance
    # on leaf.md — otherwise exit==1 could pass for the wrong reason.
    (skills_root / "INDEX.md").write_text(
        "---\nname: idx\ndescription: d\n---\n# Index\n`skills/leaf.md`\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    (skills_root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\n---\n# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(main, ["skills", "lint", "--root", str(skills_root)])
    assert result.exit_code == 1  # ratcheted: undeclared now blocks
    assert "missing-provenance" in result.output


def test_warn_only_run_still_exits_zero_synthetic(tmp_path: Path, monkeypatch) -> None:
    # Infrastructure guard: after the ratchet, NO shipped rule is WARN, so exercise
    # the WARN-only exit path through the REAL CLI with a synthetic WARN issue —
    # proving exit code and severity rendering, not just the _has_error predicate.
    import json
    from click.testing import CliRunner
    from science_tool.cli import main
    from science_tool.skills_lint.lint import SkillIssue
    synthetic = [SkillIssue(Path("synthetic.md"), "missing-provenance", severity="warn")]
    monkeypatch.setattr("science_tool.skills_lint.cli.check_skills", lambda root: list(synthetic))
    root = tmp_path / "skills"
    root.mkdir()

    js = CliRunner().invoke(main, ["skills", "lint", "--root", str(root), "--format", "json"])
    assert js.exit_code == 0  # WARN-only still exits 0
    assert ("missing-provenance", "warn") in {(i["kind"], i["severity"]) for i in json.loads(js.output)["issues"]}

    txt = CliRunner().invoke(main, ["skills", "lint", "--root", str(root)])
    assert txt.exit_code == 0
    assert "warn: synthetic.md: missing-provenance" in txt.output  # severity-leading render


def test_internal_and_attributed_yield_no_coverage_finding(tmp_path: Path) -> None:
    from science_tool.skills_lint.lint import check_provenance
    internal = _leaf(tmp_path, "i.md", "---\nname: x\ndescription: d\nprovenance: internal\n---\n# X\n")
    attributed = _leaf(tmp_path, "a.md", "---\nname: x\ndescription: d\nsources: [known]\n---\n# X\n")
    assert check_provenance(internal) == []
    assert check_provenance(attributed) == []


def test_contradiction_and_bad_marker_yield_invalid_provenance(tmp_path: Path) -> None:
    from science_tool.skills_lint.lint import check_provenance
    both = _leaf(tmp_path, "b.md", "---\nname: x\ndescription: d\nsources: [k]\nprovenance: internal\n---\n# X\n")
    bad = _leaf(tmp_path, "m.md", "---\nname: x\ndescription: d\nprovenance: nope\n---\n# X\n")
    for leaf in (both, bad):
        issues = check_provenance(leaf)
        assert len(issues) == 1
        assert issues[0].kind == "invalid-provenance"
        assert issues[0].severity == "error"


def test_no_cascade_on_broken_frontmatter(tmp_path: Path) -> None:
    from science_tool.skills_lint.lint import check_provenance
    # Every "classification impossible" shape must yield NO missing-provenance.
    broken = {
        "n.md": "# no frontmatter\n",
        "unterminated.md": "---\nname: x\n# never closes\n",
        "unparsable.md": "---\nfoo: [unclosed\n---\n# X\n",
        "nonmap-list.md": "---\n[]\n---\n# X\n",
        "nonmap-false.md": "---\nfalse\n---\n# X\n",
    }
    for name, body in broken.items():
        leaf = _leaf(tmp_path, name, body)
        assert check_provenance(leaf) == [], name


def test_empty_or_blank_sources_are_invalid_field_not_missing_provenance(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    (skills_root / "sources.yaml").write_text("", encoding="utf-8")
    (skills_root / "INDEX.md").write_text(
        "---\nname: idx\ndescription: d\n---\n# Index\n`skills/e.md`\n`skills/b.md`\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    (skills_root / "e.md").write_text(
        "---\nname: e\ndescription: d\nsources: []\n---\n# E\n## Companion Skills\n- none\n", encoding="utf-8")
    (skills_root / "b.md").write_text(
        '---\nname: b\ndescription: d\nsources: ["  "]\n---\n# B\n## Companion Skills\n- none\n', encoding="utf-8")
    from science_tool.skills_lint.lint import check_skills
    per = {(i.path.as_posix(), i.kind) for i in check_skills(skills_root)}
    assert ("e.md", "invalid-field") in per      # empty list rejected by source-ref check
    assert ("b.md", "invalid-field") in per      # blank string rejected
    assert not any(kind == "missing-provenance" for _, kind in per)  # never cascaded


def test_nonmapping_frontmatter_is_invalid_yaml_not_missing_field(tmp_path: Path) -> None:
    # check_frontmatter's `or {}` used to turn falsy non-mappings ([], false) into
    # {}, which then emitted missing-field for name/description. A non-mapping is an
    # invalid frontmatter document (invalid-yaml), and it must NOT cascade into
    # missing-field or missing-provenance.
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    (skills_root / "sources.yaml").write_text("", encoding="utf-8")
    (skills_root / "INDEX.md").write_text(
        "---\nname: idx\ndescription: d\n---\n# Index\n`skills/lst.md`\n`skills/fls.md`\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    (skills_root / "lst.md").write_text("---\n[]\n---\n# L\n## Companion Skills\n- none\n", encoding="utf-8")
    (skills_root / "fls.md").write_text("---\nfalse\n---\n# F\n## Companion Skills\n- none\n", encoding="utf-8")
    from science_tool.skills_lint.lint import check_skills
    per = {(i.path.as_posix(), i.kind) for i in check_skills(skills_root)}
    for name in ("lst.md", "fls.md"):
        assert (name, "invalid-yaml") in per                        # non-mapping => invalid-yaml
        assert (name, "missing-field") not in per                   # not treated as an empty mapping
        assert (name, "missing-provenance") not in per              # no provenance cascade


def test_missing_provenance_not_double_reported_with_unknown_ref(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    (skills_root / "sources.yaml").write_text("", encoding="utf-8")
    (skills_root / "INDEX.md").write_text("`skills/leaf.md`\n", encoding="utf-8")
    (skills_root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nsources: [ghost]\n---\n# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    from science_tool.skills_lint.lint import check_skills
    kinds = {i.kind for i in check_skills(skills_root)}
    assert "unknown-source-ref" in kinds
    assert "missing-provenance" not in kinds  # sources present => attributed, not undeclared


def test_index_md_excluded_from_coverage(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    # INDEX.md has valid frontmatter but no declaration; must NOT be flagged.
    (skills_root / "INDEX.md").write_text(
        "---\nname: idx\ndescription: d\n---\n# Index\n`skills/leaf.md`\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    (skills_root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nprovenance: internal\n---\n# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    from science_tool.skills_lint.lint import check_skills
    provenance_paths = {i.path.as_posix() for i in check_skills(skills_root) if i.kind == "missing-provenance"}
    assert provenance_paths == set()


