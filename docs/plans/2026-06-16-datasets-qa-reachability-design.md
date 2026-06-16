# `science datasets qa` Reachability — Design (Spec 4)

**Date:** 2026-06-16
**Status:** Approved (design); plan pending
**Depends on:** Spec 1 (typed Data Resource profile), Spec 2 (schema→checks compiler + generic `tabular` program), Spec 3 (`science datasets infer-schema` scaffold), Schema Adoption Campaign (14 durable-reference packages now carry authored structural invariants)
**Unblocks:** wiring QA into a build gate (future, out of scope here)

## 1. Goal

Make schema-driven QA **reachable from the main `science` CLI**. The engine that
compiles an authored Frictionless schema into checks and runs them against real data
already exists — Spec 2 shipped `run_qa_datapackage()` in the `science_qa` distribution,
reachable only via its standalone `science_qa run --datapackage P --resource R` CLI. The
Schema Adoption Campaign then produced the corpus of real authored schemas that gives
that engine something to compile. Spec 4 is the last link: a `science datasets qa`
command that runs QA at **package** granularity through the normal `science` entry point.

This is fundamentally a **wiring + ergonomics** spec, plus one modest engine addition
(package-level aggregation). It is *not* a new check framework, a new schema model, or a
verdict-persistence system.

## 2. What already exists (and is reused unchanged)

| Surface | Location | Role in Spec 4 |
|---|---|---|
| `run_qa_datapackage(dp, resource, report_dir, runknobs_path=None)` | `science/qa/src/science_qa/runner.py` | per-resource compile→run→write; its **core** is factored and reused |
| `_run_with_config(config, table_path, report_dir)` | `runner.py` | source of the non-writing core (§5.1) |
| `schema_to_config` / `merge_configs` / `CompileError` | `science/qa/src/science_qa/compile.py` | descriptor → `QAConfig`; unchanged |
| generic `tabular` program | `science/qa/src/science_qa/program.py` | default program; unchanged |
| `RunResult`, `Coverage`, `Flag`, `SEVERITY_STRUCTURAL/_DISTRIBUTION` | `runner.py` / `flags.py` / `coverage.py` | aggregated by the package runner |
| `science datasets validate <path>` → `validate_path` | `src/science_tool/datasets/validate.py` | sibling command; Spec 4's path-resolution mirrors it |
| `datasets` CLI group | `src/science_tool/cli.py:3049` | where `qa` is registered |

**Dependency direction (verified).** `pyproject.toml` declares `science-qa` as an
editable path dependency of the main package, and `import science_qa` resolves in the
framework venv. So `science_tool` may call the QA engine **in-process**; the one-way
boundary that matters — `science_qa` must never import `science_tool` — is preserved
because nothing in `science_qa` changes to depend on the consumer.

## 3. Decisions (locked during brainstorming)

1. **Granularity = package-level.** `science datasets qa <pkg>` runs QA across all tabular
   resources and aggregates a package verdict; `--resource R` narrows to one. The
   per-resource engine is the degenerate case.
2. **Output = transient report only.** No verdict materialization, no descriptor
   mutation. The pre-existing ad-hoc `*.qa_verdict.json` sidecars are left untouched and
   are explicitly out of scope.
3. **Exit semantics = build-fatal.** `0` ok · `1` structural flag fired · `2` bad input;
   `--no-strict` forces `0`. Matches the standalone `science_qa run` convention so QA is
   gate-wireable later without changing its contract.
4. **Default report destination = stdout only.** Files (`qa_report.{json,md}`) are written
   only when `--report-dir DIR` is given. Zero git-noise risk.
5. **Aggregation lives in `science_qa`** (a new `run_qa_package`), keeping QA-domain logic
   in the QA distribution and the `science_tool` command thin.

## 4. Command surface

```
science datasets qa <path> [--resource NAME] [--report-dir DIR]
                            [--format text|json] [--no-strict] [--config qa.yaml]
```

- `<path>` — a package **directory** or a **descriptor file** (`datapackage.json` /
  `datapackage.yaml`). Resolved exactly as `science datasets validate` resolves its
  target (reuse the directory→descriptor resolution; do not reinvent it).
- `--resource NAME` — restrict to one resource (the per-resource case). Omitted = all
  tabular resources.
