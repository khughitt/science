# Context-budget Slice 3 — task storage split — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the aggregated `tasks/active.md` with one YAML-frontmatter file per open task under `tasks/active/tNNN-slug.md`, remove `active.md` outright, retire the now-redundant `tasks archive` command, and ship a transactional `migrate-storage` migrator (applied to `science/meta` in-slice).

**Architecture:** `tasks/active/` holds only open tasks (one file each); `tasks/done/YYYY-MM.md` monthly ledgers keep the `## [tNNN]` DSL (extended to round-trip every field). All reads funnel through `_read_active`/`_task_search_paths`; all writers go through per-file helpers under one acquire-once file lock; a storage-state classifier fails loudly on unmigrated/half-migrated layouts. The migrator is the sole one-time router of legacy terminal tasks into `done/`.

**Tech Stack:** Python 3.12+, Pydantic (`science_model`), Click, pytest. Package root `science/` (`cd science && uv run --frozen pytest`). Design spec: [`2026-07-26-context-budget-slice3-storage-design.md`](2026-07-26-context-budget-slice3-storage-design.md) — every task cites the section it implements.

## Global Constraints

Every task's requirements implicitly include these (spec §1–§4):

- **Canonical id** = `_TASK_ID_PATTERN = r"t[0-9]{3,}"` (`tasks.py:49`). Reuse the constant; never a looser `t\d+`.
- **`active/` holds open tasks only** — statuses `{proposed, active, blocked, deferred}`. Terminal (`done`/`retired`) or unknown status in an `active/*.md` file is an error at the parse boundary. `edit` may not terminalize an active task in place.
- **One lock discipline** — top-level mutators acquire `_task_allocation_lock(tasks_dir)` exactly once; internal writers (`_move_task_to_done`, `write_task_file`, `delete_task_file`, `write_task_location`) run **lock-held and never re-acquire** (a second `flock(LOCK_EX)` on a fresh fd deadlocks in-process). Read-only paths never take it.
- **All per-file writes atomic** — via `science_model.frontmatter.atomic_write_text` (temp + `os.replace`). Slug rename = atomic-write-then-`os.replace`, refuse existing destination.
- **Fail early / no silent fallbacks / no dual-read compat layer for `active.md`.**
- **Strict YAML** — task frontmatter rejects unknown keys, duplicate keys, and merge keys before model construction.
- **Two predicates** — *migration dedup* = full structural `Task` equality; *move-recovery* = same id + ledger status == target + all transition-stable fields equal + description prefix-match. Never `(id, created)` alone.
- **Single-line titles** — reject a title containing a newline or a bare `]` at every boundary.
- Conventional commits; **no AI-attribution trailer**. Work on branch `context-budget-slice3` (verify before each commit — Dropbox main-checkout volatility). Run scoped test selections, not the full suite, from `science/`.

---

## File Structure

- `science/model/src/science_model/tasks.py` — model only (unchanged; already has all fields).
- `science/src/science_tool/markdown_utils.py` — gains neutral `reject_duplicate_and_merge_keys` + `StrictYAMLError` (Task 1).
- `science/src/science_tool/graph/autonomous_runs.py` — refactored onto the neutral helper (Task 1).
- `science/src/science_tool/tasks_ledger.py` — **new** neutral home for done-ledger primitives (`_destination_for`, `_read_destination`, `_split_preamble_and_blocks`) and the pure `plan_ledger_appends` (Tasks 2, 12).
- `science/src/science_tool/tasks.py` — DSL upgrade, `parse_task_file`/`render_task_file`, per-file writers, `_read_active`/search-path layer, state gate, lock refactor, `_move_task_to_done`, mutators (Tasks 3–9).
- `science/src/science_tool/tasks_cli.py` — `fix-blockers`/`summary`/`list` re-points, `migrate-storage` command, `tasks archive` removal (Tasks 10, 13, 14).
- `science/src/science_tool/graph/storage_adapters/task.py` — per-task-file parse (Task 15).
- health-report surface files + `instruments.py` + budget registry — archive-lag removal (Task 14).
- ~11 reader modules — re-pointed (Task 11).
- docs + templates + content guard — (Task 16).
- `science/meta/tasks/` — migrated (Task 17).

---

## Task 1: Extract a neutral strict-YAML checker

Implements spec §1 "Strict YAML … via a neutral helper". Standalone; unblocks Task 4.

**Files:**
- Modify: `science/src/science_tool/markdown_utils.py`
- Modify: `science/src/science_tool/graph/autonomous_runs.py:24-59`
- Test: `science/tests/test_markdown_utils.py` (add), `science/tests/graph/test_autonomous_runs.py` (existing — must stay green)

**Interfaces:**
- Produces: `markdown_utils.StrictYAMLError(ValueError)`; `markdown_utils.reject_duplicate_and_merge_keys(node: yaml.Node, *, on_error: Callable[[str], Exception] = StrictYAMLError) -> None` (recursive; raises `on_error(msg)` on a duplicate key or a `tag:yaml.org,2002:merge` node).
- Consumes: nothing new.

- [ ] **Step 1: Write the failing test** in `science/tests/test_markdown_utils.py`:

```python
import pytest
import yaml
from science_tool.markdown_utils import StrictYAMLError, reject_duplicate_and_merge_keys


def _node(text: str) -> yaml.Node:
    return yaml.compose(text)


def test_rejects_duplicate_key():
    with pytest.raises(StrictYAMLError, match="duplicate key 'priority'"):
        reject_duplicate_and_merge_keys(_node("priority: P1\npriority: P2\n"))


def test_rejects_yaml_equivalent_duplicate_keys():
    # yes/true resolve to the same bool; text differs, constructed key does not.
    with pytest.raises(StrictYAMLError):
        reject_duplicate_and_merge_keys(_node("yes: 1\ntrue: 2\n"))


def test_rejects_merge_key():
    text = "base: &b {a: 1}\nchild:\n  <<: *b\n"
    with pytest.raises(StrictYAMLError, match="merge"):
        reject_duplicate_and_merge_keys(_node(text))


def test_accepts_clean_nested_mapping():
    reject_duplicate_and_merge_keys(_node("a: 1\nb:\n  c: 2\n  d: [1, 2]\n"))


def test_custom_on_error_type():
    class Boom(ValueError):
        ...

    with pytest.raises(Boom):
        reject_duplicate_and_merge_keys(_node("x: 1\nx: 2\n"), on_error=Boom)
```

- [ ] **Step 2: Run it, verify failure**

Run: `cd science && uv run --frozen pytest tests/test_markdown_utils.py -q`
Expected: FAIL (`ImportError` / `AttributeError` — symbol not defined).

- [ ] **Step 3: Implement the neutral helper** in `markdown_utils.py` (move the recursive logic verbatim from `autonomous_runs._reject_duplicate_and_merge_keys`, generalizing the error):

```python
from collections.abc import Callable

import yaml


class StrictYAMLError(ValueError):
    """A YAML block violated strict-mode rules (duplicate or merge keys)."""


def reject_duplicate_and_merge_keys(
    node: yaml.Node,
    *,
    on_error: Callable[[str], Exception] = StrictYAMLError,
) -> None:
    """Refuse duplicate keys and YAML merge keys anywhere in the document.

    Recursive: nested mappings are checked too. Operates on the NODE tree from
    ``yaml.compose`` while still seeing what ``safe_load`` would collapse to
    last-wins. Keys are constructed via a throwaway ``SafeLoader`` so
    YAML-equivalent pairs (``yes``/``true``, ``1``/``1.0``) are caught, and an
    unsafe key tag can never reach an object intact.
    """
    if isinstance(node, yaml.MappingNode):
        seen: set[object] = set()
        loader = yaml.SafeLoader("")
        try:
            for key_node, value_node in node.value:
                if key_node.tag == "tag:yaml.org,2002:merge":
                    raise on_error("YAML merge keys are not allowed")
                key = loader.construct_object(key_node, deep=True)
                if key in seen:
                    raise on_error(f"duplicate key {key!r}")
                seen.add(key)
                reject_duplicate_and_merge_keys(value_node, on_error=on_error)
        finally:
            loader.dispose()
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            reject_duplicate_and_merge_keys(item, on_error=on_error)
```

- [ ] **Step 4: Refactor `autonomous_runs` onto it.** Replace `_reject_duplicate_and_merge_keys`'s body with a call, preserving `RunRecordError` messages and the `path` context:

```python
from science_tool.markdown_utils import reject_duplicate_and_merge_keys

def _reject_duplicate_and_merge_keys(node: yaml.Node, path: Path) -> None:
    reject_duplicate_and_merge_keys(
        node,
        on_error=lambda msg: RunRecordError(f"{path}: {msg} in run record"),
    )
```

- [ ] **Step 5: Run both test modules**

Run: `cd science && uv run --frozen pytest tests/test_markdown_utils.py tests/graph/test_autonomous_runs.py -q`
Expected: PASS (new helper tests + unchanged run-record strict-YAML tests).

- [ ] **Step 6: Commit** — `git commit -m "refactor(yaml): extract neutral strict-YAML key checker into markdown_utils"`

---

## Task 2: Relocate done-ledger primitives into `tasks_ledger`

Implements spec §Decision-3 "relocated to a neutral home". Keeps the tree green — `tasks_archive` and `_read_since_candidates` both import from the new home. No behavior change.

**Files:**
- Create: `science/src/science_tool/tasks_ledger.py`
- Modify: `science/src/science_tool/tasks_archive.py` (import relocated helpers), `science/src/science_tool/tasks.py:788` (`_read_since_candidates` import)
- Test: `science/tests/test_tasks_ledger.py` (add); `science/tests/test_tasks_since.py` (existing — stays green)

**Interfaces:**
- Produces: `tasks_ledger._destination_for(task, today) -> tuple[Path, bool]`, `tasks_ledger._read_destination(path) -> tuple[str, list[Task]]`, `tasks_ledger._split_preamble_and_blocks(text) -> tuple[str, list[list[str]]]` — moved verbatim from `tasks_archive.py:87-126,197-210`.
- Consumes: `tasks._parse_task_block`, `tasks.render_tasks`, `tasks._HEADER_RE`, `Task` (module-level import — one direction, `tasks_ledger` → `tasks`).

- [ ] **Step 1: Write the failing test** `science/tests/test_tasks_ledger.py`:

```python
from datetime import date
from pathlib import Path

from science_model.tasks import Task
from science_tool.tasks_ledger import _destination_for, _read_destination


def test_destination_uses_completed_month():
    t = Task(id="t005", title="x", status="done", created=date(2026, 3, 1),
             completed=date(2026, 3, 15))
    dest, missing = _destination_for(t, date(2026, 4, 25))
    assert dest == Path("done") / "2026-03.md"
    assert missing is False


def test_destination_falls_back_to_today_when_undated():
    t = Task(id="t006", title="x", status="retired", created=date(2026, 3, 1))
    dest, missing = _destination_for(t, date(2026, 4, 25))
    assert dest == Path("done") / "2026-04.md"
    assert missing is True


def test_read_destination_missing_file(tmp_path: Path):
    assert _read_destination(tmp_path / "done" / "2026-01.md") == ("", [])
```

- [ ] **Step 2: Run it, verify failure** — `cd science && uv run --frozen pytest tests/test_tasks_ledger.py -q` → FAIL (module missing).

- [ ] **Step 3: Create `tasks_ledger.py`** — move `_destination_for`, `_read_destination`, `_split_preamble_and_blocks`, and `_HEADING_PREFIX_RE` out of `tasks_archive.py` verbatim; import `Task`, `_parse_task_block`, `render_tasks`, `_HEADER_RE` from `science_tool.tasks`. Module docstring: "Neutral done-ledger read/destination primitives shared by `tasks` (`--since`) and the storage migrator."

- [ ] **Step 4: Re-point importers.** In `tasks_archive.py`, delete the moved defs and `from science_tool.tasks_ledger import _destination_for, _read_destination, _split_preamble_and_blocks`. In `tasks.py:788`, change the lazy import to `from science_tool.tasks_ledger import _read_destination`.

- [ ] **Step 5: Run affected tests**

Run: `cd science && uv run --frozen pytest tests/test_tasks_ledger.py tests/test_tasks_since.py tests/test_tasks_archive.py -q`
Expected: PASS (relocation is behavior-preserving; archive tests still green pre-retirement).

- [ ] **Step 6: Commit** — `git commit -m "refactor(tasks): relocate done-ledger primitives into tasks_ledger module"`

---

## Task 3: Extend the done-ledger DSL to round-trip every field, reversibly

Implements spec §4 "done-ledger DSL", "Reversible list/scalar grammar", "Reject duplicate AND unknown ledger keys; verify every field", and §1 single-line title (header parse). Touches `render_task`, `_parse_task_block`, `_parse_list_value`, `_verify_round_trip`.

**Files:**
- Modify: `science/src/science_tool/tasks.py` (`render_task:295`, `_parse_task_block:134`, `_parse_list_value:60`, `_parse_task_header:68`, `_verify_round_trip:211`)
- Test: `science/tests/test_tasks_dsl_roundtrip.py` (add)

