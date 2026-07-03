---
id: "dataset:<slug>"
type: "dataset"
title: "<Dataset Name — artefact-level specific>"
status: "active"
profiles: ["science-pkg-entity-1.0"]
origin: "external"                # external | derived
dataset_class: "deposit"          # deposit | reference | pointer
tier: "evaluate-next"             # use-now | evaluate-next | track
license: ""                       # SPDX id (e.g. CC-BY-4.0) or sentinel: unknown | proprietary | custom
update_cadence: ""                # static | rolling | monthly | ...
ontology_terms: []                # CURIEs

# Project-level biological identity context. This is authored on the dataset
# entity; any datapackage science.identity_context stamp is derived/read-only.
identity_context:
  taxon:
    ncbi_taxid: 9606              # NCBI taxid integer
    resolution_status: resolved
  assembly:
    seqcol_digest: "g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp"
    registry: "dataset:assembly-registry"
    resolution_status: resolved
  molecular_ids:
    gene:
      namespace: hgnc
      registry: "dataset:gene-crosswalk-hgnc"
      resolution_status: declared_unresolved
      unresolved_value: UNKNOWN   # Use UNKNOWN when declared but not resolved; omit digest fields until resolved.

# Pointer to the runtime datapackage.yaml (entity surface does NOT carry resources[])
datapackage: ""
local_path: ""                    # external single-file escape hatch (mutually exclusive with datapackage)

# External-only — REMOVE if origin: derived
accessions: []                    # external accession IDs (renamed from `datasets:`)
access:
  level: "public"                 # public | registration | controlled | commercial | mixed
  availability: "available"       # available | embargoed | withdrawn
  available_after: ""             # free-form window (ISO date when known, else e.g. "2026-Q3", "after Lee2026 publication"). Only set when availability is "embargoed".
  verified: false
  verification_method: ""         # "" | retrieved | credential-confirmed | landing-confirmed | metadata-confirmed
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
  reproducibility:                # can an INDEPENDENT party regenerate the analysis?
    obtainability: unknown        # public | registration | self-service-dua | approved-researcher | approved-project | named-collaboration | unavailable | unknown
    execution: unknown            # local | hosted-workspace | trusted-environment | federated-code-to-data | custodian-run | unknown
    extractability: unknown       # full-dataset | analysis-dataset | synthetic-dataset | aggregate-unreviewed | aggregate-reviewed | none | unknown
    notes: ""                     # free-form, e.g. "Only reviewed aggregates leave the enclave."

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
