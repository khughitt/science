# QA Check-Library (composable aspects & programs) — Design Spec

> **Status:** design (brainstormed 2026-06-13). Spins out **B2 (quantify QA breadth/depth)**
> from the discovery-improvements umbrella
> ([`2026-06-10-data-driven-discovery-improvements.md`](2026-06-10-data-driven-discovery-improvements.md),
> Theme B), **reframed and broadened** during brainstorming into a composable QA *check-library*
> (informally **B1.5**) from which breadth quantification falls out. Builds directly on the
> shipped **B1** runtime ([`2026-06-11-qa-toolkit-and-iteration-audit-design.md`](2026-06-11-qa-toolkit-and-iteration-audit-design.md)).
> Next step after approval: `writing-plans` → implementation.

## Motivation

The original B2 sketch was "a coverage score over QA checks." Brainstorming surfaced a stronger
framing: scoring breadth against an *invented* checklist is arbitrary, but scoring it against a
**declared QA program** is principled. And the deeper gap is that there is no reusable, composable
*library* of type-appropriate checks — every project hand-writes them, so know-how does not
propagate and QA cannot be built into a workflow from the start (TDD spirit).

So this spec reframes B2 into a **composable QA check-library**: shared, type-appropriate baseline
checks, composed per data type into named programs, with project-specific bug-driven checks layered
on top. **Breadth quantification then becomes a readout derived from the declared program** rather
than a separate checklist.

This **reconciles** the QA-checkpoint convention's "the check list grows from real bugs caught"
stance ([`../conventions/pipeline-qa-checkpoints.md`](../conventions/pipeline-qa-checkpoints.md))
with the reality that genuinely useful checks (missingness, type conformance, zero/variance/polarity
on numeric columns, gene-expression sanity) apply to *all* data of a kind. Both mechanisms coexist:
**baseline library + project extensions** — not bug-driven-only.

**Relationship to B1.** This *generalizes* B1, it does not discard it. B1's generic config checks
and the flat `scrna` pack are **re-homed** as composed aspects. The `science-qa` distribution and
its `Flag` dataclass, report/disposition machinery, and determinism property are reused unchanged.

## Design decisions (locked during brainstorming)

| Decision | Choice |
| --- | --- |
| Scoring basis | **Declared QA program is the breadth denominator** — not an invented universal checklist, not bug-driven-only. Baseline library + project extensions. |
| First-cut scope | **Vertical slice through scRNA, tidy-table substrate, + breadth readout.** Proves the substrate/aspect/program model end-to-end and re-seats the existing scRNA pack. |
| Core check contract | **`Check(context, params) -> list[Flag]`**, where `context` is **substrate-typed**. Column-set scoping is one substrate strategy (tables), *not* the permanent/universal contract. |
| First context | **`TableContext(table, columns)`** (pandas). The typed-context seam lets `MatrixContext` / `SparseExpressionContext` / graph / tensor land later without reworking the check protocol. |
| Aspect/program model | **Aspects** = flat, named, standalone check sets (no inheritance). **Program** = a named ordered *composition* of aspects bound to a substrate. Composition over inheritance. |
| Column resolution | **A separate concern from checks.** Selectors (`dtype` / `names` / `regex` / `named-set`) resolve columns; the check receives an already-resolved context and never knows why. |
| Context compatibility | **Declared + validated, fail-early.** Each check declares the context type it accepts; the runner hard-errors if a program binds it to the wrong substrate. No duck-typed try/skip. |
| `packs:` replacement | **Clean replacement, no compat layer.** The flat `packs: [scrna]` key is removed; scRNA behavior comes from `program: scrna-qc-table`. |
| Enforcement posture | **Advisory**, inherited from B1/B3. Never fails a build or `science validate`. Breadth is surfaced, not gated. |

## Architecture

The model is **substrate + aspect + program**, layered on B1's `science-qa` runtime.

### Core abstractions

- **`Context`** — substrate-typed input to a check. `TableContext(table: DataFrame, columns: list[str])`
  is the only one built now; it carries the full table plus the column selection a check operates
  over. The base is a typed family (future `MatrixContext`, `SparseExpressionContext`). A check
  declares which context type it consumes; the runner validates compatibility before invoking it
  (fail early — no silent skip).
- **`Check`** — `(context, params) -> list[Flag]`, reusing B1's `Flag` dataclass. A named callable
  with a declared `accepts: type[Context]` and a default severity. Universal checks carry documented
  defaults; project-parameterized checks (`ranges`, `categoricals`, `unique_key`) take their values
  from config.
