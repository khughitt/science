---
name: science-research-papers
description: "Research and summarize one or more scientific papers."
---

# Research Papers

Converted from Claude command `/science:research-papers`.

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

Research and summarize one or more papers specified by the user input.
Each paper may be given as a title, author name(s), DOI, URL, or a file path to a PDF.

the user input may contain a single paper or a list. Parse lists liberally:
- Newline-separated items
- Numbered or bulleted items (`1.`, `2.`, `-`, `*`)
- Comma-separated DOIs/titles on one line when unambiguous

If the split is ambiguous (e.g., a title that contains commas), ask the user to confirm before dispatching.

## Dispatch Strategy

This command runs in two roles. Determine which you are before proceeding.

### If you are the orchestrator

(You received the `/research-papers` slash command directly from the user.)

1. **Parse** the user input into a list of paper references. Let `N` be the count.
2. **Pre-dispatch check:** For each paper, look at `doc/papers/` for an existing summary (fuzzy match on title/author/DOI). If any may exist, ask the user whether to overwrite, skip, or supplement — resolve per-paper, then carry each decision into that paper's subagent prompt.
3. **Dispatch** the `paper-researcher` subagent *once per paper*. When `N > 1`, issue all Agent calls **in parallel** (multiple tool uses in a single message) so they overlap — the shared rate limiter in `science-tool paper-fetch` keeps per-host traffic polite automatically.
   - `subagent_type: paper-researcher`
   - `description`: a short identifier for that paper
   - `prompt`: the single paper's reference + its overwrite decision + any project-specific context the subagent would not otherwise discover
4. Do **not** perform the Setup / Source Strategy / Writing / After Writing steps below yourself — those are each subagent's job, and dispatching preserves the cost savings this command exists for.
5. When all subagents report back, continue at **Orchestrator Post-Dispatch**. For `N ≥ 2` papers with a shared thematic connection, also run **Batch Processing**.

### If you are the `paper-researcher` subagent

Skip the Dispatch Strategy section and execute Setup → Source Strategy → Writing → After Writing for your one assigned paper. Then report back per the response contract in your agent definition.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.

Additionally:
1. Read `.ai/templates/paper.md` first; if not found, read `templates/paper.md`.
2. Check `doc/papers/` for existing summary; ask before overwriting.

## Source Strategy

Retrieval is centralized through `science-tool paper-fetch`, which handles tiered source probing (Crossref → Unpaywall → arXiv → bioRxiv/medRxiv → Europe PMC → direct OA PDF) with cross-process rate limiting. This avoids open-ended scavenging and keeps parallel subagents polite to the same servers.

### Picking the right identifier flag

`paper-fetch` accepts the identifier in whatever form the user provided — pass it through as-is rather than pre-resolving:

| User-supplied form | Flag |
|--------------------|------|
| DOI or `doi.org/…` URL | `--doi <value>` |
| arXiv ID (e.g. `2502.09135`) | `--arxiv <id>` |
| arXiv URL (`arxiv.org/abs/…`) | `--url <url>` |
| PubMed ID | `--pmid <pmid>` |
| PubMed URL (`pubmed.ncbi.nlm.nih.gov/…`) | `--url <url>` |
| PMC ID (e.g. `PMC12934989`) | `--pmcid <pmcid>` |
| PMC URL (`pmc.ncbi.nlm.nih.gov/articles/…`) | `--url <url>` |
| bioRxiv/medRxiv URL | `--url <url>` |
| Title only | One Crossref search, then `--doi <result>` |

When both a DOI and a PMID/PMCID are available (e.g. user gave both, or a PubMed page surfaced both), pass both — `paper-fetch` cross-checks them and returns `status: error` with `metadata.reason: identifier_mismatch` if they conflict, catching wrong-DOI mistakes before you summarize the wrong paper.

### Branching on the result

Run `paper-fetch` once with the chosen flag(s) and branch on `status`:

- **`ok`** — read the file at `pdf_path` / `text_path` and fill the template. Cross-check key metadata via targeted searches only when template fields require it; mark unverified details as `[UNVERIFIED]`.
  - **Author-attribution check (before writing).** If the user's request named an author or research group, compare it against `metadata.authors[0]` from the `paper-fetch` result. On a clear mismatch (different surname, or different institutional group), pause and surface the discrepancy to the orchestrator before writing — the user may have had the wrong paper in mind, or the wrong author for the right paper. Don't silently follow either source; flag the conflict so the orchestrator can confirm with the user.

