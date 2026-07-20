from pathlib import Path

import pytest

from science_tool.skills_lint.lint import check_skills

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS = REPO_ROOT / "skills"


def test_corpus_has_zero_missing_provenance() -> None:
    issues = check_skills(SKILLS)
    undeclared = sorted(i.path.as_posix() for i in issues if i.kind == "missing-provenance")
    assert undeclared == [], f"undeclared skills: {undeclared}"


@pytest.mark.xfail(
    strict=True,
    reason="Task 2->3 red window: 34 leaves still lack archetype: (see docs/plans/2026-07-20-skills-archetype-backfill-implementation.md). Remove this marker when the backfill lands.",
)
def test_corpus_has_no_error_severity_findings() -> None:
    issues = check_skills(SKILLS)
    errors = [(i.path.as_posix(), i.kind, i.detail) for i in issues if i.severity == "error"]
    assert errors == [], f"error-severity findings: {errors}"


def test_corpus_missing_archetype_count_is_known() -> None:
    # Pins the size of the intentional Task 2 -> Task 3 red window (see xfail marker
    # above). Task 3 backfills archetype: on all 34 leaves, driving this to zero; at that
    # point this test (and the xfail marker) should be deleted, not adjusted further.
    issues = check_skills(SKILLS)
    missing = sorted(i.path.as_posix() for i in issues if i.kind == "missing-archetype")
    assert len(missing) == 34, f"missing-archetype findings ({len(missing)}): {missing}"
