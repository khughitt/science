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

## Authored And Derived Fields

Authored fields are recorded directly in source files. Derived fields are
computed from the graph, evidence, provenance, or health machinery. Belief
state, support summaries, dispute summaries, freshness, and health status should
be recomputed rather than manually patched.

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
Science registers core kinds itself. Active profiles, local manifests, and
declared ontology catalogs register additional loadable kinds. Duplicate
registrations and attempts to shadow core kinds are hard errors; unknown kinds
are skipped with an explicit diagnostic instead of being silently treated as a
different entity type.

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
- `topic` - A research topic synthesized from the literature.
- `unknown` - Built-in sentinel kind for unrecognized entities.
- `variable` - A modeled variable in an analysis or causal model.
<!-- entity-kinds:reference:end -->
