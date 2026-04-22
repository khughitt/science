# Unified Entity References and Topic Taxonomy

**Date:** 2026-04-21
**Status:** Draft
**Builds on:**
- `2026-04-05-project-model-design.md` — core entity taxonomy
- `2026-04-20-multi-backend-entity-resolver-design.md` — unified entity model + storage adapters
- `2026-03-01-knowledge-graph-design.md` — three-tier ontology (core / causal / domain plugins)

## Motivation

The entity model and storage architecture are well-designed. The load-time
mechanics are now fail-soft (as of the 2026-04-21 warn-and-skip landing in
`graph/sources.py`) and the `article: → paper:` canonicalization is
unconditional. What's left is a **reference-semantics** gap that shows up
in practice as the "unresolved references" audit signal.

On the mm30 corpus — a mature, curated project with 78 papers, 44 topics,
5 hypotheses, 261 tasks, 53 discussions — the gap produces **486
unresolved `topic:` references out of 633 total unresolved mentions**,
with 299 unique missing targets. Investigation of the pattern shows a
category error, not a hygiene problem:

1. `topic:PHF19` is used as shorthand for *the gene* PHF19 — which exists
   conceptually in the biology ontology (Biolink `gene`) but has no local
   entity file.
2. `topic:bayesian` is used as shorthand for the Bayesian method family —
   which would naturally be `method:bayesian`.
3. `topic:phf19-prc2-ifn-immunotherapy` is a genuine cross-theme research
   synthesis document — the legitimate `topic` use case.
4. `topic:mutations`, `topic:subtypes`, `topic:progression` are single-word
   concept labels — ad-hoc tags standing in for concepts that don't have
   local files.

All four usages currently share the `topic:` prefix. The audit treats them
identically — all must have a backing file or they produce "unresolved
reference" rows. Devs respond by either (a) creating low-value stub files,
(b) ignoring the audit, or (c) dropping cross-references entirely. None of
these serve the underlying goal of traceable, machine-queryable research
prose.

The design already supports the distinctions that would resolve this —
`ProjectEntity` vs. `DomainEntity`, bridge relations (`proposition --about-->
concept`), domain ontology plugins (Biolink), multi-entity aggregate
storage. Four small implementation gaps keep devs from using the vision.

## Goals

- Let authors reference domain things (genes, diseases, methods, concepts)
  without creating project-local files for each one.
- Narrow the `topic` kind to its substantive use — cross-cutting research
  synthesis documents — and provide cleaner alternatives for the other
  three patterns.
- Preserve the fail-fast posture on true typos and structurally missing
  entities; don't silently swallow them.
- Keep the changes small, independently shippable, and backward-compatible
  for projects that haven't yet migrated.

## Non-goals

- Redesigning the RDF materialization layer or graph store.
- Introducing a new entity model family beyond the ProjectEntity /
  DomainEntity split already in the 2026-04-20 spec.
- Mandating a full project migration sweep. Each project converges on
  the new conventions at its own pace; the tool supports both old and new
  usage during the transition.
- Defining the full initial set of core `DomainEntity` subtypes. That
  belongs in the 2026-04-20 follow-on.

## Design overview

Four independent changes, each useful on its own, which together deliver
unified-reference semantics:

1. **Cross-kind slug resolution** in the alias map.
2. **Ontology catalogs contribute both entity kinds and entity
   instances** — they extend the kind registry with
   domain-specific `DomainEntity` subclasses and materialize their
   canonical terms as lightweight entities at project load time.
3. **A documented lightweight `terms.yaml` convention** for concepts not
   worth a full file.
4. **`tag:` as a recognized external prefix** for free-form labels that
   deliberately aren't entity references.

Plus a fifth, scope-level change:

5. **Narrow the `topic` kind** and document when to use which of
   `topic` / `concept` / domain-entity / `method`.

Each is spec'd below.

## Entity-kind taxonomy: core vs. domain vs. project

Before the detailed changes, the taxonomy this spec commits to:

| Layer | Owner | Example kinds | Storage convention |
|---|---|---|---|
| **Science core — ProjectEntity** | Science framework | task, hypothesis, question, proposition, observation, interpretation, story, paper, topic, finding, plan, discussion, report, inquiry, spec | markdown + aggregate YAML |
| **Science core — cross-domain analytical** | Science framework | method, concept, variable, model | markdown + aggregate YAML |
| **Domain catalogs — DomainEntity** | Ontology catalog (biology, chemistry, physics, ...) | gene, protein, biomolecule, disease, phenotype, pathway, cell-type, chemical-entity, reaction | catalog-declared; lightweight local override via markdown or `terms.yaml` |
| **Project extensions** | Individual project | project-specific concepts (e.g. `cytogenetic-event` in MM30) | project-registered extension kind |

The 2026-04-20 unified-entity-model spec's "core types are few" principle
holds: Science core owns only kinds that are genuinely cross-project.
Everything domain-specific moves into domain catalogs, which are
declared per-project via `ontologies: [...]` in `science.yaml`.

Applied to concrete mm30 references:

| Reference (current) | Kind + source (target) | Rationale |
|---|---|---|
| `topic:PHF19` | `gene:PHF19` from biology catalog | HGNC-grounded gene |
| `topic:chromatin` | `biomolecule:chromatin` from biology catalog | Macromolecular complex; Biolink models it |
| `topic:survival` | `method:survival-analysis` from science core | Cross-domain statistical method |
| `topic:bayesian` | `method:bayesian-inference` from science core | Cross-domain methodology |
| `topic:treatment-response` | `concept:treatment-response` from project `terms.yaml` | Not clearly a domain entity; project-local concept |
| `topic:phf19-prc2-ifn-immunotherapy` | `topic:phf19-prc2-ifn-immunotherapy` unchanged | Genuine cross-theme research synthesis |

This taxonomy is the scaffolding the rest of the spec hangs off of.

## 1. Cross-kind slug resolution

### Current behavior

`build_alias_map()` in `science_tool.graph.sources` registers each entity
under:

- `entity.canonical_id` (e.g. `gene:PHF19`)
- `canonical_id.lower()`
- any explicit `aliases` entries

A reference like `topic:PHF19` in a `related:` list is matched
literally against this map. With no `topic:PHF19` entity registered, it
fails, regardless of whether `gene:PHF19` exists.

### Proposed behavior

At alias-map construction time, also register the **bare slug** of each
`canonical_id` (the portion after the first `:`) as an alias — **subject
to an ambiguity check across all kinds**.

- If the slug `PHF19` appears on exactly one entity (say `gene:PHF19`), register
  `PHF19 → gene:PHF19` and also register `*:PHF19 → gene:PHF19` via a
  wildcard-prefix lookup path used by the audit.
- If the slug appears on multiple entities (e.g. both `gene:PHF19` and
  `topic:PHF19`), raise an `AmbiguousSlugError` at load time, listing all
  colliders. The author resolves by picking a canonical entity and adding
  `same_as: [gene:PHF19]` on the `topic:PHF19` side (or vice versa), or
  retiring one.

### Why this is safe

- The ambiguity check preserves fail-fast on real conflicts — devs see the
  collision at load time, not as silent misbehavior downstream.
- Wildcard resolution is only *soft* fallback. Direct `kind:slug` matches
  are still preferred. Cross-kind fallback is a last-resort reconciliation,
  not the primary resolution path.
- Existing `same_as:` entity links remain authoritative. If a user declares
  `topic:PHF19 same_as gene:PHF19`, both canonical ids resolve to the same
  entity, and the ambiguity check collapses naturally.

### Implementation shape

```python
# science_tool/graph/sources.py

class AmbiguousSlugError(ValueError):
    """Raised when a bare slug maps to multiple canonical entities."""

def build_alias_map(entities, manual_aliases=None) -> dict[str, str]:
    ...  # existing canonical + lower + explicit-alias registration

    # New: bare-slug fallback with ambiguity check
    slug_to_ids: dict[str, set[str]] = defaultdict(set)
    for entity in entities:
        if ":" in entity.canonical_id:
            slug = entity.canonical_id.split(":", 1)[1]
            slug_to_ids[slug].add(entity.canonical_id)
            slug_to_ids[slug.lower()].add(entity.canonical_id)

    for slug, ids in slug_to_ids.items():
        if len(ids) == 1:
            _register_alias(alias_map, slug, next(iter(ids)))
        else:
            raise AmbiguousSlugError(
                f"Slug {slug!r} maps to multiple canonical entities: "
                f"{sorted(ids)}. Resolve by merging via `same_as:` or by "
                f"renaming one of them."
            )
    return alias_map
```

