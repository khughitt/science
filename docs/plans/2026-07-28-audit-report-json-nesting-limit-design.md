# Audit report JSON nesting limit

**Date:** 2026-07-28

## Problem

`load_report()` intends to convert pathological JSON nesting into
`IngestError("could not parse ...")`. The existing test relies on CPython's JSON
decoder raising `RecursionError` for 10,000 nested arrays. Python 3.14 accepts
that input, so the report reaches the later "not a JSON object" check instead.
The boundary contract therefore varies by Python version.

## Decision

Add an explicit `MAX_REPORT_NESTING = 100` limit to the audit-report ingestion
boundary. After `json.loads()` succeeds, traverse parsed dictionaries and lists
iteratively and reject any container deeper than the limit with
`IngestError("could not parse ... excessive nesting ...")`.

The traversal is iterative so the enforcement itself does not depend on
Python's recursion limit. Scalar values do not increase depth. The existing
8 MiB report-size limit bounds the work performed by `json.loads()` before the
depth check.

## Error behavior

Existing JSON decoder `ValueError` and `RecursionError` exceptions continue to
be wrapped as `IngestError("could not parse ...")`. Excessive nesting accepted
by a particular decoder version produces the same error category. Ordinary
top-level type and schema validation remain unchanged.

## Testing

The existing 10,000-level input is the red test on Python 3.14. After the
change, it must raise `IngestError` matching both `could not parse` and
`excessive nesting`. Add boundary controls at exactly the allowed depth and one
level beyond it, using a valid audit-report object, so the constant's semantics
cannot drift through an off-by-one error.

Run the focused ingestion tests under Python 3.14 and Python 3.13, then the
model and CLI/tool default suites before cleaning up the feature worktree.

## Rejected alternatives

- A lexical pre-scan would reject before decoding, but it would duplicate JSON
  string and escape handling.
- A custom JSON decoder is more invasive and the standard decoder exposes no
  stable depth-limit hook.
- Replacing the test with malformed JSON would abandon the intended
  pathological-nesting boundary.
