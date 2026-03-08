---
name: research-methodology
description: Core research methodology for scientific investigation. This skill should be used whenever conducting literature review, evaluating scientific sources, synthesizing findings across papers, assessing evidence quality, identifying gaps in knowledge, or working with hypotheses. Also use when the user mentions research, papers, citations, evidence, or scientific literature — even if they don't explicitly ask for "research methodology."
---

# Research Methodology

This skill defines how to approach scientific research tasks within a Science project. Read this before any research activity: literature review, paper summarization, hypothesis development, evidence evaluation, or topic exploration.

## Source Hierarchy

When researching a topic or summarizing a paper, use this priority order:

1. **LLM knowledge first.** Claude was trained on massive scientific literature. Start from what you know. This is fast, context-efficient, and correct for the vast majority of established science.
2. **Web search second.** Use web search to verify key facts (authors, year, journal, specific numerical results), find recent work (last 1-2 years), and fill gaps in your knowledge.
3. **PDF reading last.** Only read PDFs when the user explicitly provides a file path. When reading PDFs, use guided extraction: read abstract, introduction, methods, results, discussion. Skip references, supplemental figures, and tables to conserve context.

### Confidence Calibration

"LLM knowledge first" does NOT mean "guess first." Before writing from memory:

- **High confidence** (proceed, then cross-check): You recall specific details — author names, the core method, key findings. The paper is well-known or seminal.
- **Moderate confidence** (search first, then fill in from memory): You have a general sense of the paper's contribution but are fuzzy on specifics. Or the paper is recent / niche.
- **Low confidence** (search is the primary source): You're not sure this paper exists, or you're confusing it with something else. Say so. It's better to search than to confabulate.

The worst outcome is confidently writing about a paper that doesn't exist or attributing findings to the wrong paper. When in doubt, search first.

## Cross-Checking Key Facts

Always cross-check via web search before committing to a document:

- Author lists and affiliations
- Publication year and journal
- Specific numerical results that inform project direction (effect sizes, p-values, sample sizes)
- Method parameterizations that will be used in computational pipelines
- Claims about validation approaches or benchmarks

If you cannot verify a fact, flag it explicitly with `[UNVERIFIED]` in the document.

## Evaluating Sources

When assessing a source's value to the project:

- **Relevance:** Does it directly address a research question or hypothesis?
- **Recency:** Is it current enough? For methods, recent matters more. For foundational theory, older seminal work may be more important.
- **Quality:** Peer-reviewed > preprint > blog post > informal. But quality varies within each tier.
- **Reproducibility:** Did they share code/data? Can the methods be replicated?
- **Consensus:** Does this represent mainstream scientific consensus, or a minority/contrarian view? Note which.

## Synthesis, Not Just Summarization

When writing about multiple sources:

- Identify points of **agreement** across papers
- Identify points of **disagreement** and note the nature of the dispute
- Look for **gaps** — what has nobody studied?
- Look for **assumptions** — what does everyone take for granted that might not hold?
- Connect findings to the project's specific **hypotheses** and **research questions**

## Working with Hypotheses

Hypotheses in this project follow a structured format (see `templates/hypothesis.md`). When developing or evaluating hypotheses:

- Every hypothesis must be **falsifiable** — specify what evidence would disprove it
- Track **status**: proposed → under-investigation → supported/refuted/revised
- Link to specific **predictions** that follow from the hypothesis
- Connect to the **causal model** when applicable
- Reference **required evidence** — what data/analysis is needed to test it

## Citation Discipline

- Every factual claim in a document needs a source
- Use BibTeX keys: `[@AuthorYear]` inline, full entries in `papers/references.bib`
- When citing from LLM knowledge, cross-check key facts via web search
- If a claim cannot be sourced, mark it as `[NEEDS CITATION]`
- Prefer primary sources over secondary summaries

## Project Awareness

Before writing any document, check:

1. `specs/research-question.md` — What is this project about?
2. `specs/hypotheses/` — What hypotheses are we tracking?
3. `doc/questions/` — What questions are we trying to answer?
4. `doc/papers/` — What have we already reviewed?
5. `doc/topics/` — What topics have we already covered?

This prevents duplication and ensures new work connects to the existing knowledge base.

## Template Usage

All research documents must follow their corresponding template from the `templates/` directory. Read the relevant template before writing. The template sections are not optional — fill every section, even if briefly.
