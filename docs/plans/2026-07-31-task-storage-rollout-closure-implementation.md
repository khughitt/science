# Task-storage Rollout Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct bracket handling in the shared task parser, transactionally migrate all 13 registered legacy task stores without changing their task sets, close post-acute-infection's stale local artifacts, and refresh the 14 affected composites.

**Architecture:** A published toolkit commit is the only prerequisite. Each consumer then migrates in its own worktree, records complete unbudgeted evidence outside Git, proves normalized task and task-domain graph parity, and merges one atomic local commit into its local `main`. Composite graphs are rebuilt only after every local graph is current, preserving the authored peer lists and default Commons behavior.

**Tech Stack:** Python 3.13, Click, Pydantic `Task`, PyYAML, RDFLib, uv, pytest, Ruff, Pyright, Git worktrees, jq, yq.

## Global Constraints

- Work only in `.worktrees/task-storage-rollout-closure`; never edit a primary consumer checkout directly.
- Use `~/d/` paths in documentation and commands; do not write `/mnt/ssd/Dropbox/` paths into tracked files.
- Treat checked-in `uv.lock` files as authoritative and run `uv sync --frozen` in every worktree before invoking Science.
- The toolkit prerequisite must be reachable from `origin/main` before any consumer lock names it.
- Do not push any consumer repository. Local `main` merges are authorized; consumer remote publication is not.
- Do not change `~/.config/science/config.yaml`, any `science.yaml` peer list, or default Commons behavior. Never substitute `--no-commons` after a Commons failure.
- Every graph-diff capture, including baselines, must use `--output`; stdout is capped at 40 rows.
- Keep validation exit statuses and stderr. Exit 0 or 1 is admissible for strict validation; exit 2, a traceback, or a new unrelated finding delta stops the project.
- A newly activated `short-form-ids` or `frontmatter-inline-gap` result is reported, not tuned away. Other unexplained validation deltas stop the project.
- The transactional migrator is the only task-store writer. Do not manually finish a partial migration, delete its journal, or copy task files between projects.
- No permanent rollout helper belongs in the toolkit or consumers. The two audit helpers in Task 3 live only under `/tmp/task-storage-rollout-closure/`.
- Do not run test suites concurrently in the toolkit worktree.
- Do not add compatibility modes, feature flags, new dependencies, or `Co-Authored-By` trailers.

## File and rollout map

Toolkit files changed by the prerequisite:

- `science/src/science_tool/tasks.py` — remove the unsupported closing-bracket title restriction at the two shared boundaries.
- `science/tests/test_tasks_dsl_roundtrip.py` — prove aggregate/ledger bracketed-title round trips.
- `science/tests/test_task_file_format.py` — prove a leading bracket survives YAML frontmatter rendering and parsing; retain multiline rejection.
- `science/tests/test_migrate_storage.py` — prove bracketed titles in done ledgers do not refuse migration.
- `science/tests/validate/test_checks_tasks.py` — replace the closing-bracket invalid-title fixture with a still-invalid whitespace title.
- `docs/plans/2026-07-26-context-budget-slice3-storage-design.md` — correct the two false claims about `]` ambiguity.
- `docs/audits/downstream-project-conventions/synthesis.md` — mark its aggregate-task convention as a dated historical observation.
- `skills/generated/science-command-preamble/references/docs/audits/downstream-project-conventions/synthesis.md` — regenerated mirror, never hand-edited independently.

Consumer migration matrix:

| Task | Project root | Active | Pin | Live docs | Composite |
|---:|---|---:|---|---|---|
| 4 | `~/d/cancer/data-sources/cbioportal` | 74 | publish new SHA | none | yes |
| 5 | `~/d/health/comparisons/pan-disease` | 58 | publish new SHA | `AGENTS.md`, `README.md` | yes |
| 6 | `~/d/cancer/meta` | 11 | publish new SHA | none | yes |
| 7 | `~/d/cancer/mechanisms/evolution` | 31 | retain | `AGENTS.md` | yes |
| 8 | `~/d/cancer/conditions/pre-cancer` | 6 | publish new SHA | none | yes |
| 9 | `~/d/cancer/cancer-types/ovarian` | 0 | publish new SHA | `AGENTS.md` | yes |
| 10 | `~/d/cancer/cancer-types/head-and-neck` | 0 | publish new SHA | `AGENTS.md` | yes |
| 11 | `~/d/cancer/cancer-types/prostate` | 0 | publish new SHA | `AGENTS.md` | yes |
| 12 | `~/d/cancer/cancer-types/breast` | 0 | publish new SHA | `AGENTS.md` | yes |
| 13 | `~/d/cancer/therapeutics` | 2 | retain | `AGENTS.md` | no |
| 14 | `~/d/health/meta` | 32 | retain | `AGENTS.md` | yes |
| 15 | `~/d/health/processes/cycles` | 53 | retain | `AGENTS.md` | yes |
| 16 | `~/d/health/processes/immunity` | 5 | publish new SHA | `AGENTS.md` | yes |
| 17 | `~/d/health/processes/post-acute-infection` | already split | retain | `AGENTS.md` | yes |

`~/d/cancer/cancer-types/multiple-myeloma` is composite-only. Its historical `tasks/active.md` citations remain unchanged. `~/d/cancer/therapeutics` has no composite.

---

### Task 1: Correct and publish-test the shared parser behavior

**Files:**
- Modify: `science/src/science_tool/tasks.py:170-205`
- Modify: `science/tests/test_tasks_dsl_roundtrip.py:54`
- Modify: `science/tests/test_task_file_format.py:252-270`
- Modify: `science/tests/test_migrate_storage.py:219-236`
- Modify: `science/tests/validate/test_checks_tasks.py:296-302`
- Modify: `docs/plans/2026-07-26-context-budget-slice3-storage-design.md:136-145,646-649`
- Modify: `docs/audits/downstream-project-conventions/synthesis.md:1-10`
- Regenerate: `skills/generated/science-command-preamble/references/docs/audits/downstream-project-conventions/synthesis.md`

**Interfaces:**
- Consumes: `_HEADER_RE = ^##\s+\[(tNNN)\]\s+(.+)$`, `render_task_file(Task) -> str`, and `plan_migration(Path, today=date) -> MigrationPlan`.
- Produces: every valid single-line `Task.title`, including `]`, is accepted by aggregate, split-frontmatter, create, edit, validation, and migration paths; aggregate titles pass through the shared validator after normalization, and existing newline/edge-whitespace rules remain.

- [ ] **Step 1: Replace the false bracket-rejection tests with acceptance regressions**

In `test_tasks_dsl_roundtrip.py`, replace `test_rejects_newline_in_title_via_header` with:

```python
@pytest.mark.parametrize(
    "title",
    ["F10 [Significant] result", "Evidence [UNVERIFIED]"],
)
def test_bracketed_title_roundtrips_through_ledger(title: str) -> None:
    task = Task(id="t014", title=title, status="done", created=date(2026, 3, 1))

    assert _roundtrip(task).title == title


def test_rejects_blank_title_via_header() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        _parse_task_block(["## [t015]    ", "- created: 2026-03-01", "", "x"])
```

In `test_task_file_format.py`, remove `"contains ] bracket"` from `test_rejects_non_single_line_title`, leaving the newline case, and add:

```python
def test_leading_bracket_title_roundtrips_through_frontmatter(tmp_path: Path) -> None:
    task = Task(
        id="t042",
        title="[UNVERIFIED] source classification",
        status="active",
        created=date(2026, 7, 20),
    )
    rendered = task_module.render_task_file(task)
    path = _write(tmp_path / "t042-unverified-source-classification.md", rendered)

    assert "title: '[UNVERIFIED] source classification'" in rendered
    assert task_module.parse_task_file(path) == task
```

Replace `test_plan_refuses_invalid_source_title` in `test_migrate_storage.py` with:

```python
def test_plan_accepts_bracketed_titles_in_done_ledgers(tmp_path: Path) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    active = _task("t001", "Current work")
    completed = [
        _task("t072", "F10 [Significant] result", status="done", completed=TODAY),
        _task("t106", "Evidence [UNVERIFIED]", status="done", completed=TODAY),
    ]
    _write_legacy(tasks_dir, [active])
    done_dir = tasks_dir / "done"
    done_dir.mkdir()
    done_dir.joinpath("2026-07.md").write_text(
        "\n".join(render_task(task) for task in completed),
        encoding="utf-8",
    )

    plan = migrate.plan_migration(tasks_dir, today=TODAY)

    assert plan.refusals == []
    assert [entry.task.id for entry in plan.entries] == ["t001"]
```

In `test_checks_tasks.py`, change the `title: Bad]` invalid fixture to `title: " leading"` and retain its expected canonical title error.

- [ ] **Step 2: Run the focused tests and confirm the old predicates fail**

Run from `science/`:

```bash
uv run --frozen pytest -q \
  tests/test_tasks_dsl_roundtrip.py::test_bracketed_title_roundtrips_through_ledger \
  tests/test_tasks_dsl_roundtrip.py::test_rejects_blank_title_via_header \
  tests/test_task_file_format.py::test_leading_bracket_title_roundtrips_through_frontmatter \
  tests/test_migrate_storage.py::test_plan_accepts_bracketed_titles_in_done_ledgers \
  tests/validate/test_checks_tasks.py
```

Expected: bracket acceptance fails on the `]` restriction, the blank aggregate-title test fails because no shared title validation runs there yet, and the replacement frontmatter whitespace fixture remains green.

- [ ] **Step 3: Remove the two unsupported predicates and correct the error text**

In `_parse_task_header`, replace the dedicated `]` branch with the shared validation call after title normalization:

```python
task_id, title = match.group(1), match.group(2).strip()
_validate_task_title(title)
return task_id, title
```

In `_validate_task_title`, remove only `or "]" in title` and change the message to:

```python
"task title must be non-empty, have no leading or trailing whitespace, and be single-line"
```

Do not change `_HEADER_RE`, `_ANY_TASK_HEADER_RE`, or the splitline-boundary checks.

- [ ] **Step 4: Correct the originating design and supersede the shipped audit claim**

At both cited locations in the 2026-07-26 storage design, state that newline boundaries are rejected but `]` is valid because `_HEADER_RE` consumes the bounded `[tNNN]` ID before capturing the title remainder.

After the audit metadata, add:

```markdown
> **Superseded note (2026-07-31):** This audit records the task layout observed
> on 2026-04-25. The current active-task store is `tasks/active/`, with one
> Markdown file per open task; `tasks/done/YYYY-MM.md` remains the closed-task
> ledger. Use `science tasks` rather than treating the aggregate `active.md`
> observations below as current operating guidance.
```

- [ ] **Step 5: Regenerate the shipped agent distributions**

Run from `science/`:

```bash
uv run --frozen science agents generate
```

Confirm the generated synthesis contains the same superseded note and no other generated file changed unexpectedly.

- [ ] **Step 6: Run focused parser, migration, validation, and generation tests**

Run from `science/`:

```bash
uv run --frozen pytest -q \
  tests/test_tasks_dsl_roundtrip.py \
  tests/test_task_file_format.py \
  tests/test_migrate_storage.py \
  tests/validate/test_checks_tasks.py \
  tests/test_agent_assets.py::test_committed_agent_distributions_match_generation
```

Expected: PASS, including all existing fail-closed migration tests and multiline-title cases.

- [ ] **Step 7: Lint the changed Python files and inspect the complete diff**

Run from `science/`:

```bash
uv run --frozen ruff check \
  src/science_tool/tasks.py \
  tests/test_tasks_dsl_roundtrip.py \
  tests/test_task_file_format.py \
  tests/test_migrate_storage.py \
  tests/validate/test_checks_tasks.py
git diff --check
git diff --stat
git diff
```

Expected: no lint or whitespace errors; the production change is only two predicate removals plus one message correction.

- [ ] **Step 8: Commit the atomic toolkit prerequisite**

```bash
git add \
  science/src/science_tool/tasks.py \
  science/tests/test_tasks_dsl_roundtrip.py \
  science/tests/test_task_file_format.py \
  science/tests/test_migrate_storage.py \
  science/tests/validate/test_checks_tasks.py \
  docs/plans/2026-07-26-context-budget-slice3-storage-design.md \
  docs/audits/downstream-project-conventions/synthesis.md \
  skills/generated/science-command-preamble/references/docs/audits/downstream-project-conventions/synthesis.md
git commit -m "fix(tasks): allow brackets in task titles"
```

### Task 2: Verify, merge, and publish the toolkit prerequisite

**Files:** None beyond Task 1.

**Interfaces:**
- Consumes: clean branch `task-storage-rollout-closure` with Task 1 committed.
- Produces: a public 40-character `origin/main` SHA stored at `/tmp/task-storage-rollout-closure/toolkit-sha.txt`; Tasks 4-6, 8-12, and 16 consume that exact SHA.

- [ ] **Step 1: Run the toolkit release gate**

Run serially from `science/` and allow the full suite roughly ten minutes:

```bash
uv run --frozen ruff check
uv run --frozen pyright
uv run --frozen pytest
```

Expected: all three pass. Do not publish after a scoped-only test run.

- [ ] **Step 2: Reconfirm clean ancestry immediately before merge**

```bash
git status --short
git fetch origin
git merge-base --is-ancestor origin/main task-storage-rollout-closure
test "$(git rev-list --count task-storage-rollout-closure..origin/main)" -eq 0
test "$(git rev-list --count origin/main..task-storage-rollout-closure)" -gt 0
```

Expected: clean worktree, origin has no commit absent from the rollout branch, and the branch has unpublished commits.

- [ ] **Step 3: Fast-forward local main and push it**

```bash
git -C ~/d/science status --short --branch
git -C ~/d/science merge --ff-only task-storage-rollout-closure
git -C ~/d/science push origin main
```

Expected: the primary checkout was clean on `main`, the merge is fast-forward only, and the push succeeds.

- [ ] **Step 4: Prove the exact SHA is publicly resolvable**

```bash
mkdir -p /tmp/task-storage-rollout-closure
git -C ~/d/science rev-parse HEAD | tee /tmp/task-storage-rollout-closure/toolkit-sha.txt
test "$(wc -c < /tmp/task-storage-rollout-closure/toolkit-sha.txt)" -eq 41
test "$(git -C ~/d/science rev-parse HEAD)" = "$(git -C ~/d/science ls-remote origin refs/heads/main | cut -f1)"
```

Expected: the local SHA, recorded SHA, and public `origin/main` SHA are identical.

### Task 3: Prepare temporary parity evidence tools

**Files:**
- Create temporarily: `/tmp/task-storage-rollout-closure/snapshot_tasks.py`
- Create temporarily: `/tmp/task-storage-rollout-closure/project_task_graph.py`
- Create evidence: `/tmp/task-storage-rollout-closure/registry.sha256`

