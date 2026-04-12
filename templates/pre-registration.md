---
title: "Pre-registration: {{Short Title}}"
created: "{{YYYY-MM-DD}}"
---

# Pre-registration: {{Short Title}}

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
