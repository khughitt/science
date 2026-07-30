# Default Test Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove repeated project-source parsing from health/validation, prune excluded scan trees before descent, and eliminate the measured model-test and warning overhead without weakening stress tests.

**Architecture:** Validation will cache one lenient `ProjectSources` bundle for each meaningful corpus choice (`include_commons=True` and `False`) and project strict behavior from the bundle's existing diagnostic ledgers. A shared `os.walk` helper will provide the three reference/spec scanners with identical pruning and symlink semantics. Test-only ontology reuse will return deep copies, and rdflib warnings will be filtered only after a measured win.

**Tech Stack:** Python 3.11+, pytest, Pydantic 2, stdlib `os.walk`, Ruff, pyright.

## Global Constraints

- Optimize only the default suites; do not change `snapshot`, `real_projects`, `git_source`, or `packaging`.
- Preserve the budget fixture corpus sizes and assertions.
- No new dependency, pytest parallelism, persistent production cache, compatibility layer, or `Unified` prefix.
- Run suites sequentially and pin timing comparisons with `-p no:randomly`.
- Use the project package directories for commands; there is no root `pyproject.toml`.

---

### Task 1: Canonicalize validation source loads

**Files:**
- Modify: `science/src/science_tool/graph/sources.py`
- Modify: `science/src/science_tool/validate/context.py`
- Modify: `science/src/science_tool/validate/runner.py`
- Modify: `science/src/science_tool/graph/health_checks/validate.py`
- Modify: `science/src/science_tool/validate/checks/relations.py`
- Modify: `science/tests/test_health.py`
- Modify: `science/tests/validate/test_context.py`
- Test: `science/tests/test_health_schema_invalid.py`
- Test: `science/tests/graph/test_arbitration_strict_boundary.py`

**Interfaces:**
- Produce: `enforce_project_source_strictness(sources: ProjectSources, *, strict_core_schema: bool, strict_identity: bool) -> ProjectSources`
- Extend `ValidateContext.from_project_root()` with keyword-only parameter `project_sources: ProjectSources | None = None`.
- Extend `science_tool.validate.runner.run()` with keyword-only parameter `project_sources: ProjectSources | None = None`.
- Extend: `execute_validation(project_root: Path, *, project_sources: ProjectSources | None = None) -> ValidationHealthRun`
- Preserve: `load_project_sources()` and standalone health collector contracts.

- [ ] **Step 1: Write the failing health parse-count test**

Add a test to `science/tests/test_health.py` that writes two canonical active
tasks, wraps `science_tool.graph.storage_adapters.task._parse_task_path`, runs a
default `_report(tmp_path)`, and asserts each task path is parsed exactly twice:
once for the commons-inclusive bundle and once for the local-only bundle.

```python
def test_health_parses_each_task_once_per_commons_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from collections import Counter
    from datetime import date

    from science_model.tasks import Task
    from science_tool.graph.storage_adapters import task as task_adapter
    from science_tool.tasks import render_task_file

    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    active = tmp_path / "tasks" / "active"
    active.mkdir(parents=True)
    for index in range(2):
        task = Task(
            id=f"t{index:03d}",
            title=f"Task {index}",
            priority="P2",
            status="active",
            created=date(2026, 1, 1),
        )
        (active / f"{task.id}-task.md").write_text(render_task_file(task), encoding="utf-8")

    real = task_adapter._parse_task_path
    parsed: list[str] = []

    def counted(path: Path):
        parsed.append(path.name)
        return real(path)

    monkeypatch.setattr(task_adapter, "_parse_task_path", counted)

    _report(tmp_path)

    assert Counter(parsed) == {"t000-task.md": 2, "t001-task.md": 2}
```

- [ ] **Step 2: Run the test and verify the repeated-load failure**

Run:

```bash
cd science && uv run --frozen pytest -p no:randomly tests/test_health.py::test_health_parses_each_task_once_per_commons_mode -v
```

Expected: FAIL because each task is parsed more than twice.

- [ ] **Step 3: Write strict-projection and cache-key tests**

Replace the identical-parameter-only test in
`science/tests/validate/test_context.py` with these two tests:

```python
def test_project_sources_reuses_one_load_across_strictness_modes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace
    from typing import cast

    from science_tool.graph.sources import ProjectSources

    ctx = ValidateContext.from_project_root(_project(tmp_path), strict=False, verbose=False)
    loaded = cast(
        ProjectSources,
        SimpleNamespace(skipped_entities=[], arbitration_errors=[]),
    )
    calls: list[bool] = []

    def counted_load_project_sources(
        project_root: Path,
        *,
        include_commons: bool,
        strict_core_schema: bool,
        strict_identity: bool,
    ) -> ProjectSources:
        assert project_root == ctx.project_root
        assert strict_core_schema is False
        assert strict_identity is False
        calls.append(include_commons)
        return loaded

    monkeypatch.setattr(
        "science_tool.graph.sources.load_project_sources",
        counted_load_project_sources,
    )

    for strict_core_schema in (False, True):
        for strict_identity in (False, True):
            assert (
                ctx.project_sources(
                    strict_core_schema=strict_core_schema,
                    strict_identity=strict_identity,
                )
                is loaded
            )
    assert calls == [True]

    assert ctx.project_sources(include_commons=False) is loaded
    assert calls == [True, False]


def test_project_sources_projects_core_schema_failure_from_lenient_bundle() -> None:
    from types import SimpleNamespace
    from typing import cast

    from science_tool.graph.sources import (
        ProjectSources,
        SkippedEntity,
        enforce_project_source_strictness,
    )

    sources = cast(
        ProjectSources,
        SimpleNamespace(
            skipped_entities=[
                SkippedEntity(
                    path="entities/questions/bad.md",
                    kind="question",
                    reason="core_schema_validation_failed",
                    details="missing title",
                )
            ],
            arbitration_errors=[],
        ),
    )

    assert (
        enforce_project_source_strictness(
            sources,
            strict_core_schema=False,
            strict_identity=False,
        )
        is sources
    )
    with pytest.raises(
        ValueError,
        match="schema validation failed for registered entity kind",
    ):
        enforce_project_source_strictness(
            sources,
            strict_core_schema=True,
            strict_identity=False,
        )
```

Retain the existing arbitration strict-boundary tests for identity exceptions.

- [ ] **Step 4: Run the new context tests and verify they fail**

Run:

```bash
cd science && uv run --frozen pytest -p no:randomly tests/validate/test_context.py tests/test_health_schema_invalid.py tests/graph/test_arbitration_strict_boundary.py -v
```

Expected: the new cross-strictness reuse/projection tests FAIL; existing
strictness tests PASS.

- [ ] **Step 5: Implement strictness projection**

In `graph/sources.py`, add one function that checks
`SkippedEntity.reason == "core_schema_validation_failed"` first and raises the
same public `ValueError` shape as the strict loader, then calls
`_raise_first_arbitration_error()` when `strict_identity` is true, and finally
returns `sources`.

Do not change direct `load_project_sources()` behavior in this task.

- [ ] **Step 6: Cache only meaningful source variants**

Change `ValidateContext.project_sources()` to cache
`load_project_sources()` calls made with
`strict_core_schema=False, strict_identity=False` by
`include_commons` only, then call `enforce_project_source_strictness()` for the
requested strict flags.

Allow `from_project_root()` to seed the commons-inclusive cache with an
existing `ProjectSources` bundle. Thread that optional bundle through
`validate.runner.run()` and `health_checks.validate.execute_validation()`;
`run_check(context)` passes `context.sources`.

Change `check_authored_relations()` to use `ctx.project_sources()` instead of
calling `load_project_sources()` directly.

- [ ] **Step 7: Run the scoped correctness and performance tests**

Run:

```bash
cd science && uv run --frozen pytest -p no:randomly tests/test_health.py tests/test_health_schema_invalid.py tests/validate/test_context.py tests/validate/test_runner.py tests/validate/test_check_relations.py tests/graph/test_arbitration_strict_boundary.py -v --durations=20
```

Expected: PASS, with the parse-count test proving two parses per task.

- [ ] **Step 8: Benchmark the two measured budget hotspots**

Run twice:

```bash
cd science && uv run --frozen pytest -p no:randomly \
  tests/test_budget_regression.py \
  tests/test_budget_regression_reports.py \
  -k 'health or validate_is_bounded_and_complete' \
  --durations=20
```

Record both wall clocks and compare them with the 16–17 second health cases and
20.42 second validate-report baseline.

- [ ] **Step 9: Commit Task 1**

```bash
git add science/src/science_tool/graph/sources.py \
  science/src/science_tool/validate/context.py \
  science/src/science_tool/validate/runner.py \
  science/src/science_tool/graph/health_checks/validate.py \
  science/src/science_tool/validate/checks/relations.py \
  science/tests/test_health.py science/tests/validate/test_context.py \
  science/tests/test_health_schema_invalid.py \
  science/tests/graph/test_arbitration_strict_boundary.py
git commit -m "perf: reuse canonical sources during validation"
```

### Task 2: Prune all reference/spec walkers before descent

