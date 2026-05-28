# Pipeline Audit & Refactor Playbook — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the project-agnostic "pipeline audit & refactor" playbook plus the small data-QA convention expansion and cross-links specified in the approved design.

**Architecture:** A documentation-only change. The playbook (the reusable "how") is a new process doc with embedded report skeletons; the data-QA convention gains one table-shaped structural check (registry/enum); three existing docs gain cross-links. No code, so each task's "test" is a concrete verification (target files/anchors exist, code references match the real source, format matches house style) rather than a unit test.

**Tech Stack:** Markdown docs under `docs/`. Verification via `test`/`grep`/`rg` in `zsh`. Repo root: `/mnt/ssd/Dropbox/science`.

**Source of truth:** The approved design `docs/plans/2026-05-28-pipeline-audit-and-refactor-design.md` contains the verbatim substance for the playbook's narrative sections. Where a task says "render design §N," reproduce that section's content adapted from spec voice ("this design specifies…") to playbook voice ("do this…"); the must-include points are listed so the rendering is unambiguous. Novel content not in the design (report skeletons, the convention edit, cross-links) is given verbatim below.

---

## File Structure

- **Create** `docs/process/pipeline-audit-and-refactor.md` — the playbook. One doc, sibling to `adding-a-domain.md`. Sections: Purpose → Organizing insight (incl. axis-1 scope caveat) → Artifact placement → Method (Phases 0–3) → Three axis rubrics → Deferred disciplines (analysis/result-QA, workflow/DAG-validation) → Embedded report skeletons → See also.
- **Modify** `docs/conventions/pipeline-qa-checkpoints.md` — add the registry/enum structural check (prose at the structural-checks paragraph + one line in the config skeleton) and a See-also link to the playbook.
- **Modify** `aspects/computational-analysis/computational-analysis.md` — one cross-link to the playbook in the `review-pipeline` section.
- **Modify** `docs/project-organization-profiles.md` — one cross-link to the playbook in the existing **Pipeline Data-QA** section.

No index/README updates: `docs/process/` has no README, and no top-level docs index enumerates process docs (verified). The convention README already indexes `pipeline-qa-checkpoints.md`; the registry/enum addition does not warrant a new index line.

---

## Task 1: Create the playbook — front matter, purpose, organizing insight, placement, method

**Files:**
- Create: `docs/process/pipeline-audit-and-refactor.md`

- [ ] **Step 1: Write the doc heading + Purpose + Organizing insight + Artifact placement + Method.**

Create the file with this exact top matter and structure. Render the narrative from the design as noted.

````markdown
# Pipeline Audit & Refactor — a three-axis playbook

This playbook gives science projects a repeatable method to **audit and refactor their data
pipelines along three axes**, in a single pass per data source:

1. **Data QA** — every table analysis consumes has a wired-in QA/sanity step (per
   [`../conventions/pipeline-qa-checkpoints.md`](../conventions/pipeline-qa-checkpoints.md)).
2. **Consistency, organization, code quality / reuse.**
3. **Data portability** — reusable "base" ingestion+cleaning is disentangled from project-specific
   processing, and clean base datasets are promoted to the shared commons.

## The organizing insight — the "clean base table" boundary

<!-- Render design §2 in playbook voice. MUST include, verbatim in substance: -->
<!-- - The three axes converge on one boundary: the clean base table (after ingest+source cleaning,
       good metadata, before project-specific processing). -->
<!-- - That boundary is at once: a substrate axis 1 must validate; the seam axis 2 wants factored;
       the unit axis 3 promotes. -->
<!-- - The core move per source: isolate -> QA -> promote the clean base table; one refactor pays
       off on all three axes. -->
<!-- - SCOPE CAVEAT (load-bearing): the clean base table is ONE QA substrate, not the only one.
       The data-QA convention validates EVERY table analysis consumes; clean-base QA does NOT
       satisfy final-analysis-table QA. The "one boundary" framing is about the refactor move, not
       QA coverage. -->

## Artifact placement — upstream vs downstream

