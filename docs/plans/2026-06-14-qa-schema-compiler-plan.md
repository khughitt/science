# Schema→Checks Compiler + Generic `tabular` Program — Implementation Plan (Spec 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `science_qa` run directly off a Frictionless `datapackage.json` by compiling a resource's typed Table Schema (+ its `qa:` extension) into the existing `QAConfig`, and ship a generic `tabular` program so QA runs usefully on ordinary tables without the false build-fatal flags the scRNA program produces on non-scRNA data.

**Architecture:** A new plain-dict `science_qa/compile.py` turns a resource descriptor into a `QAConfig` (no pydantic); a new hand-declared `tabular` `Program` (general + tabular + numeric-column aspects only) consumes it through the unchanged runner. New CLI mode `run --datapackage P --resource R [--config qa.yaml]` reads the schema as the source of truth at run time and merges optional operational run-knobs.

**Tech Stack:** Python 3, `science_qa` (pandas / pyarrow / pyyaml / click only — NO pydantic), Frictionless Data Package / Table Schema v2.

---

## Reference: spec

Design doc: `docs/plans/2026-06-14-qa-schema-compiler-design.md`. Read §1 (data flow), §2 (the `tabular` program), §3 (the schema→QAConfig mapping table — the heart), §4 (`bounds` check), §5 (input/merge model), §6 (behavioral rules), §7 (severity), §8 (errors). This plan implements that design; where they differ, the design wins, **except** one deliberate implementation choice noted below.

**Implementation choice (consistent with design §4/§8):** the uncoercible-column condition in the `bounds` aspect is raised as a **`ValueError`**, not `RunnerError`. The aspects cannot import `runner.RunnerError` without a circular import (`runner → program → numeric_column`), and `cli.py` already catches `ValueError` and surfaces it as exit 2 — identical user-facing behavior to the design's stated `RunnerError` (exit 2, fail-early).

## Workspace, conventions & test recipe

**Workspace (execution-time):** implement in an isolated git worktree created **off local `main`**. The using-git-worktrees skill handles this. As a one-time setup before Task 1, copy the two Spec-2 docs into the worktree and commit them so the branch is self-contained:

```bash
# from the worktree root (off main):
cp ~/d/science/docs/plans/2026-06-14-qa-schema-compiler-design.md docs/plans/
cp ~/d/science/docs/plans/2026-06-14-qa-schema-compiler-plan.md   docs/plans/
git add docs/plans/2026-06-14-qa-schema-compiler-*.md
git commit -m "docs(qa-compiler): add Spec 2 design + implementation plan"
```

**Test recipe (use for every test step).** `science_qa` is a standalone distribution under `science/qa/`. The framework venv has pytest + pandas + pyyaml + click. Run from the `qa` dir with `PYTHONPATH=src`:

```bash
cd <worktree>/science/qa
PY=~/d/science/science/.venv/bin/python
PYTHONPATH=src $PY -m pytest tests/<file>.py -v        # one file
PYTHONPATH=src $PY -m pytest tests -q                  # whole science_qa suite (baseline: 77 passing)
```

**Commit hygiene:** `git add` only the explicit files named in each task — never `-A`/`.` (the `.git` metadata is Dropbox-synced and an unrelated workstream may advance HEAD mid-session). If you find conflict markers or changes in files outside your task's scope, STOP and report BLOCKED. **Before each commit, verify the branch** (`git -C <worktree-root> branch --show-current`) is the feature branch, not `main`.

**No Co-Authored-By trailers** in commits. Use `~/d/` (not absolute Dropbox paths) in any doc/code text.

## File structure

| File | Responsibility |
|---|---|
| `science/qa/src/science_qa/config.py` (**modify**) | add `bounds` + `unique_keys` fields; `from_file(require_program=True)` |
| `science/qa/src/science_qa/aspects/numeric_column.py` (**modify**) | new `bounds` check fn (structural) |
| `science/qa/src/science_qa/aspects/tabular.py` (**modify**) | composite-aware `unique_key` |
| `science/qa/src/science_qa/program.py` (**modify**) | new `tabular` Program; `_expand_bounds`; composite `_expand_unique_key` |
| `science/qa/src/science_qa/compile.py` (**create**) | `schema_to_config`, `merge_configs`, `CompileError` |
| `science/qa/src/science_qa/runner.py` (**modify**) | factor `_run_with_config`; add `run_qa_datapackage` |
| `science/qa/src/science_qa/cli.py` (**modify**) | `--datapackage`/`--resource` mode + mode validation |
| `science/qa/tests/test_config.py` (**modify**) | `require_program=False`; new fields |
| `science/qa/tests/test_aspect_numeric_column.py` (**modify**) | `bounds` cases |
| `science/qa/tests/test_aspect_tabular.py` (**modify**) | composite `unique_key` |
| `science/qa/tests/test_program.py` (**modify**) | `tabular` registration + expands |
| `science/qa/tests/test_compile.py` (**create**) | mapping rows, FK, merge, errors |
| `science/qa/tests/test_runner.py` (**modify**) | datapackage end-to-end |
| `science/qa/tests/test_cli_run.py` (**modify**) | datapackage CLI + mode validation + dogfood regression |

---

## Task 1: `QAConfig` — `bounds` + `unique_keys` fields and program-optional loader

**Files:**
- Modify: `science/qa/src/science_qa/config.py`
- Test: `science/qa/tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/qa/tests/test_config.py`:

```python
def test_new_fields_default_empty():
    cfg = QAConfig(program="tabular")
    assert cfg.bounds == {} and cfg.unique_keys == []


def test_require_program_false_allows_missing_program(tmp_path):
    cfg = QAConfig.from_file(_write(tmp_path, "qa:\n  polarity: [x]\n"), require_program=False)
    assert cfg.program == "" and cfg.polarity == ["x"]


def test_require_program_true_is_default(tmp_path):
    with pytest.raises(QAConfigError, match="program"):
        QAConfig.from_file(_write(tmp_path, "qa:\n  polarity: [x]\n"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_config.py -v`
Expected: FAIL — `TypeError` on unexpected `bounds`/`require_program`, or `AttributeError`.

- [ ] **Step 3: Add the fields and the loader parameter**

In `science/qa/src/science_qa/config.py`, add two fields to the `QAConfig` dataclass (after the existing `ranges` field):

```python
    bounds: dict[str, dict] = field(default_factory=dict)
    unique_keys: list[list[str]] = field(default_factory=list)
```

Then change the `from_file` signature and the program check:

