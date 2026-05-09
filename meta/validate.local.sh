#!/usr/bin/env bash
# Project-local validation hooks for science-meta.
# Sourced by the framework's validate.sh when present (see
# ../science/src/science_tool/project_artifacts/data/validate.sh:26).

# t034 evidence-payload validator. Runs the bundled slice rules against any
# YAML payloads under evidence/. Empty directory passes silently (0 payloads).
t034_payload_check() {
    info "t034: validating evidence payloads"
    local out
    if ! out=$(uv run --quiet python -m t034_validator evidence 2>&1); then
        printf '%s\n' "$out"
        error "t034: evidence-payload validator failed (see lines above)"
        return 1
    fi
    # Surface the summary line even on success when verbose
    info "$(printf '%s\n' "$out" | tail -n 1)"
}

register_validation_hook "extra_checks" "t034_payload_check"
