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

## Preconditions

This spec intentionally sits on top of the current unified-loader work,
but one prerequisite needs to be explicit:

- **Open-ended kind support at load time.** Today loader normalization
  copies `kind` into the closed `Entity.type` enum. Domain kinds like
  `gene`, `protein`, `disease`, `pathway`, or `phenotypic_feature`
  therefore cannot yet be instantiated as first-class entities even if the
  registry knows about them. Any implementation of catalog-contributed
  kinds or instances depends on a small model-layer follow-on that
  decouples load-time `kind` resolution from the closed core enum.

Changes 1, 3, 4, and 5 can ship before that prerequisite. Change 2
depends on it.

## Design overview

Four independent changes, each useful on its own, which together deliver
unified-reference semantics:

1. **Cross-kind slug fallback** at reference-resolution time, after
   exact-match alias resolution fails.
2. **Ontology catalogs contribute domain kinds first, and optionally
   resolvable entity instances in a second phase**.
3. **A documented lightweight `terms.yaml` convention** for concepts not
   worth a full file.
4. **`tag:` as a field-scoped classification token** for free-form labels
   that deliberately aren't entity references.

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
| **Domain catalogs — DomainEntity** | Ontology catalog (biology, chemistry, physics, ...) | gene, protein, disease, pathway, phenotypic_feature, biological_process, anatomical_entity, chemical_entity | catalog-declared; lightweight local extension via markdown or aggregate YAML |
| **Project extensions** | Individual project | project-specific concepts (e.g. `cytogenetic-event` in MM30) | project-registered extension kind |

The 2026-04-20 unified-entity-model spec's "core types are few" principle
holds: Science core owns only kinds that are genuinely cross-project.
Everything domain-specific moves into domain catalogs, which are
declared per-project via `ontologies: [...]` in `science.yaml`.

Applied to concrete mm30 references:

| Reference (current) | Kind + source (target) | Rationale |
|---|---|---|
| `topic:PHF19` | `gene:PHF19` from biology catalog | HGNC-grounded gene |
| `topic:chromatin` | a biology catalog term such as `cellular_component:chromatin` | Should resolve to a declared biology kind, not remain a synthetic `topic` |
| `topic:survival` | `method:survival-analysis` from science core | Cross-domain statistical method |
| `topic:bayesian` | `method:bayesian-inference` from science core | Cross-domain methodology |
| `topic:treatment-response` | `concept:treatment-response` from project `terms.yaml` | Not clearly a domain entity; project-local concept |
| `topic:phf19-prc2-ifn-immunotherapy` | `topic:phf19-prc2-ifn-immunotherapy` unchanged | Genuine cross-theme research synthesis |

This taxonomy is the scaffolding the rest of the spec hangs off of.

## Resolution algorithm

This spec standardizes the intended reference-resolution order:

1. Exact canonical-id match.
2. Explicit alias / manual alias match.
3. Canonicalization through any already-declared identity merge
   (`same_as`, once normalized into the alias map / entity index).
4. Scoped cross-kind fallback on the slug portion of `kind:slug`,
   only in places where shorthand entity references are allowed.
5. Otherwise unresolved.

The crucial constraint is that cross-kind fallback is a **lookup-time
fallback**, not a replacement for canonical ids or explicit aliases.

## 1. Cross-kind slug fallback

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

Keep `build_alias_map()` exact and explicit. Add a second resolution step
used by the audit / materialization paths:

- Parse `kind:slug`.
- Attempt exact-match alias resolution first, exactly as today.
- If exact resolution fails, consult a **slug index** keyed by the portion
  after the first `:`.
- If the slug maps to exactly one canonical entity identity, resolve to it.
- If the slug maps to multiple identities, report an
  `ambiguous_cross_kind_reference` failure on that specific authored
  reference.
- If the slug maps to multiple canonical ids that have already been
  collapsed into one identity via `same_as`, treat them as one target, not
  as an ambiguity.

