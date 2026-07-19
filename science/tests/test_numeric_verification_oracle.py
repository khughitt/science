"""Task 14: oracle-labeled acceptance test for numeric-provenance Part B.

Exercises the full stack end to end against fixture entities under
`tests/fixtures/numeric_verification/entities/`, whose `numeric_claims`
bind to the committed feather/json fixtures from Task 7. Every binding's
expected outcome is labeled in `oracle.jsonl` -- one row per
`(file, id) -> expected_outcome`, reflecting DESIGN, not whatever the
engine happens to produce (Part-A oracle discipline, carried into Part B).

Two independent things are asserted:

1. Per-binding outcomes: `run_numeric_verification` returns one
   `VerificationResult` per binding (plus one per binding-declaration
   error). This is the ONLY way to see the silent `verified`/`unverifiable`
   outcomes -- they never emit a `LintIssue`. Every oracle row must match,
   and every actual result must be covered by an oracle row (no
   untracked/no missing bindings).
2. Composition + coverage via `scan_root`: a bound claim's span must draw
   NO `numeric-anchor` finding (Part-A/Part-B suppression working end to
   end), a control UNBOUND ungrounded number must still draw one (Part-A
   behavior unchanged by Part B's existence), and
   `coverage["numeric-verification"]` must aggregate to the same tallies
   as the oracle rows.

Symlink-escape is covered in Task 6 -- not restaged here.
"""

from __future__ import annotations

import json
from pathlib import Path

from science_tool.numeric_provenance import build_document_context
from science_tool.numeric_verification import run_numeric_verification
from science_tool.prose_lint import scan_root

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "numeric_verification"
_ORACLE_PATH = _FIXTURES_DIR / "oracle.jsonl"

_KWARGS = dict(max_json_bytes=1_000_000, max_feather_bytes=1_000_000)

# The control unbound ungrounded number (Part-A only -- never a numeric_claims
# binding, so it has no oracle row of its own): "482" in claims.md, its own
# paragraph, with no anchor-pattern text, task:/[@/dataset:/cite: reference,
# or stipulated marker anywhere nearby.
_CONTROL_FILE = "entities/claims.md"
_CONTROL_LINE = 37
_CONTROL_MATCH = "482"


def _load_oracle() -> list[dict]:
    rows = []
    with _ORACLE_PATH.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            rows.append(json.loads(raw_line))
    return rows


_ORACLE_ROWS = _load_oracle()


def test_oracle_file_is_well_formed():
    assert _ORACLE_ROWS, "oracle.jsonl must not be empty"
    required_keys = {"file", "line", "id", "expected_outcome", "reason"}
    valid_outcomes = {"verified", "mismatch", "unverifiable", "error"}
    for row in _ORACLE_ROWS:
        assert required_keys <= row.keys(), row
        assert row["expected_outcome"] in valid_outcomes, row
    # (file, id) pairs must be unique -- each oracle row labels exactly one binding.
    keys = [(row["file"], row["id"]) for row in _ORACLE_ROWS]
    assert len(keys) == len(set(keys)), "duplicate (file, id) oracle rows"


