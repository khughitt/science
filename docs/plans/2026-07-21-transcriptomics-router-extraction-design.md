# Transcriptomics Hub Extraction — Design

**Phase 4, slice 2.** Convert `skills/bio/transcriptomics/SKILL.md` from a
route-and-teach hub into a pure navigation router, extracting its cross-cutting
teaching content into two typed leaves. Mirrors slice 1 (statistics router
reconciliation) but is larger: the extracted content is actively cited by the
three modality leaves, so their references must be retargeted, and the
cross-platform material is duplicated across the hub and the modality leaves.

## Problem

`bio/transcriptomics/SKILL.md` (173 lines) both routes (a 3-row modality table →
`bulk-rnaseq-qa`, `microarray-qa`, `scrna-qa`) **and** teaches substantial
cross-cutting methodology:

- a universal pre-flight checklist (6 questions to answer before analysis),
- three preprocessing idioms (validate-by-inspection, sidecar-logging,
  filter-must-commute),
- a cross-platform aggregation strategy taxonomy (3 strategies), and
- a "when to invoke" prose block.

Per the router doctrine (`skill-authoring.md:44`, `study-design/SKILL.md:9`), a
router carries no methodology; teaching content belongs in a typed leaf. The
hub is one of the remaining phase-4 extraction candidates.

The teaching content is not merely trapped — it is **cited by name** from the
modality leaves (`bulk-rnaseq-qa.md:97` references the hub's *"filter steps must
commute with the question"* idiom; all three leaves' Companion Skills point to
`SKILL.md` for *"expression-data hub conventions for cross-platform cohort
QA"*). And the cross-platform aggregation topic is **duplicated at three
levels**: the hub's generic taxonomy, `microarray-qa.md:91` (limma→metafor /
rank-norm / SVA), and `scrna-qa.md:183` (pseudobulk). The extraction gives that
topic one authoritative home for the *decision*, while the platform-specific
*realizations* stay in their modality leaves.

## Decision summary (from brainstorming)

Confirmed with the user:

1. **Two new leaves**, both under `bio/transcriptomics/`. Filenames carry **no**
   subject prefix (matching `bulk-rnaseq-qa.md`); the `transcriptomics-` prefix
   lives only in the `name:` frontmatter value:
   - **Leaf A — file `cohort-qa.md`, `name: transcriptomics-cohort-qa`**
     (`measurement-qa`): the single-cohort ingest/QA discipline the three
     modality leaves specialize.
   - **Leaf B — file `data-integration.md`, `name: transcriptomics-data-integration`**
     (`analysis-discipline`): the multi-cohort integration decision.
2. **Integration leaf is transcriptomics-scoped**, not a broader cross-assay
   home — the concrete content (microarray intensity vs UMI vs TPM, pseudobulk,
   SVA, metafor across expression cohorts) is expression-specific. A future
   genomics/proteomics batch-integration need would be a separate leaf (the
   two-target eligibility rule), not a premature generalization here.
3. **The hub becomes a pure router** mirroring slice 1's shape, routing to five
   leaves (3 modality + 2 cross-cutting).

## Content mapping (every hub section → destination)

| Hub section (`transcriptomics/SKILL.md`) | Destination |
|---|---|
| `# Expression Data — Preprocessing & QA` + intro prose | Router intro (trimmed to navigation) |
| `## Three modalities, three QA mindsets` (modality table) | Router `## Leaves` table (kept + expanded to 5 rows) |
| `## Universal pre-flight checklist` items 1–4 + 6 (single-cohort: `.X` scale, gene ID, sample ID, cohort def, single-cohort batch PCA) | **Leaf A** (cohort-qa) |
| `## Universal pre-flight checklist` item 5 (normalization *compatibility with the aggregation strategy* — effect-size vs p-value pooling) | **split**: factual "record & verify normalization state" → **Leaf A**; the aggregation-dependent compatibility *decision* → **Leaf B** |
| `## Idiom: validate by inspection, not by trust` | **Leaf A** |
| `## Idiom: log every decision in a sidecar` | **Leaf A** |
| `## Idiom: filter steps must commute with the question` | **Leaf A** |
| `## Cross-platform aggregation: the fundamental tension` (3 strategies) | **Leaf B** (data-integration) |
| `## When to invoke` (prose bullets) | Dissolved: folded into the router's `## Routing trigger` and the two leaves' When-to-use slots |
| `## Companion Skills` | Router `## Companion Skills` (kept, updated) |

