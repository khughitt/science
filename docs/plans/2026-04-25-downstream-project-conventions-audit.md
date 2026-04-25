# Downstream Project Conventions Audit Plan

**Goal:** Audit mature downstream Science projects to identify where real project practice has drifted from, extended, or clarified Science's current project model.

**Scope:** This audit focuses only on downstream projects:

- `/home/keith/d/natural-systems`
- `/home/keith/d/r/mm30`
- `/home/keith/d/protein-landscape`
- `/home/keith/d/r/cbioportal`

Do not audit the Science repository's own templates, fixtures, or command docs in this pass except when a downstream observation needs a concise upstream implication note.

**Approach:** Use a thin automated inventory to make each audit reproducible, then perform manual reviews that preserve project-specific context. The automated inventory is descriptive only; it must not enforce a schema, mutate projects, or classify findings as errors.

---

## Motivation

Science has grown quickly across project scaffolding, validation, entity modeling, data provenance, command workflows, graph generation, curation, and managed artifacts. Downstream projects now contain the best evidence for what established research projects actually need.

The audit should answer three questions:

1. Which conventions are stable enough across mature projects to support upstream?
2. Which differences are legitimate project-specific specialization?
3. Which inconsistencies are drift, stale scaffolding, or missing model/tooling support?

The result should inform later work on managed artifact versioning, project profiles, entity schemas, data handling, planning docs, validation, and curation workflows. It should not directly implement those changes.

## Deliverables

- `docs/audits/downstream-project-conventions/inventory/` - one generated inventory report per project.
- `docs/audits/downstream-project-conventions/projects/` - one manual audit report per project.
- `docs/audits/downstream-project-conventions/synthesis.md` - cross-project synthesis and upstream recommendations.
- Optional: `docs/audits/downstream-project-conventions/tooling-notes.md` - gaps in the v0 inventory script noticed during audit.

Create the audit directory before the first report:

```bash
mkdir -p docs/audits/downstream-project-conventions/inventory
mkdir -p docs/audits/downstream-project-conventions/projects
```

## Non-Goals

- Do not rewrite downstream projects during this audit.
- Do not normalize metadata, move files, or update validators as part of the audit.
- Do not decide final upstream schema migrations in project reports.
- Do not treat every divergence as a defect.
- Do not build a full `science-tool project audit` command before the manual audit has identified what is worth formalizing.
- Do not read every file in full. Use inventories, targeted samples, and representative artifacts.

## Workflow

### Phase 1: Build v0 Inventory

Create a lightweight local script or one-off command that can be run against each downstream root and emit deterministic Markdown or JSON. The script should live outside downstream project repos while the audit is exploratory.

Recommended path:

- `scripts/audit_downstream_project_inventory.py`

The script should accept:

```bash
uv run python scripts/audit_downstream_project_inventory.py /home/keith/d/r/mm30 \
  > docs/audits/downstream-project-conventions/inventory/mm30.md
```

Inventory output should include:

- project root and git status summary;
- tracked top-level file counts from `git ls-files`;
- tracked second-level counts for `doc/`, `docs/`, `specs/`, `tasks/`, `knowledge/`, `data/`, `results/`, `code/`, `src/`, `scripts/`, `workflow/`, and `workflows/`;
- present-but-untracked important directories such as `data/`, `results/`, `logs/`, `.snakemake/`, `.venv/`, `node_modules/`, and `.worktrees/`;
- symlinked project paths, especially `data`, `results`, and `models`;
- `science.yaml` keys and basic shape, including whether `data_sources` entries are strings or structured objects;
- `.gitignore` sections relevant to data, results, models, logs, PDFs, archives, worktrees, and generated files;
- `validate.sh` header summary and local differences from the current Science validator if a canonical comparator is available;
- frontmatter key counts by directory;
- observed values for `type`, `status`, `phase`, `profile`, `aspects`, and `ontologies`;
- entity id prefixes and duplicate entity ids;
- paths with `datapackage`, `local_path`, `datasets`, `consumed_by`, `produces`, `related`, `source`, or `sources` fields;
- `datapackage.json` paths;
- likely embedded metadata blocks inside long Markdown files, detected by additional `---` blocks or frontmatter-looking key runs after line 50;
- code/workflow/test layout summary.

