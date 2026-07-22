---
name: data-management-conventions
description: Use when laying out a project's data and workflow-result directories, placing QA artifacts, or writing a result-package manifest. Defines the on-disk layout and descriptor contract for research data and results.
archetype: normative-reference
sources: [edam]
---

# Data & Result Storage Conventions

Answers: what must a project's data and result directories contain, and where must artifacts live?

## Scope

The on-disk layout and descriptor conventions for a project's research **data**
(`data/raw`, `data/processed`) and **workflow-result** directories
(`results/<workflow>/<slug>/`), including where QA artifacts live. Excludes the
`datapackage` descriptor *format* (see [`frictionless.md`](frictionless.md)), the
acquisition workflow (see `acquisition.md`), and **research packages** — a
distinct artifact governed by
[`../research-package/research-package-spec.md`](../research-package/research-package-spec.md)
(see *Invariants* → package artifacts).

**Logical vs. physical paths, and split storage.** Only the bulk **`data/…`**
paths are *logical* paths relative to the **resolved project data root**: logical
`data/raw` is physically `<resolved-root>/raw`, where the root resolves by the
precedence `SCIENCE_DATA_ROOT` → `science.yaml` `data.root` → global
`~/.config/science/config.yaml` `data.root` + project id → `./data`, and bulk
data stays **out of git**. **`results/…` is different: it is project-root-relative
and version-controlled** (lightweight provenance in-repo vs out-of-tree bulk).

## Vocabulary / schema / enums

**Data directories** (logical, under the resolved data root):

- `data/raw/` — original, unmodified downloads.
- `data/processed/` — cleaned, transformed files produced by scripted steps.

**Two distinct package artifacts — kept separate:**

1. **Workflow-result packages** — `results/<workflow>/<slug>/` (project-root-
   relative, version-controlled), where `<slug>` follows the `aNNN-description`
   analysis-slug grammar: a monotonically increasing global counter, gaps
   allowed (number by workflow group for readability). The manifest is a
   Frictionless descriptor `datapackage.yaml` (or `.json`) enumerating
   `resources`, alongside a `config.yaml` snapshot; `science qa-audit` reads it
   (authority: `templates/workflow-run.md` defines the manifest path; `qa-audit`
   consumes `resources` and accepts YAML or JSON). The workflow↔result and
   entity cross-references live on the **`workflow-run` entity** (`workflow`,
   `inputs`, `produces`, entity xrefs in `templates/workflow-run.md`), not as
   manifest custom blocks.
2. **Research packages** — a **separate** artifact at `research/packages/{name}/`
   with `datapackage.json` profile `science-research-package` and a nested
   `research` extension. Authority:
   [`../research-package/research-package-spec.md`](../research-package/research-package-spec.md).
   This contract references that artifact; it does not define it.

**QA-artifact output paths** (split by lifecycle):

- **Input QA** — per-cohort/per-dataset preprocessing checks that travel with the
  dataset: `data/processed/<cohort_id>/<qa_step>/` (e.g. `cohort_audit.json`,
  per-sample QC tables, probe-to-gene mappings).
- **Analysis QA** — per-analysis post-hoc checks tied to a specific result:
  `results/<workflow>/<slug>/<qa_step>/` (e.g. bias audits, reconstruction-error
  reports, model diagnostics).

The two locations mirror each other: input QA lives next to the data it audits;
analysis QA lives next to the result it diagnoses. A step that applies to both
lives wherever it runs; document the choice in the leaf that defines it.

**Sequence outputs.** FASTA outputs go in a `sequences/` subdirectory of the
result package, annotated with EDAM terms.

## Invariants

- **Raw data is immutable.** Never modify files under the resolved `raw/`; every
  transformation produces new files under `data/processed/`.
- **Every data directory carries a data-package descriptor** (`datapackage.json`
  for `data/raw` and `data/processed`).
- **Every QA output directory carries a descriptor** (see
  [`frictionless.md`](frictionless.md)); leaves reference this convention rather
  than redefining it.
- **Provenance is recorded** — every processed file documents which
  script/pipeline produced it, from what inputs.
- **Results are version-controlled and never under the data root**; bulk data
  under the resolved data root is never committed.

## Conformance rules

- `science datasets validate` validates the resolved project data root; use
  `science datasets validate --path data/raw/` to check an explicit in-repo path.
- `science qa-audit` reads the workflow-result manifest (`resources`, YAML or
  JSON).
- Each data / result / QA directory carries its descriptor.
- Respect `SCIENCE_DATA_ROOT` and `science.yaml` `data.root`; never commit files
  under the resolved data root.

## Examples

A logical `data/` tree (physically under `<resolved-root>/`, out of git):

```
data/
├── raw/                    # immutable downloads
│   ├── datapackage.json    # Frictionless descriptor
│   └── ...
├── processed/              # cleaned, transformed
│   ├── datapackage.json
│   └── ...
└── README.md
```

A workflow-result package. The **records** are version-controlled and in-repo;
the **bulk resources** are payload governed by the data-boundary policy (not
committed here):

```
results/
└── {workflow-name}/
    └── aNNN-{description}/
        ├── datapackage.yaml     # Frictionless manifest (resources), read by qa-audit — tracked
        ├── config.yaml          # frozen config snapshot — tracked
        └── <small reports>      # lightweight JSON/text/figure records — tracked
```

Bulk result resources (`.parquet`, `.npy`, large binaries) are **payload**:
`science data audit` flags tracked payload outside a data root as
`leaked_payload`. They live under the resolved data root (or are git-ignored),
not committed in `results/`; the manifest's `resources` point at them.

EDAM annotation for a FASTA sequence resource:

```json
{
  "edam": {
    "data": "http://edamontology.org/data_2044",
    "format": "http://edamontology.org/format_1929"
  }
}
```

## Versioning / migration

The workflow-result manifest's authority is `templates/workflow-run.md` (the
manifest path) and `science qa-audit` (which consumes `resources`); the
research-package schema's authority is
[`../research-package/research-package-spec.md`](../research-package/research-package-spec.md).
This contract references them rather than restating their schemas.

## Invalid cases

- Modifying a file under the resolved `raw/` after download.
- A data, result, or QA directory with no descriptor.
- An analysis result written outside `results/<workflow>/<slug>/`.
- **Conflating a workflow-result package with a research package** — wrong path
  (`results/…` vs `research/packages/…`), profile, or descriptor form.
- Committing files under the resolved data root, or treating `results/` as
  relative to the resolved data root.

## Success test

Is there an explicit conformance check against the vocabulary and invariants —
mechanical via `science datasets validate` / `science qa-audit` where
applicable, an itemized checklist otherwise?

## Companion Skills

- `../INDEX.md` — the skill index.
- [`../research-package/research-package-spec.md`](../research-package/research-package-spec.md) — the separate research-package artifact this contract bounds against.
- [`SKILL.md`](SKILL.md) — the data-management router.
- [`frictionless.md`](frictionless.md) — the `datapackage` descriptor format that realizes these directory conventions.
- `./acquisition.md` — the acquisition workflow that produces data in this layout.