**Boundary note — single-cohort QA vs cross-experiment integration.** The split
runs through two checklist items, not one:

- **Item 6** (*"quick PCA coloured by batch… if batch separates more strongly
  than biology…"*) is **single-cohort** batch *detection* → stays in **Leaf A**.
  The *cross-experiment* remedy (which of ComBat / RUV / SVA / mixed-effects /
  exclusion, chosen as part of a committed integration strategy) → **Leaf B**.
- **Item 5** (normalization *compatibility with your meta-analysis* —
  effect-size aggregation needs scale harmonization, e.g. z-score before
  metafor; p-value pooling tolerates scale but not distributional violations) is
  an **aggregation-dependent decision** → the *decision* goes to **Leaf B**;
  Leaf A keeps only the factual "record and verify what normalization was
  applied" (which is also part of item 1's `.X`-scale check).

The two leaves compose (a multi-cohort meta-analysis loads both), same as
slice-1's composable axes.

## Leaf A — file `cohort-qa.md`, `name: transcriptomics-cohort-qa`

(Filename carries no subject prefix — matching `bulk-rnaseq-qa.md` /
`name: transcriptomics-bulk-rnaseq-qa`; the prefix lives in the `name:` field.)

- **Archetype:** `measurement-qa` (matches the 3 modality leaves; this is their
  platform-general parent QA discipline).
- **Operation:** QA a single transcriptomic cohort at ingest before it enters
  analysis.

**The extracted content must be reshaped into the `measurement-qa` slot
contract** (`skill-taxonomy.md:28`, `templates/measurement-qa.md`), not pasted
as free prose. Target section outline:

- `## Sources & ingestion/construction` — public deposits (GEO, ArrayExpress,
  MMRF, HCA, recount, ARCHS4) and the AnnData/`.X`/`.raw`/`.layers` ingest
  surface.
- `## Pre-flight checklist` — the hub's items **1–4 and 6** as `- [ ]` checks
  (`.X` scale via the inspection code block; gene-ID axis; sample-ID; cohort
  definition; single-cohort batch PCA). Plus the item-5 *factual* half: "record
  and verify what normalization the depositor applied" (the aggregation-
  compatibility *decision* is Leaf B's, cross-referenced).
- `## QA metrics` — a table making the idioms' inspection checks concrete:
  metric (e.g. `n_unique(sample_id) == n_rows`; integer-like fraction of `.X`;
  fraction of rows dropped by a filter per group) · passing range · meaning of
  failure. This operationalizes "validate by inspection, not by trust."
- `## Common failure modes` — the failure content of the three idioms:
  README-says-vs-matrix-is mismatch; unlogged preprocessing decisions
  (no sidecar); detection-rate / `mean ± 3 SD` / aggregated-doublet filters that
  don't commute with the stratifying question.
- `## Halt-On Conditions` — e.g. `.X` contents cannot be determined from data +
  metadata; sample identifiers non-unique with no collapse rule; a filter drops
  a stratification group asymmetrically with no logged mask. (**Required by the
  archetype and, once `lint.py` is updated — see *Linter enforcement edit* —
  enforced.**)
- `## Minimum output package` — the `cohort_audit.json` sidecar promoted from
  the "log every decision in a sidecar" idiom into the fixed output tree
  (raw/after-each-filter counts, dropped patients + reasons, gene-universe size,
  normalization status, batch schema) + a `summary.md`.
- `## Success test` — the canonical measurement-qa test: *does the produced QA
  package contain the named files, and does the summary state which Halt-On
  Conditions were evaluated?*

## Leaf B — file `data-integration.md`, `name: transcriptomics-data-integration`

- **Archetype:** `analysis-discipline` — the discipline of committing to and
  justifying a cross-cohort integration strategy **upfront** ("the choice
  cascades"). Verb test: justify / lock / commit.
- **Operation:** decide and commit how to integrate multiple heterogeneous
  transcriptomic cohorts for meta-analysis, and how to handle experiment-level
  technical variation when pooling.

**The content must be reshaped into the `analysis-discipline` slot contract**
(`skill-taxonomy.md`, `templates/analysis-discipline.md`), not pasted as prose.
Target section outline:

- `## Triggering condition` — before designing per-cohort preprocessing for any
  analysis that pools ≥2 cohorts/platforms.
- `## Required reasoning / check / precommitment` — (a) name the aggregation
  strategy; (b) run the **identifiability check**: is the biological contrast
  fully aliased with cohort/platform/batch? (c) name the technical-artifact
  adjustment and its assumptions.
- `## Decision rule or reasoning criteria` — the **strategy taxonomy** and the
  **branch-specific artifact rules** (these methods are *not* interchangeable):
  1. within-platform association testing → aggregate test statistics
     (Stouffer/Fisher/metafor; z-score effects before pooling);
  2. common-reference normalization (rank/percentile/z-score) — loses magnitude;
  3. hierarchical models with platform random effects — compute/assumption-heavy.
  Batch adjustment branches: **ComBat** (needs known batch labels, assumes
  batch-vs-biology not confounded); **RUV** (needs suitable negative-control
  genes or replicate samples); **SVA** (estimates latent factors, assumes they
  are separable from the contrast); **mixed-effects** (platform as random
  effect); **exclusion**. The chosen strategy dictates which is admissible.
- `## Outcomes` — strategy committed (proceed) / non-identifiable (halt) /
  admissible-but-assumption-fragile (proceed with stated limitation).
- `## Halt / escalation` — **halt when cohort/platform/batch is completely
  aliased with the biological contrast** (no adjustment recovers an
  unconfounded effect — the design is non-identifiable, not fixable by ComBat/
  RUV/SVA); escalate when the only admissible strategy rests on assumptions the
  data cannot support (e.g. no valid control genes for RUV).
- `## Required evidence & artifacts` — the committed strategy recorded in the
  pre-registration; the identifiability assessment; the adjustment method + its
  assumption check.
- `## Permitted reporting language` — an effect pooled under a fragile-assumption
  or non-recoverable-confound path must be reported with that limitation, not as
  a clean cross-cohort effect; "harmonized" is not "confound-free."
- `## Success test` — the canonical analysis-discipline test: was the strategy
  precommitted before per-cohort preprocessing, and does the pooled conclusion
  follow from it (mechanically where the identifiability gate applies)?

**Boundary (what Leaf B does NOT absorb):** the modality-specific *realizations*
stay in their leaves — `microarray-qa.md`'s SVA/rank-norm section,
`scrna-qa.md`'s pseudobulk section, and `bulk-rnaseq-qa.md`'s per-cohort-vs-
pooled section are **not** moved. Leaf B owns the decision + identifiability
gate; each modality leaf keeps its realization and gains a one-line reference up
to Leaf B. This keeps the blast radius to *retargeting/annotating* the modality
leaves, not rewriting their bodies.

## Router — `transcriptomics/SKILL.md`

Pure navigation, mirroring `study-design/SKILL.md` / the slice-1
`statistics/SKILL.md`:

- `# Transcriptomics — Expression-Data Router`
- "A router carries no methodology; teaching content belongs in a typed leaf."
- `## Routing trigger` — load when a transcriptomic dataset is being ingested,
  QA'd, or integrated for meta-analysis.
- `## Scope boundary` — covers expression-cohort ingest QA and multi-cohort
  integration across bulk RNA-seq, microarray, and scRNA-seq; excludes the
  statistical modeling itself (→ `../../statistics/SKILL.md`) and generic data
  conventions (→ `../../data-management/SKILL.md`).
- `## Leaves` — a 5-row table:

  | Leaf | Load when |
  |---|---|
  | `cohort-qa.md` | QA'ing any newly-acquired transcriptomic cohort (cross-modality checklist + idioms) |
  | `data-integration.md` | integrating/aggregating multiple cohorts for meta-analysis (strategy + batch adjustment) |
  | `bulk-rnaseq-qa.md` | bulk RNA-seq cohort specifics |
  | `microarray-qa.md` | microarray cohort specifics |
  | `scrna-qa.md` | single-cell RNA-seq cohort specifics |

  (Backticked relative paths, not `[](…)` links, per the slice-1 router style.)
- `## Decision / compose order` — stated explicitly, not left implicit:
  - **Single-cohort work** → load `cohort-qa.md` **plus** the applicable
    modality leaf (`bulk-rnaseq-qa` / `microarray-qa` / `scrna-qa`).
  - **Multi-cohort / meta-analysis work** → **additionally** load
    `data-integration.md`, and consult it **before** per-cohort preprocessing
    decisions are made (its strategy choice cascades into preprocessing).
- `## Parent & neighbors` (`../SKILL.md` = the `bio/` router; neighbors
  `../genomics/SKILL.md`, `../proteomics/SKILL.md`), `## Success test`,
  `## Companion Skills`.

## Reference-retargeting inventory

**Stay pointing at the router `SKILL.md`** (these reference the hub *as a
router / navigational entry*, which is correct after it becomes a pure router):

- `skills/bio/SKILL.md:26` — parent `bio/` router's Leaves row → `transcriptomics/SKILL.md`.
- `skills/bio/proteomics/SKILL.md:34` — "Neighboring routers: … `../transcriptomics/SKILL.md`".
- `skills/bio/genomics/SKILL.md:39` — "expression cohorts often paired with mutation cohorts" → router.
- `skills/data-management/SKILL.md:15,151` — navigational pointers to the transcriptomic area.
- `skills/INDEX.md:26` — machine entry `transcriptomics: skills/bio/transcriptomics/SKILL.md` (router stays the entry point).

**Retarget to the new leaves** (these reference the hub *for teaching content
that is moving*):

- `skills/bio/transcriptomics/bulk-rnaseq-qa.md:12` — intro "see `SKILL.md`" (platform-general conventions) → `cohort-qa.md`.
- `skills/bio/transcriptomics/bulk-rnaseq-qa.md:97` — "(see SKILL.md \"filter steps must commute with the question\")" → `cohort-qa.md` (the idiom moved there).
- `skills/bio/transcriptomics/bulk-rnaseq-qa.md:165` — Companion "expression-data hub conventions for cross-platform cohort QA" → `cohort-qa.md` (+ `data-integration.md` where the cross-platform decision now lives).
- `skills/bio/transcriptomics/microarray-qa.md:15` — "For platform-general conventions see `SKILL.md`" → `cohort-qa.md`.
- `skills/bio/transcriptomics/microarray-qa.md:175` — Companion line → `cohort-qa.md` (+ `data-integration.md`).
- `skills/bio/transcriptomics/scrna-qa.md:12` — intro `SKILL.md` → `cohort-qa.md`.
- `skills/bio/transcriptomics/scrna-qa.md:255` — Companion line → `cohort-qa.md` (+ `data-integration.md`).

Additionally, **all three** modality leaves' cross-platform sections gain a
one-line reference to `data-integration.md` as the strategy they realize (light
touch; bodies otherwise unchanged):

- `microarray-qa.md:91` — "Cross-platform meta-analysis (the hard problem)" (SVA / rank-norm).
- `scrna-qa.md:183` — "Pseudobulk for cross-platform aggregation".
- `bulk-rnaseq-qa.md:106` — the "For meta-analysis across cohorts" per-cohort-vs-pooled decision (`bulk-rnaseq-qa.md` already carries the same strategy choice). Its duplicated decision text is rephrased to read as the **bulk-specific realization** of the strategy `data-integration.md` owns, rather than a second authoritative statement of it.

`skills/data-management/SKILL.md:185` — Companion "expression-matrix
preprocessing and QA" currently → `../bio/transcriptomics/SKILL.md`. This is a
judgment call: it points at the QA content. Retarget its label target to the
router (still the entry point) but the design leaves the label as navigational;
the router's own Companion table surfaces the QA leaf. (Recorded so the
implementer does not treat it as a stale label to "fix" — it stays on the
router intentionally.)

## Doctrine edits (BOTH files — the slice-1 lesson)

1. **`skills/meta/skill-authoring.md:44`** — the router-invariant paragraph.
   Change `3 of 14 … hubs … data-management/SKILL.md, bio/transcriptomics/SKILL.md, and pipelines/SKILL.md.`
   → `2 of 14 … hubs … data-management/SKILL.md and pipelines/SKILL.md.`; add a
   dated note that `bio/transcriptomics/SKILL.md` was extracted to a router on
   2026-07-21 into `transcriptomics-cohort-qa` and `transcriptomics-data-integration`.
2. **`skills/meta/skill-taxonomy.md:112`** — **currently stale** (still lists
   four hubs incl. `statistics/`, which slice 1 already reconciled). Update to
   reflect reality after this slice: statistics reconciled (slice 1),
   transcriptomics extracted (this slice), so **two hubs remain
   (`data-management/`, `pipelines/`)**. This corrects the slice-1 miss and the
   current slice in one edit.

## Linter enforcement edit (`science/src/science_tool/skills_lint/lint.py`)

`HALT_ON_REQUIRED` (lint.py:71) is a hard-coded set of `measurement-qa` leaves
that must carry a `## Halt-On Conditions` section. It currently lists the three
existing transcriptomics modality leaves but **not** the new `cohort-qa.md`. Add
`"bio/transcriptomics/cohort-qa.md"` to the set so Leaf A's Halt-On contract is
actually enforced (a check that cannot fail is not a check —
[[feedback_never_tune_metadata_to_silence_a_check]]). `data-integration.md` is
`analysis-discipline`, not `measurement-qa`, so it is **not** added to this set;
its `## Halt / escalation` slot is an archetype-template convention, not a
lint-enforced section. Update the covering test (`tests/` for `skills_lint`) if
it asserts the membership of `HALT_ON_REQUIRED`.

## INDEX edits (`skills/INDEX.md`)

- Add two machine `name: path` entries (alphabetically among the
  `transcriptomics-*` block):
  - `transcriptomics-cohort-qa: skills/bio/transcriptomics/cohort-qa.md`
  - `transcriptomics-data-integration: skills/bio/transcriptomics/data-integration.md`
- Add the two leaves to any human descriptive listing that enumerates the
  transcriptomics leaves (mirror the existing `transcriptomics-*` descriptive
  rows).
- The `transcriptomics: …/SKILL.md` router entry is unchanged.

## Codex mirror

The generator (`codex_skills.py`) mirrors **only** `commands/*.md` (→
`science-<command>`) and the two `COMPANION_SKILLS` — `scientific-writing`
(`skills/writing/scientific-writing.md`) and `skill-development`
(`skills/meta/SKILL.md`, which bundles its sibling markdown + `templates/` as
resources). It does **not** walk `skills/bio/` leaves. Therefore:

- The two new leaves (`cohort-qa.md`, `data-integration.md`) and the router
  rewrite **do not appear** in `codex-skills/` at all — nothing to regenerate on
  their account.
- Regeneration **is** still required because both doctrine edits land on
  resources of the `skill-development` companion. The exact rewritten mirror
  files are precisely two:
  - `codex-skills/science-skill-development/skill-authoring.md`
  - `codex-skills/science-skill-development/skill-taxonomy.md`
- So the committed-mirror test `test_committed_codex_skills_match_fresh_generation`
  goes RED after the doctrine edits (Task on `skills/meta/`) and returns GREEN
  after regeneration — the green gate, exactly as slice 1, but touching two
  mirror files instead of one.

## Approaches considered / rejected

- **One combined QA leaf** (checklist + idioms + aggregation): rejected — the
  user's insight is that aggregation is a distinct *decision* (analysis-discipline)
  from single-cohort *QA* (measurement-qa); combining them overloads one leaf
  with two archetypes, violating exactly-one.
- **Move aggregation to `statistics/`**: rejected — no existing statistics
  meta-analysis leaf owns it, and the content is expression-platform-specific.
- **Consolidate the modality leaves' cross-platform sections into Leaf B**:
  rejected — those realizations are genuinely platform-specific QA; ripping them
  out enlarges the blast radius and misplaces platform detail. Leaf B owns the
  decision; the modality leaves keep their realizations and cross-reference it.
- **Broader cross-assay `data-integration` leaf**: rejected (user chose
  transcriptomics-scoped) — premature generalization of expression-specific
  content.

## Safety checks / invariants (for the plan's fail-closed gates)

- **No dropped knowledge:** every hub section maps to a destination (table
  above); the checklist, idioms, and aggregation taxonomy appear in the new
  leaves before the hub sections are deleted.
- **No stale labels:** after retargeting, no `skills/` file references a moved
  idiom via `SKILL.md#…` or by the old section title; the modality leaves' "see
  SKILL.md" teaching links resolve to the new leaves. (Slice-3 stale-label
  class — scan `[`<label>`](<href>)` where label names a path that no longer
  carries the content.)
