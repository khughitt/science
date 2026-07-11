---
id: paper:Cornelissen2025
kind: paper
title: What Are Mechanisms? Ways of Conceptualizing and Studying Causal Mechanisms
status: active
paper_kind: literature-review
ontology_terms: []
dataset_usage: []
source_refs:
- cite:Cornelissen2025
related:
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- hypothesis:0007-working-model
- question:0003-causal-synthesis-guardrails
- question:0010-causal-graph-construction-pipeline
- question:0002-evidence-payload-schema
created: '2026-07-10'
updated: '2026-07-10'
---
# What Are Mechanisms? Ways of Conceptualizing and Studying Causal Mechanisms

- **Authors:** Joep P. Cornelissen and Mirjam Werner
- **Year:** 2025
- **Journal:** Organizational Research Methods
- **Volume/Pages:** 29(2) 147–176
- **DOI:** https://doi.org/10.1177/10944281251318727
- **BibTeX key:** Cornelissen2025
- **Source:** PDF

## Key Contribution

Cornelissen and Werner provide a meta-theoretic review and synthesis of how "causal mechanism" is conceptualized and studied across management research, identifying three distinct methodological perspectives — interventionist, contextual, and constitutive — each grounded in different ontological commitments and producing different kinds of mechanism-based explanations [@Cornelissen2025].
The paper argues that recognizing these differences is a precondition for epistemological pluralism: researchers who understand the inferential strengths and characteristic biases of all three perspectives can engage in "perspective taking" that strengthens their own mechanism-based inquiries.
The synthesis offers methodological guidance for each perspective's inferential challenges rather than promoting one epistemology over another.

## Methods

Meta-theorizing approach: the authors first reviewed methodological commentaries and philosophy-of-science writings on causal mechanisms, catalogued definitions, and snowballed citations to build a preliminary typology of three perspectives.
They then searched five top management journals (Academy of Management Journal, Academy of Management Review, Administrative Science Quarterly, Journal of International Business Studies, Organization Studies) for articles referencing "mechanism/mechanical/mechanis*/drive*/motor*" over 2020–2023, yielding a corpus of 210 articles.
These were coded against the three-perspective typology and used to validate categories and provide illustrative examples; the synthesis was written at the level of methodology (coherent epistemological assumptions + associated research designs + inferential techniques), not individual methods.

## Key Findings

Three perspectives were identified, each with distinct definitions, methods, and inferential challenges:

**Interventionist perspective** (n = 123 articles, most prominent): mechanisms are functional, observable causal relationships — mediating variables that link a manipulated cause to an effect.
Research design involves experiments or quasi-experiments (propensity matching, IV, regression discontinuity, DiD) to isolate the causal path.
Characteristic inferential challenge: microscopic bias — presupposing causal sufficiency of a small variable set, which may omit the broader causal machinery and risk false positives.

**Contextual perspective** (n = 61 articles): mechanisms are situated causal processes inferred backward from an observed outcome via case study or comparative qualitative methods.
Inferential steps involve case description → analytical coding of conditions and transitions → abductive theorization of a generative mechanism.
Characteristic challenge: surface contingency — observed event sequences are not self-evidently causal; researchers may stop at "if–then" propositions instead of reaching an underlying generative mechanism.

**Constitutive perspective** (n = 26 articles): mechanisms are integrative analytical constructs that bridge micro and macro levels of analysis (the "bathtub" model), judged by explanatory parsimony and generality.
Methods include longitudinal designs, formal theory, and simulation; data are translated into covering "transformational" mechanisms.
Characteristic challenge: stylized projection — portable "plug-and-play" integrative mechanisms (e.g., social contagion) may gloss over the active organization of component parts that actually constitutes the phenomenon.

**Epistemological pluralism / perspective taking**: each perspective has distinct inferential blind spots; cross-perspective reflexivity can offset these.
An interventionist researcher informed by the constitutive perspective becomes alert to nonlinear and reciprocal causal organization; informed by the contextual perspective, they counter the tendency to select only readily manipulable variables.

## Relevance

This paper is directly relevant to how the Science toolkit represents and validates causal evidence. The three perspectives map onto three different evidence modalities the toolkit encounters and must handle correctly:

The interventionist perspective corresponds to the kind of evidence that H04 guardrails target: quantitative estimates of mediating mechanisms (effect sizes, regression coefficients, causal inference outputs). The paper explains why such estimates require full estimand specification (target population, causal contrast, aggregation rule) before they can strengthen a causal proposition — exactly the H04 claim [@Cornelissen2025]. The "microscopic bias" the paper identifies is the mechanism-level analogue of estimand mismatch: a mediation estimate may identify a proxy variable, not the full causal machinery.

