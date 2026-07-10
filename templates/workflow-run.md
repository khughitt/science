---
id: "workflow-run:<slug>"
kind: "workflow-run"
title: "<Run Description>"
status: "complete"
workflow: "workflow:<slug>"          # materializes the sci:executes edge
manifest_path: "results/<workflow>/<slug>/datapackage.yaml"  # read by `science qa-audit`
config_snapshot: "results/<workflow>/<slug>/config.yaml"  # required: parameters_digest is its sha256
supersedes: []                       # ["workflow-run:<prior-slug>"] when re-run with changed params
# What you assert about how this run executed. Authored, and complete on its own:
# a run validates before it has ever been registered.
execution:
  executor: "local"                            # local | commons | external
  input_artifact_locality: "science-managed"   # science-managed | external
  output_artifact_locality: "science-managed"
  # Required when — and only when — executor is `commons`: nothing local can
  # observe where an imported fingerprint came from, so you declare it.
  # capture_origin:
  #   origin_project: "project:<slug>"
  #   origin_run_ref: "workflow-run:<slug>"
  #   captured_at: "<YYYY-MM-DD>T00:00:00Z"
  #   captured_by: "science"
  #   capture_policy: "science-run-fingerprint/v1"
#
# `fingerprint:` is NOT authored. `science dataset register-run workflow-run:<slug>`
# captures it — code SHA, digests, and the `seed_policy` / `step_seeds` derived from
# the workflow's steps and their `seed_bindings`. Do not hand-write it. Editing
# `execution:` after registering makes the two disagree; `science validate` catches
# that and tells you to re-register. A workflow with no `workflow-step` cannot
# register a run at all.
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
