# Plans Cleanup Pending Triage

- Source index: `docs/audits/project-plans-cleanup/meta/thread-index.json`
- Pending thread count: `7`

## adaptive-project-topology-and-bio-meta-next-steps

- status: `incomplete`
- recommended_action: `keep active`
- actions: `deferred`
- files:
  - `meta/doc/plans/2026-05-17-adaptive-project-topology-and-bio-meta-next-steps.md`
- pending_actions:
  - `deferred`: no reason recorded
    - `meta/doc/plans/2026-05-17-adaptive-project-topology-and-bio-meta-next-steps.md`
- remaining_gaps:
  - Complete the signal metrics, recommendation workflow, topology audit pilot, and bio/meta scaffold brief before archival.

## evidence-payload-core-and-extension-contract

- status: `incomplete`
- recommended_action: `keep active`
- actions: `deferred`
- files:
  - `meta/doc/plans/2026-05-06-evidence-payload-core-and-extension-contract.md`
- pending_actions:
  - `deferred`: no reason recorded
    - `meta/doc/plans/2026-05-06-evidence-payload-core-and-extension-contract.md`
- remaining_gaps:
  - Create a durable non-plan contract page reconciling t022 v2.3 with current implementation before archival.
  - Resolve or explicitly document code/design drift for target refs, claim_source_ref, partial_fields, and uncertainty_summary.

## t034-causal-graph-extension

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `meta/doc/plans/2026-05-06-t034-causal-graph-extension-design.md`
- pending_actions:
  - `migration_checkpoint_created`: no reason recorded
    - `meta/doc/plans/2026-05-06-t034-causal-graph-extension-design.md`
- remaining_gaps:
  - Create a durable non-plan t034 contract page under meta/evidence/ or an equivalent durable location.
  - Port prototype self-tests into meta/tests/ or explicitly retire them as historical-only fixtures.
  - Update question and synthesis records after the durable contract/test decision lands.

## t034-effective-codes-validator

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `meta/doc/plans/2026-05-06-t034-effective-codes-validator-findings.md`
- pending_actions:
  - `migration_checkpoint_created`: no reason recorded
    - `meta/doc/plans/2026-05-06-t034-effective-codes-validator-findings.md`
    - `meta/doc/plans/2026-05-06-t034-effective-codes-validator-prototype.py`
- remaining_gaps:
  - Port or retire the prototype self-tests and capture the effective-code rules in a durable contract page.

## t034-mr-graph-model-validator

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `meta/doc/plans/2026-05-06-t034-mr-graph-model-validator-findings.md`
- pending_actions:
  - `migration_checkpoint_created`: no reason recorded
    - `meta/doc/plans/2026-05-06-t034-mr-graph-model-validator-findings.md`
    - `meta/doc/plans/2026-05-06-t034-mr-graph-model-validator-prototype.py`
- remaining_gaps:
  - Port or retire the prototype self-tests and capture MR graph model rules in a durable contract page.

## t034-pilot-extraction

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `meta/doc/plans/2026-05-06-t034-pilot-extraction.md`
- pending_actions:
  - `migration_checkpoint_created`: no reason recorded
    - `meta/doc/plans/2026-05-06-t034-pilot-extraction.md`
- remaining_gaps:
  - Capture pilot-derived authoring rules in a durable t034 contract page before moving the pilot historical.

## t034-validator-prototype

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `meta/doc/plans/2026-05-06-t034-validator-prototype-findings.md`
- pending_actions:
  - `migration_checkpoint_created`: no reason recorded
    - `meta/doc/plans/2026-05-06-t034-validator-prototype-findings.md`
    - `meta/doc/plans/2026-05-06-t034-causal-graph-validator-prototype.py`
- remaining_gaps:
  - Decide whether the prototype self-tests remain executable fixtures or are ported into meta/tests/.
