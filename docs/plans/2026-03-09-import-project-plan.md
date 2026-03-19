# Import Project Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an `import-project` command that adopts Science for existing projects, plus update infrastructure to respect path mappings from `science.yaml`.

**Architecture:** A `paths:` section in `science.yaml` maps Science conventions to existing directory names. A shared `resolve_project_paths()` utility in Python and a shell function in validate.sh read these mappings. The command preamble teaches all commands to check mappings before assuming paths.

**Tech Stack:** Bash (validate.sh), Python (science-tool), Markdown (command + reference docs)

---

### Task 1: Add `paths` support to science.yaml schema

**Files:**
- Modify: `references/science-yaml-schema.md`

**Step 1: Update the schema doc**

Add the `paths:` section after the existing `data_sources` field:

```yaml
# Optional — path mappings for imported projects
# Omit entirely for standard Science layout (all defaults apply)
paths:
  doc_dir: "string"        # Default: doc/
  code_dir: "string"       # Default: code/
  data_dir: "string"       # Default: data/
  models_dir: "string"     # Default: models/
  specs_dir: "string"      # Default: specs/
  papers_dir: "string"     # Default: papers/
  knowledge_dir: "string"  # Default: knowledge/
  tasks_dir: "string"      # Default: tasks/
  templates_dir: "string"  # Default: templates/
  prompts_dir: "string"    # Default: prompts/
```

Add an "Imported Project Example" after the existing example showing a project with path mappings.

**Step 2: Commit**

```bash
git add references/science-yaml-schema.md
git commit -m "docs: add paths section to science.yaml schema"
```

---

### Task 2: Add `resolve_paths()` utility to science-tool

**Files:**
- Create: `science-tool/src/science_tool/paths.py`
- Create: `science-tool/tests/test_paths.py`

**Step 1: Write the failing test**

```python
# science-tool/tests/test_paths.py
from pathlib import Path
from science_tool.paths import resolve_paths, ProjectPaths

def test_defaults_when_no_yaml(tmp_path: Path) -> None:
    paths = resolve_paths(tmp_path)
    assert paths.doc_dir == tmp_path / "doc"
    assert paths.code_dir == tmp_path / "code"
    assert paths.data_dir == tmp_path / "data"
    assert paths.knowledge_dir == tmp_path / "knowledge"
    assert paths.tasks_dir == tmp_path / "tasks"

def test_defaults_when_yaml_has_no_paths(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: test\nstatus: active\n")
    paths = resolve_paths(tmp_path)
    assert paths.doc_dir == tmp_path / "doc"

def test_mapped_paths(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: test\nstatus: active\npaths:\n  doc_dir: docs/\n  code_dir: src/\n"
    )
    paths = resolve_paths(tmp_path)
    assert paths.doc_dir == tmp_path / "docs"
    assert paths.code_dir == tmp_path / "src"
    # Unmapped keys still get defaults
    assert paths.data_dir == tmp_path / "data"

def test_models_dir_nested(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: test\nstatus: active\npaths:\n  models_dir: src/models/registry/\n"
    )
    paths = resolve_paths(tmp_path)
    assert paths.models_dir == tmp_path / "src/models/registry"
```

**Step 2: Run test to verify it fails**

Run: `cd /mnt/ssd/Dropbox/science && uv run --frozen pytest science-tool/tests/test_paths.py -v`
Expected: FAIL (module not found)

**Step 3: Write the implementation**