- **`Aspect`** — a flat, named set of checks (`general`, `tabular`, `numeric-column`,
  `gene-expression-qc-table`, `scrna-qc-table`, `project-local`). No inheritance; aspects are
  standalone units composed by programs. One module per aspect under `science_qa/aspects/`.
- **`Program`** — a named, ordered composition of aspects bound to a substrate:
  `scrna-qc-table = general + tabular + numeric-column + gene-expression-qc-table + scrna-qc-table + project-local`.
  The program *is* the breadth denominator. Registry lives in `science_qa/program.py`.

### Column resolution (a separate unit)

A standalone `selectors` unit maps a selector spec + the table → a resolved column list. Selector
kinds: `dtype` (e.g. all numeric), `names` (explicit list), `regex`, `named-set` (reference a
config-declared `column_sets` entry). The runner resolves columns *then* constructs the
`TableContext`; checks never resolve their own columns. This keeps "why these columns" out of every
check and makes resolution independently testable.

### Substrate roadmap (this slice vs later)

- **This slice — tidy-table substrate.** `numeric-column` checks operate on numeric *columns* of a
  DataFrame (missingness, zeros, variance, polarity). Reuses B1's substrate (the per-cell QC-metrics
  table) and the existing pandas parquet/csv reader. No sparse-matrix engineering.
- **Next substrate family (documented, out of scope here)** — **expression-matrix QA**:
  `numeric-matrix + gene-expression-matrix + scrna-expression-matrix`, over a genes×cells matrix
  (sparse handling, row + column checks, collinearity at scale). `numeric-matrix` is a **distinct
  aspect** from `numeric-column` (true row/column matrix checks vs DataFrame column checks), sharing
  check *logic* underneath where it fits — never one overloaded name.
- **Mature target (documented)** — a scRNA workflow runs **two** programs, one per substrate (the
  expression matrix and the per-cell QC table), per the convention's "one QA step per substrate."

### Dependency direction (unchanged from B1)

One-way. Project pipeline → `science_qa` (light: pandas / pyarrow / pyyaml only). `science_tool`
(`science qa-audit`) reads the *artifacts* `science_qa` emits. The two packages never import each
other.

## The aspect stack & the scRNA program

Re-homing B1's checks exposes how little was actually scRNA-specific — the proof the decomposition
is real. `non_negative` and required-columns weren't scRNA at all; only the mito/doublet gates are.

| Aspect | Checks | Severity | Provenance |
|---|---|---|---|
| `general` | **non-empty (has rows)**, overall missing-fraction | **non-empty: structural**; missing-fraction: distribution | new |
| `tabular` | `unique_key`, `required_complete`, `categoricals` (`allowed` / `allowed_from`), `exclusive_flags`, type-conformance | structural | re-homed from B1 `run_structural_checks` |
| `numeric-column` | `missing_fraction`, `zero_fraction`, `low_variance`, `polarity` (non-negative-when-declared), `ranges`, `missing_sentinels` survivor-guard | mixed (ranges/zero/variance = distribution; sentinel survivor / declared-polarity = structural) | re-homed: B1 `ranges` + sentinels + scrna `non_negative` |
| `gene-expression-qc-table` | library-size positivity (`total_counts` > 0), detected-genes plausibility, degenerate-cell (all-QC-zero) | **structural by default** (post-QC substrate) | re-homed from B1 scrna `all_zero_cell` |
| `scrna-qc-table` | mito-% ceiling, gene-count floor/ceiling, doublet ceiling, fraction-failing-each-gate | distribution | re-homed from B1 scrna gates |
| `project-local` | project-registered extension check-ids (bug-driven additions) | per-check | new hook |

**Severity locks (from review):**

- **`general.non_empty` is structural.** A zero-row analysis substrate is not "suspicious but
  possibly real" — it means the workflow produced no analyzable substrate. Build-fatal.
- **Library-size positivity / all-QC-zero cells are structural by default.** B1 targets the
  *post-QC substrate the analysis consumes*; a zero library size there is a wrong table, not a
  plausible value. (Pre-filter raw QC summaries could treat these as distribution — that is a
  different, raw-substrate program, out of scope here. This program is post-QC, so: structural.)

**Program:** `scrna-qc-table`, bound to the table substrate, composing the six aspects above in
order. Flag IDs keep B1's namespaced shape `{source}/{check}/{subject}/{side}`, with `source` now
the **aspect** name (e.g. `numeric-column/low_variance/total_counts/-`,
`scrna-qc-table/threshold/pct_counts_mt/max`).

## Config & runner integration

The `qa:` block splits along one seam: **`program:` is the only declaration; everything else is
parameterization.**

