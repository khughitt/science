---
id: paper:Tahko2023
overlay_of: paper:Tahko2023
pin_version: "1.0.0"
status: active
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
created: "2026-07-10"
updated: "2026-07-10"
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
