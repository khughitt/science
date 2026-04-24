---
id: "question:01-bioinformatics-generalizability"
type: "question"
title: "How well do replication-crisis findings generalize from psychology, cancer biology, and neuroimaging to bioinformatics and genomics?"
status: "active"
ontology_terms: []
source_refs: []
related:
  - "topic:analytic-flexibility-and-replication"
created: "2026-04-24"
updated: "2026-04-24"
---

# How well do replication-crisis findings generalize from psychology, cancer biology, and neuroimaging to bioinformatics and genomics?

## Summary

The evidence base on analyst-dependent variability and below-predicted replication rates skews heavily toward psychology, preclinical cancer biology, and fMRI neuroimaging (see `topic:analytic-flexibility-and-replication`).
This project's primary user works in bioinformatics and genomics, and its design bets are partly motivated by the replication-crisis literature.
Whether those findings transfer — and *how they transfer* — is currently assumed rather than established.

## Why It Matters

- Determines whether `science-meta`'s design principles (evidence aggregation, continuous beliefs, analyst-path uncertainty) are solving a problem at the scale the motivating literature suggests, or a smaller problem in the primary target domain.
- Determines how simulation-testable hypotheses (e.g. `H-stochastic-revisit`) should be parameterized: what the realistic distribution of analyst-path variability looks like in genomics-scale problems.
- Risk if unanswered: the tool ships opinionated choices justified by evidence from fields that do not resemble the target field, with no calibration to the actual failure modes of genomics workflows.

## Current Evidence

- Genomics has structural differences from the fields in the core replication literature:
  - large standardized public datasets (TCGA, GTEx, UK Biobank) that multiple groups actually use, supporting direct re-analysis;
  - shared analysis pipelines (Bioconductor, nf-core, Galaxy) that narrow some analyst-path variability;
  - severe multiple-testing burdens and "big p, small n" settings that create *different* false-positive pressures than those in psychology or fMRI;
  - high-throughput data with its own reproducibility issues at the measurement level (batch effects, platform effects, preprocessing choices).
- Multi-centre / multi-laboratory evidence exists at the assay level — for example Niepel et al. [@Niepel2019] on drug-response assays across LINCS laboratories — showing substantial inter-laboratory variability that protocol standardization reduces but does not eliminate. This is evidence adjacent to genomics but not a direct many-analysts study on genomics analytic choices.
- No known counterpart to Silberzahn et al. [@Silberzahn2018] or Botvinik-Nezer et al. [@BotvinikNezer2020] has been run on a shared genomics dataset with many independent analyst teams. If such a study exists, it should be identified and added here.

## Thoughts

- Best current interpretation: the *direction* of the replication-crisis findings probably transfers (analyst-path variability is a general feature of flexible data analysis), but *magnitudes and dominant failure modes* likely differ. Genomics may have less per-study variability due to pipeline standardization but more systemic risk from upstream preprocessing conventions and reference-data choices that propagate correlated errors across many downstream studies.
- Major uncertainty: whether the canonical genomics pipelines that narrow analyst variability also *concentrate* the effect of their hidden assumptions, such that when one pipeline is wrong, many papers are wrong in the same way. This would be a qualitatively different failure mode than the independent-analyst-noise pattern of the psychology literature.

## Connections to Project

- Related hypotheses: `H-stochastic-revisit` (to be authored) — any simulator used to test it must decide whether analyst variability is modelled as independent noise or as shared pipeline bias; the answer to this question shapes that choice.
- Required data or analyses: (a) literature search for many-analysts or multi-pipeline genomics replication studies; (b) if none found, record as a gap that the project's empirical evaluation cannot currently close.
- Priority level: medium. It does not block tool development, but it bounds the claims this project can make about *what its tooling is good for*.

## Related

- Topic notes: `topic:analytic-flexibility-and-replication`
- Article notes: (Niepel 2019 paper summary to be written)
- Methods/Datasets: (none registered yet)
