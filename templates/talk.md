---
id: "talk:{{citekey}}"
type: "talk"
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
    type: { default: "talk" }
    title: { from: title }
    status: { from: status }
    ontology_terms: { default: [] }
    source_refs: { from: source_refs }
    related: { from: related }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: overview, name: "Overview", required: true }
    - { key: key-points, name: "Key Points", required: true }
    - { key: relevance, name: "Relevance", required: true }
    - { key: source-details, name: "Source Details", required: true }
    - { key: follow-up, name: "Follow-up", required: false }
---

# {{title}}

<!--
- **Speakers:** <speakers>
- **Venue / event:** <venue>
- **Date:** <YYYY-MM-DD>
- **Video URL:** <url>
- **Transcript:** <path-or-url>
- **BibTeX key:** <bibtex-key>
-->

## Overview

<!-- 2-3 sentences: who presented, the main topic, the event. -->

## Key Points

<!-- The takeaways that matter for our project. -->

## Relevance

<!-- How does this connect to our research questions/hypotheses/workstreams?
Reference entity IDs. A talk is an unrefereed source: treat its claims as
hints to verify, not settled evidence. -->

## Source Details

<!-- Video URL, duration, transcript location, date presented, speaker affiliations. -->

## Follow-up

<!-- Related talks/papers. Questions this raises for our project. -->
