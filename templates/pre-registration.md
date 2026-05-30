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
QC floors, runtime limits). Those live in `## Known Limitations`,
`## Suspicious/Unexpected Result Plan`, or the paired analysis-plan doc
referenced by `spec:` in frontmatter — they are not interpretive claims
about expected biology.

### Evidence tiers

| Tier | What it means | Pre-data gate allowed? |
|---|---|---|
| `acknowledged` | Parameter known to be relevant; no estimate authored. `expected.central` and `expected.range` are null (`direction:` may still carry meaning, e.g., `unsigned` or `unknown`); `provenance:` is empty. Records a known-unknown for transparency in a machine-readable form, available for later tooling that extracts uncertainty nodes. (No parser reads these blocks today — the structure is forward-compatible.) | **No.** Cannot bind a gate — there is no number to gate on. Forces explicit treatment of the unknown in interpretation rather than silent omission. |
| `hint` | Number supported by literature only, OR by one own-analysis on a single dataset, OR by two own-analyses on disparate datasets. Could be real; not yet validated against confounding, batch effect, or technical artifact. | **Soft only.** A "soft" gate has a wider expected range, not a movable threshold. Original gate is always reported in the verdict, including for failures. Any post-data threshold change requires an amendment or a fresh pre-reg, and the recalibrated gate cannot support a confirmatory claim for the same analysis. |
| `calibrated` | Number supported by 3+ own analyses on disparate datasets, enumerated in `provenance:`. The 3+ requirement is the threshold for "real distribution, not technical artifact." | **Yes.** Narrow gates permitted; cite the 3+ in provenance. |

**On "soft" vs. "movable":** Soft gates lower evidential weight (a failure is
less catastrophic; a pass is less probative). They do *not* grant permission
to revise the threshold after seeing data. If a soft gate fails, the analysis
either accepts the failure under the registered terms or invokes the
amendment procedure — making the analysis path-B / exploratory for the
recalibrated threshold, not confirmatory.

### Calibration sources

Every `provenance:` entry declares *what kind of source* the estimate came
from. This is independent of evidence tier — a `hint` block can have one
`literature` entry, while a `calibrated` block has 3+ `prior_own_analysis`
entries on disparate datasets. The classification surfaces the most common
authoring anti-pattern: numbers picked from analyst intuition that look
like they have provenance because they appear in a structured field.

| `calibration_source` | What it means |
|---|---|
| `literature` | Paper, review, or external benchmark. Cite paper-key in `ref:`. |
| `prior_own_analysis` | A prior task or interpretation in this project that estimated this quantity on a different cohort or design. Cite `task:tNNN` or `interpretation:<slug>` in `ref:`. |
| `pilot_fit` | A committed pilot artifact that estimates this quantity for the *current* analysis cohort/design. Cite the pilot's task ID and result artifact in `ref:`. Pilot must run before main analysis if the gate depends on this. |
| `related_cohort_baseline` | A baseline analysis on a different but mechanistically-comparable cohort (e.g., healthy-tissue scRNA when the analysis is on disease scRNA). Cite the baseline task/dataset in `ref:`. |
| `analyst_judgment` | Number picked by the author from intuition without enumerable provenance. **This is the over-confidence flag.** Permitted only with explicit reasoning in `notes:` and should be paired with a `## Pilot Calibration` deferral or downgraded to `acknowledged`. |

The `analyst_judgment` class is intentionally uncomfortable to declare. If
an author is willing to flag a number as `analyst_judgment`, the right
move in most cases is one of: (a) demote the block to `acknowledged`
(no number authored); (b) author a `## Pilot Calibration` deferral that
derives the cut from a pilot/baseline; (c) widen the gate range so the
analyst_judgment cuts are clearly boundary conditions rather than load-
bearing thresholds; (d) accept the `analyst_judgment` flag as a permanent
caveat on the verdict.

### Per-expectation block

