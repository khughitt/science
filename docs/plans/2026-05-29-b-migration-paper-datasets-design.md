# B-Migration: Paper Dataset Usage Transition

Date: 2026-05-29

Status: design drafted; implementation plan next

Related:
- `docs/plans/2026-05-26-bio-dataset-influence-provenance-design.md` — Pillar B north star and B1/B2 split
- `docs/plans/2026-05-29-b1-dataset-influence-provenance-plan.md` — implemented B1 usage-node materialization and tolerant checks
- `science/src/science_tool/graph/dataset_usage.py` — B1 projection rules for authored `dataset_usage`, legacy `paper.datasets`, derivation inputs, and gene-set rows
- `science/src/science_tool/validate/checks/dataset_influence.py` — B1 validation warnings for legacy/conflicting `paper.datasets`
- `science/src/science_tool/graph/migrate.py` — existing graph migration/audit helpers

---

## 1. Purpose And Scope

B1 deliberately left `paper.datasets` as an additive transition input. That was the right compatibility
choice for introducing `dataset_usage`, but it must not become permanent architecture. This migration
phase gives projects a mechanical path from the legacy paper field to the canonical structured field.

The end state is simple: papers express dataset dependence through `dataset_usage`; `paper.datasets`
becomes empty or absent in migrated source files. B1 can still read legacy inputs during the transition,
but after this migration exists, later phases can escalate legacy use from warning to error and then
remove the field from the paper schema.

This phase is intentionally mechanical. It does not change graph materialization semantics, B2
independence interpretation, belief aggregation, or dataset-reference resolution. It only rewrites paper
frontmatter where the rewrite is lossless.

---

## 2. Current State

B1 materializes paper dataset dependence from two surfaces:

- canonical `dataset_usage` entries, with authored `role` and `overlap`;
- legacy `datasets` entries, projected as `role: analyzed`, `overlap: unknown`,
  `usageSource: paper.datasets`.

If both fields reference the same dataset, B1 treats `dataset_usage` as canonical for that ref and does
not double-materialize the legacy entry. The validate check warns when legacy `datasets` is still used,
and warns on same-ref conflicts when the explicit usage has a non-`analyzed` role.

That graph behavior is enough for B1. It is not enough for the long-term model, because authors can keep
adding the ambiguous legacy field and future B2 logic has to keep remembering that `paper.datasets` means
"analyzed with unknown overlap." This migration closes that gap.

---

## 3. Migration Contract

### B-M1 -- Lossless Projection

For each paper frontmatter document:

```yaml
datasets:
  - dataset:gtex-v8
```

the migration adds a canonical usage entry:

```yaml
dataset_usage:
  - ref: dataset:gtex-v8
    role: analyzed
    overlap: unknown
```

After all legacy refs are represented in `dataset_usage`, the `datasets` field is removed from that
paper frontmatter. Removing an empty `datasets: []` is allowed.

The migration preserves existing `dataset_usage` entries and appends only missing refs. It must be
idempotent: running it twice produces the same file content after the first successful run.

### B-M2 -- Same-Ref Merge Rules

The migration operates per dataset ref:

| Existing state | Migration behavior |
|---|---|
| ref in `datasets`, no explicit `dataset_usage` for ref | append `{ref, role: analyzed, overlap: unknown}` |
| ref in `datasets`, explicit `dataset_usage` has `role: analyzed` | keep explicit entry, remove legacy ref |
| ref in `datasets`, explicit `dataset_usage` has non-`analyzed` role | conflict; leave that paper unchanged |
| `datasets` is empty or absent | no rewrite |
| `datasets` is malformed | conflict; leave that paper unchanged |
| `dataset_usage` is malformed | conflict; leave that paper unchanged |

The `overlap` value on an existing analyzed entry is not a conflict. For example, `role: analyzed`,
`overlap: full` is a valid refinement of the legacy meaning and should not block migration.

### B-M3 -- Conflict Handling

Conflicts are reported, not guessed through. A paper is unchanged if the tool cannot prove the rewrite is
lossless. Other non-conflicting papers in the project may still be migrated in the same run.

Conflict rows should include:

- source file path,
- paper id when available,
- conflicted dataset ref when applicable,
- reason code,
- short human-readable detail.

The implementation should avoid partial rewrites within one paper. Either that paper's legacy field is
fully removed and missing usage entries are added, or the file is left untouched.

---

## 4. Tooling Shape

The migration should be exposed as a dry-run-first CLI under the existing graph migration surface:

```bash
science graph migrate-paper-datasets --project-root . --format table
science graph migrate-paper-datasets --project-root . --format json
science graph migrate-paper-datasets --project-root . --apply
```

Dry-run is the default and reports the files that would change plus conflicts. `--apply` writes the
rewrites.

The pure implementation should live outside the CLI, likely as a focused helper module or focused
functions near `science_tool.graph.migrate`, so tests can exercise frontmatter rewriting without invoking
Click. The CLI should only load paths, call the pure planner/apply functions, format results, and set the
exit code.

The migration should scan the same project source surfaces used by graph source loading, but it should
rewrite only paper markdown/frontmatter files. It should not edit commons, generated graph artifacts, task
files, or gene-set member resources.

---

## 5. YAML And Formatting Policy

This is a source rewrite, so formatting churn matters. The implementation should preserve the markdown
body and rewrite only the YAML frontmatter block.

The exact frontmatter formatting does not need to preserve comments or original key order perfectly, but
it should be deterministic and minimal:

- body content after the closing `---` is preserved byte-for-byte;
- frontmatter remains a YAML mapping;
- `dataset_usage` is emitted as a normal block list of mappings;
- `datasets` is omitted after successful migration;
- unrelated frontmatter fields are preserved.

If the current parser cannot round-trip a file safely, the tool should report a conflict and leave the
file unchanged. Silent best-effort rewrites are not acceptable for migration code.

---

## 6. Validate And Policy Handoff

This phase does not immediately change B1 validation severities. The B1 check may continue warning on
legacy `paper.datasets` while downstream projects migrate.

The design handoff for later phases is explicit:

1. **B-migration lands:** projects have a dry-run/apply tool and tests for the lossless rewrite.
2. **Migration campaign:** local and downstream projects run the tool, review conflicts, and commit
   source rewrites.
3. **Policy escalation:** `dataset-influence.paper-datasets-legacy` can move from WARNING to ERROR.
4. **Schema cleanup:** `paper.datasets` is removed from the canonical paper schema/template after the
   ecosystem no longer depends on it.

The implementation plan for this phase should not perform steps 3 or 4. It should make those future
steps straightforward and tracked.

---

## 7. Tests And Acceptance Criteria

The implementation should be accepted only when these behaviors are covered:

- dry-run reports a paper with legacy `datasets` and does not write files;
- apply adds missing `dataset_usage` entries and removes `datasets`;
- same-ref existing `role: analyzed`, `overlap: full` is treated as already migrated, not a conflict;
- same-ref existing non-`analyzed` usage reports a conflict and leaves the file unchanged;
- malformed legacy or canonical fields report conflicts and leave files unchanged;
- running apply twice is idempotent;
- CLI JSON and table outputs include changed files and conflicts;
- existing B1 graph materialization and dataset-influence validate tests still pass after migration code
  is added.

---

## 8. Non-Goals

This migration does not infer overlap beyond `unknown`, does not promote unresolved dataset refs, does
not rewrite `dataset_usage` outside papers, does not touch D1 gene-set row provenance, and does not alter
belief aggregation. It is a one-purpose transition tool: remove `paper.datasets` when doing so is
mechanically safe.
