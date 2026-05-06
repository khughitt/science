---
type: synthesis
report_kind: hypothesis-synthesis
id: synthesis:h05-sequential-evidence-improves-attention
hypothesis: hypothesis:h05-sequential-evidence-improves-attention
generated_at: "2026-05-06T03:57:33Z"
source_commit: "591956fe223318a92c9b36ba01afefcfb1246b10"
provenance_coverage: thin
---

## State

H05 is a speculative candidate hypothesis. No empirical project evidence currently supports it; the basis is architectural argument derived from three external literature sources.

The core claim is that replacing fixed-N aggregation (Bayes factors, BMA, BES) with anytime-valid procedures (e-values, test martingales, or confidence sequences) will produce better-calibrated attention and stopping behavior in workflows where evidence arrives sequentially with optional stopping and unbounded revisiting. The hypothesis asserts this improvement without yet knowing which anytime-valid primitive is the right choice.

Three literature sources provide indirect motivation. `paper:Mulder2026` supports cumulative evidence monitoring under Bayes-factor frameworks but requires explicit prior and stopping setup. `paper:Aitken2024` notes Bayes-factor evaluation is sensitive to assumptions, a problem sequential reuse exacerbates. `paper:Maier2022` covers model uncertainty under fixed evidence but does not address optional-stopping reuse. None of these establishes the anytime-valid framing for project workflows directly.

Key open questions are tracked under `question:06-sequential-anytime-valid-evidence`: whether optional stopping is prevalent enough in this project to warrant the added formalism, which anytime-valid primitive is primary, and whether current schema nodes already accommodate anytime-valid outputs or need extension.

## Arc

Arc reconstruction is limited because no interpretations with `prior_interpretations` chains exist for H05.

H05 was created 2026-05-05 as a speculative offshoot of the Batch 1 attention work. The impetus was a reading pipeline (`t028`) that queued e-value and confidence-sequence references but had not yet been ingested. Rather than wait, the hypothesis was registered speculatively so the design question (`question:06-sequential-anytime-valid-evidence`) would have a formal home and so the graduate-or-retire decision could be made explicitly once the reading was done.

The single scoped task, `t032`, defines the graduation gate: ingest the `t028` references, write a topic note on sequential evidence, audit project graph state for optional-stopping prevalence, propose an H01-simulator extension, and issue a promote-or-retire verdict. Until `t032` completes, the epistemic position is architectural conjecture only.

## Research Fronts

All substantive work on H05 flows through `t032` (P2, proposed). Its constituent steps define the full near-term agenda:

- Ingest e-value, test-martingale, and confidence-sequence references queued in `t028`; produce `doc/background/topics/sequential-evidence.md`.
- Audit project graph state to measure how often the same proposition actually receives sequential evidence — P3 (workflow fit) depends entirely on this audit.
- Extend the H01-simulator to model sequential evidence arrival with optional stopping; benchmark anytime-valid attention against fixed-N posterior and BMA-style attention at equal review budget.
- Determine whether schema and synthesis-node types from `t022`/`t023` accommodate anytime-valid outputs or require extension (bearing on P4, architectural compatibility).
- Issue the graduation verdict: promote H05 to active or retire it.

The live design question is `question:06-sequential-anytime-valid-evidence`. No topic gaps are registered in the bundle.
