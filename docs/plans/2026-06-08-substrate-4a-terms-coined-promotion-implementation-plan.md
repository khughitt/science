# Substrate Phase 4a — terms.yaml coined-concept promotion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing 3b/3c aggregate-retirement executor to also promote the coined `concept` rows in `knowledge/sources/<profile>/terms.yaml` to owned `entities/concepts/<slug>.md` files whose body preserves the row's `description`, leaving everything else (ambiguous rows, external-refs, single-type aggregates) untouched.

**Architecture:** All changes are localized to `graph/aggregate_retire.py` plus a small public-API promotion in `graph/storage_adapters/aggregate.py` and two new fields on `AggregateRowTriage` in `graph/aggregate_triage.py`. The 3a triage classifier already classifies `terms.yaml` rows (no firewall there); the executor is the only thing that excludes them. Two non-trivial catches make this more than a one-line change: `terms.yaml`'s YAML root key is `terms:` (not `entities:`), and its rows use `id`/inferred-`kind` (not explicit `canonical_id`/`kind`). The latter is resolved §C2-style: take row identity from the compiled triage/meta, take only authoring content (`title`/`description`/`profile`) from the raw row.

**Tech Stack:** Python 3.12+, `pytest`, `pyyaml`, `uv` (never `pip`). Run tests from `~/d/science/science`. Reference design: `~/d/science/docs/plans/2026-06-08-substrate-4a-terms-coined-promotion-design.md`.

---

## Conventions (read once)

- **Working dir for all commands:** `~/d/science/science` (the package root; `pyproject.toml` lives here).
- **Run a single test:** `uv run --frozen pytest tests/graph/test_FILE.py::test_NAME -v`
- **Run the touched test files:** `uv run --frozen pytest tests/graph/ -q`
- **Lint a touched file:** `uv run --frozen ruff check src/science_tool/graph/aggregate_retire.py && uv run --frozen ruff format --check src/science_tool/graph/aggregate_retire.py` (120-char lines).
- **Commit messages:** prefix `feat(substrate-4a):` / `test(substrate-4a):` / `refactor(substrate-4a):`. **No `Co-Authored-By` trailer.**
- **Branch:** create `substrate-4a-terms-coined` off `main` before Task 1 (see Task 0).
- The executor under change is `science/src/science_tool/graph/aggregate_retire.py`. Current relevant line anchors (will shift as you edit): firewall `:124`, helpers `_STUB_BODY`/`_REQUIRED_FIELDS`/`_read_entries`/`_owner_text`/`_rewrite_aggregate` `:176`–`:208`, promote loop `:231`–`:261`, planner `plan_retirement` `:100`–`:162`.

---

## Task 0: Branch

- [ ] **Step 1: Create the working branch**

```bash
cd ~/d/science
git checkout main
git checkout -b substrate-4a-terms-coined
git log --oneline -1   # expect 46888811 (4a design doc) at or near HEAD
```

---

## Task 1: Public multi-type-aggregate root-key API

Promote the adapter's private `_MULTI_TYPE_FILES` to a public constant + helper so the executor can import the single source of truth for which files are multi-type aggregates and what their YAML root keys are.

**Files:**
- Modify: `science/src/science_tool/graph/storage_adapters/aggregate.py` (constant `:36`, usage `:112`)
- Test: `science/tests/graph/test_aggregate_multi_type_api.py` (create)

- [ ] **Step 1: Write the failing test**

Create `science/tests/graph/test_aggregate_multi_type_api.py`:

```python
from __future__ import annotations

from science_tool.graph.storage_adapters.aggregate import (
    MULTI_TYPE_AGGREGATE_ROOT_KEYS,
    multi_type_root_key,
)


def test_root_keys_map_both_multi_type_files() -> None:
    assert MULTI_TYPE_AGGREGATE_ROOT_KEYS == {"entities.yaml": "entities", "terms.yaml": "terms"}


def test_helper_returns_root_key_for_known_files() -> None:
    assert multi_type_root_key("entities.yaml") == "entities"
    assert multi_type_root_key("terms.yaml") == "terms"


def test_helper_returns_none_for_single_type_or_unknown() -> None:
    assert multi_type_root_key("topics.json") is None
    assert multi_type_root_key("datasets.yaml") is None
    assert multi_type_root_key("") is None
```

- [ ] **Step 2: Run it and verify it fails**

Run: `uv run --frozen pytest tests/graph/test_aggregate_multi_type_api.py -v`
Expected: FAIL with `ImportError: cannot import name 'MULTI_TYPE_AGGREGATE_ROOT_KEYS'`.

- [ ] **Step 3: Implement — rename the constant and add the helper**

In `science/src/science_tool/graph/storage_adapters/aggregate.py`, rename `_MULTI_TYPE_FILES` to a public constant and add the helper directly below it. Current code (`:36`):

