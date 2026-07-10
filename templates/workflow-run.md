---
id: "workflow-run:<slug>"
kind: "workflow-run"
title: "<Run Description>"
status: "complete"
workflow: "workflow:<slug>"          # materializes the sci:executes edge
manifest_path: "results/<workflow>/<slug>/datapackage.yaml"  # read by `science qa-audit`
supersedes: []                       # ["workflow-run:<prior-slug>"] when re-run with changed params
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
