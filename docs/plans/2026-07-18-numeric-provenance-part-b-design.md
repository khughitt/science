# Numeric-Claim Provenance — Part B (MVP) Design

## Status

Proposed. **Revision 3 (2026-07-18, post-review).** Two review rounds against
the shipped Part A code hardened the design. Rev 2 fixed the A/B composition
(span-keyed, not `SourceCandidate`), Part B's own numeric grammar, the
severity model, the typed resolver, the fail-closed schema, and `Decimal`
comparison. Rev 3 fixes six follow-ups: the two checks are an **atomic pair**
so bound-claim ownership never depends on check selection; an explicit
**`opaque` locator** makes `unverifiable` reachable (and `task:`-only sources
are dropped — the binding artifact is always a path); coverage tallies live in
a **separate typed field**, not nested in `counts`; the displayed-precision
interval uses a **display quantum** `q` (correct under exponent notation);
`%` units are **unconditionally `unverifiable`**; and JSON is parsed
**directly into `Decimal`**. The default precision interval is now **open**
with midpoint → `unverifiable` (author tolerances stay closed).

This is the **first Part B cycle**: a working, testable vertical slice —
*authoring surface + verifier* — of the structured-numeric-claims end-state
sketched in `docs/plans/2026-07-18-numeric-provenance-check-design.md` (§ "Part
B"). Part A shipped and merged 2026-07-18. This cycle covers **less** than the
end-state deliberately: it verifies opt-in per-claim bindings for feather and
JSON, and defers reproducibility-hardening and mandatory-binding governance
(§ Deferred).

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
(§ "Numeric grammar") and does not rely on Part A's `SourceCandidate` (which
carries no claim identity — see § "Composition").

### Corpus grounding (why feather + JSON)

Sampling the health family's cited artifacts (pan-disease `entities/`):
data-bearing `artifact:` citations are **feather (dominant), then JSON**;
references across entities are 663 `.feather`, 257 `.json`, tsv/yaml/parquet in
the long tail. The most-cited `artifact:` extension is `.md` (14) — *prose
writeups*, not scalar sources. Direct signal: an author must be able to bind a
number whose source is a concrete non-data artifact and have it declared
**`unverifiable`**, never faked (the `opaque` locator, §2).

## Goals

- Let an author **opt-in bind** a specific prose number to a concrete
  **artifact path + locator**, and **verify** the artifact's value matches the
  prose within displayed precision — catching the fabricated/stale number the
  Part A anchor mechanism structurally cannot.
- Support the two data formats the corpus uses (feather, JSON); let any other
  artifact be **explicitly** declared `unverifiable` via an `opaque` locator.
- Preserve Part A's purity split: pure grammar/parse/compare core; all disk
  I/O in one injected, size-bounded, symlink-safe reader boundary.
- Leave **unbound numbers untouched** — Part A behavior byte-for-byte unchanged.
- Give `numeric-verification` **exclusive ownership** of every syntactically
  bound claim (by exact span), so `numeric-anchor` suppresses it — and, because
  the two checks are an **atomic pair**, a bound claim is *always* both
  suppressed and verified, never one without the other.

## Non-Goals (deferred to the follow-up cycle)

- **Reproducibility hardening**: content-hash / revision pinning, units and
  percent normalization, rounding/normalization declarations, repeated-value
  ambiguity beyond a `where:` key match.
- **Formats beyond feather/JSON**: csv/tsv/parquet readers.
- **Non-path sources**: `task:`/`cite:`/DOI sources as binding targets. The
  binding artifact is a file path; task-provenance stays in Part A frontmatter.
- **Mandatory-binding governance**: promoting kinds to "headline numbers must
  bind."
- Not a per-number correctness checker for *unbound* numbers.
- No change to Part A `numeric-anchor` severity (`info`); no JSON `where:`
  selector for array rows (§ Open questions).

## Decision

