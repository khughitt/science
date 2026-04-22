---
name: pipeline-runpod
description: RunPod GPU workflow construction and operational best practices. Use when setting up rented GPU pods for uv-based projects, syncing code or data to RunPod, bootstrapping dependencies on a pod, or the user mentions RunPod, remote GPU pods, or pushing jobs to a rented GPU.
---

# RunPod GPU Pods

## When To Use

- You need short-lived rented GPU capacity for a `uv`-based project
- The workload is too large or too slow for a workstation
- The job can be expressed as a small set of explicit sync, setup, and run steps
- You want a project-local starting point rather than a shared cluster abstraction

Do not use this pattern when:

- the work should stay local
- the environment is a long-lived managed cluster rather than a disposable pod
- the workflow needs a full orchestration service instead of a few explicit scripts

## Standard Flow

1. Copy the starter scripts from `templates/runpod/` into your project, usually as `runpod/`
2. Edit the project-specific placeholders before first use
3. Run `push_to_runpod.sh` locally to sync code and required inputs
4. SSH to the pod and run `setup.sh`
5. Run a smoke test or pilot job
6. Run the full workload with `run.sh`
7. Pull results back using project-specific sync commands

## Required Inputs

At minimum, decide these values up front:

- remote host and SSH port
- remote project directory under `/workspace`
- which repository paths should be synced
- which input data files must be staged
- which model or runtime artifacts should be pre-downloaded
- which workload command should run on the pod

If those values are still vague, stop and decide them before editing the scripts. The templates are meant to be explicit, not adaptive.

## Starter Scripts

Science provides three RunPod starter scripts:

- `templates/runpod/push_to_runpod.sh`
- `templates/runpod/setup.sh`
- `templates/runpod/run.sh`

They assume:

- `uv` is the package manager and runtime launcher
- Bash is acceptable for orchestration
- project-specific choices are made by editing clearly marked shell functions

The templates intentionally fail in project-specific sections until you replace the placeholder functions. This prevents half-customized scripts from looking complete.

## Pod Setup Principles

Keep these patterns intact when customizing:

- **Allow-list syncs:** include only the files you want on the pod, then end with `--exclude='*'`
- **Fail-fast preflight:** verify SSH target, GPU visibility, free disk, and required env vars before expensive setup
- **Persistent caches:** keep HuggingFace, `uv`, and Torch caches under `/workspace/.cache`
- **Idempotent setup:** marker files should skip expensive steps that already succeeded
- **Explicit remote patching:** if local editable `uv` sources break pod resolution, patch them in a clearly isolated block
- **Separate setup from execution:** dependency bootstrap belongs in `setup.sh`; workload launch belongs in `run.sh`

## Common Failure Modes

### `uv sync` fails on the pod because of workstation-only editable sources

Some repos depend on local editable packages that only exist on the workstation. Handle this in the isolated `patch_pyproject_for_remote` block inside `setup.sh`. Do not hide this behind a silent fallback.

### PyTorch wheel does not match the available GPU / CUDA stack

The template includes a GPU-aware reinstall pattern. Treat it as a starting point, then pin the wheel selection your project actually needs.

### Setup succeeds but the real workload still is not runnable

Add a project-specific smoke test to `setup.sh` and keep the real workload entrypoint in `run.sh`. Do not treat “dependency install completed” as a sufficient verification step.

### Rsync copies too much or too little

Edit the allow-list includes deliberately. Broad exclude-lists drift over time and usually leak irrelevant files to the pod.

### Model downloads fail because auth was not configured

Require env vars such as `HF_TOKEN` explicitly in `setup.sh` when the model source is gated. Remove or replace that check only if the project does not need it.

## Customization Checklist

Before first real use, edit all of these:

- `REMOTE_DIR` and repository include patterns in `push_to_runpod.sh`
- the project-specific input sync function in `push_to_runpod.sh`
- `PROJECT_DIR` and optional `patch_pyproject_for_remote` logic in `setup.sh`
- the project-specific runtime preparation function in `setup.sh`
- the project-specific workload function in `run.sh`

After editing, run:

```bash
bash -n runpod/push_to_runpod.sh
bash -n runpod/setup.sh
bash -n runpod/run.sh
```

Then do one smoke test before the full run.

## When To Graduate Beyond Bash

Stay with Bash when the workflow is still mostly:

- `ssh`
- `rsync`
- env vars
- a few deterministic remote commands

Move project-specific orchestration into a local Python CLI when:

- runtime selection or argument building becomes complex
- multiple workloads share the same remote control plane
- configuration needs structured validation
- the Bash scripts are turning into a real application

Keep the transport layer simple. The point of this skill is to make rented GPU pods reusable without introducing a second framework.
