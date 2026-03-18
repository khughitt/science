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

## When Adding a New Data Source

1. Document it using the framework `dataset.md` template (or a project override in `.ai/templates/`) — save to `doc/datasets/data-<source-name>.md`
2. Update `science.yaml` with the new data source entry
3. Add acquisition scripts to `code/scripts/`
4. Create or update `datapackage.json` in the appropriate directory

## While Tooling Is Still Maturing

Shared runtime and source clients may be incomplete in some projects.
When automation is unavailable:
- Manually document data sources using the template
- Download data by hand and place in `data/raw/`
- Write preprocessing scripts in `code/scripts/` with clear comments
- Always update `science.yaml` data_sources when adding new data
