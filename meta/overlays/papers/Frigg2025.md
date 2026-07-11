---
id: paper:Frigg2025
overlay_of: paper:Frigg2025
pin_version: "1.0.0"
status: active
source_refs:
- cite:Frigg2025
related:
- hypothesis:0007-working-model
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- question:0010-causal-graph-construction-pipeline
- question:0012-agent-tool-kg-operations
created: "2026-07-10"
updated: "2026-07-10"
---
# Models in Science (Stanford Encyclopedia of Philosophy)

- **Authors:** Roman Frigg and Stephan Hartmann
- **Year:** 2025 (first published 2006; substantive revision April 2, 2025)
- **Venue:** Stanford Encyclopedia of Philosophy (SEP)
- **URL:** https://plato.stanford.edu/entries/models-science/
- **BibTeX key:** Frigg2025
- **Source:** PDF (SEP entry saved as PDF, 2026-07-09)

## Key Contribution

This SEP entry is the canonical philosophical reference on scientific models, synthesizing the
entire philosophical literature across four main problem areas: semantics (how models
represent), ontology (what models are), epistemology (how models produce knowledge), and
the relationship between models and theories. Its central claim is that models are not
subsidiary formal objects but autonomous epistemic agents that mediate between theory and
world, and that real science operates as a patchwork of locally-valid, domain-specific models
rather than a unified theory of everything. The entry provides the conceptual vocabulary
and philosophical grounding for the Science toolkit's own "federated patchwork of epistemic
models" working model (`hypothesis:0007-working-model`).

## Methods

This is a philosophical survey entry (encyclopedia review), not primary empirical research.
It reviews and synthesizes literature across the philosophy of science, covering:
- A taxonomy of model types under the semantics/representation dimension (Section 1): scale
  models, analogical models, idealized models (Aristotelian/Galilean), toy and minimal models,
  phenomenological models, exploratory models, surrogate models, models of data.
- An ontological taxonomy (Section 2): physical/material objects; fictional and abstract objects
  (fiction view, pretense theory, artifactualism); set-theoretic structures (semantic view,
  Suppes tradition); descriptions and equations (direct-representation view).
- Epistemological analysis (Section 3): how we learn about models (construction + manipulation),
  how that knowledge transfers to targets (surrogative reasoning), explanatory function
  (Woodward's counterfactual account, Cartwright's simulacrum, Batterman/Rice minimal models,
  Bokulich's fictional explanations), understanding (Elgin's "felicitous falsehoods", de Regt's
  intelligibility), and additional cognitive roles including modeling trade-offs (Levins 1966).
- Models vs. theories (Section 4): the spectrum from subsidiary (syntactic/semantic view) to
  autonomous (interpretative models, models as mediators).
- Broader philosophy-of-science implications (Section 5): models and scientific realism,
  ceteris paribus laws, and the patchwork/reductionism debate.

## Relevance

This entry is a **central reference** for science/meta because the Science toolkit's working
model (`hypothesis:0007-working-model`) explicitly adopts the patchwork picture:
"Knowledge is not one graph … but a federated patchwork of small epistemic neighborhoods."
Frigg and Hartmann's entry supplies the authoritative philosophical backing for this design
choice and sharpens several toolkit concepts:

1. **Patchwork legitimacy**: Cartwright/Hacking's patchwork-of-models conclusion (§5.2)
   justifies Science's patch-level granularity: patches need not reduce to a global theory;
   local validity in a domain suffices. The toolkit's federation via shared ontology + latent
   axes maps onto the weak inter-model relations (structural, "story") Frigg/Hartmann cite as
   replacing deductive reduction.

2. **Representation and the object/meta layer split**: The entry's treatment of surrogative
   reasoning (§3) and the representation relation between model and target directly
   underpins Science's `object_layer` vs. `meta_layer` distinction — the object layer is the
   target system; the meta layer contains claims/evidence/belief about relations in the
   target.