```python
# science-tool/src/science_tool/paths.py
"""Resolve project directory paths from science.yaml mappings."""

from dataclasses import dataclass
from pathlib import Path

import yaml


_DEFAULTS: dict[str, str] = {
    "doc_dir": "doc",
    "code_dir": "code",
    "data_dir": "data",
    "models_dir": "models",
    "specs_dir": "specs",
    "papers_dir": "papers",
    "knowledge_dir": "knowledge",
    "tasks_dir": "tasks",
    "templates_dir": "templates",
    "prompts_dir": "prompts",
}


@dataclass(frozen=True)
class ProjectPaths:
    """Resolved project directory paths."""

    root: Path
    doc_dir: Path
    code_dir: Path
    data_dir: Path
    models_dir: Path
    specs_dir: Path
    papers_dir: Path
    knowledge_dir: Path
    tasks_dir: Path
    templates_dir: Path
    prompts_dir: Path


def resolve_paths(project_root: Path) -> ProjectPaths:
    """Read science.yaml and resolve directory paths with defaults."""
    yaml_path = project_root / "science.yaml"
    mappings: dict[str, str] = {}

    if yaml_path.is_file():
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        mappings = data.get("paths", {}) or {}

    resolved: dict[str, Path] = {"root": project_root}
    for key, default in _DEFAULTS.items():
        raw = mappings.get(key, default)
        # Strip trailing slashes for consistency
        resolved[key] = project_root / raw.rstrip("/")

    return ProjectPaths(**resolved)
```

**Step 4: Run test to verify it passes**

Run: `cd /mnt/ssd/Dropbox/science && uv run --frozen pytest science-tool/tests/test_paths.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/paths.py science-tool/tests/test_paths.py
git commit -m "feat: add resolve_paths utility for science.yaml path mappings"
```

---

### Task 3: Wire path resolution into store.py and refs.py

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py:17` (DEFAULT_GRAPH_PATH)
- Modify: `science-tool/src/science_tool/graph/store.py:1983-1994` (_build_input_manifest)
- Modify: `science-tool/src/science_tool/refs.py:35-53` (_SCAN_DIRS, _collect_markdown_files)
- Modify: `science-tool/src/science_tool/distill/__init__.py:14` (DEFAULT_SNAPSHOT_DIR)

The pattern: keep the hardcoded defaults (they're still correct for standard projects and for CLI `--path` defaults), but update the functions that scan directories to accept resolved paths instead of hardcoded names.

**Step 1: Update `_build_input_manifest` in store.py**

Currently hardcodes `include_dirs` and `include_files`. Change to accept optional `ProjectPaths`, falling back to current behavior:

```python
# In store.py, update _build_input_manifest (around line 1983)
def _build_input_manifest(graph_path: Path) -> dict[str, dict[str, int | str]]:
    project_root = _project_root_from_graph_path(graph_path)

    # Try to resolve from science.yaml; fall back to hardcoded defaults
    try:
        from science_tool.paths import resolve_paths
        pp = resolve_paths(project_root)
        include_dirs = [
            pp.doc_dir, pp.specs_dir, pp.papers_dir / "summaries",
            pp.data_dir, pp.code_dir,
        ]
        # Also include notes/ if it exists (not in paths, always at root)
        notes_dir = project_root / "notes"
        if notes_dir.is_dir():
            include_dirs.append(notes_dir)
    except Exception:
        include_dirs_str = ("doc", "specs", "notes", "papers/summaries", "data", "code")
        include_dirs = [project_root / d for d in include_dirs_str]

    include_files = ("RESEARCH_PLAN.md", "science.yaml", "CLAUDE.md", "AGENTS.md")

    files: set[Path] = set()
    for file_name in include_files:
        candidate = project_root / file_name
        if candidate.is_file():
            files.add(candidate)

    for dir_path in include_dirs:
        if dir_path.is_dir():
            ...  # existing glob logic, but use dir_path directly instead of project_root / dir_name
```

**Step 2: Update `_collect_markdown_files` in refs.py**

```python
# In refs.py, update _collect_markdown_files
def _collect_markdown_files(root: Path) -> list[Path]:
    """Collect all markdown files to scan."""
    try:
        from science_tool.paths import resolve_paths
        pp = resolve_paths(root)
        scan_dirs = [pp.doc_dir, pp.specs_dir]
    except Exception:
        scan_dirs = [root / d for d in ("doc", "specs")]

    files: list[Path] = []
    for d in scan_dirs:
        if d.is_dir():
            for p in d.rglob("*.md"):
                if not any(part in _SKIP_DIRS for part in p.parts):
                    files.append(p)
    for scan_file in _SCAN_FILES:
        f = root / scan_file
        if f.is_file():
            files.append(f)
    return files
