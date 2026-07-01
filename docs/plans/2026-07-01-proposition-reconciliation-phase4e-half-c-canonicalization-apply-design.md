# Proposition Reconciliation Phase 4e Half C: Canonicalization Apply

Date: 2026-07-01

## 1. Goal

Phase 4e Half A generates deterministic reconciliation candidates and validates
reviewed judgments. Half B turns accepted judgments into a read-only action plan.
Half C adds the first mutation surface, but only for the deterministic action kind:
reviewed `same_claim` judgments that Half B reports as `canonicalize_propositions`.

Half C should:

- consume reviewed reconciliation JSON files;
- rebuild the current Half B action plan from the live corpus;
- select only ready `canonicalize_propositions` actions;
- apply their mechanical writes;
- report exactly what changed and what was already a no-op.

The command is intentionally not a general reconciliation executor. It does not
mint new proposition wording, run an agent, apply factorization resynthesis, change
belief aggregation, or delete proposition files. `resynthesize_proposition` remains
non-applicable in this phase.

## 2. Scope

In scope:

- applying ready `canonicalize_propositions` actions from reviewed `same_claim`
  judgments;
- moving duplicate proposition `source_refs` onto the canonical proposition;
- rewriting annotation sidecar `promoted_to` backlinks from duplicates to the
  canonical proposition;
- marking duplicate proposition files as superseded while preserving them for
  auditability;
- idempotent re-run behavior;
- table and JSON apply reports.

Out of scope:

- applying `resynthesize_proposition`;
- minting narrower propositions;
- drafting claim text or factorized claim families;
- applying advisory or blocked actions;
- consuming saved Half B plan JSON as executable authority;
- deleting proposition files;
- moving proposition files into archive storage;
- materializing the graph as an implicit side effect.

## 3. CLI Surface

Add a new flat `annotate` command:

```text
science annotate apply-proposition-reconciliation \
  --input results/proposition-reconciliation/review.json \
  [--input another-review.json] \
  [--root .] \
  [--action reconcile-action:...] \
  [--format table|json]
```

Behavior:

- `--input` is repeatable and required, matching `plan-proposition-reconciliation`;
- `--root` defaults to the current working directory;
- `--format table` prints a compact summary and changed/no-op paths;
- `--format json` prints the full apply report;
- without `--action`, the command applies all ready `canonicalize_propositions`
  actions from the rebuilt current plan;
- with `--action`, every named action must exist, be ready, and have kind
  `canonicalize_propositions`.

The command rebuilds the current reconciliation report and Half B action plan from
the reviewed inputs. It does not trust a saved action-plan JSON artifact for writes.
That keeps staleness handling in one place: the existing review validation and
current-corpus action planner.

There is no `--apply` flag. The command name is the mutation boundary. Preview
remains the read-only `plan-proposition-reconciliation` command.

## 4. Action Selection

An action is applicable only when all of the following are true:

- it is present in the freshly rebuilt action plan;
- `kind == "canonicalize_propositions"`;
- `status == "ready"`;
- it has no blockers;
- every member proposition still has a current proposition snapshot;
- no selected member is also targeted by another selected action.

The command refuses before writing if:

- any requested `--action` is unknown;
- any requested action is blocked, advisory, or not `canonicalize_propositions`;
- the rebuilt plan has top-level reconciliation errors;
- the applicable action set is empty;
- any selected action overlaps a blocked/advisory/conflicting action in a way that
  would make the write ambiguous.

Selecting `resynthesize_proposition` is a hard error with a phase-specific message:
factorization resynthesis needs a reviewed drafting step and is not executable by
Half C.

## 5. Write Semantics

For each selected `canonicalize_propositions` action with canonical proposition
`A` and duplicate members `B...N`, apply these mechanical writes.

### Canonical Proposition

Append each duplicate proposition's `source_refs` to the canonical proposition's
`source_refs`.

Rules:

- preserve the canonical proposition body;
- preserve all non-`source_refs` frontmatter fields except `updated`;
- keep existing canonical `source_refs` in their current order;
- append new refs in deterministic sorted order;
- deduplicate by exact string identity;
- update `updated` only when the canonical file content changes.

### Duplicate Propositions

Each duplicate proposition remains on disk for auditability.

Rules:

- set `status: superseded`;
- set `superseded_by: <canonical proposition>`;
- preserve duplicate body;
- preserve duplicate `source_refs`;
- update `updated` only when the duplicate file content changes;
- do not delete the duplicate file;
- do not move it into archive storage in Half C.

Half C should not initially add a `relations: sci:supersedes` edge. The canonical
`superseded_by` field is already recognized by archive/materialize surfaces, while
relation authoring has additional model-validation and convention questions. A later
phase may add explicit supersession relations once that behavior is designed.

### Sidecar Backlinks

For every annotation ref listed in `inputs.sidecar_backlink_rewrites`, load the
referenced sidecar and rewrite only the matching annotation.

Rules:

- if the annotation's `promoted_to` is the duplicate proposition, set it to the
  canonical proposition;
- if it is already the canonical proposition, count it as a no-op confirmation;
- any other `promoted_to` value is a preflight error;
- preserve status, creator, created, modified fields, bodies, selectors,
  `content_hash`, and all other annotation metadata;
- preserve unrelated annotations in the same sidecar.

## 6. Preflight And Atomicity

Apply is two-phase.

Preflight is pure and must finish before any file is written:

- rebuild the current reconciliation report and action plan;
- resolve and validate selected actions;
- resolve every proposition path and sidecar path;
- verify every duplicate proposition exists;
- verify every listed annotation ref resolves to exactly one sidecar annotation;
- verify every backlink currently points either to its duplicate or already to the
  canonical proposition;
- compute the final text for every touched file in memory;
- detect path collisions or two selected actions attempting different final text for
  the same file.

If preflight fails, no files are written.

The write phase writes only files whose final text differs from the current text,
using existing atomic file replacement helpers. Files are written in deterministic
path order.

Half C should fail loud on write-phase I/O errors. It should not claim full
multi-file transaction rollback: per-file atomic replacement protects individual
files, but a filesystem error can still happen after earlier files were written.
The apply report/error should include the stage and already-written paths. Re-run
is safe because every write is idempotent.

## 7. Idempotency

A successful apply followed by the same command should produce no additional file
changes.

Idempotent confirmations:

- canonical already contains a moved source ref;
- sidecar annotation already points to the canonical proposition;
- duplicate proposition is already `status: superseded`;
- duplicate proposition already has the expected `superseded_by` value.

Conflicting current state remains an error:

- sidecar annotation points to a third proposition;
- duplicate has `superseded_by` set to a different target;
- canonical proposition is missing;
- duplicate proposition is missing;
- action membership has drifted and no longer validates through Half B.

## 8. Postflight Validation

After writes, the command should rebuild enough project state to verify the applied
semantic effect:

- selected duplicate propositions are marked superseded;
- selected duplicates have `superseded_by` set to the canonical proposition;
- selected sidecar backlinks now point to the canonical proposition;
- canonical proposition `source_refs` include all moved refs;
- rebuilt cross-paper assertion scanning no longer attributes the moved sidecar
  assertions to the duplicate propositions.

If there is a narrow in-process validation entry point for proposition source refs
and Phase 4d literature assertions, the command may run it. It should not
materialize the full graph implicitly. Graph rebuild remains an explicit project
operation.

Half C does not require the Half A candidate generator to stop surfacing a same-claim
candidate for superseded files. Current reconciliation scanning snapshots proposition
entities without a lifecycle filter, so candidate disappearance is not a safe
postcondition unless a separate active-scope change is designed.

## 9. Module Shape

Add a narrow apply module:

```text
science_tool.annotation.proposition_reconciliation_apply
```

Suggested core types:

- `ReconciliationApplySelection`: selected action ids, or all canonicalization
  actions;
- `PlannedFileEdit`: path, before hash, after hash, reason;
- `ReconciliationApplyPlan`: selected actions plus pure computed file edits;
- `ReconciliationApplyReport`: applied action ids, changed paths, no-op paths,
  refused actions/errors.

Suggested core functions:

- `plan_reconciliation_apply(project_root, reviews, action_ids=...)`;
- `apply_reconciliation_plan(plan)`;
- `reconciliation_apply_report_to_json(report)`.

Half C consumes Half B's `ReconciliationActionPlan` but does not add executable
write payloads back into it. Half B remains read-only.

## 10. Apply Report

JSON report shape should be versioned and explicit:

```json
{
  "schema_version": 1,
  "source_reviews": ["results/proposition-reconciliation/review.json"],
  "selected_actions": ["reconcile-action:..."],
  "summary": {
    "applied_actions": 1,
    "changed_files": 3,
    "noop_files": 0,
    "refused_actions": 0
  },
  "actions": [
    {
      "action_id": "reconcile-action:...",
      "kind": "canonicalize_propositions",
      "canonical_proposition": "proposition:a",
      "members": ["proposition:a", "proposition:b"],
      "changed_paths": [
        "entities/propositions/a.md",
        "entities/propositions/b.md",
        "entities/papers/Smith2020.source.anno.trig"
      ],
      "noop_paths": []
    }
  ],
  "errors": []
}
```

Table output should be compact:

```text
proposition reconciliation apply: applied=1 changed=3 noop=0 refused=0
applied  canonicalize_propositions  proposition:a  members=2  changed=3
```

## 11. Tests

Unit tests:

- refuses `resynthesize_proposition`;
- refuses blocked/advisory actions;
- refuses stale or missing action ids;
- moves duplicate `source_refs` onto canonical with deterministic dedup;
- rewrites only matching sidecar `promoted_to` backlinks;
- marks duplicates `superseded` with `superseded_by`;
- preserves unrelated sidecar annotations;
- second apply is a no-op;
- preflight failure writes nothing;
- selected `--action` applies only that action;
- write planning detects two selected actions that would produce conflicting text for
  one path.

CLI tests:

- command exists and requires `--input`;
- table output summarizes applied canonicalization;
- JSON output includes changed paths and no-op confirmations;
- selecting a non-canonicalization action exits non-zero;
- malformed review errors include the review path.

End-to-end fixture:

- create two proposition files with a reviewed `same_claim` judgment;
- create paper sidecars promoted to duplicate and canonical propositions;
- apply;
- rebuild cross-paper evidence;
- assert evidence now aggregates on the canonical proposition and the duplicate is
  superseded.

## 12. Non-Goals And Future Work

Future work may add:

- a reviewed factorization drafting/resynthesis workflow for `resynthesize_proposition`;
- explicit `sci:supersedes` relation authoring if model and validation conventions are
  pinned down;
- archive-tier movement for long-settled superseded propositions;
- saved-plan execution with a separate stale-plan validation protocol.

None of those are required for Half C. The first apply surface should be narrow,
review-backed, deterministic, and idempotent.