Ship a new **`numeric-verification`** check, coupled to `numeric-anchor` as an
atomic pair, plus a small binding-authoring surface. A binding is opt-in per
claim, lives in frontmatter with an inline pin, names a concrete artifact path
and a structured locator, and is verified by reading the artifact and testing
`Decimal` interval membership at the prose's displayed precision. The check's
base severity is **`warn`** (§ "Outcomes").

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
    locator: {column: enrichment, where: {disease: "MESH:D009101"}}
  b2:
    artifact: "results/qap.json"
    locator: {pointer: "/results/0/pvalue"}
    tolerance: 5.0e-4
  b3:
    artifact: "figures/panel_b.png"
    locator: {opaque: "read off figure panel B"}
---
The QAP enrichment was **7.94×**[^b1] (p < 0.0001[^b2]); effect visible[^b3].
```

`numeric_claims:` (not bare `claims:`) is explicit and collision-safe —
confirmed absent from health-family entity frontmatter and science schemas.

### Marker ↔ claim attachment (fail-closed, Part-B grammar)

- The token bound by `[^id]` is the **maximal numeric token immediately
  preceding** the marker on the **same line**, parsed by Part B's grammar
  (§ "Numeric grammar"). Intervening inline markup (`**`, `×`, `%`, `)`) is
  allowed. An `opaque` binding may instead pin a **non-numeric** anchor word
  (as in `visible[^b3]`), since there is nothing to compare.
- For a **non-opaque** binding, if the preceding token is **not a single scalar
  literal** (a ratio `12/15`, a range `3–5`, prose), → **`error`**.
  Prefix-parsing is forbidden: `12/15[^id]` must not verify `12`.
- If a non-opaque binding has no numeric token preceding the marker → `error`.

### Marker cardinality & graceful degradation

- A `[^id]` is a **binding only if `id` is a key in `numeric_claims:`**. A
  `[^x]` with no map entry is an ordinary markdown footnote — untouched.
- Each `id` must be referenced by **exactly one** `[^id]` marker: **0** →
  `error` (orphan); **>1** → `error` (duplicate — a binding pins one number).

### Render caveat (documented, not blocking)

`[^id]` is markdown footnote syntax with the definition in frontmatter, so a
renderer may show an unresolved reference. Documented in the convention; the
pin can later move to an invisible `<!--#id-->` comment without touching the
model. Not changing it for the MVP.

## 2. Binding schema (fail-closed)

`numeric_claims` and each entry are validated by discriminated,
`extra="forbid"` models **before any I/O**. Any violation is an authoring
**`error`**:

- `numeric_claims` must be a **mapping**; a list/scalar → `error`.
- Each `id` key is a **string**; each value a mapping over exactly
  `{artifact, locator, tolerance?}` — unknown fields → `error`.
- `artifact` is a required non-empty **string path** (never a `task:`/`cite:`
  ref in this MVP).
- `locator` is a **discriminated union**, exactly one shape:
  - `{pointer: "<json-pointer>"}` — JSON artifacts only.
  - `{column: "<name>"}` or `{column, where: {<col>: <value>, …}}` — feather
    only; `where` (if present) must be a **non-empty** mapping.
  - `{opaque: "<non-empty reason>"}` — any artifact; declares the value
    human-read / not machine-extractable → outcome `unverifiable`.
  - Zero or more-than-one of `{pointer, column, opaque}`, or an empty
    `where: {}`, → `error`.
- For `pointer`/`column` the locator shape must match the `artifact`
  **extension** (`pointer`↔`.json`, `column`↔`.feather`); mismatch → `error`.
  `opaque` imposes no extension constraint.
- `tolerance`, if present, must be a **finite number `> 0`** (only meaningful
  with `pointer`/`column`); negative/zero/`NaN`/`±inf` → `error`.

## 3. Locator semantics

