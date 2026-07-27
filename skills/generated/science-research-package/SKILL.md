---
name: science-research-package
description: "Use when building or validating a research-package bundle (datapackage + cells) and its provenance route. Routes to the research-package leaves."
---

# Research-Package Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when producing or validating a research-package artifact, before any leaf.

## Scope boundary

Covers the research-package descriptor contract and the component that renders its provenance route.
Excludes general dataset-directory conventions (see `science-data-management` skill).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `references/research-package-spec.md` | validating the datapackage.json + cells.json bundle | rendering/UI concerns only |
| `references/research-package-rendering.md` | wiring a `/src` provenance route to a package | contract validation only |

## Decision / compose order

`research-package-spec` (layer 1) is the contract `research-package-rendering` builds on.

## Parent & neighbors

- Parent index: `science-command-preamble` skill's `references/methodology-index.md`
- Neighboring routers: `science-literature` skill, `science-data-management` skill

## Success test

A research-package task routes to the correct leaf with no methodology read from this router.

## Companion Skills

- `science-command-preamble` skill's `references/methodology-index.md` — the skill index.