This is intentionally narrower than "register every bare slug as a global
alias". The fallback only runs when an authored `kind:slug` reference has
already failed exact resolution.

### Scope of fallback

Cross-kind fallback is meant to smooth legacy shorthand like
`topic:PHF19`, not to become the primary naming mode for the whole system.
The initial scope should therefore be:

- enabled for entity reference fields such as `related`
- optional for migration tooling that rewrites old shorthand to canonical ids
- disabled for `same_as`, authored relation subjects/objects, and binding
  endpoints unless a later spec explicitly broadens it

### Why this is safe

- Direct `kind:slug` matches are still preferred.
- Ambiguity is surfaced where it happens: on the offending authored
  reference, not as a project-wide loader failure.
- Existing identity links remain authoritative. If a user declares
  `topic:PHF19 same_as gene:PHF19`, the fallback sees one merged identity,
  not two competing ones.

### Implementation shape

```python
def resolve_entity_reference(
    raw: str,
    *,
    alias_map: dict[str, str],
    slug_index: dict[str, set[str]],
    allow_cross_kind_fallback: bool,
) -> ResolutionResult:
    resolved = normalize_alias(raw, alias_map)
    if resolved != raw or raw in alias_map:
        return ResolutionResult.ok(resolved)

    if not allow_cross_kind_fallback or ":" not in raw:
        return ResolutionResult.unresolved(raw)

    _kind, slug = raw.split(":", 1)
    ids = slug_index.get(slug) or slug_index.get(slug.lower()) or set()
    canonical_identities = collapse_same_as_identities(ids)

    if len(canonical_identities) == 1:
        return ResolutionResult.ok(next(iter(canonical_identities)))
    if len(canonical_identities) > 1:
        return ResolutionResult.ambiguous(raw, sorted(canonical_identities))
    return ResolutionResult.unresolved(raw)
```

The audit and materialization paths need a small integration change:
they can no longer rely on `normalize_alias()` alone for shorthand
resolution.

### Scope / edge cases

- Homonyms across kinds are expected once catalogs contribute more real
  entities. They should produce per-reference ambiguity failures, not
  global load failure.
- `same_as` must collapse identities before ambiguity is evaluated.
- Case-insensitive collisions (e.g. `gene:PHF19` vs `concept:phf19`):
  still produce ambiguity when the authored shorthand does not resolve
  exactly.

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

Ontology catalogs become the canonical source for domain-specific kind
vocabularies, and may later become the source of resolvable domain
instances too. Split the work into two phases:

### Phase 2A: catalogs contribute kinds

For each declared catalog:

1. Register the catalog's kind names with the `EntityRegistry`.
2. Route those kinds to a generic `DomainEntity` first, unless and until a
   catalog-specific subtype contract is introduced.
3. Use the catalog's own vocabulary exactly as published. For the current
   biology catalog, examples include `gene`, `protein`, `disease`,
   `pathway`, `phenotypic_feature`, `biological_process`,
   `anatomical_entity`, and `chemical_entity`.

This phase depends on the precondition above: load-time support for
open-ended kinds.

### Phase 2B: catalogs contribute resolvable instances

In a follow-on step, a catalog may also provide resolvable entity
instances through a declared provider contract:

- vendored snapshots
- generated aggregate rows
- registry-backed providers with project-local caching

Each contributed instance should materialize as a lightweight
`DomainEntity` record that carries:

- a canonical id such as `gene:PHF19` or `disease:MONDO:0016419`
- the catalog term type (for example `biolink:Gene`)
- aliases / synonyms / external cross-references
- enough provenance to distinguish catalog-provided data from local
  authored extensions

Once Phase 2B exists, references like `gene:PHF19` can resolve directly
against the catalog-provided entity, and legacy shorthand like
`topic:PHF19` can resolve through change 1.

### Why catalogs must contribute *kinds* and not just instances

The 2026-04-20 unified-entity-model spec's "core types are few"
principle implies that domain-specific kinds must come from somewhere
other than Science core. The natural home is the domain ontology
catalog — it already owns the vocabulary and the schema invariants for
its entities. Moving kind registration into the catalog:

- Keeps Science core small and domain-agnostic.
- Makes kind availability explicit in `science.yaml`
  (`ontologies: [biology]` means `gene` is a valid kind;
  `ontologies: [chemistry]` means `chemical_entity` is).
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
ontology: biology
version: "1.0"
entity_types:
  - id: "biolink:Gene"
    name: gene
    description: "..."
    curie_prefixes: [HGNC, NCBIGene, ENSEMBL]
  - id: "biolink:Disease"
    name: disease
    description: "..."
    curie_prefixes: [MONDO, DOID]
instance_provider:
  kind: snapshot   # or generated/provider in a follow-on spec
  path: "biology/entities/gene.yaml"
```

This spec does **not** require the current catalog schema to grow all of
that immediately. It only establishes the architectural split:

- catalog files own domain kind vocabulary
- a later provider contract may own resolvable domain instances

Snapshot-vs-live policy, caching, refresh semantics, and instance-provider
format belong in the catalog-authoring follow-on spec.

### Interaction with project-local overrides

A project may author a local record that extends a catalog-contributed
entity — for example a project-local markdown page about `gene:PHF19`.
To make that possible, the loader needs an explicit tiered merge step.

Policy:

- **Tier order:** catalog-provided base entity first, then project-local
  authored overlays, then manual aliases.
- **Same `canonical_id` across tiers:** legal only for
  catalog-vs-project-local extension. Duplicate canonical ids within the
  same source tier remain hard errors.
- **Merge rule:** project-local prose fields and authored graph links win on
  scalar conflicts. `same_as`, `aliases`, and `ontology_terms` are unioned.
  Provenance should preserve both the catalog source and the local source.
- **Different `canonical_id` but intended same entity:** author
  declares `same_as: [gene:PHF19]` on the local record. Identity collapse
  happens after load, not by pretending the ids were identical.
- **Kind disagreement** (e.g. project authored `topic:PHF19`, catalog
  contributes `gene:PHF19`): exact ids stay distinct; change 1 may resolve
  authored shorthand to one side or surface ambiguity on the specific
  reference until the project migrates.

### Scope / open questions (for follow-up implementation)

- **Catalog sourcing mechanism** — vendored snapshots vs. live
  registries vs. per-project config. Deferred to a catalog-authoring
  spec.
- **Catalog caching / refresh policy** — how does a project opt
  into updates, when does the cache invalidate. Follow-on.
- **Exact model-layer change for open-ended kinds** — whether `Entity.type`
  becomes open, split from `kind`, or is replaced for load-time entities.
  This spec depends on that choice but does not make it.
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

Introduce `knowledge/sources/<local_profile>/terms.yaml` by convention.
Loaded by the aggregate adapter as a second multi-entity source file with
an explicit `terms:` top-level key. Documented as:

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

The `AggregateAdapter` should treat `terms.yaml` as a first-class sibling
to `entities.yaml`, not as an undocumented special case:

- discovery checks for both `entities.yaml` and `terms.yaml`
- `entities.yaml` keeps its existing `entities:` top-level key
- `terms.yaml` uses a `terms:` top-level key
- each `terms.yaml` row is normalized into the same raw-record shape as an
  `entities.yaml` row before registry dispatch
- `kind` is derived from `id.split(":", 1)[0]` when not explicitly present
- `description`, if present, feeds `content_preview`
- `content` / body-style fields are ignored or rejected so the file stays
  intentionally lightweight

If the derived kind is unregistered, the existing warn-and-skip path
still handles it cleanly.

### Promotion path

When a term in `terms.yaml` accumulates enough content (more than a
title and a few aliases), author promotes it to a markdown file in the
appropriate directory (`doc/concepts/`, `doc/methods/`, etc.) and removes
the entry from `terms.yaml`. The `id` stays stable — references don't
break.

Promotion is a move, not a duplication. During the transition, the same
`canonical_id` should not live in both `terms.yaml` and markdown unless a
later merge-capable loader explicitly allows that source combination.

### Why a second aggregate file

`terms.yaml` vs. `entities.yaml` separation signals intent: `entities.yaml`
holds domain / legacy / heavyweight aggregate records; `terms.yaml` holds
one-line concept stubs. The tool doesn't distinguish them operationally
(both load through the same adapter), but the convention gives authors
a clean home for the lightweight case.

Projects that don't need the distinction can keep everything in
`entities.yaml`. `terms.yaml` is opt-in.

## 4. `tag:` as a field-scoped classification token

### Current state

`is_external_reference()` is used broadly across entity refs, relations,
bindings, and `same_as`. A blanket prefix-level exemption therefore affects
more than just `related:`.

### Proposed change

Recognize `tag:*` as a special classification token **only in fields where
free-form labels make sense**. Initial policy:

- allowed in entity `related:` lists as a non-entity classification marker
- not allowed in `same_as`
- not allowed in authored relation subjects or objects
- not allowed in binding endpoints
- not treated as a general-purpose external identifier namespace

Projects that want structured, queryable classification still use
`concept:*` or ontology-backed terms. `tag:*` is explicitly reserved for
unstructured labels.

### Why add it

- Documents currently use `tags: [...]` as a YAML string list, which has no
  link integrity. `tag:X` in a `related:` field is a clearer signal: this
  is a labeling intent, not an entity reference.
- Separates "I'm classifying this document" from "I'm pointing at an
  entity." Both are valid; conflating them is what produces the "unresolved
  topic" noise.

### Scope

- `tag:` is not a registered kind; there's no such thing as a `tag` entity.
- Existing `tags: [...]` string lists in frontmatter are unaffected.
- Implementation should use field-sensitive handling, not simply add `tag`
  to the global external-prefix set.

## 5. Narrowing the `topic` kind

### Current conflation

In practice, `topic:` files span four distinct patterns:

1. **Domain entities with ontology backing** (`topic:PHF19` with
   `same_as: [HGNC:30074]`) — really `gene:` / `protein:` / `disease:`.
2. **Methodology primers** (`topic:bayesian`) — really `method:`.
3. **Single-word concept labels or domain shorthands** (`topic:chromatin`)
   — really `concept:` or a catalog-defined domain kind.
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
  a gene is `gene:`, a disease is `disease:`, and other single-subject
  cases should use the catalog's own vocabulary. `topic` is not the
  fallback for "a thing I want to write about"; it's specifically for
  *theme-level synthesis*.
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
| `topic:chromatin` | a biology catalog kind | biology catalog | catalog-contributed term or local concept, depending on the chosen catalog vocabulary |
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
- Exact alias lookup fails.
- Cross-kind fallback consults the slug index and finds exactly one
  canonical entity identity, `gene:PHF19`.
- Reference resolves to `gene:PHF19`. No audit warning.
- Dev writes `related: ["topic:treatment-response"]`. No matching slug.
- Audit surfaces unresolved. Dev adds one line to `terms.yaml`
  (`{id: "concept:treatment-response", title: "..."}`) per change 3.
- Resolved.
- Dev writes `related: ["tag:draft"]` on a work-in-progress plan. Change
  4 treats it as a legal classification token in `related:`; audit skips.
- Over time, the project converges on `gene:`, `concept:`, `method:`, and
  narrow-scope `topic:` via change 5. Existing `topic:X` references keep
  working throughout.

## Implementation order

Recommended shipping order (smallest → largest, independently useful):

1. **Change 4** — field-scoped `tag:` handling. Small code change, but not
   just a prefix-list edit because behavior must vary by field.
2. **Change 1** — cross-kind fallback at lookup time. Moderate change:
   introduces a slug index plus per-reference ambiguity reporting.
3. **Change 3** — `terms.yaml` convention. Small code + doc change:
   adapter discovery, top-level-key handling, and tests.
4. **Change 5** — `topic` narrowing. Pure documentation (spec + writing
   guidance). No tool changes.
5. **Prerequisite follow-on** — open-ended kind support at load time.
6. **Change 2A** — catalogs contribute kinds.
7. **Change 2B** — catalogs contribute resolvable instances.

Changes 1, 3, and 4 are still small-to-medium. Change 5 is pure
documentation. The prerequisite + change 2A/2B sequence is the multi-week
part.

## Testing strategy

Each change gets its own test module under
`science-tool/tests/graph/references/`:

- `test_cross_kind_slug_resolution.py` — bare slug lookup, ambiguity
  detection, `same_as` identity collapse.
- `test_ontology_catalog_kinds.py` — catalog-declared kinds register
  correctly once open-ended kinds are supported.
- `test_ontology_catalog_entities.py` — instance-provider contributions
  appear in the entity index; local overlay merge works as specified.
- `test_terms_yaml_adapter.py` — minimum-field entries load; top-level
  `terms:` key is honored; promotion
  path (same id moves from terms.yaml → markdown) leaves refs stable.
- `test_tag_reference_policy.py` — `tag:X` is accepted in `related:` and
  rejected in `same_as`, relation endpoints, and bindings.
- Existing regression fixtures (mm30 golden-snapshot equivalents)
  continue to pass unchanged for projects that haven't migrated.

## Migration and backward compatibility

No breaking changes for existing projects. Each change is additive:

- Change 1 only adds fallback behavior after exact-match lookup fails.
- Change 2A adds kinds; 2B adds entities and an explicit merge phase.
- Change 3 only adds a recognized filename; nothing breaks if it's absent.
- Change 4 only legalizes `tag:*` in scoped fields; projects using `tag:`
  as a real entity kind still need a migration because this spec reserves
  the prefix for non-entity labels.
- Change 5 is documentation only.

Projects that have already authored entity files continue to work. The
changes *add* ways to reference things without authoring; they don't
remove any existing pathway.

## Resolved decisions

- Cross-kind shorthand resolution is a lookup-time fallback after exact
  alias resolution, with ambiguity reported on the specific reference.
- Ontology catalogs contribute domain kinds first; resolvable instances
  come in a second phase behind an explicit provider contract.
- Science core owns only cross-domain kinds (ProjectEntity core plus
  `method`, `concept`, `variable`, `model`). Domain-specific kinds
  (`gene`, `protein`, `disease`, etc.) come from
  ontology catalogs, not from Science core.
- `terms.yaml` is a documented convention for lightweight concepts;
  technically redundant with `entities.yaml` but semantically distinct.
- `tag:` is a field-scoped classification token; tags and entities are
  explicitly distinct concepts.
- `topic:` is retained as a project kind, narrowly defined to mean
  cross-cutting research-theme synthesis. Single-entity subjects
  belong in the catalog-contributed domain kind (`gene`, `disease`,
  or another catalog-defined domain kind), not in `topic`.

## Open questions

- **Catalog authoring format**: where do ontology catalogs come from,
  what format do they use to declare kinds and instance providers, and how are
  snapshots distributed / versioned / refreshed? Resolved in principle
  (catalogs own both kinds and instances), deferred in detail to a
  catalog-authoring follow-on spec.
- **Bare-slug ambiguity UX**: should ambiguous shorthand remain a hard
  audit failure, or become a warning plus canonicalization suggestion in
  some migration modes? Deferred until demand is demonstrated.
- **Catalog-kind vs. project-kind shadowing**: can a project register
  an extension kind named `gene` when the biology catalog also
  contributes `gene`? Recommend: hard error (matches the existing
  `EntityKindShadowError` for core-kind shadowing). Projects override
  individual entities via `same_as`, not by redefining kinds.
- **Which kinds does the v1 `biology` catalog contribute?** Out of
  scope here; a concrete candidate list (gene, protein, disease,
  phenotypic_feature, pathway, biological_process, anatomical_entity,
  chemical_entity, ...) belongs in the catalog
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