```python
_MULTI_TYPE_FILES = {
    "entities.yaml": "entities",
    "terms.yaml": "terms",
}
```

Replace with:

```python
MULTI_TYPE_AGGREGATE_ROOT_KEYS = {
    "entities.yaml": "entities",
    "terms.yaml": "terms",
}


def multi_type_root_key(filename: str) -> str | None:
    """YAML root key for a multi-type aggregate file (`entities.yaml`/`terms.yaml`), or None.

    The single source of truth for which aggregate files carry multiple entity
    types and under which top-level key their rows live. Consumed by the
    retirement executor so it never re-derives this mapping.
    """
    return MULTI_TYPE_AGGREGATE_ROOT_KEYS.get(filename)
```

- [ ] **Step 4: Update the adapter's internal use**

In the same file, the discover loop (`:112`) currently reads:

```python
            items = data.get(_MULTI_TYPE_FILES[path.name]) or []
```

Change to:

```python
            items = data.get(MULTI_TYPE_AGGREGATE_ROOT_KEYS[path.name]) or []
```

Also update the loop header that iterates the mapping (a few lines above `:112`, currently `for file_name, root_key in _MULTI_TYPE_FILES.items():`) to iterate `MULTI_TYPE_AGGREGATE_ROOT_KEYS.items()`. Grep to be sure no `_MULTI_TYPE_FILES` reference remains:

```bash
grep -rn "_MULTI_TYPE_FILES" science/src/   # expect no matches
```

- [ ] **Step 5: Run the test + adapter regressions**

Run:
```bash
uv run --frozen pytest tests/graph/test_aggregate_multi_type_api.py -v
uv run --frozen pytest tests/graph/ -q -k "aggregate or sources or triage"
```
Expected: new file PASS; existing aggregate/sources/triage tests still PASS.

- [ ] **Step 6: Lint + commit**

```bash
uv run --frozen ruff check src/science_tool/graph/storage_adapters/aggregate.py tests/graph/test_aggregate_multi_type_api.py
uv run --frozen ruff format --check src/science_tool/graph/storage_adapters/aggregate.py tests/graph/test_aggregate_multi_type_api.py
git add src/science_tool/graph/storage_adapters/aggregate.py tests/graph/test_aggregate_multi_type_api.py
git commit -m "feat(substrate-4a): public MULTI_TYPE_AGGREGATE_ROOT_KEYS + multi_type_root_key()"
```

---

## Task 2: `AggregateRowTriage` carries its `(path, line)` locator

Add the row-locating fields the planner needs to join precisely across two files. The classifier already has them via `decl.source_ref`.

**Files:**
- Modify: `science/src/science_tool/graph/aggregate_triage.py` (dataclass `:32`, classifier construction `:81`)
- Modify: `science/tests/graph/test_aggregate_retire_apply.py` (two hand-built triages `:84`, `:141`)
- Test: `science/tests/graph/test_triage_row_locators.py` (create)

- [ ] **Step 1: Write the failing test**

Create `science/tests/graph/test_triage_row_locators.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.aggregate_triage import classify_aggregate_rows
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"


def test_classified_row_carries_path_and_line(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    agg = tmp_path / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {"canonical_id": "concept:a", "kind": "concept", "title": "A",
                     "source_path": "knowledge/sources/local/entities.yaml"},
                    {"canonical_id": "concept:b", "kind": "concept", "title": "B",
                     "source_path": "knowledge/sources/local/entities.yaml"},
                ]
            }
        ),
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    rows = {t.canonical_id: t for t in classify_aggregate_rows(sources)}
    assert rows["concept:a"].path == "knowledge/sources/local/entities.yaml"
    assert rows["concept:b"].path == "knowledge/sources/local/entities.yaml"
    # Distinct rows have distinct line indices; both are non-None ints.
    assert isinstance(rows["concept:a"].line, int)
    assert isinstance(rows["concept:b"].line, int)
    assert rows["concept:a"].line != rows["concept:b"].line
```

- [ ] **Step 2: Run it and verify it fails**

Run: `uv run --frozen pytest tests/graph/test_triage_row_locators.py -v`
Expected: FAIL with `AttributeError: 'AggregateRowTriage' object has no attribute 'path'`.

- [ ] **Step 3: Add the fields to the dataclass**

In `science/src/science_tool/graph/aggregate_triage.py`, the dataclass (`:32`) is:

```python
@dataclass(frozen=True, slots=True)
class AggregateRowTriage:
    canonical_id: str
    kind: str
    source_path: str | None
    has_real_owner: bool
    bucket: AggregateBucket
    evidence: str
```

Append two required fields (the aggregate file path and the row index within it):

```python
@dataclass(frozen=True, slots=True)
class AggregateRowTriage:
    canonical_id: str
    kind: str
    source_path: str | None
    has_real_owner: bool
    bucket: AggregateBucket
    evidence: str
    path: str | None  # aggregate file (entities.yaml/terms.yaml), project-root-relative
    line: int | None  # row index within that file
```

