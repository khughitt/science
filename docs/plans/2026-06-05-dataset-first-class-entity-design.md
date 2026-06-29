# Dataset (and workflow family) as first-class entities — design + plan

**Status:** Draft / design — deferred follow-up to Plan 3 (entity-organization cutover).
**Created:** 2026-06-05
**Origin:** Surfaced while finishing the Plan 3 Task 10 cutover. The cutover made
`entities/` the only home for the 21 entity-layout kinds, but the
datapackage/workflow family (`dataset`, `workflow`, `workflow-run`) is not one of
those kinds and was left at its `doc/` markdown roots. See the "Step 1 refinement"
note in `2026-06-03-entity-organization-and-naming-implementation-plan3.md`.

## Motivation

Datasets are epistemically important and the user wants them modeled as
first-class entities, specifically to:

1. **Represent datasets supporting/opposing a claim** — i.e. dataset↔claim
   epistemic edges, so a dataset can bear on a hypothesis/finding the way
   evidence-lines and observations do.
2. **Associate datasets with papers for deduplication** — avoid counting the same
   underlying dataset multiple times when different papers report the same
   association/causal relationship.

## Current state (investigation, 2026-06-05)

Datasets are **already typed graph entities**, just deliberately classified as
*operational* (non-epistemic):

- Typed model `DatasetEntity` (`model/src/science_model/entities.py:594`) with a
  rich schema (origin/access/derivation/resources). Stable `dataset:` identity.
- `WorkflowRunEntity` exists (`entities.py:692`); **no `WorkflowEntity` class** —
  `EntityType.WORKFLOW` is declared but has no typed subclass.
- `dataset` and `workflow-run` are on the **closed non-epistemic list**
  (`entities.py:262`) → no `review_state`, no belief tracking.
- `PaperEntity.datasets: list[str]` (`entities.py:552`) already exists — the
  paper↔dataset association at (2) is supported at the model level **today**.
- **Missing:** there is no `derive_bears_on_from_dataset_references()` — datasets
  are not targets/sources of `bears_on` edges, so (1) is **not** implemented.

### Storage / source-of-truth today

| Kind | Markdown (descriptor) | Datapackage (canonical resource form) | Discoverer |
|------|----------------------|---------------------------------------|------------|
| dataset | `doc/datasets/*.md` | `data/**/datapackage.yaml`, `results/**/datapackage.yaml` | MarkdownAdapter (doc/datasets) + DatapackageAdapter |
| workflow | `doc/workflows/*.md` | — (executable definition lives in pipeline code) | MarkdownAdapter (doc/workflows) |
| workflow-run | `doc/workflow-runs/*.md` (secondary) | `results/**/datapackage.json` (SSOT) | MarkdownAdapter + WorkflowRunAdapter |

Design intent now recorded in `docs/user-guide/entities.md#dataset-lifecycle`:
"the dataset entity is the authority for project-level metadata; the runtime
`datapackage.yaml` is the authority for resource-level metadata." This dual-SSOT
split is the genuine reason datasets are not plain markdown entities.

The `doc/` markdown roots are also hard-coded in `validate/_helpers.py:143`
(`MarkdownAdapter(scan_roots=["doc/datasets"])`),
`validate/checks/dataset_promotion_contract.py:37`, and `commons/promote.py:206`.
Post-cutover, `doc/` is a **transitional** home (it no longer holds any of the 21
layout kinds), not a principled one.

## The two separable questions

1. **Storage location** — should the dataset/workflow markdown move from `doc/` to
   `entities/`? (purely a consistency/layout question; does NOT by itself unlock
   the epistemic use cases.)
2. **Epistemic semantics** — should datasets bear on claims (gain `bears_on`
   edges)? (a modeling decision, independent of where the file lives.)

These are independent. (2) is what the user actually wants; (1) is cleanup.

## Open decisions (resolve before implementing)

- **Dual-SSOT ownership.** If the dataset descriptor moves to `entities/datasets`,
  is it still the SSOT for project metadata while `data//results/ datapackage.yaml`
  stays SSOT for resources? (Recommended: yes — preserve the rev-2.2 split, only
  relocate the descriptor.)
- **Scope.** Include only `dataset`, or also `workflow`/`workflow-run`?
  - `workflow-run` SSOT is `results/**/datapackage.json`; the markdown is
    secondary — moving only the markdown adds confusion. Lean: leave as-is.
  - `workflow` has no typed class and dual identity (doc vs. executable pipeline).
    Lean: out of scope until a `WorkflowEntity` and its identity model are defined.
- **Epistemic edges.** Define how a dataset bears on a claim. Via evidence-lines
  that cite `dataset:` refs? A new `derive_bears_on_from_dataset_references()`?
  Does dataset gain a `review_state` (i.e. leave the non-epistemic list), or stay
  operational while still being a `bears_on` *source*?
- **Reference policy.** Add `dataset:` (and `article:`?) to the markdown reference
  policy table so refs are policed/rewritable.

## Sketch of the work (once decisions are made)

1. Add `dataset` (and any in-scope kinds) to `_BUILTIN_MARKDOWN_POLICIES`
   (`entities.py`) with an `entities/datasets` root + strategy.
2. Extend `entity_layout_migration.py` to move `doc/datasets` → `entities/datasets`
   (it currently filters to `markdown_entity_kinds()` minus singletons, so the
   family is skipped today).
3. Relocate the ~11 source references from `doc/datasets|workflows|workflow-runs`
   to the new roots: `graph/sources.py` (drop the transitional scan-roots),
   `validate/_helpers.py`, `dataset_promotion_contract.py`, `commons/promote.py`,
   `commons/overlay.py`, `datapackage_migrate.py`, `datasets_register.py`, etc.
4. (If epistemic) implement dataset↔claim edge derivation + materialize wiring.
5. (If workflow in scope) add `WorkflowEntity` + clarify definition-vs-index.
6. Update fixtures + tests; **pilot on a real project** (as Plan 3 did with cycles)
   before any irreversible cutover of these kinds.

## Risks

- Parallel representation (entity markdown vs datapackage) must not drift; the
  ownership rule has to be explicit and enforced.
- This touches the commons promote/overlay system, which has its own `doc/`
  conventions — coordinate so overlays and promotion stay consistent.
- Treat any layout change for these kinds as irreversible (like Plan 3); gate on a
  green pilot.
