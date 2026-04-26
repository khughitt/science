# Downstream Conventions Migration — Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the four audited downstream projects (`natural-systems`, `mm30`, `protein-landscape`, `cbioportal`) to the canonical Science conventions established by the 2026-04-25 P1 rollout, plus adopt new opt-in conventions where they fit. Drive shape migrations through `scripts/migrate_downstream_conventions.py` (one rule per migration, dry-run by default). Drive convention adoption via `science-tool` and per-project task entries.

**Non-goals:** No upstream-Science changes. No new entity types beyond what P1 plans introduced. No re-litigation of audit findings.

**Dependencies (upstream landed at HEAD `9c1d598`):**

- Plan #2 (`pre-registration` canonical type) — landed.
- Plan #4 (`synthesis` canonical type + `report_kind`) — landed.
- Plan #6 (`science-tool tasks archive`) — in flight (resumption agent running). Migration step 5 (tasks-archive adoption) is gated on this landing.
- Plan #9 (`docs/conventions/code-task-backlinks.md`) — landed.
- Plan #10 (`prior:` chain field for next-steps) — landed.
- Plan #7 (MAV addendum incl. id-prefix table) — held until MAV merges. **Per-type id-prefix conformance landing downstream is therefore the natural enforcement gate** for migrations 2, 3, 5; running migrations earlier eliminates lag once Plan #7 ships.
- `scripts/migrate_downstream_conventions.py` — exists with `report-id-prefix` rule (commit `05e929d`). This plan extends it.

---

## Migration matrix

Each row is one migration. "✓" = needed; "—" = not needed; "n/a" = doesn't apply.

| # | Migration (rule name) | Driver | natural-systems | mm30 | protein-landscape | cbioportal | Source P1 |
|---|----------------------|--------|-----------------|------|-------------------|------------|-----------|
| 1 | `report-id-prefix` | script (exists) | ✓ 26 files + ~200 mentions | — | — | — | follow-on #5 |
| 2 | `synthesis-type-and-id-rollup` (was `synthesis-type-mm30`) | script (Phase 2 redesign) | ✓ rollup (`report:project-synthesis`) | ✓ rollup (`report:synthesis`) | ✓ rollup (no `id:`; `type: synthesis-rollup`; orphan-count migration) | — | follow-on #1 / Plan #4 |
| 3 | `synthesis-type-and-id-emergent-threads` (was `synthesis-type-pl-emergent-threads`) | script (Phase 2 redesign) | ✓ threads (`report:emergent-threads`) | ✓ threads (`report:synthesis-emergent-threads`) | ✓ threads (`type: emergent-threads`) | — | follow-on #2 / Plan #4 |
| 4 | `synthesis-type-and-id-per-hyp` (was `synthesis-report-kind-pl-hyp`) | script (Phase 2 redesign) | ✓ 4 per-hyp files (no filename-prefix gating) | ✓ 5 per-hyp files (`report:synthesis-<slug>`) | ✓ 3 per-hyp files | — | Plan #4 |
| 5 | `pre-registration-id-and-type` (was `pre-registration-type`; generalized) | script (Phase 2 redesign) | ✓ 4 files (`id: plan:pre-registration-<slug>` third shape) | ✓ 6 files | ✓ 2 files | — | Plan #2 |
| 6 | `natural-systems-pre-reg-frontmatter` | manual + helper | ✓ 3 files (frontmatter lacks `id:` and/or `type:`) | — | — | — | Plan #2 |
| 7 | tasks archive lag | `science-tool tasks archive --apply` | ✓ ~114 entries | ✓ 41 entries | ✓ 44 entries | — | Plan #6 |
| 8 | next-steps `prior:` field (new files only) | per-project convention | — (no chain today) | — (already uses `prior:`) | accepted variant (`prior_analyses:` keeps working) | — (no chain today) | Plan #10 |
| 9 | code/notebook → task back-link | per-project, opt-in | optional | optional | ✓ add `task:`/`question:` to 19 descriptors (Pattern 3) | optional (already uses Pattern 1 for 3 notebooks) | Plan #9 |
| 10 | `validate.sh` MAV update | `science-tool project artifacts update validate.sh` | ✓ when MAV+#7 land | ✓ | ✓ | ✓ | Plan #7 (held) |

