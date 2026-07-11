---
id: question:0031-structural-modularity-in-causal-patches
kind: question
title: How should the Science toolkit represent modularity status and cross-equation
  restrictions as properties of a causal patch or edge?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Hoover2009
related:
- question:0010-causal-graph-construction-pipeline
- question:0003-causal-synthesis-guardrails
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- hypothesis:0007-working-model
created: '2026-07-10'
updated: '2026-07-10'
---

# How should the Science toolkit represent modularity status and cross-equation restrictions as properties of a causal patch or edge?

## Summary

Hoover (2009) shows that many real causal systems — monetary policy models subject to
the Lucas critique, carburetor mechanisms, steam-valve systems — fail Woodward's
modularity condition: equations (and the causal arrows they encode) cannot be disrupted
independently without altering the rest of the causal structure [@Hoover2009].
In a non-modular system, evidence gathered by a come-what-may intervention on one
variable is structurally invalid for the intended causal inference, because the intervention
changes the causal system rather than isolating a causal pathway within it.
This question asks whether the Science toolkit should explicitly track modularity status
(modular vs. non-modular) and cross-equation restrictions as first-class properties of
causal patches or edges, and whether modularity failure should be its own reason code in
the uncertainty/attention vocabulary.

## Why It Matters

- **Guardrail precision** (`hypothesis:0004`): the existing causal-estimand guardrails
  check whether evidence matches the estimand; non-modularity is a distinct failure mode
  (evidence is structurally invalid, not just statistically mismatched). Without a
  modularity field, this failure class is invisible to the guardrail system.
- **Evidence-type discrimination** (`question:0003`): cross-equation-restricted systems
  produce evidence that looks valid but depends on parameter correlations that Hoover's
  Reichenbach Convention forbids — this should trigger a reason code (`cross-equation-restriction`)
  distinct from `source-dependence` or `missing-identification`.
- **Patch-scope integrity** (`hypothesis:0007`): a patch's causal field (the fixed background
  conditions) determines what is in scope. In non-modular patches, changing one in-scope
  variable structurally alters another; the toolkit should warn when evidence bears on a
  variable inside such a patch.
- **Risk if unanswered**: the toolkit may silently accept intervention-based evidence from
  non-modular systems as cleanly causal, propagating structurally invalid strengthening
  updates into causal propositions.

## Current Evidence

- Hoover (2009) demonstrates modularity failure in the Lucas-critique monetary policy system
  and in Cartwright's carburetor example; in both cases, Woodward's come-what-may intervention
  changes the structural form of the remaining equations, not just their parameters [@Hoover2009].
- The structural account shows that modularity holds conventionally at the parameter level
  (by the Reichenbach Convention) but not at the mechanism/equation level — so modularity
  status is a property of the *representation*, not just of the world [@Hoover2009].
- Existing causal-discovery tools (gCastle, causal-learn) do not explicitly expose
  modularity status as a graph or edge property; the closest concept is faithfulness, which
  is distinct. [UNVERIFIED: whether any discovery toolkit exposes modularity flags]
- The current `question:0010` evidence covers hidden-variable assumptions, causal-sufficiency
  assumptions, and graph object type, but does not explicitly include modularity status as
  a required field.

## Thoughts

- **Best current interpretation**: modularity status is a coarse binary property of a
  causal patch (is the system modular given the current causal field?) and a more refined
  property of individual edges (does the arrow encoding this equation depend on parameters
  shared with other equations?). Both levels are useful: the patch-level flag warns before
  any edge is interpreted; the edge-level flag localizes the problem.
- A `cross-equation-restriction` indicator on an edge could be derived automatically from
  the parameter-set representation if the toolkit stores parameterizations explicitly;
  alternatively it could be a manually-set flag during patch construction.
- **Major uncertainty**: whether explicitly tracking modularity is operationally feasible
  for the diverse causal systems Science projects encounter (biological pathways, economic
  models, epidemiological DAGs), or whether it is primarily relevant to formal parametric
  systems (econometrics, physics). Biological systems often have functional coupling
  analogous to cross-equation restrictions (pathway crosstalk, feedback), but these are
  rarely represented with explicit parameter sets.

## Connections to Project

- Related hypotheses: `hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening`,
  `hypothesis:0007-working-model`
- Required data or analyses: design discussion against the current causal-edge schema;
  identify whether the t034 contract's existing `edge_role` taxonomy should add a
  `modularity_status` or `cross_equation_restricted` field.
- Priority level: Medium — relevant to causal guardrail completeness (H04) but gated on
  whether formal parametric systems are a realistic use case for current Science projects.
  Biological systems would need a looser, domain-adapted notion of modularity.

## Related

- Topic notes: `hypothesis:0007-working-model` (patch concept and causal field),
  `hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening`
- Article notes: `paper:Hoover2009`; future intakes: Hoover (2001) *Causality in
  Macroeconomics*, Woodward (2003) *Making Things Happen*
- Methods/Datasets: N/A (design question)
