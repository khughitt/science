---
name: science-skill-development
description: "Use when creating, classifying, naming, organizing, or reviewing a Science skill. Routes to the taxonomy contract and the authoring procedure."
---

# Skill Development

Adapted from canonical Science skill `skills/meta/SKILL.md`.

A router carries no methodology; the doctrine lives in the leaves below.

## Routing trigger

Load before creating, classifying, naming, splitting, or reviewing any skill under `skills/`.

## Scope boundary

Governs how Science skills are structured and authored. It does not contain domain methodology — that lives in the subject skills the index routes to.

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| [`skill-taxonomy.md`](skill-taxonomy.md) | classifying a skill, choosing its archetype, or applying the frontmatter contract | doing domain analysis |
| [`skill-authoring.md`](skill-authoring.md) | creating, naming, placing, or splitting a skill | the archetype is already fixed and you only need the contract |

## Templates

Author a new leaf from the matching scaffold: `templates/measurement-qa.md`, `templates/method-guide.md`, `templates/analysis-discipline.md`, `templates/normative-reference.md`, `templates/tool-guide.md`, `templates/practice-guide.md`; author a router from `templates/router.md`.

## Companion Skills

- `../INDEX.md` — the skill index.
