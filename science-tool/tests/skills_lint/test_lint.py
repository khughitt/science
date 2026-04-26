from pathlib import Path
from shutil import copytree

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.skills_lint.lint import SkillIssue, check_frontmatter

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


def test_lint_cli_against_fixtures(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    copytree(FIXTURES, skills_root)

    result = CliRunner().invoke(main, ["skills", "lint", "--root", str(skills_root)])

    assert result.exit_code == 1
    assert "bad-no-frontmatter.md" in result.output
    assert "bad-missing-name.md" in result.output
    assert "bad-missing-description.md" in result.output
    assert "good.md" not in result.output


def test_skill_issue_json_uses_posix_path() -> None:
    issue = SkillIssue(Path("nested") / "bad.md", "missing-frontmatter")

    assert issue.to_json() == {
        "path": "nested/bad.md",
        "kind": "missing-frontmatter",
        "field": None,
        "detail": "",
    }
