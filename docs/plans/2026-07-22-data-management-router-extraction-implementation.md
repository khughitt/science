# Data-Management Hub Extraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `skills/data-management/SKILL.md` from a route-and-teach hub into a pure navigation router, extracting its teaching content into two typed leaves (`conventions.md` normative-reference, `acquisition.md` practice-guide), and reshaping `frictionless.md` onto the full normative-reference template as a clean datapackage-format reference.

**Architecture:** The hub's on-disk layout + descriptor conventions become `data-management-conventions` (normative-reference); its acquisition/preprocessing runbook becomes `data-management-acquisition` (practice-guide); the `SKILL.md` becomes a pure router keeping only its navigation (the specialized-bio routing table). `frictionless.md` is reshaped to the format-only normative reference. Both doctrine files reconcile to "one hub remains (`pipelines/`)" and the codex mirror is regenerated. No linter change this slice.

**Tech Stack:** Python `science_tool` CLI (skills linter, codex mirror generator), pytest / ruff / pyright, Markdown skill files, `scripts/generate_codex_skills.py`.

**Design doc:** [`2026-07-22-data-management-router-extraction-design.md`](./2026-07-22-data-management-router-extraction-design.md) — the authoritative source for content mapping, slot contracts, the artifact-separation ruling, and the reference-retargeting inventory.

## Global Constraints

Every task's requirements implicitly include this section.

- **No AI-attribution trailers/footers** on commits (no `Co-Authored-By`, no "Generated with Claude Code").
- **Run all tooling from `science/`** (there is no root `pyproject.toml`): tests `uv run --frozen pytest`; **skills lint `uv run --frozen science skills lint --root ../skills`**. A task is not green until `skills lint` exits 0 over the whole `../skills` tree. (Tasks 1–6 touch **no** Python; **Task 7** edits two `science/tests/` files — test directories are **not** pyright-checked, and ruff is per-package. Base `main` carries pre-existing ruff/pyright failures in unrelated files — do **not** `&&`-chain them into a gate; if you run them, prove any failing file is unchanged from merge-base. The full `pytest` suite is the binding gate for Task 7.)
- **`data-management/` is a SUBJECT directory** — the two new leaves carry the `data-management-` prefix in `name:` (like the existing `data-management-frictionless`), but **NOT** in the filename (`conventions.md`, `acquisition.md` — the `frictionless.md`/`data-management-frictionless` split sets the precedent).
- **Every leaf declares exactly one recognized `archetype:`; routers and `INDEX.md` carry none** (the linter enforces both directions).
- **Slot fidelity:** each new leaf carries its archetype template's sections **in template order and with the template's exact `##` headings** (`skills/meta/templates/normative-reference.md`, `.../practice-guide.md`, `.../router.md`). No required section may be dropped or renamed. Note the normative-reference heading is exactly `## Vocabulary / schema / enums`.
- **Companion Skills form:** the reciprocal within-slice reference `conventions.md` → `acquisition.md` is a **backticked** inline-code path (`` - `./acquisition.md` — … ``), NOT a `[label](path)` markdown link, because `acquisition.md` does not exist when `conventions.md` is committed and `check_relative_links` (`lint.py:137`) validates only `](…)` links. Companions that already exist may be markdown links. `check_companion_skills` only requires the `## Companion Skills` heading to be present.
- **Logical vs. physical / split storage (findings 1 & 3):** only bulk **`data/…`** paths are logical, relative to the resolved data root (`SCIENCE_DATA_ROOT` → `science.yaml` `data.root` → global → `./data`); bulk data stays out of git. **`results/…` is project-root-relative and version-controlled** — never describe it as relative to the resolved data root. The manual-download fallback targets the resolved root's `raw/`, not a literal `./data`.
- **Two distinct package artifacts (finding 2):** the conventions leaf defines **workflow-result packages** (`results/<workflow>/<slug>/`, `datapackage.yaml`/`.json` with `resources`, read by `science qa-audit`; authority = `templates/workflow-run.md`) and **references** **research packages** (`research/packages/{name}/`, profile `science-research-package`; authority = `skills/research-package/research-package-spec.md`) as a **separate** artifact. Do **not** name research-package-spec as the authority for the `results/<workflow>/` layout, and do **not** claim `workflow`/`entities`/`provenance` manifest custom blocks (no citable authority — those cross-refs live on the `workflow-run` **entity**).
- **Reshape, do not transcribe (finding 1):** `frictionless.md` gains the three missing normative-reference slots (versioning/migration, invalid cases, success test) and is stripped of its duplicated `## Directory Conventions` block and operational `science dataset` command/data-root prose. Its `Boundary With Dataset Entities` reduces to the semantic distinction + pointers.
- **Reference retargeting:** retarget only the **conventions-content** refs to the hub (the 7 listed in Task 4); leave the **router/neighbor** refs pointing at `SKILL.md`. Where a retargeted link's label names a path (e.g. a backticked `` `SKILL.md` ``), update the **label** too. All 20 `frictionless.md` occurrences (across 19 files) stay — verify each, none retarget.
- **Doctrine agreement:** after this slice both `skill-authoring.md` and `skill-taxonomy.md` state **one hub remains (`pipelines/`)**, neither lists `data-management/` as a current hub, and neither lists `frictionless` as a remaining split.
- **Never tune content or metadata to silence a check.** If a check fires, fix the content, not the check.
- **codex-skills/ is generated** — never hand-edit; regenerate via `scripts/generate_codex_skills.py`.
- Use `~/d/` (not `/home/keith/d/` or `/mnt/ssd/Dropbox/`) in any doc/code path text.

## File structure

| File | Task | Responsibility |
|---|---|---|
| `skills/data-management/conventions.md` (create) | 1 | normative-reference: data/result on-disk layout + descriptor contract |
| `skills/data-management/acquisition.md` (create) | 2 | practice-guide: data acquisition + reproducible-preprocessing workflow |
| `skills/data-management/SKILL.md` (rewrite) | 3 | pure router (keeps specialized-bio routing; `sources:[edam]`→`provenance:internal`) |
| 7 consumer files (edit) | 4 | retarget conventions-content refs → `conventions.md` |
| `skills/data-management/frictionless.md` (reshape) | 5 | format-only normative-reference; drop dir-conventions + operational content |
| `skills/meta/skill-authoring.md`, `skills/meta/skill-taxonomy.md`, `codex-skills/science-skill-development/{skill-authoring,skill-taxonomy}.md` | 6 | doctrine reconciliation + codex regen (green gate) |
| `skills/INDEX.md` (edit) | 1, 2 | machine + descriptive entries for the two new leaves |

**No-RED task order:** 1 → 2 → 3 → 4 → 5 → 6. Every `](…)` link resolves and every leaf is INDEX-covered at its creating commit.

---

### Task 1: Leaf 1 — `data-management-conventions` (normative-reference)

Create the normative-reference leaf owning the on-disk layout + descriptor contract, and register it in `INDEX.md`. Content maps from the hub's Principles 1 & 3, Data Directory Convention, Output-Path Convention for QA Artifacts, Result-package layout/slug/manifest/sequence sections (`data-management/SKILL.md:28-114`), reshaped onto the normative-reference template and corrected per findings 1–3.

**Files:**
- Create: `skills/data-management/conventions.md`
- Modify: `skills/INDEX.md` (add machine entry + descriptive row for `data-management-conventions`)

**Interfaces:**
- Produces: leaf `name: data-management-conventions` at `skills/data-management/conventions.md`; the `conventions.md` path that Tasks 2–5 reference.
- Consumes: nothing from later tasks. Its Companion `` `./acquisition.md` `` is backticked (Task 2 file not yet present).

- [ ] **Step 1: Write `skills/data-management/conventions.md`** with exactly this content:

```markdown
---
name: data-management-conventions
description: Use when laying out a project's data and workflow-result directories, placing QA artifacts, or writing a result-package manifest. Defines the on-disk layout and descriptor contract for research data and results.
archetype: normative-reference
sources: [edam]
---

# Data & Result Storage Conventions

Answers: what must a project's data and result directories contain, and where must artifacts live?

## Scope

The on-disk layout and descriptor conventions for a project's research **data**
(`data/raw`, `data/processed`) and **workflow-result** directories
(`results/<workflow>/<slug>/`), including where QA artifacts live. Excludes the
`datapackage` descriptor *format* (see [`frictionless.md`](frictionless.md)), the
acquisition workflow (see `acquisition.md`), and **research packages** — a
distinct artifact governed by
[`../research-package/research-package-spec.md`](../research-package/research-package-spec.md)
(see *Invariants* → package artifacts).

**Logical vs. physical paths, and split storage.** Only the bulk **`data/…`**
paths are *logical* paths relative to the **resolved project data root**: logical
`data/raw` is physically `<resolved-root>/raw`, where the root resolves by the
precedence `SCIENCE_DATA_ROOT` → `science.yaml` `data.root` → global
`~/.config/science/config.yaml` `data.root` + project id → `./data`, and bulk
data stays **out of git**. **`results/…` is different: it is project-root-relative
and version-controlled** (lightweight provenance in-repo vs out-of-tree bulk).

## Vocabulary / schema / enums

**Data directories** (logical, under the resolved data root):

- `data/raw/` — original, unmodified downloads.
- `data/processed/` — cleaned, transformed files produced by scripted steps.

**Two distinct package artifacts — kept separate:**

1. **Workflow-result packages** — `results/<workflow>/<slug>/` (project-root-
   relative, version-controlled), where `<slug>` follows the `aNNN-description`
   analysis-slug grammar: a monotonically increasing global counter, gaps
   allowed (number by workflow group for readability). The manifest is a
   Frictionless descriptor `datapackage.yaml` (or `.json`) enumerating
   `resources`, alongside a `config.yaml` snapshot; `science qa-audit` reads it
   (authority: `templates/workflow-run.md` defines the manifest path; `qa-audit`
   consumes `resources` and accepts YAML or JSON). The workflow↔result and
   entity cross-references live on the **`workflow-run` entity** (`workflow`,
   `inputs`, `produces`, entity xrefs in `templates/workflow-run.md`), not as
   manifest custom blocks.
2. **Research packages** — a **separate** artifact at `research/packages/{name}/`
   with `datapackage.json` profile `science-research-package` and a nested
   `research` extension. Authority:
   [`../research-package/research-package-spec.md`](../research-package/research-package-spec.md).
   This contract references that artifact; it does not define it.

**QA-artifact output paths** (split by lifecycle):

- **Input QA** — per-cohort/per-dataset preprocessing checks that travel with the
  dataset: `data/processed/<cohort_id>/<qa_step>/` (e.g. `cohort_audit.json`,
  per-sample QC tables, probe-to-gene mappings).
- **Analysis QA** — per-analysis post-hoc checks tied to a specific result:
  `results/<workflow>/<slug>/<qa_step>/` (e.g. bias audits, reconstruction-error
  reports, model diagnostics).

The two locations mirror each other: input QA lives next to the data it audits;
analysis QA lives next to the result it diagnoses. A step that applies to both
lives wherever it runs; document the choice in the leaf that defines it.

**Sequence outputs.** FASTA outputs go in a `sequences/` subdirectory of the
result package, annotated with EDAM terms.

## Invariants

- **Raw data is immutable.** Never modify files under the resolved `raw/`; every
  transformation produces new files under `data/processed/`.
- **Every data directory carries a data-package descriptor** (`datapackage.json`
  for `data/raw` and `data/processed`).
- **Every QA output directory carries a descriptor** (see
  [`frictionless.md`](frictionless.md)); leaves reference this convention rather
  than redefining it.
- **Provenance is recorded** — every processed file documents which
  script/pipeline produced it, from what inputs.
- **Results are version-controlled and never under the data root**; bulk data
  under the resolved data root is never committed.

## Conformance rules

- `science datasets validate` validates the resolved project data root; use
  `science datasets validate --path data/raw/` to check an explicit in-repo path.
- `science qa-audit` reads the workflow-result manifest (`resources`, YAML or
  JSON).
- Each data / result / QA directory carries its descriptor.
- Respect `SCIENCE_DATA_ROOT` and `science.yaml` `data.root`; never commit files
  under the resolved data root.

## Examples

A logical `data/` tree (physically under `<resolved-root>/`, out of git):

```
data/
├── raw/                    # immutable downloads
│   ├── datapackage.json    # Frictionless descriptor
│   └── ...
├── processed/              # cleaned, transformed
│   ├── datapackage.json
│   └── ...
└── README.md
```

A workflow-result package. The **records** are version-controlled and in-repo;
the **bulk resources** are payload governed by the data-boundary policy (not
committed here):

```
results/
└── {workflow-name}/
    └── aNNN-{description}/
        ├── datapackage.yaml     # Frictionless manifest (resources), read by qa-audit — tracked
        ├── config.yaml          # frozen config snapshot — tracked
        └── <small reports>      # lightweight JSON/text/figure records — tracked
```

Bulk result resources (`.parquet`, `.npy`, large binaries) are **payload**:
`science data audit` flags tracked payload outside a data root as
`leaked_payload`. They live under the resolved data root (or are git-ignored),
not committed in `results/`; the manifest's `resources` point at them.

EDAM annotation for a FASTA sequence resource:

```json
{
  "edam": {
    "data": "http://edamontology.org/data_2044",
    "format": "http://edamontology.org/format_1929"
  }
}
```

## Versioning / migration

The workflow-result manifest's authority is `templates/workflow-run.md` (the
manifest path) and `science qa-audit` (which consumes `resources`); the
research-package schema's authority is
[`../research-package/research-package-spec.md`](../research-package/research-package-spec.md).
This contract references them rather than restating their schemas.

## Invalid cases

- Modifying a file under the resolved `raw/` after download.
- A data, result, or QA directory with no descriptor.
- An analysis result written outside `results/<workflow>/<slug>/`.
- **Conflating a workflow-result package with a research package** — wrong path
  (`results/…` vs `research/packages/…`), profile, or descriptor form.
- Committing files under the resolved data root, or treating `results/` as
  relative to the resolved data root.

## Success test

Is there an explicit conformance check against the vocabulary and invariants —
mechanical via `science datasets validate` / `science qa-audit` where
applicable, an itemized checklist otherwise?

## Companion Skills

- `../INDEX.md` — the skill index.
- [`../research-package/research-package-spec.md`](../research-package/research-package-spec.md) — the separate research-package artifact this contract bounds against.
- [`SKILL.md`](SKILL.md) — the data-management router.
- [`frictionless.md`](frictionless.md) — the `datapackage` descriptor format that realizes these directory conventions.
- `./acquisition.md` — the acquisition workflow that produces data in this layout.
```

- [ ] **Step 2: Register the leaf in `skills/INDEX.md`.**

The `## Data Management` section of `INDEX.md` (lines ~41–44) holds **machine
entries only** — `- \`name\`: \`path\`` lines, no human descriptive listing.
Add exactly one machine entry, in the `data-management` block in alphabetical
order (it sorts after `data-management` and before `data-management-frictionless`):

```
- `data-management-conventions`: `skills/data-management/conventions.md`
```

Do **not** add a descriptive row anywhere — the `## Companion Skills` block at the
bottom of `INDEX.md` lists only routers, and `## Data Management` has no per-leaf
prose listing (verify with `rg -n 'data-management' skills/INDEX.md`).

- [ ] **Step 3: Verify structure and lint** (run from the worktree root; `rg` per repo convention):

```bash
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT/science" && uv run --frozen science skills lint --root ../skills
```
Expected: exit 0 (no `broken-relative-link`, no `missing-index-entry`, no `missing-archetype`, no `missing-section`). Then confirm slot completeness and the finding-corrections held (polarity-aware, fail-closed):
```bash
cd "$ROOT"
# all 9 normative-reference headings, template order:
rg -n '^## (Scope|Vocabulary / schema / enums|Invariants|Conformance rules|Examples|Versioning / migration|Invalid cases|Success test|Companion Skills)$' skills/data-management/conventions.md
# results ARE version-controlled/project-root-relative — assert the positive statement
# (single-line-robust: `results` and `project-root-relative` co-occur on one line):
rg -q 'results.*project-root-relative' skills/data-management/conventions.md && echo "OK: results version-controlled statement present" || { echo "FAIL: missing results-version-controlled statement"; exit 1; }
# no stale hub manifest-schema header (the hub's exact stale phrasing was 'Key custom blocks'):
rg -q 'Key custom blocks' skills/data-management/conventions.md && { echo "FAIL: stale custom-block schema present"; exit 1; } || echo "OK: no stale custom-block schema"
# cross-refs live on the workflow-run entity — assert the positive statement:
rg -q 'live on the.*workflow-run.*entity' skills/data-management/conventions.md && echo "OK: cross-refs attributed to workflow-run entity" || { echo "FAIL: missing workflow-run-entity attribution"; exit 1; }
# reciprocal companion is backticked, not a markdown link (fail-closed both directions):
rg -q '`\./acquisition\.md`' skills/data-management/conventions.md && ! rg -q '\]\(\./acquisition\.md\)' skills/data-management/conventions.md && echo "OK: acquisition ref backticked" || { echo "FAIL: acquisition ref not backticked-only"; exit 1; }
```
Expected: the 9 headings print; every `OK:` line prints; no `FAIL` (nonzero exit stops the step).

- [ ] **Step 4: Commit.**

```bash
git add skills/data-management/conventions.md skills/INDEX.md
git commit -m "feat(skills): add data-management-conventions normative-reference leaf"
```

---

### Task 2: Leaf 2 — `data-management-acquisition` (practice-guide)

Create the practice-guide leaf owning the acquisition + reproducible-preprocessing workflow, and register it. Content maps from the hub's "When Adding a New Data Source", "While Tooling Is Still Maturing", and Principles 4 & 5 (`data-management/SKILL.md:116-181,33,34`).

**Files:**
- Create: `skills/data-management/acquisition.md`
- Modify: `skills/INDEX.md` (add machine entry + descriptive row for `data-management-acquisition`)

**Interfaces:**
- Consumes: `conventions.md` (created in Task 1 — reference it with an ordinary markdown link, it exists now).
- Produces: leaf `name: data-management-acquisition` at `skills/data-management/acquisition.md`.

- [ ] **Step 1: Write `skills/data-management/acquisition.md`** with exactly this content:

```markdown
---
name: data-management-acquisition
description: Use when acquiring or registering a new data source for a project, or scripting reproducible preprocessing before data enters analysis.
archetype: practice-guide
provenance: internal
---

# Data Acquisition & Preprocessing Workflow

Answers: how do I bring new data into a project reproducibly?

## When to apply

When acquiring or registering a new data source for a project, before it enters
analysis, and whenever writing preprocessing that transforms raw data into
analysis-ready files.

## Workflow steps

1. **Register the durable dataset entity** through the singular lifecycle:
   ```bash
   science dataset add <slug> \
     --title "<dataset title>" \
     --source-url "<landing-page-or-accession-url>" \
     --level <public|registration|controlled|commercial|mixed> \
     --tier <use-now|evaluate-next|track>
   ```
2. **Verify access evidence** before pipeline planning consumes the dataset:
   ```bash
   science dataset verify-access <slug> \
     --license <spdx-or-unknown> \
     --method <retrieved|credential-confirmed|landing-confirmed|metadata-confirmed> \
     --source-url "<landing-page-or-download-url>"
   ```
3. **Link the dataset** to the question or hypothesis it supports:
   ```bash
   science dataset link <dataset-ref> <question-or-hypothesis-ref>
   ```
4. **Add acquisition scripts** to `code/scripts/` or workflow rules under
   `code/workflows/`.
5. **Create or update runtime `datapackage` descriptors** in the appropriate data
   directory — the descriptor *format* is [`frictionless.md`](frictionless.md);
   *where* the files live is [`conventions.md`](conventions.md).

## Judgment rules

- **CLI first, manual template as fallback.** Use `science dataset add` /
  `verify-access` whenever the current CLI fields can express the record. Write
  `entities/datasets/<slug>.md` by hand only when the CLI cannot represent a
  needed field, for a deliberate legacy backfill, or a project-specific review
  template — keep unknown evidence visibly marked, then run
  `science dataset verify-access <slug>` or record the blocked verification
  reason.
- **Manual download is a degraded mode.** When automated download support is
  unavailable, download by hand into the **resolved data root's** `raw/` (logical
  `data/raw`, physically `<resolved-root>/raw` — the root resolves per
  `SCIENCE_DATA_ROOT` / `science.yaml` `data.root`; see
  [`conventions.md`](conventions.md)), never a literal `./data` when a root is
  configured.
- **Keep descriptors current** for raw and processed directories as data changes.

## Quality criteria

- **Preprocessing is reproducible:** every transformation is scripted (in
  `code/scripts/` or `code/workflows/`) and documented with provenance — which
  script produced each processed file, from what inputs.
- **Raw data is untouched:** transformations write to `data/processed/`, never
  back into `raw/` (the invariant is defined in [`conventions.md`](conventions.md)).

## Common pitfalls

- **Unbounded untrusted input before parsing.** When a step feeds real-world,
  heterogeneous, or externally-sourced content to a parser (LaTeX, HTML, XML,
  regex, etc.), cap the input length up front with a per-step budget. Many real
  parsers are super-linear, so a single pathological record can exhaust memory
  and OOM-kill the whole run — a failure mode small fixtures never exhibit.
  Verify the bound is output-neutral on normal records.
- **Acquiring data without registering the durable `dataset:<slug>` entity** —
  the entity is what pipeline planning and provenance consume.
- **Silent manual edits to raw data** — any change belongs in a scripted
  `data/processed/` step, not an in-place edit.

## Outputs

- A registered `dataset:<slug>` entity with verified access evidence, linked to
  the question or hypothesis it supports.
- Acquisition/preprocessing scripts under version control in `code/scripts/` or
  `code/workflows/`.
- Current runtime `datapackage` descriptors for the raw and processed data
  directories.

## Success test

Did the agent carry out the acquisition workflow per its steps, judgment rules,
and quality criteria — dataset registered, access verified, preprocessing
scripted, descriptors present?

## Companion Skills

- `../INDEX.md` — the skill index.
- [`SKILL.md`](SKILL.md) — the data-management router.
- [`conventions.md`](conventions.md) — where acquired data and results must live.
- [`frictionless.md`](frictionless.md) — the descriptor format this workflow produces.
- [`../literature/literature-evaluation.md`](../literature/literature-evaluation.md) — source-choice evaluation for data-source provenance.
- [`../literature/citation-discipline.md`](../literature/citation-discipline.md) — citation conformance for data-source references.
```

