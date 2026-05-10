"""Unit tests for prose_lint detectors."""

from pathlib import Path

from science_tool.prose_lint import (
    detect_bare_author_year,
    detect_frontmatter_inline_gaps,
    detect_short_form_ids,
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
