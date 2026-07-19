from pathlib import Path

from science_tool.numeric_provenance import build_document_context
from science_tool.numeric_verification import (
    VerificationResult,
    coverage_from_results,
    run_numeric_verification,
)

# Task-7 fixtures: committed, built by tests/fixtures/numeric_verification/_build.py.
# summary.feather:    metric=["auc"], score=[0.978]           (single row, no `where` needed)
# results.json:       {"nested": {"b/c": 42, ...}, ...}        (pointer /nested/b~1c -> 42)
_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "numeric_verification"

_KWARGS = dict(max_json_bytes=1_000_000, max_feather_bytes=1_000_000)


def _doc(tmp_path: Path, fm: str, body: str):
    path = tmp_path / "e.md"
    path.write_text(f"---\n{fm}\n---\n{body}\n")
    return build_document_context(path)


_MAIN_FM = """\
numeric_claims:
  v1:
    artifact: summary.feather
    locator: {column: score}
  m1:
    artifact: results.json
    locator: {pointer: /nested/b~1c}
  e1:
    artifact: missing.json
    locator: {pointer: /x}
  o1:
    artifact: results.json
    locator: {opaque: "described in text"}
  o2:
    artifact: missing2.txt
    locator: {opaque: "see figure"}"""

_MAIN_BODY = """\
Accuracy on the holdout set was **0.978**[^v1] overall.

The nested value used in this claim was **99**[^m1] units.

A separate figure claims **7**[^e1] from an artifact that does not exist.

As described elsewhere, the result was **5**[^o1] in the appendix.

Another opaque figure shows **6**[^o2] from a missing file."""


def test_run_numeric_verification_per_binding_outcomes(tmp_path):
    document = _doc(tmp_path, _MAIN_FM, _MAIN_BODY)

    issues, results = run_numeric_verification(
        document, _FIXTURES_DIR, _FIXTURES_DIR, **_KWARGS
    )

    outcomes = {r.id: r.outcome for r in results}
    assert outcomes == {
        "v1": "verified",
        "m1": "mismatch",
        "e1": "error",
        "o1": "unverifiable",
        "o2": "error",
    }
    assert all(isinstance(r, VerificationResult) for r in results)
    assert all(isinstance(r.line, int) for r in results)

    # LintIssues exist only for the mismatch and the two errors -- the
    # verified and unverifiable outcomes are silent (counted, not flagged).
    by_match = {i.match: i for i in issues}
    assert set(by_match) == {"99", "7", "6"}
    assert all(i.severity == "warn" for i in issues)
    assert all(i.check == "numeric-verification" for i in issues)

    assert coverage_from_results(results) == {
        "verified": 1,
        "unverifiable": 1,
        "mismatch": 1,
        "error": 2,
    }


_PERCENT_FM = """\
numeric_claims:
  p_present:
    artifact: results.json
    locator: {pointer: /nested/b~1c}
  p_missing:
    artifact: missing3.json
    locator: {pointer: /x}"""

_PERCENT_BODY = """\
The share reported was **42%**[^p_present] of the cohort.

Another share reported was **5%**[^p_missing] of the cohort."""


def test_percent_claims_resolve_first_and_fail_closed(tmp_path):
    # A `%`-unit literal never reads content (content=False, like opaque) --
    # but a missing/escaping artifact must still surface as an error, not a
    # silently-skipped unverifiable. This is the same fail-closed property
    # the opaque case proves, exercised on the percent-detection path.
    document = _doc(tmp_path, _PERCENT_FM, _PERCENT_BODY)

    issues, results = run_numeric_verification(
        document, _FIXTURES_DIR, _FIXTURES_DIR, **_KWARGS
    )

    outcomes = {r.id: r.outcome for r in results}
    assert outcomes == {"p_present": "unverifiable", "p_missing": "error"}
    assert [i.match for i in issues] == ["5%"]
    assert issues[0].severity == "warn"


_LIST_FM = """\
numeric_claims:
  - a
  - b"""


def test_non_mapping_numeric_claims_is_document_level_error(tmp_path):
    document = _doc(tmp_path, _LIST_FM, "Some text with no markers at all.")

    issues, results = run_numeric_verification(
        document, _FIXTURES_DIR, _FIXTURES_DIR, **_KWARGS
    )

    assert results == [
        VerificationResult(
            id=None,
            line=1,
            outcome="error",
            detail="numeric_claims frontmatter must be a mapping",
        )
    ]
    assert len(issues) == 1
    issue = issues[0]
    assert issue.line == 1
    assert issue.col == 1
    assert issue.match == "numeric_claims"
    assert issue.severity == "warn"
    assert issue.check == "numeric-verification"

    assert coverage_from_results(results) == {
        "verified": 0,
        "unverifiable": 0,
        "mismatch": 0,
        "error": 1,
    }
