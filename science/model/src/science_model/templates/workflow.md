---
id: "workflow:<slug>"
kind: "workflow"
title: "<Workflow Name>"
status: "active"
method: "<method-slug>"
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
| `step:<slug>` | `rule_name` | Brief description |

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

- **Method:** `method:<slug>`
- **Questions tested:** `question:<id>`, ...
- **Hypotheses tested:** `hypothesis:<id>`, ...
