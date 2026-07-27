# Science User Guide

Science helps Claude and Codex users keep research work explicit, skeptical,
and durable. It records questions, hypotheses, propositions, evidence, analyses,
graph summaries, and project health in version-controlled project files.

This guide is the canonical user-facing manual for Science. It explains the
project model, the entity system, the epistemic model, evidence authoring,
derived graph state, validation, CLI workflows, agent workflows, and
cross-project work.

## Reading Path

The chapters are grouped into four sections in the sidebar — **Getting Started**,
**Core Model**, **Workflows & Tooling**, and **Multi-Project** — and read well in
that order:

1. **Getting Started** — [Introduction](introduction.md), then the [Big Picture](big-picture.md).
2. **Core Model** — the [Science Model](science-model.md), then [Project Layout](project-layout.md), [Entities](entities.md), and [Datasets](datasets.md), then the [Epistemic Model](epistemic-model.md), [Evidence Lines](evidence-lines.md), and [Graph And Derived State](graph-and-derived-state.md).
3. **Workflows & Tooling** — [CLI And Workflows](cli-and-workflows.md), [Agent Workflows](agent-workflows.md), [Coding Agents](coding-agents.md), [Codex](codex.md), [Crush](crush.md), [OpenCode](opencode.md), [Big-Picture Synthesis](big-picture-synthesis.md), [Health And Validation](health-and-validation.md), [Benchmarking](benchmarking.md), and [Feedback And Telemetry](feedback-and-telemetry.md).
4. **Multi-Project** — [Cross-Project Work](cross-project-work.md) and [Project Packaging](project-packaging.md).

## Chapters

| Chapter | Purpose |
|---|---|
| [Introduction](introduction.md) | What Science helps users do and how Claude, Codex, and the CLI fit together. |
| [Big Picture](big-picture.md) | Concise conceptual map: stance, substrate, epistemic model, and data model, each linking down to its detailed chapter. |
| [Science Model](science-model.md) | The big-picture model: authored sources, derived graph views, epistemic neighborhoods, provenance, and federation. |
| [Project Layout](project-layout.md) | The steady-state filesystem, `science.yaml`, `pyproject.toml`, and source/generated boundaries. |
| [Entities](entities.md) | The entity file shape, the source-entity CLI, consolidation and archiving, ontologies, and the core entity kinds Science understands. |
| [Datasets](datasets.md) | Dataset entities end to end: paper usage, gene-set collections, external and derived datasets, runtime state, QA, and split storage. |
| [Epistemic Model](epistemic-model.md) | Propositions, hypotheses, belief, and uncertainty. |
| [Evidence Lines](evidence-lines.md) | How to author durable support or dispute with provenance, role, strength, and independence. |
| [Graph And Derived State](graph-and-derived-state.md) | How authored files become graph state, summaries, snapshots, and reports. |
| [Big-Picture Synthesis](big-picture-synthesis.md) | Generated per-project synthesis reports, question resolution, and topic-coverage knowledge gaps (distinct from the conceptual Big Picture chapter above). |
| [Health And Validation](health-and-validation.md) | Validation, health checks, needs-review, freshness, and honest warning states. |
| [CLI And Workflows](cli-and-workflows.md) | Command families, write classes, canonical vs migration surfaces, and shared CLI behavior. |
| [Agent Workflows](agent-workflows.md) | Command map for Claude slash commands, Codex skills, and core CLI commands. |
| [Coding Agents](coding-agents.md) | Shared generated-skill distribution, installation, updates, collision handling, and Windows guidance for Codex, Crush, and OpenCode. |
| [Codex](codex.md) | Codex skill discovery and explicit Science skill selection. |
| [Crush](crush.md) | Crush skill discovery and the Science command palette. |
| [OpenCode](opencode.md) | OpenCode skills, `/science-*` commands, and permission policy. |
| [Feedback And Telemetry](feedback-and-telemetry.md) | Feedback entries, concern taxonomy, local telemetry, redaction, reporting, pruning, and telemetry-assisted triage. |
| [Benchmarking](benchmarking.md) | Benchmark metadata, validation, catalog coverage, opportunities, gaps, calibration, and read-only test projections. |
| [Skill Coverage](https://github.com/khughitt/science/blob/main/docs/conventions/skill-coverage.md) | Enrolling projects in skill coverage and scanning portfolio coverage. |
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
