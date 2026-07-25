# Entities

An entity is a durable typed record in a Science project. Most entities are
Markdown files with YAML frontmatter and body prose. The frontmatter provides
machine-readable identity and relationships; the body provides human-readable
context.

## Figure Key

The figures in this guide share one visual vocabulary. Color marks an entity's
**class**; shape reinforces its **kind family** and the label names the exact
kind. Derived state (belief, snapshots, the graph) is drawn in slate with a
`derived` badge — never as authored source.

<figure class="sci-fig">
--8<-- "figures/f0-vocabulary.svg"
<figcaption>Entity vocabulary reader's key.</figcaption>
</figure>

## Entity Shape

```markdown
---
id: proposition:example
kind: proposition
title: "Example proposition"
status: draft
related:
  - hypothesis:h01-example
source_refs:
  - paper:Example2026
created: "2026-06-20"
updated: "2026-06-20"
---

# Example proposition

This body explains the proposition, scope, caveats, and evidence needs.
```

Important fields:

| Field | Purpose |
|---|---|
| `id` | Stable typed reference, usually `<kind>:<local-part>`. |
| `kind` | Entity kind. Usually matches the prefix in `id`. |
| `title` | Human-readable title. |
| `status` | Lifecycle state for the kind. |
| `related` | Other entity refs connected to this record. |
| `source_refs` | Sources or annotations that support the existence or content of this record. |
| Body prose | Explanation, caveats, rationale, and review context. |

`kind` is the authoritative load-time discriminator. Core Science kinds also
carry a `type` projection internally, but catalog, profile, and
project-extension kinds load as open-ended strings rather than being forced
through a closed enum or an `unknown` fallback. Kind matching is exact.

<figure class="sci-fig">
--8<-- "figures/f8-entity-anatomy.svg"
<figcaption>An entity file: <code>kind:id</code>, machine-readable frontmatter, human-readable body.</figcaption>
</figure>

## Authored And Derived Fields

Authored fields are recorded directly in source files. Derived fields are
computed from the graph, evidence, provenance, or health machinery. Belief
state, support summaries, dispute summaries, freshness, and health status should
be recomputed rather than manually patched.

## Source Entity CLI

Use `science entity` for routine source-authored entity work. These commands
write Markdown owners and then validate the prospective source load. They do not
mutate `knowledge/graph.trig`; rebuild the graph after durable source edits:

```bash
science entity create question "What explains the observed signal?"
science entity edit question:0001-what-explains-the-observed-signal --status answered
science entity note question:0001-what-explains-the-observed-signal "Resolved by interpretation:0001-model-check."
science entity list question
science graph build
```

The generic command surface is:

| Command | Purpose |
|---|---|
| `science entity create <kind> <title>` | Create a new Markdown owner under the kind's path policy. |
| `science entity show <ref>` | Show the loaded source record. |
| `science entity edit <ref>` | Update frontmatter metadata such as `title`, `status`, `related`, and `source_refs`. Relation and source-ref edits are additive. |
| `science entity note <ref> <note>` | Append a dated note under `## Notes` and advance `updated`. |
| `science entity list [kind]` | List source-authored entities, with `--kind`, `--status`, `--related`, `--include-hidden`, and `--include-archived` filters. |
| `science entity sections <kind>` | Inspect effective frontmatter constraints and template section keys for kinds backed by packaged templates. |
| `science entity neighbors <ref>` | Query graph neighbors from the materialized graph. This may warn when source files are newer than `knowledge/graph.trig`. |

Typed wrappers call the same writer and validation path as `science entity`.
Use them when they add kind-specific ergonomics:

| Wrapper | Notes |
|---|---|
| `science questions create` | Source-authored questions. |
| `science hypotheses create` | Supports `--phase candidate` to include promotion criteria. |
| `science discussions create` | `--focus <ref>` is stored as a related reference. |
| `science interpretations create` | `--input <ref-or-path>` is stored as a source reference. |
| `science propositions create` | Durable proposition sources; use this instead of retired `graph add proposition` for project work. |
| `science evidence-lines create` | Durable support/dispute evidence line sources. |

### Importing Loose Design Docs And Plans

`science entities import` turns a loose Markdown document into a canonical entity:
it proposes a numeric id, stamps frontmatter, relocates the file under the kind's
home, and repoints structured references (frontmatter reference fields and Markdown
links). Plain prose or code path mentions are reported separately and never rewritten.

Preview the import read-only and save the plan outside the project tree:

```bash
science entities import docs/_staging/my-design.md --kind spec --save-plan /tmp/p.json
```

**Inspect the manual-hit list** in the preview before applying — those prose/code path
mentions are not auto-repointed. The `--save-plan` step prints a `plan_sha256`; apply the
saved plan under that approval envelope, so a plan edited or swapped after review is refused:

```bash
science entities import --apply-plan /tmp/p.json --expected-plan-sha256 <plan_sha256>
```

Finally, **commit the canonical entity** at `entities/specs/NNNN-slug.md` (or
`entities/plans/NNNN-slug.md`), not the staging file. The source must live inside the
project root; the saved plan (`/tmp/p.json`) lives outside the project tree, since a
stale plan file is itself a scannable reference artifact. Use `--kind spec` for design
docs and `--kind plan` for implementation plans. This keeps design docs and plans
first-class: author a staging file and import it, committing the resulting entity rather
than the loose file. Newly scaffolded or imported projects carry this in their
`AGENTS.md`; **existing adopters need a manual AGENTS.md update** to adopt it.

### Migrating Legacy Specs (`science entity migrate-specs`)

Older projects hold `spec`-typed design docs at loose paths (`doc/plans/…`,
`doc/specs/…`) with date-slug or semantic ids. `science entity migrate-specs`
canonicalizes them into numeric `entities/specs/NNNN-slug.md` entities, preserving
each old id as an alias and repointing the references it can safely rewrite.

**`spec:` references still resolve as annotation-only today.** This command makes a
project *flip-ready*; it does not change resolution. Turning on `spec:` resolution
is a separate, later, gated step — run the migration first, land clean, then adopt
the revision that flips resolution (migrate-then-flip across revisions).

Plan first (writes nothing), then apply:

```bash
science entity migrate-specs                 # dry run: the plan + a flip-readiness report
science entity migrate-specs --format json   # the machine-readable report (flip_ready, counts)
science entity migrate-specs --apply         # relocate, rewrite, and report
science entity migrate-specs --resume        # finish an interrupted --apply from its journal
```

**What it projects.** Legacy frontmatter is mapped to the canonical spec schema:
`type: spec` → `kind: spec`; `date:` seeds `created`/`updated`; `related_questions`
/ `related_specs` fold into `related`; unambiguous legacy statuses map to the
canonical vocabulary (`draft/active/complete/superseded/retired/archived`).
Anything ambiguous — an unmappable status like `approved`, a missing `id:`/`title`,
an authored load-derived key — is **refused, per file**; the migration never guesses.
A date-slug id (`spec:2026-03-16-…`) is minted a fresh numeric id, not mistaken for
an already-numbered spec.

**How references are reported.** Each `spec:` reference is classified into five
groups: **rewritten** (auto-repointed), **alias_resolved** (resolves via the old-id
alias, optional cleanup), **identity_preserved** (inert prose/key mentions),
**unchanged** (already points at a live numeric spec), and **manual_retarget**
(`discusses` frames and unresolved ids — a human must fix these).

**Flip-readiness.** `flip_ready` is `true` only when no un-relocated legacy spec, no
`kind: spec` file at a singleton home, and no `manual_retarget` reference remains,
and the scan was complete. A singleton-home `spec` file is **reported, never
auto-relocated** — reconciling it is a project judgment.

### CLI Path And Identity Policy

The source entity CLI creates only kinds that have a built-in Markdown path
policy. Current owners live under `entities/` according to the core profile, for
example `entities/questions/`, `entities/hypotheses/`,
`entities/propositions/`, `entities/evidence-lines/`, and
`entities/interpretations/`. In layout v3, the prose tree is prose-only and
the knowledge tree is generated state. See [Project Layout](project-layout.md)
for the full root contract.

By default, filenames follow the entity id local part. Numeric kinds generate a
four-digit local part plus slug, such as `question:0001-observed-signal`.
Slug and id-local kinds use a deterministic kebab-case slug. Citekey and
verbatim kinds require an explicit `--id`, and singleton kinds are not created
through this path. Use `--slug` to override only the generated slug component,
or `--id` to set the complete canonical id; do not pass both.

`--path` is intentionally narrow: it must be a project-relative `.md` path under
`entities/`, must not be absolute, and must not contain `..`. It is for unusual
source placement inside the owner tree, not for writing entity owners into prose
or specification roots, overlays, or generated graph files.

References accepted by `show`, `edit`, `note`, and `neighbors` are exact
canonical ids or unambiguous local shorthands. Registered shortforms such as
`q1`, `h1`, `p1`, `i1`, `d1`, and `t1` resolve to the corresponding core kind
when they identify exactly one loaded source record.

### Source Write Boundary

The old graph writers for concepts, propositions, observations, evidence,
findings, interpretations, discussions, mechanisms, hypotheses, questions,
stories, papers, falsifications, articles, and edges are retired. For project
knowledge that should survive `science graph build`, create or edit the source
entity file, author structural relations in `relations.yaml` or inquiry
`flow_edges`, and represent support or dispute with evidence-line source
entities. Use `science entity create story <title>` for stories,
`science entity create paper <title> --id <citekey>` or
`entities/papers/<citekey>.md` with `doi:` for external literature notes, and
`science entity create falsification <title>` with `falsifies:` for
falsification records. The graph build step materializes those source records
into `knowledge/graph.trig`.