**Interfaces:**
- Produces: `_render_list_value(items: list[str]) -> str` (JSON array), `_parse_list_value` (reads JSON array; tolerant of bare `[a, b]`); `render_task`/`_parse_task_block` cover `project`/`artifacts`/`findings`; `_verify_round_trip` compares all `Task` fields.
- Consumes: `Task`.

- [ ] **Step 1: Write failing tests** `science/tests/test_tasks_dsl_roundtrip.py`:

```python
from datetime import date

import pytest
from science_model.tasks import Task
from science_tool.tasks import (
    TaskIntegrityError,
    _parse_task_block,
    _verify_round_trip,
    render_task,
    render_tasks,
)


def _roundtrip(t: Task) -> Task:
    block = render_task(t).splitlines()
    return _parse_task_block(block)


def test_project_artifacts_findings_roundtrip():
    t = Task(id="t010", title="x", status="done", created=date(2026, 3, 1),
             completed=date(2026, 3, 2), project="meta",
             artifacts=["a.md", "b.md"], findings=["f1"])
    got = _roundtrip(t)
    assert got.project == "meta"
    assert got.artifacts == ["a.md", "b.md"]
    assert got.findings == ["f1"]


def test_list_item_with_comma_is_reversible():
    t = Task(id="t011", title="x", status="done", created=date(2026, 3, 1),
             completed=date(2026, 3, 2), artifacts=["report, revised.md"])
    assert _roundtrip(t).artifacts == ["report, revised.md"]


def test_rejects_duplicate_metadata_key():
    block = [
        "## [t012] x", "- priority: P1", "- priority: P2",
        "- status: done", "- created: 2026-03-01", "", "body",
    ]
    with pytest.raises(ValueError, match="duplicate"):
        _parse_task_block(block)


def test_rejects_unknown_metadata_key():
    block = [
        "## [t013] x", "- priority: P1", "- status: done",
        "- created: 2026-03-01", "- foo: bar", "", "body",
    ]
    with pytest.raises(ValueError, match="unknown"):
        _parse_task_block(block)


def test_rejects_newline_in_title_via_header():
    # A header line cannot physically contain a newline; guard the ']' case.
    with pytest.raises(ValueError):
        _parse_task_block(["## [t014] a ] b", "- created: 2026-03-01", "", "x"])


def test_verify_round_trip_flags_full_field_mismatch():
    # A renderer that dropped artifacts must be caught by the verifier.
    good = Task(id="t015", title="x", status="done", created=date(2026, 3, 1),
                completed=date(2026, 3, 2), artifacts=["a.md"])
    text = render_tasks([good])
    _verify_round_trip(text, [good], path=None)  # passes when lossless
```

- [ ] **Step 2: Run, verify failure** — `cd science && uv run --frozen pytest tests/test_tasks_dsl_roundtrip.py -q` → FAIL.

- [ ] **Step 3: Reversible list grammar.** Replace `_parse_list_value` and add `_render_list_value`:

```python
import json

def _render_list_value(items: list[str]) -> str:
    # JSON array round-trips any string (commas, brackets, quotes, newlines).
    return json.dumps(items, ensure_ascii=False)

def _parse_list_value(raw: str) -> list[str]:
    """Parse a list value. Prefers JSON-array form; tolerates the legacy bare
    `[a, b]` (comma-split) form for existing on-disk ledgers."""
    raw = raw.strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    m = _LIST_RE.match(raw)  # legacy bare "[a, b]"
    if not m:
        return []
    return [item.strip() for item in m.group(1).split(",") if item.strip()]
```

- [ ] **Step 4: Emit all fields in `render_task`** — after the existing lines, emit `project`, `artifacts`, `findings` when non-default, and switch list fields to `_render_list_value`:

```python
    if task.project:
        lines.append(f"- project: {task.project}")
    # aspects always emitted (validate-required):
    lines.append(f"- aspects: {_render_list_value(task.aspects)}")
    if task.related:
        lines.append(f"- related: {_render_list_value(task.related)}")
    if task.blocked_by:
        lines.append(f"- blocked-by: {_render_list_value(task.blocked_by)}")
    if task.artifacts:
        lines.append(f"- artifacts: {_render_list_value(task.artifacts)}")
    if task.findings:
        lines.append(f"- findings: {_render_list_value(task.findings)}")
```
(Replace the existing `aspects`/`related`/`blocked-by` emission with the `_render_list_value` forms; keep field ordering stable.)

- [ ] **Step 5: `_parse_task_block` — reject duplicate + unknown keys, read new fields.** Define the known set and enforce it in the field loop:

```python
_KNOWN_DSL_FIELDS = frozenset({
    "type", "priority", "status", "parent", "aspects", "related",
    "blocked-by", "group", "created", "completed", "project",
    "artifacts", "findings",
})
```
In the loop replacing `fields[fm.group(1)] = ...`:
```python
            key = fm.group(1)
            if key in fields:
                raise ValueError(f"duplicate metadata key {key!r} for task {task_id}{where}")
            if key not in _KNOWN_DSL_FIELDS:
                raise ValueError(f"unknown metadata key {key!r} for task {task_id}{where}")
            fields[key] = fm.group(2).strip()
```
Then pass `project=fields.get("project", "")`, `artifacts=_parse_list_value(fields.get("artifacts", ""))`, `findings=_parse_list_value(fields.get("findings", ""))` into the `Task(...)`.

- [ ] **Step 6: Single-line title guard in `_parse_task_header`.** After a successful match, reject a `]`-bearing title residue (the header regex already forbids newlines): if `"]" in title:` raise `ValueError(f"task {task_id} title may not contain ']'{where}")`.

- [ ] **Step 7: Upgrade `_verify_round_trip` to all-field compare.** Replace the id-and-description loop with a full-`Task` compare using a canonical description normalization shared with the structural predicate:

```python
def _canonical_description(text: str) -> str:
    return text.strip()

def _tasks_equal(a: Task, b: Task) -> bool:
    return (a.model_copy(update={"description": _canonical_description(a.description)})
            == b.model_copy(update={"description": _canonical_description(b.description)}))
```
Then in `_verify_round_trip`, after the id-list check, replace the description-only loop with:
```python
    for original, parsed in zip(expected, reparsed):
        if not _tasks_equal(original, parsed):
            raise TaskIntegrityError(
                f"refusing to write {path}: task {original.id} does not round-trip "
                f"(a field is being mangled by the DSL grammar); aborting to avoid data loss."
            )
```
(`_canonical_description`/`_tasks_equal` are reused by the §1a predicates in later tasks.)

- [ ] **Step 8: Run**

Run: `cd science && uv run --frozen pytest tests/test_tasks_dsl_roundtrip.py tests/test_tasks_archive.py -q`
Expected: PASS. (Archive tests still exercise the DSL; confirm no regression from the grammar change.)

- [ ] **Step 9: Commit** — `git commit -m "feat(tasks): full-field reversible done-ledger DSL with strict key + all-field round-trip"`

---

## Task 4: `parse_task_file` / `render_task_file` + identity invariants

Implements spec §1 (format, strict YAML, required keys, single-line title, open-status-only) and §1a (canonical id, filename↔id, per-file round-trip verifier).

**Files:**
- Modify: `science/src/science_tool/tasks.py`
- Test: `science/tests/test_task_file_format.py` (add)

**Interfaces:**
- Produces: `render_task_file(task: Task) -> str`; `parse_task_file(path: Path) -> Task`; `_OPEN_STATUSES = frozenset({"proposed","active","blocked","deferred"})`; `_verify_task_file_round_trip(text, task, path)`.
- Consumes: `markdown_utils.frontmatter_span`, `markdown_utils.reject_duplicate_and_merge_keys`, `_TASK_ID_PATTERN`, `entities.derive_slug`, `_tasks_equal` (Task 3).

- [ ] **Step 1: Write failing tests** `science/tests/test_task_file_format.py` — round-trip; underscore keys; unknown-key reject; duplicate/merge reject; missing-required-key reject; terminal/unknown status reject; non-canonical id reject; filename↔id mismatch reject; single-line title reject. (One test per bullet; example core:)

```python
from datetime import date
from pathlib import Path

import pytest
from science_model.tasks import Task
from science_tool.tasks import parse_task_file, render_task_file


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def test_render_parse_roundtrip(tmp_path: Path):
    t = Task(id="t042", title="Wire --since", status="active", priority="P1",
             aspects=["software-development"], related=["hypothesis:h003"],
             created=date(2026, 7, 20))
    p = _write(tmp_path / "t042-wire-since.md", render_task_file(t))
    assert parse_task_file(p) == t


def test_rejects_unknown_frontmatter_key(tmp_path: Path):
    p = _write(tmp_path / "t042-x.md",
               "---\nid: t042\ntitle: x\nstatus: active\npriority: P1\n"
               "aspects: []\ncreated: 2026-07-20\nblocked-by: []\n---\nbody\n")
    with pytest.raises(ValueError, match="unknown"):
        parse_task_file(p)


def test_rejects_terminal_status_in_active(tmp_path: Path):
    p = _write(tmp_path / "t042-x.md",
               "---\nid: t042\ntitle: x\nstatus: done\npriority: P1\n"
               "aspects: []\ncreated: 2026-07-20\n---\nbody\n")
    with pytest.raises(ValueError, match="status"):
        parse_task_file(p)


def test_rejects_missing_required_key(tmp_path: Path):
    p = _write(tmp_path / "t042-x.md",
               "---\nid: t042\ntitle: x\nstatus: active\npriority: P1\n"
               "aspects: []\n---\nbody\n")  # no created
    with pytest.raises(ValueError, match="created"):
        parse_task_file(p)


def test_rejects_filename_id_mismatch(tmp_path: Path):
    p = _write(tmp_path / "t099-x.md",
               "---\nid: t042\ntitle: x\nstatus: active\npriority: P1\n"
               "aspects: []\ncreated: 2026-07-20\n---\nbody\n")
    with pytest.raises(ValueError, match="filename"):
        parse_task_file(p)


def test_rejects_non_canonical_id(tmp_path: Path):
    p = _write(tmp_path / "t1-x.md",
               "---\nid: t1\ntitle: x\nstatus: active\npriority: P1\n"
               "aspects: []\ncreated: 2026-07-20\n---\nbody\n")
    with pytest.raises(ValueError):
        parse_task_file(p)
```

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement `render_task_file`** — emit the full field set as YAML frontmatter with **underscore** keys (`blocked_by`), `completed: null` when None, `aspects` always, list fields as native YAML lists, then a blank line + `task.description`. Use `yaml.safe_dump` for the mapping or hand-render deterministically (stable key order = model field order). Body is `task.description`.

- [ ] **Step 4: Implement `parse_task_file`** in this exact order (fail-early):

```python
_REQUIRED_KEYS = ("id", "title", "status", "priority", "aspects", "created")
_KNOWN_KEYS = frozenset({
    "id", "project", "title", "type", "aspects", "priority", "status",
    "blocked_by", "related", "parent", "group", "artifacts", "findings",
    "created", "completed",
})
_OPEN_STATUSES = frozenset({"proposed", "active", "blocked", "deferred"})

def parse_task_file(path: Path) -> Task:
    text = path.read_text(encoding="utf-8")
    # 1. strict YAML on the composed node (dup/merge keys) before safe_load:
    fm_text, body = _split_frontmatter_text(text)  # helper: block between --- fences + remainder
    node = yaml.compose(fm_text)
    if node is not None:
        reject_duplicate_and_merge_keys(node, on_error=lambda m: ValueError(f"{path}: {m}"))
    data, _ = frontmatter_span(path)
    # 2. unknown keys:
    unknown = set(data) - _KNOWN_KEYS
    if unknown:
        raise ValueError(f"{path}: unknown frontmatter key(s): {sorted(unknown)}")
    # 3. required keys:
    for key in _REQUIRED_KEYS:
        if key not in data:
            raise ValueError(f"{path}: missing required key: {key}")
    # 4. canonical id + filename agreement:
    task_id = str(data["id"])
    if not re.fullmatch(_TASK_ID_PATTERN, task_id):
        raise ValueError(f"{path}: non-canonical task id {task_id!r}")
    if not path.name.startswith(f"{task_id}-") and path.name != f"{task_id}.md":
        raise ValueError(f"{path}: filename does not match id {task_id!r}")
    # 5. single-line title:
    title = str(data["title"])
    if "\n" in title or "]" in title:
        raise ValueError(f"{path}: title must be single-line and contain no ']'")
    # 6. open-status-only:
    if str(data["status"]) not in _OPEN_STATUSES:
        raise ValueError(f"{path}: status {data['status']!r} not open; active/ holds open tasks only")
    return Task(**data, description=body.strip())
```
(Add `_split_frontmatter_text` if `markdown_utils` lacks a raw-frontmatter-text splitter; otherwise reuse an existing splitter. Confirm `frontmatter_span` returns `(dict, body_start_line)` — read `body` from the lines after that.)

- [ ] **Step 5: Per-file round-trip verifier** — `_verify_task_file_round_trip(text, task, path)` parses `text` via an in-memory path or a temp and asserts `_tasks_equal(parse, task)`; raise `TaskIntegrityError` on mismatch. (Used by `write_task_file`, Task 5.)

- [ ] **Step 6: Run**

Run: `cd science && uv run --frozen pytest tests/test_task_file_format.py -q`
Expected: PASS.

- [ ] **Step 7: Commit** — `git commit -m "feat(tasks): per-task-file (de)serialization with strict identity invariants"`

---

## Task 5: Per-file writers — `write_task_file` / `delete_task_file` (atomic, exactly-one)

Implements spec §1a "Exactly one file per id on mutation", "All per-file writes are atomic", and the atomic slug-rename.

**Files:**
- Modify: `science/src/science_tool/tasks.py`
- Test: `science/tests/test_task_file_writers.py` (add)

**Interfaces:**
- Produces: `_active_dir(tasks_dir) -> Path`; `_find_active_file(tasks_dir, task_id) -> Path | None` (glob `tNNN-*.md` + `tNNN.md`; ≥2 → error); `write_task_file(tasks_dir, task)`; `delete_task_file(tasks_dir, task_id)`. All **require the caller to hold the lock** (documented; not re-acquired).
- Consumes: `render_task_file`, `_verify_task_file_round_trip`, `derive_slug`, `atomic_write_text`.

- [ ] **Step 1: Write failing tests** — create-new (zero-match → `tNNN-slug.md`); update-in-place (same slug); title change renames (old gone, new present, id stable); ≥2 matches → error; delete removes the single file; **crash-between-write-and-replace leaves exactly one intact file**. Example:

```python
def test_title_change_renames_atomically(tmp_path, monkeypatch):
    d = tmp_path / "tasks"
    t = Task(id="t042", title="First title", status="active", priority="P1",
             aspects=[], created=date(2026, 7, 20))
    write_task_file(d, t)
    assert (d / "active" / "t042-first-title.md").is_file()
    t2 = t.model_copy(update={"title": "Second title"})
    write_task_file(d, t2)
    files = list((d / "active").glob("t042-*.md"))
    assert len(files) == 1 and files[0].name == "t042-second-title.md"
```

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement.** Slug via `derive_slug(task.title)` with a fallback (`try: slug = derive_slug(title) except EntityCommandError: slug = "task"`), target = `active/{id}-{slug}.md`.
```python
def write_task_file(tasks_dir: Path, task: Task) -> None:
    active = _active_dir(tasks_dir)
    active.mkdir(parents=True, exist_ok=True)
    text = render_task_file(task)
    _verify_task_file_round_trip(text, task, path=active / f"{task.id}.md")
    existing = _find_active_file(tasks_dir, task.id)  # raises on >=2 matches
    target = active / f"{task.id}-{_slug_for(task.title)}.md"
    if existing is None:
        atomic_write_text(target, text)
        return
    if existing == target:
        atomic_write_text(target, text)  # in-place update, atomic
        return
    # slug changed: write new content to the EXISTING path, then atomic rename.
    atomic_write_text(existing, text)
    if target.exists():
        raise ValueError(f"rename target already exists: {target}")
    os.replace(existing, target)
```
`delete_task_file` locates the single file and `unlink`s it (missing → no-op or error per spec; choose error to fail loud on a lost file). `_find_active_file` raises `ValueError` on ≥2 matches.

- [ ] **Step 4: Run** — `cd science && uv run --frozen pytest tests/test_task_file_writers.py -q` → PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(tasks): atomic exactly-one-per-id per-task-file writers"`

---

## Task 6: Search-path + centralized read layer (`_read_active`, lookups, multi-occurrence guard)

Implements spec §2 read centralization + §1a unique-id + §2 "crash-duplicate inert / multi-occurrence hard error".

**Files:**
- Modify: `science/src/science_tool/tasks.py` (`_read_active:375`, `next_task_id:357`, `known_task_ids:420`, `_task_search_paths:412`, `find_task_location:450`, `_find_matches:439`)
- Test: `science/tests/test_tasks_read_layer.py` (add)

**Interfaces:**
- Produces: `_read_active(tasks_dir)` reads `active/*.md` sorted by id; `_task_search_paths` returns per-file active paths + `done/*.md`; `find_task_location` raises on **any** id with >1 occurrence across search paths; `next_task_id`/`known_task_ids` scan the split layout.
- Consumes: `parse_task_file`, `_active_dir`.

- [ ] **Step 1: Write failing tests** — `_read_active` over an `active/` dir returns the same set an aggregate `active.md` would; duplicate id across two active files → read error; `find_task_location` raises on active+done duplication and on two-done-ledger duplication and on dup-blocks-in-one-ledger; `next_task_id` reflects max across `active/*.md` + `done/*.md`.

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement.**
```python
def _read_active(tasks_dir: Path) -> list[Task]:
    active = _active_dir(tasks_dir)
    if not active.is_dir():
        return []
    tasks = [parse_task_file(p) for p in sorted(active.glob("*.md"))]
    ids = [t.id for t in tasks]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate task ids in {active}: {sorted(dupes)}")
    return sorted(tasks, key=lambda t: t.id)
```
`_task_search_paths` = `sorted(active.glob("*.md"))` + `sorted(done.glob("*.md"), reverse=True)`. `find_task_location` collects **all** matches across paths and raises when `len(matches) > 1` (message naming the locations) — the round-3/6 multi-occurrence rule; single match returned. `next_task_id`/`known_task_ids` iterate `_task_search_paths` (parse_task_file for active files, `_HEADER_RE`/`_parse_task_block` header scan for done ledgers). Keep `next_task_id` a header/id scan (no full parse) so a malformed body cannot block allocation.

- [ ] **Step 4: Run** — `pytest tests/test_tasks_read_layer.py -q` → PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(tasks): centralized split-layout read + multi-occurrence lookup guard"`

---

## Task 7: Storage-state gate

Implements spec §1b.

**Files:**
- Modify: `science/src/science_tool/tasks.py`
- Test: `science/tests/test_tasks_storage_state.py` (add)

**Interfaces:**
- Produces: `StorageState` enum `{EMPTY, SPLIT, LEGACY, MIGRATING, CONFLICT}`; `_tasks_storage_state(tasks_dir) -> StorageState`; `_require_split(tasks_dir)` (raises actionable messages per state, exempt to the migrator); `_MIGRATION_JOURNAL = tasks_dir/".science"/"task-storage-migration.journal"` path helper.
- Consumes: `_active_dir`.

