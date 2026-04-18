---
description: Research and summarize a single scientific paper.
---

# Research a Paper

Research and summarize the paper specified by `$ARGUMENTS`.
The input may be a paper title, author name(s), DOI, URL, or a file path to a PDF.

## Dispatch Strategy

This command runs in two roles. Determine which you are before proceeding.

### If you are the orchestrator

(You received the `/research-paper` slash command directly from the user.)

1. **Pre-dispatch check:** Look at `doc/papers/` for an existing summary that likely covers this paper (fuzzy match on title/author/DOI). If one may exist, ask the user whether to overwrite, skip, or produce a supplementary summary. Carry their decision forward into the subagent prompt.
2. **Dispatch** the `paper-researcher` subagent via the Agent tool:
   - `subagent_type: paper-researcher`
   - `description`: a short identifier for the paper
   - `prompt`: the full `$ARGUMENTS` plus the overwrite decision from step 1, plus any project-specific context the subagent would not otherwise discover
3. Do **not** perform the Setup / Source Strategy / Writing / After Writing steps below yourself — those are the subagent's job and dispatching preserves the cost savings this command exists for.
4. When the subagent reports back, continue at **Orchestrator Post-Dispatch** below.

### If you are the `paper-researcher` subagent

Skip the Dispatch Strategy section and execute Setup → Source Strategy → Writing → After Writing. Then report back per the response contract in your agent definition.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `.ai/templates/paper-summary.md` first; if not found, read `${CLAUDE_PLUGIN_ROOT}/templates/paper-summary.md`.
2. Check `doc/papers/` for existing summary; ask before overwriting.

## Source Strategy

Retrieval is centralized through `science-tool paper-fetch`, which handles tiered source probing (Crossref → Unpaywall → arXiv → bioRxiv/medRxiv → Europe PMC → direct OA PDF) with cross-process rate limiting. This avoids open-ended scavenging and keeps parallel subagents polite to the same servers.

### If given a DOI (or a URL/title that resolves to one):

1. Normalize the input to a DOI (strip `doi.org/` prefixes; for titles, do one Crossref search to find the DOI).
2. Run `uv run science-tool paper-fetch --doi <doi>` and branch on `status`:
   - **`ok`** — read the file at `pdf_path` / `text_path` and fill the template.
   - **`paywalled`** — Unpaywall has no OA record. Stop. Set `Source: paywalled` and either (a) defer (leave a stub with `status: paywalled` in frontmatter and return to the orchestrator) or (b) if the user supplies a PDF path on request, re-run against the PDF.
   - **`blocked_but_oa`** — OA copy exists but agent-accessible tiers failed. Stop. Ask the orchestrator to request a PDF from the user. Do not retry with open-ended search.
   - **`not_found`** — the DOI did not resolve at all. Ask the orchestrator for better metadata.
3. Cross-check key metadata via targeted searches only when template fields require it. Mark any unverified details as `[UNVERIFIED]`.

### If given a PDF file path:

1. Skip `paper-fetch`; read the PDF directly.
2. Read: Abstract, Introduction, Methods, Results, Discussion/Conclusion.
3. Skip: References, supplemental materials, acknowledgments unless needed for a template field.
4. Extract required template fields and cross-check metadata via `paper-fetch --doi <doi>` if the PDF surfaces a DOI (metadata resolution is fast and safe).

### If given a URL that is not a DOI landing page:

1. Fetch the URL once to extract an abstract and any DOI/PMID references.
2. If a DOI is found, hand off to the DOI branch above.
3. Otherwise, proceed on LLM knowledge + abstract, and flag the summary `Source: web` with generous `[UNVERIFIED]` markers.

### If the paper cannot be found:

1. State that the paper could not be identified reliably.
2. Ask for full title, first author, year, venue, or DOI.
3. Ask for a PDF path if available.
4. Do not fabricate a summary.

## Writing

Follow `.ai/templates/paper-summary.md` first, then `${CLAUDE_PLUGIN_ROOT}/templates/paper-summary.md`, and fill every section.

- Include frontmatter `Source:` describing provenance (`LLM knowledge`, `web search`, `PDF`, or combination).
- Generate BibTeX key as `FirstAuthorLastNameYear` (with suffix if needed).
- Save to `doc/papers/<citekey>.md`.

## After Writing

1. Add/update the BibTeX entry in `papers/references.bib` (create file with header if missing).
2. Link relevance to existing hypotheses in `specs/hypotheses/`.
3. Add new questions to `doc/questions/` using `.ai/templates/question.md` first, then `${CLAUDE_PLUGIN_ROOT}/templates/question.md` when appropriate.
4. Note approach implications in `doc/04-approach.md` when relevant.
5. Commit: `git add -A && git commit -m "papers: research <citekey> - <short title>"`

## Orchestrator Post-Dispatch

After the subagent returns its report:

1. Review any `[UNVERIFIED]` fields the subagent flagged and surface them to the user — they may warrant a follow-up web check or a note in `doc/questions/`.
2. If the subagent could not identify the paper, relay its request for additional metadata to the user and stop; do not attempt to fabricate a summary on the orchestrator.
3. Read the written summary only if you need its content for downstream reasoning (e.g., before cross-paper synthesis or hypothesis linking). Otherwise, trust the report.
4. If you hold broader project context than the subagent did — unmerged hypotheses, recent approach decisions in `doc/04-approach.md`, adjacent open questions — make small follow-up edits as a separate commit.

## Batch Processing (orchestrator)

When processing multiple papers in a single session (2+ papers with a shared thematic connection):

1. Dispatch the `paper-researcher` subagent once per paper. When the papers are independent lookups, issue the Agent calls **in parallel** (multiple tool uses in a single message) to reduce wall-clock time.
2. After all subagent reports return, produce a brief cross-paper synthesis yourself at `doc/papers/synthesis-YYYY-MM-DD-<theme>.md`. Synthesis is an orchestrator responsibility because it requires holding all papers in context at once.
3. Contents: shared themes, tensions between papers, and combined implications for the project.
4. Cross-reference the individual paper summaries by their `id` fields.

This only applies when papers share a thematic connection. Unrelated papers processed in the same session do not need synthesis.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:research-paper" \
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
