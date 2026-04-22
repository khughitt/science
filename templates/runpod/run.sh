#!/usr/bin/env bash
# Launch a project-specific workload on a RunPod instance.
#
# Copy this file into your project and replace project_run() before first use.
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:?Set PROJECT_DIR=/workspace/<project-name>}"
MODE="${1:-full}"

die() {
    echo "ERROR: $*" >&2
    exit 1
}

project_run() {
    case "$MODE" in
        pilot)
            die "Replace project_run() with the pilot command your project needs."
            ;;
        full)
            die "Replace project_run() with the full workload command your project needs."
            ;;
        *)
            die "Unknown mode: $MODE (expected: pilot or full)"
            ;;
    esac
}

cd "$PROJECT_DIR"

echo "=== RunPod job launch ==="
echo "Project: $PROJECT_DIR"
echo "Mode:    $MODE"

# Add project-specific env vars here if your workload needs them, for example:
# export BATCH_SIZE="${BATCH_SIZE:-32}"
# export MODEL_NAME="${MODEL_NAME:-replace-me}"

project_run
