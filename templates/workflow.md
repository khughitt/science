---
id: "workflow:<slug>"
kind: "workflow"
title: "<Workflow Name>"
status: "active"
# Logical outputs declared by this workflow. Used by `science dataset register-run`
# to emit one derived `dataset:<slug>` entity per output, plus a per-output runtime
# datapackage.yaml at results/<wf>/<run>/<output-slug>/datapackage.yaml.
outputs: []
# Each entry:
#   - slug: "<output-slug>"
#     title: "<Output title>"
#     resource_names: ["<frictionless-resource-name>", ...]
#     ontology_terms: []
#     identity:
#       taxon: inherit
#       assembly: inherit
#       molecular_ids:
#         gene: inherit
#     support:
#       unit: dataset
#       min: 3
#       expected: 5
# Identity declarations can use:
#   - bare pass-through inheritance: taxon/assembly/tier: inherit
#   - explicit source inheritance:
#       taxon:
#         inherit:
#           from: "dataset:<input-slug>"
#   - literal identity fields compatible with dataset identity_context
#   - tier transforms:
#       molecular_ids:
#         gene:
#           namespace: "hgnc_symbol"
#           transform:
#             type: "symbol_remap"
#             from: "input"
#             dataset: "dataset:<gene-crosswalk>"
#   - assembly transforms:
#       assembly:
#         label: "GRCh38"
#         transform:
#           type: "liftover"
#           from: "input"
#           method: "ucsc_chain"
#           dataset: "dataset:<liftover-chain>"
#   - structured unresolved proxies:
#       assembly:
#         label: "mixed-build-cytoband-proxy"
#         seqcol_digest: "UNKNOWN"
#         registry: "dataset:assembly-registry"
#         resolution_status: "declared_unresolved"
#         proxy:
#           type: "cytoband_proxy"
#           via: "dataset:<cytoband-reference>"
#           sources:
#             - dataset: "dataset:<source-a>"
#               assembly: inherit
# Support declarations are opt-in. Use them for run-aggregate resources that
# must be backed by at least `min` distinct datasets, cohorts, samples, or sources.
# `expected` is optional and records a soft target at or above `min`.
# Producers stamp each aggregate resource with science.support: {unit, observed}.
# `science dataset register-run` reduces support across resources by taking
# the minimum observed value. `science validate` ERRORs below `min`.
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---

## Purpose

What this workflow does and what research questions it addresses.

## Location

- **Snakefile:** `code/workflows/<name>/Snakefile`
- **Config:** `code/workflows/<name>/config/config.yaml`
- **Rules:** `code/workflows/<name>/rules/`

## Steps

| Step | Rule | Purpose |
|------|------|---------|
| `workflow-step:<slug>` | `rule_name` | Brief description |

## Inputs

- **Data sources:** what external data is required
- **Dependencies:** other workflows that must run first

## Outputs

- **Result directory:** `results/<workflow-name>/aNNN-slug/`
- **Key artifacts:** list primary output types (Parquet, FASTA, JSON, PNG)

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| | | |

## Related

- **Questions tested:** `question:<id>`, ...
- **Hypotheses tested:** `hypothesis:<id>`, ...
