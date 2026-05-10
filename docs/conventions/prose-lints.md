# Prose Lints

`science prose lint` detects four classes of prose-quality issue surfaced
by the natural-systems t466 citation-audit pilot. Each lint is mechanically
detectable; LLM-judgment claims (e.g., "field-state consensus claims") are
handled by the [annotation-token vocabulary](annotation-tokens.md), not by these lints.

## Lints

| Check (`--check=`)        | Detects                                                                                                              | Default severity |
|---------------------------|----------------------------------------------------------------------------------------------------------------------|------------------|
| `bare-author-year`        | `<Capitalized> <Year>` mentions (e.g., `Brunton 2022`) without an adjacent `[@key]` BibTeX-style anchor              | `warn`           |
| `short-form-ids`          | Bare `Q1`, `t088`, `q54` etc. — short forms of canonical entity refs                                                 | `warn`           |
| `frontmatter-inline-gap`  | Frontmatter `related:` entries that never appear in the document body                                                | `info`           |
| `numeric-anchor`          | Numeric claims (`ρ = 0.168`, `30%`, `n = 184`) without an anchor token (`task:`, `pipeline/`, `[@…]`) in the same paragraph | `info` |

`--strict` promotes all `info` issues to `warn` and exits non-zero on any issue.

## Lexical scope

All four lints respect the same scope rules as `science markers scan`:

- Skips YAML frontmatter.
- Skips fenced code blocks (triple-backtick).
- Skips inline code (single-backtick wrapped).
- Skips lines starting with `#` (markdown headers), `-`/`*` (lists), or `1.` (ordered list) for the numeric-anchor check.
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
```

Defaults: all four checks enabled; `anchor_patterns` defaults to `["task:", "pipeline/", "\\[@", "data/", "scripts/"]`.

`short_form_ids_deny` is a list of token strings (e.g., `D1`, `H3`, `t1`)
that the `short-form-ids` detector will skip. Useful for biology-heavy
projects where common shorthand collides with the canonical short-form
regex `\b([qQhHtTdDiI])(\d{1,4})\b`. See
[`docs/audits/2026-05-10-prose-lint-baselines.md`](../audits/2026-05-10-prose-lint-baselines.md)
for diagnostic guidance on whether your project actually needs a deny-list.

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
