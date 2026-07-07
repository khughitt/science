# Explore-Ideas Kind Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route kept `topic` and `theme` candidates through `science explore-ideas apply` instead of leaving them as manual work, and verify multi-lens convergence survives apply.

**Architecture:** Keep the existing `explore_ideas.py` apply pipeline. Replace the manual-only kind split with a single routable set for all currently valid apply kinds, and preserve the existing dataclass output shape so JSON consumers do not need a schema break.

**Tech Stack:** Python 3.12, Click CLI, Pytest, Pyright, Ruff, Science entity scaffolding.

---

### Task 1: Add failing tests for topic/theme routing

**Files:**
- Modify: `science/tests/test_explore_ideas_apply.py`

- [ ] **Step 1: Replace the invalid-kind parametrization**

Change:

```python
@pytest.mark.parametrize("kind", [None, "topic"])
def test_build_plan_rejects_invalid_proposed_kind(kind: object) -> None:
    data = _keep_question(proposed_kind=kind)
    with pytest.raises(ApplyValidationError):
        build_create_plan("cand-q", data, "opus")
```

to:

```python
@pytest.mark.parametrize("kind", [None, "proverb"])
def test_build_plan_rejects_invalid_proposed_kind(kind: object) -> None:
    data = _keep_question(proposed_kind=kind)
    with pytest.raises(ApplyValidationError):
        build_create_plan("cand-q", data, "opus")
```

- [ ] **Step 2: Add build-plan acceptance tests**

Add after `test_build_plan_rejects_invalid_proposed_kind`:

```python
@pytest.mark.parametrize("kind", ["topic", "theme"])
def test_build_plan_accepts_topic_and_theme(kind: str) -> None:
    data = _keep_question(proposed_kind=kind, title=f"A {kind}")

    plan = build_create_plan(f"cand-{kind}", data, "opus")

    assert plan.kind == kind
    assert plan.title == f"A {kind}"
    assert plan.origins == [{"type": "assistant", "ref": "explore-ideas-mechanism"}]
```

- [ ] **Step 3: Update the partition test expectation**

In `test_plan_report_partitions_by_decision_and_kind`, change the final assertions to:

```python
    assert [p.candidate_id for p in plan.to_create] == ["k1", "t1"]
    assert [p.kind for p in plan.to_create] == ["question", "topic"]
    assert plan.skipped_applied == ["a1"]
    assert plan.skipped_other == ["d1"]
    assert plan.manual == []
```

- [ ] **Step 4: Run the focused failing tests**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_explore_ideas_apply.py::test_build_plan_accepts_topic_and_theme \
  tests/test_explore_ideas_apply.py::test_plan_report_partitions_by_decision_and_kind \
  -q
```

Expected before implementation: failures showing `topic`/`theme` are invalid or still manual.

### Task 2: Route all valid current kinds through apply

**Files:**
- Modify: `science/src/science_tool/explore_ideas.py`

- [ ] **Step 1: Collapse the current kind policy**

At the top of `explore_ideas.py`, change:

```python
_ROUTABLE_KINDS = {"question", "hypothesis"}
_MANUAL_KINDS = {"topic", "theme"}
_VALID_KINDS = _ROUTABLE_KINDS | _MANUAL_KINDS
```

to:

```python
_ROUTABLE_KINDS = {"question", "hypothesis", "topic", "theme"}
_MANUAL_KINDS: set[str] = set()
_VALID_KINDS = _ROUTABLE_KINDS | _MANUAL_KINDS
```

- [ ] **Step 2: Keep `plan_report` explicit**

Do not delete the `manual` branch in `plan_report`. It should remain:

```python
        if kind in _MANUAL_KINDS:
            manual.append((block.candidate_id, kind))
            continue
```

With an empty manual set, this preserves the output contract without adding a schema break.

- [ ] **Step 3: Run the focused tests again**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_explore_ideas_apply.py::test_build_plan_accepts_topic_and_theme \
  tests/test_explore_ideas_apply.py::test_plan_report_partitions_by_decision_and_kind \
  -q
```

Expected: both tests pass.

### Task 3: Add apply/check integration coverage

**Files:**
- Modify: `science/tests/test_explore_ideas_apply.py`

- [ ] **Step 1: Replace the manual-topic CLI check test**

Find the test that writes `_KEEP_TOPIC` and asserts:

```python
assert "apply manually (topic): cand-topic" in result.output
```

Replace it with:

```python
def test_cli_apply_check_includes_topic_in_to_create(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = _write_keep_topic(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "explore-ideas",
            "apply",
            "--project-root",
            str(tmp_path),
            "--from",
            str(report),
            "--model-id",
            "test-model",
            "--check",
        ],
    )

    assert result.exit_code == 0
    assert "1 to create" in result.output
    assert "create topic: cand-topic -> Topic candidate" in result.output
    assert "apply manually" not in result.output
    assert not list((tmp_path / "entities" / "topics").glob("*.md"))
```

- [ ] **Step 2: Add topic apply integration test**

Add near the other CLI/apply integration tests:

```python
def test_apply_report_creates_topic_and_writes_back(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = _write_keep_topic(tmp_path)

    result = apply_report(tmp_path, str(report), "test-model", date(2026, 7, 6))

    assert result.manual == []
    assert [(created.candidate_id, created.kind) for created in result.created] == [("cand-topic", "topic")]
    created_path = result.created[0].path
    fm = _frontmatter(created_path)
    assert fm["kind"] == "topic"
    assert fm["title"] == "Topic candidate"
    assert fm["origins"] == [{"type": "assistant", "ref": "explore-ideas-mechanism"}]
    assert fm["added_by"] == "explore-ideas:test-model:cand-topic"
    assert "decision: applied" in report.read_text(encoding="utf-8")
    assert f"applied_as: {result.created[0].entity_id}" in report.read_text(encoding="utf-8")
```

