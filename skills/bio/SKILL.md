---
name: bio
description: Use when a biological-assay dataset (genomics, transcriptomics, proteomics, functional-genomics) needs measurement QA. Routes to the assay subtree.
provenance: internal
---

# Biological Data Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when the data under analysis is a biological assay, before loading any leaf.

## Scope boundary

Covers assay-level measurement QA for genomics, transcriptomics, proteomics, and functional-genomics
data. Excludes general dimensionality-reduction QA (see `../ml/SKILL.md`) and dataset-directory
conventions (see `../data-management/SKILL.md`).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `genomics/SKILL.md` | somatic mutation, CN/SV, or signature/selection data | expression or protein data |
| `transcriptomics/SKILL.md` | bulk RNA-seq, microarray, or scRNA data | non-expression assays |
| `proteomics/SKILL.md` | mass-spec proteomics or protein sequence/structure data | nucleic-acid assays |
| `functional-genomics-qa.md` | CRISPR/RNAi screens, DepMap, perturbation data | descriptive (non-perturbation) assays |

## Decision / compose order

Route to exactly one assay sub-area; QA leaves within a sub-area may compose per that sub-router.

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring routers: `../ml/SKILL.md`, `../data-management/SKILL.md`, `../statistics/SKILL.md`

## Success test

A representative assay dataset routes to its correct sub-area (or loose leaf) with no methodology read
from this router.

## Companion Skills

- `../INDEX.md` — the skill index.
