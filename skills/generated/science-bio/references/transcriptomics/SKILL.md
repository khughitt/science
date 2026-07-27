---
name: transcriptomics
description: Use when ingesting, QA-reviewing, or integrating transcriptomic datasets — bulk RNA-seq, microarray, or scRNA-seq cohorts (GEO, ArrayExpress, MMRF, HCA, recount, ARCHS4), especially before meta-analysis. Routes to the leaves below.
provenance: internal
---

# Transcriptomics — Expression-Data Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when a transcriptomic dataset is being ingested, QA'd, or
integrated for meta-analysis — before loading any leaf.

## Scope boundary

Covers expression-cohort ingest QA and multi-cohort integration across bulk
RNA-seq, microarray, and scRNA-seq. Excludes the statistical modeling itself
(→ the `science-statistics` skill) and generic data conventions
(→ the `science-data-management` skill).

## Leaves

| Leaf | Load when |
|---|---|
| `cohort-qa.md` | QA'ing any newly-acquired transcriptomic cohort (cross-modality checklist + inspection idioms) |
| `data-integration.md` | integrating/aggregating multiple cohorts for meta-analysis (strategy choice + batch adjustment) |
| `bulk-rnaseq-qa.md` | bulk RNA-seq cohort specifics |
| `microarray-qa.md` | microarray cohort specifics |
| `scrna-qa.md` | single-cell RNA-seq cohort specifics |

## Decision / compose order

- **Single-cohort work** → load `cohort-qa.md` **plus** the applicable modality
  leaf (`bulk-rnaseq-qa.md` / `microarray-qa.md` / `scrna-qa.md`).
- **Multi-cohort / meta-analysis work** → **additionally** load
  `data-integration.md`, and consult it **before** per-cohort preprocessing
  decisions are made — its strategy choice cascades into preprocessing.

## Parent & neighbors

- Parent index: the `science-command-preamble` skill's `references/methodology-index.md`
- Parent router: `../../SKILL.md`
- Neighboring routers: `../genomics/SKILL.md`, `../proteomics/SKILL.md`

## Success test

A representative transcriptomic task routes to the correct leaf (or the correct
compose order when leaves combine) with no methodology read from this router.

## Companion Skills

- the `science-statistics` skill — statistical modeling that consumes QA'd cohorts.
- the `science-data-management` skill — generic data conventions.
- the `science-data-management` skill — Data-Package substrate for the cohort_audit sidecar.
- `../genomics/SKILL.md` — mutation cohorts often paired with expression cohorts.
- the `science-literature` skill — field-consensus context for QA thresholds.