**Interfaces:**
- Consumes: the installed `science_tool` and `science_model` packages in each consumer worktree.
- Produces: `snapshot_tasks.py PROJECT_ROOT OUTPUT_JSON`, whose output is a stable complete task structure plus done-ledger SHA-256 values; `project_task_graph.py GRAPH_TRIG OUTPUT_JSON`, whose output is the sorted task-subject domain triples excluding source provenance.

- [ ] **Step 1: Record the registry before any consumer mutation**

```bash
sha256sum ~/.config/science/config.yaml | tee /tmp/task-storage-rollout-closure/registry.sha256
```

- [ ] **Step 2: Create the task snapshot helper with the patch tool**

Create exactly:

```python
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from science_tool.tasks import parse_task_file, parse_tasks


root = Path(sys.argv[1])
output = Path(sys.argv[2])
tasks_dir = root / "tasks"
legacy = tasks_dir / "active.md"
split = tasks_dir / "active"

if legacy.is_file():
    active = parse_tasks(legacy)
elif split.is_dir():
    active = [parse_task_file(path) for path in sorted(split.glob("*.md"))]
else:
    active = []

done = []
for path in sorted((tasks_dir / "done").glob("*.md")):
    raw = path.read_bytes()
    done.append(
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "tasks": [task.model_dump(mode="json") for task in parse_tasks(path)],
        }
    )

payload = {
    "active": sorted(
        (task.model_dump(mode="json") for task in active),
        key=lambda row: row["id"],
    ),
    "done": done,
}
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
```

- [ ] **Step 3: Create the task-domain graph projection helper with the patch tool**

Create exactly:

```python
from __future__ import annotations

import json
import sys
from pathlib import Path

from rdflib import Dataset, Namespace, RDF


graph_path = Path(sys.argv[1])
output = Path(sys.argv[2])
science = Namespace("http://example.org/science/vocab/")
prov = Namespace("http://www.w3.org/ns/prov#")
dataset = Dataset()
dataset.parse(graph_path, format="trig")
task_subjects = {
    subject
    for subject, _, _, _ in dataset.quads((None, RDF.type, science.Task, None))
}
triples = sorted(
    (subject.n3(), predicate.n3(), obj.n3())
    for subject, predicate, obj, _ in dataset.quads((None, None, None, None))
    if subject in task_subjects and predicate != prov.wasDerivedFrom
)
output.write_text(json.dumps(triples, indent=2) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Smoke-test both helpers against the already-split toolkit meta project**

Run from `~/d/science/meta`:

```bash
uv run --frozen python /tmp/task-storage-rollout-closure/snapshot_tasks.py \
  . /tmp/task-storage-rollout-closure/science-meta-tasks.json
uv run --frozen python /tmp/task-storage-rollout-closure/project_task_graph.py \
  knowledge/graph.trig /tmp/task-storage-rollout-closure/science-meta-task-graph.json
jq -e '.active | type == "array"' /tmp/task-storage-rollout-closure/science-meta-tasks.json
jq -e 'type == "array"' /tmp/task-storage-rollout-closure/science-meta-task-graph.json
```

Expected: both helpers exit zero. Do not add either helper to Git.

## Local migration protocol used by Tasks 4-16

Each task below supplies exact values for `PROJECT_ROOT`, `PROJECT_ID`, `EXPECTED_COUNT`, pin action, documentation files, and commit message. Execute this protocol inside that task; a failure stops that project before commit and before its local-main merge.

1. **Create the worktree.** With the task's exact `PROJECT_ROOT`, `PROJECT_ID`, and `EXPECTED_COUNT`, run:

   ```bash
   WORKTREE="$PROJECT_ROOT/.worktrees/task-storage-rollout-closure"
   EVIDENCE_DIR="/tmp/task-storage-rollout-closure/$PROJECT_ID"
   test "$(git -C "$PROJECT_ROOT" branch --show-current)" = main
   test -z "$(git -C "$PROJECT_ROOT" status --porcelain)"
   git -C "$PROJECT_ROOT" check-ignore -q .worktrees
   test ! -e "$WORKTREE"
   git -C "$PROJECT_ROOT" worktree add "$WORKTREE" -b task-storage-rollout-closure main
   mkdir -p "$EVIDENCE_DIR"
   if git -C "$PROJECT_ROOT" remote get-url origin >/dev/null 2>&1; then
     git -C "$PROJECT_ROOT" ls-remote origin refs/heads/main \
       | tee "$EVIDENCE_DIR/remote-main-before.txt"
   fi
   cd "$WORKTREE"
   ```

2. **Synchronize the checked-in lock.** Run `uv sync --frozen`. For a retain-pin project, capture `sha256sum pyproject.toml uv.lock | tee "$EVIDENCE_DIR/dependencies-before.sha256"` and never run `uv lock`. For an upgrade project, first capture current-pin validation with the status pattern below. Then read and validate the public SHA:

   ```bash
   TOOLKIT_SHA="$(tr -d '\n' < /tmp/task-storage-rollout-closure/toolkit-sha.txt)"
   test "${#TOOLKIT_SHA}" -eq 40
   git -C ~/d/science cat-file -e "$TOOLKIT_SHA^{commit}"
   ```

   Use the patch tool to add or replace the `science` uv source's `rev` with that exact literal SHA in `pyproject.toml`; do not use an environment variable in the TOML. Then run:

   ```bash
   uv lock --upgrade-package science --upgrade-package science-model
   git diff -- pyproject.toml uv.lock
   rg -n "$TOOLKIT_SHA" pyproject.toml uv.lock
   uv sync --frozen
   uv run --frozen science --version
   ```

   Stop if the lock diff moves an unrelated source or does not resolve both Science packages from the published commit.

3. **Capture the canonical baseline under the post-pin environment.** Run:

   ```bash
   uv run --frozen python /tmp/task-storage-rollout-closure/snapshot_tasks.py \
     . "$EVIDENCE_DIR/tasks-before.json"
   exit_code=0
   uv run --frozen science tasks migrate-storage --format json \
     --output "$EVIDENCE_DIR/migration-before.json" || exit_code=$?
   printf '%s\n' "$exit_code" | tee "$EVIDENCE_DIR/migration-before.exit"
   test "$exit_code" -le 1
   jq -e --argjson expected "$EXPECTED_COUNT" \
     '.meta.mode == "dry-run" and .meta.source_count == $expected and
      (.rows | length) == $expected and all(.rows[]; .status != "refusal")' \
     "$EVIDENCE_DIR/migration-before.json"
   test "$exit_code" -eq 0
   uv run --frozen science graph diff --format json \
     --output "$EVIDENCE_DIR/local-graph-diff-before.json"
   uv run --frozen python /tmp/task-storage-rollout-closure/project_task_graph.py \
     knowledge/graph.trig "$EVIDENCE_DIR/task-graph-before.json"
   uv run --frozen science peers list --format json \
     --output "$EVIDENCE_DIR/peers-before.json"
   sha256sum science.yaml | tee "$EVIDENCE_DIR/science-yaml-before.sha256"
   git status --short | tee "$EVIDENCE_DIR/git-status-before.txt"
   ```

   Capture strict validation with `--output validate-before.json`, stderr, and its exact 0/1 status using the status block below; reject exit 2 or `Traceback`.

4. **Apply only through the migrator.** Run:

   ```bash
   uv run --frozen science tasks migrate-storage --apply --format json \
     --output "$EVIDENCE_DIR/migration-applied.json"
   jq -e --argjson expected "$EXPECTED_COUNT" \
     '.meta.mode == "applied" and .meta.source_count == $expected and
      (.rows | length) == $expected' \
     "$EVIDENCE_DIR/migration-applied.json"
   uv run --frozen python /tmp/task-storage-rollout-closure/snapshot_tasks.py \
     . "$EVIDENCE_DIR/tasks-after.json"
   cmp "$EVIDENCE_DIR/tasks-before.json" "$EVIDENCE_DIR/tasks-after.json"
   test ! -e tasks/active.md
   test ! -e tasks/.science/task-storage-migration.journal
   uv run --frozen science tasks list --all --format json \
     --output "$EVIDENCE_DIR/tasks-list-after.json"
   if (( EXPECTED_COUNT == 0 )); then
     test ! -d tasks/active
   else
     test "$(find tasks/active -maxdepth 1 -type f -name '*.md' | wc -l)" -eq "$EXPECTED_COUNT"
   fi
   exit_code=0
   uv run --frozen science tasks migrate-storage --format json \
     --output "$EVIDENCE_DIR/migration-second-run.json" || exit_code=$?
   printf '%s\n' "$exit_code" | tee "$EVIDENCE_DIR/migration-second-run.exit"
   test "$exit_code" -eq 1
   ```

   When `EXPECTED_COUNT` is nonzero, require `tasks/active/` to contain exactly that many `*.md` files. When it is zero, require `tasks/active/` absent rather than manufacturing a placeholder. Capture a second dry-run with the status pattern below and require exit 1. For non-empty projects, its action rows must contain both `tasks/active/ is non-empty` and `tasks/active.md is absent`; for empty projects they must contain `tasks/active.md is absent; there is nothing to migrate`.
5. **Correct only live docs named by the task.** Say active tasks live under `tasks/active/`, one Markdown file per open task, and operators should use `science tasks`. Do not rewrite historical reports, done ledgers, or citations.
6. **Close the local graph.** Run:

   ```bash
   uv run --frozen science graph build --local-only
   uv run --frozen science graph validate
   uv run --frozen science graph diff --format json \
     --output "$EVIDENCE_DIR/local-graph-diff-after.json"
   jq -e '.rows | length == 0' "$EVIDENCE_DIR/local-graph-diff-after.json"
   uv run --frozen python /tmp/task-storage-rollout-closure/project_task_graph.py \
     knowledge/graph.trig "$EVIDENCE_DIR/task-graph-after.json"
   cmp "$EVIDENCE_DIR/task-graph-before.json" "$EVIDENCE_DIR/task-graph-after.json"
   ```

   Provenance paths may change; task-domain triples may not.

7. **Compare validation and topology.** Capture post-build strict validation to `validate-after.json`, stderr, and exact 0/1 status. Reject `Traceback`, `resolver unavailable`, `predates the storage split`, or `falling back to deny-list only`. Then run:

   ```bash
   jq -S '.results | sort_by(.rule, .path, .line, .message, .severity, .task)' \
     "$EVIDENCE_DIR/validate-before.json" > "$EVIDENCE_DIR/validate-before-results.json"
   jq -S '.results | sort_by(.rule, .path, .line, .message, .severity, .task)' \
     "$EVIDENCE_DIR/validate-after.json" > "$EVIDENCE_DIR/validate-after-results.json"
   diff -u "$EVIDENCE_DIR/validate-before-results.json" \
     "$EVIDENCE_DIR/validate-after-results.json" > "$EVIDENCE_DIR/validate.delta" || test $? -eq 1
   uv run --frozen science peers list --format json \
     --output "$EVIDENCE_DIR/peers-after.json"
   cmp "$EVIDENCE_DIR/peers-before.json" "$EVIDENCE_DIR/peers-after.json"
   sha256sum -c "$EVIDENCE_DIR/science-yaml-before.sha256"
   ```

   Inspect `validate.delta`. Expected removals/additions are the task-storage state and graph-freshness messages; the only newly reachable prose families allowed are `short-form-ids` and `frontmatter-inline-gap`.

8. **Commit and merge locally.** Inspect `git diff --check`, `git diff --stat`, and the full diff. Stage the complete intentional project transaction with `git add -A`, inspect `git diff --cached --check` and `git diff --cached`, commit with the task's exact message, record `git rev-parse HEAD | tee "$EVIDENCE_DIR/local-commit.txt"`, then run `git -C "$PROJECT_ROOT" merge --ff-only task-storage-rollout-closure`. Do not push. Keep composite-bearing worktrees for Tasks 18-19; Task 13 may remove its worktree after the merge because therapeutics has no composite.

Use this status-capture shape whenever a command may legitimately exit 0 or 1:

```bash
exit_code=0
uv run --frozen science validate --all --strict --format json \
  --output "$EVIDENCE_DIR/validate-before.json" \
  2>"$EVIDENCE_DIR/validate-before.stderr" || exit_code=$?
