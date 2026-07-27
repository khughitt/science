---
name: <subject>
description: Use when <the analysis phase this subtree governs> is in scope. Routes to the leaves below.
provenance: internal
---

# <Subject> Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when <the task class> is in scope, before loading any leaf.

## Scope boundary

<One sentence naming exactly what this subtree covers and what it excludes.>

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `<leaf-a>.md` | <specific trigger> | <when it does not apply> |
| `<leaf-b>.md` | <specific trigger> | <when it does not apply> |

## Decision / compose order

<If leaves combine, the order to apply them; otherwise: "Leaves are independent.">

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring routers: `<../other/SKILL.md>`

## Success test

Representative in-scope tasks route to the correct leaf (or the correct compose order when leaves combine) without any methodology being read from this router.

## Companion Skills

- `../INDEX.md` — the skill index.
