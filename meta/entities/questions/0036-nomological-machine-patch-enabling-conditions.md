---
id: question:0036-nomological-machine-patch-enabling-conditions
kind: question
title: Should the toolkit's patch schema encode the enabling conditions (nomological-machine
  boundary) under which a patch's causal claims hold?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Gaspar2024
related:
- hypothesis:0007-working-model
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- question:0019-powers-vs-laws-causal-edge-ontology
- question:0031-structural-modularity-in-causal-patches
created: '2026-07-10'
updated: '2026-07-10'
---

# Should the toolkit's patch schema encode the enabling conditions (nomological-machine boundary) under which a patch's causal claims hold?

## Summary

Cartwright's nomological machine concept — formalised and applied to cosmology by
Gaspar and Tambor (2024) — holds that laws of nature arise only within specific physical
arrangements (machines) that are "fixed enough" and operate in a "stable enough
environment." Outside the machine's enabling conditions, the law does not hold. The
Science toolkit's patch concept is already described as a local epistemic neighborhood
surrounding a hypothesis cluster, but the schema does not yet represent the enabling
conditions or background constraints (the "causal field") that demarcate the domain of
validity for the patch's causal claims [@Gaspar2024]. This question asks whether the patch
schema should be extended to encode these enabling conditions, and what that would look
like in practice.

## Why It Matters

- **False-universality guardrail (H04 + H07)**: Without an explicit enabling-conditions
  field, a causal claim validated inside one patch (e.g., for a specific biological pathway,
  energy regime, or experimental context) can be silently treated as valid across all patches.
  Gaspar2024 calls this "false universality" — a documented methodological failure even in
  cosmology. Encoding enabling conditions gives the guardrail system a hook to flag
  cross-patch extrapolation.
- **Patch boundary definition**: The working model (`hypothesis:0007`) defines patches as
  epistemic neighborhoods but does not specify what makes the boundary of a patch. The
  nomological-machine framing offers a principled answer: the boundary is set by the
  enabling conditions under which the patch's causal laws hold. Without this, patch
  boundaries are informal and subjective.
- **Cross-domain evidence reuse**: When evidence from one project (or cosmic regime)
  is promoted to science-commons for reuse in another project, the receiving project needs
  to know under what conditions the evidence was gathered. Enabling-conditions metadata
  is the carrier for that information.
- **Risk if unanswered**: The toolkit may accept evidence strengthening updates for causal
  propositions whose domain scope does not match the evidence's originating context —
  a structurally analogous failure to the modularity-violation case in q0031, but arising
  from domain-scope mismatch rather than parametric coupling.

## Current Evidence

- Gaspar and Tambor (2024) demonstrate that even the Standard Cosmological Model —
  grounded in GTR — functions as a nomological machine only within the cosmological
  principle's enabling conditions (homogeneity and isotrophy). Removing those conditions
  removes the law of expansion [@Gaspar2024].
- Cartwright (1999) defines the nomological machine formally: "a fixed (enough) arrangement
  of components … with stable (enough) capacities that in the right sort of stable (enough)
  environment will, with the repeated operation, give rise to the kind of regular behavior
  that we represent in our scientific laws" [MISSING_CITATION: Cartwright1999 not yet
  in entities/papers/].
- Smolin and Unger's false-universality critique (cited in Gaspar2024) establishes that
  assuming locally-valid laws hold globally is a documented methodological error with
  consequences for cosmological model selection; the analogous error in the toolkit is
  assuming locally-valid causal claims hold globally across projects or domains [@Gaspar2024].
- The existing patch schema (`hypothesis:0007`) uses the concept of a "causal field" in
  passing (the RFC §12 background) but does not define it as a first-class schema field.
- Question `question:0031-structural-modularity-in-causal-patches` identifies a related
  gap: whether modularity status (independence of equations) is encoded per-patch. The
  enabling-conditions question is orthogonal but complementary — modularity is about
  structural independence within a machine; enabling conditions are about what makes
  the machine run at all.

## Thoughts

- **Best current interpretation**: the toolkit needs at minimum a lightweight
  `domain_scope` annotation at the patch level — a list of named context conditions
  (e.g., `{energy_regime: low, system_type: mammalian_cell, population: European_ancestry}`)
  under which the patch's causal claims were established. This is not a formal enabling-
  conditions theory; it is a controlled-vocabulary tag that lets the guardrail system
  check for out-of-scope evidence use.
- A more principled longer-term design would encode enabling conditions as a typed
  constraint set referencing ontology terms (e.g., MONDO disease scope, tissue type,
  energy scale from a physics ontology), analogous to how Cartwright's machine is
  described by its component set and operating environment.
- **Major uncertainty**: whether it is practically feasible for toolkit users to specify
  enabling conditions at patch authoring time, or whether this information is only
  available post-hoc (after a failed extrapolation is noticed). If post-hoc, enabling
  conditions could still be added as a `scope_notes` text field as a starting point,
  deferring structured schema until real use cases motivate it.
- The cosmological case is clean (enabling conditions = cosmological principle) but most
  biological domain cases will have fuzzy, gradient enabling conditions (e.g., "normal
  cellular conditions" is not a precise boundary). This fuzziness may argue for a
  probabilistic scope confidence field rather than a binary in/out encoding.

## Connections to Project

- Related hypotheses: `hypothesis:0007-working-model` (patch concept, causal field),
  `hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening`
  (the false-universality error is a guardrail failure)
- Required data or analyses: design discussion — review current patch schema (RFC §12)
  and the `t034` edge contract to identify where domain-scope annotation would attach;
  survey existing Science project patches for examples of implicit scope conditions that
  are currently un-encoded.
- Priority level: Medium — directly blocks correct cross-domain evidence reuse (commons
  promotion) and is a prerequisite for false-universality guardrail completeness. Lower
  urgency than modularity (q0031) for single-project use but higher for multi-project
  federation.

## Related

- Topic notes: `hypothesis:0007-working-model` (patchwork model, causal field),
  `hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening`
- Article notes: `paper:Gaspar2024` (primary source; cosmological nomological machines);
  `paper:Mumford2004` (powers ontology — complementary philosophical grounding);
  future: Cartwright (1999) *The Dappled World* [MISSING_CITATION];
  Smolin and Unger (2015) *The Singular Universe and the Reality of Time* [MISSING_CITATION]
- Methods/Datasets: N/A (schema design question)
