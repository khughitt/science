---
description: Research and summarize a single scientific paper. Capability-first command surface; compatible with existing summarize-paper behavior.
---

# Research a Paper

Research and summarize the paper specified by `$ARGUMENTS`.
The input may be a paper title, author name(s), DOI, URL, or a file path to a PDF.

## Compatibility Note

This command is the capability-first surface for paper-level synthesis.
`/science:summarize-paper` remains supported for backward compatibility and should follow the same behavior.

## Before Writing

1. Read `prompts/roles/research-assistant.md` if present; otherwise read `${CLAUDE_PLUGIN_ROOT}/references/role-prompts/research-assistant.md`.
2. Read the `research-methodology` skill for source hierarchy and cross-checking guidelines.
3. Read the `scientific-writing` skill for writing conventions.
4. Read `templates/paper-summary.md` for the required document structure.
5. Check `papers/summaries/` for an existing summary; if found, ask whether to update or create a new version.
6. If present, read `references/notes-organization.md`.
7. If present, read `templates/notes/article-note.md` for compact note updates.
8. First-use compatibility: if `notes/articles/` is missing, create `notes/articles/` and `notes/index.md` before writing note outputs.

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

### If the paper cannot be found:

1. State that the paper could not be identified reliably.
2. Ask for full title, first author, year, venue, or DOI.
3. Ask for a PDF path if available.
4. Do not fabricate a summary.

## Writing

Follow `templates/paper-summary.md` and fill every section.

- Include frontmatter `Source:` describing provenance (`LLM knowledge`, `web search`, `PDF`, or combination).
- Generate BibTeX key as `FirstAuthorLastNameYear` (with suffix if needed).
- Save to `papers/summaries/AuthorYear-short-title.md`.

## After Writing

1. Add/update the BibTeX entry in `papers/references.bib` (create file with header if missing).
2. Link relevance to existing hypotheses in `specs/hypotheses/`.
3. Add new questions to `doc/08-open-questions.md` when appropriate.
4. Note approach implications in `doc/04-approach.md` when relevant.
5. Create or update `notes/articles/<citekey>.md` using `templates/notes/article-note.md`.
6. Populate note metadata when available:
   - `ontology_terms` with ontology CURIEs tied to the paper's core entities.
   - `datasets` with cited dataset accessions relevant to this project.
7. Commit: `git add -A && git commit -m "papers: research <AuthorYear> - <short title>"`

## Process Reflection

Reflect on the **paper-summary template** sections and the **cross-checking** guidance.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — research-paper

**Template/structure friction:**
- Any section you left empty, filled with boilerplate, or that felt forced

**Missing capture:**
- Information you wanted to record but had no natural place for

**Guidance issues:**
- Command instructions that were confusing, contradictory, or didn't help

**What worked well:**
- A section or instruction that genuinely improved the output
```

Guidelines:
- Be concrete and specific, not generic ("the Limitations section felt redundant for a methods paper" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback
