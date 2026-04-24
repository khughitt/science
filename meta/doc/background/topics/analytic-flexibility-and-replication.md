---
id: "topic:analytic-flexibility-and-replication"
type: "topic"
title: "Analytic Flexibility and the Replication Crisis"
status: "active"
ontology_terms: []
source_refs: []
related: []
created: "2026-04-24"
updated: "2026-04-24"
---

# Analytic Flexibility and the Replication Crisis

## Summary

Across multiple fields — biomedicine, psychology, neuroimaging — direct replication rates of published findings fall well below what published confidence intervals imply, and when given the same dataset and question, independent expert teams routinely produce materially different conclusions.
This body of work is a core motivating premise for `science-meta`: if scientific output at the article level is noisy, fragile, and sensitive to analyst choices, then a tool for cumulative research must aggregate signal across heterogeneous lines of evidence rather than trust any single study or analytic pipeline.

## Key Concepts

**Replication versus reproducibility.**
The literature distinguishes *methods reproducibility* (same data, same code, same result), *results reproducibility* or *direct replication* (new data, same design, same result), and *inferential reproducibility* (same conclusion drawn).
The replication crisis concerns primarily the second and third.

**Researcher degrees of freedom and the "garden of forking paths".**
At each step of a data analysis — outlier exclusion, covariate selection, transformation, stopping rule — the analyst makes defensible choices that can legitimately change the result.
When only the path that produced a significant finding is reported, the nominal false-positive rate understates the true one.

**Positive predictive value (PPV) of findings.**
Ioannidis [@Ioannidis2005] gave a Bayesian argument that PPV depends on pre-study odds, statistical power, bias, and multi-team competition, and that for most realistic parameter settings, PPV of a reported "positive" finding is below 0.5.

**Many-analysts designs.**
A study design in which many independent analyst teams receive the same data and question; the *spread* of their answers is itself the finding [@Silberzahn2018; @BotvinikNezer2020].

**Population dynamics of findings.**
Treating the corpus of published findings not as a stable set of facts but as an evolving population under selection (publication favours positive results) and mutation (analytic choice) [@McElreath2015].

## Current State of Knowledge

Evidence that published findings do not reliably replicate is now substantial and spans domains.

**Preclinical biomedicine.**
Begley and Ellis [@Begley2012] reported that scientists at Amgen could reproduce only 6 of 53 "landmark" cancer studies.
The Reproducibility Project: Cancer Biology [@Errington2021], which systematically attempted replications of 50 experiments from 23 high-impact cancer biology papers, reported that the median effect size in replications was 85% smaller than in the originals, and only about 40% of positive effects replicated across multiple pre-specified criteria.
The Brazilian Reproducibility Initiative [@Amaral2019] has since launched a similar multi-laboratory programme focused on common biomedical methods rather than single high-impact papers.
A complementary design — *multi-centre* rather than blinded replication — appears in Niepel et al. [@Niepel2019], in which a LINCS consortium of laboratories jointly measured drug response across mammalian cell lines using pre-agreed protocols; the study found that inter-laboratory variability in measured drug sensitivity was substantial and was reducible but not eliminable by standardised protocols, highlighting that *protocol specification* alone does not resolve analyst- and laboratory-level degrees of freedom.

**Analytic flexibility at fixed data.**
Silberzahn et al. [@Silberzahn2018] asked 29 teams to answer the same question ("are soccer referees more likely to give red cards to dark-skinned players?") using one shared dataset; estimated effects ranged from negligible to substantial, and methods varied widely, even though the teams agreed on the broad research framing.
Botvinik-Nezer et al. [@BotvinikNezer2020] extended this design to fMRI: 70 independent teams analysed a single neuroimaging dataset to test nine hypotheses, with no two teams using identical workflows; for five of the nine hypotheses, fewer than 60% of teams reached the same conclusion.
This directly grounds the intuition that the same well-posed analysis yields materially different answers from different analysts.

