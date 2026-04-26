---
name: data-management
description: Data acquisition, preprocessing, and management for Science research projects. This skill should be used when working with datasets, downloading data from repositories, creating Frictionless Data Packages, preprocessing raw data, or managing data provenance. Also use when the user mentions data sources, data cleaning, data formats, or datapackage.json.
---

# Data Management

> **Status:** Core data management guidance is active.
> Source-specific guidance is available in:
> - `skills/data/sources/openalex.md`
> - `skills/data/sources/pubmed.md`
>
> Modality-specific QA guidance is available in:
> - `skills/data/expression/SKILL.md` for transcriptomic data
> - `skills/data/genomics/somatic-mutation-qa.md` for MAF/cBioPortal/TCGA/GENIE mutation cohorts
> - `skills/data/genomics/mutational-signatures-and-selection.md` for SBS signatures, TMB, dN/dS, and driver-selection analyses
> - `skills/data/functional-genomics-qa.md` for CRISPR/RNAi screens, DepMap, LINCS/L1000, drug response, and perturbation assays
> - `skills/data/embeddings-manifold-qa.md` for embeddings, UMAP/HDBSCAN/Mapper, CKA, and manifold comparisons
> - `skills/data/protein-sequence-structure-qa.md` for protein sequence, structure, label, and homology-split datasets
>
> Additional source skills and automation tooling are still phased in over time.

## Principles

1. **Raw data is immutable.** Never modify files in `data/raw/`. All transformations produce new files in `data/processed/`.
2. **Frictionless Data Packages.** Every data directory should have a `datapackage.json` describing its contents, schemas, and provenance.
3. **Provenance tracking.** Document where data came from, when it was acquired, and what transformations were applied.
4. **Reproducible preprocessing.** All data transformations should be scripted (in `code/scripts/` or `code/workflows/`) and documented.

## Data Directory Convention

```
data/
├── raw/                    # Original, unmodified data
│   ├── datapackage.json    # Frictionless descriptor
│   └── ...
├── processed/              # Cleaned, transformed data
│   ├── datapackage.json    # Frictionless descriptor
│   └── ...
└── README.md               # Overview of all data in the project
```

## Result Packages

Analysis outputs follow the same Frictionless Data Package convention as input
data. Each workflow run produces a self-describing result package:

### Directory Convention

```
results/
├── {workflow-name}/
│   └── aNNN-{description}/
│       ├── datapackage.json      # Frictionless manifest + provenance
│       ├── config.yaml           # Frozen config snapshot
│       ├── sequences/            # FASTA outputs (when applicable)
│       ├── *.parquet             # Tabular results
│       ├── *.json                # Structured results
│       └── *.png                 # Visualizations
```

### Analysis Slugs

- Format: `aNNN-description` (e.g., `a001-protein-sp-tmr`)
- Global counter: monotonically increasing across the project
- Gaps allowed: number by workflow group for readability

### Manifest Schema

See the project spec for the full `datapackage.json` schema. Key custom blocks:

- `workflow` — which workflow produced this, git commit at run time
- `entities` — cross-references to questions, hypotheses, tasks
- `provenance` — step DAG, environment, timing

### Sequence Outputs

When a workflow processes or generates biological sequences, output them as
FASTA files in the `sequences/` subdirectory. Annotate with EDAM terms:

```json
{
  "edam": {
    "data": "http://edamontology.org/data_2044",
    "format": "http://edamontology.org/format_1929"
  }
}
```

## When Adding a New Data Source

1. Document it using the framework `dataset.md` template (or a project override in `.ai/templates/`) — save to `doc/datasets/data-<source-name>.md`
2. Update `science.yaml` with the new data source entry
3. Add acquisition scripts to `code/scripts/`
4. Create or update `datapackage.json` in the appropriate directory

## When Working With Specialized Biological Data

Load the relevant leaf before designing preprocessing or QA:

- Expression matrices, public h5ad deposits, bulk RNA-seq, microarray, or scRNA-seq:
  `skills/data/expression/SKILL.md`.
- Somatic mutation tables, targeted panels, callable denominators, or MAF harmonisation:
  `skills/data/genomics/somatic-mutation-qa.md`.
- Mutational signatures, TMB, replication-timing bias, or dN/dS / dNdScv:
  `skills/data/genomics/mutational-signatures-and-selection.md`.
- CRISPR/RNAi screens, DepMap dependencies, LINCS/L1000 signatures, drug
  response, or perturbation replication:
  `skills/data/functional-genomics-qa.md`.
- Protein embeddings, PLM manifolds, UMAP/HDBSCAN/Mapper, CKA, or Moran's I:
  `skills/data/embeddings-manifold-qa.md`.
- UniProt/Pfam/CATH/Foldseek/MMseqs/DeepLoc/Meltome workflows:
  `skills/data/protein-sequence-structure-qa.md`.

## While Tooling Is Still Maturing

Shared runtime and source clients may be incomplete in some projects.
When automation is unavailable:
- Manually document data sources using the template, including source URL or
  accession, retrieval date, license/access constraints, checksum, and exact
  files acquired
- Download data by hand and place in `data/raw/`
- Write preprocessing scripts in `code/scripts/` with clear comments
- Always update `science.yaml` data_sources when adding new data
