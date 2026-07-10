---
id: "workflow-step:<slug>"
kind: "workflow-step"
title: "<Step Name>"
status: "active"
workflow: "workflow:<slug>"
method: "method:<slug>"           # materializes the sci:applies edge
rule_name: "<snakemake-rule-name>"
seed_bindings:                    # a seed_param -> its SOURCE, never its value
  random_state: "config.seed"     #   config.<key> | literal:<int>
rationale: ""                     # why a nondeterministic method is acceptable here
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
| | | config.yaml / literal | |

## Validation

- [ ] Output file exists and is non-empty
- [ ] Domain-specific check
- [ ] Statistical check (if applicable)

## Runtime

- **Estimated time:** X minutes
- **Resources:** memory, CPU/GPU

## Related

- **Workflow:** `workflow:<slug>`
- **Method:** `method:<slug>`
- **Upstream:** `workflow-step:<slug>`
- **Downstream:** `workflow-step:<slug>`