```

**Step 3: Run existing tests to verify nothing breaks**

Run: `cd /mnt/ssd/Dropbox/science && uv run --frozen pytest science-tool/tests/ -v`
Expected: all existing tests PASS

**Step 4: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/refs.py
git commit -m "feat: use resolve_paths for directory scanning in store and refs"
```

---

### Task 4: Wire path resolution into CLI defaults

**Files:**
- Modify: `science-tool/src/science_tool/cli.py:66` and similar lines (DEFAULT_GRAPH_PATH usage)
- Modify: `science-tool/src/science_tool/cli.py:1071` (DEFAULT_TASKS_DIR)

The CLI already accepts `--path` flags for graph and task operations. The change: make the *default value* resolve from `science.yaml` when available, so users of imported projects don't need to pass `--path` every time.

**Step 1: Add a lazy default helper**

At the top of cli.py, add a helper that resolves paths from science.yaml at runtime:

```python
def _default_graph_path() -> str:
    """Resolve graph path from science.yaml, falling back to hardcoded default."""
    try:
        from science_tool.paths import resolve_paths
        pp = resolve_paths(Path.cwd())
        return str(pp.knowledge_dir / "graph.trig")
    except Exception:
        return str(DEFAULT_GRAPH_PATH)

def _default_tasks_dir() -> str:
    """Resolve tasks dir from science.yaml, falling back to hardcoded default."""
    try:
        from science_tool.paths import resolve_paths
        pp = resolve_paths(Path.cwd())
        return str(pp.tasks_dir)
    except Exception:
        return str(DEFAULT_TASKS_DIR)
```

Note: Click `default=` with a callable requires using `click.option(..., default=None)` and resolving in the function body, OR using a sentinel. The simplest approach: keep the existing defaults, but add a note in the `--help` text that science.yaml paths are respected. The actual commands already accept `--path` so the preamble can instruct Claude to pass the right path. **Defer this task to avoid over-engineering** — the command preamble (Task 6) handles this for Claude, and human users can use `--path`.

**Step 1 (revised): Skip CLI default wiring for now**

The preamble change (Task 6) will instruct Claude to read science.yaml and pass appropriate `--path` flags. This avoids complex Click plumbing for a marginal benefit.

**Step 2: Commit — nothing to commit, this task is deferred**

---

### Task 5: Update validate.sh to read path mappings

**Files:**
- Modify: `scripts/validate.sh`

**Step 1: Add path resolution function at the top of validate.sh (after line 32)**

```bash
# ─── Path resolution from science.yaml ─────────────────────────────
# Read paths: section if present, otherwise use defaults
DOC_DIR="doc"
CODE_DIR="code"
DATA_DIR="data"
SPECS_DIR="specs"
PAPERS_DIR="papers"
KNOWLEDGE_DIR="knowledge"
TASKS_DIR="tasks"
MODELS_DIR="models"

if [ -f "science.yaml" ] && command -v python3 &>/dev/null; then
    _resolve_path() {
        python3 -c "
import yaml, sys
with open('science.yaml') as f:
    d = yaml.safe_load(f) or {}
p = (d.get('paths') or {}).get('$1', '$2')
print(p.rstrip('/'))
" 2>/dev/null || echo "$2"
    }
    DOC_DIR=$(_resolve_path doc_dir doc)
    CODE_DIR=$(_resolve_path code_dir code)
    DATA_DIR=$(_resolve_path data_dir data)
    SPECS_DIR=$(_resolve_path specs_dir specs)
    PAPERS_DIR=$(_resolve_path papers_dir papers)
    KNOWLEDGE_DIR=$(_resolve_path knowledge_dir knowledge)
    TASKS_DIR=$(_resolve_path tasks_dir tasks)
    MODELS_DIR=$(_resolve_path models_dir models)
fi
```

**Step 2: Replace all hardcoded paths with variables**

Key replacements throughout validate.sh:

