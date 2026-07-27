---
name: transcriptomics-data-integration
description: Use when integrating or aggregating multiple heterogeneous transcriptomic cohorts for meta-analysis, before designing per-cohort preprocessing — committing to a cross-cohort strategy and handling experiment-level technical variation.
archetype: analysis-discipline
provenance: internal
---

# Transcriptomic Data Integration

Answers: regardless of the pooling method, what strategy and identifiability check must be committed before multiple transcriptomic cohorts may be integrated and interpreted?

## Triggering condition

Before designing per-cohort preprocessing for any analysis that pools ≥2
cohorts or platforms — microarray + RNA-seq, multiple GEO series, or bulk +
single-cell. The strategy choice cascades into preprocessing, so it must be
committed first, not reverse-engineered afterward.

## Required reasoning / check / precommitment

Before any per-cohort preprocessing, commit in writing:

- **(a) the aggregation strategy** — one of the three in the decision rule below.
- **(b) the identifiability check** — is the biological contrast fully aliased
  with cohort, platform, or batch? For the contrast of interest, list which
  cohorts/platforms contribute each level.
- **(c) the technical-artifact adjustment and its assumptions** — which of
  ComBat / RUV / SVA / mixed-effects / exclusion, and whether the data actually
  satisfy that method's prerequisites.

## Decision rule or reasoning criteria

**Aggregation strategies (not interchangeable):**

1. **Within-cohort association testing → aggregate test statistics.** Run
   DESeq2 / limma / logistic / Cox **per dataset/cohort** — cohorts sharing a
   platform still carry cohort-specific technical artifacts, so pool at the
   statistic level, not the sample level. Aggregate p-values (Stouffer's,
   Fisher's) or z-scored effects (random-effects metafor). Z-score per-cohort
   effects before pooling when scales differ — effect-size aggregation needs
   that scale harmonisation, whereas p-value pooling tolerates scale
   differences but not violated distributional assumptions.
2. **Common-reference normalisation** (gene-set rank, percentile, z-score)
   before pooling. Enables direct pooling but loses platform-specific magnitude.
3. **Hierarchical models with platform random effects.** The most principled;
   compute- and assumption-heavy. Often worth it for high-stakes confirmatory
   inference.

**Batch-adjustment branches (each with its prerequisite — the chosen strategy
dictates which is admissible):**

- **ComBat** — needs known batch labels; assumes batch is not confounded with
  biology.
- **RUV** — needs suitable negative-control genes or replicate samples.
- **SVA** — estimates latent factors; assumes they are separable from the
  biological contrast.
- **Mixed-effects** — platform/cohort as a random effect.
- **Exclusion** — drop the confounded cohort when no adjustment is admissible.

## Outcomes (pass / fail / indeterminate, or branch/threshold)

- **Strategy committed** → proceed to per-cohort preprocessing under it.
- **Non-identifiable** → halt (see below); no adjustment recovers an
  unconfounded effect.
- **Admissible but assumption-fragile** → proceed, reporting the limitation
  explicitly.

## Halt / escalation

- **Halt** when cohort/platform/batch is completely aliased with the biological
  contrast — the design is non-identifiable, and no ComBat/RUV/SVA adjustment
  can recover an unconfounded effect (adjustment removes the confound *and* the
  signal together).
- **Escalate** when the only admissible strategy rests on assumptions the data
  cannot support — no valid negative-control genes for RUV, no replicates, or
  latent factors not separable from the contrast.

## Required evidence & artifacts

- The committed aggregation strategy, recorded in the pre-registration before
  preprocessing.
- The identifiability assessment (which cohorts/platforms contribute each
  contrast level).
- The chosen adjustment method and its explicit assumption check.

## Permitted reporting language

- An effect pooled under a fragile-assumption or non-recoverable-confound path
  must be reported **with that limitation**, not as a clean cross-cohort effect.
- "Harmonised" describes a normalisation step; it is **not** a synonym for
  "confound-free." Do not imply the confound was removed unless the
  identifiability check supports it.

## Success test

Was the required reasoning/precommitment carried out before interpretation, and does the conclusion follow from it — mechanically where the identifiability gate applies, by the stated criteria otherwise?

## Companion Skills

- `router.md` — the transcriptomics router.
- `cohort-qa.md` — the per-cohort QA this decision consumes.
- `bulk-rnaseq-qa.md`, `microarray-qa.md`, `scrna-qa.md` — modality realizations of the chosen strategy.
- `science-statistics` skill — the actual aggregation / hierarchical modeling.
- `science-study-design` skill — pre-registering the committed strategy.
