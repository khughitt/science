# Substrate Phase 3a — entities.yaml retirement visibility & inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `entities.yaml` aggregate-stub debt fully visible — a standing WARN gate for *lone* stubs plus a read-only triage report that buckets every aggregate row — without creating, deleting, or mutating any content.

**Architecture:** Three additive, non-destructive changes in the `science` framework, all reading the compiled model (§C2). (1) The loader captures row-level metadata for every aggregate entry *before* non-strict dedup can drop a shadowed entry's `Entity`. (2) A pure classifier buckets each aggregate owner row using that metadata plus the identity table. (3a) A conformance check WARNs lone stubs; (3b) a `science entities triage-aggregate` CLI command renders the classifier output. Spec: `~/d/science/docs/plans/2026-06-07-substrate-3a-entities-retirement-visibility-design.md`.

**Tech Stack:** Python 3.12, Pydantic v2, `click`, `pytest`. All commands run from `~/d/science/science`. Tests: `uv run --frozen pytest`. Lint: `uv run --frozen ruff check . && uv run --frozen ruff format --check .` (120-char line limit). Never use `pip`; always `uv`.

---

## Background the implementer needs

- **Why a loader change is required (the reviewed High finding).** Under the non-strict load that diagnostics use, a *shadowed* aggregate row's `IdentityDeclaration` is appended (`src/science_tool/graph/sources.py:406`) but its `Entity` is then skipped by the dedup guard (`sources.py:416-420`, the `continue`) because a real owner already won the id. Separately, `AggregateAdapter.load_raw` records the aggregate *file* as `Entity.file_path` and never surfaces the entry's inner `source_path` as an `Entity` field. So neither `has_real_owner` nor `source_path` can be read off the aggregate `Entity` — exactly the `shadow` bucket would be unclassifiable. Task 1 fixes this by capturing the metadata at the loader's emit point, where `raw` (with the inner `source_path`) and `kind` are still in scope.
- **Identity model shapes** (`src/science_tool/graph/identity_table.py`): `IdentityDeclaration` is a frozen dataclass with fields `canonical_id, participation_mode, owner_scope, adapter, source_ref, deprecated`. `IdentityTable.owners()` returns `dict[tuple[str, str], list[IdentityDeclaration]]` grouped by `(owner_scope, canonical_id)`; a group of size 1 is a lone owner, size ≥2 is a collision. `build_identity_table(sources)` builds it from `sources.identity_declarations`.
- **`AggregateAdapter`** (`src/science_tool/graph/storage_adapters/aggregate.py`): `name == "aggregate"`; its `SourceRef` always carries `line` (the entry index, asserted in `load_raw`). `classify_owner_scope("aggregate")` yields a deprecated owner, so its declarations have `adapter == "aggregate"` and `deprecated == True`.
- **`Result`** (`src/science_tool/validate/result.py`): dataclass `Result(severity, path, line, message, rule, task)`. `Severity.WARN`.
- **Fixture gotcha:** `AggregateAdapter` scans `knowledge/sources/<value>/`, where `<value>` is the *value* in the profiles map. Use `profiles: {local: local}` (or `knowledge_profiles: {local: local}`) so the value `local` resolves to `knowledge/sources/local/entities.yaml`. A markdown owner under `entities/<kind>/<slug>.md` is discovered regardless of `layout_version` (proven by the Phase 2b tests).
- **Which kinds load in a synthetic fixture:** the **core-registered** generic kinds include `concept`, `article`, `topic`, `question` (and `dataset` via its own schema) — these validate from a minimal aggregate entry (`canonical_id`, `kind`, `title`, `source_path`; `dataset` also needs `origin` + `access`). **`decision` and `latent` are NOT core** — they are local profile kinds a real project registers in `knowledge/sources/local/manifest.yaml`. An unregistered kind is skipped (`unknown_entity_kind`) and never reaches the identity table. So the synthetic tests exercise `decision`/`latent` rules only through the pure `_bucket` helper, never through the loader.
- **`article:` → `paper:` at load:** `canonical_paper_id` (`sources.py:675`) rewrites any `article:<X>` id to `paper:<X>` unconditionally (transition-window rename); the `kind` field is left as `"article"`. So a loaded article row keys by `paper:<X>` but still trips the `kind == "article"` external-ref rule.

