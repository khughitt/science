"""Unit tests for prose_lint detectors."""

from pathlib import Path

from science_tool.prose_lint import (
    LintIssue,
    detect_bare_author_year,
    detect_frontmatter_inline_gaps,
    detect_numeric_anchor,
    detect_short_form_ids,
    scan_root,
)


def _write(tmp_path: Path, body: str, frontmatter: str = "") -> Path:
    path = tmp_path / "doc.md"
    if frontmatter:
        path.write_text(f"---\n{frontmatter}\n---\n{body}")
    else:
        path.write_text(body)
    return path


class TestBareAuthorYear:
    def test_flags_bare_author_year(self, tmp_path):
        path = _write(tmp_path, "As shown in Brunton 2022, the result holds.\n")
        issues = detect_bare_author_year(path)
        assert len(issues) == 1
        assert issues[0].check == "bare-author-year"
        assert issues[0].line == 1
        assert "Brunton 2022" in issues[0].message
        assert issues[0].severity == "warn"

    def test_no_flag_when_anchored(self, tmp_path):
        path = _write(tmp_path, "Brunton 2022 [@brunton2022] showed it.\n")
        assert detect_bare_author_year(path) == []

    def test_no_flag_inside_inline_code(self, tmp_path):
        path = _write(tmp_path, "Use the form `Brunton 2022` as a placeholder.\n")
        assert detect_bare_author_year(path) == []

    def test_no_flag_inside_fenced_code(self, tmp_path):
        path = _write(
            tmp_path,
            "```\nExample: Brunton 2022\n```\nProse here.\n",
        )
        assert detect_bare_author_year(path) == []

    def test_no_flag_inside_frontmatter(self, tmp_path):
        path = _write(
            tmp_path,
            "Body.\n",
            frontmatter='note: "Cited Brunton 2022 in earlier draft"',
        )
        assert detect_bare_author_year(path) == []

    def test_handles_multiple_per_line(self, tmp_path):
        path = _write(tmp_path, "Brunton 2022 and Gilpin 2021 both showed this.\n")
        issues = detect_bare_author_year(path)
        assert len(issues) == 2
        assert {i.message for i in issues} == {
            "bare author-year mention 'Brunton 2022' has no adjacent [@key]",
            "bare author-year mention 'Gilpin 2021' has no adjacent [@key]",
        }


class TestShortFormIds:
    def test_flags_bare_q_number(self, tmp_path):
        path = _write(tmp_path, "See Q1 for the framing question.\n")
        issues = detect_short_form_ids(path)
        assert len(issues) == 1
        assert "Q1" in issues[0].message
        assert "question:" in issues[0].message  # suggestion includes canonical kind

    def test_flags_bare_t_number(self, tmp_path):
        path = _write(tmp_path, "Implemented in t088.\n")
        issues = detect_short_form_ids(path)
        assert len(issues) == 1
        assert "t088" in issues[0].message
        assert "task:" in issues[0].message

    def test_no_flag_canonical_form(self, tmp_path):
        path = _write(tmp_path, "Implemented in task:t088.\n")
        assert detect_short_form_ids(path) == []

    def test_no_flag_inside_code(self, tmp_path):
        path = _write(tmp_path, "Refer to `Q1` as a placeholder.\n")
        assert detect_short_form_ids(path) == []

    def test_no_flag_in_task_list_header(self, tmp_path):
        # tasks/active.md uses `## [t088] Title` as its canonical heading shape.
        path = _write(tmp_path, "## [t088] Some task title\n\nDescription.\n")
        assert detect_short_form_ids(path) == []

    def test_flags_multiple_kinds(self, tmp_path):
        path = _write(tmp_path, "Per Q1 and h05, refer to t050.\n")
        issues = detect_short_form_ids(path)
        # Q1 -> question, h05 -> hypothesis, t050 -> task
        assert len(issues) == 3
        kinds_in_messages = {
            "question:" if "question:" in i.message else
            "hypothesis:" if "hypothesis:" in i.message else
            "task:"
            for i in issues
        }
        assert kinds_in_messages == {"question:", "hypothesis:", "task:"}

    def test_no_flag_on_random_caps(self, tmp_path):
        # "X1" is a generic identifier, not a known short form.
        path = _write(tmp_path, "Variable X1 holds the result.\n")
        assert detect_short_form_ids(path) == []


