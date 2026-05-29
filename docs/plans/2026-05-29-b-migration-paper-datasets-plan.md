# B-Migration Paper Dataset Usage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dry-run-first migration that rewrites paper `datasets` frontmatter into canonical `dataset_usage` entries when the rewrite is provably lossless.

**Architecture:** Add a focused pure migration module under `science_tool.graph`, expose it through `science graph migrate-paper-datasets`, and share the same same-ref role-conflict predicate with the B1 validator. The CLI stays thin: load project paths, call the pure planner/apply functions, format table/JSON output, and exit with the pinned migration-campaign codes.

**Tech Stack:** Python dataclasses, `yaml.safe_load` / `yaml.safe_dump`, Click CLI, pytest, `click.testing.CliRunner`, existing `science_model.frontmatter.parse_frontmatter`, existing `science_tool.graph.sources.load_project_sources`.

---

## File Structure

| File | Responsibility |
|---|---|
| `science/src/science_tool/graph/paper_dataset_migration.py` | Pure paper migration planner, frontmatter rewrite, conflict model, report JSON shape, apply helper, shared role-conflict predicate. |
| `science/src/science_tool/validate/checks/dataset_influence.py` | Replace the inlined paper conflict predicate with the shared helper. |
| `science/src/science_tool/cli.py` | Add `science graph migrate-paper-datasets` command, JSON/table formatting, and exit-code matrix. |
| `science/tests/test_paper_dataset_migration.py` | Pure migration tests for projection, conflict handling, idempotency, selection gate, malformed inputs, and unresolved refs. |
| `science/tests/test_graph_migrate.py` | CLI tests for dry-run/apply behavior, JSON/table payload, and exit codes. |
| `science/tests/validate/test_checks_dataset_influence.py` | Regression proving validator and migration share the same role-conflict semantics. |
| `docs/plans/2026-05-29-b-migration-paper-datasets-design.md` | Mark implementation state after all code lands. |

Keep the migration module independent of `validate` to avoid a graph → validate → graph cycle. It may import `load_project_sources` from `science_tool.graph.sources`.

## Task 1: Pure Projection And Shared Conflict Predicate

**Files:**
- Create: `science/src/science_tool/graph/paper_dataset_migration.py`
- Test: `science/tests/test_paper_dataset_migration.py`

- [ ] **Step 1: Write failing pure projection tests**

Add this file:

```python
from __future__ import annotations

import yaml

from science_tool.graph.paper_dataset_migration import (
    PaperDatasetMigrationConflict,
    is_paper_dataset_role_conflict,
    migrate_paper_frontmatter,
)


def _body(frontmatter: dict, body: str = "Body.\n") -> str:
    return "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n\n" + body


def _frontmatter(text: str) -> dict:
    block = text.split("---", 2)[1]
    return yaml.safe_load(block)


def test_migrate_paper_frontmatter_adds_dataset_usage_and_removes_legacy_field() -> None:
    original = _body(
        {
            "id": "paper:smith-2025",
            "type": "paper",
            "title": "Smith 2025",
            "datasets": ["dataset:gtex-v8"],
        }
    )

    result = migrate_paper_frontmatter("doc/papers/smith-2025.md", original)

    assert result.changed is True
    assert result.conflicts == []
    fm = _frontmatter(result.updated_text)
    assert "datasets" not in fm
    assert fm["dataset_usage"] == [
        {"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "unknown"}
    ]
    assert result.updated_text.endswith("\nBody.\n")


def test_migrate_paper_frontmatter_preserves_existing_usage_order_and_appends_missing_refs() -> None:
    original = _body(
        {
            "id": "paper:smith-2025",
            "kind": "paper",
            "title": "Smith 2025",
            "dataset_usage": [
                {"ref": "dataset:existing", "role": "analyzed", "overlap": "full"},
            ],
            "datasets": ["dataset:existing", "dataset:new", "dataset:new"],
        }
    )

    result = migrate_paper_frontmatter("doc/papers/smith-2025.md", original)

    assert result.conflicts == []
    fm = _frontmatter(result.updated_text)
    assert fm["dataset_usage"] == [
        {"ref": "dataset:existing", "role": "analyzed", "overlap": "full"},
        {"ref": "dataset:new", "role": "analyzed", "overlap": "unknown"},
    ]


def test_analyzed_full_same_ref_is_not_a_conflict() -> None:
    assert is_paper_dataset_role_conflict({"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"}) is False

    original = _body(
        {
            "id": "paper:smith-2025",
            "type": "paper",
            "dataset_usage": [
                {"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"},
            ],
            "datasets": ["dataset:gtex-v8"],
        }
    )

    result = migrate_paper_frontmatter("doc/papers/smith-2025.md", original)

    assert result.changed is True
    assert result.conflicts == []
    fm = _frontmatter(result.updated_text)
    assert "datasets" not in fm
    assert fm["dataset_usage"] == [
        {"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"},
    ]


def test_non_analyzed_same_ref_is_role_conflict_and_leaves_text_unchanged() -> None:
    assert is_paper_dataset_role_conflict({"ref": "dataset:gtex-v8", "role": "cited"}) is True
    original = _body(
        {
            "id": "paper:smith-2025",
            "type": "paper",
            "dataset_usage": [{"ref": "dataset:gtex-v8", "role": "cited"}],
            "datasets": ["dataset:gtex-v8"],
        }
    )

    result = migrate_paper_frontmatter("doc/papers/smith-2025.md", original)

    assert result.changed is False
    assert result.updated_text == original
    assert result.conflicts == [
        PaperDatasetMigrationConflict(
            path="doc/papers/smith-2025.md",
            paper_id="paper:smith-2025",
            dataset_ref="dataset:gtex-v8",
            reason="role-conflict",
            detail="legacy paper.datasets implies role analyzed but explicit dataset_usage has role cited",
        )
    ]


def test_unresolved_dataset_ref_moves_verbatim_when_syntactically_valid() -> None:
    original = _body(
        {
            "id": "paper:smith-2025",
            "type": "paper",
            "datasets": ["dataset:not-in-commons"],
        }
    )

    result = migrate_paper_frontmatter("doc/papers/smith-2025.md", original)

    assert result.conflicts == []
    fm = _frontmatter(result.updated_text)
    assert fm["dataset_usage"] == [
        {"ref": "dataset:not-in-commons", "role": "analyzed", "overlap": "unknown"}
    ]


def test_alias_equivalent_refs_are_not_deduped_by_the_migration() -> None:
    original = _body(
        {
            "id": "paper:smith-2025",
            "type": "paper",
            "dataset_usage": [{"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"}],
            "datasets": ["dataset:gtex"],
        }
    )

    result = migrate_paper_frontmatter("doc/papers/smith-2025.md", original)

    assert result.conflicts == []
    fm = _frontmatter(result.updated_text)
    assert fm["dataset_usage"] == [
        {"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"},
        {"ref": "dataset:gtex", "role": "analyzed", "overlap": "unknown"},
    ]
```

