# `science datasets infer-schema` Implementation Plan (Spec 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `science datasets infer-schema` CLI command that infers a resource's
observed shape (field names + coarse Frictionless types) from its produced table, prints a
diff-vs-existing plus a human-facing review report, and (with `--write`) applies *only* the
safe names+types patch under strict guards — never inferring build-fatal invariants.

**Architecture:** One new module `science_tool/datasets/infer_schema.py` holds the whole
pipeline as small pure-ish functions: descriptor IO (JSON+YAML, atomic canonical write),
resource resolution, table-sample reading, coarse type inference, diff, review report,
read-only orchestration + renderers, and a guarded whole-package-validated write. A thin
CLI command wires it into the existing `datasets` Click group beside `validate`. A neutral
shared fixture corpus (`science/fixtures/descriptor_contract/`) is asserted from both the
`science_tool` and `science_qa` test suites so the two forced descriptor readers can never
silently diverge. `science_qa` source is untouched.

**Tech Stack:** Python 3, Click, pandas 3 + pyarrow 24 (already `science_tool` deps),
PyYAML, Pydantic v2 (the Spec 1 models in `datasets/schema.py`).

**Design doc:** `docs/plans/2026-06-14-infer-schema-scaffold-design.md` (read §2 separation
rule, §4 inference, §5 report, §6 write guards, §7 consistency contract).

---

## Conventions for every task

- **Working dir:** the framework lives under `science/` in the repo root. Run all `pytest`
  from `science/` using its venv: `science/.venv/bin/python -m pytest ...`.
- **Run a single test:** `cd science && .venv/bin/python -m pytest tests/test_infer_schema.py::test_name -q`
- **The module under construction:** `science/src/science_tool/datasets/infer_schema.py`.
  Tasks 1–7 each add one cohesive slice to it; the file grows additively. Put new code at
  the bottom of the existing content unless a task says otherwise.
- **Imports the module needs** (add to the top once, in Task 1):
  ```python
  from __future__ import annotations

  import copy
  import json
  import os
  import tempfile
  from dataclasses import dataclass, field
  from pathlib import Path

  import pandas as pd
  import yaml
  from pandas.api import types as pdt
  from pydantic import ValidationError

  from science_tool.datasets.schema import ResourceDescriptor, package_consistency_issues
  ```
- **Commit hygiene:** `git add` only the explicit files named in each task's Step "Commit".
  Never `git add -A`/`.`.
- **No `Co-Authored-By` trailer** in commits.

---

## File structure

| File | Responsibility | Tasks |
|---|---|---|
| `science/src/science_tool/datasets/infer_schema.py` | descriptor IO, resource resolution, table read, type inference, diff, report, orchestration, renderers, guarded write | 1–7 |
| `science/src/science_tool/cli.py` | `datasets infer-schema` command (beside `validate`, ~line 3108) | 8 |
| `science/tests/test_infer_schema.py` | unit + integration tests for the module | 1–7 |
| `science/tests/test_infer_schema_cli.py` | CliRunner tests for the command | 8 |
| `science/fixtures/descriptor_contract/*.json` | neutral shared consistency corpus | 9 |
| `science/tests/test_descriptor_contract.py` | science_tool side of the contract | 9 |
| `science/qa/tests/test_descriptor_contract.py` | science_qa side of the contract | 9 |

---

## Task 1: Descriptor IO — load + atomic canonical write (JSON & YAML)

**Files:**
- Modify: `science/pyproject.toml` (add the pandas runtime dependency)
- Create: `science/src/science_tool/datasets/infer_schema.py`
- Test: `science/tests/test_infer_schema.py`

`infer_schema.py` imports pandas at module top, and `cli.py` imports `infer_schema` at
module top — so importing the CLI requires pandas. `science_tool` currently only declares
`pyarrow` (pandas resolves transitively today, but that is not guaranteed). Declare it.

- [ ] **Step 0: Declare the pandas runtime dependency**

In `science/pyproject.toml`, add `"pandas>=2.0"` to the `dependencies = [...]` list (it sits
beside the existing `"pyarrow>=24.0.0"`):

```toml
  "pyarrow>=24.0.0",
  "pandas>=2.0",
  "pypdf>=6.13.2",
```

Then refresh the lock so the declaration is recorded (the package is already present in the
venv, so this should be a no-op resolution):

Run: `cd science && uv lock`
Expected: success; `uv.lock` now lists `pandas` as a direct dependency of `science`.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_infer_schema.py
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from science_tool.datasets import infer_schema as isch


def test_load_descriptor_json_file(tmp_path: Path) -> None:
    p = tmp_path / "datapackage.json"
    p.write_text(json.dumps({"name": "x", "resources": []}))
    mapping, fmt = isch.load_descriptor(p)
    assert fmt == "json"
    assert mapping["name"] == "x"


def test_load_descriptor_yaml_file(tmp_path: Path) -> None:
    p = tmp_path / "datapackage.yaml"
    p.write_text("name: y\nresources: []\n")
    mapping, fmt = isch.load_descriptor(p)
    assert fmt == "yaml"
    assert mapping["name"] == "y"


def test_load_descriptor_directory_resolves_file(tmp_path: Path) -> None:
    (tmp_path / "datapackage.json").write_text(json.dumps({"name": "d", "resources": []}))
    mapping, fmt = isch.load_descriptor(tmp_path)
    assert fmt == "json"
    assert mapping["name"] == "d"


def test_load_descriptor_unknown_extension_errors(tmp_path: Path) -> None:
    p = tmp_path / "datapackage.txt"
    p.write_text("nope")
    with pytest.raises(isch.InferSchemaError):
        isch.load_descriptor(p)


def test_dump_descriptor_json_is_atomic_and_canonical(tmp_path: Path) -> None:
    p = tmp_path / "datapackage.json"
    p.write_text(json.dumps({"b": 2, "a": 1}))
    isch.dump_descriptor({"b": 2, "a": 1}, p, "json")
    text = p.read_text()
    # canonical = sorted keys, 2-space indent, trailing newline
    assert text == '{\n  "a": 1,\n  "b": 2\n}\n'


def test_dump_descriptor_yaml_canonical(tmp_path: Path) -> None:
    p = tmp_path / "datapackage.yaml"
    isch.dump_descriptor({"b": 2, "a": 1}, p, "yaml")
    assert yaml.safe_load(p.read_text()) == {"a": 1, "b": 2}
    assert p.read_text().startswith("a: 1")  # sorted keys
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && .venv/bin/python -m pytest tests/test_infer_schema.py -q`
Expected: FAIL with `ModuleNotFoundError` / `AttributeError: module ... has no attribute 'load_descriptor'`.

- [ ] **Step 3: Write the minimal implementation**

Create `science/src/science_tool/datasets/infer_schema.py` with the import block from
"Conventions" above, then:

```python
"""science datasets infer-schema: a safe schema-authoring scaffold (Spec 3).

Infers a resource's observed shape (field names + coarse Frictionless types) from its
produced table. Emits a diff-vs-existing plus a human review report; with --write applies
ONLY the names+types patch under strict guards. It never infers build-fatal invariants
(constraints, keys, foreignKeys, qa) — those are recommended in the report, authored by a
human. See docs/plans/2026-06-14-infer-schema-scaffold-design.md.
"""

# (import block here — see Conventions)