The audit path (`audit_project_sources`) uses the alias map unchanged;
it benefits automatically.

### Scope / edge cases

- Aliases-of-aliases (`same_as`): if A and B declare each other as
  `same_as`, the alias map should follow the link transitively. This
  reuses existing machinery.
- Case-insensitive collisions (e.g. `gene:PHF19` vs `concept:phf19`):
  flagged by the ambiguity check. Author picks one.

## 2. Ontology catalogs contribute kinds and instances

### Current behavior

`science.yaml` can declare `ontologies: [biology, chemistry]`, and
`load_catalogs_for_names()` loads the catalog metadata. Today catalogs
contribute only **external-reference prefixes** (via
`science_model.ontologies.schema.OntologyCatalog.entity_types[i].curie_prefixes`)
to `is_external_reference()` — they signal "this is an external ref,
don't audit it" but don't register any kinds with the entity registry
and don't materialize any entities. `gene:PHF19` bypasses audit, but
is never a resolvable entity — it lives in a liminal space that's neither
clearly external nor clearly local.

### Proposed behavior

Ontology catalogs become the canonical source for domain-specific entity
kinds and instances. For each declared catalog, at project load time:

1. **Register the catalog's entity kinds** with the `EntityRegistry`.
   Each kind routes to a `DomainEntity` subclass declared by the catalog
   (or to a generic `DomainEntity` if the catalog provides no custom
   subclass). Kind names follow the catalog's vocabulary — biology
   contributes `gene`, `protein`, `biomolecule`, `disease`, `phenotype`,
   `pathway`, `cell-type`, `biological-process`, etc.

2. **Materialize the catalog's canonical terms as entity instances.**
   Each term becomes a lightweight `DomainEntity` record:
   - carries the catalog-declared canonical id (e.g. `gene:PHF19`,
     `disease:MONDO:0016419`)
   - carries ontology type (`biolink:Gene`, `biolink:Disease`)
   - carries synonyms / cross-references as aliases / `same_as` links
   - inherits from the kind-specific `DomainEntity` subclass

3. **Participate in the alias map** alongside project-local entities,
   including through the cross-kind slug fallback (change 1).

References like `gene:PHF19` resolve directly against the catalog entry.
References like `topic:PHF19` resolve via cross-kind slug fallback to the
same catalog-contributed entity. The liminal "external prefix, not
resolvable" state goes away.

### Why catalogs must contribute *kinds* and not just instances

The 2026-04-20 unified-entity-model spec's "core types are few"
principle implies that domain-specific kinds must come from somewhere
other than Science core. The natural home is the domain ontology
catalog — it already owns the vocabulary and the schema invariants for
its entities. Moving kind registration into the catalog:

- Keeps Science core small and domain-agnostic.
- Makes kind availability explicit in `science.yaml`
  (`ontologies: [biology]` means `gene` is a valid kind;
  `ontologies: [chemistry]` means `chemical-entity` is).
- Lets catalogs enforce per-kind invariants (e.g. `gene` entities must
  carry at least one of HGNC/NCBIGene/Ensembl identifiers) without
  leaking biology-specific rules into Science core.
- Makes the three-layer model (core / domain / project) operational,
  not just architectural.

### Contract sketch

The exact catalog format is a follow-on spec concern; this spec
commits to the shape of the contract. Conceptually:

```yaml
# Illustrative — a biology catalog contribution
catalog: biology
version: "1.0"
kinds:
  - name: gene
    base: DomainEntity
    required_fields: [id, title, ontology_terms]
    required_identifier_prefixes: [HGNC, NCBIGene, Ensembl]
  - name: biomolecule
    base: DomainEntity
    required_fields: [id, title]
  - name: disease
    base: DomainEntity
    required_fields: [id, title, ontology_terms]
    required_identifier_prefixes: [MONDO, DOID]
  - name: phenotype
    base: DomainEntity
    required_fields: [id, title, ontology_terms]
    required_identifier_prefixes: [HP]
  - name: pathway
    base: DomainEntity
    required_fields: [id, title]
  - name: cell-type
    base: DomainEntity
    required_fields: [id, title, ontology_terms]
    required_identifier_prefixes: [CL]
  # ...
entities:
  # Either inline:
  - id: "gene:PHF19"
    title: "PHF19"
    ontology_terms: ["HGNC:30074", "NCBIGene:26147", "Ensembl:ENSG00000119403"]
  # Or lazy-loaded from an external registry via a declared source.
```

Catalogs may distribute:
- **pre-curated, vendored snapshots** for common use cases (the most
  directly useful starting point)
- **live-queryable registry adapters** for projects that want richer
  coverage (a follow-on)

This spec decides that catalogs contribute kinds + instances. It does
not decide the catalog distribution format, snapshot-vs-live policy,
caching, or refresh semantics — those belong in a catalog-authoring
follow-on spec.

### Interaction with project-local overrides

A project may author a local record for a catalog-contributed entity
— e.g. `doc/topics/PHF19.md` with MM-specific narrative about the
gene. Policy:

- **Same `canonical_id`:** project local wins on field-level conflicts.
  Local `title`, `description`, `related` override catalog values.
  `same_as`, `aliases`, `ontology_terms` are unioned rather than replaced.
- **Different `canonical_id` but intended same entity:** author
  declares `same_as: [gene:PHF19]` on the local record. Existing
  `same_as` machinery handles the merge.
- **Kind disagreement** (e.g. project authored `topic:PHF19`, catalog
  contributes `gene:PHF19`): ambiguity check per change 1 fires,
  author resolves via `same_as` or by retiring the local record.

### Scope / open questions (for follow-up implementation)

- **Catalog sourcing mechanism** — vendored snapshots vs. live
  registries vs. per-project config. Deferred to a catalog-authoring
  spec.
- **Catalog caching / refresh policy** — how does a project opt
  into updates, when does the cache invalidate. Follow-on.
- **Which entity kinds does `biology` contribute in v1?** — out
  of scope here; this spec establishes the contract, not the
  initial contents.
- **How much of Biolink becomes the `biology` catalog?** — likely a
  curated subset; decision belongs in the catalog-authoring spec.

## 3. Lightweight `terms.yaml` convention

### Current state

The aggregate adapter already loads `knowledge/sources/local/entities.yaml`
as a multi-entity YAML file, and it works — but it's used for legacy
entity records, not for lightweight terms. There's no documented
"minimal entry" shape, no example, no promotion workflow. In practice,
authors either create markdown files (overweight) or skip the concept
entirely.

### Proposed convention

Introduce `knowledge/sources/local/terms.yaml` by convention. Loaded by
the same aggregate adapter. Documented as:

```yaml
# knowledge/sources/local/terms.yaml
# One-line concept entries for things referenced from prose but not
# worth a full markdown file. Promote to a real entity file if the
# concept accumulates enough content to justify one.

terms:
  - id: "concept:ribosome-biogenesis"
    title: "Ribosome biogenesis"
  - id: "concept:treatment-response"
    title: "Treatment response"
    same_as: ["concept:response-to-therapy"]
  - id: "method:cox-regression"
    title: "Cox proportional-hazards regression"
    ontology_terms: ["biolink:StatisticalMethod"]
```

Required fields: `id`, `title`. Optional: `same_as`, `aliases`,
`ontology_terms`, `description`. Body / narrative content is explicitly
not supported; that's the signal to promote to a markdown file.

### Adapter behavior

The `AggregateAdapter` treats `terms.yaml` the same as `entities.yaml`:
each entry becomes a raw record dispatched through the kind registry.
The `id` prefix determines the kind (`concept`, `method`, `gene`, ...).
If the kind is unregistered, the existing warn-and-skip path (2026-04-21)
handles it cleanly.

### Promotion path

