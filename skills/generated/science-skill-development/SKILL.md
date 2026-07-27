---
name: science-skill-development
description: "Use when creating, extending, classifying, naming, organizing, or reviewing a Science skill. Routes to the taxonomy contract and the authoring procedure."
---

# Skill Development

A router carries no methodology; the doctrine lives in the leaves below.

## Routing trigger

Load before creating, extending, classifying, naming, organizing, splitting, or reviewing any skill under `skills/`.

## Scope boundary

Governs how Science skills are structured and authored. It does not contain domain methodology — that lives in the subject skills the index routes to.

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| [`references/skill-taxonomy.md`](references/skill-taxonomy.md) | classifying a skill, choosing its archetype, or applying the frontmatter contract | doing domain analysis |
| [`references/skill-authoring.md`](references/skill-authoring.md) | creating, extending, naming, placing, or splitting a skill | the archetype is already fixed and you only need the contract |

## Decision / compose order

When both leaves apply, load `references/skill-taxonomy.md` first to establish the archetype and frontmatter contract, then load `references/skill-authoring.md` to choose CREATE, EXTEND, or SPLIT and apply the naming and placement rules. Otherwise, load only the matching leaf.

## Parent & neighbors

- Parent index: Load the `science-command-preamble` skill and consult its `references/methodology-index.md`
- Neighboring subject routers: Load the `science-bio` skill, Load the `science-ml` skill, Load the `science-data-management` skill, Load the `science-statistics` skill, Load the `science-study-design` skill, Load the `science-epistemics` skill, Load the `science-literature` skill, Load the `science-research-package` skill, Load the `science-pipelines` skill, and Load the `science-writing` skill

## Templates

Author a new leaf from the matching scaffold: `references/templates/measurement-qa.md`, `references/templates/method-guide.md`, `references/templates/analysis-discipline.md`, `references/templates/normative-reference.md`, `references/templates/tool-guide.md`, `references/templates/practice-guide.md`; author a router from `references/templates/router.md`.

## Success test

Representative skill-development requests route to the correct leaf, or to taxonomy then authoring when both apply, without loading substantive domain methodology from this router.

## Companion Skills

- the `science-command-preamble` skill's `references/methodology-index.md` — the skill index.
- `references/skill-taxonomy.md` — the classification and metadata contract.
- `references/skill-authoring.md` — the authoring procedure.