```python
    @classmethod
    def from_file(cls, path: Path, require_program: bool = True) -> "QAConfig":
        if not path.exists():
            raise QAConfigError(f"QA config not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict) or "qa" not in data:
            raise QAConfigError(f"config {path} has no 'qa:' block")
        qa = data["qa"] or {}
        program = qa.get("program")
        if require_program and not program:
            raise QAConfigError(f"config {path} has no 'program:' key (required)")
        return cls(
            program=str(program) if program else "",
            unique_key=qa.get("unique_key"),
            required_complete=list(qa.get("required_complete", []) or []),
            categoricals=dict(qa.get("categoricals", {}) or {}),
            exclusive_flags=[list(pair) for pair in (qa.get("exclusive_flags", []) or [])],
            expected_types=dict(qa.get("expected_types", {}) or {}),
            polarity=list(qa.get("polarity", []) or []),
            ranges=dict(qa.get("ranges", {}) or {}),
            bounds=dict(qa.get("bounds", {}) or {}),
            unique_keys=[list(g) for g in (qa.get("unique_keys", []) or [])],
            missing_sentinels=list(qa.get("missing_sentinels", []) or []),
            column_sets=dict(qa.get("column_sets", {}) or {}),
            aspect_params=dict(qa.get("aspect_params", {}) or {}),
            project_local=list(qa.get("project_local", []) or []),
            base_dir=path.parent,
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_config.py -v`
Expected: PASS (existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add science/qa/src/science_qa/config.py science/qa/tests/test_config.py
git commit -m "feat(qa-compiler): QAConfig bounds/unique_keys fields + program-optional loader"
```

---

## Task 2: `numeric-column/bounds` structural check

**Files:**
- Modify: `science/qa/src/science_qa/aspects/numeric_column.py`
- Test: `science/qa/tests/test_aspect_numeric_column.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/qa/tests/test_aspect_numeric_column.py` (import `bounds` and, if not already present, `SEVERITY_STRUCTURAL`):

```python
import pandas as pd
import pytest
from science_qa.aspects.numeric_column import bounds
from science_qa.context import TableContext
from science_qa.flags import SEVERITY_STRUCTURAL


def _ctx(df, col):
    return TableContext(table=df, columns=[col])


def test_bounds_minimum_violation_is_structural():
    df = pd.DataFrame({"x": [-1, 0, 5]})
    flags = bounds(_ctx(df, "x"), {"bounds": {"minimum": 0}})
    assert len(flags) == 1
    assert flags[0].severity == SEVERITY_STRUCTURAL
    assert flags[0].side == "minimum" and flags[0].value == "1"


def test_bounds_exclusive_maximum_counts_boundary():
    df = pd.DataFrame({"x": [1, 2, 3]})
    flags = bounds(_ctx(df, "x"), {"bounds": {"exclusiveMaximum": 3}})
    assert len(flags) == 1 and flags[0].side == "exclusiveMaximum" and flags[0].value == "1"  # the 3 violates


def test_bounds_min_and_max_use_distinct_bound_key_sides():
    df = pd.DataFrame({"x": [-1, 5, 100]})
    flags = bounds(_ctx(df, "x"), {"bounds": {"minimum": 0, "maximum": 10}})
    assert {f.side for f in flags} == {"minimum", "maximum"}


def test_bounds_inclusive_and_exclusive_min_get_distinct_flag_ids():
    df = pd.DataFrame({"x": [0, 1, 2]})
    flags = bounds(_ctx(df, "x"), {"bounds": {"exclusiveMinimum": 0}})
    assert flags[0].side == "exclusiveMinimum"  # not collapsed to "min"; distinct from "minimum"


def test_bounds_clean_column_no_flags():
    df = pd.DataFrame({"x": [0, 5, 10]})
    assert bounds(_ctx(df, "x"), {"bounds": {"minimum": 0, "maximum": 10}}) == []


def test_bounds_temporal_iso_string():
    df = pd.DataFrame({"d": ["2019-01-01", "2020-06-01", "2021-01-01"]})
    flags = bounds(_ctx(df, "d"), {"bounds": {"minimum": "2020-01-01"}})
    assert len(flags) == 1 and flags[0].value == "1"  # the 2019 date


def test_bounds_uncoercible_column_raises():
    df = pd.DataFrame({"s": ["a", "b", "c"]})
    with pytest.raises(ValueError, match="cannot be coerced"):
        bounds(_ctx(df, "s"), {"bounds": {"minimum": 0}})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_aspect_numeric_column.py -v -k bounds`
Expected: FAIL — `ImportError: cannot import name 'bounds'`.

- [ ] **Step 3: Add the `bounds` check fn**

Append to `science/qa/src/science_qa/aspects/numeric_column.py`:

```python
_BOUND_CHECKS = (
    ("minimum", lambda s, v: s < v),
    ("exclusiveMinimum", lambda s, v: s <= v),
    ("maximum", lambda s, v: s > v),
    ("exclusiveMaximum", lambda s, v: s >= v),
)


def bounds(ctx: TableContext, params: dict) -> list[Flag]:
    """Hard structural bounds from native Frictionless constraints (Spec 1 invariants).

    params["bounds"] is a subset of {minimum, maximum, exclusiveMinimum, exclusiveMaximum}.
    Bound values are numbers or ISO date/datetime strings. Emits one SEVERITY_STRUCTURAL
    Flag per violated bound. Distinct from numeric-column/range (distribution soft band).
    A column that cannot be coerced to the bound's kind raises ValueError (exit 2).
    """
    col = ctx.columns[0]
    spec = params["bounds"]
    numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in spec.values())
    raw = ctx.table[col]
    if numeric:
        series = pd.to_numeric(raw, errors="coerce")
        cmp_spec = dict(spec)
    else:
        series = pd.to_datetime(raw, errors="coerce")
        cmp_spec = {k: pd.Timestamp(v) for k, v in spec.items()}
    if len(raw) and series.isna().all():
        raise ValueError(f"numeric-column/bounds: column {col!r} cannot be coerced for bounds {spec}")
    series = series.dropna()
    flags: list[Flag] = []
    for key, op in _BOUND_CHECKS:
        if key in cmp_spec:
            n = int(op(series, cmp_spec[key]).sum())
            if n:
                # `side` is the exact bound key (minimum/exclusiveMinimum/maximum/
                # exclusiveMaximum) so each constraint gets a distinct flag_id — an
                # inclusive↔exclusive change is not silently the same disposition.
                flags.append(Flag(ASPECT, "bounds", col, key, SEVERITY_STRUCTURAL,
                                  str(n), str(spec[key]), f"{n} value(s) violate {key} {spec[key]}"))
    return flags
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_aspect_numeric_column.py -v`
Expected: PASS (existing + 7 new).

- [ ] **Step 5: Commit**

```bash
git add science/qa/src/science_qa/aspects/numeric_column.py science/qa/tests/test_aspect_numeric_column.py
git commit -m "feat(qa-compiler): numeric-column/bounds structural check"
```

---

## Task 3: composite-aware `tabular/unique_key`

**Files:**
- Modify: `science/qa/src/science_qa/aspects/tabular.py`
- Test: `science/qa/tests/test_aspect_tabular.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/qa/tests/test_aspect_tabular.py` (import `unique_key`, `TableContext`, `SEVERITY_STRUCTURAL` if not present):

```python
import pandas as pd
from science_qa.aspects.tabular import unique_key
from science_qa.context import TableContext


