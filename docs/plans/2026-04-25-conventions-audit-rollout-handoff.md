# Conventions Audit P1 Rollout — Orchestrator Handoff

**Date written:** 2026-04-25
**Branch:** `main`
**Last commit at handoff:** `a9254b0`
**For:** the next orchestrator picking up this rollout. Read this doc first; it should give you everything you need to continue without re-deriving prior decisions.

---

## TL;DR

A four-project audit of mature downstream Science consumers (`natural-systems`, `mm30`, `protein-landscape`, `cbioportal`) is complete. Ten P1 candidates were identified; six (Buckets A + B) have implementation plans drafted, deep-reviewed, revised twice, and approved-with-fixes by a verification reviewer. Four (Bucket C) are explicitly deferred for a design-pass session with the user. **Next user-visible step: approve the six plans and dispatch implementation sub-agents.**

---

## Motivation

Science has grown across many surfaces (project scaffolding, validation, entity modeling, data provenance, command workflows, graph generation, curation, managed artifacts). Mature downstream projects now contain the best evidence for what real research projects actually need. The audit was commissioned to:

1. Identify conventions stable enough across mature projects to support upstream.
2. Distinguish legitimate project-specific specialization from accidental drift.
3. Surface inconsistencies that are drift, stale scaffolding, or missing model/tooling support.

Findings inform later upstream evolution. The audit itself was read-only against downstream projects — nothing in those repos was modified.

The **user's overarching directive** for this rollout: *"think about what our ideal cohesive end goal looks like and work towards that / avoid taking shortcuts to save time."* Cross-plan coherence and post-rollout end-state quality matter more than throughput.

---

## What's been accomplished

### Phase 0 — audit (commit `4d27b6d`)

- `scripts/audit_downstream_project_inventory.py` — read-only inventory tool with `--self-test`, JSON-canonical + Markdown rendering, deterministic across runs (verified by smoke-test). Lives outside downstream project roots.
- `docs/audits/downstream-project-conventions/inventory/<project>.{json,md}` — four inventory pairs.
- `docs/audits/downstream-project-conventions/projects/<project>.md` — four manual audit reports, one per project, each ~200 lines, structured per `_report-template.md` (10 sections + candidate table).
- `docs/audits/downstream-project-conventions/synthesis.md` — 421-line cross-project synthesis. **§3.3 was corrected post-audit** (see "Known correction" below).
- `docs/audits/downstream-project-conventions/tooling-notes.md` — gaps in the v0 inventory tooling (most resolved during the audit).

### Phase 1 — P1 plan creation + revision (commits `9884dc3`, `17f21de`, `a9254b0`)

Six implementation plans drafted by parallel `general-purpose` sub-agents, then deep-reviewed by six parallel `superpowers:code-reviewer` sub-agents, then revised, then verified by a single consolidated reviewer.

**Bucket A (implementation-ready):**
- P1 #2 — `docs/plans/2026-04-25-pre-registration-canonical-type.md` (5 tasks)
- P1 #4 — `docs/plans/2026-04-25-synthesis-rollup-frontmatter.md` (5 tasks; substantially reworked after deep review)
- P1 #6 — `docs/plans/2026-04-25-tasks-auto-archive.md` (6 tasks)
- P1 #10 — `docs/plans/2026-04-25-next-steps-chained-prior.md` (5 tasks)

**Bucket B (small / additive):**
- P1 #7 — `docs/plans/2026-04-25-mav-audit-addendum.md` (6 tasks; addendum to existing MAV plan)
- P1 #9 — `docs/plans/2026-04-25-code-task-backlink-convention.md` (3 tasks; convention doc only)

**Master rollout plan:** `docs/plans/2026-04-25-conventions-audit-p1-rollout.md` — tracks per-P1 status, lists cross-plan rules, follow-on actions, and the deferred Bucket C items.

### Known correction

Synthesis §3.3 (synthesis rollups) was corrected during the deep-review pass. The original draft claimed "3/4 ship the same shape." Re-verification showed only **2/4** ship structured rollup frontmatter, and they **diverge** on `type:` naming (mm30 uses `type: report` + `report_kind:`; protein-landscape uses `type: synthesis` + separate `type: emergent-threads`). The §3.3 rewrite is in `commit 17f21de`. Top P1 candidate table and Appendix threshold-application notes for §3.3 are also corrected.

### Decisions locked-in (do not re-litigate)

These were explicitly settled by the user during the rollout. A future orchestrator should treat them as fixed:

1. **Type-naming for synthesis rollups:** canonize the cleaner `type: synthesis` + `report_kind:` discriminator (option B). mm30 and protein-landscape both need migration as follow-ons.
2. **Severity for id-prefix mismatch and structural-field absences:** `warn`, not `error`. Applies across plans #2, #4, #7, #10.
3. **Validator file targeting:** until the in-flight managed-artifact-versioning plan unifies, every validator change touches BOTH `meta/validate.sh` and `scripts/validate.sh` in lockstep. Locate insertion sites by content, not absolute line.
4. **No legacy/compatibility layers:** validators stay silent on legacy shapes (`type: plan` pre-regs, `type: report` synthesis files, `prior_analyses:` next-steps). This is the natural consequence of additive type-conformance checks, not a permanent accepted variant. Downstream migrations are tracked as follow-on tasks.
5. **`source_refs:` is NOT part of the canonical pre-registration template** (not in audit evidence). Projects can add it as a project-local extension.
6. **`science-tool tasks archive --check` exits non-zero when lag is non-zero** (CI-gateable). Always emits JSON regardless of exit code.
7. **`docs/conventions/` is a new directory** for cross-cutting convention references; gets a seed `README.md` establishing scope. First entry is `code-task-backlinks.md` (4 sanctioned patterns).
8. **Bucket C is deferred** to a separate user-in-the-loop design session (see "Bucket C" below).

---

## Current state

- **Git:** clean working tree on `main`, last commit `a9254b0`.
- **Master rollout plan status table:** all six plans at `ready-for-review`. The user has approved-in-principle (chose option B + warn + drop source_refs + accepted other defaults) and the verification reviewer issued APPROVE-WITH-FIXES (fixes now applied in `a9254b0`). The remaining gate is final user approval of the post-fix plans.
- **In-session task list:** task #8 ("P1 rollout: user approval gate") is in_progress.

---

## Next steps (in order)

### 1. Final user approval of the six plans

The plans incorporate the user's choices and the verification reviewer's APPROVE-WITH-FIXES. The user has not explicitly said "approved, dispatch implementation" yet at handoff time. Confirm with the user before proceeding.

If they approve: mark each plan's status in the master rollout plan from `ready-for-review` → `approved` and proceed to step 2. If they want further revisions: surface their concerns and apply.

### 2. Implementation phase — dispatch sub-agents

For each approved plan, dispatch a sub-agent using `superpowers:executing-plans` (or `superpowers:subagent-driven-development` for plans with parallelizable tasks). **Parallelization:** plans whose File Structure declarations don't overlap can run in parallel. Concretely:

- **Validator-touching plans (#2, #4, #7, #10)** all modify `meta/validate.sh` and `scripts/validate.sh`. They must run **sequentially** (or be merged carefully) to avoid edit conflicts. Recommended order: #7 first (it's the addendum to MAV which is itself in flight; landing the broader validator changes early reduces rebase pain), then #2, then #4, then #10. Or batch all four into a single sub-agent if context budget allows.
- **Plan #6 (tasks-archive)** touches `science-tool/src/science_tool/{cli.py, graph/health.py, tasks_archive.py}` and tests + `commands/{status.md, next-steps.md}`. No overlap with the validator plans — runs in parallel.
- **Plan #9 (code-task back-link)** touches `docs/conventions/{README.md, code-task-backlinks.md}` (new) and `docs/project-organization-profiles.md`. No overlap with anything — runs in parallel.

Each sub-agent should:
- Use `superpowers:executing-plans` and follow the plan task-by-task.
- Mark each plan checkbox as it lands.
- Stop at any unanticipated obstacle and report back rather than improvising.

### 3. Code review per implementation

After each implementation, dispatch a `superpowers:code-reviewer` sub-agent with the original plan + the diff. Verify: every plan checkbox closed, tests pass, lint clean, diff matches declared file structure, audit-surfaced problem actually addressed.

### 4. Bucket C design session (separate cycle, with user)

Four P1s are explicitly deferred for design rather than direct implementation:

- **P1 #1** — Multi-axis project profile / archetype shape (4/4 projects use `aspects:` as workaround).
- **P1 #3** — Sanctioned project-local entity-kind extension surface (cbioportal's `typed-extension` is the working prototype).
- **P1 #5** — Per-type / multi-axis status enums + structured `qualifier:` (touches every entity family).
- **P1 #8** — Datapackage `<project>:` extension profile + descriptor sidecar shape (Frictionless extension).

These are coupled (especially #1 ↔ #3, and #8 ↔ plan #9's Pattern 3). A future cycle should brainstorm with the user, produce design docs, then write implementation plans.

### 5. Follow-on actions (separate cycles)

Six follow-on actions surface from the audit + plan/review passes; tracked in the master rollout plan's "Follow-on actions" section. Summary:

1. **mm30 synthesis-file migration** — rename `type: report` → `type: synthesis` + `id: report:synthesis-*` → `synthesis:*`. Triggered by plan #4 landing.
2. **protein-landscape synthesis-file migration** — rename `type: emergent-threads` → `type: synthesis` + `report_kind: emergent-threads`. Triggered by plan #4 landing.
3. **`tasks.py` preamble bug** — `_write_active` silently drops file preamble; affects `complete_task`/`retire_task`/`add_task`/`defer_task`. Plan #6 fixes only its own writer.
4. **`science-tool` clean-stdout fix** — `science-tool graph audit/validate/diff` and `inquiry validate` emit non-JSON noise. Triggers protein-landscape's `extract_json_payload` workaround.
5. **natural-systems report-id migration** — 26/31 `doc/reports/*.md` use `id: doc:DATE-slug` instead of `report:DATE-slug`. Plan #7 Task 6 will warn on these once shipped; project can opt out via `SCIENCE_VALIDATE_SKIP_ID_PREFIX=1` while migrating.
6. **Synthesis §3.3 evidence correction** — already applied in commit `17f21de`. No remaining action.

These should NOT block the six P1 implementations. They are downstream-repo migrations or separate Science backlog items.

---

## Cross-plan rules (apply during implementation)

These rules were established during cross-plan review and recorded in the master rollout plan. Honor them during implementation:

- **Validator severity** = `warn` for id-prefix mismatches and structural-field absences.
- **Validator targeting** — every change to `meta/validate.sh` is mirrored in `scripts/validate.sh` (locate by content, not line). Both validators are in the File Structure of every validator-touching plan.
- **No legacy/compatibility layers** — additive type-conformance checks only.
- **Single managed-version bump for the MAV addendum** (plan #7) — all six fixes ship under one `ArtifactDefinition.version` bump, with one entry appended to `previous_hashes`.
- **Forward-compatibility** in plan #7 Task 6's id-prefix table: `pre-registration` and `synthesis` rows ship now and activate when plans #2 and #4 land.

---

## References

**Commits in this rollout chain (chronological):**
- `4d27b6d` — audit deliverables (script + 4 inventories + 4 reports + synthesis + tooling-notes + audit-plan refinements)
- `9884dc3` — six P1 plan drafts + master rollout plan
- `17f21de` — revisions from deep-review pass 2 (substantial plan #4 rework + synthesis §3.3 correction)
- `a9254b0` — staleness fixes from verification pass 3

**Authoritative documents:**
- `docs/plans/2026-04-25-conventions-audit-p1-rollout.md` — master plan; per-P1 status table; cross-plan rules; follow-on actions; deferred Bucket C.
- `docs/audits/downstream-project-conventions/synthesis.md` — cross-project synthesis with all P1/P2/P3 candidates and the priority ladder. **§3.3 carries an explicit "Correction (post-deep-review)" callout** — read it before re-deriving any synthesis-rollup claim.
- The six P1 plans listed above.

**Related in-flight plans (do not duplicate):**
- `docs/plans/2026-04-25-managed-artifact-versioning.md` — the MAV plan that plan #7 is an addendum to. Plan #7 executes after MAV merges.
- `docs/plans/2026-04-25-hypothesis-phase.md` — the hypothesis-phase plan (introducing `phase: candidate | active`). Already informs plan #2's hypothesis-status discussion.

**Audit deliverables to consult during implementation:**
- `docs/audits/downstream-project-conventions/projects/<project>.md` — when an implementation question is "what does <project> actually look like," check this first.
- `docs/audits/downstream-project-conventions/inventory/<project>.json` — for machine-queryable per-project shape data.

---

## Useful context for the next orchestrator

- **Read-only constraint applies to downstream projects.** Do not modify anything under `/home/keith/d/r/{mm30,cbioportal}`, `/home/keith/d/{natural-systems,protein-landscape}`. Migration tasks for those projects are downstream-cycle work.
- **Both `meta/validate.sh` and `scripts/validate.sh` exist** with different sha256 at audit time. The MAV plan (in flight) creates a third copy at `science-tool/src/science_tool/project_artifacts/data/validate.sh` that becomes the package-distributed canonical. Plan #7 (MAV addendum) handles the version bump bookkeeping.
- **Six follow-on actions are NOT blockers** for the six P1 plans. Treat them as separate cycles unless the user prioritizes one.
- **The verification reviewer's full output** is in the conversation history that produced commit `a9254b0`'s message body — fixed three small staleness issues (Plan #2 Migration Notes wording, Plan #10 test count `five`→`six`, synthesis §6.3 promotion-row count `3/4`→`2/4`). All other revisions verified `addressed` per item.
- **The Science repo's user-global `~/.claude/CLAUDE.md`** carries a "no legacy/compatibility layers" rule that shaped decision #4 above. Honor it during implementation.
- **Auto-memory** is at `/home/keith/.claude/projects/-mnt-ssd-Dropbox-science/memory/`. Three project-memory entries exist (multi-project sync status, bio domain priority, natural-systems unresolved refs) — none is critical for this rollout but useful background.

---

## If something is unclear

- **Audit evidence:** check the per-project audit reports (`docs/audits/downstream-project-conventions/projects/<project>.md`) and the inventory JSONs.
- **Why a particular plan choice was made:** check the plan's Architecture / Evidence sections, then the master rollout plan's review-pass notes.
- **Who decided what:** user-locked-in decisions are in the "Decisions locked-in" section above; agent-made shape calls are noted in plan Architecture sections.
- **What's deferred vs out-of-scope vs follow-on:** master rollout plan's Bucket C and Follow-on actions sections are authoritative.
