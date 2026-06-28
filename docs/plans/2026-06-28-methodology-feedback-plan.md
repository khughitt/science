# Methodology Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing `science feedback` system with a namespaced `concern` field (`tooling` vs `methodology:*`) and a guided `/science:post-mortem` reflection skill, so generalized scientific-methodology lessons are captured in the same store as tooling feedback and can be filtered as one lens.

**Architecture:** One new field on `FeedbackEntry`, made part of entry identity so it partitions dedup and triage grouping/clustering. CLI gains `--concern` on `add`/`list`/`update`/`triage`/`report`. A new `commands/post-mortem.md` command guides the post-hoc reflection and emits lessons via the extended `feedback add`; its Codex counterpart is generated. No new persistence surface, no migration.

**Tech Stack:** Python 3.12+, Pydantic v2, Click, pytest, PyYAML. Code lives in `science/src/science_tool/`; tests in `science/tests/`; commands in `commands/` (Codex skills generated into `codex-skills/`).

## Global Constraints

- Spec: `docs/plans/2026-06-28-methodology-feedback-design.md`. Every task implicitly inherits these.
- Do **not** work on `main`. Create a feature branch (e.g. `methodology-feedback`) before the first commit.
- Commit messages: **no** `Co-Authored-By` trailer (per repo rule).
- `concern` vocabulary is the controlled set: `tooling`, `methodology:statistics`, `methodology:qa`, `methodology:design`, `methodology:data-fitness`, `methodology:reasoning`. Default `tooling`.
- Fail-loud: an unknown `concern` is rejected (no silent fallback).
- Backward-compatible: legacy YAML without `concern` loads as `tooling`; existing tests stay green; no data migration.
- `concern` and `category` stay orthogonal — do **not** touch the `category` vocab.
- Triage grouping must not leak a raw `(concern, target)` tuple into CLI headings or the telemetry join; grouped values carry explicit `concern` and `target` fields and the telemetry call uses `group["target"]`.
- **Test runner:** plain `python -m pytest` fails here (`ModuleNotFoundError: No module named 'science_tool'`). Use the repo-standard runner: `cd science && uv run --frozen pytest tests/test_feedback.py tests/test_feedback_cli.py -v`. All test/CLI commands in this plan assume `uv run --frozen`.
- Worktree note: an editable-installed `science_model` from `main` can shadow worktree edits; `uv run --frozen` from the worktree's `science/` uses the locked env. If `science_model` symbols look stale, that's the cause.

---

## File Structure

- `science/src/science_tool/feedback.py` — add `VALID_CONCERNS`, `_validate_concern_value`, `FeedbackEntry.concern` + validator; widen `find_duplicate`, `list_entries`, `update_entry`, `group_for_triage`, `cluster_for_triage`, `_FeedbackCluster`, `_matching_cluster`, `_cluster_row`, `render_report`.
- `science/src/science_tool/cli.py` — `_FB_CONCERNS`; `--concern` on `add`/`list`/`update`/`triage`/`report`; triage tuple-unpack + Concern column; report passthrough.
- `science/tests/test_feedback.py` — schema, dedup, list/update, grouping/clustering, report unit tests.
- `science/tests/test_feedback_cli.py` — CLI integration tests for `--concern`.
- `commands/post-mortem.md` — new guided reflection command (durable source).
- `commands/interpret-results.md` — soft handoff pointer.
- `codex-skills/science-post-mortem/SKILL.md`, `codex-skills/INDEX.md` — **generated** by `python scripts/generate_codex_skills.py` (do not hand-edit).

---

## Task 1: Add `concern` field to the schema

**Files:**
- Modify: `science/src/science_tool/feedback.py:15` (import), `:17` (constants), `:35-48` (model)
- Test: `science/tests/test_feedback.py`

**Interfaces:**
- Produces: `VALID_CONCERNS: tuple[str, ...]`; `_validate_concern_value(value: str) -> str`; `FeedbackEntry.concern: str` (default `"tooling"`, validated).

- [ ] **Step 1: Write the failing tests**

In `science/tests/test_feedback.py` (add near the other `FeedbackEntry` tests; ensure `import pytest` and `from pydantic import ValidationError` are present, and `from science_tool.feedback import FeedbackEntry, load_entry, VALID_CONCERNS`):