- `--report-dir DIR` — persist `qa_report.{json,md}`; default writes no files.
- `--format text|json` — `text` (default) prints the human summary table; `json` prints
  the structured `PackageRunResult` to stdout (for tooling).
- `--no-strict` — suppress the build-fatal exit `1` (local inspection only).
- `--config qa.yaml` — optional operational run-knobs, forwarded as `runknobs_path` to
  the engine (same overlay semantics as Spec 2).

### 4.1 Text output (default)

```
$ science datasets qa data/external/gdsc_v2/2022-07-24
gdsc-v2-dose-response    ok       12 checks, 0 structural, 0 distribution
gdsc-v2-expression-long  ok        4 checks, 0 structural, 0 distribution
gdsc-v2-cell-lines       FAIL      9 checks, 1 structural, 0 distribution
  numeric-column/bounds  cosmic_id  1 value(s) violate minimum 0
--
package: FAIL  (1/3 resources structural; 0 blocked, 0 skipped)
```

Non-tabular resources (`.json` sidecars, `*.qa_verdict.json`) are silent unless
`--format json`. Blocked/skipped resources appear with their status and reason.

## 5. Engine addition: `run_qa_package`

### 5.1 Factor a non-writing core (behavior-preserving)

Today `_run_with_config(config, table_path, report_dir)` does compile-independent work
(resolve program, read table, run checks → flags + coverage) **and then** writes reports
and reconciles dispositions. Split it:

```python
def _evaluate(config: QAConfig, table_path: Path) -> RunResult:
    """Compile-independent core: resolve program, read table, run checks.
    Returns a RunResult. Writes nothing, reconciles nothing."""
    ...  # exactly the current _run_with_config body up to (not including) write_reports

def _run_with_config(config: QAConfig, table_path: Path, report_dir: Path) -> RunResult:
    result = _evaluate(config, table_path)
    write_reports(result.flags, report_dir=report_dir, rows_checked=..., coverage=result.coverage)
    reconcile_dispositions(report_dir, [f.flag_id for f in result.flags if f.severity == SEVERITY_DISTRIBUTION])
    return result
```

`run_qa` and `run_qa_datapackage` are unchanged in behavior — they still go through
`_run_with_config`, so their existing tests stay green. This is the only edit to existing
runner logic, and it is byte-equivalent for the single-resource paths.

### 5.2 New `run_qa_package`

```python
@dataclass(frozen=True)
class ResourceOutcome:
    name: str
    status: str            # "ok" | "fail" | "blocked" | "skipped"
    reason: str            # "" for ok/fail; e.g. "data file absent", "no schema", "non-tabular"
    result: RunResult | None   # None for blocked/skipped

@dataclass(frozen=True)
class PackageRunResult:
    package: str
    outcomes: list[ResourceOutcome]
    package_structural_failed: bool   # any outcome.status == "fail"

def run_qa_package(datapackage_path: Path, report_dir: Path | None = None,
                   resources: list[str] | None = None,
                   runknobs_path: Path | None = None) -> PackageRunResult:
    ...
```

Algorithm:
1. Load the descriptor (JSON or YAML — reuse `infer_schema.load_descriptor` shape).
2. Resource selection: if `resources` given, that set (error → `CompileError` if a named
   resource is absent); else every resource.
3. Per resource, classify before running:
   - **non-tabular** (path suffix ∉ `.parquet/.csv/.tsv`) → `skipped`, reason `"non-tabular"`.
   - **no schema** (`schema.fields` absent/empty) → `skipped`, reason `"no schema"`.
     QA needs a contract; un-QA-able is surfaced, not fatal, not a crash.
   - **data file absent** → `blocked`, reason `"data file absent"`. These packages
     legitimately have absent resources (walker_2024 has 4; dgidb has 1) — never fatal.
   - otherwise → run: `cfg = schema_to_config(resource, pkg_dir, package)`; overlay
     `merge_configs` if `runknobs_path`; default `program="tabular"`; `result = _evaluate(cfg, table_path)`.
     `status = "fail"` if `result.structural_failed` else `"ok"`.
4. `package_structural_failed = any(o.status == "fail")`.
5. If `report_dir` is given, write **one** package report (`qa_report.json` with a
   per-resource section list + a flat `flags[]`; `qa_report.md` the human rollup) using a
   small package-level writer that composes the existing per-resource `write_reports`
   payload shape. If `report_dir` is `None`, write nothing.