Keep parsing forgiving. If a file has invalid frontmatter, record the path and error; do not stop the inventory.

### Phase 2: Manual Project Audits

For each downstream project, write one report:

- `docs/audits/downstream-project-conventions/projects/natural-systems.md`
- `docs/audits/downstream-project-conventions/projects/mm30.md`
- `docs/audits/downstream-project-conventions/projects/protein-landscape.md`
- `docs/audits/downstream-project-conventions/projects/cbioportal.md`

Each report should include the sections below.

#### 1. Project Center Of Gravity

Record the project's primary shape:

- research, software, content/publication, pipeline, viewer/app, or hybrid;
- dominant tracked directories;
- dominant untracked or symlinked directories;
- whether the current `profile` and `aspects` in `science.yaml` capture the real project.

Note when a project needs multiple axes rather than a single profile.

#### 2. File And Directory Organization

Compare organization within the project and against the other downstream projects:

- `doc/` taxonomy and naming;
- `docs/` versus `doc/`;
- `specs/` usage;
- `tasks/` layout and archival pattern;
- `knowledge/` generated versus source content;
- code locations: `src/`, `code/`, `scripts/`, `workflow/`, `workflows/`, notebooks, viewer apps;
- data/results/log/model locations;
- archive and migration directories.

Classify observations as:

- recurring candidate convention;
- valid project-specific convention;
- accidental drift;
- stale or unclear convention.

#### 3. Entity Model And Metadata

Sample representative files from each active entity family:

- hypotheses;
- propositions or claims;
- questions;
- papers;
- topics/background;
- datasets;
- interpretations;
- reports/syntheses;
- plans and pre-registrations;
- tasks;
- project-specific entities such as genes, mechanisms, models, lenses, descriptors, or workflows.

Record:

- missing entity families that are clearly present in prose or paths;
- duplicated information across entity types;
- inconsistent `id` prefixes;
- overloaded `type`, `status`, or `phase` values;
- fields that should likely be enums;
- fields that should likely be structured objects instead of strings;
- inline information that should likely be metadata;
- embedded entity metadata blocks inside long prose or plans;
- inconsistent use of `related`, `datasets`, `source_refs`, `datapackage`, `local_path`, `consumed_by`, and `produces`;
- external accession or ontology usage, including HGNC, NCBI Gene, UniProt, GO, UBERON, OncoTree, PDB, Pfam, InterPro, GEO, PubMed, DOI, PMCID, and arXiv where applicable.

Do not require every project to use every entity type. Focus on whether the project has a clear representation for the concepts it actually uses.

#### 4. Planning, Pre-Registration, And Decision Records

Audit planning artifacts separately from general docs:

- implementation plans;
- design/spec docs;
- pre-registrations;
- next-step/gap-analysis docs;
- curation sweeps;
- handoffs;
- audit reports;
- project roadmap or research plan files.

Record where each lives, how it is named, whether it has metadata, and whether it links to tasks, hypotheses, questions, datasets, code, or outputs.

Pay special attention to pre-registration placement, since downstream projects may use `doc/pre-registrations/`, `doc/meta/pre-registration-*`, or inline task notes.

#### 5. Task Lifecycle

Review `tasks/active.md` and done archives:

- whether completed tasks remain in active files;
- how task IDs are formatted;
- how task status values are used;
- use of `priority`, `aspects`, `group`, `related`, `blocked-by`, `created`, `completed`;
- whether code, data outputs, reports, and interpretations link back to task IDs;
- whether task groups are a stable concept worth modeling;
- whether tasks contain enough result/provenance information or should link to separate result entities.

#### 6. Code, Workflows, And Tests

Record:

- code root conventions;
- Snakemake layout;
- script naming and grouping;
- notebook placement;
- tests colocated with scripts versus root tests;
- generated model/schema code;
- viewer or app subprojects;
- config and environment files;
- linkage from code artifacts to tasks, questions, hypotheses, datasets, or plans.

Assess whether code artifacts would benefit from a lightweight metadata block or sidecar manifest. Do not assume all code files need metadata.

#### 7. Data, Results, And Provenance

Audit how the project handles:

- input data;
- protected/manual data;
- public downloadable data;
- intermediate outputs;
- final results;
- logs;
- models;
- descriptors or sidecars;
- datapackages;
- symlinked external storage;
- `.gitignore` exceptions.

