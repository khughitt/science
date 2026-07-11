---
id: paper:Tahko2023
kind: paper
title: The modal basis of scientific modelling
status: active
paper_kind: ''
ontology_terms: []
dataset_usage: []
source_refs:
- cite:Tahko2023
related:
- hypothesis:0007-working-model
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- question:0025-causal-edge-modal-typing
- question:0026-inter-patch-relation-types
- question:0010-causal-graph-construction-pipeline
- question:0030-model-system-vs-target-system-claims
- paper:Frigg2025
created: '2026-07-10'
updated: '2026-07-10'
---
# The modal basis of scientific modelling

- **Authors:** Tuomas E. Tahko
- **Year:** 2023
- **Journal:** Synthese, 201, Article 75
- **DOI:** https://doi.org/10.1007/s11229-023-04063-z
- **BibTeX key:** Tahko2023
- **Source:** PDF (CC BY 4.0 open access)

## Key Contribution

Tahko argues that all scientific models represent *networks of possibilities* rather than
actual states of affairs directly, and that the truthmakers for every modal claim derived
from a model — including claims about idealised, fictional, or "false" models — can be
located in the actual world, specifically in the modal properties (dispositions, powers, or
essential properties) of actually existing entities and the dependence structures among them.
The upshot is a unified account: we need never posit non-actual target systems; instead,
all models aim at the modal properties of actual entities, and the epistemology of modal
modelling becomes a special case of the epistemology of modality.

## Methods

This is a conceptual/philosophical paper (Synthese, special issue on Modal Modelling in
Science). The method is analytic metaphysics combined with illustrative case studies:

- A survey of the existing literature on model representation, idealisation, and fictionalisation
  (Bokulich, Weisberg, Cartwright, Elliott-Graves, and others reviewed in [@Tahko2023] §1).
- Formulation of the core metaphysical thesis: models represent possibilities; modal
  properties of actual entities are the truthmakers.
- Analysis of three challenging model types: "false" idealisations (frictionless plane),
  fictional models (Bohr's atom), and counterlegal models (models with metaphysically
  impossible antecedents, e.g., diamond without covalent bonds).
- A detailed case study: the nuclear shell model and its predictions about superheavy
  elements and the "island of stability" (elements Z ≥ 103, especially unbihexium Z = 126),
  showing that counterfactual claims about never-synthesised elements have actual
  truthmakers in the known energy-level dependence structure of nucleons.

