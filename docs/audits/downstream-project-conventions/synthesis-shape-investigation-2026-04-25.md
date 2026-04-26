# Synthesis-Shape Investigation — 2026-04-25

**Triggered by:** natural-systems migration HALT (Task 2 of `docs/plans/2026-04-25-downstream-conventions-migration.md`). Multiple audit/spec predictions diverged from observed downstream state. Per the user's directive — "we shouldn't bend the validation and migration to the metadata; we should investigate and determine what the intended shape is post-migration" — Task 2 is paused pending findings.

**Status:** investigation complete. Findings + decision points below. No mutations performed in any downstream project except cbioportal (commit `fad556c` — task entry only) and natural-systems (commit `3adeeb0e` — pre-existing user work, unrelated).

---

## TL;DR

The 2026-04-25 audit and migration plan have **real gaps**. Three categories:

1. **Audit cataloging gaps** — undercounted per-project synthesis-area shapes by 6+ distinct id/type forms. Most consequentially: natural-systems was declared "no synthesis files"; it has a full synthesis area with three drifted shapes.
2. **Plan #4 spec ambiguities** — protein-landscape's rollup carries `orphan_question_count` directly (not on the threads file); Plan #4's canonical is silent on whether this is allowed or must migrate. Two open questions for the user.
3. **Migration-script narrowness** — five rules from `2026-04-25-downstream-conventions-migration.md` Task 1 were modeled per-project rather than per-shape. They miss several real downstream shapes that fall outside their hardcoded preconditions.

Recommendation: do not mutate any downstream project further until (a) the user resolves the two Plan #4 spec questions, (b) the audit § 3.3 is corrected with the actual shape catalog, and (c) the migration rules are redesigned around **shape→canonical mapping** rather than project-named buckets.

---

## What we observed in the wild

Catalog of every synthesis-area file across the four projects. Frontmatter sampled at HEAD `497a75f`.

### natural-systems (`/home/keith/d/natural-systems`)

Audit said: no synthesis files. **Wrong.** NS has a complete synthesis area:

| File | `id:` | `type:` | `report_kind:` | Notes |
|---|---|---|---|---|
| `doc/reports/synthesis.md` | `report:project-synthesis` | `report` | (absent) | Rollup. Has `synthesized_from:` (inline-dict form) |
| `doc/reports/synthesis/_emergent-threads.md` | `report:emergent-threads` | `report` | (absent) | Has `orphan_ids:` |
| `doc/reports/synthesis/double-categorical-model-relationships.md` | `synthesis:h01-double-categorical-model-relationships` | `synthesis` | (absent) | Per-hyp |
| `doc/reports/synthesis/dynamical-invariant-validation.md` | `synthesis:h04-dynamical-invariant-validation` | `synthesis` | (absent) | Per-hyp |
| `doc/reports/synthesis/enriched-categorical-lenses.md` | `synthesis:h02-enriched-categorical-lenses` | `synthesis` | (absent) | Per-hyp |
| `doc/reports/synthesis/higher-order-topology.md` | `synthesis:h03-higher-order-topology` | `synthesis` | (absent) | Per-hyp; only one with `h`-prefixed filename |

Per-hyp files are **partially** Plan-#4 canonical (`type: synthesis` + `synthesis:<slug>` id), missing only `report_kind:`. Rollup + emergent-threads use the legacy `type: report` shape.

### mm30 (`/home/keith/d/r/mm30`)

| File | `id:` | `type:` | `report_kind:` |
|---|---|---|---|
| `synthesis.md` | `report:synthesis` | `report` | `synthesis-rollup` |
| `_emergent-threads.md` | `report:synthesis-emergent-threads` | `report` | `emergent-threads` |
| 5× `h<X>-...md` | `report:synthesis-h<X>-<slug>` | `report` | `hypothesis-synthesis` |

mm30 is **uniformly drifted** — every file is `type: report` with `report_kind` already present. The `id:` form for the emergent-threads file (`report:synthesis-emergent-threads`) was **not cataloged in the audit** and is not handled by any current rule.