When a term in `terms.yaml` accumulates enough content (more than a
title and a few aliases), author promotes it to a markdown file in the
appropriate directory (`doc/concepts/`, `doc/methods/`, etc.) and removes
the entry from `terms.yaml`. The `id` stays stable — references don't
break.

### Why a second aggregate file

`terms.yaml` vs. `entities.yaml` separation signals intent: `entities.yaml`
holds domain / legacy / heavyweight aggregate records; `terms.yaml` holds
one-line concept stubs. The tool doesn't distinguish them operationally
(both load through the same adapter), but the convention gives authors
a clean home for the lightweight case.

Projects that don't need the distinction can keep everything in
`entities.yaml`. `terms.yaml` is opt-in.

## 4. `tag:` as a recognized external prefix

### Current state

`_EXTERNAL_PREFIXES` in `science_tool.graph.sources` includes ontology
namespaces (`go`, `mesh`, `doid`, `hp`, `so`, `ncbitaxon`, `ncbigene`,
`ensembl`). References with these prefixes bypass audit.

### Proposed change

Add `tag` to `_EXTERNAL_PREFIXES`. References like `tag:draft`,
`tag:experimental`, `tag:wip` are recognized as free-form labels and
bypass audit. Projects that want structured queryable classification
still use `concept:*` or ontology-backed terms; `tag:*` is explicitly
reserved for unstructured labels.

### Why add it

- Documents currently use `tags: [...]` as a YAML string list, which has no
  link integrity. `tag:X` in a `related:` field is a clearer signal: this
  is a labeling intent, not an entity reference.
- Separates "I'm classifying this document" from "I'm pointing at an
  entity." Both are valid; conflating them is what produces the "unresolved
  topic" noise.

### Scope

- `tag:` is not a registered kind; there's no such thing as a `tag` entity.
  It's purely a reference-time convention.
- Existing `tags: [...]` string lists in frontmatter are unaffected;
  they're a separate concept (free-form classification within a document's
  own frontmatter). This change only touches the reference-in-related-list
  pattern.

## 5. Narrowing the `topic` kind

### Current conflation

In practice, `topic:` files span four distinct patterns:

1. **Domain entities with ontology backing** (`topic:PHF19` with
   `same_as: [HGNC:30074]`) — really `gene:` / `protein:` / `disease:`.
2. **Methodology primers** (`topic:bayesian`) — really `method:`.
3. **Single-word concept labels** (`topic:chromatin`) — really `concept:`.
4. **Cross-cutting research-theme synthesis documents**
   (`topic:phf19-prc2-ifn-immunotherapy`) — the legitimate `topic` case.

### Proposed narrowing

`topic` is a `ProjectEntity` kind reserved for **substantive prose
synthesis documents about a research theme that spans multiple concepts,
is not organized around a specific question or hypothesis, and is not
tied to a specific analysis session**.

Concretely, a document is a `topic` if and only if:

- It has narrative prose body, not just a title + 1-line description.
- Its subject is a cross-cutting theme, not a single entity. **If the
  subject is a single thing covered by a declared ontology catalog
  (per change 2), use the catalog-contributed kind instead of `topic`**:
  a gene is `gene:`, a biomolecule is `biomolecule:`, a disease is
  `disease:`, etc. `topic` is not the fallback for "a thing I want to
  write about"; it's specifically for *theme-level synthesis*.
- It isn't organized around a specific question or hypothesis (those are
  `story` entities per the project model).
- It isn't the output of a specific analysis session (that's
  `interpretation`).

The "prefer catalog kinds over `topic` or `concept`" rule gives authors
a clear decision procedure: **check the declared ontologies first,
use a domain kind if one fits, fall back to `concept`/`method` only for
genuinely cross-domain or not-yet-cataloged subjects, use `topic` only
for theme-level synthesis documents.**

Everything else goes to the appropriate existing kind:

| Current pattern | Proposed kind | Source | Storage |
|---|---|---|---|
| `topic:PHF19` with HGNC id | `gene:PHF19` | biology catalog | catalog-contributed lightweight entity + optional `doc/genes/PHF19.md` for project-specific extension |
| `topic:chromatin` | `biomolecule:chromatin` | biology catalog (Biolink models it as a macromolecular complex) | catalog-contributed + optional local extension |
| `topic:survival` | `method:survival-analysis` | science core | `doc/methods/survival-analysis.md` or `terms.yaml` entry |
| `topic:bayesian` | `method:bayesian-inference` | science core | `doc/methods/bayesian-inference.md` or `terms.yaml` entry |
| `topic:mutations` (bare label, no clear catalog home) | `concept:mutations` | science core | `terms.yaml` entry |
| `topic:phf19-prc2-ifn-immunotherapy` (multi-concept synthesis) | `topic:phf19-prc2-ifn-immunotherapy` | project-local | `doc/topics/phf19-prc2-ifn-immunotherapy.md` (unchanged) |

### Why keep `topic` at all

A literature review or cross-cutting synthesis like
`epigenetic-attractors-convergence-canalization` genuinely doesn't fit
the other compositional kinds. It's:

- Not a `story` (no single question or hypothesis it's organized around).
- Not an `interpretation` (not tied to a specific analysis session).
- Not a `report` (`report` in the project model is analysis output, not
  narrative synthesis).
- Not a `method` (no methodology described).
- Not a `concept` (multi-concept, prose-bodied).

`topic` fills a real niche: **standalone research-theme synthesis**.

### Migration guidance (per-project)

The narrowing is **documentation / convention** only. No enforcement at
the tool level; projects migrate at their own pace. Suggested order:

1. Identify existing `topic:` files that carry ontology `same_as:`
   mappings — migrate those to `gene:` / `protein:` / `disease:` kinds
   first (these are the easiest wins and will resolve cleanly once the
   catalog-contributed entities land in change 2).
2. Identify `topic:` files that are purely methodology primers — rename
   to `method:`.
3. Identify single-word bare labels — either promote to `concept:` (in
   `terms.yaml`) or rewrite call-sites to use an existing domain entity.
4. Leave the genuine research-theme synthesis documents as `topic:`.

No deadline; projects that haven't migrated still work thanks to
change (1) (cross-kind slug resolution).

## Interaction summary

The five changes work together:

- Dev writes `related: ["topic:PHF19"]`.
- Alias map has `gene:PHF19` (contributed by biology ontology catalog
  per change 2), and `PHF19` as a slug alias per change 1.
- Reference resolves to `gene:PHF19`. No audit warning.
- Dev writes `related: ["topic:treatment-response"]`. No matching slug.
- Audit surfaces unresolved. Dev adds one line to `terms.yaml`
  (`{id: "concept:treatment-response", title: "..."}`) per change 3.
- Resolved.
- Dev writes `related: ["tag:draft"]` on a work-in-progress plan. Change
  4 treats it as external; audit skips.
- Over time, the project converges on `gene:`, `concept:`, `method:`, and
  narrow-scope `topic:` via change 5. Existing `topic:X` references keep
  working throughout.

## Implementation order

Recommended shipping order (smallest → largest, independently useful):

1. **Change 4** — `tag:` prefix addition. ~5 lines in `sources.py`.
2. **Change 1** — Cross-kind slug resolution. ~30 lines; adds one error
   class + tests for ambiguity cases.
3. **Change 3** — `terms.yaml` convention. Mostly documentation +
   template + one loader assertion (accept terms.yaml alongside
   entities.yaml). ~10 lines of code; more doc work.
4. **Change 5** — `topic` narrowing. Pure documentation (spec + CLAUDE.md
   + `science:writing` skill updates). No tool changes.
5. **Change 2** — Ontology catalogs contribute kinds + instances.
   Largest; requires a companion catalog-authoring spec for the catalog
   format and sourcing policy, then kind-registration integration with
   `load_project_sources` and initial `biology` catalog content.
   Ships last.

Changes 1, 3, and 4 are a ~half-day of work each. Change 5 is pure
documentation. Change 2 is a multi-week design-and-implement including
the catalog-authoring follow-on.

## Testing strategy

Each change gets its own test module under
`science-tool/tests/graph/references/`:

- `test_cross_kind_slug_resolution.py` — bare slug lookup, ambiguity
  detection, `same_as` transitivity.
- `test_ontology_catalog_entities.py` — catalog contributions appear in
  alias map; `same_as` to local entities merges correctly.
- `test_terms_yaml_adapter.py` — minimum-field entries load; promotion
  path (same id moves from terms.yaml → markdown) leaves refs stable.
- `test_tag_prefix_external.py` — `tag:X` refs bypass audit.
- Existing regression fixtures (mm30 golden-snapshot equivalents)
  continue to pass unchanged for projects that haven't migrated.

## Migration and backward compatibility

No breaking changes for existing projects. Each change is additive:

- Change 1 only adds fallback behavior after exact-match lookup fails.
- Change 2 only adds entities; never removes local ones.
- Change 3 only adds a recognized filename; nothing breaks if it's absent.
- Change 4 only adds a prefix; existing `tag:*` refs (if any) that were
  failing the audit start passing — projects using `tag:` as a real entity
  kind break, but that's an intended migration step with a clear fix
  (rename to any other prefix).
- Change 5 is documentation only.

Projects that have already authored entity files continue to work. The
changes *add* ways to reference things without authoring; they don't
remove any existing pathway.

## Resolved decisions

- Cross-kind slug fallback happens at alias-map construction time, with
  ambiguity as a hard error.
- Ontology catalogs contribute **both entity kinds and entity
  instances** — they register `DomainEntity` subclasses with the kind
  registry and materialize canonical terms as lightweight entities in
  the alias map.
- Science core owns only cross-domain kinds (ProjectEntity core plus
  `method`, `concept`, `variable`, `model`). Domain-specific kinds
  (`gene`, `protein`, `biomolecule`, `disease`, etc.) come from
  ontology catalogs, not from Science core.
- `terms.yaml` is a documented convention for lightweight concepts;
  technically redundant with `entities.yaml` but semantically distinct.
- `tag:` is a recognized external prefix; tags and entities are
  explicitly distinct concepts.
- `topic:` is retained as a project kind, narrowly defined to mean
  cross-cutting research-theme synthesis. Single-entity subjects
  belong in the catalog-contributed domain kind (`gene`, `biomolecule`,
  ...), not in `topic`.

## Open questions

- **Catalog authoring format**: where do ontology catalogs come from,
  what format do they use to declare kinds and entities, and how are
  snapshots distributed / versioned / refreshed? Resolved in principle
  (catalogs own both kinds and instances), deferred in detail to a
  catalog-authoring follow-on spec.
- **Bare-slug ambiguity UX**: the hard-error is the right default, but
  should there be a project-level opt-out for projects that deliberately
  want multi-kind slugs without explicit `same_as` declarations?
  Deferred until demand is demonstrated.
- **Catalog-kind vs. project-kind shadowing**: can a project register
  an extension kind named `gene` when the biology catalog also
  contributes `gene`? Recommend: hard error (matches the existing
  `EntityKindShadowError` for core-kind shadowing). Projects override
  individual entities via `same_as`, not by redefining kinds.
- **Which kinds does the v1 `biology` catalog contribute?** Out of
  scope here; a concrete candidate list (gene, protein, biomolecule,
  disease, phenotype, pathway, cell-type, biological-process,
  molecular-activity, anatomical-entity) belongs in the catalog
  follow-on.

## Relationship to other specs

- **2026-04-20 unified-entity-model**: this spec fills in the
  reference-resolution layer for the already-landed architecture and
  operationalizes the "core types are few; domain types come from
  catalogs" principle with a concrete kind-contribution mechanism.
- **2026-04-05 project-model**: this spec refines the conventions for
  which kind to use (`topic` vs. `concept` vs. `method` vs. domain
  entity) and makes the ProjectEntity / DomainEntity boundary
  observable at reference time.
- **2026-03-01 knowledge-graph-design**: this spec operationalizes the
  "`sci:Concept + biolink:Gene`" vision by making Biolink-backed
  entities first-class references via the ontology-catalog layer.
- **2026-04-21 project-curation**: curation sweeps surface unresolved
  references; this spec eliminates the systemic causes.
- **Follow-on: catalog authoring**: a separate spec will define the
  format by which ontology catalogs declare kinds and distribute
  entities. This spec is a prerequisite for that one.
