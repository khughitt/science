# QA Toolkit & Iteration Audit — Design Spec

> **Status:** design (brainstormed 2026-06-11). Spins out **B1 (QA-check toolkit)** and
> **B3 (no-iteration flagging)** from the discovery-improvements umbrella
> ([`2026-06-10-data-driven-discovery-improvements.md`](2026-06-10-data-driven-discovery-improvements.md),
> Theme B). Next step after approval: `writing-plans` → implementation.

## Motivation

The MIA seminar *"Evaluating AI agents in biological discovery"* (`talk:Johri2026`,
`cite:Johri2026`) reported that AI agents iterated only on cell-type **annotations**, never on
QC / clustering resolution / parameters — they followed the canned scanpy recipe verbatim,
while every real paper deviates for dataset-specific reasons. *"No computational biologist
one-shots the analysis."* Two gaps in Science follow:

- **B1 — no reusable QA code.** The QA-checkpoint convention
  ([`../conventions/pipeline-qa-checkpoints.md`](../conventions/pipeline-qa-checkpoints.md))
  fully specifies a `qa:` config schema and a structural/distribution severity split, but every
  project hand-writes the script that implements them. There is no shared runtime, so fixes and
  modality know-how don't propagate.
- **B3 — a one-shot analysis is invisible.** A `build → run-once → record → "truth"` workflow is
  indistinguishable from a properly iterated one. Nothing surfaces "ran once, recorded as truth
  while QA flags went unexamined."

This spec builds a small QA runtime that *implements* the existing convention, plus an advisory
audit that makes (non-)iteration visible — without re-proposing the conventions, and without
turning QA into a validator-enforced gate (the convention is deliberately project-side
discipline).

**Scope note — baseline.** Independent of the held `epistemic-edges` /
`dataset-evidence-flow` substrate. The only existing machinery this relies on is the
`computational-analysis` **run lifecycle** — `workflow-run` entities linked by `sci:supersedes`
on re-execution with updated parameters (already defined in
[`../../aspects/computational-analysis/computational-analysis.md`](../../aspects/computational-analysis/computational-analysis.md),
*Workflow Lifecycle*).

## Design decisions (locked during brainstorming)

| Decision | Choice |
| --- | --- |
| B1 toolkit form | **Config-driven runner + modality check-packs** (hybrid). Generic checks come from config; domain checks come from importable packs. |
| B3 iteration signal | **Run-supersession chain depth + QA-response evidence.** Reading the run chain *and* whether any distribution flag was dispositioned. |
| Enforcement posture | **Advisory CLI audit.** Never fails a build or `science validate`. Surfaced via the audit playbook + `review-pipeline` rubric. |
| First-cut scope | **Vertical slice, one pack** (scRNA). Generic runner + disposition record + B3 audit. B2 (breadth scoring) and other packs deferred. |
| Packaging | **Standalone `science_qa` runtime package** for the runner + packs; B3 audit as a `science_tool` CLI subcommand. One-way dependency. |

## Architecture

Four units — one new package, one new CLI subcommand, one project artifact:

| # | Unit | Home | Responsibility |
|---|------|------|----------------|
| 1 | QA config-runner | `science_qa` (new pkg, `science/qa/`) | Reads the `qa:` YAML + a built table → runs generic structural/distribution checks → writes `qa_report.{md,json}` |
| 2 | scRNA check-pack | `science_qa.packs.scrna` | Domain checks declarative config can't express (mito-fraction, doublet rate, gene/cell-count gates) |
| 3 | QA-disposition record | project artifact `qa_dispositions.yaml` | Per-distribution-flag analyst response; runner emits a stub, analyst fills it, git-tracked |
| 4 | Iteration audit (B3) | `science_tool` → `science qa-audit` | Reads workflow-run/`supersedes` chains + dispositions via run manifests → advisory process-quality report |

**Dependency arrow is one-way.** Project pipeline → `science_qa` (light deps: pandas / pyarrow /
pyyaml — *not* `science_tool`). `science_tool` → reads the *artifacts* `science_qa` emits. The
two packages never import each other. This keeps the pipeline-runtime install small and the
graph-tooling ignorant of pipeline internals.

### Data flow

```
pipeline build (Snakemake rule)
  └─ python -m science_qa run --config qa.yaml --table analysis.parquet
       ├─ structural flag fired? → exit non-zero (build-fatal)
       └─ writes qa_report.{md,json}  +  qa_dispositions.yaml (stub: open distribution flags)
                                          │
analyst reviews distribution flags ──────┘ (fills disposition + optional param change → may re-run)
  re-run with changed params → new workflow-run, sci:supersedes prior run

later, project-level:
  science qa-audit
    └─ for each workflow: walk run chain + read qa_report.json / qa_dispositions.yaml (via run manifest)
         → verdict: ITERATED / SINGLE-RUN / SINGLE-RUN-WITH-OPEN-FLAGS / NO-QA  (advisory; exits 0)
         → referenced as an audit-playbook line + review-pipeline rubric row
```

