---
name: science-find-datasets
description: "Discover and document candidate datasets for research or tool demos. Uses LLM knowledge + dataset repository search to find, rank, and document relevant public datasets. Also use when the user explicitly asks for `science-find-datasets` or references `/science:find-datasets`."
---

# Find Datasets

Converted from Claude command `/science:find-datasets`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `research-methodology` and `scientific-writing` skills.
4. Read `specs/research-question.md` for project context when it exists.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. `aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under `aspects/`.

   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `specs/hypotheses/` | `hypothesis-testing` |
   | Files in `models/` (`.dot`, `.json` DAG files) | `causal-modeling` |
   | Workflow files, notebooks, or benchmark scripts in `code/` | `computational-analysis` |
   | Package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`) at project root with project source code (not just tool dependencies) | `software-development` |

   If a signal is detected and the corresponding aspect is not in the `aspects` list,
   briefly note it to the user before proceeding:
   > "This project has [signal] but the `[aspect]` aspect isn't enabled.
   > This would add [brief description of what the aspect contributes].
   > Want me to add it to `science.yaml`?"

   If the user agrees, add the aspect to `science.yaml` and load the aspect file
   before continuing. If they decline, proceed without it.

   Only check once per command invocation — do not re-prompt for the same aspect
   if the user has previously declined it in this session.
7. **Resolve templates:** When a command says "Read `.ai/templates/<name>.md`",
   check the project's `.ai/templates/` directory first. If not found, read from
   `templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Resolve science-tool invocation:** When a command says to run `science-tool`,
   prefer the project-local install path: `uv run science-tool <command>`.
   This assumes the root `pyproject.toml` includes `science-tool` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`.
   If that fails (no root `pyproject.toml` or science-tool not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science-tool science-tool <command>`

Find datasets for the user input.
If no argument is provided, derive candidate search terms from `specs/research-question.md`, active hypotheses, and inquiry variables, then ask the user to confirm the focus.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.

Additionally:
1. Read `skills/data/SKILL.md` for data management conventions.
2. If present, read `skills/data/frictionless.md` for Data Package guidance.
3. Read `.ai/templates/dataset.md` first; if not found, read `templates/dataset.md`.
4. Read project context:
   - `specs/research-question.md`
   - `specs/scope-boundaries.md`
   - `specs/hypotheses/`
   - Existing `doc/datasets/` (to avoid duplicating known datasets)
5. If an inquiry exists, check inquiry variables to understand what data the project needs:
   ```bash
   science-tool inquiry list --format json
   ```

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run science-tool <command>
```

For brevity, the examples below write just `science-tool <command>` — **always expand to `uv run science-tool <command>` when executing. See step 8 of `references/command-preamble.md` for the fallback.**

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

Use `science-tool datasets search` to find datasets across repositories:

```bash
# Broad search across all sources
science-tool datasets search "<query>" --format json

# Targeted search on specific sources
science-tool datasets search "<query>" --source zenodo,geo --format json
```

For each promising result, get full metadata:

```bash
science-tool datasets metadata <source>:<id> --format json
```

And list available files:

```bash
science-tool datasets files <source>:<id> --format json
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

### Step 5: Document selected datasets

For each `Use now` or `Evaluate next` dataset, create a dataset note:

**File:** `doc/datasets/data-<slug>.md` using `.ai/templates/dataset.md` first, then `templates/dataset.md`

Fill in all available fields. For fields you cannot verify, mark as `[UNVERIFIED]`.

Required frontmatter fields to populate (see template comments for enum values):

- `tier` — one of `use-now`, `evaluate-next`, `track` (mirror the ranking label from Step 4)
- `access` — one of `public`, `controlled`, `mixed`
- `license` — SPDX identifier or `unknown`
- `formats` — list of lower-case format slugs
- `size_estimate` — with unit (e.g., `"12 GB"`, `"~500 MB"`, `"unknown"`)
- `update_cadence` — `static`, `rolling`, `monthly`, `quarterly`, `annual`, or `versioned-releases`
- `ontology_terms` — canonical CURIEs (UBERON:*, CL:*, MONDO:*, DOID:*, EFO:*, etc.), not free text

#### Multi-accession resources

If a resource spans multiple accessions (primary + mirror, atlas + component studies, etc.), pick one pattern:

1. **One record, multi-accession list** — preferred default. List every accession in `datasets:`.
2. **Parent + overview + children** — preferred for atlases. One overview record, one per component, linked via `related:`.
3. **One record per accession** — last resort, when accessions share little context.

See the `## Multi-accession resources` comment block in `templates/dataset.md` for examples.

### Step 6: Variable mapping (if inquiry exists)

If the project has an active inquiry, create a coverage matrix:
- List each inquiry variable
- Map which dataset(s) provide data for it
- Flag unmapped variables (data gaps)
- Flag variables with multiple dataset sources (potential for cross-validation)

Include this mapping in a `## Variable Coverage` section of the search output.

### Step 7: Update project files

1. Update `science.yaml` data_sources section with new entries.
2. Write machine-readable search results to `doc/searches/YYYY-MM-DD-datasets-<slug>.json`.
3. If appropriate, suggest download commands:
   ```bash
   science-tool datasets download <source>:<id> --dest data/raw/
   ```
4. Offer to create follow-up tasks via `science-tool tasks add`:
   - Download and inspect `Use now` datasets
   - Create `datapackage.json` for downloaded data
   - Map variables for pipeline planning

### Step 8: Suggest next steps

1. Download selected datasets
2. Create Frictionless Data Package descriptors
3. Run `science-plan-pipeline` to build computational workflow
4. Run `science-discuss` to evaluate dataset choices

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
science-tool feedback add \
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
