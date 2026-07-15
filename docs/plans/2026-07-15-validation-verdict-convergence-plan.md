# ValidationVerdict Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the validator/audit function family a canonical `ValidationVerdict[RowT]` return type so a validator that could not run cannot masquerade as a clean pass, closing item 2 of the instrument-result convergence follow-on.

**Architecture:** A sibling to `InstrumentResult` in `instruments.py` carrying a `passed`/`failed`/`unwired` verdict over a report card. Four public functions migrate to it; every consumer fails closed on `unwired`. The AST boundary guard is widened to cover the family and two newly-in-scope modules.

**Tech Stack:** Python 3.11+, Pydantic v2, click, rdflib, pytest. Package root: `science/` (run everything from there).

**Design:** [`2026-07-15-validation-verdict-convergence-design.md`](2026-07-15-validation-verdict-convergence-design.md). Read §2 (type), §4 (unwired), §5 (consumer contract table), §6 (guard).

## Global Constraints

- **Run from `science/`.** Tests: `cd science && uv run --frozen pytest`. Lint: `uv run ruff check`. Types: `uv run pyright` (walks up to the repo-root `pyrightconfig.json`).
- **Type name is `ValidationVerdict`** — never `Verdict` (collides with the `science_tool.verdict` epistemic package).
- **`unwired` handling is a design invariant:** no consumer may derive a pass/fail bool via `status == "failed"` without first handling `unwired` and failing closed. Never use `assert` for a runtime boundary (`python -O` strips it).
- **`ValidationVerdict` is the PUBLIC boundary type only.** Private plumbing (`_audit_phase`, `_compile`, `CompilationResult.has_failures`) keeps its internal `bool`.
- Project rules: composition over inheritance; explicit over defensive; fail early; **no legacy/compatibility layers**; no `Unified` prefix; **no AI-attribution trailers** on commits.
- Each task leaves the tree green (`pytest`, `ruff`, `pyright` all pass) — a producer's return-type change and all its consumers land in the same commit.

## File Structure

- `science/src/science_tool/instruments.py` — add `ValidationVerdict` (new type; sits beside `InstrumentResult`).
- `science/src/science_tool/output.py` — add `unwrap_verdict` (parallel of `unwrap_instrument`).
- `science/src/science_tool/graph/store/validation.py` — migrate `validate_graph`, `validate_graph_dataset`; privatize `validate_empirical_run_resolution`.
- `science/src/science_tool/graph/migrate.py` — migrate `audit_project_sources`.
- `science/src/science_tool/graph/materialize.py` — migrate `materialization_audit`; `_audit_phase`/`_compile` fail-closed.
- `science/src/science_tool/graph/cli.py` — `graph validate` + `graph audit` via `unwrap_verdict`.
- `science/src/science_tool/validate/checks/graph.py` — validate + audit sides handle `unwired`.
- `science/src/science_tool/graph/freshness.py`, `entities.py`, `graph/health_checks/unresolved_refs.py` — consumer contract.
- `science/tests/test_instrument_boundary.py` — namespace, detector, prose, `_NOT_INSTRUMENTS`.
- `science/tests/test_validation_verdict.py` — new type + `unwrap_verdict` unit tests.

## Task Dependency

Task 1 (type) → Task 2 (validator pair + its consumers) and Task 3 (audit family + its consumers), which are independent of each other → Task 4 (guard, after both migrations remove all offenders).

---

### Task 1: `ValidationVerdict` type + `unwrap_verdict` helper

**Files:**
- Modify: `science/src/science_tool/instruments.py`
- Modify: `science/src/science_tool/output.py`
- Test: `science/tests/test_validation_verdict.py` (create)

**Interfaces:**
- Produces: `ValidationVerdict[RowT]` with `status: Literal["passed","failed","unwired"]`, `rows`, `reason`, `code`; classmethods `passed(rows,*,code=None,reason=None)`, `failed(rows,*,code=None,reason=None)`, `unwired(*,code,reason=None)`, `from_has_failures(rows,has_failures,*,code=None,reason=None)`.
- Produces: `unwrap_verdict(verdict, *, what) -> tuple[list[RowT], bool]` — raises `click.ClickException` on `unwired`, echoes `reason` to stderr on a run, returns `(rows, status == "failed")`.

- [ ] **Step 1: Write the failing test** (`science/tests/test_validation_verdict.py`)

