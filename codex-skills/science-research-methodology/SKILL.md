---
name: science-research-methodology
description: "Core research methodology for scientific investigation. This skill should be used whenever conducting literature review, evaluating scientific sources, synthesizing findings across papers, assessing evidence quality, identifying gaps in knowledge, or working with hypotheses. Also use when the user mentions research, papers, citations, evidence, or scientific literature — even if they don't explicitly ask for \"research methodology.\""
---

# Research Methodology Router

Adapted from canonical Science skill `skills/research/SKILL.md`.

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when any research activity is in scope — literature review,
paper summarization, hypothesis development, evidence evaluation, curation, or
topic exploration — before loading any leaf.

For analysis-readiness planning, start at [`../INDEX.md`](../INDEX.md) or run
`science-plan-analysis`.

## Scope boundary

Covers how the project evaluates external sources and reasons over its own
proposition graph. Excludes prose conventions (see
[`../../skills/writing/SKILL.md`](../../skills/writing/SKILL.md)) and statistical interpretation
(see [`../../skills/statistics/SKILL.md`](../../skills/statistics/SKILL.md)).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| [`literature-evaluation.md`](literature-evaluation.md) | Reviewing literature, assessing source quality, or synthesizing across papers | Reasoning about the project's own recorded evidence |
| [`citation-discipline.md`](citation-discipline.md) | Authoring or validating citations, bibliography keys, or `source_refs` | Deciding which sources to trust |
| [`proposition-graph-reasoning.md`](proposition-graph-reasoning.md) | Interpreting or updating the project's proposition graph, or deciding where to direct effort | Evaluating an external source |
| [`proposition-schema.md`](proposition-schema.md) | Authoring proposition entities, evidence metadata, or layered-claim fields | Reasoning about support adequacy rather than field values |
| [`annotation-curation-qa.md`](annotation-curation-qa.md) | Designing or reviewing claim extraction, labels, adjudication, or LLM-assisted curation | Curating nothing — reading only |
| [`research-package-spec.md`](research-package-spec.md) | Defining research-package manifests, cells, provenance, or workflow integration | Rendering an existing package |
| [`research-package-rendering.md`](research-package-rendering.md) | Rendering research packages and source routes in web experiences | Defining the package schema itself |

## Decision / compose order

Leaves are independent except where noted:

1. `literature-evaluation.md` before `citation-discipline.md` — select and assess sources, then record them correctly.
2. `proposition-schema.md` before `proposition-graph-reasoning.md` — know the field semantics before reasoning over their values.
3. `research-package-spec.md` before `research-package-rendering.md` — the rendering leaf builds on the spec as layer 1.

## Parent & neighbors

- Parent index: [`../INDEX.md`](../INDEX.md)
- Neighboring routers: [`../../skills/writing/SKILL.md`](../../skills/writing/SKILL.md), [`../../skills/statistics/SKILL.md`](../../skills/statistics/SKILL.md), [`../../skills/data/SKILL.md`](../../skills/data/SKILL.md)

## Success test

Representative in-scope tasks route to the correct leaf (or the correct compose order when leaves combine) without any methodology being read from this router.

## Companion Skills

- [`../INDEX.md`](../INDEX.md) — the skill index.
