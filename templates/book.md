---
id: "book:{{nn}}-{{slug}}"
type: "book"
title: "{{title}}"
status: "active"
ontology_terms: []
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
_template:
  frontmatter:
    id: { from: entity_id }
    type: { default: "book" }
    title: { from: title }
    status: { from: status }
    ontology_terms: { default: [] }
    source_refs: { from: source_refs }
    related: { from: related }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: overview, name: "Overview", required: true }
    - { key: whole-book-synthesis, name: "Whole-Book Synthesis", required: true }
    - { key: chapter-map, name: "Chapter Map", required: true }
    - { key: key-themes, name: "Key Themes", required: true }
    - { key: relevance, name: "Relevance", required: true }
    - { key: limitations, name: "Limitations", required: true }
    - { key: follow-up, name: "Follow-up", required: true }
---

# {{title}}

<!--
- **Authors:** <authors>
- **Year:** <year>
- **Publisher:** <publisher>
- **ISBN:** <isbn>
- **BibTeX key:** <bibtex-key>
- **Source:** PDF
-->

## Overview

<!-- Bibliographic block + scope / intended audience. What kind of book is this? -->

## Whole-Book Synthesis

<!-- The cross-chapter argument and through-lines. Synthesized after all chapters. -->

## Chapter Map

<!-- Table: chapter # -> link to ../../doc/books/<citekey>/chNN-*.md -> one-line gist. -->

| # | Chapter | Gist |
|---|---------|------|

## Key Themes

<!-- Recurring concepts that span chapters. -->

## Relevance

<!-- Connection to project research questions / hypotheses. Reference hypothesis/question IDs. -->

## Limitations

<!-- What the book does not cover; dated or contested positions. -->

## Follow-up

<!-- Derived questions, chapters worth re-reading, related papers to ingest. -->
