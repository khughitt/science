---
id: "convention:annotation-tokens"
type: "convention"
title: "Annotation tokens"
status: "active"
created: "2026-05-09"
updated: "2026-06-14"
---

# Annotation tokens

Inline marker tokens used in prose to flag specific epistemic states. Counted by `validate.sh` and `science refs check` via the shared scanner in `science_tool/markers.py`.

## Vocabulary

| Token                | Meaning                                                                  | Default severity | Under `--strict` |
|----------------------|--------------------------------------------------------------------------|------------------|------------------|
| `[UNVERIFIED]`       | Verifiable in principle but not yet checked.                              | warn             | warn             |
| `[MISSING_CITATION]` | A specific factual claim needs a source pointer (claim not in dispute). | warn             | warn             |
| `[SPECULATION]`      | Author conjecture / brainstorming layer.                                  | info             | warn             |
| `[INACCESSIBLE]`     | Source paywalled / image-only / DACO-gated / private; expected permanent. | info             | warn             |

`info`-severity tokens are counted by the scanner but do not contribute to `validate.sh`'s warning count nor cause a non-zero exit from `science refs check` unless `--strict` is set.

## Lexical scope

A token's *meaning* depends on whether it appears inside an inline-code span or a fenced code block:

- **Bare token** in prose (e.g., `the n is [UNVERIFIED] in the abstract`) is a **document annotation** and counts toward severity tallies.
- **Backticked token** (e.g., ``mark this `[UNVERIFIED]` per the convention``) is **documentation/example use** — referring to the token as a token. Excluded from tallies.
- Tokens inside fenced code blocks (` ``` `) are also excluded.

This split lets convention docs (this file included) discuss the tokens without polluting validation output.

## Choosing the right token

```
Is the claim verifiable from a source you can reach?
├── Yes → not yet checked → [UNVERIFIED]
├── Yes → checked, just need to write the cite → [MISSING_CITATION]
├── No  → because it's your own conjecture → [SPECULATION]
└── No  → because the source is paywalled / private / image-only → [INACCESSIBLE]
```

## Legacy alias

`[NEEDS CITATION]` is recognized as a synonym for `[MISSING_CITATION]` during the deprecation window. The scanner reports occurrences as canonical `[MISSING_CITATION]` but tags the underlying hit as `legacy: true` in JSON output. Run `science markers migrate --write` to rewrite legacy spellings in place. Backticked legacy spellings (in this doc, for example) are preserved.

## Tooling

- `science markers scan [--root .] [--format json|table] [--strict] [--include-documentation]` — scan project markdown for tokens.
- `science markers migrate [--root .] [--write]` — rewrite legacy `[NEEDS CITATION]` spellings to canonical `[MISSING_CITATION]`.
- `science refs check` and `validate.sh` both delegate marker counting to the same scanner.

## Future work (phase 3)

A richer sub-document annotation system (rich payloads, multi-annotation per ROI, graph integration) is deferred to a follow-up RFC. The four phase-2 tokens become annotation *types* under that design; existing inline tokens continue to work, and richer payloads opt into a sidecar form. See `docs/plans/2026-05-09-annotation-system-stub.md` for the full phase-3 sketch.

## See also

- [Prose lints](prose-lints.md) — mechanically-detectable prose issues
  (bare author-year, short-form IDs, frontmatter-inline gaps, numeric
  anchors). Lints surface candidates; the four-token vocabulary is the
  authoring output for claims that need LLM/human judgment.

## Full-text license whitelist (Phase 1 — source-text persistence)

`<citekey>.source.md` persists full text only when the resolved license is on
this whitelist. The persisted `license` frontmatter field records the raw value
verbatim; the canonical token below is used only for membership testing
(uppercased, spaces/underscores → hyphens, version suffix stripped).

| Canonical token | Versioned forms accepted | Persist full text? |
|-----------------|--------------------------|--------------------|
| `CC0`           | `CC0-1.0`                | yes |
| `CC-BY`         | `CC-BY-4.0`, `CC-BY-3.0` | yes |
| `CC-BY-SA`      | `CC-BY-SA-4.0`           | yes |
| `CC-BY-ND`      | `CC-BY-ND-4.0`           | yes |
| anything else (incl. `CC-BY-NC*`, `unknown`, absent) | — | **no** — abstract only; `fulltext_omitted_reason` is `license-not-whitelisted` when full text existed, else `no-fulltext-available` |

License is resolved from Europe PMC `license` in Phase 1 (Unpaywall's `oa_locations[].license` is deferred, with EPMC license the Phase 1 primary); with multiple values the most-permissive whitelisted one
wins, else `unknown`.

> Annotation-type and source-prefix vocabularies (e.g. `entity-gene`,
> `pubtator3:<release>:seeder-vN`) are introduced in Phase 2+; only the license
> whitelist is in scope for Phase 1.
