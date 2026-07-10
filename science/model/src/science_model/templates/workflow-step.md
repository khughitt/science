---
id: "workflow-step:<slug>"
kind: "workflow-step"
title: "<Step Name>"
status: "active"
workflow: "workflow:<slug>"
inquiry: "inquiry:<slug>"
rule_name: "<snakemake-rule-name>"
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---

## Purpose

What the step does and why it exists.

## Input / Output

- **Input:** `path/to/input` (format)
- **Output:** `path/to/output` (format)

## Tool / Library

- **Tool:** name, version
- **Function/command:** relevant call

## Parameters

| Parameter | Value | Source | Notes |
|-----------|-------|--------|-------|
| | | inquiry AnnotatedParam / config.yaml | |

## Validation

- [ ] Output file exists and is non-empty
- [ ] Domain-specific check
- [ ] Statistical check (if applicable)

## Runtime

- **Estimated time:** X minutes
- **Resources:** memory, CPU/GPU

## Related

- **Workflow:** `workflow:<slug>`
- **Inquiry:** `inquiry:<slug>`
- **Upstream:** `workflow-step:<slug>`
- **Downstream:** `workflow-step:<slug>`
