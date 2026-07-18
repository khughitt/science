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
- Skips biomedical timepoint/reagent shorthand in local context (for example, `D1`/`D7` samples or histone/reagent `H3` language).
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
  exclude_paths:
    - "doc/plans/historical/**"
  short_form_ids_deny:
    - "D1"   # cyclin D1 — biology shorthand, not a project entity ref
    - "H3"   # histone H3
    - "T1"   # T1-weighted MRI
  bare_author_year_deny:
    - "IMMULITE 2000"   # assay/product name, not an author-year citation
    - "CDC 2011"        # org+year, not an author-year citation
```

Defaults: all four checks enabled; `anchor_patterns` defaults to `["task:", "pipeline/", "\\[@", "data/", "scripts/"]`; `exclude_paths` defaults to `[]`.

`exclude_paths` is a list of project-relative glob patterns for markdown files that
should not be scanned. Use it for archived/generated prose snapshots whose text is
preserved for historical traceability rather than maintained as current project
claims.

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

## numeric-anchor (numeric provenance)

`numeric-anchor` classifies every numeric claim in a document's body prose into
exactly one of **four outcomes** — a discriminated assessment, not a boolean pass/fail:

- **NotClaim** — structural, not a quantitative claim (hardware id, accession
  number, license version, download size). Narrow and context-gated: a number
  is only excluded when it's adjacent to a triggering token (e.g. `RTX 3070`,
  `GCST90441`, `CC-BY-4.0`), never blanket-masked, so a real claim like "3.2 Gb
  genome" still counts.
- **Exempt** — the author has explicitly marked the claim as a stipulated
  parameter (marker syntax below). No provenance is expected for a stipulated
  design constant (e.g. `alpha = 0.05`).
- **Anchored** — declared, resolvable provenance covers the claim, at one of
  two scopes:
  - *entity scope* — a frontmatter provenance field (`source_refs`,
    `task_links`, `input`), paper identity (`doi`/`pmid`/`url`/`bibkey`),
    interpretation `artifact`/`artifacts`, or an owning `tNNN` named in the
    title — covers every claim in the document.
  - *local scope* — a resolvable `task:tNNN`, `[@citekey]`, `cite:key`, or
    `dataset:slug` reference in the **same paragraph** — covers only that
    paragraph.
- **Unanchored** — the genuine signal. No structural exclusion, no stipulated
  marker, and no resolvable source at either scope. This is what surfaces as a
  `numeric-anchor` finding.

**What a firing finding means.** A finding says "this number lacks a declared,
resolvable source at the appropriate scope" — it does **not** mean the value is
wrong. Treat it as a provenance gap to close, not a correctness accusation.

**Remediation is two-way.** Either:

1. **Mark it as stipulated**, if the number is a genuine design/methodology
   parameter that doesn't need an external source (see marker syntax below); or
2. **Provide resolvable provenance** — add/point to a frontmatter provenance
   field, or cite a `task:`/`[@key]`/`cite:`/`dataset:` reference in the same
   paragraph that actually resolves.

### Stipulated markers

Marker syntax is fixed (not a config knob), so tooling and templates agree
across projects:

| Form | Scope | Notes |
|------|-------|-------|
| Frontmatter `stipulated: true` | whole document | **Pure-spec docs only** (e.g. a `kind: pre-registration` or `kind: plan` doc that is *entirely* stipulated parameters). Never set this as a template default — it must be an explicit per-document author decision. |
| `<!-- stipulated -->` on the line under a heading | that heading's section | Fail-closed: covers down to (but not past) the next equal-or-higher-level heading. |
| `<!-- stipulated:start -->` … `<!-- stipulated:end -->` | the lines between the fence pair | Use inside an otherwise mixed section — e.g. a parameter block embedded in narrative prose that itself needs citations. |

Documents whose `kind` is in `spec_class_kinds` (default: `pre-registration`,
`plan`) get a more specific message when a claim is still unanchored —
`"stipulated parameter '<value>' lacks grounding"` — as a hint that these doc
kinds are exactly where marking-as-stipulated is expected. That hint does
**not** grant an automatic exemption; the doc still needs an explicit marker
or resolvable provenance like any other.

### Existence-checking

Provenance is now existence-checked, not just pattern-matched: a `task:t999`
that no task ledger declares, or an `artifact:` path that doesn't resolve to a
real file, is treated as **unresolved** and does not clear the claim. This is a
deliberate tightening (not a regression) — expect a few previously-hidden
fabricated references to newly surface as findings alongside the much larger
drop in false positives from entity/local-scope anchoring. See
[`docs/plans/2026-07-18-numeric-provenance-check-design.md`](../plans/2026-07-18-numeric-provenance-check-design.md)
for the full redesign rationale and empirical grounding.

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
