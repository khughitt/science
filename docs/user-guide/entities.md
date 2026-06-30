# Entities

An entity is a durable typed record in a Science project. Most entities are
Markdown files with YAML frontmatter and body prose. The frontmatter provides
machine-readable identity and relationships; the body provides human-readable
context.

## Entity Shape

```markdown
---
id: proposition:example
type: proposition
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
| `type` | Entity kind. Usually matches the prefix in `id`. |
| `title` | Human-readable title. |
| `status` | Lifecycle state for the kind. |
| `related` | Other entity refs connected to this record. |
| `source_refs` | Sources or annotations that support the existence or content of this record. |
| Body prose | Explanation, caveats, rationale, and review context. |

`kind` is the authoritative load-time discriminator. Markdown frontmatter may
use the legacy `type:` field; storage adapters normalize it to `kind` before
registry dispatch. Core Science kinds also carry a `type` projection internally,
but catalog, profile, and project-extension kinds load as open-ended strings
rather than being forced through a closed enum or an `unknown` fallback. Kind
matching is exact after adapter normalization.

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
| `science entity sections <kind>` | Inspect template section keys for kinds backed by packaged templates. |
| `science entity neighbors <ref>` | Query graph neighbors from the materialized graph. This may warn when source files are newer than `knowledge/graph.trig`. |

Typed wrappers call the same writer and validation path as `science entity`.
Use them when they add kind-specific ergonomics:

| Wrapper | Notes |
|---|---|
| `science questions create` | Source-authored questions. |
| `science hypotheses create` | Supports `--phase candidate` to include promotion criteria. |
| `science discussions create` | `--focus <ref>` is stored as a related reference. |
| `science interpretations create` | `--input <ref-or-path>` is stored as a source reference. |
| `science propositions create` | Durable proposition sources; prefer this over throwaway `graph add proposition` for project work. |
| `science evidence-lines create` | Durable support/dispute evidence line sources. |

### CLI Path And Identity Policy

The source entity CLI creates only kinds that have a built-in Markdown path
policy. Current owners live under `entities/` according to the core profile, for
example `entities/questions/`, `entities/hypotheses/`,
`entities/propositions/`, `entities/evidence-lines/`, and
`entities/interpretations/`. The `doc/` tree is prose-only in layout v3, and
`knowledge/` is generated state.

By default, filenames follow the entity id local part. Numeric kinds generate a
four-digit local part plus slug, such as `question:0001-observed-signal`.
Slug and id-local kinds use a deterministic kebab-case slug. Citekey and
verbatim kinds require an explicit `--id`, and singleton kinds are not created
through this path. Use `--slug` to override only the generated slug component,
or `--id` to set the complete canonical id; do not pass both.

`--path` is intentionally narrow: it must be a project-relative `.md` path under
`entities/`, must not be absolute, and must not contain `..`. It is for unusual
source placement inside the owner tree, not for writing entity owners into
`doc/`, `specs/`, overlays, or generated graph files.

References accepted by `show`, `edit`, `note`, and `neighbors` are exact
canonical ids or unambiguous local shorthands. Registered shortforms such as
`q1`, `h1`, `p1`, `i1`, `d1`, and `t1` resolve to the corresponding core kind
when they identify exactly one loaded source record.

### Source Write Boundary

`science graph add ...` remains available for graph-level experiments and
legacy workflows, but it is not the durable source-authoring surface. For
project knowledge that should survive `science graph build`, create or edit the
source entity file. The graph build step materializes those source records into
`knowledge/graph.trig`; direct graph mutations are overwritten by the next
materialization.

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
| `on_owner_declared(...)` | Captures row-level metadata, currently used by aggregate rows for triage and migration reports. |
| `deferred_dataset_datapackage(...)` | Lets a deferring datapackage keep package-resource metadata available after a Markdown or aggregate owner wins. |

This policy surface keeps adapter quirks close to the adapter. For example,
bibliography and CURIE-reference adapters act as external references and defer
to existing owners; datapackage records are owner-shaped but defer when a
project source already owns the dataset id; aggregate rows emit row metadata for
retirement triage; Markdown records are the only records that capture a source
document body.

Current project source loading uses these adapter families:

| Adapter | Source surface | Role |
|---|---|---|
| `markdown` | `entities/**/*.md` and `research/packages/**/*.md` | Normal single-entity authoring surface with YAML frontmatter and body prose. |
| `aggregate` | `knowledge/sources/<profile>/entities.yaml`, `terms.yaml`, and selected `doc/<plural>/<plural>.{json,yaml}` files | Transitional multi-entity rows and single-type aggregate rows. Prefer Markdown owners for new durable entities. |
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
ambiguous references without running the materialize-only project-root preflight,
without deriving graph layers, and without writing `knowledge/graph.trig`.
`science graph build` runs the full sequence and hard-gates on audit failures
before emitting or writing the graph. The materialize-only preflight still blocks
strict builds on legacy unmigrated data-package owners; it is intentionally
outside the audit-only path.

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
process in [Adding a Domain](../process/adding-a-domain.md).

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
| Stable project-local concept | `concept`, often as a lightweight row in `knowledge/sources/<profile>/terms.yaml`. |
| Cross-cutting organizing lens | `theme`. |
| Conjecture under investigation | `hypothesis`. |
| Analysis-session narrative | `interpretation`. |
| Communication-layer synthesis | `story`. |
| Named explanatory bundle with participants and claims | `mechanism`. |
| Temporary classification marker | Field-scoped `tag:*`, only where free-form labels are accepted. |
| Operational marker | `meta:*`, or prose when it should not enter the graph. |

`terms.yaml` is for lightweight semantic rows that are more durable than a
one-off prose label but do not yet deserve a full Markdown owner:

```yaml
terms:
  - id: "concept:treatment-response"
    title: "Treatment response"
  - id: "method:cox-regression"
    title: "Cox proportional-hazards regression"
    ontology_terms: ["biolink:StatisticalMethod"]
```

Keep entries minimal: `id` and `title` are required; `aliases`, `same_as`,
`ontology_terms`, and short descriptions are optional. Promote the row to a
Markdown entity owner when it accumulates body prose, structured relations, or
lifecycle work.

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

Legacy `article:<bibkey>` references are accepted only as a transition-window
alias for `paper:<bibkey>` at load and comparison boundaries. New authored
files should use `paper:<bibkey>`. Health checks still surface legacy
structured `article:` references so projects can remove them from source before
the alias is retired. See [Refs Check](../conventions/refs-check.md) for the
reference-checking and alias-retirement policy.

`papers/references.bib` is an external-reference authority, not an entity owner
store. It can synthesize lightweight paper or book records so `paper:` and
`cite:` references resolve and minimal bibliography metadata can materialize,
but it does not claim ownership over a project-authored literature note.
For app-facing citation rendering, Science exports a separate
`science.references` bundle from the same bibliography authority. See
[Citations And Reference Bundles](../conventions/citations-and-references.md)
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

## Aggregate Retirement

Some older projects still contain aggregate entity rows in
`knowledge/sources/<profile>/entities.yaml`, `terms.yaml`, or single-type files
such as `doc/observations/observations.yaml`. These are transitional source
surfaces. New durable entities should be authored as owner files under
`entities/`.

Use `science entities triage-aggregate` to inventory aggregate rows:

```bash
science entities triage-aggregate --project-root <project>
science entities triage-aggregate --project-root <project> --format json
```

The read-only report buckets rows by the compiled source model:

| Bucket | Meaning |
|---|---|
| `shadow` | A non-aggregate owner for the same id already exists. |
| `coined` | The row can promote to a first-class owner file. |
| `decision-log` | The row is backed by a `core/decisions.md` decision section. |
| `external-ref` | The row is backed by bibliography authority. |
| `curie-external-ref` | The row has `primary_external_id` and can move to `external_refs.yaml`. |
| `cruft` | An unreferenced migration artifact row. |
| `referenced-orphan` | A migration artifact row still referenced by live entities. |
| `question-deferred` | A question stub that needs epistemic authoring. |
| `ambiguous` | A row that still needs a human identity decision. |

Mutation requires `--apply` plus explicit bucket flags, and only runs for
layout-version 3 projects:

```bash
science entities triage-aggregate --project-root <project> --promote-coined --apply
science entities triage-aggregate --project-root <project> --promote-decisions --apply
science entities triage-aggregate --project-root <project> --retire-external-refs --apply
science entities triage-aggregate --project-root <project> --migrate-curie-refs --apply
science entities triage-aggregate --project-root <project> --delete-shadow --delete-cruft --apply
```

Promotion is id-preserving and path-policy aware. A non-conforming or unsafe id
is rejected rather than silently renamed. Shadow deletion is safe only when a
real owner exists. Referenced or ambiguous rows stay for human triage.

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

Prefer source-authored Markdown owners for durable project knowledge. `finding`
and `interpretation` have packaged templates; `story` can be authored as an
entity when a project uses that narrative layer. Use `related:`,
`source_refs:`, and structured relation fields to connect the chain rather than
hand-editing generated graph state.

For proposition bundle membership, prefer `discusses:` on proposition sources or
`knowledge/sources/local/relations.yaml` entries with
`predicate: cito:discusses` and `role: core|rival|background`. The `role:` field
is valid only for proposition-to-live-hypothesis/mechanism membership edges. See
[Bundle Membership Roles](epistemic-model.md#bundle-membership-roles).

The old graph-only composition commands (`science graph add finding`,
`science graph add story`, and `science graph add paper`) are exploratory
helpers that write directly to `knowledge/graph.trig`. Those graph edits are
overwritten by `science graph build`. The current loadable `paper` kind is an
external literature note; do not use `paper:<id>` for the project's own
publication draft.

## Paper Dataset Usage

Papers should express dataset dependence with `dataset_usage` entries. The
legacy paper `datasets` field is still read as a transition input, but it only
means `role: analyzed` with `overlap: unknown`.

Use the migration command to inspect or apply lossless rewrites:

```bash
science graph migrate-paper-datasets --project-root . --format table
science graph migrate-paper-datasets --project-root . --format json
science graph migrate-paper-datasets --project-root . --apply
```

Dry-run is the default. It exits `10` when safe rewrites are pending and `20`
when conflicts need manual review. `--apply` rewrites only papers whose
`datasets` refs can be represented exactly as canonical `dataset_usage` entries.

## Gene-Set Collections And Members

Gene-set collections are normal `dataset` entities with the
`bio.geneset/1.0` extension. The collection frontmatter declares the member row
resource, row counts, set-size summary, and the `identifier_space` used by the
member identifiers. The member table is keyed by `set_key` and may carry
per-set `dataset_usage`, source PMIDs, and source-class overrides.

Most sets stay as rows in the collection. Promote an individual set only when it
needs its own evidence-bearing reference, independent provenance, or review
state. A promoted set is a child `dataset` with
`bio.geneset.member/1.0`, `origin: derived`, `datapackage: virtual:member-of`,
and `derivation.kind: member_of` pointing back to the parent collection:

```yaml
schema_profile: science-entity-base/1.0+dataset/1.0+bio.geneset.member/1.0
id: dataset:reactome-r-hsa-1
type: dataset
origin: derived
source_class: reference
parent_dataset: dataset:reactome-v89
datapackage: virtual:member-of
derivation:
  kind: member_of
  parent_dataset: dataset:reactome-v89
  member_key: R-HSA-1
identifier_space:
  tier: gene
  namespace: hgnc_id
n_members: 42
```

The virtual payload resolver slices the parent collection's `members_resource`
by `derivation.member_key` and returns that row plus the collection's
`identifier_space`. No tiny per-set data artifact is required unless a workflow
explicitly materializes one.

Use `science commons member-payload dataset:<member> --json` to inspect the
resolved virtual payload for a promoted member dataset. The command uses the
shared `member_of` dispatcher and supports both `bio.geneset.member` and
`bio.reference_graph.member` datasets.

For reference graphs, use
`science commons reference-graph scaffold-member <parent_dataset> <member_key> --slug <slug>`
to preview a promoted `bio.reference_graph.member` child dataset. Dry-run is
the default; add `--apply` to write the child `entity.md` plus the virtual
`datapackage.yaml` sibling.

Use `science commons reference-graph resolve-member <registry_id> <member_key> --json`
to resolve an exact graph member key from a pinned reference graph node index.
Deprecated or withdrawn members are returned with lifecycle state and
`replaced_by`; replacements are not followed automatically.

## Dataset Lifecycle

`dataset` is the single entity kind for data that a project consumes, whether
the data comes from an external source or from a workflow run. Dataset owners
live under `entities/datasets/` in layout v3 projects. The entity frontmatter is
the authority for project-level metadata; a runtime `datapackage.yaml` or
`datapackage.json` is the authority for resource-level file metadata.

The split is intentional:

| Surface | Owns |
|---|---|
| Dataset entity | `id`, `type`, `title`, `status`, `origin`, `dataset_class`, `tier`, `license`, `update_cadence`, `ontology_terms`, `access`, `derivation`, lineage, `qa_report`, `consumed_by`, and human prose. |
| Runtime datapackage | Resource names, paths, hashes, byte counts, formats, schemas, and other file-level package details. |

Dataset entities use `profiles: ["science-pkg-entity-1.0"]`. Do not put
`resources:` on the entity; consumers that need resource details read the file
named by `datapackage:`.

### Origin

Every dataset has an `origin`:

- `external` means the dataset comes from a paper, public repository, portal,
  controlled-access archive, commercial source, or another source outside the
  local workflow run.
- `derived` means the dataset is a logical output of a recorded workflow run.

External datasets carry an `access:` block. Derived datasets carry a
`derivation:` block. Do not mix the two on one entity.

### Dataset Class

`dataset_class` describes how the record can be used:

| Class | Meaning |
|---|---|
| `deposit` | Obtainable data that can be staged as a local runtime artifact. |
| `reference` | A portal, registry, atlas, leaderboard, or other lookup source that should be tracked but normally has no local runtime artifact. |
| `pointer` | A record worth tracking for planning or discovery, but not directly usable as staged data yet. |

`dataset_class` is independent from `source_class`. A reference genome can be a
downloadable `deposit`; a web portal can be a `reference`.

### External Datasets

Create new external candidates with:

```bash
science dataset add <slug> --title "<title>"
```

`science dataset add` writes a local `entities/datasets/<slug>.md` candidate
with `origin: external`, `dataset_class: deposit` by default, `license:
unknown`, and an unverified `access:` block. Use `--class reference` or
`--class pointer` when the record is not a staged-data deposit. Reference and
pointer records need an `access.source_url`.

When access has been checked, record the whole coupled edit with:

```bash
science dataset verify-access <slug> --license <spdx-or-sentinel> --method <method>
```

For deposits, valid verification methods are `retrieved` and
`credential-confirmed`. For reference records, use `credential-confirmed`,
`landing-confirmed`, or `metadata-confirmed`. For pointer records, use
`landing-confirmed` or `metadata-confirmed`.

If an external dataset cannot be used as originally scoped, record a structured
exception instead of leaving `access.verified: false` unexplained:

```bash
science dataset verify-access <slug> --license <spdx-or-sentinel> \
  --exception scope-reduced --rationale "<why>"
```

Exception modes are `scope-reduced`, `expanded-to-acquire`, and `substituted`.
The command updates the frontmatter and appends a dated entry under
`## Access verification log`.

### Derived Datasets

Derived dataset entities are machine-authored from workflow runs. A workflow
declares logical outputs in `entities/workflows/<slug>.md`:

```yaml
outputs:
  - slug: "<output-slug>"
    title: "<Output title>"
    resource_names: ["<frictionless-resource-name>"]
    ontology_terms: []
```

A completed workflow run lives under `entities/workflow-runs/` and lists its
upstream dataset inputs. After the run writes its aggregate runtime
datapackage, register the derived outputs with:

```bash
science dataset register-run workflow-run:<slug>
```

Registration writes one per-output `datapackage.yaml` under the run results
tree, creates one `origin: derived` dataset entity per declared workflow output,
and updates symmetric edges:

- the workflow run's `produces:` lists each derived dataset;
- each upstream dataset's `consumed_by:` includes the workflow run.

Per-output datapackages are views into the run output, not relocated copies of
the resources.

### Runtime State And Inspection

Use the singular `science dataset` command group for the catalog lifecycle:

```bash
science dataset list
science dataset list --origin external --unverified
science dataset list --include-gated
science dataset show <slug>
science dataset consumers <slug>
science dataset prioritize --explain
science dataset reconcile <slug>
```

`science dataset list` hides gated external deposits by default; pass
`--include-gated` or a specific `--level` to inspect them. `science dataset
prioritize` ranks records by accessibility, runtime state, and graph reach. It
excludes gated deposits, references, and pointers by default so the first view is
actionable.

Runtime state is derived from the entity:

| State | Meaning |
|---|---|
| `runnable` | A `datapackage` or `local_path` is present. |
| `unstaged-deposit` | Access is verified but a deposit has not been staged yet. |
| `blocked-access` | Access is gated, unverified, or exception-gated. |
| `reference-only` | The record is a reference-class dataset. |
| `pointer-only` | The record is a pointer-class dataset. |

### Prioritization And Reach

`science dataset prioritize` ranks local dataset records as:

```text
readiness_weight * (1 + reach) * leverage_tilt
```

