---
name: science-skill-development
description: "Use when creating, extending, classifying, naming, organizing, or reviewing a Science skill. Routes to the taxonomy contract and the authoring procedure."
---

# Skill Development

Adapted from canonical Science skill `skills/meta/SKILL.md`.

A router carries no methodology; the doctrine lives in the leaves below.

## Routing trigger

Load before creating, extending, classifying, naming, organizing, splitting, or reviewing any skill under `skills/`.

## Scope boundary

Governs how Science skills are structured and authored. It does not contain domain methodology — that lives in the subject skills the index routes to.

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| [`skill-taxonomy.md`](skill-taxonomy.md) | classifying a skill, choosing its archetype, or applying the frontmatter contract | doing domain analysis |
| [`skill-authoring.md`](skill-authoring.md) | creating, extending, naming, placing, or splitting a skill | the archetype is already fixed and you only need the contract |

## Decision / compose order

When both leaves apply, load `skill-taxonomy.md` first to establish the archetype and frontmatter contract, then load `skill-authoring.md` to choose CREATE, EXTEND, or SPLIT and apply the naming and placement rules. Otherwise, load only the matching leaf.

## Parent & neighbors

- Parent index: [`../INDEX.md`](../INDEX.md)
- Neighboring subject routers: [`../../skills/bio/SKILL.md`](../../skills/bio/SKILL.md), [`../../skills/ml/SKILL.md`](../../skills/ml/SKILL.md), [`../../skills/data-management/SKILL.md`](../../skills/data-management/SKILL.md), [`../../skills/statistics/SKILL.md`](../../skills/statistics/SKILL.md), [`../../skills/study-design/SKILL.md`](../../skills/study-design/SKILL.md), [`../../skills/epistemics/SKILL.md`](../../skills/epistemics/SKILL.md), [`../../skills/literature/SKILL.md`](../../skills/literature/SKILL.md), [`../../skills/research-package/SKILL.md`](../../skills/research-package/SKILL.md), [`../../skills/pipelines/SKILL.md`](../../skills/pipelines/SKILL.md), and [`../../skills/writing/SKILL.md`](../../skills/writing/SKILL.md)

## Templates

Author a new leaf from the matching scaffold: `templates/measurement-qa.md`, `templates/method-guide.md`, `templates/analysis-discipline.md`, `templates/normative-reference.md`, `templates/tool-guide.md`, `templates/practice-guide.md`; author a router from `templates/router.md`.

## Success test

Representative skill-development requests route to the correct leaf, or to taxonomy then authoring when both apply, without loading substantive domain methodology from this router.

## Companion Skills

- `../INDEX.md` — the skill index.
- `skill-taxonomy.md` — the classification and metadata contract.
- `skill-authoring.md` — the authoring procedure.
