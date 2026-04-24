---
name: science-search-literature
description: "Search scientific literature using OpenAlex and PubMed, rank results by project relevance, and produce a prioritized reading queue."
---

# Search Literature

Converted from Claude command `/science:search-literature`.

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

Search literature for the user input.
If no argument is provided, derive candidate search foci from `specs/research-question.md` and `doc/questions/`, then ask the user to confirm the focus.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.

Additionally:
1. If present, read source-specific skills from `<science-plugin-root>`:
   - `skills/data/sources/openalex.md`
   - `skills/data/sources/pubmed.md`
2. Read `.ai/templates/paper.md` first; if not found, read `templates/paper.md`.
3. Read project context:
   - `specs/research-question.md`
   - `specs/scope-boundaries.md`
   - `doc/questions/`
   - `specs/hypotheses/`
   - `doc/papers/`
   - `doc/topics/`, `doc/questions/`
4. Check `doc/searches/` for recent related searches and ask whether to refresh or create a new run.

## Query Planning

Create 3-5 query variants before running searches:

1. A broad conceptual query.
2. A mechanism/pathway query.
3. A methods/measurement query.
4. A contrasting/alternative explanation query (when relevant).
5. An optional domain narrowing query (population, assay, disease subtype, etc.).

Default constraints unless user specifies otherwise:

- Time window: last 10 years, plus seminal older papers if they dominate citations.
- Result depth: retrieve up to 50 candidates before ranking.
- Output depth: keep top 20 ranked records.

## Search Execution

Use this execution order:

1. Run direct source queries:
   - OpenAlex API (primary broad-discovery source)
   - PubMed E-utilities (for biomedical scope)
2. If source APIs are temporarily unavailable, use web search as fallback and mark source as `fallback-web`.

At least one query must hit OpenAlex with a broad conceptual framing and return ≥30 candidates before ranking. If every query is seed/author/title-driven and returns <30 results, you are in verify-mode, not discover-mode — stop and reformulate at least one query as a broad conceptual search.

For each candidate, capture identifiers where available:

- DOI
- PMID/PMCID
- OpenAlex ID
- Year
- Venue
- First/last author

Do not fabricate missing metadata. Mark unknown fields as `[UNVERIFIED]`.

## Deduplication and Ranking

Deduplicate across sources by DOI first, then PMID, then normalized title.

Rank with explicit rationale using:

1. Relevance to project question and active hypotheses.
2. Evidence strength (study design and methodological clarity).
3. Recency and citation momentum.
4. Novelty or contradiction value (papers that challenge current assumptions are high value).
5. Reproducibility signal (clear data/method reporting).

Label each ranked item as one of:

- `Core now` (read immediately)
- `Relevant next` (read if time allows)
- `Peripheral monitor` (track but defer)

## Coverage Audit (before writing)

Before writing output, enumerate the project's declared scope and check which parts this search does **not** cover.

Sources of declared scope (read all that exist):

- `science.yaml` aspects
- `doc/topics/` (topic slugs and their subtopics)
- `doc/questions/` (open questions)
- `specs/hypotheses/` (active hypotheses)

For each declared item, mark whether the current search surfaced at least one ranked candidate that materially addresses it. If gaps exist, either:

1. Run one additional targeted query per uncovered item and fold results into the run, or
2. Record the uncovered item explicitly in `## Coverage Notes and Gaps` with a suggested follow-up query.

Do not skip this step — a reading queue that silently omits declared scope is worse than one that flags the omission.

## Writing Output

If `doc/searches/` does not exist yet, create it first.

Create `doc/searches/YYYY-MM-DD-<slug>.md` with sections:

1. `## Search Focus`
2. `## Query Set`
3. `## Sources and Run Metadata`
4. `## Ranked Results`
5. `## Priority Reading Queue`
6. `## Coverage Notes and Gaps`
7. `## Recommended Next Actions`

In `## Ranked Results`, include a table with columns:

- Rank
- Citation (short)
- Year
- Source IDs (DOI / PMID / OpenAlex)
- Tier
- Why it matters for this project

Also write machine-readable output to:

- `doc/searches/YYYY-MM-DD-<slug>.json`

Include the normalized candidate list, dedupe keys, source provenance, and rank/tier fields.

## After Search

1. Offer to create tasks for the top `Core now` papers via `science-tool tasks add`.
2. For selected high-priority papers, run `science-research-papers` (or create a task for later).
3. For `Core now` items, create a **stub-only** note at `doc/papers/<citekey>.md` using `.ai/templates/paper.md` first, then `templates/paper.md`. The stub must contain:
   - Template frontmatter filled from search metadata only (title, authors, year, identifiers).
   - Every prose/content section (Key Contribution, Methods, Key Findings, etc.) replaced with a single line: `UNREAD — populate after reading the paper`.
   - Do **not** write plausible-sounding summaries from the LLM prior; those are hard to distinguish from real notes later and cause stub-drift when the paper is actually read.
   Full content is populated later by `science-research-papers` or during task execution.
4. Populate note metadata fields from search results only (do not infer):
   - `tags` for project-specific labels.
   - `ontology_terms` for normalized ontology CURIEs (for example MeSH, GO, Biolink terms).
   - `datasets` for relevant dataset accessions when identified.
5. Update related topic/question notes (`doc/topics/`, `doc/questions/`) with new links and key takeaways.
6. Add BibTeX entries for selected high-priority papers to `papers/references.bib`. If the file does not exist yet, create it with:
   ```bibtex
   % references.bib — BibTeX database for this Science project
   % Use keys in the format: FirstAuthorLastNameYear (e.g., Smith2024)
   ```
7. If substantial gaps remain, run `science-next-steps` focused on the searched scope.
8. Commit: `git add -A && git commit -m "papers: search literature <slug>"`

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:search-literature" \
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
