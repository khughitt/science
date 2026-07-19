# Numeric-Claim Provenance — Part B (MVP) Design

## Status

Proposed. This is the **first Part B cycle**: a working, testable vertical
slice — *authoring surface + verifier* — of the structured-numeric-claims
end-state sketched in
`docs/plans/2026-07-18-numeric-provenance-check-design.md` (§ "Part B —
Structured numeric claims"). Part A (the precision overhaul of the
`numeric-anchor` lint) shipped and merged 2026-07-18; this design builds
directly on the assessment engine it left behind.

It deliberately covers **less** than the full end-state: it makes an opt-in
per-claim binding *verifiable* for the two formats the corpus actually uses
(feather, JSON), and defers reproducibility-hardening and mandatory-binding
governance to a named follow-up cycle (see § Deferred).

## Context

Part A classifies each numeric claim in a document's body as exactly one of
`NotClaim / Exempt / Anchored / Unanchored`, via a pure core
(`science/src/science_tool/numeric_provenance.py`) fed a `DocumentContext`
and a `ResolutionIndex` by the scanning layer. Its promise is *whether
declared provenance resolves at the right scope* — not *whether this exact
value came from that source*. The design doc states the boundary explicitly:

> "Resolvable source" belongs in Part A; "this exact value came from that
> locator" belongs in Part B.

Two facts from the Part A engine make Part B cheap to build on:

- Each claim is already captured as `NumericClaim(value, line, col,
  paragraph_id, section_id)` — the prose value and its exact location.
- Anchored claims already carry `Anchored.candidates: tuple[SourceCandidate,
  ...]`, which the design doc calls "B's binding menu."

And science already depends on `pyarrow>=24`, `pandas>=2`, `numpy>=2.4` —
reading feather/JSON to verify a value needs **no new dependency**.

### Corpus grounding (why feather + JSON)

Sampling the health family's cited artifacts (pan-disease
`entities/`): data-bearing `artifact:` citations are **feather (dominant),
then JSON**; pipeline references across entities are 663 `.feather`, 257
`.json`, with tsv/yaml/parquet in the long tail. The single most-cited
`artifact:` extension is `.md` (14) — but those are *prose writeups*, not
scalar sources. That is a direct design signal: the verifier must classify a
non-data artifact (`.md`, `.png`, unsupported format, a `task:`-only source)
as **`unverifiable`**, never error, never pretend.

## Goals

- Let an author **opt-in bind** a specific prose number to `artifact +
  locator`, and **verify** that the artifact's value matches the prose within
  the precision the prose displays — catching the fabricated/stale number the
  Part A token/anchor mechanism structurally cannot.
- Support the two formats the corpus uses (feather, JSON); declare everything
  else `unverifiable` honestly.
- Preserve Part A's purity split: pure classification/parse core, all disk
  I/O in a thin injected layer.
- Leave **unbound numbers untouched** — Part A behavior is unchanged for them.
- Make a bound claim's artifact double as a Part A `SourceCandidate`, so a
  bound number is `Anchored` (no `numeric-anchor` false-positive on it).

## Non-Goals (deferred to the follow-up cycle)

- **Reproducibility hardening**: artifact content-hash / revision pinning,
  units and percent normalization, rounding/normalization declarations, and
  repeated-value ambiguity beyond a `where:` key match.
- **Formats beyond feather/JSON**: csv/tsv/parquet readers (one reader each,
  intentionally out of scope).
- **Mandatory-binding governance**: promoting specific kinds (e.g.
  `interpretation`) from "entity-scope OK" to "headline numbers must bind."
- Not a per-number correctness checker for *unbound* numbers — that remains
  the documented Part A recall boundary.
- No change to Part A's `numeric-anchor` default severity (`info`).

## Decision

Ship a new **`numeric-verification`** check plus a small binding-authoring
surface. A binding is opt-in per claim, lives in frontmatter with an inline
pin, names a concrete artifact + a structured locator, and is verified by
reading the artifact and comparing at the prose's displayed precision.

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

### Key name

`numeric_claims:` (not bare `claims:`) — explicit and collision-safe;
confirmed absent from health-family entity frontmatter and from science
frontmatter schemas.

### Marker ↔ claim attachment (fail-closed)

- A binding attaches to the numeric claim **immediately preceding** its
  `[^id]` on the **same line**. Intervening inline markup (`**`, `×`, `%`,
  `)`) between the number and the marker is allowed.
- If no numeric claim immediately precedes the marker → **`error`**
  ("binding marker not attached to a number"). Fail closed: a marker that
  cannot be pinned to a number is a broken binding, not a silent pass.

### Graceful degradation with real footnotes

- A `[^id]` is a **binding only if `id` is a key in `numeric_claims:`**. A
  `[^x]` with no map entry is an ordinary markdown footnote — the check does
  not touch it.
- A `numeric_claims:` entry with **no inline `[^id]` reference** anywhere in
  the body → **`error`** (orphan binding — declared but never referenced).

### Render caveat (documented, not blocking)

`[^id]` is markdown footnote syntax, but the definition lives in frontmatter
rather than a `[^id]:` block, so a renderer may show an unresolved footnote
reference. This is documented in the convention. If it becomes a real
problem, the pin can move to an invisible `<!--#id-->` comment without
touching the binding model or the verifier — the pin's only job is to
identify *which* number. Not changing it for the MVP.

## 2. Locator grammar (structured YAML, format-discriminated)

The locator is a YAML mapping (no bespoke string grammar to parse or escape),
discriminated by which keys appear:

- **JSON** — `locator: {pointer: "/results/0/enrichment"}`. An RFC-6901 JSON
  Pointer; addresses exactly one node. Pointer that misses, or resolves to a
  non-scalar (object/array), or to a non-numeric scalar → `error`.
- **feather** — a column plus an optional stable row selector:
  - `locator: {column: enrichment}` — for a **single-row** summary table.
    More than one row present with no `where:` → `error` (ambiguous).
  - `locator: {column: enrichment, where: {disease: "MESH:D009101"}}` — a
    **keyed** row match. `where:` is an equality match on one or more
    columns. Never a positional row index (unstable across re-runs). `where:`
    matching **0** rows or **>1** rows → `error`.
  - Column absent, or the selected cell non-numeric → `error`.

### Feasibility boundary (honest)

`.json` and `.feather` are readable and verifiable. `.md`, `.png`, `.txt`,
any unsupported extension, or a `task:`-only source with no concrete readable
file → **`unverifiable`** (declared, never faked). csv/tsv/parquet are one
reader away and explicitly deferred — until then they are `unverifiable`.

## 3. Verification & match semantics

Per bound claim:

1. Resolve `artifact` through Part A's existing resolution machinery
   (existence-checked; absolute paths / `..` traversal rejected exactly as in
   Part A). Missing/dangling → `error`.
2. Dispatch on extension: `.json` → JSON reader; `.feather` → feather reader;
   otherwise → `unverifiable`.
3. Extract the scalar at the locator (§2). Any extraction failure → `error`.
4. Parse the prose value's **leading numeric literal**: optional sign,
   integer part with thousands-commas, optional decimals, optional `e`/`E`
   exponent, and an optional trailing `×`. Unparseable → `error`.
5. **Compare at displayed precision**: round the artifact value to the number
   of decimal places the prose literal shows, and require equality. For
   exponent notation (`7.94e3`), the precision is the mantissa's decimal
   places applied at the literal's scale — the comparison is made on the
   fully-expanded value (`7940` shown to the mantissa's 2 decimals → compare
   at the ±5 unit implied by that scale), not on the two mantissa digits in
   isolation. A per-claim `tolerance:` (absolute) overrides this when present
   (match iff `abs(artifact - prose) <= tolerance`).

Worked cases (default policy):

```
prose "7.94×"  artifact 7.94312  → round(…, 2dp)=7.94  == 7.94   verified
prose "0.001"  artifact 0.00098  → round(…, 3dp)=0.001 == 0.001  verified
prose "8"      artifact 7.9449   → round(…, 0dp)=8     == 8      verified
prose "7.94"   artifact 7.951    → round(…, 2dp)=7.95  != 7.94   mismatch
```

Unit/percent normalization (e.g. prose `58%` vs stored `0.58`) is **deferred**
— such a claim mismatches unless the artifact stores the display-native value
or the author sets an explicit `tolerance:`. The convention documents this
boundary.

## 4. Outcomes & severity