### protein-landscape (`/home/keith/d/protein-landscape`)

| File | `id:` | `type:` | `report_kind:` | Notes |
|---|---|---|---|---|
| `synthesis.md` | (absent) | `synthesis-rollup` | (absent) | Has `synthesized_from:`, `emergent_threads_sha:`, **`orphan_question_count: 23`** |
| `_emergent-threads.md` | (absent) | `emergent-threads` | (absent) | Has `orphan_ids:` |
| 3× `h0<X>-...md` | `synthesis:h0<X>-<slug>` | `synthesis` | (absent) | Per-hyp |

PL's rollup uses the type itself as the discriminator (`type: synthesis-rollup`) rather than `type: synthesis` + `report_kind: synthesis-rollup`. The audit cataloged this. **What the audit did NOT catalog:** PL's rollup carries `orphan_question_count` (a Plan-#4 emergent-threads-only field). Either (a) PL consolidates orphan counts onto the rollup as a project extension, or (b) it's drift. Plan #4's spec doesn't say either way.

### cbioportal (`/home/keith/r/cbioportal`)

No synthesis area. Confirmed.

---

## What Plan #4 canonized

From `templates/synthesis.md`, `commands/big-picture.md` Phase 2/3, and `meta/validate.sh` § 11a:

**All `type: synthesis` files require:**
- `id: "synthesis:<slug>"` — slug ∈ {`<hyp-id>`, `rollup`, `emergent-threads`}
- `type: "synthesis"`
- `report_kind:` ∈ {`hypothesis-synthesis`, `synthesis-rollup`, `emergent-threads`}
- `generated_at:` (ISO-8601)
- `source_commit:` (40-char SHA)

**Per-`report_kind` required fields:**
- `synthesis-rollup`: `synthesized_from:`, `emergent_threads_sha:`
- `hypothesis-synthesis`: `hypothesis:`, `provenance_coverage:`
- `emergent-threads`: `orphan_question_count:`, `orphan_interpretation_count:`, `orphan_ids:`

**Optional all kinds:** `phase: active`.

---

## Gaps identified

### A. Audit cataloging gaps (factual corrections needed)

1. **NS has a synthesis area** (rollup + emergent-threads + 4 per-hyp). Audit § 3.3 declared NS had none.
2. **NS rollup uses a third id-form** (`report:project-synthesis`), distinct from mm30 (`report:synthesis`) and PL (no `id:`).
3. **NS emergent-threads uses a fourth id-form** (`report:emergent-threads`), distinct from mm30's `report:synthesis-emergent-threads`.
4. **mm30 emergent-threads id-form** (`report:synthesis-emergent-threads`) was not cataloged — audit only listed mm30's per-hyp `report:synthesis-<slug>` and rollup `report:synthesis`.
5. **PL rollup carries `orphan_question_count`** directly — a Plan-#4 emergent-threads-only field, not cataloged as a PL extension or drift.
6. **PL rollup lacks any `id:`** — present in audit's prose but not surfaced as a migration target.

### B. Plan #4 spec ambiguities (user decisions needed)

**Q1 — Orphan counts on rollup vs. threads file.**
PL puts `orphan_question_count` on the rollup. Plan #4 puts it on the emergent-threads file. After migration, where should it live?

- **Option A:** strict Plan #4 — orphan counts ONLY on emergent-threads. PL's rollup must lose `orphan_question_count`; emergent-threads must gain it. Migration would need to read the value off the rollup and write it onto the threads file.
- **Option B:** allow both — Plan #4 spec is extended to permit `orphan_question_count` on the rollup as a denormalized convenience. PL's shape is canonical-as-is.
- **Option C:** strict Plan #4 + rollup keeps a back-pointer — orphan counts move to threads, rollup keeps `emergent_threads_sha:` only (already does).

I'd recommend **(C)** — keeps Plan #4's separation cleaner; the threads file is the source-of-truth for orphan-population data; rollup just links via SHA. But it's your call.

**Q2 — `synthesized_from:` form.**
PL uses inline-dict form: `synthesized_from: [{ hypothesis: ..., file: ..., sha: ... }]`. mm30 and NS use block-list form. Plan #4's template shows block-list; `commands/big-picture.md` Phase 3 example shows inline-dict.

- **Option A:** allow both — they're equivalent YAML. Validator accepts either; `commands/big-picture.md` continues emitting whichever form it prefers.
- **Option B:** canonize block-list — migration converts inline-dict → block-list.
- **Option C:** canonize inline-dict — migration converts block-list → inline-dict.

I'd recommend **(A)** — both are valid YAML; forcing a normalization adds churn for no semantic gain. Plan #4 should explicitly say "either form is canonical".

### C. Migration-script gaps (rule redesign needed)

Once Q1/Q2 are decided, the rule set needs redesign. Current state:

| Current rule | What it covers | What it MISSES |
|---|---|---|
| `synthesis-type-mm30` | `id: report:synthesis-<slug>` (per-hyp) and literal `id: report:synthesis` (rollup); rewrites `type: report` → `type: synthesis` and matching id rewrites | mm30 emergent-threads (`id: report:synthesis-emergent-threads`); NS rollup (`id: report:project-synthesis`); NS emergent-threads (`id: report:emergent-threads`) — all three keep `type: report` after this rule because no id pattern matches; the `type:` rewrite IS unconditional but no id rewrite means the file ends up half-migrated |
| `synthesis-type-pl-emergent-threads` | PL's `_emergent-threads.md` with `type: emergent-threads` | NS / mm30 emergent-threads (different starting `type:`) |
| `synthesis-report-kind-pl-hyp` | Files matching glob `h*.md` only | NS per-hyp files: 3 of 4 don't start with `h` (`double-categorical-...`, `dynamical-invariant-...`, `enriched-categorical-...`); only `higher-order-topology.md` is caught |
| `pre-registration-type` | Files where `id:` starts with `pre-registration:` | NS's third-shape: `id: plan:pre-registration-<slug>` (4 files) |
| `natural-systems-pre-reg-frontmatter` | NS pre-regs missing both `id:` and `type:` (3 files) | Works as designed |

**Net effect of running the current rules on each project:**

| Project | What lands cleanly | What stays half-migrated or untouched |
|---|---|---|
| NS rollup | `type: report` → `type: synthesis` | `id: report:project-synthesis` not rewritten; `report_kind:` not inserted |
| NS emergent-threads | nothing (script errors on PL-shape rule) | `id:`, `type:`, `report_kind:` all stay drifted |
| NS per-hyp (3 of 4) | nothing | `report_kind:` not inserted (filename glob mismatch) |
| NS per-hyp (1 of 4: `higher-order-topology.md`) | `report_kind: hypothesis-synthesis` inserted | clean |
| NS pre-reg (4× `id: plan:pre-registration-<slug>`) | nothing | wrong `id:` prefix; wrong `type:` |
| mm30 rollup | `type:` rewritten, `id:` rewritten to `synthesis:rollup` | clean |
| mm30 emergent-threads | `type:` rewritten | `id: report:synthesis-emergent-threads` not rewritten; ends up `type: synthesis` + invalid id (drift after migration) |
| mm30 per-hyp | both passes work | clean |
| mm30 pre-reg | `type: plan` → `type: pre-registration` (good) | clean |
| PL rollup | nothing | needs `id:` insertion, `type: synthesis-rollup` → `type: synthesis`, `report_kind: synthesis-rollup` insertion, possible orphan-count migration |
| PL emergent-threads | works | clean |
| PL per-hyp | works | clean |
| PL pre-reg | `type: plan` → `type: pre-registration` (good) | clean |

In short: **mm30 ends up with one half-migrated file (emergent-threads with invalid id), NS ends up with multiple half-migrated files plus an unmigrated emergent-threads, and PL's rollup is entirely untouched by the current rule set.**

---

## Recommendation

### Phase 1 (gated on Q1 + Q2 answers — before any code)

1. **You answer Q1 (orphan counts) and Q2 (`synthesized_from:` form).** I've recommended (C) and (A) respectively.
2. **Update `docs/audits/downstream-project-conventions/synthesis.md` § 3.3** with the corrected per-project shape catalog. The current text claims NS has no synthesis area — that's the most consequential factual error.
3. **Update `templates/synthesis.md` and/or `commands/big-picture.md`** with the resolution of Q1 and Q2 if those decisions extend Plan #4.

### Phase 2 (rule redesign — once Phase 1 lands)

4. **Replace the three project-named synthesis rules with shape-driven rules.** Rough sketch:
   - `synthesis-type-and-id-rollup` — for any `<root>/doc/reports/synthesis.md`: rewrite `type:` to `synthesis`, ensure `id: synthesis:rollup`, ensure `report_kind: synthesis-rollup`.
   - `synthesis-type-and-id-emergent-threads` — for any `<root>/doc/reports/synthesis/_emergent-threads.md`: rewrite `type:` to `synthesis`, ensure `id: synthesis:emergent-threads`, ensure `report_kind: emergent-threads`. Handle pre-existing `type` values: `report`, `emergent-threads`, `synthesis-rollup` (defensive). If Q1 → option (C), also migrate `orphan_question_count`/`orphan_interpretation_count` from rollup to threads when both files exist.
   - `synthesis-type-and-id-per-hyp` — for any `<root>/doc/reports/synthesis/*.md` excluding `_*`: ensure `type: synthesis`; rewrite legacy `id:` forms (`report:synthesis-<slug>` → `synthesis:<slug>`); ensure `report_kind: hypothesis-synthesis`. **No filename-prefix gating** — the directory placement is the discriminator.
   - Mention rewrites: rewrite any reference to `report:synthesis-<slug>`, `report:synthesis`, `report:project-synthesis`, `report:synthesis-emergent-threads`, `report:emergent-threads` to the new canonical equivalents, path-keyed against the post-pass-1 file set.
5. **Generalize `pre-registration-type`** to also handle the third shape: when `id:` starts with `plan:pre-registration-<slug>`, rewrite both `id:` (strip `plan:` prefix) AND `type: plan` → `type: pre-registration`.
6. **Re-dry-run on all four projects** before any apply. Compare against the corrected audit catalog.

### Phase 3 (apply, gated on Phase 2 dry-run match)

7. Apply on cbioportal first (still expected to be no-op for synthesis since it has none).
8. Apply on mm30 second (uniformly drifted; cleanest test of the redesigned rules).
9. Apply on PL third (script-error path resolved + rollup migration).
10. Apply on NS last (mixed shapes; highest risk of surprise).

---

## Decision points for user

- **Q1:** Orphan counts placement — (A) strict-Plan-#4 / (B) allow on rollup / (C) strict + back-pointer. **Recommendation: C.**
- **Q2:** `synthesized_from:` form — (A) allow both / (B) canonize block-list / (C) canonize inline-dict. **Recommendation: A.**
- **Q3:** Audit § 3.3 update — (A) edit in place with strikethrough on stale claims / (B) append a "post-investigation correction" subsection. **Recommendation: B** — preserves the audit's original observations as historical record while linking to corrected state.
- **Q4:** Greenlight to redesign rules per Phase 2? Estimated work: ~half the size of the original `synthesis-type-mm30` rule per replacement; one extra rule for orphan-count migration if Q1=C.
- **Q5:** Should the redesigned rules also cover the cross-mention rewrites for the new id forms (e.g., NS rollup `report:project-synthesis` mentions in linked docs)? Audit didn't quantify; would need a quick `git grep` per project to size.

---

## Files referenced

- `docs/plans/2026-04-25-downstream-conventions-migration.md` (the migration plan; Task 2 paused)
- `docs/audits/downstream-project-conventions/synthesis.md` (the audit; § 3.3 is the section needing correction)
- `docs/plans/2026-04-25-synthesis-rollup-frontmatter.md` (the upstream Plan #4)
- `templates/synthesis.md`, `commands/big-picture.md`, `meta/validate.sh` (Plan #4 canonical surfaces)
- `scripts/migrate_downstream_conventions.py` (the rules; lines 354–717 are the additions from commit `497a75f`)
