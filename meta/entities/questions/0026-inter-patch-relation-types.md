---
id: question:0026-inter-patch-relation-types
kind: question
title: What types of inter-patch relations are valid in the Science federation model,
  and how do they map to the philosophical spectrum from reduction to 'stories'?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Frigg2025
related:
- hypothesis:0007-working-model
- question:0011-graph-valued-synthesis-artifacts
- question:0014-adaptive-project-topology
created: '2026-07-10'
updated: '2026-07-10'
---

# What types of inter-patch relations are valid in the Science federation model, and how do they map to the philosophical spectrum from reduction to 'stories'?

## Summary

Frigg and Hartmann (2025) document a philosophical spectrum of inter-model relations
running from thoroughgoing reduction (Scheibe) through controlled approximation, singular
limits, structural relations, to loose "story" relations (Hartmann's "stories" work). The Science working
model (`hypothesis:0007-working-model`) commits to a federated patchwork where patches
connect via a dual common space (shared ontology + latent axis), but does not yet specify
which of these inter-patch relation types are expressible, desirable, or computable in the
graph. This question asks: which inter-patch relation types should the toolkit support,
how are they represented in the graph, and under what conditions does evidence in one
patch legitimately propagate to another?

## Why It Matters

- **Design decision for the federation layer**: The current implementation (task:t067,
  `question:0014-adaptive-project-topology`) realizes one inter-patch relation type —
  latent-axis cosine similarity — but does not yet represent formal reducibility,
  approximation, or story relations that the philosophy literature identifies as distinct.
  A principled taxonomy of inter-patch relation types is a prerequisite for a well-typed
  federation graph.
- **Evidence propagation correctness**: The risk of leaving this unanswered is that
  evidence from one patch propagates to another patch via association alone (similarity-based
  extrapolation), when the correct warrant is structural (the patches share a formal
  inter-model relation). Mis-typing the relation could under- or over-propagate belief updates.
- **Epistemic honesty**: The patchwork picture (Cartwright/Hacking) says patches hold
  ceteris paribus in their domains; inter-patch claims are stronger and require explicit
  justification. Without typed inter-patch relations the graph cannot distinguish
  "these patches are similar" from "this patch reduces to that one."

## Current Evidence

- **Supporting**: The latent-axis federation in task:t067 demonstrates that data-driven
  similarity (corrected PMI cosine) is a working inter-patch relation in the natural-systems
  domain. The shared ontology backbone provides a second, symbolic relation. Both are
  already in the toolkit.
- **Philosophical taxonomy available**: Frigg and Hartmann (§5.2) enumerate the full
  spectrum: reductive (Scheibe), controlled approximation, singular limit (Batterman),
  structural (Gähde), and "story" (Hartmann's "stories" work). These could serve as a controlled
  vocabulary for relation-type annotation on federation edges.
- **Against a premature taxonomy**: The entry notes that whether a general account of these
  relations is achievable remains open. For many model pairs, only case-by-case analysis
  determines which type holds. A toolkit-level taxonomy should therefore be optional
  annotation, not mandatory classification.

## Thoughts

- The most tractable near-term addition: annotate inter-patch similarity edges with a
  `relation_type` field drawn from a lightweight controlled vocabulary
  (e.g., `latent-similarity | ontology-overlap | approximation | story | reduction`).
  Default: `latent-similarity` (the current task:t067 relation).
- A "story" relation (Hartmann's "stories" work — two patches share causal mechanism fragments
  without formal derivability) is likely the most common inter-patch relation in the
  natural-sciences domain and should be expressible without requiring formal reducibility.
- The connection to Bayesian inter-model relations (Dizadji-Bahmani et al.; Liefke and Hartmann) is promising: if patches are treated as alternative models
  of the same target, Bayesian model comparison could provide a principled propagation
  weight. This is worth a separate spike before committing a relation taxonomy.

## Connections to Project

- Related hypotheses: `hypothesis:0007-working-model` (the patchwork architecture
  this question directly concerns), `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`
  (evidence propagation correctness depends on inter-patch relation typing).
- Required data or analyses: A case study applying the proposed relation taxonomy to
  two real patches (e.g., the CMT and HSP patches from task:t067) would ground the
  design decision.
- Priority level: Medium — the current latent-similarity relation already works for the
  natural-systems use case; typing refinement is an improvement, not a blocker.

## Related

- Topic notes: `hypothesis:0007-working-model` §FEDERATION; task:t067 patch federation.
- Article notes: `paper:Frigg2025` §5.2 (patchwork, inter-model relations); Cartwright
  (1999) *The Dappled World*; Morgan and Morrison (1999) *Models as Mediators*.
- Methods/Datasets: pan-disease CMT/HSP patches (task:t067 proving ground).