def test_unique_key_single_column_dupes():
    df = pd.DataFrame({"id": [1, 1, 2]})
    flags = unique_key(TableContext(table=df, columns=["id"]), {})
    assert len(flags) == 1 and flags[0].subject == "id" and flags[0].value == "1"


def test_unique_key_composite_counts_tuple_dupes():
    df = pd.DataFrame({"a": [1, 1, 1], "b": ["x", "x", "y"]})
    flags = unique_key(TableContext(table=df, columns=["a", "b"]), {})
    # (1,"x") repeats once -> 1 duplicate row-tuple; subject is the joined key
    assert len(flags) == 1 and flags[0].subject == "a+b" and flags[0].value == "1"


def test_unique_key_composite_unique_is_clean():
    df = pd.DataFrame({"a": [1, 1], "b": ["x", "y"]})
    assert unique_key(TableContext(table=df, columns=["a", "b"]), {}) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_aspect_tabular.py -v -k unique_key`
Expected: FAIL — composite test gets `subject == "id"`/`IndexError`, or the join assertion fails (current impl uses `ctx.columns[0]` only).

- [ ] **Step 3: Make `unique_key` composite-aware**

Replace the existing `unique_key` function in `science/qa/src/science_qa/aspects/tabular.py` with:

```python
def unique_key(ctx: TableContext, params: dict) -> list[Flag]:
    cols = list(ctx.columns)
    subject = "+".join(cols)
    dupes = int(ctx.table[cols].duplicated().sum())
    if dupes:
        return [Flag("tabular", "unique_key", subject, None, SEVERITY_STRUCTURAL,
                     str(dupes), "0", f"{dupes} duplicate key value(s)")]
    return []