The migration is intentionally ref-resolution agnostic, so it compares refs as raw strings. That means it can diverge from B1 validation when aliases canonicalize two different strings to one dataset. For v1 this is acceptable because requiring commons/local resolution would break the mechanical migration contract; B1 validation remains the place that canonicalizes and reports alias-level same-ref conflicts.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_paper_dataset_migration.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.graph.paper_dataset_migration'`.

- [ ] **Step 3: Implement the minimal pure module**

Create `science/src/science_tool/graph/paper_dataset_migration.py`:

```python
"""Mechanical migration from paper.datasets to paper.dataset_usage."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

import yaml

ConflictReason = Literal[
    "malformed-frontmatter",
    "malformed-datasets",
    "malformed-usage",
    "role-conflict",
    "roundtrip-failure",
]


@dataclass(frozen=True, slots=True)
class PaperDatasetMigrationConflict:
    path: str
    paper_id: str | None
    dataset_ref: str | None
    reason: ConflictReason
    detail: str

    def to_json(self) -> dict[str, str | None]:
        return {
            "path": self.path,
            "paper_id": self.paper_id,
            "dataset_ref": self.dataset_ref,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class PaperDatasetMigrationResult:
    path: str
    changed: bool
    updated_text: str
    conflicts: list[PaperDatasetMigrationConflict] = field(default_factory=list)


def is_paper_dataset_role_conflict(entry: Mapping[str, Any]) -> bool:
    return entry.get("role") != "analyzed"


def migrate_paper_frontmatter(path: str | Path, text: str) -> PaperDatasetMigrationResult:
    path_str = str(path)
    split = _split_frontmatter(text)
    if split is None:
        return PaperDatasetMigrationResult(path=path_str, changed=False, updated_text=text)
    prefix, yaml_text, suffix = split
    try:
        loaded = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as exc:
        return PaperDatasetMigrationResult(
            path=path_str,
            changed=False,
            updated_text=text,
            conflicts=[
                PaperDatasetMigrationConflict(
                    path=path_str,
                    paper_id=None,
                    dataset_ref=None,
                    reason="malformed-frontmatter",
                    detail=str(exc).splitlines()[0],
                )
            ],
        )
    if not isinstance(loaded, dict):
        return _single_conflict(path_str, text, None, None, "malformed-frontmatter", "frontmatter must be a mapping")
    kind = loaded.get("kind") or loaded.get("type")
    if kind != "paper":
        return PaperDatasetMigrationResult(path=path_str, changed=False, updated_text=text)

    paper_id = loaded.get("id") if isinstance(loaded.get("id"), str) else None
    raw_datasets = loaded.get("datasets")
    if raw_datasets is None:
        return PaperDatasetMigrationResult(path=path_str, changed=False, updated_text=text)
    if raw_datasets == []:
        updated = dict(loaded)
        updated.pop("datasets", None)
        return _dump_result(path_str, text, prefix, updated, suffix)
    if not isinstance(raw_datasets, list) or any(not isinstance(ref, str) or not ref.startswith("dataset:") for ref in raw_datasets):
        return _single_conflict(
            path_str,
            text,
            paper_id,
            None,
            "malformed-datasets",
            "datasets must be a list of dataset: strings",
        )

    usage = loaded.get("dataset_usage", [])
    if usage is None:
        usage = []
    if not isinstance(usage, list):
        return _single_conflict(path_str, text, paper_id, None, "malformed-usage", "dataset_usage must be a list")
    for index, entry in enumerate(usage):
        if _usage_defect(entry) is not None:
            return _single_conflict(
                path_str,
                text,
                paper_id,
                None,
                "malformed-usage",
                f"dataset_usage[{index}] {_usage_defect(entry)}",
            )

    explicit_by_ref = {str(entry["ref"]): entry for entry in usage}
    deduped_legacy = list(dict.fromkeys(raw_datasets))
    for ref in deduped_legacy:
        explicit = explicit_by_ref.get(ref)
        if explicit is not None and is_paper_dataset_role_conflict(explicit):
            return _single_conflict(
                path_str,
                text,
                paper_id,
                ref,
                "role-conflict",
                f"legacy paper.datasets implies role analyzed but explicit dataset_usage has role {explicit.get('role')}",
            )

    updated = dict(loaded)
    updated_usage = list(usage)
    explicit_refs = {str(entry["ref"]) for entry in updated_usage}
    for ref in deduped_legacy:
        if ref not in explicit_refs:
            updated_usage.append({"ref": ref, "role": "analyzed", "overlap": "unknown"})
            explicit_refs.add(ref)
    updated["dataset_usage"] = updated_usage
    updated.pop("datasets", None)
    return _dump_result(path_str, text, prefix, updated, suffix)


def _usage_defect(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return "must be an object"
    if not isinstance(entry.get("ref"), str) or not str(entry["ref"]).startswith("dataset:"):
        return "must have a dataset: ref"
    if not isinstance(entry.get("role"), str):
        return "must have a role"
    overlap = entry.get("overlap")
    if overlap is not None and not isinstance(overlap, str):
        return "overlap must be a string"
    return None


def _split_frontmatter(text: str) -> tuple[str, str, str] | None:
    if not text.startswith("---\n"):
        return None
    close = text.find("\n---", 4)
    if close < 0:
        return None
    end = close + len("\n---")
    if text[end : end + 1] == "\n":
        end += 1
    return "---\n", text[4:close], text[end:]


def _dump_result(
    path: str,
    original: str,
    prefix: str,
    frontmatter: dict[str, Any],
    suffix: str,
) -> PaperDatasetMigrationResult:
    dumped = yaml.safe_dump(frontmatter, sort_keys=False)
    updated_text = f"{prefix}{dumped}---\n{suffix}"
    if not updated_text.startswith("---\n") or "\n---\n" not in updated_text:
        return _single_conflict(path, original, _paper_id(frontmatter), None, "roundtrip-failure", "frontmatter roundtrip failed")
    return PaperDatasetMigrationResult(path=path, changed=updated_text != original, updated_text=updated_text)


def _single_conflict(
    path: str,
    text: str,
    paper_id: str | None,
    dataset_ref: str | None,
    reason: ConflictReason,
    detail: str,
) -> PaperDatasetMigrationResult:
    return PaperDatasetMigrationResult(
        path=path,
        changed=False,
        updated_text=text,
        conflicts=[PaperDatasetMigrationConflict(path, paper_id, dataset_ref, reason, detail)],
    )


def _paper_id(frontmatter: Mapping[str, Any]) -> str | None:
    value = frontmatter.get("id")
    return value if isinstance(value, str) else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --frozen pytest science/tests/test_paper_dataset_migration.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
rtk git add science/src/science_tool/graph/paper_dataset_migration.py science/tests/test_paper_dataset_migration.py
rtk git commit -m "feat: add paper dataset migration projection"
```

