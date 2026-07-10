---
id: "workflow-run:<slug>"
kind: "workflow-run"
title: "<Run Description>"
status: "complete"
workflow: "workflow:<slug>"          # materializes the sci:executes edge
manifest_path: "results/<workflow>/<slug>/datapackage.yaml"  # read by `science qa-audit`
config_snapshot: "results/<workflow>/<slug>/config.yaml"  # required: parameters_digest is its sha256
supersedes: []                       # ["workflow-run:<prior-slug>"] when re-run with changed params
# Declarations, not observations — `science dataset register-run` captures the rest.
# ORDERING CONSTRAINT: this block is a stub until `register-run` completes it, and
# a stub does not satisfy the RunFingerprint schema. `science validate` and
# `science graph build` will REJECT this run until you have registered it. Author
# the run, run `science dataset register-run workflow-run:<slug>`, then validate.
# (Tracked as task:t093 — the model cannot represent "declared, not yet captured".)
fingerprint:
  executor: "local"                          # local | commons | external
  input_artifact_locality: "science-managed"   # science-managed | external
  output_artifact_locality: "science-managed"
# `seed_policy` and `step_seeds` are DERIVED at register-run from the workflow's
# steps, their `seed_bindings`, and the realized values. Hand-authoring either is
# an error. A workflow with no `workflow-step` cannot register a run at all.
# Symmetric edges (populated by `science dataset register-run`).
# `produces:` is the inverse of dataset.derivation.workflow_run (state invariant #9).
# `inputs:` enumerates upstream datasets the run consumed; symmetric with each
# upstream dataset's consumed_by listing this workflow-run.
produces: []                       # ["dataset:<slug>", ...]
inputs: []                         # ["dataset:<slug>", ...]
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---

## Summary

What this run produced and why it was executed.

## Manifest

- **Location:** `results/<workflow>/<slug>/datapackage.yaml`
- **Config snapshot:** `results/<workflow>/<slug>/config.yaml`

## Entity Cross-References

- **Tests:** `question:<id>`, `hypothesis:<id>`
- **Tasks:** `task:<id>`
- **Supersedes:** `workflow-run:<slug>` (if applicable)

## Key Results

Brief summary of primary findings or outputs from this run.

## Sequences

List any FASTA outputs in `results/<workflow>/<slug>/sequences/`.

## Related

- **Workflow:** `workflow:<slug>`
- **Interpretation:** `interpretation:<slug>` (if results have been interpreted)
