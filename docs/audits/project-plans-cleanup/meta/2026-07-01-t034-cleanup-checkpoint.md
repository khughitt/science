# t034 cleanup checkpoint

Date: 2026-07-01

## Summary

The t034 causal graph construction design/prototype cluster has been migrated
out of active plans.

Durable replacements:

- `meta/evidence/t034-causal-graph-contract.md` records the authoring contract
  enforced by the production validator.
- `meta/tests/test_t034_validator.py` carries the prototype test coverage as
  normal pytest coverage against `meta/src/t034_validator/`.
- `meta/entities/questions/0010-causal-graph-construction-pipeline.md`,
  `meta/entities/synthesis/0010-rich-evidence-payloads-improve-graph-calibration.md`,
  and `meta/tasks/done/2026-06.md` record the current project state.

Moved to `meta/doc/plans/historical/`:

- `2026-05-06-t034-causal-graph-extension-design.md`
- `2026-05-06-t034-pilot-extraction.md`
- `2026-05-06-t034-validator-prototype-findings.md`
- `2026-05-06-t034-causal-graph-validator-prototype.py`
- `2026-05-06-t034-effective-codes-validator-findings.md`
- `2026-05-06-t034-effective-codes-validator-prototype.py`
- `2026-05-06-t034-mr-graph-model-validator-findings.md`
- `2026-05-06-t034-mr-graph-model-validator-prototype.py`

Remaining active meta plan threads after this checkpoint should be the t022
contract reconciliation and adaptive topology follow-up.