```yaml
qa:
  program: scrna-qc-table          # WHAT runs (composed aspect/check inventory)  ← declaration
  unique_key: cell_id              # ── parameterization below ──
  ranges:    {n_genes_by_counts: {min: 200, max: 8000}}   # generic numeric plausibility
  column_sets:                     # resolver inputs (separate concern)
    numeric:        {dtype: numeric}
    expression_qc:  [total_counts, n_genes_by_counts, pct_counts_mt]
  aspect_params:                   # domain gates live with their aspect
    scrna-qc-table: {max_mito_pct: 20, min_genes: 200, max_genes: 8000, max_doublet: 0.3}
  project_local:   [my_project.qa:custom_check]
```

**Seam semantics (locked):**

- `program:` declares the **aspect/check inventory** — the full set of checks that *should* run.
- `column_sets`, `ranges`, `aspect_params`, `project_local` **only parameterize or expand** declared
  checks. They never alter program *shape* implicitly (no hidden program assembly via config keys).
- A declared check that requires params with **no value supplied** is either a **hard config error**
  or uses a **documented default** — **never silently skipped**.
- **No duplicate thresholds.** Generic `ranges:` is for *project-defined numeric plausibility*;
  scRNA biological gates live in `aspect_params.scrna-qc-table`. The same biological gate must not be
  expressed twice (e.g. `ranges.pct_counts_mt` *and* `aspect_params…max_mito_pct`) producing two
  flags with different IDs — unless that duplication is explicitly intended and configured.

`packs:` is **removed** (clean replacement, no compat layer). Runner flow:

1. Load config → resolve `program:` to its ordered aspect→check list. **Unknown program → hard
   error, exit 2.**
2. **Context-compat validation:** each check declares `accepts: type[Context]`; the runner asserts
   `isinstance(context, check.accepts)` else hard error naming check + program. All slice checks
   accept `TableContext`; the guard is built now so the matrix substrate lands safely later.
3. **Resolve columns** via the `selectors` unit → build `TableContext(table, resolved_columns)`.
4. Run each check with params (config or documented default) → `Flag`s.
5. Record each invocation's **resolution result** (which columns, including zero) for the readout.
6. Write `qa_report.{json,md}` + reconcile `qa_dispositions.yaml` — **unchanged from B1** (immutable
   ledger, analyst-owned dispositions never a rule output, determinism preserved).

## Breadth readout

The denominator is the **resolved invocations** from step 5 — concrete check invocations *after*
config resolution — not aspect membership. `numeric-column.low_variance` over five columns is a
different coverage fact from the same check resolving to zero columns.

**Per-invocation status (locked):**

- **`ran`** — selector resolved to ≥1 target; executed.
- **`empty`** — declared but the selector resolved to **0 targets** (the "looks covered, isn't"
  case — e.g. `low_variance` matched no numeric columns). Surfaced explicitly.
- **`not-applicable`** — an **optional** input is legitimately unavailable (e.g. the doublet-ceiling
  check when the program/config declares doublet scoring optional).
- **A missing *required* input is NOT `not-applicable`.** It is a **structural flag** (e.g.
  `scrna-qc-table` missing `pct_counts_mt`) or a **config error** — never benign N/A. `not-applicable`
  is reserved for declared-optional checks only.

**Emission.** A deterministic `coverage` block in `qa_report.json` (pure function of
program + config + table — preserves re-run-and-diff) plus a Coverage section in `qa_report.md`:
aspects-in-program vs aspects-with-a-`ran`-check, check counts by status, and the **shallow/narrow
signal** = the explicit list of `empty` / `not-applicable` invocations. Descriptive coverage facts,
not a single opaque score (an optional `ran / (ran + empty)` ratio is secondary).

**Consumer.** `science qa-audit` (B3) already reads `qa_report.json` per workflow → it gains one
**breadth column** reading this `coverage` block, so the advisory table shows iteration verdict ·
engagement verdict · coverage together. Small, since the block already exists by audit time.

## Locked semantics (summary)

- `empty` = selector resolved to **zero** targets.
- `not-applicable` = a declared-**optional** input legitimately unavailable.
- A **missing required input** = a **structural flag** or a **config error** (never N/A).
- `general.non_empty`, library-size positivity, and all-QC-zero cells are **structural** (post-QC
  substrate).
- A declared check missing required params = **hard config error or documented default**, never a
  silent skip.
- **No duplicate generic/domain thresholds** for the same gate unless explicitly configured.
- **B1 parity:** `program: scrna-qc-table` detects the **same defects with the same severities** as
  the prior `packs: [scrna]`; flag IDs change `source` only (re-homing remaps scrna's checks onto
  `numeric-column` / `gene-expression-qc-table` / `scrna-qc-table`).

## Doc & convention changes (extend, don't rediscover)

