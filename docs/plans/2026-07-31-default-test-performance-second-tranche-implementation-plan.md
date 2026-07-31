# Default Test Performance Second Tranche Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut the dominant default pytest costs by reusing immutable generated assets, real collector results, and one verified-stable stress corpus without changing production behavior or weakening assertions.

**Architecture:** Keep every optimization inside the three affected test modules. Patch the existing collection boundaries only after their first real full-corpus call, and keep CLI rendering, projection, exit-code, and output-file paths real on every invocation; independently, move deterministic read-only fixtures to module scope.

**Tech Stack:** Python 3.12, pytest fixtures and `monkeypatch`, Click `CliRunner`, Ruff, Pyright.

## Global Constraints

- No production behavior changes, production memoization, new dependencies, markers, exclusions, or stress-corpus reductions.
- The first cached value must come from a real collector run over the same stress corpus; synthetic reports do not satisfy the guards.
- Tests that mutate generated output keep private function-scoped trees.
- All per-test output files stay under function-scoped `tmp_path`, outside shared source corpora.
- Run suites sequentially; never run two suites concurrently in the same worktree.
- Success medians: `test_agent_assets.py` at most 35 seconds; the three budget modules at most 90 seconds; the full default suite at most 8 minutes.
- Preserve 151 agent-asset tests and 73 budget-cluster tests, including randomized-order success.

---

### Task 1: Reuse real budget collectors and the shared project corpus

**Files:**
- Modify: `science/tests/test_budget_regression.py`
- Modify: `science/tests/test_budget_regression_reports.py`

**Interfaces:**
- Consumes: the real boundaries `science_tool.graph.health.execute_health_report`, `science_tool.tasks._read_active`, `science_tool.prose_lint_cli.scan_root`, `science_tool.curate.cli.collect_inventory`, `science_tool.consolidation_candidates.detect_consolidation_candidates`, and `science_tool.validate.cli.run`.
- Produces: module-scoped `project_root`, function-scoped `project`, and local one-value cache wrappers that return real collector result types unchanged; `_read_active` returns a fresh `list` per call.

- [ ] **Step 1: Record the performance-red baseline**

Run from `science/` three times sequentially:

```bash
uv run --frozen pytest -p no:randomly --durations=40 \
  tests/test_budget_regression.py \
  tests/test_budget_regression_reports.py \
  tests/test_budget_regression_rows.py
```

Expected: 73 tests pass and the median is above the 90-second target (measured baseline: 180.58 seconds).

- [ ] **Step 2: Share only the large project source corpus**

Replace the current `project` builder with a module-scoped source fixture and a function-scoped working-directory wrapper:

```python
@pytest.fixture(scope="module")
def project_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("budget-project")
    # existing science.yaml, task, entity, hypothesis, and data seeding, rooted at `root`
    return root


@pytest.fixture
def project(project_root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(project_root)
    return project_root
```

Keep all 14 overflow fixtures function-scoped.

- [ ] **Step 3: Cache the project collectors after their first real call**

Add module-scoped caches beside `project_root`. Patch health with the same real `HealthExecution` for presentation-only variants, and patch task `_read_active` with a cache keyed by its real read arguments:

```python
@pytest.fixture(scope="module")
def project_cache() -> dict[str, object]:
    return {}


@pytest.fixture
def project(project_root, project_cache, monkeypatch):
    from science_tool.graph import health as health_module

    real_health = health_module.execute_health_report
    real_read_active = task_module._read_active

    def health_once(*args, **kwargs):
        if "health" not in project_cache:
            project_cache["health"] = real_health(*args, **kwargs)
        return project_cache["health"]

    def tasks_once(*args, **kwargs):
        if "tasks" not in project_cache:
            project_cache["tasks"] = real_read_active(*args, **kwargs)
        return list(project_cache["tasks"])

    monkeypatch.setattr(health_module, "execute_health_report", health_once)
    monkeypatch.setattr(task_module, "_read_active", tasks_once)
    monkeypatch.chdir(project_root)
    return project_root
```

Use the exact collector signatures found in the source when implementing. Do not cache project-index, inventory, or data-audit collection unless fresh timings prove they dominate after this change.

- [ ] **Step 4: Move project output sinks to function temp roots**

Add `tmp_path: Path` to every shared-project test that writes a report and replace `project / <output>` with `tmp_path / <output>`, including failure-path and control-notice targets. Keep `project` only as the command input and working directory.

- [ ] **Step 5: Cache each inline report collector locally**

In `test_budget_regression_reports.py`, use the smallest local helper that executes its boundary once and patches the named module attribute:

```python
def _reuse_collection(monkeypatch: pytest.MonkeyPatch, module: object, name: str) -> None:
    collect = getattr(module, name)
    result = []

    def collect_once(*args, **kwargs):
        if not result:
            result.append(collect(*args, **kwargs))
        return result[0]

    monkeypatch.setattr(module, name, collect_once)
```

Install it after seeding and before the first `_assert_document_*` or `_assert_report_projection` call for the four exact boundaries. This keeps all CLI invocations real while avoiding repeated scans.

- [ ] **Step 6: Verify behavior and the performance-green result**

Run from `science/`:

```bash
uv run --frozen pytest -p no:randomly \
  tests/test_budget_regression.py \
  tests/test_budget_regression_reports.py \
  tests/test_budget_regression_rows.py
uv run --frozen pytest \
  tests/test_budget_regression.py \
  tests/test_budget_regression_reports.py \
  tests/test_budget_regression_rows.py
```

Expected: 73 passed in both runs. Then repeat the deterministic timed command three times; expected median at most 90 seconds.

- [ ] **Step 7: Commit the budget test optimization**

```bash
git add science/tests/test_budget_regression.py science/tests/test_budget_regression_reports.py
git commit -m "test: reuse budget regression collections"
```

### Task 2: Reuse deterministic agent distributions

**Files:**
- Modify: `science/tests/test_agent_assets.py`

**Interfaces:**
- Consumes: `generate_agent_assets(ROOT, skills_output, commands_output) -> GenerationResult`.
- Produces: module-scoped `generated: GenerationResult` and `skills_root: Path` fixtures; no `_generate` helper remains.

- [ ] **Step 1: Record the performance-red baseline**

Run from `science/` three times sequentially:

```bash
uv run --frozen pytest -p no:randomly --durations=30 tests/test_agent_assets.py
```

Expected: 151 tests pass and the median is above the 35-second target (measured baseline: 106.77 seconds).

- [ ] **Step 2: Make the immutable fixtures module-scoped**

```python
@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> GenerationResult:
    root = tmp_path_factory.mktemp("agent-assets")
    return generate_agent_assets(ROOT, root / "skills", root / "commands")


@pytest.fixture(scope="module")
def skills_root(generated: GenerationResult) -> Path:
    return generated.skill_paths["science-status"].parent.parent
```

- [ ] **Step 3: Reuse the fixture in read-only tests**

For each direct `_generate(tmp_path)` call that only reads emitted files, replace `tmp_path: Path` with `generated: GenerationResult` and bind `skills = generated.skill_paths` where needed. Delete `_generate`. Keep direct `generate_agent_assets` calls in failure, mutation, pruning, symlink, and committed-output equivalence tests.

- [ ] **Step 4: Verify behavior and the performance-green result**

Run from `science/`:

```bash
uv run --frozen pytest -p no:randomly tests/test_agent_assets.py
uv run --frozen pytest tests/test_agent_assets.py
```

Expected: 151 passed in both runs. Then repeat the deterministic timed command three times; expected median at most 35 seconds.

- [ ] **Step 5: Commit the agent fixture optimization**

```bash
git add science/tests/test_agent_assets.py
git commit -m "test: reuse generated agent assets"
```

### Task 3: Reassess the default suite

**Files:**
- Modify only if results require factual corrections: `docs/plans/2026-07-31-default-test-performance-second-tranche-design.md`

**Interfaces:**
- Consumes: the exact test commands and success targets in the approved design.
- Produces: fresh scoped medians, randomized-order evidence, lint/type evidence, and full-suite wall-clock evidence.

- [ ] **Step 1: Run static checks**

From `science/`:

```bash
uv run --frozen ruff check
uv run --frozen pyright
```

Expected: both exit 0.

- [ ] **Step 2: Run the combined affected tests with randomization**

```bash
uv run --frozen pytest tests/test_agent_assets.py \
  tests/test_budget_regression.py \
  tests/test_budget_regression_reports.py \
  tests/test_budget_regression_rows.py
```

Expected: 224 passed.

- [ ] **Step 3: Run the full default CLI suite**

```bash
uv run --frozen pytest -p no:randomly --durations=60
```

Expected: zero failures and at most 8 minutes.

- [ ] **Step 4: Run the model suite sequentially**

From `science/model/`:

```bash
uv run --frozen pytest -p no:randomly
```

Expected: zero failures.

- [ ] **Step 5: Review the final diff and commits**

```bash
git diff main...HEAD --check
git diff main...HEAD --stat
git status --short
```

Expected: no whitespace errors, only the plan and three test modules changed, and a clean worktree after commits.
