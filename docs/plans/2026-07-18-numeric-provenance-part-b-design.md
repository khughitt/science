# Numeric-Claim Provenance — Part B (MVP) Design

## Status

Proposed. **Revision 2 (2026-07-18, post-review).** The first draft was
reviewed against the shipped Part A code and revised on six points: the A/B
composition is now span-keyed (not a `SourceCandidate` contribution); Part B
carries its own full-token numeric grammar (Part A's `_NUMERIC_CLAIM_RE` drops
signs/exponents/bare-ints and accepts ratios); severity stays inside the
existing two-tier `info`/`warn` model (no invented `error` tier); artifact
resolution is a typed, symlink-safe, size-bounded reader boundary (not Part
A's boolean `resolve()`); the YAML binding is a fail-closed discriminated
schema; and numeric comparison is defined as `Decimal` interval membership.

This is the **first Part B cycle**: a working, testable vertical slice —
*authoring surface + verifier* — of the structured-numeric-claims end-state
sketched in `docs/plans/2026-07-18-numeric-provenance-check-design.md` (§ "Part
B"). Part A shipped and merged 2026-07-18. This cycle covers **less** than the
end-state deliberately: it verifies opt-in per-claim bindings for the two
formats the corpus uses (feather, JSON) and defers reproducibility-hardening
and mandatory-binding governance (§ Deferred).

## Context

Part A classifies each numeric claim in a document's body as `NotClaim /
Exempt / Anchored / Unanchored`, via a pure core
(`science/src/science_tool/numeric_provenance.py`) fed a `DocumentContext` and
a `ResolutionIndex` by the scanning layer. Its promise is *whether declared
provenance resolves at the right scope* — not *whether this exact value came
from that source*.

**What Part A does and does not give Part B.** It gives the module split to
imitate (pure classification core, injected I/O) and confirms the dependency
surface — science already ships `pyarrow>=24`, `pandas>=2`, `numpy>=2.4`, so
reading feather/JSON needs **no new dependency**. It does **not** give a reusable
value extractor: `_NUMERIC_CLAIM_RE` (`prose_lint.py:436`) drops a leading
sign, rejects exponent notation and bare integers below 100, and *accepts*
ratios like `12/15`. Exercised directly: `-7.94× → "7.94"`, `7.94e3 → no
match`, `8 → no match`. Part B therefore defines its **own** full-token grammar
(§ "Numeric grammar") shared by extraction, marker attachment, and comparison;
it does not reuse `_NUMERIC_CLAIM_RE`, and it does not rely on Part A's
`SourceCandidate` (which carries no claim identity — see § "Composition").

### Corpus grounding (why feather + JSON)

Sampling the health family's cited artifacts (pan-disease `entities/`):
data-bearing `artifact:` citations are **feather (dominant), then JSON**;
references across entities are 663 `.feather`, 257 `.json`, tsv/yaml/parquet in
the long tail. The single most-cited `artifact:` extension is `.md` (14) — but
those are *prose writeups*, not scalar sources. Direct signal: the verifier
must classify a non-data artifact (`.md`, `.png`, unsupported format, a
`task:`-only source) as **`unverifiable`**, never error, never pretend.

## Goals

- Let an author **opt-in bind** a specific prose number to `artifact +
  locator`, and **verify** the artifact's value matches the prose within the
  precision the prose displays — catching the fabricated/stale number the
  Part A token/anchor mechanism structurally cannot.
- Support the two formats the corpus uses (feather, JSON); declare everything
  else `unverifiable` honestly.
- Preserve Part A's purity split: pure grammar/parse/compare core; all disk
  I/O in one injected, size-bounded, symlink-safe reader boundary.
- Leave **unbound numbers untouched** — Part A behavior byte-for-byte
  unchanged for them.
- Give `numeric-verification` **exclusive ownership** of every syntactically
  bound claim (identified by exact span), so `numeric-anchor` suppresses it and
  the two checks never double-flag — regardless of verification outcome.

## Non-Goals (deferred to the follow-up cycle)

- **Reproducibility hardening**: artifact content-hash / revision pinning,
  units and percent normalization, rounding/normalization declarations, and
  repeated-value ambiguity beyond a `where:` key match.
- **Formats beyond feather/JSON**: csv/tsv/parquet readers.
- **Mandatory-binding governance**: promoting kinds from "entity-scope OK" to
  "headline numbers must bind."
- Not a per-number correctness checker for *unbound* numbers — the documented
  Part A recall boundary stands.
- No change to Part A `numeric-anchor` severity (`info`).
- No JSON `where:`-style selector for array-of-objects rows (§ Open questions).

## Decision

Ship a new **`numeric-verification`** check plus a small binding-authoring
surface. A binding is opt-in per claim, lives in frontmatter with an inline
pin, names a concrete artifact and a structured locator, and is verified by
reading the artifact and testing `Decimal` interval membership at the prose's
displayed precision. The check's base severity is **`warn`** (§ "Outcomes").

---

## 1. Authoring surface

Footnote-style **sidecar with inline pin**. An inline `[^id]` marker pins the
claim; a frontmatter `numeric_claims:` map binds `id → {artifact, locator,
tolerance?}`.

```markdown
---
numeric_claims:
  b1:
    artifact: "output/mm/qap.feather"
    locator:
      column: enrichment
      where: {disease: "MESH:D009101"}
  b2:
    artifact: "results/qap.json"
    locator: {pointer: "/results/0/pvalue"}
    tolerance: 5.0e-4
---
The QAP enrichment was **7.94×**[^b1] (p < 0.0001[^b2]), robust to reshuffling.
```

`numeric_claims:` (not bare `claims:`) is explicit and collision-safe —
confirmed absent from health-family entity frontmatter and science schemas.

### Marker ↔ claim attachment (fail-closed, Part-B grammar)

- The token bound by `[^id]` is the **maximal numeric token immediately
  preceding** the marker on the **same line**, parsed by Part B's grammar
  (§ "Numeric grammar"). Intervening inline markup (`**`, `×`, `%`, `)`)
  between the token and the marker is allowed.
- If the preceding token is **not a single scalar literal** under that grammar
  (e.g. a ratio `12/15`, a range `3–5`, prose), → **`error`**. Prefix-parsing
  is forbidden: `12/15[^id]` must not verify `12`.
- If no numeric token precedes the marker → **`error`**.

### Marker cardinality & graceful degradation

- A `[^id]` is a **binding only if `id` is a key in `numeric_claims:`**. A
  `[^x]` with no map entry is an ordinary markdown footnote — untouched.
- An `id` must be referenced by **exactly one** `[^id]` marker: **0** → `error`
  (orphan binding, declared but never referenced); **>1** → `error` (duplicate
  reference — a binding pins one number).

### Render caveat (documented, not blocking)

`[^id]` is markdown footnote syntax, but the definition lives in frontmatter,
so a renderer may show an unresolved footnote reference. Documented in the
convention; if it becomes a problem the pin can move to an invisible
`<!--#id-->` comment without touching the model. Not changing it for the MVP.

## 2. Binding schema (fail-closed)

The `numeric_claims:` value and each entry are validated by discriminated,
`extra="forbid"` input models before any I/O. Any violation is an authoring
**`error`** (not a silent skip):

- `numeric_claims` must be a **mapping**; a list/scalar → `error`.
- Each `id` key must be a **string**; each value a mapping with fields drawn
  from exactly `{artifact, locator, tolerance?}` — unknown fields → `error`.
- `artifact` is a required non-empty **string** path.
- `locator` is a **discriminated union**, exactly one shape:
  - `{pointer: "<json-pointer>"}` — JSON only.
  - `{column: "<name>"}` or `{column: "<name>", where: {<col>: <value>, …}}`
    — feather only.
  - Mixed keys (`{pointer, column}`), neither key, or an empty `where: {}` →
    `error`.
- `locator` shape must match the `artifact` **extension**: `pointer` on a
  non-`.json`, or `column` on a non-`.feather`, → `error`.
- `tolerance`, if present, must be a **finite number `> 0`**; negative, zero,
  `NaN`, or `±inf` → `error`.

## 3. Locator semantics

- **JSON** — `{pointer: "/results/0/enrichment"}`. RFC-6901; addresses exactly
  one node. Pointer that misses, or resolves to a non-scalar (object/array) or
  a non-numeric scalar (string, `true`/`false`, `null`) → `error`.
- **feather**:
  - `{column: enrichment}` — a **single-row** table. Column present with **>1**
    row and no `where:` → `error` (ambiguous).
  - `{column: enrichment, where: {disease: "MESH:D009101"}}` — equality match
    on one or more columns; never a positional index. `where:` matching **0**
    rows or **>1** rows → `error`.
  - Column absent, or the selected cell non-numeric → `error`.

### Feasibility boundary (honest)

`.json` and `.feather` are verifiable. `.md`, `.png`, `.txt`, any unsupported
extension, or a `task:`-only source with no concrete readable file →
**`unverifiable`** (declared, never faked). csv/tsv/parquet are deferred and
are `unverifiable` until the follow-up ships a reader.

## Numeric grammar (shared core)

One grammar governs prose extraction, marker attachment, and comparison:

- **Accepts** a single scalar literal: optional leading sign (`-`/`+`), integer
  part with optional thousands-commas, optional fractional part, optional
  `e`/`E` exponent, and an optional trailing unit glyph `×` or `%`. Examples
  accepted: `8`, `-7.94×`, `0.001`, `1,234`, `7.94e3`, `58%`.
- **Rejects** (→ `error` when marked): ratios (`12/15`), ranges (`3–5`,
  `3-5`), multiple numbers, non-numeric tokens. No prefix parsing — the token
  is consumed maximally and must parse **whole**.
- `parse_prose_literal(text) -> ParsedLiteral | None`, where `ParsedLiteral`
  carries the `Decimal` value, the count of displayed fractional digits, and
  any unit glyph. `%`/`×` handling for comparison: `×` is dropped (a
  fold-change label); `%` is **retained as an unsupported scale for the MVP**
  (§ "Verification").

## 4. Verification & match semantics

Per bound claim:

1. **Resolve the artifact** through Part B's typed resolver (§ "Module
   boundaries") to one canonical, regular-file path within an allowed root.
   Missing/dangling, absolute/`..`, ambiguous (present under both roots),
   symlink-escaping, non-regular-file, or over the size cap → `error`.
2. **Dispatch on extension**: `.json` → JSON reader; `.feather` → feather
   reader; otherwise → `unverifiable`.
3. **Extract the scalar** at the locator (§3), normalized to `Decimal` at the
   reader boundary (§ "Numeric normalization"). Extraction failure → `error`;
   a boolean/`NaN`/`±inf` cell → `error`.
4. **Parse the prose literal** (§ "Numeric grammar"). Unparseable / not a whole
   single literal → `error`. A `%` unit → `unverifiable` for the MVP (scale
   normalization is deferred; an absolute `tolerance` cannot meaningfully bridge
   `58%` vs a stored `0.58`), unless the author sets an explicit `tolerance`
   accepting responsibility.
5. **Interval membership at displayed precision.** A prose literal shown to `d`
   fractional digits denotes the closed interval `[v − ½·10⁻ᵈ, v + ½·10⁻ᵈ]`;
   `verified` iff the `Decimal` artifact value lies in it. An explicit
   per-claim `tolerance: t` replaces the interval with `[v − t, v + t]`. This
   is rounding-mode-free and defines negatives and boundaries (closed)
   unambiguously.

Worked cases (default policy):

```
prose "7.94×" (d=2)  artifact 7.94312  ∈ [7.935, 7.945]   → verified
prose "0.001" (d=3)  artifact 0.00098  ∈ [0.0005, 0.0015] → verified
prose "8"     (d=0)  artifact 7.9449   ∈ [7.5, 8.5]       → verified
prose "7.94"  (d=2)  artifact 7.951    ∉ [7.935, 7.945]   → mismatch
```

For exponent notation the interval is computed on the fully-expanded value at
the mantissa's scale (`7.94e3`, d=2 mantissa digits → `[7935, 7945]`).

### Numeric normalization

- JSON values: `int`/`float` accepted; `bool` is **not** a number → `error`;
  `NaN`/`±inf` → `error`. Convert `float` via `Decimal(str(x))` (shortest
  round-trip), `int` via `Decimal(x)`.
- feather/pandas/pyarrow cells: coerce to a Python scalar (`.item()`), reject
  `bool`/`NaN`/`±inf`, then normalize as above. Non-numeric dtype → `error`.

## 5. Outcomes & severity (inside the existing two-tier model)

`numeric-verification` is a single-severity **`warn`** check (added to
`DEFAULT_SEVERITY` as `warn`; unaffected by the `info→warn` strict promotion,
which does not apply). Per bound claim:

| outcome | emits | rationale |
|---|---|---|
| `verified` | **nothing** (success) | value matches |
| `mismatch` | a **`warn`** LintIssue | confirmed-wrong number — the signal |
| `error` | a **`warn`** LintIssue | binding broken (schema/read/locator; § matrix) |
| `unverifiable` | **nothing**; counted | honest, not machine-checkable |

- No new `error` **severity** is introduced (the framework has only
  `info`/`warn`, and validation discards non-`warn` detail hits —
  `prose_lints.py:136`). `mismatch` and `error` are both `warn`, distinguished
  by message. Under `--strict`, the existing CLI mechanism exits non-zero when
  any hit is present (`prose_lint_cli.py:98`).
- `verified` / `unverifiable` produce no LintIssue. Coverage — "bound numbers
  machine-verified vs merely bound" — is reported through the check's `counts`
  (`verified` / `unverifiable` / `mismatch` / `error`), which the CLI and
  validation summary already surface.

### Composition with Part A (span-keyed, no double-flag)

`parse_claim_bindings` yields a **binding map keyed by exact claim span**
`(line, col_start, col_end)`. `numeric-verification` owns **every** entry in
that map, regardless of outcome. The seam to Part A: `detect_numeric_anchor` /
`assess_numeric_claims` take a `bound_spans` set and **skip any claim whose
span intersects a bound span** — so a bound number never yields an `Unanchored`
finding, even when its binding is dangling (which surfaces once, as a
`numeric-verification` `error`). No `SourceCandidate` is contributed (that type
has no claim identity and would anchor unrelated numbers at paragraph/entity
scope).

## 6. Module boundaries (preserving Part A's purity split)

- **Pure grammar** — new `numeric_literal.py`: `parse_prose_literal` and the
  interval/`Decimal` comparison `compare_at_precision(parsed, value,
  tolerance=None) -> bool`.
- **Pure binding parse** — extend `numeric_provenance.py`:
  `ClaimBinding(id, artifact, locator, tolerance, span)` and
  `parse_claim_bindings(document) -> (bindings_by_span, authoring_errors)`,
  applying §1–§2 rules. Pure; no I/O.
- **Typed reader boundary** — new `artifact_value_reader.py`:
  - `resolve_artifact(ref, project_root, data_root) -> ResolvedArtifact |
    ArtifactError`. Rejects absolute/`..` (as Part A), realpath-resolves and
    requires the real path to stay within the **same** chosen root (symlink
    escape → error), requires a **regular file**, rejects presence under
    **both** roots (ambiguity → error), and enforces the size cap.
  - `read_scalar(resolved, locator) -> Decimal | ReaderError` — all
    pandas/pyarrow/json I/O; the only impure module added; normalizes per § 4.
- **New check** — `numeric-verification`, wired in the scanning layer beside
  `numeric-anchor`, registered across the same surfaces (`prose_lint.py`
  `DEFAULT_SEVERITY` + emission, `prose_lint_cli.py`,
  `validate/checks/prose_lints.py`, and the annotation adapter's detector
  version map). It reads each binding, calls the reader + comparator, emits the
  `warn` findings, and feeds `bound_spans` into the numeric-anchor pass.

## 7. Config surface (under `prose_lint`)

- `numeric-verification` added to the check registry; a **no-op when a document
  has no `numeric_claims:`** (I/O incurred only per binding), so on-by-default
  is safe.
- Reuses Part A's `project_root` / `data_root` for artifact resolution.
- `max_artifact_bytes` — resolver size cap, default **50 MB** for `.json`
  (whole-file parse) and **256 MB** for `.feather` (read is column-selective,
  but the cap guards pathological files). Configurable; over-cap → `error`.
- Per-claim `tolerance:` lives in the binding; no other new global knobs.

## 8. Error handling matrix (all `error`-outcome → `warn`)

| condition | outcome |
|---|---|
| `numeric_claims` not a mapping / entry not a mapping | `error` |
| unknown field in an entry; missing `artifact` | `error` |
| `locator` neither/both shapes; empty `where: {}` | `error` |
| `locator` shape ↔ artifact extension mismatch | `error` |
| `tolerance` not a finite number `> 0` | `error` |
| `[^id]` not immediately preceded by a numeric token | `error` |
| preceding token not a whole single scalar (ratio/range/prose) | `error` |
| `id` referenced by 0 markers (orphan) or >1 markers (duplicate) | `error` |
| `[^id]` present but `id` absent from map | *ignored* (real footnote) |
| artifact missing / dangling / absolute / `..` traversal | `error` |
| artifact present under **both** roots (ambiguous) | `error` |
| artifact symlink resolving outside its root; non-regular file | `error` |
| artifact over `max_artifact_bytes` | `error` |
| artifact extension unsupported, or `task:`-only source | `unverifiable` |
| prose `%` unit, no explicit `tolerance` | `unverifiable` |
| JSON pointer misses / non-scalar / non-numeric / `bool` / `null` | `error` |
| feather column absent; cell non-numeric; `bool`/`NaN`/`±inf` cell | `error` |
| feather `where:` matches 0, or >1 (or >1 row, no `where:`) | `error` |
| value read, within interval / `tolerance` | `verified` |
| value read, outside interval / `tolerance` | `mismatch` |

## 9. Testing

- **Pure units** (no I/O): `parse_prose_literal` across
  sign/decimals/exponent/commas/`×`/`%` and the reject set (`12/15`, `3–5`,
  multiple, prose); `compare_at_precision` across the worked table, exponent
  scale, boundary inclusivity, and the `tolerance` override;
  `parse_claim_bindings` including every §2 schema/cardinality branch, fail-
  closed attachment (non-adjacent, non-whole token), orphan, duplicate, and
  real-footnote passthrough.
- **Resolver units**: ambiguity (both roots), symlink escape (a fixture
  symlink pointing outside the root → `error`), non-regular file, `..`,
  absolute, over-cap.
- **Reader units** against tiny committed fixtures — JSON pointer hit / miss /
  non-scalar / `bool` / `null`; feather single-row, keyed row, 0-match,
  >1-match, missing column, non-numeric cell, `NaN` cell.
- **Fixture artifacts**: committed `.feather` (single-row *and* multi-row-keyed)
  and `.json` with known values under `tests/fixtures/`; entities binding
  across all outcomes.
- **End-to-end**: a `scan_root` run asserting `Bound` findings, their `warn`
  severity, and the `counts`; a small labeled verification-outcome set
  mirroring Part A's oracle discipline (labels reflect design, never bent to a
  buggy engine).
