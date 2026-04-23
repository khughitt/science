#!/usr/bin/env bash
# Bootstrap a uv-based project on a RunPod instance.
#
# Copy this file into your project and replace the project-specific functions
# before relying on it for real setup.
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:?Set PROJECT_DIR=/workspace/<project-name>}"
HF_TOKEN="${HF_TOKEN:?Set HF_TOKEN for gated model downloads}"
UV_PYTHON_VERSION="${UV_PYTHON_VERSION:-3.12}"
MIN_FREE_GB="${MIN_FREE_GB:-25}"
UV_HTTP_TIMEOUT="${UV_HTTP_TIMEOUT:-120}"
UV_CONCURRENT_DOWNLOADS="${UV_CONCURRENT_DOWNLOADS:-5}"
SYNC_ATTEMPTS="${SYNC_ATTEMPTS:-3}"
SETUP_MODE="${SETUP_MODE:-default}"

die() {
    echo "ERROR: $*" >&2
    exit 1
}

patch_pyproject_for_remote() {
    # Optional hook:
    # replace this with project-specific edits when local editable sources
    # exist on your workstation but not on the pod.
    :
}

project_install_runtime_tools() {
    # Optional hook:
    # install workflow CLIs that are intentionally omitted from `uv sync --no-dev`
    # but are still required on the pod, for example snakemake.
    :
}

project_runtime_smoke_test() {
    # Optional hook:
    # add mode-specific import or CLI checks here so runtime incompatibilities
    # fail before large model downloads begin.
    :
}

project_prepare_runtime() {
    die "Replace project_prepare_runtime() with your project's model download and smoke-test logic."
}

echo "=== Preflight ==="

if ! command -v nvidia-smi >/dev/null 2>&1; then
    die "nvidia-smi not found; this does not look like a GPU pod"
fi

GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)"
[[ -z "$GPU_NAME" ]] && die "No GPU detected by nvidia-smi"

AVAILABLE_GB="$(df --output=avail /workspace 2>/dev/null | tail -1 | awk '{printf "%.0f", $1/1024/1024}')"
if [[ -n "$AVAILABLE_GB" && "$AVAILABLE_GB" -lt "$MIN_FREE_GB" ]]; then
    die "Only ${AVAILABLE_GB} GB free on /workspace; need at least ${MIN_FREE_GB} GB"
fi

echo "GPU:  $GPU_NAME"
echo "Disk: ${AVAILABLE_GB:-?} GB free on /workspace"
echo "Mode: $SETUP_MODE"

cd "$PROJECT_DIR"

export HF_HOME="/workspace/.cache/huggingface"
export UV_CACHE_DIR="/workspace/.cache/uv"
export TORCH_HOME="/workspace/.cache/torch"
export UV_HTTP_TIMEOUT
export UV_CONCURRENT_DOWNLOADS
mkdir -p "$HF_HOME" "$UV_CACHE_DIR" "$TORCH_HOME"

SYNC_MARKER=".venv/.setup-sync-done"
TORCH_MARKER=".venv/.setup-torch-package-set-done"

echo ""
echo "=== Install uv ==="
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
echo "uv version: $(uv --version)"

echo ""
echo "=== Sync project dependencies ==="
uv python install "$UV_PYTHON_VERSION"

if [[ -f "$SYNC_MARKER" ]]; then
    echo "Sync marker present at $SYNC_MARKER; skipping uv sync."
else
    echo "uv HTTP timeout: ${UV_HTTP_TIMEOUT}s"
    echo "uv concurrent downloads: ${UV_CONCURRENT_DOWNLOADS}"
    echo "uv sync attempts: ${SYNC_ATTEMPTS}"
    patch_pyproject_for_remote

    sync_succeeded=0
    for ((attempt = 1; attempt <= SYNC_ATTEMPTS; attempt++)); do
        echo "uv sync attempt ${attempt}/${SYNC_ATTEMPTS}..."
        if uv sync --python "$UV_PYTHON_VERSION" --no-dev; then
            sync_succeeded=1
            break
        fi

        if (( attempt < SYNC_ATTEMPTS )); then
            sleep_seconds=$((attempt * 10))
            echo "uv sync failed; retrying in ${sleep_seconds}s..." >&2
            sleep "$sleep_seconds"
        fi
    done

    if (( sync_succeeded == 0 )); then
        die "uv sync failed after ${SYNC_ATTEMPTS} attempts (UV_HTTP_TIMEOUT=${UV_HTTP_TIMEOUT}s, UV_CONCURRENT_DOWNLOADS=${UV_CONCURRENT_DOWNLOADS})"
    fi

    mkdir -p .venv
    touch "$SYNC_MARKER"
fi

echo "Python: $(uv run --no-sync python --version)"

echo ""
echo "=== Ensure a GPU-compatible PyTorch build ==="
if echo "$GPU_NAME" | grep -qiE "blackwell|b100|b200|gb200|rtx.*pro.*6000"; then
    TORCH_SPEC="torch==2.8.0+cu128"
    TORCHVISION_SPEC="torchvision==0.23.0+cu128"
    CUDA_WHEEL="cu128"
else
    TORCH_SPEC="torch==2.5.1+cu124"
    TORCHVISION_SPEC="torchvision==0.20.1+cu124"
    CUDA_WHEEL="cu124"
fi
TORCH_PACKAGE_SET="${TORCH_SPEC} ${TORCHVISION_SPEC}"

if [[ -f "$TORCH_MARKER" && "$(cat "$TORCH_MARKER" 2>/dev/null)" == "$TORCH_PACKAGE_SET" ]]; then
    echo "Torch marker matches $TORCH_PACKAGE_SET; skipping reinstall."
else
    echo "Installing $TORCH_PACKAGE_SET from $CUDA_WHEEL..."
    uv pip install --python .venv/bin/python --reinstall \
        "$TORCH_SPEC" \
        "$TORCHVISION_SPEC" \
        --index-url "https://download.pytorch.org/whl/$CUDA_WHEEL"
    echo "$TORCH_PACKAGE_SET" > "$TORCH_MARKER"
fi

export UV_NO_SYNC=1

echo ""
echo "=== Install runtime-only tools ==="
project_install_runtime_tools

echo ""
echo "=== Runtime smoke checks ==="
uv run --no-sync python -c "import torch; import torchvision; assert torch.cuda.is_available(); print('torch', torch.__version__, 'cuda', torch.version.cuda); print('torchvision', torchvision.__version__)"
project_runtime_smoke_test

echo ""
echo "=== Project-specific runtime preparation ==="
# Use SETUP_MODE or replace it with a project-specific variable such as
# MODEL_TO_DOWNLOAD when one repository supports multiple remote workloads.
project_prepare_runtime

echo ""
echo "=== Setup complete ==="
echo "Run your customized run.sh next."
