---
name: science-pipelines
description: "Source of truth for choosing and combining computational-execution skills (Snakemake, marimo, RunPod). Load when planning the orchestration shape of an analysis after methodology is decided. Routes to the leaves below."
---

# Pipelines Router

A router carries no methodology; teaching content belongs in a typed leaf. For
the cross-cutting rigor every pipeline must satisfy regardless of substrate, load
`references/reproducibility.md`.

## Routing trigger

Load this router when the execution shape of an analysis is in scope — **only
after** methodology is decided (see `science-command-preamble` skill's `references/methodology-index.md` and `science-plan-analysis`)
— before loading any leaf. Picking an execution substrate before the analysis
question is specified usually produces ceremony without rigor.

## Scope boundary

Covers the choice and combination of computational-execution substrates and the
substrate-agnostic reproducibility practice. Excludes the analysis methodology
itself (statistics, study design) and data acquisition/QA (data-management).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| [`references/reproducibility.md`](references/reproducibility.md) | Constructing any pipeline that must be reproducible, provenance-captured, or robust to sandboxed fetches | You are only comparing substrates and no pipeline is being constructed |
| [`references/snakemake.md`](references/snakemake.md) | Multi-step pipeline with file dependencies; intermediates worth caching; reproducible re-runs matter | One-off exploration; no DAG of dependencies |
| [`references/marimo.md`](references/marimo.md) | Interactive exploration; parameter sweeps; presentation with widgets; pre-pipeline prototyping | Production batch; long jobs; CI |
| [`references/runpod.md`](references/runpod.md) | Short-lived rented GPU; uv-based project; workload too large/slow for workstation | Long-lived managed cluster; CPU-only work |

## Decision / compose order

The substrate leaves are not mutually exclusive: `marimo` for prototyping ->
`snakemake` for the pipeline -> `runpod` for the GPU rule. `reproducibility`
applies across all of them — load it alongside whichever substrate you choose,
not instead of it.

## Parent & neighbors

- Parent index: `science-command-preamble` skill's `references/methodology-index.md`
- Neighboring routers: `science-statistics` skill, `science-data-management` skill, `science-research-package` skill

## Success test

Representative in-scope tasks route to the correct substrate leaf (or the correct
compose order when leaves combine), and construction-rigor questions route to
`references/reproducibility.md`, without any methodology being read from this router.

## Companion Skills

- `science-data-management` skill — data/result layout: read from `data/raw/`, write processed outputs and workflow-result packages under `results/<workflow>/<slug>/`.
- `science-research-package` skill — **only when** the pipeline's deliverable is a narrative research package under `research/packages/{name}/`; ordinary workflow results do not need one.
- `science-statistics` skill — statistical decisions that should be made before pipeline construction.
