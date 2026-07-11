---
id: paper:Giere2004
kind: paper
title: How Models Are Used to Represent Reality
status: active
paper_kind: ''
ontology_terms: []
dataset_usage: []
source_refs:
- cite:Giere2004
related:
- hypothesis:0007-working-model
- hypothesis:0006-adaptive-project-topology-improves-research-fit
created: '2026-07-10'
updated: '2026-07-10'
---
# How Models Are Used to Represent Reality

- **Authors:** Ronald N. Giere
- **Year:** 2004
- **Journal:** Philosophy of Science, 71 (December 2004), pp. 742-752
- **DOI:** 10.1086/425063
- **BibTeX key:** Giere2004
- **Source:** PDF (local)

## Key Contribution

Giere argues that scientific representation is fundamentally a pragmatic, agent-centered
activity rather than a dyadic semantic relationship between language and world. The key
move is to replace the two-place "X represents W" with a four-place schema:

> **S uses X to represent W for purposes P**

where S is the scientist or scientific community, X is the model (not a linguistic entity),
W is an aspect of the real world, and P captures why the representation is being made.
Models (abstract objects constructed from principles and specific conditions) are the
primary representational tools in science; scientists use designated similarities between
models and target systems to make empirical claims. The representation relation is not
intrinsic to the model but is enacted by agents for purposes.

## Methods

This is a short theoretical/philosophical position paper (11 pp.) published in
*Philosophy of Science* as part of a symposium. Giere draws on examples from
classical mechanics (mass-on-spring, gravitational field vs. Newtonian force), molecular
biology (Watson's DNA model), and fluid dynamics (water as molecules vs. continuous
fluid) to illustrate the four-place schema. No empirical data; the argument is conceptual
and proceeds by distinguishing five representational tiers (principles, specific conditions,
models, hypotheses, generalizations) and motivating each distinction with concrete
scientific cases.

The paper does not engage with the full literature on scientific representation but
positions itself explicitly against the semantic-view tradition (Suppe, van Fraassen) and
the language-of-science tradition, taking inspiration from Hacking (1983) on the
primacy of practice and from Clark (1997) / Tomasello (1999) on language as a cultural
artifact.

## Key Findings

**The four-place schema.** The core claim is that "S uses X to represent W for purposes P"
is the irreducible unit of scientific representation. Abstracting away to a two-place
"X represents W" loses the agent (who picks relevant similarities) and the purpose
(which determines which similarities are relevant). There is no representation without
a representing agent with a goal.

**Models as abstract objects.** Giere holds that models are abstract objects, not
linguistic entities. Any given abstract model can be characterized by many different
linguistic or mathematical expressions; conversely, two equations may characterize the
same model. Models are created-interpreted: they are not merely formal structures
but already come "with content." This means models are ontologically distinct from
the representations (words, diagrams, equations) used to characterize them.

**Principles as templates, not laws.** Newton's three laws, Maxwell's equations, the
principle of natural selection — these are not empirical generalizations but templates
for constructing models. They define very abstract objects (by specifying the quantities
and relations that models built under them must exhibit), and they function by
constraining and shaping the models constructed from them. This dissolves the old
debate about whether laws are empirical claims or definitions: the question is ill-posed
for principles; what is empirically testable are always specific models built with those
principles plus specific conditions.

**Similarity and agent choice.** Models represent via designated similarities. A scientist
uses a model to represent a target by picking out specific features of the model and
claiming those features are similar to features of the real system to some specified
degree of fit. No objective similarity measure is required; the lack of such a measure
does not introduce unacceptable relativity because claims about features of the world
remain as objective as they ever were. The agent specifying which features are to be
compared does the "loading" that makes representation directional.

**Purpose-relativity without conflict.** Water can be modeled as a collection of
molecules (for Brownian motion) and simultaneously as a continuous fluid (for pipe
flow) without contradiction, because both representations are relative to distinct
purposes. There is no privileged "what water really is" beyond the sense in which a
molecular perspective is asymmetrically more general (one can in principle explain why
a macroscopic fluid model works from within molecular principles, but not vice versa).
This asymmetry justifies a form of realism about the molecular level without requiring
that the fluid model be false.

**Perspectival realism.** The account is realist — claims of similarity extend to
unobservable features (DNA structure, atomic bonding angles) — but bounded: where
two models differ only in regions in principle undetectable (e.g., outside our light
cone), there is no scientific basis for preferring one. Representation claims are limited
to what is in principle detectable by any means compatible with our best physical
theories.

**Evidence as decision.** A brief coda (§7) notes that evidentiary relationships should
also be understood pragmatically — as human decisions to accept or reject hypotheses
in light of interests — deferring to *Explaining Science* (1988) for the full argument.

## Relevance

This paper supplies the **agent-based, purpose-indexed account of representation** that
grounds the Science toolkit's patch model. The connections are direct:

1. **Four-place schema → patch provenance + purpose.** The toolkit's `provenance_type`
   tracks who authored a patch (the S slot) and the patch entity is the X. Giere's
   analysis shows that W (target system) and P (purpose) must also be explicitly
   represented to make a patch's representational role intelligible. The `object_layer`
   in the working model (`hypothesis:0007-working-model`) fills the W slot; a corresponding
   `purpose` annotation is currently absent from the patch schema — this paper motivates
   adding it (see `question:0027-patch-purpose-annotation`).