Migrations 1–6 are shape rewrites driven by the migration script. Migrations 7–9 are convention adoption (no shape rewrite). Migration 10 unlocks once the MAV plan + Plan #7 land upstream.

---

## File Structure

Modify:

- `scripts/migrate_downstream_conventions.py` — extend with five new rules: `synthesis-type-mm30`, `synthesis-type-pl-emergent-threads`, `synthesis-report-kind-pl-hyp`, `pre-registration-type`, plus a small `natural-systems-pre-reg-frontmatter` helper that emits a *report* (not a writer — the field-derivation requires manual review).
- `docs/audits/downstream-project-conventions/synthesis.md` — append a "Migration tracking" appendix listing per-project status (one short line per migration). Optional follow-up; not required to start.

Create per-project tracking entries:

- `<project>/tasks/active.md` — file one `[t<NNN>]` task per project listing the migrations applicable to it (for downstream visibility / Curator awareness). The orchestrator does NOT modify those files directly — the per-project execution sub-agent (one per project) files them as part of the per-project execution.

Do not modify:

- Any downstream project's source files except via the migration script (or the per-project sub-agent's explicit, scoped edits for migration #6 / #9).
- `science-tool/`, validators, or anything in the upstream Science source tree.

---

## Task 1: Extend the migration script with new rules

**Files:** `scripts/migrate_downstream_conventions.py`.

The existing `apply_rule_report_id_prefix` is the template. Each new rule reuses `RuleResult` / `FileChange` / `_split_frontmatter` / `_record_line_changes` / `_tracked_markdown` and follows the same dry-run-by-default contract. Each rule must be idempotent on re-apply.

- [x] **Step 1: Add `synthesis-type-mm30`.** **(superseded)**

  **Status:** rules from `497a75f` superseded by Phase 2 redesign — those rule functions will be removed in the redesign commit. See `## Phase 2: Rule redesign (post-investigation)` below.

- [x] **Step 2: Add `synthesis-type-pl-emergent-threads`.** **(superseded)**

  **Status:** rules from `497a75f` superseded by Phase 2 redesign — those rule functions will be removed in the redesign commit. See `## Phase 2: Rule redesign (post-investigation)` below.

- [x] **Step 3: Add `synthesis-report-kind-pl-hyp`.** **(superseded)**

  **Status:** rules from `497a75f` superseded by Phase 2 redesign — those rule functions will be removed in the redesign commit. See `## Phase 2: Rule redesign (post-investigation)` below.

- [x] **Step 4: Add `pre-registration-type`.** **(superseded)**

  **Status:** rules from `497a75f` superseded by Phase 2 redesign — those rule functions will be removed in the redesign commit. See `## Phase 2: Rule redesign (post-investigation)` below.

- [x] **Step 5: Add `natural-systems-pre-reg-frontmatter` (report-only).** **(superseded)**

  **Status:** rules from `497a75f` superseded by Phase 2 redesign — those rule functions will be removed in the redesign commit. See `## Phase 2: Rule redesign (post-investigation)` below.

- [x] **Step 6: Update CLI help and `RULES` registry.**

Update the module docstring's "Rules" section and the `RULES` dict to register all five new rules. Verify `--help` lists them.

- [x] **Step 7: Self-test all rules.**

Run `uv run scripts/migrate_downstream_conventions.py --self-test`. Self-test must cover dry-run, apply, and idempotence for every new rule using the existing tempdir-fixture pattern. Each new rule gets its own fixture + assertions.

- [x] **Step 8: Lint & format.**

`uv run --frozen ruff check scripts/migrate_downstream_conventions.py` and `uv run --frozen ruff format scripts/migrate_downstream_conventions.py`. No new pyright errors.

- [x] **Step 9: Commit.**

`git commit -m "feat(scripts): add five canonical-shape rules to migrate_downstream_conventions"`.

---

## Phase 2: Rule redesign (post-investigation)

Triggered by the 2026-04-25 synthesis-shape investigation (`docs/audits/downstream-project-conventions/synthesis-shape-investigation-2026-04-25.md`). The original Task 1 rules from `497a75f` (Steps 1-5 above) were modeled per-project rather than per-shape and miss several real downstream shapes. This section sketches the replacements; landing them is a separate Phase 2 dispatch (it does NOT happen as part of the investigation follow-up).

The new rules are **shape-driven, not project-named**: each rule canonicalizes any matching shape regardless of which project ships it. The discriminator is the file's directory placement + filename + (current) `type:`/`id:` field combination, never a project name.

### New rules

- **`synthesis-type-and-id-rollup`** — handles any `<root>/doc/reports/synthesis.md`: ensure `type: synthesis`, `id: synthesis:rollup`, `report_kind: synthesis-rollup`. Defensive: handles starting `type:` values of `report` and `synthesis-rollup`. Also handles `id:` rewrite from any of `report:synthesis`, `report:project-synthesis`, or absent. **If Q1=C and the rollup carries `orphan_question_count` / `orphan_interpretation_count` / `orphan_ids`, MOVE those to the companion `_emergent-threads.md` file** (read rollup → strip → write rollup; read threads → insert → write threads; both writes happen in the same atomic apply step or neither).

- **`synthesis-type-and-id-emergent-threads`** — handles any `<root>/doc/reports/synthesis/_emergent-threads.md`: ensure `type: synthesis`, `id: synthesis:emergent-threads`, `report_kind: emergent-threads`. Defensive: handles starting `type:` values of `report`, `emergent-threads`, or already `synthesis`. Also handles `id:` rewrite from `report:emergent-threads`, `report:synthesis-emergent-threads`, or absent.

- **`synthesis-type-and-id-per-hyp`** — handles any `<root>/doc/reports/synthesis/*.md` excluding `_*`: ensure `type: synthesis`, ensure `report_kind: hypothesis-synthesis`, rewrite `id:` from `report:synthesis-<slug>` to `synthesis:<slug>` if needed. **No filename-prefix gating** (the directory placement is the discriminator). Idempotent on already-canonical files.

