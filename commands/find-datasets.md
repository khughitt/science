---
description: Discover and document candidate datasets for research or tool demos. Uses LLM knowledge + dataset repository search to find, rank, and document relevant public datasets.
---

# Find Datasets

Find candidate external datasets for `$ARGUMENTS`.
If no argument is provided, derive candidate search terms from active questions,
hypotheses, inquiry variables, and legacy specs only when those files exist;
then ask the user to confirm the focus.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `${CLAUDE_PLUGIN_ROOT}/skills/data/SKILL.md` for data management conventions.
2. If present, read `${CLAUDE_PLUGIN_ROOT}/skills/data/frictionless.md` for runtime Data Package guidance.
3. Read project context:
   - `entities/questions/`
   - `entities/hypotheses/`
   - `entities/datasets/` to avoid duplicating known dataset records
   - legacy specs/research-question.md only if it exists
   - legacy specs/scope-boundaries.md only if it exists
4. If an inquiry exists, check inquiry variables to understand what data the project needs:
   ```bash
   science inquiry list --format json
   ```

## Tool invocation

All `science` commands below use this pattern:

```bash
uv run science <command>
```

For brevity, the examples below write just `science <command>` — **always expand to `uv run science <command>` when executing. See step 8 of `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` for the fallback.**

## Workflow

### Step 1: Identify data needs

Based on project context:
- What variables does the project need data for?
- What modalities are relevant? (genomics, clinical, survey, imaging, etc.)
- What organisms or populations?
- What access constraints apply? (must be public, specific licenses, etc.)
- What formats are preferred?

Summarize needs concisely before searching.

### Step 2: LLM candidate generation

Using your knowledge of available datasets in the field:
- Suggest 5-10 candidate datasets with rationale
- Include known accessions, DOIs, or repository names where possible
- Explain why each is relevant to the project

### Step 3: Adapter-driven search

Use `science datasets search` to find datasets across repositories:

```bash
# Broad search across all sources
science datasets search "<query>" --format json

# Targeted search on specific sources
science datasets search "<query>" --source zenodo,geo --format json

# Oncology cohorts (TCGA, CPTAC, MSK, ...) via cBioPortal's public catalog
science datasets search "<query>" --source cbioportal --format json
```

Adapters cover Zenodo, NCBI GEO, Dryad, Semantic Scholar, the public cBioPortal
study catalog, figshare, ArrayExpress (EBI BioStudies), PhysioNet, and NCBI SRA.

**Demand-gated source priorities:** Do not promise adapter coverage for sources
that are not listed above. If a project genuinely needs one of these sources,
file or implement a focused adapter instead of broadening the adapter surface
speculatively:

| Source | Use when | Current handling |
|---|---|---|
| Open Targets Platform | target-disease, drug-target, genetic-evidence, or disease-gene lookup is load-bearing | Verify manually through the platform downloads/API and record as a reference or dataset entity. |
| DepMap | CCLE, Achilles/Chronos, dependency, or drug-response matrices are needed | Verify manually through the DepMap downloads portal. |
| PDC / CPTAC | Proteomics or multi-omics CPTAC files are needed beyond cBioPortal study metadata | Verify manually through the PDC portal/manifest. |
| clue.io / LINCS | L1000 perturbation signatures or connectivity-map data are needed | Prefer public release indexes first; only use key-gated API paths when credentials exist. |
| IHEC / BLUEPRINT | Hematopoietic or immune epigenomic reference data are needed | Verify public EpiRR records and mark EGA-controlled children as controlled. |
| Generic HTTP manifest | A niche source has stable URLs and checksums but no repository adapter | Create project-local dataset entities from the curated manifest; implement an adapter only after repeated use. |

**Search quality:** Results are ranked by lexical relevance to the query (title
weighted over keywords over description) and deduped across sources by DOI,
keeping the most relevant / metadata-complete copy. The result table shows
modality and organism; `--format json` additionally carries `sample_count`. Pass
distinct query terms — ranking is lexical token overlap, not semantic.

**Access tiers:** PhysioNet and SRA report an access tier on each result —
`public` (freely downloadable), `restricted` (self-serve DUA/login), or
`controlled` (application/approval required). PhysioNet `restricted`/`credentialed`
files raise on download until access is granted; SRA `.sra` files need
`fasterq-dump` conversion downstream.

**Limitation:** DUA-gated or separately hosted
oncology resources — notably AACR GENIE / GENIE BPC (Synapse +
`genie.cbioportal.org`), MSK-CHORD, and TCGA MC3 controlled-access tiers — are
not indexed by any adapter. For those, fall back to LLM knowledge plus the
project's `entities/datasets` cross-reference and record the access path (Synapse
DUA, dbGaP, etc.) manually.

For each promising result, get full metadata:

```bash
science datasets metadata <source>:<id> --format json
```

And list available files:

```bash
science datasets files <source>:<id> --format json
```

