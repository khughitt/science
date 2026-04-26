# Conventions Audit Rollout + Downstream Migration — Orchestrator Handoff (post-migration)

**Date written:** 2026-04-25 (end of session that closed out the migration cycle)
**Branch:** `main`
**Last commit at handoff:** `b394ec0`
**Supersedes:** `docs/plans/2026-04-25-conventions-audit-rollout-handoff.md` (the earlier mid-rollout handoff at commit `a9254b0`)
**For:** the next orchestrator picking up this work. Read this first; it should give you everything you need to continue without re-deriving prior decisions.

---

## TL;DR

The 2026-04-25 P1 rollout from the downstream conventions audit is complete: **5 of 6 Bucket A+B plans landed and code-reviewed**; the **downstream migration cycle is done across all four projects**. Plan #7 (MAV addendum) remains held pending MAV merge. Bucket C (4 P1s) still needs a user-in-the-loop design session. Five concrete open threads remain — see "Next steps" below. No upstream code changes are blocked on anything.

---

## What's been accomplished

### Phase 0 — audit (commit `4d27b6d`, predates this session)

- `scripts/audit_downstream_project_inventory.py` + 4 per-project inventories + 4 audit reports + cross-project synthesis (`docs/audits/downstream-project-conventions/`).

### Phase 1 — P1 plan creation, deep-review, revision (commits `9884dc3`, `17f21de`, `a9254b0`, `eaa8571`, predates this session)

- Six implementation plans drafted, deep-reviewed by parallel `superpowers:code-reviewer` sub-agents, revised twice, and approved-with-fixes by a verification reviewer. Plans #2/#4/#6/#7/#9/#10. Bucket C plans #1/#3/#5/#8 deferred for design-pass session.

### Phase 2 — implementation, this session (commits `b1eacc7`..`c29e4b7`)

Five P1 plans implemented and merged:

- **P1 #2** (pre-registration canonical type) — commits `d840e07`..`fc1cc80` (4 commits). Includes pre-dispatch refinement (commit `b1eacc7`): id-prefix conformance check removed from Plan #2's loop because Plan #7 Task 6's PREFIX_RULES table is the single canonical home.
- **P1 #4** (synthesis-rollup frontmatter + `report_kind` discriminator) — commits `4dcd2ed`..`d1e4751` (4 commits).
- **P1 #6** (`science-tool tasks archive` + health-report `archive_lag` surfacing) — commits `dbee325`..`c29e4b7` (6 commits). Required mid-flight intervention: a stale `git stash apply` had left conflict markers in `science-tool/tests/test_health.py`; resolved via `git checkout HEAD -- ...` after user authorization.
- **P1 #9** (code/notebook → task back-link convention; new `docs/conventions/` directory) — commits `2768fa2`..`4196b8f` (3 commits).
- **P1 #10** (chained-prior `next-steps` ledger; `prior:` canonical, `prior_analyses:` accepted variant) — commits `d5aa677`..`aee533f` (4 commits).
- **P1 #7** (MAV addendum) — **HELD**. Depends on the in-flight `2026-04-25-managed-artifact-versioning.md` plan reaching `merged`. Plan is approved (status `approved (held: MAV not merged)` in the master rollout plan).

Plus shared checkbox-flip commit `9c1d598` and code-review close-out commit `fb65f0c`.

Reviewer verdicts (all green):
- #2 APPROVE, #4 APPROVE, #6 APPROVE-WITH-FIXES (one nit filed as `meta/tasks/active.md` `[t007]`), #9 APPROVE, #10 APPROVE.

### Phase 3 — downstream migration cycle, this session (commits `05e929d`..`b394ec0`)

**Migration script** (`scripts/migrate_downstream_conventions.py`):
- `05e929d` — initial script with `report-id-prefix` rule (committed by user).
- `497a75f` — Task 1 of migration plan: 5 new project-named rules added.
- `fe8d974` — Phase 2 redesign: project-named rules replaced with **shape-driven rules** after the investigation memo surfaced spec ambiguities and audit gaps.

**Investigation cycle** (commit `02f5b45`):
- Triggered by natural-systems Task 2 dispatch HALT — agent surfaced six audit-cataloging gaps and three migration-script gaps.
- `docs/audits/downstream-project-conventions/synthesis-shape-investigation-2026-04-25.md` — full memo with per-project shape catalog + spec-ambiguity decision points.
- User resolved Q1=C (orphan counts ONLY on emergent-threads file; rollup keeps `emergent_threads_sha:` back-pointer; migration moves), Q2=block-list canonical for `synthesized_from:`, Q3=B (audit § 3.3 appendix-style correction), Q4=Yes (Phase 2 rule redesign greenlit).
- Phase 1 spec/audit updates (commits `ab88dc7`, `cd22533`, `1bd6eaa`, `869b669`): block-list canonized in `commands/big-picture.md`, audit § 3.3 appendix added, migration plan updated, `[t008]` filed for validator strictness on inline-dict.

**Per-project migration** (Task 2 of migration plan):
| Project | Project commits | Outcome |
|---|---|---|
| cbioportal | `fad556c` | All shape rules no-op as predicted; task `[t140]` filed |
| mm30 | `f0448f8`..`afd0814` (5 commits) | 23 file changes; orphan-count atomic-move verified (`orphan_question_count: 6`); task `[t314]` filed |
| protein-landscape | `9bc1477`..`6083bfe` (6 commits) | 7 file changes; orphan-count atomic-move verified (`orphan_question_count: 23`); task `[t168]` filed |
| natural-systems | `5d2fb44a`..`67421095` (5 commits) | 11 file changes; orphan-count atomic-move verified (`orphan_question_count: 56`); task `[t338]` filed |

Cycle close-out: commit `b394ec0` updated migration plan + master rollout plan status tables.

---

## Decisions locked-in (do not re-litigate)

These were settled by the user during this session. A future orchestrator should treat them as fixed:

1. **Pre-registration id-prefix conformance lives in Plan #7 Task 6**, not in Plan #2's per-file loop. Plan #2 owns only `committed:` / `spec:` structural-field checks. (Refinement applied 2026-04-25 commit `b1eacc7`.)
2. **Q1 (synthesis orphan counts)** — strict Plan #4 + back-pointer: `orphan_question_count`, `orphan_interpretation_count`, `orphan_ids:` live ONLY on the `_emergent-threads.md` file. Rollup keeps `emergent_threads_sha:` as the back-pointer. Migration moves orphan fields rollup→threads atomically.
3. **Q2 (synthesized_from form)** — block-list canonical: `commands/big-picture.md` Phase 3 example aligned to the template's block-list form. Inline-dict (`[{...}]`) is deprecated. `[t008]` tracks the validator-strictness follow-on (warn on inline-dict).
4. **Q3 (audit corrections)** — appendix-style: `docs/audits/downstream-project-conventions/synthesis.md` § 3.3 has a "Post-investigation correction (2026-04-25)" subsection; original prose preserved as historical record.
5. **Q4 (rule design)** — shape-driven, not project-named. Each rule canonicalizes any matching shape regardless of which project ships it. Discriminator is the file's directory placement + filename + `type:`/`id:` field combination, not a project name.
6. **Q5 (long-term ideal)** — articulated in conversation 2026-04-25: entity-id references become first-class citizens of the knowledge graph; `science-tool entity rename <old-id> <new-id>` becomes a primitive; migration scripts become declarative ("transition entity instances of kind K from shape S₀ to shape S₁") rather than imperative regex flailing. Phase 2's shape-driven rules are the first concrete step toward this. Bucket C work is the next major step (defines abstract entity model).
7. **Validator severity = `warn`** (not error) for id-prefix mismatches and structural-field absences. Established across Plans #2, #4, #7, #10.
8. **Both validators in lockstep** — every change to `meta/validate.sh` is mirrored in `scripts/validate.sh` (locate by content, not absolute line). Until MAV unifies them.
9. **No legacy/compatibility layers** — additive type-conformance checks only. Validators stay silent on legacy shapes (e.g. `type: plan` pre-regs, `type: report` synthesis files, `prior_analyses:` next-steps). Downstream migrations are the cleanup path, not validator branches.
10. **Default dispatch posture** — sequential, with user spot-checks between, when mutating downstream state. Parallel is fine for read-only/independent work (e.g. five parallel code-review sub-agents). Pre-flight gates HALT on any unexpected state; never auto-fix; never `git stash`/`reset`/`checkout HEAD --`/`clean`/`--no-verify`.

---

## Current state

- **Git:** clean working tree on `main`, last commit `b394ec0`. 99 commits ahead of `origin/main`.
- **Master rollout plan:** five P1s `merged` + reviewed. Plan #7 `approved (held: MAV not merged)`. Master plan's "Suggested Task Breakdown" reflects the open threads below.
- **Migration plan:** Phase 1 (script + per-project task entries done across cbioportal/mm30/PL/NS); Phase 2 (rule redesign done at `fe8d974`); Task 2 (per-project execution done across all four).
- **Investigation memo:** authoritative source for the per-project shape catalog at this point in time. May need a small corollary correction noting that mm30 and NS also had `orphan_question_count` on rollup (memo predicted only PL did) — but the script handled all three correctly so this is a documentation-only fix.

---

## Next steps (in order, each can be tackled independently)

### 1. MAV review/merge (unblocks Plan #7 + migration Task 4)

`docs/plans/2026-04-25-managed-artifact-versioning.md` exists but is not yet executed. Once MAV merges, Plan #7 (the audit-surfaced `mav-input` set addendum) can be dispatched. After Plan #7 lands, downstream projects can `science-tool project artifacts update validate.sh` to pull the canonical with the audit-surfaced fixes. This is the largest open thread that genuinely depends on prior work landing first.

### 2. Bucket C design session

Four P1s explicitly deferred for user-in-the-loop design:

- **P1 #1** — Multi-axis project profile / archetype shape (4/4 projects use `aspects:` as workaround).
- **P1 #3** — Sanctioned project-local entity-kind extension surface (cbioportal's `typed-extension` is the working prototype).
- **P1 #5** — Per-type / multi-axis status enums + structured `qualifier:` (touches every entity family).
- **P1 #8** — Datapackage `<project>:` extension profile + descriptor sidecar shape (Frictionless extension).

These collectively define the abstract entity data model that Q5's long-term ideal needs. They are coupled (especially #1 ↔ #3, and #8 ↔ Plan #9's Pattern 3 status callout). A future cycle should brainstorm with the user, produce design docs, then write implementation plans. The orchestrator should NOT proceed to implementation plans without each design landing first.

### 3. Hand-fill 7 sparse pre-reg files

Files that lack `id:` and `type:` entirely; canonical-FM values for `committed:` / `spec:` cannot be derived mechanically. Suggestions are available via the report-only `natural-systems-pre-reg-frontmatter` rule.

- **natural-systems** (3 files): `doc/meta/pre-registration-{q54-temporal-profile,t085-t086,t092}.md`
- **mm30** (4 files): `doc/meta/pre-registration-{decomposition,h-mgus-enrichment,integration,t28-fraction-qc}.md`

Workflow per file: (a) run the rule against the project to see the suggested canonical FM block; (b) user fills in `committed:` and `spec:` values; (c) commit the canonicalized FM in the downstream repo. Small chunks of focused work; whenever convenient.

### 4. Tasks-archive adoption per project (migration plan Task 3)

