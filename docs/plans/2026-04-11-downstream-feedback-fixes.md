# Downstream Feedback Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the live downstream feedback issues by aligning command docs with centralized framework defaults, making `graph question-summary` return all rows by default, and requiring `science-tool` installation for every new or imported project.

**Architecture:** The work splits into three layers. Documentation contract tests protect the command/docs model. `science-tool` CLI and validation changes enforce the runtime behavior. Project-bootstrap docs define the install path for new and imported repositories, including non-Python repos that need a root tool manifest.

**Tech Stack:** Markdown command docs, Bash (`validate.sh`), Python 3.11, Click, pytest

**References:** `docs/plans/2026-04-11-downstream-feedback-fixes-design.md`, `references/command-preamble.md`

---

### Task 1: Add regression tests for command-doc path resolution

**Files:**
- Create: `science-tool/tests/test_command_docs.py`
- Modify: `commands/add-hypothesis.md`
- Modify: `commands/bias-audit.md`
- Modify: `commands/compare-hypotheses.md`
- Modify: `commands/discuss.md`
- Modify: `commands/find-datasets.md`
- Modify: `commands/interpret-results.md`
- Modify: `commands/next-steps.md`
- Modify: `commands/pre-register.md`
- Modify: `commands/research-paper.md`
- Modify: `commands/research-topic.md`
- Modify: `commands/search-literature.md`
- Modify: `commands/status.md`

- [ ] **Step 1: Write the failing doc-contract tests**

Create `science-tool/tests/test_command_docs.py` with checks that command docs no longer rely on project-local framework defaults. Cover at least:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_commands_do_not_reference_project_local_command_preamble() -> None:
    command_paths = [
        "commands/add-hypothesis.md",
        "commands/bias-audit.md",
        "commands/compare-hypotheses.md",
        "commands/discuss.md",
        "commands/find-datasets.md",
        "commands/interpret-results.md",
        "commands/next-steps.md",
        "commands/pre-register.md",
        "commands/research-paper.md",
        "commands/research-topic.md",
        "commands/search-literature.md",
    ]
    for path in command_paths:
        assert "Follow `references/command-preamble.md`" not in _read(path)


def test_commands_use_ai_template_or_framework_template_language() -> None:
    command_paths = [
        "commands/discuss.md",
        "commands/find-datasets.md",
        "commands/interpret-results.md",
        "commands/pre-register.md",
        "commands/research-paper.md",
        "commands/research-topic.md",
    ]
    for path in command_paths:
        text = _read(path)
        assert "Read `templates/" not in text
        assert "Follow `templates/" not in text


def test_status_and_interpret_results_do_not_assume_project_local_model_doc() -> None:
    assert "docs/claim-and-evidence-model.md" not in _read("commands/status.md")
    assert "docs/claim-and-evidence-model.md" not in _read("commands/interpret-results.md")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_command_docs.py -q
```

Expected: FAIL because the command docs still contain project-local `references/`, `templates/`, and `docs/` paths.

- [ ] **Step 3: Update the command docs to use explicit resolution rules**

For each affected command:

- replace `Follow references/command-preamble.md` with explicit framework wording such as:

```md
Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).
```

- replace `Read templates/<name>.md` / `Follow templates/<name>.md` with override-aware wording such as:

```md
Resolve `.ai/templates/<name>.md` first; if it does not exist, use `${CLAUDE_PLUGIN_ROOT}/templates/<name>.md`.
```

- replace project-local model-doc references in command setup text with explicit framework references or with the canonical proposition/evidence document chosen for this workflow

- [ ] **Step 4: Re-run the doc-contract tests**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_command_docs.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science-tool/tests/test_command_docs.py commands/*.md
git commit -m "docs: align command references with centralized framework defaults"
```

---

### Task 2: Define and document the `science-tool` install contract for all projects

**Files:**
- Modify: `commands/create-project.md`
- Modify: `commands/import-project.md`
- Modify: `references/project-structure.md`
- Modify: `README.md`
- Modify: `references/command-preamble.md`
- Modify: `science-tool/tests/test_command_docs.py`

- [ ] **Step 1: Extend the doc-contract tests with install expectations**

Append tests that lock in the new bootstrap requirement:

```python
def test_create_project_requires_science_tool_install_step() -> None:
    text = _read("commands/create-project.md")
    assert "uv add --dev --editable" in text
    assert "pyproject.toml" in text


def test_import_project_requires_science_tool_install_step() -> None:
    text = _read("commands/import-project.md")
    assert "uv add --dev --editable" in text
    assert "pyproject.toml" in text


def test_project_structure_documents_root_tool_manifest() -> None:
    text = _read("references/project-structure.md")
    assert "pyproject.toml" in text
    assert "science-tool" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_command_docs.py -q
```

Expected: FAIL because the bootstrap docs do not yet require a tool manifest or `uv add --dev --editable`.

- [ ] **Step 3: Update create/import docs**

In `commands/create-project.md` and `commands/import-project.md`:

- add a root `pyproject.toml` to the canonical top-level files for all projects
- specify:
  - reuse the existing root `pyproject.toml` if present
  - otherwise create a minimal one for Science tooling
- add an explicit install step:

```bash
uv add --dev --editable "$SCIENCE_TOOL_PATH"
```

- state that this applies even for non-Python repos because the manifest hosts project-local tooling

A minimal tool-only manifest should look like:

```toml
[project]
name = "<project-slug>-science-tools"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[dependency-groups]
dev = []
```

- [ ] **Step 4: Update the structure and usage references**

In `references/project-structure.md`, `README.md`, and `references/command-preamble.md`:

- document the root `pyproject.toml` as the home for project-local Science tooling
- explain that a tool-only manifest is valid for non-Python repos
- keep the `uv run --with ...` fallback in `references/command-preamble.md` for legacy projects, but make project-local install the expected default

- [ ] **Step 5: Re-run the doc-contract tests**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_command_docs.py -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add commands/create-project.md commands/import-project.md references/project-structure.md README.md references/command-preamble.md science-tool/tests/test_command_docs.py
git commit -m "docs: require project-local science-tool install for all projects"
```

---

### Task 3: Enforce `science-tool` availability in `validate.sh`

**Files:**
- Modify: `scripts/validate.sh`
- Modify: `science-tool/tests/test_validate_script.py`

- [ ] **Step 1: Write the failing validation tests**

Add tests that cover both failure and success:

```python
import os


def test_validate_fails_when_science_tool_unavailable(tmp_path: Path) -> None:
    _write_common_files(tmp_path, "software")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "science-tool is required" in result.stdout + result.stderr


def test_validate_accepts_project_when_science_tool_on_path(tmp_path: Path) -> None:
    _write_common_files(tmp_path, "software")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tool = bin_dir / "science-tool"
    tool.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    tool.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
```

- [ ] **Step 2: Run the validation tests to verify they fail**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_validate_script.py -q
```

Expected: FAIL because `validate.sh` currently warns when `science-tool` is missing instead of failing.

- [ ] **Step 3: Update `validate.sh`**

Change the script so `science-tool` is treated as a baseline project requirement:

- resolve the tool once near the top of the script:

```bash
SCIENCE_TOOL_CMD="$(resolve_science_tool)"
```

- if empty, emit an error like:

```bash
error "science-tool is required for task management, feedback, and graph workflows"
```

- downgrade later graph-specific missing-tool branches so they do not duplicate the same error

- [ ] **Step 4: Re-run the validation tests**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_validate_script.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/validate.sh science-tool/tests/test_validate_script.py
git commit -m "feat(validate): require science-tool for all science projects"
```

---

### Task 4: Make `graph question-summary` return all rows by default

**Files:**
- Modify: `science-tool/tests/test_graph_cli.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `commands/status.md`
- Modify: `commands/interpret-results.md`
- Modify: `README.md`

- [ ] **Step 1: Write the failing CLI regression test**

Append a test near the existing `question-summary` coverage:

```python
def test_graph_question_summary_returns_all_questions_by_default() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        for i in range(30):
            qid = f"Q{i:02d}"
            pid = f"claim_{i:02d}"
            assert runner.invoke(
                main,
                ["graph", "add", "question", qid, "--text", f"Question {i}", "--source", "article:doi_10_5555_all"],
            ).exit_code == 0
            assert runner.invoke(
                main,
                ["graph", "add", "proposition", f"Claim {i}", "--source", "article:doi_10_5555_all", "--id", pid],
            ).exit_code == 0
            assert runner.invoke(
                main,
                ["graph", "add", "edge", f"proposition/{pid}", "sci:addresses", f"question/q{i:02d}"],
            ).exit_code == 0

        result = runner.invoke(main, ["graph", "question-summary", "--format", "json"])
        payload = json.loads(result.output)

        assert result.exit_code == 0
        assert len(payload["rows"]) == 30
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_graph_cli.py -q -k "question_summary_returns_all_questions_by_default"
```

Expected: FAIL because the command still defaults to `--top 25`.

- [ ] **Step 3: Implement the minimal CLI/store change**

Update `science-tool/src/science_tool/cli.py`:

- change `--top` on `graph question-summary` to default to `None`
- update help text to clarify that `--top` is optional truncation

Update `science-tool/src/science_tool/graph/store.py`:

- accept `top: int | None`
- return all rows when `top is None`
- preserve existing sorting logic

The core return should become:

```python
rows.sort(key=lambda row: (-float(row["priority_score"]), row["text"]))
return rows if top is None else rows[:top]
```

- [ ] **Step 4: Update the user-facing docs**

In `commands/status.md`, `commands/interpret-results.md`, and `README.md`:

- note that `question-summary` returns the full set by default
- mention `--top` only as an optional narrowing flag for dashboards or quick scans

- [ ] **Step 5: Re-run the targeted and nearby graph tests**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_graph_cli.py -q -k "question_summary"
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add science-tool/tests/test_graph_cli.py science-tool/src/science_tool/cli.py science-tool/src/science_tool/graph/store.py commands/status.md commands/interpret-results.md README.md
git commit -m "fix(graph): return all question-summary rows by default"
```

---

### Task 5: Run the focused verification suite and clean up docs wording

**Files:**
- Modify as needed: files from Tasks 1-4

- [ ] **Step 1: Run the focused verification commands**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_command_docs.py tests/test_validate_script.py tests/test_graph_cli.py -q -k "question_summary or validate or command_docs"
```

Expected: PASS

- [ ] **Step 2: Run repo formatting and targeted checks if any touched Python files need it**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen ruff check src tests
```

Expected: PASS

- [ ] **Step 3: Review command wording for consistency**

Confirm the final docs consistently distinguish:

- project-local overrides in `.ai/`
- centralized framework defaults under `${CLAUDE_PLUGIN_ROOT}`
- project-local `science-tool` installation as the baseline expectation

- [ ] **Step 4: Final commit**

```bash
git add commands README.md references scripts/validate.sh science-tool/src science-tool/tests docs/plans
git commit -m "fix: address downstream feedback on defaults, installs, and question summaries"
```