## Entity Consolidation And Archive

Science separates entity cleanup into two cases:

| Case | Surface | Result |
|---|---|---|
| Linear supersession | `science entities mark-superseded` then `science entities archive` | Older entities are hidden or relocated, while references remain resolvable. |
| Semantic consolidation | `science curate consolidation-candidates`, then `science entities consolidate scaffold/apply` | A live cluster-digest summarizes several members, and the members move into the archive. |

Hidden status and archive location are different axes. `superseded` and
`archived` entities are hidden from normal entity lists by default, but a hidden
entity may still live under its original path. Archived files live under
`entities/_archive/` and are skipped by normal source loading. Use
`--include-hidden` to show hidden live records and `--include-archived` to include
archived records in entity listing. `--include-archived` does not imply
`--include-hidden`; use both when you need hidden archived rows in list output.

### Supersession And Candidate Review

`science entities mark-superseded` is report-then-apply. It detects linear
`supersedes` chains, marks non-survivors as `superseded`, and leaves graph
resolution intact. Run it without `--apply` first:

```bash
science entities mark-superseded --project-root .
science entities mark-superseded --project-root . --apply
```

`science curate consolidation-candidates` is read-only decision support. It
reports mechanical superseded lineage and heuristic semantic clusters, then
exits without editing files:

```bash
science curate consolidation-candidates --project-root . --format json
```

Semantic cluster detection is intentionally precision-oriented. Structural
families qualify on durable signals such as shared id stem or explicit `group`.
Shared task families and single shared anchors are corroborating signals, not
enough by themselves. Related-overlap clusters use entity-reference overlap,
not free-text citation strings. Treat the report as a review queue, not an
automatic consolidation plan.

The detector defaults are tuned to avoid flooding review with topical but
non-redundant clusters. A real-corpus tuning pass found high precision from
`id-stem`, heavy noise from task-family and single-anchor signals, and large
single-linkage blobs from loose related-overlap. The default related-overlap
Jaccard threshold is therefore `0.7`, and oversized clusters above the default
maximum size are suppressed rather than silently capped.

### Archive Index

`science entities archive` relocates hidden-status entities into
`entities/_archive/` and appends one row per operation to
`entities/_archive/archive-index.jsonl`:

```bash
science entities archive --project-root .
science entities archive --project-root . --apply
science entities unarchive interpretation:0001-old --project-root .
science entities unarchive interpretation:0001-old --project-root . --apply
```

The default archive statuses are `superseded` and `archived`; pass `--status`
to choose a narrower or custom set. Archive and unarchive are report-then-apply
and never overwrite destination files. Archive moves each file first, appends the
index row, and rolls the move back if appending fails. Unarchive restores the
original path and appends an `unarchive` tombstone. The archive index is
append-only; the active archive set is the last operation per id.

Archive rows preserve `id`, `kind`, `title`, `aliases`, `same_as`, `status`,
`superseded_by`, `original_path`, timestamps, and consolidation fields such as
`consolidated_into` and `digest_insight` when present. Reference resolution uses
the active archive index, not scans of archived Markdown files, so references to
archived ids, aliases, and `same_as` tokens remain resolvable. `science validate`
checks for active rows whose files are missing, archived files without active
rows, and archive id/alias collisions with live or archived entries.

Use archive-aware retrieval when you need to find old material:

```bash
science search "old finding" --archived --project-root . --format json
science entity list --include-archived --include-hidden
```

Archived entities are frozen for tool-mediated edits. If an edit command targets
an archived id or alias, Science tells you to unarchive, edit, then re-archive.
Raw filesystem edits under `entities/_archive/` are outside that tool contract.

### Cluster Digests

Semantic consolidation creates a live `synthesis` entity with
`report_kind: cluster-digest`. The digest carries one authored relation per
member:

```yaml
report_kind: cluster-digest
relations:
  - predicate: sci:consolidates
    target: finding:0001-old
```

Create the digest first, review and fill in its body, then apply the
consolidation:

```bash
science entities consolidate scaffold \
  --project-root . \
  --into synthesis:0001-digest \
  --members finding:0001-old,finding:0002-old \
  --title "Digest of old findings"

science entities consolidate apply synthesis:0001-digest --project-root .
science entities consolidate apply synthesis:0001-digest --project-root . --apply
```

`scaffold` validates that every member is live, that no member is the digest
itself, that members are unique, and that the digest id does not collide with an
active archived id or alias. It refuses kinds whose closed status vocabulary
lacks `archived`. If the create-then-rewrite validation fails, the new digest
file is removed.