The disposition file is the seam between B1 and B3: a declared output of the QA rule (so it lives
in the run manifest and B3 can find it), but its *contents* are filled in by the analyst after
the fact.

## Unit 1 — config-runner (`science_qa run`)

**Config: reuse the convention's `qa:` block verbatim, add two keys.** The runner reads the exact
schema `pipeline-qa-checkpoints.md` already specifies — `unique_key`, `required_complete`,
`categoricals` (`allowed` / `allowed_from`), `exclusive_flags`, `ranges`, `missing_sentinels` —
so existing hand-written QA configs become runner input with zero translation. Additions:

- `packs: [scrna]` — modality packs to run.
- `pack_params:` — per-pack settings, e.g. `scrna: {max_mito_pct: 20}`.

Thresholds stay config-driven and single-source (shared with the cleaning step), per the
convention.

**Severity contract (unchanged from the convention).**

- **Structural** — key non-uniqueness, required-complete violation, illegal categorical /
  `allowed_from` subset violation, exclusive-flag co-occurrence, sentinel survivors, pack
  structural flags. The table is *wrong* → **build-fatal**.
- **Distribution** — range exceedances, outlier counts, heavy tails, pack plausibility flags.
  *Suspicious but possibly real* → surfaced, never auto-corrected.

**Outputs — two files, deterministic.**

- `qa_report.md` — the convention's report skeleton (counts header, flags by severity,
  per-variable distribution table). Human-facing.
- `qa_report.json` — machine-readable: every flag with a **stable `flag_id` = `f"{variable}:{check}"`**
  (e.g. `glucose:range`, `mito_pct:scrna_mito`), plus `severity`, observed `value`, `threshold`,
  `message`. This is what the disposition file and B3 key against.

**No wall-clock** in either file — same config + table → byte-identical output. This preserves the
re-run-and-diff property Theme D will later depend on.

**Exit & cleanup contract.** Run all checks, write both reports, *then* `sys.exit(1)` if any
structural flag fired. `--no-strict` suppresses only the exit code (structural flags still run and
still appear in the report); never wire it into the default target. Per the convention's
failed-job-cleanup warning, the reports must **not** be declared as the strict rule's `output:` —
projects write them outside that rule's output set, or use the two-rule split (an always-write
report rule + a downstream strict-gate rule), so the build-fatal path never deletes the report.

**CLI:** `python -m science_qa run --config qa.yaml --table analysis.parquet [--report-dir results/<wf>/] [--no-strict]`.

## Unit 2 — scRNA check-pack (`science_qa.packs.scrna`)

**Pack interface — composition, not inheritance.** A pack is a module exposing one callable:

```python
def run(table: DataFrame, params: dict) -> list[Flag]
```

The runner invokes each pack named in `packs:` and merges its `Flag`s into the same
structural/distribution buckets. Adding a pack is registering a callable — no base class. `Flag`
is the shared dataclass the runner emits (`flag_id`, `severity`, `variable`, `value`, `threshold`,
`message`).

**Substrate: the per-cell QC-metrics table** (one row per cell: `total_counts`,
`n_genes_by_counts`, `pct_counts_mt`, optional `doublet_score`) — the processed substrate analysis
consumes, not the raw matrix, so it stays table-shaped like the runner.

**Checks:**

- *Structural:* required QC columns present; counts non-negative; no all-zero cells.
- *Distribution:* `pct_counts_mt` above `max_mito_pct`; `n_genes_by_counts` below `min_genes` or
  above `max_genes`; `total_counts` below `min_counts`; `doublet_score` above `max_doublet`;
  fraction of cells failing each gate.

**Params (config-driven, documented defaults):** `max_mito_pct: 20`, `min_genes: 200`,
`max_genes: 8000`, `min_counts: 500`, `max_doublet: 0.3`.

## Unit 3 — QA-disposition record (`qa_dispositions.yaml`)

The seam between B1 and B3. Distribution flags are "analyst decides at model time"; this file
*captures* that decision. Structural flags are build-fatal and never appear here (fix, don't
disposition).

- **Runner emits / reconciles a stub.** On each run: if the file is absent, write one open entry
  per distribution `flag_id`; if present, **merge by `flag_id`** — preserve filled entries, add
  stubs for new flags, mark vanished flags `resolved`. The merge is reported explicitly
  (`"2 new flags, 1 resolved, 3 unchanged"`) and **never silently overwrites** analyst edits.
- **Entry schema:** `flag_id`, `disposition ∈ {accepted-real, addressed, investigating, wont-fix}`,
  `note`, optional `change` (what param/config moved, when `addressed`).
- Declared as a QA-rule output → listed in the run manifest → discoverable by B3.

A flag dispositioned `addressed` with a `change`, alongside a `supersedes` re-run, is B3's positive
evidence of genuine iteration; an untouched stub file is the "ran once, recorded as truth"
signature.

## Unit 4 — iteration audit (`science qa-audit`)

Lives in `science_tool` (it reads the entity graph). For each `workflow` entity it walks the
`workflow-run` chain (`executes` edges) and `supersedes` links, then locates that workflow's QA
artifacts through each run's manifest — the runner declares `qa_report.json` and
`qa_dispositions.yaml` as manifest resources tagged `role: qa-report` / `role: qa-dispositions`,
so discovery is **explicit**, never path-guessing.

**Per-workflow verdict:**

- **ITERATED** — supersedes chain depth ≥ 2, *or* ≥ 1 distribution flag dispositioned
  (`addressed` / `accepted-real` / `wont-fix`). The analyst engaged.
- **SINGLE-RUN-WITH-OPEN-FLAGS** — one run, and a QA report whose distribution flags are still
  untouched stubs. The talk's headline pattern. Loudest advisory.
- **SINGLE-RUN** — one run, no open flags. Possibly fine; surfaced quietly.
- **NO-QA** — no QA artifacts at all. *Informational only*, with a pointer that **axis-1 of the
  audit playbook owns "missing QA step."** B3 does not conflate "didn't QA" with "didn't iterate."

**Output:** a markdown table (workflow · run count · chain depth · open/dispositioned flag counts ·
verdict), printed and writable to the project audit area; `--json` for tooling. **Always exits 0**
— advisory.

## Doc & convention changes (extend, don't rediscover)

1. [`../conventions/pipeline-qa-checkpoints.md`](../conventions/pipeline-qa-checkpoints.md) — add a
   **Reference implementation** note: `science_qa` executes this exact `qa:` schema; the
   disposition file is the formal home of the convention's "analyst decides at model time" step.
   The convention stays the contract; the runner is one implementation of it.
2. [`../process/pipeline-audit-and-refactor.md`](../process/pipeline-audit-and-refactor.md) — add
   **process-iteration** as a third entry in "Related QA disciplines" (beside analysis/result-QA
   and workflow/DAG-validation), scored during the sweep with `science qa-audit` as its tool, plus
   a findings/synthesis note.
3. [`../../aspects/computational-analysis/computational-analysis.md`](../../aspects/computational-analysis/computational-analysis.md)
   — a new **Process iteration** row in the `review-pipeline` rubric (PASS iterated / WARN
   single-run-with-open-flags / FAIL ran-once-no-response), and a `plan-pipeline` note to emit
   dispositions.

## Error handling (fail-early, explicit — no silent fallback)

- Missing/unreadable config, or a config key naming a column absent from the table → **hard error,
  exit 2**, message naming the column. No default config is ever assumed.
- Unknown pack name in `packs:` → hard error (no silent skip).
- `--no-strict` suppresses only the exit code; structural flags still run and still appear in the
  report.
- `qa-audit` reads many workflows: a single bad/missing run manifest becomes a per-row **ERROR
  verdict** (named explicitly), not a crash — the audit completes and exits 0. An unknown
  `disposition` value in a dispositions file is a hard error there (don't silently treat as open).
- Disposition merge never overwrites filled entries; reconciliation is reported.

## Testing (TDD, red → green)

- **Runner:** per-check unit tests (structural fires/clears, distribution surfaces, `allowed_from`
  subset, exclusive-flags), exit-code contract, **determinism** (same config + table →
  byte-identical `qa_report.json`), disposition stub emission + merge-preserve. Fixtures = tiny
  parquet/csv tables with seeded defects.
- **scRNA pack:** synthetic per-cell QC table with known mito / gene-count / doublet violations →
  expected flag set.
- **qa-audit:** temp graph with single-run, superseded-chain, and open-flag fixtures → assert each
  verdict (ITERATED / SINGLE-RUN / SINGLE-RUN-WITH-OPEN-FLAGS / NO-QA / ERROR).
- **Doc changes:** verified via existing markdown link-check / `science validate`.

## Out of scope (explicit)

- **B2 QA-breadth scoring** — separate workstream; this spec defines the check surface it will
  later score (`B2 *Deps:* B1`).
- **Additional packs** (bulk RNA, genomics CN/SV, amplicon) — mechanical follow-ons once scRNA
  proves the interface.
- **Non-table substrates** (graph / corpus / JSONL from the playbook's modality table) — runner is
  table-first for the first cut.
- **Any `science validate` gating** — advisory only.
- **Git-history iteration inference** — rejected in favor of the run-chain + disposition signal.
- **Themes A & D** — untouched; this spec only *preserves* report determinism as an enabling
  property for D's future re-run-and-diff.

## Provenance

- Source talk: `talk:Johri2026` (`meta/doc/background/talks/Johri2026.md`).
- Umbrella: [`2026-06-10-data-driven-discovery-improvements.md`](2026-06-10-data-driven-discovery-improvements.md),
  Theme B (B1 + B3; B2 deferred).
- Reused machinery: the `computational-analysis` run lifecycle (`workflow-run` / `sci:supersedes`).
