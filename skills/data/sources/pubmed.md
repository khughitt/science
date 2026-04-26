---
name: data-source-pubmed
description: PubMed E-utilities source guidance for literature search and metadata normalization. Use when running `/science:search-literature` for biomedical topics or validating biomedical identifiers.
---

# PubMed Source Guide

Use this guide when searching biomedical literature with PubMed E-utilities.

## Purpose

PubMed is the primary biomedical indexing source.
Use it for high-recall biomedical retrieval, PMID resolution, and biomedical metadata verification.

## When To Use

- Running `/science:search-literature` on biomedical topics.
- Resolving PMID/PMCID identifiers.
- Verifying publication metadata for biomedical papers.
- Filling gaps when OpenAlex misses biomedical indexing details.

## API Surface

Core E-utilities flow:

1. `esearch` to retrieve candidate PMIDs for a query.
2. `esummary` to retrieve structured metadata for PMIDs.
3. `efetch` only when additional record detail is required.

Use `NCBI_API_KEY` from `.env` when available.
Persist retrieval timestamps and request parameters in search output metadata.

## Query Construction

Create query variants aligned with project context:

1. broad topic terms
2. mechanism/pathway terms
3. methods/measurement terms
4. alternative/confounder terms

Use query fields deliberately when needed (for example title/abstract constraints or MeSH-oriented terms), but avoid premature over-filtering.

Default behavior:

- start with broader retrieval
- refine iteratively if precision is poor

## Retrieval Workflow

1. Run `esearch` for each query variant and collect PMIDs.
2. Combine and deduplicate PMIDs across variants.
3. Fetch metadata in batches via `esummary`.
4. Use `efetch` selectively for records requiring deeper inspection.

Record, per PMID:

- title
- publication year/date
- journal/venue
- author list
- DOI (if available)
- PMCID (if available)
- source query variants

## Field Normalization

Map PubMed-derived fields to the project search schema:

- `pmid`
- `pmcid` (if available)
- `doi` (if available)
- `title`
- `publication_year`
- `venue`
- `authors`
- `source`: `pubmed`

Missing values should be `null`.
If a field appears inconsistent across sources, retain both values in JSON provenance notes and flag for review.

## Deduplication Guidance

When merging with OpenAlex and fallback-web candidates:

1. DOI match
2. PMID match
3. normalized title + year

For biomedical topics, prefer PubMed authority for:

- PMID/PMCID presence
- biomedical indexing context
- journal metadata consistency checks

## Quality Checks

Before final ranking:

- Verify topic relevance from title/abstract-level metadata.
- Ensure at least one stable identifier exists (PMID, DOI, or OpenAlex ID).
- Mark uncertain metadata as `[UNVERIFIED]` in markdown output.

If retrieval is sparse, widen query terms before adding aggressive filters.

## Output Contract

Populate:

- `papers/searches/YYYY-MM-DD-<slug>.json`
- `papers/searches/YYYY-MM-DD-<slug>.md`

Each PubMed-derived item must include:

- source tag `pubmed`
- originating query variants
- identifier fields (PMID/PMCID/DOI as available)
- ranking rationale text

## Companion Skills

- [`openalex.md`](openalex.md) - citation-count, author-order, and OpenAlex identifier reconciliation.
- [`../../research/annotation-curation-qa.md`](../../research/annotation-curation-qa.md) - label, claim, and source-curation QA for ranked literature sets.
- [`../../research/SKILL.md`](../../research/SKILL.md) - citation discipline and project-awareness rules.
