---
id: paper:Ghins2011
kind: paper
title: Scientific Representation and Realism
status: active
paper_kind: ''
ontology_terms: []
dataset_usage: []
source_refs:
- cite:Ghins2011
related:
- hypothesis:0007-working-model
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- question:0019-powers-vs-laws-causal-edge-ontology
- question:0025-causal-edge-modal-typing
- question:0011-graph-valued-synthesis-artifacts
- question:0029-scientific-representation-grounding-in-graph
created: '2026-07-10'
updated: '2026-07-10'
---
# Scientific Representation and Realism

- **Authors:** Michel Ghins
- **Year:** 2011
- **Journal:** Principia: an international journal of epistemology
- **Volume/Issue/Pages:** 15(3): 461–474
- **DOI/URL:** https://doi.org/10.5007/1808-1711.2011v15n3p461
- **BibTeX key:** Ghins2011
- **Source:** PDF

## Key Contribution

Ghins argues that scientific models achieve contact with reality not through structural
correspondence alone (isomorphism or homomorphism), but through the truth of
*ontic judgements* — first-person predicative acts that attribute properties to real
phenomenal targets [@Ghins2011].
He introduces a five-level model-theoretic hierarchy (phenomena → phenomenal structures
→ data models → empirical substructures → embedding theories) and uses it to diagnose
and rebut van Fraassen's "Loss of Reality Objection": the claim that abstract mathematical
models only represent phenomena *as described*, never phenomena *as they are* [@Ghins2011].
The paper concludes that scientific realism — including belief in unobservable entities —
is grounded in the variety and concordance of independent measurement procedures, and that
true judgements are the soil on which all representational activity rests [@Ghins2011].

## Methods

