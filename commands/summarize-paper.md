---
description: Summarize a scientific paper for the research project. Use when the user mentions a paper by title, author, DOI, or provides a PDF path. Accepts paper titles, DOIs, URLs, or file paths as input.
---

# Summarize a Paper

> Compatibility alias: this command remains supported. Prefer `/science:research-paper` for the capability-first interface.

Summarize the paper specified by `$ARGUMENTS`. The input may be a paper title, author name(s), DOI, URL, or a file path to a PDF.

## Before Writing

1. Read the `research-methodology` skill for source hierarchy and cross-checking guidelines.
2. Read the `scientific-writing` skill for writing conventions.
3. Read `templates/paper-summary.md` for the required document structure.
4. Check `papers/summaries/` — has this paper already been summarized? If so, tell the user and ask if they want an update.

## Source Strategy

Follow the source hierarchy strictly:

### If given a paper title, authors, or DOI:

1. **LLM knowledge first.** Attempt to summarize from training data. You likely know the key contribution, methods, and findings for most published papers.
2. **Cross-check key facts via web search:**
   - Author list and affiliations
   - Publication year and journal
   - Specific numerical results (effect sizes, sample sizes, p-values)
   - Method parameterizations that may inform project pipelines
   - Any claims about validation or benchmarks
3. **Flag uncertainties.** If you cannot verify a specific detail, include it but mark with `[UNVERIFIED]`.

### If given a PDF file path:

1. Read the PDF with guided extraction:
   - **Read:** Abstract, Introduction, Methods, Results, Discussion/Conclusion
   - **Skip:** References, Supplemental figures, Supplemental tables, Acknowledgments
2. Extract the information needed for the template.
3. Still cross-check key facts via web search when possible.

### If given a URL:

1. Fetch the URL to get the paper's abstract and metadata.
2. Supplement with LLM knowledge for deeper context.
3. Cross-check key facts via web search.

### If the paper cannot be found:

If you don't recognize the paper from training data AND web search returns nothing useful:

1. Tell the user you couldn't find the paper.
2. Ask for additional identifying information: full title, first author, year, journal, or DOI.
3. If the user has the PDF, ask them to provide the file path.
4. Do NOT fabricate a summary — it's better to say "I couldn't find this paper" than to hallucinate details.

## Writing

Follow the `templates/paper-summary.md` structure. Fill every section.

**Important:** Include the `Source:` field in the frontmatter indicating how the summary was produced: `LLM knowledge`, `web search`, `PDF`, or a combination.

### Generating the BibTeX key

Use the format: `FirstAuthorLastNameYear` (e.g., `Smith2024`). If ambiguous, add a lowercase letter suffix (e.g., `Smith2024a`).

### File naming

Save to `papers/summaries/AuthorYear-short-title.md` where:
- `Author` = first author's last name
- `Year` = publication year
- `short-title` = 2-4 word kebab-case description

Example: `papers/summaries/Smith2024-causal-inference-review.md`

## After Writing

1. Add the BibTeX entry to `papers/references.bib`. If the file doesn't exist yet, create it with a header comment:
   ```bibtex
   % references.bib — BibTeX database for this Science project
   % Use keys in the format: FirstAuthorLastNameYear (e.g., Smith2024)
   ```
2. Check if findings are relevant to existing hypotheses in `specs/hypotheses/` — note connections in the Relevance section.
3. If the paper raises new questions, add them to `doc/08-open-questions.md`.
4. If the paper's methods are relevant to the project approach, note this in the summary and consider updating `doc/04-approach.md`.
5. Commit: `git add -A && git commit -m "papers: summarize <AuthorYear> - <short title>"`