- **JSON** — `{pointer: "/results/0/enrichment"}`. RFC-6901; addresses exactly
  one node. Pointer that misses, or resolves to a non-scalar (object/array) or
  a non-numeric scalar (string, `true`/`false`, `null`) → `error`.
- **feather**:
  - `{column: enrichment}` — a **single-row** table; column present with **>1**
    row and no `where:` → `error` (ambiguous).
  - `{column, where: {disease: "MESH:D009101"}}` — equality match on one or more
    columns; never a positional index. `where:` matching **0** or **>1** rows →
    `error`.
  - Column absent, or selected cell non-numeric → `error`.
- **opaque** — no read is attempted; outcome `unverifiable` regardless of the
  artifact's existence or extension. This is the *only* route to a declared
  `unverifiable` (a data locator on a non-data extension is an `error`, not
  `unverifiable`).

## Numeric grammar (shared core)

One grammar governs prose extraction, marker attachment, and comparison:

- **Accepts** a single scalar literal: optional leading sign (`-`/`+`), integer
  part with optional thousands-commas, optional fractional part, optional
  `e`/`E` exponent, and an optional trailing unit glyph `×` or `%`. Accepted:
  `8`, `-7.94×`, `0.001`, `1,234`, `7.94e3`, `58%`.
- **Rejects** (→ `error` when marked non-opaque): ratios (`12/15`), ranges
  (`3–5`), multiple numbers, non-numeric tokens. The token is consumed
  maximally and must parse **whole** — no prefix parsing.
- `parse_prose_literal(text) -> ParsedLiteral | None`. `ParsedLiteral` carries
  the `Decimal` mantissa value `v`, a **display quantum**
  `q = 10^(exponent − fractional_digits)` (the place value of the least
  significant displayed digit; `q = 1` for `"8"`, `0.01` for `"7.94"`, `10`
  for `"7.94e3"`), and any unit glyph.
- `×` is dropped (a fold-change label). `%` marks the literal **percent-scaled**
  → the claim is **unconditionally `unverifiable`** in this MVP (scale
  normalization is deferred; an absolute `tolerance` cannot bridge `58%` vs a
  stored `0.58`, so it is not permitted to try).

## 4. Verification & match semantics

Per bound claim:

1. If the locator is `opaque` → `unverifiable` (no I/O).
2. **Resolve the artifact** via the typed resolver (§ "Module boundaries") to
   one canonical, regular-file path within an allowed root. Missing/dangling,
   absolute/`..`, ambiguous (present under both roots), symlink-escaping,
   non-regular-file, or over the size cap → `error`.
3. **Dispatch on extension**: `.json` → JSON reader; `.feather` → feather
   reader. (A non-data extension cannot reach here: with a `pointer`/`column`
   locator it failed §2 extension validation; with `opaque` it returned at
   step 1.)
4. **Extract the scalar** at the locator (§3), normalized to `Decimal` at the
   reader boundary (§ "Numeric normalization"). Extraction failure, or a
   `bool`/`NaN`/`±inf` value → `error`.
5. **Parse the prose literal** (§ "Numeric grammar"). Not a whole single
   literal → `error`. A `%` unit → `unverifiable`.
6. **Interval membership.** Let `q` be the literal's display quantum.
   - **Default (no tolerance):** the **open** interval `(v − q/2, v + q/2)`;
     `verified` iff `v − q/2 < a < v + q/2`. A value exactly on a boundary
     (`a == v ± q/2`) → **`unverifiable`** (it is the midpoint shared with the
     adjacent display value — e.g. `7.945` is ambiguous between prose `7.94`
     and `7.95`; rounding declarations that would resolve it are deferred).
     Otherwise → `mismatch`.
   - **Explicit `tolerance: t`:** the **closed** interval `[v − t, v + t]`;
     `verified` iff `|a − v| ≤ t`, else `mismatch` (no boundary-`unverifiable`
     — the author asserted the tolerance).

Worked cases (default policy):