class TestFrontmatterInlineGap:
    def test_flags_unmentioned_related_entry(self, tmp_path):
        path = _write(
            tmp_path,
            "# Title\n\nNo mention of the related entries.\n",
            frontmatter="related:\n  - task:t050\n  - question:q01-foo",
        )
        issues = detect_frontmatter_inline_gaps(path)
        refs_flagged = {i.message.split("'")[1] for i in issues}
        assert refs_flagged == {"task:t050", "question:q01-foo"}
        for issue in issues:
            assert issue.check == "frontmatter-inline-gap"
            assert issue.severity == "info"
            assert issue.line == 1  # reported at file start

    def test_no_flag_when_mentioned_in_body(self, tmp_path):
        path = _write(
            tmp_path,
            "# Title\n\nSee task:t050 for details.\n",
            frontmatter="related:\n  - task:t050",
        )
        assert detect_frontmatter_inline_gaps(path) == []

    def test_no_flag_when_no_frontmatter(self, tmp_path):
        path = _write(tmp_path, "Just body.\n")
        assert detect_frontmatter_inline_gaps(path) == []

    def test_no_flag_when_no_related_field(self, tmp_path):
        path = _write(
            tmp_path,
            "# Title\n\nBody.\n",
            frontmatter="id: question:q01-foo",
        )
        assert detect_frontmatter_inline_gaps(path) == []

    def test_strict_promotes_severity(self, tmp_path):
        path = _write(
            tmp_path,
            "Body without mention.\n",
            frontmatter="related:\n  - task:t050",
        )
        issues = detect_frontmatter_inline_gaps(path, strict=True)
        assert all(i.severity == "warn" for i in issues)


class TestNumericAnchor:
    def test_flags_unanchored_numeric_claim(self, tmp_path):
        path = _write(tmp_path, "The correlation rho = 0.168 was observed.\n")
        issues = detect_numeric_anchor(path)
        assert len(issues) == 1
        assert issues[0].check == "numeric-anchor"
        assert issues[0].severity == "info"
        assert "0.168" in issues[0].message

    def test_no_flag_when_anchored_with_task(self, tmp_path):
        path = _write(tmp_path, "We measured rho = 0.168 (task:t050).\n")
        assert detect_numeric_anchor(path) == []

    def test_no_flag_when_anchored_with_pipeline(self, tmp_path):
        path = _write(tmp_path, "Result: 30% accuracy from pipeline/t099/results.\n")
        assert detect_numeric_anchor(path) == []

    def test_no_flag_when_anchored_with_bibtex(self, tmp_path):
        path = _write(tmp_path, "Reported as 0.168 in the paper [@brunton2022].\n")
        assert detect_numeric_anchor(path) == []

    def test_no_flag_in_section_header(self, tmp_path):
        path = _write(tmp_path, "## 3.2 Methods\n\nText.\n")
        assert detect_numeric_anchor(path) == []

    def test_no_flag_on_year_alone(self, tmp_path):
        # Years are too noisy to flag as bare numerics.
        path = _write(tmp_path, "In 2022, the model was published.\n")
        assert detect_numeric_anchor(path) == []

    def test_flags_percent_claim(self, tmp_path):
        path = _write(tmp_path, "Improvement of 47% was observed.\n")
        issues = detect_numeric_anchor(path)
        assert len(issues) == 1

    def test_custom_anchor_patterns(self, tmp_path):
        # Caller passes in extended anchors; "doc/" should now count.
        path = _write(tmp_path, "Result rho = 0.168 (see doc/notes/foo.md).\n")
        issues = detect_numeric_anchor(path, anchor_patterns=["task:", "doc/"])
        assert issues == []


class TestScanRoot:
    def test_scans_doc_tree_with_all_checks(self, tmp_path):
        (tmp_path / "doc").mkdir()
        (tmp_path / "doc" / "a.md").write_text(
            "# A\n\nAs Brunton 2022 showed, the result rho = 0.168 holds.\n"
        )
        (tmp_path / "doc" / "b.md").write_text(
            "---\nrelated:\n  - task:t050\n---\n# B\n\nNo mention.\n"
        )
        result = scan_root(tmp_path)
        assert result["counts"]["bare-author-year"] == 1
        assert result["counts"]["numeric-anchor"] >= 1
        assert result["counts"]["frontmatter-inline-gap"] == 1
        assert all(isinstance(h, LintIssue) for h in result["hits"])

    def test_filters_by_check(self, tmp_path):
        (tmp_path / "doc").mkdir()
        (tmp_path / "doc" / "a.md").write_text(
            "# A\n\nBrunton 2022 and rho = 0.168.\n"
        )
        result = scan_root(tmp_path, checks=["bare-author-year"])
        assert "numeric-anchor" not in result["counts"]
        assert result["counts"]["bare-author-year"] == 1

    def test_skips_non_markdown(self, tmp_path):
        (tmp_path / "doc").mkdir()
        (tmp_path / "doc" / "a.txt").write_text("Brunton 2022\n")
        result = scan_root(tmp_path)
        assert result["counts"] == {}
