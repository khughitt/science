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
| P1 #2 | Promote `pre-registration` to canonical type | `docs/plans/2026-04-25-pre-registration-canonical-type.md` | merged | merged (`d840e07`..`fc1cc80`) | APPROVE |
| P1 #4 | Synthesis-rollup frontmatter convention | `docs/plans/2026-04-25-synthesis-rollup-frontmatter.md` | merged | merged (`4dcd2ed`..`d1e4751`) | APPROVE |
| P1 #6 | Auto-archive done tasks (`science-tool tasks archive`) | `docs/plans/2026-04-25-tasks-auto-archive.md` | merged | merged (`dbee325`..`c29e4b7`) | APPROVE-WITH-FIXES |
| P1 #10 | Chained-prior `next-steps` ledger | `docs/plans/2026-04-25-next-steps-chained-prior.md` | merged | merged (`d5aa677`..`aee533f`) | APPROVE |

### Bucket B — small / additive (dispatched 2026-04-25)

| ID | Title | Plan doc | Plan | Impl | Review |
| --- | --- | --- | --- | --- | --- |
| P1 #7 | MAV addendum: audit-surfaced `mav-input` set | `docs/plans/2026-04-25-mav-audit-addendum.md` | approved (held: MAV not merged) | — | — |
| P1 #9 | Code/notebook → task back-link convention | `docs/plans/2026-04-25-code-task-backlink-convention.md` | merged | merged (`2768fa2`..`4196b8f`) | APPROVE |

### Plan review pass 1 (2026-04-25)

All six plans drafted by parallel sub-agents, then reviewed for cross-plan consistency. First-round revisions applied:

- **Plans #2 and #4** updated to target both `meta/validate.sh` and `scripts/validate.sh` (the two files have different sha256 at audit time and are kept in lockstep until the in-flight managed-artifact-versioning plan unifies them). Plans #7 and #10 already targeted both. This resolves cross-plan inconsistency in validator-canonical interpretation.
- **Plan #7 Task 1** (`LOCAL_PROFILE` parameterization) verified by reading `meta/validate.sh` lines 87, 111-118: the parameterization is **already in place** in canonical. Agent correctly framed Task 1 as "verify and tighten"; no demotion needed. The natural-systems drift is "natural-systems was patched before the canonical fix landed" — the right resolution is MAV-updating natural-systems, not another canonical change.

### Plan review pass 2 — deep-review findings + revisions (2026-04-25)

Six `superpowers:code-reviewer` sub-agents produced independent deep reviews. Findings folded back as revisions:

- **Plan #4 substantially reworked.** Deep review surfaced two blockers: my synthesis §3.3 misread mm30's actual frontmatter (mm30 uses `type: "report"` + `report_kind:` + `id: "report:synthesis-<slug>"`, not `type: synthesis`), and required `synthesized_from:` on per-hypothesis files even though neither downstream project ships it there. Synthesis §3.3 corrected in place; plan #4 rewritten to canonize the cleaner `type: synthesis` shape (option B per user direction) with `synthesized_from:` required only on `report_kind: synthesis-rollup`. `curation-sweep` dropped from the `report_kind` enum (deferred to §6.3 promotion). Validator silent on legacy `type: report` files — no compatibility layer; mm30 + protein-landscape migrations flagged as follow-ons.
- **Plan #2 revised:** id-prefix mismatch downgraded `error` → `warn` (matches adjacent notes id-prefix check and Plan #7 Task 6's deliberate severity choice); Migration Notes corrected (only 2/4 use `id: pre-registration:*` legacy shape; natural-systems uses a third shape `id: plan:pre-registration-<slug>`); Task 3 split into Step 2a/2b to actually edit both validators (commit step now adds both); `source_refs:` dropped from canonical template (not in audit evidence — projects can add it as a project-local extension); `warn-on-missing-spec` test added.
- **Plan #6 revised:** evidence prose clarified (mm30 done+retired = 27%, not 30%; deferred deliberately stays in active); `--check` exit-code semantics changed to non-zero on lag (CI-gateable); destination-preamble preservation test added; prior-month routing precedence test added; **follow-on action filed** for the `tasks.py` `_write_active` preamble bug that affects four other functions outside this plan's scope.
- **Plan #7 revised:** Task 1 framing tightened (verify-only is the expected outcome; canonical bytes only change if Step 1 surfaces an edge case); explicit single-version-bump statement added to bookkeeping section; Task 6 Step 5 expanded to cover both `pre-registration` (depends on plan #2) and `synthesis` (depends on plan #4).
- **Plan #9 revised:** commit-message tag added as a fourth sanctioned pattern (synthesis §8.2 lists three observed patterns including this one — agent had dropped it); `docs/conventions/` directory creation justified with a seed `README.md` Task 1 establishing the directory's scope; Pattern 3 (descriptor sidecar field) gains an explicit "pending Bucket C namespace decision" status callout in the convention doc itself.
- **Plan #10 revised:** YAML block-list test variant added (the shape protein-landscape actually ships in `doc/meta/next-steps-2026-04-19.md`; the original plan only tested inline `[...]` form); auto-population guard "exclude today's file" hoisted out of parens (load-bearing for delta-mode semantics).

### Plan review pass 3 — pre-dispatch refinement (2026-04-25)

Final spot-read before user approval surfaced one cross-plan duplication:

- **Plan #2 dropped its in-loop id-prefix check.** The original pre-registration loop in `validate.sh` warned twice on the same condition once Plan #7 lands: once via Plan #2's `if [ "$pre_type" = "pre-registration" ]; then ... grep -Eq '^pre-registration:'` block, and once via Plan #7 Task 6's generic `PREFIX_RULES` table walk. Plan #7 Task 6 is the deliberate single canonical home for id-prefix conformance, so Plan #2's redundant block was removed: bash check, the matching `test_validate_warns_when_pre_registration_id_prefix_wrong` test, and corresponding prose in Architecture / File Structure / Migration Notes / Self-Review. Plan #2 retains the pre-registration-specific `committed:` / `spec:` warnings (which Plan #7 does not cover). After the refinement, four Plan #2 tests remain (acceptance, legacy-silence, missing-committed warn, missing-spec warn).
- **Trade-off accepted.** Until Plan #7 ships (after MAV), bad pre-reg id-prefixes go unwarned. Practical cost is small: cbioportal already converges canonically; mm30/protein-landscape/natural-systems all use `type: plan` legacy shapes that Plan #7's `pre-registration` row does not match (those projects' id mismatches are their respective `plan` rows in the table — natural-systems opts out via `SCIENCE_VALIDATE_SKIP_ID_PREFIX=1` per follow-on action #5).

### Cross-plan consistency rules established

- **Validator severity:** id-prefix mismatches and structural-field absences are `warn`, not `error`. Established in Plan #7 Task 6 and applied retroactively to Plan #2.
- **Validator targeting:** all validator-touching plans modify both `meta/validate.sh` and `scripts/validate.sh` until MAV unifies. Locate insertion sites by content, not absolute line.
- **Type promotion + id-prefix table coordination:** Plan #7 Task 6's id-prefix table includes rows for both `pre-registration` (canonized by Plan #2) and `synthesis` (canonized by Plan #4). These rows are forward-compatible — they activate when each canonical type lands downstream.
- **No legacy/compatibility layers** (per the user's global rule). Validators stay silent on legacy shapes (`type: plan` pre-regs, `type: report` synthesis files) — this is the natural consequence of additive type-conformance checks, not a permanent accepted variant. Downstream migrations are tracked as follow-on tasks.

### Follow-on actions (NOT part of any individual P1 plan)

These surface from the audit + plan/review passes but are out of scope for the six P1 plans. Tracked here for the user to file as appropriate (downstream `tasks/active.md` entries or upstream Science backlog):

1. **mm30 synthesis-file migration** — rename `type: report` → `type: synthesis` and `id: report:synthesis-*` → `id: synthesis:*` across `doc/reports/synthesis/h{1..6}*.md`, `doc/reports/synthesis.md`, and `_emergent-threads.md`. Triggered by Plan #4 landing.
2. **protein-landscape synthesis-file migration** — rename `type: emergent-threads` → `type: synthesis` + add `report_kind: emergent-threads` on `doc/reports/synthesis/_emergent-threads.md`. Add `report_kind: hypothesis-synthesis` to existing `type: synthesis` per-hypothesis files. Triggered by Plan #4 landing.
3. **`tasks.py` preamble bug** — `_write_active` (called by `complete_task`, `retire_task`, `add_task`, `defer_task`) silently drops file preamble. Plan #6's archiver fixes its own writes; the bug remains for the other four callers. File a Science task to apply preamble-preserving rewrite consistently.
4. **`science-tool` clean-stdout fix** — protein-landscape's `extract_json_payload` workaround in `validate.sh` exists because `science-tool graph audit/validate/diff` and `science-tool inquiry validate` emit non-JSON noise on stdout. The proper fix is upstream (`science-tool` emits clean JSON). File as a `science-tool` task; Plan #7 explicitly defers this rather than absorbing it as a `validate.sh` workaround.
5. **natural-systems report-id migration** — 26 of 31 `doc/reports/*.md` files use `id: doc:DATE-slug` instead of `id: report:DATE-slug`. Plan #7 Task 6 will warn on these once shipped; natural-systems can opt out via `SCIENCE_VALIDATE_SKIP_ID_PREFIX=1` while migrating.
6. **Synthesis §3.3 evidence correction** — applied directly to `docs/audits/downstream-project-conventions/synthesis.md`. The original "3/4 ship rollups in some form" overclaim is now a precise "2/4 with type-naming divergence" account; Top P1 candidate table entry updated; Appendix threshold-application notes updated.

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
- [x] Review each plan as it lands; mark `ready-for-review` in the table above.
- [x] User approval gate per plan; mark `approved`. (All six approved 2026-04-25 with Plan #2 id-prefix refinement applied.)
- [x] Dispatch implementation sub-agents for approved plans: parallel `#6`, `#9`, and a batched `#2/#4/#10`. Plan `#7` held until MAV merges. (All five landed `d840e07`..`c29e4b7`.)
- [x] Dispatch code-review sub-agents per implementation; mark `merged` after green. (All five APPROVE / APPROVE-WITH-FIXES; Plan #6's one actionable nit filed as `meta/tasks/active.md` `[t007]`.)
- [ ] Land Plan #7 once MAV merges (currently held).
- [ ] Execute downstream conventions migration per `docs/plans/2026-04-25-downstream-conventions-migration.md`.
- [ ] Schedule a Bucket C design session with the user.