```
prose "7.94×" q=0.01  artifact 7.94312  ∈ (7.935, 7.945)  → verified
prose "0.001" q=0.001 artifact 0.00098  ∈ (0.0005,0.0015) → verified
prose "8"     q=1     artifact 7.9449    ∈ (7.5, 8.5)      → verified
prose "7.94"  q=0.01  artifact 7.951     ∉ (7.935, 7.945)  → mismatch
prose "7.94"  q=0.01  artifact 7.945     == boundary        → unverifiable
prose "7.94e3" q=10   artifact 7943.1    ∈ (7935, 7945)    → verified
```

### Numeric normalization

- **JSON**: parse with `json.load(..., parse_float=Decimal, parse_int=Decimal)`
  and a `parse_constant` that **rejects** `NaN`/`Infinity`/`-Infinity` — the
  artifact's decimal digits are preserved exactly, never routed through binary
  `float`. A JSON `bool`/`null`/string at the pointer → `error`.
- **feather** (inherently binary floats): coerce the cell to a Python scalar
  (`.item()`), reject `bool`/`NaN`/`±inf`, convert `float` via
  `Decimal(str(x))` (shortest round-trip) and `int` via `Decimal(x)`. Non-numeric
  dtype → `error`.

## 5. Outcomes, severity & coverage (inside the existing contract)

`numeric-verification` is a single-severity **`warn`** check (added to
`DEFAULT_SEVERITY` as `warn`; the `info→warn` strict promotion does not apply).
Per bound claim:

| outcome | emits `LintIssue`? | rationale |
|---|---|---|
| `verified` | no | value matches |
| `mismatch` | **`warn`** | confirmed-wrong number — the signal |
| `error` | **`warn`** | binding broken (schema/read/locator; § matrix) |
| `unverifiable` | no | honest, not machine-checkable |

- No new `error` **severity**: the framework has only `info`/`warn`, and
  validation discards non-`warn` detail hits (`prose_lints.py:139`). `mismatch`
  and `error` are both `warn`, distinguished by message. `--strict` uses the
  existing non-zero-exit-on-any-hit mechanism (`prose_lint_cli.py:99`).

### Coverage is a separate typed field (not `counts`)

`counts` stays exactly as built — `{check: emitted_issue_count}` derived from
`LintIssue`s (`prose_lint.py:820`); for `numeric-verification` that is
`mismatch + error`. Nested outcome tallies would break validation's numeric
`count <= 0` comparison (`prose_lints.py:140`). So `scan_root` gains a
**separate** `coverage` field:

```
coverage["numeric-verification"] = {verified, unverifiable, mismatch, error}
```

Presentation changes are explicit deliverables:
- **CLI** — `_render_table` currently returns early on zero hits
  (`prose_lint_cli.py:104`); it must print a one-line coverage summary even
  when there are no findings, so a fully-`verified` scan reports coverage
  rather than "no issues found."
- **validation** — surface `coverage` as an **advisory** (`info`) Result,
  distinct from the `warn` `mismatch`/`error` findings; it must not be routed
  through the `counts` warn/advisory logic.

### Composition with Part A (span-keyed, atomic pair)

`parse_claim_bindings` yields a **binding map keyed by exact claim span**
`(line, col_start, col_end)`. Two consequences:

- **Suppression is unconditional wherever `numeric-anchor` runs.**
  `detect_numeric_anchor` / `assess_numeric_claims` take a `bound_spans` set
  and **skip any claim whose span intersects a bound span** — so a bound number
  never yields an `Unanchored` finding, in *any* surface: the scanner, CLI,
  validation, and the annotation adapter (`annotation/sources/lint.py:96`),
  which reconstructs historical anchor findings and must apply the same
  suppression to avoid mis-flagging.
