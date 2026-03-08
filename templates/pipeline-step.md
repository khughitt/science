---
id: "step:<slug>"
type: "pipeline-step"
title: "<Step Name>"
status: "planned"
tags: []
inquiry: "<inquiry-slug>"
rule_name: "<snakemake-rule-name>"
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---

# <Step Name>

## Purpose

<What this step does and why it exists in the pipeline.>

## Input / Output

- **Input:** `<path/to/input>`
- **Output:** `<path/to/output>`
- **Format:** <input format> → <output format>

## Tool / Library

- <tool name and version>
- <relevant function or command>

## Parameters

| Parameter | Value | Source | Notes |
|---|---|---|---|
| <param> | <value> | inquiry AnnotatedParam / config.yaml | <why this value> |

## Validation

- [ ] Output file exists and is non-empty
- [ ] <domain-specific check>
- [ ] <statistical check if applicable>

## Runtime

- Estimated time: <estimate>
- Resource needs: <memory, CPU, GPU>

## Related

- Inquiry: `<inquiry-slug>`
- Upstream step: `<step-slug>`
- Downstream step: `<step-slug>`
