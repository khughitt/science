---
kind: paper
title: From Weight of Evidence to Quantitative Data Integration using Multicriteria
  Decision Analysis and Bayesian Methods
status: active
created: '2026-05-05'
updated: '2026-07-08'
id: paper:Linkov2017
ontology_terms: []
source_refs:
- cite:Linkov2017
related:
- topic:bayesian-methods-continuous-belief
---

# From Weight of Evidence to Quantitative Data Integration using Multicriteria Decision Analysis and Bayesian Methods

- **Authors:** Igor Linkov, Olivia Massey, Jeff Keisler, Ivan Rusyn, and Thomas Hartung
- **Year:** 2015 final journal publication; 2017 PMC manuscript availability
- **Journal:** ALTEX
- **DOI/URL:** https://doi.org/10.14573/altex.1412231
- **BibTeX key:** Linkov2017
- **Source:** PDF

## Key Contribution

Linkov et al. argue that weight-of-evidence assessment should not be discarded because of vague qualitative usage, but should be redirected toward quantitative, transparent data integration [@Linkov2017].
The paper connects modern evidence-integration debates back to I. J. Good's Bayesian definition of weight of evidence as the logarithm of a Bayes factor [@Linkov2017].
It proposes Bayesian methods as the principled target and multicriteria decision analysis as a practical proxy when toxicological evidence is heterogeneous, sparse, or difficult to model probabilistically [@Linkov2017].

## Methods

The paper is a methodological commentary and synthesis rather than an empirical validation study [@Linkov2017].
It reviews criticisms of colloquial weight-of-evidence practice, especially the National Research Council's critique of vague use in EPA IRIS assessments [@Linkov2017].
It summarizes a taxonomy of weight-of-evidence methods ranging from simple evidence listing through best professional judgment to quantitative statistical and decision-analytic methods [@Linkov2017].
It then sketches Bayesian updating, Bayes factors, Bayesian belief networks, decision trees, integrated testing strategies, and MCDA as candidate formalisms for integrating diverse lines of toxicological evidence [@Linkov2017].

## Key Findings

The authors distinguish criticism of vague "colloquial" weight-of-evidence labels from criticism of evidence integration itself, arguing that some integration step is unavoidable in hazard assessment [@Linkov2017].
Bayesian weight of evidence provides an explicit prior-to-posterior update mechanism and makes evidence strength additive when expressed as the logarithm of the Bayes factor [@Linkov2017].
Existing Bayesian and Bayesian-network applications in integrated testing strategies show that quantitative weight-of-evidence workflows can be transparent and reproducible, though often constrained by data limitations [@Linkov2017].
MCDA can combine evidence-source qualities such as reliability, specificity, relevance, and precision into explicit weights, then aggregate source-level estimates or hypothesis-support scores [@Linkov2017].
The authors argue that MCDA may approximate Bayesian integration in simple cases and may be more practical when full probability models or expert elicitations are infeasible [@Linkov2017].
They emphasize that regulatory acceptance depends on flexibility, transparency, consistency, reproducibility, and objectivity, not on retaining the term "weight of evidence" [@Linkov2017].

## Relevance

This paper directly supports Science's Batch 2 theme by treating data integration as an explicit operator over heterogeneous evidence, not as an informal narrative judgment [@Linkov2017].
It reinforces the Batch 1 evidence-payload schema because useful aggregation requires recording evidence source, comparison target or hypothesis, assumptions, data quality criteria, uncertainty, and aggregation method [@Linkov2017].
For Science's graph model, the paper suggests that evidence edges should carry enough metadata to distinguish Bayesian updating, MCDA scoring, expert judgment, meta-analysis, and simple listing [@Linkov2017].
The MCDA framing is especially relevant for research-agent workflows where an agent may need to rank imperfect evidence before a defensible probabilistic model is available [@Linkov2017].

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Weight of evidence | Evidence aggregation operator | The same label can mean anything from listing evidence to formal Bayesian updating, so Science should encode the actual operator. |
| Bayes factor / log Bayes factor | Continuous evidence strength | Supports continuous belief updates and additive evidence scoring when assumptions are explicit. |
| Prior and posterior belief | Belief-state node | Evidence integration updates a live proposition belief rather than producing a binary accept/reject result. |
| Evidence source quality criteria | Evidence payload diagnostics | Reliability, relevance, specificity, and precision should be attached to evidence items before aggregation. |
| MCDA source weighting | Quality-weighted aggregation | Practical bridge for heterogeneous evidence when full Bayesian modeling is underspecified. |
| Bayesian belief network | Evidential / causal graph | Dependency structure among evidence items should be represented rather than silently assuming independence. |
| Guided expert judgment | Human or agent judgment node | Should be made explicit, auditable, and separable from quantitative evidence operators. |

## Limitations

The paper is argumentative and conceptual, so it does not test MCDA against Bayesian integration across controlled benchmark datasets [@Linkov2017].
The claim that MCDA can approximate Bayesian integration is plausible but identified by the authors as needing further research on robustness [@Linkov2017].
The toxicology and environmental-health setting may not transfer directly to all Science workflows, especially domains with richer likelihood models or stronger experimental standardization [@Linkov2017].
The MCDA formulation still depends on expert elicitation of criterion weights, so transparency improves but subjectivity is not eliminated [@Linkov2017].
The paper discusses tools such as OSIRIS and Netica through prior examples, but it does not release a new reusable model, benchmark, or software package [@Linkov2017].

## Model / Tool Availability

No standalone model or software artifact is released with the paper [@Linkov2017].
The commentary mentions the OSIRIS webtool for integrated testing strategies and Netica Bayesian belief network software as examples used in related work [@Linkov2017].
Tool availability was checked on 2026-07-08.
The UFZ OSIRIS project pages still describe the OSIRIS ITS webtool as the central OSIRIS software outcome and list `https://www.ufz.de/osiris/index.php?en=22157` for tool information, with SIMPPLE as the contact.
The separate OSIRIS Property Explorer remains publicly hosted at `https://www.organic-chemistry.org/prog/peo/` and `https://openmolecules.org/propertyexplorer/`.
Netica remains available from Norsys at `https://www.norsys.com/netica.html` with application and API products; it is commercial/proprietary software rather than an artifact released by this paper.

## Follow-up

Define Science evidence-aggregation operators as first-class graph objects with explicit type, inputs, assumptions, and output belief semantics.
Add an MCDA-style fallback path for evidence integration when heterogeneous sources cannot yet support a calibrated likelihood model.
Track whether an evidence item is being listed, quality-scored, causally linked, or used in a Bayesian update, because the paper shows that collapsing these modes under one "weight" label creates ambiguity.