- [ ] **Step 2: Register the leaf in `skills/INDEX.md`.**

Add the machine entry in the `data-management-*` block, alphabetically first:

```
- `data-management-acquisition`: `skills/data-management/acquisition.md`
```

Do **not** add a descriptive row (the `## Data Management` section holds machine
entries only). After both leaves, the block reads, in order: `data-management`,
`data-management-acquisition`, `data-management-conventions`,
`data-management-frictionless`.

- [ ] **Step 3: Verify structure and lint** (run from the worktree root; `rg` per repo convention):

```bash
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT/science" && uv run --frozen science skills lint --root ../skills
```
Expected: exit 0. Then (fail-closed):
```bash
cd "$ROOT"
# all 8 practice-guide headings, template order:
rg -n '^## (When to apply|Workflow steps|Judgment rules|Quality criteria|Common pitfalls|Outputs|Success test|Companion Skills)$' skills/data-management/acquisition.md
# manual fallback targets the resolved root, not a literal ./data:
rg -q 'resolved data root' skills/data-management/acquisition.md && echo "OK: resolved-root fallback" || { echo "FAIL: fallback not resolved-root"; exit 1; }
```
Expected: the 8 headings print; the OK line prints.

- [ ] **Step 4: Commit.**

```bash
git add skills/data-management/acquisition.md skills/INDEX.md
git commit -m "feat(skills): add data-management-acquisition practice-guide leaf"
```

---

### Task 3: Rewrite `data-management/SKILL.md` as a pure router

Strip all teaching content (Principles, Data Directory Convention, Output-Path Convention, Result Packages/Manifest Schema, When Adding a New Data Source, While Tooling Is Still Maturing). Keep only navigation: the specialized-bio + source routing pointers. Add the router template's sections. Change frontmatter `sources: [edam]` → `provenance: internal` (EDAM moved to `conventions.md`).

**Files:**
- Modify (rewrite): `skills/data-management/SKILL.md`

**Interfaces:**
- Consumes: `conventions.md`, `acquisition.md`, `frictionless.md` (all exist) — referenced in the Leaves table (backticked, per router style).

- [ ] **Step 1: Rewrite `skills/data-management/SKILL.md`** with exactly this content:

```markdown
---
name: data-management
description: Router for data acquisition, preprocessing, on-disk layout, and QA. Load when working with datasets, downloading data, laying out data/results directories, or managing data provenance. Routes to the leaves below.
provenance: internal
---

# Data Management — Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when acquiring, preprocessing, laying out, or QA'ing project
data or results, before loading any leaf.

## Scope boundary

Covers the on-disk conventions, descriptor format, and acquisition workflow for
project data and results; excludes modality-specific QA (routed to the bio/ml
leaves below) and the statistical modeling itself (`../statistics/SKILL.md`).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `conventions.md` | laying out `data/`/`results/`, placing QA artifacts, or writing a result manifest | operating the `datapackage` format itself (→ `frictionless.md`) |
| `acquisition.md` | acquiring/registering a new data source or scripting reproducible preprocessing | the data is already registered and laid out |
| `frictionless.md` | writing or validating a `datapackage` descriptor | choosing where files go (→ `conventions.md`) |

## Specialized biological & source data

Route to the owning leaf before designing preprocessing or QA:

- Expression matrices, bulk RNA-seq, microarray, scRNA-seq → `../bio/transcriptomics/SKILL.md`.
- Somatic mutation tables, MAF/cBioPortal/TCGA/GENIE cohorts → `../bio/genomics/somatic-mutation-qa.md`.
- Mutational signatures, TMB, dN/dS, driver selection → `../bio/genomics/mutational-signatures-and-selection.md`.
- CRISPR/RNAi screens, DepMap, LINCS/L1000, drug response, perturbation assays → `../bio/functional-genomics-qa.md`.
- Proteomics, phosphoproteomics, mass spec, TMT/LFQ/DIA/DDA → `../bio/proteomics/proteomics-qa.md`.
- Protein sequence/structure, homology-split datasets → `../bio/proteomics/protein-sequence-structure-qa.md`.
- Embeddings, UMAP/HDBSCAN/Mapper, CKA, manifolds → `../ml/embeddings-manifold-qa.md`.
- Literature sources → `../literature/sources/openalex.md`, `../literature/sources/pubmed.md`.

## Decision / compose order

For a new dataset, `acquisition.md` is the driving workflow; within it, consult
`conventions.md` **before** placing files (to choose the logical layout) and
`frictionless.md` **at the descriptor step** (to write the `datapackage`).
`conventions.md` and `frictionless.md` are references the acquisition workflow
invokes, not phases that wholly precede or follow it. Load the relevant
specialized leaf for modality QA after the data is laid out.

## Parent & neighbors

- Parent index: `../INDEX.md` (or run `science-plan-analysis`).
- Neighboring routers: `../pipelines/SKILL.md`, `../statistics/SKILL.md`, `../bio/SKILL.md`, `../ml/SKILL.md`.

## Success test

Representative in-scope tasks — acquire a dataset, place a QA artifact, write a
result manifest — route to the correct leaf (or compose order) without any
methodology being read from this router.

## Companion Skills

- `../INDEX.md` — the skill index.
- [`conventions.md`](conventions.md) — data/result layout + descriptor contract.
- [`acquisition.md`](acquisition.md) — data acquisition + preprocessing workflow.
- [`frictionless.md`](frictionless.md) — `datapackage` descriptor format.
```

