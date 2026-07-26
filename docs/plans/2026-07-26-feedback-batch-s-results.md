# Feedback Batch S — results

Design: `2026-07-26-feedback-batch-s-design.md`. Branch `feedback-batch-s`,
6 commits. All four filings closed.

| suite | before | after |
|---|---|---|
| science | 10812 passed | **10825 passed**, 7 skipped, 8 deselected |
| model | 1449 passed | **1449 passed** |
| ruff (science, model) | clean | clean |
| pyright | 0 errors | **0 errors, 0 warnings** |

13 new tests: 5 causal, 1 project-root guard, 7 spec-path.

## What each filing turned out to be

### `fb-2026-07-19-001` — larger than filed, and half-fixed in a way that read as done

The filing named one defect ("the causal checks/exporter inspect the
`graph/causal` named graph"). `fc9e0201`, landed the day after filing, fixed the
**exporter** and left both validators. Because the commit message read as a
complete fix and the branch that produced it sat at a merged commit with a clean
tree, the entry looked closable on inspection.

It was not. `scic:causes` has two authoring routes — an entity relation with
`graph_layer: graph/causal`, and an `inquiry:` block flow edge that
`inquiry_compile` writes into `inquiry/<slug>` — and after `fc9e0201` exactly one
of three readers knew both.

**The suite could not have caught this.** `test_causal.py::_causal_relation`
hardcodes `"graph_layer": "graph/causal"`, so every pre-existing causal test
authored the route the readers already knew. Verified empirically rather than
argued: the five new tests were run against the pre-fix source and all five fail
there. The first of them proves a *genuine cycle*, authored as flow edges, was
being reported `causal_acyclicity: pass`.

This is the second recorded instance in one file of a fixture writing the
reader's own convention — `fc9e0201`'s message records the first
(`normalize_slug=True`). A fixture that writes what the reader expects cannot
falsify the reader.

### `fb-2026-07-19-003` — the same defect one layer up

Nothing separate to fix in the toolkit; the repair was making the command route
on the signal S1 now emits. The filing's sharpest observation is preserved
verbatim in the new Vacuous-DAG Mode: a reader who installs pgmpy to clear the
skipped identifiability checks gets *green* results computed over an empty
model, which is worse than the skip it replaced.

### `fb-2026-07-25-008` — conformance, plus one call site nobody counted

Straightforward against the existing precedent (`validate/context.py`).
`project index` has the identical defect and was not in the filing; it is guarded
too. A guard scoped to the reported call sites has a hole by construction.

The `topic_coverage` fixture directory had no `science.yaml` — it was not a
project, and so could not exercise a reader that requires one. Adding it was the
honest fix; loosening the guard to accommodate the fixture would have been the
dishonest one.

### `fb-2026-07-26-020` — a doctrine contradiction, and seven readers not five

`create-project.md` instructed the scaffolder to write
`specs/research-question.md` and `specs/scope-boundaries.md`, then said eleven
lines later: "do not place typed entity owners under `doc/` or `specs/`."
`entity migrate-specs` had already ruled — specs are typed entities — so the
scaffolder contradicted both the migrator and its own next paragraph. That is
why the stale path regenerates: fixing readers alone would leave the writer
re-creating the condition.

The filing counted five readers. There are seven: `sketch-model.md` and
`status.md` read the `research-question` spec the same way. Both fixed.

## Corrections to the design doc

- D1's reader table listed `graph/store/validation.py` as reading route 1 only,
  which is right, but the fix there is not the same shape as the inquiry-scoped
  one: project-wide validation has no member set, so it unions `scic:causes`
  across *every* graph rather than calling `resolve_causal_edges`. A consequence
  worth stating plainly: a "cycle" spanning two inquiries that each declare an
  edge between the same two concepts will now be reported. That is a genuine
  project-level contradiction, but it is a behavior change beyond what the
  filing described, and no fixture exercised it.
- D5 said "five commands plus create-project", inherited from the filing. Seven.

## Two behavior changes a reader should expect

1. `causal_acyclicity` reports **`skip`** on any project with no `scic:causes`
   edges, where it previously reported `pass`. A freshly initialized graph is
   the common case. Two suite assertions asserted uniform `pass` across all rows
   and were updated to assert *no failures* plus an explicit `skip` on that row —
   the guard's substance, minus the vacuous claim.
2. `science project topic-coverage`, `resolve-refs`, `index`, and `spec-path`
   now **exit non-zero** outside a project root rather than returning an empty
   result.

## Not done, deliberately

`fb-2026-07-26-005` stays open. Its remaining half needs the unbuilt XDG state
tier and is owned by the context-budget program, which is live in another
worktree. See the design doc's exclusion note.