- **Composition**: a bound claim (verified, mismatch, *and* dangling) produces
  **no** `numeric-anchor` finding on that span (the `bound_spans` seam).

## 10. Deferred (named follow-up cycle)

content-hash / artifact revision pinning · units & percent normalization ·
rounding/normalization declarations · repeated-value ambiguity beyond `where:`
· csv/tsv/parquet readers · JSON `where:`-style selector for array rows ·
mandatory-binding governance per kind.

## Success criteria

- An author binds a prose number to a feather cell or JSON node; a matching
  value verifies silently; a wrong value is a `warn` `mismatch`.
- A binding to a non-data artifact is `unverifiable`, never errored, never
  silently passed; a `%`-unit claim without `tolerance` is `unverifiable`.
- A binding to a missing/dangling/ambiguous/escaping artifact, a missing
  column/pointer, an ambiguous row, or a broken schema is a `warn` `error` — no
  false `verified`.
- An unbound number's Part A assessment is byte-for-byte unchanged; a bound
  number (any outcome) draws **no** `numeric-anchor` finding on its span.
- All outcomes verified against the labeled oracle plus the fixture entities,
  including the fail-closed authoring, schema, and resolver controls.

## Open questions

- **JSON array-of-objects rows.** Addressed by positional pointer
  (`/3/enrichment`) — the instability `where:` avoids for feather. MVP
  position: acceptable, author's responsibility; a JSON `where:` selector is
  deferred (§10). Confirm acceptable.
- **Interval boundary inclusivity** is specified closed (`≤` both sides) for
  determinism; a value exactly at `v ± ½·10⁻ᵈ` verifies. Confirm the lenient
  choice is intended.