```python
from __future__ import annotations

import click
import pytest

from science_tool.instruments import ValidationVerdict
from science_tool.output import unwrap_verdict


def test_unwired_forbids_rows() -> None:
    with pytest.raises(ValueError, match="unwired.*forbids rows"):
        ValidationVerdict(status="unwired", rows=[{"a": "b"}], code="x")


def test_unwired_requires_code() -> None:
    with pytest.raises(ValueError, match="unwired.*requires a machine-readable code"):
        ValidationVerdict(status="unwired", rows=[])


def test_passed_allows_empty_rows_and_is_not_unwired() -> None:
    v = ValidationVerdict.passed([])
    assert v.status == "passed"
    assert v.rows == []
    assert v.code is None


def test_from_has_failures_maps_bool_to_status() -> None:
    assert ValidationVerdict.from_has_failures([{"s": "pass"}], has_failures=False).status == "passed"
    assert ValidationVerdict.from_has_failures([{"s": "fail"}], has_failures=True).status == "failed"


def test_failed_carries_rows() -> None:
    v = ValidationVerdict.failed([{"check": "x", "status": "fail"}])
    assert v.status == "failed"
    assert v.rows == [{"check": "x", "status": "fail"}]


def test_unwrap_verdict_raises_on_unwired() -> None:
    with pytest.raises(click.ClickException, match=r"graph validate did not run \(unparseable\)"):
        unwrap_verdict(ValidationVerdict.unwired(code="unparseable", reason="bad"), what="graph validate")


def test_unwrap_verdict_returns_rows_and_has_failures() -> None:
    rows, has_failures = unwrap_verdict(ValidationVerdict.failed([{"s": "fail"}]), what="x")
    assert rows == [{"s": "fail"}]
    assert has_failures is True
    rows, has_failures = unwrap_verdict(ValidationVerdict.passed([{"s": "pass"}]), what="x")
    assert has_failures is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_validation_verdict.py -q`
Expected: FAIL with `ImportError: cannot import name 'ValidationVerdict'`.

- [ ] **Step 3: Add `ValidationVerdict` to `instruments.py`**

Insert after the `InstrumentResult` class. Reuse the module's existing `RowT`, `Generic`, `Literal`, `BaseModel`, `Field`, `model_validator` imports.

```python
ValidationVerdictStatus = Literal["passed", "failed", "unwired"]


class ValidationVerdict(BaseModel, Generic[RowT]):
    """Canonical validator/audit result — the verdict axis of the instrument convergence.

    Sibling to ``InstrumentResult``. Where an *instrument* reports found/empty/unwired, a
    *validator* reports a pass/fail VERDICT over a report card present whenever it ran.
    There is no ``empty``: a validator that ran is ``passed`` or ``failed``; one that could
    not is ``unwired``. ``passed`` with an empty card is told from ``unwired`` by STATUS,
    never by row count.

    Named ``ValidationVerdict``, not ``Verdict``: ``science_tool.verdict`` is the epistemic
    verdict-token package — a different meaning of the word.

    The verdict is set EXPLICITLY by the caller. The type is ``Generic[RowT]`` and cannot
    inspect ``row["status"]``, exactly as ``InstrumentResult`` cannot inspect its rows.
    """

    status: ValidationVerdictStatus
    rows: list[RowT] = Field(default_factory=list)
    reason: str | None = None
    code: str | None = None

    @model_validator(mode="after")
    def _enforce_status_invariant(self) -> "ValidationVerdict[RowT]":
        if self.status == "unwired":
            if self.rows:
                raise ValueError("status='unwired' forbids rows; they are meaningless")
            if not self.code:
                raise ValueError("status='unwired' requires a machine-readable code")
        return self

    @classmethod
    def passed(
        cls, rows: list[RowT], *, code: str | None = None, reason: str | None = None
    ) -> "ValidationVerdict[RowT]":
        return cls(status="passed", rows=rows, code=code, reason=reason)

    @classmethod
    def failed(
        cls, rows: list[RowT], *, code: str | None = None, reason: str | None = None
    ) -> "ValidationVerdict[RowT]":
        return cls(status="failed", rows=rows, code=code, reason=reason)

    @classmethod
    def unwired(cls, *, code: str, reason: str | None = None) -> "ValidationVerdict[RowT]":
        return cls(status="unwired", rows=[], code=code, reason=reason)

    @classmethod
    def from_has_failures(
        cls,
        rows: list[RowT],
        has_failures: bool,
        *,
        code: str | None = None,
        reason: str | None = None,
    ) -> "ValidationVerdict[RowT]":
        return cls(status="failed" if has_failures else "passed", rows=rows, code=code, reason=reason)
```

- [ ] **Step 4: Add `unwrap_verdict` to `output.py`**

Add `ValidationVerdict` to the existing `from science_tool.instruments import ...` line, then add beside `unwrap_instrument`:

```python
def unwrap_verdict(verdict: ValidationVerdict[RowT], *, what: str) -> tuple[list[RowT], bool]:
    """Turn a ValidationVerdict into ``(rows, has_failures)``, REFUSING to render unwired.

    The parallel of ``unwrap_instrument`` for the verdict axis: an unwired validator did
    not run, so emitting its empty rows as a clean report would be the exact silent-run lie
    the convergence exists to stop -- so it raises before anything is rendered.
    """
    if verdict.status == "unwired":
        raise click.ClickException(f"{what} did not run ({verdict.code}): {verdict.reason}")
    if verdict.reason:
        click.echo(f"notice ({verdict.code}): {verdict.reason}", err=True)
    return verdict.rows, verdict.status == "failed"
```