1. [`../conventions/pipeline-qa-checkpoints.md`](../conventions/pipeline-qa-checkpoints.md) — reframe
   to **baseline library + project extensions** (not bug-driven-only): document the
   substrate/aspect/program model, that `science_qa` composes programs from aspects, and the breadth
   coverage readout. The convention stays the contract; the library is one composition of it.
2. [`../process/pipeline-audit-and-refactor.md`](../process/pipeline-audit-and-refactor.md) — note
   **QA breadth/coverage** as a dimension of the axis-1 data-QA / process-iteration discipline, with
   the `science qa-audit` breadth column as its readout.
3. [`../../aspects/computational-analysis/computational-analysis.md`](../../aspects/computational-analysis/computational-analysis.md)
   — extend the `review-pipeline` *QA Coverage* rubric to reference program breadth (which aspects of
   the declared program ran; `empty`/`not-applicable` invocations are the narrow-checking signal).
4. [`2026-06-10-data-driven-discovery-improvements.md`](2026-06-10-data-driven-discovery-improvements.md)
   — update the B2 entry to record the B1.5 reframing (composable check-library; breadth as a
   program-derived readout).

## Error handling (fail-early, explicit — no silent fallback)

- Unknown `program:` name → hard error, exit 2.
- A check bound to an incompatible context type → hard error naming check + program (no try/skip).
- A declared check whose required params are absent → hard config error (or documented default);
  never silently skipped.
- A program/aspect requiring a column absent from the table → **structural flag** (required) — not a
  silent pass and not `not-applicable`.
- Unknown selector kind, or a `named-set` referencing an undeclared `column_sets` entry → hard error.
- Disposition reconciliation and the `--no-strict` exit-code contract are inherited unchanged from B1.

## Testing (TDD, red → green)

- **Selectors:** `dtype` / `names` / `regex` / `named-set` → expected resolved columns, including the
  **empty-resolution** case; undeclared named-set → error.
- **Context compatibility:** a check declaring an incompatible `accepts` → hard error (build the
  guard now even though all slice checks are `TableContext`).
- **Per-aspect checks:** each aspect's checks fire / clear on tiny seeded fixtures; severity is as
  locked (e.g. `general.non_empty` structural; library-size positivity structural).
- **Program composition:** `scrna-qc-table` resolves to the expected ordered aspect→check inventory.
- **B1 parity (load-bearing):** `program: scrna-qc-table` over the B1 scRNA fixtures detects the
  **same defects with the same severities** as the previous `packs: [scrna]` — flag IDs differ only
  in the `source` prefix (re-homing remaps scrna's checks onto `numeric-column` /
  `gene-expression-qc-table` / `scrna-qc-table`) — proving the re-homing is behavior-preserving.
- **Breadth readout:** `ran` / `empty` / `not-applicable` statuses; missing **required** input →
  structural flag (not N/A); declared-**optional** missing input → `not-applicable`;
  **determinism** (byte-identical `coverage` block for the same program+config+table).
- **Config:** program selection; unknown program → exit 2; missing-required-param → error-or-default
  (never silent skip); duplicate-threshold guard.
- **qa-audit breadth column:** reads the `coverage` block; a report without it degrades gracefully
  (no crash; column blank/`-`).
- **Doc changes:** verified via existing markdown link-check / `science validate`.

## Out of scope (explicit)

- **Expression-matrix substrate** (genes×cells, sparse handling, `numeric-matrix` /
  `gene-expression-matrix` / `scrna-expression-matrix` aspects) — documented as the next substrate
  family.
- **The two-program mature target** (matrix + per-cell QC table per workflow) — documented; needs the
  matrix substrate first.
- **Additional modality programs** (bulk RNA, genomics CN/SV, amplicon) — mechanical follow-ons once
  the aspect model proves out on scRNA.
- **A single opaque "QA score" number** — breadth is reported as structured, descriptive coverage
  facts.
- **Any `science validate` gating** — advisory only, inherited from B1/B3.
- **Changes to B1's report/disposition/determinism machinery or `science qa-audit`'s verdict axes** —
  reused unchanged; the only B3 change is the additive breadth column.

## Provenance

- Source talk: `talk:Johri2026` (`meta/doc/background/talks/Johri2026.md`).
- Umbrella: [`2026-06-10-data-driven-discovery-improvements.md`](2026-06-10-data-driven-discovery-improvements.md),
  Theme B (B2, reframed to the B1.5 check-library).
- Builds on shipped B1/B3: [`2026-06-11-qa-toolkit-and-iteration-audit-design.md`](2026-06-11-qa-toolkit-and-iteration-audit-design.md)
  (the `science-qa` runtime, `Flag`, reports, dispositions, determinism; `science qa-audit`).