`apply` validates that the digest is a `cluster-digest` with
`sci:consolidates` relations, then processes members one at a time. For each
member, it snapshots bytes, writes `status: archived` and `consolidated_into`,
relocates the file through the archive machinery, and appends an archive-index
row with `reason: consolidated` and `digest_insight`. A failure restores the
current member's original bytes. Earlier members in the same run remain archived
if they already succeeded; recovery is explicit with `science entities
unarchive`, manual digest adjustment, or a rerun after repair.

The digest remains live. Archived members are represented in the index by
`consolidated_into`, and the archive index is the source for alias and `same_as`
redirection to the digest. A scaffolded-but-unapplied digest has live members;
those members are not redirected until `apply --apply` archives them.

As-built boundaries are intentionally narrow. Science does not auto-patch
project manifests during consolidation, does not write a separate `cluster_id`
field when `consolidated_into` names the digest, and does not rematerialize full
archived Markdown into the live graph. `--include-archived` is a recall surface
for listing and search, while normal source loading and graph builds continue to
skip `entities/_archive/`.

## Entity Loading And Storage Adapters

Science loads authored entities through one model family, not through separate
schemas per file format. The stable flow is:

```text
storage format -> storage adapter -> entity registry -> validated entity
```

The canonical base contract is `Entity`: `id`, `canonical_id`, `kind`, `title`,
status, source references, aliases, external mappings, authored relationships,
body prose, and source-location metadata. `ProjectEntity` and `DomainEntity`
are subfamilies for project-operational records and domain-grounded records.
Core kinds with stronger invariants, such as `task`, `dataset`,
`workflow-run`, `research-package`, `paper`, `mechanism`, `evidence-line`,
`proposition`, and `code-file`, validate through typed subclasses. Profile,
extension, and ontology-catalog kinds still participate in the same base
contract, usually as `ProjectEntity` or `DomainEntity` unless Science owns a
typed subclass.

The entity registry resolves `kind` to the schema that validates a record.
Science registers core kinds itself. Active profiles, declared ontology
catalogs, and local manifests register additional loadable kinds in separate
tiers: core, profile, catalog, and project extension. Duplicate registrations
and attempts to shadow core/profile/catalog kinds are hard errors; unknown
kinds are skipped with an explicit diagnostic instead of being silently treated
as a different entity type.

Core kind facts live in the built-in `CORE_PROFILE` descriptors. Those
descriptors are the source of truth for core kind category, entity class,
template readiness, shortform aliases, markdown home, filename strategy, default
status, and closed status vocabulary. The tool layer derives path policies,
status validation, and shortform maps from those descriptors instead of keeping
parallel kind tables.

Kind categories are named contracts. `authored-core` kinds are Science-owned
project records. `reserved` kinds are built-in sentinels such as `unknown`.
`source-only` kinds are valid profile kinds loaded from structured sources rather
than authored as core Markdown files.

Project-local profiles can declare additional markdown kinds under
`entity_kinds:`. A local kind's `name` is its kind, id prefix, and default
directory segment. Unless the profile says otherwise, a local kind is stored at
`entities/<kind>/`, uses numeric local ids, defaults to `active`, and accepts any
status. Optional profile fields can set `home`, `strategy`, `default_status`, and
`statuses`. Local `home` overrides must stay under `entities/<segment>/...`, and
local kinds cannot shadow core kinds or use singleton layout.

The source-entity creation CLI remains conservative: `science entities create`
mints only built-in Markdown path-policy kinds. Project-local kinds are loaded,
migrated, and validated when authored as Markdown, but new local-kind creation is
still a manual authoring or project-specific workflow.

Storage adapters own discovery and parsing only. They discover project-relative
source locations, load a raw record with `kind` and identity fields, and pass
that record to the registry. They do not decide dataset semantics, task state,
or domain-entity validity. Those rules live on the resolved entity schema and
on validation checks.

Adapter-specific load policy is declared on the adapter, not hard-coded in the
source-load loop. The shared policy surface includes:

| Policy Hook | Purpose |
|---|---|
| `participation_mode` | Whether records are owners, borrowers, or external references in the identity table. |
| `should_defer(already_owned=...)` | Whether this record yields to an already-loaded owner instead of declaring another owner. |
| `skip_core_on_missing_identity` | Allows Markdown frontmatter without identity fields to be skipped with a diagnostic rather than crashing schema validation. |
| `source_document(ref, raw)` | Captures Markdown frontmatter/body for annotation and source-text consumers. |
| `deferred_dataset_datapackage(...)` | Lets a deferring datapackage keep package-resource metadata available after a Markdown owner wins. |

