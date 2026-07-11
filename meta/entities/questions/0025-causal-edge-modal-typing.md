---
id: question:0025-causal-edge-modal-typing
kind: question
title: Should the causal graph distinguish deterministic, probabilistic, and chaotic
  edge types?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Hoefer2023
related:
- paper:Hoefer2023
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- question:0003-causal-synthesis-guardrails
- question:0010-causal-graph-construction-pipeline
created: '2026-07-10'
updated: '2026-07-10'
---

# Should the causal graph distinguish deterministic, probabilistic, and chaotic edge types?

## Summary

When the Science toolkit records a causal edge in its graph, should the edge carry a modal-strength type distinguishing: (a) deterministic determination (state + laws logically entail the next state); (b) genuinely probabilistic / stochastic causation; or (c) apparently-stochastic behavior from a deterministic-chaotic underlying process (SDIC)?
Hoefer [@Hoefer2023] shows that physical theories differ sharply in their determinism properties, and that deterministic-chaotic and genuinely stochastic processes can be empirically indistinguishable to any finite embedded observer.
The question is whether this distinction matters operationally for evidence tagging, belief updating, and guardrail design in the toolkit.

## Why It Matters

- Affects the causal edge schema: if modal typing is added, evidence that "X deterministically causes Y" and evidence that "X probabilistically causes Y" would update different graph fields — strengthening one would not strengthen the other.
- Affects the H04 guardrail design: estimand metadata for a deterministic mechanism differs from metadata for a probabilistic one (e.g., a deterministic mechanism requires no effect-measure specification, whereas a probabilistic one requires a probability contrast or risk ratio).
- Risk if unanswered: edges accumulate heterogeneous evidence under a single undifferentiated causal link, allowing deterministic-mechanism evidence and probabilistic-mechanism evidence to spuriously reinforce each other in the belief aggregation layer.

## Current Evidence

- Hoefer (2023) §3.3: Suppes (1993) proved that some systems are empirically equivalent under deterministic and indeterministic models regardless of observation count — meaning the distinction can be epistemically inaccessible. If it is inaccessible in practice, typing may add overhead without payoff.
- Hoefer (2023) §5: Under a Humean account of laws, deterministic and probabilistic laws can coexist. The existing toolkit evidence schema does not yet record mechanism-level law type.
- Question q0010 (causal graph construction pipeline) identifies that graph object type, discovery method, and assumption set must be recorded before graph edges can strengthen causal propositions, but does not address the deterministic/probabilistic/chaotic partition specifically.
- No current toolkit schema fields distinguish these cases; all directed edges use the same representation regardless of underlying mechanism type.

## Thoughts

- Best current interpretation: the distinction matters most when the mechanism-type claim is itself a substantive assertion in a paper (e.g., "this gene silences transcription deterministically vs stochastically via noise-driven burst kinetics"). In those cases, the modal type should be an edge annotation, not just an assumption on the edge.
- For most research-grade causal claims, the underlying mechanism is unknown and the distinction is irrelevant; a default of "probabilistic / unspecified" is the safe choice.
- The major uncertainty is whether the toolkit will encounter enough explicit deterministic-mechanism claims (e.g., from physics-derived models in natural-systems or chemical kinetics) to justify the schema complexity of a three-way type partition.

## Connections to Project

- Related hypotheses: `hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening` (modal type is one dimension of the estimand metadata P2 requires); `hypothesis:0001-stochastic-revisiting` (the choice not to hard-gate low-evidence claims is coherent precisely because the system cannot certify non-chaotic determinism).
- Required data or analyses: audit a sample of causal claims in `entities/papers/` to measure how often the mechanism type (deterministic / probabilistic / chaotic) is explicitly asserted. If fewer than ~10% assert a type, a single probabilistic default suffices.
- Priority level: low — dependent on the causal graph construction pipeline design (q0010) being finalized first.

## Related

- Topic notes: `topic:causal-inference` if present; `topic:bayesian-methods-continuous-belief`
- Article notes: `paper:Hoefer2023` (primary source); Earman (1986) *A Primer on Determinism* (deeper treatment of physical-theory determinism)
- Methods/Datasets: n/a at this stage
