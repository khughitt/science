---
id: "pre-registration:{{nn}}-{{slug}}"
type: "pre-registration"
title: "{{title}}"
status: "committed"
committed: "{{YYYY-MM-DD}}"
spec: ""  # optional path to design/spec doc, e.g. entities/design/<NNNN>-<slug>-design.md
related: []  # hypothesis IDs, inquiry slugs, or task IDs this pre-reg covers
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
_template:
  frontmatter:
    id: { from: entity_id }
    type: { default: "pre-registration" }
    title: { from: title }
    status: { from: status }
    committed: { from: created }
    spec: { default: "" }
    related: { from: related }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: hypotheses-under-test, name: "Hypotheses Under Test", required: true }
    - { key: expected-outcomes, name: "Expected Outcomes", required: true }
    - { key: decision-criteria, name: "Decision Criteria", required: true }
    - { key: null-result-plan, name: "Null Result Plan", required: true }
    - { key: suspicious-unexpected-result-plan, name: "Suspicious/Unexpected Result Plan", required: true }
    - { key: known-limitations, name: "Known Limitations", required: true }
    - { key: metric-selection-rationale, name: "Metric Selection Rationale", required: true }
    - { key: exploratory-vs-confirmatory, name: "Exploratory vs. Confirmatory", required: true }
    - { key: total-comparison-count, name: "Total Comparison Count", required: true }
    - { key: execution-readiness-gate, name: "Execution-Readiness Gate (runnable-now mode)", required: false }
    - { key: vehicle-admissibility-gate, name: "Vehicle-Admissibility Gate (data-gated mode)", required: false }
---

# Pre-registration: {{title}}

## Hypotheses Under Test

<!-- Which hypotheses does this analysis address? List by ID (e.g., H01).
     These must match entries in the `related` frontmatter field
     so that interpret-results can find this pre-registration. -->

## Expected Outcomes

<!-- What do you expect to find, and why? Be specific about direction, magnitude, and pattern. -->

## Decision Criteria

<!-- For each hypothesis:
- What evidence would SUPPORT it?
- What evidence would WEAKEN it?
- What evidence would REFUTE it?
Be concrete — name the metric, the threshold, the pattern. -->

## Null Result Plan

<!-- What does it mean if results are ambiguous or null?
- Is the analysis underpowered?
- Does null mean the hypothesis is wrong, or that the test was inadequate?
- What would you do next? -->

## Suspicious/Unexpected Result Plan

<!-- What would "too good to be true" look like?
- What result would be suspiciously high (e.g., AUC > 0.95, perfect accuracy)?
- What inflators could produce misleading results (data leakage, confounds, overfitting)?
- What checks would you run before accepting an unexpectedly strong result?

This section prevents post-hoc rationalization of inflated signals.
Omit if the analysis type doesn't have a meaningful "too good" threshold. -->

## Known Limitations

<!-- What can this analysis NOT tell you, even if it works perfectly? -->

## Metric Selection Rationale

<!-- What metrics are used and why?
- Primary metric: what is it, and why was it chosen?
- If the metric changed from a prior analysis, explain what motivated the switch.
- What are the metric's known limitations?

This section ensures the rationale for metric choices is documented up front,
especially when the primary metric has changed mid-project.
Omit if metric choice is straightforward and unchanged. -->

## Exploratory vs. Confirmatory

<!-- Which analyses are pre-registered (confirmatory) and which are explicitly exploratory?
Mark each planned analysis as one or the other. Exploratory analyses are fine — but they need different evidential weight. -->

## Total Comparison Count

<!-- How many statistical tests or comparisons will this analysis involve?
Include both confirmatory and exploratory.
If the count is high (>10), specify the correction method
(e.g., Bonferroni, FDR, permutation null).

| Category | Count | Correction |
|---|---|---|
| Confirmatory tests | N | method |
| Exploratory tests | N | method or "none (exploratory)" |
| **Total** | **N** | |
-->

## Execution-Readiness Gate (runnable-now mode)

<!-- Optional. Use in RUNNABLE-NOW mode when the current data/vehicle exists,
but the result is only interpretable if pre-specified checks pass. Omit when
all readiness checks are already covered by the main Decision Criteria.

- State the power floor, input QA checks, preprocessing checks, and required
  sensitivity checks that must pass before the result can carry confirmatory weight.
- These checks gate verdict interpretability rather than data availability.
- If a gate fails, classify the result as inconclusive/protocol-failed according
  to the Null Result Plan; do not treat it as a substantive null against the target.
-->

## Vehicle-Admissibility Gate (data-gated mode)

<!-- Optional. Use in DATA-GATED mode: when the decision rule is committed now but
execution is deferred until a suitable data vehicle is admissible. Omit otherwise.

- State the standing verdict while gated, e.g. `[?] inconclusive-for-coverage`.
- Enumerate the substrate-verification preconditions (G1, G2, … ) that a candidate
  dataset/vehicle MUST satisfy before this pre-reg's confirmatory analysis may run.
- These G-gates ARE the "Blocking Checks Before Execution" that /science:plan-analysis
  reports for a committed pre-reg — define them once here and reference them there,
  rather than restating the gate in both artifacts.

cf. the t054/t048 coverage-suspension pattern this generalizes. -->
