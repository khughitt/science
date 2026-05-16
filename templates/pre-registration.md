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

Every *interpretive* numerical commitment in `## Decision Criteria` — i.e., a
threshold that interprets what an observed effect size, CI, or posterior
quantity means for the hypothesis — should appear here as its own block. The
goal is to make the *epistemic basis* of each expectation auditable before
data arrives, and to prevent pre-data numerical commitments from masquerading
as rigor when they are in fact extrapolations from one cohort or thin-air
guesses.

Out of scope: operational and QA thresholds (minimum sample size, MCMC
convergence checks like R-hat / ESS, leakage / suspicious-result bounds,
QC floors, runtime limits). Those live in `## Methods`, `## Known
Limitations`, or `## Suspicious/Unexpected Result Plan` with their own
rationale — they are not interpretive claims about expected biology.

### Evidence tiers

| Tier | What it means | Pre-data gate allowed? |
|---|---|---|
| `acknowledged` | Parameter known to be relevant; no estimate authored. `expected:` is null and `provenance:` is empty. Records a known-unknown for transparency and surfaces it as a graph-visible uncertainty node. | **No.** Cannot bind a gate — there is no number to gate on. Forces explicit treatment of the unknown in interpretation rather than silent omission. |
| `hint` | Number supported by literature only, OR by 1–2 own analyses on disparate datasets. Could be real; not yet validated against confounding, batch effect, or technical artifact. | **Soft only.** A "soft" gate has a wider expected range, not a movable threshold. Original gate is always reported in the verdict, including for failures. Any post-data threshold change requires an amendment or a fresh pre-reg, and the recalibrated gate cannot support a confirmatory claim for the same analysis. |
| `calibrated` | Number supported by 3+ own analyses on disparate datasets, enumerated in `provenance:`. The 3+ requirement is the threshold for "real distribution, not technical artifact." | **Yes.** Narrow gates permitted; cite the 3+ in provenance. |

**On "soft" vs. "movable":** Soft gates lower evidential weight (a failure is
less catastrophic; a pass is less probative). They do *not* grant permission
to revise the threshold after seeing data. If a soft gate fails, the analysis
either accepts the failure under the registered terms or invokes the
amendment procedure — making the analysis path-B / exploratory for the
recalibrated threshold, not confirmatory.

### Per-expectation block

Repeat for each expectation. YAML is parser-friendly; prose `notes:` are fine
for anything the schema can't capture.

```yaml
- parameter: "<name of the quantity, with units if relevant>"
  expected:
    central: "<best single guess, with sign>"      # null for `acknowledged`
    range:   "<plausible range, e.g., [+0.05, +1.0]>"  # null for `acknowledged`
    direction: "<positive | negative | either | unsigned>"
  evidence_tier: <acknowledged | hint | calibrated>
  provenance:
    # One entry per supporting source. Empty list for `acknowledged`.
    # 1–2 entries → `hint`. 3+ disparate-dataset own-analyses → `calibrated`.
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
    # `acknowledged` blocks: "no gate; surfaces a known unknown"
    # `hint`-tier expectations: informational / soft gate only
```

Worked examples:

```yaml
# Hint tier — disagreeing prior own-analyses, soft gate only.
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
    - "whether cohort-disagreement reflects biology (cytogenetic stratum mix) or technical confounding (platform, ambient RNA, capture rate)"
    - "whether ribosome-axis score behaves linearly with E2F1 outside [-1, +2] range observed in prior cohorts"
  gate_use: "Informs prior range and direction-prior weakly. Does not anchor a narrow β threshold. Verdict uses a wider acceptable-β range than would be granted with calibrated backing; the registered range is reported regardless of result."
```

```yaml
# Acknowledged tier — known-relevant parameter, no estimate authored.
- parameter: "patient-level NB dispersion structure φ_p in MM scRNA"
  expected:
    central: null
    range: null
    direction: unsigned
  evidence_tier: acknowledged
  provenance: []
  unknowns:
    - "no MM scRNA cohort has measured per-patient φ_p at the cell-count scale of the planned fit"
    - "expected magnitude of cross-patient variation in φ_p (1.5× vs 10× vs 50×?)"
    - "whether φ_p variation is dominated by biology (cell-cycle composition, malignancy stage) or technical capture"
  gate_use: "No gate. Recorded as a known unknown so PPC-adequacy interpretation does not silently assume shared dispersion. Surfaces as a graph-visible uncertainty node for follow-up calibration."
```

The β example would *not* clear a `calibrated` tier — only two own-analyses
exist and they disagree. `hint` is the correct declaration; any
β-referencing threshold in Decision Criteria must be authored with a wider
acceptance range up front. The current pre-reg's analysis may become the
third data point that lets the *next* pre-reg author `calibrated`
expectations for this parameter.

The φ_p example is `acknowledged` not `hint` because no numerical estimate
is authored — we know the parameter matters but have no prior data to
commit to. Acknowledged blocks should be common in early-stage projects;
they make graph-visible the "what we don't know" surface.

If a pre-reg has zero numerical commitments — e.g., a purely qualitative
"we expect direction X" registration — this section may be omitted, but
`## Decision Criteria` should then also contain no interpretive numerical
thresholds. -->

## Decision Criteria

<!-- For each hypothesis:
- What evidence would SUPPORT it?
- What evidence would WEAKEN it?
- What evidence would REFUTE it?
Be concrete — name the metric, the threshold, the pattern.

Every *interpretive* numerical threshold in this section — a threshold that
reads an observed effect, CI, or posterior quantity as supporting / weakening /
refuting the hypothesis — must trace back to an `## Expectations` block via
`gate_use:`. A criterion citing a `hint`-tier expectation must be authored
with a wider acceptance range than a `calibrated`-backed criterion would
permit; narrow gates require `calibrated`-tier backing (3+ disparate own-
analyses in provenance). If an interpretive criterion has no upstream
Expectations block, either author the block or remove the numerical
specificity from the criterion.

**Operational / QA thresholds are out of scope** for this binding rule:
minimum sample size, MCMC convergence checks (R-hat, ESS), leakage /
suspicious-result bounds, QC floors, and runtime limits live in `## Methods`,
`## Known Limitations`, or `## Suspicious/Unexpected Result Plan` with their
own rationale, and do not require Expectations blocks.

**Soft gates are not movable gates.** A criterion citing a `hint`-tier
expectation has wider acceptance bands authored *before* data arrives. If
that wider gate fails, the analysis either accepts the failure under the
registered terms or invokes the amendment procedure — and the recalibrated
gate cannot support a confirmatory claim for the same analysis (it becomes
path-B / exploratory for that threshold). -->

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
