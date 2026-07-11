---
id: question:0028-dynamical-causal-structure-representation
kind: question
title: Should the Science toolkit represent causal structure as a dynamical object
  conditioned on recorded interventions?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Baumeler2025
related:
- question:0010-causal-graph-construction-pipeline
- question:0025-causal-edge-modal-typing
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
created: '2026-07-10'
updated: '2026-07-10'
---

# Should the Science toolkit represent causal structure as a dynamical object conditioned on recorded interventions?

## Summary

Baumeler and Wolf (2025) formalise that the causal structure of a
classical-deterministic process is not a fixed property but a *dynamical object*:
it evolves as agents perform interventions at source vertices, and the same cyclic
digraph can realise different effective causal structures depending on what
interventions have been recorded [@Baumeler2025].
The Science toolkit currently treats causal edges as static graph objects whose
belief is updated by evidence payloads.
This question asks whether the toolkit should instead represent causal structure
as intervention-conditioned — tracking, at minimum, which intervention-sequence
state a causal edge assertion is relative to.

## Why It Matters

- **Causal edge schema design**: if causal structure is dynamical, an edge
  asserted before any intervention has a different epistemic status than one
  asserted after a set of interventions has been recorded.
  Conflating them risks letting pre-intervention structural hypotheses and
  post-intervention causal claims reinforce each other spuriously.
- **Cyclic causal graphs**: the toolkit may encounter feedback loops (e.g., in
  biological regulatory networks or research-process models); without a notion of
  intervention-conditioned causal structure, cyclic graphs cannot be safely
  handled — a static representation implies potentially contradictory causal
  directions.
- **Guardrail coherence (H04)**: the H04 causal-estimand guardrail requires that
  evidence be matched to an explicit causal claim; a dynamical-causal-structure
  lens sharpens *which* claim is being supported — the pre-intervention structural
  hypothesis, or a post-intervention causal correlation claim.
- **Risk if unanswered**: the toolkit accumulates structural and estimand-bearing
  evidence on the same edge without distinguishing intervention-conditioned scope,
  weakening the correctness guarantees the guardrail is designed to provide.

## Current Evidence

- Baumeler and Wolf prove (Theorem 3) that if all leaves of a flow are trivial
  then the process produces only causal correlations; this is a *structural*
  result obtainable without model parameters, showing that qualitative causal
  reasoning is separable from quantitative estimation [@Baumeler2025].
- The superflow algorithm operates on causal structure alone, directly supporting
  a `structural_hypothesis` evidence role that is parameter-free — the toolkit
  already informally distinguishes structural from quantitative causal claims, but
  has no schema field for it.
- The admissibility constraint (Theorem 2: faithful + consistent implies
  siblings-on-cycles) could serve as a validator for cyclic causal graphs accepted
  by the toolkit.
- The toolkit's existing causal-graph-construction pipeline (q0010) identifies
  that graph object type and discovery method must be recorded before graph edges
  can strengthen causal propositions, but does not address the
  intervention-conditioning of the causal structure itself.
- No counter-evidence exists in the current project literature; the question is
  primarily about whether the formalism is *operationally necessary* at the
  toolkit's current stage.

## Thoughts

- **Best current interpretation**: for the toolkit's immediate use cases
  (observational biological data, causal discovery, LLM-assisted graph
  construction), a full intervention-conditioned representation is likely premature.
  A pragmatic first step is to add a `structural_only` boolean or an
  `evidence_role: structural_hypothesis` annotation to distinguish parameter-free
  structural causal claims from estimand-bearing ones — this is the superflow
  analogy.
- **Major uncertainty**: whether any real toolkit workflow will generate or
  consume true dynamical-causal-structure sequences (flows) in the near term, or
  whether the paper's value is primarily conceptual scaffolding for the schema
  design.
- The siblings-on-cycles validation rule is the most immediately actionable
  implication: if the toolkit ever admits cyclic causal structures, this
  constraint should be enforced.

## Connections to Project

- Related hypotheses: `hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening`
  (the dynamical-structure view sharpens what an estimand must be relative to);
  `hypothesis:0007-working-model` (patches as local epistemic neighborhoods —
  dynamical structure suggests patches are also intervention-indexed).
- Required data or analyses: schema design exercise — enumerate all current
  toolkit causal-edge use cases and check whether any involve intervention
  sequences; if none do, defer to a later design phase.
- Priority level: low — conceptual scaffolding; actionable only after q0010 causal
  graph construction pipeline design stabilises.

## Related

- Topic notes: `topic:causal-inference` (if present); `topic:structured-scientific-knowledge`
- Article notes: `paper:Baumeler2025` (primary source);
  Barrett, Lorenz, and Oreshkov (arXiv:1906.10726) for quantum causal models;
  Vilasini and Renner on embedding quantum cyclic models in relativistic spacetime.
- Methods/Datasets: n/a at this stage