- [ ] **Step 4: Populate them in the classifier**

In the same file, the classifier loop already computes `ref` and `agg_path`. Add `ref_line` and pass both to the constructor. Current loop body (`:72`–`:81`):

```python
        for decl in agg_rows:
            ref = decl.source_ref
            meta = meta_by_ref.get((ref.path, ref.line)) if ref is not None else None
            kind = meta.kind if meta is not None else canonical_id.split(":", 1)[0]
            source_path = meta.source_path if meta is not None else None
            agg_path = ref.path if ref is not None else None
            # Absent OR empty source_path counts as self-sourced (design §5.2).
            self_sourced = source_path in (None, "") or source_path == agg_path
            bucket, evidence = _bucket(kind, source_path, has_real_owner, self_sourced)
            triaged.append(AggregateRowTriage(canonical_id, kind, source_path, has_real_owner, bucket, evidence))
```

Replace the last two lines (`agg_path` is already there) — add `ref_line` and extend the constructor call:

```python
            agg_path = ref.path if ref is not None else None
            ref_line = ref.line if ref is not None else None
            # Absent OR empty source_path counts as self-sourced (design §5.2).
            self_sourced = source_path in (None, "") or source_path == agg_path
            bucket, evidence = _bucket(kind, source_path, has_real_owner, self_sourced)
            triaged.append(
                AggregateRowTriage(
                    canonical_id, kind, source_path, has_real_owner, bucket, evidence, agg_path, ref_line
                )
            )
```

- [ ] **Step 5: Update the two hand-built triages in the apply test**

In `science/tests/graph/test_aggregate_retire_apply.py`, two tests construct `AggregateRowTriage` positionally with 6 args and now need 8. Line `:84`:

```python
    triage = AggregateRowTriage("concept:no-title", "concept", _AGG_REL, False, AggregateBucket.COINED, "x")
```
becomes:
```python
    triage = AggregateRowTriage("concept:no-title", "concept", _AGG_REL, False, AggregateBucket.COINED, "x", _AGG_REL, 0)
```

Line `:141`:
```python
    triage = AggregateRowTriage("concept:1q-gain", "concept", _AGG_REL, False, AggregateBucket.COINED, "x")
```
becomes:
```python
    triage = AggregateRowTriage("concept:1q-gain", "concept", _AGG_REL, False, AggregateBucket.COINED, "x", _AGG_REL, 0)
```

- [ ] **Step 6: Run the new test + the apply test + triage regressions**

Run:
```bash
uv run --frozen pytest tests/graph/test_triage_row_locators.py tests/graph/test_aggregate_retire_apply.py tests/graph/test_aggregate_triage.py -v
```
Expected: ALL PASS.

- [ ] **Step 7: Lint + commit**

```bash
uv run --frozen ruff check src/science_tool/graph/aggregate_triage.py tests/graph/test_triage_row_locators.py tests/graph/test_aggregate_retire_apply.py
uv run --frozen ruff format --check src/science_tool/graph/aggregate_triage.py tests/graph/test_triage_row_locators.py tests/graph/test_aggregate_retire_apply.py
git add src/science_tool/graph/aggregate_triage.py tests/graph/test_triage_row_locators.py tests/graph/test_aggregate_retire_apply.py
git commit -m "feat(substrate-4a): AggregateRowTriage carries (path, line) row locator"
```

---

## Task 3: Description-preserving, schema-agnostic owner renderer + identity from the compiled model

Rewrite `_owner_text` to take explicit fields and emit the `description` as the owner body. In `apply_retirement`, source identity (`canonical_id`/`kind`) from `pr.triage` and content (`title`/`description`/`profile`) from the raw row. This is behavior-preserving for `entities.yaml` and is the prerequisite that lets `terms.yaml`'s `id`-only rows promote (Task 4) instead of being rejected.

**Files:**
- Modify: `science/src/science_tool/graph/aggregate_retire.py` (`_STUB_BODY`/`_REQUIRED_FIELDS` `:176`, `_owner_text` `:195`, promote loop `:231`–`:261`)
- Test: `science/tests/graph/test_owner_text_renderer.py` (create)
- Test: `science/tests/graph/test_aggregate_retire_apply.py` (add one description-preservation test)

- [ ] **Step 1: Write the failing unit tests for `_owner_text`**

Create `science/tests/graph/test_owner_text_renderer.py`:

```python
from __future__ import annotations

import yaml

from science_tool.graph.aggregate_retire import _STUB_BODY, _owner_text


def _split(text: str) -> tuple[dict, str]:
    assert text.startswith("---\n")
    _, fm_block, body = text.split("---\n", 2)
    return yaml.safe_load(fm_block), body


def test_non_empty_description_becomes_body() -> None:
    text = _owner_text("concept:x", "concept", "X", "A definition.", None, promoted_from="a.yaml")
    fm, body = _split(text)
    assert fm == {"id": "concept:x", "type": "concept", "title": "X", "promoted_from": "a.yaml"}
    assert body == "\nA definition.\n"  # single blank line after frontmatter, then body + one newline


def test_empty_description_falls_back_to_stub_body() -> None:
    text = _owner_text("concept:x", "concept", "X", "", None, promoted_from="a.yaml")
    assert _STUB_BODY in text


def test_non_string_description_treated_as_absent() -> None:
    text = _owner_text("concept:x", "concept", "X", {"unexpected": "mapping"}, None, promoted_from="a.yaml")
    assert _STUB_BODY in text


def test_description_trailing_newlines_normalized_to_one() -> None:
    text = _owner_text("concept:x", "concept", "X", "Def.\n\n\n", None, promoted_from="a.yaml")
    _, body = _split(text)
    assert body == "\nDef.\n"


def test_profile_included_when_present() -> None:
    text = _owner_text("concept:x", "concept", "X", "Def.", "research", promoted_from="a.yaml")
    fm, _ = _split(text)
    assert fm["profile"] == "research"
```

- [ ] **Step 2: Run them and verify they fail**

Run: `uv run --frozen pytest tests/graph/test_owner_text_renderer.py -v`
Expected: FAIL — `_owner_text` currently takes `(entry, *, promoted_from)`, so the new-signature calls raise `TypeError`.

- [ ] **Step 3: Rewrite `_STUB_BODY` and `_owner_text`**

In `science/src/science_tool/graph/aggregate_retire.py`, current (`:176`–`:200`):

```python
_STUB_BODY = "<!-- promoted from entities.yaml by substrate-3b; add definition -->\n"
_REQUIRED_FIELDS = ("canonical_id", "kind", "title")
```
...
```python
def _owner_text(entry: dict, *, promoted_from: str) -> str:
    fm: dict[str, object] = {"id": entry["canonical_id"], "type": entry["kind"], "title": entry["title"]}
    if entry.get("profile"):
        fm["profile"] = entry["profile"]
    fm["promoted_from"] = promoted_from
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n" + _STUB_BODY
```

Replace the constant line and the function. **Delete `_REQUIRED_FIELDS`** (the title check moves inline in Step 4):

```python
_STUB_BODY = "<!-- promoted from an aggregate manifest by substrate retirement; add definition -->\n"
```
...
```python
def _owner_text(
    canonical_id: str,
    kind: str,
    title: str,
    description: object,
    profile: object,
    *,
    promoted_from: str,
) -> str:
    """Render an id-preserving owner file.

    Identity (`canonical_id`/`kind`) comes from the compiled model (the caller
    passes the triage values), not the raw aggregate row — the two multi-type
    files differ (entities.yaml: explicit canonical_id/kind; terms.yaml: `id` +
    inferred kind). A non-empty string `description` becomes the owner body (the
    §B5 "line of definition"); anything else falls back to the stub body.
    """
    fm: dict[str, object] = {"id": canonical_id, "type": kind, "title": title}
    if profile:
        fm["profile"] = profile
    fm["promoted_from"] = promoted_from
    body = description.rstrip("\n") + "\n" if isinstance(description, str) and description else _STUB_BODY
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n" + body
```

- [ ] **Step 4: Source identity from the triage in the promote loop**

In the same file, the promote loop currently (`:232`–`:258`) opens:

```python
    for pr in plan.promote:
        entry = entries(pr.source_path)[pr.line]
        missing = next((f for f in _REQUIRED_FIELDS if not entry.get(f)), None)
        if missing is not None:
            rejected.append((pr.triage.canonical_id, f"missing required field {missing}"))
            continue
        assert pr.target_path is not None
```

and its write branch (`:255`–`:256`) is:

```python
            else:
                text = _owner_text(entry, promoted_from=pr.source_path)
```

Make two edits. First, replace the `_REQUIRED_FIELDS` block with a title-only check (identity now comes from the triage, always present):

```python
    for pr in plan.promote:
        entry = entries(pr.source_path)[pr.line]
        title = entry.get("title")
        if not title:
            rejected.append((pr.triage.canonical_id, "missing required field title"))
            continue
        assert pr.target_path is not None
```

Second, replace the non-decision write branch with the explicit-field call (identity from `pr.triage`, content from `entry`):

```python
            else:
                text = _owner_text(
                    pr.triage.canonical_id,
                    pr.triage.kind,
                    title,
                    entry.get("description"),
                    entry.get("profile"),
                    promoted_from=pr.source_path,
                )
```

(The decision branch — `if pr.triage.kind == "decision": ... render_owner_file(...)` — is unchanged.)

- [ ] **Step 5: Add an entities.yaml description-preservation test**

In `science/tests/graph/test_aggregate_retire_apply.py`, add this test (it uses the existing `_write_entities`/`_run` helpers; note `_concept` has no description, so add a row with one inline):

```python
def test_promote_preserves_description_as_owner_body(tmp_path: Path) -> None:
    _write_entities(
        tmp_path,
        [
            {
                "canonical_id": "concept:apoptosis",
                "kind": "concept",
                "title": "Apoptosis",
                "description": "Programmed cell death relevant to MM survival signaling.",
                "source_path": _AGG_REL,
            }
        ],
    )
    report = _run(tmp_path, dry_run=False, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert report.promoted == ("concept:apoptosis",)
    body = (tmp_path / "entities/concepts/apoptosis.md").read_text(encoding="utf-8")
    assert "Programmed cell death relevant to MM survival signaling." in body
```

- [ ] **Step 6: Run renderer unit tests + the apply suite**

Run:
```bash
uv run --frozen pytest tests/graph/test_owner_text_renderer.py tests/graph/test_aggregate_retire_apply.py tests/graph/test_aggregate_retire_decisions.py tests/graph/test_aggregate_retire_roundtrip.py -v
```
Expected: ALL PASS. (Decision promotion still works — it uses `render_owner_file`, untouched; description-less concepts still get the stub body.)

- [ ] **Step 7: Lint + commit**

```bash
uv run --frozen ruff check src/science_tool/graph/aggregate_retire.py tests/graph/test_owner_text_renderer.py tests/graph/test_aggregate_retire_apply.py
uv run --frozen ruff format --check src/science_tool/graph/aggregate_retire.py tests/graph/test_owner_text_renderer.py tests/graph/test_aggregate_retire_apply.py
git add src/science_tool/graph/aggregate_retire.py tests/graph/test_owner_text_renderer.py tests/graph/test_aggregate_retire_apply.py
git commit -m "feat(substrate-4a): owner renderer preserves description; identity from compiled model"
```

---

## Task 4: Firewall widening + root-key-aware read/rewrite (terms.yaml end-to-end)

Admit both multi-type files into the executor and make `_read_entries`/`_rewrite_aggregate` honor each file's YAML root key. With Task 3 already sourcing identity from the triage, `terms.yaml` concepts now promote end-to-end.

**Files:**
- Modify: `science/src/science_tool/graph/aggregate_retire.py` (imports `:11`–`:24`, `_ENTITIES_FILE` `:29`, firewall `:124`, `_read_entries` `:180`, `_rewrite_aggregate` `:203`)
- Test: `science/tests/graph/test_aggregate_retire_terms.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `science/tests/graph/test_aggregate_retire_terms.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.aggregate_retire import _read_entries, _rewrite_aggregate, apply_retirement, plan_retirement
from science_tool.graph.aggregate_triage import classify_aggregate_rows
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"
_TERMS_REL = "knowledge/sources/local/terms.yaml"
_ENT_REL = "knowledge/sources/local/entities.yaml"


def _write(root: Path, *, terms: list[dict] | None = None, entities: list[dict] | None = None) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    src = root / "knowledge" / "sources" / "local"
    src.mkdir(parents=True, exist_ok=True)
    if terms is not None:
        (src / "terms.yaml").write_text(yaml.safe_dump({"terms": terms}), encoding="utf-8")
    if entities is not None:
        (src / "entities.yaml").write_text(yaml.safe_dump({"entities": entities}), encoding="utf-8")


def _run(root: Path, **flags):
    sources = load_project_sources(root, include_commons=False, strict_core_schema=False, strict_identity=False)
    plan = plan_retirement(root, sources, classify_aggregate_rows(sources), **flags)
    return apply_retirement(root, plan, dry_run=False)


def test_read_and_rewrite_use_terms_root_key(tmp_path: Path) -> None:
    _write(tmp_path, terms=[{"id": "concept:a", "title": "A"}, {"id": "concept:b", "title": "B"}])
    assert [e["id"] for e in _read_entries(tmp_path, _TERMS_REL)] == ["concept:a", "concept:b"]
    _rewrite_aggregate(tmp_path, _TERMS_REL, {0})  # drop row 0
    data = yaml.safe_load((tmp_path / _TERMS_REL).read_text(encoding="utf-8"))
    assert "terms" in data and "entities" not in data  # root key preserved
    assert [e["id"] for e in data["terms"]] == ["concept:b"]


def test_terms_coined_concept_promotes_with_description_body(tmp_path: Path) -> None:
    _write(
        tmp_path,
        terms=[
            {"id": "concept:prc2-complex", "title": "PRC2 complex",
             "description": "Polycomb repressive complex 2 as a local semantic placeholder."}
        ],
    )
    report = _run(tmp_path, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert report.promoted == ("concept:prc2-complex",)
    owner = tmp_path / "entities/concepts/prc2-complex.md"
    assert owner.exists()
    text = owner.read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---")[1])
    assert fm["id"] == "concept:prc2-complex"
    assert fm["type"] == "concept"
    assert fm["title"] == "PRC2 complex"
    assert fm["promoted_from"] == _TERMS_REL
    assert "Polycomb repressive complex 2 as a local semantic placeholder." in text
    # Row dropped, terms root preserved.
    data = yaml.safe_load((tmp_path / _TERMS_REL).read_text(encoding="utf-8"))
    assert data == {"terms": []}


def test_promoted_terms_concept_reloads_with_content_preview(tmp_path: Path) -> None:
    _write(
        tmp_path,
        terms=[{"id": "concept:prc2-complex", "title": "PRC2 complex",
                "description": "Polycomb repressive complex 2 placeholder."}],
    )
    _run(tmp_path, promote_coined=True, delete_cruft=False, delete_shadow=False)
    reloaded = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    ent = next((e for e in reloaded.entities if e.canonical_id == "concept:prc2-complex"), None)
    assert ent is not None, "promoted concept owner did not reload as an entity"
    # Definition survives: promoted to the owner BODY, so content->content_preview fallback applies.
    assert ent.content_preview
    assert "Polycomb repressive complex 2 placeholder." in ent.content_preview


def test_terms_ambiguous_row_is_left_untouched(tmp_path: Path) -> None:
    # A non-self-sourced concept row classifies AMBIGUOUS (the coined branch requires
    # self_sourced); --promote-coined must not promote or delete it.
    _write(
        tmp_path,
        terms=[
            {"id": "concept:coined", "title": "Coined"},  # self-sourced (no source_path) -> COINED
            {"id": "concept:external", "title": "External", "source_path": "doc/something.md"},  # -> AMBIGUOUS
        ],
    )
    report = _run(tmp_path, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert report.promoted == ("concept:coined",)
    assert "concept:external" not in report.promoted
    assert "concept:external" not in report.deleted
    remaining = yaml.safe_load((tmp_path / _TERMS_REL).read_text(encoding="utf-8"))["terms"]
    assert [r["id"] for r in remaining] == ["concept:external"]


def test_mixed_entities_and_terms_each_file_rewritten_once(tmp_path: Path) -> None:
    _write(
        tmp_path,
        entities=[{"canonical_id": "concept:ent", "kind": "concept", "title": "Ent", "source_path": _ENT_REL}],
        terms=[{"id": "concept:trm", "title": "Trm"}],
    )
    report = _run(tmp_path, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert set(report.promoted) == {"concept:ent", "concept:trm"}
    assert set(report.files_rewritten) == {_ENT_REL, _TERMS_REL}
    assert yaml.safe_load((tmp_path / _ENT_REL).read_text())["entities"] == []
    assert yaml.safe_load((tmp_path / _TERMS_REL).read_text())["terms"] == []
```

- [ ] **Step 2: Run them and verify they fail**

Run: `uv run --frozen pytest tests/graph/test_aggregate_retire_terms.py -v`
Expected: FAIL — `_read_entries`/`_rewrite_aggregate` read the `entities` key (so terms rows look empty), and the firewall skips `terms.yaml` (so nothing promotes).

- [ ] **Step 3: Import the public API, remove `_ENTITIES_FILE`, refresh stale comments**

In `science/src/science_tool/graph/aggregate_retire.py`, add the import next to the other `science_tool.graph` imports (after the `aggregate_triage` import, `:23`):

```python
from science_tool.graph.storage_adapters.aggregate import MULTI_TYPE_AGGREGATE_ROOT_KEYS, multi_type_root_key
```

Delete the now-unused constant (`:29`):

```python
_ENTITIES_FILE = "entities.yaml"
```

Refresh two now-inaccurate comments (4a widens scope to both multi-type files):

- The module docstring (`:1`–`:9`) currently says *"It is scoped to `entities.yaml` declarations only (the §3.1 firewall — `terms.yaml` and single-type aggregates are Phase-4/out of scope)."* Replace that sentence with: *"It is scoped to the multi-type aggregate files (`entities.yaml`, `terms.yaml`); single-type aggregates (`doc/<plural>/<plural>.{json,yaml}`) are out of scope."*
- The `PlannedRow.source_path` field comment (`:41`) currently reads *"the entities.yaml file (declaration source_ref.path), project-root-relative"*. Replace with *"the aggregate file (entities.yaml/terms.yaml) declaration source_ref.path, project-root-relative"*.

- [ ] **Step 4: Widen the firewall**

In `plan_retirement`, current (`:124`–`:125`):

```python
        if Path(meta.path).name != _ENTITIES_FILE:
            continue  # §3.1 firewall: never touch terms.yaml / single-type aggregates
```

Replace with:

```python
        if Path(meta.path).name not in MULTI_TYPE_AGGREGATE_ROOT_KEYS:
            continue  # firewall: only the multi-type files (entities.yaml/terms.yaml); never single-type aggregates
```

- [ ] **Step 5: Make read/rewrite root-key-aware**

Current `_read_entries` (`:180`–`:182`):

```python
def _read_entries(project_root: Path, rel: str) -> list[dict]:
    data = yaml.safe_load((project_root / rel).read_text(encoding="utf-8")) or {}
    return data.get("entities") or []
```

Replace:

```python
def _read_entries(project_root: Path, rel: str) -> list[dict]:
    data = yaml.safe_load((project_root / rel).read_text(encoding="utf-8")) or {}
    root_key = multi_type_root_key(Path(rel).name)
    assert root_key is not None, f"not a multi-type aggregate file: {rel}"
    return data.get(root_key) or []
```

Current `_rewrite_aggregate` (`:203`–`:208`):

```python
def _rewrite_aggregate(project_root: Path, rel: str, drop: set[int]) -> None:
    path = project_root / rel
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = data.get("entities") or []
    data["entities"] = [row for i, row in enumerate(items) if i not in drop]
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
```

Replace:

```python
def _rewrite_aggregate(project_root: Path, rel: str, drop: set[int]) -> None:
    path = project_root / rel
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    root_key = multi_type_root_key(path.name)
    assert root_key is not None, f"not a multi-type aggregate file: {rel}"
    items = data.get(root_key) or []
    data[root_key] = [row for i, row in enumerate(items) if i not in drop]
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
```

- [ ] **Step 6: Run the terms suite + the full retire/triage regressions**

Run:
```bash
uv run --frozen pytest tests/graph/test_aggregate_retire_terms.py -v
uv run --frozen pytest tests/graph/ -q -k "aggregate or triage or sources or retire"
```
Expected: terms suite PASS; all existing aggregate/triage/sources/retire tests still PASS.

- [ ] **Step 7: Lint + commit**

```bash
uv run --frozen ruff check src/science_tool/graph/aggregate_retire.py tests/graph/test_aggregate_retire_terms.py
uv run --frozen ruff format --check src/science_tool/graph/aggregate_retire.py tests/graph/test_aggregate_retire_terms.py
git add src/science_tool/graph/aggregate_retire.py tests/graph/test_aggregate_retire_terms.py
git commit -m "feat(substrate-4a): admit terms.yaml; root-key-aware read/rewrite; terms concepts promote"
```

---

## Task 5: Planner joins triage by `(path, line)` — duplicate ids across files

With two files in scope, a `canonical_id` present in both must not inherit the wrong bucket. Switch the planner's triage lookup from id-keyed to `(path, line)`-keyed.

**Files:**
- Modify: `science/src/science_tool/graph/aggregate_retire.py` (`plan_retirement` `:111`, `:126`)
- Test: `science/tests/graph/test_aggregate_retire_terms.py` (add the dup-id test)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/graph/test_aggregate_retire_terms.py`:

```python
def test_duplicate_id_across_files_routes_by_path_line(tmp_path: Path) -> None:
    # Same canonical_id in both files but DIFFERENT buckets: COINED (self-sourced)
    # in entities.yaml vs CRUFT (migration source) in terms.yaml. Correct routing
    # promotes the entities row (owner created) and deletes the terms cruft row.
    #
    # Old id-keyed triage collapses both metas to ONE triage for "concept:dup":
    # rows are sorted by (bucket, id), so the dict's last write wins = CRUFT, and
    # BOTH metas take the delete action under --delete-cruft -> the coined row is
    # destroyed and the owner file is never written. The owner-exists assertion
    # below fails on the old code and passes on the (path, line)-keyed planner,
    # independent of meta iteration order.
    _write(
        tmp_path,
        entities=[{"canonical_id": "concept:dup", "kind": "concept", "title": "Coined", "source_path": _ENT_REL}],
        terms=[{"id": "concept:dup", "title": "Cruft", "source_path": "migration:audit"}],
    )
    report = _run(tmp_path, promote_coined=True, delete_cruft=True, delete_shadow=False)
    assert (tmp_path / "entities/concepts/dup.md").exists()  # entities (coined) row promoted
    assert "concept:dup" in report.promoted
    assert yaml.safe_load((tmp_path / _ENT_REL).read_text())["entities"] == []     # coined row removed
    assert yaml.safe_load((tmp_path / _TERMS_REL).read_text())["terms"] == []      # cruft row deleted
```

- [ ] **Step 2: Run it and verify it fails**

Run: `uv run --frozen pytest "tests/graph/test_aggregate_retire_terms.py::test_duplicate_id_across_files_routes_by_path_line" -v`
Expected: FAIL on `assert (tmp_path / "entities/concepts/dup.md").exists()` — id-keyed `triage_by_id` collapses both metas to the CRUFT triage (last write wins after the `(bucket, id)` sort), so under `--delete-cruft` both rows are deleted and the owner file is never written.

- [ ] **Step 3: Key the planner join by `(path, line)`**

In `science/src/science_tool/graph/aggregate_retire.py`, `plan_retirement` currently builds (`:111`):

```python
    triage_by_id = {t.canonical_id: t for t in rows}
```
and looks up (`:126`):
```python
        triage = triage_by_id.get(meta.canonical_id)
```

Replace the build line with:

```python
    triage_by_ref = {(t.path, t.line): t for t in rows}
```

and the lookup with:

```python
        triage = triage_by_ref.get((meta.path, meta.line))
```

- [ ] **Step 4: Run the dup-id test + the full terms + apply suites**

Run:
```bash
uv run --frozen pytest tests/graph/test_aggregate_retire_terms.py tests/graph/test_aggregate_retire_apply.py tests/graph/test_aggregate_retire_decisions.py tests/graph/test_aggregate_retire_roundtrip.py -v
```
Expected: ALL PASS (single-file behavior unchanged — ids were unique within a file, so `(path, line)` keying is identical there).

- [ ] **Step 5: Lint + commit**

```bash
uv run --frozen ruff check src/science_tool/graph/aggregate_retire.py tests/graph/test_aggregate_retire_terms.py
uv run --frozen ruff format --check src/science_tool/graph/aggregate_retire.py tests/graph/test_aggregate_retire_terms.py
git add src/science_tool/graph/aggregate_retire.py tests/graph/test_aggregate_retire_terms.py
git commit -m "feat(substrate-4a): planner joins triage by (path, line) — no cross-file id mis-route"
```

---

## Final verification (run before handing off to the holistic reviewer)

- [ ] **Full suite green**

Run: `uv run --frozen pytest -q`
Expected: all pass / only the project's pre-existing skips (≈6). No new failures.

- [ ] **Lint clean on all touched files**

Run:
```bash
uv run --frozen ruff check \
  src/science_tool/graph/aggregate_retire.py \
  src/science_tool/graph/aggregate_triage.py \
  src/science_tool/graph/storage_adapters/aggregate.py \
  tests/graph/test_aggregate_multi_type_api.py \
  tests/graph/test_triage_row_locators.py \
  tests/graph/test_owner_text_renderer.py \
  tests/graph/test_aggregate_retire_apply.py \
  tests/graph/test_aggregate_retire_terms.py
uv run --frozen ruff format --check \
  src/science_tool/graph/aggregate_retire.py \
  src/science_tool/graph/aggregate_triage.py \
  src/science_tool/graph/storage_adapters/aggregate.py
```
Expected: zero errors on these files. (The repo has ≈174 pre-existing baseline ruff errors in *untouched* files + the 2c `commons/datapackage.py` format drift — leave those alone; only the files above must be clean.)

- [ ] **MM30 v2 smoke — dry-run shows terms concepts, `--apply` refused**

MM30 is still `layout_version: 2`, so `--apply` must refuse and nothing may mutate. From the MM30 repo:

```bash
cd /mnt/ssd/Dropbox/cancer/cancer-types/multiple-myeloma
# Run the science CLI against MM30 using the branch build (see reference_container_invocation memory if needed).
uv run --frozen --project ~/d/science/science science entities triage-aggregate \
  --project-root . --promote-coined 2>&1 | tail -20   # dry-run: now lists ~108 terms.yaml concepts as promotable
uv run --frozen --project ~/d/science/science science entities triage-aggregate \
  --project-root . --promote-coined --apply; echo "exit=$?"   # expect exit=1, message names layout_version
git -C . status --short   # expect clean: no mutation
```
Expected: dry-run report includes the `terms.yaml` coined concepts; `--apply` exits 1 naming `layout_version`; MM30 working tree clean.

- [ ] **Hand off to subagent-driven-development's final holistic review.**

---

## Notes for the implementer

- **Do not** add `terms.yaml`-specific branches in the planner or executor beyond the root-key map and the firewall membership — the design is deliberately kind/file-generic. Identity comes from the triage; content from the raw row; the `concept` path policy (`entities/concepts/`, slug strategy) is resolved by the existing `_promote_target`.
- **Non-conforming coined ids** (e.g. an uppercase/underscore concept slug) are already rejected/retained by `_promote_target`'s conformance belt, which is source-file-agnostic — this is covered by the existing 3b `_promote_target` tests, so no new test is needed for it here.
- **`latent` rows** are bucketed coined too, but `latent` is a project-local kind that defaults to the `numeric` filename strategy; `_promote_target` will reject `latent:<slug>` ids until a project manifest grants `latent` a conforming policy (MM30 Task #30). No special-casing in 4a.
- If a `ruff format` step reports drift you did not introduce, confirm it is pre-existing on `main` (`git stash && ruff format --check <file>`); do not reformat unrelated code in this branch.
