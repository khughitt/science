# Spec Y — Multi-Backend Entity Resolver — Handoff Note

**Date:** 2026-04-19
**Status:** Not yet brainstormed in detail, not yet written, not yet planned.
**Picks up from:** `docs/specs/2026-04-19-dataset-entity-lifecycle-design.md` (rev 2.2), referenced there as "Spec Y" (forward reference at line 10).

This is a stub document so the next developer (future-Claude or human) doesn't have to re-derive the design context. The dataset-entity-lifecycle work was originally going to be one spec; during brainstorming we identified an underlying architectural concern (entity *storage* vs entity *representation* are conflated in the framework) that warranted its own spec. We shipped dataset-entity-lifecycle first with a forward-compatibility commitment, then deferred Spec Y to keep momentum.

## What Spec Y is for

The framework currently assumes **one entity = one markdown file under `doc/`**. This conflates two distinct concerns:

1. **Logical entity identity** — `dataset:foo`, `topic:bar`, `hypothesis:h01` as references in the knowledge graph.
2. **Physical storage** — where the entity's data lives on disk and in what format.

Several existing pain points trace back to this conflation:

- **mm30 rare-topic friction.** A real project has ~200 rare topics flagged by health checks because each lacks an `<entity>.md` file. Creating 200 thin markdown files is overhead for no analytical value — the topics are real, they just don't deserve their own document. An aggregated representation (one `topics.json` listing them all) would be cleaner. Today there's no way to declare that.
- **Datasets in `doc/`.** Per the dataset-entity-lifecycle spec, datasets logically live in two places: project-level metadata in `doc/datasets/<slug>.md` (entity surface) and resource-level data in `data/<slug>/datapackage.yaml` (runtime surface). The natural home for a dataset entity IS the runtime datapackage — `doc/datasets/<slug>.md` is a sidecar that exists only because of the "all entities under `doc/`" rule.
- **research-package was the first exception.** dataset-entity-lifecycle introduced a per-entity-type discovery rule (research-package lives at `research/packages/<lens>/<section>/research-package.md`, NOT under `doc/`). This is a small precursor — the rule is hardcoded, not pluggable.

Spec Y generalizes: an entity resolver knows about multiple **storage backends** and any entity type can declare which backend(s) it supports.

## Sketched backends (from brainstorming, not finalized)

1. **Markdown backend** — current default. One entity per `.md` file with YAML frontmatter. All entity types support this.
2. **Datapackage-directory backend** — entity lives as the `datapackage.yaml` (or `.json`) inside a directory alongside its data. Datasets are the natural candidate to promote here (the markdown sidecar would go away — `data/<slug>/datapackage.yaml` IS the entity).
3. **Aggregate-JSON backend** — many lightweight entities packed into one file. mm30's rare topics → `doc/topics.json` with 200 entries. Each entry has the same logical fields a markdown entity would; just no per-entity file.

A future spec might add more (database-table backend, remote-graph backend, etc.) but the v1 should ship the three above.

## Forward-compatibility commitments from the dataset-entity-lifecycle spec

These are **already decided** — Spec Y must honor them or break a recently-shipped contract:

1. **The `science-pkg` schema is identical regardless of backend.** Whether a dataset entity lives in markdown frontmatter or in a datapackage.yaml, the same JSON Schema validates it. Promoting datasets to the datapackage-directory backend changes the *file location and reader*, not the schema.
2. **Per-entity-type discovery is the seam.** dataset-entity-lifecycle hardcoded two paths in `science-tool/src/science_tool/graph/sources.py:_load_markdown_entities` (passing `roots=[doc_dir, specs_dir, project_root / "research" / "packages"]`). Spec Y replaces this hardcoded list with a per-entity-type config that maps entity type → backend → discovery rule.
3. **`parse_entity_file` is the canonical loader.** All entity reading already flows through `science_model.frontmatter.parse_entity_file`. Spec Y dispatches inside that function (or wraps it) — does not introduce a parallel loader.
4. **Strict mode for legacy migrations is the established pattern.** The `data-package_unmigrated` health anomaly + strict graph-build behavior set a precedent: when an entity type's storage convention changes, the graph build fails on unmigrated entries with an actionable migrate command. Spec Y's backend migrations should follow this pattern.

## Recommended sequencing for picking this up

1. **Brainstorm session** (`superpowers:brainstorming`). Re-explore the design space — the verbal sketch above is starting context, not a finished design. Open questions:
   - Does the resolver expose a single `load_entity(<id>) -> Entity` interface, or is dispatch internal to `parse_entity_file`?
   - How are backend choices declared? Per project (`science.yaml`)? Per entity type? Per file?
   - What does the migration story look like for the three concrete cases (rare topics → aggregate, datasets → datapackage, hypotheticals)?
   - What's the test-fixture story for backend-pluggability? (Today's tests assume markdown.)
   - Does Frictionless's Data Package have an existing pattern for "multiple resources, one schema family" that we should mirror, or does this need its own design?
2. **Write design spec** at `docs/specs/2026-04-19-multi-backend-entity-resolver-design.md` (the path the dataset-entity-lifecycle spec already forward-references — keep that filename so the cross-link resolves).
3. **Get user review of the spec** before planning.
4. **Write implementation plan** at `docs/specs/plans/2026-04-19-multi-backend-entity-resolver.md`.
5. **Execute** — likely smaller than dataset-entity-lifecycle's 35 tasks since this is structural plumbing rather than a new entity type.

## Concrete first task to brainstorm against

The mm30 rare-topics case is the smallest end-to-end problem to pick as the design's anchor. If the resolver can let mm30 declare "topics are stored in an aggregate JSON file" and silence the existing health flags without losing any analytical capability, the design has earned its scope. Datasets-as-datapackage-directory follows naturally; everything else is generalization.

## Where to find the dataset-entity-lifecycle artifacts (for reference)

- Spec: `docs/specs/2026-04-19-dataset-entity-lifecycle-design.md` (rev 2.2)
- Plan: `docs/specs/plans/2026-04-19-dataset-entity-lifecycle.md`
- Implementation: 51 commits on `main`, ending at the merge commit `3aa5e5b`
- Key files Spec Y will likely revisit:
  - `science-tool/src/science_tool/graph/sources.py` (line 160 — the hardcoded roots list)
  - `science_model/frontmatter.py:125` (`parse_entity_file` — the canonical loader)
  - `science_model/entities.py` (`EntityType` enum + `Entity` model)
  - `science-tool/src/science_tool/graph/health.py` (the `data_package_unmigrated` pattern, for backend-migration parallels)
