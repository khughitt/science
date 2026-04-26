---
name: science-skill-index
description: Source of truth for finding Science methodology skills during analysis-readiness planning.
---

# Science Skill Index

Use this index before planning or running a data analysis. Load only the leaves
that match the current task. Do not load every leaf "just in case"; that defeats
progressive disclosure.

## Core Analysis Checks

- `data-management`: `skills/data/SKILL.md`
- `statistics`: `skills/statistics/SKILL.md`
- `research-methodology`: `skills/research/SKILL.md`
- `scientific-writing`: `skills/writing/SKILL.md`

## Data Modalities

- `data-expression`: `skills/data/expression/SKILL.md`
- `data-expression-bulk-rnaseq-qa`: `skills/data/expression/bulk-rnaseq-qa.md`
- `data-expression-microarray-qa`: `skills/data/expression/microarray-qa.md`
- `data-expression-scrna-qa`: `skills/data/expression/scrna-qa.md`
- `data-genomics`: `skills/data/genomics/SKILL.md`
- `data-genomics-somatic-mutation-qa`: `skills/data/genomics/somatic-mutation-qa.md`
- `data-genomics-mutational-signatures-and-selection`: `skills/data/genomics/mutational-signatures-and-selection.md`
- `data-functional-genomics-qa`: `skills/data/functional-genomics-qa.md`
- `data-protein-sequence-structure-qa`: `skills/data/protein-sequence-structure-qa.md`
- `data-embeddings-manifold-qa`: `skills/data/embeddings-manifold-qa.md`

## Data Sources and Provenance

- `data-frictionless`: `skills/data/frictionless.md`
- `data-source-openalex`: `skills/data/sources/openalex.md`
- `data-source-pubmed`: `skills/data/sources/pubmed.md`
- `research-package-spec`: `skills/research/research-package-spec.md`
- `research-package-rendering`: `skills/research/research-package-rendering.md`
- `research-proposition-schema`: `skills/research/proposition-schema.md`

## Statistics

- `statistics-replicate-count-justification`: `skills/statistics/replicate-count-justification.md`
- `statistics-bias-vs-variance-decomposition`: `skills/statistics/bias-vs-variance-decomposition.md`
- `statistics-power-floor-acknowledgement`: `skills/statistics/power-floor-acknowledgement.md`
- `statistics-sensitivity-arbitration`: `skills/statistics/sensitivity-arbitration.md`
- `statistics-survival-and-hierarchical-models`: `skills/statistics/survival-and-hierarchical-models.md`
- `statistics-compositional-data`: `skills/statistics/compositional-data.md`
- `statistics-prereg-amendment-vs-fresh`: `skills/statistics/prereg-amendment-vs-fresh.md`

## Curation and Evidence

- `research-annotation-curation-qa`: `skills/research/annotation-curation-qa.md`

## Execution / Orchestration

Load these only after methodology is clear or when execution planning is the
user's explicit request:

- `pipelines`: `skills/pipelines/SKILL.md`
- `pipeline-snakemake`: `skills/pipelines/snakemake.md`
- `pipeline-marimo`: `skills/pipelines/marimo.md`
- `pipeline-runpod`: `skills/pipelines/runpod.md`

## Companion Skills

- [`data/SKILL.md`](data/SKILL.md) - load when data acquisition, preprocessing, or QA is in scope.
- [`statistics/SKILL.md`](statistics/SKILL.md) - load when finite-sample quantitative interpretation is in scope.
- [`research/SKILL.md`](research/SKILL.md) - load when evidence evaluation, curation, or proposition schema is in scope.
- [`pipelines/SKILL.md`](pipelines/SKILL.md) - load only after methodology is clear and execution planning is needed.
