---
name: science-data-management
description: "Router for data acquisition, preprocessing, on-disk layout, and QA. Load when working with datasets, downloading data, laying out data/results directories, or managing data provenance. Routes to the leaves below."
---

# Data Management — Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when acquiring, preprocessing, laying out, or QA'ing project
data or results, before loading any leaf.

## Scope boundary

Covers the on-disk conventions, descriptor format, and acquisition workflow for
project data and results; excludes modality-specific QA (routed to the bio/ml
leaves below) and the statistical modeling itself (the `science-statistics` skill).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `references/conventions.md` | laying out `data/`/`results/`, placing QA artifacts, or writing a result manifest | operating the `datapackage` format itself (→ `references/frictionless.md`) |
| `references/acquisition.md` | acquiring/registering a new data source or scripting reproducible preprocessing | the data is already registered and laid out |
| `references/frictionless.md` | writing or validating a `datapackage` descriptor | choosing where files go (→ `references/conventions.md`) |

## Specialized biological & source data

Route to the owning leaf before designing preprocessing or QA:

- Expression matrices, bulk RNA-seq, microarray, scRNA-seq → the `science-bio` skill.
- Somatic mutation tables, MAF/cBioPortal/TCGA/GENIE cohorts → the `science-bio` skill.
- Mutational signatures, TMB → the `science-bio` skill.
- dN/dS, dNdScv, driver selection → the `science-bio` skill.
- CRISPR/RNAi screens, DepMap, LINCS/L1000, drug response, perturbation assays → the `science-bio` skill.
- Proteomics, phosphoproteomics, mass spec, TMT/LFQ/DIA/DDA → the `science-bio` skill.
- Protein sequence/structure, homology-split datasets → the `science-bio` skill.
- Embeddings, UMAP/HDBSCAN/Mapper, CKA, manifolds → the `science-ml` skill.
- Literature sources → the `science-literature` skill, the `science-literature` skill.

## Decision / compose order

For a new dataset, `references/acquisition.md` is the driving workflow; within it, consult
`references/conventions.md` **before** placing files (to choose the logical layout) and
`references/frictionless.md` **at the descriptor step** (to write the `datapackage`).
`references/conventions.md` and `references/frictionless.md` are references the acquisition workflow
invokes, not phases that wholly precede or follow it. Load the relevant
specialized leaf for modality QA after the data is laid out.

## Parent & neighbors

- Parent index: the `science-command-preamble` skill's `references/methodology-index.md` (or run `science-plan-analysis`).
- Neighboring routers: the `science-pipelines` skill, the `science-statistics` skill, the `science-bio` skill, the `science-ml` skill.

## Success test

Representative in-scope tasks — acquire a dataset, place a QA artifact, write a
result manifest — route to the correct leaf (or compose order) without any
methodology being read from this router.

## Companion Skills

- the `science-command-preamble` skill's `references/methodology-index.md` — the skill index.
- [`references/conventions.md`](references/conventions.md) — data/result layout + descriptor contract.
- [`references/acquisition.md`](references/acquisition.md) — data acquisition + preprocessing workflow.
- [`references/frictionless.md`](references/frictionless.md) — `datapackage` descriptor format.
