---
name: skill-authoring
description: Use when creating, naming, placing, splitting, or extending a Science skill. The decision procedure, naming and placement rules, and template-eligibility doctrine.
archetype: practice-guide
provenance: internal
---

# Skill Authoring

## When to apply

Before creating, naming, placing, splitting, or extending a skill.

## Workflow steps

1. Load `skill-taxonomy.md` and identify the guidance's primary archetype and primary artifact or decision.
2. Apply the CREATE, EXTEND, and SPLIT criteria below before editing an existing leaf.
3. Choose a stable name for the promised operation on the subject.
4. Place the skill in the existing directory whose subject matches, or record an unresolved placement question for migration.
5. Author the leaf from its archetype template. For a router, keep only navigation and extract teaching content into typed leaves.

## Judgment rules

### Create vs extend vs split

- **EXTEND** an existing leaf when the new guidance shares its archetype **and** its primary artifact/decision **and** would be loaded in the same task.
- **CREATE** a new leaf when the guidance has a **distinct archetype** *or* a **distinct primary artifact/decision loaded independently**.
- **SPLIT** an existing leaf when it carries **two archetypes** (violating exactly-one) *or* **two independent artifacts/decisions loaded in different tasks** (e.g. `frictionless`: the datapackage contract vs. the CLI tooling).

### Naming

- A skill `name` is a **stable identifier**. Renaming is a breaking change (INDEX.md, the codex mirror, and every cross-reference) and is a migration-scoped operation, never casual.
- `name` is kebab-case and encodes the **promised operation on its subject**, not the tool and not the archetype: `bulk-rnaseq-qa`, not `deseq2-guide`; `survival-and-hierarchical-models`, not `method-guide-survival`. The archetype lives in metadata, never in the name.
- Pre-migration, a leaf name carries the **subject prefix of its placement directory** (`data-`, `data-source-`, `data-expression-`, `statistics-`, `pipeline-`, `research-`). This is a *transitional* convention: the migration reshapes subjects, so prefixes are expected to change then, not now.

### Placement (pre-migration)

- Place a new skill in the **existing directory whose subject matches**, even though several of those directories are known-incoherent — do **not** begin the reorg early or spin up a new top-level directory. `meta/` is the sole new directory this phase.
- If no existing directory fits, that is a signal to record the placement question for the migration, not to invent structure now.

### Router invariant and the hub anti-pattern

This is stated as a **target invariant** the corpus is converging on: 4 of 7 current `SKILL.md` files are still **hubs** (route + teach). `research/SKILL.md` and `writing/SKILL.md` were extracted on 2026-07-20 and are now true routers; `data/genomics/SKILL.md` was already one. Every remaining hub is a migration extraction candidate (see the matrix). A document that routes *and* teaches is a hub; its teaching content is extracted into typed leaves before it is a true router.

### Template-eligibility rule

> Template eligibility considers both existing leaves and independently identifiable practices embedded in hubs, provided at least two concrete target extractions demonstrate the same content contract and success test.

**Open trip-wire (recorded 2026-07-20).** `research/research-package-rendering.md` is classified `practice-guide` as an acknowledged force-fit: it is a software *implementation* guide (build-a-component), which none of the six archetypes model well, and its population of one is below the two-target threshold above. If a second build-a-component leaf appears, the pair becomes eligible and a seventh `implementation-guide` archetype must be reconsidered rather than force-fitted again.

## Quality criteria

- The guidance has one primary archetype and uses that archetype's content slots and success test.
- The name is a stable kebab-case operation on its subject, not a tool name or archetype label.
- CREATE, EXTEND, or SPLIT follows the shared-archetype, shared-artifact/decision, and same-task criteria.
- Placement follows the current subject tree without beginning the deferred corpus migration.
- Routers contain navigation only; substantive methodology lives in typed leaves.

## Common pitfalls

- Do not overload one field with two axes. Structural role, subject, depth, and source-basis are separate; `type:` was retired precisely because it conflated structural role with content contract.
- Do not encode the archetype in the skill name. The name states the operation on its subject; `archetype:` carries the contract.
- Do not begin the corpus reorganization (renames, moves, archetype backfill, hub extraction) while authoring a single skill. That is a separate migration phase, driven by the corpus matrix.

## Outputs

- A recorded CREATE, EXTEND, or SPLIT decision.
- A typed leaf or navigation-only router with the applicable template slots and success test.
- A stable name and current subject-tree placement, or a placement question recorded for migration.

## Success test

The agent carried out skill authoring according to the workflow, applied the judgment rules to CREATE, EXTEND, or SPLIT, and produced an artifact meeting the quality criteria.

## Companion Skills

- [`skill-taxonomy.md`](skill-taxonomy.md) — the classification and metadata contract.
- [`../INDEX.md`](../INDEX.md) — the skill index.
