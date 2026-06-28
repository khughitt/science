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
    - { key: analysis-registry, name: "Analysis Registry", required: false }
    - { key: expected-outcomes, name: "Expected Outcomes", required: true }
    - { key: decision-criteria, name: "Decision Criteria", required: true }
    - { key: calibration-gate, name: "Calibration Gate (in-run no-peeking threshold)", required: false }
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

## Analysis Registry

<!-- Optional. Use when one pre-registration covers multiple analyses, especially
when those analyses have mixed runnable/data-gated statuses or different
confirmatory/exploratory roles.

Each row is one analysis-level commitment. Do not force the whole pre-reg into
one top-level mode when rows differ. Instead, link to that analysis's Execution-Readiness Gate or Vehicle-Admissibility Gate and state the per-row verdict policy.

| Analysis ID | Commitment target | Mode | Status | Gate reference | Verdict policy |
|---|---|---|---|---|---|
| A1 | hypothesis:H01 or inquiry:<slug> | runnable-now | confirmatory | Execution-Readiness Gate / G1 | result carries confirmatory weight only if gate passes |
| A2 | hypothesis:H02 or inquiry:<slug> | data-gated | confirmatory | Vehicle-Admissibility Gate / G2 | `[?]` inconclusive-for-coverage until admissible vehicle exists |
-->

## Expected Outcomes

<!-- What do you expect to find, and why? Be specific about direction, magnitude, and pattern. -->

## Decision Criteria

<!-- For each hypothesis:
- What evidence would SUPPORT it?
- What evidence would WEAKEN it?
- What evidence would REFUTE it?
Be concrete — name the metric, the threshold, the pattern. -->

## Calibration Gate (in-run no-peeking threshold)

<!-- Optional. Use when a threshold will be derived inside the run from the
current substrate before confirmatory scoring. This is for an in-run,
no-peeking, marginal-derived threshold; it is not a data-gated pre-registration
and does not defer the analysis.

- Allowed calibration inputs must be marginal distributions or eligibility
  counts only.
- Explicitly forbid outcome labels, effect estimates, group-contrast results,
  downstream performance metrics, and other target-linked signals before lock.
- State the lock point and the audit artifact that proves calibration occurred
  before confirmatory scoring.

| Threshold | Allowed calibration inputs | Forbidden inputs | Lock point | Formula |
|---|---|---|---|---|
| <name> | marginal distributions or eligibility counts only | outcome labels, effect estimates, group-contrast results | before confirmatory scoring | <pre-committed rule> |
-->

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
