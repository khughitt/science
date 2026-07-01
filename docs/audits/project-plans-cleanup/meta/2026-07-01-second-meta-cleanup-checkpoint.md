# Second Meta Cleanup Checkpoint

Date: 2026-07-01

This cleanup slice reviewed the remaining `meta/doc/plans/` backlog after the
first h01/t030 pass. It moved only threads whose active planning role had ended
and left incomplete contract work in place.

## Moved To Historical

### t023

`t023` typed synthesis nodes moved to `meta/doc/plans/historical/` because the
contract is now captured in `science/docs/typed-synthesis-nodes.md` and
implemented by `science_tool.synthesis_payload`. The deferred lifecycle and
output-artifact model remains active as `t042`.

### h00 RFC

The epistemic causal/probabilistic graph model RFC moved to historical. Its
settled architecture is now carried by D-005, D-006, D-007,
`meta/entities/hypotheses/0007-working-model.md`, and
`docs/user-guide/science-model.md`. Remaining hardening belongs to active
follow-ups such as `t069` and `t070`.

### t037

The `t037` agent/tool operations design, implementation plan, pilot extraction,
prototype, and findings moved to historical. This is a completed
design/prototype thread, not a production implementation. The durable question
record `meta/entities/questions/0012-agent-tool-kg-operations.md` now states the
answer/follow-up split: production registry storage, durable validator
integration, `agent-evaluation`, propagation integration, and project-local
trace/frontmatter sidecars remain future work.

## Deferred

### t034

The `t034` causal graph validator is implemented in `meta/src/t034_validator/`
and wired through `meta/validate_local.py`, but the active plan files still hold
contract detail and executable prototype fixtures. Do not move the thread until
a durable non-plan contract page captures the v1.4 rule set and the prototype
self-tests are either ported to `meta/tests/` or explicitly retired as
historical-only fixtures.

### t022

The evidence-payload core contract remains active. The code and v2.3 plan have
known drift around fields such as `target_artifact_ref`, `claim_source_ref`,
`partial_fields`, and `uncertainty_summary`, so it needs a reconciliation pass
before archival.

### Adaptive Topology

The adaptive topology / `bio/meta` planning note remains active. It has durable
question and hypothesis records, but only `t055` is complete; `t053`, `t054`,
`t056`, `t057`, and `t058` remain active/proposed.