- **The two checks are an atomic pair in the selectable-check surfaces.**
  Selecting `numeric-anchor` runs `numeric-verification` and vice versa (in
  `enabled_checks`, `--check`, and validation), so a document's bindings are
  *always* both suppressed **and** verified — never suppressed-but-unchecked
  (silent trust) nor flagged-because-verification-was-off. No `SourceCandidate`
  is contributed (that type has no claim identity and would anchor unrelated
  numbers at paragraph/entity scope).

## 6. Module boundaries (preserving Part A's purity split)

- **Pure grammar** — new `numeric_literal.py`: `parse_prose_literal` (→
  `ParsedLiteral` with `v`, `q`, unit) and `compare_at_precision(parsed, value,
  tolerance=None) -> {verified, mismatch, unverifiable}`.
- **Pure binding parse** — extend `numeric_provenance.py`:
  `ClaimBinding(id, artifact, locator, tolerance, span)` and
  `parse_claim_bindings(document) -> (bindings_by_span, authoring_errors)`,
  applying §1–§2. Pure; no I/O. Also add the `bound_spans` parameter to
  `assess_numeric_claims` / `detect_numeric_anchor` for suppression.
- **Typed reader boundary** — new `artifact_value_reader.py`:
  - `resolve_artifact(ref, project_root, data_root) -> ResolvedArtifact |
    ArtifactError`: rejects absolute/`..`; realpath-resolves and requires the
    real path to stay within the **same** chosen root (symlink escape →
    error); requires a **regular file**; rejects presence under **both** roots
    (ambiguity → error); enforces the size cap.
  - `read_scalar(resolved, locator) -> Decimal | ReaderError` — all
    pandas/pyarrow/json I/O (JSON via `Decimal` per §4); the only impure
    module added.
- **New check** — `numeric-verification`, coupled to `numeric-anchor`
  (§5), wired across `prose_lint.py` (`DEFAULT_SEVERITY`, emission, `coverage`),
  `prose_lint_cli.py` (coupling, coverage rendering), the validation check
  (`validate/checks/prose_lints.py`: coupling, coverage advisory), and the
  annotation detector-version map. It reads each binding, calls the reader +
  comparator, emits `warn` findings, populates `coverage`, and feeds
  `bound_spans` into the anchor pass.

## 7. Config surface (under `prose_lint`)

- `numeric-verification` in the check registry, coupled to `numeric-anchor`
  (selecting either enables both). A **no-op when a document has no
  `numeric_claims:`** (I/O only per binding), so on-by-default is safe.
- Reuses Part A's `project_root` / `data_root` for artifact resolution.
- `max_json_bytes` (default **50 MB**, whole-file parse) and `max_feather_bytes`
  (default **256 MB**; reads are column-selective but the cap guards
  pathological files). Over-cap → `error`.
- Per-claim `tolerance:` in the binding; no other new global knobs.

## 8. Error handling matrix (all `error`-outcome → `warn`)

| condition | outcome |
|---|---|
| `numeric_claims` not a mapping / entry not a mapping | `error` |
| unknown field in an entry; missing/empty `artifact` | `error` |
| `locator` not exactly one of `{pointer, column, opaque}`; empty `where: {}` | `error` |
| `pointer`/`column` locator ↔ artifact extension mismatch | `error` |
| `tolerance` not finite `> 0`, or present with `opaque` | `error` |
| non-opaque `[^id]` not preceded by a numeric token | `error` |
| non-opaque preceding token not a whole single scalar (ratio/range/prose) | `error` |
| `id` referenced by 0 markers (orphan) or >1 markers (duplicate) | `error` |
| `[^id]` present but `id` absent from map | *ignored* (real footnote) |
| artifact missing / dangling / absolute / `..` | `error` |
| artifact present under **both** roots (ambiguous) | `error` |
| artifact symlink resolving outside its root; non-regular file | `error` |
| artifact over `max_json_bytes` / `max_feather_bytes` | `error` |
| JSON pointer misses / non-scalar / non-numeric / `bool` / `null` | `error` |
| feather column absent; cell non-numeric; `bool`/`NaN`/`±inf` | `error` |
| feather `where:` matches 0, or >1 (or >1 row with no `where:`) | `error` |
| `opaque` locator (any artifact) | `unverifiable` |
| prose `%` unit | `unverifiable` |
| value read, exactly on a default-precision boundary | `unverifiable` |
| value read, inside open interval / closed `tolerance` | `verified` |
| value read, outside interval / `tolerance` | `mismatch` |

