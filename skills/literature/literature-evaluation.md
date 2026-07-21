---
name: literature-evaluation
description: Use when reviewing literature, assessing source quality, or synthesizing findings across papers, before writing durable claims.
archetype: practice-guide
provenance: internal
---

# Literature Evaluation

Answers: how do I evaluate and synthesize external sources well?

## When to apply

Before writing any durable output that rests on external sources: a paper
summary, a topic synthesis, a background section, or an evidence line citing
literature. Also when auditing claims someone else sourced.

## Workflow steps

When researching a topic or summarizing a paper, use this priority order:

1. **Known context for orientation only.** Use model memory to frame search
   terms, expected concepts, and likely failure modes. Do not treat it as a
   source for durable claims.
2. **Primary and authoritative sources.** Verify claims against papers, official
   documentation, dataset records, or project-local notes before writing durable
   outputs.
3. **Web search for discovery and recency.** Use search to find recent work,
   source metadata, dataset versions, and missing primary sources.
4. **Full text when details matter.** Read the relevant methods, results,
   tables, and supplements when extracting parameters, numerical results,
   benchmark claims, cohort definitions, or evidence used in project decisions.
   If only the abstract is inspected, mark conclusions as abstract-level and
   avoid durable evidence updates.
5. **Cross-check before committing.** Always cross-check these via web search:

- Author lists and affiliations
- Publication year and journal
- Specific numerical results that inform project direction (effect sizes, p-values, sample sizes)
- Method parameterizations that will be used in computational pipelines
- Claims about validation approaches or benchmarks

If you cannot verify a fact, flag it explicitly with `[UNVERIFIED]` in the document.

## Judgment rules

Model memory is for orientation, not citation. Before writing from memory:

- **High confidence** (proceed, then cross-check): You recall specific details — author names, the core method, key findings. The paper is well-known or seminal.
- **Moderate confidence** (search first, then fill in from memory): You have a general sense of the paper's contribution but are fuzzy on specifics. Or the paper is recent / niche.
- **Low confidence** (search is the primary source): You're not sure this paper exists, or you're confusing it with something else. Say so. It's better to search than to confabulate.

The worst outcome is confidently writing about a paper that doesn't exist or attributing findings to the wrong paper. When in doubt, search first.

When assessing a source's value to the project:

- **Relevance:** Does it directly address a research question or hypothesis?
- **Recency:** Is it current enough? For methods, recent matters more. For foundational theory, older seminal work may be more important.
- **Quality:** Peer-reviewed > preprint > blog post > informal. But quality varies within each tier.
- **Reproducibility:** Did they share code/data? Can the methods be replicated?
- **Consensus:** Does this represent mainstream scientific consensus, or a minority/contrarian view? Note which.

## Quality criteria

When writing about multiple sources:

- Identify points of **agreement** across papers
- Identify points of **disagreement** and note the nature of the dispute
- Look for **gaps** — what has nobody studied?
- Look for **assumptions** — what does everyone take for granted that might not hold?
- Connect findings to the project's specific **hypotheses** and **research questions**

## Common pitfalls

- Writing from model memory without searching → treat recall as orientation for search terms, never as a citable source.
- Citing a paper read only at the abstract level → mark conclusions abstract-level and make no durable evidence update.
- Reporting agreement across sources that share an origin → check whether the sources are independent before counting them as convergent.
- Summarizing each source in turn and stopping → synthesis requires naming the disagreements and the gaps, not just the contents.

## Outputs

A source set with two axes recorded separately for each item — **provenance**
(primary or secondary) and **publication status** (peer-reviewed, preprint, or
informal) — since a peer-reviewed review article is secondary and a preprint may
be primary. Plus the claims each source backs, and explicit `[UNVERIFIED]` marks
on anything that could not be cross-checked.

## Success test

Did the agent carry out the cross-cutting practice according to its workflow, judgment rules, and quality criteria?

## Companion Skills

- [`citation-discipline.md`](citation-discipline.md) - citation and source-pointer conformance for what this practice produces.
- [`proposition-graph-reasoning.md`](proposition-graph-reasoning.md) - reasoning over the project's own proposition graph, as opposed to external sources.
- [`../INDEX.md`](../INDEX.md) — the skill index.
