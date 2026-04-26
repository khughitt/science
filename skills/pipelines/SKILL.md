---
name: pipelines
description: Source of truth for choosing and combining computational-execution skills (Snakemake, marimo, RunPod). Load when planning the orchestration shape of an analysis after methodology is decided.
---

# Pipelines

Decision aid for execution shape. Load **only after** methodology is decided
(see `skills/INDEX.md` and `science-plan-analysis`). Picking an execution
substrate before the analysis question is specified usually produces ceremony
without rigor.

## When to use which

| Skill | Load when | Avoid when |
|---|---|---|
| [`snakemake.md`](./snakemake.md) | Multi-step pipeline with file dependencies; intermediates worth caching; reproducible re-runs matter | One-off exploration; no DAG of dependencies |
| [`marimo.md`](./marimo.md) | Interactive exploration; parameter sweeps; presentation with widgets; pre-pipeline prototyping | Production batch; long jobs; CI |
| [`runpod.md`](./runpod.md) | Short-lived rented GPU; uv-based project; workload too large/slow for workstation | Long-lived managed cluster; CPU-only work |

These three are not mutually exclusive: `marimo` for prototyping -> `snakemake`
for the pipeline -> `runpod` for the GPU rule. The hub records the decision
order; the leaves cover the mechanics.

## Cross-cutting principles

1. **Tool-agnostic plans first.** `science-plan-pipeline` produces tool-agnostic
   task lists. Only commit to a specific orchestration substrate after the task
   list stabilizes.
2. **Side effects belong outside the workflow tree.** Snakemake's
   `protected()` does not save you from cleanup-before-rerun (see
   `snakemake.md` "protected() does NOT prevent rerun-cleanup"). Apply the
   marker-file pattern to any rule whose outputs live outside `out_dir`.
3. **Reproducibility = environment + seeds + inputs.** Pin tool versions, lock
   random seeds, hash inputs (`datapackage.json`). Without all three the
   pipeline is decorative.

## Companion Skills

- [`../data/SKILL.md`](../data/SKILL.md) — input-data conventions; pipelines should read from `data/raw/` and write to `data/processed/` or `results/`.
- [`../research/research-package-spec.md`](../research/research-package-spec.md) — terminal rule should produce a research package.
- [`../statistics/SKILL.md`](../statistics/SKILL.md) — statistical decisions that should be made before pipeline construction.
