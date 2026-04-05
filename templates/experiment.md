---
id: "experiment:<slug>"
type: "experiment"
title: "<Experiment Name>"
status: "planned"
tags: []
inquiry: "<inquiry-slug>"
hypothesis: "<hypothesis-id>"
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---

# <Experiment Name>

## Purpose

> **Note:** Use the `experiment` type for hypothesis-testing designs with explicit
> controls and expected outcomes. For computational workflow executions that produce
> durable result packages, use `workflow-run` instead.

## Hypothesis Context

<!--
What higher-level hypothesis or inquiry does this experiment bear on?
-->

## Proposition(s) Under Test

<!--
List the specific propositions this experiment is intended to update.
-->

## Evidence Type

<!--
Mark the expected evidence class:
- empirical-data
- simulation
- benchmark
- methodological
-->

## Design

- **Independent variable(s):** <what is being varied>
- **Dependent variable(s):** <what is being measured>
- **Controls:** <baseline comparisons>
- **Sample size:** <N>
- **Analysis method:** <test, model, or workflow>
- **Primary outputs:** <effect size, ranking, estimate, etc.>

## Pipeline Steps

1. <step-slug> — <brief description>
2. <step-slug> — <brief description>

## Expected Belief Update

<!--
What result would support the target claim?
What result would dispute it?
What result would remain ambiguous?
-->

## Actual Results

<!-- Fill in after running. Include effect sizes, uncertainty, and key diagnostics. -->

## Proposition Update

<!--
How should these results update the proposition(s) under test?
Use support/dispute/ambiguous language and note residual uncertainty.
-->

## Limitations

<!--
What keeps this from being decisive?
Examples: small sample size, model dependence, single dataset, weak controls.
-->

## Related

- Hypothesis: `specs/hypotheses/<hypothesis-id>.md`
- Inquiry: `doc/inquiries/<inquiry-slug>.md`
- Pipeline: `doc/plans/<pipeline-plan>.md`
- Data: `data/processed/<output>`
