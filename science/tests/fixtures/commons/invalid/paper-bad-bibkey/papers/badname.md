---
schema_profile: "science-entity-base/1.0+paper/1.0"
id: "paper:bad-name"
kind: "paper"
title: "Paper with non-camelcase bibkey"
version: "1.0.0"
status: "active"
created: "2026-05-13"
updated: "2026-05-13"
bibkey: "bad-name"
authors: ["X"]
year: 2025
journal: "Test"
ontology_terms: []
tags: []
---

# Bad bibkey

`bibkey` and `id` slug contain hyphens, which the paper-mixin regex rejects
(it expects camelcase like `Adams2025`).