printf '%s\n' "$exit_code" | tee "$EVIDENCE_DIR/validate-before.exit"
test "$exit_code" -le 1
! rg -n "Traceback" "$EVIDENCE_DIR/validate-before.stderr"
```

### Task 4: Migrate cBioPortal and prove the parser fix on the largest bracketed corpus

**Files:** `pyproject.toml`, `uv.lock`, `tasks/active.md`, `tasks/active/*.md`, `knowledge/graph.trig`, `knowledge/sources/local/manifest.yaml`, `knowledge/sources/local/mappings.yaml` under `~/d/cancer/data-sources/cbioportal`.

**Interfaces:** Consumes the public toolkit SHA and Local migration protocol. Produces 74 structurally identical split tasks and a current local graph on local `main`.

- [ ] **Step 1: Create cBioPortal's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/cancer/data-sources/cbioportal`, `PROJECT_ID=cbioportal`, and `EXPECTED_COUNT=74`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact public Task 2 SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the canonical task/validation/graph/peer baseline; explicitly prove all six historical bracketed done-ledger titles parse and the complete plan has 74 writes and zero refusals.**
- [ ] **Step 4: Apply the migrator and prove 74-task structural parity, done-ledger byte parity, split-store shape, no journal, successful listing, and the expected second-run refusal.**
- [ ] **Step 5: Make no live-doc edit because the audit found no current aggregate-path guidance in this project.**
- [ ] **Step 6: Rebuild and verify the local graph, including byte-identical task-domain projection and zero complete graph diff.**
- [ ] **Step 7: Review the complete validation delta and require unchanged peer output and `science.yaml`.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward cBioPortal's local `main`; do not push its existing origin.**

### Task 5: Migrate pan-disease and prove the second bracketed corpus

**Files:** `pyproject.toml`, `uv.lock`, `tasks/active.md`, `tasks/active/*.md`, `AGENTS.md`, `README.md`, and local graph artifacts under `~/d/health/comparisons/pan-disease`.

**Interfaces:** Consumes the public toolkit SHA and Local migration protocol. Produces 58 structurally identical split tasks and current live guidance/local graph.

- [ ] **Step 1: Create pan-disease's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/health/comparisons/pan-disease`, `PROJECT_ID=pan-disease`, and `EXPECTED_COUNT=58`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact public Task 2 SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the canonical baseline; prove the `[UNVERIFIED]` ledger title parses and the unbudgeted plan contains 58 writes and zero refusals.**
- [ ] **Step 4: Apply the migrator and prove 58-task structural parity, done-ledger byte parity, split shape, no journal, listing success, and expected second-run refusal.**
- [ ] **Step 5: Update `AGENTS.md` and both live `README.md` aggregate-path instructions to `tasks/active/` plus `science tasks`; leave historical records untouched.**
- [ ] **Step 6: Rebuild and verify the local graph, including task-domain projection parity and zero complete graph diff.**
- [ ] **Step 7: Review the complete validation delta and require unchanged peer output and `science.yaml`.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward pan-disease's local `main`; do not push.**

### Task 6: Migrate cancer/meta

**Files:** `pyproject.toml`, `uv.lock`, task store, and local graph artifacts under `~/d/cancer/meta`.

**Interfaces:** Consumes the public toolkit SHA and Local migration protocol. Produces 11 structurally identical split tasks and a current local graph.

- [ ] **Step 1: Create cancer/meta's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/cancer/meta`, `PROJECT_ID=cancer-meta`, and `EXPECTED_COUNT=11`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact public Task 2 SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical task, dry-run, validation, graph, and peer baseline; require 11 writes and no refusal.**
- [ ] **Step 4: Apply the migrator and prove 11-task structural parity, done-ledger byte parity, split shape, no journal, listing success, and expected second-run refusal.**
- [ ] **Step 5: Make no live-doc edit because no current aggregate-path instruction was found.**
- [ ] **Step 6: Rebuild and verify the local graph, task-domain parity, and zero complete graph diff.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward cancer/meta's local `main`; do not push.**

### Task 7: Migrate evolution without moving its capable pin

**Files:** task store, `AGENTS.md`, and local graph artifacts under `~/d/cancer/mechanisms/evolution`.

**Interfaces:** Consumes the Local migration protocol with the existing `7ab7528c...` lock. Produces 31 structurally identical split tasks and a current local graph.

- [ ] **Step 1: Create evolution's clean worktree and synchronize its existing lock, using `PROJECT_ROOT=~/d/cancer/mechanisms/evolution`, `PROJECT_ID=evolution`, and `EXPECTED_COUNT=31`.**
- [ ] **Step 2: Retain the capable `7ab7528c...` pin; record and later compare `pyproject.toml` and `uv.lock` digests instead of relocking.**
- [ ] **Step 3: Capture the complete canonical task, 31-write dry-run, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove 31-task structural parity, done-ledger byte parity, split shape, no journal, listing success, and expected second-run refusal.**
- [ ] **Step 5: Update `AGENTS.md` to the split-store/CLI guidance.**
- [ ] **Step 6: Rebuild and verify the local graph, task-domain parity, and zero complete graph diff.**
- [ ] **Step 7: Review validation activation, require peer/config identity, and prove dependency files remain byte-identical.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward evolution's local `main`; do not push.**

### Task 8: Migrate pre-cancer

**Files:** `pyproject.toml`, `uv.lock`, task store, and local graph artifacts under `~/d/cancer/conditions/pre-cancer`.

**Interfaces:** Consumes the public toolkit SHA and Local migration protocol. Produces six structurally identical split tasks and a current local graph.

- [ ] **Step 1: Create pre-cancer's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/cancer/conditions/pre-cancer`, `PROJECT_ID=pre-cancer`, and `EXPECTED_COUNT=6`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact public Task 2 SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical task, six-write dry-run, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove six-task structural parity, done-ledger byte parity, split shape, no journal, listing success, and expected second-run refusal.**
- [ ] **Step 5: Make no live-doc edit because no current aggregate-path instruction was found.**
- [ ] **Step 6: Rebuild and verify the local graph, task-domain parity, and zero complete graph diff.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward pre-cancer's local `main`; do not push.**

### Task 9: Migrate the empty ovarian store

**Files:** `pyproject.toml`, `uv.lock`, `tasks/active.md`, `AGENTS.md`, and local graph artifacts under `~/d/cancer/cancer-types/ovarian`.

**Interfaces:** Consumes the public toolkit SHA and Local migration protocol. Produces valid `EMPTY` task storage with no placeholder and a current local graph.

- [ ] **Step 1: Create ovarian's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/cancer/cancer-types/ovarian`, `PROJECT_ID=ovarian`, and `EXPECTED_COUNT=0`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact public Task 2 SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical zero-write dry-run, empty task snapshot, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove valid `EMPTY` storage, done-ledger parity, no aggregate, placeholder, or journal, zero-row listing, and the absent-source second-run refusal.**
- [ ] **Step 5: Update both live aggregate-path statements in `AGENTS.md` to the split-store/CLI guidance.**
- [ ] **Step 6: Rebuild and verify the local graph, empty task-domain parity, and zero complete graph diff.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward ovarian's local `main`; do not push.**

### Task 10: Migrate the empty head-and-neck store

**Files:** `pyproject.toml`, `uv.lock`, `tasks/active.md`, `AGENTS.md`, and local graph artifacts under `~/d/cancer/cancer-types/head-and-neck`.

**Interfaces:** Consumes the public toolkit SHA and Local migration protocol. Produces valid `EMPTY` task storage with no placeholder and a current local graph.

- [ ] **Step 1: Create head-and-neck's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/cancer/cancer-types/head-and-neck`, `PROJECT_ID=head-and-neck`, and `EXPECTED_COUNT=0`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact public Task 2 SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical zero-write dry-run, empty task snapshot, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove valid `EMPTY` storage, done-ledger parity, no aggregate, placeholder, or journal, zero-row listing, and absent-source refusal.**
- [ ] **Step 5: Update both live aggregate-path statements in `AGENTS.md` to the split-store/CLI guidance.**
- [ ] **Step 6: Rebuild and verify the local graph, empty task-domain parity, and zero complete graph diff.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward head-and-neck's local `main`; do not push.**

### Task 11: Migrate the empty prostate store

**Files:** `pyproject.toml`, `uv.lock`, `tasks/active.md`, `AGENTS.md`, and local graph artifacts under `~/d/cancer/cancer-types/prostate`.

**Interfaces:** Consumes the public toolkit SHA and Local migration protocol. Produces valid `EMPTY` task storage with no placeholder and a current local graph.

- [ ] **Step 1: Create prostate's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/cancer/cancer-types/prostate`, `PROJECT_ID=prostate`, and `EXPECTED_COUNT=0`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact public Task 2 SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical zero-write dry-run, empty task snapshot, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove valid `EMPTY` storage, done-ledger parity, no aggregate, placeholder, or journal, zero-row listing, and absent-source refusal.**
- [ ] **Step 5: Update both live aggregate-path statements in `AGENTS.md` to the split-store/CLI guidance.**
- [ ] **Step 6: Rebuild and verify the local graph, empty task-domain parity, and zero complete graph diff.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward prostate's local `main`; do not push.**

### Task 12: Migrate the empty breast store

**Files:** `pyproject.toml`, `uv.lock`, `tasks/active.md`, `AGENTS.md`, and local graph artifacts under `~/d/cancer/cancer-types/breast`.

**Interfaces:** Consumes the public toolkit SHA and Local migration protocol. Produces valid `EMPTY` task storage with no placeholder and a current local graph.

- [ ] **Step 1: Create breast's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/cancer/cancer-types/breast`, `PROJECT_ID=breast`, and `EXPECTED_COUNT=0`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact public Task 2 SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical zero-write dry-run, empty task snapshot, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove valid `EMPTY` storage, done-ledger parity, no aggregate, placeholder, or journal, zero-row listing, and absent-source refusal.**
- [ ] **Step 5: Update both live aggregate-path statements in `AGENTS.md` to the split-store/CLI guidance.**
- [ ] **Step 6: Rebuild and verify the local graph, empty task-domain parity, and zero complete graph diff.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward breast's local `main`; do not push.**

### Task 13: Migrate therapeutics and close its stale environment

**Files:** task store, `AGENTS.md`, and local graph artifacts under `~/d/cancer/therapeutics`.

**Interfaces:** Consumes the Local migration protocol with the existing capable lock. Produces two structurally identical split tasks and a current local graph; no composite follows.

- [ ] **Step 1: Create therapeutics' clean worktree and run `uv sync --frozen` to replace its stale installed environment, using `PROJECT_ROOT=~/d/cancer/therapeutics`, `PROJECT_ID=therapeutics`, and `EXPECTED_COUNT=2`.**
- [ ] **Step 2: Retain the capable pin; record and later compare `pyproject.toml` and `uv.lock` digests instead of relocking.**
- [ ] **Step 3: Capture the complete canonical task, two-write dry-run, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove two-task structural parity, done-ledger byte parity, split shape, no journal, listing success, and expected second-run refusal.**
- [ ] **Step 5: Update `AGENTS.md` to the split-store/CLI guidance.**
- [ ] **Step 6: Rebuild and verify the local graph, task-domain parity, zero complete graph diff, and byte-identical dependency files.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, fast-forward local `main`, do not push its origin, then require a clean merged branch and run `git -C "$PROJECT_ROOT" worktree remove "$WORKTREE"` followed by `git -C "$PROJECT_ROOT" branch -d task-storage-rollout-closure`.**

### Task 14: Migrate health/meta without moving its capable pin

**Files:** task store, `AGENTS.md`, and local graph artifacts under `~/d/health/meta`.

**Interfaces:** Consumes the Local migration protocol with the existing `7ab7528c...` lock. Produces 32 structurally identical split tasks and a current local graph.

- [ ] **Step 1: Create health/meta's clean worktree and synchronize its existing lock, using `PROJECT_ROOT=~/d/health/meta`, `PROJECT_ID=health-meta`, and `EXPECTED_COUNT=32`.**
- [ ] **Step 2: Retain the capable `7ab7528c...` pin; record and later compare `pyproject.toml` and `uv.lock` digests instead of relocking.**
- [ ] **Step 3: Capture the complete canonical task, 32-write dry-run, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove 32-task structural parity, done-ledger byte parity, split shape, no journal, listing success, and expected second-run refusal.**
- [ ] **Step 5: Update both live aggregate-path statements in `AGENTS.md` to the split-store/CLI guidance.**
- [ ] **Step 6: Rebuild and verify the local graph, task-domain parity, zero complete graph diff, and byte-identical dependency files.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward health/meta's local `main`; do not push.**

### Task 15: Migrate cycles without rewriting its historical workflow README

**Files:** task store, `AGENTS.md`, and local graph artifacts under `~/d/health/processes/cycles`.

**Interfaces:** Consumes the Local migration protocol with the existing capable lock. Produces 53 structurally identical split tasks and a current local graph.

- [ ] **Step 1: Create cycles' clean worktree and synchronize its existing lock, using `PROJECT_ROOT=~/d/health/processes/cycles`, `PROJECT_ID=cycles`, and `EXPECTED_COUNT=53`.**
- [ ] **Step 2: Retain the capable pin; record and later compare `pyproject.toml` and `uv.lock` digests instead of relocking.**
- [ ] **Step 3: Capture the complete canonical task, 53-write dry-run, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove 53-task structural parity, done-ledger byte parity, split shape, no journal, listing success, and expected second-run refusal.**
- [ ] **Step 5: Update `AGENTS.md`; leave the workflow README's dated aggregate-path record unchanged as history.**
- [ ] **Step 6: Rebuild and verify the local graph, task-domain parity, zero complete graph diff, and byte-identical dependency files.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward cycles' local `main`; do not push its existing origin.**

### Task 16: Migrate immunity

**Files:** `pyproject.toml`, `uv.lock`, task store, `AGENTS.md`, and local graph artifacts under `~/d/health/processes/immunity`.

**Interfaces:** Consumes the public toolkit SHA and Local migration protocol. Produces five structurally identical split tasks and a current local graph.

- [ ] **Step 1: Create immunity's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/health/processes/immunity`, `PROJECT_ID=immunity`, and `EXPECTED_COUNT=5`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact public Task 2 SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical task, five-write dry-run, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove five-task structural parity, done-ledger byte parity, split shape, no journal, listing success, and expected second-run refusal.**
- [ ] **Step 5: Update both live aggregate-path statements in `AGENTS.md` to the split-store/CLI guidance.**
- [ ] **Step 6: Rebuild and verify the local graph, task-domain parity, and zero complete graph diff.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward immunity's local `main`; do not push.**

### Task 17: Close post-acute-infection without rerunning migration

**Files:** `AGENTS.md`, `knowledge/graph.trig`, `knowledge/sources/local/manifest.yaml`, `knowledge/sources/local/mappings.yaml` under `~/d/health/processes/post-acute-infection`.

**Interfaces:** Consumes its already-split task store at local-main commit ancestry containing `67361ff`. Produces unchanged split tasks, corrected live guidance, and a current local graph.

- [ ] **Step 1: Create and synchronize the isolated worktree**

```bash
PROJECT_ROOT=~/d/health/processes/post-acute-infection
WORKTREE="$PROJECT_ROOT/.worktrees/task-storage-rollout-closure"
EVIDENCE_DIR=/tmp/task-storage-rollout-closure/post-acute-infection
git -C "$PROJECT_ROOT" status --short --branch
git -C "$PROJECT_ROOT" check-ignore -q .worktrees
git -C "$PROJECT_ROOT" merge-base --is-ancestor 67361ff main
git -C "$PROJECT_ROOT" worktree add "$WORKTREE" -b task-storage-rollout-closure main
mkdir -p "$EVIDENCE_DIR"
git -C "$PROJECT_ROOT" ls-remote origin refs/heads/main \
  | tee "$EVIDENCE_DIR/remote-main-before.txt"
cd "$WORKTREE"
uv sync --frozen
```

Expected: clean `main`, the migration commit is already an ancestor, and no migrator command is run.

- [ ] **Step 2: Capture task, validation, graph, and topology baselines**

Use the Task 3 helpers and the protocol's complete `--output` captures. Record `tasks-before.json`, `task-graph-before.json`, `validate-before.json` plus status/stderr, `local-graph-diff-before.json`, `peers-before.json`, and the `science.yaml` digest.

- [ ] **Step 3: Correct the live guide and rebuild only the local graph**

Patch `AGENTS.md` to describe `tasks/active/` and `science tasks`, then run:

```bash
uv run --frozen science graph build --local-only
uv run --frozen science graph validate
uv run --frozen science graph diff --format json \
  --output "$EVIDENCE_DIR/local-graph-diff-after.json"
```

- [ ] **Step 4: Prove closure parity**

Recreate task and task-domain graph snapshots and require both byte-identical to baseline. Require zero graph-diff rows, identical peer output and `science.yaml` digest, no migration journal, no `tasks/active.md`, successful task listing, and post-validation without traceback or storage fallback. Review validation deltas under the same rules as the Local migration protocol.

- [ ] **Step 5: Commit and merge locally**

```bash
git add AGENTS.md knowledge/graph.trig \
  knowledge/sources/local/manifest.yaml knowledge/sources/local/mappings.yaml
git diff --cached --check
git diff --cached
git commit -m "chore(science): close task storage rollout"
git rev-parse HEAD | tee "$EVIDENCE_DIR/local-commit.txt"
git -C "$PROJECT_ROOT" merge --ff-only task-storage-rollout-closure
```

Do not push its existing origin. Keep the worktree for the health composite phase.

## Composite refresh protocol used by Tasks 18-19

For each listed project's `.worktrees/task-storage-rollout-closure`, set that project's existing `EVIDENCE_DIR` and run:

```bash
sha256sum knowledge/graph.trig | tee "$EVIDENCE_DIR/local-graph-before-composite.sha256"
uv run --frozen science peers list --format json \
  --output "$EVIDENCE_DIR/peers-composite-before.json"
uv run --frozen science graph build
sha256sum -c "$EVIDENCE_DIR/local-graph-before-composite.sha256"
uv run --frozen science peers list --format json \
  --output "$EVIDENCE_DIR/peers-composite-after.json"
cmp "$EVIDENCE_DIR/peers-composite-before.json" \
  "$EVIDENCE_DIR/peers-composite-after.json"
uv run --frozen science graph validate --path knowledge/composite.trig
uv run --frozen science graph diff --path knowledge/composite.trig --format json \
  --output "$EVIDENCE_DIR/composite-graph-diff-after.json"
jq -e '.rows | length == 0' "$EVIDENCE_DIR/composite-graph-diff-after.json"
```

Any Commons resolution failure, local graph byte delta, peer delta, validation failure, or nonzero diff stops that project. Do not retry with `--no-commons`. Inspect `git status --short`: if `knowledge/composite.trig` changed, stage only that file, run `git diff --cached --check`, inspect the staged diff, commit `chore(science): refresh composite graph`, and record `git rev-parse HEAD | tee "$EVIDENCE_DIR/composite-commit.txt"`. If it did not change, make no commit and record `git rev-parse HEAD | tee "$EVIDENCE_DIR/composite-unchanged-at.txt"`. Fast-forward the rollout branch into the repository's local `main`; do not push.

### Task 18: Refresh all affected cancer composites

**Files:** `knowledge/composite.trig` in cancer/meta, multiple-myeloma, evolution, pre-cancer, cBioPortal, ovarian, head-and-neck, prostate, and breast.

**Interfaces:** Consumes every cancer local migration commit already merged to its local `main`; consumes the existing authored `peers:` lists and default Commons resolution. Produces validated, zero-diff composites without changing any local graph bytes.

- [ ] **Step 1: Create the composite-only multiple-myeloma worktree**

At `~/d/cancer/cancer-types/multiple-myeloma`, assert clean `main` and ignored `.worktrees`, create branch/worktree `task-storage-rollout-closure`, run `uv sync --frozen`, and create `/tmp/task-storage-rollout-closure/multiple-myeloma`.

- [ ] **Step 2: Refresh each cancer composite from its retained worktree**

Process exactly these roots, one at a time:

```text
~/d/cancer/meta
~/d/cancer/cancer-types/multiple-myeloma
~/d/cancer/mechanisms/evolution
~/d/cancer/conditions/pre-cancer
~/d/cancer/data-sources/cbioportal
~/d/cancer/cancer-types/ovarian
~/d/cancer/cancer-types/head-and-neck
~/d/cancer/cancer-types/prostate
~/d/cancer/cancer-types/breast
```

Execute the Composite refresh protocol for each project in that order. Stop at the affected project on any failed gate.

- [ ] **Step 3: Commit only changed composites and merge each branch locally**

For each root, inspect `git status --short`. The Composite refresh protocol commits only a changed `knowledge/composite.trig` with:

```bash
git add knowledge/composite.trig
git diff --cached --check
git commit -m "chore(science): refresh composite graph"
```

If it did not change, make no commit. In either case, merge the rollout branch into that repository's local `main` with `--ff-only`. Do not push cBioPortal or any other consumer.

### Task 19: Refresh all affected health composites

**Files:** `knowledge/composite.trig` in health/meta, pan-disease, cycles, immunity, and post-acute-infection.

**Interfaces:** Consumes all health local commits already merged to local `main`, authored peer lists, and default Commons resolution. Produces validated, zero-diff composites without local graph changes.

- [ ] **Step 1: Process exactly the five retained health worktrees**

```text
~/d/health/meta
~/d/health/comparisons/pan-disease
~/d/health/processes/cycles
~/d/health/processes/immunity
~/d/health/processes/post-acute-infection
```

Execute the Composite refresh protocol for each project in that order using its existing evidence directory. Stop on Commons failure, local graph change, peer change, invalid graph, or nonzero diff; never use `--no-commons`.

- [ ] **Step 2: Commit only changed composites and merge locally**

For each root, commit only a changed `knowledge/composite.trig` with `chore(science): refresh composite graph`, make no empty commit, and fast-forward the local rollout branch into local `main`. Do not push cycles, post-acute-infection, or any other consumer.

### Task 20: Run the registry-wide closure audit and clean consumer worktrees

**Files:** Evidence only under `/tmp/task-storage-rollout-closure/`; no tracked mutation.

**Interfaces:** Consumes all local-main merges and evidence from Tasks 3-19. Produces the final completion report and leaves primary repositories clean with consumer changes unpublished.

- [ ] **Step 1: Prove the global registry was not edited**

```bash
sha256sum -c /tmp/task-storage-rollout-closure/registry.sha256
```

- [ ] **Step 2: Prove every present non-Commons registered project has retired the aggregate store**

Run:

```bash
yq -r '.projects[] | select(.role != "commons") | [.id, .path] | @tsv' \
  ~/.config/science/config.yaml |
while IFS=$'\t' read -r project_id project_root; do
  if [[ "$project_id" == obsproj ]]; then
    test ! -e "$project_root"
    printf 'skip %s: registered path is absent\n' "$project_id"
    continue
  fi
  test -d "$project_root"
  test ! -e "$project_root/tasks/active.md"
done
printf 'skip commons: role has no task queue\n'
```

Expected: the two skips are explicit; every present non-Commons project passes the absence assertion.

- [ ] **Step 3: Prove all 272 migrated active tasks survived structurally**

Run:

```bash
project_ids=(
  cbioportal pan-disease cancer-meta evolution pre-cancer ovarian head-and-neck
  prostate breast therapeutics health-meta cycles immunity
)
for project_id in $project_ids; do
  cmp "/tmp/task-storage-rollout-closure/$project_id/tasks-before.json" \
    "/tmp/task-storage-rollout-closure/$project_id/tasks-after.json"
done
jq -s -e 'map(.active | length) | add == 272' \
  /tmp/task-storage-rollout-closure/{cbioportal,pan-disease,cancer-meta,evolution,pre-cancer,ovarian,head-and-neck,prostate,breast,therapeutics,health-meta,cycles,immunity}/tasks-before.json
```

Also require no `tasks/.science/task-storage-migration.journal` in those 13 roots or post-acute-infection.

- [ ] **Step 4: Recheck every local and composite artifact from local main**

Use this exact local target map:

```bash
closure_ids=(
  cancer-meta evolution pre-cancer cbioportal ovarian head-and-neck prostate breast
  therapeutics health-meta pan-disease cycles immunity post-acute-infection
)
closure_roots=(
  ~/d/cancer/meta
  ~/d/cancer/mechanisms/evolution
  ~/d/cancer/conditions/pre-cancer
  ~/d/cancer/data-sources/cbioportal
  ~/d/cancer/cancer-types/ovarian
  ~/d/cancer/cancer-types/head-and-neck
  ~/d/cancer/cancer-types/prostate
  ~/d/cancer/cancer-types/breast
  ~/d/cancer/therapeutics
  ~/d/health/meta
  ~/d/health/comparisons/pan-disease
  ~/d/health/processes/cycles
  ~/d/health/processes/immunity
  ~/d/health/processes/post-acute-infection
)
for (( index = 1; index <= ${#closure_ids}; index++ )); do
  project_id="${closure_ids[$index]}"
  project_root="${closure_roots[$index]}"
  final_dir="/tmp/task-storage-rollout-closure/$project_id/final"
  mkdir -p "$final_dir"
  (
    cd "$project_root"
    uv run --frozen science graph validate
    uv run --frozen science graph diff --format json \
      --output "$final_dir/local-graph-diff.json"
  )
  jq -e '.rows | length == 0' "$final_dir/local-graph-diff.json"
done
```

Then run:

```bash
composite_ids=(
  cancer-meta multiple-myeloma evolution pre-cancer cbioportal ovarian head-and-neck
  prostate breast health-meta pan-disease cycles immunity post-acute-infection
)
composite_roots=(
  ~/d/cancer/meta
  ~/d/cancer/cancer-types/multiple-myeloma
  ~/d/cancer/mechanisms/evolution
  ~/d/cancer/conditions/pre-cancer
  ~/d/cancer/data-sources/cbioportal
  ~/d/cancer/cancer-types/ovarian
  ~/d/cancer/cancer-types/head-and-neck
  ~/d/cancer/cancer-types/prostate
  ~/d/cancer/cancer-types/breast
  ~/d/health/meta
  ~/d/health/comparisons/pan-disease
  ~/d/health/processes/cycles
  ~/d/health/processes/immunity
  ~/d/health/processes/post-acute-infection
)
for (( index = 1; index <= ${#composite_ids}; index++ )); do
  project_id="${composite_ids[$index]}"
  project_root="${composite_roots[$index]}"
  final_dir="/tmp/task-storage-rollout-closure/$project_id/final"
  mkdir -p "$final_dir"
  (
    cd "$project_root"
    uv run --frozen science graph validate --path knowledge/composite.trig
    uv run --frozen science graph diff --path knowledge/composite.trig --format json \
      --output "$final_dir/composite-graph-diff.json"
  )
  jq -e '.rows | length == 0' "$final_dir/composite-graph-diff.json"
done
test ! -e ~/d/cancer/therapeutics/knowledge/composite.trig
```

Do not create a therapeutics composite.

- [ ] **Step 5: Recheck federation health without changing topology**

Using the exact `closure_ids` and `closure_roots` arrays from Step 4, run from every project root:

```bash
for (( index = 1; index <= ${#closure_ids}; index++ )); do
  project_id="${closure_ids[$index]}"
  project_root="${closure_roots[$index]}"
  final_dir="/tmp/task-storage-rollout-closure/$project_id/final"
  (
    cd "$project_root"
    uv run --frozen science peers check --format json
    uv run --frozen science peers list --format json --output "$final_dir/peers.json"
  )
  cmp "/tmp/task-storage-rollout-closure/$project_id/peers-before.json" \
    "$final_dir/peers.json"
done
```

Exit 0 and byte-identical peer lists are required.

- [ ] **Step 6: Recheck task and validation behavior**

Using the exact `closure_ids` and `closure_roots` arrays from Step 4, run for every entry:

```bash
for (( index = 1; index <= ${#closure_ids}; index++ )); do
  project_id="${closure_ids[$index]}"
  project_root="${closure_roots[$index]}"
  final_dir="/tmp/task-storage-rollout-closure/$project_id/final"
  (
    cd "$project_root"
    uv run --frozen science tasks list --all --format json \
      --output "$final_dir/tasks.json"
    exit_code=0
    uv run --frozen science validate --all --strict --format json \
      --output "$final_dir/validate.json" \
      2>"$final_dir/validate.stderr" || exit_code=$?
    printf '%s\n' "$exit_code" | tee "$final_dir/validate.exit"
    test "$exit_code" -le 1
  )
  ! rg -n "Traceback|resolver unavailable|predates the storage split|falling back to deny-list only" \
    "$final_dir/validate.stderr"
done
```

Extract and report any activated `short-form-ids` or `frontmatter-inline-gap` result; do not suppress it.

- [ ] **Step 7: Confirm local-main state and unpublished remotes**

For every touched repository, require the SHA in its `local-commit.txt` (or the multiple-myeloma composite SHA) to be an ancestor of local `main`, and require an empty primary `git status --porcelain`. This works even though Task 13 already deleted therapeutics' merged branch. For the four repositories with remotes, compare the remote ref to its recorded pre-rollout value and report local ahead counts:

```bash
remote_ids=(cbioportal therapeutics cycles post-acute-infection)
remote_roots=(
  ~/d/cancer/data-sources/cbioportal
  ~/d/cancer/therapeutics
  ~/d/health/processes/cycles
  ~/d/health/processes/post-acute-infection
)
for (( index = 1; index <= ${#remote_ids}; index++ )); do
  project_id="${remote_ids[$index]}"
  project_root="${remote_roots[$index]}"
  git -C "$project_root" ls-remote origin refs/heads/main \
    > "/tmp/task-storage-rollout-closure/$project_id/remote-main-after.txt"
  cmp "/tmp/task-storage-rollout-closure/$project_id/remote-main-before.txt" \
    "/tmp/task-storage-rollout-closure/$project_id/remote-main-after.txt"
  git -C "$project_root" rev-list --left-right --count origin/main...main
done
```

An identical remote ref proves the rollout did not publish consumer commits.

- [ ] **Step 8: Remove only clean, merged consumer worktrees**

For the 13 migrated roots, post-acute-infection, and multiple-myeloma, run:

```bash
cleanup_roots=($closure_roots ~/d/cancer/cancer-types/multiple-myeloma)
for PROJECT_ROOT in $cleanup_roots; do
  WORKTREE="$PROJECT_ROOT/.worktrees/task-storage-rollout-closure"
  if [[ -d "$WORKTREE" ]]; then
    test -z "$(git -C "$WORKTREE" status --porcelain)"
    git -C "$PROJECT_ROOT" merge-base --is-ancestor task-storage-rollout-closure main
    git -C "$PROJECT_ROOT" worktree remove "$WORKTREE"
    git -C "$PROJECT_ROOT" branch -d task-storage-rollout-closure
  fi
done
```

Therapeutics is already absent by Task 13. Leave the toolkit worktree in place for final review and branch handoff.

- [ ] **Step 9: Write the completion report**

Report: public toolkit SHA; all consumer commit SHAs; 272/272 task parity; empty-store outcomes; local/composite zero-diff results; cBioPortal 74 and pan-disease 58 no-refusal proofs; validation activations; unchanged registry and peer topology; Commons success; worktree cleanup; and which consumer mains remain unpublished. Also list the intentionally deferred `obsproj`, registry-parent, peer-symmetry, standalone-graph, and historical-citation follow-ups.
