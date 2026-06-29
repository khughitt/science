# Prose Lints

`science prose lint` detects four classes of prose-quality issue surfaced
by the natural-systems t466 citation-audit pilot. Each lint is mechanically
detectable; LLM-judgment claims (e.g., "field-state consensus claims") are
handled by the [annotation-token vocabulary](annotation-tokens.md), not by these lints.

## Lints

| Check (`--check=`)        | Detects                                                                                                              | Default severity |
|---------------------------|----------------------------------------------------------------------------------------------------------------------|------------------|
| `bare-author-year`        | `<Capitalized> <Year>` mentions (e.g., `Brunton 2022`) without an adjacent `[@key]` BibTeX-style anchor; **bib-aware** — when `papers/references.bib` exists, flags only mentions whose author is in the bibliography | `warn`           |
| `short-form-ids`          | Bare `Q1`, `t088`, `q54` etc. — short forms of canonical entity refs                                                 | `warn`           |
| `frontmatter-inline-gap`  | Frontmatter `related:` entries that never appear in the document body                                                | `info`           |
| `numeric-anchor`          | Numeric claims (`ρ = 0.168`, `30%`, `n = 184`) without an anchor token (`task:`, `pipeline/`, `[@…]`) in the same paragraph | `info` |

`--strict` promotes all `info` issues to `warn` and exits non-zero on any issue.

## Lexical scope

All four lints respect the same scope rules as `science markers scan`:

- Skips YAML frontmatter.
- Skips fenced code blocks (triple-backtick).
- Skips inline code (single-backtick wrapped).
- Skips lines starting with `#` (markdown headers), Markdown list items including wrapped continuation lines, or `|` (markdown tables) for the numeric-anchor check.
- Treats comma-grouped numerics as one claim token (for example, `5,424`, not `424`).
- Skips numeric fragments embedded in DOI/accession-style identifiers (for example, `10.1038/s41586-021-03836-1`, `PMID:24390350`, or `t070`).
- Skips common cell-line tokens that collide with uppercase short-form IDs (for example, `H929`).
- Skips task-list headers of the shape `## [t088] Title` for the short-form-ids check.

## Project config

`science.yaml` may include an optional `prose_lint:` block:

```yaml
prose_lint:
  enabled_checks:
    - bare-author-year
    - short-form-ids
    - frontmatter-inline-gap
    - numeric-anchor
  anchor_patterns:
    - "task:"
    - "pipeline/"
    - "\\[@"
  short_form_ids_deny:
    - "D1"   # cyclin D1 — biology shorthand, not a project entity ref
    - "H3"   # histone H3
    - "T1"   # T1-weighted MRI
  bare_author_year_deny:
    - "IMMULITE 2000"   # assay/product name, not an author-year citation
    - "CDC 2011"        # org+year, not an author-year citation
```

Defaults: all four checks enabled; `anchor_patterns` defaults to `["task:", "pipeline/", "\\[@", "data/", "scripts/"]`.

`short_form_ids_deny` is a list of token strings (e.g., `D1`, `H3`, `t1`)
that the `short-form-ids` detector will skip. Useful for biology-heavy
projects where common shorthand collides with the canonical short-form
regex `\b([qQhHtTdDiI])(\d{1,4})\b`. See
[`docs/audits/2026-05-10-prose-lint-baselines.md`](../audits/2026-05-10-prose-lint-baselines.md)
for diagnostic guidance on whether your project actually needs a deny-list.

`bare-author-year` is **driveable to zero** by design, mirroring `short-form-ids`:

- **Bib-awareness (resolver).** When `papers/references.bib` exists, the detector
  flags only `<Surname> <Year>` mentions whose surname matches an author in the
  bibliography — i.e. "you have this paper but never cited it with `[@key]`".
  Secondary citations to papers *not* in the bib, and non-author false positives
  (journal/org/product fragments like `Metab 2005`, `NHANES 2015`, `IMMULITE 2000`),
  are skipped by construction. With no `references.bib`, the check falls back to
  flagging every unanchored mention.
- **`bare_author_year_deny`** is a list of exact `<Surname> <Year>` strings to skip,
  for any residual false positive the resolver can't exclude — parity with
  `short_form_ids_deny`.

This is why `bare-author-year` is a `warn`-tier check: like `short-form-ids` it has
both a resolver and a deny-list, so a well-maintained project can drive it to zero.

## Tooling

- `science prose lint --root . --format table` — run all lints, render to terminal.
- `science prose lint --root . --format json` — JSON output (used by `validate.sh`).
- `science prose lint --check bare-author-year` — run a single lint.
- `science prose lint --strict` — promote info → warn, exit 1 on any issue.

## validate.sh integration

`validate.sh` runs `$SCIENCE_TOOL prose lint --format json` as **Section 18** and emits per-check counts in its summary. Default behavior reports info-severity issues without failing; `validate.sh --strict` (or `science prose lint --strict`) promotes them.

## Origin

These lints were extracted from the natural-systems citation-audit pilot
(t466) which identified six recurring patterns across audited prose. The
four mechanically-detectable patterns are implemented here. The two
LLM-judgment patterns ("field-state consensus claims unsupported" and the
broader "load-bearing claim has no anchor") are handled by the
[annotation-token vocabulary](annotation-tokens.md): an LLM auditor or
human writer marks them with `[SPECULATION]` or `[MISSING_CITATION]`, and
`science markers scan` counts them.

## Related: `science refs check --include-body`

Where prose-lint detects authoring patterns ("you wrote a short-form ID;
canonical form is `<kind>:<id>`"), `science refs check --include-body`
detects unresolved typed refs in body prose ("you wrote `task:t999` but no
project file declares that `id:`"). The two are complementary; run both.