Repeat for each expectation. YAML is parser-friendly; prose `notes:` are fine
for anything the schema can't capture.

```yaml
- parameter: "<name of the quantity, with units if relevant>"
  scope: <confirmatory | exploratory | sensitivity>   # optional; see "Block scope" below
  expected:
    central: "<best single guess, with sign>"      # null for `acknowledged`
    range:   "<plausible range, e.g., [+0.05, +1.0]>"  # null for `acknowledged`
    direction: "<positive | negative | either | unsigned>"
  evidence_tier: <acknowledged | hint | calibrated>
  provenance:
    # One entry per supporting source. Empty list for `acknowledged`.
    # 1–2 entries → `hint`. 3+ disparate-dataset own-analyses → `calibrated`.
    - source: "<paper-key | cohort name | task id>"
      calibration_source: <literature | prior_own_analysis | pilot_fit | related_cohort_baseline | analyst_judgment>
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
  gate_limitations:   # optional; see "Gate limitations" below
    # Foreseen limits on the gate's *resolving power* — rival models the gate
    # cannot exclude within a stated result region, known before data. Distinct
    # from `unknowns:` (which is about the parameter value).
    - alternative: "<the rival model/reading the gate cannot rule out>"
      region: "<observed-value region where the gate cannot discriminate>"
      verdict_if_unresolved: "<[?] inconclusive | [⌀] non-adjudicating>"
```

### Block scope

`scope:` is **optional** and declares each expectation's evidential role:

- `confirmatory` — pre-registered; gates a hypothesis verdict.
- `exploratory` — hypothesis-generating; carries no confirmatory weight.
- `sensitivity` — robustness check on a confirmatory block (e.g., re-running
  the gate under an alternative prior or covariate set).

Forward-compatible: omitting it leaves all current behavior unchanged and the
`## Exploratory vs. Confirmatory` section remains authoritative. When present,
it lets that section be derived per-block rather than restated, makes the
confirmatory-test count machine-readable, and enables one-rule lints (e.g.
"hint-tier confirmatory blocks must cite a soft gate").

### Gate limitations

`gate_limitations:` is **optional** and records foreseen limits on the gate's
*resolving power*: rival models the gate cannot exclude within a stated result
region, known before data. This is **not** the same as `unknowns:` — `unknowns:`
captures uncertainty in the parameter *value*, whereas a gate limitation can
hold even when the value is estimated perfectly: the gate still cannot
adjudicate between two mechanisms that both produce a result in that region.

Each entry names the rival reading, the result region where the gate cannot
discriminate, and the verdict the result carries there. That verdict is `[?]`
**inconclusive** (the design cannot discriminate) — or `[⌀]` **non-adjudicating**
when the test layer *does* resolve but the rollup is deliberately closed without
a direction. (Both tokens are from the canonical verdict vocabulary in
`templates/interpretation.md`; see `## Decision Criteria`.) Recording this up
front stops a result in the non-discriminating region from being read post-hoc
as a confirmation of either model.

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
      calibration_source: prior_own_analysis
      estimate: "-0.11 [-0.44, +0.24]"
      ref: "task:t172"
      notes: "Per-cell unstratified; HDI spans 0; sign-suggestive but inconclusive."
    - source: "Ledergor 2018 (own analysis)"
      calibration_source: prior_own_analysis
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
  gate_use: "No gate. Recorded as a known unknown so PPC-adequacy interpretation does not silently assume shared dispersion. Machine-readable for later tooling that extracts uncertainty nodes."