```python
def test_concern_defaults_to_tooling():
    entry = FeedbackEntry(id="fb-2026-06-28-001", target="command:x", summary="s")
    assert entry.concern == "tooling"


def test_concern_accepts_methodology_value():
    entry = FeedbackEntry(
        id="fb-2026-06-28-001",
        target="skill:statistics",
        summary="s",
        concern="methodology:statistics",
    )
    assert entry.concern == "methodology:statistics"


def test_concern_rejects_unknown_value():
    with pytest.raises(ValidationError):
        FeedbackEntry(id="fb-2026-06-28-001", target="x", summary="s", concern="bogus")


def test_legacy_yaml_without_concern_loads_as_tooling(tmp_path):
    path = tmp_path / "fb-2026-01-01-001.yaml"
    path.write_text(
        "id: fb-2026-01-01-001\ncreated: '2026-01-01'\n"
        "target: command:x\nsummary: s\n",
        encoding="utf-8",
    )
    entry = load_entry(path)
    assert entry.concern == "tooling"


def test_valid_concerns_membership():
    assert "tooling" in VALID_CONCERNS
    assert "methodology:statistics" in VALID_CONCERNS
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_feedback.py -k concern -v`
Expected: FAIL (`AttributeError`/`ImportError` — `concern` and `VALID_CONCERNS` don't exist).

- [ ] **Step 3: Implement the field, vocab, and validator**

In `feedback.py`, change the pydantic import (line 15):

```python
from pydantic import BaseModel, Field, field_validator
```

Add after `VALID_STATUSES` (line 18):

```python
VALID_CONCERNS = (
    "tooling",
    "methodology:statistics",
    "methodology:qa",
    "methodology:design",
    "methodology:data-fitness",
    "methodology:reasoning",
)


def _validate_concern_value(value: str) -> str:
    if value not in VALID_CONCERNS:
        allowed = ", ".join(VALID_CONCERNS)
        msg = f"Invalid concern {value!r}; must be one of: {allowed}"
        raise ValueError(msg)
    return value
```

Add the field + validator to `FeedbackEntry` (after `related`, making `concern` the last field):

```python
    related: list[str] = Field(default_factory=list)
    concern: str = "tooling"

    @field_validator("concern")
    @classmethod
    def _check_concern(cls, value: str) -> str:
        return _validate_concern_value(value)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_feedback.py -k concern -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full feedback unit suite for regressions**

Run: `cd science && uv run --frozen pytest tests/test_feedback.py -v`
Expected: PASS (all prior tests still green; `concern` defaults keep them valid).

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/feedback.py science/tests/test_feedback.py
git commit -m "feat(feedback): add validated concern field to FeedbackEntry"
```

---

## Task 2: Make `concern` part of duplicate identity

**Files:**
- Modify: `science/src/science_tool/feedback.py:177-194` (`find_duplicate`)
- Test: `science/tests/test_feedback.py`

**Interfaces:**
- Consumes: `FeedbackEntry.concern` (Task 1).
- Produces: `find_duplicate(feedback_dir, *, target, summary, concern="tooling") -> FeedbackEntry | None`.

- [ ] **Step 1: Write the failing test**

In `science/tests/test_feedback.py` (uses `save_entry`, `find_duplicate`, `FeedbackEntry`):

```python
def test_find_duplicate_distinguishes_concern(tmp_path):
    base = dict(target="skill:statistics", summary="check independence assumption", status="open")
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-06-28-001", concern="tooling", **base))

    # Same target + same summary but different concern → NOT a duplicate.
    dup = find_duplicate(
        tmp_path,
        target="skill:statistics",
        summary="check independence assumption",
        concern="methodology:statistics",
    )
    assert dup is None

    # Same target + summary + concern → IS a duplicate.
    same = find_duplicate(
        tmp_path,
        target="skill:statistics",
        summary="check independence assumption",
        concern="tooling",
    )
    assert same is not None
    assert same.id == "fb-2026-06-28-001"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_feedback.py::test_find_duplicate_distinguishes_concern -v`
Expected: FAIL (`TypeError: unexpected keyword argument 'concern'`).

- [ ] **Step 3: Add `concern` to `find_duplicate`**

Replace `find_duplicate` (lines 177-194) with:

```python
def find_duplicate(
    feedback_dir: Path,
    *,
    target: str,
    summary: str,
    concern: str = "tooling",
) -> FeedbackEntry | None:
    """Find an existing open entry with the same target, concern, and similar summary.

    Uses bidirectional substring matching on summary. Entries differing in
    concern are distinct even when target and summary match.
    """
    entries = list_entries(feedback_dir, status="open", target=target)
    summary_lower = summary.lower()
    for entry in entries:
        if entry.concern != concern:
            continue
        entry_summary_lower = entry.summary.lower()
        if summary_lower in entry_summary_lower or entry_summary_lower in summary_lower:
            return entry
    return None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_feedback.py::test_find_duplicate_distinguishes_concern -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/feedback.py science/tests/test_feedback.py
git commit -m "feat(feedback): key duplicate detection on concern"
```

---

## Task 3: `concern` filtering in `list_entries` and correction in `update_entry`

**Files:**
- Modify: `science/src/science_tool/feedback.py:112-135` (`list_entries`), `:138-174` (`update_entry`)
- Test: `science/tests/test_feedback.py`

**Interfaces:**
- Produces: `list_entries(..., concern: str | None = None)` with fnmatch glob on `concern`; `update_entry(..., concern: str | None = None)` validating via `_validate_concern_value`.

- [ ] **Step 1: Write the failing tests**

```python
def test_list_entries_filters_concern_glob(tmp_path):
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-06-28-001", target="command:x", summary="a", concern="tooling"))
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-06-28-002", target="skill:statistics", summary="b", concern="methodology:statistics"))
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-06-28-003", target="skill:qa", summary="c", concern="methodology:qa"))

    methodology = list_entries(tmp_path, status="open", concern="methodology:*")
    assert {e.id for e in methodology} == {"fb-2026-06-28-002", "fb-2026-06-28-003"}

    tooling = list_entries(tmp_path, status="open", concern="tooling")
    assert {e.id for e in tooling} == {"fb-2026-06-28-001"}


def test_update_entry_sets_concern(tmp_path):
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-06-28-001", target="skill:statistics", summary="a", concern="tooling"))
    updated = update_entry(tmp_path, "fb-2026-06-28-001", concern="methodology:statistics")
    assert updated.concern == "methodology:statistics"
    assert load_entry(tmp_path / "fb-2026-06-28-001.yaml").concern == "methodology:statistics"


def test_update_entry_rejects_unknown_concern(tmp_path):
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-06-28-001", target="x", summary="a"))
    with pytest.raises(ValueError):
        update_entry(tmp_path, "fb-2026-06-28-001", concern="bogus")
```

Ensure `update_entry` is imported in the test module.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_feedback.py -k "filters_concern_glob or update_entry_sets_concern or update_entry_rejects_unknown_concern" -v`
Expected: FAIL (`TypeError: unexpected keyword argument 'concern'`).

- [ ] **Step 3: Add the `concern` filter to `list_entries`**

In `list_entries`, add the parameter (after `project`):

```python
    project: str | None = None,
    concern: str | None = None,
) -> list[FeedbackEntry]:
```

and the filter (after the `category` filter block, before the `project` block — order does not matter, keep grouped with the other glob filter):

```python
    if concern is not None:
        entries = [e for e in entries if fnmatch(e.concern, concern)]
