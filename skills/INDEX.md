---
name: science-skill-index
description: Source of truth for finding Science methodology skills and the skill-authoring doctrine.
---

# Science Skill Index

Use this index before planning or running a data analysis, and when creating,
naming, or organizing a skill. Load only the leaves that match the current task.
Do not load every leaf "just in case"; that defeats progressive disclosure.

## Meta / Skill Authoring

- `skill-development`: `skills/meta/SKILL.md`
- `skill-taxonomy`: `skills/meta/skill-taxonomy.md`
- `skill-authoring`: `skills/meta/skill-authoring.md`

## Biological Data

- `bio`: `skills/bio/SKILL.md`
- `functional-genomics-qa`: `skills/bio/functional-genomics-qa.md`
- `genomics`: `skills/bio/genomics/SKILL.md`
- `genomics-somatic-mutation-qa`: `skills/bio/genomics/somatic-mutation-qa.md`
- `genomics-mutational-signatures-and-selection`: `skills/bio/genomics/mutational-signatures-and-selection.md`
- `genomics-mutational-signatures-qa`: `skills/bio/genomics/mutational-signatures-qa.md`
- `genomics-copy-number-sv-qa`: `skills/bio/genomics/copy-number-sv-qa.md`
- `transcriptomics`: `skills/bio/transcriptomics/SKILL.md`
- `transcriptomics-bulk-rnaseq-qa`: `skills/bio/transcriptomics/bulk-rnaseq-qa.md`
- `transcriptomics-cohort-qa`: `skills/bio/transcriptomics/cohort-qa.md`
- `transcriptomics-data-integration`: `skills/bio/transcriptomics/data-integration.md`
- `transcriptomics-microarray-qa`: `skills/bio/transcriptomics/microarray-qa.md`
- `transcriptomics-scrna-qa`: `skills/bio/transcriptomics/scrna-qa.md`
- `proteomics`: `skills/bio/proteomics/SKILL.md`
- `proteomics-qa`: `skills/bio/proteomics/proteomics-qa.md`
- `proteomics-protein-sequence-structure-qa`: `skills/bio/proteomics/protein-sequence-structure-qa.md`

## Machine Learning

- `ml`: `skills/ml/SKILL.md`
- `ml-embeddings-manifold-qa`: `skills/ml/embeddings-manifold-qa.md`

## Data Management

- `data-management`: `skills/data-management/SKILL.md`
- `data-management-acquisition`: `skills/data-management/acquisition.md`
- `data-management-conventions`: `skills/data-management/conventions.md`
- `data-management-frictionless`: `skills/data-management/frictionless.md`

## Statistics

- `statistics`: `skills/statistics/SKILL.md`
- `statistics-survival-and-hierarchical-models`: `skills/statistics/survival-and-hierarchical-models.md`
- `statistics-compositional-data`: `skills/statistics/compositional-data.md`
- `statistics-time-series-and-longitudinal-models`: `skills/statistics/time-series-and-longitudinal-models.md`
- `statistics-likelihood-model-comparison`: `skills/statistics/likelihood-model-comparison.md`
- `statistics-population-genetics-likelihood`: `skills/statistics/population-genetics-likelihood.md`
- `statistics-bayesian-workflow`: `skills/statistics/bayesian-workflow.md`

## Study Design & Inference Discipline

- `study-design`: `skills/study-design/SKILL.md`
- `study-design-prereg-amendment-vs-fresh`: `skills/study-design/prereg-amendment-vs-fresh.md`
- `study-design-prereg-defensive-instrumentation`: `skills/study-design/prereg-defensive-instrumentation.md`
- `study-design-replicate-count-justification`: `skills/study-design/replicate-count-justification.md`
- `study-design-power-floor-acknowledgement`: `skills/study-design/power-floor-acknowledgement.md`
- `study-design-estimator-certification`: `skills/study-design/estimator-certification.md`
- `study-design-sensitivity-arbitration`: `skills/study-design/sensitivity-arbitration.md`
- `study-design-causal-identification`: `skills/study-design/causal-identification.md`
- `study-design-bias-vs-variance-decomposition`: `skills/study-design/bias-vs-variance-decomposition.md`

## Epistemics

- `epistemics`: `skills/epistemics/SKILL.md`
- `epistemics-proposition-schema`: `skills/epistemics/proposition-schema.md`
- `epistemics-proposition-graph-reasoning`: `skills/epistemics/proposition-graph-reasoning.md`
- `epistemics-annotation-curation-qa`: `skills/epistemics/annotation-curation-qa.md`

## Literature

- `literature`: `skills/literature/SKILL.md`
- `literature-evaluation`: `skills/literature/literature-evaluation.md`
- `literature-citation-discipline`: `skills/literature/citation-discipline.md`
- `literature-source-openalex`: `skills/literature/sources/openalex.md`
- `literature-source-pubmed`: `skills/literature/sources/pubmed.md`

## Research Package

- `research-package`: `skills/research-package/SKILL.md`
- `research-package-spec`: `skills/research-package/research-package-spec.md`
- `research-package-rendering`: `skills/research-package/research-package-rendering.md`

## Execution / Orchestration

Load these only after methodology is clear or when execution planning is the
user's explicit request:

- `pipelines`: `skills/pipelines/SKILL.md`
- `pipeline-reproducibility`: `skills/pipelines/reproducibility.md`
- `pipeline-snakemake`: `skills/pipelines/snakemake.md`
- `pipeline-marimo`: `skills/pipelines/marimo.md`
- `pipeline-runpod`: `skills/pipelines/runpod.md`

## Writing

- `writing`: `skills/writing/SKILL.md`
- `scientific-writing`: `skills/writing/scientific-writing.md`

## Companion Skills

- [`bio/SKILL.md`](bio/SKILL.md) - load when a biological-assay dataset needs measurement QA.
- [`ml/SKILL.md`](ml/SKILL.md) - load when embedding/manifold/unsupervised-structure QA is in scope.
- [`data-management/SKILL.md`](data-management/SKILL.md) - load when data acquisition, preprocessing, or QA is in scope.
- [`statistics/SKILL.md`](statistics/SKILL.md) - load when designing, fitting, or comparing a finite-sample statistical model.
- [`study-design/SKILL.md`](study-design/SKILL.md) - load when rigor must be pre-committed or a numeric verdict certified/arbitrated.
- [`epistemics/SKILL.md`](epistemics/SKILL.md) - load when proposition/evidence schema or graph reasoning is in scope.
- [`literature/SKILL.md`](literature/SKILL.md) - load when evidence evaluation, curation, or literature sourcing is in scope.
- [`research-package/SKILL.md`](research-package/SKILL.md) - load when building or validating a research-package bundle.
- [`pipelines/SKILL.md`](pipelines/SKILL.md) - load only after methodology is clear and execution planning is needed.
- [`writing/SKILL.md`](writing/SKILL.md) - load when scientific prose for a research project is in scope.