| Hardcoded | Variable |
|---|---|
| `"specs"`, `"doc"`, `"papers"`, `"data"`, `"code"` in the `for dir in` loop (line 59) | `"$SPECS_DIR"`, `"$DOC_DIR"`, `"$PAPERS_DIR"`, `"$DATA_DIR"`, `"$CODE_DIR"` |
| `"specs/research-question.md"` (line 79) | `"$SPECS_DIR/research-question.md"` |
| `"doc/background"` (line 87) | `"$DOC_DIR/background"` |
| `"specs/hypotheses"` (line 104) | `"$SPECS_DIR/hypotheses"` |
| `"papers/references.bib"` (line 130) | `"$PAPERS_DIR/references.bib"` |
| `"doc"` in grep/citation checks (lines 133-134, 154, 184-188) | `"$DOC_DIR"` |
| `"papers/summaries"` (lines 137-138, 164, 194-198) | `"$PAPERS_DIR/summaries"` |
| `"doc/10-research-gaps.md"` (line 217) | `"$DOC_DIR/10-research-gaps.md"` |
| `"doc/discussions"` (line 261) | `"$DOC_DIR/discussions"` |
| `"knowledge/graph.trig"` (lines 370, 386, 410, 436) | `"$KNOWLEDGE_DIR/graph.trig"` |
| `"tasks/active.md"` (line 486) | `"$TASKS_DIR/active.md"` |

**Step 3: Test with a standard project (no paths: section)**

Run: `cd /path/to/existing-science-project && bash validate.sh --verbose`
Expected: identical behavior to before (all defaults apply)

**Step 4: Test with mapped paths**

Create a temp project with `paths:` in science.yaml and verify validate.sh checks the right directories.

**Step 5: Commit**

```bash
git add scripts/validate.sh
git commit -m "feat: validate.sh reads path mappings from science.yaml"
```

---

### Task 6: Update command preamble for path awareness

**Files:**
- Modify: `references/command-preamble.md`

**Step 1: Add path resolution step**

Update the preamble from:

```markdown
1. Load role prompt: `prompts/roles/<role>.md` if present, else `${CLAUDE_PLUGIN_ROOT}/references/role-prompts/<role>.md`.
2. Load the `research-methodology` and `scientific-writing` skills.
3. Read `specs/research-question.md` for project context.
```

To:

```markdown
1. **Resolve project paths:** Read `science.yaml`. If it has a `paths:` section, use mapped directories throughout this command instead of defaults. Common mappings:
   - `doc_dir` → where research docs live (default: `doc/`)
   - `code_dir` → where code lives (default: `code/`)
   - `specs_dir` → where specs live (default: `specs/`)
   - `papers_dir` → where papers/references live (default: `papers/`)
   - `knowledge_dir` → where graph.trig lives (default: `knowledge/`)
   - `tasks_dir` → where task queue lives (default: `tasks/`)
   - `models_dir` → where models live (default: `models/`)
   - `prompts_dir` → where role prompts live (default: `prompts/`)
   If no `paths:` section exists, use the standard Science directory names.
2. Load role prompt: `<prompts_dir>/roles/<role>.md` if present, else `${CLAUDE_PLUGIN_ROOT}/references/role-prompts/<role>.md`.
3. Load the `research-methodology` and `scientific-writing` skills.
4. Read `<specs_dir>/research-question.md` for project context.
```

**Step 2: Commit**

```bash
git add references/command-preamble.md
git commit -m "feat: command preamble resolves paths from science.yaml"
```

---

### Task 7: Update project-structure.md for imported projects

**Files:**
- Modify: `references/project-structure.md`

**Step 1: Add imported projects section**

Add at the end of the file:

```markdown
## Imported Projects

Projects initialized with `/science:import-project` may have non-standard directory layouts.
Check `science.yaml` for a `paths:` section that maps Science conventions to existing directories.

For example, a project with `paths: { doc_dir: docs/, code_dir: src/ }` stores research
documents in `docs/` instead of `doc/` and code in `src/` instead of `code/`.

All Science commands, `validate.sh`, and `science-tool` respect these mappings.
When a `paths:` key is absent, the standard Science default applies.

See `references/science-yaml-schema.md` for the full list of mappable paths.
```