```

- [ ] **Step 4: Add `concern` correction to `update_entry`**

Add the parameter (after `detail`):

```python
    detail: str | None = None,
    related: list[str] | None = None,
    concern: str | None = None,
) -> FeedbackEntry:
```

and the assignment (after the `related` block, before `save_entry`):

```python
    if concern is not None:
        entry.concern = _validate_concern_value(concern)
```

(Default Pydantic does not re-validate on assignment, so call `_validate_concern_value` explicitly to stay fail-loud.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_feedback.py -k "filters_concern_glob or update_entry_sets_concern or update_entry_rejects_unknown_concern" -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/feedback.py science/tests/test_feedback.py
git commit -m "feat(feedback): filter list by concern and allow concern correction on update"
```

---

## Task 4: Partition triage grouping and clustering by `concern`

**Files:**
- Modify: `science/src/science_tool/feedback.py:51-61` (`_FeedbackCluster`), `:197-223` (`group_for_triage`), `:226-269` (`cluster_for_triage`), `:363-374` (`_matching_cluster`), `:377-390` (`_cluster_row`)
- Test: `science/tests/test_feedback.py`

**Interfaces:**
- Produces:
  - `group_for_triage(..., concern: str | None = None) -> dict[tuple[str, str], dict]` where each value has keys `concern`, `target`, `entries`, `projects`, `total_recurrence`.
  - `cluster_for_triage(..., concern: str | None = None) -> list[dict]` where each row includes a `concern` key.

- [ ] **Step 1: Write the failing tests**

```python
def test_group_for_triage_partitions_by_concern(tmp_path):
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-06-28-001", target="skill:statistics", summary="a", concern="tooling"))
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-06-28-002", target="skill:statistics", summary="b", concern="methodology:statistics"))

    groups = group_for_triage(tmp_path)
    assert set(groups.keys()) == {("tooling", "skill:statistics"), ("methodology:statistics", "skill:statistics")}
    for (concern_key, target_key), group in groups.items():
        assert group["concern"] == concern_key
        assert group["target"] == target_key


def test_cluster_for_triage_includes_concern(tmp_path):
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-06-28-001", target="skill:statistics", summary="check independence", concern="methodology:statistics"))
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-06-28-002", target="skill:statistics", summary="check independence", concern="tooling"))

    rows = cluster_for_triage(tmp_path)
    concerns = {row["concern"] for row in rows}
    assert concerns == {"methodology:statistics", "tooling"}
    # Same target + similar summary but different concern must not merge.
    assert all(row["count"] == 1 for row in rows)
```

Ensure `group_for_triage` and `cluster_for_triage` are imported in the test module.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_feedback.py -k "partitions_by_concern or cluster_for_triage_includes_concern" -v`
Expected: FAIL (`KeyError`/wrong keys — grouping keys on target only).

- [ ] **Step 3: Add `concern` to `_FeedbackCluster`**

Insert `concern: str` after `target` (line 53):

```python
@dataclass
class _FeedbackCluster:
    target: str
    concern: str
    category: str
    summary_key: str
    representative_summary: str
    entries: list[FeedbackEntry] = field(default_factory=list)
    projects: set[str] = field(default_factory=set)
    tokens: set[str] = field(default_factory=set)
    total_recurrence: int = 0
    newest_created: str = ""
```

- [ ] **Step 4: Rewrite `group_for_triage`**

Replace lines 197-223 with:

```python
def group_for_triage(
    feedback_dir: Path,
    *,
    target: str | None = None,
    concern: str | None = None,
) -> dict[tuple[str, str], dict]:
    """Group open entries by (concern, target) for triage display.

    Returns: {(concern, target): {concern, target, entries, projects, total_recurrence}}
    Sorted by total_recurrence descending. The grouped value carries explicit
    `concern` and `target` so callers never read the tuple key for display or
    telemetry joins.
    """
    entries = list_entries(feedback_dir, status="open", target=target, concern=concern)

    groups: dict[tuple[str, str], dict] = {}
    for entry in entries:
        key = (entry.concern, entry.target)
        if key not in groups:
            groups[key] = {
                "concern": entry.concern,
                "target": entry.target,
                "entries": [],
                "projects": set(),
                "total_recurrence": 0,
            }
        groups[key]["entries"].append(entry)
        if entry.project:
            groups[key]["projects"].add(entry.project)
        groups[key]["total_recurrence"] += entry.recurrence

    return dict(sorted(groups.items(), key=lambda item: -item[1]["total_recurrence"]))
