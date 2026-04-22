# RunPod Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an upstream Science RunPod pipeline skill plus reusable Bash starter scripts that capture the proven `uv`-based local sync, pod setup, and job execution pattern.

**Architecture:** Keep the existing Science pipeline-skill structure by adding one new markdown skill at `skills/pipelines/runpod.md`. Put the reusable operational artifacts in `templates/runpod/` so downstream projects can copy them directly and customize a small number of clearly marked placeholders without changing the core safety patterns.

**Tech Stack:** Markdown, Bash, `uv`, `ssh`, `rsync`

---

### Task 1: Add the RunPod pipeline skill document

**Files:**
- Read: `skills/pipelines/snakemake.md`
- Read: `skills/pipelines/marimo.md`
- Create: `skills/pipelines/runpod.md`

**Step 1: Review existing pipeline skill tone and structure**

Run:

```bash
sed -n '1,220p' skills/pipelines/snakemake.md
sed -n '1,220p' skills/pipelines/marimo.md
```

Expected:

- both files use YAML frontmatter with `name` and `description`
- both are concise, task-oriented markdown guidance rather than exhaustive documentation

**Step 2: Write `skills/pipelines/runpod.md`**

Include these sections:

- frontmatter:

```yaml
---
name: pipeline-runpod
description: RunPod GPU workflow construction and operational best practices. Use when setting up rented GPU pods for uv-based projects, syncing code/data to RunPod, bootstrapping dependencies on the pod, or the user mentions RunPod, remote GPU pods, pod setup, or pushing jobs to a rented GPU.
---
```

- `# RunPod GPU Pods`
- `## When To Use`
- `## Standard Flow`
- `## Required Inputs`
- `## Starter Scripts`
- `## Pod Setup Principles`
- `## Common Failure Modes`
- `## Customization Checklist`
- `## When To Graduate Beyond Bash`

The document must point readers to:

- `templates/runpod/push_to_runpod.sh`
- `templates/runpod/setup.sh`
- `templates/runpod/run.sh`

It must state explicitly that:

- the scripts assume `uv`
- project-specific path, data, and command placeholders must be edited
- the templates use fail-fast checks and should not grow compatibility layers

**Step 3: Review the new skill for consistency**

Run:

```bash
sed -n '1,260p' skills/pipelines/runpod.md
```

Expected:

- sections are concise and consistent with existing `skills/pipelines/*.md`
- the trigger description is about when to use the skill, not a workflow summary

### Task 2: Add reusable RunPod starter scripts under `templates/runpod/`

**Files:**
- Create: `templates/runpod/push_to_runpod.sh`
- Create: `templates/runpod/setup.sh`
- Create: `templates/runpod/run.sh`

**Step 1: Create the local sync starter**

Write `templates/runpod/push_to_runpod.sh` with:

- `#!/usr/bin/env bash`
- `set -euo pipefail`
- required env vars:

```bash
RUNPOD_HOST="${RUNPOD_HOST:?Set RUNPOD_HOST=root@<ip>}"
RUNPOD_PORT="${RUNPOD_PORT:-22}"
REMOTE_DIR="${REMOTE_DIR:?Set REMOTE_DIR=/workspace/<project-name>}"
```

- remote directory creation:

```bash
ssh -p "$RUNPOD_PORT" "$RUNPOD_HOST" "mkdir -p $REMOTE_DIR"
```

- an allow-list `rsync` block with clearly marked include placeholders for project files
- comments explaining the final `--exclude='*'` catch-all and why this is safer than a broad exclude-list
- clearly marked placeholders for project-specific data sync

**Step 2: Create the pod setup starter**

Write `templates/runpod/setup.sh` with:

- `#!/usr/bin/env bash`
- `set -euo pipefail`
- required env vars:

```bash
PROJECT_DIR="${PROJECT_DIR:?Set PROJECT_DIR=/workspace/<project-name>}"
HF_TOKEN="${HF_TOKEN:?Set HF_TOKEN for gated model downloads}"
```

- preflight checks for:
  - `nvidia-smi`
  - visible GPU name
  - free space on `/workspace`
- cache setup:

```bash
export HF_HOME="/workspace/.cache/huggingface"
export UV_CACHE_DIR="/workspace/.cache/uv"
export TORCH_HOME="/workspace/.cache/torch"
mkdir -p "$HF_HOME" "$UV_CACHE_DIR" "$TORCH_HOME"
```

- `uv` bootstrap
- `uv python install 3.12`
- `uv sync --python 3.12 --no-dev`
- marker-file pattern such as:

```bash
SYNC_MARKER=".venv/.setup-sync-done"
TORCH_MARKER=".venv/.setup-torch-done"
```

- a clearly fenced placeholder section for repo-specific `pyproject.toml` patching when local editable sources break pod resolution
- a GPU-aware PyTorch install example with comments that explain why wheel selection may need project-level customization
- a placeholder model pre-download / smoke-test section

**Step 3: Create the workload starter**

Write `templates/runpod/run.sh` with:

- `#!/usr/bin/env bash`
- `set -euo pipefail`
- optional pilot/full mode switch, for example:

```bash
MODE="${1:-full}"
```

- env-var based knobs for project-specific workload settings
- one clearly delimited block where the project inserts the actual `uv run ...` command
- no implicit fallback behavior

**Step 4: Syntax-check the new scripts**

Run:

```bash
bash -n templates/runpod/push_to_runpod.sh
bash -n templates/runpod/setup.sh
bash -n templates/runpod/run.sh
```

Expected:

- no output
- zero exit status for all three commands

### Task 3: Validate the upstream artifact as a coherent starter kit

**Files:**
- Read: `skills/pipelines/runpod.md`
- Read: `templates/runpod/push_to_runpod.sh`
- Read: `templates/runpod/setup.sh`
- Read: `templates/runpod/run.sh`

**Step 1: Check cross-references and placeholder clarity**

Run:

```bash
rg -n "templates/runpod|RUNPOD_HOST|REMOTE_DIR|PROJECT_DIR|Customize|placeholder|project-specific" \
  skills/pipelines/runpod.md templates/runpod/
```

Expected:

- the skill references all three starter scripts
- each script has obvious project-specific placeholders
- no script silently hardcodes a `protein-landscape` path or workload command

**Step 2: Spot-check that the templates preserve the intended safety patterns**

Run:

```bash
rg -n "set -euo pipefail|--exclude='\\*'|SYNC_MARKER|TORCH_MARKER|nvidia-smi|uv sync" \
  templates/runpod/
```

Expected:

- the new templates keep the fail-fast shell settings
- allow-list sync is present
- setup idempotency markers are present
- GPU preflight and `uv` dependency bootstrap are present

**Step 3: Review git diff for accidental project-specific leakage**

Run:

```bash
git diff -- skills/pipelines/runpod.md templates/runpod docs/plans/2026-04-22-runpod-skill-design.md docs/plans/2026-04-22-runpod-skill-implementation.md
```

Expected:

- only the new RunPod skill, starter templates, and plan docs are changed
- no downstream `protein-landscape` command paths leaked into the upstream templates except as deliberate “replace this” examples

**Step 4: Stage and commit when satisfied**

Run:

```bash
git add skills/pipelines/runpod.md templates/runpod docs/plans/2026-04-22-runpod-skill-design.md docs/plans/2026-04-22-runpod-skill-implementation.md
git commit -m "feat: add runpod pipeline skill and templates"
```

Expected:

- staged diff contains only the new skill, templates, and plan docs
- commit message follows the repo’s conventional commit style