<!-- Render design §3 in playbook voice. MUST include: -->
<!-- - Upstream (science repo, reusable): this playbook + its embedded report skeletons. -->
<!-- - Downstream (target project): filled-in inventory / findings / synthesis + refactor tasks,
       under the project's audits dir in a pipeline-refactor/ subdir (mm30: doc/audits/pipeline-refactor/).
       Follow the project's doc/ vs docs/ convention; no new top-level dir. -->
<!-- - In-project filenames collapse to inventory.{md,json}, findings.md, synthesis.md (the
       per-project qualifier is unneeded inside the project repo). -->
<!-- - Two things still flow upstream: convention nominations (a doc PR to science/docs/conventions/)
       and commons promotions (via the registry; see the axis-3 procedure). -->

## Method

The unit of work is the **data-source chain**:
`external source → ingest → clean/normalize → clean base table → project-specific downstream`.
Each chain is swept on all three axes in one pass.

<!-- Render design §4 Phases 0-3 in playbook voice. MUST include: -->
<!-- Phase 0 Inventory -> pipeline-refactor/inventory.{md,json}. -->
<!-- Phase 1 per-chain sweep (all 3 axes) -> pipeline-refactor/findings.md, one section per chain,
     each finding carrying a disposition (fix-now / backlog / promote / flagged-optional / leave). -->
<!-- Phase 2 synthesis & backlog -> pipeline-refactor/synthesis.md, incl. a "convention nominations"
     subsection; triage into tasks in the project's task system. -->
<!-- Phase 3 execute & guard: TDD; axis-1 fixes land as structural regression-guard checks;
     axis-3 promotions follow the multi-step procedure in the axis-3 rubric, not one command. -->
````

- [ ] **Step 2: Verify the file exists and the section skeleton is complete.**

Run:
```bash
cd /mnt/ssd/Dropbox/science
test -f docs/process/pipeline-audit-and-refactor.md && \
grep -c '^## ' docs/process/pipeline-audit-and-refactor.md
```
Expected: exit 0 and a count of `3` — the three `## ` headings created in this task: "The organizing insight", "Artifact placement", "Method". (Purpose sits under the H1 with no `##`; more `##` headings are added in Tasks 2–3.) If the count differs, recount your headings.

- [ ] **Step 3: Verify no HTML render-comment leaks remain as content.**

The `<!-- … -->` blocks are *authoring directives* — they must be replaced by real prose, not committed. Run:
```bash
grep -n '<!--' docs/process/pipeline-audit-and-refactor.md || echo "OK: no directive comments left"
```
Expected: `OK: no directive comments left`. If any remain, you left a directive un-rendered — write the prose.

- [ ] **Step 4: Commit.**

```bash
cd /mnt/ssd/Dropbox/science
git add docs/process/pipeline-audit-and-refactor.md
git commit -m "docs(process): scaffold pipeline audit & refactor playbook (purpose, insight, method)"
```

---

## Task 2: Playbook — the three axis rubrics + deferred disciplines

**Files:**
- Modify: `docs/process/pipeline-audit-and-refactor.md`

- [ ] **Step 1: Append the axis-rubrics section.**

Append after the `## Method` section. Render design §5 in playbook voice. The MUST-include content per axis:

````markdown
## The three axis rubrics

Each axis scores PASS / WARN / FAIL per sub-dimension; attach a disposition to every finding.

### Axis 1 — Data QA

- A **wired-in** data-QA step (own pipeline rule on the default target) for **every table analysis
  consumes**: the clean base table **and** each project-specific analysis table produced downstream.
  Clean-base QA does **not** satisfy final-table QA (see the scope caveat above). One QA step per
  substrate, per [`../conventions/pipeline-qa-checkpoints.md`](../conventions/pipeline-qa-checkpoints.md).
- Each QA step splits **structural** (build-fatal) vs **distribution** (surfaced-not-fatal) flags.
- Bounds / allowed-codes / sentinels are **config-driven** and shared with the cleaning step.
- **Existing post-hoc checks:** which manual / pytest-only QA scripts should become wired-in
  structural checks on a built table?
- **Companion DAG-validation check (NOT table-QA):** is each pipeline output produced by exactly one
  rule, with no orphaned/duplicately-owned outputs? This is a **workflow/DAG-level** structural
  checkpoint scored alongside data-QA but explicitly *outside* the table-QA convention (it inspects
  the rule graph, not a table). See "Deferred disciplines" below.

