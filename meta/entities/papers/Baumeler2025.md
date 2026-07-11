---
kind: paper
title: Flow of dynamical causal structures with application to correlations
status: active
created: '2026-07-10'
updated: '2026-07-10'
id: paper:Baumeler2025
ontology_terms: []
source_refs:
- cite:Baumeler2025
related:
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- hypothesis:0007-working-model
- question:0010-causal-graph-construction-pipeline
- question:0025-causal-edge-modal-typing
---

# Flow of dynamical causal structures with application to correlations

- **Authors:** Ämin Baumeler and Stefan Wolf
- **Year:** 2025
- **Journal/Venue:** Physical Review Research, 7, 033278
- **DOI/URL:** https://doi.org/10.1103/PhysRevResearch.7.033278
- **BibTeX key:** Baumeler2025
- **Source:** PDF

## Key Contribution

Baumeler and Wolf introduce the *flow of causal structures* — a directed graph
that records every possible way a classical-deterministic causal model's causal
structure can evolve as agents intervene sequentially at source vertices [@Baumeler2025].
They also define the *superflow*, a model-parameter-agnostic outer approximation
constructable from the causal structure alone, without access to the underlying
functional parameters.
As a first application, they prove (Theorem 3) that if every leaf of a flow is
trivial — a single-vertex graph — then all correlations the process can produce
are *causal*: future events cannot influence past ones.
This strictly strengthens a prior result (Ref. [15] in the paper) that chordless
cycles are sufficient for causal correlations.

## Methods

The paper works within the classical-deterministic causal model framework (a
directed graph D = (V, E) for causal structure plus functional parameters F =
{ωv : O_{Pa(v)} → I_v}), which is also the classical limit of the Barrett–Lorenz–Oreshkov
quantum causal model.
Two algorithms are developed:

- **Algorithm 1 (Flow — model-parameter-aware):** Iterates over source vertices
  (parentless nodes) in the current causal structure, applies every possible
  intervention value, computes the reduced causal model (removing the source and
  partially applying its output to its children's functions), and records the
  resulting causal structures as children in the flow graph.
  Terminates when all leaves are trivial or have no sources.
- **Algorithm 2 (Superflow — model-parameter-agnostic):** Same skeleton but,
  instead of evaluating actual functional reductions, exhausts all subsets of
  incoming edges to each child of the removed source and keeps only those that
  yield a *siblings-on-cycles* graph (Theorem 2: every faithful consistent causal
  model has a siblings-on-cycles causal structure).

Both algorithms have exponential runtime O(2^{poly(n)}) in the number of agents n.
The reduction correctness rests on Theorem 1 (consistency is preserved under
source-agent reduction) and Theorem 2 (admissibility: faithful + consistent
implies siblings-on-cycles).

The quantum generalization is discussed but identified as currently intractable,
because partial tracing in the quantum case does not factorise the way functional
substitution does in the classical case.

## Key Findings

1. The flow graph makes the dynamical aspect of cyclic causal structures explicit:
   directed cycles in a causal model represent *potential* information paths, not
   actual causal loops; the flow "unravels" which paths are realised under each
   sequence of interventions.
2. The superflow is a purely qualitative object — its construction requires only
   the causal structure (digraph), not the numerical or functional parameters.
   Qualitative causal-order questions can therefore be answered at the
   structural level alone.
3. **Theorem 3 (Causal correlations):** If every leaf of a flow F is a trivial
   (single-vertex) graph, then the process produces only causal correlations, i.e.,
   correlations that decompose as a convex mixture in which each term fixes a
   definite causal order among the agents.
4. The theorem also holds for superflows (since a superflow is a supergraph of
   the flow), making it applicable without model parameters.
5. There exist causal structures with chordal directed cycles that, by Theorem 3,
   still produce only causal correlations — filling a gap left by the prior
   chordless-cycles sufficient condition.
6. The companion C implementation of Algorithm 2 is openly available [Ref 29].

## Relevance

This paper bears on two live areas of the Science toolkit.

**Causal graph representation and dynamics (H04, q0010).**
The toolkit currently treats causal edges as static graph objects updated by
evidence payloads.
Baumeler and Wolf formalise that causal structure is *dynamically relative to
interventions*: the effective causal structure changes as agents act, and a
single directed graph with cycles can represent many distinct operational causal
structures depending on what has been intervened on.
This suggests the toolkit may need to track *which interventions have been
recorded* when asserting a causal edge, or at least distinguish structural
(pre-intervention) causal hypotheses from intervention-conditioned causal claims.

**Qualitative vs. quantitative causal reasoning (H04 P2, superflow).**
The superflow is parameter-free but still supports the causal-correlation result.
This provides formal backing for the toolkit's existing intuition that structural
causal claims (edge topology) should be modelled separately from estimand-bearing
quantitative claims.
It suggests adding a `structural_only` flag or a distinct evidence-role type to
distinguish "this evidence bears on causal structure" from "this evidence bears on
the functional/estimand content."

**Cross-link: natural-systems project.**
The formalism (dynamical causal order, process-matrix framework, quantum gravity
motivation) is relevant to natural-systems work on formal causal structure
representation; this paper should be promoted to `science-commons` when commons
curation resumes.

## Project Framework Mapping

| Paper Concept | Toolkit Concept | Notes |
|---|---|---|
| Causal structure D (digraph) | Causal graph (structural layer) | The toolkit's graph nodes and directed edges correspond to D's vertices and edges. |
| Model parameters F | Evidence payload / functional mechanisms | Quantitative dependencies ωv correspond to the toolkit's estimated-effect or mechanism evidence payloads (H04 P2 fields). |
| Flow graph F | Intervention-conditioned causal-structure sequence | The toolkit has no direct equivalent yet; closest is an ordered sequence of evidence payloads or causal-discovery pipeline stages (q0010). |
| Superflow S | Structural causal hypothesis (pre-parameter) | Corresponds to a causal edge with `evidence_role: structural_hypothesis` and no estimand metadata. |
| Trivial leaf | Fully observed / no cyclic dependency remaining | A state where every agent has been assigned a definite causal position; analogous to a fully identified causal model. |
| Causal correlations | Causal edge with definite directional support | A correlation that decomposes causally maps onto a toolkit edge whose belief has been updated with valid causal direction evidence. |
| Siblings-on-cycles constraint | Admissibility rule for cyclic causal graphs | If the toolkit ever accepts cyclic causal structures (e.g., feedback loops), this constraint should be enforced as a validation rule. |

## Limitations

The paper is restricted to classical-deterministic models; the authors explicitly
defer the quantum case.
Algorithms are exponential in the number of agents, limiting practical
applicability to small causal structures.
The results concern *possible* correlations, not their statistical
estimation — the paper is a theoretical contribution with no empirical component.
The practical operationalisation for software tooling (e.g., how to index or
store flows in a graph database) is not addressed.

## Model / Tool Availability

Algorithm 2 (superflow) is implemented as a C program, openly available per
the paper's data availability statement (Ref [29]).
No Python or ecosystem-compatible package is released; the C code is a research
prototype.

## Follow-up

- Evaluate whether the toolkit's causal edge schema should include an
  `evidence_role: structural_hypothesis` type to capture parameter-free causal
  structure claims (analogous to the superflow).
- Consider whether the `siblings-on-cycles` admissibility constraint should be
  added as a validation rule for cyclic causal graphs in the Science toolkit
  (related: `question:0010-causal-graph-construction-pipeline`).
- Review Barrett, Lorenz, and Oreshkov (arXiv:1906.10726) for the quantum causal
  model formalism that this paper extends — the quantum case is relevant to
  understanding the boundaries of the classical causal model representation.
- Cross-link to `natural-systems` project for formal causal structure; flag for
  promotion to `science-commons` in the next curation pass.