```

- [ ] **Step 5: Add `concern` to `cluster_for_triage`**

In `cluster_for_triage` (lines 226-251), add the parameter and pass it to `list_entries`, and set `concern` when constructing a cluster:

```python
def cluster_for_triage(
    feedback_dir: Path,
    *,
    target: str | None = None,
    concern: str | None = None,
    since_days: int | None = None,
    today: date | None = None,
) -> list[dict[str, object]]:
    """Cluster open entries by concern, target, category, and near-duplicate summary."""
    entries = list_entries(feedback_dir, status="open", target=target, concern=concern)
```

and in the cluster-creation block:

```python
        if cluster is None:
            cluster = _FeedbackCluster(
                target=entry.target,
                concern=entry.concern,
                category=entry.category,
                summary_key=_summary_key(entry.summary),
                representative_summary=entry.summary,
                newest_created=entry.created,
            )
            clusters.append(cluster)
```

- [ ] **Step 6: Add `concern` to `_matching_cluster` and `_cluster_row`**

In `_matching_cluster` (line 370), widen the guard:

```python
        if cluster.target != entry.target or cluster.concern != entry.concern or cluster.category != entry.category:
            continue
```

In `_cluster_row` (line 379), add the key:

```python
    return {
        "target": cluster.target,
        "concern": cluster.concern,
        "category": cluster.category,
        "summary_key": cluster.summary_key,
        "representative_summary": cluster.representative_summary,
        "entry_ids": [entry.id for entry in entries],
        "count": len(entries),
        "total_recurrence": cluster.total_recurrence,
        "projects": sorted(cluster.projects),
        "suggested_status": _suggested_status(target=cluster.target, category=cluster.category, count=len(entries)),
        "suggested_next_test_target": _suggested_next_test_target(cluster.target),
    }
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_feedback.py -k "partitions_by_concern or cluster_for_triage_includes_concern" -v`
Expected: PASS (2 tests).

- [ ] **Step 8: Rewrite the two pre-existing `group_for_triage` tests that key on a bare target**

These two tests **will** break (re-keying to `(concern, target)`): `test_group_for_triage` indexes `groups["command:discuss"]`, and `test_group_for_triage_with_target_glob` does `"command:discuss" in groups` (now a tuple-key membership test → silently `False`). The `_make_entry` helper leaves `concern` at its default `"tooling"`, so the new keys are `("tooling", "<target>")`.

Replace `test_group_for_triage` (currently ~lines 293-303) with:

```python
def test_group_for_triage(tmp_path: Path):
    _make_entry(tmp_path, "fb-2026-03-25-001", target="command:discuss", project="proj-a")
    _make_entry(tmp_path, "fb-2026-03-25-002", target="command:discuss", project="proj-b")
    _make_entry(tmp_path, "fb-2026-03-25-003", target="command:next-steps", project="proj-a")

    groups = group_for_triage(tmp_path)
    discuss_key = ("tooling", "command:discuss")
    assert discuss_key in groups
    assert ("tooling", "command:next-steps") in groups
    assert groups[discuss_key]["concern"] == "tooling"
    assert groups[discuss_key]["target"] == "command:discuss"
    assert len(groups[discuss_key]["entries"]) == 2
    assert groups[discuss_key]["projects"] == {"proj-a", "proj-b"}
    assert groups[discuss_key]["total_recurrence"] == 2
```

Replace `test_group_for_triage_with_target_glob` (currently ~lines 306-311) with:

```python
def test_group_for_triage_with_target_glob(tmp_path: Path):
    _make_entry(tmp_path, "fb-2026-03-25-001", target="command:discuss")
    _make_entry(tmp_path, "fb-2026-03-25-002", target="template:discussion")
    groups = group_for_triage(tmp_path, target="command:*")
    assert ("tooling", "command:discuss") in groups
    assert ("tooling", "template:discussion") not in groups
```

- [ ] **Step 9: Run the full feedback unit suite**

Run: `cd science && uv run --frozen pytest tests/test_feedback.py -v`
Expected: PASS (all tests, including the two rewritten above). No other test in this file keys on a bare target — `test_render_report` uses substring checks against the rendered `### command:discuss`, and the cluster tests assert on row dict values, not group keys.

- [ ] **Step 10: Commit**

```bash
git add science/src/science_tool/feedback.py science/tests/test_feedback.py
git commit -m "feat(feedback): partition triage grouping and clustering by concern"
```

---

## Task 5: `concern`-aware report grouping

**Files:**
- Modify: `science/src/science_tool/feedback.py:450-480` (`render_report`)
- Test: `science/tests/test_feedback.py`

**Interfaces:**
- Produces: `render_report(..., concern: str | None = None)` grouping `concern → target` (`##` concern, `###` target).

