# Meta Project Plans Cleanup Checkpoint

This checkpoint starts the project-level cleanup pass with `meta/doc/plans/`.
The goal is the same as the root `docs/plans/` cleanup: remove completed
execution artifacts from the active planning surface while preserving useful
design provenance and moving durable state into entities, synthesis notes, and
project docs.

## Moved To Historical

### h01

Moved:

- `meta/doc/plans/2026-04-24-h01-simulator.md`
- `meta/doc/plans/2026-04-24-h01-simulator-spec.md`
- `meta/doc/plans/2026-04-24-h01-sweep-and-interpretation.md`
- `meta/doc/plans/2026-04-24-h01-engine-followups.md`

Reason: the simulator engine, follow-ups, sweep output, notebook, and
interpretation are implemented. Durable state now lives in
`meta/entities/interpretations/0001-simulator-2026-04-24.md`,
`meta/entities/synthesis/0009-stochastic-revisiting.md`, and the updated
`meta/entities/hypotheses/0001-stochastic-revisiting.md`.

Remaining work is follow-on research, not unfinished h01 plan work: t004
r-curve extension, t005 Gaussian effect-size variant, and t025 reason-coded
attention.

### t030

Moved:

- `meta/doc/plans/2026-05-06-t030-narrow-authoring-cost-audit.md`
- `meta/doc/plans/2026-05-06-t030-full-sampling-plan-and-rubric.md`
- `meta/doc/plans/2026-05-06-t030-llm-pass-1-output.md`
- `meta/doc/plans/2026-05-06-t030-llm-pass-2-output.md`
- `meta/doc/plans/2026-05-06-t030-full-audit-results.md`

Reason: the authoring-cost audit is complete and already shaped the t022
contract. Durable state now lives in `meta/evidence/t022-core-contract.md`,
`meta/doc/plans/historical/2026-05-06-evidence-payload-core-and-extension-contract.md`,
`meta/entities/questions/0005-authoring-cost-audit.md`, and
`meta/entities/synthesis/0010-rich-evidence-payloads-improve-graph-calibration.md`.

The useful follow-up is narrower than t030: recover the originally intended
full-context-human-vs-blind-LLM signal or run a multi-model extraction audit.

## Deferred Threads

### t034

The t034 causal graph / effective-code validator functionality is implemented
in `meta/src/t034_validator/` and wired through `meta/validate_local.py`, but
the plan files still function as the practical contract and fixture record.
Keep the t034 thread active until a durable non-plan contract page captures the
graph role rules, MR rules, effective-code semantics, auto-injection,
retirement, and validate hook behavior.

### t037

The t037 agent/tool operations design is complete and the prototype passes, but
production implementation was explicitly deferred. Keep it active until the
accepted schema is distilled into durable docs and
`meta/entities/questions/0012-agent-tool-kg-operations.md` is updated with the
answer/follow-up split.
