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
For agent-facing API details, also consult the OpenAlex LLM quick reference:
<https://developers.openalex.org/guides/llm-quick-reference>.

Current OpenAlex usage constraints to preserve in workflows:

- Use `per_page` values at or below 100.
- Prefer `select=` to retrieve only fields the workflow consumes.
- Resolve human-readable names to OpenAlex IDs before applying filters where an ID filter is available.
- Batch DOI lookup with pipe-separated values when the workflow has known DOIs.
- Avoid deprecated Concepts endpoints and `/text`; prefer the current Topics, fields, subfields, domains, and Works surfaces.

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

For reusable Python tooling, prefer `science_tool.openalex.OpenAlexClient` over ad hoc `httpx` calls.
Its request records distinguish successful hits, valid empty result sets, rate limits, server errors, and request errors.
When a workflow can be long-running or quota-sensitive, attach `OpenAlexRequestCache` so successful and valid-empty requests are reused on rerun.
For the built-in science-map distiller, pass `science distill openalex --cache-path <path>` to make the API page fetches resumable.
Downstream QA should call `assert_no_unresolved_openalex_failures(...)` or an equivalent workflow-specific check before interpreting sparse results.

Do not treat an HTTP failure as an empty scientific result.
Only a successful payload with `meta.count == 0` and an empty `results` list should be interpreted as a valid empty OpenAlex result.
If OpenAlex returns `429` or a transient server error after retries, stop the workflow or mark the run incomplete so it can resume after quota or service recovery.

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

## Companion Skills

- [`pubmed.md`](pubmed.md) - biomedical metadata reconciliation and PMID/PMCID authority.
- [`../../research/annotation-curation-qa.md`](../../research/annotation-curation-qa.md) - label, claim, and source-curation QA for ranked literature sets.
- [`../../research/SKILL.md`](../../research/SKILL.md) - citation discipline and project-awareness rules.