2. **Purpose-relativity → federation without conflict** (`hypothesis:0007-working-model`).
   Giere's water example makes explicit why multiple patches representing the same
   target system are not in conflict: they serve different purposes. This is the
   philosophical foundation for the toolkit's federation of co-existing local patches.
   Two disease patches using molecular vs. phenotypic representations are both valid;
   the federation layer does not need to resolve which is "truer."

3. **Similarity without objective measure → uncertainty representation**
   (`hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`). Giere's
   point that designated similarity does not require an objective measure but does
   require the agent to specify which features are compared maps directly onto the
   toolkit's evidence payload schema: the agent must state which feature of the model
   the evidence item bears on, and the degree-of-fit is the belief value, not a
   formal isomorphism score.

4. **Adaptive topology** (`hypothesis:0006-adaptive-project-topology-improves-research-fit`).
   The purpose-indexed view implies that project topology (which patches exist, which
   models are active) should adapt as research purposes shift. A project whose purpose
   shifts from discovery to mechanism-testing needs a different set of patches, even
   over the same target W — directly motivating adaptive topology.

5. **Principles-as-templates → ontology as patch scaffold.** In the toolkit,
   shared ontologies (MONDO, HGNC, MeSH) play a role analogous to Giere's principles:
   they are abstract templates from which specific patches (models) are constructed
   by adding specific conditions (data, assay, population constraints). This analogy
   validates Science's design choice to treat ontology alignment as the "symbolic
   half" of the glue layer rather than treating ontology terms as direct empirical
   claims.

6. **Evidence as decision** (Giere §7 pointer). The evidentiary side of Giere's account
   (accepting/rejecting hypotheses in light of interests) maps onto the toolkit's
   belief update machinery: a `bears_on` evidence item does not automatically shift a
   prior — it is weighed by the agent via the belief policy. This is consistent with
   the toolkit's `BeliefPolicy` design (Spec 5).

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| `S uses X to represent W for purposes P` (four-place schema) | patch = X; agent provenance = S; object_layer target = W; purpose [missing] = P | The P slot is currently absent from the patch schema — see question:0027 |
| Abstract model (X) | patch / epistemic neighborhood | A patch is an abstract object, not a linguistic entity; may be serialized in many forms |
| Principle | shared ontology schema / template | Ontology terms constrain which patches can be built; do not themselves make empirical claims |
| Specific conditions | patch-specific data constraints / assay/population context | The conditions that turn a template into a specific model |
| Hypothesis (fit claim) | proposition (model ↔ target similarity claim) | A hypothesis in Giere's sense = a specific claim that a model fits a particular real system |
| Designated similarity (agent-specified features) | evidence item + `bears_on` edge | The agent specifies which model feature the evidence bears on and the degree of fit |
| Purpose (P) | intended research goal of a patch | Currently implicit; Giere motivates making it explicit |
| Purpose-relative representation | patch federation without conflict | Multiple patches of the same W coexist if they have distinct P |
| Perspectival realism | multi-patch federation / no global truth commitment | Each patch is a perspective; the federation does not require a single "real" model |
| Principles ≠ empirical laws | ontology terms ≠ propositions | Ontology terms define the vocabulary; propositions make claims within that vocabulary |

## Limitations

- The paper's scope is narrow (11 pp.); it establishes the four-place schema but does
  not develop a full theory of representation, similarity, or evidence. For the
  full similarity-vs-isomorphism debate, see Suárez (2003) [cited] and Nguyen & Frigg (2022).
- Giere does not address multi-model consistency or how agents should reason when two
  models of the same target give conflicting predictions for the same purpose — the
  toolkit's "incompatible models" problem (discussed in Frigg and Hartmann's SEP entry [@Frigg2025], §5.1)
  is not resolved here.
- The account of similarity is intentionally permissive (no objective measure required),
  which leaves open how agents should quantify degree-of-fit when models are used for
  quantitative prediction. The toolkit's belief machinery must supply this.
- The paper does not address computational or knowledge-representation questions; it
  cannot advise on how to encode the four-place schema in a graph store or what
  fields to add to a patch schema.

## Model / Tool Availability

No software artifacts. Philosophical position paper; freely available via institutional
access (DOI: 10.1086/425063). The paper is 11 pages; the full argument is in §§2-5.

## Follow-up

- Giere (1988), *Explaining Science: A Cognitive Approach* — full development of the
  evidence-as-decision account briefly noted in §7.
- Giere (1999), *Science without Laws* — the no-laws corollary; principles as templates.
- Suárez (2003), "Scientific Representation: Against Similarity and Isomorphism" — the
  main interlocutor on the similarity account; argues neither similarity nor isomorphism
  is sufficient or necessary for representation, suggesting inferential roles instead.
- Nguyen & Frigg (2022), *Scientific Representation* (Cambridge UP) — book-length
  treatment; the SEP companion entry defers to this for the full semantics.
- Teller (2001), "Twilight of the Perfect Model Model" — argues for approximate truth
  over exact fit; cited by Giere on purpose-relative modeling.
- **Open question for the toolkit:** Should patches carry an explicit `purpose` field
  (the P in Giere's schema)? If so, what is the right vocabulary — research-question
  references, a free-text annotation, or a controlled term? See `question:0027-patch-purpose-annotation`.
