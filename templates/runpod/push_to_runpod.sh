#!/usr/bin/env bash
# Sync a uv-based project and its required inputs to a RunPod instance.
#
# Copy this file into your project, then edit the marked project-specific
# sections before first real use.
set -euo pipefail

RUNPOD_HOST="${RUNPOD_HOST:?Set RUNPOD_HOST=root@<ip>}"
RUNPOD_PORT="${RUNPOD_PORT:-22}"
REMOTE_DIR="${REMOTE_DIR:?Set REMOTE_DIR=/workspace/<project-name>}"
LOCAL_ROOT="${LOCAL_ROOT:-.}"

die() {
    echo "ERROR: $*" >&2
    exit 1
}

project_sync_inputs() {
    die "Replace project_sync_inputs() with the data/file sync commands your project needs."
}

echo "=== Push to RunPod ==="
echo "Host:   $RUNPOD_HOST"
echo "Port:   $RUNPOD_PORT"
echo "Remote: $REMOTE_DIR"

ssh -p "$RUNPOD_PORT" "$RUNPOD_HOST" "mkdir -p $REMOTE_DIR"

echo ""
echo "=== Sync repository files ==="

# Allow-list semantics:
# - every --include adds a path that is allowed to transfer
# - the final --exclude='*' blocks everything else
# This is safer than trying to maintain a growing exclude-list.
rsync -avz --progress \
    -e "ssh -p $RUNPOD_PORT" \
    --no-owner --no-group \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='.ruff_cache' \
    --include='/src/***' \
    --include='/workflow/***' \
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
echo "=== Push complete ==="
echo "SSH to the pod and run your customized setup script next."
