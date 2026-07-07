# Guidance Cleanup Plan

Date: 2026-07-07
Status: implemented

## Steps

1. Add regression tests in `science/tests/test_command_docs.py` for pre-register and interpret-results guidance.
2. Add generated-skill tests in `science/tests/test_codex_skills.py` so command changes remain mirrored into Codex skills.
3. Add a user-guide test in `science/tests/test_user_guide_docs.py` for feedback as upstream task assignment.
4. Update `commands/pre-register.md`, `commands/interpret-results.md`, and `docs/user-guide/feedback-and-telemetry.md`.
5. Regenerate committed Codex skill mirrors with `scripts/generate_codex_skills.py`.
6. Run focused tests plus `ruff`.

## Non-Goals

- No new feedback CLI command.
- No new validation rule for derivation-cohort circularity.
- No changes to belief aggregation thresholds.
