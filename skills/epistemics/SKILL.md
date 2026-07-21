---
name: epistemics
description: Use when propositions, evidence, or curated annotations must be schema-valid, graph-reasoned, or agreement-checked. Routes to the epistemics leaves.
provenance: internal
---

# Epistemics Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when the object is a proposition/annotation and its schema, graph outcome, or
label agreement is in question — before interpretation.

## Scope boundary

Covers proposition/evidence schema conformance, proposition-graph outcome reasoning, and curated-label
QA. Excludes source selection/citation (see `../literature/SKILL.md`).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `proposition-schema.md` | writing/validating proposition or evidence frontmatter | non-proposition data |
| `proposition-graph-reasoning.md` | flagging an interpretation against graph outcome conditions | schema-only concerns |
| `annotation-curation-qa.md` | QA of manual/LLM annotation or taxonomy-label agreement | non-curated measurement |

## Decision / compose order

Leaves are independent; schema conformance typically precedes graph reasoning.

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring routers: `../literature/SKILL.md`

## Success test

A proposition/annotation concern routes to the correct leaf with no methodology read from this router.

## Companion Skills

- `../INDEX.md` — the skill index.
