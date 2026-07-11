---
kind: paper
title: External Validity
status: active
paper_kind: literature-review
created: '2026-07-10'
updated: '2026-07-10'
id: paper:Findley2021
ontology_terms: []
dataset_usage: []
source_refs:
- cite:Findley2021
related:
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- question:0001-bioinformatics-generalizability
- question:0003-causal-synthesis-guardrails
- question:0013-robustness-reproducibility-evaluation
---

# External Validity

- **Authors:** Michael G. Findley, Kyosuke Kikuta, Michael Denly
- **Year:** 2021
- **Journal:** Annual Review of Political Science
- **DOI/URL:** https://doi.org/10.1146/annurev-polisci-041719-102556
- **BibTeX key:** Findley2021
- **Source:** PDF

## Key Contribution

Findley, Kikuta, and Denly provide a systematic review and conceptual synthesis of external validity in social science, arguing that the field's obsession with internal validity (causal identification) has come at the cost of generalized knowledge [@Findley2021].
The paper extends the classical UTOS framework (units, treatments, outcomes, settings) into M-STOUT by adding mechanisms and time as first-class external validity dimensions [@Findley2021].
It proposes three evaluative criteria — model utility, scope plausibility, and specification credibility — and provides a formal decomposition of external validity bias into sample selection bias and variable selection bias [@Findley2021].

## Methods

The paper combines a systematic literature review with a content analysis of over 1,000 randomly sampled articles from 12 leading social science journals (including American Political Science Review, American Economic Review, and American Journal of Sociology), coded for how they address external validity [@Findley2021].
Formal results include a bias-decomposition framework: the sample average treatment effect (SATE) equals the population average treatment effect (PATE) plus sample selection bias (bP), and when variables differ across contexts a variable selection bias term (bV) also applies [@Findley2021].
The conceptual framework distinguishes generalizability (sample ⊆ population; S ⊆ P) from transportability (sample from a different population; S ⊄ P) and defines population average treatment effect (PATE) versus target population average treatment effect (TATE) as the inferential targets for each [@Findley2021].

## Key Findings

About 65% of surveyed articles mention external validity in some form, but only an exceptional few contain a dedicated discussion; most inferences are incomplete or inaccurate [@Findley2021].
Both experimentalists and observationalists fail at external validity in complementary ways: experimentalists largely ignore it (relying on internally valid but narrow samples), while observationalists have a false sense of security (believing large-N or TSCS data automatically confers external validity) [@Findley2021].
The formal decomposition shows that external validity bias can be as severe as internal validity bias; the SATE departs from the PATE by bP, which grows with effect heterogeneity between included and excluded units and with the fraction of missing units [@Findley2021].
Variable selection bias bV arises when operationalizations of treatment or outcome in the sample do not match those of theoretical interest, a common but underappreciated problem [@Findley2021].
The three evaluative criteria distill the literature into an assessment checklist: (1) model utility requires a clearly specified mechanism with appropriate abstraction; (2) scope plausibility requires prespecified theoretical and accessible populations across all M-STOUT dimensions, with causal interaction between M and STOUT articulated; (3) specification credibility requires a falsifiable theory and research design, preregistration of transport claims, credible synthesis, and explicit discussion of validity threats [@Findley2021].
The time dimension is especially underappreciated: credible external validity requires acknowledging that treatment effects, population composition, and confounders may all shift over time, and that the ultimate target population of any study is some future state [@Findley2021].

## Relevance

This paper is directly relevant to how the Science toolkit should represent and check the transport of evidence across contexts.
The generalizability/transportability distinction maps onto a gap in the current evidence-payload schema: payloads record source population and study design but do not require explicit notation of whether an inference is generalizability-type (S ⊆ P) or transportability-type (S ⊄ P_target), nor do they require an explicit PATE vs. TATE estimand declaration.
H04 (causal-estimand guardrails) already requires target population, causal contrast, and transport or exchangeability assumptions before evidence can strengthen causal propositions; Findley et al. sharpen what "transport assumptions" should cover — specifically, causal interaction across M-STOUT dimensions, prespecification of the theoretical and accessible populations, and acknowledgment of time-dependent mechanism instability [@Findley2021].
H02 (rich evidence payloads) benefits from the M-STOUT vocabulary as a principled set of dimensions to represent in payload metadata beyond the estimand fields already required.
Q01 (bioinformatics generalizability) asks exactly the question this paper helps answer at the conceptual level: do findings from replication-crisis fields transport to genomics, and what would rigorous transportability reasoning look like?

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Generalizability (S ⊆ P) | Same-population evidence scope | Payloads from the same source population; weaker transport assumptions needed. |
| Transportability (S ⊄ P_target) | Cross-context evidence transport | Requires explicit target-population field, exchangeability assumptions, and mechanism invariance claim. |
| M-STOUT dimensions | Evidence-payload metadata axes | Mechanisms, Settings, Treatments, Outcomes, Units, Time — each is a potential confound or scope boundary. |
| PATE / TATE | Target estimand in causal guardrails | H04 already requires this; Findley et al. formalize the bias that arises when PATE ≠ SATE. |
| Sample selection bias bP | Source–target population mismatch flag | Should be a named warning class in the guardrail (cf. H04 `source-target-mismatch`). |
| Variable selection bias bV | Construct-validity drift | Related to Q15 (claim-operationalization drift): operationalization mismatch between sample and target is a form of variable selection bias. |
| Model utility (mechanism abstraction) | Mechanism-clarity metadata | Evidence that doesn't specify the active causal mechanism provides weaker transport warrant. |
| Scope plausibility (prespecified populations) | Evidence-scope preregistration | Science payloads should distinguish ex-ante scope declarations from retrofitted population definitions. |
| Specification credibility | Falsifiability of transport claims | External validity inferences should be falsifiable and preregistered, not only post-hoc. |
| Time dimension of M-STOUT | Temporal scope of evidence | Evidence payloads should record the time period of the source study and whether mechanism stability over time was assessed. |

## Limitations

The evaluative criteria (model utility, scope plausibility, specification credibility) are qualitative checklists; the paper does not provide a formal scoring procedure or show that compliance actually reduces external validity bias in practice [@Findley2021].
The evidence base for the survey (over 1,000 articles coded) comes entirely from social science journals, primarily political science and economics; direct applicability to computational biology or genomics pipelines requires a separate transportability argument.
The formal decomposition abstracts from measurement error, interference (SUTVA violations), and time-varying confounding, which are important in computational biology settings [@Findley2021].
The paper identifies time as an under-theorized dimension but does not provide a formal model of mechanism drift or time-heterogeneous treatment effects.
No software artifact is released.

## Model / Tool Availability

No software artifact is released with this paper.

## Follow-up

Add a new science-meta question on how Science should represent external validity metadata (generalizability vs. transportability type, M-STOUT scope, mechanism-invariance claims) in evidence payloads.
Examine whether H04's required transport/exchangeability assumptions field should be expanded to distinguish sample-selection bias from variable-selection bias paths.
Check whether Q15 (claim-operationalization drift) and this paper's variable-selection bias concept can be unified into a single schema requirement.
Consider adding `temporal_scope` and `mechanism_invariance_claim` as optional but recommended evidence-payload fields.
