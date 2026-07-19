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
real file or directory, is treated as **unresolved** and does not clear the claim. This is a
deliberate tightening (not a regression) — expect a few previously-hidden
fabricated references to newly surface as findings alongside the much larger
drop in false positives from entity/local-scope anchoring. See
[`docs/plans/2026-07-18-numeric-provenance-check-design.md`](../plans/2026-07-18-numeric-provenance-check-design.md)
for the full redesign rationale and empirical grounding.

## numeric-verification (structured numeric claims)

`numeric-anchor` (above) checks that a numeric claim has *declared,
resolvable provenance* — a citation, task, or artifact reference nearby. It
does not check that the number is *correct*. `numeric-verification` is the
companion check that closes that gap for claims an author opts into binding:
it reads the claim's value out of a real artifact (a `.feather` cell or a
`.json` node) and compares it against the prose literal.

### Authoring shape

A binding is a **footnote-style sidecar with an inline pin**: a frontmatter
`numeric_claims:` map declares `id → {artifact, locator, tolerance?}`, and an
inline `[^id]` marker pins the claim by attaching to the numeric literal
immediately before it on the same line. The binding does **not** restate the
prose value — the verifier reads both the prose number and the artifact
value independently and compares them, so a stale or fabricated prose number
is caught rather than trusted.

```markdown
---
numeric_claims:
  b1:
    artifact: "output/mm/qap.feather"
    locator: {column: enrichment, where: {disease: "MESH:D009101"}}
  b2:
    artifact: "results/qap.json"
    locator: {pointer: "/results/0/pvalue"}
    tolerance: 5.0e-4
  b3:
    artifact: "figures/panel_b.png"
    locator: {opaque: "read off figure panel B"}
---
The QAP enrichment was **7.94×**[^b1] (p < 0.0001[^b2]); peak near **2.1×**[^b3].
```

`id` must match the marker charset `^[A-Za-z0-9_-]+$` — a `numeric_claims`
key outside it can never be referenced by a `[^id]` marker and is an
authoring error. Every binding — **`opaque` included** — must pin a numeric
literal immediately before its marker; a non-number, a ratio (`12/15`), or a
range (`3–5`) in that position is an error, never a silently-dropped
coverage gap. A `[^id]` whose `id` has no `numeric_claims` entry is an
ordinary markdown footnote and is left untouched.

### Locator forms

A `locator` is exactly one of three shapes:

- **`pointer:`** — an RFC-6901 JSON pointer into a `.json` artifact, e.g.
  `{pointer: "/results/0/pvalue"}`. Must address exactly one numeric scalar
  node.
- **`column:`** (+ optional `where:`) — reads a `.feather` artifact.
  `column` names the value column. `where:` selects exactly one row by an
  **equality match on named columns** — never a positional index — so
  `{column: enrichment, where: {disease: "MESH:D009101"}}` reads the
  `enrichment` cell of the row keyed by `disease`. Omitting `where:` is only
  valid against a single-row table; a `where:` that matches zero or more
  than one row is an error.
- **`opaque:`** — any artifact, with a free-text reason (e.g. "read off
  figure panel B"). The value is **not machine-read** — the claim always
  comes out `unverifiable` — but the artifact path is still resolved (must
  exist, must be a regular file, must not escape its root); a missing or
  invalid `opaque` artifact is still an **`error`**, not a silent pass.

### Outcomes and severity

Each bound claim is classified into exactly one of four outcomes:

| outcome | emits a finding? | meaning |
|---|---|---|
| `verified` | no (silent) | artifact value matches the prose literal |
| `unverifiable` | no (silent, counted) | honestly not machine-checkable (`opaque`, or a `%`-unit claim) |
| `mismatch` | **warn** | artifact value contradicts the prose literal — the signal |
| `error` | **warn** | the binding itself is broken (bad schema, unresolvable artifact, missing column/pointer, ambiguous row, etc.) |

Only `mismatch` and `error` produce a lint issue; `verified` and
`unverifiable` are silent in the findings list and show up only in the
coverage tally (below).

### Coupling with `numeric-anchor`

`numeric-anchor` and `numeric-verification` are an **atomic pair**: selecting
either one in `--check`, `enabled_checks`, or `science validate` runs both.
This guarantees a bound claim is always both suppressed from
`numeric-anchor` (a bound number never draws an "unanchored" finding — its
provenance is the binding itself) *and* actually verified — never
suppressed-but-unchecked, and never flagged for lacking an anchor it doesn't
need.

### `%` and `opaque` are unverifiable, but still resolve

A `%`-unit prose literal (e.g. `58%`) and an `opaque` locator both report
`unverifiable` unconditionally — percent-scale normalization isn't
attempted, and an opaque value is by definition not machine-read. Neither
of these skips artifact resolution, though: the artifact path must still
exist, stay within its allowed root, and be a regular file. A missing,
escaping, or ambiguous artifact is an `error` in both cases — fail-closed,
so `opaque`/`%` can never be used to launder a broken binding into a quiet
pass.

### Displayed-precision matching

Without an explicit `tolerance:`, a claim verifies if the artifact value
falls in the **open interval** implied by the prose literal's displayed
precision — `± half the last displayed digit's place value`. For example
`7.94×` has a place value of `0.01`, so it verifies against any artifact
value in `(7.935, 7.945)`. A value that lands exactly on that boundary is
**`unverifiable`**, not `verified` — it's equally consistent with the
adjacent displayed value (`7.945` could round to either `7.94` or `7.95`).
An explicit `tolerance:` (a positive number) replaces this with a **closed**
interval `[value − tolerance, value + tolerance]` and no boundary carve-out.

### Config

Reads are size-bounded: `max_json_bytes` (default 50 MiB, whole-file parse)
and `max_feather_bytes` (default 256 MiB) cap how large a bound artifact may
be. An over-cap artifact is an `error`, not a silent skip.

### Coverage tally

Because `verified`/`unverifiable` never appear as findings, both
`science prose lint` and `science validate` surface a separate per-project
**coverage** tally — counts of `verified` / `unverifiable` / `mismatch` /
`error` across all bound claims — as an advisory, so a fully-verified
document still reports how much of its numeric-claim surface is bound and
checked rather than showing "no issues found."

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
