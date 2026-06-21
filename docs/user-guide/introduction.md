# Introduction

Science is both an agent workflow package and local project tooling for research
work. Claude and Codex workflows are the primary user interface; the `science`
CLI supports durable file creation, validation, graph materialization, evidence
summaries, synchronization, and project health.

Science is skeptical by default:

- hypotheses are organizing conjectures;
- propositions are the main belief-bearing assertions;
- evidence supports or disputes propositions rather than proving them outright;
- uncertainty, contestation, and fragility stay visible;
- literature, data, and causal provenance should be explicit.

## How Users Enter The System

Claude users invoke Science as slash commands:

```text
/science:<command>
```

Codex users invoke generated skills:

```text
science-<command>
```

The CLI form is:

```text
science <group> <command>
```

In normal use, the agent workflows guide the conversation and call the CLI when
work needs to create or validate durable project artifacts.

## One Possible Research Loop

```text
create/import project -> status -> research-topic/search-literature ->
add-hypothesis -> proposition/evidence lines -> graph build ->
dashboard summary -> validate/health -> next-steps
```

Research is usually nonlinear. Start where the work actually starts: a paper, a
dataset, a question, a failed model, a surprising result, or a project-health
warning. Science keeps the resulting claims, evidence, provenance, and next
actions explicit.

## Durable Sources First

Authored state lives in source files. Derived graph files, summaries, snapshots,
and health reports should be rebuilt from those sources. If the graph is wrong,
fix the source artifact and rebuild the graph rather than patching generated
TriG directly.