- [ ] **Step 2: Verify the router carries no methodology and lint.**

```bash
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
# no teaching sections survive (fail-closed):
rg -q '^## (Principles|Data Directory Convention|Result Packages|Output-Path Convention|Manifest Schema|When Adding a New Data Source|While Tooling Is Still Maturing)$' skills/data-management/SKILL.md && { echo "FAIL: teaching section survived"; exit 1; } || echo "OK: no teaching sections"
# frontmatter flipped to internal, edam gone from the router (fail-closed):
rg -q '^provenance: internal$' skills/data-management/SKILL.md && ! rg -q '^sources:' skills/data-management/SKILL.md && echo "OK: provenance internal, no sources" || { echo "FAIL: frontmatter not flipped"; exit 1; }
# router template sections present:
rg -n '^## (Routing trigger|Scope boundary|Leaves|Decision / compose order|Parent & neighbors|Success test|Companion Skills)$' skills/data-management/SKILL.md
cd "$ROOT/science" && uv run --frozen science skills lint --root ../skills
```
Expected: both OK lines print; the router sections print; `skills lint` exit 0.

- [ ] **Step 3: Commit.**

```bash
git add skills/data-management/SKILL.md
git commit -m "refactor(skills): rewrite data-management/SKILL.md as a pure router"
```

---

### Task 4: Retarget the 7 conventions-content references

Retarget the references that cite the hub *for conventions content that moved* to `conventions.md`. Leave router/neighbor references pointing at `SKILL.md` (do **not** touch them). Where the link label names a path, update the label too.

**Files (edit one line each):**
- `skills/pipelines/SKILL.md:44`
- `skills/bio/SKILL.md:19`
- `skills/bio/transcriptomics/SKILL.md:55`
- `skills/bio/genomics/SKILL.md:38`
- `skills/bio/proteomics/protein-sequence-structure-qa.md:115`
- `skills/statistics/SKILL.md:59`
- `skills/research-package/SKILL.md:18`

**Do NOT touch** (router/neighbor refs — stay on `SKILL.md`): `skills/INDEX.md:43,108`, `skills/bio/SKILL.md:37`, `skills/bio/transcriptomics/SKILL.md:21`, `skills/research-package/SKILL.md:34`, `skills/meta/SKILL.md:33`.

- [ ] **Step 1: Retarget each of the 7 references** so its href points at `data-management/conventions.md` (adjusting the relative depth per file) and any path-naming label is updated. Concretely:
  - `pipelines/SKILL.md:44` — `[`../data-management/SKILL.md`](../data-management/SKILL.md)` → `[`../data-management/conventions.md`](../data-management/conventions.md)`.
  - `bio/SKILL.md:19` — `(see `../data-management/SKILL.md`)` → `(see `../data-management/conventions.md`)`.
  - `bio/transcriptomics/SKILL.md:55` — `../../data-management/SKILL.md` → `../../data-management/conventions.md`.
  - `bio/genomics/SKILL.md:38` — `[`../../data-management/SKILL.md`](../../data-management/SKILL.md)` → `[`../../data-management/conventions.md`](../../data-management/conventions.md)`.
  - `bio/proteomics/protein-sequence-structure-qa.md:115` — `[`SKILL.md`](../../data-management/SKILL.md)` → `[`conventions.md`](../../data-management/conventions.md)` (label **and** href).
  - `statistics/SKILL.md:59` — `../data-management/SKILL.md` → `../data-management/conventions.md`.
  - `research-package/SKILL.md:18` — `(see `../data-management/SKILL.md`)` → `(see `../data-management/conventions.md`)`.

- [ ] **Step 2: Verify the retarget set is exact, no stale labels, and lint.**

```bash
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
# (a) Each of the 7 files now references data-management/conventions.md (fail-closed):
for f in \
  skills/pipelines/SKILL.md \
  skills/bio/SKILL.md \
  skills/bio/transcriptomics/SKILL.md \
  skills/bio/genomics/SKILL.md \
  skills/bio/proteomics/protein-sequence-structure-qa.md \
  skills/statistics/SKILL.md \
  skills/research-package/SKILL.md ; do
  rg -q 'data-management/conventions\.md' "$f" || { echo "FAIL: $f not retargeted to conventions.md"; exit 1; }
done
echo "OK: all 7 retargeted to conventions.md"
# (b) The 5 keep-refs STILL point at SKILL.md (fail-closed):
for f in \
  skills/INDEX.md \
  skills/bio/SKILL.md \
  skills/bio/transcriptomics/SKILL.md \
  skills/research-package/SKILL.md \
  skills/meta/SKILL.md ; do
  rg -q 'data-management/SKILL\.md' "$f" || { echo "FAIL: $f lost its router reference"; exit 1; }
done
echo "OK: all 5 router/neighbor refs preserved"
# (c) No file names SKILL.md as a data-management CONVENTIONS label (stale label; fail-closed):
rg -q '\[`SKILL\.md`\]\([^)]*data-management/SKILL\.md\)' skills/ && { echo "FAIL: stale [\`SKILL.md\`] conventions label remains"; exit 1; } || echo "OK: no stale SKILL.md conventions labels"
cd "$ROOT/science" && uv run --frozen science skills lint --root ../skills
```
Expected: the three `OK:` lines print; no `FAIL` (nonzero exit stops the step); `skills lint` exit 0.

> Note: `bio/SKILL.md` and `bio/transcriptomics/SKILL.md` appear in **both** (a) and (b) — each legitimately carries a retargeted conventions ref (line 19 / line 55) **and** a preserved router ref (line 37 / line 21). Both assertions must hold for those files.

- [ ] **Step 3: Commit.**

```bash
git add skills/pipelines/SKILL.md skills/bio/SKILL.md skills/bio/transcriptomics/SKILL.md skills/bio/genomics/SKILL.md skills/bio/proteomics/protein-sequence-structure-qa.md skills/statistics/SKILL.md skills/research-package/SKILL.md
git commit -m "refactor(skills): retarget data-management conventions references to conventions.md"
```

---

### Task 5: Reshape `frictionless.md` to a format-only normative reference

Replace the file wholesale with the exact content below. This reshapes it onto the full normative-reference template (adding versioning/migration, invalid cases, success test), removes the duplicated `## Directory Conventions` block, reduces the dataset-entity boundary to the semantic distinction + pointers (dropping the operational `science dataset` command lines and data-root prose), and retargets the companion to `conventions.md`. All substantive descriptor-format content (field-type table, validation, package-creation examples, inquiry-variable mapping, provenance) is preserved.

