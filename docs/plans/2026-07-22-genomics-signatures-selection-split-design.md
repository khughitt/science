# Genomics: Split `mutational-signatures-and-selection` — Design

**Status:** design, pending review
**Date:** 2026-07-22
**Program:** skills taxonomy, phase 4 (final remaining slice — leaf split)

## Goal

Split the genomics leaf `mutational-signatures-and-selection.md` — whose two
sources back two independently triggered analyses with different contracts —
into two single-concern leaves, and reconcile the `bio/genomics/SKILL.md` router
(which also carries a stale "existing two leaves" count) and all cross-references
to the split.

## Background

`skills/bio/genomics/mutational-signatures-and-selection.md` fuses two distinct
analyses under one `measurement-qa` leaf with `sources: [cosmic-signatures,
dndscv]`:

1. **Mutational-signature decomposition** — SBS/DBS/ID spectra, TMB,
   reconstruction error, COSMIC-version pinning, low-count/hypermutator flags.
   Tool basis: `cosmic-signatures`. This is *output QA*: is the fitted
   signature assignment trustworthy?
2. **Driver / selection inference** — dN/dS, dNdScv, driver-gene enrichment,
   length/expression/replication-timing confounding, circular validation. Tool
   basis: `dndscv`. This is an *interpretation gate*: may a gene rank be called
   selection, or is it confounded?

The single-concern principle that drives the whole taxonomy program flags this
leaf as a split candidate — not because it declares two sources (many leaves
legitimately do), but because those two sources back two independently triggered
analyses with different content contracts and success tests. The two analyses
use different tools, answer different downstream questions, and have disjoint
failure-mode sets.

The `bio/genomics/SKILL.md` router additionally says (line 34) "the existing
**two** leaves" — already stale (there are three today) and about to change
again. This slice fixes that in the same pass.

## Decision (confirmed with owner)

- **Split** into two single-concern leaves.
- **Asymmetric archetypes**, honest to the content:
  - signatures leaf → `measurement-qa` (output QA; keeps `## Halt-On
    Conditions`, required by the linter for this archetype)
  - selection leaf → `analysis-discipline` (interpretation gate; uses the
    Triggering-condition / Required-precommitment / Decision-rule / Outcomes /
    Halt-escalation / Required-evidence / Permitted-reporting-language slots,
    per `skills/meta/templates/analysis-discipline.md`)

## The two new leaves

Both leaves use the **exact section headings from their archetype templates**
(`skills/meta/templates/measurement-qa.md`,
`skills/meta/templates/analysis-discipline.md`) — the linter only mechanically
enforces `## Halt-On Conditions`, so template fidelity is a design obligation,
not a lint outcome.

> **Sibling-divergence note (in-scope decision, flagged):** the two existing
> genomics measurement-qa leaves (`somatic-mutation-qa`, `copy-number-sv-qa`)
> predate this template and use an older heading convention (`Acquisition
> Checklist` / `Minimum QA Tables` / `Analysis Rules` / `Output Package`). This
> divergence is not specific to genomics — it affects most measurement-qa leaves
> corpus-wide, so reshaping only these two siblings would be arbitrary. The new
> leaves follow the current template contract; bringing the existing corpus into
> line is a **separate corpus-wide measurement-qa conformance pass**, out of
> scope here.

### `skills/bio/genomics/mutational-signatures-qa.md`

- `name: genomics-mutational-signatures-qa`
- `archetype: measurement-qa`
- `sources: [cosmic-signatures, focr-tmb-harmonization]` — the second source
  (Friends of Cancer Research TMB harmonization study, added to
  `skills/sources.yaml`) is the provenance for the TMB methodology this leaf now
  teaches.
- Template-exact headings: `## Sources & ingestion/construction` · `## Pre-flight
  checklist` (checkbox items) · `## QA metrics` (Metric / Passing range / Meaning
  of failure) · `## Common failure modes` · `## Halt-On Conditions` ·
  `## Minimum output package` · `## Success test` · `## Companion Skills`.
- **Owns TMB.** This leaf explicitly owns tumor mutational burden: a pre-flight
  rule for the eligible-variant definition and callable/interrogated-megabase
  denominator, a QA-metric row for TMB per callable Mb, a `tmb.parquet` artifact,
  and a success-test mention. (The alternative — leave TMB with
  `somatic-mutation-qa` — was rejected: TMB and signatures both depend on
  callable territory, so they belong to the same burden-and-process concern.)