---

## Task 1: Loader captures aggregate row-level metadata

**Files:**
- Modify: `src/science_tool/graph/sources.py` (add `AggregateRowMeta`; add `ProjectSources.aggregate_rows` field; init accumulator near line 275; capture in the aggregate branch near line 406; pass to constructor near line 554)
- Test: `tests/graph/test_aggregate_row_metadata.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/graph/test_aggregate_row_metadata.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo-project\nprofile: research\nprofiles: {local: local}\n"


def _write_project(root: Path, entries: list[dict]) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    agg = root / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "entities.yaml").write_text(yaml.safe_dump({"entities": entries}), encoding="utf-8")


def _write_dataset_md(root: Path, slug: str, ident: str) -> None:
    d = root / "entities" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(
        f'---\nid: "{ident}"\ntype: "dataset"\ntitle: "{ident}"\n'
        'origin: "external"\naccess:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )


def test_aggregate_rows_capture_lone_and_shadowed(tmp_path: Path) -> None:
    # The shadowed dataset's Entity is deduped away under non-strict load, but its
    # aggregate row metadata must STILL be captured (the High-finding fix).
    _write_dataset_md(tmp_path, "shadowed", "dataset:shadowed")
    _write_project(
        tmp_path,
        [
            {
                "canonical_id": "concept:coined",
                "kind": "concept",
                "title": "Coined",
                "source_path": "knowledge/sources/local/entities.yaml",
            },
            {
                "canonical_id": "dataset:shadowed",
                "kind": "dataset",
                "title": "Shadowed",
                "origin": "external",
                "access": {"level": "public", "verified": False},
                "source_path": "knowledge/sources/local/entities.yaml",
            },
        ],
    )
    sources = load_project_sources(
        tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False
    )
    by_id = {m.canonical_id: m for m in sources.aggregate_rows}
    assert set(by_id) == {"concept:coined", "dataset:shadowed"}
    assert by_id["concept:coined"].kind == "concept"
    assert by_id["concept:coined"].source_path == "knowledge/sources/local/entities.yaml"
    assert by_id["concept:coined"].path == "knowledge/sources/local/entities.yaml"
    assert by_id["dataset:shadowed"].line is not None


def test_non_string_source_path_normalized_to_none(tmp_path: Path) -> None:
    # source_path is extra metadata the entity schema ignores, so a malformed
    # (non-string) value survives into `raw`. Normalize it to None at capture so the
    # read-only report cannot crash on `.startswith()` downstream.
    _write_project(
        tmp_path,
        [{"canonical_id": "concept:weird", "kind": "concept", "title": "Weird", "source_path": 123}],
    )
    sources = load_project_sources(
        tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False
    )
    by_id = {m.canonical_id: m for m in sources.aggregate_rows}
    assert by_id["concept:weird"].source_path is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/graph/test_aggregate_row_metadata.py -v`
Expected: FAIL — `AttributeError: 'ProjectSources' object has no attribute 'aggregate_rows'`.

- [ ] **Step 3: Add the `AggregateRowMeta` dataclass**

In `src/science_tool/graph/sources.py`, ensure `from dataclasses import dataclass` is imported (add it if absent). Define this class immediately **above** the `class ProjectSources(BaseModel):` definition (near line 141):

```python
@dataclass(frozen=True, slots=True)
class AggregateRowMeta:
    """Row-level triage metadata for one aggregate (`entities.yaml`) entry.

    Captured at load time — before non-strict dedup can drop a shadowed entry's
    Entity (sources.py emit point) — so the §B5 triage classifier can bucket every
    aggregate row. Joined to its IdentityDeclaration by (path, line), which
    AggregateAdapter always populates.
    """

    path: str
    line: int
    canonical_id: str
    kind: str
    source_path: str | None
```

- [ ] **Step 4: Add the `ProjectSources.aggregate_rows` field**

In `class ProjectSources(BaseModel)`, immediately after the `identity_declarations: list[IdentityDeclaration] = Field(default_factory=list)` line (near line 163), add:

```python
    # §B5: row-level metadata for every aggregate (entities.yaml) owner row, captured
    # before non-strict dedup so shadowed rows (whose Entity is dropped) stay triable.
    aggregate_rows: list[AggregateRowMeta] = Field(default_factory=list)
```