- **Router carries no methodology:** final `SKILL.md` has no `## Universal
  pre-flight`, no `## Idiom:` sections, no `## Cross-platform aggregation`, no
  numbered teaching list.
- **Doctrine consistency:** both `skill-authoring.md` and `skill-taxonomy.md`
  agree on the hub count/list (two hubs), and neither lists `statistics/` or
  `bio/transcriptomics/` as a current hub.
- **Archetype-slot completeness:** Leaf A carries every `measurement-qa` slot
  (sources · pre-flight checklist · QA metrics table · common failure modes ·
  **Halt-On Conditions** · minimum output package · canonical success test);
  Leaf B carries every `analysis-discipline` slot (triggering · required
  precommitment · decision rule/criteria · outcomes · **halt/escalation
  identifiability gate** · required evidence & artifacts · permitted reporting
  language · canonical success test). Routers carry no `archetype:`.
- **Halt-On enforcement is live:** `HALT_ON_REQUIRED` includes
  `bio/transcriptomics/cohort-qa.md`, and the leaf actually contains the
  `## Halt-On Conditions` section — verified by a fail-closed check that the
  lint flags a stripped section (the check can fail).
- **Green gate:** codex mirror regenerated; exactly two mirror files change
  (`science-skill-development/skill-authoring.md` + `skill-taxonomy.md`); the new
  bio/ leaves do **not** appear in `codex-skills/`;
  `test_committed_codex_skills_match_fresh_generation` + full `pytest` +
  `skills lint` green.

## Out of scope (explicitly unchanged)

- The three modality leaves' bodies (only their reference links + one-line
  cross-refs change).
- The `frictionless` / `mutational-signatures` splits, the `data-management` and
  `pipelines` extractions, the genomics "two leaves" fix — separate slices.
