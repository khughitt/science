# Science User Guide

Science helps Claude and Codex users keep research work explicit, skeptical,
and durable. It records questions, hypotheses, propositions, evidence, analyses,
graph summaries, and project health in version-controlled project files.

This guide is the canonical user-facing manual for Science. It explains the
project model, the entity system, the epistemic model, evidence authoring,
derived graph state, validation, agent workflows, and cross-project work.

## Reading Path

1. Start with [Introduction](introduction.md) and [Science Model](science-model.md).
2. Learn [Project Layout](project-layout.md) and [Entities](entities.md).
3. Learn the [Epistemic Model](epistemic-model.md) and [Evidence Lines](evidence-lines.md).
4. Learn [Graph And Derived State](graph-and-derived-state.md), [Big-Picture Synthesis](big-picture-synthesis.md), [Health And Validation](health-and-validation.md), [Agent Workflows](agent-workflows.md), [Feedback And Telemetry](feedback-and-telemetry.md), [Project Packaging](project-packaging.md), and [Cross-Project Work](cross-project-work.md).

## Chapters

| Chapter | Purpose |
|---|---|
| [Introduction](introduction.md) | What Science helps users do and how Claude, Codex, and the CLI fit together. |
| [Science Model](science-model.md) | The big-picture model: authored sources, derived graph views, epistemic neighborhoods, provenance, and federation. |
| [Project Layout](project-layout.md) | The steady-state filesystem, `science.yaml`, `pyproject.toml`, and source/generated boundaries. |
| [Entities](entities.md) | What entity files look like, which core entity kinds Science understands, and the dataset lifecycle. |
| [Epistemic Model](epistemic-model.md) | Propositions, hypotheses, belief, and uncertainty. |
| [Evidence Lines](evidence-lines.md) | How to author durable support or dispute with provenance, role, strength, and independence. |
| [Graph And Derived State](graph-and-derived-state.md) | How authored files become graph state, summaries, snapshots, and reports. |
| [Big-Picture Synthesis](big-picture-synthesis.md) | Generated synthesis reports, question resolution, and topic-coverage knowledge gaps. |
| [Health And Validation](health-and-validation.md) | Validation, health checks, needs-review, freshness, and honest warning states. |
| [Agent Workflows](agent-workflows.md) | Command map for Claude slash commands, Codex skills, and core CLI commands. |
| [Feedback And Telemetry](feedback-and-telemetry.md) | Feedback entries, concern taxonomy, local telemetry, redaction, reporting, pruning, and telemetry-assisted triage. |
| [Project Packaging](project-packaging.md) | Deterministic project bundles, manifest payload inventories, verification, extraction, and exit-code semantics. |
| [Cross-Project Work](cross-project-work.md) | Peers, sync, project collections, and federated Science projects. |

## Core Loop

```text
question -> hypothesis -> proposition -> evidence line -> graph build ->
dashboard summary -> inquiry / analysis planning -> validation / health
```

That path is a teaching spine, not a required order. Real research is nonlinear:
you may start from a paper, dataset, failed analysis, causal concern, or health
warning, then loop through the same concepts in a different order.
