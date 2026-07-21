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

1. **Two new leaves**, both under `bio/transcriptomics/` (subject prefix
   `transcriptomics-`):
   - **Leaf A — `transcriptomics-cohort-qa.md`** (`measurement-qa`): the
     single-cohort ingest/QA discipline the three modality leaves specialize.
   - **Leaf B — `transcriptomics-data-integration.md`** (`analysis-discipline`):
     the multi-cohort integration decision.
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
| `## Universal pre-flight checklist` (6 items, incl. item 6 single-cohort batch PCA) | **Leaf A** (cohort-qa) |
| `## Idiom: validate by inspection, not by trust` | **Leaf A** |
| `## Idiom: log every decision in a sidecar` | **Leaf A** |
| `## Idiom: filter steps must commute with the question` | **Leaf A** |
| `## Cross-platform aggregation: the fundamental tension` (3 strategies) | **Leaf B** (data-integration) |
| `## When to invoke` (prose bullets) | Dissolved: folded into the router's `## Routing trigger` and the two leaves' When-to-use slots |
| `## Companion Skills` | Router `## Companion Skills` (kept, updated) |

**Boundary note — single-cohort batch QA vs cross-experiment integration.**
Pre-flight item 6 (*"quick PCA coloured by batch… if batch separates more
strongly than biology… ComBat, RUV, mixed-effects, exclusion"*) is
**single-cohort** batch *detection* → stays in **Leaf A**. **Leaf B** owns the
*cross-experiment* framing: choosing an aggregation strategy across
heterogeneous cohorts and adjusting for experiment-level technical artifacts
when integrating them. The two leaves compose (a multi-cohort meta-analysis
loads both), same as slice-1's composable axes.

## Leaf A — file `cohort-qa.md`, `name: transcriptomics-cohort-qa`

(Filename carries no subject prefix — matching `bulk-rnaseq-qa.md` /
`name: transcriptomics-bulk-rnaseq-qa`; the prefix lives in the `name:` field.)

- **Archetype:** `measurement-qa` (matches the 3 modality leaves; this is their
  platform-general parent QA discipline).
- **Operation:** QA a single transcriptomic cohort at ingest before it enters
  analysis — verify what `.X` is, the identifiers, the cohort definition, and
  that preprocessing choices don't distort the downstream question.
- **Content:** the pre-flight checklist (6 items) + the three idioms, verbatim
  from the hub (the `.X`-inspection code block and the `cohort_audit.json`
  sketch move with them).
- **Success test:** a newly-acquired transcriptomic deposit is QA'd against the
  checklist and idioms without reading methodology from the router.

## Leaf B — file `data-integration.md`, `name: transcriptomics-data-integration`

- **Archetype:** `analysis-discipline` — the discipline of committing to and
  justifying a cross-cohort aggregation strategy **upfront** ("state which
  strategy you're using before designing per-cohort preprocessing; the choice
  cascades"). Verb test: justify / lock / commit.
- **Operation:** decide and commit how to integrate multiple heterogeneous
  transcriptomic cohorts for meta-analysis, and how to handle experiment-level
  technical variation when pooling.
- **Content:**
  - The cross-platform aggregation strategy taxonomy from the hub: (1)
    within-platform association testing → aggregate test statistics
    (Stouffer/Fisher/metafor), (2) common-reference normalization
    (rank/percentile/z-score), (3) hierarchical models with platform random
    effects — with the "state upfront, the choice cascades" discipline.
  - Cross-experiment batch / technical-artifact adjustment as an integration
    concern (the confound when batch separates more strongly than biology
    *across cohorts*; ComBat / RUV / SVA / mixed-effects / exclusion as the
    lever, chosen as part of the committed strategy).
- **Boundary (what Leaf B does NOT absorb):** the modality-specific
  realizations stay in their leaves — `microarray-qa.md`'s SVA/rank-norm section
  and `scrna-qa.md`'s pseudobulk section are **not** moved. Leaf B references
  them as platform realizations of the strategy it governs; they reference Leaf
  B for the strategy decision. This keeps the slice's blast radius to
  *retargeting* the modality leaves, not rewriting their bodies.
- **Success test:** a multi-cohort meta-analysis commits to one aggregation
  strategy and a technical-artifact-adjustment plan before per-cohort
  preprocessing is designed.

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
- `## Decision / compose order`, `## Parent & neighbors` (`../SKILL.md` = the
  `bio/` router; neighbors `../genomics/SKILL.md`, `../proteomics/SKILL.md`),
  `## Success test`, `## Companion Skills`.

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

Additionally, `microarray-qa.md`'s SVA section and `scrna-qa.md`'s pseudobulk
section gain a one-line cross-reference to `data-integration.md` as the strategy
they realize (light touch; bodies unchanged).

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

Regenerate `codex-skills/` via `scripts/generate_codex_skills.py` after all
`skills/` edits. Unlike slice 1, this slice **does** change generator inputs
that reach the mirror beyond `skill-authoring.md` — verify empirically during
planning which `codex-skills/` files the generator rewrites (the two new leaves
are under `bio/`, whose mirroring behavior must be confirmed, plus the
`skill-authoring.md`/`skill-taxonomy.md` copies). The committed-mirror test
`test_committed_codex_skills_match_fresh_generation` is the green gate.

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
- **Archetype validity:** Leaf A `measurement-qa`, Leaf B `analysis-discipline`;
  routers carry no `archetype:`; `skills lint` passes.
- **Green gate:** codex mirror regenerated; `test_committed_codex_skills_match_fresh_generation`
  + full `pytest` + `skills lint` green.

## Out of scope (explicitly unchanged)

- The three modality leaves' bodies (only their reference links + one-line
  cross-refs change).
- The `frictionless` / `mutational-signatures` splits, the `data-management` and
  `pipelines` extractions, the genomics "two leaves" fix — separate slices.
