---
description: Research and summarize a single scientific paper.
---

# Research a Paper

Research and summarize the paper specified by `$ARGUMENTS`.
The input may be a paper title, author name(s), DOI, URL, or a file path to a PDF.

## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `templates/paper-summary.md`.
2. Check `doc/papers/` for existing summary; ask before overwriting.

## Source Strategy

Follow the source hierarchy strictly:

### If given a paper title, authors, or DOI:

1. Start from LLM knowledge.
2. Cross-check key facts via web search:
   - Author list and affiliations
   - Publication year and venue
   - Specific quantitative results that matter to project decisions
   - Method details relevant to reproducibility
3. Mark uncertain details as `[UNVERIFIED]`.

### If given a PDF file path:

1. Read: Abstract, Introduction, Methods, Results, Discussion/Conclusion.
2. Skip: References, supplemental materials, acknowledgments unless needed.
3. Extract required template fields.
4. Cross-check key metadata when possible.

### If given a URL:

1. Fetch metadata/abstract from the URL.
2. Supplement with LLM context.
3. Cross-check key facts.
4. **If the URL returns a paywall, 403, or redirect loop:** fall back to DOI resolution → PubMed/preprint search (bioRxiv, arXiv, SSRN) → press coverage → GitHub README/repo. Do not abandon the paper — most paywalled papers have accessible metadata through alternative channels. Note the fallback source in the `Source:` frontmatter field.

### If the paper cannot be found:

1. State that the paper could not be identified reliably.
2. Ask for full title, first author, year, venue, or DOI.
3. Ask for a PDF path if available.
4. Do not fabricate a summary.

## Writing

Follow `templates/paper-summary.md` and fill every section.

- Include frontmatter `Source:` describing provenance (`LLM knowledge`, `web search`, `PDF`, or combination).
- Generate BibTeX key as `FirstAuthorLastNameYear` (with suffix if needed).
- Save to `doc/papers/<citekey>.md`.

## After Writing

1. Add/update the BibTeX entry in `papers/references.bib` (create file with header if missing).
2. Link relevance to existing hypotheses in `specs/hypotheses/`.
3. Add new questions to `doc/questions/` using `templates/question.md` when appropriate.
4. Note approach implications in `doc/04-approach.md` when relevant.
5. Commit: `git add -A && git commit -m "papers: research <citekey> - <short title>"`

## Batch Processing

When processing multiple papers in a single session (2+ papers with a shared thematic connection), after all individual summaries are written:

1. Produce a brief cross-paper synthesis document at `doc/papers/synthesis-YYYY-MM-DD-<theme>.md`.
2. Contents: shared themes, tensions between papers, and combined implications for the project.
3. Cross-reference the individual paper summaries by their `id` fields.

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