Record whether source/provenance is visible and whether publicly available data can be reproduced through a pipeline.

Classify each data pattern:

- tracked source metadata only;
- tracked small public data;
- ignored raw payload with tracked descriptor;
- ignored generated output;
- symlinked external data root;
- protected/manual data requiring explicit instructions;
- unclear or risky tracking policy.

#### 8. Validation And Managed Artifacts

Compare each project's `validate.sh` behavior at a high level:

- local modifications;
- project-specific environment assumptions;
- checks that likely belong upstream;
- checks that are correctly project-specific;
- places where validator drift would be solved by managed artifact versioning;
- places where managed artifact versioning would not be enough because project profiles or schemas are missing.

Do not update validators in this audit.

#### 9. Project-Grown Conventions

List conventions that the project introduced on its own. Examples to look for:

- descriptor files;
- generated schema/model packages;
- report rollups;
- synthesis documents;
- curation ledgers;
- app/viewer resource layers;
- runpod or cloud execution notes;
- local ontology folders;
- data source overviews;
- method docs;
- issue folders;
- guide docs.

For each, note whether it appears:

- project-specific;
- useful for at least two downstream projects;
- likely missing upstream support;
- worth a future focused design pass.

#### 10. Candidate Upstream Changes

End each project report with a concise table:

| Candidate | Evidence | Scope | Priority | Migration Cost | Notes |
| --- | --- | --- | --- | --- | --- |
| Example convention or gap | Paths and brief observation | project-specific / recurring / upstream | low / medium / high | low / medium / high | Short note |

Keep this table evidence-backed. Avoid speculative recommendations that do not point to observed downstream artifacts.

### Phase 3: Cross-Project Synthesis

Write `docs/audits/downstream-project-conventions/synthesis.md` after all four project reports exist.

Required sections:

1. **Executive Summary** - high-signal findings and priority recommendations.
2. **Project Archetypes** - observed centers of gravity and whether `profile`/`aspects` are sufficient.
3. **Stable Cross-Project Conventions** - patterns present across multiple projects.
4. **Legitimate Heterogeneity** - differences Science should allow explicitly.
5. **Drift And Ambiguity** - inconsistent patterns that create operational cost.
6. **Entity Model Recommendations** - fields, enums, entity types, external IDs, ontology links, and metadata normalization.
7. **Data And Result Handling Recommendations** - data storage, datapackages, descriptors, symlinks, `.gitignore`, provenance, protected data.
8. **Planning And Task Recommendations** - planning docs, pre-registrations, task lifecycle, decision records, code/result linkages.
9. **Validation And Managed Artifact Recommendations** - what managed artifacts solve and what needs separate modeling.
10. **Tooling Recommendations** - candidates for `science-tool` inventory, health, migration, or project-profile commands.
11. **Deferred Questions** - decisions that need a design doc before implementation.

Use a priority ladder:

- **P0:** Blocks safe downstream use or causes repeated drift.
- **P1:** High-value model/tooling support with clear evidence across projects.
- **P2:** Useful convention, but project-specific or lower urgency.
- **P3:** Interesting observation; do not implement without more evidence.

## Suggested Task Breakdown

- [ ] Build the v0 downstream inventory script.
- [ ] Run inventory for `natural-systems`.
- [ ] Run inventory for `mm30`.
- [ ] Run inventory for `protein-landscape`.
- [ ] Run inventory for `cbioportal`.
- [ ] Write the `natural-systems` manual audit report.
- [ ] Write the `mm30` manual audit report.
- [ ] Write the `protein-landscape` manual audit report.
- [ ] Write the `cbioportal` manual audit report.
- [ ] Write the cross-project synthesis.
- [ ] Review synthesis for unsupported claims, missing evidence links, and premature implementation recommendations.
- [ ] Convert accepted recommendations into focused specs or implementation plans.

## Quality Bar

Every finding should include at least one concrete path or inventory observation. The audit can include hypotheses, but they must be labeled as hypotheses and should move to the deferred-questions section unless downstream evidence is strong.

The synthesis should be useful even if no implementation follows immediately. A future maintainer should be able to read it and understand which downstream pressures motivated each proposed upstream change.
