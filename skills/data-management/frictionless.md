---
name: data-management-frictionless
description: Use when authoring or validating a datapackage.json descriptor — its resources, schemas, field types, and validation. Defines the Frictionless descriptor format for files in data and result directories.
archetype: normative-reference
sources: [frictionless-spec, frictionless]
---

# Frictionless Data Package Contract

Answers: what must a `datapackage.json` descriptor mean or contain?

## Scope

The `datapackage.json` descriptor **format** for files in `data/raw/`,
`data/processed/`, or result-package directories: resources, schemas, field
types, and validation. Excludes the on-disk directory and result-package
**layout** (see [`conventions.md`](conventions.md)) and the data-acquisition
workflow (see [`acquisition.md`](acquisition.md)).

Load this after downloading raw data, before connecting data to a pipeline or
notebook, when validating schema conformance, or when documenting dataset
structure for reproducibility.

## Vocabulary / schema / enums

A **Data Package** is a `datapackage.json` file describing one or more data
**resources** (files) with their schemas, formats, and metadata. A **resource**
describes a single data file: its path, format, schema (field names, types,
constraints), and encoding.

Use these Frictionless field types:

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

## Invariants

- A `datapackage.json` is a **runtime/package descriptor** for files that exist
  on disk — it is **not** the durable `dataset:<slug>` entity lifecycle. For the
  entity lifecycle and data-root policy, see [`acquisition.md`](acquisition.md)
  and [`conventions.md`](conventions.md).
- Every `resource` describes a file that exists at its `path`.
- A resource `schema` matches the actual file's columns and types.
- Required fields declare their constraints; missing-value tokens are declared
  where the data uses them.

## Conformance rules

```bash
# Validate a runtime data package (built-in lightweight checks)
science datasets validate --path data/raw/

# For deeper validation, install the frictionless CLI separately: uv add frictionless
frictionless validate data/raw/datapackage.json
```

Common validation errors:

- **Missing values** in required fields — add `missingValues: ["", "NA", "N/A"]` to the resource.
- **Type errors** — check whether auto-detected types are correct.
- **Extra/missing columns** — update the schema to match the actual file.

When a `datapackage.json` exists and an inquiry is active, map resource fields to
inquiry variables in `entities/datasets/<slug>.md` and document any
transformations needed (unit conversions, normalization, filtering).

## Examples

**Option A — auto-describe from existing files:**

```bash
frictionless describe data/raw/observations.csv --json > data/raw/datapackage.json
```

Review and edit the generated descriptor — auto-detection may mis-type fields.

**Option B — write manually:**

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

**Provenance** — add a `sources` field to track where data came from:

```json
{
  "name": "processed-data",
  "sources": [
    {"title": "GEO GSE12345", "path": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE12345"},
    {"title": "Downloaded via science", "path": "science datasets download geo:GSE12345"}
  ],
  "resources": []
}
```

## Versioning / migration

The Frictionless Data Package specification governs the descriptor format; this
contract tracks the fields Science's `science datasets validate` checks.
Directory and result-package **layout** is versioned separately in
[`conventions.md`](conventions.md).

## Invalid cases

- A `datapackage.json` whose `resources` reference files that do not exist.
- A required field with unhandled missing values (no `missingValues`).
- A `schema` whose fields do not match the actual file's columns.
- Using a `datapackage.json` descriptor as if it were the durable
  `dataset:<slug>` entity (the two are distinct — see *Invariants*).

## Success test

Is there an explicit conformance check? `science datasets validate --path <dir>`
(built-in) or `frictionless validate <dir>/datapackage.json` (deeper) passes
against the described files.

## Companion Skills

- `../INDEX.md` — the skill index.
- [`conventions.md`](conventions.md) — the directory/result layout that these descriptors describe.
- [`acquisition.md`](acquisition.md) — the acquisition workflow that produces these descriptors.
- [`../research-package/research-package-spec.md`](../research-package/research-package-spec.md) - Frictionless descriptor conventions reused by research packages.
- [`../pipelines/snakemake.md`](../pipelines/snakemake.md) - workflow rules that generate package descriptors as terminal artifacts.