Readiness comes from the dataset entity's access, origin, derivation, and
runtime pointer state. Reach is the number of question or hypothesis targets the
dataset connects to. Leverage tilt is available when a fresh graph is loaded and
uses proposition summary signals such as contested, single-source, no-empirical,
and risk score.

Reach is intentionally authorable without a graph, then enriched by the graph:

| Surface | Meaning for reach |
|---|---|
| Dataset `related:` | Dataset lists a `question:*` or `hypothesis:*` it informs. |
| Q/H `related:` | A question or hypothesis lists a `dataset:*` back-edge. |
| Q/H `datasets:` | A question or hypothesis directly names needed or relevant datasets. |
| Consumer `dataset_usage` plus `related:` | A paper or other consumer names datasets and is related to Q/H records. |
| Evidence-line `dataset_usage` plus proposition reach | An evidence line uses a dataset and supports/disputes a proposition that reaches Q/H records. |

These paths are a union. Do not duplicate edges only to satisfy prioritization:
use Q/H `datasets:` for direct dataset needs, dataset `related:` when the
dataset file is the active editing surface, and `dataset_usage` where a paper,
evidence line, workflow-derived row, or virtual row records actual use.

`science dataset prioritize --coverage --format json` inverts the view to one
row per question or hypothesis. Coverage states are `covered-runnable`,
`covered-unstaged`, `covered-reference`, `covered-pointer`, `blocked-access`,
`unverified`, and `no-candidate`. Gap reasons include `unstaged-deposit`,
`only-reference`, `only-pointer`, `only-gated`, `only-unverified`, and
`no-candidate`.

Treat a flood of `no-candidate` rows as a curation-design signal, not only as a
filtering problem. Especially when the missing rows are internal,
methodological, or too abstract for dataset discovery, the likely follow-up is
to reformulate the upstream question or hypothesis into dataset-addressable
needs before tuning the scan output.

### Typed Resource Schemas

Runtime datapackages can give each tabular resource a typed Frictionless Table
Schema. Science treats that schema as the single source of truth for resource
shape and machine-checkable QA inputs:

```yaml
resources:
  - name: observations
    path: observations.parquet
    schema:
      fields:
        - name: sample_id
          type: string
          constraints: {required: true, unique: true}
        - name: value
          type: number
          constraints: {minimum: 0}
          qa: {low_variance: true, zero_fraction: true}
      primaryKey: sample_id
      missingValues: ["", "NA"]
      qa:
        exclusive_flags: [[case, control]]
```

Native Table Schema declarations are invariants: field `type`,
`constraints.required`, `constraints.unique`, `primaryKey`, `uniqueKeys`,
`foreignKeys`, bounds, enums, and `missingValues` describe data that must be
true. The Science `qa:` extension is deliberately small and distribution
oriented: field-level `low_variance` and `zero_fraction`, plus table-level
`exclusive_flags`.

The schema profile is model-owned in `science_tool.datasets.schema`; the
committed JSON Schema is generated from those Pydantic models rather than
hand-maintained. `science datasets validate --path <datapackage>` checks a
descriptor or package directory through that profile, confirms resource files
exist, and checks declared tabular `schema.fields[]` against the observed table
names and coarse types. A descriptor that is missing, malformed, empty, stale,
or points at absent data fails early instead of warning-and-passing.

Use `science datasets infer-schema` to bootstrap the names-and-types portion of
a resource schema from an existing table:

```bash
science datasets infer-schema <datapackage-dir-or-file> --resource <name>
science datasets infer-schema <datapackage-dir-or-file> --resource <name> --write
science datasets infer-schema <datapackage-dir-or-file> --resource <name> --emit-suggestions suggestions.yaml
science datasets infer-schema <datapackage-dir-or-file> --resource <name> --format json
```

The command is read-only by default. It resolves resources by name first and by
path second, refuses ambiguous matches, reads Parquet types from Arrow metadata,
and samples CSV/TSV resources for coarse type inference. With `--write`, it
applies only safe `fields[].name` and `fields[].type` edits, preserves authored
constraints and QA metadata, refuses authored type conflicts, validates the
whole package before writing, and atomically re-renders the descriptor in its
own JSON/YAML format. It never writes constraints, keys, foreign keys, or
`qa:` declarations; those appear only as human review recommendations.

### Dataset QA

Use the plural `science datasets qa` command for package-level, schema-driven
QA over tabular resources:

```bash
science datasets qa <datapackage-dir-or-file>
science datasets qa <datapackage-dir-or-file> --resource <name>
science datasets qa <datapackage-dir-or-file> --report-dir <dir>
science datasets qa <datapackage-dir-or-file> --config <runknobs.yaml>
science datasets qa <datapackage-dir-or-file> --format json
science datasets qa <datapackage-dir-or-file> --no-strict
```

The command accepts a package directory or a descriptor named
`datapackage.json`, `datapackage.yaml`, or `datapackage.yml`. With
`--report-dir`, it persists `qa_report.json`, `qa_report.md`, and per-resource
report subdirectories. Text output renders one non-`not-applicable` resource
line followed by a package summary. Resource outcomes are `ok`, `fail`,
`blocked`, `skipped`, or `not-applicable`: non-tabular resources are
not-applicable, tabular resources without schemas are skipped, missing data
files are blocked, and evaluated resources fail when any structural QA flag is
emitted.

The QA runner compiles each resource's typed schema into the generic `tabular`
program unless run-knobs select another program. Schema-derived invariants
compile to structural checks: required fields, unique keys, expected types,
hard bounds, enums, missing sentinels, and single-column foreign-key
categoricals. Composite foreign keys are rejected rather than weakened to
per-column checks. A run-knobs file passed with `--config` overlays operational
settings such as soft ranges, polarity, project-local checks, aspect
parameters, and program choice; contract fields are merged with schema-derived
values so authors can tighten a specific run without forking the descriptor.

Exit codes are:

| Code | Meaning |
|---|---|
| `0` | No build-fatal structural package failure, or `--no-strict` was used for local inspection. |
| `1` | A structural package failure fired and strict mode is active. |
| `2` | Bad input, such as missing descriptor, unknown resource, unreadable data, or compile/runner error. |

To feed QA into graph and belief behavior, set a dataset entity's `qa_report` to
the project-root-relative path of the persisted `qa_report.json`. Graph build
does not rerun QA. It reads each opted-in report, requires
`package_structural_failed` to be a JSON boolean, hashes the report, and emits:

- `sci:qaStructuralFailed`
- `sci:qaReport`
- `sci:qaReportHash`
- `sci:qaFailedResource` for failed resources

For empirical evidence lines that rest on structurally failed dependence
datasets, graph build also emits `sci:qaFailedDataset`. Belief aggregation uses
that provenance to apply the QA dataset ceiling; QA-clean support can still
carry the belief if it is sufficient without the failed dataset.

### Sub-Cohort Lineage

Datasets can declare cohort lineage with `parent_dataset` and optional
`siblings`. Graph build materializes `parent_dataset` as a child-to-parent
`sci:subCohortOf` edge. Dataset-derived independence uses that lineage when
deciding whether two empirical evidence lines are truly independent.

When two full-overlap dependence uses refer to the same dataset or an
ancestor/descendant pair in the same lineage, Science emits a commitment:
`DatasetIndependenceCommitment`, `shared-source`, and a
`dataset-derived:*` independence group. Sibling sub-cohorts under the same root
are not committed as the same source; they remain candidate warnings because
they may overlap but are not guaranteed to be duplicate evidence. Partial,
unknown, validation-only, citation-only, indirect, and virtual-row paths also
stay candidate-level.

`science dataset reconcile` checks the narrow duplication channel between the
entity and runtime package: `license`, `update_cadence`, and
`ontology_terms`. Per-resource fields are not reconciled because they belong to
the runtime package only.

### Validation Expectations

Validation checks dataset metadata without assuming perfect input. The current
checks warn on missing or unrecognized licenses, tiers, cadence values, dataset
classes, incompatible verification methods, and reference/pointer records that
claim runtime artifacts. Lineage validation checks `parent_dataset` references
and cycles. Promotion checks enforce the extra requirements needed before a
dataset can move into the commons.

## Entity Classes

Science groups core entity kinds into three classes.

### Epistemic

Epistemic entities carry, organize, or evaluate uncertain knowledge.

<!-- entity-kinds:epistemic:start -->
- `assumption` - An explicit assumption underpinning a model, analysis, or argument.
- `chain-audit` - Verdict over a structural-chain. Carries verdict+bayes_factor_evidence with enforced consistency.
- `discussion` - Structured critical discussion of a hypothesis, question, or topic.
- `evidence-line` - A single, independence-tagged line of evidence that supports or disputes a proposition.
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
- `workflow-step` - Individual step within a workflow definition or run.
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