The paper is a work of analytic philosophy of science; the primary method is conceptual
analysis and critical engagement with van Fraassen's *Scientific Representation* (2008)
[@Ghins2011].
Ghins reconstructs the representational démarche of science as a five-step chain: an
observer abstracts a *phenomenal structure* (a system of perceived properties and relations)
from an observable phenomenon; measurement instruments generate a *data model*; scientists
smooth discrete measurements into a *surface model*; an *empirical substructure* is
identified within a theoretical model that is homomorphic to the data model; and the phenomenon
is thereby embedded in the *embedding theory* [@Ghins2011].
The argument against van Fraassen's pragmatic dissolution of the Loss of Reality Objection
proceeds by distinguishing between representational *success* (the representor correctly
denotes a target) and representational *correctness* (the representor accurately
characterizes the target's properties), and showing that both conditions rest on the truth
of ontic judgements rather than on pragmatic coherence alone [@Ghins2011].
Ghins adopts a mild correspondence view of truth — propositions are true in virtue of
real phenomenal entities that serve as their truth-makers — while explicitly declining to
commit to any elaborated correspondence theory of truth [@Ghins2011].

## Key Findings

Representation in science is irreducibly perspectival: the scientist abstracts a phenomenal
structure from a phenomenon under a chosen vantage point, so there is no single correct
representation of any given phenomenon [@Ghins2011].
The "Loss of Reality Objection" arises within van Fraassen's own framework because he denies
a correspondence view of truth and treats phenomena as the targets of representation; Ghins
avoids the objection by restricting representation to structures (not phenomena) and grounding
contact with reality in the truth of ontic judgements about phenomena [@Ghins2011].
Van Fraassen's pragmatic dissolution — that adequacy to phenomena and adequacy to
phenomena-as-represented are identical for the observer — fails because it collapses
a meaningful distinction: judgements, unlike representations, can be true of real entities
independently of any particular vantage point [@Ghins2011].
For scientific realism, Ghins argues that entity realism and statement realism stand or fall
together: to assert that unobservable entities exist is already to assert that some judgements
about their properties are true [@Ghins2011].
The epistemic warrant for belief in real properties — observable or unobservable — is the
variety and concordance of independent measurement procedures; diverse methods yielding
convergent quantitative results justify the claim that the measured entity really possesses
the measured property [@Ghins2011].
Emphasizing models and representations to the exclusion of judgements (the "representational
view of theories") generates the Loss of Reality problem; the solution is to restore
true judgements as the primary locus of empirical content [@Ghins2011].

## Relevance

The paper is directly relevant to the Science working model (`hypothesis:0007-working-model`)
because that model describes how epistemic patches — local graphical representations
surrounding hypotheses and evidence clusters — are supposed to relate to real-world entities.
Ghins' five-level hierarchy (phenomena → phenomenal structures → data models → empirical
substructures → theory) provides a philosophical scaffold for asking at which layer
Science's propositions, evidence payloads, and graph edges are operating, and what truth
conditions they carry.
The paper's central distinction between representational *success* (a model correctly
denotes a target) and representational *correctness* (a model accurately characterizes
the target's properties) is directly actionable for Science: proposition nodes in the
knowledge graph need to distinguish whether they are asserting that an edge denotes
a real relationship versus asserting that the edge accurately describes the relationship's
magnitude or mechanism.
Ghins' mild correspondence view of truth, grounded in ontic judgements rather than
structural isomorphism, bears on the debate about whether the toolkit should adopt a
structural-realist or a more robustly realist stance toward its causal graph; it supports
the more robustly realist direction where judgements, not structures, carry truth value.
The "variety and concordance of independent measurements" argument for realism about
unobservable entities maps directly onto Science's evidence calibration work
(`hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`): corroboration by
independent sources is the epistemic warrant for belief, and multi-source evidence
triangulation is precisely what Science's evidence payload schema is designed to support.
The irreducibility of the perspectival/indexical ingredient in representation corresponds
to Science's provenance model: every evidence node should record the agent, vantage point,
and measurement procedure, because representations are not "from nowhere".
The paper is also tangentially relevant to `question:0019-powers-vs-laws-causal-edge-ontology`
because Ghins argues that no unique metaphysical "butchering of nature at its joints" is
justified — the plural perspectives available on phenomena support a modest realism about
real properties without committing to a single fundamental ontology of powers or laws.
For `question:0025-causal-edge-modal-typing`, Ghins notes that moving from phenomenal
to theoretical properties is a difference of degree, not nature — this supports treating
causal-edge typing as a continuum from observational-association to theoretical-causal
rather than a sharp categorical boundary.
Cross-links to natural-systems project: the five-level representation hierarchy is
applicable to multi-omics integration workflows, where measured molecular properties
(gene expression levels, protein abundances) map to Ghins' data-model layer, biological
mechanisms map to empirical-substructure level, and pathway models map to embedding-theory
level; note for future commons-promotion.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Phenomenal structure | Evidence source (first-order observation) | Abstracted property-relation structure extracted from an observed phenomenon; the first structural layer before model construction |
| Data model | Evidence payload / measurement record | Measurement outputs numerically assigned to properties via instrument procedures; corresponds to Science's evidence graph node with measurement metadata |
| Surface model | Smoothed or aggregated evidence | Continuous curve fitted to discrete measurement points; analogous to aggregated evidence signals in Science |
| Empirical substructure | Hypothesis-linked support structure | Part of a theoretical model homomorphic to the data model; the piece of a patch that embeds observable evidence |
| Embedding theory | Working model patch (h00) | Encompassing theoretical frame; a patch as a named epistemic neighborhood in Science |
| Ontic judgement | Proposition node | Predicative first-person act attributing a property to a real entity; the basic unit of truth-bearable content in Science's graph |
| Representational success | Evidence-to-target denotation | Whether a model correctly picks out its intended real-world referent |
| Representational correctness | Proposition truth-value / confidence | Whether the model accurately characterizes the target's properties; maps to the belief value on a proposition edge |
| Perspectival / indexical ingredient | Provenance (agent, vantage, method) | Irreducible first-person component of any representation; captured in Science's provenance type and PROV agent fields |
| Variety and concordance of independent measurements | Multi-source evidence corroboration | Epistemic warrant for realist claims; corresponds to Science's evidence aggregation and independence-reduction machinery |
| Loss of Reality Objection | Abstract model grounding problem | How do graph structures in Science connect to real-world entities rather than only to other representations? |

## Limitations

The paper engages primarily with van Fraassen's (2008) framework; the response to
structural realism positions (e.g. French and Ladyman) is not addressed [@Ghins2011].
Ghins' "mild correspondence view of truth" is asserted rather than rigorously defended;
he acknowledges that no satisfactory correspondence theory of truth has yet been proposed
and treats this as a non-objection [@Ghins2011].
The five-level hierarchy is presented informally and its generalizability beyond
measurement-based physical science is not demonstrated; application to
computational/agent-based knowledge representation requires additional scaffolding.
The perspectival ingredient in model construction is noted but not developed into a
formal theory of perspective-relative truth conditions, which is what Science would need
for rigorous provenance-qualified propositions.
The argument for scientific realism about unobservables via concordance of measurements
is sketched rather than defended against underdetermination objections.

## Model / Tool Availability

This is a philosophical paper; no software, dataset, or computational artifact is released.

## Follow-up

Read van Fraassen (2008) *Scientific Representation: Paradoxes of Perspective* for the
full statement of the Loss of Reality Objection and the empirical-stance position that
Ghins is engaging with.
Read French and Ladyman on structural realism to situate Ghins' modest-realism position
within the broader realism debate and evaluate its implications for Science's graph model.
Consider whether Science's proposition layer should explicitly distinguish between
"denotation-success" metadata (does this proposition node correctly pick out a real
relationship?) and "characterization-correctness" metadata (does it accurately describe
the relationship's properties?), following Ghins' success/correctness distinction.
Consider drafting a question about whether the Science working model implicitly commits
to structural realism, and what the implications are for how truth-conditions are assigned
to proposition and edge nodes.
The five-level hierarchy could be used to audit Science's evidence schema: map each
evidence node type to its level in the hierarchy and check that the schema preserves
provenance across levels.
