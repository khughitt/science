---
name: data-frictionless
description: Frictionless Data Package creation and validation. Use when creating datapackage.json descriptors, validating data files against schemas, or connecting datasets to analysis pipelines. Also use when the user mentions data packages, data validation, or data schemas.
---

# Frictionless Data Packages

## When To Use

- After downloading raw data to `data/raw/`
- Before connecting data to a pipeline or notebook
- When validating data quality and schema conformance
- When documenting dataset structure for reproducibility

## Core Concepts

A **Data Package** is a `datapackage.json` file describing one or more data **resources** (files) with their schemas, formats, and metadata.

A **resource** describes a single data file: its path, format, schema (field names, types, constraints), and encoding.

## Creating a Data Package

### Option A: Auto-describe from existing files

```bash
# Generate descriptor from a CSV file
frictionless describe data/raw/observations.csv --json > data/raw/datapackage.json
```

Review and edit the generated descriptor — auto-detection may mis-type fields.

### Option B: Write manually

```json
{
  "name": "project-raw-data",
  "title": "Raw Data for <Project>",
  "description": "Downloaded from <source> on <date>",
  "licenses": [{"name": "CC-BY-4.0", "path": "https://creativecommons.org/licenses/by/4.0/"}],
  "resources": [
    {
      "name": "observations",
      "path": "observations.csv",
      "format": "csv",
      "encoding": "utf-8",
      "schema": {
        "fields": [
          {"name": "sample_id", "type": "string", "constraints": {"required": true}},
          {"name": "gene", "type": "string"},
          {"name": "expression", "type": "number"},
          {"name": "condition", "type": "string", "constraints": {"enum": ["control", "treated"]}}
        ],
        "primaryKey": "sample_id"
      }
    }
  ]
}
```

## Field Types

Use these Frictionless types:

| Type | Python equivalent | Use for |
|---|---|---|
| `string` | `str` | text, identifiers, categories |
| `number` | `float` | measurements, continuous values |
| `integer` | `int` | counts, indices |
| `boolean` | `bool` | flags |
| `date` | `datetime.date` | dates without time |
| `datetime` | `datetime.datetime` | timestamps |
| `array` | `list` | JSON arrays |
| `object` | `dict` | JSON objects |

## Validation

```bash
# Validate a data package (built-in lightweight checks)
science-tool datasets validate --path data/raw/

# For deeper validation, install frictionless CLI separately: uv add frictionless
frictionless validate data/raw/datapackage.json
```

Common validation errors:
- **Missing values** in required fields — add `missingValues: ["", "NA", "N/A"]` to resource
- **Type errors** — check if auto-detected types are correct
- **Extra/missing columns** — update schema to match actual file

## Connecting to Inquiry Variables

When a `datapackage.json` exists and an inquiry is active:

1. Map resource fields to inquiry variables in `doc/datasets/data-<slug>.md`
2. Manually check which inquiry variables are covered by available dataset fields
3. Document any transformations needed (unit conversions, normalization, filtering)

## Directory Conventions

```
data/
├── raw/                    # Immutable downloads
│   ├── datapackage.json    # Describes raw files
│   ├── observations.csv
│   └── metadata.csv
├── processed/              # Cleaned, transformed
│   ├── datapackage.json    # Describes processed files
│   └── normalized.csv
└── README.md               # Overview
```

**Rules:**
- Never modify files in `data/raw/` after download
- All transformations go to `data/processed/`
- Both directories get their own `datapackage.json`
- Record provenance: which script/pipeline produced each processed file

## Provenance in Data Packages

Add a `sources` field to track where data came from:

```json
{
  "name": "processed-data",
  "sources": [
    {"title": "GEO GSE12345", "path": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE12345"},
    {"title": "Downloaded via science-tool", "path": "science-tool datasets download geo:GSE12345"}
  ],
  "resources": [...]
}
```
