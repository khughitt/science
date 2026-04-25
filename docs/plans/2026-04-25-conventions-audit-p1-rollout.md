# Conventions Audit P1 Rollout — Master Plan

**Goal:** Convert the ten P1 findings from the 2026-04-25 downstream conventions audit into shipped Science changes, in a sequenced rollout that respects which findings are implementation-ready vs need a design pass first.

**Source:** `docs/audits/downstream-project-conventions/synthesis.md` (commit `4d27b6d`).

**Status legend:** `pending` / `in-progress` / `ready-for-review` / `approved` / `implementing` / `merged` / `deferred`.

---

## Scope

Ten P1 candidates from the synthesis. Each is in one of three buckets based on readiness:

- **Bucket A — implementation-ready.** Recommendation shape is concrete enough in the synthesis to write a task-level implementation plan now. Migration cost is low/medium.
- **Bucket B — small or additive.** Either an addendum to an in-flight plan or a lightweight convention doc; not a multi-step implementation.
- **Bucket C — needs design pass first.** The synthesis identifies the need; the *shape* requires a focused design doc with user input before implementation planning can proceed.

P2 and P3 candidates from the synthesis are out of scope for this rollout. They can be picked up after Bucket A+B lands and Bucket C designs settle.

## Workflow

For each P1 in Bucket A and Bucket B:

1. **Plan creation.** A sub-agent reads the synthesis + relevant audit reports + a recent in-tree plan as a style reference, then writes a focused implementation plan to `docs/plans/2026-04-25-<slug>.md`. No code changes; planning only.
2. **Plan review.** Either the orchestrator or a `superpowers:code-reviewer` sub-agent reads the plan against the synthesis recommendation and checks: (a) does it match the audit evidence? (b) is the file structure sensible? (c) is the task breakdown coherent and self-contained? (d) does it overreach (touch unrelated surfaces) or underreach (miss recommended pieces)?
3. **Approval gate.** User reviews the plan and approves (or asks for revisions). Plans are not executed without approval.
4. **Implementation.** A sub-agent executes the approved plan task-by-task using `superpowers:executing-plans` or `superpowers:subagent-driven-development`. May be dispatched in parallel with other approved plans if there are no shared files.
5. **Code review.** A `superpowers:code-reviewer` sub-agent reads the implementation against the plan and the synthesis. Checks: (a) every plan task done? (b) tests pass? (c) any unintended changes outside the plan's declared file structure? (d) does the implementation actually solve the audit-surfaced problem?
6. **Merge.** Final approval and commit.

For Bucket C: the workflow is **design doc first**, not implementation plan. Each Bucket C item gets a separate design session with the user; implementation plans only follow approved designs.

## Per-P1 Tracking

Status updated as each P1 progresses through the workflow.

### Bucket A — implementation-ready (dispatched 2026-04-25)

| ID | Title | Plan doc | Plan | Impl | Review |
| --- | --- | --- | --- | --- | --- |
| P1 #2 | Promote `pre-registration` to canonical type | `docs/plans/2026-04-25-pre-registration-canonical-type.md` | ready-for-review | — | — |
| P1 #4 | Synthesis-rollup frontmatter convention | `docs/plans/2026-04-25-synthesis-rollup-frontmatter.md` | ready-for-review | — | — |
| P1 #6 | Auto-archive done tasks (`science-tool tasks archive`) | `docs/plans/2026-04-25-tasks-auto-archive.md` | ready-for-review | — | — |
| P1 #10 | Chained-prior `next-steps` ledger | `docs/plans/2026-04-25-next-steps-chained-prior.md` | ready-for-review | — | — |

### Bucket B — small / additive (dispatched 2026-04-25)

| ID | Title | Plan doc | Plan | Impl | Review |
| --- | --- | --- | --- | --- | --- |
| P1 #7 | MAV addendum: audit-surfaced `mav-input` set | `docs/plans/2026-04-25-mav-audit-addendum.md` | ready-for-review | — | — |
| P1 #9 | Code/notebook → task back-link convention | `docs/plans/2026-04-25-code-task-backlink-convention.md` | ready-for-review | — | — |

