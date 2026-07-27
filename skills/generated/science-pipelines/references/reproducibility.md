---
name: pipeline-reproducibility
description: Use when constructing a computational pipeline that must be reproducible — after methodology is decided, before and while committing to an orchestration substrate.
archetype: practice-guide
provenance: internal
---

# Pipeline Reproducibility

Answers: how do I construct any computational pipeline — regardless of substrate
(Snakemake, marimo, RunPod) — so that it is reproducible, provenance-captured,
and robust in constrained environments?

## When to apply

Load this after methodology is decided and you are planning or building the
execution shape of an analysis, before and while committing to a specific
orchestration substrate. The principles are substrate-agnostic; their mechanics
differ by substrate, and each substrate's realization lives in its tool-guide
leaf (`snakemake.md`, `marimo.md`, `runpod.md`). This practice covers what must
hold across all of them.

## Workflow steps

1. **Produce a tool-agnostic task list first.** `science-plan-pipeline` produces
   tool-agnostic task lists. Only commit to a specific orchestration substrate
   after the task list stabilizes — picking an execution substrate before the
   analysis question is specified usually produces ceremony without rigor.
2. **Pin the environment and seeds, and pre-stage inputs.** Pin tool versions and
   lock random seeds; declare each step's `seed_bindings` so the run's seed policy
   can be captured rather than guessed. Fetch inputs to `data/raw/` in a separate,
   network-allowed step so the run itself reads local files and never depends on
   egress.
3. **Execute on the chosen substrate.** Run the pipeline; the workflow executor
   writes (or updates) the tracked run-aggregate `datapackage.yaml` at
   `results/<workflow>/<run>/`.
4. **Commit the run records, verify a clean worktree, then register — after
   execution.** Execution itself writes tracked files, so a worktree that was
   clean *before* the run is dirty after it: commit the lightweight run manifest
   and `config.yaml` snapshot and confirm `git status` is clean immediately before
   capture, or the fingerprint records `code_dirty` and cannot reconstruct the
   source. Then capture with `science dataset register-run workflow-run:<slug>`. It
   reads the aggregate `datapackage.yaml`, records the `code_sha`, the
   environment/parameter/input/output-manifest digests, and the
   `seed_policy`/`step_seeds` derived from the workflow's steps, and writes the
   per-output `datapackage.yaml` views beneath the run package (with derived
   dataset entities under `entities/datasets/`). The fingerprint is an
   observation, never hand-authored; `science validate` re-checks it against
   `execution:` and tells you to re-register if they drift.

## Judgment rules

- **Side effects outside the managed output tree must be handled idempotently or
  transactionally** so a rerun cannot observe partial state. The general rule is
  substrate-independent; its realization differs — in Snakemake, use the
  marker-file pattern for any rule writing outside `out_dir` (`protected()` does
  *not* prevent rerun-cleanup; see `snakemake.md`), whereas a reactive notebook
  re-derives state on each run.
- **Bound fetch concurrency rather than leaning on retries.** When a substrate's
  own retry mechanism can deadlock under high fetch concurrency, reduce
  concurrency instead of adding retry loops. (In Snakemake, `--retries` under
  high `-c`; see `snakemake.md`.)

## Quality criteria

- **Reproducibility = environment + seeds + inputs.** Pin tool versions, lock
  random seeds, and identify inputs by their dataset references and the upstream
  datapackage resource hashes. Without all three the pipeline is decorative.
- **Provenance is captured, not hand-stamped.** A reproducible run is registered
  from a **clean worktree** with `science dataset register-run`, producing a
  `science-run-fingerprint/v1` record on the `workflow-run` entity (`code_sha`,
  env/param/input/output-manifest digests, `seed_policy`/`step_seeds`). A dirty
  tree is flagged (`code_dirty`) but not reconstructable — treat it as
  non-reproducible. Inputs are identified through the run's declared dataset
  references plus the upstream datapackage resource hashes, not through
  hand-authored per-output fields. Making this a convention rather than a
  per-script habit is the difference between a recoverable incident and an
  unrecoverable one: an unrelated pipeline's fingerprint saving your run is luck;
  your own is design. (fb-2026-07-11-026.)

## Common pitfalls

- **In constrained/sandboxed environments, network fetches can hang, not fail.**
  A sandbox that denies egress may *stall* an in-rule download indefinitely
  rather than return an error, wedging the whole run. Give every fetch a **total
  wall-clock watchdog**, not just a per-read timeout — a per-read `timeout=` does
  nothing against a slow-trickle or half-open socket, so a partial download can
  sit for hours. (fb-2026-07-10-001, -002, -003.)
- **Registering before the run completes, or from a dirty tree.** `register-run`
  reads the run-aggregate `datapackage.yaml` the executor writes at
  `results/<workflow>/<run>/`; run it *after* execution and from a committed tree,
  or the fingerprint records `code_dirty` and cannot reconstruct the source.
- **Relying on `protected()` for side-effect safety.** It does not prevent
  rerun-cleanup; use the marker-file pattern (see Judgment rules and
  `snakemake.md`).

## Outputs

A registered workflow run: the run owns one workflow-result package at
`results/<workflow>/<run>/` (its aggregate `datapackage.yaml`), and `science
dataset register-run` writes the per-output `datapackage.yaml` views beneath it —
and the derived dataset entities under `entities/datasets/` — while capturing the
run's `science-run-fingerprint/v1` fingerprint (`code_sha`, environment/input/
output digests, `seed_policy`/`step_seeds`). From a clean-tree registration, that
record identifies the tree
state and — via the input dataset references and their upstream resource hashes —
the inputs that produced the results, without any hand-authored metadata.

## Success test

Given a pipeline run registered from a clean worktree, can an independent agent
reproduce its outputs from the pinned environment, captured seeds, and the input
dataset references (with their upstream datapackage resource hashes), and tie any
output to the tree state via the run's captured `science-run-fingerprint/v1`
fingerprint — without relying on egress at run time and without hand-authored
provenance fields?

## Companion Skills

- Load the `science-command-preamble` skill and consult its `references/methodology-index.md` — the skill index.
- [`../SKILL.md`](../SKILL.md) — the pipelines router (choose the execution substrate).
- [`snakemake.md`](snakemake.md), [`marimo.md`](marimo.md), [`runpod.md`](runpod.md) — the substrate tool-guides whose mechanics this practice constrains.