- [ ] **Step 1: Write the failing test**

```python
def test_render_report_groups_by_concern_then_target(tmp_path):
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-06-28-001", target="command:x", summary="tool issue", concern="tooling"))
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-06-28-002", target="skill:statistics", summary="assumption gap", concern="methodology:statistics"))

    report = render_report(tmp_path)
    assert "## methodology:statistics" in report
    assert "### skill:statistics" in report
    assert "## tooling" in report
    # concern heading precedes its target subheading
    assert report.index("## methodology:statistics") < report.index("### skill:statistics")

    filtered = render_report(tmp_path, concern="methodology:*")
    assert "skill:statistics" in filtered
    assert "command:x" not in filtered
```

Ensure `render_report` is imported in the test module.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_feedback.py::test_render_report_groups_by_concern_then_target -v`
Expected: FAIL (no `## methodology:statistics`; current report groups by target only and has no `concern` param).

- [ ] **Step 3: Rewrite `render_report`**

Replace lines 450-480 with:

```python
def render_report(
    feedback_dir: Path,
    *,
    status: str | None = None,
    project: str | None = None,
    concern: str | None = None,
) -> str:
    """Render a human-readable markdown report grouped by concern then target."""
    entries = list_entries(feedback_dir, status=status, project=project, concern=concern)

    if not entries:
        return "No feedback entries found.\n"

    by_concern: dict[str, dict[str, list[FeedbackEntry]]] = {}
    for entry in entries:
        by_concern.setdefault(entry.concern, {}).setdefault(entry.target, []).append(entry)

    lines = ["# Feedback Report", ""]
    # Alphabetical order is intentional: methodology:* groups sort before
    # tooling, giving the methodology lens top billing. A future reorder must
    # not break the Task-5 test that relies on this.
    for concern_value, by_target in sorted(by_concern.items()):
        lines.append(f"## {concern_value}")
        lines.append("")
        for target, group in sorted(by_target.items()):
            lines.append(f"### {target}")
            lines.append("")
            for entry in group:
                status_badge = f"[{entry.status}]"
                lines.append(f"- **{entry.id}** {status_badge} ({entry.category}) — {entry.summary}")
                if entry.recurrence > 1:
                    lines.append(f"  - Recurrence: {entry.recurrence}")
                if entry.resolution:
                    lines.append(f"  - Resolution: {entry.resolution}")
            lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_feedback.py::test_render_report_groups_by_concern_then_target -v`
Expected: PASS.

- [ ] **Step 5: Run the full feedback unit suite**

Run: `cd science && uv run --frozen pytest tests/test_feedback.py -v`
Expected: PASS (update any prior report test asserting `## command:...` to the new `## <concern>` / `### <target>` shape).

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/feedback.py science/tests/test_feedback.py
git commit -m "feat(feedback): group report by concern then target"
```

---

## Task 6: Wire `--concern` through the CLI

**Files:**
- Modify: `science/src/science_tool/cli.py:5531` (constants), `:5548-5620` (`add`), `:5641-5684` (`list`), `:5687-5721` (`update`), `:5724-5819` (`triage`), `:5895-5904` (`report`)
- Test: `science/tests/test_feedback_cli.py`

**Interfaces:**
- Consumes: all `feedback.py` functions from Tasks 1-5.
- Produces: `--concern` option on `feedback add` (Choice, default `tooling`), `feedback update` (Choice), `feedback list`/`triage`/`report` (free string glob); triage tuple-unpack + Concern column.

- [ ] **Step 1: Write the failing CLI tests**

In `science/tests/test_feedback_cli.py` (uses the existing `CliRunner`/`SCIENCE_FEEDBACK_DIR` fixture pattern already in the file; mirror how other tests set the feedback dir):

```python
def test_add_with_concern_round_trips(tmp_path, monkeypatch):
    monkeypatch.setenv("SCIENCE_FEEDBACK_DIR", str(tmp_path))
    from science_tool.cli import main
    runner = CliRunner()
    result = runner.invoke(main, [
        "feedback", "add",
        "--target", "skill:statistics",
        "--summary", "needs an independence check",
        "--concern", "methodology:statistics",
    ])
    assert result.exit_code == 0, result.output
    from science_tool.feedback import list_entries
    entries = list_entries(tmp_path, status="open")
    assert len(entries) == 1
    assert entries[0].concern == "methodology:statistics"


def test_add_rejects_unknown_concern(tmp_path, monkeypatch):
    monkeypatch.setenv("SCIENCE_FEEDBACK_DIR", str(tmp_path))
    from science_tool.cli import main
    runner = CliRunner()
    result = runner.invoke(main, [
        "feedback", "add", "--target", "x", "--summary", "s", "--concern", "bogus",
    ])
    assert result.exit_code != 0


