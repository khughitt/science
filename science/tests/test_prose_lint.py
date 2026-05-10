"""Unit tests for prose_lint detectors."""

from pathlib import Path

from science_tool.prose_lint import detect_bare_author_year


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
