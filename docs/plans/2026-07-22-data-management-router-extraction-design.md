# Data-Management Hub Extraction — Design

**Phase 4, slice 3.** Convert `skills/data-management/SKILL.md` from a
route-and-teach hub into a pure navigation router, extracting its teaching
content into two typed leaves, and reshape `skills/data-management/frictionless.md`
onto the full normative-reference template as a clean datapackage-format
reference. Mirrors slice 1 (statistics) and
slice 2 (transcriptomics). `data-management/` is the second-to-last hub;
`pipelines/` remains after this slice.

## Problem

`data-management/SKILL.md` (189 lines) both routes **and** teaches substantial
methodology:

- **(A)** 5 principles — raw-immutable, frictionless-packages,
  provenance-tracking, reproducible-preprocessing, bound-untrusted-input;
- **(B)** the `data/raw` + `data/processed` directory convention;
- **(C)** the Input-QA vs Analysis-QA output-path convention for QA artifacts;
- **(D)** the result-package layout — `results/<workflow>/aNNN-…`, analysis-slug
  grammar, manifest custom-block schema, and the EDAM-annotated sequence-output
  convention;
- **(E)** the "When Adding a New Data Source" runbook
  (`science dataset add / verify-access / link` + manual-template fallback);
- **(F)** the "specialized biological data" routing table → the bio/ml leaves;
- **(G)** the "While Tooling Is Still Maturing" degraded-mode fallback.

Per the router doctrine (`skill-authoring.md:44`, `skill-taxonomy.md:74`), a
router carries no methodology; teaching content belongs in a typed leaf. Only
**(F)** is navigation.

The teaching content is also **duplicated with `frictionless.md`**: that leaf's
"## Directory Conventions" block (`frictionless.md:115-133`) restates **(B)**;
its "**Rules:**" restate the raw-immutable principle; its "Boundary With Dataset
Entities" overlaps **(E)**. This duplication is the "frictionless split" the
program flagged — on inspection it is a **dedup**, not a genuine two-way split:
`frictionless.md` is otherwise a cohesive `datapackage.json` *format* reference.

## Decision summary (from brainstorming)

Confirmed with the user:

1. **Two new leaves + a slim router** (the recommended shape, mirroring slices
   1 & 2). `data-management/` is a **subject** directory (its existing leaf is
   named `data-management-frictionless`), so the new leaves carry the
   `data-management-` prefix in `name:` — but, per the phase-2/3 filename rule,
   **not** in the filename (`frictionless.md` → `data-management-frictionless`
   sets the precedent).
   - **Leaf 1 — file `conventions.md`, `name: data-management-conventions`**
     (`normative-reference`): the on-disk layout + descriptor contract for
     research data and results.
   - **Leaf 2 — file `acquisition.md`, `name: data-management-acquisition`**
     (`practice-guide`): the reproducible data-acquisition + preprocessing
     workflow.
2. **frictionless is reshaped to a format-only normative reference, not split**
   — it stays one `normative-reference` leaf for the `datapackage.json` format,
   reshaped onto the full slot template (gaining versioning/invalid-cases/
   success-test) and stripped of its duplicated directory block and operational
   `science dataset` content, which move to Leaf 1 / the acquisition leaf.
   Result: Leaf 1 owns directory/result layout, frictionless owns descriptor
   format — a clean, non-overlapping boundary between two `normative-reference`
   leaves (permitted: two leaves of the same archetype in a subject is not a
   hybrid).
3. **The genomics "two leaves"→"three leaves" prose fix and `pipelines/` are
   out of scope** (separate work).

## Content mapping (every hub section → destination)

| Hub section (`data-management/SKILL.md`) | Destination |
|---|---|
| `# Data Management` + the `> Status:` routing blockquote (pointers to literature/bio/ml QA leaves) | **Router** (reshaped — these are navigation) |
| "For analysis-readiness planning, start at `../INDEX.md`…" | **Router** |
| `## Principles` 1 (raw-immutable) | **Leaf 1** (invariant) |
| `## Principles` 2 (frictionless-packages) | **Leaf 1** (invariant; pointer to `frictionless.md`) |
| `## Principles` 3 (provenance-tracking) | **Leaf 1** (invariant) |
| `## Principles` 4 (reproducible-preprocessing) | **Leaf 2** (quality criterion) |
| `## Principles` 5 (bound-untrusted-input-before-parsing) | **Leaf 2** (common pitfall) |
| `## Data Directory Convention` | **Leaf 1** (vocabulary/examples) |
| `## Result Packages` + `## Output-Path Convention for QA Artifacts` (Input-QA vs Analysis-QA) | **Leaf 1** |
| `### Directory Convention` (results/) + `### Analysis Slugs` + `### Manifest Schema` + `### Sequence Outputs` (EDAM) | **Leaf 1** |
| `## When Adding a New Data Source` (CLI runbook + manual fallback) | **Leaf 2** (workflow steps + judgment rules) |
| `## When Working With Specialized Biological Data` (routing table) | **Router** (F — navigation, kept) |
| `## While Tooling Is Still Maturing` (degraded-mode fallback) | **Leaf 2** (judgment rules) |
| `## Companion Skills` | **Router** `## Companion Skills` (kept, updated) |

**No dropped knowledge:** every section has a destination; the new leaves carry
the content before the hub sections are deleted.

## Leaf 1 — file `conventions.md`, `name: data-management-conventions`

- **Archetype:** `normative-reference` — the skill *is* the contract for where
  research data/results live on disk and what descriptors they carry. (Not
  teaching how to operate a tool; that is frictionless/acquisition.)