Rubric reuses the `review-pipeline` → **QA Coverage** dimension (incl. its severity-split row), plus
the DAG-validation check as its own line. Disposition: a missing structural check on an
already-fixed bug → **fix-now** (regression-guard); missing distribution checks → **backlog**.

### Axis 2 — Consistency, organization, code quality / reuse

- **Naming & layout** consistency across chains (e.g. `workflows/` vs `scripts/` vs an unused
  `code/`; config sprawl; versioned-config drift like `v8` / `v8.1`).
- **Config-driven over hardcoded:** flag scripts bypassing config with hardcoded data paths.
- **Duplication → shared helpers:** repeated datapackage boilerplate, effect-size/association logic,
  decode logic wanting a shared module.
- **Code → task back-links** per [`../conventions/code-task-backlinks.md`](../conventions/code-task-backlinks.md).

Disposition: extract helper / consolidate config / add back-links → **backlog** (mechanical,
TDD-guarded). **Package consolidation** (flat `scripts/` + `sys.path` hacks → an installable
package) is an **optional flagged finding**, never a default recommendation.

### Axis 3 — Data portability / commons

Per source: is the **base ingestion + cleaning** (clean state + good metadata, no project-specific
processing) **disentangled** from downstream?

- Entangled → refactor task to **split the chain at the clean-base-table boundary** (the same
  boundary axis 1 QAs — do them together).
- Cleanly factored → is the clean base dataset (with `datapackage.json`) **promoted to the commons**?

