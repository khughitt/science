---
id: "interpretation:{{slug}}"
type: "interpretation"
mode: "dev"
title: "{{Short Title}}"
status: "active"
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
input: "{{path to tooling work, PR, workflow, or commit range}}"
workflow_run: "<workflow-run-slug>"  # optional: links to the run that exercised the tooling
prior_interpretations: []  # optional: interpretation IDs this document extends or supersedes
---

# Interpretation (dev mode): {{Short Title}}

<!--
This is the dev-mode template for interpret-results.

Use it when the interpreted "result" is about tooling, infrastructure, workflow,
or methodology rather than substantive empirical evidence.

If the work generated empirical findings (effect sizes, sample-level results,
proposition-level support / dispute), use templates/interpretation.md instead.

The empirical sections (Evidence Quality, Data Quality Checks,
Proposition-Level Updates, Evidence vs. Open Questions) are intentionally
omitted from this template — they create dead weight for infrastructure work
and tempt confabulated empirical framing.
-->

## Mode

`dev` — interpreting tooling / workflow / methodology output, not empirical results.

## Infrastructure Outcomes

<!--
What was built, fixed, or changed?
- new capability or contract
- behavior change in an existing system
- removed or deprecated surface
- performance / reliability shift, with before / after if measured

Be concrete: link to commits, PRs, files, or workflow slugs. Avoid framing
infrastructure work as if it were a study.
-->

## Methodological Findings

<!--
What did the work surface about *how* the project does science?
- analysis steps that were unreliable, slow, or ambiguous
- assumptions that did not hold once the tooling exposed them
- conventions that need to change (naming, layout, schema, contract)
- comparisons between alternative approaches with a recommendation
-->

## Reusable Lessons

<!--
What should the next person doing similar work know?
- patterns that worked and should be defaulted to
- traps and the smallest reproduction that surfaces them
- design decisions and the alternatives that were considered and rejected
- non-obvious constraints to respect (rate limits, data formats, env quirks)

These should read as durable guidance, not a chronological log.
-->

## Downstream Tasks Unblocked

<!--
What work can now proceed because of this?
- list each unblocked task or analysis with a one-line "now possible because"
- if a task was previously blocked in tasks/, link it
- if no tasks were unblocked, say so explicitly — the work may still be
  worthwhile but pretending it unblocked something is the wrong story
-->

## Follow-up Risks and Open Loops

<!--
What is left unfinished, fragile, or untested?
- partial implementations that need a follow-up
- assumptions baked in that may need to be revisited
- areas the dev work intentionally did not touch but probably should
- monitoring / telemetry that should be added but was not
-->

## User Questions

<!-- Questions the user raised during the work, with answers.
Often the most insightful prompts. Omit if no user questions were raised. -->

## Updated Priorities

<!--
- new tasks to add
- tasks to deprioritize because the dev work superseded them
- conventions to roll out across the project
- documentation that should be updated to reflect the new state
-->