- [ ] **Step 5: Run tests + lint + types**

Run: `cd science && uv run --frozen pytest tests/test_validation_verdict.py -q && uv run ruff check src/science_tool/instruments.py src/science_tool/output.py && uv run pyright src/science_tool/instruments.py src/science_tool/output.py`
Expected: PASS; clean.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/instruments.py science/src/science_tool/output.py science/tests/test_validation_verdict.py
git commit -m "feat(instruments): add ValidationVerdict type and unwrap_verdict"
```

---

### Task 2: Migrate the validator pair + its consumers

**Files:**
- Modify: `science/src/science_tool/graph/store/validation.py` (`validate_graph`, `validate_graph_dataset`; privatize `validate_empirical_run_resolution`)
- Modify: `science/src/science_tool/graph/cli.py` (`graph validate`)
- Modify: `science/src/science_tool/validate/checks/graph.py` (validate side)
- Test: `science/tests/test_graph_validate_run_resolution.py`, `science/tests/test_graph_validate_patch_convenience.py`, `science/tests/validate/test_checks_graph.py`, `science/tests/test_graph_cli.py`

**Interfaces:**
- Consumes: `ValidationVerdict`, `unwrap_verdict` (Task 1).
- Produces: `validate_graph(graph_path) -> ValidationVerdict[dict[str, str]]` (`unwired` code `graph_missing`/`unparseable`); `validate_graph_dataset(dataset) -> ValidationVerdict[dict[str, str]]` (always `passed`/`failed`).

- [ ] **Step 1: Write failing migration tests**

Add to `science/tests/test_graph_validate_run_resolution.py`:

```python
def test_validate_graph_missing_is_unwired(tmp_path) -> None:
    from science_tool.graph.store.validation import validate_graph

    verdict = validate_graph(tmp_path / "nope.trig")
    assert verdict.status == "unwired"
    assert verdict.code == "graph_missing"
    assert verdict.rows == []


def test_validate_graph_unparseable_is_unwired(tmp_path) -> None:
    from science_tool.graph.store.validation import validate_graph

    p = tmp_path / "graph.trig"
    p.write_text("this is not trig <<<", encoding="utf-8")
    verdict = validate_graph(p)
    assert verdict.status == "unwired"
    assert verdict.code == "unparseable"


def test_validate_graph_dataset_returns_verdict() -> None:
    from science_tool.graph.store.validation import validate_graph_dataset

    verdict = validate_graph_dataset(_dataset_from_trig("@prefix ex: <http://e/> . ex:a ex:b ex:c ."))
    assert verdict.status in {"passed", "failed"}
    assert verdict.rows  # report card is always present
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_graph_validate_run_resolution.py -k "unwired or returns_verdict" -q`
Expected: FAIL (`validate_graph` returns a tuple; `.status` AttributeError).

- [ ] **Step 3: Migrate `validation.py`**

Add `from ...instruments import InstrumentResult, ValidationVerdict` (extend the existing import). Rewrite `validate_graph`:

```python
def validate_graph(graph_path: Path) -> ValidationVerdict[dict[str, str]]:
    if not graph_path.exists():
        return ValidationVerdict.unwired(
            code="graph_missing",
            reason=f"Graph file not found: {graph_path}",
        )
    try:
        dataset = _load_dataset(graph_path)
    except Exception as exc:  # noqa: BLE001
        return ValidationVerdict.unwired(
            code="unparseable",
            reason=f"graph.trig did not parse: {exc}",
        )
    return validate_graph_dataset(dataset)
```

Change `validate_graph_dataset`'s signature to `-> ValidationVerdict[dict[str, str]]` and its final two lines:

```python
    has_failures = any(row["status"] == "fail" for row in rows)
    return ValidationVerdict.from_has_failures(rows, has_failures)
