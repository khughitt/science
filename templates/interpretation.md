---
id: "interpretation:{{slug}}"
type: "interpretation"
title: "{{Short Title}}"
status: "active"
tags: []
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
input: "{{path to results, notebook, or prose description}}"
workflow_run: "<workflow-run-slug>"  # optional: links to the run that produced the interpreted results
prior_interpretations: []  # optional: interpretation IDs this document extends or supersedes
---

# Interpretation: {{Short Title}}

## Findings Summary

<!--
Summarize the main results.
For each finding, note signal strength and evidence type.
-->

## Evidence Quality

<!--
Before updating beliefs, record:
- data quality or QA concerns
- sample size and power concerns
- confirmatory vs exploratory status
- dependence or independence relative to prior evidence
-->

## Data Quality Checks

<!-- Any data quality concerns discovered during interpretation?
- Control uniqueness: are controls distinct from test samples?
- Sample counts: do they match the experimental design?
- Dimensionality: do embedding sizes / feature counts match expectations?
- Unexpected duplicates or anomalies?

If no issues found, note "No data quality concerns identified."
Flag any issues as findings with signal strength "methodological". -->

## Claim-Level Updates

<!--
For each relevant claim or relation-claim:
- what supports it?
- what disputes it?
- what remains unresolved?

This is the core epistemic section.
-->

## Hypothesis-Level Implications

<!-- How do the claim-level updates affect the broader hypothesis?
Avoid direct "proved/refuted" language unless the case is genuinely overwhelming.

If the project uses open questions rather than formal hypotheses,
rename this section to "Question-Level Implications" and evaluate
against questions in doc/questions/ instead. -->

## Evidence vs. Open Questions

<!--
Which open questions were addressed, partially addressed, or left unchanged?
-->

## New Questions Raised

<!--
For each new question:
- priority
- type
- suggested next evidence
-->

## User Questions

<!-- Questions the user raised during interpretation, with answers.
These are often the most insightful prompts — record them as part of the
interpretation rather than losing them to conversation history.
Omit if no user questions were raised. -->

## Limitations & Residual Uncertainty

<!--
What prevents these results from being decisive?
What remains fragile, contested, or underdetermined?
-->

## Updated Priorities

<!--
Given these findings, what should happen next?
- claims to investigate further
- tasks to add or reprioritize
- evidence gaps worth targeting
-->
