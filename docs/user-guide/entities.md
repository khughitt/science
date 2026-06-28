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

Storage adapters own discovery and parsing only. They discover project-relative
source locations, load a raw record with `kind` and identity fields, and pass
that record to the registry. They do not decide dataset semantics, task state,
or domain-entity validity. Those rules live on the resolved entity schema and
on validation checks.

Current project source loading uses these adapter families:

| Adapter | Source surface | Role |
|---|---|---|
| `markdown` | `entities/**/*.md` and `research/packages/**/*.md` | Normal single-entity authoring surface with YAML frontmatter and body prose. |
| `aggregate` | `knowledge/sources/<profile>/entities.yaml`, `terms.yaml`, and selected `doc/<plural>/<plural>.{json,yaml}` files | Transitional multi-entity rows and single-type aggregate rows. Prefer Markdown owners for new durable entities. |
| `bib` and `curie-ref` | bibliography and ontology reference inputs | External-reference rows that defer to an existing entity owner when one exists. |
| `datapackage` | `data/**/datapackage.yaml` and `results/**/datapackage.yaml` with `science-pkg-entity-1.0` | Dataset entity records embedded in promoted runtime packages; if a Markdown owner already exists, the datapackage defers but remains available as resource metadata. |
| `workflow-run`, `task`, and `code` | workflow run files, task sources, and configured code roots | Specialized storage formats that materialize first-class entities into the same registry flow. |
| `commons-merged` and `overlay` | shared/commons entities and local overlays | Cross-project entity owners and borrower overlays loaded into the same identity table. |

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

The old graph-only composition commands (`science graph add finding`,
`science graph add story`, and `science graph add paper`) are exploratory
helpers that write directly to `knowledge/graph.trig`. Those graph edits are
overwritten by `science graph build`. The current loadable `paper` kind is an
external literature note; do not use `paper:<id>` for the project's own
publication draft.

## Dataset Lifecycle

`dataset` is the single entity kind for data that a project consumes, whether
the data comes from an external source or from a workflow run. Dataset owners
live under `entities/datasets/` in layout v3 projects. The entity frontmatter is
the authority for project-level metadata; a runtime `datapackage.yaml` or
`datapackage.json` is the authority for resource-level file metadata.

The split is intentional:

| Surface | Owns |
|---|---|
| Dataset entity | `id`, `type`, `title`, `status`, `origin`, `dataset_class`, `tier`, `license`, `update_cadence`, `ontology_terms`, `access`, `derivation`, lineage, `consumed_by`, and human prose. |
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
- `hypothesis` - Testable project hypothesis.
- `inquiry` - A scoped research inquiry (boundary + estimand over the knowledge graph).
- `interpretation` - One analysis session's narrative and its findings.
- `mechanism` - Named explanatory structure linking multiple typed entities and propositions.
- `observation` - Concrete empirical fact anchored to specific data.
- `patch-definition` - Authored patch profile asserting a belief membership over the graph.
- `proposition` - Truth-apt statement - the fundamental epistemic unit.
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
- `prose-source` - Authored internal Markdown prose used as an operational evidence source.
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