## 9. Testing

- **Pure units** (no I/O): `parse_prose_literal` across
  sign/decimals/exponent/commas/`×`/`%` and the reject set (`12/15`, `3–5`,
  multiple, prose), asserting `q` per case; `compare_at_precision` across the
  worked table, exponent scale, **open-boundary → unverifiable**, and the
  closed `tolerance` override; `parse_claim_bindings` for every §2
  schema/cardinality branch, the three locator shapes, opaque-on-non-numeric-
  anchor, fail-closed attachment, orphan, duplicate, and real-footnote
  passthrough.
- **Resolver units**: ambiguity (both roots); symlink escape (fixture symlink
  outside the root → `error`); non-regular file; `..`; absolute; over-cap.
- **Reader units** against tiny committed fixtures — JSON `Decimal` fidelity
  (a value whose binary `float` round-trip would lose a digit), pointer hit /
  miss / non-scalar / `bool` / `null`; feather single-row, keyed row, 0-match,
  >1-match, missing column, non-numeric / `NaN` cell.
- **Fixture artifacts**: committed `.feather` (single- and multi-row-keyed) and
  `.json` with known values under `tests/fixtures/`; entities binding across
  all outcomes incl. `opaque` and the `%` case.
- **End-to-end**: a `scan_root` run asserting `Bound` `warn` findings, the
  `coverage` field, and the CLI coverage line on a fully-verified scan; a small
  labeled verification-outcome set mirroring Part A's oracle discipline.
- **Composition & coupling**: a bound claim (verified, mismatch, *and*
  dangling) draws **no** `numeric-anchor` finding on its span; selecting only
  `numeric-anchor` still verifies bindings (atomic pair); the annotation
  adapter suppresses bound spans.

## 10. Deferred (named follow-up cycle)

content-hash / artifact revision pinning · units & percent normalization ·
rounding/normalization declarations · repeated-value ambiguity beyond `where:`
· csv/tsv/parquet readers · JSON `where:`-style selector for array rows ·
mandatory-binding governance per kind.

## Success criteria

- An author binds a prose number to a feather cell or JSON node; a matching
  value verifies silently; a wrong value is a `warn` `mismatch`.
- A number sourced from a non-data artifact is bound with an `opaque` locator
  and reported `unverifiable`; a `%`-unit claim is `unverifiable`; neither is
  ever silently passed as `verified`.
- A binding to a missing/dangling/ambiguous/escaping artifact, a missing
  column/pointer, an ambiguous row, or a broken schema is a `warn` `error` — no
  false `verified`.
- An unbound number's Part A assessment is byte-for-byte unchanged; a bound
  number (any outcome) draws **no** `numeric-anchor` finding on its span, under
  every check selection.
- JSON decimal digits are preserved (no binary-`float` loss); the default
  precision interval is open with a midpoint reported `unverifiable`.
- All outcomes verified against the labeled oracle plus fixtures, including the
  fail-closed authoring, schema, resolver, and coupling controls.

## Open questions (resolved in review; recorded for the plan)

1. **JSON array-of-objects rows** stay on positional pointer (`/3/enrichment`)
   for the MVP; the limitation is explicit and a JSON `where:` selector is
   named for follow-up (§10). *Accepted.*
2. **Default precision intervals are open**, not closed: closed intervals let
   `7.945` verify both `7.94` and `7.95`. An exact midpoint is `unverifiable`
   (rounding declarations that would disambiguate are deferred); author-provided
   `tolerance` stays closed. *Accepted.*
