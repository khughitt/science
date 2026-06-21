#!/usr/bin/env bash
# Launch a project-specific workload on a RunPod instance.
#
# Copy this file into your project and replace project_run() before first use.
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:?Set PROJECT_DIR=/workspace/<project-name>}"
MODE="${1:-${RUNPOD_JOB:-full}}"
DRY_RUN=0

die() {
    echo "ERROR: $*" >&2
    exit 1
}

if [[ "${1:-}" == "--dry-run" ]]; then
    MODE="${RUNPOD_JOB:-full}"
    DRY_RUN=1
elif [[ "${2:-}" == "--dry-run" ]]; then
    DRY_RUN=1
fi

project_run() {
    die "Replace project_run() with the workload command your project needs for MODE=$MODE."
}

cd "$PROJECT_DIR"

echo "=== RunPod job launch ==="
echo "Project: $PROJECT_DIR"
echo "Mode:    $MODE"
echo "Dry run: $DRY_RUN"

# Add project-specific env vars here if your workload needs them, for example:
# export BATCH_SIZE="${BATCH_SIZE:-32}"
# export MODEL_NAME="${MODEL_NAME:-replace-me}"
#
# CRITICAL: the pod shell is fresh and inherits none of your workstation
# environment. If the workload's OUTPUT location is governed by an env var
# (output-root, results-dir, cache-dir), you MUST export it here, pinned to the
# same path pull_results.sh retrieves from. Otherwise the workload falls back to
# its built-in (usually relative) default and the outputs are stranded on the pod
# where the pull never looks. Treat run-output and pull-input as one contract.
# Example:
# export OUTPUT_ROOT="${OUTPUT_ROOT:-/workspace/<project-name>/data/out}"
#
# If you want a standard log path, define it here and have project_run use tee.
# Example:
# export RUN_LOG_DIR="${RUN_LOG_DIR:-logs/runpod}"
# mkdir -p "$RUN_LOG_DIR"
# export RUN_LOG_PATH="$RUN_LOG_DIR/$(date +%Y%m%d-%H%M%S)-${MODE}.log"

project_run