- [ ] **Step 5: Initialise the accumulator**

In `load_project_sources`, next to `identity_declarations: list[IdentityDeclaration] = []` (near line 275), add:

```python
    aggregate_rows: list[AggregateRowMeta] = []
```

- [ ] **Step 6: Capture metadata in the aggregate branch**

In the loop, immediately **after** the `identity_declarations.append(IdentityDeclaration(...))` block (the append that ends near line 415) and **before** the `existing = identity_table.get(entity.canonical_id)` line (near line 416), insert:

```python
                if adapter.name == "aggregate":
                    assert ref.line is not None  # AggregateAdapter always sets the entry index
                    sp_raw = raw.get("source_path")
                    aggregate_rows.append(
                        AggregateRowMeta(
                            path=ref.path,
                            line=ref.line,
                            canonical_id=entity.canonical_id,
                            kind=kind,
                            # source_path is unschema'd extra metadata; normalize a
                            # malformed (non-string) value to None so the report can't crash.
                            source_path=sp_raw if isinstance(sp_raw, str) else None,
                        )
                    )
```

This runs for both lone and shadowed aggregate rows, because it precedes the `continue` that the dedup guard takes for a shadowed row.

- [ ] **Step 7: Pass `aggregate_rows` to the constructor**

In the `return ProjectSources(` call (near line 554), add a line alongside `identity_declarations=identity_declarations,`:

```python
        aggregate_rows=aggregate_rows,
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/graph/test_aggregate_row_metadata.py -v`
Expected: PASS.

- [ ] **Step 9: Run the full suite + lint to confirm no regression**

Run: `cd ~/d/science/science && uv run --frozen pytest -q && uv run --frozen ruff check src/science_tool/graph/sources.py tests/graph/test_aggregate_row_metadata.py && uv run --frozen ruff format --check src/science_tool/graph/sources.py tests/graph/test_aggregate_row_metadata.py`
Expected: all pass; ruff clean.

- [ ] **Step 10: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/sources.py science/tests/graph/test_aggregate_row_metadata.py
git commit -m "feat(substrate-3a): capture aggregate row metadata at load (§B5 prerequisite)"
```

---

## Task 2: Aggregate triage classifier

**Files:**
- Create: `src/science_tool/graph/aggregate_triage.py`
- Test: `tests/graph/test_aggregate_triage.py`

- [ ] **Step 1: Write the failing test**

Create `tests/graph/test_aggregate_triage.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.graph.aggregate_triage import AggregateBucket, _bucket, classify_aggregate_rows
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo-project\nprofile: research\nprofiles: {local: local}\n"
_AGG = "knowledge/sources/local/entities.yaml"


# --- Pure rule-matrix unit tests (no loading, no kind registration) ----------
# `decision`/`latent` are LOCAL profile kinds (not core-registered), so they would
# be skipped by the synthetic loader. Test the full six-bucket matrix + precedence
# directly on the pure _bucket helper, which takes (kind, source_path,
# has_real_owner, self_sourced) and needs no project on disk.
@pytest.mark.parametrize(
    "kind,source_path,has_real_owner,self_sourced,expected",
    [
        ("concept", _AGG, False, True, AggregateBucket.COINED),
        ("latent", None, False, True, AggregateBucket.COINED),
        ("decision", "knowledge/x", False, True, AggregateBucket.COINED),  # self-sourced decision
        ("decision", "core/decisions.md", False, False, AggregateBucket.DECISION_LOG),
        ("article", _AGG, False, True, AggregateBucket.EXTERNAL_REF),
        ("concept", "refs.bib", False, False, AggregateBucket.EXTERNAL_REF),  # .bib source
        ("decision", "migration:audit", False, False, AggregateBucket.CRUFT),
        ("concept", "migration:audit", False, True, AggregateBucket.CRUFT),  # cruft before coined
        ("question", None, False, True, AggregateBucket.AMBIGUOUS),
        ("topic", _AGG, False, True, AggregateBucket.AMBIGUOUS),
        ("concept", _AGG, True, True, AggregateBucket.SHADOW),  # shadow wins over coined
        ("decision", "core/decisions.md", True, False, AggregateBucket.SHADOW),  # shadow before decision-log
        ("decision", "migration:audit", True, False, AggregateBucket.SHADOW),  # shadow before cruft
    ],
)
def test_bucket_rule_matrix(kind, source_path, has_real_owner, self_sourced, expected) -> None:
    bucket, evidence = _bucket(kind, source_path, has_real_owner, self_sourced)
    assert bucket is expected
    assert evidence  # every row carries a non-empty basis


# --- Integration tests (load -> classify plumbing; CORE kinds only) ----------
def _write_project(root: Path, entries: list[dict]) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    agg = root / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "entities.yaml").write_text(yaml.safe_dump({"entities": entries}), encoding="utf-8")


def _write_dataset_md(root: Path, slug: str, ident: str) -> None:
    d = root / "entities" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(
        f'---\nid: "{ident}"\ntype: "dataset"\ntitle: "{ident}"\n'
        'origin: "external"\naccess:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )


def _lightweight(cid: str, kind: str, source_path: str) -> dict:
    return {"canonical_id": cid, "kind": kind, "title": cid, "source_path": source_path}


def _dataset_stub(cid: str, source_path: str) -> dict:
    return {
        "canonical_id": cid,
        "kind": "dataset",
        "title": cid,
        "origin": "external",
        "access": {"level": "public", "verified": False},
        "source_path": source_path,
    }


def _classify(root: Path):
    sources = load_project_sources(
        root, include_commons=False, strict_core_schema=False, strict_identity=False
    )
    return {t.canonical_id: t for t in classify_aggregate_rows(sources)}


def test_integration_core_kinds(tmp_path: Path) -> None:
    # Uses only core-registered kinds. `article:lit` is canonicalized to `paper:lit`
    # at load (the transition-window paper rename), while `kind` stays "article" — so
    # the row keys by paper:lit but still buckets external-ref.
    _write_dataset_md(tmp_path, "shadowed", "dataset:shadowed")
    _write_project(
        tmp_path,
        [
            _dataset_stub("dataset:shadowed", _AGG),
            _lightweight("concept:coined", "concept", _AGG),
            _lightweight("article:lit", "article", _AGG),
        ],
    )
    by_id = _classify(tmp_path)
    assert by_id["dataset:shadowed"].bucket is AggregateBucket.SHADOW
    assert by_id["dataset:shadowed"].has_real_owner is True
    assert by_id["concept:coined"].bucket is AggregateBucket.COINED
    assert by_id["concept:coined"].has_real_owner is False
    assert "article:lit" not in by_id  # canonicalized away
    assert by_id["paper:lit"].bucket is AggregateBucket.EXTERNAL_REF
    assert by_id["paper:lit"].kind == "article"


def test_empty_source_path_is_self_sourced(tmp_path: Path) -> None:
    # An explicit empty source_path must count as self-sourced (design): a coinable
    # kind with source_path "" buckets as coined, not ambiguous.
    _write_project(tmp_path, [_lightweight("concept:empty", "concept", "")])
    by_id = _classify(tmp_path)
    assert by_id["concept:empty"].bucket is AggregateBucket.COINED
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/graph/test_aggregate_triage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.graph.aggregate_triage'`.

- [ ] **Step 3: Write the classifier**

Create `src/science_tool/graph/aggregate_triage.py`:

```python
"""Triage classifier for aggregate (`entities.yaml`) owner rows (design §B5, 3a).

Reads the compiled model only — the IdentityTable and the row-level
`ProjectSources.aggregate_rows` metadata produced by load_project_sources — and
buckets every aggregate owner row by deterministic, evidence-bearing rules. The
output is read-only decision support feeding the Phase 3b `--apply`; the rules are
heuristics (design §D5: the concept-vs-tag boundary is judgment, not algorithm),
so each row carries the basis for its bucket.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from science_tool.graph.identity_table import build_identity_table

if TYPE_CHECKING:
    from science_tool.graph.sources import ProjectSources


class AggregateBucket(str, Enum):
    SHADOW = "shadow"
    COINED = "coined"
    DECISION_LOG = "decision-log"
    EXTERNAL_REF = "external-ref"
    CRUFT = "cruft"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class AggregateRowTriage:
    canonical_id: str
    kind: str
    source_path: str | None
    has_real_owner: bool
    bucket: AggregateBucket
    evidence: str


_COINABLE_KINDS = frozenset({"concept", "latent"})


def _bucket(
    kind: str, source_path: str | None, has_real_owner: bool, self_sourced: bool
) -> tuple[AggregateBucket, str]:
    if has_real_owner:
        return AggregateBucket.SHADOW, "a non-aggregate owner of this id exists -> shadow"
    if source_path is not None and source_path.startswith("migration:"):
        return AggregateBucket.CRUFT, f"source_path {source_path!r} is a migration artifact -> cruft"
    if kind == "decision" and source_path == "core/decisions.md":
        return AggregateBucket.DECISION_LOG, "decision sourced from core/decisions.md -> decision-log"
    if kind == "article" or (source_path is not None and source_path.endswith(".bib")):
        return AggregateBucket.EXTERNAL_REF, f"kind={kind} / bibliographic source -> external-ref"
    if self_sourced and (kind in _COINABLE_KINDS or kind == "decision"):
        return AggregateBucket.COINED, f"self-sourced coinable kind={kind} -> coined"
    return AggregateBucket.AMBIGUOUS, f"self-sourced kind={kind}, no rule matched -> ambiguous"


def classify_aggregate_rows(sources: "ProjectSources") -> list[AggregateRowTriage]:
    """Bucket every aggregate owner row, sorted by (bucket, canonical_id)."""
    table = build_identity_table(sources)
    meta_by_ref = {(m.path, m.line): m for m in sources.aggregate_rows}

    triaged: list[AggregateRowTriage] = []
    for (_scope, canonical_id), rows in table.owners().items():
        agg_rows = [r for r in rows if r.adapter == "aggregate"]
        if not agg_rows:
            continue
        has_real_owner = any(r.adapter != "aggregate" and not r.deprecated for r in rows)
        for decl in agg_rows:
            ref = decl.source_ref
            meta = meta_by_ref.get((ref.path, ref.line)) if ref is not None else None
            kind = meta.kind if meta is not None else canonical_id.split(":", 1)[0]
            source_path = meta.source_path if meta is not None else None
            agg_path = ref.path if ref is not None else None
            # Absent OR empty source_path counts as self-sourced (design §5.2).
            self_sourced = source_path in (None, "") or source_path == agg_path
            bucket, evidence = _bucket(kind, source_path, has_real_owner, self_sourced)
            triaged.append(
                AggregateRowTriage(canonical_id, kind, source_path, has_real_owner, bucket, evidence)
            )
    triaged.sort(key=lambda t: (t.bucket.value, t.canonical_id))
    return triaged
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/graph/test_aggregate_triage.py -v`
Expected: PASS (the parametrized `_bucket` matrix + both integration tests).

- [ ] **Step 5: Lint**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/graph/aggregate_triage.py tests/graph/test_aggregate_triage.py && uv run --frozen ruff format --check src/science_tool/graph/aggregate_triage.py tests/graph/test_aggregate_triage.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/aggregate_triage.py science/tests/graph/test_aggregate_triage.py
git commit -m "feat(substrate-3a): rule-based aggregate-row triage classifier (§B5)"
```

---

## Task 3: Lone-aggregate-stub conformance check

**Files:**
- Create: `src/science_tool/validate/checks/aggregate_stub.py`
- Modify: `src/science_tool/validate/checks/__init__.py` (add `"aggregate_stub"` to `CANONICAL_CHECK_MODULES`, immediately after `"identity_collision"`)
- Test: `tests/validate/test_checks_aggregate_stub.py`

- [ ] **Step 1: Write the failing test**

Create `tests/validate/test_checks_aggregate_stub.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.validate.checks.aggregate_stub import check_lone_aggregate_stub
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_MANIFEST = "name: demo-project\nprofile: research\nprofiles: {local: local}\n"


def _ctx(root: Path) -> ValidateContext:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write_aggregate(root: Path, entries: list[dict]) -> None:
    agg = root / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "entities.yaml").write_text(yaml.safe_dump({"entities": entries}), encoding="utf-8")


def _write_dataset_md(root: Path, slug: str, ident: str) -> None:
    d = root / "entities" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(
        f'---\nid: "{ident}"\ntype: "dataset"\ntitle: "{ident}"\n'
        'origin: "external"\naccess:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )


def test_lone_stub_warns(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    _write_aggregate(
        tmp_path,
        [{"canonical_id": "concept:lonely", "kind": "concept", "title": "Lonely",
          "source_path": "knowledge/sources/local/entities.yaml"}],
    )
    results = list(check_lone_aggregate_stub(ctx))
    assert len(results) == 1
    assert results[0].severity is Severity.WARN
    assert results[0].rule == "lone-aggregate-stub"
    assert "concept:lonely" in results[0].message


def test_shadowed_stub_not_flagged_here(tmp_path: Path) -> None:
    # A shadowed stub is a collision -> forbidden-second-declaration's surface, not this
    # check's (single-surface principle).
    ctx = _ctx(tmp_path)
    _write_dataset_md(tmp_path, "shadowed", "dataset:shadowed")
    _write_aggregate(
        tmp_path,
        [{"canonical_id": "dataset:shadowed", "kind": "dataset", "title": "Shadowed",
          "origin": "external", "access": {"level": "public", "verified": False},
          "source_path": "knowledge/sources/local/entities.yaml"}],
    )
    assert list(check_lone_aggregate_stub(ctx)) == []


def test_real_owner_no_aggregate_not_flagged(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    _write_dataset_md(tmp_path, "real", "dataset:real")
    assert list(check_lone_aggregate_stub(ctx)) == []


def test_check_registered_via_canonical_loader() -> None:
    # Real wiring test: clear the registry, drop the cached module so
    # _load_canonical_checks() must re-import it from CANONICAL_CHECK_MODULES, and
    # assert the @Check ran. Importing the check at module top would register it even
    # if the tuple entry were missing -- this proves the tuple entry, not the import.
    import sys

    from science_tool.validate.checks import (
        CANONICAL_CHECKS,
        _load_canonical_checks,
        clear_checks_for_tests,
    )

    original_entries = list(CANONICAL_CHECKS)
    module_name = "science_tool.validate.checks.aggregate_stub"
    original_module = sys.modules.get(module_name)
    try:
        clear_checks_for_tests()
        sys.modules.pop(module_name, None)
        _load_canonical_checks()
        entries = [e for e in CANONICAL_CHECKS if e.fn.__name__ == "check_lone_aggregate_stub"]
        assert len(entries) == 1
        assert entries[0].order == 51
    finally:
        CANONICAL_CHECKS[:] = original_entries
        if original_module is None:
            sys.modules.pop(module_name, None)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_aggregate_stub.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.validate.checks.aggregate_stub'`.

- [ ] **Step 3: Write the check**

Create `src/science_tool/validate/checks/aggregate_stub.py`:

```python
"""Conformance check: a lone aggregate (`entities.yaml`) stub (design §B5).

A deprecated aggregate owner row that is the SOLE owner of its id is fileless
rollout debt: it sole-sources an entity §B5 will retire to an owner file (or
delete). It is not a collision, so the forbidden-second-declaration check (which
fires only when a second owner shadows a real one) never surfaces it. This check
makes the lone-stub debt visible. WARN unconditionally: the retirement tool (3b
`--apply`) does not exist yet, so the debt must stay visible without blocking
(design §C4 -- a half-rolled project is never bricked). The richer per-bucket
inventory lives in `science entities triage-aggregate`; this check is only the
standing gate for the lone-stub subset.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.graph.identity_table import build_identity_table
from science_tool.graph.sources import load_project_sources
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


@Check(section="lone aggregate stub (entities.yaml retirement, design §B5)", order=51)
def check_lone_aggregate_stub(ctx: ValidateContext) -> Iterator[Result]:
    # Non-strict, no commons, lenient core schema -- matching the identity-collision
    # check: a diagnostic must not abort on the condition it reports, and a malformed
    # row must not take the visibility tool offline.
    sources = load_project_sources(
        ctx.project_root,
        include_commons=False,
        strict_core_schema=False,
        strict_identity=False,
    )
    table = build_identity_table(sources)
    for (_scope, canonical_id), rows in sorted(table.owners().items()):
        if len(rows) != 1:
            continue  # >=2 owners is a collision -> forbidden-second-declaration's surface
        (row,) = rows
        if row.adapter != "aggregate" or not row.deprecated:
            continue
        path = Path(row.source_ref.path) if row.source_ref else None
        yield Result(
            Severity.WARN,
            path,
            None,
            f"{canonical_id}: lone aggregate stub (entities.yaml) sole-sources this "
            "entity (design §B5) -- retire it to an owner file or delete it via "
            "`science entities triage-aggregate` + Phase 3b --apply; carried as WARN "
            "until then.",
            "lone-aggregate-stub",
            None,
        )
```

- [ ] **Step 4: Register the check module**

In `src/science_tool/validate/checks/__init__.py`, in the `CANONICAL_CHECK_MODULES` tuple, add `"aggregate_stub"` on its own line immediately after `"identity_collision",`:

```python
    "identity_collision",
    "aggregate_stub",
    "variant_identity",
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_aggregate_stub.py -v`
Expected: PASS (all four tests).

- [ ] **Step 6: Lint**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/validate/checks/aggregate_stub.py src/science_tool/validate/checks/__init__.py tests/validate/test_checks_aggregate_stub.py && uv run --frozen ruff format --check src/science_tool/validate/checks/aggregate_stub.py tests/validate/test_checks_aggregate_stub.py`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/validate/checks/aggregate_stub.py science/src/science_tool/validate/checks/__init__.py science/tests/validate/test_checks_aggregate_stub.py
git commit -m "feat(substrate-3a): WARN on lone aggregate stubs (entities.yaml, §B5)"
```

---

## Task 4: `science entities triage-aggregate` CLI report

**Files:**
- Modify: `src/science_tool/cli.py` (add the `triage-aggregate` command in the existing `entities` group, after `entities_migrate_command`)
- Test: `tests/test_cli_entities_triage_aggregate.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_entities_triage_aggregate.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main

_MANIFEST = "name: demo-project\nprofile: research\nprofiles: {local: local}\n"


def _write_project(root: Path) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    agg = root / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    entries = [
        {"canonical_id": "concept:coined", "kind": "concept", "title": "Coined",
         "source_path": "knowledge/sources/local/entities.yaml"},
        # `article:lit` is canonicalized to `paper:lit` at load (kind stays "article").
        {"canonical_id": "article:lit", "kind": "article", "title": "Lit",
         "source_path": "knowledge/sources/local/entities.yaml"},
    ]
    (agg / "entities.yaml").write_text(yaml.safe_dump({"entities": entries}), encoding="utf-8")


def test_triage_aggregate_json(tmp_path: Path) -> None:
    _write_project(tmp_path)
    result = CliRunner().invoke(
        main,
        ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    by_id = {row["canonical_id"]: row for row in payload}
    assert by_id["concept:coined"]["bucket"] == "coined"
    assert by_id["paper:lit"]["bucket"] == "external-ref"  # article: -> paper: at load


def test_triage_aggregate_text(tmp_path: Path) -> None:
    _write_project(tmp_path)
    result = CliRunner().invoke(
        main, ["entities", "triage-aggregate", "--project-root", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "coined" in result.output
    assert "external-ref" in result.output
    assert "concept:coined" in result.output
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_cli_entities_triage_aggregate.py -v`
Expected: FAIL — `No such command 'triage-aggregate'` (non-zero exit).

- [ ] **Step 3: Add the CLI command**

In `src/science_tool/cli.py`, immediately after the `entities_migrate_command` function (the `@entities_group.command("migrate")` block near line 274), add:

```python
@entities_group.command("triage-aggregate")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def entities_triage_aggregate_command(project_root: Path, output_format: str) -> None:
    """Triage aggregate (entities.yaml) rows for §B5 retirement (read-only)."""
    from collections import Counter

    from science_tool.graph.aggregate_triage import classify_aggregate_rows
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(
        project_root, include_commons=False, strict_core_schema=False, strict_identity=False
    )
    rows = classify_aggregate_rows(sources)
    if output_format == "json":
        payload = [
            {
                "canonical_id": r.canonical_id,
                "kind": r.kind,
                "source_path": r.source_path,
                "has_real_owner": r.has_real_owner,
                "bucket": r.bucket.value,
                "evidence": r.evidence,
            }
            for r in rows
        ]
        click.echo(json.dumps(payload, indent=2))
        return
    counts = Counter(r.bucket.value for r in rows)
    click.echo(f"{len(rows)} aggregate rows:")
    for bucket in sorted(counts):
        click.echo(f"  {bucket}: {counts[bucket]}")
    for r in rows:
        click.echo(
            f"  [{r.bucket.value}] {r.canonical_id} "
            f"(kind={r.kind}, source_path={r.source_path}) -- {r.evidence}"
        )
```

(`json` and `click` are already imported at the top of `cli.py`; the local `Counter` import keeps the change self-contained.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_cli_entities_triage_aggregate.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Lint**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/cli.py tests/test_cli_entities_triage_aggregate.py && uv run --frozen ruff format --check tests/test_cli_entities_triage_aggregate.py`
Expected: clean.

- [ ] **Step 6: Full suite + commit**

```bash
cd ~/d/science/science && uv run --frozen pytest -q
cd ~/d/science && git add science/src/science_tool/cli.py science/tests/test_cli_entities_triage_aggregate.py
git commit -m "feat(substrate-3a): science entities triage-aggregate read-only report (§B5)"
```

Expected: full suite green.

---

## Final verification (after all tasks)

- [ ] **Run the complete suite and lint the whole tree**

Run: `cd ~/d/science/science && uv run --frozen pytest -q && uv run --frozen ruff check . && uv run --frozen ruff format --check .`
Expected: all pass. (If `ruff format --check .` reports drift in `src/science_tool/commons/datapackage.py`, that is the known pre-existing drift from before Phase 2c — not introduced here; leave it alone.)

- [ ] **Smoke the new command against MM30** (manual sanity, read-only — does not modify anything):

Run: `cd ~/d/science/science && uv run --frozen science entities triage-aggregate --project-root ~/d/cancer/cancer-types/multiple-myeloma --format json | head -40`
Expected: a JSON array bucketing MM30's 176 aggregate rows (≈76 external-ref, ≈26 coined, ≈16 decision-log, shadows, ≈26 cruft, etc.). Exit 0. Confirms the tool runs end-to-end on the real project without mutating it.

---

## Self-review notes (for the executor)

- **Spec coverage:** Task 1 ↔ spec §3.1 (loader prerequisite + `AggregateRowMeta`); Task 2 ↔ spec §5.1–5.2 (classifier + six buckets); Task 3 ↔ spec §4 (lone-stub check, WARN unconditional, order 51, registration test); Task 4 ↔ spec §5.3 (read-only CLI, text + json, exit 0). The single-surface split (spec §3.2) is enforced by Task 3 skipping `len(rows) != 1` and verified by `test_shadowed_stub_not_flagged_here`. Load flags (spec Finding 2) are pinned in Tasks 3 and 4 and the test helper in Task 2.
- **Type consistency:** `AggregateRowMeta(path, line, canonical_id, kind, source_path)` is produced in Task 1 and joined by `(path, line)` in Task 2. `AggregateRowTriage(canonical_id, kind, source_path, has_real_owner, bucket, evidence)` and `AggregateBucket` values (`shadow/coined/decision-log/external-ref/cruft/ambiguous`) are consumed unchanged by Task 4's JSON/text rendering. `check_lone_aggregate_stub` order is `51` in both the decorator and the registration test.
- **Fixture realities baked into the tests (review round 2):** `decision`/`latent` are **local** profile kinds, not core-registered, so the synthetic loader would skip them — the full six-bucket matrix is therefore unit-tested on the pure `_bucket` helper (no loading), and the load→classify integration tests use only core kinds (`concept`, `dataset`, `article`). `article:<X>` is canonicalized to `paper:<X>` at load (`sources.py:675`, transition-window paper rename) while `kind` stays `"article"`, so the integration/CLI tests key external-ref rows by `paper:lit`. Two normalizations guard the report: Task 1 coerces a non-string `source_path` to `None` at capture; Task 2 treats `source_path in (None, "")` (and `== agg_path`) as self-sourced. Both have dedicated tests.
- **Non-destructive guarantee:** no task writes, deletes, or mutates project entities; the only writes are the new source/test files and the loader/CLI/check edits.
