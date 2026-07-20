from pathlib import Path

from science_tool.skills_lint.lint import check_skills

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS = REPO_ROOT / "skills"


def test_corpus_has_zero_missing_provenance() -> None:
    issues = check_skills(SKILLS)
    undeclared = sorted(i.path.as_posix() for i in issues if i.kind == "missing-provenance")
    assert undeclared == [], f"undeclared skills: {undeclared}"


def test_corpus_has_no_error_severity_findings() -> None:
    # missing-archetype is excluded here: this is the intentional Task 2 -> Task 3 red
    # window (docs/plans/2026-07-20-skills-archetype-backfill-implementation.md). Task 2
    # ratchets archetype: to ERROR and *observes* the real corpus fail (34 leaves); Task 3
    # backfills those 34 leaves. See test_corpus_missing_archetype_count_is_known below,
    # which pins the size of the gap and should be deleted once Task 3 closes it.
    issues = check_skills(SKILLS)
    errors = [
        (i.path.as_posix(), i.kind, i.detail)
        for i in issues
        if i.severity == "error" and i.kind != "missing-archetype"
    ]
    assert errors == [], f"error-severity findings: {errors}"


def test_corpus_missing_archetype_count_is_known() -> None:
    # Pins the size of the intentional Task 2 -> Task 3 red window (see comment above).
    # Task 3 backfills archetype: on all 34 leaves, driving this to zero; at that point
    # this test (and the exclusion above) should be deleted, not adjusted further.
    issues = check_skills(SKILLS)
    missing = sorted(i.path.as_posix() for i in issues if i.kind == "missing-archetype")
    assert len(missing) == 34, f"missing-archetype findings ({len(missing)}): {missing}"