**Step 2: Commit**

```bash
git add references/project-structure.md
git commit -m "docs: document imported project path mappings"
```

---

### Task 8: Add cross-reference in create-project.md

**Files:**
- Modify: `commands/create-project.md:1-3` (frontmatter/description area)

**Step 1: Add a note at the top of Step 0**

After the existing Step 0 content (line 14), add:

```markdown
> **Note:** If the user has an existing project they want to adopt Science for,
> use `/science:import-project` instead. `create-project` is for brand-new projects only.
```

**Step 2: Commit**

```bash
git add commands/create-project.md
git commit -m "docs: cross-reference import-project from create-project"
```

---

### Task 9: Create the import-project command

**Files:**
- Create: `commands/import-project.md`

**Step 1: Write the command**

```markdown
---
description: Add Science research framework to an existing project. Use when the user has a pre-existing codebase, documentation, or research project and wants to adopt Science conventions without restructuring. Triggered by "import project", "adopt science", "add science to existing project", or similar.
---

# Import an Existing Project into Science

You are adding Science research infrastructure to an existing project. The key principle:
**additive only** — never overwrite, rename, or restructure existing files.

## Step 0: Pre-flight Checks

1. Confirm you are inside an existing project root (look for `.git/`, `package.json`,
   `pyproject.toml`, `Cargo.toml`, `go.mod`, or similar project markers).
2. If `science.yaml` already exists, this project has already been imported. Ask the user
   if they want to re-run import (which will fill in any missing pieces) or cancel.
3. Read the project's existing `CLAUDE.md` and `AGENTS.md` if they exist — you will
   extend these, not replace them.

## Step 1: Discover Existing Structure

Scan the project directory and identify existing equivalents for Science conventions:

| Science convention | Look for |
|---|---|
| `doc/` | `docs/`, `documentation/`, `doc/` |
| `code/` | `src/`, `lib/`, `app/`, `code/` |
| `data/` | `data/`, `datasets/` |
| `models/` | `models/`, `src/models/` |
| `papers/` | `papers/`, `references/`, `bibliography/` |
| `CLAUDE.md` | `CLAUDE.md` |
| `AGENTS.md` | `AGENTS.md` |
| `.bib` files | any `*.bib` file |

Present your findings to the user:

```
Found existing project structure:
  docs/          → will map as doc_dir
  src/           → will map as code_dir
  CLAUDE.md      → will extend (not replace)

No equivalent found for:
  papers/        → will create
  specs/         → will create
  data/          → will create (or skip if not needed)
```

Ask the user to confirm or adjust the mappings.

## Step 2: Gather Research Context

Have an interactive conversation to understand:

1. **Research question** — what is this project investigating or building?
2. **Brief summary** — 2-3 sentences describing the project
3. **Tags** — keywords for categorization
4. **Status** — likely `active` (since it's an existing project being worked on)

If the project has existing documentation (README, planning docs, design docs), read them
first and propose a research question based on what you find. Let the user refine it.

Don't ask all questions at once — have a natural conversation.

## Step 3: Create Science Infrastructure

### `science.yaml`

Create with the `paths:` section reflecting discovered mappings. Only include non-default
mappings — if a key would map to the Science default, omit it.

```yaml
name: "<project-name>"
created: "<original project creation date if known, else today>"
last_modified: "<today YYYY-MM-DD>"
summary: "<from conversation>"
status: "active"
tags:
  - "<tag1>"
  - "<tag2>"
data_sources: []
paths:
  doc_dir: "<mapped dir, e.g. docs/>"
  code_dir: "<mapped dir, e.g. src/>"
  # Only list non-default mappings
