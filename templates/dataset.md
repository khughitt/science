---
id: "dataset:<slug>"
type: "dataset"
title: "<Dataset Name — artefact-level specific>"
status: "active"
profiles: ["science-pkg-entity-1.0"]
origin: "external"                # external | derived
tier: "evaluate-next"             # use-now | evaluate-next | track
license: ""                       # SPDX identifier or "unknown"
update_cadence: ""                # static | rolling | monthly | ...
ontology_terms: []                # CURIEs

# Pointer to the runtime datapackage.yaml (entity surface does NOT carry resources[])
datapackage: ""
local_path: ""                    # external single-file escape hatch (mutually exclusive with datapackage)

# External-only — REMOVE if origin: derived
accessions: []                    # external accession IDs (renamed from `datasets:`)
access:
  level: "public"                 # public | registration | controlled | commercial | mixed
  verified: false
  verification_method: ""         # "" | retrieved | credential-confirmed
  last_reviewed: ""               # YYYY-MM-DD
  verified_by: ""
  source_url: ""
  credentials_required: ""
  exception:
    mode: ""                      # "" | scope-reduced | expanded-to-acquire | substituted
    decision_date: ""
    followup_task: ""
    superseded_by_dataset: ""
    rationale: ""

# Derived-only — UNCOMMENT and populate when origin: derived; REMOVE access: above
# derivation:
#   workflow: "workflow:<slug>"
#   workflow_run: "workflow-run:<slug>"
#   git_commit: ""
#   config_snapshot: ""
#   produced_at: ""
#   inputs:
#     - "dataset:<upstream-slug>"

# Lineage
parent_dataset: ""
siblings: []

# Backlinks (written by plan-pipeline Step 4.5 / register-run)
consumed_by: []

source_refs: []
related: []
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---

# <Dataset Name>

## Summary

<What the dataset contains and why it is relevant.>

## Access verification log

<!-- Append-only chronological log; one entry per verification event. -->
<!-- Format: - YYYY-MM-DD (agent-or-user): brief note. -->

## Granularity at this access level

<!-- For granular siblings: state explicitly what THIS entity covers vs what sibling entities cover. -->

## Connections to Project

- Questions/hypotheses it can inform:
- Variables likely available:
- Planned usage:

## Related

- Topic notes:
- Method notes:
- Article notes:
