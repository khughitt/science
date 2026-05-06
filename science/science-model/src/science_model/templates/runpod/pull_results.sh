#!/usr/bin/env bash
# Pull project-specific outputs back from a RunPod instance.
#
# Copy this file into your project, then replace project_pull_outputs()
# before first real use.
set -euo pipefail

RUNPOD_JOB="${RUNPOD_JOB:-default}"
RUNPOD_HOST="${RUNPOD_HOST:?Set RUNPOD_HOST=root@<ip>}"
RUNPOD_PORT="${RUNPOD_PORT:-22}"
REMOTE_DIR="${REMOTE_DIR:?Set REMOTE_DIR=/workspace/<project-name>}"
LOCAL_ROOT="${LOCAL_ROOT:-.}"

die() {
    echo "ERROR: $*" >&2
    exit 1
}

project_pull_outputs() {
    die "Replace project_pull_outputs() with the result sync commands your project needs."
}

echo "=== Pull results from RunPod ==="
echo "Host:   $RUNPOD_HOST"
echo "Port:   $RUNPOD_PORT"
echo "Remote: $REMOTE_DIR"
echo "Job:    $RUNPOD_JOB"

project_pull_outputs

echo ""
echo "=== Pull complete ==="