## Task 2: Project Scanner, Apply Helper, And Selection Gate

**Files:**
- Modify: `science/src/science_tool/graph/paper_dataset_migration.py`
- Modify: `science/tests/test_paper_dataset_migration.py`

- [ ] **Step 1: Write failing project-level tests**

Append to `science/tests/test_paper_dataset_migration.py`:

```python
from pathlib import Path

from science_tool.graph.paper_dataset_migration import plan_paper_dataset_migration


def _write_project(root: Path) -> None:
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    (root / "doc" / "papers").mkdir(parents=True)
    (root / "doc" / "topics").mkdir(parents=True)


def test_plan_scans_only_paper_frontmatter_documents(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _write_project(root)
    paper = root / "doc" / "papers" / "smith.md"
    topic = root / "doc" / "topics" / "dataset-note.md"
    paper.write_text(_body({"id": "paper:smith", "type": "paper", "datasets": ["dataset:gtex-v8"]}), encoding="utf-8")
    topic.write_text(_body({"id": "topic:data", "type": "topic", "datasets": ["dataset:gtex-v8"]}), encoding="utf-8")

    report = plan_paper_dataset_migration(root)

    assert report.changed_files == [str(paper)]
    assert report.conflicts == []


def test_plan_reports_malformed_frontmatter_only_for_paper_source_surface(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _write_project(root)
    bad_paper = root / "doc" / "papers" / "bad.md"
    bad_topic = root / "doc" / "topics" / "bad.md"
    bad_paper.write_text("---\nid: [\n---\nBody.\n", encoding="utf-8")
    bad_topic.write_text("---\nid: [\n---\nBody.\n", encoding="utf-8")

    report = plan_paper_dataset_migration(root)

    assert [conflict.reason for conflict in report.conflicts] == ["malformed-frontmatter"]
    assert report.conflicts[0].path == str(bad_paper)
    assert report.changed_files == []


def test_apply_rewrites_changed_files_and_second_run_is_clean(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _write_project(root)
    paper = root / "doc" / "papers" / "smith.md"
    paper.write_text(_body({"id": "paper:smith", "kind": "paper", "datasets": ["dataset:gtex-v8"]}), encoding="utf-8")

    first = plan_paper_dataset_migration(root, apply=True)
    second = plan_paper_dataset_migration(root, apply=True)

    assert first.changed_files == [str(paper)]
    assert second.changed_files == []
    assert "datasets:" not in paper.read_text(encoding="utf-8")
    assert "dataset_usage:" in paper.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_paper_dataset_migration.py::test_plan_scans_only_paper_frontmatter_documents science/tests/test_paper_dataset_migration.py::test_plan_reports_malformed_frontmatter_only_for_paper_source_surface science/tests/test_paper_dataset_migration.py::test_apply_rewrites_changed_files_and_second_run_is_clean -q
```

