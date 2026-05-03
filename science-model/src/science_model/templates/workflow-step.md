---
id: "step:<slug>"
type: "workflow-step"
title: "<Step Name>"
status: "planned"
workflow: "<workflow-slug>"
run: "<workflow-run-slug>"
inquiry: "<inquiry-slug>"
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
- **Run:** `workflow-run:<slug>` (if documenting a specific execution)
- **Inquiry:** `inquiry:<slug>`
- **Upstream:** `step:<slug>`
- **Downstream:** `step:<slug>`
