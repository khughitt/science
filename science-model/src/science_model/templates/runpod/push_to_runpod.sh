#!/usr/bin/env bash
# Sync a uv-based project and its required inputs to a RunPod instance.
#
# Copy this file into your project, then edit the marked project-specific
# sections before first real use.
set -euo pipefail

RUNPOD_JOB="${RUNPOD_JOB:-default}"
RUNPOD_HOST="${RUNPOD_HOST:?Set RUNPOD_HOST=root@<ip>}"
RUNPOD_PORT="${RUNPOD_PORT:-22}"
REMOTE_DIR="${REMOTE_DIR:?Set REMOTE_DIR=/workspace/<project-name>}"
LOCAL_ROOT="${LOCAL_ROOT:-.}"
RSYNC_BASE_FLAGS=(-avz --progress --no-owner --no-group --partial --partial-dir=".rsync-partial")
RSYNC_RESUME_FLAGS=(-avz --progress --no-owner --no-group --partial --append-verify)

die() {
    echo "ERROR: $*" >&2
    exit 1
}

rsync_large_file() {
    local source_path="$1"
    local dest_path="$2"
    rsync "${RSYNC_RESUME_FLAGS[@]}" -e "ssh -p $RUNPOD_PORT" "$source_path" "$RUNPOD_HOST:$dest_path"
}

project_sync_inputs() {
    die "Replace project_sync_inputs() with the data/file sync commands your project needs."
}

project_sync_artifacts() {
    # Optional hook:
    # add large immutable artifact uploads here when the pod should consume
    # precomputed outputs instead of rebuilding them remotely.
    #
    # Example:
    # rsync_large_file "results/model/full.h5" "$REMOTE_DIR/results/model/full.h5"
    :
}

echo "=== Push to RunPod ==="
echo "Host:   $RUNPOD_HOST"
echo "Port:   $RUNPOD_PORT"
echo "Remote: $REMOTE_DIR"
echo "Job:    $RUNPOD_JOB"

ssh -p "$RUNPOD_PORT" "$RUNPOD_HOST" "mkdir -p $REMOTE_DIR"

echo ""
echo "=== Sync repository files ==="

# Allow-list semantics:
# - every --include adds a path that is allowed to transfer
# - the final --exclude='*' blocks everything else
# This is safer than trying to maintain a growing exclude-list.
rsync "${RSYNC_BASE_FLAGS[@]}" \
    -e "ssh -p $RUNPOD_PORT" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='.ruff_cache' \
    --include='/src/***' \
    --include='/workflow/***' \
    --include='/code/***' \
    --include='/scripts/***' \
    --include='/runpod/***' \
    --include='/pyproject.toml' \
    --include='/uv.lock' \
    --include='/README.md' \
    --include='/AGENTS.md' \
    --include='/CLAUDE.md' \
    --exclude='*' \
    "$LOCAL_ROOT/" "$RUNPOD_HOST:$REMOTE_DIR/"

echo ""
echo "=== Sync project-specific inputs ==="
project_sync_inputs

echo ""
echo "=== Sync optional precomputed artifacts ==="
project_sync_artifacts

echo ""
echo "=== Push complete ==="
echo "SSH to the pod and run your customized setup script next."
echo ""
echo "If a large artifact upload is interrupted, rerun this script."
echo "The resumable rsync flags will skip completed files and continue partial uploads when possible."
