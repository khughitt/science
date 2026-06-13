# QA Check-Library (composable aspects & programs) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the shipped `science-qa` runtime into a composable check-library — substrate-typed `Context`, standalone aspects, a declared `Program`, and a breadth-coverage readout — proving it end-to-end on a tidy-table scRNA program.

**Architecture:** A `Check` is `(context, params) -> list[Flag]` over a substrate-typed `Context` (`TableContext` first). Aspects are flat sets of `CheckSpec`s; a `Program` is an ordered composition of aspects bound to a substrate. The runner resolves the program → expands *parameterized families* from config and instantiates *required checks* → resolves columns via a standalone selectors unit → validates context compatibility → runs each invocation → records a coverage entry (`ran`/`empty`/`blocked`/`not-applicable`). Re-homing B1's generic checks + the flat `scrna` pack into aspects is behavior-preserving for the legacy checks (asserted against an explicit flag-id map); new baseline checks are tested separately.

**Tech Stack:** Python 3.11, pandas + pyarrow + pyyaml, click, pytest (TDD red→green), hatchling + uv, ruff (line-length 120), pyright basic.

**Spec:** `docs/plans/2026-06-13-qa-check-library-design.md`. **Builds on:** the shipped B1/B3 runtime under `science/qa/src/science_qa/` and `science/src/science_tool/qa_audit/`.

**Conventions for every task:**
- `science-qa` package root is `science/qa/`; run its tests from there: `cd science/qa && python -m pytest <path> -v`.
- After implementation passes, run `cd science/qa && ruff check src tests --fix` (and for Phase F, `cd science && ruff check src tests --fix`) before committing.
- Commit messages: `feat(science-qa): …` / `refactor(science-qa): …` / `test(science-qa): …`; **no `Co-Authored-By` trailer**.
- Work on a feature branch off `main` (created in Task 0). Re-verify the branch before every commit — this repo is Dropbox-synced and `HEAD` can drift.

---

## File structure

New, under `science/qa/src/science_qa/`:

| File | Responsibility |
|---|---|
| `context.py` | `Context` marker base + `TableContext(table, columns)` |
| `selectors.py` | `resolve_columns(spec, table, column_sets) -> list[str]` (dtype / names / regex / named_set) |
| `aspects/__init__.py` | `CheckSpec`, `Invocation`, check-kind constants, aspect registry |
| `aspects/general.py` | `non_empty` (structural), `missing_fraction` |
| `aspects/tabular.py` | `unique_key`, `required_complete`, `categoricals`, `exclusive_flags`, `type_conformance` (families) |
| `aspects/numeric_column.py` | `zero_fraction`, `low_variance` (required, selector-driven); `polarity`, `ranges`, `missing_sentinels` (families) |
| `aspects/gene_expression_qc.py` | `required_column`, `library_size_positive`, `degenerate_cell` (required) |
| `aspects/scrna_qc.py` | `gates` (mito/gene-count/total-count thresholds) + `doublet_ceiling`; threshold flags carry failing counts |
| `program.py` | `Program`, registry, `scrna-qc-table` program, `resolve_program` |
| `coverage.py` | `CoverageEntry`, `Coverage`, status constants, executable-denominator |
| `extensions.py` | `load_project_local(refs, reserved_check_ids=...)` — resolve `module:attr` → namespaced, non-colliding `CheckSpec`s |

Modified:

| File | Change |
|---|---|
| `config.py` | add `program`, `column_sets`, `aspect_params`, `project_local`, `polarity`, `expected_types`; **remove** `packs`/`pack_params` |
| `runner.py` | rewrite orchestration: program resolve → static substrate check → family expansion → per-invocation column-resolve/context/validate/run → coverage |
| `report.py` | add a `coverage` block to `qa_report.json` + a Coverage section in `qa_report.md` |
| `cli.py` | catch the new exception types; same options |
| `science/src/science_tool/qa_audit/` | add a breadth column reading the `coverage` block |

Deleted (clean replacement, no compat layer): `checks.py`, `packs/__init__.py`, `packs/scrna.py`, and their obsolete tests (`test_checks_structural.py`, `test_checks_distribution.py`, `test_pack_scrna.py`).

Docs: `docs/conventions/pipeline-qa-checkpoints.md`, `docs/process/pipeline-audit-and-refactor.md`, `aspects/computational-analysis/computational-analysis.md`, `docs/plans/2026-06-10-data-driven-discovery-improvements.md`.

---

## Phase A — Core scaffolding

### Task 0: Feature branch

- [ ] **Step 1: Create and switch to the branch**

```bash
cd ~/d/science
git checkout main && git pull --ff-only 2>/dev/null; git checkout -b feat/qa-check-library
git branch --show-current
```
Expected: `feat/qa-check-library`

---

### Task 1: `context.py` — substrate-typed context

**Files:**
- Create: `science/qa/src/science_qa/context.py`
- Test: `science/qa/tests/test_context.py`

- [ ] **Step 1: Write the failing test**

```python
# science/qa/tests/test_context.py
import pandas as pd
from science_qa.context import Context, TableContext


def test_table_context_holds_table_and_columns():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    ctx = TableContext(table=df, columns=["a"])
    assert isinstance(ctx, Context)
    assert ctx.columns == ["a"]
    assert list(ctx.table.columns) == ["a", "b"]


def test_table_context_allows_empty_column_selection():
    ctx = TableContext(table=pd.DataFrame({"a": [1]}), columns=[])
    assert ctx.columns == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/qa && python -m pytest tests/test_context.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_qa.context'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/qa/src/science_qa/context.py
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


class Context:
    """Marker base for substrate-typed check inputs.

    Subtypes carry whatever a check needs for that substrate. Only TableContext
    exists today; MatrixContext / SparseExpressionContext land with later substrates.
    """


@dataclass(frozen=True)
class TableContext(Context):
    table: pd.DataFrame
    columns: list[str]  # the resolved column selection a check operates over (may be empty)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/qa && python -m pytest tests/test_context.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Lint and commit**

```bash
cd ~/d/science && git branch --show-current   # must be feat/qa-check-library
cd science/qa && ruff check src tests --fix
cd ~/d/science
git add science/qa/src/science_qa/context.py science/qa/tests/test_context.py
git commit -m "feat(science-qa): substrate-typed Context + TableContext"
```

---

### Task 2: `selectors.py` — standalone column resolution

**Files:**
- Create: `science/qa/src/science_qa/selectors.py`
- Test: `science/qa/tests/test_selectors.py`

- [ ] **Step 1: Write the failing test**

```python
# science/qa/tests/test_selectors.py
import pandas as pd
import pytest
from science_qa.selectors import SelectorError, resolve_columns

DF = pd.DataFrame({"a": [1, 2], "b": [3.0, 4.0], "label": ["x", "y"]})


def test_dtype_numeric_selects_numeric_columns():
    assert resolve_columns({"dtype": "numeric"}, DF, column_sets={}) == ["a", "b"]


def test_dtype_all_selects_every_column():
    assert resolve_columns({"dtype": "all"}, DF, column_sets={}) == ["a", "b", "label"]


def test_explicit_names_list_preserves_order_and_validates():
    assert resolve_columns(["b", "a"], DF, column_sets={}) == ["b", "a"]
    with pytest.raises(SelectorError, match="missing"):
        resolve_columns(["a", "nope"], DF, column_sets={})


def test_regex_matches_column_names():
    assert resolve_columns({"regex": "^a$|label"}, DF, column_sets={}) == ["a", "label"]


def test_named_set_resolves_through_config_column_sets():
    cs = {"numeric": {"dtype": "numeric"}}
    assert resolve_columns({"named_set": "numeric"}, DF, column_sets=cs) == ["a", "b"]
    with pytest.raises(SelectorError, match="undeclared"):
        resolve_columns({"named_set": "ghost"}, DF, column_sets=cs)


def test_empty_resolution_returns_empty_list_not_error():
    assert resolve_columns({"regex": "zzz"}, DF, column_sets={}) == []


def test_unknown_selector_kind_errors():
    with pytest.raises(SelectorError, match="unknown selector"):
        resolve_columns({"bogus": 1}, DF, column_sets={})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/qa && python -m pytest tests/test_selectors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_qa.selectors'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/qa/src/science_qa/selectors.py
from __future__ import annotations

import re

import pandas as pd


class SelectorError(Exception):
    """Raised on an unknown selector kind, an undeclared named-set, or absent explicit columns."""