3. **Idealization, approximation, and calibration** (`hypothesis:0002`): The entry's
   detailed taxonomy of idealizations clarifies what "calibration" means in the toolkit. A
   model that is necessarily idealized cannot be expected to produce perfectly calibrated
   belief unless the idealization is controlled. The ineliminable-idealization cases (Batterman)
   set a ceiling: de-idealization loops are not always available, and toolkit uncertainty
   representations should reflect this.

4. **Causal models and mediators** (`hypothesis:0004`, `question:0010`): Interpretative
   models and mediating models (§4.2) are exactly the causal DAG patches in Science —
   local, constructed, theory-underdetermined, requiring domain knowledge to build.
   The entry confirms that causal-estimand guardrails are philosophically appropriate:
   a model does not "come out of" theory; additional modeling decisions always mediate.

5. **Agent tools and elicited beliefs** (`question:0012`): The epistemological section on
   learning through model construction + manipulation (§3.1) mirrors how Science's
   agent/tool KG operations work: an LLM-assisted construction step that is itself
   epistemically informative, not just a data-lookup.

6. **Trade-offs and model selection**: Levins's (1966) irreducible trade-offs among accuracy,
   generality, and simplicity reappear in Science's ladder (L0–L4): each rung sacrifices one
   dimension to gain another, and no rung is universally superior — consistent with the
   toolkit's decision to let evidence move patches up the ladder rather than mandating a
   single level.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Patchwork of models (Cartwright/Hacking §5.2) | `Patch` (epistemic neighborhood) | The SEP entry names and justifies the core metaphor in `h00`. |
| Models as mediators / autonomous agents (§4.2) | Patch as first-class entity, not derived from theory | A patch is built, not deduced; toolkit agent-tools do the construction. |
| Surrogative reasoning (Swoyer 1991, §3) | Object layer → meta layer reasoning | We study the graph to learn about the target system. |
| Representational model vs. target system (§1) | `object_layer` entities + their relations | The target is the world; the patch is the model of it. |
| Idealization, de-idealization (§1) | Uncertainty representation + belief ceiling | Ineliminable idealizations put a ceiling on calibration achievable by correction. |
| Models of data (Suppes 1962, §1) | `data/` payload → evidence node | Raw data must be regimented before being evidence; the toolkit's evidence ingestion step. |
| Interpretative / mediating model (§4.2) | Causal DAG patch | Underdetermined by theory; requires domain knowledge + explicit modeling choices. |
| Levins trade-offs (§3.5) | L0–L4 ladder trade-offs | No single ladder level maximizes all epistemic desiderata simultaneously. |
| Fiction view / pretense theory (§2.2) | Provenance type `editorial` | AI-drafted or expert-elicited patches are analogous to fictional constructs: they may be instrumentally useful without being literally true. |
| Perspectival realism (§5.1) | Multi-patch federation | Different patches represent the same system from different perspectives without mutual inconsistency forcing a single realist commitment. |

## Model / Tool Availability

No software artifacts. SEP entry is freely available at
https://plato.stanford.edu/entries/models-science/ (substantive revision 2 April 2025).
See also the companion SEP entry "Scientific Representation" by Nguyen and Frigg.

## Follow-up

- Nguyen and Frigg, *Scientific Representation* (Cambridge UP, 2022): the representation
  relation in depth — the SEP entry defers the core semantics question here.
- Cartwright (1999), *The Dappled World*: primary source for the patchwork/ceteris paribus
  picture referenced in §5.2.
- Morgan and Morrison (1999), *Models as Mediators*: the foundational collection on models
  as autonomous agents.
- Elgin (2017), *True Enough*: the "felicitous falsehoods" / understanding-not-truth position
  on models and epistemic goals.
- Open question: How does the toolkit's dual common space (ontology + latent axis) relate to
  the inter-model "stories" and structural relations Frigg/Hartmann cite as alternatives to
  full reduction? This is worth a dedicated question entity.