```

```yaml
# Gate-limitation example — the gate cannot adjudicate a rival model in part
# of its output range. `scope:` and `gate_limitations:` shown together.
- parameter: "R² for per-patient phase_score ~ stage + cytogenetic_subtype"
  scope: confirmatory
  expected:
    central: "0.45"
    range:   "[0.30, 0.60]"
    direction: positive
  evidence_tier: hint
  provenance:
    - source: "t640 variance decomposition (own analysis)"
      calibration_source: prior_own_analysis
      estimate: "R² ≈ 0.4 on a single cohort"
      ref: "task:t640"
      notes: "One cohort only; soft gate, wide band."
  unknowns:
    - "whether the R² band generalizes beyond the single cohort it was estimated on"
  gate_use: "Soft gate. R² in the captured band is read as 'cytogenetic subtype explains phase-score variance'; the registered band is reported regardless of result."
  gate_limitations:
    - alternative: "cell-cycle composition is a strong downstream mediator of cytogenetic subtype (not an orthogonal axis)"
      region: "R² in the captured band [0.30, 0.60] when mediation is strong"
      verdict_if_unresolved: "[?] inconclusive"
      # A captured-band R² is consistent with BOTH 'orthogonal axis' and
      # 'strong mediator'; the variance decomposition cannot separate them.
      # Resolving it requires the mediation pilot in ## Pilot Calibration.
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
they make the "what we don't know" surface machine-readable for later tooling.

If a pre-reg has zero numerical commitments — e.g., a purely qualitative
"we expect direction X" registration — this section may be omitted, but
`## Decision Criteria` should then also contain no interpretive numerical
thresholds. -->

## Pilot Calibration

<!-- Optional. Use this section when an Expectations block's numerical cuts
*cannot* be honestly anchored in literature, prior own-analyses, or a
related-cohort baseline — i.e., when the only honest classification of the
provenance would be `analyst_judgment`.

Rather than authoring `analyst_judgment` numbers directly, defer the cut
to a pilot fit or related-cohort baseline that will run before the main
analysis is interpreted. The deferral is itself pre-registered: the
calibration source, the rule for deriving the cut, and the no-peeking
discipline.

Each pilot-calibration block registers one or more cuts that will be
filled in by an upstream artifact before the main analysis verdict is
read. Authoring this block does not move the cut post-hoc — it registers
*before data* that the cut comes from the pilot, by the stated rule.

```yaml
- target_parameter: "<parameter the cut applies to; must match an Expectations block>"
  target_gate: "<which §Decision Criteria threshold this cut feeds, by name or table row>"
  deferred_to:
    artifact: "<task ID, pilot fit slug, or related-cohort baseline ID>"
    output_path: "<where the pilot result will be recorded — e.g., 'json:tNNN_pilot/result.json' or 'doc:interpretations/...'>"
    must_complete_before: "main analysis fit unblocks"
  derivation_rule: |
    <Plain-language rule for deriving the cut from the pilot result.
    Must be specific enough that two independent readers would derive
    the same cut from the same pilot output.>
  no_peeking_discipline: "<one line on how the author will avoid letting the main analysis's data inform the cut>"
  fallback_if_pilot_fails:
    condition: "<what counts as pilot failure>"
    action: "<what happens — usually: demote the target Expectations block to acknowledged, or convert the gate to direction-only>"
```

Worked example:

```yaml
- target_parameter: "R² for per-patient phase_score ~ stage + cytogenetic_subtype"
  target_gate: "Primary R² gate verdict bands (orthogonal / inconclusive / captured)"
  deferred_to:
    artifact: "task:tNNN-permutation-null-pilot"
    output_path: "json:tNNN_pilot/null_R2_quantiles.json"
    must_complete_before: "main analysis variance-decomposition fit"
  derivation_rule: |
    Compute the permutation null distribution of R² by shuffling
    cytogenetic subtype labels across patients 1000 times and refitting
    the variance decomposition under each shuffle. Define:
      - 'orthogonal' cut = 95th percentile of null R²
      - 'captured' cut   = empirical R² required to reject the null
                           at α=0.05 under a one-sided permutation test
    The inconclusive band is the [orthogonal cut, captured cut] range.
  no_peeking_discipline: "Pilot runs only on cytogenetic-label-shuffled data; the real R² is never computed during pilot. Pilot's null quantiles are committed to the artifact before main fit unblocks."
  fallback_if_pilot_fails:
    condition: "Pilot permutation null is degenerate (e.g., R² distribution is concentrated at one value due to stratum imbalance)"
    action: "Demote the R² gate from confirmatory to exploratory. Verdict bands are not reported; the analysis becomes a description of within-stratum variance only."
```

