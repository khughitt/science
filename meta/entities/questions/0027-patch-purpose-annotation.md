---
id: question:0027-patch-purpose-annotation
kind: question
title: Should toolkit patches carry explicit purpose annotations (the P in Giere's
  agent-based representation schema)?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Giere2004
related:
- hypothesis:0007-working-model
created: '2026-07-10'
updated: '2026-07-10'
---

# Should toolkit patches carry explicit purpose annotations (the P in Giere's agent-based representation schema)?

## Summary

Giere's agent-based account of scientific representation takes the form "S uses X to
represent W for purposes P." The Science toolkit explicitly models S (provenance/agent),
X (patch / epistemic neighborhood), and W (target system via `object_layer`), but has
no dedicated slot for P — the purpose for which a patch was built. This question asks
whether patches should carry an explicit `purpose` field, what vocabulary that field
should use, and what downstream benefits or costs that would entail.

## Why It Matters

- **Disambiguation of co-existing patches:** When two patches represent the same target
  system (same W) using different models, the federation layer needs a principled way
  to say they are not in conflict. Explicit purpose annotations supply that: they are
  not in conflict because they serve different P. Without P, the only available
  disambiguator is model structure, which may not be sufficient.
- **Evidence routing:** Evidence items `bears_on` a particular patch feature. If a
  patch's purpose shifts, the same evidence may no longer be relevant. Purpose
  annotations would make that sensitivity explicit and allow evidence relevance to
  be checked against purpose.
- **Risk if unanswered:** Patch federation remains philosophically under-specified.
  Agents constructing patches may inadvertently build redundant representations of
  the same W for the same P, leading to double-counted evidence, without a formal
  mechanism to detect the duplication.

## Current Evidence

- **Supporting (add purpose):** Giere (2004) establishes that purpose is constitutive
  of representation — you cannot say what a model represents without specifying for
  what it was used. The water/molecular vs. continuous-fluid example shows that the
  same target demands different models for different purposes, and both are legitimate.
  The toolkit's patch federation does not currently detect same-W/same-P duplication.
- **Supporting (add purpose):** The working model (`hypothesis:0007-working-model`)
  describes patches as surrounding a hypothesis/question/evidence cluster. Research
  questions already function as implicit purpose specifications, suggesting a natural
  vocabulary: purpose could reference the question or hypothesis the patch is built
  to address.
- **Against / complicating:** Purposes can be nested or shift over a patch's lifecycle
  (a patch built for discovery may later be repurposed for mechanism analysis).
  A static `purpose` field may mislead rather than clarify. A reference to a question
  entity already captures purpose indirectly via the patch's `related` edges.
- **Against:** Adding a required field increases authoring cost. If purpose is already
  captured by the patch's `related` questions/hypotheses, the cost may outweigh the
  benefit.

## Thoughts

- The best current interpretation is that purpose is already implicitly present via
  the patch's `related` edges (links to questions and hypotheses). Making it
  explicit as a controlled field would improve machine-readability of the federation
  layer, but the benefit needs to be weighed against authoring overhead.
- A minimal first step could be a free-text `purpose` frontmatter field (optional,
  not required), to be used when a patch's purpose is not obvious from its `related`
  edges alone.
- The major remaining uncertainty is whether the duplication-detection use case
  (same-W/same-P collision detection) is worth implementing. If federation always
  expects multiple co-existing patches and never needs to detect redundancy, the
  field adds no value.

## Connections to Project

- Related hypotheses: `hypothesis:0007-working-model` (federation model; patches as
  epistemic neighborhoods); `hypothesis:0006-adaptive-project-topology-improves-research-fit`
  (topology changes when purposes shift).
- Required data or analyses: Survey of existing patches in a live project to assess
  whether same-W/same-P duplication has occurred in practice.
- Priority level: Low-medium. The federation layer is not yet deployed; this question
  becomes load-bearing when cross-patch reasoning is implemented.

## Related

- Topic notes: Giere's four-place schema (paper:Giere2004); working model (hypothesis:0007-working-model).
- Article notes: `paper:Giere2004` (the source paper), `paper:Frigg2025` (the SEP survey
  discussing perspectival realism and the representation relation).
- Methods/Datasets: None currently required.
