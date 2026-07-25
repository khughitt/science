---
id: topic:evaluating-research-tools
kind: topic
title: Evaluating Research Tools with Human Participants
status: active
related: []
source_refs: []
created: '2026-07-25'
updated: '2026-07-25'
---
# Evaluating Research Tools with Human Participants

## Summary

The project has extensive machinery for representing evidence about the toolkit's design
and very little for measuring whether that design helps a person. This topic gathers the
literature on evaluating research and developer tools with human participants: the study
designs, the control conditions, the outcome operationalizations, and the validity threats
that decide whether such an evaluation says anything.

It exists because four entities created on 2026-07-25 all need this literature and none of
the five prior topics supplies it.

> **Intake status.** Every reference below was surfaced by the 2026-07-25
> `explore-ideas` lens pass and is **unverified**: the identifiers are
> model-generated and no source has been read. Nothing here should be cited or
> treated as evidence until the intake task promotes it to a real paper entity.
> This topic is a scoped reading brief, not a synthesis.

## Key Concepts

**Dismantling / factorial design.** Isolating the contribution of one component of a
composite intervention by withholding it, rather than comparing the whole intervention
against nothing. The relevant control here is not "no tool" but "unstructured LLM
assistance", since general model availability is the dominant confound.

**Ecological validity.** The degree to which behaviour observed in a study setting
transfers to the target setting. Distinct from internal validity, and frequently traded
against it: the tightest-controlled study of a research tool is often the least
representative of real research.

**Construct validity of the outcome.** "Research quality" is not a measurable quantity.
It must be operationalized — causal-structure accuracy against known ground truth,
calibration of resulting beliefs, reproducibility of conclusions, expert-rated hypothesis
precision — and these are not interchangeable, so the choice partly determines the result.

**Common-method / double-construction bias.** When the same party builds both the
intervention and the instrument that evaluates it, the instrument tends to measure the
workflow the intervention was designed to support. Directly applicable to this project's
simulation instruments.

**Deskilling as a longitudinal outcome.** Tool evaluations typically measure a
cross-section. If a tool's effect reverses over sustained exposure — benefit early, harm
late — a cross-sectional design cannot see it.

## Current State of Knowledge

Nothing is established here yet; this topic is newly scoped and no source has been read.
What is known is which questions depend on it, and that the project currently has no
instrument for any of them.

## Controversies & Open Questions

- What is the right control condition for a research-agent toolkit — unaided researcher,
  unstructured LLM, or partial toolkit?
- Can any outcome operationalization of "research quality" avoid being either trivially
  measurable or contested?
- Is a many-analysts design (the same evidence base, many independent analysts, toolkit as
  treatment arm) feasible at this project's scale, or does it require collaborators the
  project does not have?

## Relevance to This Project

This topic is the shared literature base for the toolkit-evaluation cluster:
`question:0041` (simulator ecological validity), `question:0042` (factorial dismantling),
`question:0043` (deskilling), and `hypothesis:0008` (analyst-divergence reduction). It also
supports `question:0055`, which asks which self-directed claims need an instrument outside
the system at all.

## Key References

- Ko et al. (2013) — controlled experiments of software engineering tools with human
  participants; internal vs external validity tradeoffs *(unverified intake)*
- Eriksson et al. (2025) — validity threats in AI evaluation; construct validity and the
  inadequacy of task-completion metrics *(unverified intake)*
- Silberzahn et al. (2018) — many-analysts design *(already held as `cite:Silberzahn2018`)*
- Breznau et al. (2022) — 73-team divergence quantification *(unverified intake)*
- Natali et al. (2025); Ferdman (2025) — AI-induced deskilling *(unverified intake)*
