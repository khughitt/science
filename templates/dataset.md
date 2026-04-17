---
id: "dataset:<accession-or-slug>"
type: "dataset"
title: "<Dataset Name>"
status: "active"
tier: "evaluate-next"              # use-now | evaluate-next | track
access: "public"                   # public | controlled | mixed
license: ""                        # SPDX identifier (e.g., CC-BY-4.0) or "unknown"
formats: []                        # e.g., ["tsv", "h5ad", "parquet"]
size_estimate: ""                  # e.g., "12 GB", "~500 MB", "unknown"
update_cadence: ""                 # e.g., "static", "quarterly", "rolling"
ontology_terms: []                 # CURIEs: UBERON:*, CL:*, MONDO:*, DOID:*, GO:*, etc.
datasets:                          # one or more accessions (see Multi-accession below)
  - "<accession>"
source_refs: []
related: []
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---

# <Dataset Name>

## Summary

<What the dataset contains and why it is relevant.>

## Access and Scope

- Accessions:
- Source URL:
- Organism/population:
- Modality:
- Sample size:

## Thoughts

- <strength>
- <limitation or bias>

## Connections to Project

- Questions/hypotheses it can inform:
- Variables likely available:
- Planned usage:

## Related

- Topic notes:
- Method notes:
- Article notes:

<!--
Frontmatter field notes:

- `tier`: reading/use priority.
  - `use-now`    — download and integrate immediately
  - `evaluate-next` — promising, inspect before committing
  - `track`      — potentially useful, defer

- `access`: `public` (open), `controlled` (dbGaP / EGA / application required),
  `mixed` (some resources public, some controlled).

- `license`: prefer SPDX identifiers (https://spdx.org/licenses/).
  Examples: `CC-BY-4.0`, `CC0-1.0`, `ODbL-1.0`, `custom`, `unknown`.

- `formats`: lower-case file extensions or format slugs.
  Examples: `tsv`, `csv`, `parquet`, `h5ad`, `mtx`, `bam`, `vcf`, `loom`, `nii`.

- `size_estimate`: include unit. Use `"unknown"` rather than leaving blank.

- `update_cadence`: one of
  `static` | `rolling` | `monthly` | `quarterly` | `annual` | `versioned-releases`.

- `ontology_terms`: use canonical CURIEs. Examples:
  - Anatomy: `UBERON:0002048` (lung)
  - Cell type: `CL:0000127` (astrocyte)
  - Disease: `MONDO:0005148` (type-2 diabetes) or `DOID:9352`
  - Tissue/assay: `EFO:0003021` (RNA-seq)
  Avoid free-text labels here; use a structured registry term.

- `datasets`: the list accepts multiple accessions for resources that span
  several deposits (e.g., primary + mirror, atlas + component studies, CPTAC
  studies spanning PDC + cBioPortal). See "Multi-accession resources" below.

## Multi-accession resources

Some high-value resources are split across multiple accessions (primary host +
mirror, parent atlas + component studies, etc.). Three acceptable patterns:

1. **One record, multi-accession list (preferred for tight siblings).**
   Use this when all accessions describe the same underlying data. List every
   accession in `datasets:` and in the `## Access and Scope` section.

2. **Parent + child records (preferred for atlases).**
   Create one overview record for the atlas and one per component study. Use
   the `related:` list to link children to the parent. Tier the parent as
   `evaluate-next` and tier children based on individual value.

3. **One record per accession (last resort).**
   Use only when the accessions are independently meaningful and share little
   context. Cross-link via `related:`.

Default to pattern 1 when in doubt.
-->
