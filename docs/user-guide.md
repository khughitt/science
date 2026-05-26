# Science User Guide

Science helps Claude and Codex users keep research work explicit, skeptical,
and durable. It records questions, hypotheses, propositions, evidence,
inquiries, tasks, and graph summaries in version-controlled project files.

This guide follows one possible path through a project:

```text
question -> hypothesis -> proposition -> evidence lines -> graph build ->
dashboard summary -> causal inquiry / analysis planning -> validation / health
```

That path is a teaching spine, not a required order. Real research is nonlinear:
you may start from a paper, a dataset, an existing hypothesis, a failed
analysis, a causal concern, or a health-check warning, then loop through the
same concepts in a different order.

## What Science Helps You Do

Science turns Claude and Codex into research workflow partners that can work
inside a durable project structure. The agent workflows are the primary user
interface; the `science` CLI is the project tooling layer they call when work
needs to create files, validate structure, build graphs, summarize evidence, or
inspect project health.

Science is skeptical by default. It helps you surface disagreement, missing
evidence, fragility, and alternative explanations rather than collect only
confirming notes. Evidence supports or disputes propositions; it does not prove
them outright. Literature provenance, data provenance, causal assumptions, and
belief snapshots are part of the project record.

## Install And Start

Claude users invoke Science as slash commands:

```text
/science:<command>
```

Codex users invoke generated skills:

```text
science-<command>
```

For Codex setup and the generated skill index, see
[`docs/README.codex.md`](README.codex.md).

The CLI form is:

```text
science <group> <command>
```

Common invocation patterns:

| Intent | Claude | Codex | CLI |
|---|---|---|---|
| Sketch a model | `/science:sketch-model` | `science-sketch-model` | `science inquiry ...` |
| Pre-register expectations | `/science:pre-register` | `science-pre-register` | source-authored document workflow |
| Stress-test bias | `/science:bias-audit` | `science-bias-audit` | source-authored document workflow |
| Add durable evidence | workflow-guided | workflow-guided | `science entity create evidence-line ...` |
| Build graph | `/science:create-graph` or `/science:update-graph` | `science-create-graph` or `science-update-graph` | `science graph build` |
| Summarize belief/evidence | `/science:status` | `science-status` | `science graph dashboard-summary` |

## Project Layout And Aspects

Most users work in a small set of project roots:

- `science.yaml`: project manifest, profile, peers, ontologies, and aspects.
- `AGENTS.md` / `CLAUDE.md`: operational instructions for agents.
- `doc/`: background notes, paper summaries, interpretations, discussions,
  reports, datasets, and other research documents.
- `specs/`: hypotheses, propositions, plans, and other structured project
  specifications.
- `tasks/`: active, blocked, deferred, retired, and completed work.
- `knowledge/`: generated graph files, summaries, and belief snapshots.
- `papers/references.bib`: bibliography entries for cited literature.
- `.ai/`: optional project-specific prompts, templates, and overrides.

Science supports `research` and `software` project profiles. For full profile
rules and migration guidance, see
[`docs/project-organization-profiles.md`](project-organization-profiles.md).

Aspects are project-context modifiers declared in `science.yaml`. They tailor
command behavior to the research context without changing the core project
layout. Common aspects include `causal-modeling`, `hypothesis-testing`,
`computational-analysis`, and `software-development`.

## The Reasoning Model

Science keeps the reasoning model explicit:

- `question`: what the project wants to learn.
- `hypothesis`: an organizing conjecture.
- `proposition`: a belief-bearing assertion.
- `observation`: a concrete empirical finding.
- `evidence-line`: durable support or dispute with stance, source, strength,
  role, and independence.
- `inquiry`: a graph-backed work program for questions, variables,
  assumptions, propositions, datasets, transformations, and decisions.

Authored state lives in source files. Derived graph and belief state should be
recomputed from those sources. Support, dispute, contestation, fragility, and
provenance are first-class concerns, not hidden notes.

For field-level details, use
[`docs/proposition-and-evidence-model.md`](proposition-and-evidence-model.md)
as the source of truth; this guide teaches the workflow layer.

## A First Research Loop

The next section walks through the continuous example from question to evidence
summary.

## Graphical Questions And Causal Work

The causal and graphical workflow builds on the same question, hypothesis,
proposition, and evidence concepts.

## Planning Analyses And Interpreting Results

Analysis outputs become evidence only after interpretation.

## Maintaining Project Health

Validation, health checks, freshness, and belief snapshots keep the project
reviewable as it changes.

## Cross-Project Work

Peers, commons, sync, and federation help Science projects refer to and reuse
knowledge across project boundaries.

## Cheat Sheet

Use the command map below as a quick reminder once the concepts are familiar.
