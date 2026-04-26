#!/usr/bin/env bash
# science-managed-artifact: validate.sh
# science-managed-version: 2026.04.26
# science-managed-source-sha256: 0000000000000000000000000000000000000000000000000000000000000000

set -euo pipefail

# === managed-artifact: hook infrastructure ===
declare -A SCIENCE_VALIDATE_HOOKS=()

register_validation_hook() {
  local hook_name="$1"
  local fn_name="$2"
  if [[ -z "${SCIENCE_VALIDATE_HOOKS[$hook_name]:-}" ]]; then
    SCIENCE_VALIDATE_HOOKS[$hook_name]="$fn_name"
  else
    SCIENCE_VALIDATE_HOOKS[$hook_name]+=" $fn_name"
  fi
}

dispatch_hook() {
  local hook_name="$1"
  local fns="${SCIENCE_VALIDATE_HOOKS[$hook_name]:-}"
  for fn in $fns; do
    "$fn"
  done
}

# Source the project-local sidecar BEFORE any validation runs.
if [[ -f "validate.local.sh" ]]; then
  # shellcheck source=/dev/null
  source "validate.local.sh"
fi

# === canonical body ===
echo "BEGIN"
dispatch_hook "before_pre_registration_check"
echo "MIDDLE"
dispatch_hook "after_synthesis_check"
echo "END"
dispatch_hook "final_summary"