- **Opportunity is realized per analysis, not uniformly.** Signature spectra use
  trinucleotide-context opportunity; TMB uses eligible mutations per callable
  (interrogated) megabase. The leaf must NOT require TMB in trinucleotide context
  (a distinct-realization error). Selection's coding-length/context/local-rate
  realization lives in the selection leaf.
- **"Replication-timing bias" is NOT a signatures concern.** It is the
  driver-selection bias audit; the signatures leaf keeps only the SBS1/SBS5
  clock-signature comparison (a positive control, not a bias audit).

### `skills/bio/genomics/driver-selection.md`

- `name: genomics-driver-selection`
- `archetype: analysis-discipline` (no `## Halt-On Conditions`; the linter
  requires that section only for `measurement-qa`)
- `sources: [dndscv]`
- Template-exact headings: `## Triggering condition` · `## Required reasoning /
  check / precommitment` · `## Decision rule or reasoning criteria` ·
  `## Outcomes (pass / fail / indeterminate, or branch/threshold)` · `## Halt /
  escalation` · `## Required evidence & artifacts` · `## Permitted reporting
  language` · `## Success test` · `## Companion Skills`.
- Content mapping: opportunity model + context-aware method + pathway
  pre-definition + hypermutator handling + known-driver-as-prior →
  precommitment; the six bias audits → decision rule; pass/fail(confounded)/
  indeterminate → outcomes; permitted-reporting-language gates the wording.
- **Foundational halt.** `## Halt / escalation` halts when the opportunity model
  is missing or unverifiable (a rank may not be interpreted without per-gene
  callable territory, coding length, and context) — in addition to the
  length-confound and circular-validation halts.
- **Applicable-audit reconciliation.** Because the replication-timing audit is
  conditional on a proxy being available, Pass requires "every **applicable**
  bias audit"; an unavailable covariate must be declared unrun, and the rank is
  indeterminate (not "unconfounded") along that untested axis.

### Naming rationale

`genomics/` is treated as a subject (like `transcriptomics/`, `proteomics/`), so
leaf `name:` carries the `genomics-` prefix while filenames stay bare — matching
the three existing genomics leaves. The signatures leaf keeps the `-qa` suffix
(measurement-qa convention); the selection leaf drops it (analysis-discipline
leaves do not carry `-qa`, e.g. `transcriptomics-data-integration`). "driver-
selection" mirrors the router's existing vocabulary ("driver-selection
analyses", genomics description line 3).

## Companion-link discipline (avoids a RED window)

The two new leaves reference each other as sibling companions. Since they are
co-created across two tasks, a markdown link from the first to the
not-yet-created second would dangle (skills-lint RED) until the second lands. So
in Task 1 the signatures leaf references `driver-selection.md` with **backticks**
(not link-validated) — but this is **transient**: Task 2 creates
`driver-selection.md` and, in the same task, converts the signatures leaf's
backticked reference to an ordinary markdown link. From the end of Task 2 both
sibling references are markdown links, so drift detection is retained corpus-wide
and no reference stays permanently exempt. Companion links to already-existing
targets (`somatic-mutation-qa.md`, the `study-design/` leaves, `frictionless.md`,
`conventions.md`) are markdown links throughout. Every task stays green.

## Shared-constraint relocation

The current leaf opens with the shared thesis: "mutation counts are not
exchangeable across genome, gene, cancer type, assay, or mutational process;
every result needs an explicit opportunity model." On the split, each leaf keeps
its own realization of the opportunity requirement (signatures: trinucleotide
context; selection: coding length + context), and the *shared* precondition is
lifted into the genomics router's ordering rule, so it is stated once at the
routing layer rather than duplicated as a coupling between the two leaves.

## `bio/genomics/SKILL.md` router edits (minimal, in-scope)

1. **Layers table** — replace the single "Signatures and selection" row with two
   rows (signatures leaf; driver-selection leaf), each with its own dominant
   failure modes.
2. **Ordering rule** — keep "complete `somatic-mutation-qa.md` first"; add the
   shared opportunity-model precondition for both downstream leaves.
3. **Count-prose fix** — reword "the existing two leaves" to "the existing
   leaves" (drop the brittle hardcoded count entirely rather than change 2→4;
   this removes the class of bug we are fixing).
4. **Description** — line 3 already reads "mutational signatures, dN/dS, or
   driver-selection analyses"; no change needed.

**Non-goal:** this slice does **not** rewrite `bio/genomics/SKILL.md` onto the
full router template (Routing trigger / Scope boundary / Leaves / Decision-
compose order / Parent & neighbors / Success test). It is already an accepted
router (doctrine: "was already one"); a template-conformance pass is separate
scope.

