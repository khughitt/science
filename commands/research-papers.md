---
description: Research and summarize one or more scientific papers.
---

# Research Papers

Research and summarize one or more papers specified by `$ARGUMENTS`.
Each paper may be given as a title, author name(s), DOI, URL, or a file path to a PDF.

`$ARGUMENTS` may contain a single paper or a list. Parse lists liberally:
- Newline-separated items
- Numbered or bulleted items (`1.`, `2.`, `-`, `*`)
- Comma-separated DOIs/titles on one line when unambiguous

If the split is ambiguous (e.g., a title that contains commas), ask the user to confirm before dispatching.

## Dispatch Strategy

This command runs in two roles. Determine which you are before proceeding.

### If you are the orchestrator

(You received the `/research-papers` slash command directly from the user.)

1. **Parse** `$ARGUMENTS` into a list of paper references. Let `N` be the count.
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

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `.ai/templates/paper.md` first; if not found, read `${CLAUDE_PLUGIN_ROOT}/templates/paper.md`.
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

Follow `.ai/templates/paper.md` first, then `${CLAUDE_PLUGIN_ROOT}/templates/paper.md`, and fill every section.

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
5. Commit: `git add -A && git commit -m "papers: research <citekey> - <short title>"`

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
