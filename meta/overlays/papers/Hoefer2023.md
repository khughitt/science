---
id: paper:Hoefer2023
overlay_of: paper:Hoefer2023
pin_version: "1.0.0"
status: active
created: "2026-07-10"
updated: "2026-07-10"
source_refs:
- cite:Hoefer2023
related:
- hypothesis:0001-stochastic-revisiting
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- hypothesis:0007-working-model
- question:0003-causal-synthesis-guardrails
- question:0025-causal-edge-modal-typing
---
# Causal Determinism (Stanford Encyclopedia of Philosophy)

- **Authors:** Carl Hoefer
- **Year:** 2023 (first published 2003; substantive revision 21 September 2023)
- **Venue:** Stanford Encyclopedia of Philosophy
- **URL:** https://plato.stanford.edu/entries/determinism-causal/
- **BibTeX key:** Hoefer2023
- **Source:** PDF (web page saved as PDF; SEP encyclopedia entry)

## Key Contribution

Hoefer's SEP entry provides the canonical philosophical analysis of causal determinism.
The core definition: the world is deterministic if and only if, given a specified way things are at a time t plus the laws of nature, the way things go thereafter is fixed — where "fixed" means logically entailed.
The entry distinguishes determinism sharply from fatalism and from predictability, surveys formal breakdowns in physical theories (classical mechanics, GR, QM), and argues that objective chance (non-trivial probabilities strictly between 0 and 1) is compatible with determinism under a Humean "Best Systems" account of laws.

## Methods

Conceptual and philosophical analysis; authoritative survey of the literature from Leibniz and Laplace through 20th-century physics and analytic philosophy of science.
Covers classical mechanics, special relativity, general relativity, and quantum mechanics in turn; examines epistemological challenges (chaos, metaphysical argument); and reviews major law-theoretic positions: Humean Best Systems Analysis (BSA), "pushy explainers," and anti-fundamentalism (Cartwright, van Fraassen, Dupré).

## Relevance

This entry is directly relevant to three load-bearing choices in the Science toolkit.

**D-003 (beliefs strictly in (0, 1)).** Section 5's treatment of non-trivial objective probabilities maps exactly to D-003's constraint: regardless of whether the world is fundamentally deterministic or indeterministic, the epistemically appropriate representation uses probabilities strictly inside (0, 1). Under a Humean account, even a deterministic world can sustain non-trivial chances; under an indeterminist account, the chances are fundamental. Either way, 0 and 1 are epistemically unreachable for any proposition whose truth is not logically guaranteed or logically excluded.

**H01 (stochastic revisiting) [@hypothesis:0001-stochastic-revisiting].** Hoefer §3.3 supplies a physics-grounded argument for why any finite embedded agent should treat low-confidence claims as potentially recoverable: a deterministic-chaotic process and a genuinely stochastic process are empirically indistinguishable. Hard-gating a low-evidence claim would be valid only if the agent could certify that the process is not chaotic-deterministic — a certification unavailable to any embedded observer.

**H04 (causal-estimand guardrails) [@hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening].** Hoefer §2.1 identifies the fundamental problem with event-level "sufficient cause": any set of prior events that plausibly suffices is only sufficient *ceteris paribus*, with an open-ended list of potential disruptors excluded. This is Bertrand Russell's original objection to causation (1912). The toolkit's requirement for explicit target population, covariate coverage, and transport assumptions is the operationalization of this ceteris paribus clause — making what is left implicit in ordinary causal language explicit in the evidence schema.

**Cross-project relevance (natural-systems).** The entry's formal structure of physical law — (world state, t) + laws → (world state, t') — provides the conceptual vocabulary for natural-systems' causal-modeling domain. The toolkit's causal graph nodes and edges correspond, respectively, to world states and laws-of-influence; the entry grounds why this representation requires typed, assumption-explicit edges rather than bare directional links.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| World state at time t | Node state / observation | The snapshot of a causal system at one point in time |
| Laws of nature (entailing) | Causal mechanism / directed edge | Hoefer: "logical entailment" is the modality; the toolkit edge should carry the assumption set that licenses this entailment |
| Non-trivial objective chance | Continuous belief in (0, 1) | D-003's lower/upper bound; Humean chance is exactly the probability type the toolkit's belief representation models |
| Deterministic chaos / SDIC | Epistemic uncertainty from finite observation | An embedded agent cannot distinguish chaos from genuine stochasticity; evidence tagging should not assert determinism on the basis of finite observation alone |
| Ceteris paribus clause on sufficient cause | Estimand + covariate coverage + transport assumptions | H04 guardrail; Hoefer/Russell show that every event-level causal claim hides an open-ended exclusion list that the toolkit must make explicit |
| Bi-directional determination | Causal direction as a modeling choice | Physical determination is time-symmetric; causal asymmetry in the toolkit reflects a modeling assumption, not an ontological fact |

## Model / Tool Availability

No software artifact. This is a reference article (SEP encyclopedia entry).

## Follow-up

- Loewer (2004) "Determinism and Chance" and Hoefer (2019) *Chance in the World* for the Humean account that justifies non-trivial objective chances under determinism — directly relevant to D-003's philosophical grounding.
- Earman (1986) *A Primer on Determinism* for the original comprehensive survey of determinism in physical theories.
- Consider reserving a question on whether the Science causal graph should type edges by their modal strength (deterministic vs probabilistic vs chaotic/SDIC) — this gap is identified in §2.1 and §3.3 of this entry.