_DESCRIPTOR_NAMES = ("datapackage.json", "datapackage.yaml", "datapackage.yml")
_FMT_BY_SUFFIX = {".json": "json", ".yaml": "yaml", ".yml": "yaml"}


class InferSchemaError(Exception):
    """Any user-facing infer-schema failure (the CLI maps it to a clean error exit)."""


def load_descriptor(path: Path) -> tuple[dict, str]:
    """Load a datapackage descriptor mapping + its format ('json'|'yaml').

    `path` may be the descriptor file or a directory containing one. The descriptor is read
    as a plain mapping (json.load / yaml.safe_load), independent of the commons
    canonical-datapackage parser.
    """
    if path.is_dir():
        for name in _DESCRIPTOR_NAMES:
            candidate = path / name
            if candidate.exists():
                path = candidate
                break
        else:
            raise InferSchemaError(f"no datapackage descriptor found in {path}")
    fmt = _FMT_BY_SUFFIX.get(path.suffix)
    if fmt is None:
        raise InferSchemaError(
            f"unsupported descriptor extension {path.suffix!r} (want .json/.yaml/.yml)"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InferSchemaError(f"cannot read descriptor {path}: {exc}") from exc
    try:
        mapping = json.loads(text) if fmt == "json" else yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise InferSchemaError(f"malformed {fmt} descriptor {path}: {exc}") from exc
    if not isinstance(mapping, dict):
        raise InferSchemaError(f"descriptor {path} top level is not a mapping")
    return mapping, fmt


def _render_descriptor(mapping: dict, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(mapping, indent=2, sort_keys=True) + "\n"
    return yaml.safe_dump(mapping, sort_keys=True, default_flow_style=False, allow_unicode=True)


def dump_descriptor(mapping: dict, path: Path, fmt: str) -> None:
    """Atomically write the descriptor, canonically re-rendered in its own format.

    Canonical = sorted keys, deterministic output. Formatting/comments are not preserved.
    """
    text = _render_descriptor(mapping, fmt)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".infer-schema-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && .venv/bin/python -m pytest tests/test_infer_schema.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add science/pyproject.toml science/uv.lock \
        science/src/science_tool/datasets/infer_schema.py science/tests/test_infer_schema.py
git commit -m "feat(infer-schema): descriptor load + atomic canonical write (JSON+YAML); declare pandas dep"
```

---

## Task 2: Resource resolution — name primary, path fallback, ambiguity error

**Files:**
- Modify: `science/src/science_tool/datasets/infer_schema.py` (append)
- Test: `science/tests/test_infer_schema.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_resolve_resource_by_name() -> None:
    pkg = {"resources": [{"name": "a", "path": "a.csv"}, {"name": "b", "path": "b.csv"}]}
    res, idx = isch.resolve_resource(pkg, "b")
    assert idx == 1 and res["path"] == "b.csv"


def test_resolve_resource_path_fallback_when_no_name_match() -> None:
    pkg = {"resources": [{"name": "a", "path": "data/obs.parquet"}]}
    res, idx = isch.resolve_resource(pkg, "data/obs.parquet")
    assert idx == 0 and res["name"] == "a"


def test_resolve_resource_name_wins_over_path() -> None:
    # "x" is resource 0's name AND resource 1's path → name match is primary, unambiguous
    pkg = {"resources": [{"name": "x", "path": "x.csv"}, {"name": "y", "path": "x"}]}
    res, idx = isch.resolve_resource(pkg, "x")
    assert idx == 0


def test_resolve_resource_duplicate_name_is_ambiguous() -> None:
    pkg = {"resources": [{"name": "a", "path": "1.csv"}, {"name": "a", "path": "2.csv"}]}
    with pytest.raises(isch.InferSchemaError, match="ambiguous"):
        isch.resolve_resource(pkg, "a")


def test_resolve_resource_not_found() -> None:
    pkg = {"resources": [{"name": "a", "path": "a.csv"}]}
    with pytest.raises(isch.InferSchemaError, match="no resource"):
        isch.resolve_resource(pkg, "zzz")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && .venv/bin/python -m pytest tests/test_infer_schema.py -k resolve_resource -q`
Expected: FAIL (`no attribute 'resolve_resource'`).

- [ ] **Step 3: Implement**

Append to `infer_schema.py`:

```python
def resolve_resource(pkg: dict, resource: str) -> tuple[dict, int]:
    """Resolve `resource` against resources[]: by name first, then by path.

    Ambiguity (a name matching >1 resource, or a path-fallback matching >1 resource) is an
    error — never a silent pick. A name match is primary and short-circuits path matching.
    """
    resources = pkg.get("resources")
    if not isinstance(resources, list) or not resources:
        raise InferSchemaError("descriptor has no resources[] to resolve against")
    by_name = [(i, r) for i, r in enumerate(resources) if r.get("name") == resource]
    if len(by_name) > 1:
        raise InferSchemaError(f"resource name {resource!r} is ambiguous (matches {len(by_name)})")
    if len(by_name) == 1:
        i, r = by_name[0]
        return r, i
    by_path = [(i, r) for i, r in enumerate(resources) if r.get("path") == resource]
    if len(by_path) > 1:
        raise InferSchemaError(f"resource path {resource!r} is ambiguous (matches {len(by_path)})")
    if len(by_path) == 1:
        i, r = by_path[0]
        return r, i
    raise InferSchemaError(f"no resource named or pathed {resource!r} in descriptor")
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && .venv/bin/python -m pytest tests/test_infer_schema.py -k resolve_resource -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/infer_schema.py science/tests/test_infer_schema.py
git commit -m "feat(infer-schema): resource resolution (name primary, path fallback, ambiguity)"
```

---

## Task 3: Table read + coarse type inference

**Files:**
- Modify: `science/src/science_tool/datasets/infer_schema.py` (append)
- Test: `science/tests/test_infer_schema.py` (append)

- [ ] **Step 1: Write the failing tests**

First add `import pandas as pd` to the imports at the top of
`science/tests/test_infer_schema.py` (Task 1 created it without pandas; Task 3 onward needs
it). Then append:

```python
def test_coarse_type_mapping() -> None:
    assert isch.coarse_type(pd.Series([1, 2, 3])) == "integer"
    assert isch.coarse_type(pd.Series([1.0, 2.5])) == "number"
    assert isch.coarse_type(pd.Series([True, False])) == "boolean"
    assert isch.coarse_type(pd.Series(pd.to_datetime(["2020-01-01", "2021-06-01"]))) == "datetime"
    assert isch.coarse_type(pd.Series(["a", "b"])) == "string"


def test_coarse_type_all_null_is_string() -> None:
    assert isch.coarse_type(pd.Series([None, None], dtype="object")) == "string"


def test_coarse_type_from_arrow() -> None:
    import pyarrow as pa

    assert isch.coarse_type_from_arrow(pa.int64()) == "integer"
    assert isch.coarse_type_from_arrow(pa.float64()) == "number"
    assert isch.coarse_type_from_arrow(pa.bool_()) == "boolean"
    assert isch.coarse_type_from_arrow(pa.timestamp("ns")) == "datetime"
    assert isch.coarse_type_from_arrow(pa.string()) == "string"


def test_is_mixed_object_detects_mixed() -> None:
    assert isch.is_mixed_object(pd.Series([1, "a", 2.0], dtype="object")) is True
    assert isch.is_mixed_object(pd.Series(["a", "b"], dtype="object")) is False


def test_read_table_sample_csv(tmp_path: Path) -> None:
    p = tmp_path / "t.csv"
    p.write_text("id,val,flag\nA,1.5,true\nB,2.5,false\n")
    df = isch.read_table_sample(p, sample=100)
    assert list(df.columns) == ["id", "val", "flag"]
    assert len(df) == 2


def test_read_table_sample_unsupported(tmp_path: Path) -> None:
    p = tmp_path / "t.xlsx"
    p.write_text("x")
    with pytest.raises(isch.InferSchemaError):
        isch.read_table_sample(p, sample=10)


def test_observed_fields_csv(tmp_path: Path) -> None:
    p = tmp_path / "t.csv"
    p.write_text("id,val,mixed\nA,1.5,1\nB,2.5,x\n")
    by_name = {f.name: f for f in isch.observed_fields(p, sample=100)}
    assert by_name["id"].type == "string"
    assert by_name["val"].type == "number"
    assert by_name["mixed"].type == "string" and by_name["mixed"].mixed is True


def test_observed_fields_parquet_from_arrow_schema(tmp_path: Path) -> None:
    p = tmp_path / "t.parquet"
    pd.DataFrame({"id": ["A", "B"], "n": [1, 2]}).to_parquet(p)
    by_name = {f.name: f.type for f in isch.observed_fields(p, sample=100)}
    assert by_name == {"id": "string", "n": "integer"}


def test_observed_fields_parquet_zero_rows_still_infers(tmp_path: Path) -> None:
    # The core design invariant: parquet names/types come from the Arrow schema metadata,
    # so an empty file still yields fields (a sampled-dtype approach would lose them).
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.table({"id": pa.array([], type=pa.string()), "n": pa.array([], type=pa.int64())})
    p = tmp_path / "empty.parquet"
    pq.write_table(table, p)
    by_name = {f.name: f.type for f in isch.observed_fields(p, sample=100)}
    assert by_name == {"id": "string", "n": "integer"}


def test_infer_fields_from_dataframe(tmp_path: Path) -> None:
    df = pd.DataFrame({"id": ["A", "B"], "val": [1.5, 2.5], "mixed": [1, "x"]})
    by_name = {f.name: f for f in isch.infer_fields(df)}
    assert by_name["val"].type == "number"
    assert by_name["mixed"].mixed is True
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && .venv/bin/python -m pytest tests/test_infer_schema.py -k "coarse_type or mixed_object or read_table_sample or observed_fields or infer_fields" -q`
Expected: FAIL (`no attribute 'coarse_type'`).

- [ ] **Step 3: Implement**

Append to `infer_schema.py`. Note the split that satisfies the design invariant: parquet
**types** come from the Arrow schema (`observed_fields`, robust to empty/all-null files);
`read_table_sample` returns a sample DataFrame used only for report stats and for CSV type
inference.

```python
@dataclass
class InferredField:
    name: str
    type: str
    mixed: bool = False


def coarse_type(series: pd.Series) -> str:
    """Map a pandas column to a coarse Frictionless type (used for CSV, which has no embedded
    schema). Conservative: anything not clearly int/float/bool/datetime — including all-null
    and mixed object columns — is 'string'."""
    if series.notna().sum() == 0:
        return "string"
    if pdt.is_bool_dtype(series):
        return "boolean"
    if pdt.is_integer_dtype(series):
        return "integer"
    if pdt.is_float_dtype(series):
        return "number"
    if pdt.is_datetime64_any_dtype(series):
        return "datetime"
    return "string"


def coarse_type_from_arrow(arrow_type) -> str:
    """Map a pyarrow DataType to a coarse Frictionless type (authoritative for parquet)."""
    import pyarrow as pa

    if pa.types.is_boolean(arrow_type):
        return "boolean"
    if pa.types.is_integer(arrow_type):
        return "integer"
    if pa.types.is_floating(arrow_type) or pa.types.is_decimal(arrow_type):
        return "number"
    if pa.types.is_temporal(arrow_type):
        return "datetime"
    return "string"


def is_mixed_object(series: pd.Series) -> bool:
    """True when an object column holds >1 distinct python base type among non-null values."""
    if not pdt.is_object_dtype(series):
        return False
    kinds = {type(v) for v in series.dropna().tolist()}
    return len(kinds) > 1


def read_table_sample(table_path: Path, sample: int) -> pd.DataFrame:
    """Read up to `sample` rows of the table as a DataFrame (CSV/TSV/parquet).

    Used for report statistics and for CSV type inference. NOT the source of truth for
    parquet types — see observed_fields, which reads the Arrow schema instead.
    """
    suffix = table_path.suffix.lower()
    if not table_path.exists():
        raise InferSchemaError(f"table file not found: {table_path}")
    try:
        if suffix == ".parquet":
            import pyarrow.parquet as pq

            pf = pq.ParquetFile(str(table_path))
            batch = next(pf.iter_batches(batch_size=max(sample, 1)), None)
            return batch.to_pandas() if batch is not None else pd.DataFrame()
        if suffix in (".csv", ".tsv"):
            sep = "\t" if suffix == ".tsv" else ","
            return pd.read_csv(table_path, nrows=sample, sep=sep)
    except Exception as exc:  # malformed table is a user-facing failure, not a crash
        raise InferSchemaError(f"cannot read table {table_path}: {exc}") from exc
    raise InferSchemaError(f"unsupported table format {suffix!r} (want .parquet/.csv/.tsv)")


def infer_fields(df: pd.DataFrame) -> list[InferredField]:
    """Infer (name, coarse type, mixed-flag) from a DataFrame (the CSV path)."""
    return [
        InferredField(name=str(col), type=coarse_type(df[col]), mixed=is_mixed_object(df[col]))
        for col in df.columns
    ]


def observed_fields(table_path: Path, sample: int) -> list[InferredField]:
    """Authoritative (name, type) per column. Parquet → Arrow schema metadata (no row scan;
    robust to empty/all-null/nullable columns). CSV/TSV → coarse inference over a sample."""
    if table_path.suffix.lower() == ".parquet":
        import pyarrow.parquet as pq

        if not table_path.exists():
            raise InferSchemaError(f"table file not found: {table_path}")
        schema = pq.ParquetFile(str(table_path)).schema_arrow
        return [
            InferredField(name=schema.field(i).name, type=coarse_type_from_arrow(schema.field(i).type))
            for i in range(len(schema))
        ]
    return infer_fields(read_table_sample(table_path, sample))
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && .venv/bin/python -m pytest tests/test_infer_schema.py -k "coarse_type or mixed_object or read_table_sample or observed_fields or infer_fields" -q`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/infer_schema.py science/tests/test_infer_schema.py
git commit -m "feat(infer-schema): table-sample read + coarse type inference"
```

---

## Task 4: Diff-vs-existing (with type-conflict detection)

**Files:**
- Modify: `science/src/science_tool/datasets/infer_schema.py` (append)
- Test: `science/tests/test_infer_schema.py` (append)

The conflict rule (design §6.2): a conflict is **only** an existing *authored* `type` that
differs from the inferred type. An existing field with no `type` (or `type: "any"`) is
*filled* (a non-conflict `change`). Matching type → `same`. New field → `add`. A field in
the schema but absent from the file → `remove` (reported, never auto-applied).

- [ ] **Step 1: Write the failing tests**

```python
def _inf(name: str, typ: str) -> "isch.InferredField":
    return isch.InferredField(name=name, type=typ)


def test_diff_absent_schema_all_add() -> None:
    diff = isch.diff_schema([], [_inf("a", "integer"), _inf("b", "string")])
    assert [(d.name, d.action) for d in diff] == [("a", "add"), ("b", "add")]


def test_diff_same_type() -> None:
    diff = isch.diff_schema([{"name": "a", "type": "integer"}], [_inf("a", "integer")])
    assert diff[0].action == "same" and diff[0].conflict is False


def test_diff_fill_untyped_field_is_nonconflict_change() -> None:
    diff = isch.diff_schema([{"name": "a"}], [_inf("a", "number")])
    assert diff[0].action == "change" and diff[0].conflict is False
    assert diff[0].old_type is None and diff[0].new_type == "number"


def test_diff_any_typed_field_is_nonconflict_change() -> None:
    diff = isch.diff_schema([{"name": "a", "type": "any"}], [_inf("a", "string")])
    assert diff[0].action == "change" and diff[0].conflict is False


def test_diff_type_disagreement_is_conflict() -> None:
    diff = isch.diff_schema([{"name": "a", "type": "string"}], [_inf("a", "integer")])
    assert diff[0].action == "change" and diff[0].conflict is True


def test_diff_field_absent_from_file_is_remove() -> None:
    diff = isch.diff_schema([{"name": "gone", "type": "string"}], [])
    assert diff[0].action == "remove"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && .venv/bin/python -m pytest tests/test_infer_schema.py -k diff -q`
Expected: FAIL (`no attribute 'diff_schema'`).

- [ ] **Step 3: Implement**

Append to `infer_schema.py`:

```python
@dataclass
class DiffEntry:
    name: str
    action: str  # "add" | "change" | "same" | "remove"
    old_type: str | None
    new_type: str | None
    conflict: bool = False


def diff_schema(existing_fields: list[dict], inferred: list[InferredField]) -> list[DiffEntry]:
    """Diff inferred fields against an existing schema's fields. See §6.2 conflict rule."""
    existing = {f.get("name"): f for f in existing_fields}
    inferred_names = {i.name for i in inferred}
    entries: list[DiffEntry] = []
    for inf in inferred:
        if inf.name not in existing:
            entries.append(DiffEntry(inf.name, "add", None, inf.type))
            continue
        old = existing[inf.name].get("type")
        if old is None or old == "any":
            entries.append(DiffEntry(inf.name, "change", old, inf.type, conflict=False))
        elif old == inf.type:
            entries.append(DiffEntry(inf.name, "same", old, inf.type, conflict=False))
        else:
            entries.append(DiffEntry(inf.name, "change", old, inf.type, conflict=True))
    for name, fld in existing.items():
        if name not in inferred_names:
            entries.append(DiffEntry(str(name), "remove", fld.get("type"), None))
    return entries
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && .venv/bin/python -m pytest tests/test_infer_schema.py -k diff -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/infer_schema.py science/tests/test_infer_schema.py
git commit -m "feat(infer-schema): diff-vs-existing with type-conflict detection"
```

---

## Task 5: Review report (recommendations + warnings)

**Files:**
- Modify: `science/src/science_tool/datasets/infer_schema.py` (append)
- Test: `science/tests/test_infer_schema.py` (append)

Every report item is a recommendation or warning — never emitted into a schema. Thresholds
(named constants so they're tunable in one place): `ENUM_MAX_DISTINCT = 20`,
`HIGH_CARDINALITY_FRACTION = 0.9`,
`STRING_SENTINELS = {"NA", "N/A", "null", "NULL", "NaN", "-", "?"}`. Enum candidacy uses
"some repetition" (`not is_unique`) plus the absolute distinct cap — deliberately no
fraction guard, which mis-fires on small samples.

- [ ] **Step 1: Write the failing tests**

```python
def test_report_required_and_identifier() -> None:
    df = pd.DataFrame({"id": ["A", "B", "C"], "g": ["x", "x", "y"]})
    rep = isch.build_report(df, isch.infer_fields(df))
    kinds = {(r.kind, r.column) for r in rep.recommendations}
    assert ("required", "id") in kinds       # no nulls observed
    assert ("identifier", "id") in kinds     # unique + non-null + id-type
    assert ("enum", "g") in kinds            # low cardinality


def test_report_bound_for_numeric() -> None:
    df = pd.DataFrame({"x": [0.0, 1.0, 2.0]})
    rep = isch.build_report(df, isch.infer_fields(df))
    assert any(r.kind == "bound" and r.column == "x" for r in rep.recommendations)


def test_report_warns_mixed_and_nullable() -> None:
    df = pd.DataFrame({"m": [1, "a", 2.0], "n": ["p", None, "q"]})
    rep = isch.build_report(df, isch.infer_fields(df))
    cols = {(w.column) for w in rep.warnings}
    assert "m" in cols  # mixed object
    assert "n" in cols  # nullable


def test_report_missing_sentinel_recommendation() -> None:
    df = pd.DataFrame({"v": ["1", "NA", "NA", "3"]})
    rep = isch.build_report(df, isch.infer_fields(df))
    assert any(r.kind == "missing_sentinel" and r.column == "v" for r in rep.recommendations)


def test_report_records_sample_size() -> None:
    df = pd.DataFrame({"a": [1, 2]})
    rep = isch.build_report(df, isch.infer_fields(df))
    assert rep.sample_rows == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && .venv/bin/python -m pytest tests/test_infer_schema.py -k report -q`
Expected: FAIL (`no attribute 'build_report'`).

- [ ] **Step 3: Implement**

Append to `infer_schema.py`:

```python
ENUM_MAX_DISTINCT = 20
HIGH_CARDINALITY_FRACTION = 0.9
STRING_SENTINELS = {"NA", "N/A", "null", "NULL", "NaN", "-", "?"}


@dataclass
class Recommendation:
    kind: str  # identifier|enum|required|unique|missing_sentinel|bound
    column: str
    message: str


@dataclass
class ReportWarning:
    column: str
    message: str


@dataclass
class ReviewReport:
    recommendations: list[Recommendation] = field(default_factory=list)
    warnings: list[ReportWarning] = field(default_factory=list)
    sample_rows: int = 0


def build_report(df: pd.DataFrame, inferred: list[InferredField]) -> ReviewReport:
    """Build the human-facing review report from a sample. Recommendations are candidate
    invariants the author may choose to add by hand; they are NEVER emitted into a schema."""
    rep = ReviewReport(sample_rows=int(len(df)))
    by_name = {i.name: i for i in inferred}
    for col in df.columns:
        s = df[col]
        name = str(col)
        nonnull = s.dropna()
        n_nonnull = int(len(nonnull))
        n_null = int(len(s) - n_nonnull)
        distinct = int(nonnull.nunique())
        ftype = by_name[name].type if name in by_name else "string"

        if n_null == 0 and len(s) > 0:
            rep.recommendations.append(Recommendation(
                "required", name, f"no nulls in {len(s)} sampled rows — consider constraints.required"))
        is_unique = n_nonnull > 0 and distinct == n_nonnull
        if is_unique and n_null == 0 and ftype in ("string", "integer"):
            rep.recommendations.append(Recommendation(
                "identifier", name, "unique & non-null in sample — consider primaryKey"))
        elif is_unique:
            rep.recommendations.append(Recommendation(
                "unique", name, "all sampled values distinct — consider constraints.unique"))
        if (ftype in ("string", "integer", "boolean") and 2 <= distinct <= ENUM_MAX_DISTINCT
                and n_nonnull and not is_unique):
            rep.recommendations.append(Recommendation(
                "enum", name, f"low cardinality ({distinct} distinct) — consider constraints.enum"))
        if ftype in ("number", "integer", "datetime") and n_nonnull:
            rep.recommendations.append(Recommendation(
                "bound", name,
                f"observed range [{nonnull.min()!r}, {nonnull.max()!r}] in sample — "
                "possible minimum/maximum (sample-derived, NOT a constraint)"))

        # missing-sentinel: recurring out-of-band tokens
        sentinels = {str(v) for v in nonnull.unique()} & STRING_SENTINELS
        for tok in sorted(sentinels):
            if int((nonnull.astype(str) == tok).sum()) > 1:
                rep.recommendations.append(Recommendation(
                    "missing_sentinel", name,
                    f"recurring sentinel-like value {tok!r} — consider table missingValues"))

        # warnings
        if by_name.get(name) and by_name[name].mixed:
            rep.warnings.append(ReportWarning(name, "mixed python types in sample — typed as string"))
        if n_null:
            rep.warnings.append(ReportWarning(name, f"{n_null}/{len(s)} null in sample (nullable)"))
        if ftype == "string" and n_nonnull and distinct > HIGH_CARDINALITY_FRACTION * n_nonnull and not is_unique:
            rep.warnings.append(ReportWarning(name, "high-cardinality string (likely free text)"))
    return rep
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && .venv/bin/python -m pytest tests/test_infer_schema.py -k report -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/infer_schema.py science/tests/test_infer_schema.py
git commit -m "feat(infer-schema): human review report (recommendations + warnings)"
```

---

## Task 6: Read-only orchestration + renderers

**Files:**
- Modify: `science/src/science_tool/datasets/infer_schema.py` (append)
- Test: `science/tests/test_infer_schema.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def _write_pkg(tmp_path: Path, pkg: dict, table_name: str, table_text: str) -> Path:
    (tmp_path / table_name).write_text(table_text)
    dp = tmp_path / "datapackage.json"
    dp.write_text(json.dumps(pkg))
    return dp


def test_infer_schema_result_end_to_end(tmp_path: Path) -> None:
    pkg = {"name": "p", "resources": [{"name": "obs", "path": "obs.csv"}]}
    dp = _write_pkg(tmp_path, pkg, "obs.csv", "id,val\nA,1.5\nB,2.5\n")
    result = isch.infer_schema_result(dp, "obs", sample=100)
    assert result.fmt == "json"
    assert result.res_index == 0
    assert {d.name for d in result.diff} == {"id", "val"}
    assert all(d.action == "add" for d in result.diff)
    assert result.report.sample_rows == 2
    assert result.descriptor_path == dp


def test_render_diff_rows_shape(tmp_path: Path) -> None:
    pkg = {"name": "p", "resources": [{"name": "obs", "path": "obs.csv"}]}
    dp = _write_pkg(tmp_path, pkg, "obs.csv", "id\nA\n")
    result = isch.infer_schema_result(dp, "obs", sample=100)
    rows = isch.render_diff_rows(result.diff)
    assert rows[0]["field"] == "id"
    assert rows[0]["action"] == "add"


def test_report_to_yaml_is_labelled(tmp_path: Path) -> None:
    pkg = {"name": "p", "resources": [{"name": "obs", "path": "obs.csv"}]}
    dp = _write_pkg(tmp_path, pkg, "obs.csv", "id\nA\n")
    result = isch.infer_schema_result(dp, "obs", sample=100)
    text = isch.report_to_yaml(result.report)
    obj = yaml.safe_load(text)
    assert "not emitted as invariant" in obj["disclaimer"].lower()


def test_result_to_json_roundtrips(tmp_path: Path) -> None:
    pkg = {"name": "p", "resources": [{"name": "obs", "path": "obs.csv"}]}
    dp = _write_pkg(tmp_path, pkg, "obs.csv", "id,val\nA,1\n")
    result = isch.infer_schema_result(dp, "obs", sample=100)
    obj = json.loads(isch.result_to_json(result))
    assert {"patch", "diff", "report"} <= set(obj)
    assert obj["patch"]["schema"]["fields"]  # proposed names+types only
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && .venv/bin/python -m pytest tests/test_infer_schema.py -k "result_end_to_end or render_diff_rows or report_to_yaml or result_to_json" -q`
Expected: FAIL (`no attribute 'infer_schema_result'`).

- [ ] **Step 3: Implement**

Append to `infer_schema.py`:

```python
@dataclass
class InferResult:
    fmt: str
    pkg: dict
    res_index: int
    descriptor_path: Path
    table_path: Path
    diff: list[DiffEntry]
    report: ReviewReport
    inferred: list[InferredField]


def infer_schema_result(dp_path: Path, resource: str, sample: int) -> InferResult:
    """Read-only pipeline: load descriptor, resolve resource, read table, infer, diff, report."""
    mapping, fmt = load_descriptor(dp_path)
    descriptor_path = dp_path if dp_path.is_file() else _resolved_descriptor_path(dp_path)
    res, idx = resolve_resource(mapping, resource)
    rel = res.get("path")
    if not rel:
        raise InferSchemaError(f"resource {resource!r} has no path")
    table_path = descriptor_path.parent / rel
    df = read_table_sample(table_path, sample)          # sample for the report stats
    inferred = observed_fields(table_path, sample)      # authoritative names+types (Arrow for parquet)
    existing_fields = (res.get("schema") or {}).get("fields") or []
    diff = diff_schema(existing_fields, inferred)
    report = build_report(df, inferred)
    return InferResult(fmt, mapping, idx, descriptor_path, table_path, diff, report, inferred)


def _resolved_descriptor_path(directory: Path) -> Path:
    for name in _DESCRIPTOR_NAMES:
        candidate = directory / name
        if candidate.exists():
            return candidate
    raise InferSchemaError(f"no datapackage descriptor found in {directory}")


def proposed_schema(inferred: list[InferredField]) -> dict:
    """The machine-safe patch: names + types ONLY."""
    return {"schema": {"fields": [{"name": i.name, "type": i.type} for i in inferred]}}


def render_diff_rows(diff: list[DiffEntry]) -> list[dict]:
    rows: list[dict] = []
    glyph = {"add": "+", "change": "~", "same": "=", "remove": "-"}
    for d in diff:
        if d.action == "change":
            detail = f"{d.old_type or '(none)'} -> {d.new_type}" + (" CONFLICT" if d.conflict else "")
        elif d.action == "add":
            detail = f"type={d.new_type}"
        elif d.action == "remove":
            detail = "in schema, not in file"
        else:
            detail = f"type={d.new_type}"
        rows.append({"action": f"{glyph[d.action]} {d.action}", "field": d.name, "details": detail})
    return rows


def render_report_rows(report: ReviewReport) -> list[dict]:
    rows = [{"kind": r.kind, "column": r.column, "note": r.message,
             "label": "recommendation — not emitted as invariant"}
            for r in report.recommendations]
    rows += [{"kind": "warning", "column": w.column, "note": w.message, "label": "warning"}
             for w in report.warnings]
    return rows


def report_to_yaml(report: ReviewReport) -> str:
    obj = {
        "disclaimer": "recommendations are candidate invariants only — NOT emitted as invariant",
        "sample_rows": report.sample_rows,
        "recommendations": [{"kind": r.kind, "column": r.column, "message": r.message}
                            for r in report.recommendations],
        "warnings": [{"column": w.column, "message": w.message} for w in report.warnings],
    }
    return yaml.safe_dump(obj, sort_keys=False, default_flow_style=False, allow_unicode=True)


def result_to_json(result: InferResult) -> str:
    obj = {
        "patch": proposed_schema(result.inferred),
        "diff": [{"name": d.name, "action": d.action, "old_type": d.old_type,
                  "new_type": d.new_type, "conflict": d.conflict} for d in result.diff],
        "report": {
            "sample_rows": result.report.sample_rows,
            "recommendations": [{"kind": r.kind, "column": r.column, "message": r.message}
                                for r in result.report.recommendations],
            "warnings": [{"column": w.column, "message": w.message} for w in result.report.warnings],
        },
    }
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && .venv/bin/python -m pytest tests/test_infer_schema.py -k "result_end_to_end or render_diff_rows or report_to_yaml or result_to_json" -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/infer_schema.py science/tests/test_infer_schema.py
git commit -m "feat(infer-schema): read-only orchestration + diff/report/json renderers"
```

---

## Task 7: Guarded write (`write_patch`)

**Files:**
- Modify: `science/src/science_tool/datasets/infer_schema.py` (append)
- Test: `science/tests/test_infer_schema.py` (append)

Guards (design §6): preserve-only (authored field-level *and* table-level metadata
survives); refuse on a type-disagreement conflict; whole-package post-validation
(`ResourceDescriptor.model_validate` over **every** resource + `package_consistency_issues`
over all); verify the written field set still contains the inferred columns; atomic
canonical write in the input format. The write mutates a **deepcopy** — never the in-memory
`result.pkg` the caller may still render.

- [ ] **Step 1: Write the failing tests**

```python
def _result(tmp_path: Path, pkg: dict, table: str = "obs.csv",
            text: str = "id,val\nA,1\nB,2\n") -> "isch.InferResult":
    dp = _write_pkg(tmp_path, pkg, table, text)
    return isch.infer_schema_result(dp, pkg["resources"][0]["name"], sample=100)


def test_write_patch_adds_fields_to_schemaless(tmp_path: Path) -> None:
    pkg = {"name": "p", "resources": [{"name": "obs", "path": "obs.csv"}]}
    result = _result(tmp_path, pkg)
    isch.write_patch(result)
    written = json.loads(result.descriptor_path.read_text())
    fields = written["resources"][0]["schema"]["fields"]
    assert {f["name"] for f in fields} == {"id", "val"}
    assert {f["type"] for f in fields} == {"string", "integer"}


def test_write_patch_preserves_field_and_table_metadata(tmp_path: Path) -> None:
    # Field-level metadata that is Spec-1-valid on a *string* field: constraints.required,
    # a `description`, and an unmodelled `extra` (extra="allow"). (qa.low_variance is NOT
    # valid on a string field — Spec 1 rejects it — so it cannot be used here.)
    pkg = {"name": "p", "resources": [{
        "name": "obs", "path": "obs.csv",
        "schema": {
            "fields": [{"name": "id", "type": "string", "constraints": {"required": True},
                        "description": "the row id", "extra": {"owner": "me"}}],
            "primaryKey": "id",
            "missingValues": ["", "NA"],
        },
    }]}
    result = _result(tmp_path, pkg)  # file has id,val → val is new, id unchanged
    isch.write_patch(result)
    schema = json.loads(result.descriptor_path.read_text())["resources"][0]["schema"]
    id_field = next(f for f in schema["fields"] if f["name"] == "id")
    assert id_field["constraints"] == {"required": True}   # preserved
    assert id_field["description"] == "the row id"          # field-level metadata preserved
    assert id_field["extra"] == {"owner": "me"}             # field-level extra preserved
    assert schema["primaryKey"] == "id"                     # table-level preserved
    assert schema["missingValues"] == ["", "NA"]
    assert any(f["name"] == "val" for f in schema["fields"])  # new field added


def test_write_patch_refuses_type_conflict(tmp_path: Path) -> None:
    pkg = {"name": "p", "resources": [{
        "name": "obs", "path": "obs.csv",
        "schema": {"fields": [{"name": "id", "type": "string"}, {"name": "val", "type": "string"}]},
    }]}
    # file: val is integer → conflicts with authored type "string"
    result = _result(tmp_path, pkg)
    before = result.descriptor_path.read_text()
    with pytest.raises(isch.InferSchemaError, match="conflict"):
        isch.write_patch(result)
    assert result.descriptor_path.read_text() == before  # wrote nothing


def test_write_patch_yaml_roundtrips(tmp_path: Path) -> None:
    (tmp_path / "obs.csv").write_text("id,val\nA,1\n")
    dp = tmp_path / "datapackage.yaml"
    dp.write_text("name: p\nresources:\n- name: obs\n  path: obs.csv\n")
    result = isch.infer_schema_result(dp, "obs", sample=100)
    isch.write_patch(result)
    written = yaml.safe_load(dp.read_text())
    assert {f["name"] for f in written["resources"][0]["schema"]["fields"]} == {"id", "val"}


def test_write_patch_validates_external_foreign_key(tmp_path: Path) -> None:
    # resource B has an FK into A; writing A's inferred schema must keep the package valid
    (tmp_path / "a.csv").write_text("aid\nX\nY\n")
    (tmp_path / "b.csv").write_text("bid,aref\n1,X\n")
    pkg = {"name": "p", "resources": [
        {"name": "a", "path": "a.csv", "schema": {"fields": [{"name": "aid", "type": "string"}]}},
        {"name": "b", "path": "b.csv", "schema": {
            "fields": [{"name": "bid", "type": "string"}, {"name": "aref", "type": "string"}],
            "foreignKeys": [{"fields": "aref", "reference": {"resource": "a", "fields": "aid"}}],
        }},
    ]}
    dp = tmp_path / "datapackage.json"
    dp.write_text(json.dumps(pkg))
    result = isch.infer_schema_result(dp, "a", sample=100)
    isch.write_patch(result)  # must NOT raise — FK target field "aid" still present
    assert json.loads(dp.read_text())["resources"][0]["schema"]["fields"]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && .venv/bin/python -m pytest tests/test_infer_schema.py -k write_patch -q`
Expected: FAIL (`no attribute 'write_patch'`).

- [ ] **Step 3: Implement**

Append to `infer_schema.py`:

```python
def write_patch(result: InferResult) -> None:
    """Apply ONLY the names+types patch, under the §6 guards, then atomically write.

    Refuses (and writes nothing) on a type-disagreement conflict or a descriptor that would
    parse invalid as a whole package. Authored field- and table-level metadata is preserved.
    """
    conflicts = [d.name for d in result.diff if d.conflict]
    if conflicts:
        raise InferSchemaError(
            f"type conflict on field(s) {conflicts} — authored type differs from inferred; "
            "resolve by hand (the tool never overwrites an authored type)")

    pkg = copy.deepcopy(result.pkg)
    res = pkg["resources"][result.res_index]
    schema = res.setdefault("schema", {})
    fields = schema.setdefault("fields", [])
    by_name = {f.get("name"): f for f in fields}
    for d in result.diff:
        if d.action == "add":
            fields.append({"name": d.name, "type": d.new_type})
        elif d.action == "change":  # conflicts already excluded → safe type fill
            by_name[d.name]["type"] = d.new_type
        # "same"/"remove": untouched (remove is reported, never auto-applied)

    # Whole-package post-validation (cross-resource FK resolution needs every descriptor).
    descriptors: list[ResourceDescriptor] = []
    for r in pkg["resources"]:
        try:
            descriptors.append(ResourceDescriptor.model_validate(r))
        except ValidationError as exc:
            raise InferSchemaError(f"resulting descriptor is invalid: {exc.errors()[0]}") from exc
    issues = package_consistency_issues(descriptors)
    if issues:
        raise InferSchemaError("resulting package is inconsistent: " + "; ".join(issues))

    written = {f.get("name") for f in fields}
    missing = {i.name for i in result.inferred} - written
    if missing:
        raise InferSchemaError(f"internal: inferred columns missing after patch: {sorted(missing)}")

    dump_descriptor(pkg, result.descriptor_path, result.fmt)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && .venv/bin/python -m pytest tests/test_infer_schema.py -k write_patch -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/infer_schema.py science/tests/test_infer_schema.py
git commit -m "feat(infer-schema): guarded whole-package-validated atomic write"
```

---

## Task 8: CLI command `datasets infer-schema`

**Files:**
- Modify: `science/src/science_tool/cli.py` (add command after `datasets_validate`, ~line 3108)
- Test: `science/tests/test_infer_schema_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_infer_schema_cli.py
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import datasets


def _pkg(tmp_path: Path) -> Path:
    (tmp_path / "obs.csv").write_text("id,val\nA,1.5\nB,2.5\n")
    dp = tmp_path / "datapackage.json"
    dp.write_text(json.dumps({"name": "p", "resources": [{"name": "obs", "path": "obs.csv"}]}))
    return dp


def test_cli_readonly_does_not_mutate(tmp_path: Path) -> None:
    dp = _pkg(tmp_path)
    before = dp.read_text()
    result = CliRunner().invoke(datasets, ["infer-schema", str(dp), "--resource", "obs"])
    assert result.exit_code == 0, result.output
    assert dp.read_text() == before
    assert "val" in result.output


def test_cli_write_applies_patch(tmp_path: Path) -> None:
    dp = _pkg(tmp_path)
    result = CliRunner().invoke(datasets, ["infer-schema", str(dp), "--resource", "obs", "--write"])
    assert result.exit_code == 0, result.output
    fields = json.loads(dp.read_text())["resources"][0]["schema"]["fields"]
    assert {f["name"] for f in fields} == {"id", "val"}


def test_cli_emit_suggestions_writes_yaml_only(tmp_path: Path) -> None:
    dp = _pkg(tmp_path)
    out = tmp_path / "sugg.yaml"
    before = dp.read_text()
    result = CliRunner().invoke(
        datasets, ["infer-schema", str(dp), "--resource", "obs", "--emit-suggestions", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert dp.read_text() == before  # descriptor untouched


def test_cli_unknown_resource_errors(tmp_path: Path) -> None:
    dp = _pkg(tmp_path)
    result = CliRunner().invoke(datasets, ["infer-schema", str(dp), "--resource", "nope"])
    assert result.exit_code != 0
    assert "no resource" in result.output.lower()


def test_cli_json_format(tmp_path: Path) -> None:
    dp = _pkg(tmp_path)
    result = CliRunner().invoke(
        datasets, ["infer-schema", str(dp), "--resource", "obs", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert '"patch"' in result.output
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && .venv/bin/python -m pytest tests/test_infer_schema_cli.py -q`
Expected: FAIL (`No such command 'infer-schema'`).

- [ ] **Step 3: Implement**

First add the import near the top of `cli.py`, beside the existing
`from science_tool.datasets.validate import validate_data_packages` (line 15):

```python
from science_tool.datasets import infer_schema as _infer_schema
```

Then add this command immediately **after** `datasets_validate` (after its
`raise click.exceptions.Exit(1)`, ~line 3108):

```python
@datasets.command("infer-schema")
@click.argument("datapackage", type=click.Path(path_type=Path))
@click.option("--resource", "resource", required=True, help="Resource name (or path) to infer.")
@click.option("--sample", default=10000, show_default=True, help="Max rows sampled for inference.")
@click.option("--write", "do_write", is_flag=True, help="Apply ONLY the safe names+types patch in place.")
@click.option("--emit-suggestions", "suggestions_path", default=None, type=click.Path(path_type=Path),
              help="Write the review report to this YAML file (never mutates the descriptor).")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def datasets_infer_schema(
    datapackage: Path,
    resource: str,
    sample: int,
    do_write: bool,
    suggestions_path: Path | None,
    output_format: str,
) -> None:
    """Infer a resource's observed shape (field names + coarse types) from its table.

    Read-only by default (prints a diff vs the existing schema + a review report). With
    --write, applies ONLY the safe names+types patch; it never infers constraints, keys,
    foreignKeys, or qa: those are recommended in the report and authored by hand. Writes
    are canonical (the descriptor is re-rendered in its own format; formatting/comments are
    not preserved).
    """
    try:
        result = _infer_schema.infer_schema_result(datapackage, resource, sample)
    except _infer_schema.InferSchemaError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        click.echo(_infer_schema.result_to_json(result), nl=False)
    else:
        emit_query_rows(
            output_format=output_format, title="Proposed schema (names + types only)",
            columns=[("action", "Action"), ("field", "Field"), ("details", "Details")],
            rows=_infer_schema.render_diff_rows(result.diff))
        emit_query_rows(
            output_format=output_format, title="Review recommendations (NOT applied — author by hand)",
            columns=[("kind", "Kind"), ("column", "Column"), ("note", "Note"), ("label", "Label")],
            rows=_infer_schema.render_report_rows(result.report))

    if suggestions_path is not None:
        suggestions_path.write_text(_infer_schema.report_to_yaml(result.report), encoding="utf-8")
        click.echo(f"Wrote review report to {suggestions_path}")

    if do_write:
        try:
            _infer_schema.write_patch(result)
        except _infer_schema.InferSchemaError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"Applied names+types patch to {result.descriptor_path}")
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && .venv/bin/python -m pytest tests/test_infer_schema_cli.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_infer_schema_cli.py
git commit -m "feat(infer-schema): datasets infer-schema CLI command"
```

---

## Task 9: Consistency-contract corpus + both-side tests

**Files:**
- Create: `science/fixtures/descriptor_contract/minimal.json`
- Create: `science/fixtures/descriptor_contract/rich_single_fk.json`
- Create: `science/fixtures/descriptor_contract/composite_fk.json`
- Create: `science/fixtures/descriptor_contract/malformed_bound.json`
- Create: `science/tests/test_descriptor_contract.py`
- Create: `science/qa/tests/test_descriptor_contract.py`

The corpus is the *shared artifact* (no code crosses the `science_tool`↔`science_qa`
boundary). Each fixture is a single **resource descriptor** (the unit both readers consume).
`science_tool` asserts each parses under Spec 1; `science_qa` asserts each compiles **or**
fails only for a *documented compiler-only reason* (composite FK; malformed bound).

- [ ] **Step 1: Create the corpus fixtures**

`science/fixtures/descriptor_contract/minimal.json` — names+types only (what infer-schema
emits); must be Spec-1-valid AND QA-compilable:

```json
{
  "name": "minimal",
  "path": "minimal.csv",
  "schema": {
    "fields": [
      {"name": "id", "type": "string"},
      {"name": "value", "type": "number"}
    ]
  }
}
```

`science/fixtures/descriptor_contract/rich_single_fk.json` — exercises the full invariant
vocabulary with a *self* single-column FK (so `schema_to_config` can resolve it within the
one resource); Spec-1-valid AND QA-compilable:

```json
{
  "name": "rich",
  "path": "rich.csv",
  "schema": {
    "fields": [
      {"name": "id", "type": "string", "constraints": {"required": true, "unique": true}},
      {"name": "parent_id", "type": "string"},
      {"name": "score", "type": "number", "constraints": {"minimum": 0, "maximum": 1}},
      {"name": "grade", "type": "string", "constraints": {"enum": ["A", "B", "C"]}}
    ],
    "primaryKey": "id",
    "foreignKeys": [{"fields": "parent_id", "reference": {"resource": "", "fields": "id"}}],
    "missingValues": ["", "NA"]
  }
}
```

`science/fixtures/descriptor_contract/composite_fk.json` — Spec-1-VALID but a *documented
compiler-only failure* (`schema_to_config` rejects composite FKs):

```json
{
  "name": "composite",
  "path": "composite.csv",
  "schema": {
    "fields": [
      {"name": "a", "type": "string"},
      {"name": "b", "type": "string"}
    ],
    "foreignKeys": [{"fields": ["a", "b"], "reference": {"resource": "", "fields": ["a", "b"]}}]
  }
}
```

`science/fixtures/descriptor_contract/malformed_bound.json` — Spec-1-VALID (a `minimum` of
type `str` on a `number` field passes the model's bound *applicability* check) but the
second *documented compiler-only failure*: `_validate_bound_value` rejects a bound value
that is neither a number nor a parseable ISO date:

```json
{
  "name": "badbound",
  "path": "badbound.csv",
  "schema": {
    "fields": [
      {"name": "x", "type": "number", "constraints": {"minimum": "abc"}}
    ]
  }
}
```

- [ ] **Step 2: Write the failing science_tool-side test**

```python
# science/tests/test_descriptor_contract.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from science_tool.datasets.schema import ResourceDescriptor, package_consistency_issues

CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "descriptor_contract"


def _fixtures() -> list[Path]:
    files = sorted(CORPUS.glob("*.json"))
    assert files, f"no contract fixtures found in {CORPUS}"
    return files


@pytest.mark.parametrize("path", _fixtures(), ids=lambda p: p.name)
def test_fixture_is_spec1_valid(path: Path) -> None:
    descriptor = ResourceDescriptor.model_validate(json.loads(path.read_text()))
    # single-resource self-consistency (FK self-references resolve within the one resource)
    assert package_consistency_issues([descriptor]) == []
```

`parents[1]`: `tests/ -> science/`, so `science/fixtures/descriptor_contract`.

- [ ] **Step 3: Run the science_tool side**

Run: `cd science && .venv/bin/python -m pytest tests/test_descriptor_contract.py -q`
Expected: PASS (4 parametrized cases) — fix any fixture that fails Spec 1 before moving on.
(`malformed_bound.json` is Spec-1-valid, so it passes here; it only fails on the QA side.)

- [ ] **Step 4: Write the failing science_qa-side test**

```python
# science/qa/tests/test_descriptor_contract.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from science_qa.compile import CompileError, schema_to_config

CORPUS = Path(__file__).resolve().parents[2] / "fixtures" / "descriptor_contract"

# The ONLY reasons a Spec-1-valid descriptor may fail to compile (design §7 allow-list).
DOCUMENTED_COMPILER_ONLY = {
    "composite_fk.json": "composite foreignKey not supported",
    "malformed_bound.json": "bound value is neither a number nor a parseable ISO date",
}


def _fixtures() -> list[Path]:
    files = sorted(CORPUS.glob("*.json"))
    assert files, f"no contract fixtures found in {CORPUS}"
    return files


@pytest.mark.parametrize("path", _fixtures(), ids=lambda p: p.name)
def test_fixture_compiles_or_fails_for_documented_reason(path: Path) -> None:
    resource = json.loads(path.read_text())
    package = {"resources": [resource]}
    if path.name in DOCUMENTED_COMPILER_ONLY:
        expected = DOCUMENTED_COMPILER_ONLY[path.name]
        with pytest.raises(CompileError, match=expected):
            schema_to_config(resource, path.parent, package)
    else:
        cfg = schema_to_config(resource, path.parent, package)  # must not raise
        assert cfg is not None
```

`parents[2]`: `tests/ -> qa/ -> science/`, so `science/fixtures/descriptor_contract`.

- [ ] **Step 5: Run the science_qa side**

Run: `cd science/qa && .venv/bin/python -m pytest tests/test_descriptor_contract.py -q`
Expected: PASS (4 parametrized cases): `minimal` + `rich_single_fk` compile;
`composite_fk` + `malformed_bound` raise `CompileError`. If `rich_single_fk.json` fails to
compile, adjust the fixture to what the compiler supports (single-column self-FK), NOT the
allow-list.

- [ ] **Step 6: Commit**

```bash
git add science/fixtures/descriptor_contract/minimal.json \
        science/fixtures/descriptor_contract/rich_single_fk.json \
        science/fixtures/descriptor_contract/composite_fk.json \
        science/fixtures/descriptor_contract/malformed_bound.json \
        science/tests/test_descriptor_contract.py \
        science/qa/tests/test_descriptor_contract.py
git commit -m "test(infer-schema): two-sided descriptor consistency contract + shared corpus"
```

---

## Final verification (after all tasks)

- [ ] **Full module + CLI suite:** `cd science && .venv/bin/python -m pytest tests/test_infer_schema.py tests/test_infer_schema_cli.py tests/test_descriptor_contract.py -q` → all green.
- [ ] **science_qa contract side:** `cd science/qa && .venv/bin/python -m pytest tests/test_descriptor_contract.py -q` → green.
- [ ] **No regressions, science_tool:** `cd science && .venv/bin/python -m pytest -q` → baseline still passing.
- [ ] **No regressions, science_qa:** `cd science/qa && .venv/bin/python -m pytest -q` → baseline still passing (no `science_qa` source changed; only a new test added).
- [ ] **One-way dependency intact:** `rg -n '^\s*(import|from)\s.*science_tool' science/qa/src` → no import lines (docstring prose only).
- [ ] **Dogfood (manual, optional):** run `science datasets infer-schema ~/d/r/p3/package --resource drug_metadata` and confirm the diff shows `+ add` rows and the report lists recommendations without mutating the file.
```