**Files:**
- Create: `science/src/science_tool/project_walk.py`
- Modify: `science/src/science_tool/entities.py`
- Modify: `science/src/science_tool/text_scan.py`
- Modify: `science/src/science_tool/migrate_specs.py`
- Modify: `science/tests/test_text_scan.py`
- Test: `science/tests/test_entities.py`
- Test: `science/tests/test_migrate_specs.py`

**Interfaces:**
- Produce: `REFERENCE_SCAN_SKIP_DIRS: frozenset[str]`
- Produce: `iter_project_files(project_root: Path, *, suffixes: frozenset[str] | None = None) -> list[Path]`
- Preserve: explicit exclusions, graph-artifact exclusion, size limits, scan-skip reporting, filenames matching the skip set, symlink-file inclusion, symlink-directory non-descent, and deterministic ordering.

- [ ] **Step 1: Write failing shared-walker behavior tests**

Add tests in `test_text_scan.py` that exercise the new helper contract:

```python
def test_project_walk_prunes_skipped_directories_and_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os

    from science_tool.project_walk import iter_project_files

    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "hidden.md").write_text("hidden\n", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "worktrees").write_text("hidden\n", encoding="utf-8")
    keep = tmp_path / "keep.md"
    keep.write_text("keep\n", encoding="utf-8")

    real_scandir = os.scandir
    scanned_directories: list[Path] = []

    def recording_scandir(path: str | bytes | os.PathLike[str] | os.PathLike[bytes]):
        scanned_directories.append(Path(path))
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", recording_scandir)

    assert iter_project_files(tmp_path) == [keep]
    assert tmp_path / ".git" not in scanned_directories


def test_project_walk_filters_suffix_before_file_stat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.project_walk import iter_project_files

    keep = tmp_path / "keep.md"
    keep.write_text("keep\n", encoding="utf-8")
    skipped = tmp_path / "skip.bin"
    skipped.write_bytes(b"binary")
    real_is_file = Path.is_file

    def guarded_is_file(path: Path) -> bool:
        if path == skipped:
            raise AssertionError("suffix filtering happened after stat")
        return real_is_file(path)

    monkeypatch.setattr(Path, "is_file", guarded_is_file)

    assert iter_project_files(tmp_path, suffixes=frozenset({".md"})) == [keep]


def test_project_walk_does_not_follow_directory_symlinks(tmp_path: Path) -> None:
    from science_tool.project_walk import iter_project_files

    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "target.md"
    target.write_text("target\n", encoding="utf-8")
    hidden = outside / "hidden.md"
    hidden.write_text("hidden\n", encoding="utf-8")
    link_to_file = project / "link.md"
    link_to_directory = project / "linked-directory"
    try:
        link_to_file.symlink_to(target)
        link_to_directory.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")

    files = iter_project_files(project)

    assert link_to_file in files
    assert all(path.name != "hidden.md" for path in files)
```

- [ ] **Step 2: Run the tests and verify the helper is absent**

Run:

```bash
cd science && uv run --frozen pytest -p no:randomly tests/test_text_scan.py -v
```

Expected: FAIL because `science_tool.project_walk` does not exist.

- [ ] **Step 3: Implement the shared stdlib walker**

Create `project_walk.py` using `os.walk` with
`onerror=_raise_walk_error` and `followlinks=False`. Sort and mutate
`dirnames[:]` after removing every name in
`REFERENCE_SCAN_SKIP_DIRS`. Remove matching filenames too. When `suffixes` is
provided, reject nonmatching names before `Path.is_file()`. Return sorted
regular-file paths; this retains symlink files and excludes FIFOs and directory
symlinks.

Move the skip-dir constant out of `entities.py`; do not leave an alias or
compatibility layer.

- [ ] **Step 4: Route all three consumers through the helper**

Delete `entities._iter_reference_scan_files()` and call
`iter_project_files(project_root)` directly.

Use `iter_project_files(project_root, suffixes=TEXT_SUFFIXES)` in text scanning
and spec discovery. Keep each consumer's own graph/exclude/size/readability
rules after the shared walk. In text scanning, test the cheap suffix in the
walker before calling `resolve()` or `stat()`.

- [ ] **Step 5: Run scoped scanner tests**

Run:

```bash
cd science && uv run --frozen pytest -p no:randomly \
  tests/test_text_scan.py tests/test_entities.py tests/test_migrate_specs.py -v
```

Expected: PASS.

- [ ] **Step 6: Benchmark the real-checkout scan back-to-back**

Run at least three times:

```bash
cd science && uv run --frozen pytest -p no:randomly \
  tests/test_text_scan.py::test_scans_the_real_repository_and_covers_its_python \
  --durations=1
```