- [ ] **Step 3: Add theme apply integration test**

Add:

```python
def test_apply_report_creates_theme_and_writes_back(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = tmp_path / "doc" / "explorations" / "explore-theme.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        """\
# Theme report

```yaml
candidate_id: cand-theme
proposed_kind: theme
title: Cross-cutting theme
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-contrast
```
""",
        encoding="utf-8",
    )

    result = apply_report(tmp_path, str(report), "test-model", date(2026, 7, 6))

    assert result.manual == []
    assert [(created.candidate_id, created.kind) for created in result.created] == [("cand-theme", "theme")]
    fm = _frontmatter(result.created[0].path)
    assert fm["kind"] == "theme"
    assert fm["title"] == "Cross-cutting theme"
    assert fm["theme_kind"] == "methodological"
    assert fm["theme_scope"] == "project"
    assert fm["origins"] == [{"type": "assistant", "ref": "explore-ideas-contrast"}]
    assert "decision: applied" in report.read_text(encoding="utf-8")
```

- [ ] **Step 4: Run the new focused integration tests**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_explore_ideas_apply.py::test_cli_apply_check_includes_topic_in_to_create \
  tests/test_explore_ideas_apply.py::test_apply_report_creates_topic_and_writes_back \
  tests/test_explore_ideas_apply.py::test_apply_report_creates_theme_and_writes_back \
  -q
```

Expected: all pass after Task 2.

### Task 4: Verify convergence apply persistence

**Files:**
- Modify: `science/tests/test_explore_ideas_apply.py`

- [ ] **Step 1: Add an end-to-end multi-lens apply test**

Add near the existing lens-view tests:

```python
def test_apply_report_persists_multi_lens_origins_and_views(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = tmp_path / "doc" / "explorations" / "explore-converged.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        """\
# Converged report

```yaml
candidate_id: cand-converged
proposed_kind: question
title: Shared idea
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
      independent: true
    - type: assistant
      ref: explore-ideas-contrast
      independent: true
lens_views:
  - lens: mechanism
    rationale: Mechanism-first framing.
    origin_ref: explore-ideas-mechanism
  - lens: contrast
    rationale: Contrast-first framing.
    origin_ref: explore-ideas-contrast
```
""",
        encoding="utf-8",
    )

    result = apply_report(tmp_path, str(report), "test-model", date(2026, 7, 6))

    fm = _frontmatter(result.created[0].path)
    assert fm["origins"] == [
        {"type": "assistant", "ref": "explore-ideas-mechanism", "independent": True},
        {"type": "assistant", "ref": "explore-ideas-contrast", "independent": True},
    ]
    assert fm["lens_views"] == [
        {
            "lens": "mechanism",
            "rationale": "Mechanism-first framing.",
            "origin_ref": "explore-ideas-mechanism",
        },
        {
            "lens": "contrast",
            "rationale": "Contrast-first framing.",
            "origin_ref": "explore-ideas-contrast",
        },
    ]
```

- [ ] **Step 2: Run the new convergence test**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_explore_ideas_apply.py::test_apply_report_persists_multi_lens_origins_and_views \
  -q
```

Expected: pass.

### Task 5: Update command and skill documentation

**Files:**
- Modify: `commands/explore-ideas.md`
- Modify: `codex-skills/science-explore-ideas/SKILL.md`

- [ ] **Step 1: Replace stale manual wording in command docs**

In `commands/explore-ideas.md`, replace apply wording that says topic/theme blocks are manual with wording equivalent to:

```markdown
`--check` performs the same parse and validation without writing entities or marking
blocks applied. It reports creates, skipped blocks, and any manual blocks reserved for
future valid-but-not-routable decisions.
```

and:

```markdown
Apply creates kept `question`, `hypothesis`, `topic`, and `theme` blocks. It rejects
unknown `decision`/`proposed_kind`, duplicate ids, malformed origins, malformed
`lens_views`, unresolved or ambiguous `related_existing`, and malformed routed anchors
before any writes.
```

- [ ] **Step 2: Mirror the same wording in the Codex skill**

Make the same wording changes in `codex-skills/science-explore-ideas/SKILL.md`.

- [ ] **Step 3: Run docs mirror tests**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_command_docs.py \
  tests/test_codex_skills.py \
  -q
```

Expected: pass.

### Task 6: Full focused verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run the focused explore-ideas apply suite**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_explore_ideas_apply.py \
  tests/test_explore_ideas_anchor_resolver.py \
  tests/test_command_docs.py \
  tests/test_codex_skills.py \
  -q
```

Expected: pass.

- [ ] **Step 2: Run lint**

Run from `science/`:

```bash
uv run --frozen ruff check
```

Expected: pass.

- [ ] **Step 3: Run type check on touched implementation and tests**

Run from `science/`:

```bash
uv run --frozen pyright \
  src/science_tool/explore_ideas.py \
  tests/test_explore_ideas_apply.py
```

Expected: pass.

- [ ] **Step 4: Inspect final diff**

Run from the worktree root:

```bash
git diff --stat
git diff -- science/src/science_tool/explore_ideas.py science/tests/test_explore_ideas_apply.py commands/explore-ideas.md codex-skills/science-explore-ideas/SKILL.md
```

Expected: the diff only contains the kind-routing change, focused tests, and stale manual wording updates.
