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
3. Decide whether the pod will consume precomputed artifacts or recompute them remotely
4. Run `push_to_runpod.sh` locally to sync code and required inputs
5. SSH to the pod and run `setup.sh`
6. Run a smoke test or dry-run before the real workload
7. Run the real workload with `run.sh`
8. Pull results back with `pull_results.sh`

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

Science provides four RunPod starter scripts:

- `templates/runpod/push_to_runpod.sh`
- `templates/runpod/setup.sh`
- `templates/runpod/run.sh`
- `templates/runpod/pull_results.sh`

They assume:

- `uv` is the package manager and runtime launcher
- Bash is acceptable for orchestration
- project-specific choices are made by editing clearly marked shell functions

The templates intentionally fail in project-specific sections until you replace the placeholder functions. This prevents half-customized scripts from looking complete.

## Job Modes

Use a small explicit mode variable when one repository has multiple remote workloads. Two patterns work well:

- `RUNPOD_JOB=<mode>` for push and pull scripts
- `MODEL_TO_DOWNLOAD=<mode>` or a similar setup-specific mode in `setup.sh`

Do not fork a new template directory per workload unless the transport or runtime contract is genuinely different. Most repos only need one transport layer with a few named modes.

## Pod Setup Principles

Keep these patterns intact when customizing:

- **Allow-list syncs:** include only the files you want on the pod, then end with `--exclude='*'`
- **Resumable uploads:** use `rsync` partial-transfer flags so large artifact uploads can resume after interruption
- **Fail-fast preflight:** verify SSH target, GPU visibility, free disk, and required env vars before expensive setup
- **Persistent caches:** keep HuggingFace, `uv`, and Torch caches under `/workspace/.cache`
- **Idempotent setup:** marker files should skip expensive steps that already succeeded
- **Track the full Torch package set:** record and compare the matched `torch` plus `torchvision` wheel pair, not just `torch`
- **Explicit remote patching:** if local editable `uv` sources break pod resolution, patch them in a clearly isolated block
- **Controlled dependency sync:** cap `uv` download fanout and add retries on flaky pod networks
- **Install runtime-only tools explicitly:** if `uv sync --no-dev` omits workflow CLIs such as `snakemake`, install them in a dedicated hook instead of hoping they exist
- **Early runtime smoke checks:** import `torch` and `torchvision`, assert CUDA, then run one small workload-specific smoke test before large downloads
- **Separate setup from execution:** dependency bootstrap belongs in `setup.sh`; workload launch belongs in `run.sh`
- **Standard pull phase:** make result retrieval explicit instead of relying on ad hoc `rsync` commands after the run

## Common Failure Modes

### `uv sync` fails on the pod because of workstation-only editable sources

Some repos depend on local editable packages that only exist on the workstation. Handle this in the isolated `patch_pyproject_for_remote` block inside `setup.sh`. Do not hide this behind a silent fallback.

### PyTorch wheel does not match the available GPU / CUDA stack

Pin a matched `torch` plus `torchvision` wheel pair and store that whole package set in the setup marker. Reinstalling only `torch` can leave the pod with operator mismatches such as `torchvision::nms does not exist`.

### `uv sync --no-dev` succeeds but the workflow runner is missing

This usually means the workload depends on a CLI that only lives in the dev group, such as `snakemake`. Install those tools in a dedicated `project_install_runtime_tools()` hook inside `setup.sh`, then verify them there.

### Setup succeeds but the real workload still is not runnable

Add a project-specific smoke test to `setup.sh` and keep the real workload entrypoint in `run.sh`. Do not treat “dependency install completed” as a sufficient verification step. The shared template should already verify:

- `torch` import
- `torchvision` import
- `torch.cuda.is_available()`

Then add one workload-specific check such as a model import or workflow CLI `--version`.

### Rsync copies too much or too little

Edit the allow-list includes deliberately. Broad exclude-lists drift over time and usually leak irrelevant files to the pod.

### Large uploads restart from byte zero after a network hiccup

Use resumable `rsync` defaults for large artifact transfers. In practice this means `--partial`, `--partial-dir=.rsync-partial` for ordinary syncs, and `--append-verify` for large immutable artifacts.

### `uv sync` times out while downloading many packages in parallel

The default `uv` download concurrency is high enough to stress weak pod networking. Set explicit values such as `UV_HTTP_TIMEOUT`, `UV_CONCURRENT_DOWNLOADS`, and `SYNC_ATTEMPTS` in `setup.sh`, and log them so failures are diagnosable.

### Model downloads fail because auth was not configured

Require env vars such as `HF_TOKEN` explicitly in `setup.sh` when the model source is gated. Remove or replace that check only if the project does not need it.

## Customization Checklist

Before first real use, edit all of these:

- `REMOTE_DIR` and repository include patterns in `push_to_runpod.sh`
- the project-specific input and optional artifact sync functions in `push_to_runpod.sh`
- `PROJECT_DIR`, timeout or retry defaults, and optional `patch_pyproject_for_remote` logic in `setup.sh`
- the optional `project_install_runtime_tools()` hook in `setup.sh` if the pod needs workflow CLIs that are omitted from `uv sync --no-dev`
- the optional `project_runtime_smoke_test()` hook in `setup.sh` if the workload needs an early import or CLI check
- the project-specific runtime preparation function in `setup.sh`
- the project-specific workload function in `run.sh`
- the project-specific result sync function in `pull_results.sh`

After editing, run:

```bash
bash -n runpod/push_to_runpod.sh
bash -n runpod/setup.sh
bash -n runpod/run.sh
bash -n runpod/pull_results.sh
```

Then do this sequence once before the real run:

1. local push
2. remote setup
3. remote dry-run or smoke test
4. full run
5. pull results

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

## Companion Skills

- [`SKILL.md`](SKILL.md) - shared pipeline conventions and artifact contracts.
- [`snakemake.md`](snakemake.md) - production workflow rules for remote workloads that have stabilized.