**Disposition reconciliation.** The build-fatal decision depends only on *structural*
flags, which carry no disposition state, so a transient (no `--report-dir`) run needs no
disposition ledger. Distribution-flag disposition reconciliation runs only when
`report_dir` is set, against that one package report dir.

### 5.3 Standalone-CLI reach (optional, low-cost)

Because aggregation now lives in `science_qa`, its own CLI can grow a package mode
(`science_qa run --datapackage P` with no `--resource` → `run_qa_package`). This is a
natural by-product, not a requirement; include it only if it falls out cleanly.

## 6. `science_tool` command (thin)

- **New module** `src/science_tool/datasets/qa.py`: `run_package_qa(path, resource,
  report_dir, runknobs, no_strict) -> tuple[PackageRunResult, int]` — resolves the path
  to a descriptor (shared with `validate`), calls `science_qa.run_qa_package`, computes
  the exit code, and returns both for the CLI to render.
- **CLI** `src/science_tool/cli.py`: register `qa` in the `datasets` group (next to
  `validate`/`infer-schema`), parse options, render `--format text|json`, `raise
  SystemExit(code)`.
- Exit code: `0` ok · `1` `package_structural_failed and not no_strict` · `2` on
  `CompileError` / bad path / unknown resource (surfaced as the message, fail-early).

The command imports `science_qa` at call time and contains **no QA logic** — only
path resolution, rendering, and exit-code policy.

## 7. Error handling (fail early, explicit)

- Bad `<path>` (no descriptor) → exit `2`, message naming the path. Reuse `validate`'s
  resolution so the two commands agree on what "a package" is.
- `--resource` naming an absent resource → `CompileError` → exit `2`.
- A resource that is tabular + has a schema but whose data is **corrupt/unreadable** →
  the engine raises (`RunnerError`/`ValueError`); surface as exit `2` (it is a real
  failure to evaluate, distinct from a clean structural finding).
- Composite foreign keys are already rejected at compile time by Spec 2 — Spec 4 adds no
  new FK handling; single-column FK reachability checks run as the compiler already
  emits them.

## 8. Scope boundaries (explicit non-goals)

- **No verdict materialization / descriptor mutation.** No `*.qa_verdict.json` is written
  or declared; the existing sidecars are neither read nor reconciled.
- **Not auto-wired into `science validate` or the Phase-0 gate.** `science datasets qa`
  is standalone opt-in. Wiring QA into a build gate is a separate future spec (the
  build-fatal exit code is the seam that makes it possible without re-contracting).
- **Tabular only** (`.parquet/.csv/.tsv`), consistent with the campaign and the engine.
- **No new checks, no schema-model change, no `qa:` authoring.** Spec 4 runs what the
  authored schemas already declare.
- **`science_qa` stays non-importing of `science_tool`.**

## 9. Testing strategy

`science_qa` (run from `science/qa`, `PYTHONPATH=src`):
- `_evaluate`/`_run_with_config` split is behavior-preserving — existing `test_runner.py`
  single-resource tests stay green unchanged.
- New `run_qa_package` tests: clean multi-resource package → `ok`; one resource with a
  bounds/PK violation → that resource `fail`, package `fail`; absent data file → `blocked`
  (non-fatal); non-tabular resource → `skipped`; tabular-but-schemaless → `skipped`;
  `--report-dir` writes exactly one `qa_report.{json,md}` (no per-resource clobber);
  no `report_dir` writes nothing; `resources=[...]` selection + unknown-name → `CompileError`.

`science_tool` (framework venv):
- `test_datasets_qa.py`: path resolution (dir vs descriptor), `--format json` shape,
  exit-code matrix (`0`/`1`/`2`, `--no-strict`→`0`), unknown resource → `2`.
- `test_datasets_qa_cli.py`: end-to-end CLI invocation on a tmp package fixture.
- Boundary guard test: `grep` that `science/qa/src` contains no `science_tool` import
  (extend the existing one-way-dependency check).

## 10. Definition of done

`science datasets qa <pkg>` runs schema-driven QA across a package's tabular resources,
prints a package rollup, exits build-fatal on structural failure (suppressible with
`--no-strict`), and optionally persists `qa_report.{json,md}` — with the `science_qa`
engine reused in-process, the non-importing boundary intact, no descriptor mutation, and
green `science_qa` + `science_tool` suites. Running it against the 14 campaign packages
produces real QA verdicts from their authored schemas.