```

For the schema, see `${CLAUDE_PLUGIN_ROOT}/references/science-yaml-schema.md`.

### Create missing directories

Create these Science-specific directories (they won't have existing equivalents):

```bash
mkdir -p specs/hypotheses
mkdir -p papers/pdfs
mkdir -p knowledge
mkdir -p prompts/roles
mkdir -p templates
mkdir -p tasks
```

Skip any that already exist. Add `.gitkeep` to empty directories.

### Create subdirectories in the mapped doc dir

The mapped doc directory needs Science-standard subdirectories for research artifacts.
Create them inside the mapped `doc_dir`:

```bash
# Using the mapped doc_dir (e.g., docs/)
mkdir -p <doc_dir>/topics
mkdir -p <doc_dir>/papers
mkdir -p <doc_dir>/questions
mkdir -p <doc_dir>/methods
mkdir -p <doc_dir>/datasets
mkdir -p <doc_dir>/searches
mkdir -p <doc_dir>/discussions
mkdir -p <doc_dir>/interpretations
mkdir -p <doc_dir>/meta
```

Only create subdirectories that don't already exist. Add `.gitkeep` to empty ones.

### `specs/research-question.md`

Write the research question from the conversation. If the project has existing planning
or design documents, reference them and synthesize the question from those.

### `specs/scope-boundaries.md`

Write scope boundaries based on the conversation and any existing project documentation.

### `papers/references.bib`

If the project already has a `.bib` file, map to it in `science.yaml` paths (or symlink).
Otherwise create a new one:

```bibtex
% references.bib — BibTeX database for this Science project
% Add entries here for every paper cited in docs.
% Use keys in the format: FirstAuthorLastNameYear (e.g., Smith2024)
```

### `RESEARCH_PLAN.md`

Create based on the project's current state. If existing planning docs exist, synthesize
them into the Science format:

```markdown
# Research Plan

> High-level research strategy and direction for this project.
> For the operational task queue, see `tasks/active.md`.

## Research Direction

<synthesized from existing docs and conversation>

## Current State

<what has been accomplished so far>

## Long-Term Goals

