# Evidence payloads

This directory holds typed evidence payloads against the t022 v2.3 core contract
plus any t034 / t037 / etc. extensions.

**Validation.** `validate.sh` runs `python -m t034_validator evidence/` via
`validate.local.sh`. Each `.yaml` / `.yml` file is one payload; the file's
`core.payload_id` is its registry key.

**Contract.** `t034-causal-graph-contract.md` is the durable authoring contract
for causal-graph / MR graph-model payloads and effective-code propagation.

**Authoring rules** (v1.4 hard-error policy, t034):
- Auto-injected reason codes (per the t034 v1.3 contribution table) must NOT be
  hand-written in `core.reason_codes`. The contribution-merger adds them. The
  four auto-injected codes are: `identification-missing`,
  `instrument-assumption-risk`, `mechanism-hypothesis-only`,
  `prior-network-dependent`.
- Reason codes that depend on extension *field state* (e.g. `pleiotropy-untested`,
  `reverse-causation-assumed`) are read biconditionally — over-declaration is
  an error.
- Promotion-only edge roles (`identified_causal_effect`, `mediation_path`,
  `mr_instrumental_effect`) are recorded by reference from a downstream payload,
  never authored in-place on the producing graph.
