---
name: genomics
description: Source of truth for genomic-mutation data ingestion and QA. Use when working with somatic mutation calls, mutational signatures, dN/dS, or driver-selection analyses.
provenance: internal
---

# Genomics - Data Ingestion & QA

Practical guidance for ingesting and quality-assessing genomic-mutation data.
Public mutation deposits combine biological signal with assay-specific failure
modes (panel coverage, calling pipeline drift, reference-build mismatches,
cohort composition) that look plausible until they invalidate downstream
inference.

For analysis-readiness planning, start at Load the `science-command-preamble` skill and consult its `references/methodology-index.md` or
run `science-plan-analysis`.

## Layers and QA mindsets

| Layer | Leaf | Dominant failure modes |
|---|---|---|
| Mutation calls (input QA) | [`somatic-mutation-qa.md`](somatic-mutation-qa.md) | callable territory, panel/exome mixing, NaN-vs-zero collapse, hypermutator dominance, sample-ID drift |
| Signatures and burden (analysis QA) | [`mutational-signatures-qa.md`](mutational-signatures-qa.md) | opportunity-model omission, COSMIC version drift, low-count / panel-biased spectra, TMB denominator errors |
| Selection (interpretation gate) | [`driver-selection.md`](driver-selection.md) | length / expression / replication-confounded driver ranks, raw-frequency selection tests, circular validation |
| CN / SV / amplicon calls (input + derived QA) | [`copy-number-sv-qa.md`](copy-number-sv-qa.md) | ploidy/purity conditioning, AA/AC version drift, FFPE fragmentation, per-cell binning, AA→AC non-independence |

Always complete `somatic-mutation-qa.md` before treating signature or selection
results as verdict-bearing. Both downstream leaves require an explicit
mutation-opportunity model, realized differently per analysis — signature spectra
in trinucleotide context, tumor mutational burden as eligible mutations per
callable (interrogated) megabase, selection scores in coding length, sequence
context, and local mutation rate; counts without the appropriate opportunity
model are descriptive only.

## Anticipated growth

Future leaves likely under this hub: fusion-transcript QA,
methylation/EPIC-array QA. When adding a new leaf,
follow the frontmatter and companion-skills conventions established for
the existing leaves.

## Companion Skills

- Load the `science-data-management` skill — generic data-management conventions.
- [`../transcriptomics/SKILL.md`](../transcriptomics/SKILL.md) — expression cohorts often paired with mutation cohorts.
- Load the `science-study-design` skill — mutation-frequency contrasts are typically low-power for rare genes.
- Load the `science-study-design` skill — hypermutator-included vs -excluded analyses are the canonical sensitivity pair.