- [ ] **Step 1: Write failing tests** — one per state: EMPTY/SPLIT proceed; LEGACY (active.md, no active/*.md) → `_require_split` raises "run migrate-storage --apply"; **empty `active/` dir beside active.md → LEGACY** (not CONFLICT); MIGRATING (journal present) → "run --resume"; CONFLICT (active.md + ≥1 active/*.md, no journal) → manual message.

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement** classifier (journal presence first; then layout with "`active/` present" ≡ "≥1 `*.md`") and `_require_split` with the three exact messages from spec §1b.

- [ ] **Step 4: Wire the gate** into `_read_active` (call `_require_split` at entry) — but the migrator and `_read_since_candidates`/read-only checks must bypass. Introduce `_read_active(tasks_dir, *, require_split: bool = True)`; the migrator and internal recovery call with `require_split=False`. (Every mutator, Task 9, relies on the default.)

- [ ] **Step 5: Run** — `pytest tests/test_tasks_storage_state.py -q` → PASS.

- [ ] **Step 6: Commit** — `git commit -m "feat(tasks): storage-state gate fails loudly on unmigrated/conflicting layouts"`

---

## Task 8: Lock discipline + `_move_task_to_done` idempotent recovery

Implements spec §2 lock bullet + `_move_task_to_done` + move-recovery predicate (§1a).

**Files:**
- Modify: `science/src/science_tool/tasks.py` (`_task_allocation_lock:339` docstring, `_move_task_to_done:569`)
- Test: `science/tests/test_move_to_done_recovery.py` (add)

**Interfaces:**
- Produces: `_move_recovery_equivalent(active: Task, ledger: Task, *, target_status: str) -> bool`; `_move_task_to_done(tasks_dir, task, *, target_status)` — **require-held**, ledger-append-first / active-delete-last, store-wide replay search.
- Consumes: `_task_search_paths`, `_read_destination`, `_tasks_equal`, `_canonical_description`.

- [ ] **Step 1: Write failing tests** — crash-between-append-and-delete → retry deletes active without duplicate; next-day retry across month boundary → still no duplicate; ledger occurrence failing the predicate → refuse; **status-match**: `done` retry finding a `retired` ledger record → refuse (active kept); id in two ledgers → refuse.

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement predicate** — same id; `ledger.status == target_status`; all transition-stable fields equal (compare `model_copy(update={"status": ..., "completed": ..., "description": ...})` cleared on both, i.e. equality ignoring `status`/`completed`/`description`); and `ledger.description.strip().startswith(active.description.strip())` (prefix match). 

- [ ] **Step 4: Implement `_move_task_to_done`** — search all `done/*.md` for the id; classify occurrences via the predicate; exactly-one-equivalent → skip append, delete active; failing/multiple → raise; else append to `_destination_for(task, date.today())` ledger and delete the active file (`delete_task_file`). Assert (comment) the caller holds the lock; do not acquire.

- [ ] **Step 5: Rewrite `_task_allocation_lock` docstring** to "serializes all `active/` + `done/` writes; acquire once at the top-level, never re-acquire in a helper (flock deadlocks on a second fd)".

- [ ] **Step 6: Run** — `pytest tests/test_move_to_done_recovery.py -q` → PASS.

- [ ] **Step 7: Commit** — `git commit -m "feat(tasks): idempotent-recoverable move-to-done with status-exact replay predicate"`

---

## Task 9: Rewrite mutators to per-file, under acquire-once lock

Implements spec §2 (mutator rewrite, edit terminalize-refusal, defer/block/unblock multi-occurrence guard, archived-task ledger path).

**Files:**
- Modify: `science/src/science_tool/tasks.py` (`add_task:530`, `append_task_note:512`, `edit_task:676`, `defer_task:610`, `block_task:640`, `unblock_task:664`, `complete_task:593`, `retire_task:623`, `write_task_location:463`)
- Test: `science/tests/test_task_mutators_split.py` (add); existing `tests/test_tasks*.py` mutator tests re-pointed to the split layout.

**Interfaces:**
- Consumes: `write_task_file`, `delete_task_file`, `_move_task_to_done`, `find_task_location`, `_require_split`, `_task_allocation_lock`.

- [ ] **Step 1: Write failing tests** — each mutator writes/updates/deletes the correct per-task file; `add` allocates + creates; `complete`/`retire` move to done and remove the active file; `edit --status done` on an active task → refuse with the use-`done`/`retire` message; `defer`/`block`/`unblock` raise on a crash-duplicate id; a note/edit on a done-ledger task rewrites the ledger in place and creates no `active/` file.

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement.** Each **top-level** mutator: `with _task_allocation_lock(tasks_dir): _require_split(tasks_dir); ...` then reads via `_read_active(..., require_split=False)` (gate already checked) / `find_task_location`, mutates the single `Task`, and persists via `write_task_file` (active) or the ledger-rewrite path (archived). `complete_task`/`retire_task` call `_move_task_to_done(..., target_status="done"/"retired")` inside the same lock. `edit_task`: if the task is active and the requested status ∈ terminal → `raise ValueError("use science tasks done/retire to close a task")`. `defer`/`block`/`unblock`: locate via `find_task_location` (which now raises on multi-occurrence) rather than a bare active read. `write_task_location` gains a require-held contract (docstring; no lock acquire).

- [ ] **Step 4: Run** — `pytest tests/test_task_mutators_split.py tests/test_tasks.py -q` → PASS (re-point any active.md-shaped fixtures to `active/`).

- [ ] **Step 5: Commit** — `git commit -m "feat(tasks): per-file mutators under acquire-once lock; edit cannot terminalize in place"`

---

## Task 10: `fix-blockers` — lockless prompt + optimistic recheck

Implements spec §2 `fix-blockers` bullets (no lock across prompt; post-prompt recheck; done-collision reject).

**Files:**
- Modify: `science/src/science_tool/tasks_cli.py` (`tasks fix-blockers`, `:314-376`)
- Test: `science/tests/test_tasks_fix_blockers_split.py` (add)

**Interfaces:**
- Consumes: `_read_active`, `_task_allocation_lock`, `write_task_file`, `known_task_ids`.

- [ ] **Step 1: Write failing tests** — post-migration `fix-blockers` still repairs a per-file task; a concurrent change to the active set between pre-prompt read and write → abort with "tasks changed under you"; a selected id that appears in `done/` after the prompt → abort (no divergent active write).

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement** — read the active set + record a hash (no lock); run the interactive `click.prompt` loop; then `with _task_allocation_lock(tasks_dir):` re-read, compare hash (abort on mismatch), reject any selected id now in `done/`, and `write_task_file` each changed task. Re-point the initial read from `active.md` to `_read_active`.

- [ ] **Step 4: Run** — `pytest tests/test_tasks_fix_blockers_split.py -q` → PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(tasks): fix-blockers lockless prompt with optimistic post-prompt recheck"`

---

## Task 11: Re-point remaining readers + CLI summary/list warning

Implements spec §2 "tasks_cli direct-active.md callers" (summary + list warning) and the ~11 reader list.

**Files:**
- Modify: `tasks_cli.py` (`summary:885`, `list` warning pass `:673`), and `big_picture/validator.py`, `curate/inventory.py`, `dag/refs.py`, `graph/health_checks/legacy_task_type.py`, `graph/health_checks/lingering_tags.py`, `refs.py`, `validate/checks/cross_references.py`, `validate/checks/project_readme.py`, `validate/checks/tasks.py`, `validate/_helpers.py`, `correspondence/probe.py`
- Test: existing suites for each module (re-pointed fixtures)

**Interfaces:**
- Consumes: `_read_active`, `_task_search_paths`, `known_task_ids`, `parse_tasks_for_cli` (directory-aware form).

- [ ] **Step 1:** Add a directory-aware `parse_tasks_for_cli` (accept a `tasks_dir` and read via `_read_active`, preserving the legacy-blocker warning surface). Write/adjust a test that `tasks summary` and the `list` warning pass report real counts over a split layout.

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3:** Replace every `tasks_dir / "active.md"` read (grep: `grep -rn '"active.md"\|/ "active.md"' src/science_tool`) with the centralized helper. Where a check asserts a *file* fact, re-express it against the directory.

- [ ] **Step 4: Run** — `pytest tests/test_tasks_cli.py tests/validate tests/graph tests/test_refs.py -q` (scoped to touched modules) → PASS.

- [ ] **Step 5: Commit** — `git commit -m "refactor(tasks): re-point all task readers to the centralized split-layout read"`

---

## Task 12: `plan_ledger_appends` pure helper

Implements spec §3 terminal routing + store-wide dedup (structural equality).

**Files:**
- Modify: `science/src/science_tool/tasks_ledger.py`
- Test: `science/tests/test_plan_ledger_appends.py` (add)

**Interfaces:**
- Produces: `plan_ledger_appends(terminal_tasks: list[Task], done_ledgers: dict[Path, list[Task]], *, today: date) -> tuple[dict[Path, str], list[str]]` — returns `{dest_path: full_post_image_text}` and a list of conflict ids. Pure (no I/O).
- Consumes: `_destination_for`, `render_tasks`, `_tasks_equal`.

- [ ] **Step 1: Write failing tests** — a terminal task absent everywhere → appended to its `_destination_for` month; a **structurally-equal** existing occurrence → no new append; an id present with any differing field → conflict; an id in **two** ledgers → conflict; undated terminal uses the explicit `today`.

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement** — index every `done_ledgers` task by id (collecting counts); for each terminal task: if id appears 0× → add to its destination's append set; if 1× and `_tasks_equal` → skip; if 1× and not equal, or ≥2× → conflict. Build each touched destination's post-image via `render_tasks(existing + appended)`; return post-images + conflicts. No writes.

- [ ] **Step 4: Run** — `pytest tests/test_plan_ledger_appends.py -q` → PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(tasks): pure store-wide ledger-append planner with structural-equality dedup"`

---

## Task 13: `migrate-storage` command (plan / apply / resume)

Implements spec §3 (whole section) + §1b mode validity.

**Files:**
- Modify: `science/src/science_tool/tasks_cli.py` (add `migrate-storage`), `science/src/science_tool/tasks_ledger.py` or a new `tasks_migrate.py` for the transaction core
- Test: `science/tests/test_migrate_storage.py` (add)

**Interfaces:**
- Produces: `plan_migration(tasks_dir, *, today) -> MigrationPlan`; `apply_migration(tasks_dir, *, today)`; `resume_migration(tasks_dir)`; journal at `.science/task-storage-migration.journal`.
- Consumes: `_tasks_storage_state`, `_parse_tasks_text`(aggregate `active.md`), `plan_ledger_appends`, `render_task_file`, `_task_allocation_lock`, `_destination_for`.

- [ ] **Step 1: Write failing tests** (the §Testing migrator bullets) — dry-run report; duplicate source id → refuse (offenders listed); colliding/existing open target → refuse; **unknown source status → refuse**; mixed open+terminal → open to `active/`, terminal to `done/` in one apply, `active.md` removed; store-wide dedup (undated terminal already in last month → not duplicated); source-hash safety (apply re-confirms pre-image; resume refuses on changed still-present `active.md`); resume states (absent→write, exact→accept, different→refuse+retain, crash-after-delete→clear); mode validity by state (`--apply` only LEGACY, `--resume` only MIGRATING).

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement plan** — parse aggregate `active.md` (`_parse_tasks_text`); partition into open/terminal over the known status sets, **refuse unknown status**; canonical-id + unique-source-id + unique/absent open-target-path checks; `plan_ledger_appends` over all `done/*.md` for terminal conflicts; refuse if `active/` non-empty or `active.md` absent. Build the post-image set: open → `render_task_file` at `active/{id}-{slug}.md`; terminal → the ledger post-images from `plan_ledger_appends` (with explicit `today`).

- [ ] **Step 4: Implement apply** — under `_task_allocation_lock`: journal pre-image hash of `active.md` + all post-images (path+content); write all `active/` files + ledger post-images; re-confirm `active.md` hash == pre-image (else refuse + retain journal); delete `active.md` last, confirm gone; clear journal.

- [ ] **Step 5: Implement resume** — under the lock: if `active.md` present, its hash must equal the journalled pre-image (else refuse+retain); for each journalled post-image classify absent→write / exact→accept / different→refuse+retain; once all exact (and source-hash ok or `active.md` gone) delete `active.md` if present and clear journal.

- [ ] **Step 6: Wire the Click command** — `tasks migrate-storage [--apply|--resume]`; default dry-run prints the plan; `--apply` valid only in LEGACY, `--resume` only in MIGRATING (else the state-specific refusal from §1b). Add a `BoundedSink` for its output per the budget convention.

- [ ] **Step 7: Run** — `pytest tests/test_migrate_storage.py -q` → PASS.

- [ ] **Step 8: Commit** — `git commit -m "feat(tasks): transactional migrate-storage command (plan/apply/resume, journalled)"`

---

## Task 14: Retire `tasks archive` + remove the archive-lag health surface

Implements spec §Decision-3 + §4 "Archive-lag health-report removal — the full public surface".

**Files:**
- Delete: `science/src/science_tool/graph/health_checks/archive_lag.py`
- Modify: `tasks_cli.py` (remove `tasks archive` command `:392-…`), `tasks_archive.py` (remove `plan_archive`/`apply_archive`/`count_archivable`; keep nothing that's now unused → delete the module if empty), `graph/health_checks/__init__.py:12,40`, `graph/health_cli.py:88,168-169,229-230`, `graph/health_projection.py:47,68,335-336`, `graph/health_count.py:8,62`, `instruments.py:56`, budget registry (`tasks-archive` entry)
- Test: `science/tests/graph/test_health*.py` (regenerate snapshots), delete `test_tasks_archive.py` archive-sweep tests
- **Docs:** deferred to Task 16

**Interfaces:** removal only.

- [ ] **Step 1: Write/adjust failing tests** — invoking `tasks archive` errors (unknown command); the projected/rendered/counted health report has **no `archive_lag` section**; no import of `tasks_archive.{plan_archive,apply_archive,count_archivable}` remains (`grep` guard test). Update health snapshot fixtures.

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Remove** every enumerated surface. Confirm `tasks_ledger` still holds the primitives Task 2 relocated (do not delete those). If `tasks_archive.py` is now empty, delete it and drop its imports; else leave only what's still referenced (should be nothing → delete).

- [ ] **Step 4: Run** — `cd science && uv run --frozen pytest tests/graph -q -k "health"` and `uv run --frozen pytest tests/test_tasks_cli.py -q`; regenerate snapshots (`-m snapshot` where applicable) → PASS. Then `uv run ruff check && uv run pyright` (import removals often surface here).

- [ ] **Step 5: Commit** — `git commit -m "refactor(tasks): retire tasks archive command and archive-lag health surface"`

---

## Task 15: Storage adapter reads per-task files

Implements spec §4 adapter bullet.

**Files:**
- Modify: `science/src/science_tool/graph/storage_adapters/task.py`
- Test: `science/tests/graph/test_storage_adapters_task.py` (or existing adapter test)

**Interfaces:**
- Consumes: `parse_task_file` (for `tasks/active/*.md`), existing DSL `_parse_task_block` (for `tasks/done/*.md`).

- [ ] **Step 1: Write failing test** — a graph build over a split `tasks/active/` yields the same task nodes as an aggregate `active.md` would; `done/*.md` still parses.

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement** — in `discover()`/`load_raw`, route files under `tasks/active/` through `parse_task_file` and `tasks/done/*.md` through the DSL parser (skip `archive.md`).

- [ ] **Step 4: Run** — `pytest tests/graph/test_storage_adapters_task.py -q` → PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(graph): task storage adapter parses per-task active files"`

---

## Task 16: Docs, templates, content guard, scoped archive-retirement docs

Implements spec §4 docs bullets.

**Files:**
- Modify: `docs/user-guide/big-picture.md:68`, `commands/create-graph.md:48`, `templates/agents-md.md`, `templates/core-overview.md`, the `create-project` scaffold section, `science/tests/test_no_raw_task_file_reads_in_docs.py` allow-list; plus current user/reference docs + help text mentioning `tasks archive`
- Test: `test_no_raw_task_file_reads_in_docs.py`

- [ ] **Step 1:** Update the aggregate-`active.md` descriptions to `tasks/active/` one-file-per-task (do **not** reopen Slice-2 read-directive rules — docs still point agents at `science tasks list`). Update the content-guard allow-list for any changed legit line.

- [ ] **Step 2: Archive-retirement docs — scoped.** `grep -rn "tasks archive\|count_archivable" docs commands templates`; triage each hit: **current** user/reference/help/active-design → rewrite; **historical** plan/audit under `docs/plans/` → preserve (optionally a one-line marked retrospective note). Do not rewrite history.

- [ ] **Step 3: Run** — `cd science && uv run --frozen pytest tests/test_no_raw_task_file_reads_in_docs.py -q` → PASS.

- [ ] **Step 4: Commit** — `git commit -m "docs: describe per-task active/ storage; scope archive-retirement doc updates"`

---

## Task 17: Migrate `science/meta` (worked example)

Implements spec §3 worked example + decision 2.

**Files:**
- Modify: `science/meta/tasks/` (migrated: `active.md` removed, `active/tNNN-*.md` created, terminal `t089`/`t093` routed into a `done/` ledger)

- [ ] **Step 1: Verify branch** — `git -C /path/to/worktree branch --show-current` == `context-budget-slice3` (Dropbox volatility; meta is in-repo so commits land here).

- [ ] **Step 2: Dry-run** — `cd science && uv run --frozen science tasks migrate-storage --tasks-dir ../meta/tasks` (or the meta project's invocation); review the plan: open tasks → `active/`, `t089`/`t093` → `done/`.

- [ ] **Step 3: Apply** — `... migrate-storage --apply` on `meta/tasks`.

- [ ] **Step 4: Verify** — `science tasks list` (in meta) is unchanged vs a pre-migration capture; `t089`/`t093` are in a `done/` ledger, not `active/`; `git status` shows `active.md` deleted + `active/*.md` added.

- [ ] **Step 5: Run** — `cd science && uv run --frozen pytest -q` scoped to `tests/test_migrate_storage.py` plus a meta smoke (or `science graph build` on meta if cheap) → clean.

- [ ] **Step 6: Commit** — `git commit -m "chore(meta): migrate task storage to per-task active/ layout"`

---

## Final validation (top-level agent, after all tasks)

- [ ] Full suite: `cd science && uv run --frozen pytest` (allow ~2-3 min; do not background-and-yield) and `cd science/model && uv run --frozen pytest`.
- [ ] `cd science && uv run ruff check && uv run pyright`.
- [ ] Grep guards: no `tasks_dir / "active.md"` reader remains outside the migrator/tests; no live import of retired archive functions.

## Self-Review (author)

- **Spec coverage:** §1 → Tasks 3,4; §1a → Tasks 4,5,6,8; §1b → Task 7; §2 → Tasks 6,8,9,10,11; §3 → Tasks 12,13; §4 → Tasks 3,14,15,16; decisions 1/2/3 → Tasks 4/17/(2,14). Every §Testing bullet maps to a task's tests.
- **Type consistency:** `_tasks_equal`/`_canonical_description` (Task 3) reused by the predicates (Tasks 8,12); `plan_ledger_appends` signature identical in Tasks 12 and 13; `_read_active(require_split=)` introduced in Task 7 and used in Task 9.
- **Ordering:** serialization primitives (1–5) precede the read/write layer (6–9), which precedes CLI/readers (10–11), the migrator (12–13), retirement (14), adapter/docs/meta (15–17). `tasks_archive` stays importable until Task 14 so the tree is green throughout.

## Execution Handoff

Plan saved to `docs/plans/2026-07-26-context-budget-slice3-storage-implementation.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh implementer per task, task review (spec + quality) between tasks, broad whole-branch review at the end.
2. **Inline Execution** — executing-plans, batched with checkpoints.

Which approach?