Key assumptions: anti-Humean approach to modality (modal properties are objective, not
merely epistemic); a realist framework about possibilities; the representation relation
between model and target involves at minimum partial similarity or isomorphism of
counterfactual structure (Bokulich's "isomorphism of counterfactual structure"). The paper
remains deliberately neutral between essentialist, dispositionalist, and powers-based
accounts of what modal properties are.

## Key Findings

**Models represent possibilities, not actuality directly.** Every scientific model — even
those with actual targets — represents a network of possibilities arising from dependence
structures among entities. Actual targets are a limiting case (they are also possible).

**Actual truthmakers for all modal claims.** Both model-system claims (claims about what
a model represents internally, e.g., "the frictionless-plane model has no friction") and
target-system claims (claims about what the model is supposed to represent, e.g., "a real
plane approximately exhibits frictionless behaviour") can have their truthmakers in the
actual world — located in the modal properties (dependences, dispositions, essential
relations) of actually existing entities.

**Fictional and idealised models are tractable.** "False" idealisations work because their
counterfactual structure is isomorphic to the counterfactual structure of actual phenomena
(Bokulich's account, endorsed by Tahko). Fictional models like Bohr's hydrogen atom —
which cannot be de-idealised back to quantum mechanics — still connect to actuality via the
isomorphism of counterfactual structure: the spectral-line predictions remain grounded in
actual atomic-level dependences.

**Counterlegal models are handled case-by-case.** Models that invoke metaphysically
impossible antecedents (e.g., "if diamond were not covalently bonded") are not necessarily
vacuously true. Many can be analysed by re-reading the antecedent as a claim about a
related actual phenomenon (e.g., "what we know about electrical conductors in general"),
and finding actual truthmakers there.

**Case study — superheavy elements.** The prediction that unbihexium (Z = 126) would have
a longer half-life than oganesson (Z = 118) is true, even though no unbihexium atoms exist,
because the truthmaker is the actual shell-model energy structure of nucleons — the same
structure that produces the observed "magic-number" stability in known elements like calcium.
The dependence structure (binding energies, closed shells) is actual and grounded in known
physics, so the counterfactual has actual truthmakers.

**Epistemological corollary.** The paper does not develop the epistemology of modal
modelling fully, but notes that it becomes a special case of the epistemology of modality.
Fischer's (2016, 2017) theory-based approach — inferring possibilities from a believed
theory — is compatible with and complementary to Tahko's truthmaking framework.

## Relevance

This paper is directly relevant to the Science toolkit on several dimensions:

1. **Modal grounding for causal edges** (`hypothesis:0004`, `question:0025`). The toolkit
   represents causal claims as graph edges bearing counterfactual content: "if X had not
   occurred, Y would not have occurred." Tahko's framework demands that every such claim
   be traceable to an actual dependence structure — not just to a modal claim about
   possibilities. This is the philosophical backing for why causal-estimand guardrails
   (`h04`) should require dependence-structure evidence: without an actual truthmaker, a
   causal edge is merely asserting a possibility without grounding.

2. **Patchwork of epistemic models** (`hypothesis:0007-working-model`). Tahko's view that
   each model represents a *network* of possibilities arising from a local dependence
   structure maps cleanly onto the toolkit's patches (epistemic neighborhoods). A patch IS
   the local dependence structure that grounds the modal claims of a set of propositions.
   The "modal properties of actual entities" = the actual edge dependencies recorded in a
   patch. The paper thus provides metaphysical support for treating patches as first-class
   epistemic objects (not derived from a global theory).

3. **Model-system vs. target-system claim distinction** (`question:0002-evidence-payload-schema`,
   new question). Tahko draws a sharp distinction between model-system claims (about what a
   model represents internally) and target-system claims (about the modelled phenomenon).
   In the toolkit's evidence schema, this distinction is currently absent: an LLM-generated
   claim about a theoretical framework and an empirical measurement of an actual system are
   tagged similarly. Tahko's framework implies these warrant different truthmakers and
   different propagation rules across patches.

4. **Inter-patch relations and counterfactual structure** (`question:0026`). Tahko's central
   mechanism — isomorphism of counterfactual structure between models and actual dependence
   structures — is a candidate formal basis for one type of inter-patch relation. Two patches
   whose counterfactual structures are isomorphic (in Bokulich's sense) support legitimate
   inference transfer without full reducibility. This is weaker than formal reduction but
   stronger than mere latent-axis similarity; it fills a gap in the inter-patch relation
   taxonomy posed by `question:0026`.

5. **Counterlegal modelling and exploratory hypotheses.** The paper's treatment of
   counterlegal models (with metaphysically impossible antecedents) is directly relevant to
   the toolkit's handling of exploratory/speculative hypotheses. Tahko's recommendation to
   analyse such models case-by-case, re-reading the antecedent as a claim about an actual
   phenomenon, aligns with the toolkit's proposal to flag such claims as `[SPECULATION]`
   pending identification of actual dependence-structure evidence.

6. **Cross-link: natural-systems project.** The superheavy-elements case study illustrates
   the toolkit's intended use pattern in natural-systems domains: modelling entities (e.g.,
   genes, disease mechanisms) whose properties are only partially characterised. Tahko's
   framework implies that the toolkit's disease-gene patches are legitimate epistemic objects
   as long as the propositions in each patch are anchored to actual dependence structures
   (co-occurrence, GWAS signals, pathway dependencies) — even if the underlying mechanisms
   are not yet synthesised. This connection warrants a note when the paper is promoted to
   science-commons.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Network of possibilities (model's target) | Patch (epistemic neighborhood) | A patch is the local dependence structure that grounds the modal claims of its propositions. |
| Modal properties of actual entities | Actual edge dependencies in a patch | The "actual" grounding required by Tahko is realized by empirical evidence nodes bearing on a patch edge. |
| Counterfactual structure of a model | Causal DAG / CPDAG structure | The model's counterfactual structure is isomorphic to an actual dependence structure — this is what causal discovery tries to recover. |
| Model-system claim | Claim about a model/theory (editorial provenance) | A claim like "the model predicts X" differs from "the system does X"; the former is a model-system claim. |
| Target-system claim | Empirical claim (empirical provenance) | A data-derived claim about an actual system; a different truthmaker class. |
| De-idealisation | Belief ceiling under ineliminable idealisation | When a model cannot be de-idealised, uncertainty representations should carry a calibration ceiling (connects to `h02`). |
| Truthmaker (entity in the actual world) | Evidence node bearing on a proposition | Tahko's truthmakers map onto the evidence nodes in the evidence graph: actual entities and their dependences. |
| Counterlegal model | Speculative/exploratory hypothesis | A hypothesis with metaphysically impossible antecedents; requires re-reading as a claim about actual phenomena before the toolkit can record a dependence anchor. |
| Island of stability case study | Prediction from a patch with novel entities | Modelling entities not yet synthesised (new disease subtypes, novel gene variants) is legitimate if grounded in actual dependence patterns from known entities. |

## Limitations

- The paper is squarely in philosophy of science / modal metaphysics and provides no
  operational guidance on how to represent dependence structures computationally. It does
  not address serialization, graph schemas, or evidence aggregation.
- The anti-Humean commitment (modal properties are objective, non-reducible to patterns of
  occurrent facts) is substantive and contested. Researchers working within a Humean or
  structural-realist framework may interpret the "truthmakers" differently — the paper
  acknowledges this and tries to remain neutral at the level of which specific modal
  metaphysics holds (essentialism vs. dispositionalism vs. powers), but the anti-Humean
  commitment is load-bearing and may not satisfy all readers.
- The paper's metaphysical focus deliberately excludes the epistemology of modal modelling:
  how we come to *know* the modal properties that serve as truthmakers is deferred to
  future work (Tahko Forthcoming, "Possibility Precedes Actuality", *Erkenntnis*). For
  the toolkit, this means the grounding question (what makes a claim justified) is not
  answered here — only the truthmaking question (what makes it true).
- The superheavy-elements case study is drawn from physics/chemistry. Biological and social
  models — where dependence structures are more complex, harder to specify, and often
  contested — are not analysed. The framework is plausibly extensible but requires more
  domain-specific work for the natural-systems use case.
- The treatment of counterlegal and counterpossible models is deliberately cursory
  (acknowledged as a hard case). The toolkit will encounter such models (e.g., "if gene X
  were not expressed") and will need a more detailed operationalisation than "handle
  case-by-case."

## Model / Tool Availability

No software artifacts. This is a philosophical paper. Open access under CC BY 4.0;
full text at https://doi.org/10.1007/s11229-023-04063-z.

## Follow-up

- Tahko (Forthcoming), "Possibility Precedes Actuality", *Erkenntnis* (
  https://doi.org/10.1007/s10670-022-00518-w): the companion epistemology paper; directly
  relevant for how the toolkit should justify its modal claims, not just ground them.
- Fischer (2016), "A Theory-based Epistemology of Modality", *Canadian Journal of
  Philosophy*: a modal epistemology compatible with Tahko's truthmaking framework;
  relevant to how the toolkit can infer possibilities from theories.
- Bokulich (2011), "How Scientific Models Can Explain", *Synthese*: Tahko's main anchor
  for the isomorphism-of-counterfactual-structure account; deeper treatment of fictional
  and explanatory models.
- Open question raised by this paper: should the toolkit's evidence schema explicitly tag
  model-system claims separately from target-system claims, given that their truthmakers
  are structurally different? → see new `question:0027-model-system-vs-target-system-claims`