**Theoretical and population-level framing.**
Ioannidis's PPV account [@Ioannidis2005] supplies the Bayesian skeleton for why the above patterns are expected rather than aberrant.
McElreath and Smaldino [@McElreath2015] model the corpus of findings as a population subject to publication selection and show that replication rates below 50% can be sustained indefinitely under plausible incentives, with unreplicated findings accumulating faster than the system retires them.

**Proposed remedies.**
Munafò et al.'s manifesto [@Munafo2017] synthesises reforms across the system — pre-registration, registered reports, replication incentives, reporting standards, and infrastructural investment in reproducibility tooling — most of which depend on collective rather than individual adoption.

**Field-scale dynamics.**
Chu and Evans [@Chu2021] argue that in large scientific fields, the sheer volume of published work can paradoxically slow canonical progress by preventing consensus on any single line of work — a finding relevant to tooling that aims to aggregate evidence across a field.

## Controversies & Open Questions

**Generalisability across fields.**
Most replication evidence comes from psychology, preclinical cancer biology, and neuroimaging.
Whether comparable rates hold in genomics, bioinformatics, physics, chemistry, or ecology is less well-characterised.
Genomics in particular has distinctive features (large standardised public datasets, widely shared analysis pipelines, severe multiple-testing burdens, and a "big p, small n" regime) that may push replication behaviour in either direction.
The translation of these findings to any specific field should be treated as an open question, not a given.

**What kind of replication should be expected.**
Some authors argue that close direct replications are less informative than conceptual replications or systematic reviews; others argue the opposite.
This is unresolved and affects how "evidence aggregation" should be operationalised in any tool.

**Selection into replication studies.**
Critics of the Cancer Biology project and similar efforts raise concerns about selection of which studies to replicate and about the interpretation of partial replication [@Errington2021].
This debate is ongoing.

**Efficacy of reform.**
Evidence that pre-registration, registered reports, and open-data norms materially improve replication rates is accumulating but not yet decisive at scale.

## Relevance to This Project

This topic supplies the motivating premises on which several of `science-meta`'s design bets rest.

1. The claim that a substantial share of published research is unreliable [@Ioannidis2005; @Begley2012; @Errington2021; @Niepel2019] directly justifies aggregating evidence across multiple lines rather than privileging single studies — a design principle recorded in `core/decisions.md` and to be expanded in a forthcoming `doc/plans/design-principles.md`.
2. The many-analysts evidence [@Silberzahn2018; @BotvinikNezer2020] grounds the intuition that scientific data analysis is substantially analyst-dependent.
   A tool that represents a project's evidence graph as if the analyst path were neutral is implicitly claiming this literature is wrong; the project should instead treat analyst-path variability as a first-class source of uncertainty.
3. The population-dynamics framing [@McElreath2015] supports the tooling premise that replication behaviour is *modellable*, not merely lamentable — a premise that enables simulation-testable hypotheses (for example, H-stochastic-revisit: whether stochastic revisiting of down-weighted claims improves convergence to ground truth vs. hard gating at equal evidence budget).
4. Field-scale dynamics [@Chu2021] motivate the longer-range bet about forkable, shareable project packages: if the sheer volume of published work slows consensus, tooling that makes evidence composable across researchers targets a plausible mechanism rather than a speculative one.

A caveat to record: the evidence base skews heavily toward psychology, preclinical biomedicine, and neuroimaging.
Translation to genomics or bioinformatics — the background of the project's primary user — is itself an open question worth making explicit as a separate document under `doc/questions/`.

## Key References

- Ioannidis (2005) — Bayesian account of why most published findings are false [@Ioannidis2005]
- Errington et al. (2021) — systematic replication effort in cancer biology [@Errington2021]
- Silberzahn et al. (2018) and Botvinik-Nezer et al. (2020) — many-analysts designs in psychology and neuroimaging [@Silberzahn2018; @BotvinikNezer2020]
- McElreath & Smaldino (2015) — population-dynamics model of the finding corpus [@McElreath2015]
- Munafò et al. (2017) — systems-level reform manifesto [@Munafo2017]