**Files:**
- Modify (replace entirely): `skills/data-management/frictionless.md`

**Interfaces:**
- Consumes: `conventions.md`, `acquisition.md` (both exist by now) for the pointers.

- [ ] **Step 1: Overwrite `skills/data-management/frictionless.md`** with exactly this content:

```markdown
---
name: data-management-frictionless
description: Use when authoring or validating a datapackage.json descriptor — its resources, schemas, field types, and validation. Defines the Frictionless descriptor format for files in data and result directories.
archetype: normative-reference
sources: [frictionless-spec, frictionless]
---

# Frictionless Data Package Contract

Answers: what must a `datapackage.json` descriptor mean or contain?

## Scope

The `datapackage.json` descriptor **format** for files in `data/raw/`,
`data/processed/`, or result-package directories: resources, schemas, field
types, and validation. Excludes the on-disk directory and result-package
**layout** (see [`conventions.md`](conventions.md)) and the data-acquisition
workflow (see [`acquisition.md`](acquisition.md)).

Load this after downloading raw data, before connecting data to a pipeline or
notebook, when validating schema conformance, or when documenting dataset
structure for reproducibility.

## Vocabulary / schema / enums

A **Data Package** is a `datapackage.json` file describing one or more data
**resources** (files) with their schemas, formats, and metadata. A **resource**
describes a single data file: its path, format, schema (field names, types,
constraints), and encoding.

Use these Frictionless field types:

| Type | Python equivalent | Use for |
|---|---|---|
| `string` | `str` | text, identifiers, categories |
| `number` | `float` | measurements, continuous values |
| `integer` | `int` | counts, indices |
| `boolean` | `bool` | flags |
| `date` | `datetime.date` | dates without time |
| `datetime` | `datetime.datetime` | timestamps |
| `array` | `list` | JSON arrays |
| `object` | `dict` | JSON objects |

## Invariants

- A `datapackage.json` is a **runtime/package descriptor** for files that exist
  on disk — it is **not** the durable `dataset:<slug>` entity lifecycle. For the
  entity lifecycle and data-root policy, see [`acquisition.md`](acquisition.md)
  and [`conventions.md`](conventions.md).
- Every `resource` describes a file that exists at its `path`.
- A resource `schema` matches the actual file's columns and types.
- Required fields declare their constraints; missing-value tokens are declared
  where the data uses them.

## Conformance rules

```bash
# Validate a runtime data package (built-in lightweight checks)
science datasets validate --path data/raw/

