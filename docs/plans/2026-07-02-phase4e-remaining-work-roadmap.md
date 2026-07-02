# Proposition Reconciliation Phase 4e: Remaining Work Roadmap

Date: 2026-07-02

## 1. Purpose

This roadmap tracks the work left after Phase 4e Half A-D:

- Half A: deterministic reconciliation candidates plus reviewed judgment files;
- Half B: read-only action planning from reviewed judgments;
- Half C: narrow apply surface for reviewed `same_claim` canonicalization;
- Half D: narrow scaffold/validate/apply surface for reviewed factorization
  resynthesis.

The shipped path is usable, but several adjacent capabilities remain intentionally
deferred. This document keeps those deferrals visible without turning them into
stale implementation plans.

## 2. Recommended Order

1. **Live lineage visibility.**
   Make live `superseded_by` and `resynthesized_into` frontmatter graph-visible via
   `sci:supersededBy`. This closes the most concrete gap left by Half C/D.

2. **Agent-assisted resynthesis draft filling.**
   Use Half D's scaffold context, observed statement hints, and reviewer rationale
   to draft replacement propositions and annotation assignments. The output remains
   a reviewed draft artifact; apply stays deterministic and mechanical.

3. **Archive movement for settled superseded propositions.**
   Once live lineage is graph-visible and stable, add a deliberate archive path for
   superseded propositions that no longer need to remain in the active entity tree.

4. **Richer claim-family suggestions.**
   Improve factorization candidate context by clustering observed statement hints
   into explainable claim families. This should improve review and draft-filling
   ergonomics without changing belief semantics.

5. **Explicit relation/approval metadata.**
   Add explicit relation authoring or saved-draft approval metadata only when a
   downstream consumer needs more than the current source string and frontmatter
   lineage fields.

## 3. Tracking Items

### Live Lineage Visibility

Status: designed; implementation plan not drafted.

Design doc:
`docs/plans/2026-07-02-phase4e-live-lineage-visibility-design.md`

Scope:

- read live raw frontmatter during graph materialization;
- emit `sci:supersededBy` for live `superseded_by`;
- emit one `sci:supersededBy` edge per `resynthesized_into` target;
- audit graph consumers before implementation so adding live-subject
  `sci:supersededBy` triples does not accidentally trigger archive-only behavior;
- fail loud on malformed or dangling live lineage.

Why first:

Half C/D already write durable lineage. Making that lineage visible in the graph
unblocks later health, archive, and consumer-facing surfaces.

### Agent-Assisted Resynthesis Draft Filling

Status: not designed.

Likely shape:

- input: one Half D scaffold plus the corresponding reviewed Half B judgment;
- output: a completed resynthesis draft JSON file;
- constraints: deterministic validator remains authoritative; agent output is never
  applied directly; manual review/edit remains required before apply.

Open questions:

- whether the command should live under `science annotate` or as a separate agent
  workflow script;
- whether generated proposition ids should be proposed by the agent or constrained
  by a deterministic slugger;
- how much of the reviewer rationale should be copied into replacement proposition
  bodies versus kept only as draft notes.

### Archive Movement For Settled Superseded Propositions

Status: blocked on live lineage visibility.

Likely shape:

- select `status: superseded` propositions with resolvable lineage;
- verify no live sidecar `promoted_to` values still point at the superseded owner;
- move files through existing archive machinery rather than deleting them;
- preserve lineage in the archive index so graph tombstone behavior remains intact.

Open questions:

- when a superseded proposition is "settled" enough to archive;
- whether archive should be manual-only or plan/apply;
- how to handle superseded propositions that still carry historical source refs.

### Richer Claim-Family Suggestions

Status: not designed.

Likely shape:

- improve factorization candidate context by grouping statement hints into small,
  explainable clusters;
- remain deterministic or reviewable; do not use opaque embedding-only decisions as
  executable authority;
- feed review and draft-filling surfaces, not belief aggregation directly.

Open questions:

- whether grouping should use exact subject/object/predicate hints only or include
  lexical similarity;
- how to represent cluster confidence without implying automatic correctness;
- how to keep candidate ids stable when hint clusters change.

### Explicit Relation Or Approval Metadata

Status: deferred.

Possible future additions:

- authored `sci:supersedes` relation records;
- a dedicated `sci:resynthesizedInto` predicate;
- stronger saved-draft approval metadata beyond the source string;
- optional signed approval snapshots for high-stakes project states.

Rationale for deferral:

The current reconciliation apply surfaces already require reviewed files and
deterministic live validation. Additional metadata should be driven by a concrete
consumer need, not added preemptively.

## 4. Non-Goals

This roadmap is not an implementation plan. It should not pin task order inside an
item, exact helper names, or test code. Each item should get its own reviewed design
and implementation plan before code changes begin.