### Plan review notes (2026-04-25)

All six plans drafted by parallel sub-agents, then reviewed for cross-plan consistency. Revisions applied:

- **Plans #2 and #4** updated to target both `meta/validate.sh` and `scripts/validate.sh` (the two files have different sha256 at audit time and are kept in lockstep until the in-flight managed-artifact-versioning plan unifies them). Plans #7 and #10 already targeted both. This resolves cross-plan inconsistency in validator-canonical interpretation.
- **Plan #7 Task 1** (`LOCAL_PROFILE` parameterization) verified by reading `meta/validate.sh` lines 87, 111-118: the parameterization is **already in place** in canonical. Agent correctly framed Task 1 as "verify and tighten"; no demotion needed. The natural-systems drift is "natural-systems was patched before the canonical fix landed" — the right resolution is MAV-updating natural-systems, not another canonical change.
- **Plan #2** flagged two shape decisions for reviewer attention: id-prefix mismatch as **error** (matches adjacent notes-id-prefix check at `scripts/validate.sh:543`); validator glob extension to `doc/pre-registrations/*.md` (mm30's canonical placement). Both kept as agent decided.
- **Plan #6** flagged edge case: existing `_write_active` drops file preamble; implementation must read+re-emit verbatim. Test coverage planned. Round-trip cleanliness needs verification during implementation.
- **Plan #7 Task 6** (id-prefix table) explicit dependency on Plan #2 (pre-registration must be canonized first); plan already notes the dependency in its Task 6 section.

### Bucket C — needs design pass first (deferred)

| ID | Title | Status | Notes |
| --- | --- | --- | --- |
| P1 #1 | Multi-axis project profile (or archetype) | deferred | Pair with #3; see synthesis §11.2 |
| P1 #3 | Sanctioned project-local entity-kind extension | deferred | Coupled to #1; cbioportal's `typed-extension` is the working prototype |
| P1 #5 | Per-type / multi-axis status enums + structured `qualifier:` | deferred | Touches every entity family; major schema decisions |
| P1 #8 | Datapackage `<project>:` extension profile + descriptor sidecar shape | deferred | Frictionless extension profile shape; needs Science-blessed naming |

These four become design sessions (with the user) once Bucket A+B lands. Output is a design doc; implementation plans only follow approved designs.

## Review Protocol

**Plan review** (before approval):

- Plan cites at least one concrete evidence path from the audit per recommendation it makes.
- Plan does not invent new shape beyond what the synthesis recommends. Where the synthesis defers a decision, the plan defers it too.
- File structure section names every file the plan will create or modify. Plan does not modify files outside that list.
- Task breakdown is self-contained: each task has `Files`, declarative steps, and a clear acceptance signal (test, lint, manual check).

**Code review** (after implementation):

- Every plan checkbox closed.
- Tests added per plan and passing (`uv run --frozen pytest` or project-equivalent).
- Lint clean (`uv run --frozen ruff check` etc.).
- Diff matches the plan's declared file structure — no incidental changes.
- Synthesis evidence: the implementation actually addresses the audit-surfaced problem (cite the project + paths from the audit that motivated the change).

## Out of Scope

- P2 and P3 candidates from the synthesis (defer until P1 lands).
- Migrating downstream projects to new conventions (the audit was read-only; downstream migrations are a separate cycle).
- The four deferred questions in synthesis §11 beyond the four Bucket C items above (atomic-claim modeling, structured-prose, LinkML codegen, refactor-pair, decision-log).

## Suggested Task Breakdown

- [x] Write this master plan.
- [x] Dispatch six plan-creation sub-agents in parallel for Bucket A+B.
- [ ] Review each plan as it lands; mark `ready-for-review` in the table above.
- [ ] User approval gate per plan; mark `approved`.
- [ ] Dispatch implementation sub-agents for approved plans (parallel where file structures don't overlap).
- [ ] Dispatch code-review sub-agents per implementation; mark `merged` after green.
- [ ] Schedule a Bucket C design session with the user.