Rubric: **PASS** (base separated *and* promoted) / **WARN** (separated, not promoted — includes "no
dataset entity yet") / **FAIL** (entangled).

**Promotion procedure (not a one-liner).** `science commons promote dataset` sources from the
project's dataset entity descriptors (`doc/datasets/data-<slug>.md`), requires `--slug`, and selects
the source project with `--from <project-id>`. So promotion has prerequisites that are themselves
refactor tasks:

1. **Create / verify the dataset entity** at `doc/datasets/data-<slug>.md` with the required
   `mixin-dataset-1.0` fields and a `datapackage:` pointer to the clean base table's `datapackage.json`.
2. **Dry-run** `science commons promote dataset --from <project-id> --slug <slug>` and inspect the plan.
3. **Apply** with `--apply` (add `--mixin <bio.*>` where a bio extension matches the dataset modality).

## Deferred disciplines (named, not specified here)

This playbook **names** two related disciplines and **nominates** each as a future convention, but
does not specify them:

- **Analysis / result-QA** — validates *results*, not the input table: leave-one-out /
  dataset-dropout stability; permutation / empirical-null calibration and assumption sweeps.
- **Workflow / DAG-validation** — validates the *rule graph*, not a table: output-ownership / dedup
  (each output produced by exactly one rule). Deliberately kept out of the table-QA convention,
  whose contract is "one script + one rule reads the built table" and which cannot see DAG structure.

Surface both during the sweep so they are not forgotten; writing either convention is a separate
decision recorded in the synthesis "convention nominations".
````

- [ ] **Step 2: Verify the three axes and deferred section are present.**

Run:
```bash
cd /mnt/ssd/Dropbox/science
grep -nE '^### Axis [123] —|^## Deferred disciplines' docs/process/pipeline-audit-and-refactor.md
```
Expected: four lines — Axis 1, Axis 2, Axis 3, and Deferred disciplines.

- [ ] **Step 3: Verify the commons CLI reference is accurate against the source.**

The procedure must match the real CLI. Run:
```bash
cd /mnt/ssd/Dropbox/science
grep -n 'source_subdirs=("doc/datasets",)\|filename_prefix="data-"' science/src/science_tool/commons/promote.py
grep -n 'required=True' science/src/science_tool/commons/cli.py | head
```
Expected: the `promote.py` line confirms `doc/datasets` + `data-` prefix; `cli.py` confirms `--slug required=True`. If these no longer match, update the playbook procedure to match the source.

- [ ] **Step 4: Commit.**

```bash
cd /mnt/ssd/Dropbox/science
git add docs/process/pipeline-audit-and-refactor.md
git commit -m "docs(process): add three-axis rubrics + deferred disciplines to playbook"
```

---

## Task 3: Playbook — embedded report skeletons + See also

**Files:**
- Modify: `docs/process/pipeline-audit-and-refactor.md`

- [ ] **Step 1: Append the report skeletons and See also.**

Append after "Deferred disciplines". These are verbatim (not in the design doc):

`````markdown
## Report skeletons (copy into the target project)

Copy these into the project's audits area (`<doc-or-docs>/audits/pipeline-refactor/`).

### `inventory.md` — one row per data-source chain

````markdown
# Pipeline inventory — <project>

| Chain | Source | Ingest rule(s) | Clean base table | Base config | Project-specific downstream |
| --- | --- | --- | --- | --- | --- |
| <name> | <external source> | <rule(s)> | <path to clean table> | <config key/file> | <consumers> |
````

A machine-readable `inventory.json` mirrors the table: a list of objects with keys
`chain, source, ingest_rules[], clean_base_table, base_config, downstream[]`.

### `findings.md` — one section per chain

````markdown
# Pipeline audit findings — <project>

## Chain: <name>

- **Axis 1 — Data QA:** PASS / WARN / FAIL — <notes>
  - substrates with a wired-in QA step: clean base [y/n]; <downstream tables…> [y/n]
  - companion DAG-validation (output-ownership): PASS / WARN / FAIL
- **Axis 2 — Consistency/quality:** PASS / WARN / FAIL — <notes>
- **Axis 3 — Portability/commons:** PASS / WARN / FAIL — base separated [y/n]; promoted [y/n]

### Findings
| # | Axis | Finding | Severity | Disposition | Task |
| --- | --- | --- | --- | --- | --- |
| 1 | 1/2/3 | <what> | structural / distribution / quality | fix-now / backlog / promote / flagged-optional / leave | <task-id> |
````

### `synthesis.md` — roll-up across chains

````markdown
# Pipeline audit synthesis — <project>

## Prioritized refactor backlog
| Rank | Axis | Item | Chains affected | Effort | Task |
| --- | --- | --- | --- | --- | --- |

## Recurring anti-patterns
- <pattern> — <chains where it recurs>

## Convention nominations (upstream candidates)
| Candidate check | Kind (data-QA / analysis-result-QA / workflow-DAG) | Evidence (chains / bugs caught) | Proposed home |
| --- | --- | --- | --- |

## Commons promotion candidates
| Dataset | Entity exists? | Promoted? | Blocking prerequisites |
| --- | --- | --- | --- |
`````

````markdown
## See also

- [`../conventions/pipeline-qa-checkpoints.md`](../conventions/pipeline-qa-checkpoints.md) — the
  axis-1 (data-QA) convention this playbook audits against.
- [`../conventions/code-task-backlinks.md`](../conventions/code-task-backlinks.md) — axis-2 code→task
  back-link patterns.
- [`../../aspects/computational-analysis/computational-analysis.md`](../../aspects/computational-analysis/computational-analysis.md)
  — `plan-pipeline` / `review-pipeline` QA sections.
- `science commons promote dataset` (`science/src/science_tool/commons/promote.py`) — the axis-3 endpoint.
- [`../plans/2026-05-28-pipeline-audit-and-refactor-design.md`](../plans/2026-05-28-pipeline-audit-and-refactor-design.md)
  — the design this playbook implements.
````

- [ ] **Step 2: Verify all relative links in the playbook resolve.**

Run this link-resolver (extracts `](relative)` targets, strips anchors, checks each exists relative to `docs/process/`):
```bash
cd /mnt/ssd/Dropbox/science/docs/process
rg -o '\]\(([^)]+)\)' -r '$1' pipeline-audit-and-refactor.md | grep -v '^http' | sed 's/#.*//' | sort -u | while read -r p; do
  [ -z "$p" ] && continue
  test -e "$p" && echo "OK  $p" || echo "BROKEN  $p"
done
```
Expected: every line begins `OK`. Any `BROKEN` line is a wrong relative path — fix it. (Targets include `../conventions/pipeline-qa-checkpoints.md`, `../conventions/code-task-backlinks.md`, `../../aspects/computational-analysis/computational-analysis.md`, `science/src/science_tool/commons/promote.py` via repo-root-relative — note that one is NOT relative to `docs/process/`; write it as the repo-root path in prose, not a markdown link, so it is excluded by being unparenthesised.)

- [ ] **Step 3: Re-verify no authoring directives leaked.**

```bash
cd /mnt/ssd/Dropbox/science
grep -n '<!--' docs/process/pipeline-audit-and-refactor.md || echo "OK: clean"
```
Expected: `OK: clean`.

- [ ] **Step 4: Commit.**

```bash
cd /mnt/ssd/Dropbox/science
git add docs/process/pipeline-audit-and-refactor.md
git commit -m "docs(process): add report skeletons + see-also to pipeline audit playbook"
```

---

## Task 4: Convention expansion — registry/enum structural check

**Files:**
- Modify: `docs/conventions/pipeline-qa-checkpoints.md` (structural-checks paragraph ~line 45; config skeleton ~line 76; See also ~line 132)

- [ ] **Step 1: Extend the structural-checks prose to cover a shared registry.**

Replace this exact text:
```
key, required columns present and complete, categorical values within an allowed set,
cross-field invariants (e.g. two flags that must be mutually exclusive), and guards against
```
with:
```
key, required columns present and complete, categorical values within an allowed set — or,
when that allowed set is a *shared data registry* the pipeline also consumes (e.g. a contrast or
code registry), the table's values validated as a subset of that registry so a single source of
truth governs both, cross-field invariants (e.g. two flags that must be mutually exclusive), and
guards against
```

- [ ] **Step 2: Add a registry line to the config skeleton.**

Replace this exact text:
```
  categoricals:
    stage: {allowed: [1, 2, 3, 4, 5]}      # structural: illegal code => bug
```
with:
```
  categoricals:
    stage:    {allowed: [1, 2, 3, 4, 5]}                       # structural: illegal code => bug
    contrast: {allowed_from: "registries/contrasts.csv#name"}  # structural: subset of a shared registry
```

- [ ] **Step 3: Add the playbook to the convention's See also.**

Read the current `## See also` list, then add this as the first bullet under it:
```
- [`../process/pipeline-audit-and-refactor.md`](../process/pipeline-audit-and-refactor.md) — the
  three-axis pipeline audit/refactor playbook; this convention is its axis-1 (data-QA) target.
```

- [ ] **Step 4: Verify the edits landed and YAML still parses.**

Run:
```bash
cd /mnt/ssd/Dropbox/science
grep -n 'shared data registry\|allowed_from: "registries/contrasts.csv\|pipeline-audit-and-refactor' docs/conventions/pipeline-qa-checkpoints.md
python3 -c "import yaml; yaml.safe_load('stage: {allowed: [1,2,3,4,5]}\ncontrast: {allowed_from: \"registries/contrasts.csv#name\"}'); print('yaml-ok')"
```
Expected: three grep hits (prose, skeleton, see-also) and `yaml-ok` (the two edited flow-mapping lines parse — confirming the `#` is treated as a literal in the quoted scalar, not a YAML comment).

- [ ] **Step 5: Commit.**

```bash
cd /mnt/ssd/Dropbox/science
git add docs/conventions/pipeline-qa-checkpoints.md
git commit -m "docs(conventions): add shared-registry/enum structural check to pipeline-qa-checkpoints"
```

---

## Task 5: Cross-links from the aspect and the profiles doc

**Files:**
- Modify: `aspects/computational-analysis/computational-analysis.md` (after the QA Coverage rubric, ~line 111)
- Modify: `docs/project-organization-profiles.md` (the Pipeline Data-QA section)

- [ ] **Step 1: Add a playbook pointer to the aspect's review-pipeline section.**

Replace this exact text:
```
Include QA Coverage as an additional row in the rubric results table.
```
with:
```
Include QA Coverage as an additional row in the rubric results table.

To audit and refactor an existing project's pipelines across QA, organization/code-quality, and data
portability in one pass, follow [`docs/process/pipeline-audit-and-refactor.md`](../../docs/process/pipeline-audit-and-refactor.md).
```

- [ ] **Step 2: Add a playbook pointer to the profiles' Pipeline Data-QA section.**

In `docs/project-organization-profiles.md`, append to the end of the **Pipeline Data-QA** paragraph
(the one ending `… See [`docs/conventions/pipeline-qa-checkpoints.md`](conventions/pipeline-qa-checkpoints.md).`):
```
 To audit and refactor existing pipelines across all three axes (QA, organization, portability), see [`docs/process/pipeline-audit-and-refactor.md`](process/pipeline-audit-and-refactor.md).
```

- [ ] **Step 3: Verify both cross-links resolve.**

Run:
```bash
cd /mnt/ssd/Dropbox/science
test -e docs/process/pipeline-audit-and-refactor.md && echo "target OK"
grep -n 'pipeline-audit-and-refactor' aspects/computational-analysis/computational-analysis.md docs/project-organization-profiles.md
# resolve the aspect's relative path explicitly:
( cd aspects/computational-analysis && test -e ../../docs/process/pipeline-audit-and-refactor.md && echo "aspect link OK" )
( cd docs && test -e process/pipeline-audit-and-refactor.md && echo "profiles link OK" )
```
Expected: `target OK`, one grep hit in each file, `aspect link OK`, `profiles link OK`.

- [ ] **Step 4: Commit.**

```bash
cd /mnt/ssd/Dropbox/science
git add aspects/computational-analysis/computational-analysis.md docs/project-organization-profiles.md
git commit -m "docs: cross-link pipeline audit playbook from aspect and project-organization-profiles"
```

---

## Task 6: Whole-set verification

**Files:** none (verification only)

- [ ] **Step 1: Confirm all four deliverable touchpoints exist and reference each other.**

Run:
```bash
cd /mnt/ssd/Dropbox/science
test -f docs/process/pipeline-audit-and-refactor.md && echo "playbook OK"
grep -lq 'pipeline-audit-and-refactor' docs/conventions/pipeline-qa-checkpoints.md && echo "convention link OK"
grep -lq 'pipeline-audit-and-refactor' aspects/computational-analysis/computational-analysis.md && echo "aspect link OK"
grep -lq 'pipeline-audit-and-refactor' docs/project-organization-profiles.md && echo "profiles link OK"
grep -lq 'shared data registry' docs/conventions/pipeline-qa-checkpoints.md && echo "registry check OK"
```
Expected: five `… OK` lines.

- [ ] **Step 2: Confirm no authoring directives or placeholders shipped in the playbook.**

```bash
cd /mnt/ssd/Dropbox/science
grep -nE '<!--|TBD|TODO|FIXME|<placeholder>' docs/process/pipeline-audit-and-refactor.md || echo "OK: no placeholders"
```
Expected: `OK: no placeholders`.

- [ ] **Step 3: Confirm the working tree is clean (everything committed).**

```bash
cd /mnt/ssd/Dropbox/science
git status --porcelain docs/process docs/conventions aspects/computational-analysis docs/project-organization-profiles.md
```
Expected: empty output.

---

## Self-Review notes (author)

- **Spec coverage:** design §1 deliverable → Tasks 1–5; §2 insight + caveat → Task 1; §3 placement → Task 1; §4 method → Task 1; §5 rubrics + axis-3 procedure → Task 2; §6 analysis/result-QA + §7 output-ownership-as-DAG → Task 2 "Deferred disciplines"; §7 registry/enum convention edit → Task 4; §9 cross-links → Tasks 3–5. Report skeletons (implied by §3/§4 "embedded skeletons") → Task 3.
- **Placeholder policy:** the `<!-- … -->` blocks in Tasks 1–2 are *authoring directives* keyed to verbatim design sections (the design doc is the committed source of truth); Step 3 of Task 1 and Step 3 of Task 3 fail the task if any survive into the committed doc. The `<…>` tokens inside the report skeletons are intentional fill-in fields of the template itself, not plan placeholders.
- **Reference consistency:** CLI facts (`doc/datasets`, `data-` prefix, `--slug`, `--from`, `--apply`, `mixin-dataset-1.0`) are checked against `promote.py` / `cli.py` in Task 2 Step 3 so the doc cannot drift from the source.
