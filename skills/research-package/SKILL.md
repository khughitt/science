---
name: research-package
description: Use when building or validating a research-package bundle (datapackage + cells) and its provenance route. Routes to the research-package leaves.
provenance: internal
---

# Research-Package Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when producing or validating a research-package artifact, before any leaf.

## Scope boundary

Covers the research-package descriptor contract and the component that renders its provenance route.
Excludes general dataset-directory conventions (see `../data-management/SKILL.md`).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `research-package-spec.md` | validating the datapackage.json + cells.json bundle | rendering/UI concerns only |
| `research-package-rendering.md` | wiring a `/src` provenance route to a package | contract validation only |

## Decision / compose order

`research-package-spec` (layer 1) is the contract `research-package-rendering` builds on.

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring routers: `../literature/SKILL.md`, `../data-management/SKILL.md`

## Success test

A research-package task routes to the correct leaf with no methodology read from this router.

## Companion Skills

- `../INDEX.md` — the skill index.
