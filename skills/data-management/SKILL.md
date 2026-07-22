---
name: data-management
description: Router for data acquisition, preprocessing, on-disk layout, and QA. Load when working with datasets, downloading data, laying out data/results directories, or managing data provenance. Routes to the leaves below.
provenance: internal
---

# Data Management — Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when acquiring, preprocessing, laying out, or QA'ing project
data or results, before loading any leaf.

## Scope boundary

Covers the on-disk conventions, descriptor format, and acquisition workflow for
project data and results; excludes modality-specific QA (routed to the bio/ml
leaves below) and the statistical modeling itself (`../statistics/SKILL.md`).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `conventions.md` | laying out `data/`/`results/`, placing QA artifacts, or writing a result manifest | operating the `datapackage` format itself (→ `frictionless.md`) |
| `acquisition.md` | acquiring/registering a new data source or scripting reproducible preprocessing | the data is already registered and laid out |
| `frictionless.md` | writing or validating a `datapackage` descriptor | choosing where files go (→ `conventions.md`) |

## Specialized biological & source data

Route to the owning leaf before designing preprocessing or QA:

- Expression matrices, bulk RNA-seq, microarray, scRNA-seq → `../bio/transcriptomics/SKILL.md`.
- Somatic mutation tables, MAF/cBioPortal/TCGA/GENIE cohorts → `../bio/genomics/somatic-mutation-qa.md`.
- Mutational signatures, TMB, dN/dS, driver selection → `../bio/genomics/mutational-signatures-and-selection.md`.
- CRISPR/RNAi screens, DepMap, LINCS/L1000, drug response, perturbation assays → `../bio/functional-genomics-qa.md`.
- Proteomics, phosphoproteomics, mass spec, TMT/LFQ/DIA/DDA → `../bio/proteomics/proteomics-qa.md`.
- Protein sequence/structure, homology-split datasets → `../bio/proteomics/protein-sequence-structure-qa.md`.
- Embeddings, UMAP/HDBSCAN/Mapper, CKA, manifolds → `../ml/embeddings-manifold-qa.md`.
- Literature sources → `../literature/sources/openalex.md`, `../literature/sources/pubmed.md`.

## Decision / compose order

For a new dataset, `acquisition.md` is the driving workflow; within it, consult
`conventions.md` **before** placing files (to choose the logical layout) and
`frictionless.md` **at the descriptor step** (to write the `datapackage`).
`conventions.md` and `frictionless.md` are references the acquisition workflow
invokes, not phases that wholly precede or follow it. Load the relevant
specialized leaf for modality QA after the data is laid out.

## Parent & neighbors

- Parent index: `../INDEX.md` (or run `science-plan-analysis`).
- Neighboring routers: `../pipelines/SKILL.md`, `../statistics/SKILL.md`, `../bio/SKILL.md`, `../ml/SKILL.md`.

## Success test

Representative in-scope tasks — acquire a dataset, place a QA artifact, write a
result manifest — route to the correct leaf (or compose order) without any
methodology being read from this router.

## Companion Skills

- `../INDEX.md` — the skill index.
- [`conventions.md`](conventions.md) — data/result layout + descriptor contract.
- [`acquisition.md`](acquisition.md) — data acquisition + preprocessing workflow.
- [`frictionless.md`](frictionless.md) — `datapackage` descriptor format.
