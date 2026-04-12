---
id: "workflow:<slug>"
type: "workflow"
title: "<Workflow Name>"
status: "active"
method: "<method-slug>"
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