When this section is non-empty, the `analyst_judgment` calibration-source
flag should not appear on any block whose cuts are deferred here. The
pilot artifact's output becomes the authoritative source for those cuts;
the Expectations block's `provenance:` is updated to cite
`calibration_source: pilot_fit` once the pilot completes, *before* the
main analysis is run. This is the only post-authoring `provenance:`
update permitted without an amendment. -->

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
suspicious-result bounds, QC floors, and runtime limits live in
`## Known Limitations`, `## Suspicious/Unexpected Result Plan`, or the
paired analysis-plan doc (`spec:` in frontmatter) with their own rationale,
and do not require Expectations blocks.

**Soft gates are not movable gates.** A criterion citing a `hint`-tier
expectation has wider acceptance bands authored *before* data arrives. If
that wider gate fails, the analysis either accepts the failure under the
registered terms or invokes the amendment procedure — and the recalibrated
gate cannot support a confirmatory claim for the same analysis (it becomes
path-B / exploratory for that threshold).

**Verdict vocabulary — name the outcome, don't invent labels.** When
`interpret-results` reads this analysis it emits one of the five canonical
polarity tokens defined in `templates/interpretation.md` (with respect to the
*predicted* direction): `[+]` supports · `[-]` refutes · `[~]` mixed/null ·
`[?]` inconclusive · `[⌀]` non-adjudicating. A `hint`-tier soft gate whose
result lands in its wider acceptance band is a `[?]` **inconclusive** verdict —
not a passing confirmation, not a failure, and not an ad-hoc label like
"REGISTERED-INCONCLUSIVE". Author each criterion so its inconclusive band maps
to `[?]` explicitly, and reserve `[⌀]` for a gate that resolves at the test
layer but is deliberately closed without a direction (e.g. a `gate_limitations:`
entry on the relevant Expectations block). This is the downstream machinery you
are authoring against. -->

## Null Result Plan

<!-- What does it mean if results are ambiguous or null?
- Is the analysis underpowered?
- Does null mean the hypothesis is wrong, or that the test was inadequate?
- What would you do next? -->

## Vehicle-Admissibility Gate

<!-- DATA-GATED MODE ONLY. Omit unless this pre-reg commits a rule before any
qualifying vehicle/data exists (binding constraint = data availability, not
analysis design). If present, declare `mode: data-gated` near the top.

Specify the explicit preconditions a future vehicle must satisfy to ACTIVATE
this pre-reg's rule:
- power floor: minimum n (and any design requirement, e.g. differential design)
- comparator/lineage requirement, if any
- which spent vehicles do NOT qualify, and why (state their n)

Standing semantics until an admissible vehicle exists:
- the standing verdict is *inconclusive-for-coverage* (canonical `[?]`), which
  produces NO `bears_on` belief update — this is "no qualifying evidence yet",
  not a null result (which would be evidence);
- track activation with a `status: blocked` task whose blocker is this gate.

Contrast with `## Pilot Calibration`, which defers a single threshold while the
analysis runs now; data-gated mode defers the entire analysis. -->

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
Mark each planned analysis as one or the other. Exploratory analyses are fine — but they need different evidential weight.

If your Expectations blocks declare per-block `scope:` (confirmatory |
exploratory | sensitivity), this section can simply point at those declarations
instead of restating them — the per-block field is the single source of truth
and avoids the two drifting apart. Use prose here only for planned analyses
that have no Expectations block (e.g. purely qualitative exploratory passes). -->

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