Cross-reference LLM suggestions with search results. Note which candidates were verified and which remain unverified.

### Step 4: Rank candidates

Rank by:
1. **Relevance** — covers project variables, matches research question
2. **Quality** — sample size, known provenance, peer-reviewed origin
3. **Accessibility** — public access, permissive license, standard format
4. **Completeness** — covers multiple needed variables, adequate sample size
5. **Recency** — newer datasets may have better methods/standards

Label each as:
- `Use now` — download and integrate immediately
- `Evaluate next` — promising but needs closer inspection
- `Track` — potentially useful, defer

### Step 5: Record selected datasets

For each `Use now` or `Evaluate next` dataset, ensure there is a durable
project record managed through the singular dataset entity lifecycle. Discovery
uses plural `science datasets ...`; durable project records use singular
`science dataset ...`.

For new durable records that can be expressed by current fields, use:

```bash
science dataset add <slug> \
  --title "<dataset title>" \
  --source-url "<landing-page-or-accession-url>" \
  --level <public|registration|controlled|commercial|mixed> \
  --tier <use-now|evaluate-next|track>
```

Then verify access evidence before handing the dataset to pipeline planning:

```bash
science dataset verify-access <slug> \
  --license <spdx-or-unknown> \
  --method <retrieved|credential-confirmed|landing-confirmed|metadata-confirmed> \
  --source-url "<landing-page-or-download-url>"
```

When the dataset supports a question or hypothesis, add typed links with the
helper instead of editing backlinks by hand:

```bash
science dataset link <dataset-ref> <question-or-hypothesis-ref>
```

If multiple dataset records need ranking after discovery, run:

```bash
science dataset prioritize --format json
```

Direct template authoring is a fallback, reserved for unsupported fields or
deliberate legacy backfills. When using that fallback, record why CLI lifecycle
commands cannot represent the needed change. Read `.ai/templates/dataset.md`
first; if it is not present, read `${CLAUDE_PLUGIN_ROOT}/templates/dataset.md`.
Fill unknown fields as `[UNVERIFIED]`, then immediately run
`science dataset verify-access <slug>` or record why verification is blocked.

When mapping an adapter result's `access` tier to the entity `access.level`,
apply: `public -> public`, `restricted -> controlled`, and
`controlled -> controlled`. Use `mixed` only when sibling artefacts differ in
access level.

### Step 6: Variable mapping (if inquiry exists)

If the project has an active inquiry, create a coverage matrix:
- List each inquiry variable
- Map which dataset(s) provide data for it
- Flag unmapped variables (data gaps)
- Flag variables with multiple dataset sources (potential for cross-validation)

Include this mapping in a `## Variable Coverage` section of the search output.

### Step 7: Write durable outputs

1. Write machine-readable search results to `entities/searches/YYYY-MM-DD-datasets-<slug>.json`.
2. Ensure new durable records were created with `science dataset add <slug>`;
   refresh access evidence for new or existing records with
   `science dataset verify-access <slug>`.
3. If appropriate, suggest runtime acquisition commands:
   ```bash
   science datasets download <source>:<id> --dest data/raw/
   ```
4. Offer to create follow-up tasks via `science tasks add`:
   - Download and inspect `Use now` datasets
   - Create or update `datapackage.json` for downloaded runtime files
   - Map variables for pipeline planning

### Step 8: Suggest next steps

1. Download selected datasets
2. Create Frictionless Data Package descriptors
3. Run `/science:plan-pipeline` to build computational workflow
4. Run `/science:discuss` to evaluate dataset choices

### Emission rules (rev 2.1)

When emitting or backfilling `entities/datasets/<slug>.md` through the CLI or the
explicit template fallback:

- One entity per **distinguishable artefact** at a distinct access level. A paper
  with one public supplement and one controlled EGA deposit produces TWO entities,
  optionally plus a third umbrella entity linking them via `parent_dataset` /
  `siblings`.
- External discovery records should resolve to `origin: "external"`.
- Default `access.verified: false`, `access.last_reviewed: ""`, `consumed_by: []`.
- Populate `access.level`, `access.source_url`, and `access.credentials_required`
  from discovery evidence. When uncertain, use the most restrictive known level
  — the verification step corrects it.
- The `accessions:` field carries external accession IDs (renamed from `datasets:`;
  legacy entries continue to read).
- Do NOT emit `origin: derived` entities — those are produced by `science
  dataset register-run` after a workflow run.

## Output Summary

Present a concise summary table:

| Dataset | Source | Accession/DOI | Tier | Key Variables | Size |
|---|---|---|---|---|---|

Followed by any data gaps that need to be addressed.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
  --target "command:find-datasets" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Guidelines:
- One entry per distinct issue (not one big dump)
- If the same issue has occurred before, the tool will detect it and
  increment recurrence automatically
- Skip if everything worked smoothly — no feedback is valid feedback
- For template-specific issues, use `--target "template:<name>"` instead
