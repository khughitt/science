---
id: "interpretation:{{slug}}"
type: "interpretation"
title: "{{Short Title}}"
status: "active"
# aspects: ["hypothesis-testing"]  # optional override; omitted entities inherit project aspects
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
input: "{{path to results, notebook, or prose description}}"
workflow_run: "<workflow-run-slug>"  # optional: links to the run that produced the interpreted results
prior_interpretations: []  # optional: interpretation IDs this document extends or supersedes
---

# Interpretation: {{Short Title}}

## Verdict

<!--
One line. Lead with a polarity token, then a short clause.

Tokens (with respect to the predicted direction, NOT project valence):
  [+]  positive — supports the prediction / hypothesis arm under test
  [-]  negative — refutes or contradicts the prediction
  [~]  null / mixed / bimodal — no clear directional signal, or different
       directions in different sub-strata (multi-finding panel, per-context
       divergence, within-result bimodality)
  [⌀]  non-adjudicating terminal — the design *was* able to discriminate at
       the test layer but the rollup is deliberately closed without resolving
       polarity (e.g. `non_adjudicating_under_observational_adjusters`).
       Distinct from [?] (a design failure) and from [~] (which has structured
       directional content).
  [?]  inconclusive — protocol failure, data gap, or insufficient power to
       discriminate

Examples:
  **Verdict:** [+] Cooperrider strong-form supported (acquirer LEN+ rate >80%, p<0.01)
  **Verdict:** [-] Cooperrider strong-form refuted (rate 25% vs predicted ≥80%, p=0.47)
  **Verdict:** [~] Bimodal — 2/16 basins robust, 14/16 collapse under 50% perturbation
  **Verdict:** [⌀] Terminal `non_adjudicating_under_observational_adjusters`; observational route closed, handed to interventional evidence
  **Verdict:** [?] Inconclusive — pre-reg PPC failed across all student-t variants

The polarity is with respect to the *predicted* direction. A `[-]` verdict
that closes a long-open question is a positive epistemic event for the
project — do not read polarity as project valence.

Rationale: see `discussion:2026-04-19-verdict-polarity-display` (mm30) — plain-
text tokens are robust across renderers (GitHub, email, terminal), accessible
to colorblind readers, and grep-able for cross-doc verdict surveys.
-->

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

## Proposition-Level Updates

<!--
For each relevant proposition:
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
- propositions to investigate further
- tasks to add or reprioritize
- evidence gaps worth targeting
-->
