# Downstream Project Audit: <PROJECT_NAME>

> Copy this template to `docs/audits/downstream-project-conventions/projects/<project>.md` and fill in. Replace placeholder lines with concrete observations or `N/A — see inventory §X` (with a one-line reason). The report is ready when every section is filled in or explicitly N/A-marked, and every row in the section-10 candidate table has at least one evidence path.

## Header

- **Project root:** `<absolute path>`
- **Project SHA at audit:** `<git rev-parse HEAD>`
- **Dirty tree summary:** `<one line: clean / N modified / N untracked>` (full porcelain in inventory)
- **Inventory artifact:** `docs/audits/downstream-project-conventions/inventory/<project>.json`
- **Science SHA used for comparators:** `<git rev-parse HEAD on this repo>`
- **Auditor / agent:** `<name or agent id>`
- **Audit date:** `YYYY-MM-DD`

## Known Starting Conditions

Pre-existing conditions surfaced from `docs/plans/2026-04-25-downstream-project-conventions-audit.md` "Known Starting Conditions" or discovered during inventory. List paths, not classifications — these are *not* findings.

- `<path or area>` — `<one-line description>`

---

## 1. Project Center Of Gravity

- **Primary shape:** `<research / software / content / pipeline / viewer / hybrid>`
- **Dominant tracked directories:** `<top 3-5 from inventory>`
- **Dominant untracked / symlinked directories:** `<from inventory>`
- **`science.yaml` profile / aspects:** `<value(s)>`
- **Does profile + aspects capture the real project?** `<yes / partial / no>` — `<reason>`
- **Multi-axis needed?** `<yes / no>` — `<reason>`

## 2. File And Directory Organization

For each subsection, classify each observation as one of: *recurring candidate convention*, *valid project-specific convention*, *accidental drift*, *stale or unclear convention*.

- **`doc/` taxonomy and naming:**
- **`docs/` vs `doc/`:**
- **`specs/` usage:**
- **`tasks/` layout and archival:**
- **`knowledge/` (generated vs source):**
- **Code locations (`src/` / `code/` / `scripts/` / `workflow(s)/` / notebooks / viewer apps):**
- **Data / results / log / model locations:**
- **Archive and migration directories:**

## 3. Entity Model And Metadata

Sampling floor: `min(5, all)` per entity family present, plus any inventory-flagged long-form (>300 lines) or embedded-metadata files. State explicitly when the floor cannot be met.

For each family present in the project, record sampled paths + observations.

- **Hypotheses:** `<sampled paths>` — `<observations>`
- **Propositions / claims:**
- **Questions:**
- **Papers:**
- **Topics / background:**
- **Datasets:**
- **Interpretations:**
- **Reports / syntheses:**
- **Plans / pre-registrations:**
- **Tasks:**
- **Project-specific entities (genes, mechanisms, models, lenses, descriptors, workflows, ...):**

Cross-cutting observations:

- **Missing entity families (clearly present in prose or paths):**
- **Duplicated information across entity types:**
- **Inconsistent `id` prefixes:**
- **Overloaded `type` / `status` / `phase` values:**
- **Fields that should likely be enums:**
- **Fields that should likely be structured objects, not strings:**
- **Inline information that should likely be metadata:**
- **Embedded entity metadata blocks inside long prose / plans:**
- **Inconsistent use of `related` / `datasets` / `source_refs` / `datapackage` / `local_path` / `consumed_by` / `produces`:**
- **External accession / ontology usage (HGNC, NCBI Gene, UniProt, GO, UBERON, OncoTree, PDB, Pfam, InterPro, GEO, PubMed, DOI, PMCID, arXiv):**

## 4. Planning, Pre-Registration, And Decision Records

For each artifact type present: where it lives, naming, has-metadata, links to other entities.

- **Implementation plans:**
- **Design / spec docs:**
- **Pre-registrations:** `<location: doc/pre-registrations/ | doc/meta/pre-registration-* | inline | other>`
- **Next-step / gap-analysis docs:**
- **Curation sweeps:**
- **Handoffs:**
- **Audit reports:**
- **Project roadmap / research plan files:**

## 5. Task Lifecycle

- **`tasks/active.md` shape:** `<observation>`
- **Done archive pattern:**
- **Completed tasks remaining in active files:** `<yes / no — paths>`
- **Task ID format:**
- **Status values observed:**
- **Use of `priority` / `aspects` / `group` / `related` / `blocked-by` / `created` / `completed`:**
- **Code, data, reports, interpretations link back to task IDs:** `<yes / partial / no>`
- **Are task groups a stable concept worth modeling:**
- **Do tasks contain enough provenance, or should they link to result entities:**

## 6. Code, Workflows, And Tests

- **Code root convention:**
- **Snakemake layout (if any):**
- **Script naming and grouping:**
- **Notebook placement:**
- **Tests colocated vs root:**
- **Generated model / schema code:**
- **Viewer / app subprojects:**
- **Config and environment files:**
- **Linkage from code artifacts to tasks / questions / hypotheses / datasets / plans:**
- **Would code artifacts benefit from lightweight metadata blocks or sidecar manifests?** `<yes / no / case-by-case>` — `<reason>`

## 7. Data, Results, And Provenance

For each pattern observed, classify as one of: *tracked source metadata only*, *tracked small public data*, *ignored raw payload with tracked descriptor*, *ignored generated output*, *symlinked external data root*, *protected/manual data requiring explicit instructions*, *unclear or risky tracking policy*.

- **Input data:**
- **Protected / manual data:**
- **Public downloadable data:**
- **Intermediate outputs:**
- **Final results:**
- **Logs:**
- **Models:**
- **Descriptors / sidecars:**
- **Datapackages:**
- **Symlinked external storage:**
- **`.gitignore` exceptions:**

- **Is source / provenance visible?** `<yes / partial / no>` — `<reason>`
- **Can publicly available data be reproduced through a pipeline?** `<yes / partial / no>` — `<reason>`

## 8. Validation And Managed Artifacts

Compare `validate.sh` against `templates/research/validate.sh` at the pinned Science SHA. Findings here flow into the managed-artifact-versioning plan; do *not* propose alternate update mechanisms.

- **Local modifications to `validate.sh`:**
- **Project-specific environment assumptions:**
- **Checks that likely belong upstream:** `<tag: mav-input>`
- **Checks that are correctly project-specific:**
- **Drift solvable by managed artifact versioning:** `<tag: mav-input>`
- **Drift NOT solvable by MAV (missing profile / schema / entity model):**

## 9. Project-Grown Conventions

For each: name, paths, classification (project-specific / useful for ≥2 projects / likely missing upstream support / worth a future design pass).

- `<convention>` — `<paths>` — `<classification>` — `<one-line note>`

Examples to look for: descriptor files, generated schema/model packages, report rollups, synthesis docs, curation ledgers, app/viewer resource layers, runpod/cloud execution notes, local ontology folders, data source overviews, method docs, issue folders, guide docs.

## 10. Candidate Upstream Changes

Every row needs at least one evidence path. Scope: `project-specific` / `recurring` / `upstream`. Priority: `low` / `medium` / `high`. Migration cost: `low` / `medium` / `high`.

| Candidate | Evidence | Scope | Priority | Migration Cost | Notes |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |
