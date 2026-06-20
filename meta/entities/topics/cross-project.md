---
type: topic
title: Cross-Project Knowledge and Task Coordination
status: active
created: '2026-05-07'
updated: '2026-05-07'
id: topic:cross-project
ontology_terms: []
source_refs: []
related:
- topic:structured-scientific-knowledge
---

# Cross-Project Knowledge and Task Coordination

## Summary

Science projects need to reference work that lives outside the current project
without collapsing every project into one shared repository. This topic tracks
addressing, validation, graph composition, and task coordination concerns for
peer projects.

## Key Concepts

- **Local peer declarations** — each project names its peers explicitly rather
  than discovering them implicitly, keeping the namespace model auditable.
- **Namespace-first references** — cross-project refs use the
  `<project-id>:<kind>:<slug>` form; bare and `<kind>:`-prefixed IDs always
  resolve locally.
- **Graph composition** — peer graphs compose by opt-in (`compose:`) rather than
  being merged unconditionally, so a project controls what foreign claims it
  inherits.
- **Cross-project coordination** — blockers, freshness propagation, registry
  reindexing, and change notification operate across the peer boundary.

## Current State of Knowledge

Local peer declarations are implemented as the first coordination layer
(see the project-peers work and `core/decisions.md`). Namespace-first
addressing and the commons-promote overlay/skip path are in place. Richer
behaviors — auto-unblock/change notification (`task:t051`), L2 caching and
freshness (`task:t047`), and multi-user identity scoping (`task:t050`) — remain
open follow-ups tracked in the backlog.

## Relevance to This Project

The project-peers work establishes local peer declarations as the first layer of
cross-project coordination. Follow-up work under this topic should preserve the
same explicit namespace model while adding richer blockers, freshness, registry,
and notification behavior.

## Key References

No external literature is attached to this topic yet; it is driven by internal
design decisions (`core/decisions.md`) and the cross-project coordination
backlog rather than published sources.
