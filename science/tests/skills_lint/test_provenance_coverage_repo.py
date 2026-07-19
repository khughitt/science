from pathlib import Path

from science_tool.skills_lint.lint import check_skills

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS = REPO_ROOT / "skills"


def test_corpus_has_zero_missing_provenance() -> None:
    issues = check_skills(SKILLS)
    undeclared = sorted(i.path.as_posix() for i in issues if i.kind == "missing-provenance")
    assert undeclared == [], f"undeclared skills: {undeclared}"


def test_corpus_has_no_error_severity_findings() -> None:
    issues = check_skills(SKILLS)
    errors = [(i.path.as_posix(), i.kind, i.detail) for i in issues if i.severity == "error"]
    assert errors == [], f"error-severity findings: {errors}"