<from conversation and existing docs>
```

### `tasks/active.md`

```markdown
<!-- Task queue. Use /science:tasks to manage. -->
```

### `validate.sh`

Copy from plugin:

```bash
cp ${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh ./validate.sh
chmod +x validate.sh
```

### `templates/`

Copy all templates from `${CLAUDE_PLUGIN_ROOT}/templates/`:

```bash
mkdir -p ./templates
cp -R ${CLAUDE_PLUGIN_ROOT}/templates/* ./templates/
```

### `prompts/roles/`

Copy role prompts from `${CLAUDE_PLUGIN_ROOT}/references/role-prompts/`:

```bash
mkdir -p ./prompts/roles
cp ${CLAUDE_PLUGIN_ROOT}/references/role-prompts/*.md ./prompts/roles/
```

### Extend `CLAUDE.md`

If `CLAUDE.md` exists, **append** a Science section. If it doesn't exist, create one
from `${CLAUDE_PLUGIN_ROOT}/references/claude-md-template.md`.

When appending, add:

```markdown

## Science Project

This project uses the Science research framework.
See `science.yaml` for project manifest and path mappings.

### Automatic Skill Triggers

Before performing any of the following tasks, read the corresponding skill:

- **Writing any document in `<doc_dir>/` or `specs/`:** Read the `scientific-writing` skill
- **Literature review, source evaluation, paper summarization:** Read the `research-methodology` skill
- **Knowledge graph work:** Read the `knowledge-graph` skill (when available)

### Role Prompt Packs

- `prompts/roles/research-assistant.md` for research/synthesis/prioritization tasks
- `prompts/roles/discussant.md` for critical discussion tasks

### Document Conventions

- Use templates from `templates/` for all new research documents
- Run `bash validate.sh` before committing research artifacts
- Every factual claim needs a citation; use BibTeX keys `[@AuthorYear]`
- Mark unverified facts with `[UNVERIFIED]` and unsourced claims with `[NEEDS CITATION]`

### Path Mappings

<list the active mappings, e.g.:>
- Research docs: `docs/` (Science default: `doc/`)
- Code: `src/` (Science default: `code/`)
- Specs: `specs/` (Science default)
- Papers: `papers/` (Science default)
```

### Extend `AGENTS.md`

If `AGENTS.md` exists, **append** a Science section. If it doesn't exist, create a
skeleton (same format as `create-project` Step 3).

When appending, add:

```markdown

## Science Conventions

### Validation

Run structural checks before committing research artifacts:

    bash validate.sh
    bash validate.sh --verbose

### Commit Messages for Research Artifacts

Use format: `<scope>: <description>` for research commits:
- `doc: add background on topic-x`
- `hypothesis: add H01`
- `papers: summarize Smith2024`
- `specs: refine research question`

### Citations

Use BibTeX keys `[@AuthorYear]` inline. All entries go in `papers/references.bib`.

### Markers

- `[UNVERIFIED]` for unverified facts
- `[NEEDS CITATION]` for unsourced claims

### Task Management

Tasks tracked in `tasks/active.md`. Manage via `/science:tasks`.
```

## Step 4: Update .gitignore (if needed)

Check the existing `.gitignore` and add Science-specific entries if missing:

```gitignore
# Science project
papers/pdfs/
.env
```

Do NOT add entries that conflict with existing gitignore rules or the project's needs.

## Step 5: Verify

Run validation:

```bash
bash validate.sh --verbose
```

It should pass. Warnings are acceptable (empty hypothesis directory, etc.). If there are
errors due to path mapping issues, fix the mappings in `science.yaml` and re-run.

## Step 6: Summarize

Tell the user what was created, what was mapped, and suggest next steps:

1. Review the generated `specs/research-question.md` and refine it
2. Add initial hypotheses with `/science:add-hypothesis`
3. Explore background with `/science:research-topic`
4. Review existing docs for papers to add to `papers/references.bib`
5. Run `/science:next-steps` to prioritize work

**Important:** Do NOT create a git commit automatically. The user may want to review the
changes first, especially since this modifies an existing project. Ask if they'd like to
commit.
```

**Step 2: Commit**

```bash
git add commands/import-project.md
git commit -m "feat: add import-project command for existing projects"
```

---

### Task 10: Update claude-md-template.md for path awareness

**Files:**
- Modify: `references/claude-md-template.md`

**Step 1: Add a note about path mappings**

After the "Project State Files" section (line 70), add:

```markdown
## Path Mappings (Imported Projects)

If this project was imported with `/science:import-project`, check `science.yaml` for
a `paths:` section. Use mapped directories instead of Science defaults:
- `doc_dir` for research documents (default: `doc/`)
- `code_dir` for code (default: `code/`)
- `specs_dir` for specs (default: `specs/`)
- etc.

If no `paths:` section exists, use standard Science directory names.
```

**Step 2: Commit**

```bash
git add references/claude-md-template.md
git commit -m "docs: add path mappings guidance to CLAUDE.md template"
```

---

### Task 11: End-to-end test on natural-systems-guide

This is a manual integration test. Run the import-project command on the actual target project.

**Step 1: Navigate to the project**

```bash
cd ~/d/mindful/natural-systems-guide
```

**Step 2: Invoke the command**

Run `/science:import-project` and walk through the interactive flow.

**Step 3: Verify**

- `science.yaml` exists with correct path mappings
- `validate.sh --verbose` passes
- Existing files (CLAUDE.md, AGENTS.md, docs/, src/) are unchanged except for appended sections
- Science-specific directories created (specs/, papers/, knowledge/, tasks/, templates/, prompts/)
- `specs/research-question.md` reflects the project's actual research question

**Step 4: Commit the import in the target project**

```bash
git add -A
git commit -m "feat: adopt Science research framework"
```

---

## Summary

| Task | Type | Description |
|---|---|---|
| 1 | docs | Add `paths` to science.yaml schema |
| 2 | code+test | `resolve_paths()` utility |
| 3 | code | Wire into store.py and refs.py |
| 4 | ~~code~~ | ~~CLI defaults~~ (deferred — preamble handles it) |
| 5 | script | validate.sh path resolution |
| 6 | docs | Command preamble path awareness |
| 7 | docs | Project structure imported projects section |
| 8 | docs | Cross-reference in create-project |
| 9 | command | The `import-project.md` command itself |
| 10 | docs | CLAUDE.md template path awareness |
| 11 | manual | End-to-end test on natural-systems-guide |
