---
id: t101
project: ''
title: Make the curation-ratchet model explicit and formulate its evaluation
type: ''
aspects:
- hypothesis-testing
- computational-analysis
priority: P2
status: proposed
blocked_by: []
related:
- question:0008-llm-agents-as-fallible-sources
- question:0012-agent-tool-kg-operations
- question:0017-benchmark-grounding-metrics
parent: ''
group: ''
artifacts: []
findings: []
created: '2026-07-24'
completed: null
---

Follow-up from the autonomous-research S1 (autonomy envelope) design work in the toolkit repo. That design assumes, but never states, a model of why continuous autonomous curation should help. Make the model explicit and specify how it could be evaluated — or refuted.

Working hypothesis (RATCHET): combining iterative knowledge-graph growth (user-driven, hybrid, or agent-driven) with continuous review/curation/refinement acts mostly like a ratchet — review catches and corrects mistakes more often than it introduces them, so quality is monotone-ish over time. 'Mostly' is the load-bearing qualifier and the part that needs operationalizing: some errors go unfixed, and review itself introduces new ones. The interesting quantity is the net correction rate and the conditions under which it turns negative (e.g. review pass depth, sampling weight, model capability, entity kind, how contested a region of the graph is).

The ratchet is about ERROR CORRECTION, not accretion. The claim is not that the graph grows monotonically; it is that auditing propositions, references, and links catches mistakes, and fixing them moves the graph continuously toward ground truth — or, more modestly, toward clear expressions of what is believed and what data supports it. The ratchet is the asymmetry between fixes and newly-introduced errors, nothing more.

Second proposition (SPARSITY): sparsity induction / distillation / pruning can help focus the graph on a robust 'core' and improve performance. Read alongside the corrected ratchet framing these are complementary rather than opposed — both remove error, one by correcting claims and one by removing weakly-supported ones. What the model does need to state is their MEASUREMENT interaction: pruning changes the population any quality metric is computed over, so a loop that both corrects and prunes can improve almost any per-claim average by deleting the hard cases. Guard: denominate quality over a frozen entity population fixed at t0, not over the surviving population.

Evaluation direction: diverse benchmarks used reflexively (testing our own curation strategies, not just the domain content) to compare strategies and covariates. Existing anchors: q0017 benchmark grounding metrics, q0013 robustness/reproducibility evaluation.

Deliverable: an explicit written model (hypothesis + propositions with stated falsification conditions), plus a proposed evaluation design naming the benchmark(s), the metric(s), the covariates to vary, and what result would refute the ratchet claim.

MEASUREMENT HAZARD (design constraint, not a caveat): a curation system evaluated on a metric it can influence is scoring its own homework, and 'quality improved' becomes unfalsifiable. Candidate loop-breakers, roughly by cost:

1. Historical-error replay. The repo's own git history is a labeled error corpus: every human fix commit is a (before=error, after=correction) pair. Replay before-states and measure detection/correction rate. Representative by construction, no fabrication, and it measures the ratchet's actual quantity rather than a proxy.
2. Sham-curation negative control. An arm making changes of similar volume but semantically null. If the metric improves there too, it is measuring activity, not quality.
3. Frozen holdout. Curate region A, evaluate on region B the loop never touches — enforceable by the autonomy envelope's path gate, which already denies writes by path.
4. Seeded-error injection, with the injector independent of the curator (different process/prompt/model) and the injection log outside the curator's read surface.
5. Prospective/temporal. Freeze at T, run, score against what became known by T+k. Strongest (the answer did not exist when the loop ran) and slowest — worth standing up early so it can pay off later.
6. Blind adjudication. Before/after pairs in random order to an independent judge; expensive per sample, so use it to calibrate the cheap metrics rather than as the primary measure.

Two standing rules regardless of which are chosen: the curator must not be able to READ its own score (compute it in the supervisor, which already sits outside the actor's write surface), and the metric plus refutation threshold must be pre-registered — the toolkit already requires this for estimators, and this is the same failure mode.