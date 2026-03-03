---
name: data-source-openalex
description: OpenAlex source guidance for literature search and metadata normalization. Use when running `/science:search-literature`, collecting paper metadata, or reconciling identifiers across sources.
---

# OpenAlex Source Guide

Use this guide when searching literature through OpenAlex or validating metadata returned from other sources.

## Purpose

OpenAlex is the primary source for broad, cross-domain scholarly metadata and citation context.
Use it to expand candidate sets, recover identifiers, and support relevance ranking.

## When To Use

- Running `/science:search-literature`.
- Expanding topic coverage beyond a seed paper list.
- Recovering canonical metadata for DOI/title matches.
- Collecting citation and concept context for ranking.

## API Surface

Primary entity:

- `works` for paper-level records.

Typical query patterns:

1. Text search:
   - `GET /works?search=<query>`
2. Filtered search:
   - `GET /works?search=<query>&filter=<filters>`
3. Targeted lookup:
   - `GET /works/<openalex-id>`

Prefer including contact metadata via `mailto` when supported by the endpoint.

## Query Construction

For each search focus, create multiple query variants:

1. Broad domain phrase.
2. Mechanism or pathway phrase.
3. Methods and measurement phrase.
4. Contradictory or alternative framing phrase.

Add filters when needed:

- publication date window
- language
- document type
- concept/domain constraints

Do not over-constrain the first pass.
Start broad, then tighten based on result quality.

## Pagination and Retrieval

- Pull multiple pages up to the command-level candidate cap.
- Persist source query parameters and retrieval timestamp for provenance.
- Stop early if results become clearly off-topic.

## Field Normalization

Map OpenAlex record fields to the project search schema:

- `openalex_id`: canonical OpenAlex work ID
- `doi`: normalized DOI (if present)
- `title`
- `publication_year`
- `venue`
- `authors`: ordered list (first author explicitly retained)
- `cited_by_count`
- `ids`: include available alternate identifiers
- `source`: `openalex`

Unknown values should be set to `null` and flagged as `[UNVERIFIED]` in markdown output where relevant.

## Deduplication Guidance

When merging with PubMed or fallback-web results:

1. Match DOI first.
2. Then match PMID.
3. Then match normalized title + year.

Prefer OpenAlex as metadata authority for:

- author ordering
- venue names
- citation counts

If metadata conflicts with PubMed on core identifiers, keep both values in JSON and mark the conflict in notes.

## Quality Checks

Before final ranking:

- Confirm the record is actually about the intended topic.
- Confirm year/venue are plausible.
- Check that at least one stable identifier exists (DOI, PMID, or OpenAlex ID).

Demote records lacking stable identifiers unless they are clearly high-value to the project.

## Output Contract

Populate:

- `papers/searches/YYYY-MM-DD-<slug>.json`
- `papers/searches/YYYY-MM-DD-<slug>.md`

Each included OpenAlex-derived item must carry:

- query provenance (which query variant found it)
- source tag `openalex`
- ranking rationale text

