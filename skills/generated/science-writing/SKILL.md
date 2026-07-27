---
name: science-writing
description: "Use when scientific prose for a research project is in scope. Routes to the writing leaves below."
---

# Writing Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when writing or editing project prose is in scope, before
loading any leaf.

For analysis-readiness planning, start at `science-command-preamble` skill's `references/methodology-index.md` or run
`science-plan-analysis`.

## Scope boundary

Covers prose conventions for project documents — voice, hedging, structure,
and framework connection. Excludes citation conformance and source evaluation
(see `science-literature` skill).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `science-scientific-writing` skill | Writing or editing any research document, entity description, or project prose | Only validating citation keys — load `science-literature` skill |

## Decision / compose order

Leaves are independent. Compose with
`science-literature` skill
whenever the prose carries citations.

## Parent & neighbors

- Parent index: `science-command-preamble` skill's `references/methodology-index.md`
- Neighboring routers: `science-literature` skill, `science-epistemics` skill, `science-statistics` skill

## Success test

Representative in-scope tasks route to the correct leaf (or the correct compose order when leaves combine) without any methodology being read from this router.

## Companion Skills

- `science-command-preamble` skill's `references/methodology-index.md` — the skill index.