Compare the median with the 16–20 second range. Record checkout state because
Dropbox and `.git` contents make isolated measurements noisy.

- [ ] **Step 7: Commit Task 2**

```bash
git add science/src/science_tool/project_walk.py \
  science/src/science_tool/entities.py science/src/science_tool/text_scan.py \
  science/src/science_tool/migrate_specs.py science/tests/test_text_scan.py \
  science/tests/test_entities.py science/tests/test_migrate_specs.py
git commit -m "perf: prune excluded scan trees before descent"
```

### Task 3: Reuse mutable ontology fixtures safely

**Files:**
- Modify: `science/model/tests/test_ontologies.py`

**Interfaces:**
- Produce test helper: `_catalog(name: str) -> OntologyCatalog`
- Preserve direct tests of `load_registry()`, unknown-name rejection,
  `available_ontology_names()`, and `load_catalogs_for_names()`.

- [ ] **Step 1: Add a cached loader plus deep-copy boundary**

Use stdlib `functools.cache`:

```python
@cache
def _loaded_catalog(name: str) -> OntologyCatalog:
    return load_catalogs_for_names([name])[0]


def _catalog(name: str) -> OntologyCatalog:
    return _loaded_catalog(name).model_copy(deep=True)
```

Replace repeated content-test loads with `_catalog(name)`. Leave the direct
loader-contract tests unchanged.

- [ ] **Step 2: Run and benchmark the ontology module**

Run twice:

```bash
cd science/model && uv run --frozen pytest -p no:randomly tests/test_ontologies.py --durations=40
```

Expected: PASS, with repeated 0.06–0.07 second catalog parse entries removed.

- [ ] **Step 3: Commit Task 3**

```bash
git add science/model/tests/test_ontologies.py
git commit -m "test: reuse parsed ontology catalogs"
```

### Task 4: Measure and optionally filter rdflib warning noise

**Files:**
- Modify only if retained: `science/pyproject.toml`

**Interfaces:**
- Preserve all toolkit warnings.
- Ignore only exact rdflib deprecation messages already observed from
  `Dataset.default_context`, `Dataset.contexts`, and `ConjunctiveGraph`.

- [ ] **Step 1: Measure a warning-heavy module without filters**

Run twice and record wall clocks and warning counts:

```bash
cd science && uv run --frozen pytest -p no:randomly \
  tests/test_proposition_resynthesis_apply.py --durations=10
```

- [ ] **Step 2: Measure exact temporary filters**

Repeat with command-line `-W` filters matching only the observed rdflib
messages. Keep the configuration change only if the median improves by at
least one second or five percent.

- [ ] **Step 3: Add exact pytest filters or skip the change**

If retained, add `filterwarnings` entries under
`[tool.pytest.ini_options]`; do not use a blanket
`ignore::DeprecationWarning`. Re-run the module without command-line filters and
confirm the warning summary and timing.

- [ ] **Step 4: Commit only if retained**

```bash
git add science/pyproject.toml
git commit -m "test: filter rdflib deprecation noise"
```

If the threshold is not met, make no commit and record the measured no-op.

### Task 5: Verify, re-profile, and correct runtime guidance

**Files:**
- Modify if stale after optimization: `AGENTS.md`
- Mirror if modified: `templates/agents-md.md`

- [ ] **Step 1: Run static checks**

```bash
cd science && uv run ruff check
cd science && uv run pyright
```

- [ ] **Step 2: Run the model default suite**

```bash
cd science/model && uv run --frozen pytest -p no:randomly --durations=40
```

- [ ] **Step 3: Run the Science default suite**

Run only after no other suite is active in this worktree:

```bash
cd science && uv run --frozen pytest -p no:randomly --durations=60
```

Record passed/skipped/deselected counts, wall clock, and the slowest grouped
causes. Do not claim that the first tranche explains the unmeasured remainder.

- [ ] **Step 4: Update stale runtime guidance if needed**

If the fresh full-suite result is outside the documented `~2–3 min`, replace
that estimate in `AGENTS.md` and mirror the same phrasing in
`templates/agents-md.md`.

- [ ] **Step 5: Commit verification documentation if changed**

```bash
git add AGENTS.md templates/agents-md.md
git commit -m "docs: update default suite runtime guidance"
```

- [ ] **Step 6: Review the final diff and measurements**

```bash
git status --short
git diff --check HEAD~4..HEAD
git log --oneline -6
```

Report before/after wall clocks, task-parse counts, walker medians, ontology
timings, warning-filter decision, and remaining hotspots that justify a second
tranche.