A new `Bound(status)` axis, orthogonal to Part A's `NotClaim / Exempt /
Anchored / Unanchored`:

| status | meaning | severity |
|---|---|---|
| `verified` | value read, matches at displayed precision | silent (success) |
| `mismatch` | value read, **differs** — the fabricated/stale-number signal | **`warn` default / `error` under `--strict`** |
| `unverifiable` | bound honestly, source not machine-readable | `info` |
| `error` | binding broken (see error matrix §7) | `warn` |

`mismatch` is deliberately **elevated above the `numeric-anchor` default
`info`**: a confirmed-wrong number is categorically worse than "no declared
provenance." `unverifiable` at `info` also powers a coverage signal —
"headline numbers machine-verified vs merely bound."

### Composition with Part A

A binding's `artifact` is contributed to the Part A candidate set as a
**resolved local `SourceCandidate`** (when it resolves), so the bound claim is
`Anchored` and `numeric-anchor` does not additionally flag it. The two checks
never double-flag the same number: Part A sees provenance-resolves;
`numeric-verification` owns the value-check.

## 5. Module boundaries (preserving Part A's purity split)

- **Pure core** — extend `numeric_provenance.py`:
  - `ClaimBinding(id, artifact, locator, tolerance, claim)` dataclass.
  - `parse_claim_bindings(document) -> (bindings, authoring_errors)` — reads
    the frontmatter `numeric_claims:` map, finds inline `[^id]` markers,
    applies the attachment/degradation rules (§1). Pure; no I/O.
  - Feed each resolved binding's `artifact` into the candidate set consumed by
    `assess_numeric_claims` (the A/B seam, §4).
- **I/O reader** — new module `artifact_value_reader.py`:
  - `read_scalar(path, locator) -> ReadResult` where `ReadResult` is a scalar
    value or a typed `ReaderError(kind, detail)`. Contains all pandas /
    pyarrow / json I/O; the only impure module added.
- **Pure compare** — `compare_at_displayed_precision(prose_literal,
  artifact_value, tolerance=None) -> bool`, plus
  `parse_prose_numeric_literal(text) -> Decimal | None`.
- **New check** — `numeric-verification`, wired in the scanning layer
  (alongside where `numeric-anchor` is wired): for each bound claim it calls
  `read_scalar`, then `compare_at_displayed_precision`, and emits the `Bound`
  finding. Registered in the same check registry / CLI / validation surfaces
  as `numeric-anchor` (parity across `prose_lint_cli.py`,
  `validate/checks/prose_lints.py`, and the annotation adapter's detector
  version map).

## 6. Config surface (under `prose_lint`)

- `numeric-verification` added to the check registry. It is a **no-op when a
  document has no `numeric_claims:`** (artifact I/O incurred only per binding),
  so enabling it by default is safe.
- Reuses Part A's `project_root` / `data_root` for artifact-path resolution —
  no new path config.
- Per-claim `tolerance:` lives in the binding, not global config. No new
  global knobs in the MVP.

## 7. Error handling matrix

| condition | outcome |
|---|---|
| `[^id]` marker not immediately preceded by a number | `error` |
| `numeric_claims:` entry with no inline `[^id]` reference | `error` (orphan) |
| `[^id]` present but `id` absent from map | *ignored* (real footnote) |
| artifact path missing / dangling / absolute / `..` traversal | `error` |
| artifact extension unsupported (`.md`/`.png`/`.txt`/…) or `task:`-only | `unverifiable` |
| JSON pointer misses / resolves to non-scalar / non-numeric | `error` |
| feather column absent | `error` |
| feather `where:` matches 0 rows | `error` |
| feather `where:` matches >1 rows, or >1 row with no `where:` | `error` (ambiguous) |
| selected cell non-numeric | `error` |
| prose value has no parseable leading numeric literal | `error` |
| value read, differs at displayed precision (no `tolerance`) | `mismatch` |
| value read, within `tolerance` | `verified` |

## 8. Testing

- **Pure units** (no I/O): binding parse; marker↔claim attachment incl.
  fail-closed non-adjacent, orphan entry, and real-footnote passthrough;
  `parse_prose_numeric_literal` across sign/decimals/exponent/commas/`×`;
  `compare_at_displayed_precision` across the worked-case table plus the
  `tolerance:` override; every `error`-producing branch of the reader dispatch
  (mocked).
- **Fixture artifacts**: tiny committed `.feather` (single-row *and*
  multi-row-keyed) and `.json` files with known values, under
  `tests/fixtures/`. Entities binding to them across all five outcomes:
  `verified`, `mismatch`, `unverifiable`, missing-artifact `error`,
  ambiguous-row `error`.
- **Reader units**: `read_scalar` against the fixtures — JSON pointer hit /
  miss / non-scalar; feather single-row, keyed row, 0-match, >1-match,
  missing column, non-numeric cell.
- **End-to-end**: a `scan_root` run over a fixture project asserting the
  `Bound` findings and their severities; a small labeled verification-outcome
  set mirroring Part A's oracle discipline (labels reflect design, never bent
  to a buggy engine).
- **Composition**: a bound+resolved claim produces **no** `numeric-anchor`
  finding (the A/B seam).

## 9. Deferred (named follow-up cycle)

content-hash / artifact revision pinning · units & percent normalization ·
rounding/normalization declarations · repeated-value ambiguity beyond
`where:` · csv/tsv/parquet readers · mandatory-binding governance per kind.

## Success criteria

- An author can bind a prose number to a feather cell or JSON node; a matching
  value verifies silently; a wrong value produces a `mismatch` at `warn`.
- A binding to a non-data artifact is reported `unverifiable`, never errored,
  never silently passed.
- A binding to a missing/dangling artifact, a missing column/pointer, or an
  ambiguous row produces an `error` — no false `verified`.
- An unbound number's Part A assessment is byte-for-byte unchanged; a
  bound+resolved number no longer draws a `numeric-anchor` finding.
- All outcomes verified against the labeled oracle plus the fixture entities,
  including the fail-closed authoring controls.

## Open questions

- **JSON array-of-objects rows.** A JSON artifact shaped like a table
  (`[{...}, {...}]`) can be addressed by pointer (`/3/enrichment`) but that is
  a positional index — the instability the feather `where:` selector exists to
  avoid. MVP position: JSON uses pointer as-is (author's responsibility if the
  array is unstable); a `where:`-style selector for JSON arrays is a
  follow-up. Confirm this is acceptable for the MVP.
- **`tolerance:` semantics** are absolute in this design. A relative form
  (`rtol`) is a plausible later addition; not in the MVP.