- **`paywalled`** — Unpaywall has no OA record. By default: stop, set `Source: paywalled`, and either (a) defer with `status: paywalled` in frontmatter, or (b) re-run against a PDF if the user supplies one.
  - **Well-known classic exception** — if *all* of the following hold, you may proceed on LLM knowledge instead of stopping:
    - Published more than 3 calendar years ago (i.e. `year ≤ current_year − 3`).
    - Widely cited (>500 citations — quick estimate via Crossref `is-referenced-by-count` or a Google Scholar lookup).
    - Task is conceptual/theoretical synthesis, not data extraction or methods replication.
    - Paper is comprehensively covered by general LLM training (a foundational paper, not a niche follow-up).
  - When proceeding under this exception: set `Source: LLM knowledge`, mark every specific number / figure / method detail as `[UNVERIFIED]`, and **do not invent quantitative claims** (cohort sizes, effect sizes, fold-changes, accuracies). Stick to conceptual contributions.
  - **Review-paper triangulation** — if the paywalled paper's Crossref `type` indicates a review (or the title says "review" / "perspective"), pull 2-3 citing primary papers via Europe PMC's citations endpoint and triangulate the headline claims rather than relying on the abstract alone.

- **`blocked_but_oa`** — OA copy exists but every agent-accessible tier failed. Before asking the orchestrator for a PDF, try one Europe PMC abstract-level fallback: `WebFetch https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:"<doi>"&format=json` — if it returns an abstract, you have enough for the summary's overview/significance fields (mark methods/results as `[UNVERIFIED]`). If that also fails, ask the orchestrator to request a PDF. Do not retry with open-ended search.

- **`not_found`** — no source resolved the identifier. Ask the orchestrator for better metadata; do not fabricate a summary.

- **`error`** — caller-supplied identifiers conflict (`metadata.reason` names the class, e.g. `identifier_mismatch`). Surface the conflict in `access_hint` to the orchestrator and stop — re-checking is the user's call.

### If given a PDF file path:

1. Skip `paper-fetch`; read the PDF directly.
2. Read: Abstract, Introduction, Methods, Results, Discussion/Conclusion.
3. Skip: References, supplemental materials, acknowledgments unless needed for a template field.
4. Extract required template fields and cross-check metadata via `paper-fetch --doi <doi>` if the PDF surfaces a DOI (metadata resolution is fast and safe).

### If the paper cannot be found:

1. State that the paper could not be identified reliably.
2. Ask for full title, first author, year, venue, or DOI.
3. Ask for a PDF path if available.
4. Do not fabricate a summary.

## Writing

Follow `.ai/templates/paper.md` first, then `templates/paper.md`, and fill every section.

- Include frontmatter `Source:` describing provenance (`LLM knowledge`, `web search`, `PDF`, or combination).
- Generate BibTeX key as `FirstAuthorLastNameYear` (with suffix if needed).
- Save to `doc/papers/<citekey>.md`.

## After Writing

1. Add/update the BibTeX entry in `papers/references.bib` (create file with header if missing).
2. Link relevance to existing hypotheses in `specs/hypotheses/`.
3. Add new questions via `science-tool question reserve`. **Do not** create files under `doc/questions/` directly — parallel subagents racing on the next q-number cause silent collisions. The CLI uses `O_CREAT|O_EXCL` to atomically claim the next slot, even with multiple subagents writing concurrently.

   For each new question:
   ```bash
   uv run science-tool question reserve \
     --slug "<short-kebab-slug>" \
     --title "<question title>" \
     --source-refs "<this paper's citekey>" \
     [--related "<related-id>,<related-id>"] \
     [--ontology "<term>,<term>"] \
     --json
   ```
   The command returns JSON with the assigned `path`. Read that file (it has frontmatter pre-filled and section scaffolding) and edit the body sections in place. The project's `.ai/templates/question.md` overrides the default body via `--template <path>` if needed.
4. Note approach implications in `doc/04-approach.md` when relevant.
5. Commit: `git add -A && git commit -m "docs(papers): research <citekey> - <short title>"`. The `docs(papers):` prefix is commitlint-conventional compliant out of the box; if your project's commitlint config explicitly allows `papers:` as a custom type, prefer that.

## Orchestrator Post-Dispatch

After the subagent returns its report:

1. Review any `[UNVERIFIED]` fields the subagent flagged and surface them to the user — they may warrant a follow-up web check or a note in `doc/questions/`.
2. If the subagent could not identify the paper, relay its request for additional metadata to the user and stop; do not attempt to fabricate a summary on the orchestrator.
3. Read the written summary only if you need its content for downstream reasoning (e.g., before cross-paper synthesis or hypothesis linking). Otherwise, trust the report.
4. If you hold broader project context than the subagent did — unmerged hypotheses, recent approach decisions in `doc/04-approach.md`, adjacent open questions — make small follow-up edits as a separate commit.

## Batch Processing (orchestrator)

When the dispatched batch contained `N ≥ 2` papers with a shared thematic connection, after all subagent reports return:

1. Produce a brief cross-paper synthesis at `doc/papers/synthesis-YYYY-MM-DD-<theme>.md`. Synthesis is an orchestrator responsibility because it requires holding all papers in context at once — the subagents do not talk to each other.
2. Contents: shared themes, tensions between papers, and combined implications for the project.
3. Cross-reference the individual paper summaries by their `id` fields.

Skip synthesis when the papers are unrelated (e.g., the user dropped a mixed list for cleanup). A shared connection is the trigger, not the count.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:research-papers" \
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