def test_add_distinct_concern_not_deduplicated(tmp_path, monkeypatch):
    # Regression: `add` must thread --concern into find_duplicate, so the same
    # target+summary under a different concern creates a SECOND entry rather
    # than incrementing recurrence on the first.
    monkeypatch.setenv("SCIENCE_FEEDBACK_DIR", str(tmp_path))
    from science_tool.cli import main
    from science_tool.feedback import list_entries
    runner = CliRunner()

    first = runner.invoke(main, [
        "feedback", "add", "--target", "skill:statistics",
        "--summary", "check independence assumption",
        # no --concern → defaults to tooling
    ])
    assert first.exit_code == 0, first.output

    second = runner.invoke(main, [
        "feedback", "add", "--target", "skill:statistics",
        "--summary", "check independence assumption",
        "--concern", "methodology:statistics",
    ])
    assert second.exit_code == 0, second.output
    assert "Incremented recurrence" not in second.output

    yaml_files = sorted(tmp_path.glob("fb-*.yaml"))
    assert len(yaml_files) == 2
    entries = list_entries(tmp_path, status="open")
    assert {e.concern for e in entries} == {"tooling", "methodology:statistics"}
    assert all(e.recurrence == 1 for e in entries)


def test_list_filters_by_concern_glob(tmp_path, monkeypatch):
    monkeypatch.setenv("SCIENCE_FEEDBACK_DIR", str(tmp_path))
    from science_tool.cli import main
    from science_tool.feedback import FeedbackEntry, save_entry
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-06-28-001", target="command:x", summary="a", concern="tooling"))
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-06-28-002", target="skill:statistics", summary="b", concern="methodology:statistics"))
    runner = CliRunner()
    result = runner.invoke(main, ["feedback", "list", "--concern", "methodology:*", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert "fb-2026-06-28-002" in result.output
    assert "fb-2026-06-28-001" not in result.output


def test_update_corrects_concern(tmp_path, monkeypatch):
    monkeypatch.setenv("SCIENCE_FEEDBACK_DIR", str(tmp_path))
    from science_tool.cli import main
    from science_tool.feedback import FeedbackEntry, save_entry, load_entry
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-06-28-001", target="skill:statistics", summary="a", concern="tooling"))
    runner = CliRunner()
    result = runner.invoke(main, ["feedback", "update", "fb-2026-06-28-001", "--concern", "methodology:statistics"])
    assert result.exit_code == 0, result.output
    assert load_entry(tmp_path / "fb-2026-06-28-001.yaml").concern == "methodology:statistics"


def test_fb_concerns_constant_matches_lib():
    # Fail-loud guard against vocab drift between the CLI's click.Choice tuple
    # and the library SSOT. (We keep a literal copy to satisfy click.Choice at
    # decoration time, matching the existing _FB_CATEGORIES/_FB_STATUSES pattern.)
    from science_tool.cli import _FB_CONCERNS
    from science_tool.feedback import VALID_CONCERNS
    assert _FB_CONCERNS == VALID_CONCERNS


def test_triage_group_heading_shows_concern(tmp_path, monkeypatch):
    monkeypatch.setenv("SCIENCE_FEEDBACK_DIR", str(tmp_path))
    from science_tool.cli import main
    from science_tool.feedback import FeedbackEntry, save_entry
    save_entry(tmp_path, FeedbackEntry(id="fb-2026-06-28-001", target="skill:statistics", summary="a", concern="methodology:statistics"))
    runner = CliRunner()
    result = runner.invoke(main, ["feedback", "triage"])
    assert result.exit_code == 0, result.output
    assert "methodology:statistics" in result.output
    assert "skill:statistics" in result.output
```

(If the existing tests use a shared fixture rather than `monkeypatch.setenv`, follow that fixture instead — match the file's established pattern.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_feedback_cli.py -k "concern or triage_group_heading" -v`
Expected: FAIL (`--concern` is not a known option).

- [ ] **Step 3: Add the `_FB_CONCERNS` constant**

After `_FB_STATUSES` (line 5532) in `cli.py`:

```python
# Keep in sync with science_tool.feedback.VALID_CONCERNS.
_FB_CONCERNS = (
    "tooling",
    "methodology:statistics",
    "methodology:qa",
    "methodology:design",
    "methodology:data-fitness",
    "methodology:reasoning",
)
```

- [ ] **Step 4: Wire `feedback add`**

Add the option after `--category` (line 5552):

```python
@click.option("--concern", default=None, type=click.Choice(_FB_CONCERNS), help="tooling (default) or a methodology:* lens")
```

Add `concern: str | None,` to the signature (after `category`). Then, after `category = category or "suggestion"` (line 5593), add:

```python
    concern = concern or "tooling"
```

Pass `concern` to `find_duplicate` (line 5599):

```python
    dup = find_duplicate(fb_dir, target=target, summary=summary, concern=concern)
```

and to `FeedbackEntry(...)` (line 5609):

```python
    entry = FeedbackEntry(
        id=entry_id,
        created=today,
        project=project,
        target=target,
        category=category,
        summary=summary,
        detail=detail,
        related=list(related),
        concern=concern,
    )
```

- [ ] **Step 5: Wire `feedback list`**

Add the option after `--project` (line 5645):

```python
@click.option("--concern", default=None, help="Filter by concern (supports fnmatch globs, e.g. 'methodology:*')")
```

Add `concern: str | None,` to the signature, pass `concern=concern` into `list_entries(...)` (line 5661), and add a Concern column to `columns` and each row dict:

```python
        ("target", "Target"),
        ("concern", "Concern"),
        ("category", "Category"),
```

```python
            "target": e.target,
            "concern": e.concern,
            "category": e.category,
```

- [ ] **Step 6: Wire `feedback update`**

Add the option after `--category` (line 5691):

```python
@click.option("--concern", default=None, type=click.Choice(_FB_CONCERNS))
```

Add `concern: str | None,` to the signature and pass `concern=concern` into the `_update(...)` call.

- [ ] **Step 7: Wire `feedback triage` (filter, Concern column, tuple-unpack)**

Add the option after `--target` (line 5725):

```python
@click.option("--concern", default=None, help="Filter by concern (fnmatch glob)")
```

Add `concern: str | None,` to the signature. Pass `concern=concern` into both `cluster_for_triage(...)` (line 5746) and `group_for_triage(...)` (line 5789).

Add a Concern column to the cluster `columns` list (after Target, line 5768):

```python
            ("target", "Target"),
            ("concern", "Concern"),
            ("category", "Category"),
```

Replace the grouped-display loop (lines 5801-5819) so it unpacks the `(concern, target)` key and uses `group["target"]` for telemetry:

```python
    for (concern_key, target_key), group in groups.items():
        n_projects = len(group["projects"])
        n_entries = len(group["entries"])
        total_recur = group["total_recurrence"]
        projects_str = ", ".join(sorted(group["projects"])) if group["projects"] else "unknown"
        click.echo(
            f"\n## [{concern_key}] {target_key}  "
            f"({n_entries} entries, {total_recur} recurrences, {n_projects} projects: {projects_str})"
        )
        if with_telemetry:
            from science_tool.telemetry import format_feedback_telemetry, summarize_recent_for_feedback_target

            summary = summarize_recent_for_feedback_target(
                telemetry_events,
                target=group["target"],
                since_days=since_days if since_days is not None else 14,
            )
            click.echo(f"Telemetry: {format_feedback_telemetry(summary)}")
        for entry in group["entries"]:
            click.echo(f"  - {entry.id} [{entry.category}] {entry.summary}")
```

- [ ] **Step 8: Wire `feedback report`**

Add the option after `--project` (line 5897):

```python
@click.option("--concern", default=None, help="Filter by concern (fnmatch glob)")
```

Add `concern: str | None,` to the signature and pass `concern=concern` into `render_report(...)`.

- [ ] **Step 9: Run the CLI tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_feedback_cli.py -k "concern or triage_group_heading" -v`
Expected: PASS (5 tests).

- [ ] **Step 10: Run the full feedback CLI suite for regressions**

Run: `cd science && uv run --frozen pytest tests/test_feedback_cli.py -v`
Expected: PASS (existing triage tests may assert a `## <target>` heading — update them to the new `## [<concern>] <target>` form; legacy entries are `tooling`).

- [ ] **Step 11: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_feedback_cli.py
git commit -m "feat(cli): add --concern to feedback add/list/update/triage/report"
```

---

## Task 7: `/science:post-mortem` command + handoff + Codex generation

**Files:**
- Create: `commands/post-mortem.md`
- Modify: `commands/interpret-results.md` (handoff, before `## Process Reflection`)
- Generated: `codex-skills/science-post-mortem/SKILL.md`, `codex-skills/INDEX.md` (via script)
- Test: `science/tests/test_codex_skills.py` (only if it enumerates commands; otherwise the generation run is the check)

**Interfaces:**
- Consumes: `science feedback add --concern methodology:*` (Task 6).

- [ ] **Step 1: Create `commands/post-mortem.md`**

```markdown
---
description: Post-hoc reflection after an analysis failed or behaved unexpectedly. Investigate the root cause, identify what would have surfaced it sooner, and file the generalized methodology lesson as feedback. Use after a surprising result, a failed run, or a violated assumption.
---

# Post-Mortem

Run a structured post-hoc reflection on an analysis that failed or behaved unexpectedly, described by `$ARGUMENTS`, and capture any **generalized** methodology lesson as feedback.

If no argument is provided, ask the user which analysis, run, or result to reflect on.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).

## When to use

Use this after the fact, when something did not go as planned: a QA issue surfaced late, an analysis design did not fit the data's constraints, a statistical method was applied in violation of its assumptions, or a result contradicted a pre-registered expectation. The goal is not to fix the one analysis — it is to improve the guidance so the next analysis surfaces the issue sooner.

## Reflection

Work through these steps with the user. Keep the project-specific incident in the project (as an interpretation, note, or task); only a cross-project lesson goes to the global feedback store.

1. **Scope.** What was attempted, what was expected, and what actually happened? Be concrete about the gap between expectation and outcome.

2. **Root cause.** Why did it happen — the actual technical or methodological reason, not the symptom? Distinguish a one-off data/code mistake from a reasoning or process flaw.

3. **Earlier signal.** What would have surfaced this sooner? A QA check, an assumption test, a design review, a different pre-registration question? This is the core of the reflection.

4. **Generalize gate.** Is the lesson cross-project, or specific to this project? If it is purely project-local, **stop**: record it in the project and file nothing globally. Only continue for lessons that should change shared guidance.

5. **Target the surface.** Which guidance artifact should change so the earlier signal becomes routine — a skill (`skill:statistics`, `skill:research`, `skill:data`), a command (`command:plan-analysis`, `command:review-pipeline`, `command:pre-register`), a template, or a CLI check? Pick the `concern`:
   - `methodology:statistics` — assumptions, inference validity, model/finite-sample choices
   - `methodology:qa` — data/quality checks that should have caught it
   - `methodology:design` — analysis/study design vs. the question or data constraints
   - `methodology:data-fitness` — dataset suitability, preprocessing, provenance
   - `methodology:reasoning` — interpretation / causal / epistemic errors

6. **File the lesson.** For each distinct generalized lesson, run:

   ```bash
   science feedback add \
     --target "skill:statistics" \
     --concern methodology:statistics \
     --category <gap|guidance|suggestion|positive> \
     --summary "<the generalized lesson, one line>" \
     --detail "<what happened in this project as evidence; link the project entity>"
   ```

   - The `summary` is the improvement to shared guidance, not the incident.
   - The `detail` carries the incident as evidence and a pointer (path or id) to the project entity where the failure lives.
   - One entry per distinct lesson, not one big dump. The tool detects recurrence automatically.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
  --target "command:post-mortem" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Guidelines:
- One entry per distinct issue (not one big dump)
- Skip if everything worked smoothly — no feedback is valid feedback
```

- [ ] **Step 2: Add the soft handoff to `interpret-results`**

In `commands/interpret-results.md`, immediately **before** the `## Process Reflection` heading (currently at the tail), insert:

```markdown
## When results surprise you

If a result contradicted a pre-registered expectation, a run failed, or an
assumption turned out to be violated, consider `/science:post-mortem` to capture
a generalized methodology lesson — what would have surfaced the issue sooner —
as feedback.

```

(This is discoverability only; `interpret-results` behavior is unchanged.)

- [ ] **Step 3: Regenerate the Codex skills**

Run: `python scripts/generate_codex_skills.py`
Expected output: `Generated Codex skills in <repo>/codex-skills`

- [ ] **Step 4: Verify the generated artifacts exist**

Run: `test -f codex-skills/science-post-mortem/SKILL.md && grep -q "science-post-mortem" codex-skills/INDEX.md && echo OK`
Expected: `OK`

- [ ] **Step 5: Run the codex-skills test (if present) and the full feedback suites**

Run: `cd science && uv run --frozen pytest tests/test_codex_skills.py tests/test_feedback.py tests/test_feedback_cli.py -v`
Expected: PASS. (If `test_codex_skills.py` enumerates `commands/*.md`, it now includes `post-mortem` automatically.)

- [ ] **Step 6: Commit**

```bash
git add commands/post-mortem.md commands/interpret-results.md codex-skills/
git commit -m "feat(commands): add post-mortem reflection command with methodology-feedback handoff"
```

---

## Final verification

- [ ] Run the full affected suites once more:

Run: `cd science && uv run --frozen pytest tests/test_feedback.py tests/test_feedback_cli.py tests/test_codex_skills.py -v`
Expected: All PASS.

- [ ] Manual smoke test end-to-end:

```bash
cd science
export SCIENCE_FEEDBACK_DIR=$(mktemp -d)
uv run --frozen science feedback add --target skill:statistics --concern methodology:statistics \
  --category gap --summary "warn when residuals are autocorrelated before OLS" \
  --detail "mm30 run X assumed independence; pointer: entities/interpretations/..."
uv run --frozen science feedback list --concern 'methodology:*'
uv run --frozen science feedback triage
uv run --frozen science feedback report --concern 'methodology:*'
```
Expected: entry created with `concern: methodology:statistics`; list/triage/report show it under the methodology lens; a `tooling` add (default concern) with the same target/summary creates a *separate* entry rather than incrementing recurrence.

---

## Self-Review (completed)

- **Spec coverage:** Schema (Task 1), evidence linking via existing `project`/`detail` (no code — used in Task 7 command body), core-logic identity/grouping/clustering (Tasks 2, 4), CLI surface incl. `update` (Task 6), report `concern → target` grouping (Task 5), skill + handoff + Codex generation (Task 7). All spec sections map to a task.
- **Placeholder scan:** No TBDs; every code step shows real code and exact commands.
- **Wiring coverage:** the `add → find_duplicate` path (concern as dedup identity) has a dedicated CLI regression (`test_add_distinct_concern_not_deduplicated`) asserting two YAML files and no recurrence bump, in addition to the `find_duplicate` unit test (Task 2) and the manual smoke test.
- **Test runner:** every test/CLI command uses `uv run --frozen` (plain `python -m pytest` fails in this checkout).
- **Vocab drift:** `test_fb_concerns_constant_matches_lib` asserts the CLI's `_FB_CONCERNS` literal equals the library SSOT `VALID_CONCERNS`, fail-loud.
- **Pre-existing test breakage:** Task 4 Step 8 names the two `group_for_triage` tests that re-key to `(concern, target)` and gives exact replacements — no soft hedging.
- **Type consistency:** `concern: str` everywhere; `find_duplicate(..., concern=)`, `list_entries(..., concern=)`, `update_entry(..., concern=)`, `group_for_triage -> dict[tuple[str,str], dict]` with explicit `concern`/`target` values, `cluster_for_triage` rows include `concern`, `render_report(..., concern=)` consistent across tasks. `_FB_CONCERNS` (CLI) mirrors `VALID_CONCERNS` (lib) with a sync comment.
