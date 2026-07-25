---
id: hypothesis:0008-structured-workflow-reduces-analyst-belief-divergence
kind: hypothesis
title: Structured workflow reduces analyst belief divergence
status: active
source_refs: []
origins:
- type: assistant
  ref: explore-ideas-methodology
  independent: true
- type: literature
  ref: cite:Silberzahn2018
  date: '2018-08-23'
  independent: true
related: []
created: '2026-07-25'
updated: '2026-07-25'
added_by: explore-ideas:claude-opus-5:cand-methodology-many-analysts-convergence
lens_views:
- lens: methodology
  rationale: 'Turns the project''s own motivating literature into an evaluation design
    with the toolkit as the intervention arm.

    '
  origin_ref: explore-ideas-methodology
---
# Hypothesis: Structured workflow reduces analyst belief divergence

## Organizing Conjecture

Independent analysts using the toolkit's structured workflow (typed evidence aggregation, pre-registration, belief-update protocol) on the same evidence base converge to narrower belief intervals and show smaller inter-analyst variance in posterior probability than analysts using unstructured LLM assistance or unaided judgment on the same material.

**Exploration rationale (one line per contributing lens):**

- _methodology_: Turns the project's own motivating literature into an evaluation design with the toolkit as the intervention arm.

## Proposition Bundle

<!--
List the key propositions that make up this hypothesis.
Prefer explicit sub-propositions, especially those with explicit S-P-O structure:
- subject
- predicate
- object
-->

### Core Propositions

<!-- Propositions that must be roughly true for the hypothesis to survive. -->

### Supporting Or Auxiliary Propositions

<!-- Propositions that strengthen or elaborate the hypothesis but are not essential. -->

## Current Uncertainty

<!--
What makes this hypothesis currently fragile, contested, or underspecified?
Note whether support is sparse, single-source, indirect, literature-only, etc.
-->

## Predictions

<!--
What should we observe if the core claims are true?
Distinguish strong discriminating predictions from weaker corollaries.
-->

## Falsifiability

The hypothesis is refuted if, on the same evidence base and question, inter-analyst
variance in posterior belief is **not lower** in the toolkit arm than in the
unstructured-LLM arm — or is higher.

Specific results that would force revision:

- Variance in the toolkit arm equal to or greater than the unstructured-LLM control.
  Structure supplies more surfaces to disagree about (which evidence is admissible, how to
  type a relation, which ceiling applies); it is entirely possible that it *relocates*
  divergence rather than reducing it, and produces more of it in the process.
- Convergence that is achieved but spurious: analysts converge because the workflow
  anchors them on the same early framing, not because they reason better. Detectable by
  checking whether the converged belief is closer to ground truth, not merely tighter.
  Convergence without accuracy gain refutes the useful form of the claim even if it
  satisfies the literal one.
- A sensitivity check that shows the effect is carried by pre-registration alone, or by
  any single component, would not refute the hypothesis as stated but would gut its
  interest — the claim is about the structured workflow, not about one gate.

Note the hypothesis is currently untestable at this project's scale: it needs multiple
independent analysts. Recording it now fixes the prediction before the capability exists,
which is the point.

## Supporting Evidence

<!--
Existing evidence that supports one or more propositions in this bundle.
Note evidence type where possible:
- literature
- empirical-data
- simulation
- benchmark
-->

## Disputing Evidence

<!--
Existing evidence that weakens or contests one or more propositions.
Include null or conflicting findings here.
-->

## Evidence Needed To Shift Belief

<!--
What evidence would most efficiently increase or decrease confidence?
What is the most discriminating next test?
-->

## Related Work

<!--
Papers, topics, inquiries, and other hypotheses that bear on this hypothesis.
-->
