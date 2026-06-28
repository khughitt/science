# B-Migration: Paper Dataset Usage Transition

Date: 2026-05-29

Status: implemented; see `docs/plans/historical/2026-05-29-b-migration-paper-datasets-plan.md`

Related:
- `docs/plans/historical/2026-05-26-bio-dataset-influence-provenance-design.md` — Pillar B north star and B1/B2 split
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

### B-M1 -- Paper Selection Gate

The migration rewrites only markdown/frontmatter documents whose frontmatter declares `type: paper` or
`kind: paper`. The paper kind is a hard gate: a non-paper entity that happens to carry a `datasets` key
must be ignored. Both keys are accepted because current source adapters normalize legacy `type` and newer
`kind` frontmatter surfaces into entity kind; the migration should not depend on which spelling a paper
has already adopted. The scanner may use the same source surfaces as `load_project_sources`, but selection
is by parsed frontmatter kind rather than by directory name alone.

Malformed frontmatter is not a migration target. It is reported as a conflict row only if the file was
inside a paper source surface and looked like an intended paper file; otherwise it is skipped. The
predicate is concrete: the file is under a source root the graph loader treats as papers, such as
`doc/papers/` or an equivalent profile paper source, and its content begins with a YAML frontmatter fence
(`---`) that cannot be parsed. A malformed markdown file outside the paper source surface is skipped by
this migration.

### B-M2 -- Lossless Projection

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

The migration preserves existing `dataset_usage` entry order and appends only missing refs in their
source `datasets` order. Repeated legacy refs are deduped by first occurrence before appending. It must be
idempotent: running it twice produces the same file content after the first successful run.

The migration is ref-resolution agnostic. A `datasets` entry is moved verbatim if it is syntactically a
`dataset:` ref, even if it does not resolve locally or in commons. Reference-resolution warnings remain
owned by B1 validation and graph audit; this migration must not require commons to be built or available.

### B-M3 -- Same-Ref Merge Rules

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

The same-ref role-conflict predicate must be shared with the B1 validate check's
`dataset-influence.paper-datasets-conflict` behavior: same ref plus explicit role other than `analyzed`
is a conflict; same ref plus explicit `role: analyzed` is not a conflict, regardless of overlap.
The implementation should extract this predicate from the inlined B1 validate logic into a small shared
helper so the migration and validator cannot drift.

The migration remains ref-resolution agnostic, so "same ref" here means the same raw ref string. B1
validation may canonicalize aliases before comparing refs; the migration should not, because doing so
would make this mechanical source rewrite depend on local/commons resolution state.

### B-M4 -- Conflict Handling

Conflicts are reported, not guessed through. A paper is unchanged if the tool cannot prove the rewrite is
lossless. Other non-conflicting papers in the project may still be migrated in the same run.

Conflict rows should include:

- source file path,
- paper id when available,
- conflicted dataset ref when applicable,
- reason code,
- short human-readable detail.

Stable reason codes:

| Code | Meaning |
|---|---|
| `malformed-frontmatter` | paper-like file cannot be parsed as YAML frontmatter |
| `malformed-datasets` | `datasets` is present but is not a list of `dataset:` strings |
| `malformed-usage` | `dataset_usage` is present but is not a list of canonical usage objects |
| `role-conflict` | same ref appears in `datasets` and explicit `dataset_usage` with non-`analyzed` role |
| `roundtrip-failure` | the migration cannot safely rewrite the frontmatter block |

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

Exit-code semantics are pinned for migration-campaign automation:

| Mode/result | Exit code |
|---|---:|
| dry-run, no pending rewrites and no conflicts | 0 |
| dry-run, pending rewrites and no conflicts | 10 |
| dry-run, any conflicts | 20 |
| apply, rewrites applied and no conflicts | 0 |
| apply, no rewrites needed and no conflicts | 0 |
| apply, any conflicts, even if other files were migrated | 20 |

Conflicts take precedence over pending-change status. Codes `10` and `20` are intentionally outside the
normal Click traceback/usage-error range, so automation can distinguish migration state from tool
failure. A non-20 dry-run exit code therefore tells CI whether the project is already migrated (`0`) or
has safe rewrites waiting (`10`).

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

For migrated papers, comments inside the YAML frontmatter block may be lost because the block is
re-serialized. That loss is acceptable for this mechanical migration, but it must be visible in dry-run
file lists and reviewable in the applied diff. Untouched papers are not re-serialized.

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
- non-paper markdown/frontmatter files with a `datasets` key are ignored;
- apply adds missing `dataset_usage` entries and removes `datasets`;
- existing `dataset_usage` order is preserved, missing refs append in legacy source order, and repeated
  legacy refs are deduped;
- same-ref existing `role: analyzed`, `overlap: full` is treated as already migrated, not a conflict;
- same-ref existing non-`analyzed` usage reports a conflict and leaves the file unchanged;
- same-ref role-conflict logic is shared with the B1 validator rather than retyped in two places;
- malformed legacy or canonical fields report stable conflict codes and leave files unchanged;
- malformed frontmatter conflict reporting is deterministic for paper-source files with a YAML fence;
- running apply twice is idempotent;
- syntactically valid but unresolved `dataset:` refs are migrated verbatim and still reported later by
  validation/audit;
- CLI exit codes follow the pinned clean/pending/conflict matrix;
- CLI JSON and table outputs include changed files and conflicts;
- existing B1 graph materialization and dataset-influence validate tests still pass after migration code
  is added.

---

## 8. Non-Goals

This migration does not infer overlap beyond `unknown`, does not promote unresolved dataset refs, does
not rewrite `dataset_usage` outside papers, does not touch D1 gene-set row provenance, and does not alter
belief aggregation. It is a one-purpose transition tool: remove `paper.datasets` when doing so is
mechanically safe.