def resolve_columns(spec, table: pd.DataFrame, *, column_sets: dict) -> list[str]:
    """Resolve a selector spec to an ordered list of existing column names (may be empty).

    Selector forms:
      - list[str]            -> explicit names (must all exist)
      - {"dtype": "numeric"} -> numeric-dtype columns
      - {"dtype": "all"}     -> every column
      - {"regex": "..."}     -> columns whose name matches
      - {"named_set": name}  -> resolve the spec stored under column_sets[name]
    """
    if isinstance(spec, list):
        missing = [c for c in spec if c not in table.columns]
        if missing:
            raise SelectorError(f"explicit column-set names missing from table: {missing}")
        return list(spec)
    if not isinstance(spec, dict) or len(spec) != 1:
        raise SelectorError(f"unknown selector spec: {spec!r}")
    (kind, arg), = spec.items()
    if kind == "named_set":
        if arg not in column_sets:
            raise SelectorError(f"named_set references undeclared column-set {arg!r}")
        return resolve_columns(column_sets[arg], table, column_sets=column_sets)
    if kind == "dtype":
        if arg == "all":
            return list(table.columns)
        if arg == "numeric":
            return [c for c in table.columns if pd.api.types.is_numeric_dtype(table[c])]
        raise SelectorError(f"unknown dtype selector {arg!r}")
    if kind == "regex":
        pattern = re.compile(arg)
        return [c for c in table.columns if pattern.search(c)]
    raise SelectorError(f"unknown selector kind {kind!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/qa && python -m pytest tests/test_selectors.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Lint and commit**

```bash
cd ~/d/science && git branch --show-current
cd science/qa && ruff check src tests --fix
cd ~/d/science
git add science/qa/src/science_qa/selectors.py science/qa/tests/test_selectors.py
git commit -m "feat(science-qa): standalone column-resolution selectors unit"
```

---

### Task 3: `aspects/__init__.py` — CheckSpec, Invocation, kinds

**Files:**
- Create: `science/qa/src/science_qa/aspects/__init__.py`
- Test: `science/qa/tests/test_aspect_registry.py`

> Note: the existing `science_qa/packs/` package still exists at this point; it is removed in Task 14. This new `aspects/` package is independent.

- [ ] **Step 1: Write the failing test**

```python
# science/qa/tests/test_aspect_registry.py
from science_qa.aspects import CHECK_FAMILY, CHECK_REQUIRED, CheckSpec, Invocation
from science_qa.context import TableContext


def test_required_checkspec_defaults():
    spec = CheckSpec(aspect="general", name="non_empty", kind=CHECK_REQUIRED,
                     accepts=TableContext, fn=lambda ctx, params: [])
    assert spec.check_id == "general/non_empty"
    assert spec.expand is None
    assert spec.requires == ()
    assert spec.selector is None


def test_family_checkspec_carries_expand_callable():
    spec = CheckSpec(aspect="numeric-column", name="ranges", kind=CHECK_FAMILY,
                     accepts=TableContext, fn=lambda ctx, params: [],
                     expand=lambda config: [Invocation(params={"x": 1}, requires=("a",), columns=["a"])])
    invs = spec.expand(object())
    assert invs[0].columns == ["a"]
    assert invs[0].requires == ("a",)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/qa && python -m pytest tests/test_aspect_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_qa.aspects'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/qa/src/science_qa/aspects/__init__.py
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from science_qa.context import Context
from science_qa.flags import Flag

CHECK_REQUIRED = "required"
CHECK_FAMILY = "family"

CheckFn = Callable[[Context, dict], list[Flag]]


@dataclass(frozen=True)
class Invocation:
    """One concrete instantiation of a check after config resolution."""
    params: dict = field(default_factory=dict)
    requires: tuple[str, ...] = ()        # input columns that must exist
    columns: list[str] | None = None      # explicit column selection; None -> use CheckSpec.selector
    optional: bool = False                # True -> absent required input is not-applicable, not an error


@dataclass(frozen=True)
class CheckSpec:
    aspect: str
    name: str
    kind: str                              # CHECK_REQUIRED | CHECK_FAMILY
    accepts: type                          # the Context subtype this check consumes
    fn: CheckFn
    selector: object | None = None         # selector spec for selector-driven required checks
    requires: tuple[str, ...] = ()         # required-check input columns (blocked if absent)
    expand: Callable[[object], list[Invocation]] | None = None  # families only

    @property
    def check_id(self) -> str:
        return f"{self.aspect}/{self.name}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/qa && python -m pytest tests/test_aspect_registry.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Lint and commit**

```bash
cd ~/d/science && git branch --show-current
cd science/qa && ruff check src tests --fix
cd ~/d/science
git add science/qa/src/science_qa/aspects/__init__.py science/qa/tests/test_aspect_registry.py
git commit -m "feat(science-qa): CheckSpec/Invocation aspect-registry types"
```

---

## Phase B — Aspect modules (re-homing)

> All aspect checks emit `Flag` with `source=<aspect-name>`. Flag construction matches B1's positional shape: `Flag(source, check, subject, side, severity, value, threshold, message)`.

### Task 4: `aspects/general.py`

**Files:**
- Create: `science/qa/src/science_qa/aspects/general.py`
- Test: `science/qa/tests/test_aspect_general.py`

- [ ] **Step 1: Write the failing test**

```python
# science/qa/tests/test_aspect_general.py
import pandas as pd
from science_qa.aspects.general import missing_fraction, non_empty
from science_qa.context import TableContext


def _ctx(df):
    return TableContext(table=df, columns=list(df.columns))


def test_non_empty_flags_structural_on_zero_rows():
    flags = non_empty(_ctx(pd.DataFrame({"a": []})), {})
    assert len(flags) == 1
    assert flags[0].severity == "structural"
    assert flags[0].source == "general"
    assert flags[0].check == "non_empty"


def test_non_empty_clears_on_rows_present():
    assert non_empty(_ctx(pd.DataFrame({"a": [1]})), {}) == []


def test_missing_fraction_flags_distribution_only_when_threshold_exceeded():
    df = pd.DataFrame({"a": [1, None, None, None]})  # 75% missing
    assert missing_fraction(_ctx(df), {}) == []                        # no threshold -> no flag
    assert missing_fraction(_ctx(df), {"max_missing_fraction": 0.5})   # exceeded -> flag
    flags = missing_fraction(_ctx(df), {"max_missing_fraction": 0.5})
    assert flags[0].severity == "distribution"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/qa && python -m pytest tests/test_aspect_general.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_qa.aspects.general'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/qa/src/science_qa/aspects/general.py
from __future__ import annotations

from science_qa.context import TableContext
from science_qa.flags import SEVERITY_DISTRIBUTION, SEVERITY_STRUCTURAL, Flag


def non_empty(ctx: TableContext, params: dict) -> list[Flag]:
    if len(ctx.table) == 0:
        return [Flag("general", "non_empty", "table", None, SEVERITY_STRUCTURAL,
                     "0", ">0", "analysis substrate has zero rows")]
    return []


def missing_fraction(ctx: TableContext, params: dict) -> list[Flag]:
    threshold = params.get("max_missing_fraction")
    if threshold is None:
        return []
    total = ctx.table.size
    if total == 0:
        return []
    frac = float(ctx.table.isna().sum().sum()) / total
    if frac > threshold:
        return [Flag("general", "missing_fraction", "table", None, SEVERITY_DISTRIBUTION,
                     f"{frac:.4f}", str(threshold), f"overall missing fraction {frac:.4f} exceeds {threshold}")]
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/qa && python -m pytest tests/test_aspect_general.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Lint and commit**

```bash
cd ~/d/science && git branch --show-current
cd science/qa && ruff check src tests --fix
cd ~/d/science
git add science/qa/src/science_qa/aspects/general.py science/qa/tests/test_aspect_general.py
git commit -m "feat(science-qa): general aspect (non_empty structural, missing_fraction)"
```

---

### Task 5: `aspects/tabular.py` — re-home B1 structural family checks

**Files:**
- Create: `science/qa/src/science_qa/aspects/tabular.py`
- Test: `science/qa/tests/test_aspect_tabular.py`

> Re-homes `run_structural_checks` from `checks.py`: `unique_key`, `required_complete`, `categoricals`, `exclusive_flags`, plus a new `type_conformance`. Each `fn` operates on a single resolved column/pair via `ctx.columns` + `params`. The `_allowed_values` helper moves here unchanged.

- [ ] **Step 1: Write the failing test**

```python
# science/qa/tests/test_aspect_tabular.py
import pandas as pd
from science_qa.aspects.tabular import (
    categoricals, exclusive_flags, required_complete, type_conformance, unique_key,
)
from science_qa.context import TableContext


def _ctx(df, cols):
    return TableContext(table=df, columns=cols)


def test_unique_key_flags_duplicate_keys_structural():
    df = pd.DataFrame({"id": [1, 1, 2]})
    flags = unique_key(_ctx(df, ["id"]), {})
    assert flags[0].check == "unique_key" and flags[0].severity == "structural"
    assert flags[0].source == "tabular"


def test_required_complete_flags_missing_values():
    df = pd.DataFrame({"x": [1, None]})
    flags = required_complete(_ctx(df, ["x"]), {})
    assert flags[0].check == "required_complete" and flags[0].value == "1"


def test_categoricals_flags_illegal_values_via_allowed():
    df = pd.DataFrame({"stage": [1, 2, 9]})
    flags = categoricals(_ctx(df, ["stage"]), {"spec": {"allowed": [1, 2, 3]}, "base_dir": "."})
    assert flags[0].check == "allowed"


def test_exclusive_flags_flags_cooccurrence():
    df = pd.DataFrame({"a": [1, 0], "b": [1, 0]})
    flags = exclusive_flags(_ctx(df, ["a", "b"]), {})
    assert flags[0].check == "exclusive_flags" and flags[0].subject == "a+b"


def test_type_conformance_flags_wrong_dtype():
    df = pd.DataFrame({"n": ["x", "y"]})
    flags = type_conformance(_ctx(df, ["n"]), {"expected": "numeric"})
    assert flags[0].check == "type_conformance" and flags[0].severity == "structural"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/qa && python -m pytest tests/test_aspect_tabular.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_qa.aspects.tabular'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/qa/src/science_qa/aspects/tabular.py
from __future__ import annotations

from pathlib import Path

import pandas as pd

from science_qa.context import TableContext
from science_qa.flags import SEVERITY_STRUCTURAL, Flag


class CategoricalSpecError(Exception):
    """Raised when a categorical spec has neither 'allowed' nor 'allowed_from'."""


def _allowed_values(spec: dict, base_dir: Path) -> set:
    if "allowed" in spec:
        return set(spec["allowed"])
    if "allowed_from" in spec:
        ref = str(spec["allowed_from"])
        file_part, _, column = ref.partition("#")
        path = (base_dir / file_part) if not Path(file_part).is_absolute() else Path(file_part)
        registry = pd.read_csv(path)
        return set(registry[column].dropna().tolist())
    raise CategoricalSpecError(f"categorical spec must have 'allowed' or 'allowed_from': {spec!r}")


def unique_key(ctx: TableContext, params: dict) -> list[Flag]:
    col = ctx.columns[0]
    dupes = int(ctx.table[col].duplicated().sum())
    if dupes:
        return [Flag("tabular", "unique_key", col, None, SEVERITY_STRUCTURAL,
                     str(dupes), "0", f"{dupes} duplicate key value(s)")]
    return []


def required_complete(ctx: TableContext, params: dict) -> list[Flag]:
    col = ctx.columns[0]
    missing = int(ctx.table[col].isna().sum())
    if missing:
        return [Flag("tabular", "required_complete", col, None, SEVERITY_STRUCTURAL,
                     str(missing), "0", f"{missing} missing value(s)")]
    return []


def categoricals(ctx: TableContext, params: dict) -> list[Flag]:
    col = ctx.columns[0]
    allowed = _allowed_values(params["spec"], Path(params.get("base_dir", ".")))
    illegal = set(ctx.table[col].dropna().unique()) - allowed
    if illegal:
        return [Flag("tabular", "allowed", col, None, SEVERITY_STRUCTURAL,
                     ",".join(map(str, sorted(map(str, illegal)))), "in allowed set",
                     f"{len(illegal)} value(s) outside allowed set")]
    return []


def exclusive_flags(ctx: TableContext, params: dict) -> list[Flag]:
    a, b = ctx.columns[0], ctx.columns[1]
    cooccur = int((ctx.table[a].astype(bool) & ctx.table[b].astype(bool)).sum())
    if cooccur:
        return [Flag("tabular", "exclusive_flags", f"{a}+{b}", None, SEVERITY_STRUCTURAL,
                     str(cooccur), "0", f"{cooccur} row(s) where {a} and {b} co-occur")]
    return []


def type_conformance(ctx: TableContext, params: dict) -> list[Flag]:
    col = ctx.columns[0]
    expected = params["expected"]
    is_numeric = pd.api.types.is_numeric_dtype(ctx.table[col])
    ok = is_numeric if expected == "numeric" else (not is_numeric)
    if not ok:
        return [Flag("tabular", "type_conformance", col, None, SEVERITY_STRUCTURAL,
                     str(ctx.table[col].dtype), expected, f"{col} dtype not {expected}")]
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/qa && python -m pytest tests/test_aspect_tabular.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Lint and commit**

```bash
cd ~/d/science && git branch --show-current
cd science/qa && ruff check src tests --fix
cd ~/d/science
git add science/qa/src/science_qa/aspects/tabular.py science/qa/tests/test_aspect_tabular.py
git commit -m "feat(science-qa): tabular aspect (re-homed structural family checks + type_conformance)"
```

---

### Task 6: `aspects/numeric_column.py`

**Files:**
- Create: `science/qa/src/science_qa/aspects/numeric_column.py`
- Test: `science/qa/tests/test_aspect_numeric_column.py`

> `zero_fraction` + `low_variance` are required selector-driven checks over the resolved numeric column-set (one `Flag` per offending column). `polarity` (re-homes scrna `non_negative`), `ranges` (re-homes `run_distribution_checks`), and `missing_sentinels` (re-homes the sentinel survivor guard) are families.

- [ ] **Step 1: Write the failing test**

```python
# science/qa/tests/test_aspect_numeric_column.py
import pandas as pd
from science_qa.aspects.numeric_column import (
    low_variance, missing_sentinels, polarity, ranges, zero_fraction,
)
from science_qa.context import TableContext


def _ctx(df, cols):
    return TableContext(table=df, columns=cols)


def test_zero_fraction_flags_all_zero_column_distribution():
    df = pd.DataFrame({"a": [0, 0, 0], "b": [1, 2, 3]})
    flags = zero_fraction(_ctx(df, ["a", "b"]), {})
    assert [f.subject for f in flags] == ["a"]
    assert flags[0].severity == "distribution" and flags[0].source == "numeric-column"


def test_low_variance_flags_constant_column():
    df = pd.DataFrame({"a": [5, 5, 5], "b": [1, 2, 3]})
    flags = low_variance(_ctx(df, ["a", "b"]), {})
    assert [f.subject for f in flags] == ["a"]
    assert flags[0].check == "low_variance"


def test_polarity_flags_negative_values_structural():
    df = pd.DataFrame({"total_counts": [-1, 2]})
    flags = polarity(_ctx(df, ["total_counts"]), {})
    assert flags[0].check == "polarity" and flags[0].severity == "structural"


def test_ranges_flags_min_and_max_distribution():
    df = pd.DataFrame({"g": [0, 50, 9000]})
    flags = ranges(_ctx(df, ["g"]), {"bounds": {"min": 1, "max": 8000}})
    sides = sorted(f.side for f in flags)
    assert sides == ["max", "min"] and all(f.severity == "distribution" for f in flags)


def test_missing_sentinels_flags_survivors_structural():
    df = pd.DataFrame({"x": [-9, 1, 2], "y": [1.0, 2.0, 3.0]})
    flags = missing_sentinels(_ctx(df, ["x", "y"]), {"sentinels": [-9]})
    assert [f.subject for f in flags] == ["x"] and flags[0].severity == "structural"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/qa && python -m pytest tests/test_aspect_numeric_column.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# science/qa/src/science_qa/aspects/numeric_column.py
from __future__ import annotations

from typing import cast

import pandas as pd

from science_qa.context import TableContext
from science_qa.flags import SEVERITY_DISTRIBUTION, SEVERITY_STRUCTURAL, Flag

ASPECT = "numeric-column"


def zero_fraction(ctx: TableContext, params: dict) -> list[Flag]:
    flags: list[Flag] = []
    for col in ctx.columns:
        series = ctx.table[col]
        if len(series) and int((series == 0).sum()) == len(series):
            flags.append(Flag(ASPECT, "zero_fraction", col, None, SEVERITY_DISTRIBUTION,
                              "1.0", "<1.0", f"{col} is entirely zero"))
    return flags


def low_variance(ctx: TableContext, params: dict) -> list[Flag]:
    flags: list[Flag] = []
    for col in ctx.columns:
        series = cast("pd.Series", pd.to_numeric(ctx.table[col], errors="coerce")).dropna()
        if len(series) > 1 and float(series.var()) == 0.0:
            flags.append(Flag(ASPECT, "low_variance", col, None, SEVERITY_DISTRIBUTION,
                              "0.0", ">0", f"{col} has zero variance (constant)"))
    return flags


def polarity(ctx: TableContext, params: dict) -> list[Flag]:
    col = ctx.columns[0]
    n = int((ctx.table[col] < 0).sum())
    if n:
        return [Flag(ASPECT, "polarity", col, None, SEVERITY_STRUCTURAL,
                     str(n), "0", f"{n} negative value(s) in {col} (expected non-negative)")]
    return []


def ranges(ctx: TableContext, params: dict) -> list[Flag]:
    col = ctx.columns[0]
    bounds = params["bounds"]
    series = cast("pd.Series", pd.to_numeric(ctx.table[col], errors="coerce")).dropna()
    flags: list[Flag] = []
    if "min" in bounds:
        below = int((series < bounds["min"]).sum())
        if below:
            flags.append(Flag(ASPECT, "range", col, "min", SEVERITY_DISTRIBUTION,
                              str(below), str(bounds["min"]), f"{below} value(s) below min"))
    if "max" in bounds:
        above = int((series > bounds["max"]).sum())
        if above:
            flags.append(Flag(ASPECT, "range", col, "max", SEVERITY_DISTRIBUTION,
                              str(above), str(bounds["max"]), f"{above} value(s) above max"))
    return flags


def missing_sentinels(ctx: TableContext, params: dict) -> list[Flag]:
    sentinels = list(params["sentinels"])
    flags: list[Flag] = []
    for col in ctx.columns:
        if not pd.api.types.is_numeric_dtype(ctx.table[col]):
            continue
        survivors = int(ctx.table[col].isin(sentinels).sum())
        if survivors:
            flags.append(Flag(ASPECT, "missing_sentinel", col, None, SEVERITY_STRUCTURAL,
                              str(survivors), "0", f"{survivors} surviving missing-sentinel value(s)"))
    return flags
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/qa && python -m pytest tests/test_aspect_numeric_column.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Lint and commit**

```bash
cd ~/d/science && git branch --show-current
cd science/qa && ruff check src tests --fix
cd ~/d/science
git add science/qa/src/science_qa/aspects/numeric_column.py science/qa/tests/test_aspect_numeric_column.py
git commit -m "feat(science-qa): numeric-column aspect (zero/variance + re-homed polarity/ranges/sentinels)"
```

---

### Task 7: `aspects/gene_expression_qc.py`

**Files:**
- Create: `science/qa/src/science_qa/aspects/gene_expression_qc.py`
- Test: `science/qa/tests/test_aspect_gene_expression_qc.py`

> `required_column` re-homes scrna's required-column structural flags (subject = each missing required QC column). `degenerate_cell` re-homes scrna `all_zero_cell`. `library_size_positive` is a new baseline check. All structural (post-QC substrate).

- [ ] **Step 1: Write the failing test**

```python
# science/qa/tests/test_aspect_gene_expression_qc.py
import pandas as pd
from science_qa.aspects.gene_expression_qc import (
    REQUIRED_COLUMNS, degenerate_cell, library_size_positive, required_column,
)
from science_qa.context import TableContext


def _ctx(df):
    return TableContext(table=df, columns=list(df.columns))


def test_required_column_flags_each_absent_required_column():
    df = pd.DataFrame({"total_counts": [1]})  # missing n_genes_by_counts, pct_counts_mt
    flags = required_column(_ctx(df), {})
    subjects = sorted(f.subject for f in flags)
    assert subjects == ["n_genes_by_counts", "pct_counts_mt"]
    assert all(f.severity == "structural" and f.source == "gene-expression-qc-table" for f in flags)
    assert set(REQUIRED_COLUMNS) == {"total_counts", "n_genes_by_counts", "pct_counts_mt"}


def test_library_size_positive_flags_nonpositive_total_counts():
    df = pd.DataFrame({"total_counts": [0, 5]})
    flags = library_size_positive(_ctx(df), {})
    assert flags[0].check == "library_size_positive" and flags[0].severity == "structural"


def test_degenerate_cell_flags_all_zero_cells():
    df = pd.DataFrame({"total_counts": [0, 5], "n_genes_by_counts": [0, 3]})
    flags = degenerate_cell(_ctx(df), {})
    assert flags[0].check == "degenerate_cell" and flags[0].value == "1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/qa && python -m pytest tests/test_aspect_gene_expression_qc.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# science/qa/src/science_qa/aspects/gene_expression_qc.py
from __future__ import annotations

from science_qa.context import TableContext
from science_qa.flags import SEVERITY_STRUCTURAL, Flag

ASPECT = "gene-expression-qc-table"
REQUIRED_COLUMNS = ("total_counts", "n_genes_by_counts", "pct_counts_mt")


def required_column(ctx: TableContext, params: dict) -> list[Flag]:
    return [Flag(ASPECT, "required_column", col, None, SEVERITY_STRUCTURAL,
                 "absent", "present", f"required QC column {col!r} missing")
            for col in REQUIRED_COLUMNS if col not in ctx.table.columns]


def library_size_positive(ctx: TableContext, params: dict) -> list[Flag]:
    n = int((ctx.table["total_counts"] <= 0).sum())
    if n:
        return [Flag(ASPECT, "library_size_positive", "total_counts", None, SEVERITY_STRUCTURAL,
                     str(n), "0", f"{n} cell(s) with non-positive library size")]
    return []


def degenerate_cell(ctx: TableContext, params: dict) -> list[Flag]:
    mask = (ctx.table["total_counts"] == 0) & (ctx.table["n_genes_by_counts"] == 0)
    n = int(mask.sum())
    if n:
        return [Flag(ASPECT, "degenerate_cell", "total_counts+n_genes_by_counts", None,
                     SEVERITY_STRUCTURAL, str(n), "0", f"{n} all-zero cell(s)")]
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/qa && python -m pytest tests/test_aspect_gene_expression_qc.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Lint and commit**

```bash
cd ~/d/science && git branch --show-current
cd science/qa && ruff check src tests --fix
cd ~/d/science
git add science/qa/src/science_qa/aspects/gene_expression_qc.py science/qa/tests/test_aspect_gene_expression_qc.py
git commit -m "feat(science-qa): gene-expression-qc-table aspect (re-homed required_column + degenerate_cell)"
```

---

### Task 8: `aspects/scrna_qc.py`

**Files:**
- Create: `science/qa/src/science_qa/aspects/scrna_qc.py`
- Test: `science/qa/tests/test_aspect_scrna_qc.py`

> Re-homes the scrna pack's distribution gates. Each gate emits `Flag(source="scrna-qc-table", check="threshold", subject=<col>, side=<min|max>)` — matching the parity map. Defaults match B1's `DEFAULTS`. `doublet_ceiling` only runs when `doublet_score` is present (the optional-input case → `not-applicable` is handled by the runner via `requires` on a *separate* optional invocation in Task 9; here the function simply returns `[]` if the column is absent).

- [ ] **Step 1: Write the failing test**

```python
# science/qa/tests/test_aspect_scrna_qc.py
import pandas as pd
from science_qa.aspects.scrna_qc import DEFAULTS, doublet_ceiling, gates
from science_qa.context import TableContext


def _ctx(df):
    return TableContext(table=df, columns=list(df.columns))


def test_gates_flag_mito_gene_and_total_thresholds():
    df = pd.DataFrame({
        "total_counts": [100, 1000],          # 100 < min_counts 500
        "n_genes_by_counts": [50, 500],        # 50 < min_genes 200
        "pct_counts_mt": [30.0, 5.0],          # 30 > max_mito_pct 20
    })
    flags = gates(_ctx(df), DEFAULTS)
    keyed = {(f.subject, f.side) for f in flags}
    assert ("pct_counts_mt", "max") in keyed
    assert ("n_genes_by_counts", "min") in keyed
    assert ("total_counts", "min") in keyed
    assert all(f.source == "scrna-qc-table" and f.check == "threshold" for f in flags)


def test_doublet_ceiling_flags_when_present():
    df = pd.DataFrame({"doublet_score": [0.5, 0.1]})
    flags = doublet_ceiling(_ctx(df), DEFAULTS)
    assert flags[0].subject == "doublet_score" and flags[0].side == "max"


def test_doublet_ceiling_returns_empty_when_column_absent():
    assert doublet_ceiling(_ctx(pd.DataFrame({"x": [1]})), DEFAULTS) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/qa && python -m pytest tests/test_aspect_scrna_qc.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# science/qa/src/science_qa/aspects/scrna_qc.py
from __future__ import annotations

from science_qa.context import TableContext
from science_qa.flags import SEVERITY_DISTRIBUTION, Flag

ASPECT = "scrna-qc-table"
DEFAULTS = {"max_mito_pct": 20, "min_genes": 200, "max_genes": 8000, "min_counts": 500, "max_doublet": 0.3}


def _gate(flags: list[Flag], table, column: str, side: str, mask, threshold) -> None:
    n = int(mask.sum())
    if n:
        flags.append(Flag(ASPECT, "threshold", column, side, SEVERITY_DISTRIBUTION,
                          str(n), str(threshold), f"{n} cell(s) failing {column} {side} gate"))


def gates(ctx: TableContext, params: dict) -> list[Flag]:
    p = {**DEFAULTS, **(params or {})}
    t = ctx.table
    flags: list[Flag] = []
    _gate(flags, t, "pct_counts_mt", "max", t["pct_counts_mt"] > p["max_mito_pct"], p["max_mito_pct"])
    _gate(flags, t, "n_genes_by_counts", "min", t["n_genes_by_counts"] < p["min_genes"], p["min_genes"])
    _gate(flags, t, "n_genes_by_counts", "max", t["n_genes_by_counts"] > p["max_genes"], p["max_genes"])
    _gate(flags, t, "total_counts", "min", t["total_counts"] < p["min_counts"], p["min_counts"])
    return flags


def doublet_ceiling(ctx: TableContext, params: dict) -> list[Flag]:
    if "doublet_score" not in ctx.table.columns:
        return []
    p = {**DEFAULTS, **(params or {})}
    flags: list[Flag] = []
    _gate(flags, ctx.table, "doublet_score", "max",
          ctx.table["doublet_score"] > p["max_doublet"], p["max_doublet"])
    return flags
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/qa && python -m pytest tests/test_aspect_scrna_qc.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Lint and commit**

```bash
cd ~/d/science && git branch --show-current
cd science/qa && ruff check src tests --fix
cd ~/d/science
git add science/qa/src/science_qa/aspects/scrna_qc.py science/qa/tests/test_aspect_scrna_qc.py
git commit -m "feat(science-qa): scrna-qc-table aspect (re-homed distribution gates + doublet ceiling)"
```

---

## Phase C — Program

### Task 9: `program.py` — Program, registry, family expansion

**Files:**
- Create: `science/qa/src/science_qa/program.py`
- Test: `science/qa/tests/test_program.py`

> The program lists `CheckSpec`s in order. Family `expand` callables read a `QAConfig` and return `Invocation`s. The optional `doublet_ceiling` is modelled as a family that expands to **one invocation with `requires=("doublet_score",)`** so the runner records `not-applicable` when the column is absent (rather than the function silently returning `[]`).

- [ ] **Step 1: Write the failing test**

```python
# science/qa/tests/test_program.py
import pytest
from science_qa.config import QAConfig
from science_qa.context import TableContext
from science_qa.program import ProgramError, resolve_program


def test_scrna_program_lists_aspects_in_order():
    prog = resolve_program("scrna-qc-table")
    assert prog.substrate is TableContext
    aspects = [c.aspect for c in prog.checks]
    # general first, scrna gates after gene-expression, project-local last
    assert aspects[0] == "general"
    assert aspects.index("tabular") < aspects.index("numeric-column")
    assert aspects.index("gene-expression-qc-table") < aspects.index("scrna-qc-table")


def test_unknown_program_errors():
    with pytest.raises(ProgramError, match="unknown program"):
        resolve_program("nope")


def test_ranges_family_expands_one_invocation_per_declared_range():
    prog = resolve_program("scrna-qc-table")
    ranges_spec = next(c for c in prog.checks if c.check_id == "numeric-column/range")
    config = QAConfig(program="scrna-qc-table", ranges={"g": {"min": 1, "max": 9}})
    invs = ranges_spec.expand(config)
    assert len(invs) == 1 and invs[0].columns == ["g"] and invs[0].requires == ("g",)


def test_unconfigured_family_expands_to_zero_invocations():
    prog = resolve_program("scrna-qc-table")
    cat_spec = next(c for c in prog.checks if c.check_id == "tabular/categoricals")
    assert cat_spec.expand(QAConfig(program="scrna-qc-table")) == []


def test_doublet_family_expands_with_optional_required_column():
    prog = resolve_program("scrna-qc-table")
    doublet = next(c for c in prog.checks if c.check_id == "scrna-qc-table/doublet_ceiling")
    invs = doublet.expand(QAConfig(program="scrna-qc-table"))
    assert len(invs) == 1 and invs[0].requires == ("doublet_score",) and invs[0].optional is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/qa && python -m pytest tests/test_program.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_qa.program'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/qa/src/science_qa/program.py
from __future__ import annotations

from dataclasses import dataclass

from science_qa.aspects import CHECK_FAMILY, CHECK_REQUIRED, CheckSpec, Invocation
from science_qa.aspects import gene_expression_qc as gx
from science_qa.aspects import general, numeric_column, scrna_qc, tabular
from science_qa.context import TableContext


class ProgramError(Exception):
    """Raised when an unknown program is requested."""


@dataclass(frozen=True)
class Program:
    name: str
    substrate: type
    checks: list[CheckSpec]


# --- family expand callables (program declares WHAT; config supplies items) ---

def _expand_unique_key(config) -> list[Invocation]:
    return [Invocation(columns=[config.unique_key], requires=(config.unique_key,))] if config.unique_key else []


def _expand_required_complete(config) -> list[Invocation]:
    return [Invocation(columns=[c], requires=(c,)) for c in config.required_complete]


def _expand_categoricals(config) -> list[Invocation]:
    return [Invocation(columns=[c], requires=(c,), params={"spec": spec, "base_dir": config.base_dir})
            for c, spec in config.categoricals.items()]


def _expand_exclusive_flags(config) -> list[Invocation]:
    return [Invocation(columns=list(pair), requires=tuple(pair)) for pair in config.exclusive_flags]


def _expand_type_conformance(config) -> list[Invocation]:
    return [Invocation(columns=[c], requires=(c,), params={"expected": exp})
            for c, exp in config.expected_types.items()]


def _expand_polarity(config) -> list[Invocation]:
    return [Invocation(columns=[c], requires=(c,)) for c in config.polarity]


def _expand_ranges(config) -> list[Invocation]:
    return [Invocation(columns=[c], requires=(c,), params={"bounds": b}) for c, b in config.ranges.items()]


def _expand_missing_sentinels(config) -> list[Invocation]:
    if not config.missing_sentinels:
        return []
    return [Invocation(columns=None, params={"sentinels": list(config.missing_sentinels)})]  # selector-driven


def _expand_doublet(config) -> list[Invocation]:
    # one *optional* invocation: doublet_score is legitimately optional -> not-applicable when absent
    params = config.aspect_params.get("scrna-qc-table", {})
    return [Invocation(requires=("doublet_score",), columns=["doublet_score"], optional=True, params=params)]


def _scrna_param(config) -> dict:
    return config.aspect_params.get("scrna-qc-table", {})


_SCRNA_QC_TABLE = Program(
    name="scrna-qc-table",
    substrate=TableContext,
    checks=[
        CheckSpec("general", "non_empty", CHECK_REQUIRED, TableContext, general.non_empty),
        CheckSpec("general", "missing_fraction", CHECK_REQUIRED, TableContext, general.missing_fraction),
        CheckSpec("tabular", "unique_key", CHECK_FAMILY, TableContext, tabular.unique_key, expand=_expand_unique_key),
        CheckSpec("tabular", "required_complete", CHECK_FAMILY, TableContext, tabular.required_complete, expand=_expand_required_complete),
        CheckSpec("tabular", "categoricals", CHECK_FAMILY, TableContext, tabular.categoricals, expand=_expand_categoricals),
        CheckSpec("tabular", "exclusive_flags", CHECK_FAMILY, TableContext, tabular.exclusive_flags, expand=_expand_exclusive_flags),
        CheckSpec("tabular", "type_conformance", CHECK_FAMILY, TableContext, tabular.type_conformance, expand=_expand_type_conformance),
        CheckSpec("numeric-column", "zero_fraction", CHECK_REQUIRED, TableContext, numeric_column.zero_fraction, selector={"dtype": "numeric"}),
        CheckSpec("numeric-column", "low_variance", CHECK_REQUIRED, TableContext, numeric_column.low_variance, selector={"dtype": "numeric"}),
        CheckSpec("numeric-column", "polarity", CHECK_FAMILY, TableContext, numeric_column.polarity, expand=_expand_polarity),
        CheckSpec("numeric-column", "range", CHECK_FAMILY, TableContext, numeric_column.ranges, expand=_expand_ranges),
        CheckSpec("numeric-column", "missing_sentinel", CHECK_FAMILY, TableContext, numeric_column.missing_sentinels, selector={"dtype": "numeric"}, expand=_expand_missing_sentinels),
        CheckSpec("gene-expression-qc-table", "required_column", CHECK_REQUIRED, TableContext, gx.required_column),
        CheckSpec("gene-expression-qc-table", "library_size_positive", CHECK_REQUIRED, TableContext, gx.library_size_positive, requires=("total_counts",)),
        CheckSpec("gene-expression-qc-table", "degenerate_cell", CHECK_REQUIRED, TableContext, gx.degenerate_cell, requires=("total_counts", "n_genes_by_counts")),
        CheckSpec("scrna-qc-table", "gates", CHECK_REQUIRED, TableContext, scrna_qc.gates, requires=("total_counts", "n_genes_by_counts", "pct_counts_mt")),
        CheckSpec("scrna-qc-table", "doublet_ceiling", CHECK_FAMILY, TableContext, scrna_qc.doublet_ceiling, expand=_expand_doublet),
    ],
)

PROGRAMS: dict[str, Program] = {_SCRNA_QC_TABLE.name: _SCRNA_QC_TABLE}


def resolve_program(name: str) -> Program:
    if name not in PROGRAMS:
        raise ProgramError(f"unknown program {name!r}; known: {sorted(PROGRAMS)}")
    return PROGRAMS[name]
```

> The `gates` required check uses `check_id` `scrna-qc-table/gates` but emits flags with `check="threshold"`. The test in Task 9 looks up `scrna-qc-table/doublet_ceiling` and `numeric-column/range` by `check_id`; confirm these `check_id`s exist. The `scrna_qc.gates` `params` come from `aspect_params` — wired in the runner (Task 12).
>
> **Program invariant — required-column ownership (avoids duplicate flags).** Exactly one check *owns* the structural flag for an absent required column: `gene-expression-qc-table/required_column` emits the **parity-mapped** `gene-expression-qc-table/required_column/<col>` flag (the re-homed `scrna/required_column/<col>`) for each absent column in `REQUIRED_COLUMNS`. The dependent checks `gates`/`library_size_positive`/`degenerate_cell` carry `requires` purely so the runner records them **`blocked` (coverage-only, no flag)** instead of `KeyError`-ing on the absent column. **Invariant:** every column in any check's `requires` must be covered by a `required_column`-style owner (true here: all are in `gene-expression-qc-table.REQUIRED_COLUMNS`). This is why the runner's blocked branch emits no flag — the single owner does, so the ledger has no duplicate `flag_id`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/qa && python -m pytest tests/test_program.py -v`
Expected: PASS (5 tests). (Requires `QAConfig` fields `program`, `base_dir`, `expected_types`, `polarity`, `aspect_params` — added in Task 11; if running Task 9 before Task 11, temporarily stub them. Recommended order: do Task 11 before Task 9's Step 4, or accept the test depends on Task 11. **Execute Task 11 before Task 9.**)

> **Execution note:** Task 11 (config fields) is a dependency of Task 9's test. Execute **Task 11 first**, then Task 9. The plan lists them in file-cohesion order; the subagent executing should follow this dependency note.

- [ ] **Step 5: Lint and commit**

```bash
cd ~/d/science && git branch --show-current
cd science/qa && ruff check src tests --fix
cd ~/d/science
git add science/qa/src/science_qa/program.py science/qa/tests/test_program.py
git commit -m "feat(science-qa): scrna-qc-table program + family expansion"
```

---

## Phase D — Coverage

### Task 10: `coverage.py`

**Files:**
- Create: `science/qa/src/science_qa/coverage.py`
- Test: `science/qa/tests/test_coverage.py`

- [ ] **Step 1: Write the failing test**

```python
# science/qa/tests/test_coverage.py
from science_qa.coverage import (
    STATUS_BLOCKED, STATUS_EMPTY, STATUS_NA, STATUS_RAN, Coverage, CoverageEntry,
)


def _cov():
    return Coverage(
        entries=[
            CoverageEntry("a/x", "a", STATUS_RAN, ["c1"], 0),
            CoverageEntry("a/y", "a", STATUS_EMPTY, [], 0),
            CoverageEntry("b/z", "b", STATUS_BLOCKED, [], 1),
            CoverageEntry("b/o", "b", STATUS_NA, [], 0),
        ],
        unconfigured_families=["tabular/categoricals"],
    )


def test_executable_denominator_excludes_not_applicable():
    # ran + empty + blocked = 3 ; not-applicable excluded
    assert _cov().executable_denominator() == 3


def test_narrow_signal_lists_empty_blocked_and_unconfigured():
    signal = _cov().narrow_signal()
    assert "a/y" in signal and "b/z" in signal and "tabular/categoricals" in signal
    assert "a/x" not in signal


def test_to_dict_is_deterministic_and_sorted():
    d = _cov().to_dict()
    assert [e["check_id"] for e in d["entries"]] == ["a/x", "a/y", "b/o", "b/z"]
    assert d["executable_denominator"] == 3
    assert d["ran"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/qa && python -m pytest tests/test_coverage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_qa.coverage'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/qa/src/science_qa/coverage.py
from __future__ import annotations

from dataclasses import dataclass, field

STATUS_RAN = "ran"
STATUS_EMPTY = "empty"
STATUS_BLOCKED = "blocked"
STATUS_NA = "not-applicable"

_IN_DENOMINATOR = {STATUS_RAN, STATUS_EMPTY, STATUS_BLOCKED}


@dataclass
class CoverageEntry:
    check_id: str
    aspect: str
    status: str
    columns: list[str]
    flag_count: int


@dataclass
class Coverage:
    entries: list[CoverageEntry] = field(default_factory=list)
    unconfigured_families: list[str] = field(default_factory=list)

    def executable_denominator(self) -> int:
        return sum(1 for e in self.entries if e.status in _IN_DENOMINATOR)

    def narrow_signal(self) -> list[str]:
        flagged = [e.check_id for e in self.entries if e.status in {STATUS_EMPTY, STATUS_BLOCKED}]
        return sorted(flagged + list(self.unconfigured_families))

    def to_dict(self) -> dict:
        # total-order key: families repeat a check_id, so disambiguate by resolved columns
        ordered = sorted(self.entries, key=lambda e: (e.check_id, tuple(e.columns)))
        counts = {s: sum(1 for e in self.entries if e.status == s)
                  for s in (STATUS_RAN, STATUS_EMPTY, STATUS_BLOCKED, STATUS_NA)}
        return {
            "executable_denominator": self.executable_denominator(),
            **counts,
            "unconfigured_families": sorted(self.unconfigured_families),
            "narrow_signal": self.narrow_signal(),
            "entries": [
                {"check_id": e.check_id, "aspect": e.aspect, "status": e.status,
                 "columns": list(e.columns), "flag_count": e.flag_count}
                for e in ordered
            ],
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/qa && python -m pytest tests/test_coverage.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Lint and commit**

```bash
cd ~/d/science && git branch --show-current
cd science/qa && ruff check src tests --fix
cd ~/d/science
git add science/qa/src/science_qa/coverage.py science/qa/tests/test_coverage.py
git commit -m "feat(science-qa): coverage model (statuses + executable denominator + narrow signal)"
```

---

## Phase E — Integration

> **Execute Task 11 before Task 9's Step 4** (config fields are a test dependency). If using subagent-driven execution, run Tasks in order 0,1,2,3,4,5,6,7,8,10,11,9,12,12b,13,14,15,16.

### Task 11: `config.py` — program selection + parameterization; drop `packs`

**Files:**
- Modify: `science/qa/src/science_qa/config.py`
- Test: `science/qa/tests/test_config.py` (extend; existing tests for `packs` are removed here)

- [ ] **Step 1: Write the failing test**

```python
# science/qa/tests/test_config.py  (append; remove any existing packs/pack_params assertions)
from pathlib import Path

import pytest
from science_qa.config import QAConfig, QAConfigError


def _write(tmp_path, body: str) -> Path:
    p = tmp_path / "qa.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_loads_program_and_parameterization(tmp_path):
    cfg = QAConfig.from_file(_write(tmp_path, """
qa:
  program: scrna-qc-table
  unique_key: cell_id
  ranges: {pct_counts_ribo: {min: 0, max: 60}}
  column_sets: {numeric: {dtype: numeric}}
  aspect_params: {scrna-qc-table: {max_mito_pct: 20}}
  polarity: [total_counts]
  expected_types: {cell_id: numeric}
  project_local: ["pkg.mod:check"]
"""))
    assert cfg.program == "scrna-qc-table"
    assert cfg.column_sets == {"numeric": {"dtype": "numeric"}}
    assert cfg.aspect_params["scrna-qc-table"]["max_mito_pct"] == 20
    assert cfg.polarity == ["total_counts"]
    assert cfg.expected_types == {"cell_id": "numeric"}
    assert cfg.project_local == ["pkg.mod:check"]
    assert cfg.base_dir == tmp_path


def test_missing_program_key_errors(tmp_path):
    with pytest.raises(QAConfigError, match="program"):
        QAConfig.from_file(_write(tmp_path, "qa:\n  unique_key: id\n"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/qa && python -m pytest tests/test_config.py -v`
Expected: FAIL — `QAConfig` has no `program` / `base_dir` / `expected_types` / `polarity`.

- [ ] **Step 3: Write minimal implementation**

```python
# science/qa/src/science_qa/config.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


class QAConfigError(Exception):
    """Raised when the QA config is missing or malformed (fail early, explicit)."""


@dataclass
class QAConfig:
    program: str = ""
    unique_key: str | None = None
    required_complete: list[str] = field(default_factory=list)
    categoricals: dict[str, dict] = field(default_factory=dict)
    exclusive_flags: list[list[str]] = field(default_factory=list)
    expected_types: dict[str, str] = field(default_factory=dict)
    polarity: list[str] = field(default_factory=list)
    ranges: dict[str, dict] = field(default_factory=dict)
    missing_sentinels: list = field(default_factory=list)
    column_sets: dict[str, object] = field(default_factory=dict)
    aspect_params: dict[str, dict] = field(default_factory=dict)
    project_local: list[str] = field(default_factory=list)
    base_dir: Path = field(default_factory=lambda: Path("."))

    @classmethod
    def from_file(cls, path: Path) -> "QAConfig":
        if not path.exists():
            raise QAConfigError(f"QA config not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict) or "qa" not in data:
            raise QAConfigError(f"config {path} has no 'qa:' block")
        qa = data["qa"] or {}
        program = qa.get("program")
        if not program:
            raise QAConfigError(f"config {path} has no 'program:' key (required)")
        return cls(
            program=str(program),
            unique_key=qa.get("unique_key"),
            required_complete=list(qa.get("required_complete", []) or []),
            categoricals=dict(qa.get("categoricals", {}) or {}),
            exclusive_flags=[list(pair) for pair in (qa.get("exclusive_flags", []) or [])],
            expected_types=dict(qa.get("expected_types", {}) or {}),
            polarity=list(qa.get("polarity", []) or []),
            ranges=dict(qa.get("ranges", {}) or {}),
            missing_sentinels=list(qa.get("missing_sentinels", []) or []),
            column_sets=dict(qa.get("column_sets", {}) or {}),
            aspect_params=dict(qa.get("aspect_params", {}) or {}),
            project_local=list(qa.get("project_local", []) or []),
            base_dir=path.parent,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/qa && python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Lint and commit**

```bash
cd ~/d/science && git branch --show-current
cd science/qa && ruff check src tests --fix
cd ~/d/science
git add science/qa/src/science_qa/config.py science/qa/tests/test_config.py
git commit -m "refactor(science-qa): config = program selection + parameterization; drop packs"
```

---

### Task 12: `runner.py` — orchestration + coverage + B1 parity

**Files:**
- Modify: `science/qa/src/science_qa/runner.py`
- Test: `science/qa/tests/test_runner.py` (rewrite)

> The runner is the heart: static substrate validation → per-CheckSpec expansion (required = one implicit invocation; family = `spec.expand(config)`) → per-invocation column resolution → context-compat validation → `blocked`/`empty`/`ran`/`not-applicable` → flags + coverage. Absent required input resolves three ways: an `inv.optional` input → `not-applicable`; a built-in required check's input → `blocked` **coverage-only** because the program's `required_column` owner emits the structural flag; a *configured* family item naming an absent column → fail early (exit 2, preserving B1's `_require_column` behavior). In this slice, project-local checks may not declare `requires`; they should validate any project-specific required inputs inside the check and emit their own project-local structural flags.

- [ ] **Step 1: Write the failing test**

```python
# science/qa/tests/test_runner.py  (rewrite)
import json
from pathlib import Path

import pandas as pd
from science_qa.runner import run_qa


def _cfg(tmp_path, body="qa:\n  program: scrna-qc-table\n") -> Path:
    p = tmp_path / "qa.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def _table(tmp_path, df) -> Path:
    p = tmp_path / "t.parquet"
    df.to_parquet(p)
    return p


def _good_scrna():
    return pd.DataFrame({
        "total_counts": [1000, 2000, 1500],
        "n_genes_by_counts": [500, 800, 600],
        "pct_counts_mt": [5.0, 8.0, 3.0],
    })


def test_clean_table_reports_coverage_no_structural_fail(tmp_path):
    res = run_qa(_cfg(tmp_path), _table(tmp_path, _good_scrna()), tmp_path)
    assert res.structural_failed is False
    cov = json.loads((tmp_path / "qa_report.json").read_text())["coverage"]
    assert cov["executable_denominator"] >= 5
    # doublet is optional and absent -> not-applicable
    statuses = {e["check_id"]: e["status"] for e in cov["entries"]}
    assert statuses["scrna-qc-table/doublet_ceiling"] == "not-applicable"


def test_missing_required_column_blocks_and_structural_fails(tmp_path):
    df = _good_scrna().drop(columns=["pct_counts_mt"])
    res = run_qa(_cfg(tmp_path), _table(tmp_path, df), tmp_path)
    assert res.structural_failed is True
    cov = json.loads((tmp_path / "qa_report.json").read_text())["coverage"]
    statuses = {e["check_id"]: e["status"] for e in cov["entries"]}
    assert statuses["scrna-qc-table/gates"] == "blocked"


def test_b1_parity_mito_gate_fires_with_same_severity(tmp_path):
    df = _good_scrna()
    df.loc[0, "pct_counts_mt"] = 30.0  # exceeds default max_mito_pct 20
    run_qa(_cfg(tmp_path), _table(tmp_path, df), tmp_path)
    flags = json.loads((tmp_path / "qa_report.json").read_text())["flags"]
    mito = [f for f in flags if f["flag_id"] == "scrna-qc-table/threshold/pct_counts_mt/max"]
    assert mito and mito[0]["severity"] == "distribution"


def test_b1_parity_rehomed_flag_ids(tmp_path):
    # scrna non_negative -> numeric-column/polarity ; all_zero_cell -> gene-expression-qc-table/degenerate_cell
    df = _good_scrna()
    df.loc[0, "total_counts"] = -1          # negative library size -> polarity (structural)
    df.loc[1, "total_counts"] = 0           # all-zero cell -> degenerate_cell (structural)
    df.loc[1, "n_genes_by_counts"] = 0
    cfg = _cfg(tmp_path, "qa:\n  program: scrna-qc-table\n  polarity: [total_counts]\n")
    res = run_qa(cfg, _table(tmp_path, df), tmp_path)
    ids = {f["flag_id"]: f["severity"] for f in json.loads((tmp_path / "qa_report.json").read_text())["flags"]}
    assert ids.get("numeric-column/polarity/total_counts/-") == "structural"
    assert ids.get("gene-expression-qc-table/degenerate_cell/total_counts+n_genes_by_counts/-") == "structural"
    assert res.structural_failed is True


def test_unconfigured_family_recorded_not_errored(tmp_path):
    cov = json.loads(_run_and_read(tmp_path))["coverage"]
    assert "tabular/categoricals" in cov["unconfigured_families"]


def _run_and_read(tmp_path) -> str:
    run_qa(_cfg(tmp_path), _table(tmp_path, _good_scrna()), tmp_path)
    return (tmp_path / "qa_report.json").read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/qa && python -m pytest tests/test_runner.py -v`
Expected: FAIL — current `run_qa` has no program/coverage behavior.

- [ ] **Step 3: Write minimal implementation**

```python
# science/qa/src/science_qa/runner.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from science_qa.aspects import CHECK_REQUIRED, CheckSpec, Invocation
from science_qa.config import QAConfig
from science_qa.context import Context, TableContext
from science_qa.coverage import (
    STATUS_BLOCKED, STATUS_EMPTY, STATUS_NA, STATUS_RAN, Coverage, CoverageEntry,
)
from science_qa.dispositions import reconcile_dispositions
from science_qa.flags import SEVERITY_DISTRIBUTION, SEVERITY_STRUCTURAL, Flag
from science_qa.program import resolve_program
from science_qa.report import write_reports
from science_qa.selectors import resolve_columns


class RunnerError(Exception):
    """Raised on a static program/substrate incompatibility (fail early)."""


@dataclass
class RunResult:
    flags: list[Flag]
    structural_failed: bool
    coverage: Coverage


def _read_table(table_path: Path) -> pd.DataFrame:
    if table_path.suffix == ".parquet":
        return pd.read_parquet(table_path)
    if table_path.suffix in {".csv", ".tsv"}:
        return pd.read_csv(table_path, sep="\t" if table_path.suffix == ".tsv" else ",")
    raise ValueError(f"unsupported table format: {table_path.suffix}")


def _invocations(spec: CheckSpec, config: QAConfig) -> list[Invocation]:
    if spec.kind == CHECK_REQUIRED:
        return [Invocation(requires=spec.requires)]
    return spec.expand(config) if spec.expand else []


def _missing_required(spec: CheckSpec, inv: Invocation, table: pd.DataFrame) -> list[str]:
    return [c for c in inv.requires if c not in table.columns]


def run_qa(config_path: Path, table_path: Path, report_dir: Path) -> RunResult:
    config = QAConfig.from_file(config_path)
    program = resolve_program(config.program)
    table = _read_table(table_path)

    # static program <-> substrate validation, before any context is built
    for spec in program.checks:
        if spec.accepts is not program.substrate:
            raise RunnerError(f"check {spec.check_id} accepts {spec.accepts.__name__}, "
                              f"program {program.name} binds {program.substrate.__name__}")

    flags: list[Flag] = []
    coverage = Coverage()

    for spec in program.checks:
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


def _run_invocation(spec: CheckSpec, inv: Invocation, table: pd.DataFrame,
                    config: QAConfig, flags: list[Flag]) -> CoverageEntry:
    missing = _missing_required(spec, inv, table)
    if missing:
        if inv.optional:
            return CoverageEntry(spec.check_id, spec.aspect, STATUS_NA, [], 0)  # declared-optional input absent
        if spec.kind == CHECK_REQUIRED:
            # coverage-only: the absent column's structural flag is emitted by the owning
            # required_column check (program invariant), so we DON'T flag here -> no duplicates.
            return CoverageEntry(spec.check_id, spec.aspect, STATUS_BLOCKED, [], 0)
        # a configured family item names a column absent from the table -> fail early (exit 2), per B1
        raise RunnerError(f"{spec.check_id} references column(s) absent from table: {missing}")

    columns = _resolve(spec, inv, table, config)
    if (inv.columns is not None or spec.selector is not None) and not columns:
        return CoverageEntry(spec.check_id, spec.aspect, STATUS_EMPTY, [], 0)

    ctx: Context = TableContext(table=table, columns=columns)
    if not isinstance(ctx, spec.accepts):
        raise RunnerError(f"context {type(ctx).__name__} incompatible with {spec.check_id}")

    # merge this aspect's configured params under the invocation's explicit params
    params = dict(inv.params)
    for k, v in config.aspect_params.get(spec.aspect, {}).items():
        params.setdefault(k, v)
    produced = spec.fn(ctx, params)
    flags.extend(produced)
    return CoverageEntry(spec.check_id, spec.aspect, STATUS_RAN, columns, len(produced))


def _resolve(spec: CheckSpec, inv: Invocation, table: pd.DataFrame, config: QAConfig) -> list[str]:
    if inv.columns is not None:
        return [c for c in inv.columns if c in table.columns]
    if spec.selector is not None:
        return resolve_columns(spec.selector, table, column_sets=config.column_sets)
    return list(table.columns)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/qa && python -m pytest tests/test_runner.py -v`
Expected: PASS (4 tests). (Depends on `report.write_reports` accepting `coverage=` — implemented next; if red on `write_reports() got unexpected keyword 'coverage'`, do Task 13 then re-run.)

> **Execution note:** Task 12 Step 4 depends on Task 13's `write_reports(coverage=…)` signature. Implement Task 13 Step 3 alongside Task 12 Step 3, or run them as a pair, then verify both test files green.

- [ ] **Step 5: Lint and commit**

```bash
cd ~/d/science && git branch --show-current
cd science/qa && ruff check src tests --fix
cd ~/d/science
git add science/qa/src/science_qa/runner.py science/qa/tests/test_runner.py
git commit -m "feat(science-qa): program-driven runner with coverage + blocked/empty/na statuses"
```

---

### Task 12b: `project_local` extension loading (runtime)

**Files:**
- Create: `science/qa/src/science_qa/extensions.py`
- Modify: `science/qa/src/science_qa/runner.py` (compose program checks + project-local checks)
- Test: `science/qa/tests/test_extensions.py`, and append a runner test to `science/qa/tests/test_runner.py`

> `project_local` is the spec's append-only extension point — it must actually run, not just live in config. Project-local specs are constrained to the `project-local` aspect namespace, must not collide with built-in or sibling project-local `check_id`s, and cannot carry `requires` in this slice. The runner composes `program.checks + load_project_local(config.project_local, reserved_check_ids={...})`; the existing static substrate validation then context-checks the project-local specs too (a wrong `accepts` → `RunnerError`).

- [ ] **Step 1: Write the failing tests**

```python
# science/qa/tests/test_extensions.py
import pytest
from science_qa.aspects import CheckSpec
from science_qa.extensions import ProjectLocalError, load_project_local


def test_load_resolves_checkspec_reference(tmp_path, monkeypatch):
    (tmp_path / "myext.py").write_text(
        "from science_qa.aspects import CHECK_REQUIRED, CheckSpec\n"
        "from science_qa.context import TableContext\n"
        "marker = CheckSpec('project-local', 'marker', CHECK_REQUIRED, TableContext, lambda ctx, params: [])\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    specs = load_project_local(["myext:marker"])
    assert len(specs) == 1 and isinstance(specs[0], CheckSpec) and specs[0].check_id == "project-local/marker"


def test_bad_ref_shape_errors():
    with pytest.raises(ProjectLocalError, match="module:attr"):
        load_project_local(["noseparator"])


def test_non_checkspec_errors(tmp_path, monkeypatch):
    (tmp_path / "badext.py").write_text("marker = 123\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(ProjectLocalError, match="not a CheckSpec"):
        load_project_local(["badext:marker"])


def test_project_local_requires_project_local_aspect(tmp_path, monkeypatch):
    (tmp_path / "badns.py").write_text(
        "from science_qa.aspects import CHECK_REQUIRED, CheckSpec\n"
        "from science_qa.context import TableContext\n"
        "marker = CheckSpec('general', 'non_empty', CHECK_REQUIRED, TableContext, lambda ctx, params: [])\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(ProjectLocalError, match="project-local aspect"):
        load_project_local(["badns:marker"])


def test_project_local_check_id_collision_errors(tmp_path, monkeypatch):
    (tmp_path / "collision.py").write_text(
        "from science_qa.aspects import CHECK_REQUIRED, CheckSpec\n"
        "from science_qa.context import TableContext\n"
        "marker = CheckSpec('project-local', 'marker', CHECK_REQUIRED, TableContext, lambda ctx, params: [])\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(ProjectLocalError, match="collides"):
        load_project_local(["collision:marker"], reserved_check_ids={"project-local/marker"})


def test_project_local_requires_owned_missing_input_policy(tmp_path, monkeypatch):
    (tmp_path / "requires.py").write_text(
        "from science_qa.aspects import CHECK_REQUIRED, CheckSpec\n"
        "from science_qa.context import TableContext\n"
        "marker = CheckSpec('project-local', 'needs_col', CHECK_REQUIRED, TableContext, "
        "lambda ctx, params: [], requires=('x',))\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(ProjectLocalError, match="requires"):
        load_project_local(["requires:marker"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science/qa && python -m pytest tests/test_extensions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_qa.extensions'`

- [ ] **Step 3: Implement `extensions.py`**

```python
# science/qa/src/science_qa/extensions.py
from __future__ import annotations

import importlib

from science_qa.aspects import CheckSpec


class ProjectLocalError(Exception):
    """Raised when a project_local reference cannot be imported or is not a CheckSpec."""


def load_project_local(refs: list[str], *, reserved_check_ids: set[str] | None = None) -> list[CheckSpec]:
    """Resolve 'module.path:attr' references to CheckSpec instances (append-only extension).

    Each attr must be a CheckSpec, or a list of CheckSpecs. Fail early on a malformed ref,
    an import error, a missing attribute, a wrong type, a non-project-local namespace,
    a check_id collision, or a project-local `requires` clause.
    """
    specs: list[CheckSpec] = []
    seen = set(reserved_check_ids or set())
    for ref in refs:
        module_path, sep, attr = ref.partition(":")
        if not sep or not attr:
            raise ProjectLocalError(f"project_local ref must be 'module:attr': {ref!r}")
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ProjectLocalError(f"cannot import project_local module {module_path!r}: {exc}") from exc
        if not hasattr(module, attr):
            raise ProjectLocalError(f"project_local module {module_path!r} has no attribute {attr!r}")
        obj = getattr(module, attr)
        for candidate in (obj if isinstance(obj, list) else [obj]):
            if not isinstance(candidate, CheckSpec):
                raise ProjectLocalError(f"project_local {ref!r} resolved to {type(candidate).__name__}, not CheckSpec")
            if candidate.aspect != "project-local":
                raise ProjectLocalError(f"project_local {ref!r} must use the project-local aspect")
            if candidate.check_id in seen:
                raise ProjectLocalError(f"project_local check_id {candidate.check_id!r} collides with an existing check")
            if candidate.requires:
                raise ProjectLocalError(
                    f"project_local {candidate.check_id!r} declares requires={candidate.requires!r}; "
                    "missing-input ownership is not implemented for project-local checks"
                )
            seen.add(candidate.check_id)
            specs.append(candidate)
    return specs
```

- [ ] **Step 4: Wire the runner to compose project-local checks**

Modify `science/qa/src/science_qa/runner.py`:

```python
# add import:
from science_qa.extensions import load_project_local

# in run_qa, replace the line `program = resolve_program(config.program)` block so that a combined
# check list is built and used by BOTH the static validation loop and the run loop:
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
        ...
```

(Replace both former `for spec in program.checks:` loops with `for spec in checks:`. Nothing else in `run_qa` changes.)

- [ ] **Step 5: Append a runner integration test**

```python
# science/qa/tests/test_runner.py  (append)
import json as _json

import pytest as _pytest


def test_project_local_check_runs(tmp_path, monkeypatch):
    (tmp_path / "ext_runs.py").write_text(
        "from science_qa.aspects import CHECK_REQUIRED, CheckSpec\n"
        "from science_qa.context import TableContext\n"
        "from science_qa.flags import Flag, SEVERITY_DISTRIBUTION\n"
        "def _fn(ctx, params):\n"
        "    return [Flag('project-local', 'marker', 'table', None, SEVERITY_DISTRIBUTION, '1', '0', 'ran')]\n"
        "marker = CheckSpec('project-local', 'marker', CHECK_REQUIRED, TableContext, _fn)\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    cfg = _cfg(tmp_path, "qa:\n  program: scrna-qc-table\n  project_local: ['ext_runs:marker']\n")
    run_qa(cfg, _table(tmp_path, _good_scrna()), tmp_path)
    ids = [f["flag_id"] for f in _json.loads((tmp_path / "qa_report.json").read_text())["flags"]]
    assert "project-local/marker/table/-" in ids


def test_project_local_wrong_context_rejected(tmp_path, monkeypatch):
    from science_qa.runner import RunnerError
    (tmp_path / "ext_bad_ctx.py").write_text(
        "from science_qa.aspects import CHECK_REQUIRED, CheckSpec\n"
        "class OtherContext: pass\n"
        "marker = CheckSpec('project-local', 'marker', CHECK_REQUIRED, OtherContext, lambda c, p: [])\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    cfg = _cfg(tmp_path, "qa:\n  program: scrna-qc-table\n  project_local: ['ext_bad_ctx:marker']\n")
    with _pytest.raises(RunnerError):
        run_qa(cfg, _table(tmp_path, _good_scrna()), tmp_path)
```

- [ ] **Step 6: Run, lint, commit**

Run: `cd science/qa && python -m pytest tests/test_extensions.py tests/test_runner.py -v`
Expected: PASS

```bash
cd ~/d/science && git branch --show-current
cd science/qa && ruff check src tests --fix
cd ~/d/science
git add science/qa/src/science_qa/extensions.py science/qa/src/science_qa/runner.py science/qa/tests/test_extensions.py science/qa/tests/test_runner.py
git commit -m "feat(science-qa): runtime project_local append-only check extension"
```

---

### Task 13: `report.py` — coverage block + Coverage section

**Files:**
- Modify: `science/qa/src/science_qa/report.py`
- Test: `science/qa/tests/test_report.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# science/qa/tests/test_report.py  (append)
import json

from science_qa.coverage import STATUS_RAN, Coverage, CoverageEntry
from science_qa.report import write_reports


def test_report_includes_coverage_block_and_is_deterministic(tmp_path):
    cov = Coverage(entries=[CoverageEntry("a/x", "a", STATUS_RAN, ["c"], 0)],
                   unconfigured_families=["b/y"])
    write_reports([], report_dir=tmp_path, rows_checked=3, coverage=cov)
    first = (tmp_path / "qa_report.json").read_text()
    write_reports([], report_dir=tmp_path, rows_checked=3, coverage=cov)
    assert first == (tmp_path / "qa_report.json").read_text()  # byte-identical
    payload = json.loads(first)
    assert payload["coverage"]["executable_denominator"] == 1
    assert "## Coverage" in (tmp_path / "qa_report.md").read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/qa && python -m pytest tests/test_report.py -v`
Expected: FAIL — `write_reports()` has no `coverage` parameter.

- [ ] **Step 3: Write minimal implementation**

```python
# science/qa/src/science_qa/report.py
from __future__ import annotations

import json
from pathlib import Path

from science_qa.coverage import Coverage
from science_qa.flags import SEVERITY_DISTRIBUTION, SEVERITY_STRUCTURAL, Flag


def _sorted(flags: list[Flag]) -> list[Flag]:
    return sorted(flags, key=lambda f: f.flag_id)


def write_reports(flags: list[Flag], *, report_dir: Path, rows_checked: int, coverage: Coverage) -> None:
    """Write qa_report.json (immutable flag ledger + coverage) and qa_report.md.

    Deterministic: output depends only on the sorted flag set, rows_checked, and the
    coverage block — never on wall-clock — so re-run-and-diff stays clean.
    """
    report_dir.mkdir(parents=True, exist_ok=True)
    ordered = _sorted(flags)
    structural = [f for f in ordered if f.severity == SEVERITY_STRUCTURAL]
    distribution = [f for f in ordered if f.severity == SEVERITY_DISTRIBUTION]
    cov = coverage.to_dict()

    payload = {
        "rows_checked": rows_checked,
        "structural_count": len(structural),
        "distribution_count": len(distribution),
        "flags": [f.to_dict() for f in ordered],
        "coverage": cov,
    }
    (report_dir / "qa_report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# QA / sanity-check report",
        "",
        f"- Rows checked: {rows_checked}",
        f"- Structural flags: **{len(structural)}** · Distribution flags: **{len(distribution)}**",
        "",
        "## Flagged issues",
        "### 🔴 Structural (ingest/derive bugs — build-fatal)",
    ]
    lines += [f"- `{f.flag_id}` — {f.message}" for f in structural] or ["- none"]
    lines += ["", "### 🟡 Distribution (domain review — not fatal)"]
    lines += [f"- `{f.flag_id}` — {f.message}" for f in distribution] or ["- none"]
    lines += [
        "",
        "## Coverage",
        f"- Executable denominator: {cov['executable_denominator']} "
        f"(ran {cov['ran']} · empty {cov['empty']} · blocked {cov['blocked']} · n/a {cov['not-applicable']})",
        f"- Declared-but-unconfigured families: {', '.join(cov['unconfigured_families']) or 'none'}",
        f"- Narrow-checking signal: {', '.join(cov['narrow_signal']) or 'none'}",
        "",
    ]
    (report_dir / "qa_report.md").write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/qa && python -m pytest tests/test_report.py tests/test_runner.py -v`
Expected: PASS

- [ ] **Step 5: Lint and commit**

```bash
cd ~/d/science && git branch --show-current
cd science/qa && ruff check src tests --fix
cd ~/d/science
git add science/qa/src/science_qa/report.py science/qa/tests/test_report.py
git commit -m "feat(science-qa): coverage block in qa_report.json + Coverage md section"
```

---

### Task 14: CLI errors + remove `checks.py`/`packs/`; full suite green

**Files:**
- Modify: `science/qa/src/science_qa/cli.py`
- Delete: `science/qa/src/science_qa/checks.py`, `science/qa/src/science_qa/packs/__init__.py`, `science/qa/src/science_qa/packs/scrna.py`
- Delete: `science/qa/tests/test_checks_structural.py`, `science/qa/tests/test_checks_distribution.py`, `science/qa/tests/test_pack_scrna.py`
- Test: `science/qa/tests/test_cli_run.py` (update import expectations)

- [ ] **Step 1: Update the CLI and delete replaced modules**

```python
# science/qa/src/science_qa/cli.py
from __future__ import annotations

from pathlib import Path

import click

from science_qa.aspects.tabular import CategoricalSpecError
from science_qa.config import QAConfigError
from science_qa.extensions import ProjectLocalError
from science_qa.program import ProgramError
from science_qa.runner import RunnerError, run_qa
from science_qa.selectors import SelectorError


@click.group()
def cli() -> None:
    """science-qa command-line interface."""


@cli.command("run")
@click.option("--config", "config_path", type=click.Path(path_type=Path, exists=True, dir_okay=False), required=True)
@click.option("--table", "table_path", type=click.Path(path_type=Path, exists=True, dir_okay=False), required=True)
@click.option("--report-dir", "report_dir", type=click.Path(path_type=Path), default=Path("."), show_default=True)
@click.option("--no-strict", is_flag=True, default=False,
              help="Suppress the build-fatal exit code (local inspection only; never wire into a default target).")
def run_command(config_path: Path, table_path: Path, report_dir: Path, no_strict: bool) -> None:
    """Run a QA program over a built table; write qa_report.{md,json} + reconcile dispositions.

    Exit codes: 0 = ok (or structural suppressed by --no-strict); 1 = structural flag fired
    (build-fatal); 2 = bad input (config/table/program/selector error, unsupported format).
    """
    try:
        result = run_qa(config_path, table_path, report_dir)
    except (QAConfigError, ProgramError, SelectorError, RunnerError, CategoricalSpecError,
            ProjectLocalError, ValueError) as exc:
        raise click.UsageError(str(exc)) from exc
    click.echo(f"{len(result.flags)} flag(s); structural_failed={result.structural_failed}; "
               f"coverage_denominator={result.coverage.executable_denominator()}")
    if result.structural_failed and not no_strict:
        raise SystemExit(1)
```

```bash
cd ~/d/science
git rm science/qa/src/science_qa/checks.py \
       science/qa/src/science_qa/packs/__init__.py \
       science/qa/src/science_qa/packs/scrna.py \
       science/qa/tests/test_checks_structural.py \
       science/qa/tests/test_checks_distribution.py \
       science/qa/tests/test_pack_scrna.py
```

- [ ] **Step 2: Update the CLI fixtures — every config now needs `program:`**

`program:` is required after Task 11, so every config the CLI tests write must declare it, or the
exit-code (0/1/2) tests will return config-error 2 instead of 1/0. Update `science/qa/tests/test_cli_run.py`:

```python
# _setup: add program: scrna-qc-table to the written config (keeps duplicate-key structural flag).
def _setup(tmp_path):
    pd.DataFrame({"SUBJECT_ID": [1, 1]}).to_parquet(tmp_path / "t.parquet")
    (tmp_path / "qa.yaml").write_text("qa:\n  program: scrna-qc-table\n  unique_key: SUBJECT_ID\n")
```

```python
# test_cli_run_absent_column_exits_2_with_message: add program: to the inline config too.
    (tmp_path / "qa.yaml").write_text("qa:\n  program: scrna-qc-table\n  unique_key: SUBJECT_ID\n")
```

Exit codes still hold: duplicate `SUBJECT_ID` → structural flag → exit 1 (no-strict → 0); the
absent-column case (table has only `OTHER`, config names `SUBJECT_ID`) now raises `RunnerError`
(configured family naming an absent column) → exit 2. If any test asserts on stdout text, accept the
new suffix: `assert "structural_failed=" in result.output and "coverage_denominator=" in result.output`.

- [ ] **Step 3: Run the full science-qa suite**

Run: `cd science/qa && python -m pytest -v`
Expected: PASS — all aspect/program/coverage/runner/report/cli/config tests green; no import errors from removed modules. If any test still imports `science_qa.checks` or `science_qa.packs`, delete/port that assertion.

- [ ] **Step 4: Lint and commit**

```bash
cd ~/d/science && git branch --show-current
cd science/qa && ruff check src tests --fix && python -m pytest -q
cd ~/d/science
git add -A science/qa
git commit -m "refactor(science-qa): wire CLI to programs; remove re-homed checks.py + packs/"
```

---

## Phase F — Consumer (science_tool)

### Task 15: `qa-audit` breadth column

**Files:**
- Modify: `science/src/science_tool/qa_audit/manifest.py` (add `load_qa_coverage`, aggregating coverage from the same `qa_report` resources `load_qa_artifacts` already walks)
- Modify: `science/src/science_tool/qa_audit/audit.py` (add a `breadth` cell to each row + a Breadth column in `render_markdown`)
- Test: `science/tests/test_qa_audit_manifest.py` (the `load_qa_coverage` tests) and `science/tests/test_qa_audit_audit.py` (the `render_markdown` test) — the qa_audit tests live under **`science/tests/`**, not `science/src/...`.

> Context (verified): `audit.py:audit_workflows` discovers a run's `qa_report.json` **through the manifest** — `load_qa_artifacts(manifest_path)` selects resources named `qa_report`/`qa_report:<substrate>`. The coverage block lives in those same payloads, so the consumer adds a sibling `load_qa_coverage(manifest_path)` that walks the same resources and aggregates `ran` + `executable_denominator`. `load_qa_artifacts`'s signature is left unchanged.

- [ ] **Step 1: Confirm the qa_audit test files**

Run:
```bash
cd ~/d/science
rtk rg -l "audit_workflows|render_markdown|load_qa_artifacts" science/tests | sort -u
```
Expected: `science/tests/test_qa_audit_audit.py`, `science/tests/test_qa_audit_manifest.py`, etc. Append the new tests to those existing files (same style).

- [ ] **Step 2: Write the failing test**

```python
# Append to the qa_audit test module found in Step 1.
import json

import yaml
from science_tool.qa_audit.audit import render_markdown
from science_tool.qa_audit.manifest import load_qa_coverage


def _manifest_with_report(tmp_path, payload: dict):
    (tmp_path / "qa_report.json").write_text(json.dumps(payload))
    manifest = tmp_path / "datapackage.yaml"
    manifest.write_text(yaml.safe_dump({"resources": [{"name": "qa_report", "path": "qa_report.json"}]}))
    return manifest


def test_load_qa_coverage_aggregates_from_manifest(tmp_path):
    manifest = _manifest_with_report(tmp_path, {
        "flags": [],
        "coverage": {"executable_denominator": 7, "ran": 5, "empty": 1, "blocked": 1,
                     "not-applicable": 0, "unconfigured_families": [], "narrow_signal": [], "entries": []},
    })
    assert load_qa_coverage(manifest) == {"ran": 5, "executable_denominator": 7}


def test_load_qa_coverage_absent_block_returns_none(tmp_path):
    manifest = _manifest_with_report(tmp_path, {"flags": []})  # no coverage key
    assert load_qa_coverage(manifest) is None


def test_render_markdown_includes_breadth_column():
    out = render_markdown([{
        "workflow": "wf", "runs": 1, "chain_depth": 1, "open_flags": 0, "dispositioned_flags": 0,
        "iteration": "SINGLE-RUN", "engagement": "NO-FLAGS", "breadth": "5/7",
    }])
    assert "Breadth" in out and "5/7" in out
```

- [ ] **Step 3: Implement `load_qa_coverage` + the breadth column**

```python
# science/src/science_tool/qa_audit/manifest.py  — add this function (json, yaml, Path, _substrate_suffix already imported):
def load_qa_coverage(manifest_path: Path) -> dict | None:
    """Aggregate the coverage block(s) from a run's qa_report resources.

    Walks the same `qa_report`/`qa_report:<substrate>` resources as load_qa_artifacts and
    sums `ran` + `executable_denominator` across substrates. Returns None when there is no
    qa_report or no coverage block present (older reports predate the block).
    """
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    base = manifest_path.parent
    ran = denom = 0
    found = False
    for res in manifest.get("resources", []) or []:
        if _substrate_suffix(str(res.get("name", "")), "qa_report") is None:
            continue
        payload = json.loads((base / res["path"]).read_text(encoding="utf-8"))
        cov = payload.get("coverage")
        if isinstance(cov, dict):
            found = True
            ran += int(cov.get("ran", 0))
            denom += int(cov.get("executable_denominator", 0))
    return {"ran": ran, "executable_denominator": denom} if found else None
```

```python
# science/src/science_tool/qa_audit/audit.py
# (1) import alongside load_qa_artifacts:
from science_tool.qa_audit.manifest import load_qa_artifacts, load_qa_coverage

# (2) in the success branch, after `has_report, flags = load_qa_artifacts(manifest_path)`, compute breadth:
        coverage = load_qa_coverage(manifest_path)
        breadth = f"{coverage['ran']}/{coverage['executable_denominator']}" if coverage else "-"
# ...and add `"breadth": breadth,` to that row dict.

# (3) in the ERROR-branch row dict, add `"breadth": "-",`.

# (4) update render_markdown header + body to add a Breadth column:
def render_markdown(rows: list[dict]) -> str:
    header = (
        "| Workflow | Runs | Chain | Open | Dispositioned | Iteration | Engagement | Breadth |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |"
    )
    body = [
        f"| {r['workflow']} | {r['runs']} | {r['chain_depth']} | {r['open_flags']} | "
        f"{r['dispositioned_flags']} | {r['iteration']} | {r['engagement']} | {r.get('breadth', '-')} |"
        for r in rows
    ]
    return "\n".join([header, *body]) + "\n"
```

> `breadth` is `ran/denominator` (e.g. `5/7`) or `-` when a report predates the coverage block. Additive only — the iteration/engagement verdict logic is untouched, and a missing block never crashes the audit.

- [ ] **Step 4: Run the qa_audit tests**

Run: `cd science && python -m pytest tests -k qa_audit -v`
Expected: PASS — new breadth tests green; existing qa_audit verdict tests unchanged.

- [ ] **Step 5: Lint and commit**

```bash
cd ~/d/science && git branch --show-current
cd science && ruff check src/science_tool/qa_audit tests --fix
cd ~/d/science
git add science/src/science_tool/qa_audit science/tests/test_qa_audit_manifest.py science/tests/test_qa_audit_audit.py
git commit -m "feat(qa-audit): additive breadth column from qa_report coverage block"
```

---

## Phase G — Docs

### Task 16: Convention, playbook, rubric, umbrella updates

**Files:**
- Modify: `docs/conventions/pipeline-qa-checkpoints.md`
- Modify: `docs/process/pipeline-audit-and-refactor.md`
- Modify: `aspects/computational-analysis/computational-analysis.md`
- Modify: `docs/plans/2026-06-10-data-driven-discovery-improvements.md`

- [ ] **Step 1: Update `pipeline-qa-checkpoints.md` — baseline library + extensions**

Under the existing "Reference implementation" section, add a paragraph:

```markdown
### Composable aspects & programs (baseline library + project extensions)

`science_qa` composes checks as **aspects** (`general`, `tabular`, `numeric-column`,
`gene-expression-qc-table`, `scrna-qc-table`, `project-local`) into a named **program** selected
by `qa.program` (e.g. `scrna-qc-table`). The program is the *baseline library* of type-appropriate
checks; project-specific, bug-driven checks remain valuable and are added via `qa.project_local`
(an append-only extension point) plus the parameterized families (`ranges`, `categoricals`, …).
The check list is therefore **baseline library + project extensions**, not bug-driven-only. Breadth
is reported as a coverage block in `qa_report.json` (executable denominator + `ran`/`empty`/`blocked`/
`not-applicable` per invocation + declared-but-unconfigured families); see
`docs/plans/2026-06-13-qa-check-library-design.md`.
```

- [ ] **Step 2: Update `pipeline-audit-and-refactor.md` — breadth as a coverage dimension**

In the "Related QA disciplines" / process-iteration area, add a line noting QA **breadth/coverage**
is read from the `science qa-audit` breadth column (`ran/denominator`), and that `empty`/`blocked`
invocations and declared-but-unconfigured families are the narrow-checking signal.

- [ ] **Step 3: Update `computational-analysis.md` — QA Coverage rubric**

In the `review-pipeline` *QA Coverage* rubric row, reference program breadth: PASS = broad program
ran with few `empty`/`blocked`; WARN = several `empty`/`blocked` or unconfigured families; note the
breadth comes from the `qa_report.json` coverage block surfaced by `science qa-audit`.

- [ ] **Step 4: Update the umbrella roadmap B2 entry**

In `2026-06-10-data-driven-discovery-improvements.md`, update the **B2** entry to record the B1.5
reframing: B2 shipped as a composable check-library (aspects/programs) with breadth as a
program-derived coverage readout; link the design + plan docs.

- [ ] **Step 5: Validate links and commit**

Run: `cd science && python -m science_tool.cli validate 2>/dev/null || true` (markdown link-check, if wired); otherwise visually confirm relative links resolve.

```bash
cd ~/d/science && git branch --show-current
git add docs/conventions/pipeline-qa-checkpoints.md docs/process/pipeline-audit-and-refactor.md \
        aspects/computational-analysis/computational-analysis.md \
        docs/plans/2026-06-10-data-driven-discovery-improvements.md
git commit -m "docs: QA check-library — baseline-library framing, breadth coverage, umbrella B2 update"
```

---

## Final verification

- [ ] **Full science-qa suite:** `cd science/qa && python -m pytest -q` → all green.
- [ ] **science_tool qa_audit slice:** `cd science && python -m pytest tests -k qa_audit -q` → all green.
- [ ] **One-way dependency intact:** `rtk rg "science_tool" science/qa/src` → only prose/docstrings, no import; `rtk rg "import science_qa" science/src/science_tool` → none.
- [ ] **No leftover references:** `rtk rg "science_qa.packs|science_qa.checks" science/qa` → none.
- [ ] Finish with `superpowers:finishing-a-development-branch`.

---

## Self-review notes (coverage of the design spec)

- Substrate-typed `Context` + `TableContext` → Task 1. Selectors as a separate unit → Task 2.
- Required-vs-family check kinds → Task 3 (`CheckSpec.kind`/`expand`), Task 9 (expanders), Task 12 (`_invocations`, unconfigured-family recording).
- Aspect stack + re-homing (general/tabular/numeric-column/gene-expression-qc/scrna-qc) → Tasks 4–8; parity map asserted in Task 12 (`scrna-qc-table/threshold/pct_counts_mt/max`) — extend with the other mapped ids during execution.
- Program declares *what*; config supplies thresholds/column-sets/project-local → Tasks 9 + 11; `project_local` append-only extension → config field (Task 11) **+ runtime loading/validation/execution (Task 12b)** + convention text (Task 16).
- Coverage statuses `ran`/`empty`/`blocked`/`not-applicable`; executable denominator excludes `not-applicable` → Task 10; wired in Task 12; emitted in Task 13.
- `general.non_empty` + library-size/degenerate-cell structural → Tasks 4, 7.
- Context-compat validated statically before context build, then per-invocation → Task 12.
- Determinism (byte-identical coverage block) → Task 13 test.
- Additive `qa-audit` breadth column, no verdict change → Task 15.
- Convention/playbook/rubric/umbrella doc changes → Task 16.
- Out-of-scope (matrix substrate, extra programs, opaque score, validate-gating) → untouched by all tasks.
