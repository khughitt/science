---
name: pipelines
description: Source of truth for choosing and combining computational-execution skills (Snakemake, marimo, RunPod). Load when planning the orchestration shape of an analysis after methodology is decided.
provenance: internal
---

# Pipelines

Decision aid for execution shape. Load **only after** methodology is decided
(see `skills/INDEX.md` and `science-plan-analysis`). Picking an execution
substrate before the analysis question is specified usually produces ceremony
without rigor.

For analysis-readiness planning, start at [`../INDEX.md`](../INDEX.md) or run
`science-plan-analysis`.

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
4. **Every output stamps its own provenance.** Each pipeline output artifact must
   carry, in the artifact itself (JSON sidecar, header, or manifest), the
   `git_revision` of the tree that produced it, a `created` timestamp, and the
   `sha256` of every input it consumed. Make this a convention, not a per-script
   habit. It is the difference between a recoverable incident and an unrecoverable
   one: when a frozen vehicle is destroyed, the only thing that can identify the tree
   state that produced it — and let it be rebuilt and verified against a frozen ledger
   in an isolated worktree — is a stamped revision. An unrelated pipeline's stamp
   saving your run is luck; your own stamp is design. (fb-2026-07-11-026.)
5. **In constrained/sandboxed environments, network fetches can hang, not fail.**
   A sandbox that denies egress may *stall* an in-rule download indefinitely
   rather than return an error, wedging the whole run. Two guards: (a) give every
   fetch a **total wall-clock watchdog**, not just a per-read timeout — a
   per-read `timeout=` does nothing against a slow-trickle or half-open socket, so
   a partial download can sit for hours; (b) **pre-stage inputs outside the
   sandboxed run** (fetch to `data/raw/` in a separate, network-allowed step) so
   the reproducible pipeline reads local files and never depends on egress. When
   an orchestrator's own `--retries` can deadlock under high `-c`, prefer fewer
   concurrent fetch jobs over retry loops. (fb-2026-07-10-001, -002, -003.)

## Companion Skills

- [`../data-management/SKILL.md`](../data-management/SKILL.md) — input-data conventions; pipelines should read from `data/raw/` and write to `data/processed/` or `results/`.
- [`../research-package/research-package-spec.md`](../research-package/research-package-spec.md) — terminal rule should produce a research package.
- [`../statistics/SKILL.md`](../statistics/SKILL.md) — statistical decisions that should be made before pipeline construction.