- **`pre-registration-id-and-type`** (generalized) — for files matching `<root>/doc/meta/pre-registration-*.md` and `<root>/doc/pre-registrations/*.md`: ensure `type: pre-registration`. Handle two starting id shapes:
  - `id: pre-registration:<slug>` — already canonical id; just rewrite `type: plan` → `type: pre-registration`. (This is the existing rule's behavior.)
  - `id: plan:pre-registration-<slug>` — strip the `plan:` prefix, then rewrite `type:`. (NS third-shape; previously unhandled.)

- **Mention rewrites:** any reference to `report:synthesis`, `report:synthesis-<slug>`, `report:project-synthesis`, `report:synthesis-emergent-threads`, `report:emergent-threads`, `plan:pre-registration-<slug>` is rewritten to its canonical equivalent. Path-keyed against the post-pass-1 file set so non-entity references aren't affected.

### Cross-cutting principles

- *Rules are **shape-driven, not project-named** — each rule canonicalizes any matching shape regardless of which project ships it.*
- *Each rule operates on the abstract entity (`SynthesisFile{kind=rollup|emergent-threads|hypothesis-synthesis}` or `PreRegistrationFile`) — discriminator is the file's directory placement + filename + (current) `type:`/`id:` field combination, not a project name.*
- *Idempotence is non-negotiable: re-apply produces zero `changes` for any project that has reached canonical.*
- *Self-test fixtures must cover EVERY observed downstream shape from the investigation memo's "What we observed in the wild" section, not just one example per rule.*

---

## Task 2: Per-project execution playbook

For each downstream project, dispatch one sub-agent (or run sequentially) following the playbook below. Each sub-agent operates on ONE project and ONE project only.

**Standing rules for every per-project sub-agent:**

- Work happens in the downstream project's repo (`/home/keith/d/r/<project>` or `/home/keith/d/<project>`), NOT in the Science meta-repo.
- Always run rules in dry-run first. Inspect the diff. Apply only after the diff matches expectations.
- After every `--apply`, run the project's `bash validate.sh --verbose` to confirm no new validator errors.
- After every `--apply`, also run a focused content-check: `git diff --stat` should match the expected files-touched count from the dry-run.
- Each rule application gets its own commit in the downstream repo.
- File a `[t<NNN>]` entry in the project's `tasks/active.md` referencing this plan and listing the rules applied / pending.
- If a rule's dry-run output looks wrong, STOP — do not apply, report back.

**Per-project tasks:**

Recommended sequencing (post-investigation): **cbioportal → mm30 → PL → NS**. Rationale: cbioportal is no-op (already done in initial pass) and serves as the dry-run sanity check for the redesigned rules; mm30 is uniformly drifted and is the cleanest test of the redesigned rules; PL has the rollup migration unblocked plus the script-error path resolved; NS goes last because it carries mixed shapes (highest residual surprise risk) and a partial-migration of per-hyp files is already in place from the original Task 1 pass.

- [x] **cbioportal** (`/home/keith/d/r/cbioportal`) — **DONE 2026-04-25** (warmup pass + redesigned-rules confirmation; both passes 0/0). Task entry `[t140]` filed (cbioportal commit `fad556c`). All shape migrations were no-ops as predicted. Pending: tasks-archive adoption (Plan #6); MAV validator update (Plan #7).

- [x] **mm30** (`/home/keith/d/r/mm30`) — **DONE 2026-04-25**. mm30 commits: `f0448f8` rollup (Q1=C atomic move verified: `orphan_question_count: 6` → threads), `74c581c` emergent-threads, `cb0e96d` per-hyp (5 files), `f05045b` pre-reg (16 files — actual count 16 vs predicted ~6, all uniform `type: plan` → `type: pre-registration`), `afd0814` task entry `[t314]`. Validator state unchanged at 160/85. Idempotence ✓. Commitlint enforcement adapted (no `--no-verify` used). Pending: 4 sparse `doc/meta/pre-registration-*.md` files need hand-fill (separate cleanup cycle); tasks-archive (Plan #6); MAV validator update (Plan #7).

- [x] **protein-landscape** (`/home/keith/d/protein-landscape`) — **DONE 2026-04-25**. Required two dispatches: first halted on pre-flight (Q63 dev work in progress); user landed Q63 work; resumed cleanly. PL commits: `9bc1477` rollup (Q1=C atomic move verified: `orphan_question_count: 23` → threads; `orphan_interpretation_count` and `orphan_ids:` were already on threads file, script correctly migrated only what was on rollup), `5c882a8` emergent-threads, `33ed567` per-hyp (3 files), `c9791f0` pre-reg (2 files), `6083bfe` task entry `[t168]`. Validator state unchanged at 1/2 (1 pre-existing error from `science-tool` clean-stdout follow-on). Idempotence ✓. Commitlint enforcement adapted. Pending: tasks-archive (Plan #6); MAV validator update (Plan #7); descriptor sidecar Pattern 3 adoption (Plan #9, deferred until Bucket C / P1 #8 namespace decision).

- [x] **natural-systems** (`/home/keith/d/natural-systems`) — **DONE 2026-04-25**. Rule 1 (`report-id-prefix`) was previously applied by user (NS commit `3adeeb0e`). NS commits this cycle: `5d2fb44a` rollup (Q1=C atomic move verified: `orphan_question_count: 56` → threads), `554b79e5` emergent-threads (3 files / 82 changes — largest mention-rewrite footprint of cycle; no false positives), `ae933219` per-hyp (4 files — non-`h*`-prefixed files caught by Phase 2 glob fix), `444a3ea4` pre-reg (2 files including t214 third-shape `id: plan:pre-registration-t214` → `id: pre-registration:t214`), `67421095` task entry `[t338]`. Validator state: migration commits unchanged at 239/77; task entry added +1 of pre-existing `missing required field: type` class (236 NS tasks share the same shape; not migration-introduced). Idempotence ✓. Commitlint enforcement adapted. Pending: 3 sparse `doc/meta/pre-registration-*.md` files need hand-fill (separate cleanup cycle, suggestions available via `natural-systems-pre-reg-frontmatter --rule`); tasks-archive (Plan #6); MAV validator update (Plan #7).

---

## Task 3: Tasks archive adoption (gated on Plan #6 landing)

**Files:** No script changes. Per-project commits only.

Once `science-tool tasks archive` is shipped (Plan #6 merged), per-project sub-agents run:

- [ ] `science-tool tasks archive --tasks-dir <project>/tasks --format json` (dry-run preview).
- [ ] Inspect plan; confirm route-by-month destinations match `completed:` dates.
- [ ] `science-tool tasks archive --tasks-dir <project>/tasks --apply`.
- [ ] Commit (`chore(tasks): archive done/retired entries via science-tool tasks archive`).
- [ ] Confirm `science-tool health --project-root <project> --format json` reports `archive_lag.done_in_active == 0` and `archive_lag.retired_in_active == 0`.

Expected per-project counts (from audit + plan #6 evidence):

- natural-systems: ~114 done.
- mm30: 36 done + 5 retired = 41 entries.
- protein-landscape: ~44 done.
- cbioportal: 0 (clean reference; expected no-op).

---

## Task 4: MAV update (gated on MAV + Plan #7 landing)

**Files:** Per-project `validate.sh`.

Once the MAV plan + Plan #7 (validator addendum) land upstream:

- [ ] Per project: `science-tool project artifacts update validate.sh --project-root .` (or `--check` first).
- [ ] Each project's local `validate.sh` should pull the canonical version with the audit-surfaced fixes.
- [ ] Per-project run of `bash validate.sh --verbose` to confirm green (with `SCIENCE_VALIDATE_SKIP_ID_PREFIX=1` opt-out for natural-systems while migration #1 mentions are still settling, if relevant).
- [ ] Per-project commit (`chore(validate): update to managed validate.sh v<DATE>`).

This task is the natural close-out of the migration cycle: once it lands, every project is on the canonical validator with all P1-rollout-era fixes in place, and the per-type id-prefix table starts firing on any remaining drift.

---

## Task 5: Track + report

**Files:** `docs/audits/downstream-project-conventions/synthesis.md`.

- [ ] Append a short "Migration tracking (post-rollout)" section listing per-project status: which migrations applied, which remain, MAV-update status, archive-lag status. Keep it terse — a 4×N table is sufficient.
- [ ] Mark the relevant follow-on actions in `docs/plans/2026-04-25-conventions-audit-p1-rollout.md` as complete once each migration lands downstream.

---

## Sequencing (recommended)

1. **Now (does not block on Plan #6):** Task 1 (extend script with five new rules). Confirm self-test passes.
2. **In parallel with Task 1 (one sub-agent per project):** Task 2 — per-project execution. Migrations 1–5 land one project at a time with their own commits.
3. **After Plan #6 lands upstream:** Task 3 (tasks-archive adoption per project).
4. **After MAV + Plan #7 land upstream:** Task 4 (MAV update per project).
5. **Anytime once items above settle:** Task 5 (tracking + report).

---

## Self-Review Checklist

- Each migration has explicit audit-evidence citation in its rule docstring (synthesis §3.x or projects/<x>.md §y).
- Each rule is dry-run by default and idempotent on re-apply.
- Self-test fixture covers each new rule independently with both pre-migration and post-migration shapes.
- Per-project execution writes to the downstream repo, not the Science meta-repo.
- No upstream Science source-tree changes (the script extension is the only Science-side change).
- Task 3 and Task 4 are explicitly gated on the relevant upstream plan landing; no premature dispatch.
- `<TODO>` placeholders in migration #6 are clearly flagged for human review.

---

## Open Questions / Edge Cases

- **mm30 rollup id form.** Plan #4 emits `id: "synthesis:rollup"` from `commands/big-picture.md` Phase 3 (after rewrite). mm30 currently has `id: "report:synthesis"`. The migration uses `synthesis:rollup` to match the upstream emitter; if the project owner prefers `synthesis:project-rollup` or another form, the rule's literal-id rewrite needs adjustment.
- **natural-systems pre-reg `committed:` derivation.** No mechanical source for the value. Migration #6 emits `<TODO>` and waits for user input; sub-agent must NOT guess.
- **PL descriptor back-link adoption (Pattern 3).** Status is "pending Bucket C namespace decision" per `docs/conventions/code-task-backlinks.md`. Defer Pattern 3 application to PL until Bucket C concludes; until then, PL can adopt as project-local optional convention but should expect a one-shot field rename when Bucket C decides on top-level vs `science:` namespace.
- **Re-running `report-id-prefix` on natural-systems.** The rule is idempotent; re-runs after migration are safe and fast.
