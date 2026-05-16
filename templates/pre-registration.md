---
id: "pre-registration:{{slug}}"
type: "pre-registration"
title: "{{Short Title}}"
status: "committed"
committed: "{{YYYY-MM-DD}}"
spec: ""  # optional path to design/spec doc, e.g. doc/specs/2026-04-25-<slug>-design.md
related: []  # hypothesis IDs, inquiry slugs, or task IDs this pre-reg covers
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
---

# Pre-registration: {{Short Title}}

## Hypotheses Under Test

<!-- Which hypotheses does this analysis address? List by ID (e.g., H01).
     These must match entries in the `related` frontmatter field
     so that interpret-results can find this pre-registration. -->

## Expected Outcomes

<!-- What do you expect to find, and why? Be specific about direction, magnitude, and pattern.

Use the `## Expectations` section below for any *numerical* expectation that will
anchor a decision criterion. Use this section for narrative direction/pattern
intuitions and qualitative shape claims. -->

## Expectations

<!-- Structured per-parameter expectations with explicit evidence provenance.

Every numerical commitment that an `## Decision Criteria` threshold references
should appear here as its own block. The goal is to make the *epistemic basis*
of each expectation auditable before data arrives — and to prevent pre-data
numerical commitments from masquerading as rigor when they are in fact
extrapolations from one cohort or thin-air guesses.

### Evidence tiers

| Tier | What it means | Pre-data gate allowed? |
|---|---|---|
| `invalid` | Number pulled from intuition, narrative reasoning, or untraceable source. | **No.** Cannot anchor any decision criterion. Either upgrade the tier with provenance or remove the commitment. |
| `hint` | Number supported by literature only, OR by one own-analysis on a single dataset. Could be real; not yet validated for robustness against confounding, batch effect, or technical artifact. | **Soft only.** Use wide CIs, conservative thresholds, and treat the gate as recalibratable post-data. Do *not* author a narrow PPC/CI/effect-size threshold from a `hint`. |
| `calibrated` | Number supported by 3+ own analyses on disparate datasets, enumerated in `provenance:`. The 3+ requirement is the threshold for "real distribution, not technical artifact." | **Yes.** Narrow gates permitted; cite the 3+ in provenance. |

### Per-expectation block

Repeat for each expectation. YAML is parser-friendly; prose `notes:` are fine
for anything the schema can't capture.

```yaml
- parameter: "<name of the quantity, with units if relevant>"
  expected:
    central: "<best single guess, with sign>"
    range:   "<plausible range, e.g., [+0.05, +1.0]>"
    direction: "<positive | negative | either | unsigned>"
  evidence_tier: <invalid | hint | calibrated>
  provenance:
    # One entry per supporting source. At least 3 disparate-dataset own-analyses
    # required to reach `calibrated`.
    - source: "<paper-key | cohort name | task id>"
      estimate: "<reported value or range>"
      ref: "<doc/task/file ref — e.g., task:t172, doc:interpretations/...>"
      notes: "<one line on what this source establishes and what it doesn't>"
  unknowns:
    # Required. At least one entry. Empty `unknowns:` is the over-confidence
    # smell — if there is genuinely nothing you don't know about this
    # quantity, the expectation should be `calibrated` with provenance proving it.
    - "<what you don't know that could move this estimate>"
  gate_use: "<how this expectation binds to a Decision Criteria threshold>"
    # e.g. "informs prior range; does not anchor hard threshold"
    # e.g. "anchors §3 success threshold at central ± 30%"
    # `hint`-tier expectations should declare informational use only.
```

Worked example (the kind of block this section expects):

```yaml
- parameter: "β_ribosome→E2F1 (per-cell, NB regression)"
  expected:
    central: "+0.3"
    range:   "[-0.5, +1.0]"
    direction: "either (cohorts disagree on sign)"
  evidence_tier: hint
  provenance:
    - source: "Boiarsky 2022 (own analysis)"
      estimate: "-0.11 [-0.44, +0.24]"
      ref: "task:t172"
      notes: "Per-cell unstratified; HDI spans 0; sign-suggestive but inconclusive."
    - source: "Ledergor 2018 (own analysis)"
      estimate: "+0.544 [+0.04, +1.03]"
      ref: "task:t203 Q3"
      notes: "Per-cell Q3; positive sign; PPC-passing; conflicts with Boiarsky."
  unknowns:
    - "patient-level dispersion structure φ_p — never measured in MM scRNA at this scale"
    - "whether cohort-disagreement reflects biology (cytogenetic stratum mix) or technical confounding (platform, ambient RNA, capture rate)"
    - "whether ribosome-axis score behaves linearly with E2F1 outside [-1, +2] range observed in prior cohorts"
  gate_use: "informs prior range and direction-prior weakly; does not anchor a hard β threshold. PPC adequacy gate must be soft (≥80%) because patient-level dispersion is unknown."
```

The example would *not* clear a `calibrated` tier — only two own-analyses exist
and they disagree. The right move is to declare `hint`, soften any threshold
that references β, and use the current pre-reg analysis as the third data point
that *might* upgrade the next pre-reg to `calibrated`.

If a pre-reg has zero numerical commitments — e.g., a purely qualitative
"we expect direction X" registration — this section may be omitted, but
`## Decision Criteria` should then also contain no numerical thresholds. -->

## Decision Criteria

<!-- For each hypothesis:
- What evidence would SUPPORT it?
- What evidence would WEAKEN it?
- What evidence would REFUTE it?
Be concrete — name the metric, the threshold, the pattern.

Every numerical threshold in this section must trace back to an `## Expectations`
block via `gate_use:`. A criterion citing a `hint`-tier expectation must be
authored as soft / recalibratable — narrow gates require `calibrated`-tier
backing (3+ disparate own-analyses in provenance). If a criterion has no
upstream Expectations block, either author the block or remove the numerical
specificity from the criterion. -->

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

<!-- What can this analysis NOT tell you, even if it works perfectly?

This is the *analysis-level* limitations section. Per-expectation unknowns
belong inside each Expectations block (`unknowns:`). Use this section for
limitations that span the whole analysis (sample size, design constraints,
cohort selection, modeling-class assumptions). -->

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
