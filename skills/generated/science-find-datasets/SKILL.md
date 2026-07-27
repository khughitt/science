---
name: science-find-datasets
description: "Discover and document candidate datasets for research or tool demos. Uses LLM knowledge + dataset repository search to find, rank, and document relevant public datasets."
user-invocable: true
---

# Find Datasets

## Science Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load the `science-command-preamble` skill. Use its
   `references/role-prompts/research-assistant.md` role prompt and its aspect definitions.
3. Load the `science-scientific-writing` skill. For research methodology, read the `science-command-preamble` skill's `references/methodology-index.md` and load the emitted methodology router skills that own the relevant leaf guidance (for example, load the `science-literature` skill for `literature-evaluation` and `literature-citation-discipline` guidance, and load the `science-epistemics` skill for `epistemics-proposition-graph-reasoning` guidance).
4. Read project context from current entity roots:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. the `science-command-preamble` skill's `references/aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under the `science-command-preamble` skill's `references/aspects/`.

   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `entities/hypotheses/` | `hypothesis-testing` |
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
   `references/templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Verify the project-local Science CLI:** Execute the top-level CLI
   Compatibility Gate below before the command's first Science invocation. It
   uses the consumer's frozen lock; do not route through a toolkit checkout or
   another environment.

## CLI Compatibility Gate

```bash
SCIENCE_REQUIRED_VERSION=0.3.0
if output=$(uv run --frozen science --version 2>&1); then
  SCIENCE_INSTALLED_VERSION=${output##* }
elif uv run --frozen science --help >/dev/null 2>&1; then
  # The CLI runs but has no --version option, so it predates the baseline.
  # Decided by behavior, never by matching Click's version-dependent wording.
  SCIENCE_INSTALLED_VERSION=
else
  # The CLI cannot run at all: missing/stale lock, Git fetch failure, import
  # error. Report the real diagnosis; never advise moving the Science pin.
  printf '%s\n' "$output" >&2
  exit 1
fi

if ! SCIENCE_INSTALLED_VERSION="$SCIENCE_INSTALLED_VERSION" \
     SCIENCE_REQUIRED_VERSION="$SCIENCE_REQUIRED_VERSION" \
     uv run --no-project python - <<'PY'
import os
import re
import sys

def release(name: str) -> tuple[int, int, int] | None:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", name)
    return tuple(map(int, match.groups())) if match else None

installed = release(os.environ["SCIENCE_INSTALLED_VERSION"])
required = release(os.environ["SCIENCE_REQUIRED_VERSION"])
sys.exit(0 if installed is not None and required is not None and installed >= required else 1)
PY
then
  display=${SCIENCE_INSTALLED_VERSION:-unknown-or-pre-0.3.0}
  echo "This Science agent command requires science >=$SCIENCE_REQUIRED_VERSION; found $display." >&2
  echo "upgrade with: uv lock --upgrade-package science && uv sync --frozen" >&2
  exit 1
fi
```

After the gate succeeds, run the command through the consumer's project-local
environment as `uv run science <command>`. Missing dependency, missing or stale
lock, and Git fetch failures are surfaced directly and must be fixed in the
consumer project.

A CLI that answers `--help` but rejects `--version` predates the baseline;
malformed successful output and a version below the floor are likewise
compatibility failures, and all three stop with the upgrade command. A CLI that
cannot run at all is an environment failure: its output is printed verbatim and
must be fixed as reported.

The `--help` probe is what separates those two classes. Do not substitute a match
against Click's error text — its wording changed in Click 8.4, and `science`
allows any `click>=8.1`, so a freshly locked consumer can emit either form. The
root `--version` probe is the permanent bootstrap surface; do not replace it with
a preflight subcommand, which an older CLI could not recognize either.

Find candidate external datasets for the user input.
If no argument is provided, derive candidate search terms from active questions,
hypotheses, and inquiry variables; then ask the user to confirm the focus.

## Setup


Additionally:
1. Read `science-data-management` skill for data management conventions.
2. If present, read `science-data-management` skill for runtime Data Package guidance.
3. Read project context:
   - `entities/questions/`
   - `entities/hypotheses/`
   - `entities/datasets/` to avoid duplicating known dataset records
4. If an inquiry exists, check inquiry variables to understand what data the project needs:
   ```bash
   science inquiry list --format json
   ```

## Tool invocation

All `science` commands below use this pattern:

```bash
uv run science <command>
```

For brevity, the examples below write just `science <command>` — **always expand to `uv run science <command>` when executing. See step 8 of the Science Command Preamble above for the fallback.**

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

If a needed field is not yet exposed by the CLI, author the entity file directly
from the current dataset template and record why the lifecycle commands could
not represent the change. Read `.ai/templates/dataset.md` first; if it is not
present, read `references/templates/dataset.md`. Fill unknown fields
as `[UNVERIFIED]`, then immediately run `science dataset verify-access <slug>`
or record why verification is blocked.

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
3. Run `science-plan-pipeline` skill to build computational workflow
4. Run `science-discuss` skill to evaluate dataset choices

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
- The `accessions:` field carries external accession IDs.
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
