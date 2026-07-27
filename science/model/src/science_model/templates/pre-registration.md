---
id: "pre-registration:{{nn}}-{{slug}}"
kind: "pre-registration"
title: "{{title}}"
status: "committed"
committed: "{{YYYY-MM-DD}}"
spec: ""  # optional path to design/spec doc, e.g. entities/design/<NNNN>-<slug>-design.md
related: []  # hypothesis IDs, inquiry slugs, or task IDs this pre-reg covers
vehicles: []  # the data this pre-reg freezes; each entry needs BOTH a path and a sha256:
              #   - path: "inputs/graph-export.json"
              #     sha256: "<64-hex>"
              # A path alone freezes nothing. `science validate` fails closed on a vehicle
              # that is gitignored, untracked, or whose content has drifted from its hash.
              # Leave empty ONLY in data-gated mode (see the Vehicle-Admissibility Gate).
              # Declaring vehicles here also anchors this document's numeric claims for
              # `numeric-anchor` — it is the pre-registration's provenance field, so do
              # NOT duplicate the paths into `source_refs:`.
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "pre-registration" }
    title: { from: title }
    status: { from: status }
    committed: { from: created }
    spec: { default: "" }
    related: { from: related }
    vehicles: { default: [] }
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
    - { key: training-side-confound-gate, name: "Training-Side Confound Gate (signature / model-transfer feasibility)", required: false }
    - { key: known-limitations, name: "Known Limitations", required: true }
    - { key: metric-selection-rationale, name: "Metric Selection Rationale", required: true }
    - { key: exploratory-vs-confirmatory, name: "Exploratory vs. Confirmatory", required: true }
    - { key: total-comparison-count, name: "Total Comparison Count", required: true }
    - { key: estimator-certification-gate, name: "Estimator Certification Gate", required: true }
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

Name each row's vehicle by the `vehicles:` frontmatter entry that freezes it, not by a
bare path. A path is a location, not a record: if the file is a build product, running
the registered analysis can regenerate it and destroy what was registered.
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

## Training-Side Confound Gate (signature / model-transfer feasibility)

<!-- Required when the analysis freezes a signature, score, or model to be projected
onto a NEW target cohort. Target-side gates (feature compatibility, target-local
technical correlations, label-permutation / matched-random-set nulls at projection)
do NOT test whether the signature is a batch artifact of its OWN training cohort — a
signature confounded with training-batch structure passes every downstream target-side
check by construction (fb-2026-07-18-007).

Before freezing, add a training-side gate:
- Cross-tab the training contrast (e.g. frail vs. old) against every technical axis of
  the training data — GEO submission / batch / platform, library depth, cell/sample
  count. Any strong contingency is a confound, not a nuisance.
- Refit the signature with the confounder as a covariate (e.g. `~ submission + <contrast>`),
  repeat LODO / cross-validation on the adjusted model, and compare the adjusted signed
  signature to the frozen primary at the SAME Jaccard / gene-count thresholds; restrict
  null permutations to within-batch.
- Pre-commit the pass/fail: e.g. adjusted reproducibility above bar AND primary-gene
  retention above bar AND signed Jaccard above bar. A borderline result (adjusted
  reproducible but low retention / low signed Jaccard) is INCONCLUSIVE — halt before any
  target label is read, do not project. -->

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


## Estimator Certification Gate

<!-- Applies when the analysis estimates parameters numerically -- any optimiser, profile, or
     ODE/discretisation in the inferential path. If it does not, DELETE this section.

     Nothing validates this section. Its force is that a threshold finer than its instrument's
     resolution is not conservative -- it is noise-driven, and the noise has a SIGN: optimiser
     error in a likelihood ratio is a difference of two one-sided biases, and the larger model
     is systematically the harder one to fit.

     Order: well-posedness -> certify the estimator -> price the design -> commit the budget.
     A budget priced on an uncertified estimator is a consequence of an untested assumption,
     not a constraint on the analysis.

     See skills/study-design/estimator-certification.md. -->

| Axis / commitment | Value | Reference / domain |
|---|---|---|
| 0. Well-posedness | <structural + practical identifiability; are the profile CIs closed?> | <design-only; no data needed> |
| 1. Forward-map accuracy | <tolerance, on the DECISION STATISTIC, propagated> | <INDEPENDENT mechanism: a different scheme family, or an adaptive solver 2-3 orders tighter. A finer step of the SAME scheme is a convergence check, not a reference.> |
| 2. Reproducibility | <MAX over R >= 5 replicates -- not the median> | <perturb every inferentially irrelevant DOF: start point, ordering, threads, seeds. If the estimator is deterministic, INJECT jitter -- a check that cannot fail is not a check.> |
| 3. Threshold calibration | <EXECUTED, or CONDITIONAL> | <if CONDITIONAL: cost, trigger, invalidation clause, AND the decisions that may not depend on it until it completes> |
| Outer optimiser | <method> | <why it is valid for this profile's smoothness/discontinuity structure. Gradient- and FD-based methods are PROHIBITED unless smoothness is DEMONSTRATED.> |
| Error budget | E = |b| + k*s <= rho * sigma_null(T), k in [2,3] | <rho = 0.1 default, and NEVER unstated. Dimensionless, against the null's sampling SD -- NOT a % of the critical value, which drifts with the degrees of freedom. Do not call it alpha; alpha is the test size.> |
| Indeterminate band | units with |T - c| <= E are INDETERMINATE | <report the count; they are not silently decided> |
| Compute budget | <cost> | <certified | CONDITIONAL on ...> |
| Invalidation | <what re-opens this certificate> | <estimator, forward model, tolerances, hardware, libraries> |

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
- While gated, `vehicles:` is legitimately empty -- this section is what declares that.
  Once a vehicle IS admitted, record it in `vehicles:` with its sha256 before executing.
- Enumerate the substrate-verification preconditions (G1, G2, … ) that a candidate
  dataset/vehicle MUST satisfy before this pre-reg's confirmatory analysis may run.
- These G-gates ARE the "Blocking Checks Before Execution" that /science:plan-analysis
  reports for a committed pre-reg — define them once here and reference them there,
  rather than restating the gate in both artifacts.

cf. the t054/t048 coverage-suspension pattern this generalizes. -->