`science-tool tasks archive` shipped upstream (`c29e4b7`). Each downstream project needs to install/update `science-tool` and run the archiver. Per-project counts (from audit + Plan #6 evidence):

- natural-systems: ~114 done entries
- mm30: 41 entries (36 done + 5 retired)
- protein-landscape: 44 entries
- cbioportal: 0 (clean reference; expected no-op)

Each project: dry-run preview → inspect → `--apply` → commit (`chore(tasks): archive done/retired entries`). Health-report `archive_lag` should drop to zero after.

### 5. Hand-off cleanup (small)

- Investigation memo's "What we observed in the wild" section claims only PL had orphan counts on rollup — actually all three projects with synthesis areas did (mm30 had 6, NS had 56). Add a one-line corollary correction so future readers don't get the wrong impression. Memo lives at `docs/audits/downstream-project-conventions/synthesis-shape-investigation-2026-04-25.md`.

---

## Cross-plan rules (apply during any future P1 implementation work)

These rules were established during cross-plan review and recorded in the master rollout plan. Honor them:

- **Validator severity** = `warn` for id-prefix mismatches and structural-field absences.
- **Validator targeting** — every change to `meta/validate.sh` is mirrored in `scripts/validate.sh` (locate by content, not line). Both validators are in the File Structure of every validator-touching plan.
- **No legacy/compatibility layers** — additive type-conformance checks only.
- **Single managed-version bump for the MAV addendum** (Plan #7) — all six fixes ship under one `ArtifactDefinition.version` bump, with one entry appended to `previous_hashes`.
- **Forward-compatibility** in Plan #7 Task 6's id-prefix table: `pre-registration` and `synthesis` rows ship now and activate when those plans land downstream.

---

## Useful context for the next orchestrator

- **Read-only constraint applies to downstream projects** for any *audit* or *upstream-Science* work. Migration cycles MUTATE downstream state — but only via the script's per-rule `--apply`, with pre-flight gates and one-rule-per-commit atomicity. Never use `git stash`/`reset`/`checkout HEAD --`/`clean` in a downstream repo without explicit user authorization. The mm30 and NS projects enforce commitlint via husky; adapt commit subjects to ≤100 chars and never use `--no-verify`.
- **Both `meta/validate.sh` and `scripts/validate.sh` exist** with different sha256 at audit time. The MAV plan (still in flight) creates a third copy at `science-tool/src/science_tool/project_artifacts/data/validate.sh` that becomes the package-distributed canonical. Plan #7 (MAV addendum) handles the version bump bookkeeping after MAV merges.
- **The migration script's seven rules** are: `report-id-prefix`, `synthesis-type-and-id-rollup`, `synthesis-type-and-id-emergent-threads`, `synthesis-type-and-id-per-hyp`, `pre-registration-id-and-type`, `natural-systems-pre-reg-frontmatter` (report-only), `specs-frontmatter-backfill`. All idempotent. Self-test at `--self-test` covers every observed downstream shape.
- **Pre-flight gates** for any downstream-mutating dispatch: clean working tree, no merge/rebase/cherry-pick/bisect, stash list noted (don't touch user WIP), HEAD captured for revert reference, validator baseline captured. HALT on any unexpected state.
- **Pre-existing baseline issues** to be aware of:
  - cbioportal: 37 `task tNNN missing required field: type` errors (de-facto schema; not migration-introduced; will resolve when Plan #7's per-type id-prefix table ships and projects either adopt `type:` or opt out via `SCIENCE_VALIDATE_SKIP_ID_PREFIX=1`).
  - natural-systems: 235+ of the same `task missing required field: type` errors (same de-facto schema, larger volume).
  - protein-landscape: 1 pre-existing error `graph audit produced unparseable output` (the `science-tool` clean-stdout follow-on `[t<NNN>]` track).
  - These baselines are NOT migration-introduced. Treat new errors that fail to match any of these classes as real regressions.
- **Auto-memory** is at `/home/keith/.claude/projects/-mnt-ssd-Dropbox-science/memory/`. Three project-memory entries exist (multi-project sync status, bio domain priority, natural-systems unresolved refs); none are critical for this rollout.
- **Important user instructions surfaced this session:**
  - "We shouldn't bend the validation and migration to the metadata; we should investigate and determine what the intended shape is post-migration." → Drove the Phase 2 redesign (shape-driven rules) instead of patching project-named rules.
  - "Aim for strictness / single cohesive abstraction (starting from abstract entity data model → specialized forms aligned with data model / meta model, where possible)." → Q4=Yes; this is the long-term direction.
  - "Make sure that they check to ensure they don't clobber unrelated changes made by other devs." → Standing pre-flight gate for every downstream-mutating dispatch. Saved PL when Q63 dev work was in flight.

---

## References

**Commits in chronological order (this session):**

- `b1eacc7` — Plan #2 id-prefix refinement; flip plans to `approved`
- `2768fa2`, `904f077`, `4196b8f` — Plan #9 implementation
- `d840e07`, `4d7f094`, `17d4868`, `fc1cc80` — Plan #2 implementation
- `4dcd2ed`, `e764a57`, `8985b57`, `d1e4751` — Plan #4 implementation
- `d5aa677`, `cb6f9a5`, `955d217`, `aee533f` — Plan #10 implementation
- `9c1d598` — checkbox flips for Plans #2/#4/#10
- `dbee325`, `3c2fad3`, `74e6cbf`, `52f8098`, `0046c8f`, `c29e4b7` — Plan #6 implementation
- `8feabf5` — initial migration plan
- `fb65f0c` — code-review close-out
- `497a75f` — migration script Task 1 (project-named rules — superseded)
- `02f5b45` — investigation memo
- `ab88dc7`, `cd22533`, `1bd6eaa`, `869b669` — Phase 1 spec/audit updates
- `fe8d974` — Phase 2 rule redesign (shape-driven)
- `b394ec0` — Task 2 close-out

**Authoritative documents:**

- `docs/plans/2026-04-25-conventions-audit-p1-rollout.md` — master plan; per-P1 status table; cross-plan rules; follow-on actions; deferred Bucket C.
- `docs/plans/2026-04-25-downstream-conventions-migration.md` — migration plan; Phase 2 rule design; Task 2 per-project execution outcomes.
- `docs/audits/downstream-project-conventions/synthesis.md` — cross-project synthesis. **§ 3.3 carries an explicit "Post-investigation correction" subsection** — read it before re-deriving any synthesis-rollup claim.
- `docs/audits/downstream-project-conventions/synthesis-shape-investigation-2026-04-25.md` — investigation memo; per-project shape catalog at HEAD `497a75f`; resolved decision points.
- The five merged P1 plans (#2, #4, #6, #9, #10) and the held P1 #7.

**Related in-flight plans (do not duplicate):**

- `docs/plans/2026-04-25-managed-artifact-versioning.md` — the MAV plan that Plan #7 is an addendum to. Plan #7 executes after MAV merges.
- `docs/plans/2026-04-25-hypothesis-phase.md` — the hypothesis-phase plan (introducing `phase: candidate | active`).

**Audit deliverables to consult during any future implementation:**

- `docs/audits/downstream-project-conventions/projects/<project>.md` — when an implementation question is "what does <project> actually look like," check this first (but verify against the corrected catalog in the investigation memo).
- `docs/audits/downstream-project-conventions/inventory/<project>.json` — for machine-queryable per-project shape data.

**Downstream task-entry references** (filed this cycle, useful for cross-project context):

- cbioportal `[t140]`
- mm30 `[t314]`
- protein-landscape `[t168]`
- natural-systems `[t338]`

**Upstream task-entry follow-ons** (filed this cycle in `meta/tasks/active.md`):

- `[t006]` — `parse_tasks` blank-line-after-header silently dropping fields (filed by user during cycle).
- `[t007]` — `_write_active` silently dropping `tasks/active.md` preamble (filed from Plan #6 code review).
- `[t008]` — Validator: warn on inline-dict `synthesized_from` items (filed from investigation Q2).

---

## If something is unclear

- **Per-project state catalog:** check the investigation memo first (`synthesis-shape-investigation-2026-04-25.md`); the audit synthesis predates the corrections.
- **Why a particular plan choice was made:** check the plan's Architecture / Evidence sections, then the master rollout plan's review-pass notes, then the investigation memo's decision points.
- **Who decided what:** user-locked-in decisions are in the "Decisions locked-in" section above; agent-made shape calls are noted in plan Architecture sections and the investigation memo.
- **What's deferred vs out-of-scope vs follow-on:** master rollout plan's Bucket C and migration plan's Task 3/4 + this handoff's "Next steps" are authoritative.
- **Why a downstream commit looks the way it does:** per-rule commits in the downstream repos use the format `fix(<scope>): apply <rule-name> per Science 2026-04-25 conventions migration` with the body referencing this plan + the script. Each rule application is its own commit for atomic revertability.