## Cross-reference reconciliation

Every reference to the old leaf, updated to the split:

| Site | Change |
|---|---|
| `skills/INDEX.md:24` | one machine entry → two (`genomics-mutational-signatures-qa`, `genomics-driver-selection`) |
| `commands/plan-analysis.md:68` | routing row "SBS signatures, TMB, dN/dS, dNdScv, driver ranking" → route to both new leaves |
| `commands/plan-analysis.md:203` | scenario 2 (cBioPortal dN/dS): TMB/signatures → signatures leaf; dN/dS/driver ranking → driver-selection leaf |
| `skills/data-management/SKILL.md:36` | one routing line → two (signatures; dN/dS + driver selection) |
| `skills/bio/genomics/somatic-mutation-qa.md:117` | downstream companion back-ref → two refs |
| `skills/bio/genomics/SKILL.md` | table + ordering + count prose (above) |

The old file `mutational-signatures-and-selection.md` is `git rm`-ed (neither new
leaf is a pure rename — content is redistributed and the selection half is
reshaped onto the analysis-discipline template).

## Guard-test and codex-mirror analysis

- **Content-guard tests:** grep of `test_command_docs.py` + `test_codex_skills.py`
  shows no test asserts on this leaf's content or filename. The "signature" hits
  (`test_command_docs.py:120`, `:274`, `test_codex_skills.py:478`) are
  statistical *model-signatures* in `commands/review-pipeline.md`, unrelated.
  `test_plan_analysis_command_covers_pressure_scenarios` (`:756`) asserts
  `genomics-somatic-mutation-qa` (a different leaf, unchanged) and scenario
  strings that do not name the split leaf — so editing `plan-analysis.md` rows
  68/203 does not break it. Guard risk: **low**.
- **Codex mirror:** `codex-skills/` mirrors no genomics leaf, and doctrine files
  hardcode **hub** counts (0/14, unchanged — genomics is already a router), not
  leaf counts, so no doctrine edit is required. But `commands/plan-analysis.md`
  **is** a generator input, so the flip regenerates exactly one mirrored skill,
  `codex-skills/science-plan-analysis/SKILL.md`. That regeneration is part of the
  flip commit; only a **subsequent** regeneration on the committed tree has zero
  additional delta (`test_committed_codex_skills_match_fresh_generation` is the
  gate).
- **Sources:** both `cosmic-signatures` and `dndscv` are already registered in
  `skills/sources.yaml`; no registry change.

## Corpus effect

- Total non-template leaves: **45 → 46**.
- Non-meta archetype matrix (excludes the two `skills/meta/` doctrine leaves
  `skill-taxonomy.md`, `skill-authoring.md`): **43 → 44**.
- Genomics subtree: 3 → 4 leaves. measurement-qa net 0 (signatures replaces the
  old measurement-qa leaf); analysis-discipline +1 (selection is newly
  analysis-discipline); net +1 leaf overall.

## Output placement (both leaves)

QA/analysis outputs land under the canonical workflow-result package
`results/<workflow>/<slug>/<qa_step>/` (`<slug>` = `aNNN-description`;
project-root-relative), NOT `results/<analysis>/…`. Per
`data-management/conventions.md`, the lightweight manifest/config/report records
are tracked in-repo, while the bulk Parquet resources are payload governed by the
data-boundary policy (not committed here). Each step directory carries a
`datapackage` descriptor. Placement authority: `data-management/conventions.md`;
descriptor format: `data-management/frictionless.md` — both linked from the
leaves.

## Task decomposition (preview)

1. Create `mutational-signatures-qa.md` (measurement-qa, owns TMB) + INDEX entry
   (sibling ref backticked).
2. Create `driver-selection.md` (analysis-discipline) + INDEX entry, and convert
   the signatures leaf's sibling ref to a markdown link (both siblings now
   link-validated).
3. Atomic flip: retarget every reference (genomics router table/ordering/count
   prose, `somatic-mutation-qa.md` back-ref, `plan-analysis.md` rows 68/203,
   `data-management/SKILL.md`), `git rm` the old leaf, regenerate the codex
   mirror (`science-plan-analysis` changes).
4. Controller-run green gate: full pytest must exit zero, skills lint exit 0,
   codex zero-additional-delta, final whole-branch review, finish.

All four tasks are green (no RED window). Task boundaries are settled in the
implementation plan.