```

Privatize the helper: rename `def validate_empirical_run_resolution(` → `def _validate_empirical_run_resolution(` and update its one call site (line ~168) `run_messages, run_fatal = _validate_empirical_run_resolution(dataset)`. Delete the now-dead `_parse_failure_rows` helper if `validate_graph` no longer references it (it does not after this change) — confirm with `grep -n _parse_failure_rows src/science_tool/graph/store/validation.py`; remove if unreferenced.

- [ ] **Step 4: Update the two producers' consumers**

`graph/cli.py` — add `unwrap_verdict` to the `from science_tool.output import ...` line; rewrite `graph_validate`:

```python
    rows, has_failures = unwrap_verdict(validate_graph(graph_path), what="graph validate")
    emit_query_rows(
        output_format=output_format,
        title="Graph Validation",
        columns=[("check", "Check"), ("status", "Status"), ("details", "Details")],
        rows=rows,
    )
    if has_failures:
        raise click.exceptions.Exit(1)
```

`validate/checks/graph.py` — replace the block at lines ~199-215 (the `try/except` + row loop + `parseable_failed` early return):

```python
    try:
        dataset = ctx.graph_dataset(graph_path)
    except Exception:  # noqa: BLE001
        verdict = validate_graph(graph_path)
    else:
        verdict = validate_graph_dataset(dataset)

    if verdict.status == "unwired":
        yield _result(Severity.ERROR, f"graph validate: could not run ({verdict.code}) — {verdict.reason}")
        return

    for row in verdict.rows:
        status = _status(row, context="graph validate", accepted={"fail", "warn", "pass"})
        check = row["check"]
        severity = Severity.ERROR if status == "fail" else Severity.WARN if status == "warn" else Severity.INFO
        yield _result(severity, f"graph validate: {check} — {row['details']}")
```

The `parseable_failed` variable and its `if parseable_failed: return` are deleted — `unwired` now carries that early exit, and the subsequent `diff_graph_inputs_dataset(dataset, ...)` runs only in the `else` branch where `dataset` is bound.

- [ ] **Step 5: Update existing tuple-unpacking tests for these two functions**

Canonical transform, applied at every `validate_graph`/`validate_graph_dataset` call site in `tests/test_graph_validate_run_resolution.py` and `tests/test_graph_validate_patch_convenience.py`:

```python
# before:
rows, has_failures = validate_graph_dataset(ds)
# after:
verdict = validate_graph_dataset(ds)
rows, has_failures = verdict.rows, verdict.status == "failed"
```
(For sites that used `rows, _ = ...`, use `rows = validate_graph_dataset(ds).rows`.)

In `tests/validate/test_checks_graph.py`, the monkeypatch return values for `validate_graph`/`validate_graph_dataset` must return `ValidationVerdict`, not tuples:
```python
# before: monkeypatch.setattr(graph, "validate_graph_dataset", lambda _dataset: ([], False))
# after:
monkeypatch.setattr(graph, "validate_graph_dataset", lambda _dataset: ValidationVerdict.passed([]))
# a fail stub: lambda _dataset: ValidationVerdict.failed([{"check": "x", "status": "fail", "details": "d"}])
```
Add `from science_tool.instruments import ValidationVerdict` to that test module.

- [ ] **Step 6: Write the validate-check + CLI fail-closed regressions**

Add to `tests/validate/test_checks_graph.py`:

```python
def test_validate_check_unwired_emits_error_and_skips_diff(tmp_path, monkeypatch) -> None:
    from science_tool.instruments import ValidationVerdict
    from science_tool.validate.checks import graph

    called = {"diff": False}
    monkeypatch.setattr(graph, "validate_graph", lambda _p: ValidationVerdict.unwired(code="unparseable", reason="bad"))
    monkeypatch.setattr(graph, "materialization_audit", lambda _root: ValidationVerdict.passed([]))

    def _boom(*a, **k):
        raise AssertionError("graph_dataset should fail so validate_graph is used")

    monkeypatch.setattr(graph, "diff_graph_inputs_dataset", lambda *a, **k: called.__setitem__("diff", True))
    # force the except branch: make ctx.graph_dataset raise (a broken graph.trig on disk)
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    gdir = tmp_path / "knowledge"
    gdir.mkdir()
    (gdir / "graph.trig").write_text("not trig <<<", encoding="utf-8")

    from science_tool.validate.runner import run

    result = run(tmp_path, strict=False, verbose=False, enable_python_sidecar=False)
    msgs = [r.message for r in result.results if "graph validate" in r.message]
    assert any("could not run (unparseable)" in m for m in msgs)
    assert called["diff"] is False
```

Add to `tests/test_graph_cli.py` (use its existing `CliRunner` fixture/pattern):

```python
def test_graph_validate_unparseable_table_and_json(tmp_path) -> None:
    from click.testing import CliRunner
    from science_tool.graph.cli import graph_group

    p = tmp_path / "graph.trig"
    p.write_text("not trig <<<", encoding="utf-8")
    for fmt in ("table", "json"):
        res = CliRunner().invoke(graph_group, ["validate", "--path", str(p), "--format", fmt])
        assert res.exit_code != 0
        assert "did not run (unparseable)" in res.output
        assert '"rows": []' not in res.output  # never a clean empty payload


def test_graph_validate_missing_is_graph_missing(tmp_path) -> None:
    from click.testing import CliRunner
    from science_tool.graph.cli import graph_group

    res = CliRunner().invoke(graph_group, ["validate", "--path", str(tmp_path / "nope.trig")])
    assert res.exit_code != 0
    assert "did not run (graph_missing)" in res.output
```

- [ ] **Step 7: Run the affected suites + lint + types**

Run:
```bash
cd science && uv run --frozen pytest tests/test_graph_validate_run_resolution.py tests/test_graph_validate_patch_convenience.py tests/validate/test_checks_graph.py tests/test_graph_cli.py -q \
  && uv run ruff check src/science_tool/graph/store/validation.py src/science_tool/graph/cli.py src/science_tool/validate/checks/graph.py \
  && uv run pyright src/science_tool/graph/store/validation.py src/science_tool/graph/cli.py src/science_tool/validate/checks/graph.py
```
Expected: PASS; clean. If `pyright` flags callers elsewhere importing the old tuple shape, they belong to Task 3's family or are already covered — re-run the full `pyright` at Task 4.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/graph/store/validation.py science/src/science_tool/graph/cli.py science/src/science_tool/validate/checks/graph.py science/tests/test_graph_validate_run_resolution.py science/tests/test_graph_validate_patch_convenience.py science/tests/validate/test_checks_graph.py science/tests/test_graph_cli.py
git commit -m "feat(validate): validate_graph* return ValidationVerdict; unwired on missing/unparseable"
```

---

### Task 3: Migrate the audit family + its consumers

**Files:**
- Modify: `science/src/science_tool/graph/migrate.py` (`audit_project_sources`)
- Modify: `science/src/science_tool/graph/materialize.py` (`materialization_audit`, `_audit_phase`, `_compile`)
- Modify: `science/src/science_tool/graph/cli.py` (`graph audit`)
- Modify: `science/src/science_tool/validate/checks/graph.py` (audit side)
- Modify: `science/src/science_tool/graph/freshness.py`, `entities.py`, `graph/health_checks/unresolved_refs.py`
- Test: `test_graph_migrate.py`, `test_dataset_usage_materialize.py`, `graph/test_phase_split_contracts.py`, `test_chain_freshness_integration.py`, `test_meta_reference.py`, `test_substrate_two_scope_e2e.py`, `test_identity_audit_entrypoints.py`, `test_chain_audit_references.py`, `test_entities.py`, `test_freshness_derivation.py`, `test_health.py`

**Interfaces:**
- Consumes: `ValidationVerdict`, `unwrap_verdict` (Task 1).
- Produces: `audit_project_sources(sources) -> ValidationVerdict[AuditRow]`; `materialization_audit(project_root) -> ValidationVerdict[dict[str, str]]`. Both always `passed`/`failed` (total given loaded inputs); consumers still fail closed on `unwired`.

- [ ] **Step 1: Write failing migration + fail-closed tests**

Add to `tests/test_graph_migrate.py`:

```python
def test_audit_project_sources_returns_verdict() -> None:
    # reuse this module's existing `sources` builder for a clean project
    verdict = audit_project_sources(sources)  # sources fixture as used by neighboring tests
    assert verdict.status in {"passed", "failed"}
    assert isinstance(verdict.rows, list)
```

Add to `tests/graph/test_phase_split_contracts.py`:

```python
def test_compile_fails_closed_on_unwired_audit(tmp_path, monkeypatch) -> None:
    from science_tool.instruments import ValidationVerdict
    from science_tool.graph import materialize

    monkeypatch.setattr(materialize, "audit_project_sources", lambda _s: ValidationVerdict.unwired(code="x", reason="r"))
    with pytest.raises(ValueError, match="did not run"):
        materialize._compile(tmp_path, stop_after="audit")
```

Add to `tests/test_freshness_derivation.py`:

```python
def test_freshness_fails_closed_on_unwired_audit(tmp_path, monkeypatch) -> None:
    from science_tool.instruments import ValidationVerdict
    from science_tool.graph import migrate

    from science_tool.graph import freshness, migrate

    # freshness.py:407 (`propagate_freshness_in_memory`) imports audit_project_sources LAZILY
    # inside the function (freshness.py:420), so patch the SOURCE module, not `freshness`.
    monkeypatch.setattr(migrate, "audit_project_sources", lambda _s: ValidationVerdict.unwired(code="x", reason="r"))
    with pytest.raises(ValueError, match="did not run"):
        freshness.propagate_freshness_in_memory(tmp_path)
```

Add to `tests/test_entities.py`:

```python
def test_entity_prospective_audit_fails_closed_on_unwired(tmp_path, monkeypatch) -> None:
    from science_tool.instruments import ValidationVerdict
    from science_tool import entities
    from science_tool.entities import EntityCommandError

    monkeypatch.setattr(entities, "audit_project_sources", lambda _s: ValidationVerdict.unwired(code="x", reason="r"))
    with pytest.raises(EntityCommandError):
        entities._validate_prospective_write(  # entities.py:1731, keyword-only
            project_root=tmp_path,
            rel_path=Path("entities/topics/x.md"),
            text="---\nid: topic:x\nkind: topic\n---\n",
            target_entity_id="topic:x",
            include_commons=False,
        )
```

Add to `tests/test_health.py`:

```python
def test_collect_unresolved_refs_bridges_unwired_audit(monkeypatch) -> None:
    from science_tool.instruments import ValidationVerdict
    from science_tool.graph.health_checks import unresolved_refs

    monkeypatch.setattr(unresolved_refs, "audit_project_sources", lambda _s: ValidationVerdict.unwired(code="x", reason="r"))
    result = unresolved_refs.collect_unresolved_refs(project_root=..., sources=<non-empty sources>)
    assert result.status == "unwired"
    assert result.code == "x"
```

(Replace `...`/placeholders with the neighboring tests' existing builders — `test_entities.py` already has `fake_audit_project_sources` monkeypatch scaffolding, and `test_health.py` builds `ProjectSources`.)

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_graph_migrate.py::test_audit_project_sources_returns_verdict tests/graph/test_phase_split_contracts.py::test_compile_fails_closed_on_unwired_audit -q`
Expected: FAIL (tuple has no `.status`; `_compile` unpacks a tuple).

- [ ] **Step 3: Migrate `audit_project_sources` (`migrate.py`)**

Add `from science_tool.instruments import ValidationVerdict` (extend existing imports). Change the signature to `-> ValidationVerdict[AuditRow]` and the final two lines:

```python
    rows.sort(key=lambda row: (row["source"], row["target"]))
    has_failures = any(row["status"] == "fail" for row in rows)
    return ValidationVerdict.from_has_failures(rows, has_failures)
```

- [ ] **Step 4: Migrate `materialize.py` — `_audit_phase`, `_compile`, `materialization_audit`**

`_audit_phase` returns the verdict now (private plumbing):
```python
def _audit_phase(sources: ProjectSources) -> ValidationVerdict[AuditRow]:
    """Audit phase: the single `audit_project_sources` call site."""
    return audit_project_sources(sources)
```

`_compile` fails closed on `unwired`, then derives the internal bool (add `from science_tool.instruments import ValidationVerdict` import):
```python
    sources = load_project_sources(project_root, strict_identity=False)
    verdict = _audit_phase(sources)
    if verdict.status == "unwired":
        raise ValueError(f"Source audit did not run ({verdict.code}): {verdict.reason}")
    audit_rows = verdict.rows
    has_failures = verdict.status == "failed"
```
`CompilationResult.has_failures` stays `bool` — unchanged. The rest of `_compile` (the `if has_failures:` gate, `stop_after` branch) is untouched.

`materialization_audit` re-projects rows and wraps:
```python
def materialization_audit(project_root: Path) -> ValidationVerdict[dict[str, str]]:
    """Audit a project root for unresolved canonical references."""
    result = _compile(project_root, stop_after="audit")
    audit_rows = [
        {
            "check": row["check"],
            "status": row["status"],
            "source": row["source"],
            "field": row["field"],
            "target": row["target"],
            "details": row["details"],
        }
        for row in result.audit_rows
    ]
    return ValidationVerdict.from_has_failures(audit_rows, result.has_failures)
```

- [ ] **Step 5: Update the audit-family consumers**

`graph/cli.py` `graph audit` (line ~162):
```python
    rows, has_failures = unwrap_verdict(materialization_audit(project_root), what="graph audit")
```
(keep the existing emit + `if has_failures:` exit).

`validate/checks/graph.py` audit side (line ~177) — replace `audit_rows, _has_failures = materialization_audit(...)`:
```python
    audit_verdict = materialization_audit(ctx.project_root)
    if audit_verdict.status == "unwired":
        yield _result(Severity.ERROR, f"graph audit: could not run ({audit_verdict.code}) — {audit_verdict.reason}")
        return
    audit_rows = audit_verdict.rows
    if not audit_rows:
        yield _result(Severity.INFO, "graph audit: all canonical references resolved")
    else:
        ...  # existing per-row loop unchanged
```

`freshness.py` (line ~422):
```python
    verdict = audit_project_sources(sources)
    if verdict.status == "unwired":
        raise ValueError(f"Cannot compute freshness — source audit did not run ({verdict.code}): {verdict.reason}")
    audit_rows = verdict.rows
    if verdict.status == "failed":
        details = "; ".join(f"{row['source']} -> {row['target']}" for row in audit_rows if row["status"] == "fail")
        raise ValueError(f"Cannot compute freshness with unresolved references: {details}")
```

`entities.py` (lines ~1747, ~1751) — introduce a small local that fails closed:
```python
    def _audit_rows(project_sources) -> list[AuditRow]:
        verdict = audit_project_sources(project_sources)
        if verdict.status == "unwired":
            raise EntityCommandError(f"source audit did not run ({verdict.code}): {verdict.reason}")
        return verdict.rows

    baseline_rows = _audit_rows(load_project_sources(project_root, include_commons=include_commons))
    prospective = load_project_sources(project_root, markdown_overrides={rel_path_text: text}, include_commons=include_commons)
    prospective_rows = _audit_rows(prospective)
```
(Ensure `AuditRow` is imported in `entities.py`; if not, use `list` in the annotation.)

`graph/health_checks/unresolved_refs.py` (line ~64) — bridge to `InstrumentResult.unwired`:
```python
    verdict = audit_project_sources(sources)
    if verdict.status == "unwired":
        return InstrumentResult.unwired(code=verdict.code, reason=verdict.reason)
    rows = verdict.rows
```
(`code` is non-None on an `unwired` verdict by invariant, satisfying `InstrumentResult.unwired`'s required `code`.)

- [ ] **Step 6: Update existing tuple-unpacking tests (mechanical)**

Apply the canonical transform at every `audit_project_sources(...)` / `materialization_audit(...)` call site in: `test_graph_migrate.py`, `test_dataset_usage_materialize.py`, `graph/test_phase_split_contracts.py`, `test_chain_freshness_integration.py`, `test_meta_reference.py`, `test_substrate_two_scope_e2e.py`, `test_identity_audit_entrypoints.py`, `test_chain_audit_references.py`:
```python
# before:
rows, has_failures = materialization_audit(tmp_path)
# after:
verdict = materialization_audit(tmp_path)
rows, has_failures = verdict.rows, verdict.status == "failed"
# (rows, _ = ...  ->  rows = fn(...).rows)
```
In `test_entities.py`, the `fake_audit_project_sources` monkeypatch helpers must return a `ValidationVerdict`, not a tuple:
```python
# before: def fake_audit_project_sources(sources): return ([...], False)
# after:  return ValidationVerdict.from_has_failures([...], False)
```

- [ ] **Step 7: Run the affected suites + lint + types**

Run:
```bash
cd science && uv run --frozen pytest tests/test_graph_migrate.py tests/test_dataset_usage_materialize.py tests/graph/test_phase_split_contracts.py tests/test_chain_freshness_integration.py tests/test_meta_reference.py tests/test_substrate_two_scope_e2e.py tests/test_identity_audit_entrypoints.py tests/test_chain_audit_references.py tests/test_entities.py tests/test_freshness_derivation.py tests/test_health.py -q \
  && uv run ruff check src/science_tool/graph/migrate.py src/science_tool/graph/materialize.py src/science_tool/graph/cli.py src/science_tool/validate/checks/graph.py src/science_tool/graph/freshness.py src/science_tool/entities.py src/science_tool/graph/health_checks/unresolved_refs.py \
  && uv run pyright src/science_tool/graph/materialize.py src/science_tool/graph/migrate.py src/science_tool/graph/freshness.py src/science_tool/entities.py src/science_tool/graph/health_checks/unresolved_refs.py
```
Expected: PASS; clean.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/graph/migrate.py science/src/science_tool/graph/materialize.py science/src/science_tool/graph/cli.py science/src/science_tool/validate/checks/graph.py science/src/science_tool/graph/freshness.py science/src/science_tool/entities.py science/src/science_tool/graph/health_checks/unresolved_refs.py science/tests/
git commit -m "feat(graph): audit family returns ValidationVerdict; all consumers fail closed on unwired"
```

---

### Task 4: Widen the boundary guard to cover the family

**Files:**
- Modify: `science/src/science_tool/instruments.py` (`INSTRUMENT_MODULES` docstring + entries)
- Modify: `science/tests/test_instrument_boundary.py` (namespace, detector, `_NOT_INSTRUMENTS`, prose, parameterized detector test)

**Interfaces:**
- Consumes: the migrated tree (Tasks 2, 3) — after them, no public function in the namespace returns `tuple[list[T], bool]`.

- [ ] **Step 1: Write the failing detector + parameterization tests**

Add to `tests/test_instrument_boundary.py`:

```python
import ast

import pytest

from science_tool.instruments import INSTRUMENT_MODULES


@pytest.mark.parametrize(
    "annotation",
    ["tuple[list[dict[str, str]], bool]", "tuple[list[str], str | None]", "tuple[list[int], Optional[str]]"],
)
def test_detector_flags_both_precursor_families(annotation: str) -> None:
    node = ast.parse(f"def f() -> {annotation}: ...").body[0]
    assert _is_tuple_precursor(node.returns) is True


def test_detector_ignores_verdict_and_instrument_returns() -> None:
    for annotation in ("ValidationVerdict[dict[str, str]]", "InstrumentResult[dict[str, str]]", "tuple[Graph, Graph]"):
        node = ast.parse(f"def f() -> {annotation}: ...").body[0]
        assert _is_tuple_precursor(node.returns) is False


def test_new_modules_in_namespace() -> None:
    assert "graph/materialize.py" in INSTRUMENT_MODULES
    assert "graph/migrate.py" in INSTRUMENT_MODULES
```

Import `_is_tuple_precursor` at the top of the test module.

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_instrument_boundary.py -k "detector or new_modules" -q`
Expected: FAIL (`tuple[list, bool]` not flagged; new modules absent).

- [ ] **Step 3: Widen the namespace + detector**

In `instruments.py`, append to `INSTRUMENT_MODULES` and update its docstring's "must return `InstrumentResult`" wording to "must return `InstrumentResult` or `ValidationVerdict`":
```python
    "graph/materialize.py",
    "graph/migrate.py",
```

In `test_instrument_boundary.py`, rewrite `_is_tuple_precursor` to accept the `bool` verdict channel as well as the `str | None` reason channel:
```python
def _is_tuple_precursor(node: ast.expr) -> bool:
    """Match ``tuple[list[T], bool]`` (the has_failures verdict) and ``tuple[list[T], str | None]``
    (the reason precursor). Both are pre-convergence shapes: the verdict now belongs in
    ``ValidationVerdict`` and the reason in ``InstrumentResult``. (Reversed from the earlier
    exclusion of the bool channel — the sibling type carries it now.)
    """
    if not isinstance(node, ast.Subscript):
        return False
    if _annotation_root(node) != "tuple":
        return False
    inner = node.slice
    if not isinstance(inner, ast.Tuple) or len(inner.elts) != 2:
        return False
    if _annotation_root(inner.elts[0]) != "list":
        return False
    second = inner.elts[1]
    return _is_str_or_none(second) or _annotation_root(second) == "bool"
```

Add the `_NOT_INSTRUMENTS` entry for the newly-exposed pure helper:
```python
        # Pure fold over a caller-supplied IdentityTable -> audit rows. Zero I/O; the only
        # caller is audit_project_sources internally. Empty rows == "no collisions in THIS
        # table", a fact about the argument, not the world. Surfaced only because migrate.py
        # joined the namespace.
        ("graph/migrate.py", "audit_identity_table"),
```

Update the module docstring, the `test_instrument_namespace_returns_instrument_result` assertion message, and the offender-message text to read "`InstrumentResult` or `ValidationVerdict`."

- [ ] **Step 4: Run the full guard suite**

Run: `cd science && uv run --frozen pytest tests/test_instrument_boundary.py -q`
Expected: PASS — `test_instrument_namespace_returns_instrument_result`, `test_migration_is_complete`, `test_allowlist_has_no_stale_entries`, `test_sets_are_disjoint`, and the new detector tests all green (the full-namespace scan finds zero remaining offenders).

- [ ] **Step 5: Full validation sweep**

Run: `cd science && uv run --frozen pytest -q && uv run ruff check && uv run pyright`
Expected: PASS across the suite; ruff + pyright clean. This is the whole-tree gate: any consumer missed in Tasks 2-3 surfaces here as a `pyright` error or a failing test.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/instruments.py science/tests/test_instrument_boundary.py
git commit -m "test(instruments): guard covers the ValidationVerdict family; detector flags tuple[list,bool]"
```

---

## Self-Review

**Spec coverage** (design §1-§9):
- §2 type → Task 1. §3 scope (4 migrations, 1 privatization, 1 `_NOT_INSTRUMENTS`) → Tasks 2 (validators + privatize), 3 (audit family), 4 (`audit_identity_table`). §4 unwired codes → Task 2 Step 3 (`graph_missing`/`unparseable`, tested Step 1). §5 consumer contract (every disposition) → Task 2 (validate CLI, validate-check) + Task 3 (audit CLI, audit-check, `_compile`, freshness, entities, `collect_unresolved_refs`). §6 guard (modules, detector, `_NOT_INSTRUMENTS`, prose) → Task 4. §7 tests (type, per-disposition fail-closed, both-precursor detector) → Tasks 1, 2, 3, 4. §8 files → covered.
- **Every §5 disposition has a fail-closed test:** graph validate (T2), graph audit (T3 — via `unwrap_verdict`, exercised by the audit-check test + CLI), validate-check validate side (T2), validate-check audit side (add in T3 Step 6 if not present — see note), `_compile` (T3), freshness (T3), entities (T3), `collect_unresolved_refs` (T3).

**Placeholder scan:** All production symbols are pinned — `_validate_prospective_write` (entities.py:1731), `propagate_freshness_in_memory` (freshness.py:407), `collect_unresolved_refs(project_root, *, sources=None)` (unresolved_refs.py:49). The remaining `...` occurrences are the neighboring tests' existing `ProjectSources`/`sources` builders (`test_graph_migrate.py`, `test_health.py`, `test_entities.py` already construct these) — the implementer reuses each module's own builder rather than inventing one. Monkeypatch targets account for import style: `freshness` imports the audit **lazily**, so its test patches `migrate.audit_project_sources`; `materialize`/`entities`/`unresolved_refs` import it at module level and patch their own module name.

**Type consistency:** `ValidationVerdict.from_has_failures(rows, has_failures)`, `.passed(rows)`, `.failed(rows)`, `.unwired(code=, reason=)`, and `unwrap_verdict(verdict, what=) -> (rows, has_failures)` are used identically across Tasks 1-3. `AuditRow` is the row type for `audit_project_sources`; `dict[str, str]` for `validate_graph*` and `materialization_audit`.

**Note for the implementer:** Task 3 Step 5 adds the validate-check *audit-side* `unwired` branch; add a regression for it alongside the validate-side one in `tests/validate/test_checks_graph.py` (inject an `unwired` `materialization_audit`, assert an ERROR finding, not "all canonical references resolved").
