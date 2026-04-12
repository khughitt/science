---
id: "workflow-run:<slug>"
type: "workflow-run"
title: "<Run Description>"
status: "complete"
workflow: "<workflow-slug>"
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---

## Summary

What this run produced and why it was executed.

## Manifest

- **Location:** `results/<workflow>/<slug>/datapackage.json`
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
