# RunPod Skill Design

## Goal

Capture the RunPod execution pattern we developed in `protein-landscape` as an upstream Science pipeline skill plus bundled starter scripts, so other `uv`-based projects can reuse the same operational lessons without rebuilding them from scratch.

## Context

The current project has two concrete scripts that encode the most useful RunPod lessons:

- local sync to a pod with explicit allow-list semantics
- on-pod bootstrap with fail-fast preflight checks
- persistent cache directories under `/workspace`
- idempotency markers for expensive setup stages
- GPU-aware PyTorch wheel selection
- explicit handling for workstation-only `uv` source entries that break pod resolution

Those lessons are valuable beyond this repository, but the current scripts are tightly coupled to `protein-landscape` paths, data files, models, and workflow commands.

Science already organizes pipeline guidance as lightweight markdown skills under `skills/pipelines/`, for example `snakemake.md` and `marimo.md`. It also ships reusable project artifacts under `templates/`.

## Approaches Considered

### 1. Add a single markdown skill plus bundled starter scripts

Add a new `skills/pipelines/runpod.md` document that explains when and how to use RunPod, then ship reusable starter scripts under `templates/runpod/`.

Pros:

- matches the existing Science skill layout
- keeps operational guidance concise
- gives downstream projects real copyable artifacts instead of doc snippets
- lets the scripts stay opinionated about `uv` without hardcoding a specific project

Cons:

- requires one more template subdirectory under `templates/`

### 2. Add a single markdown skill with inline shell examples only

Keep everything inside the skill document and present the scripts as examples to copy manually.

Pros:

- smallest structural change

Cons:

- encourages copy-paste drift immediately
- makes the most operationally important pieces harder to reuse faithfully
- weakens the value of the upstream artifact

### 3. Package the upstream artifact as a Python `click` CLI

Ship a reusable Python command instead of shell starter scripts.

Pros:

- better long-term structure if orchestration becomes a real application
- easier to unit test complex branching logic

Cons:

- too heavy for the intended “copy as a starting point” use case
- adds packaging and integration overhead to every adopting project
- the core operations are mostly shell-native (`ssh`, `rsync`, env vars, remote commands)

## Decision

Use **one markdown skill plus bundled Bash starter scripts**.

The upstream artifact should optimize for low-friction reuse. In this workflow, the hard-earned value is mostly operational shell orchestration, not complex local business logic. Bash is therefore the right default for the starter layer. The skill should explicitly note that projects can graduate to a local Python CLI later if their RunPod orchestration becomes materially more complex.

## File Layout

Add these upstream files:

- `skills/pipelines/runpod.md`
- `templates/runpod/push_to_runpod.sh`
- `templates/runpod/setup.sh`
- `templates/runpod/run.sh`

No separate README is needed unless the skill becomes too large to stay concise. The markdown skill should remain the main entrypoint.

## Skill Scope

The new skill should cover:

- when RunPod is a good fit versus local execution or other remote infrastructure
- the standard execution flow:
  1. local preflight and environment setup
  2. allow-list sync to the pod
  3. on-pod bootstrap
  4. smoke test
  5. full run
  6. result retrieval and cleanup
- guidance for persistent caches, mounted volumes, and idempotent setup
- common failure modes:
  - missing SSH connectivity
  - missing GPU visibility
  - insufficient disk
  - gated model authentication
  - `uv` resolution failures caused by local editable sources
  - PyTorch / CUDA wheel mismatch
- a project customization checklist that makes clear what must be edited in the templates

The skill should stay focused on RunPod-style rented GPU pods. It should not try to become a generic cloud or cluster execution skill.

## Template Design

### `templates/runpod/push_to_runpod.sh`

This script is the local-to-pod sync entrypoint. It should provide:

- required env vars for host, port, and remote directory
- explicit allow-list `rsync` patterns
- remote directory creation
- comments explaining why allow-list sync is safer than broad exclude-lists
- placeholders for project-specific data files that need to be transferred

### `templates/runpod/setup.sh`

This script is the pod bootstrap entrypoint. It should provide:

- fail-fast preflight checks for required env vars, GPU visibility, and disk space
- cache setup under `/workspace/.cache/...`
- `uv` installation and `uv python install`
- `uv sync` as the default dependency bootstrap path
- idempotency markers for expensive setup stages
- a clearly isolated placeholder block for project-specific `pyproject.toml` patching when local editable sources must be removed on the pod
- a placeholder model download / smoke-test section

### `templates/runpod/run.sh`

This script is the project workload entrypoint. It should provide:

- a minimal pattern for pilot versus full runs
- env-var based configuration for workload parameters
- a clearly marked project-specific command block
- no hidden fallback behavior

Keeping execution in a separate script preserves the clean split between setup and workload execution.

## Generalization Boundary

The upstream templates should keep these pieces generalized:

- SSH and `rsync` transport pattern
- `uv` bootstrap and sync
- cache directory convention
- marker-file idempotency
- fail-fast shell structure
- comments that explain the operational reasoning

The upstream templates should leave these as explicit placeholders:

- project name and remote checkout path
- exact directories to sync
- exact data files to stage
- model name and download logic
- pod-side dry-run command
- workload command in `run.sh`
- any repo-specific `pyproject.toml` edits needed to strip local editable sources

The templates should never silently guess these values.

## Non-Goals

Out of scope:

- a packaged Python or `click` CLI
- support for non-`uv` projects
- vendor-agnostic cloud abstraction
- back-porting project-specific `protein-landscape` commands into Science defaults
- a compatibility layer for every possible remote environment

## Expected Outcome

After this work:

- Science will have a discoverable RunPod pipeline skill
- new projects can copy a real starter kit instead of mining old repos
- downstream RunPod setups will inherit the key operational safeguards we already learned
- project-specific customization points will be explicit instead of buried in ad hoc shell edits