def test_per_binding_outcomes_match_oracle_labels():
    """Every VerificationResult, across every fixture entity, matches its oracle label.

    Also asserts completeness in both directions: no oracle row is left
    unmatched (a stale label) and no actual result is left unlabeled (an
    untracked binding/outcome the oracle forgot to cover).
    """
    oracle_by_file: dict[str, list[dict]] = {}
    for row in _ORACLE_ROWS:
        oracle_by_file.setdefault(row["file"], []).append(row)

    files = sorted(oracle_by_file)
    assert files, "expected at least one fixture entity referenced by the oracle"

    actual_by_file: dict[str, dict[str, tuple[int, str]]] = {}
    issues_by_file: dict[str, int] = {}
    for rel in files:
        path = _FIXTURES_DIR / rel
        document = build_document_context(path)
        assert document is not None, f"failed to build document context for {rel}"
        issues, results = run_numeric_verification(document, _FIXTURES_DIR, _FIXTURES_DIR, **_KWARGS)
        actual_by_file[rel] = {r.id: (r.line, r.outcome) for r in results}
        issues_by_file[rel] = len(issues)

    for rel, rows in oracle_by_file.items():
        actual = actual_by_file[rel]
        for row in rows:
            claim_id = row["id"]
            assert claim_id in actual, f"{rel}: oracle expects a result for id={claim_id!r} but none was produced"
            actual_line, actual_outcome = actual[claim_id]
            assert actual_outcome == row["expected_outcome"], (
                f"{rel}#{claim_id}: expected outcome {row['expected_outcome']!r} (design: {row['reason']}), "
                f"got {actual_outcome!r}"
            )
            assert actual_line == row["line"], (
                f"{rel}#{claim_id}: expected line {row['line']}, got {actual_line}"
            )
        # Completeness: no result for this file is left unlabeled by the oracle.
        expected_ids = {row["id"] for row in rows}
        assert set(actual) == expected_ids, (
            f"{rel}: actual result ids {sorted(actual)} do not match oracle-labeled ids {sorted(expected_ids)}"
        )
        # Silence contract: `verified`/`unverifiable` never emit a LintIssue;
        # `mismatch`/`error` emit exactly one each -- so the file's issue
        # count is fully predictable from the oracle-labeled outcomes alone.
        expected_issue_count = sum(1 for row in rows if row["expected_outcome"] in ("mismatch", "error"))
        assert issues_by_file[rel] == expected_issue_count, (
            f"{rel}: expected {expected_issue_count} LintIssues (mismatch/error rows only), "
            f"got {issues_by_file[rel]}"
        )


def _oracle_tallies() -> dict[str, int]:
    tallies = {"verified": 0, "unverifiable": 0, "mismatch": 0, "error": 0}
    for row in _ORACLE_ROWS:
        tallies[row["expected_outcome"]] += 1
    return tallies


def test_scan_root_composition_and_coverage():
    result = scan_root(_FIXTURES_DIR, checks=["numeric-anchor"], **_KWARGS)

    # --- coverage aggregation matches the oracle tallies exactly. ---
    assert result["coverage"]["numeric-verification"] == _oracle_tallies()

    numeric_anchor_hits = [h for h in result["hits"] if h.check == "numeric-anchor"]
    hit_keys = {(h.file.relative_to(_FIXTURES_DIR).as_posix(), h.line, h.match) for h in numeric_anchor_hits}

    # --- composition: every successfully BOUND claim (i.e. every oracle row
    # that is NOT a binding-declaration error -- orphan1/dup1 never produced a
    # ClaimBinding, so they were never eligible for suppression in the first
    # place) draws NO numeric-anchor finding at its own (file, line, token).
    bound_tokens = {
        ("entities/claims.md", 25, "0.978"),
        ("entities/claims.md", 27, "0.50"),
        ("entities/claims.md", 29, "512"),
        ("entities/claims.md", 31, "744"),
        ("entities/claims.md", 33, "351"),
        ("entities/claims.md", 35, "0.60"),
        ("entities/percent-and-binding-errors.md", 16, "13%"),
    }
    for key in bound_tokens:
        assert key not in hit_keys, f"bound claim {key} unexpectedly drew a numeric-anchor finding: {hit_keys}"

    # --- Part-A unchanged: the control UNBOUND ungrounded number still flags.
    control_key = (_CONTROL_FILE, _CONTROL_LINE, _CONTROL_MATCH)
    assert control_key in hit_keys, f"control unbound claim {control_key} did not draw a numeric-anchor finding"


def test_scan_root_selecting_only_numeric_verification_still_couples_and_matches_oracle():
    # `couple_checks` guarantees numeric-anchor is pulled in too; coverage must
    # be identical regardless of which of the coupled pair was requested.
    result = scan_root(_FIXTURES_DIR, checks=["numeric-verification"], **_KWARGS)
    assert result["coverage"]["numeric-verification"] == _oracle_tallies()