```

(`ctx.table[cols]` with a single-element list yields the same duplicate count as the old single-column path, so existing single-column behavior is preserved; only the `subject` for a 1-col key is unchanged because `"+".join(["id"]) == "id"`.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_aspect_tabular.py -v`
Expected: PASS (existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add science/qa/src/science_qa/aspects/tabular.py science/qa/tests/test_aspect_tabular.py
git commit -m "feat(qa-compiler): composite-aware tabular/unique_key"
```

---

## Task 4: the generic `tabular` program

**Files:**
- Modify: `science/qa/src/science_qa/program.py`
- Test: `science/qa/tests/test_program.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/qa/tests/test_program.py`:

```python
def test_tabular_program_registered_with_table_substrate():
    prog = resolve_program("tabular")
    assert prog.substrate is TableContext


def test_tabular_program_excludes_gene_expression_and_scrna():
    prog = resolve_program("tabular")
    aspects = {c.aspect for c in prog.checks}
    assert "gene-expression-qc-table" not in aspects
    assert "scrna-qc-table" not in aspects
    assert {"general", "tabular", "numeric-column"} <= aspects


def test_tabular_has_bounds_family():
    prog = resolve_program("tabular")
    bounds_spec = next(c for c in prog.checks if c.check_id == "numeric-column/bounds")
    config = QAConfig(program="tabular", bounds={"x": {"minimum": 0}})
    invs = bounds_spec.expand(config)
    assert len(invs) == 1 and invs[0].columns == ["x"] and invs[0].requires == ("x",)
    assert invs[0].params == {"bounds": {"minimum": 0}}


def test_tabular_unique_key_expands_scalar_and_groups():
    prog = resolve_program("tabular")
    uk = next(c for c in prog.checks if c.check_id == "tabular/unique_key")
    config = QAConfig(program="tabular", unique_key="id", unique_keys=[["a", "b"]])
    invs = uk.expand(config)
    cols = sorted([inv.columns for inv in invs])
    assert cols == [["a", "b"], ["id"]]


def test_tabular_unique_key_dedupes_overlapping_groups():
    prog = resolve_program("tabular")
    uk = next(c for c in prog.checks if c.check_id == "tabular/unique_key")
    # a field both unique:true and the primaryKey compiles the same ["id"] group twice
    config = QAConfig(program="tabular", unique_keys=[["id"], ["id"]])
    invs = uk.expand(config)
    assert [inv.columns for inv in invs] == [["id"]]  # one invocation, not two
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_program.py -v -k tabular`
Expected: FAIL — `ProgramError: unknown program 'tabular'`.

- [ ] **Step 3: Add `_expand_bounds`, extend `_expand_unique_key`, declare the program**

In `science/qa/src/science_qa/program.py`, replace `_expand_unique_key` with the scalar+groups version:

```python
def _expand_unique_key(config) -> list[Invocation]:
    groups: list[list[str]] = []
    if config.unique_key:
        groups.append([config.unique_key])
    groups.extend([list(g) for g in config.unique_keys])
    # Dedupe overlapping groups (a field can be both unique:true and the primaryKey)
    # so the same key never yields two invocations -> two flags. Order preserved.
    deduped: list[list[str]] = []
    for g in groups:
        if g not in deduped:
            deduped.append(g)
    return [Invocation(columns=g, requires=tuple(g)) for g in deduped]
```

Add a bounds expander (next to the other `_expand_*` functions):

```python
def _expand_bounds(config) -> list[Invocation]:
    return [Invocation(columns=[c], requires=(c,), params={"bounds": b})
            for c, b in config.bounds.items()]
```

Then add the `tabular` program declaration after `_SCRNA_QC_TABLE` and register it:

```python
_TABULAR = Program(
    name="tabular",
    substrate=TableContext,
    checks=[
        CheckSpec("general", "non_empty", CHECK_REQUIRED, TableContext, general.non_empty),
        CheckSpec("general", "missing_fraction", CHECK_REQUIRED, TableContext, general.missing_fraction),
        CheckSpec("tabular", "unique_key", CHECK_FAMILY, TableContext, tabular.unique_key, expand=_expand_unique_key),
        CheckSpec("tabular", "required_complete", CHECK_FAMILY, TableContext, tabular.required_complete, expand=_expand_required_complete),
        CheckSpec("tabular", "categoricals", CHECK_FAMILY, TableContext, tabular.categoricals, expand=_expand_categoricals),
        CheckSpec("tabular", "exclusive_flags", CHECK_FAMILY, TableContext, tabular.exclusive_flags, expand=_expand_exclusive_flags),
        CheckSpec("tabular", "type_conformance", CHECK_FAMILY, TableContext, tabular.type_conformance, expand=_expand_type_conformance),
        CheckSpec("numeric-column", "bounds", CHECK_FAMILY, TableContext, numeric_column.bounds, expand=_expand_bounds),
        CheckSpec("numeric-column", "range", CHECK_FAMILY, TableContext, numeric_column.ranges, expand=_expand_ranges),
        CheckSpec("numeric-column", "polarity", CHECK_FAMILY, TableContext, numeric_column.polarity, expand=_expand_polarity),
        CheckSpec("numeric-column", "zero_fraction", CHECK_REQUIRED, TableContext, numeric_column.zero_fraction, selector={"dtype": "numeric"}),
        CheckSpec("numeric-column", "low_variance", CHECK_REQUIRED, TableContext, numeric_column.low_variance, selector={"dtype": "numeric"}),
        CheckSpec("numeric-column", "missing_sentinel", CHECK_FAMILY, TableContext, numeric_column.missing_sentinels, selector={"dtype": "numeric"}, expand=_expand_missing_sentinels),
    ],
)

PROGRAMS: dict[str, Program] = {_SCRNA_QC_TABLE.name: _SCRNA_QC_TABLE, _TABULAR.name: _TABULAR}
```

(Delete the old single-line `PROGRAMS = {_SCRNA_QC_TABLE.name: _SCRNA_QC_TABLE}` assignment — replaced by the two-entry dict above.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_program.py -v`
Expected: PASS (existing + 5 new). The existing scrna `_expand_unique_key` test still passes (scalar path unchanged).

- [ ] **Step 5: Commit**

```bash
git add science/qa/src/science_qa/program.py science/qa/tests/test_program.py
git commit -m "feat(qa-compiler): generic tabular program (+bounds family, composite unique_key)"
```

---

## Task 5: `compile.py` — native-constraints mapping

**Files:**
- Create: `science/qa/src/science_qa/compile.py`
- Test: `science/qa/tests/test_compile.py`

- [ ] **Step 1: Write the failing tests**

Create `science/qa/tests/test_compile.py`:

```python
from pathlib import Path

import pytest
from science_qa.compile import CompileError, schema_to_config


def _resource(schema: dict, name="obs", path="obs.csv") -> dict:
    return {"name": name, "path": path, "schema": schema}


def _pkg(*resources: dict) -> dict:
    return {"name": "p", "resources": list(resources)}


class TestNativeMapping:
    def test_required_and_unique_and_type(self):
        res = _resource({"fields": [
            {"name": "id", "type": "integer", "constraints": {"required": True, "unique": True}},
            {"name": "label", "type": "string"},
        ]})
        cfg = schema_to_config(res, Path("/pkg"), _pkg(res))
        assert cfg.required_complete == ["id"]
        assert cfg.unique_keys == [["id"]]
        assert cfg.expected_types == {"id": "numeric", "label": "non-numeric"}
        assert cfg.base_dir == Path("/pkg")

    def test_type_any_produces_no_conformance_entry(self):
        res = _resource({"fields": [{"name": "x"}, {"name": "y", "type": "any"}]})
        cfg = schema_to_config(res, Path("/pkg"), _pkg(res))
        assert cfg.expected_types == {}

    def test_bounds_and_enum(self):
        res = _resource({"fields": [
            {"name": "p", "type": "number", "constraints": {"minimum": 0, "maximum": 100}},
            {"name": "grade", "type": "string", "constraints": {"enum": ["a", "b"]}},
        ]})
        cfg = schema_to_config(res, Path("/pkg"), _pkg(res))
        assert cfg.bounds == {"p": {"minimum": 0, "maximum": 100}}
        assert cfg.categoricals == {"grade": {"allowed": ["a", "b"]}}

    def test_primary_key_and_unique_keys_groups(self):
        res = _resource({"fields": [{"name": "a"}, {"name": "b"}, {"name": "c"}],
                         "primaryKey": ["a", "b"], "uniqueKeys": [["c"]]})
        cfg = schema_to_config(res, Path("/pkg"), _pkg(res))
        assert ["a", "b"] in cfg.unique_keys and ["c"] in cfg.unique_keys

    def test_missing_values_normalized_and_empty_dropped(self):
        res = _resource({"fields": [{"name": "x"}],
                         "missingValues": ["", "NA", {"value": "-999", "label": "sensor"}]})
        cfg = schema_to_config(res, Path("/pkg"), _pkg(res))
        assert cfg.missing_sentinels == ["NA", "-999"]

    def test_missing_schema_or_path_errors(self):
        with pytest.raises(CompileError, match="schema"):
            schema_to_config({"name": "o", "path": "o.csv"}, Path("/pkg"), _pkg())
        with pytest.raises(CompileError, match="path"):
            schema_to_config({"name": "o", "schema": {"fields": []}}, Path("/pkg"), _pkg())

    def test_empty_schema_is_minimal_not_crash(self):
        res = _resource({"fields": []})
        cfg = schema_to_config(res, Path("/pkg"), _pkg(res))
        assert cfg.program == "" and cfg.required_complete == [] and cfg.bounds == {}

    def test_numeric_and_iso_date_bounds_accepted(self):
        res = _resource({"fields": [
            {"name": "p", "type": "number", "constraints": {"minimum": 0}},
            {"name": "d", "type": "date", "constraints": {"maximum": "2020-01-01"}},
        ]})
        cfg = schema_to_config(res, Path("/pkg"), _pkg(res))
        assert cfg.bounds == {"p": {"minimum": 0}, "d": {"maximum": "2020-01-01"}}

    def test_malformed_bound_value_is_compile_error(self):
        # descriptor-only: a string bound that is neither a number nor a parseable date
        res = _resource({"fields": [{"name": "p", "type": "number",
                                     "constraints": {"minimum": "not-a-date"}}]})
        with pytest.raises(CompileError, match="parseable ISO date"):
            schema_to_config(res, Path("/pkg"), _pkg(res))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_compile.py -v -k TestNativeMapping`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_qa.compile'`.

- [ ] **Step 3: Create `compile.py` with `schema_to_config` (native + table-qa; FK added in Task 6)**

Create `science/qa/src/science_qa/compile.py`:

```python
"""Compile a Frictionless resource descriptor into a QAConfig (Spec 2).

Plain-dict only (no pydantic): the on-disk Table Schema + its `qa:` extension are the
single source of truth, read at run time. Native constraints map to structural checks;
the `qa:` extension maps to distribution checks. See
docs/plans/2026-06-14-qa-schema-compiler-design.md.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from science_qa.config import QAConfig

_BOUND_KEYS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")


class CompileError(Exception):
    """Raised on a descriptor that cannot be compiled (fail early, exit 2)."""


def _validate_bound_value(field: str, key: str, value: object) -> None:
    """A bound value must be a number or a parseable ISO date/datetime string (design §8).

    This is a *descriptor-only* check (no table) — it uses the same parser (`pd.Timestamp`)
    the bounds aspect uses at run time, so a value the compiler accepts is one the aspect
    can parse. A non-scalar, or an unparseable string, is a CompileError (exit 2).
    """
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise CompileError(f"field {field!r} bound {key} has non-scalar value {value!r}")
    if isinstance(value, str):
        try:
            pd.Timestamp(value)
        except (ValueError, TypeError) as exc:
            raise CompileError(
                f"field {field!r} bound {key}={value!r} is neither a number nor a parseable ISO date"
            ) from exc


def schema_to_config(resource: dict, package_dir: Path, package: dict) -> QAConfig:
    schema = resource.get("schema")
    name = resource.get("name", "?")
    if not isinstance(schema, dict) or "fields" not in schema:
        raise CompileError(f"resource {name!r} has no usable schema (need schema.fields)")
    if "path" not in resource:
        raise CompileError(f"resource {name!r} has no path")

    cfg = QAConfig(program="", base_dir=package_dir)

    for f in schema.get("fields", []):
        fname = f["name"]
        ftype = f.get("type", "any")
        constraints = f.get("constraints", {}) or {}
        if constraints.get("required"):
            cfg.required_complete.append(fname)
        if constraints.get("unique"):
            cfg.unique_keys.append([fname])
        if ftype in ("integer", "number"):
            cfg.expected_types[fname] = "numeric"
        elif ftype != "any":
            cfg.expected_types[fname] = "non-numeric"
        bound = {k: constraints[k] for k in _BOUND_KEYS if k in constraints}
        if bound:
            for bkey, bval in bound.items():
                _validate_bound_value(fname, bkey, bval)
            cfg.bounds[fname] = bound
        if "enum" in constraints:
            cfg.categoricals[fname] = {"allowed": list(constraints["enum"])}

    pk = schema.get("primaryKey")
    if pk:
        cfg.unique_keys.append(pk if isinstance(pk, list) else [pk])
    for group in schema.get("uniqueKeys", []) or []:
        cfg.unique_keys.append(list(group))

    for entry in schema.get("missingValues", [""]):
        value = entry if isinstance(entry, str) else entry.get("value")
        if value not in ("", None):
            cfg.missing_sentinels.append(value)

    table_qa = schema.get("qa", {}) or {}
    for pair in table_qa.get("exclusive_flags", []) or []:
        cfg.exclusive_flags.append(list(pair))

    _compile_foreign_keys(resource, schema, package, cfg)  # added in Task 6
    return cfg


def _compile_foreign_keys(resource: dict, schema: dict, package: dict, cfg: QAConfig) -> None:
    """Single-column FK → categoricals(allowed_from). Filled in Task 6."""
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_compile.py -v -k TestNativeMapping`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add science/qa/src/science_qa/compile.py science/qa/tests/test_compile.py
git commit -m "feat(qa-compiler): schema_to_config native-constraints + table-qa mapping"
```

---

## Task 6: `compile.py` — foreign keys (single-column) + composite rejection

**Files:**
- Modify: `science/qa/src/science_qa/compile.py`
- Test: `science/qa/tests/test_compile.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/qa/tests/test_compile.py`:

```python
class TestForeignKeys:
    def test_single_column_fk_resolves_to_allowed_from(self):
        proteins = _resource({"fields": [{"name": "id"}]}, name="proteins", path="proteins.csv")
        edges = _resource(
            {"fields": [{"name": "src"}],
             "foreignKeys": [{"fields": "src", "reference": {"resource": "proteins", "fields": "id"}}]},
            name="edges", path="edges.csv",
        )
        cfg = schema_to_config(edges, Path("/pkg"), _pkg(proteins, edges))
        assert cfg.categoricals == {"src": {"allowed_from": "proteins.csv#id"}}

    def test_self_reference_points_at_own_path(self):
        tree = _resource(
            {"fields": [{"name": "id"}, {"name": "parent"}],
             "foreignKeys": [{"fields": "parent", "reference": {"fields": "id"}}]},
            name="tree", path="tree.csv",
        )
        cfg = schema_to_config(tree, Path("/pkg"), _pkg(tree))
        assert cfg.categoricals == {"parent": {"allowed_from": "tree.csv#id"}}

    def test_composite_fk_rejected(self):
        res = _resource(
            {"fields": [{"name": "a"}, {"name": "b"}],
             "foreignKeys": [{"fields": ["a", "b"], "reference": {"resource": "t", "fields": ["x", "y"]}}]},
        )
        with pytest.raises(CompileError, match="composite foreignKey"):
            schema_to_config(res, Path("/pkg"), _pkg(res))

    def test_unknown_target_resource_rejected(self):
        res = _resource(
            {"fields": [{"name": "src"}],
             "foreignKeys": [{"fields": "src", "reference": {"resource": "ghost", "fields": "id"}}]},
        )
        with pytest.raises(CompileError, match="unknown resource"):
            schema_to_config(res, Path("/pkg"), _pkg(res))

    def test_unknown_target_field_rejected(self):
        proteins = _resource({"fields": [{"name": "id"}]}, name="proteins", path="proteins.csv")
        edges = _resource(
            {"fields": [{"name": "src"}],
             "foreignKeys": [{"fields": "src", "reference": {"resource": "proteins", "fields": "nope"}}]},
            name="edges", path="edges.csv",
        )
        with pytest.raises(CompileError, match="reference field"):
            schema_to_config(edges, Path("/pkg"), _pkg(proteins, edges))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_compile.py -v -k TestForeignKeys`
Expected: FAIL — `_compile_foreign_keys` is a stub, so `cfg.categoricals` is empty and the error cases don't raise.

- [ ] **Step 3: Implement `_compile_foreign_keys`**

Replace the stub `_compile_foreign_keys` in `science/qa/src/science_qa/compile.py` with:

```python
def _as_one(value) -> tuple[str, bool]:
    """Return (single_name, is_composite) for a FK fields value (str or list)."""
    if isinstance(value, list):
        return (value[0] if value else "", len(value) > 1)
    return (value, False)


def _compile_foreign_keys(resource: dict, schema: dict, package: dict, cfg: QAConfig) -> None:
    by_name = {r.get("name"): r for r in package.get("resources", [])}
    self_name = resource.get("name")
    for fk in schema.get("foreignKeys", []) or []:
        local, local_composite = _as_one(fk["fields"])
        ref = fk.get("reference", {})
        ref_field, ref_composite = _as_one(ref.get("fields"))
        if local_composite or ref_composite:
            raise CompileError(f"composite foreignKey not supported (single-column only): {fk}")
        target_name = ref.get("resource") or self_name
        target = by_name.get(target_name)
        if target is None:
            raise CompileError(f"foreignKey on {self_name!r} references unknown resource {target_name!r}")
        target_fields = {f["name"] for f in (target.get("schema", {}) or {}).get("fields", [])}
        if ref_field not in target_fields:
            raise CompileError(
                f"foreignKey on {self_name!r} reference field {ref_field!r} not in resource {target_name!r}")
        cfg.categoricals[local] = {"allowed_from": f"{target['path']}#{ref_field}"}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_compile.py -v`
Expected: PASS (TestNativeMapping + TestForeignKeys).

- [ ] **Step 5: Commit**

```bash
git add science/qa/src/science_qa/compile.py science/qa/tests/test_compile.py
git commit -m "feat(qa-compiler): single-column foreignKey compilation + composite rejection"
```

---

## Task 7: `compile.py` — `merge_configs`

**Files:**
- Modify: `science/qa/src/science_qa/compile.py`
- Test: `science/qa/tests/test_compile.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/qa/tests/test_compile.py` (add `merge_configs` to the import):

```python
from science_qa.compile import merge_configs  # add to existing import line
from science_qa.config import QAConfig


class TestMerge:
    def test_program_scalar_runknob_wins(self):
        contract = QAConfig(program="")
        runknobs = QAConfig(program="tabular")
        assert merge_configs(contract, runknobs).program == "tabular"

    def test_dict_union_with_runknob_override(self):
        contract = QAConfig(program="", bounds={"x": {"minimum": 0}}, categoricals={"g": {"allowed": ["a"]}})
        runknobs = QAConfig(program="", bounds={"y": {"maximum": 9}}, categoricals={"g": {"allowed": ["b"]}})
        merged = merge_configs(contract, runknobs)
        assert merged.bounds == {"x": {"minimum": 0}, "y": {"maximum": 9}}
        assert merged.categoricals == {"g": {"allowed": ["b"]}}  # runknob overrides same key

    def test_runknob_only_fields_overlay(self):
        contract = QAConfig(program="", base_dir=Path("/pkg"))
        runknobs = QAConfig(program="", polarity=["x"], project_local=["m:c"])
        merged = merge_configs(contract, runknobs)
        assert merged.polarity == ["x"] and merged.project_local == ["m:c"]
        assert merged.base_dir == Path("/pkg")  # contract base_dir (allowed_from resolves against package)

    def test_list_union_dedupes(self):
        # ["a"] and required "a" both appear in contract AND runknobs -> deduped, order kept
        contract = QAConfig(program="", required_complete=["a"], unique_keys=[["a"]])
        runknobs = QAConfig(program="", required_complete=["a", "b"], unique_keys=[["a"], ["b"]])
        merged = merge_configs(contract, runknobs)
        assert merged.required_complete == ["a", "b"]
        assert merged.unique_keys == [["a"], ["b"]]  # the duplicate ["a"] group collapsed
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_compile.py -v -k TestMerge`
Expected: FAIL — `ImportError: cannot import name 'merge_configs'`.

- [ ] **Step 3: Add `merge_configs`**

Append to `science/qa/src/science_qa/compile.py`:

```python
def merge_configs(contract: QAConfig, runknobs: QAConfig) -> QAConfig:
    """Overlay operational run-knobs onto the schema-derived contract config (design §5).

    Scalars: run-knob wins when set. Contract list/dict fields: union, run-knob overriding
    on key collision. Run-knob-only fields (polarity, ranges, project_local, aspect_params,
    column_sets): overlaid directly. base_dir stays the contract's (package dir) so
    schema-derived allowed_from pointers resolve.
    """
    merged = QAConfig(
        program=runknobs.program or contract.program,
        unique_key=runknobs.unique_key or contract.unique_key,
        base_dir=contract.base_dir,
    )
    merged.required_complete = list(dict.fromkeys([*contract.required_complete, *runknobs.required_complete]))
    merged.unique_keys = []  # list-of-lists: dedupe by value, preserve order
    for group in [*contract.unique_keys, *runknobs.unique_keys]:
        if group not in merged.unique_keys:
            merged.unique_keys.append(group)
    merged.bounds = {**contract.bounds, **runknobs.bounds}
    merged.categoricals = {**contract.categoricals, **runknobs.categoricals}
    merged.expected_types = {**contract.expected_types, **runknobs.expected_types}
    merged.exclusive_flags = [*contract.exclusive_flags,
                              *[p for p in runknobs.exclusive_flags if p not in contract.exclusive_flags]]
    merged.missing_sentinels = list(dict.fromkeys([*contract.missing_sentinels, *runknobs.missing_sentinels]))
    # run-knob-only overlays
    merged.polarity = runknobs.polarity or contract.polarity
    merged.ranges = {**contract.ranges, **runknobs.ranges}
    merged.project_local = runknobs.project_local or contract.project_local
    merged.aspect_params = {**contract.aspect_params, **runknobs.aspect_params}
    merged.column_sets = {**contract.column_sets, **runknobs.column_sets}
    return merged
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_compile.py -v`
Expected: PASS (all compile tests).

- [ ] **Step 5: Commit**

```bash
git add science/qa/src/science_qa/compile.py science/qa/tests/test_compile.py
git commit -m "feat(qa-compiler): merge_configs run-knob overlay"
```

---

## Task 8: runner — `run_qa_datapackage` (factor `_run_with_config`)

**Files:**
- Modify: `science/qa/src/science_qa/runner.py`
- Test: `science/qa/tests/test_runner.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/qa/tests/test_runner.py`:

```python
import json as _json


def _dp(tmp_path, resource: dict, df) -> Path:
    df.to_parquet(tmp_path / resource["path"])
    pkg = {"name": "p", "resources": [resource]}
    (tmp_path / "datapackage.json").write_text(_json.dumps(pkg))
    return tmp_path / "datapackage.json"


def test_datapackage_zero_config_runs_tabular_clean(tmp_path):
    from science_qa.runner import run_qa_datapackage
    res = {"name": "obs", "path": "obs.parquet",
           "schema": {"fields": [{"name": "id", "type": "integer", "constraints": {"required": True, "unique": True}}]}}
    dp = _dp(tmp_path, res, pd.DataFrame({"id": [1, 2, 3]}))
    result = run_qa_datapackage(dp, "obs", tmp_path)
    assert result.structural_failed is False
    cov = json.loads((tmp_path / "qa_report.json").read_text())["coverage"]
    assert cov["executable_denominator"] >= 1


def test_datapackage_bounds_violation_is_structural(tmp_path):
    from science_qa.runner import run_qa_datapackage
    res = {"name": "obs", "path": "obs.parquet",
           "schema": {"fields": [{"name": "p", "type": "number", "constraints": {"minimum": 0}}]}}
    dp = _dp(tmp_path, res, pd.DataFrame({"p": [-1.0, 0.5, 2.0]}))
    result = run_qa_datapackage(dp, "obs", tmp_path)
    assert result.structural_failed is True
    ids = {f["flag_id"] for f in json.loads((tmp_path / "qa_report.json").read_text())["flags"]}
    assert "numeric-column/bounds/p/minimum" in ids


def test_datapackage_with_runknobs_overlay(tmp_path):
    from science_qa.runner import run_qa_datapackage
    res = {"name": "obs", "path": "obs.parquet",
           "schema": {"fields": [{"name": "v", "type": "number"}]}}
    dp = _dp(tmp_path, res, pd.DataFrame({"v": [-1.0, 1.0]}))
    (tmp_path / "qa.yaml").write_text("qa:\n  polarity: [v]\n")  # no program: -> tabular default
    result = run_qa_datapackage(dp, "obs", tmp_path, runknobs_path=tmp_path / "qa.yaml")
    ids = {f["flag_id"] for f in json.loads((tmp_path / "qa_report.json").read_text())["flags"]}
    assert "numeric-column/polarity/v/-" in ids  # polarity came from the run-knob yaml


def test_datapackage_unknown_resource_errors(tmp_path):
    from science_qa.compile import CompileError
    from science_qa.runner import run_qa_datapackage
    res = {"name": "obs", "path": "obs.parquet", "schema": {"fields": [{"name": "id"}]}}
    dp = _dp(tmp_path, res, pd.DataFrame({"id": [1]}))
    with pytest.raises(CompileError, match="resource"):
        run_qa_datapackage(dp, "missing", tmp_path)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_runner.py -v -k datapackage`
Expected: FAIL — `ImportError: cannot import name 'run_qa_datapackage'`.

- [ ] **Step 3: Factor `_run_with_config` and add `run_qa_datapackage`**

In `science/qa/src/science_qa/runner.py`, add imports near the top (after the existing imports):

```python
import json

from science_qa.compile import CompileError, merge_configs, schema_to_config
```

Replace the body of `run_qa` so it delegates to a new core function, and add `run_qa_datapackage`:

```python
def run_qa(config_path: Path, table_path: Path, report_dir: Path) -> RunResult:
    return _run_with_config(QAConfig.from_file(config_path), table_path, report_dir)


def run_qa_datapackage(datapackage_path: Path, resource_name: str, report_dir: Path,
                       runknobs_path: Path | None = None) -> RunResult:
    package = json.loads(Path(datapackage_path).read_text(encoding="utf-8"))
    resource = next((r for r in package.get("resources", []) if r.get("name") == resource_name), None)
    if resource is None:
        raise CompileError(f"resource {resource_name!r} not found in {datapackage_path}")
    pkg_dir = Path(datapackage_path).parent
    config = schema_to_config(resource, pkg_dir, package)
    if runknobs_path is not None:
        config = merge_configs(config, QAConfig.from_file(runknobs_path, require_program=False))
    if not config.program:
        config.program = "tabular"
    return _run_with_config(config, pkg_dir / resource["path"], report_dir)


def _run_with_config(config: QAConfig, table_path: Path, report_dir: Path) -> RunResult:
    program = resolve_program(config.program)
    built_in_ids = {spec.check_id for spec in program.checks}
    checks = [*program.checks, *load_project_local(config.project_local, reserved_check_ids=built_in_ids)]
    table = _read_table(table_path)

    # static program <-> substrate validation, before any context is built
    for spec in checks:
        if spec.accepts is not program.substrate:
            raise RunnerError(f"check {spec.check_id} accepts {spec.accepts.__name__}, "
                              f"program {program.name} binds {program.substrate.__name__}")

    flags: list[Flag] = []
    coverage = Coverage()

    for spec in checks:
        invs = _invocations(spec, config)
        if spec.expand is not None and not invs:
            coverage.unconfigured_families.append(spec.check_id)
            continue
        for inv in invs:
            entry = _run_invocation(spec, inv, table, config, flags)
            coverage.entries.append(entry)

    write_reports(flags, report_dir=report_dir, rows_checked=len(table), coverage=coverage)
    distribution_ids = [f.flag_id for f in flags if f.severity == SEVERITY_DISTRIBUTION]
    reconcile_dispositions(report_dir, distribution_ids)
    structural_failed = any(f.severity == SEVERITY_STRUCTURAL for f in flags)
    return RunResult(flags=flags, structural_failed=structural_failed, coverage=coverage)
```

(The body of `_run_with_config` is exactly the old `run_qa` body minus its first `config = QAConfig.from_file(...)` line. Delete the original `run_qa` implementation that contained that logic.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_runner.py -v`
Expected: PASS — existing `run_qa(...)` tests (delegating through `_run_with_config`) plus the 4 new datapackage tests.

- [ ] **Step 5: Commit**

```bash
git add science/qa/src/science_qa/runner.py science/qa/tests/test_runner.py
git commit -m "feat(qa-compiler): run_qa_datapackage compiling schema -> QAConfig"
```

---

## Task 9: CLI — `--datapackage`/`--resource` mode + validation + dogfood regression

**Files:**
- Modify: `science/qa/src/science_qa/cli.py`
- Test: `science/qa/tests/test_cli_run.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/qa/tests/test_cli_run.py`:

```python
import json


def _write_dp(tmp_path, resource, df):
    df.to_parquet(tmp_path / resource["path"])
    (tmp_path / "datapackage.json").write_text(json.dumps({"name": "p", "resources": [resource]}))


def test_cli_datapackage_non_scrna_table_runs_clean(tmp_path):
    # the dogfood regression: an ordinary (non-scRNA) table must NOT trip build-fatal flags
    res = {"name": "obs", "path": "obs.parquet",
           "schema": {"fields": [{"name": "cluster", "type": "integer"},
                                 {"name": "label", "type": "string"}]}}
    _write_dp(tmp_path, res, pd.DataFrame({"cluster": [0, 1, 2], "label": ["a", "b", "c"]}))
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "run",
         "--datapackage", str(tmp_path / "datapackage.json"), "--resource", "obs",
         "--report-dir", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "out" / "qa_report.json").exists()


def test_cli_datapackage_bounds_violation_exits_1(tmp_path):
    res = {"name": "obs", "path": "obs.parquet",
           "schema": {"fields": [{"name": "p", "type": "number", "constraints": {"minimum": 0}}]}}
    _write_dp(tmp_path, res, pd.DataFrame({"p": [-1.0, 1.0]}))
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "run",
         "--datapackage", str(tmp_path / "datapackage.json"), "--resource", "obs",
         "--report-dir", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 1


def test_cli_datapackage_requires_resource(tmp_path):
    res = {"name": "obs", "path": "obs.parquet", "schema": {"fields": [{"name": "id"}]}}
    _write_dp(tmp_path, res, pd.DataFrame({"id": [1]}))
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "run",
         "--datapackage", str(tmp_path / "datapackage.json"),
         "--report-dir", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "resource" in (result.stderr + result.stdout).lower()


def test_cli_table_and_datapackage_mutually_exclusive(tmp_path):
    res = {"name": "obs", "path": "obs.parquet", "schema": {"fields": [{"name": "id"}]}}
    _write_dp(tmp_path, res, pd.DataFrame({"id": [1]}))
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "run",
         "--datapackage", str(tmp_path / "datapackage.json"), "--resource", "obs",
         "--table", str(tmp_path / "obs.parquet"),
         "--report-dir", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_cli_run.py -v -k datapackage`
Expected: FAIL — `run` has no `--datapackage`/`--resource` options (click errors / wrong exit code).

- [ ] **Step 3: Add the datapackage mode to the CLI**

Replace the contents of `science/qa/src/science_qa/cli.py` with:

```python
# science/qa/src/science_qa/cli.py
from __future__ import annotations

from pathlib import Path

import click

from science_qa.aspects.tabular import CategoricalSpecError
from science_qa.compile import CompileError
from science_qa.config import QAConfigError
from science_qa.extensions import ProjectLocalError
from science_qa.program import ProgramError
from science_qa.runner import RunnerError, run_qa, run_qa_datapackage
from science_qa.selectors import SelectorError


@click.group()
def cli() -> None:
    """science-qa command-line interface."""


@cli.command("run")
@click.option("--config", "config_path", type=click.Path(path_type=Path, exists=True, dir_okay=False), default=None)
@click.option("--table", "table_path", type=click.Path(path_type=Path, exists=True, dir_okay=False), default=None)
@click.option("--datapackage", "datapackage_path", type=click.Path(path_type=Path, exists=True, dir_okay=False), default=None)
@click.option("--resource", "resource_name", type=str, default=None)
@click.option("--report-dir", "report_dir", type=click.Path(path_type=Path), default=Path("."), show_default=True)
@click.option("--no-strict", is_flag=True, default=False,
              help="Suppress the build-fatal exit code (local inspection only; never wire into a default target).")
def run_command(config_path: Path | None, table_path: Path | None, datapackage_path: Path | None,
                resource_name: str | None, report_dir: Path, no_strict: bool) -> None:
    """Run a QA program over a built table; write qa_report.{md,json} + reconcile dispositions.

    Two input modes:
      - datapackage: --datapackage P --resource R [--config qa.yaml]  (compiles the resource
        schema; defaults to the generic 'tabular' program; optional qa.yaml supplies run-knobs)
      - legacy:      --config qa.yaml --table T

    Exit codes: 0 = ok (or structural suppressed by --no-strict); 1 = structural flag fired
    (build-fatal); 2 = bad input (config/table/program/selector/compile error).
    """
    datapackage_mode = datapackage_path is not None or resource_name is not None
    try:
        if datapackage_mode:
            if datapackage_path is None or resource_name is None:
                raise click.UsageError("--datapackage and --resource must be supplied together")
            if table_path is not None:
                raise click.UsageError("--table cannot be combined with --datapackage/--resource")
            result = run_qa_datapackage(datapackage_path, resource_name, report_dir, runknobs_path=config_path)
        else:
            if config_path is None or table_path is None:
                raise click.UsageError("legacy mode requires both --config and --table")
            result = run_qa(config_path, table_path, report_dir)
    except (QAConfigError, ProgramError, SelectorError, RunnerError, CategoricalSpecError,
            ProjectLocalError, CompileError, ValueError) as exc:
        raise click.UsageError(str(exc)) from exc
    click.echo(f"{len(result.flags)} flag(s); structural_failed={result.structural_failed}; "
               f"coverage_denominator={result.coverage.executable_denominator()}")
    if result.structural_failed and not no_strict:
        raise SystemExit(1)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_cli_run.py -v`
Expected: PASS — existing legacy-mode tests + 4 new datapackage tests.

- [ ] **Step 5: Run the full `science_qa` suite (no regressions)**

Run: `PYTHONPATH=src $PY -m pytest tests -q`
Expected: PASS — the baseline 77 plus all new tests.

- [ ] **Step 6: Commit**

```bash
git add science/qa/src/science_qa/cli.py science/qa/tests/test_cli_run.py
git commit -m "feat(qa-compiler): science_qa run --datapackage/--resource mode"
```

---

## Final verification (after all tasks)

- [ ] Run the whole `science_qa` suite:

```bash
cd <worktree>/science/qa
PYTHONPATH=src ~/d/science/science/.venv/bin/python -m pytest tests -q
```
Expected: green; baseline 77 + the new tests (Tasks 1–9).

- [ ] Sanity-check the one-way dependency is intact (the QA distribution must not import `science_tool`):

```bash
cd <worktree>/science/qa
grep -rn "science_tool" src/ && echo "LEAK" || echo "clean (no science_tool import)"
```
Expected: `clean`.

---

## Self-review (filled in by plan author)

**1. Spec coverage** (design §→task):
- §1 data flow (compile → merge → runner) → Tasks 5–8. ✓
- §2 `tabular` program (general+tabular+numeric-column, no gx/scrna) → Task 4 (+ exclusion test). ✓
- §3 mapping rows: required/unique/type/`any`-skip/bounds/enum/missingValues-normalize/primaryKey/uniqueKeys → Task 5; foreignKeys single-col + composite-reject → Task 6; table `qa.exclusive_flags` → Task 5. ✓
- §4 `bounds` check (structural, temporal, per-bound-key `side`, uncoercible→ValueError) → Task 2. ✓
- §5 input/merge model (dual input, precedence, program-optional loader, defaults to tabular) → Tasks 1 (loader), 7 (merge), 8 (datapackage entry), 9 (CLI + mode validation). ✓
- §6 composite key, type coarse, FK resolution, low_variance/zero_fraction blanket → Tasks 3, 4 (program blanket selector checks), 5/6. ✓
- §7 severity (bounds structural; exclusive_flags stays structural; distribution via existing checks) → Tasks 2, 4. ✓
- §8 errors (CompileError descriptor-only — incl. **malformed bound value** in Task 5; ValueError runtime coercion in Task 2; empty-schema minimal) → Tasks 2, 5, 6, 8. ✓
- §10 testing strategy → test files per task; dogfood regression → Task 9. ✓
- §11 one-way dep → final verification grep. ✓

**2. Placeholder scan:** none — every code step shows complete code. The Task 5 `_compile_foreign_keys` stub is an explicit, named two-step build (stub in T5, implemented in T6), not a TODO.

**3. Type consistency:** `schema_to_config(resource, package_dir, package)` and `merge_configs(contract, runknobs)` signatures stable across Tasks 5/6/7/8; `run_qa_datapackage(datapackage_path, resource_name, report_dir, runknobs_path=None)` stable across Tasks 8/9; `bounds(ctx, params)` reads `params["bounds"]` consistently (Task 2 defn, Task 4 expand, Task 8 end-to-end); `CompileError` defined Task 5, imported in Tasks 6/8/9; new `QAConfig.bounds`/`unique_keys` fields (Task 1) consumed in Tasks 4/5/7; `_expand_unique_key` reads both `unique_key` (scalar) and `unique_keys` (Task 4, dedup'd), populated by the compiler (Task 5). Flag ids: `numeric-column/bounds/<col>/<bound-key>` — e.g. `/minimum`, `/exclusiveMinimum` (Task 2) — asserted identically in Task 8 (`/minimum`); each bound key stays a distinct disposition.