The contextual perspective corresponds to qualitative mechanism evidence: process-tracing outputs, case-based inference, abductive generative mechanism models. The toolkit's evidence payload schema (`question:0002-evidence-payload-schema`) currently lacks mechanism-type fields that would distinguish this evidence modality from quantitative associations. The paper's "gerundive mechanism" critique — nominalized constructs that are rhetorical rather than substantive — is a precise risk for any knowledge graph that allows free-text mechanism labels.

The constitutive perspective corresponds to multi-level analytical models: simulation outputs, formal theory schemes, Coleman's bathtub representations. The toolkit's causal graph construction pipeline (`question:0010-causal-graph-construction-pipeline`) and the h00 working model's patch-federation design (at the micro-macro / patch–project–project-collection levels) instantiate constitutive reasoning. The paper's warning about stylized integrative mechanisms that project a covering model without "bottoming out" in component-part organization is directly applicable to Science's patch-level model-building.

The epistemological pluralism argument supports the toolkit's heterogeneous evidence synthesis goal: it is not sufficient to accept only interventionist evidence for causal claims — contextual and constitutive evidence bear on different aspects of a causal mechanism and should strengthen different edges or evidence layers, not the same proposition as if they were the same type of evidence.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Interventionist mechanism (mediating variable, RCT/quasi-experiment) | Quantitative causal evidence node | Requires estimand, effect measure, and target population metadata before strengthening a causal edge (H04) |
| Contextual mechanism (situated process, case-inferred) | Qualitative process/mechanism evidence strand | Needs mechanism-type label in evidence payload (`question:0002-evidence-payload-schema`) to distinguish from associational evidence |
| Constitutive mechanism (integrative analytical model, micro-macro) | Multi-level causal model / h00 patch at ladder level L3–L4 | Connects to h00 patch-federation across project levels; risk of stylized projection applies to LLM-elicited priors |
| Epistemological pluralism | Heterogeneous evidence synthesis across evidence types | Supports evidence-type labeling so different mechanism perspectives update different graph layers |
| Microscopic bias (interventionist) | Causal edge scope underspecification | Risk of modeling only manipulable proxies rather than the broader causal machinery |
| Gerundive mechanism labels | Nominalized mechanism entities in KG | Risk of rhetorical vs. substantive mechanism claims; validates need for operationalization checks |
| Perspective taking (cross-paradigm reflexivity) | Cross-evidence-type triangulation | Cornelissen and Kaandorp (2023) call this "causal triangulation"; supports multi-perspective evidence bundles |
| Cartwright's evidential diversity | Evidential pluralism in evidence payload | Directly cited; supports heterogeneous evidence type requirements |

## Limitations

The paper is grounded in management and organizational research; its typology may require adaptation for natural-science contexts where experimental and mechanistic standards differ (e.g., biology has a richer tradition of constitutive decomposition than management's Coleman-bathtub constitutive approach).
The three perspectives are analytically distinct but empirically overlapping; the paper acknowledges that researchers often mix elements, making precise corpus categorization challenging.
The perspective-taking proposal remains programmatic — the paper concedes "this is somewhat speculative at this point (as the synthesis has not been used yet)."
No formal operationalization, scoring, or weighting criteria are provided for combining evidence across perspectives; this limits direct implementation in a computational evidence model.
The corpus covers 2020–2023 and five journals; more recent or interdisciplinary work may not be represented.

## Model / Tool Availability

No software artifact. The supplementary Table 3 in the paper provides coded study examples across the three perspectives that could serve as a ground-truth coding benchmark for mechanism-type classification tasks.

## Follow-up

- Cornelissen and Kaandorp (2023) — "Towards stronger causal claims in management research: Causal triangulation instead of causal identification" (JMS) — is the direct methodological companion and elaborates the perspective-taking approach as "causal triangulation."
- Cartwright (2021) — "Rigour versus the need for evidential diversity" (Synthese) — is a foundational reference for the epistemological pluralism argument and connects to the dappled-world / patchwork evidence literature directly relevant to Science's design.
- Hedström and Ylikoski (2010) — "Causal mechanisms in the social sciences" (Annual Review of Sociology) — provides the analytical sociology background for the constitutive perspective.
- New questions raised for the project: whether the evidence payload schema should carry a `mechanism_perspective` field (interventionist / contextual / constitutive) to allow perspective-aware guardrails, and how cross-perspective triangulation should update causal belief.