- **Frontmatter provenance:** `sources: [edam]` — relocated from the hub, whose
  only external-basis content is the EDAM-annotated sequence-output convention
  that moves here. (The rest is internal convention, but the leaf legitimately
  carries the EDAM-derived vocabulary; `sources:` records the basis, and moving
  it here rather than dropping it preserves the hub's provenance.)

**Reshape into the `normative-reference` slot contract** (`skill-taxonomy.md:53`),
not pasted prose. Target outline:

- `## Scope` — the on-disk layout and descriptor conventions for a project's
  research **data** (`data/raw`, `data/processed`) and **workflow-result**
  directories (`results/<workflow>/<slug>/`), including where QA artifacts live.
  Excludes the `datapackage.json`/`.yaml` *format* (→ `frictionless.md`), the
  acquisition workflow (→ `acquisition.md`), and **research packages** — a
  distinct artifact governed by `../research-package/research-package-spec.md`
  (see the boundary note below).
- **Logical vs. physical paths, and the split-storage distinction (stated once,
  up front, and used consistently throughout).** Only the bulk **`data/…`** paths
  are **logical** paths relative to the **resolved project data root**: logical
  `data/raw` is physically `<resolved-root>/raw`, where the root resolves by the
  precedence `SCIENCE_DATA_ROOT` → `science.yaml` `data.root` → global
  `~/.config/science/config.yaml` `data.root` + project id → `./data`
  (`docs/user-guide/datasets.md:584`), and bulk data stays **out of git**.
  **`results/…` is different: it is project-root-relative and version-controlled**
  (the split-storage boundary at `datasets.md:579` — lightweight,
  version-controlled provenance vs out-of-tree bulk). Do not describe `results/`
  as relative to the resolved data root. Examples and invalid cases below use
  the logical form for `data/` and name its resolution; `results/` paths are
  literal in-repo paths.
- `## Vocabulary / schema` — the two data directory trees (`data/raw`,
  `data/processed`); the **two distinct package artifacts**, kept separate:
  1. **Workflow-result packages** — `results/<workflow>/<slug>/` (project-root-
     relative, version-controlled) where `<slug>` follows the `aNNN-description`
     analysis-slug grammar (monotonic global counter, gaps allowed). The manifest
     is a Frictionless descriptor `datapackage.yaml` (or `.json`) enumerating
     `resources`, alongside a `config.yaml` snapshot; `science qa-audit` reads it
     (authority: `templates/workflow-run.md:7` defines the manifest path,
     `qa-audit` consumes `resources` and accepts YAML or JSON). **Do not** claim
     `workflow`/`entities`/`provenance` manifest custom blocks — those had no
     citable authority (they were the hub's stale generic schema). The
     workflow↔result and entity cross-references live on the **`workflow-run`
     entity** (`templates/workflow-run.md` frontmatter: `workflow`, `inputs`,
     `produces`, entity xrefs), not as manifest blocks. Authority is the
     workflow-run template — **not** research-package-spec.
  2. **Research packages** — a **separate** artifact at `research/packages/{name}/`
     with `datapackage.json` profile `science-research-package` and a nested
     `research` extension block (authority:
     `../research-package/research-package-spec.md:20`). This leaf **references**
     that artifact and its authority; it does not define it.

  Plus: the Input-QA path pattern `data/processed/<cohort_id>/<qa_step>/` vs the
  Analysis-QA path pattern `results/<workflow>/<slug>/<qa_step>/`; the EDAM
  `data`/`format` annotation shape for FASTA sequence outputs.
  **Descriptor-form accuracy:** state the form each artifact actually uses per
  its authoritative template (data packages: `datapackage.json` from
  `frictionless describe`; workflow-result manifests: `datapackage.yaml` per
  `workflow-run.md`); do **not** transcribe the hub's stale generic
  "`datapackage.json` for every result" — reconcile against the template.
- `## Invariants` — raw data is immutable (never modify `data/raw/`;
  transformations produce new files under `data/processed/`); every data
  directory carries a data-package descriptor; every QA output directory carries
  a descriptor; every processed file records its provenance (which
  script/pipeline produced it); the two QA locations are mirrors (input-QA
  travels with the dataset, analysis-QA travels with the result).
- `## Conformance rules` — how to check: `science datasets validate` (validates
  the resolved data root; `--path data/raw/` for an explicit in-repo path);
  `science qa-audit` reads the workflow-result manifest; presence of a descriptor
  in each data/result/QA directory; respect `SCIENCE_DATA_ROOT` / `science.yaml`
  `data.root`; never commit files under the resolved data root.
- `## Examples` — the annotated logical `data/` tree (noting the
  logical→resolved-root mapping and that bulk data stays out of git), the
  version-controlled in-repo `results/<workflow>/<slug>/` (= `aNNN-…`) tree with
  `datapackage.yaml` + `config.yaml`, and the EDAM sequence-annotation JSON
  snippet.
- `## Versioning / migration` — brief; the workflow-result manifest schema's
  authority is the workflow-run template + project spec; the research-package
  schema's authority is research-package-spec (referenced, not restated).
- `## Invalid cases` — modifying files under the resolved `raw/`; a QA/result
  directory with no descriptor; an analysis result written outside
  `results/<workflow>/<slug>/`; **conflating a workflow-result package with a
  research package** (wrong path, profile, or descriptor form); committing files
  under the resolved data root.
- `## Success test` (canonical normative-reference) — is there an explicit
  conformance check against the vocabulary/invariants (mechanical via
  `science datasets validate` / `science qa-audit` where applicable, itemized
  checklist otherwise)?
- `## Companion Skills` (required by the linter, `lint.py`
  `check_companion_skills`) — `../research-package/research-package-spec.md` (the
  **separate** research-package artifact this leaf bounds against), `./SKILL.md`
  (router), `./frictionless.md` (the descriptor format that realizes these
  conventions), and the acquisition leaf. The acquisition entry is written as a
  **backticked** path `` `./acquisition.md` `` (not a `[](…)` link): it is the
  reciprocal within-slice reference and `acquisition.md` does not yet exist when
  this leaf is committed. `check_relative_links` scans only `](…)` markdown
  links (`lint.py:137`), so a backticked path is not validated — the slice-2
  mechanism that keeps this commit green (see *No RED window* below). The three
  companions that already exist are ordinary markdown links.

## Leaf 2 — file `acquisition.md`, `name: data-management-acquisition`

- **Archetype:** `practice-guide` — a cross-cutting activity (bring new data
  into a project reproducibly) that is not a method, modality, gate, tool, or
  spec. The `science dataset` CLI is a means, not the subject; the leaf is the
  workflow discipline.
- **Frontmatter provenance:** `provenance: internal` — all content is internal
  CLI/workflow/discipline.

**Reshape into the `practice-guide` slot contract** (`skill-taxonomy.md:67`):

- `## When to apply` — when acquiring or registering a new data source for a
  project, before it enters analysis.
- `## Workflow steps` — the (E) runbook as ordered steps: `science dataset add
  <slug>` (title/source-url/level/tier) → `science dataset verify-access <slug>`
  (license/method/source-url) → `science dataset link <dataset-ref>
  <question-or-hypothesis-ref>` → add acquisition scripts to `code/scripts/` or
  workflow rules under `code/workflows/` → create/update runtime
  `datapackage.json` descriptors (deferring their format to `frictionless.md`
  and their placement to `conventions.md`).
- `## Judgment rules` — CLI-first vs manual-template fallback: use
  `science dataset add`/`verify-access` whenever the CLI fields can express the
  record; write `entities/datasets/<slug>.md` manually only when the CLI cannot
  represent a needed field, for a deliberate backfill, or a project-specific
  review template — keeping unknown evidence visibly marked and then running
  `verify-access` or recording the blocked reason. Download by hand into the
  **resolved data root's** `raw/` (logical `data/raw`, physically
  `<resolved-root>/raw` — the root resolves per `SCIENCE_DATA_ROOT` /
  `science.yaml` `data.root`; see `./conventions.md`), never a literal `./data`
  when a root is configured, and only when automated download is unavailable
  (the (G) degraded mode).
- `## Quality criteria` — preprocessing is reproducible: every transformation is
  scripted (`code/scripts/` or `code/workflows/`) and documented with
  provenance; raw is untouched (defers the invariant to `conventions.md`).
- `## Common pitfalls` — **unbounded untrusted input before parsing** (the
  bound-untrusted-input principle: when a step feeds real-world/heterogeneous/
  externally-sourced content to a parser — LaTeX, HTML, XML, regex — cap input
  length up front with a per-step budget; super-linear parsers can OOM the run
  on a single pathological record; verify the bound is output-neutral on normal
  records); acquiring data without registering the durable `dataset:<slug>`
  entity; silent manual edits to `data/raw/`.
- `## Outputs` — a registered `dataset:<slug>` entity with verified access
  evidence, linked to the question/hypothesis it supports; acquisition scripts
  under version control; runtime `datapackage.json` descriptors for raw and
  processed directories.
- `## Success test` (canonical practice-guide) — did the agent carry out the
  acquisition workflow per its steps, judgment rules, and quality criteria
  (dataset registered + access verified + scripted preprocessing + descriptors
  present)?
- `## Companion Skills` — `./SKILL.md` (router), `./conventions.md` (where the
  acquired data/results must live), `./frictionless.md` (the descriptor format
  the workflow produces), `../literature/literature-evaluation.md` +
  `../literature/citation-discipline.md` (source-choice/citation for data-source
  provenance — carried over from the hub's current Companion table).

## Router — `data-management/SKILL.md`

Pure navigation, mirroring `study-design/SKILL.md` and the slice-1/2 routers:

- `# Data Management — Router` + "A router carries no methodology; teaching
  content belongs in a typed leaf."
- **Frontmatter:** `sources: [edam]` → `provenance: internal` (the EDAM content
  moved to Leaf 1; a pure router claiming edam provenance would be false).
- `## Routing trigger` — load when acquiring, preprocessing, laying out, or
  QA'ing project data or results.
- `## Scope boundary` — covers the on-disk conventions, descriptor format, and
  acquisition workflow for project data/results; excludes modality-specific QA
  (→ the bio/ml leaves it routes to) and the statistical modeling itself.
- `## Leaves` — a 3-row table (backticked relative paths, not `[](…)` links,
  per the slice-1/2 router style):

  | Leaf | Load when | Do not load when |
  |---|---|---|
  | `conventions.md` | laying out `data/`/`results/`, placing QA artifacts, or writing a result-package manifest | operating the `datapackage.json` format itself (→ `frictionless.md`) |
  | `acquisition.md` | acquiring/registering a new data source or scripting reproducible preprocessing | the data is already registered and laid out |
  | `frictionless.md` | writing or validating a `datapackage.json` descriptor | choosing where files go (→ `conventions.md`) |

- `## Specialized biological data` — **kept** (the (F) routing pointers to
  `../bio/transcriptomics/SKILL.md`, `../bio/genomics/…`, `../bio/proteomics/…`,
  `../bio/functional-genomics-qa.md`, `../ml/embeddings-manifold-qa.md`), plus
  the source-specific pointers (`../literature/sources/openalex.md`,
  `pubmed.md`) reshaped from the current `> Status:` blockquote. This is
  navigation and stays in the router.
- `## Decision / compose order` — non-circular, acquisition-driven: for a new
  dataset, **`acquisition.md` is the driving workflow**; within it, consult
  `conventions.md` **before** placing files (to choose the logical layout) and
  `frictionless.md` **at the descriptor step** (to write the `datapackage`).
  `conventions.md` and `frictionless.md` are references the acquisition workflow
  invokes, not phases that wholly precede or follow it. For modality QA, load the
  relevant specialized-bio leaf after the data is laid out.
- `## Parent & neighbors` — `../INDEX.md`; neighbor routers `../pipelines/SKILL.md`,
  `../statistics/SKILL.md`, the bio/ml routers.
- `## Success test` (required by `router.md:35`) — representative in-scope tasks
  (acquire a dataset, place a QA artifact, write a result manifest) route to the
  correct leaf / compose order without any methodology being read from the
  router.
- `## Companion Skills`.

## Frictionless reshape — `data-management/frictionless.md`

This is a **reshape onto the full `normative-reference` template**, not just a
dedup — the leaf currently lacks three required slots (versioning/migration,
invalid cases, success test) and still carries operational content that belongs
in the new leaves. Target: a clean descriptor-**format** reference.

- **Slots.** Reshape to the normative-reference contract: `## Scope` ·
  `## Vocabulary / schema` (Core Concepts, Field Types) · `## Invariants` ·
  `## Conformance rules` (Validation) · `## Examples` (Creating a Data Package —
  Options A/B) · `## Versioning / migration` (**new**) · `## Invalid cases`
  (**new**) · `## Success test` (**new** — an explicit conformance check:
  `science datasets validate` / `frictionless validate`) · `## Companion Skills`.
- **Remove** the `## Directory Conventions` block (`frictionless.md:115-133`,
  which duplicates Leaf 1's data-directory tree + raw-immutable "**Rules:**"):
  directory/result layout is Leaf 1's contract; replace with a one-line pointer
  to `conventions.md`.
- **Reduce `Boundary With Dataset Entities`** (`frictionless.md:23-36`) to the
  **semantic** distinction only — "a `datapackage.json` is a runtime descriptor
  for files on disk; it is *not* the durable `dataset:<slug>` entity lifecycle"
  — plus pointers to `./acquisition.md` (the `science dataset add` /
  `verify-access` workflow) and `./conventions.md` (data-root policy: respect
  `SCIENCE_DATA_ROOT` / `science.yaml`, never commit under the resolved root).
  **Remove** the duplicated operational `science dataset` command lines and
  data-root prose from this leaf — they now live in acquisition/conventions.
- **Keep** (as descriptor-format content): When-To-Use, the field-type table,
  validation, package-creation examples, Connecting to Inquiry Variables,
  Provenance in Data Packages (the `sources` field *is* descriptor-format, not
  the moved principle), and the `sources:` frontmatter.
- **Retarget** the Companion line `frictionless.md:152`
  (`[`SKILL.md`](SKILL.md) - data-management conventions that require
  descriptors…`) → `[`conventions.md`](conventions.md)` (label **and** href).
- **External blast radius: none — but every occurrence is classified, not
  assumed uniform** (finding 6). Excluding the hub `SKILL.md` and `frictionless.md`
  itself, there are **20 occurrences across 19 files** (`proteomics-qa.md`
  carries both a body and a Companion occurrence — `:86` and `:108` — which is
  why 20 > 19):
  - **14 body** "*Generate a `datapackage.json` for this directory; see
    frictionless.md*" links (e.g. `somatic-mutation-qa.md:98`,
    `bulk-rnaseq-qa.md:151`, `embeddings-manifold-qa.md:100`,
    `proteomics-qa.md:86`, `compositional-data.md:99`,
    `annotation-curation-qa.md:81`);
  - **5 Companion / neighbor** entries — `research-package-spec.md:115`
    ("Frictionless descriptor conventions reused by research packages"),
    `snakemake.md:491` ("data-package descriptors for workflow inputs and
    outputs"), `proteomics-qa.md:108`, `transcriptomics/SKILL.md:56`,
    `cohort-qa.md:118` ("Data-Package substrate for the cohort_audit sidecar");
  - **1 INDEX** machine entry (`INDEX.md:44`).

  **All 20** cite the descriptor-format role frictionless **keeps**; **none**
  cite the removed Directory-Conventions block. The plan must verify each
  occurrence (not rely on uniformity) and confirm no retarget is needed.

## Reference-retargeting inventory (refs to the hub `SKILL.md`)

**Retarget to `conventions.md`** (these cite the hub *for conventions content
that is moving*):

- `skills/pipelines/SKILL.md:44` — "input-data conventions; read from `data/raw/`…".
- `skills/bio/SKILL.md:19` — "conventions (see `../data-management/SKILL.md`)".
- `skills/bio/transcriptomics/SKILL.md:55` — Companion "generic data conventions".
- `skills/bio/genomics/SKILL.md:38` — Companion "generic data-management conventions".
- `skills/bio/proteomics/protein-sequence-structure-qa.md:115` — Companion "generic data-management conventions for processed protein datasets" (label is a backticked `SKILL.md` — update label **and** href).
- `skills/statistics/SKILL.md:59` — Companion "input-data conventions; some modeling decisions depend on data shape".
- `skills/research-package/SKILL.md:18` — "Excludes general dataset-directory conventions (see …)".

**Stay pointing at the router `SKILL.md`** (navigational / neighbor entries —
correct after it becomes a pure router):

- `skills/INDEX.md:43` — machine entry `data-management: …/SKILL.md` (router is the entry point).
- `skills/INDEX.md:108` — human "load when data acquisition, preprocessing, or QA is in scope" (router routes to those leaves).
- `skills/bio/SKILL.md:37` — "Neighboring routers: … `../data-management/SKILL.md`".
- `skills/bio/transcriptomics/SKILL.md:21` — scope-boundary neighbor pointer.
- `skills/research-package/SKILL.md:34` — "Neighboring routers: … `../data-management/SKILL.md`".
- `skills/meta/SKILL.md:33` — "Neighboring subject routers: … `../data-management/SKILL.md`".

**Stale-label discipline** (the slice-3 lesson): where a retargeted link's label
names a path (e.g. a backticked `` `SKILL.md` ``), update the **label** to the
new path too — an href-only retarget leaves a label naming a file that no longer
carries the content.

## Doctrine edits (BOTH files — the slice-1 lesson)

1. **`skills/meta/skill-authoring.md:44`** — the router-invariant paragraph.
   `2 of 14 … hubs … data-management/SKILL.md and pipelines/SKILL.md.`
   → `1 of 14 … hubs … pipelines/SKILL.md.`; add a dated note that
   `data-management/SKILL.md` was extracted to a router on 2026-07-22 into
   `data-management-conventions` (normative-reference) and
   `data-management-acquisition` (practice-guide), with `frictionless.md`
   reshaped to the format-only descriptor reference.
2. **`skills/meta/skill-authoring.md:39`** — the phase-4 work list mentions "the
   `frictionless`/`mutational-signatures` splits". Update to drop `frictionless`
   (dedup'd, not split): "the `mutational-signatures` split".
3. **`skills/meta/skill-taxonomy.md:112`** — "Two hubs remain
   (`data-management/`, `pipelines/`)" → "**One hub remains (`pipelines/`)**";
   record the data-management extraction.
4. **`skills/meta/skill-taxonomy.md:111`** — "`frictionless`/`mutational-signatures`
   splits remain (phase 4)" → drop `frictionless` (dedup'd): "the
   `mutational-signatures` split remains (phase 4)".

## INDEX edits (`skills/INDEX.md`)

- Add two machine `name: path` entries (in the `data-management-*` block,
  alphabetically):
  - `data-management-acquisition: skills/data-management/acquisition.md`
  - `data-management-conventions: skills/data-management/conventions.md`
- Add the two leaves to any human descriptive listing that enumerates the
  data-management leaves (mirror the existing `data-management-frictionless`
  row).
- The `data-management: …/SKILL.md` router entry (`INDEX.md:43,108`) is unchanged.

## Codex mirror

The generator (`scripts/generate_codex_skills.py` / `codex_skills.py`) mirrors
only `commands/*.md` and the two `COMPANION_SKILLS` — `scientific-writing` and
`skill-development` (`skills/meta/SKILL.md` + its sibling markdown +
`templates/`). It does **not** walk `skills/data-management/` leaves. Therefore:

- The two new leaves, the router rewrite, and the frictionless reshape **do not
  appear** in `codex-skills/` — nothing to regenerate on their account.
- Regeneration **is** required because the doctrine edits land on resources of
  the `skill-development` companion. The exact rewritten mirror files are
  precisely two:
  - `codex-skills/science-skill-development/skill-authoring.md`
  - `codex-skills/science-skill-development/skill-taxonomy.md`
- `test_committed_codex_skills_match_fresh_generation` goes RED after the
  doctrine edits and GREEN after regeneration — the green gate, exactly as
  slices 1 & 2. Assert the changed-file set is **exactly** those two.

## No linter change this slice

Unlike slice 2 (which made `check_halt_on_conditions` archetype-derived), this
slice needs **no** `skills_lint` change. Leaf 1 is `normative-reference` and
Leaf 2 is `practice-guide`; neither archetype has a lint-enforced section (only
`measurement-qa`'s Halt-On is enforced). Their slot completeness is a
design/review checklist item, not a mechanical lint. `check_frontmatter`,
`check_companion_skills`, `check_relative_links`, `check_index_coverage`, and
`check_provenance` already cover the new files with no code change.

## Approaches considered / rejected

- **One conventions leaf, frictionless absorbs it** (extract B/C/D into
  `frictionless.md`, one big normative-reference): rejected by the user —
  frictionless would grow and mix descriptor-*format* with directory/result
  *layout*, two distinct contracts.
- **Split frictionless into two leaves** (format reference + validation/QA
  practice): rejected — frictionless is cohesive; its only real defect is the
  directory-convention duplication, which the dedup resolves. Splitting a
  cohesive leaf on a population of one is a premature split.
- **Fold acquisition (E/G) into the router as a runbook**: rejected — the router
  carries no methodology; a procedural runbook is teaching content and needs a
  typed leaf.
- **Merge acquisition into conventions**: rejected — the acquisition *workflow*
  (practice-guide) and the storage *contract* (normative-reference) are distinct
  archetypes; combining them violates exactly-one-primary-archetype.

## Safety checks / invariants (for the plan's fail-closed gates)

- **No dropped knowledge:** every hub section maps to a destination (table
  above); the principles, directory/result conventions, and runbooks appear in
  the new leaves before the hub sections are deleted.
- **Router carries no methodology:** final `SKILL.md` has no `## Principles`, no
  `## Data Directory Convention`, no `## Output-Path Convention`, no
  `## Result Packages`/`### Manifest Schema`, no `## When Adding a New Data
  Source`, no `## While Tooling Is Still Maturing` — only routing sections.
- **No stale labels:** after retargeting, no `skills/` file references moved
  conventions content via a label naming `SKILL.md` while pointing at content
  now in `conventions.md`; scan `[`<label>`](<href>)` where label≠href and label
  no longer carries the content.
- **Two normative-reference leaves, non-overlapping:** `conventions.md` (layout
  contract) and `frictionless.md` (descriptor format) share no duplicated
  directory-convention prose after the dedup; each points at the other for its
  complement.
- **Archetype-slot completeness:** Leaf 1 carries every `normative-reference`
  slot (scope · vocabulary/schema · invariants · conformance rules · examples ·
  versioning/migration · invalid cases · success test); Leaf 2 carries every
  `practice-guide` slot (when to apply · workflow steps · judgment rules ·
  quality criteria · common pitfalls · outputs · success test). Routers carry no
  `archetype:`.
- **Provenance relocation:** the router's `sources: [edam]` becomes
  `provenance: internal`; `conventions.md` carries `sources: [edam]`;
  `acquisition.md` carries `provenance: internal`; `frictionless.md` keeps its
  `sources:`. `check_provenance` green on all four files.
- **Doctrine consistency:** both `skill-authoring.md` and `skill-taxonomy.md`
  agree — **one hub remains (`pipelines/`)** — and neither lists
  `data-management/` as a current hub or `frictionless` as a remaining split.
- **Corpus count (linter-structural definition):** **42 → 44 leaves** — derived
  as 64 total `.md` − 7 `meta/templates/` = 57 discovered (`discovery.py:15`)
  − 14 `SKILL.md` routers − 1 `INDEX.md` = 42 today, +2 new leaves = 44. (The
  archetype *matrix* count, excluding the two `meta/` doctrine leaves, is
  40 → 42 — the denominator the memory/doctrine uses.) Both new leaves have
  machine INDEX entries (`check_index_coverage` green); routers/`INDEX.md` carry
  no `archetype:`.
- **Result-package separation (finding 2):** the conventions leaf defines
  workflow-result packages (`results/<workflow>/<slug>/`, `datapackage.yaml`,
  authority = `workflow-run.md` + `science qa-audit`) and research packages
  (`research/packages/{name}/`, profile `science-research-package`, authority =
  `research-package-spec.md`) as **distinct** artifacts; it never names
  research-package-spec as the authority for the `results/<workflow>/` layout.
- **Logical vs. physical paths (finding 3):** both leaves state the logical→
  resolved-root mapping once and use logical paths consistently; the manual-
  download fallback targets the resolved data root, not a literal `./data`.
- **Frictionless is a full normative-reference (finding 1):** after the reshape
  `frictionless.md` carries all eight normative-reference slots (incl. the three
  previously missing: versioning/migration, invalid cases, success test) and no
  longer carries operational `science dataset` command lines or duplicated
  data-root/directory prose.
- **No RED window (finding 4, explicit mechanism):** task order (Leaf 1 + INDEX
  entry → Leaf 2 + INDEX entry → router rewrite → frictionless reshape →
  doctrine + codex regen). The only reciprocal within-slice reference —
  `conventions.md` → `acquisition.md`, written before `acquisition.md` exists —
  is a **backticked** path, which `check_relative_links` does not validate
  (`lint.py:137` scans only `MARKDOWN_LINK_RE`; `INLINE_CODE_RE` is used solely
  by `_collect_indexed_paths`, `lint.py:239`). Every `](…)` markdown link at
  each commit resolves; every leaf is INDEX-covered at its creating commit.
- **Green gate:** codex mirror regenerated; exactly two mirror files change
  (`science-skill-development/skill-authoring.md` + `skill-taxonomy.md`); the new
  data-management leaves do **not** appear in `codex-skills/`;
  `test_committed_codex_skills_match_fresh_generation` + full `pytest` +
  `skills lint` green. (Base main carries pre-existing ruff/pyright failures in
  unrelated files — run ruff/pyright components **separately**, not
  `&&`-chained, and prove any failing file is unchanged from merge-base.)

## Out of scope (explicitly unchanged)

- `pipelines/SKILL.md` — the last remaining hub; its own future slice.
- The `bio/genomics/SKILL.md` "two leaves"→"three leaves" prose fix — a trivial
  separate commit.
- The `mutational-signatures` split — a separate slice.
- All 20 external `frictionless.md` datapackage-format occurrences (across 19
  files) — unchanged.