Expected: FAIL with `ImportError` or `AttributeError` for `plan_paper_dataset_migration`.

- [ ] **Step 3: Implement the project-level planner**

Add to `science/src/science_tool/graph/paper_dataset_migration.py`:

```python
@dataclass(frozen=True, slots=True)
class PaperDatasetMigrationReport:
    project_root: str
    apply: bool
    changed_files: list[str]
    conflicts: list[PaperDatasetMigrationConflict]

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    @property
    def changed_file_count(self) -> int:
        return len(self.changed_files)

    def to_json(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "apply": self.apply,
            "changed_files": self.changed_files,
            "changed_file_count": self.changed_file_count,
            "conflicts": [conflict.to_json() for conflict in self.conflicts],
            "conflict_count": self.conflict_count,
        }


def plan_paper_dataset_migration(project_root: Path, *, apply: bool = False) -> PaperDatasetMigrationReport:
    root = project_root.resolve()
    changed_files: list[str] = []
    conflicts: list[PaperDatasetMigrationConflict] = []
    for path in _candidate_markdown_files(root):
        text = path.read_text(encoding="utf-8")
        result = migrate_paper_frontmatter(path, text)
        if result.conflicts:
            if _looks_like_paper_source_path(root, path):
                conflicts.extend(result.conflicts)
            continue
        if result.changed:
            changed_files.append(str(path))
            if apply:
                path.write_text(result.updated_text, encoding="utf-8")
    return PaperDatasetMigrationReport(
        project_root=str(root),
        apply=apply,
        changed_files=sorted(changed_files),
        conflicts=sorted(conflicts, key=lambda item: (item.path, item.reason, item.dataset_ref or "")),
    )


def _candidate_markdown_files(project_root: Path) -> list[Path]:
    roots = [project_root / "doc" / "papers", project_root / "doc" / "background" / "papers"]
    files: list[Path] = []
    for root in roots:
        if root.is_dir():
            files.extend(path for path in root.rglob("*.md") if path.is_file())
    # Include other docs so the kind gate is tested without rewriting non-paper files.
    doc_root = project_root / "doc"
    if doc_root.is_dir():
        files.extend(path for path in doc_root.rglob("*.md") if path.is_file())
    return sorted(set(files))


def _looks_like_paper_source_path(project_root: Path, path: Path) -> bool:
    try:
        rel = path.relative_to(project_root)
    except ValueError:
        return False
    parts = rel.parts
    return len(parts) >= 3 and parts[0] == "doc" and parts[-2] == "papers"
```

Then adjust the malformed-YAML branch inside `migrate_paper_frontmatter` so malformed frontmatter outside paper source paths can be filtered by the planner while direct unit tests still see a conflict:

```python
    except yaml.YAMLError as exc:
        return PaperDatasetMigrationResult(
            path=path_str,
            changed=False,
            updated_text=text,
            conflicts=[
                PaperDatasetMigrationConflict(
                    path=path_str,
                    paper_id=None,
                    dataset_ref=None,
                    reason="malformed-frontmatter",
                    detail=str(exc).splitlines()[0],
                )
            ],
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --frozen pytest science/tests/test_paper_dataset_migration.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
rtk git add science/src/science_tool/graph/paper_dataset_migration.py science/tests/test_paper_dataset_migration.py
rtk git commit -m "feat: plan paper dataset migrations"
```

## Task 3: Share Conflict Predicate With B1 Validator

**Files:**
- Modify: `science/src/science_tool/validate/checks/dataset_influence.py`
- Modify: `science/tests/validate/test_checks_dataset_influence.py`
- Modify: `science/tests/test_paper_dataset_migration.py`

- [ ] **Step 1: Write failing validator regression for analyzed/full**

Append to `science/tests/validate/test_checks_dataset_influence.py` near the existing paper dataset conflict tests:

```python
def test_paper_datasets_analyzed_full_refinement_is_not_conflict() -> None:
    results = list(
        evaluate_dataset_influence(
            [
                {
                    "_path": "doc/papers/smith.md",
                    "id": "paper:smith",
                    "kind": "paper",
                    "datasets": ["dataset:gtex-v8"],
                    "dataset_usage": [
                        {"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"},
                    ],
                }
            ],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    assert [(result.severity, result.rule) for result in results] == []
```

Append to `science/tests/test_paper_dataset_migration.py`:

```python
def test_role_conflict_predicate_matches_validator_semantics() -> None:
    assert is_paper_dataset_role_conflict({"ref": "dataset:x", "role": "analyzed", "overlap": "unknown"}) is False
    assert is_paper_dataset_role_conflict({"ref": "dataset:x", "role": "analyzed", "overlap": "full"}) is False
    assert is_paper_dataset_role_conflict({"ref": "dataset:x", "role": "validation_source", "overlap": "full"}) is True
```

- [ ] **Step 2: Run tests to verify they fail if validator still has drift**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_dataset_influence.py::test_paper_datasets_analyzed_full_refinement_is_not_conflict science/tests/test_paper_dataset_migration.py::test_role_conflict_predicate_matches_validator_semantics -q
```

Expected: PASS if the current validator already uses role-only semantics; still perform Step 3 to share the predicate and prevent drift.

- [ ] **Step 3: Replace the validator's inlined predicate**

In `science/src/science_tool/validate/checks/dataset_influence.py`, add:

```python
from science_tool.graph.paper_dataset_migration import is_paper_dataset_role_conflict
```

Replace:

```python
                    if entry.get("role") != "analyzed":
```

with:

```python
                    if is_paper_dataset_role_conflict(entry):
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_dataset_influence.py science/tests/test_paper_dataset_migration.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
rtk git add science/src/science_tool/validate/checks/dataset_influence.py science/tests/validate/test_checks_dataset_influence.py science/tests/test_paper_dataset_migration.py
rtk git commit -m "refactor: share paper dataset conflict predicate"
```

## Task 4: CLI Command And Exit Codes

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/tests/test_graph_migrate.py`

- [ ] **Step 1: Write failing CLI tests**

Append to `science/tests/test_graph_migrate.py`:

```python
def _write_paper_dataset_project(root: Path, *, conflict: bool = False) -> Path:
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    (root / "doc" / "papers").mkdir(parents=True)
    paper = root / "doc" / "papers" / "smith.md"
    if conflict:
        paper.write_text(
            "\n".join(
                [
                    "---",
                    "id: paper:smith",
                    "type: paper",
                    "dataset_usage:",
                    "  - ref: dataset:gtex-v8",
                    "    role: cited",
                    "datasets:",
                    "  - dataset:gtex-v8",
                    "---",
                    "",
                    "Body.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    else:
        paper.write_text(
            "\n".join(
                [
                    "---",
                    "id: paper:smith",
                    "type: paper",
                    "datasets:",
                    "  - dataset:gtex-v8",
                    "---",
                    "",
                    "Body.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    return paper


def test_graph_migrate_paper_datasets_dry_run_json_exit_10_for_pending(tmp_path: Path) -> None:
    root = tmp_path / "project"
    paper = _write_paper_dataset_project(root)

    result = CliRunner().invoke(
        main,
        ["graph", "migrate-paper-datasets", "--project-root", str(root), "--format", "json"],
    )

    assert result.exit_code == 10
    payload = json.loads(result.output)
    assert payload["apply"] is False
    assert payload["changed_files"] == [str(paper)]
    assert payload["conflict_count"] == 0
    assert "datasets:" in paper.read_text(encoding="utf-8")


def test_graph_migrate_paper_datasets_apply_rewrites_and_exits_zero(tmp_path: Path) -> None:
    root = tmp_path / "project"
    paper = _write_paper_dataset_project(root)

    result = CliRunner().invoke(
        main,
        ["graph", "migrate-paper-datasets", "--project-root", str(root), "--format", "json", "--apply"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["apply"] is True
    assert payload["changed_files"] == [str(paper)]
    text = paper.read_text(encoding="utf-8")
    assert "datasets:" not in text
    assert "dataset_usage:" in text


def test_graph_migrate_paper_datasets_conflict_exits_20_and_leaves_file(tmp_path: Path) -> None:
    root = tmp_path / "project"
    paper = _write_paper_dataset_project(root, conflict=True)
    original = paper.read_text(encoding="utf-8")

    result = CliRunner().invoke(
        main,
        ["graph", "migrate-paper-datasets", "--project-root", str(root), "--format", "json", "--apply"],
    )

    assert result.exit_code == 20
    payload = json.loads(result.output)
    assert payload["conflicts"][0]["reason"] == "role-conflict"
    assert paper.read_text(encoding="utf-8") == original


def test_graph_migrate_paper_datasets_table_mentions_mode_and_conflicts(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _write_paper_dataset_project(root, conflict=True)

    result = CliRunner().invoke(
        main,
        ["graph", "migrate-paper-datasets", "--project-root", str(root), "--format", "table"],
    )

    assert result.exit_code == 20
    assert "Paper Dataset Migration" in result.output
    assert "role-conflict" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_graph_migrate.py::test_graph_migrate_paper_datasets_dry_run_json_exit_10_for_pending science/tests/test_graph_migrate.py::test_graph_migrate_paper_datasets_apply_rewrites_and_exits_zero science/tests/test_graph_migrate.py::test_graph_migrate_paper_datasets_conflict_exits_20_and_leaves_file science/tests/test_graph_migrate.py::test_graph_migrate_paper_datasets_table_mentions_mode_and_conflicts -q
```

Expected: FAIL with Click saying command `migrate-paper-datasets` does not exist.

- [ ] **Step 3: Implement CLI command**

In `science/src/science_tool/cli.py`, add the import near the existing graph migration imports:

```python
from science_tool.graph.paper_dataset_migration import plan_paper_dataset_migration
```

Add this command near `graph_migrate`:

```python
@graph.command("migrate-paper-datasets")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Rewrite paper frontmatter in place.")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def graph_migrate_paper_datasets(output_format: str, apply_changes: bool, project_root: Path) -> None:
    """Migrate legacy paper.datasets fields to canonical dataset_usage."""

    report = plan_paper_dataset_migration(project_root.resolve(), apply=apply_changes)
    payload = report.to_json()
    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        rows = [
            {"kind": "change", "path": path, "reason": "", "detail": ""}
            for path in report.changed_files
        ]
        rows.extend(
            {
                "kind": "conflict",
                "path": conflict.path,
                "reason": conflict.reason,
                "detail": conflict.detail,
            }
            for conflict in report.conflicts
        )
        emit_query_rows(
            output_format=output_format,
            title="Paper Dataset Migration",
            columns=[
                ("kind", "Kind"),
                ("path", "Path"),
                ("reason", "Reason"),
                ("detail", "Detail"),
            ],
            rows=rows,
        )
        mode = "apply" if apply_changes else "dry-run"
        click.echo(f"Mode: {mode}")
        click.echo(f"Changed files: {report.changed_file_count}")
        click.echo(f"Conflicts: {report.conflict_count}")

    if report.conflicts:
        raise click.exceptions.Exit(20)
    if not apply_changes and report.changed_files:
        raise click.exceptions.Exit(10)
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run --frozen pytest science/tests/test_graph_migrate.py::test_graph_migrate_paper_datasets_dry_run_json_exit_10_for_pending science/tests/test_graph_migrate.py::test_graph_migrate_paper_datasets_apply_rewrites_and_exits_zero science/tests/test_graph_migrate.py::test_graph_migrate_paper_datasets_conflict_exits_20_and_leaves_file science/tests/test_graph_migrate.py::test_graph_migrate_paper_datasets_table_mentions_mode_and_conflicts -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_graph_migrate.py
rtk git commit -m "feat: add paper dataset migration cli"
```

## Task 5: Polish Scanner Against Source Loader And Full Acceptance

**Files:**
- Modify: `science/src/science_tool/graph/paper_dataset_migration.py`
- Modify: `science/tests/test_paper_dataset_migration.py`
- Modify: `docs/plans/2026-05-29-b-migration-paper-datasets-design.md`

- [ ] **Step 1: Add a source-surface regression using configured profile paths**

Append to `science/tests/test_paper_dataset_migration.py`:

```python
def test_plan_uses_configured_local_profile_paper_surface(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "knowledge_profiles:",
                "  local: lab",
                "profiles:",
                "  lab:",
                "    papers:",
                "      - literature/papers",
                "",
            ]
        ),
        encoding="utf-8",
    )
    paper_dir = root / "literature" / "papers"
    paper_dir.mkdir(parents=True)
    paper = paper_dir / "smith.md"
    paper.write_text(_body({"id": "paper:smith", "type": "paper", "datasets": ["dataset:gtex-v8"]}), encoding="utf-8")

    report = plan_paper_dataset_migration(root)

    assert report.changed_files == [str(paper)]


def test_plan_reports_malformed_frontmatter_in_discovered_paper_surface(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "knowledge_profiles:",
                "  local: lab",
                "profiles:",
                "  lab:",
                "    papers:",
                "      - literature/papers",
                "",
            ]
        ),
        encoding="utf-8",
    )
    paper_dir = root / "literature" / "papers"
    paper_dir.mkdir(parents=True)
    valid = paper_dir / "valid.md"
    bad = paper_dir / "bad.md"
    valid.write_text(_body({"id": "paper:valid", "type": "paper"}), encoding="utf-8")
    bad.write_text("---\nid: [\n---\nBody.\n", encoding="utf-8")

    report = plan_paper_dataset_migration(root)

    assert [conflict.reason for conflict in report.conflicts] == ["malformed-frontmatter"]
    assert report.conflicts[0].path == str(bad)
```

- [ ] **Step 2: Run test to verify it fails if scanner only hardcodes `doc/papers`**

Run:

```bash
uv run --frozen pytest science/tests/test_paper_dataset_migration.py::test_plan_uses_configured_local_profile_paper_surface science/tests/test_paper_dataset_migration.py::test_plan_reports_malformed_frontmatter_in_discovered_paper_surface -q
```

Expected: FAIL if `_candidate_markdown_files` does not consult project source surfaces or if malformed-paper reporting is still hardcoded to `doc/**/papers`.

- [ ] **Step 3: Reuse `load_project_sources` surfaces without depending on entity validity**

Adjust `paper_dataset_migration.py` so `_source_scan(project_root)` uses `load_project_sources(project_root)` when available and returns both candidate markdown files and discovered paper roots. `ProjectSources.markdown_documents` contains `MarkdownSourceDocument(path=..., frontmatter=..., body=...)`, where `path` is project-relative. Do not silently mask source-loading failures: if `load_project_sources` raises, return a `roundtrip-failure` conflict with the exception class/message and fall back only to conventional `doc/papers` paths for best-effort visibility.

```python
@dataclass(frozen=True, slots=True)
class _SourceScan:
    files: list[Path]
    paper_roots: frozenset[Path]
    load_conflict: PaperDatasetMigrationConflict | None = None


def _source_scan(project_root: Path) -> _SourceScan:
    files: set[Path] = set()
    paper_roots: set[Path] = {
        project_root / "doc" / "papers",
        project_root / "doc" / "background" / "papers",
        *_declared_paper_roots(project_root),
    }
    load_conflict: PaperDatasetMigrationConflict | None = None
    try:
        from science_tool.graph.sources import load_project_sources

        sources = load_project_sources(project_root)
        for doc in sources.markdown_documents:
            path = Path(doc.path)
            absolute = path if path.is_absolute() else project_root / path
            if absolute.suffix != ".md":
                continue
            files.add(absolute)
            kind = doc.frontmatter.get("kind") or doc.frontmatter.get("type")
            if kind == "paper":
                paper_roots.add(absolute.parent)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        load_conflict = PaperDatasetMigrationConflict(
            path=str(project_root / "science.yaml"),
            paper_id=None,
            dataset_ref=None,
            reason="roundtrip-failure",
            detail=f"could not load project sources for migration scan: {type(exc).__name__}: {exc}",
        )
    for root in (project_root / "doc" / "papers", project_root / "doc" / "background" / "papers"):
        if root.is_dir():
            files.update(path for path in root.rglob("*.md") if path.is_file())
    for root in list(paper_roots):
        if root.is_dir():
            files.update(path for path in root.rglob("*.md") if path.is_file())
    return _SourceScan(
        files=sorted(path for path in files if path.is_file()),
        paper_roots=frozenset(root.resolve() for root in paper_roots if root.is_dir()),
        load_conflict=load_conflict,
    )


def _declared_paper_roots(project_root: Path) -> set[Path]:
    manifest_path = project_root / "science.yaml"
    if not manifest_path.is_file():
        return set()
    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return set()
    if not isinstance(data, dict):
        return set()
    roots: set[Path] = set()
    profiles = data.get("profiles")
    if isinstance(profiles, dict):
        for profile in profiles.values():
            if not isinstance(profile, dict):
                continue
            papers = profile.get("papers")
            if isinstance(papers, list):
                roots.update(project_root / item for item in papers if isinstance(item, str))
    return roots
```

Update `plan_paper_dataset_migration` to use the scan result:

```python
def plan_paper_dataset_migration(project_root: Path, *, apply: bool = False) -> PaperDatasetMigrationReport:
    root = project_root.resolve()
    changed_files: list[str] = []
    conflicts: list[PaperDatasetMigrationConflict] = []
    scan = _source_scan(root)
    if scan.load_conflict is not None:
        conflicts.append(scan.load_conflict)
    for path in scan.files:
        text = path.read_text(encoding="utf-8")
        result = migrate_paper_frontmatter(path, text)
        if result.conflicts:
            if _looks_like_paper_source_path(path, scan.paper_roots):
                conflicts.extend(result.conflicts)
            continue
        if result.changed:
            changed_files.append(str(path))
            if apply:
                path.write_text(result.updated_text, encoding="utf-8")
    return PaperDatasetMigrationReport(
        project_root=str(root),
        apply=apply,
        changed_files=sorted(changed_files),
        conflicts=sorted(conflicts, key=lambda item: (item.path, item.reason, item.dataset_ref or "")),
    )
```

Replace `_looks_like_paper_source_path` with a root-set check:

```python
def _looks_like_paper_source_path(path: Path, paper_roots: frozenset[Path]) -> bool:
    resolved = path.resolve()
    for root in paper_roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False
```

Only paths under the discovered paper source roots report `malformed-frontmatter`. A malformed markdown file under an unrelated directory is still skipped.

CRLF frontmatter (`---\r\n`) remains out of scope for v1; `_split_frontmatter` only recognizes the repo's LF convention. If a CRLF paper is encountered, it is skipped rather than rewritten.

- [ ] **Step 4: Update design status**

In `docs/plans/2026-05-29-b-migration-paper-datasets-design.md`, change:

```markdown
Status: design drafted; implementation plan next
```

to:

```markdown
Status: implementation ready; see `docs/plans/2026-05-29-b-migration-paper-datasets-plan.md`
```

- [ ] **Step 5: Run full affected suite**

Run:

```bash
uv run --frozen pytest science/tests/test_paper_dataset_migration.py science/tests/test_graph_migrate.py science/tests/validate/test_checks_dataset_influence.py -q
uv run --frozen ruff check science/src/science_tool/graph/paper_dataset_migration.py science/src/science_tool/cli.py science/src/science_tool/validate/checks/dataset_influence.py science/tests/test_paper_dataset_migration.py science/tests/test_graph_migrate.py science/tests/validate/test_checks_dataset_influence.py
```

Expected: both commands PASS.

- [ ] **Step 6: Commit**

Run:

```bash
rtk git add science/src/science_tool/graph/paper_dataset_migration.py science/tests/test_paper_dataset_migration.py docs/plans/2026-05-29-b-migration-paper-datasets-design.md
rtk git commit -m "test: harden paper dataset migration scanning"
```

## Task 6: Final Verification

**Files:**
- No planned source edits.

- [ ] **Step 1: Run migration command against the current repo in dry-run mode**

Run:

```bash
uv run --frozen science graph migrate-paper-datasets --project-root . --format json
```

Expected: exit code is one of:
- `0` if the repo has no legacy paper `datasets` left;
- `10` if safe rewrites are pending;
- `20` if real conflicts exist.

Do not apply changes to the current repo unless the user explicitly asks for the migration campaign.

- [ ] **Step 2: Run affected tests**

Run:

```bash
uv run --frozen pytest science/tests/test_paper_dataset_migration.py science/tests/test_graph_migrate.py science/tests/validate/test_checks_dataset_influence.py -q
```

Expected: PASS.

- [ ] **Step 3: Run formatting/lint checks**

Run:

```bash
uv run --frozen ruff check science/src/science_tool/graph/paper_dataset_migration.py science/src/science_tool/cli.py science/src/science_tool/validate/checks/dataset_influence.py science/tests/test_paper_dataset_migration.py science/tests/test_graph_migrate.py science/tests/validate/test_checks_dataset_influence.py
rtk git diff --check
```

Expected: PASS and no whitespace errors.

- [ ] **Step 4: Commit any verification-only doc adjustment**

If Task 6 required a small doc correction, commit it:

```bash
rtk git add docs/plans/2026-05-29-b-migration-paper-datasets-design.md
rtk git commit -m "docs: mark paper dataset migration implemented"
```

If no files changed, skip this commit.

## Self-Review Checklist

- [ ] Spec coverage: B-M1 selection gate, B-M2 lossless projection, B-M3 same-ref merge, B-M4 stable conflict codes, CLI shape, exit-code matrix, YAML policy, validate handoff, and all acceptance bullets are covered by tasks above.
- [ ] Placeholder scan: this plan contains no unspecified implementation steps; every code-changing step has concrete code or exact replacement instructions.
- [ ] Type consistency: `PaperDatasetMigrationConflict`, `PaperDatasetMigrationResult`, `PaperDatasetMigrationReport`, `is_paper_dataset_role_conflict`, `migrate_paper_frontmatter`, and `plan_paper_dataset_migration` are introduced before use.
