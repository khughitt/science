# Guidance Cleanup Design

Date: 2026-07-07
Status: implemented

## Feedback Items

- `fb-2026-07-03-003`: pre-register should flag derivation-cohort circularity when the proposed validation vehicle helped train or validate the scored signature.
- `fb-2026-07-04-002`: interpret-results should distinguish authoring a new intentionally fragile single-line proposition from touching an existing one.
- `fb-2026-07-04-009`: feedback should be discoverable as an upstream task-assignment channel, not only passive commentary.

## Design

This is a guidance-only change. No CLI behavior or schema changes are needed.

For pre-registration, the check belongs in §1b because that section already forces agents to inspect real input artifacts before locking thresholds. The circularity case is a data-fitness failure: a vehicle that helped train or validate the scored signature cannot independently adjudicate whether the signature is predictive versus merely prognostic in that same cohort.

For interpret-results, the fragile-single-line guidance belongs immediately after the health check that asks agents to confirm `belief.fragile-single-line` did not newly fire. The important distinction is causal responsibility:

- New single-line propositions may be correct and should keep the warning.
- Existing propositions should be investigated only if the current run made them newly single-line.

For feedback discoverability, the durable home is `docs/user-guide/feedback-and-telemetry.md`. There is no `commands/feedback.md` source command. The guide should state that open non-positive feedback is also the upstream task-assignment queue for Science toolkit work.

## Acceptance Criteria

- Command docs mention derivation-cohort circularity and independent validation vehicles.
- Interpret-results docs distinguish new single-line authoring from touching existing propositions.
- Feedback user guide states that open feedback is actionable upstream task assignment.
- Generated Codex skill mirrors reflect command-doc changes.
- Focused command-doc, skill, and user-guide tests pass.