# For deeper validation, install the frictionless CLI separately: uv add frictionless
frictionless validate data/raw/datapackage.json
```

Common validation errors:

- **Missing values** in required fields — add `missingValues: ["", "NA", "N/A"]` to the resource.
- **Type errors** — check whether auto-detected types are correct.
- **Extra/missing columns** — update the schema to match the actual file.

When a `datapackage.json` exists and an inquiry is active, map resource fields to
inquiry variables in `entities/datasets/<slug>.md` and document any
transformations needed (unit conversions, normalization, filtering).

## Examples

**Option A — auto-describe from existing files:**

```bash
frictionless describe data/raw/observations.csv --json > data/raw/datapackage.json
```

Review and edit the generated descriptor — auto-detection may mis-type fields.

**Option B — write manually:**

```json
{
  "name": "project-raw-data",
  "title": "Raw Data for <Project>",
  "description": "Downloaded from <source> on <date>",
  "licenses": [{"name": "CC-BY-4.0", "path": "https://creativecommons.org/licenses/by/4.0/"}],
  "resources": [
    {
      "name": "observations",
      "path": "observations.csv",
      "format": "csv",
      "encoding": "utf-8",
      "schema": {
        "fields": [
          {"name": "sample_id", "type": "string", "constraints": {"required": true}},
          {"name": "gene", "type": "string"},
          {"name": "expression", "type": "number"},
          {"name": "condition", "type": "string", "constraints": {"enum": ["control", "treated"]}}
        ],
        "primaryKey": "sample_id"
      }
    }
  ]
}
```

**Provenance** — add a `sources` field to track where data came from:

```json
{
  "name": "processed-data",
  "sources": [
    {"title": "GEO GSE12345", "path": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE12345"},
    {"title": "Downloaded via science", "path": "science datasets download geo:GSE12345"}
  ],
  "resources": []
}
```

## Versioning / migration

The Frictionless Data Package specification governs the descriptor format; this
contract tracks the fields Science's `science datasets validate` checks.
Directory and result-package **layout** is versioned separately in
[`conventions.md`](conventions.md).

## Invalid cases

- A `datapackage.json` whose `resources` reference files that do not exist.
- A required field with unhandled missing values (no `missingValues`).
- A `schema` whose fields do not match the actual file's columns.
- Using a `datapackage.json` descriptor as if it were the durable
  `dataset:<slug>` entity (the two are distinct — see *Invariants*).

## Success test

Is there an explicit conformance check? `science datasets validate --path <dir>`
(built-in) or `frictionless validate <dir>/datapackage.json` (deeper) passes
against the described files.

## Companion Skills

- `../INDEX.md` — the skill index.
- [`conventions.md`](conventions.md) — the directory/result layout that these descriptors describe.
- [`acquisition.md`](acquisition.md) — the acquisition workflow that produces these descriptors.
- [`../research-package/research-package-spec.md`](../research-package/research-package-spec.md) - Frictionless descriptor conventions reused by research packages.
- [`../pipelines/snakemake.md`](../pipelines/snakemake.md) - workflow rules that generate package descriptors as terminal artifacts.
```

- [ ] **Step 2: Verify the reshape and lint** (run from the worktree root; `rg` per repo convention):

```bash
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
# all 9 normative-reference headings, template order:
rg -n '^## (Scope|Vocabulary / schema / enums|Invariants|Conformance rules|Examples|Versioning / migration|Invalid cases|Success test|Companion Skills)$' skills/data-management/frictionless.md
# duplicated directory-conventions block gone (fail-closed):
rg -q '^## Directory Conventions$' skills/data-management/frictionless.md && { echo "FAIL: directory-conventions block still present"; exit 1; } || echo "OK: directory-conventions block removed"
# operational dataset-CLI command lines gone (fail-closed):
rg -q 'science dataset (add|verify-access|link) ' skills/data-management/frictionless.md && { echo "FAIL: operational CLI content still present"; exit 1; } || echo "OK: operational CLI content removed"
# companion retargeted off the router:
rg -q '\]\(SKILL\.md\)' skills/data-management/frictionless.md && { echo "FAIL: still links to SKILL.md"; exit 1; } || echo "OK: no SKILL.md companion"
cd "$ROOT/science" && uv run --frozen science skills lint --root ../skills
```
Expected: the 9 headings print; all three OK lines print; `skills lint` exit 0.

- [ ] **Step 3: Commit.**

```bash
git add skills/data-management/frictionless.md
git commit -m "refactor(skills): reshape frictionless.md to a format-only normative reference"
```

---

### Task 6: Reconcile both doctrine files and regenerate the codex mirror

Update `skill-authoring.md` and `skill-taxonomy.md` to "one hub remains (`pipelines/`)", record the data-management extraction, and drop `frictionless` from the remaining-splits list. Regenerate the codex mirror (green gate).

**Files:**
- Modify: `skills/meta/skill-authoring.md` (lines ~39, ~44)
- Modify: `skills/meta/skill-taxonomy.md` (lines ~111, ~112)
- Regenerate (do not hand-edit): `codex-skills/science-skill-development/skill-authoring.md`, `codex-skills/science-skill-development/skill-taxonomy.md`

**Interfaces:**
- Consumes: `scripts/generate_codex_skills.py`; the committed-mirror test `science/tests/test_codex_skills.py::test_committed_codex_skills_match_fresh_generation`.

- [ ] **Step 1: Edit `skills/meta/skill-authoring.md`.**
  - Line ~44 (router-invariant paragraph): change `2 of 14 current `SKILL.md` files are still **hubs** (route + teach) — `data-management/SKILL.md` and `pipelines/SKILL.md`.` → `1 of 14 current `SKILL.md` files is still a **hub** (route + teach) — `pipelines/SKILL.md`.` Add a dated sentence: "`data-management/SKILL.md` was extracted to a router on 2026-07-22 into `data-management-conventions` (normative-reference) and `data-management-acquisition` (practice-guide), with `frictionless.md` reshaped to the format-only descriptor reference."
  - Line ~39 (phase-4 work list): change "the `frictionless`/`mutational-signatures` splits" → "the `mutational-signatures` split".

- [ ] **Step 2: Edit `skills/meta/skill-taxonomy.md`.**
  - Line ~112: change "Two hubs remain (`data-management/`, `pipelines/`)" → "One hub remains (`pipelines/`)" and append that `data-management/` was extracted on 2026-07-22 into `data-management-conventions` and `data-management-acquisition`.
  - Line ~111: change "`frictionless`/`mutational-signatures` splits remain (phase 4)" → "the `mutational-signatures` split remains (phase 4)".

- [ ] **Step 3: Confirm the committed mirror is now stale (RED before regen).**

Run:
```bash
cd science && uv run --frozen pytest tests/test_codex_skills.py::test_committed_codex_skills_match_fresh_generation -q
```
Expected: FAIL — the committed `codex-skills/science-skill-development/{skill-authoring.md,skill-taxonomy.md}` no longer match fresh generation.

- [ ] **Step 4: Regenerate the mirror and assert the changed-file set is EXACTLY the two doctrine resources.**

```bash
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT/science" && uv run --frozen python ../scripts/generate_codex_skills.py
cd "$ROOT"
changed=$(git status --porcelain codex-skills/ | sed 's/^...//' | sort)
expected=$(printf '%s\n' \
  codex-skills/science-skill-development/skill-authoring.md \
  codex-skills/science-skill-development/skill-taxonomy.md | sort)
[ "$changed" = "$expected" ] || { echo "UNEXPECTED codex-skills change set:"; echo "$changed"; exit 1; }
echo "OK: exactly the two doctrine mirror files changed"
```
Expected: "OK: exactly the two doctrine mirror files changed" (proves no data-management leaf was mirrored — a content-grep for the leaf names cannot prove this, since Steps 1–2 deliberately write those names into the doctrine resources).

- [ ] **Step 5: Green gate — MANDATORY full suite + skills lint.**

Both are required before the final commit — the full `pytest` is not optional.

```bash
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT/science"
uv run --frozen science skills lint --root ../skills   # must exit 0
uv run --frozen pytest                                 # must exit 0 (whole suite)
```
The full suite may exceed the 2-minute default; run it with an extended timeout or in the background and wait for completion. Expected: `skills lint` exit 0; `pytest` exit 0. This slice touches no Python, so a green base suite stays green; if any failure appears, prove it is pre-existing (unchanged file vs merge-base) before proceeding — do not commit over a red suite.

- [ ] **Step 6: Commit.**

```bash
git add skills/meta/skill-authoring.md skills/meta/skill-taxonomy.md codex-skills/science-skill-development/skill-authoring.md codex-skills/science-skill-development/skill-taxonomy.md
git commit -m "docs(skills): reconcile doctrine to one remaining hub; regenerate codex mirror"
```

---

### Task 7: Re-home three stale content-guard tests to the extracted leaves

**Discovered during Task 6's green gate** (the plan's "touches no Python, stays green" assumption was wrong): three pre-existing content-guard tests assert that guidance lives in the *old* files. The slice moved that guidance to its new correct homes, so the guards now fail on base-slice. Base `main` is green on all three; the failures are slice-caused. Fix (user-approved approach: **re-home, preserve strength**): point each guard at the content's new home, keep every assertion, and restore the exact guarded literal into the leaf where a reword made it a non-match — never weaken or delete an assertion.

The three tests (unchanged on disk by Tasks 1–6):
- `science/tests/test_codex_skills.py::test_data_skills_document_configured_data_root` — asserts the data-root policy tokens in `frictionless.md` (moved → `conventions.md`) and `snakemake.md` (unchanged).
- `science/tests/test_command_docs.py::test_data_skill_routes_new_sources_through_dataset_entity_lifecycle` — asserts the dataset-entity lifecycle CLI in `SKILL.md` (moved → `acquisition.md`).
- `science/tests/test_command_docs.py::test_frictionless_skill_distinguishes_datapackages_from_dataset_entities` — asserts a `## Boundary With Dataset Entities` section in `frictionless.md` (section dissolved; distinction kept as an Invariant; operational CLI moved → `acquisition.md`).

NOTE: `science/tests/test_user_guide_docs.py:71` also asserts `Never commit files under the resolved data root` but reads a **different** (user-guide) file — it is unaffected; do NOT touch it. No other tests reference the phrases changed below.

**Files:**
- Modify (leaf wording — restore guarded literals): `skills/data-management/conventions.md`, `skills/data-management/acquisition.md`
- Modify (re-home guards): `science/tests/test_codex_skills.py`, `science/tests/test_command_docs.py`

**Interfaces:**
- Consumes: `conventions.md`/`acquisition.md`/`frictionless.md` as produced by Tasks 1–5.

- [ ] **Step 1: Restore the capitalized, single-line data-root literal in `conventions.md`.** The guard needs `Never commit files under the resolved data root` **contiguous on one line** (currently lowercase and line-wrapped). Replace exactly:

```
- Respect `SCIENCE_DATA_ROOT` and `science.yaml` `data.root`; never commit files
  under the resolved data root.
```
with:
```
- Respect `SCIENCE_DATA_ROOT` and `science.yaml` `data.root`.
- Never commit files under the resolved data root.
```

- [ ] **Step 2: Restore two guarded literals in `acquisition.md`.**

  (a) Make `Manual template authoring is a fallback` appear verbatim (capital M, one line). Replace exactly:
```
- **CLI first, manual template as fallback.** Use `science dataset add` /
```
with:
```
- **Prefer the CLI.** Manual template authoring is a fallback. Use `science dataset add` /
```

  (b) Un-backtick both `runtime `datapackage` descriptors` occurrences so the plain literal `runtime datapackage descriptors` matches. Replace exactly `Create or update runtime `datapackage` descriptors` with `Create or update runtime datapackage descriptors`, and `Current runtime `datapackage` descriptors` with `Current runtime datapackage descriptors`.

- [ ] **Step 3: Re-home `test_data_skills_document_configured_data_root`** (`science/tests/test_codex_skills.py`) — change the first file read from `frictionless.md` to `conventions.md`; keep every assertion. New body:

```python
def test_data_skills_document_configured_data_root() -> None:
    conventions = (ROOT / "skills/data-management/conventions.md").read_text(encoding="utf-8")
    snakemake = (ROOT / "skills/pipelines/snakemake.md").read_text(encoding="utf-8")
    for text in (conventions, snakemake):
        assert "SCIENCE_DATA_ROOT" in text
        assert "data.root" in text
        assert "Never commit files under the resolved data root" in text
```

- [ ] **Step 4: Re-home `test_data_skill_routes_new_sources_through_dataset_entity_lifecycle`** (`science/tests/test_command_docs.py`) — change ONLY the read path from `SKILL.md` to `acquisition.md`; every other assertion is unchanged and holds against `acquisition.md` (verified: the `--license`-not-in-add-example slice, the `--source-url` vs `--source` negatives, and all positive tokens). Replace exactly:

```python
    text = _read("skills/data-management/SKILL.md")

    assert "science dataset add <slug>" in text
```
with:
```python
    text = _read("skills/data-management/acquisition.md")

    assert "science dataset add <slug>" in text
```

- [ ] **Step 5: Re-home `test_frictionless_skill_distinguishes_datapackages_from_dataset_entities`** (`science/tests/test_command_docs.py`) — the `## Boundary With Dataset Entities` section was intentionally dissolved; the semantic distinction is now an Invariant in `frictionless.md` and the operational lifecycle CLI moved to `acquisition.md`. Preserve every guard, re-homed; the distinction assertion asserts the leaf's **more precise** approved phrase (`the durable `dataset:<slug>` entity lifecycle`) — stronger than the old `not the local dataset entity lifecycle`, not weaker. Replace the whole function body:

```python
def test_frictionless_skill_distinguishes_datapackages_from_dataset_entities() -> None:
    text = _read("skills/data-management/frictionless.md")

    boundary = _slice_between(
        text,
        "## Boundary With Dataset Entities",
        "## Creating a Data Package",
    )

    assert "runtime/package descriptor" in boundary
    assert "not the local dataset entity lifecycle" in boundary
    assert "Use `science dataset add <slug>`" in boundary
    assert "science dataset verify-access <slug>" in boundary
    assert "science datasets validate --path data/raw/" in boundary
```
with:
```python
def test_frictionless_skill_distinguishes_datapackages_from_dataset_entities() -> None:
    # After the router/leaf reshape, the datapackage-vs-entity distinction lives in
    # frictionless.md's Invariants; the operational dataset-entity lifecycle CLI
    # moved to acquisition.md. Both guards are preserved, re-homed to where the
    # content now lives.
    frictionless = _read("skills/data-management/frictionless.md")
    assert "runtime/package descriptor" in frictionless
    assert "the durable `dataset:<slug>` entity lifecycle" in frictionless
    assert "science datasets validate --path data/raw/" in frictionless

    acquisition = _read("skills/data-management/acquisition.md")
    assert "science dataset add <slug>" in acquisition
    assert "science dataset verify-access <slug>" in acquisition
```

- [ ] **Step 6: Verify — the three tests pass, no leaf mirrored, and the FULL suite + lint are green.**

```bash
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT/science"
# the three re-homed guards pass:
uv run --frozen pytest \
  "tests/test_codex_skills.py::test_data_skills_document_configured_data_root" \
  "tests/test_command_docs.py::test_data_skill_routes_new_sources_through_dataset_entity_lifecycle" \
  "tests/test_command_docs.py::test_frictionless_skill_distinguishes_datapackages_from_dataset_entities" -q
# leaf edits are NOT mirrored — codex-skills must be untouched (fail-closed):
cd "$ROOT"
[ -z "$(git status --porcelain codex-skills/)" ] && echo "OK: codex-skills unchanged" || { echo "FAIL: codex-skills changed"; git status --porcelain codex-skills/; exit 1; }
# MANDATORY full suite + lint:
cd "$ROOT/science"
uv run --frozen science skills lint --root ../skills   # must exit 0
uv run --frozen pytest                                 # must exit 0 (WHOLE suite)
```
Expected: the three named tests pass; `OK: codex-skills unchanged`; `skills lint` exit 0; full `pytest` exit 0 (0 failed). Run the full suite with an extended timeout (600000 ms) or in the background and wait. Do NOT commit over any remaining failure.

- [ ] **Step 7: Commit.**

```bash
git add skills/data-management/conventions.md skills/data-management/acquisition.md science/tests/test_codex_skills.py science/tests/test_command_docs.py
git commit -m "test(skills): re-home data-management content guards to the extracted leaves"
```

---

## Final whole-branch review checklist (for the reviewer)

- Router carries no methodology (no Principles/conventions/manifest/runbook sections); keeps the specialized-bio routing; frontmatter `provenance: internal`, no `sources:`.
- Leaf 1 carries all 8 normative-reference slots; `results/` is version-controlled/project-root-relative (never tied to the resolved data root); workflow-result vs research-package artifacts are distinct with correct authorities; no `workflow`/`entities`/`provenance` manifest custom-block claim; `sources: [edam]`.
- Leaf 2 carries all 8 practice-guide slots; manual fallback targets the resolved data root; `provenance: internal`.
- `frictionless.md` has all 8 normative-reference slots incl. the three previously missing; no `## Directory Conventions` block; no operational `science dataset` command lines; `:152` companion retargeted.
- All 7 conventions-content refs retargeted (label+href); the 5 router/neighbor refs untouched; all 20 `frictionless.md` occurrences unchanged.
- Both doctrine files agree: **one hub remains (`pipelines/`)**; no `data-management/` hub; no `frictionless` split listed.
- Codex mirror: exactly the two doctrine files changed; new leaves absent from `codex-skills/`; `test_codex_skills.py` + full `pytest` + `skills lint` green.
- Corpus: 42 → 44 structural leaves; both new leaves INDEX-covered; routers/`INDEX.md` carry no `archetype:`.
- Task 7: the three content guards re-homed (not deleted/weakened) — each still asserts its tokens, against the file where the content now lives; the two restored leaf literals (`Never commit files under the resolved data root`, `Manual template authoring is a fallback`, plus un-backticked `runtime datapackage descriptors`) are present and single-line; `test_user_guide_docs.py` untouched; full `pytest` 0 failed.
