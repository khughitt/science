mm30 DAG fixture source
=======================

Branch: main
Commit: 183cde8b51d97ec57ef80b718fdd18c1a32318f8
Date: 2026-04-20
Captured-by: Task 4 + follow-up 1 of docs/plans/2026-04-19-dag-rendering-and-audit-pipeline.md

Re-captured after the mm30 migration commit (183cde8) which:
  - Retired the three local DAG scripts
  - Migrated `doi: null` / `author_year`-only lit_support entries to `paper: ...`
    refs, unblocking the previously `xfail(strict=True)` schema-validation tests.

The four `-auto.dot.reference` files remain byte-identical to the pre-migration
versions (Task 5 byte-identity verified post-migration with zero diff).
