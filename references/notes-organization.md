# Notes Organization

This document defines the compact note layer for Science projects.
Notes are short, link-heavy artifacts optimized for quick retrieval by humans and agents.

## Goals

- Keep operational knowledge compact and searchable.
- Avoid duplicating long-form summaries in `doc/` and `papers/summaries/`.
- Standardize metadata for filtering, linking, and graph alignment.

## Directory Layout

```
notes/
├── index.md
├── topics/
├── articles/
├── questions/
├── methods/
└── datasets/
```

## Metadata Contract (All Note Types)

Use YAML frontmatter with these fields:

```yaml
id: "topic:single-cell-rna-seq"
type: "topic"                # topic | article | question | method | dataset
title: "Single-cell RNA-seq"
status: "active"             # seed | active | archived
tags: []                     # free-form project tags
ontology_terms: []           # ontology CURIEs, e.g., mesh:D009369, go:0008150, biolink:Gene
datasets: []                 # optional dataset accessions, e.g., GSE161529, PRJNA123456
source_refs: []              # citation keys, DOI URLs, or trusted links
related: []                  # note IDs, question IDs, hypothesis IDs
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
```

## Source of Truth Boundaries

- `papers/references.bib` is the citation source of truth.
- `papers/summaries/*.md` holds deep paper summaries.
- `notes/articles/*.md` holds compact paper notes and links to summaries.
- `doc/background/*.md` holds long-form topic synthesis.
- `notes/topics/*.md` holds compact topic notes and action links.

## Common Body Sections

All note types should include:

1. `## Summary`
2. `## Thoughts`
3. `## Connections to Project`
4. `## Related`

Entity-specific templates can add sections as needed.