This policy surface keeps adapter quirks close to the adapter. For example,
bibliography and CURIE-reference adapters act as external references and defer
to existing owners; datapackage records are owner-shaped but defer when a
project source already owns the dataset id; Markdown records are the only
records that capture a source document body.

Current project source loading uses these adapter families:

| Adapter | Source surface | Role |
|---|---|---|
| `markdown` | `entities/**/*.md` and `research/packages/**/*.md` | Normal single-entity authoring surface with YAML frontmatter and body prose. |
| `bib` and `curie-ref` | bibliography and ontology reference inputs | External-reference rows that defer to an existing entity owner when one exists. |
| `datapackage` | `data/**/datapackage.yaml` and `results/**/datapackage.yaml` with `science-pkg-entity-1.0` | Dataset entity records embedded in promoted runtime packages; if a Markdown owner already exists, the datapackage defers but remains available as resource metadata. |
| `workflow-run`, `task`, and `code` | workflow run files, task sources, and configured code roots | Specialized storage formats that materialize first-class entities into the same registry flow. |
| `commons-merged` and `overlay` | shared/commons entities and local overlays | Cross-project entity owners and borrower overlays loaded into the same identity table. |

Dataset, workflow, workflow-run, and workflow-step owners are first-class
Markdown entity kinds. They use `strategy: id-local`: the explicit frontmatter
`id` is authoritative and the filename follows the id local part. For example,
`dataset:ctrpv2` lives at `entities/datasets/ctrpv2.md`. Commons borrower files
with `overlay_of:` live under `overlays/<type>/`, not under `entities/` and not
under `doc/`.

Every loaded entity records the adapter that sourced it. The loader also keeps
`SourceRef` metadata: adapter name, project-relative path, and entry index when
the source is a multi-row file. Validation and collision errors should point to
that source location.

Canonical identity is strict. Within one owner scope, two owner records for the
same `canonical_id` are a project-state error. Deferring adapters, such as
bibliography references and datapackages with an existing entity owner, may
contribute supporting metadata without claiming a second owner. Cross-project
commons and overlay declarations are tracked separately so reference resolution
can distinguish local owners, shared owners, and borrowers.

Identity diagnostics use two strictness levels. Normal source loading is strict
and raises early on duplicate ownership. Audit, validation, and migration paths
that need to explain transitional project state load non-strictly, compile the
same identity table, and report structured rows. A collision between two
non-deprecated owners is a hard failure. A deprecated aggregate or datapackage
owner shadowing one real owner is transitional debt: it is visible as a warning
and should be retired, but it is not the same as two real owners claiming one
identity.

Bare references are valid only when the target has a single owner in the loaded
identity table. If the same id is owned in multiple scopes, such as a local owner
and a commons owner, graph audit reports `ambiguous_reference`. Use an explicit
scope prefix such as `commons:topic:single-cell-foundation-models` when the
intended owner is the shared commons entity.

Graph build uses the same compiled source model for audit and materialization:

```text
Load -> Audit -> Emit -> Derive -> Write
```

`science graph audit` stops after Load and Audit. It reports unresolved or
ambiguous references without deriving graph layers and without writing
`knowledge/graph.trig`. `science graph build` runs the full sequence and
hard-gates on audit failures before emitting or writing the graph.

The public in-memory build helper consumes a `ProjectSources` object and returns
an RDF dataset without touching the filesystem. That pure path is used by
diagnostic and freshness checks that need to compare expected graph state without
writing generated files.

## Domain Ontology Catalogs

Science separates ontology vocabulary from authored project knowledge. Declared
ontology catalogs provide entity kinds, relation predicates, and recognized
CURIE prefixes. They do not import external knowledge graph assertions into the
project graph. A project can use community vocabulary such as `gene` or
`interacts_with`, but claims like "gene X interacts with protein Y" must still
be authored by the project with evidence.

Declare domain catalogs in `science.yaml`:

```yaml
ontologies: [biology, chemistry]
knowledge_profiles:
  local: local
```

Available built-in catalogs are registered in
`science_model/ontologies/registry.yaml`. The current bundled names are
`biology`, `physics`, `units`, `math`, `earth`, `chemistry`, `astronomy`, and
`information`. Unknown names fail early when project sources load.

Each bundled catalog is package data with the same YAML shape:

| Field | Purpose |
|---|---|
| `ontology`, `version`, `prefix`, `prefix_uri` | Catalog identity and source vocabulary. |
| `entity_types` | Loadable domain entity kind names, descriptions, CURIE prefixes, and recommendation flags. |
| `predicates` | Domain relation predicate names, descriptions, domain/range metadata, and recommendation flags. |

When a catalog is declared, its entity type names become registered
`DomainEntity` kinds for that project. The entity loader sets the entity
`profile` to the catalog name, keeps authored entities in `graph/knowledge`, and
uses catalog CURIE prefixes for external-reference recognition. The suggestion
mechanism also scans undeclared catalog kinds and CURIE prefixes during graph
build and may recommend adding a catalog to `science.yaml`.

Catalogs are flat in the current model: Science validates names and prefixes but
does not perform ontology hierarchy reasoning, runtime ontology fetching, or
external assertion import. Add new domains through the documented catalog
process in [Adding a Domain](https://github.com/khughitt/science/blob/main/docs/process/adding-a-domain.md).

## Reference Semantics

References should name the most specific stable semantic object available.
Science resolves exact ids and aliases first, then may use cross-kind slug
fallback only for migration paths such as an old `topic:PHF19` mention that now
has a single unambiguous `gene:PHF19` owner. Ambiguous slug matches remain
health or materialization findings; do not rely on fallback as the authored
canonical form.

Use these destinations instead of new semantic `topic:*` refs:

| Intent | Preferred reference |
|---|---|
| Catalog-backed thing | Domain kind such as `gene`, `protein`, `disease`, `pathway`, or another declared catalog kind. |
| Analytical procedure | `method`. |
| Stable project-local concept | Prefer the most specific registered source kind. When a local `concept:*` ref needs a durable graph identity, create a Markdown owner with `science entity create concept ...`. |
| Cross-cutting organizing lens | `theme`. |
| Conjecture under investigation | `hypothesis`. |
| Analysis-session narrative | `interpretation`. |
| Communication-layer synthesis | `story`. |
| Named explanatory bundle with participants and claims | `mechanism`. |
| Temporary classification marker | Field-scoped `tag:*`, only where free-form labels are accepted. |
| Operational marker | `meta:*`, or prose when it should not enter the graph. |

### Project-Local Concepts

Project-local concepts use the same owner-file model as other durable entities.
Use `science entity create concept "<title>"` when a `concept:*` ref needs to
resolve in the graph:

```bash
science entity create concept "Treatment Response"
```

For weak or temporary ideas, keep the mention in prose until it needs a graph
identity. For catalog-backed objects or procedures, prefer the most specific
registered kind instead of a generic concept owner.

### Source-Authored Concepts

Use the most specific registered kind before creating a local concept. Domain
and core reference kinds such as `gene`, `protein`, `disease`, `pathway`,
`dataset`, `method`, `construct`, or `outcome` carry more meaning than a generic
`concept:*` owner.

For weak or temporary ideas, keep the mention in prose until it needs a graph
identity.

Use `science entity create concept "<title>"` when a project-local concept needs
a full Markdown owner:

```bash
science entity create concept "Treatment Response"
```

That command writes `entities/concepts/<slug>.md` and uses the normal entity
lifecycle: slug identity, `active` / `deprecated` status validation, source
refs, related refs, aliases, same-as links, notes, and graph materialization.

`science graph add concept` is retired. Do not use retired graph-writer output
as a durable owner for variables, treatment/outcome refs, unknowns, or boundary
refs; author `entities/concepts/<slug>.md` and rebuild instead.

### Legacy Topic Triage

`topic` remains registered for legacy projects and migration surfaces, but it is
not the default semantic destination for new work. Do not create topic stubs to
silence unresolved-reference checks. Triage each legacy `topic:*` mention into a
catalog-backed entity, method, concept, theme, hypothesis, interpretation,
story, mechanism, metadata, or prose-only note.

## Papers And Manuscripts

Science uses separate references for external literature and user-authored
publication drafts:

| Surface | Meaning |
|---|---|
| `paper:<bibkey>` | External literature note for a paper the project has read, searched, or summarized. |
| `cite:<bibkey>` | Bibliography/source reference, usually backed by `papers/references.bib`. |
| `manuscript:<slug>` | The project's own publication-in-progress. |

Use `entities/papers/<bibkey>.md` and `templates/paper.md` for external
literature notes. Use `templates/manuscript.md` for publication drafts. Do not
use `paper:` for the project's own manuscript.

The canonical bibkey is the full substring after the first `:`. Comparisons are
case-sensitive and byte-for-byte: `paper:Smith2024` and `cite:Smith2024` share
the bibkey `Smith2024`, but `paper:smith2024` is a different key.

`article` remains a live entity kind for article records, but
`article:<bibkey>` is not the external-literature ref prefix. Use
`paper:<bibkey>` for literature notes and `cite:<bibkey>` for bibliography
references.

`papers/references.bib` is an external-reference authority, not an entity owner
store. It can synthesize lightweight paper or book records so `paper:` and
`cite:` references resolve and minimal bibliography metadata can materialize,
but it does not claim ownership over a project-authored literature note.
For app-facing citation rendering, Science exports a separate
`science.references` bundle from the same bibliography authority. See
[Citations And Reference Bundles](https://github.com/khughitt/science/blob/main/docs/conventions/citations-and-references.md)
for the normalized record shape, citation grammar, and Labnote package contract.

CURIE-backed external references live in
`knowledge/sources/<profile>/external_refs.yaml`:

```yaml
references:
  - id: "gene:PHF19"
    title: "PHF19"
    primary_external_id:
      source: "HGNC"
      id: "HGNC:18350"
      curie: "hgnc:18350"
      provenance: "manual-curation"
```

Rows in this file are external references. They provide a durable authority for
ontology or catalog identifiers and can materialize exact-match links, but they
do not replace a project owner file when the project has one.

## Entity Owner Files

Author durable entities as owner files under `entities/`, keep external
authority rows in `external_refs.yaml`, and keep generated graph output out of
source ownership. Do not create aggregate entity manifests such as
`knowledge/sources/<profile>/entities.yaml`, `terms.yaml`, or retired per-kind
doc-tree manifests. Use owner files under `entities/<kind>/`; use
`overlays/<type>/` only for borrower files with `overlay_of:`.

Decision owners are authoritative after promotion. Render the derived decision
log view with:

```bash
science entities generate-decisions --project-root <project> --write
```

## Compositional Research Outputs

Science keeps epistemic content in source-authored entities, then lets higher
level records assemble those entities into narratives:

| Layer | Current durable surface |
|---|---|
| `proposition` | A truth-apt assertion that can receive support, dispute, verdict, and belief summaries. |
| `observation` | A concrete empirical fact or recorded datum, usually grounded by a workflow run or dataset. |
| `finding` | A unit of learned knowledge: propositions grounded by observations from an analysis. |
| `interpretation` | One analysis session's narrative and findings, authored under `entities/interpretations/`. |
| `story` | A coherent narrative arc synthesizing interpretations around a question or hypothesis. |
| `synthesis` / `report` | Durable rollups and written reports over project knowledge. |

Prefer source-authored Markdown owners for durable project knowledge. `finding`,
`interpretation`, and `story` have packaged templates; create story scaffolds
with `science entity create story <title>` when a project uses that narrative
layer. Use `related:`, `source_refs:`, and structured relation fields to
connect the chain rather than hand-editing generated graph state.

For proposition bundle membership, prefer `discusses:` on proposition sources or
`knowledge/sources/local/relations.yaml` entries with
`predicate: cito:discusses` and `role: core|rival|background`. The `role:` field
is valid only for proposition-to-live-hypothesis/mechanism membership edges. See
[Bundle Membership Roles](epistemic-model.md#bundle-membership-roles).

Author mechanisms as `entities/mechanisms/<slug>.md` with at least two
participants and proposition refs for the mechanism steps, then run
`science graph build`. `science graph add mechanism` is retired.

The old graph-only composition writers for finding, mechanism, story, and paper
are retired; use source-authored entity files. Author story synthesis with
`science entity create story <title>` plus relations such as `sci:synthesizes`
and `sci:organizedBy` in `relations.yaml`. The current loadable `paper` kind is
an external literature note; create DOI-backed notes with
`science entity create paper <title> --id <citekey>` or by editing
`entities/papers/<citekey>.md` with a `doi:` field; do not use `paper:<id>` for
the project's own publication draft.

### Explore-Ideas Lens Views

Exploration-discovered entities can carry `origins`, `lens_views`, and
`added_by` metadata. These fields record how an idea entered the project; they
do not count as evidence and do not update belief by themselves.

When two or more idea lenses independently converge on the same candidate,
represent that convergence as one entity with multiple `lens_views`, not as
multiple duplicate entities. The entity should have one `origins` entry per
contributing lens and one `lens_views` entry per lens-specific framing:

```yaml
origins:
  - type: assistant
    ref: explore-ideas-mechanism
    independent: true
  - type: assistant
    ref: explore-ideas-analogy
    independent: true
lens_views:
  - lens: mechanism
    rationale: Mechanism-first framing.
    origin_ref: explore-ideas-mechanism
  - lens: analogy
    rationale: Cross-domain analogy framing.
    origin_ref: explore-ideas-analogy
added_by: explore-ideas:gpt-5:cand-hspc-trained-immunity
```

Each `origin_ref` must match one of the entity's own non-null origin refs. Do
not create duplicate question or hypothesis entities merely to preserve each
lens; keep the entity singular and preserve the independent lens framings in
`lens_views`.

### Autonomous Run Provenance

An entity written by an unattended agent run carries `autonomous_run`, a
reference to a record in `runs/`:

```yaml
autonomous_run: run:2026-07-24-curation-sweep-a3f1
```

This answers a different question from `added_by`. `added_by` records how an
*idea* entered the project and legitimately holds values like `user` that no
run could explain; `autonomous_run` records which *execution* wrote the file.
Neither counts as evidence, and neither updates belief.

It is also distinct from an evidence line's `run_refs`, which names
fingerprinted workflow runs and *does* bear on belief. A dangling
`autonomous_run` — one naming a run with no record in `runs/` — is reported by
`science refs check`. The graph build also fails on it.

The field is a scalar and is overwritten, so it names the **last** run that
wrote the file. Full attribution history lives in git, under each run
record's `base_commit..head_commit` range.

## Entity Classes

Science groups core entity kinds into three classes.

### Epistemic

Epistemic entities carry, organize, or evaluate uncertain knowledge.

<!-- entity-kinds:epistemic:start -->
- `assumption` - An explicit assumption underpinning a model, analysis, or argument.
- `chain-audit` - Verdict over a structural-chain. Carries verdict+bayes_factor_evidence with enforced consistency.
- `discussion` - Structured critical discussion of a hypothesis, question, or topic.
- `evidence-line` - A single, independence-tagged line of evidence that supports or disputes a proposition.
- `falsification` - A structured record that a proposition-backed prediction was falsified.
- `finding` - Unit of learned knowledge: propositions grounded by observations from an analysis.
- `hypothesis` - Testable project hypothesis; see bundle belief and membership roles in `epistemic-model.md`.
- `inquiry` - A scoped research inquiry (boundary + estimand over the knowledge graph).
- `interpretation` - One analysis session's narrative and its findings.
- `mechanism` - Named explanatory structure linking multiple typed entities and propositions; `hasProposition` steps are core bundle members.
- `observation` - Concrete empirical fact anchored to specific data.
- `patch-definition` - Authored patch profile asserting a belief membership over the graph.
- `proposition` - Truth-apt statement - the fundamental epistemic unit; can enter hypothesis/mechanism bundles as `core`, `rival`, or `background`.
- `question` - Open or resolved project question.
- `report` - Standalone written report over project knowledge.
- `research-question` - The project's single guiding research question.
- `story` - Coherent narrative arc synthesizing interpretations around a question or hypothesis.
- `structural-chain` - Ordered structural decomposition: >=2 entity refs forming a chain whose verdicts are carried by chain-audit.
- `synthesis` - Cross-cutting synthesis rolling up interpretations and findings.
- `theme` - Durable cross-cutting organizing frame linking project questions, hypotheses, tasks, reports, concepts, and guardrails.
- `validation-report` - Report validating an analysis, model, or pipeline result.
<!-- entity-kinds:epistemic:end -->

### Operational

Operational entities describe work products, sources, runs, plans, datasets, and
project machinery.

<!-- entity-kinds:operational:start -->
- `book` - Long-form monograph summarized chapter-by-chapter; an evidence source.
- `claim-registry` - The project's single registry of tracked external claims.
- `code-file` - Source-code file implementing workflow steps and methods.
- `curation-sweep` - A project-memory curation sweep tracked as an operational artifact.
- `data-package` - Frictionless research package containing analysis results, prose, and provenance metadata.
- `dataset` - Tabular or file dataset tracked as a research artifact.
- `experiment` - Experiment or analysis step that tests project questions.
- `method` - Analytical method or computational approach.
- `paper` - External literature note for a read, searched, or summarized paper.
- `plan` - An authored implementation or analysis plan.
- `pre-registration` - Pre-registered analysis plan stating expectations before analysis.
- `prose-source` - Authored internal Markdown prose used as an operational evidence source; see prose-derived reports in [Graph And Derived State](graph-and-derived-state.md).
- `research-package` - Composed research package bundling analysis results and provenance.
- `search` - A literature or dataset search and its recorded results.
- `spec` - A design or implementation specification.
- `talk` - Recorded seminar or conference presentation; an unrefereed evidence source.
- `task` - Operational project task tracked in the graph.
- `transformation` - A data transformation applied within an analysis.
- `workflow` - Reusable pipeline definition (Snakefile + config + rules).
- `workflow-run` - Concrete execution of a workflow producing durable outputs.
- `workflow-step` - Individual step within a workflow definition.
<!-- entity-kinds:operational:end -->

### Reference

Reference entities name concepts, variables, outcomes, sources, decisions, and
other stable objects that the project points at.

<!-- entity-kinds:reference:start -->
- `article` - External article or document referenced as a source.
- `concept` - A named concept referenced across the project.
- `construct` - A theoretical construct operationalized by the project.
- `decision` - A recorded project decision with rationale.
- `outcome` - A measured or targeted outcome variable.
- `topic` - Legacy research-topic synthesis note; prefer typed semantic entities for new work.
- `unknown` - Built-in sentinel kind for unrecognized entities.
- `variable` - A modeled variable in an analysis or causal model.
<!-- entity-kinds:reference:end -->
