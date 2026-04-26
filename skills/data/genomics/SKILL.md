---
name: data-genomics
description: Source of truth for genomic-mutation data ingestion and QA. Use when working with somatic mutation calls, mutational signatures, dN/dS, or driver-selection analyses.
---

# Genomics - Data Ingestion & QA

Practical guidance for ingesting and quality-assessing genomic-mutation data.
Public mutation deposits combine biological signal with assay-specific failure
modes (panel coverage, calling pipeline drift, reference-build mismatches,
cohort composition) that look plausible until they invalidate downstream
inference.

For analysis-readiness planning, start at [`../../INDEX.md`](../../INDEX.md) or
run `science-plan-analysis`.

## Two layers, two QA mindsets

| Layer | Leaf | Dominant failure modes |
|---|---|---|
| Mutation calls (input QA) | [`somatic-mutation-qa.md`](./somatic-mutation-qa.md) | callable territory, panel/exome mixing, NaN-vs-zero collapse, hypermutator dominance, sample-ID drift |
| Signatures and selection (analysis QA) | [`mutational-signatures-and-selection.md`](./mutational-signatures-and-selection.md) | opportunity-model omission, COSMIC version drift, length-confounded driver ranks, circular validation |

Always complete `somatic-mutation-qa.md` before treating signature or selection
results as verdict-bearing.

## Anticipated growth

Future leaves likely under this hub: copy-number QA, structural-variant QA,
fusion-transcript QA, methylation/EPIC-array QA. When adding a new leaf,
follow the frontmatter and companion-skills conventions established for
the existing two leaves.

## Companion Skills

- [`../SKILL.md`](../SKILL.md) — generic data-management conventions.
- [`../expression/SKILL.md`](../expression/SKILL.md) — expression cohorts often paired with mutation cohorts.
- [`../../statistics/power-floor-acknowledgement.md`](../../statistics/power-floor-acknowledgement.md) — mutation-frequency contrasts are typically low-power for rare genes.
- [`../../statistics/sensitivity-arbitration.md`](../../statistics/sensitivity-arbitration.md) — hypermutator-included vs -excluded analyses are the canonical sensitivity pair.
