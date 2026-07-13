# Git-Sourced Science Dependency and Worktree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Science-managed projects consume the toolkit from a Git-pinned uv source so nested `.worktrees/` checkouts run the full toolchain without sandbox exceptions or relative-path failures.

**Architecture:** The toolkit publishes a versioned CLI and agent-command compatibility floor, while a shared structural inspector classifies each consumer's `science` dependency as Git-sourced, same-repository path-sourced, missing, or externally path-sourced. Scaffolding writes the canonical public Git source, generated Codex skills embed the executable compatibility gate, and a local-Git integration fixture proves uv rewrites nested in-package path sources to the same commit. After the toolkit commit is validated and published to `origin/main`, registered consumers are converted and validated one repository at a time.

**Tech Stack:** Python 3.11+, Click, uv, TOML via `tomllib`, pytest, Git, Markdown command/skill generation

## Global Constraints

- Canonical external source: `science = { git = "https://github.com/khughitt/science.git", subdirectory = "science" }`.
- The consumer's tracked `uv.lock`, not `pyproject.toml`, owns the exact Science commit pin.
- The package and Claude plugin release versions become `0.3.0` and remain equal; the command-preamble floor begins at `0.3.0` and must never exceed the package version.
- Root version output is exactly `science <version>`; the compatibility probe remains a root `--version` option, never a new subcommand.
- Only the exact pre-baseline Click diagnostic `Error: No such option: --version` is converted to an upgrade diagnosis. Every unrelated uv, lock, Git, import, or runtime error passes through verbatim.
- Successful version strings accept numeric `major.minor.patch` prefixes plus release-candidate, development, and local suffixes.
- Git fetch failures are reported directly. Do not fall back to a local checkout, alternate revision, shared environment, `UV_PROJECT`, or sibling worktree.
- Deliberate local toolkit development uses `uv run --with-editable ~/d/science/science <command>` without changing the consumer manifest or lock.
- `meta/` retains its same-repository editable path source. `science-commons` remains excluded because it has no root `pyproject.toml` and is not an ordinary consumer.
- Do not add an update helper, compatibility layer, or migration guide.
- Keep the managed `validate.sh` body unchanged: `exec uv run science validate "$@"`.
- Preserve unrelated worktree changes, especially `meta/knowledge/graph.trig`, and never stage them with toolkit commits.
- Toolkit package commands run from `science/`; documentation and generator commands run from the repository root.

---

### Task 1: Establish the 0.3.0 CLI and plugin release contract

**Files:**
- Create: `science/tests/test_cli_version.py`
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/pyproject.toml`
- Modify: `science/uv.lock`
- Modify: `.claude-plugin/plugin.json`

**Interfaces:**
- Produces: root option `science --version` with stdout `science 0.3.0\n` and exit code 0.
- Produces: package and plugin version strings that are both exactly `0.3.0`.
- Consumes: Click's installed-package metadata lookup for package name `science`.

- [ ] **Step 1: Write the failing root-version and release-surface tests**

Create `science/tests/test_cli_version.py`:

```python
from __future__ import annotations

import json
import tomllib
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


ROOT = Path(__file__).resolve().parents[2]


def test_root_version_option_has_stable_output() -> None:
    result = CliRunner().invoke(main, ["--version"])

    assert result.exit_code == 0
    assert result.output == "science 0.3.0\n"


def test_package_and_plugin_establish_0_3_0_baseline() -> None:
    package = tomllib.loads((ROOT / "science" / "pyproject.toml").read_text(encoding="utf-8"))
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))

    assert package["project"]["version"] == "0.3.0"
    assert plugin["version"] == package["project"]["version"]
```

- [ ] **Step 2: Run the tests and confirm the current release surfaces fail**

Run:

```bash
cd science && uv run --frozen pytest tests/test_cli_version.py -q
```

Expected: FAIL because `--version` is not defined, the package is `0.2.0`, and the plugin is `0.1.0`.

- [ ] **Step 3: Add the stable root option and bump both release surfaces**

Add this decorator to `main` in `science/src/science_tool/cli.py`, between `@click.group(...)` and the existing `@click.option("--color", ...)`:

```python
@click.version_option(
    package_name="science",
    prog_name="science",
    message="%(prog)s %(version)s",
)
```

Change the package version in `science/pyproject.toml`:

```toml
[project]
name = "science"
version = "0.3.0"
```

Change the plugin version in `.claude-plugin/plugin.json`:

```json
{
  "name": "science",
  "version": "0.3.0",
  "description": "Science — an AI research assistant for hypothesis development, literature review, and reproducible computational pipelines. Named after the lab rat from Adventure Time.",
  "author": {
    "name": "Keith Hughitt"
  },
  "license": "MIT"
}
```

Refresh the lock metadata from `science/`:

```bash
uv lock
```

- [ ] **Step 4: Run the focused tests and direct CLI probe**

Run:

```bash
cd science && uv run --frozen pytest tests/test_cli_version.py -q
cd science && uv run --frozen science --version
```

Expected: 2 tests pass, followed by exactly `science 0.3.0`.

- [ ] **Step 5: Commit the release contract**

```bash
git add science/tests/test_cli_version.py science/src/science_tool/cli.py science/pyproject.toml science/uv.lock .claude-plugin/plugin.json
git commit -m "feat: establish Science CLI compatibility baseline"
```

---

### Task 2: Make the plugin-to-CLI compatibility contract executable

**Files:**
- Create: `science/tests/test_agent_cli_compatibility.py`
- Modify: `references/command-preamble.md`
- Modify: `commands/annotate-paper.md`
- Modify: `commands/big-picture.md`
- Modify: `commands/curate.md`
- Modify: `commands/health.md`
- Modify: `commands/review-tasks.md`
- Modify: `commands/synthesize-propositions.md`
- Modify: `commands/tasks.md`
- Modify: `commands/wander.md`

**Interfaces:**
- Consumes: `science --version` from Task 1.
- Produces: `SCIENCE_REQUIRED_VERSION=0.3.0` compatibility block in the authoritative preamble.
- Produces: deterministic failure copy with `uv lock --upgrade-package science && uv sync --frozen` only for old, malformed, or below-floor CLI versions.
- Produces: command-tree contract requiring each literal `uv run science <top-level-command>` in `commands/*.md` to exist in `science_tool.cli.main.commands`.

- [ ] **Step 1: Write the failing executable compatibility and command-contract tests**

Create `science/tests/test_agent_cli_compatibility.py`:

```python
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

import pytest

from science_tool.cli import main


ROOT = Path(__file__).resolve().parents[2]
PREAMBLE = ROOT / "references" / "command-preamble.md"
COMMAND_RE = re.compile(r"\buv run(?: --frozen)? science ([a-z][a-z0-9-]*)")
FLOOR_RE = re.compile(r"^\s*SCIENCE_REQUIRED_VERSION=(\d+\.\d+\.\d+)$", re.MULTILINE)


def _release(value: str) -> tuple[int, int, int]:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", value)
    assert match is not None, value
    return tuple(map(int, match.groups()))


def _compatibility_block() -> str:
    text = PREAMBLE.read_text(encoding="utf-8")
    marker = "SCIENCE_REQUIRED_VERSION=0.3.0"
    marker_at = text.index(marker)
    start = text.rindex("```bash\n", 0, marker_at) + len("```bash\n")
    end = text.index("\n```", marker_at)
    return textwrap.dedent(text[start:end]) + "\n"


def _fake_uv(tmp_path: Path) -> Path:
    executable = tmp_path / "bin" / "uv"
    executable.parent.mkdir()
    executable.write_text(
        """#!/usr/bin/env bash
set -u
if [ "$*" = "run --frozen science --version" ]; then
  printf '%s\\n' "$SCIENCE_TEST_PROBE_OUTPUT"
  exit "$SCIENCE_TEST_PROBE_EXIT"
fi
if [ "$*" = "run --no-project python -" ]; then
  exec "$SCIENCE_TEST_PYTHON" -
fi
printf 'unexpected fake uv invocation: %s\\n' "$*" >&2
exit 99
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _run_gate(tmp_path: Path, *, output: str, exit_code: int) -> subprocess.CompletedProcess[str]:
    fake_uv = _fake_uv(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_uv.parent}{os.pathsep}{env['PATH']}",
            "SCIENCE_TEST_PROBE_OUTPUT": output,
            "SCIENCE_TEST_PROBE_EXIT": str(exit_code),
            "SCIENCE_TEST_PYTHON": sys.executable,
        }
    )
    return subprocess.run(
        ["bash"],
        input=_compatibility_block(),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def test_prebaseline_click_failure_becomes_upgrade_message(tmp_path: Path) -> None:
    result = _run_gate(
        tmp_path,
        output="Usage: science [OPTIONS] COMMAND [ARGS]...\nError: No such option: --version",
        exit_code=2,
    )

    assert result.returncode == 1
    assert "requires science >=0.3.0" in result.stderr
    assert "unknown-or-pre-0.3.0" in result.stderr
    assert "No such option" not in result.stderr


def test_uv_environment_failure_passes_through_verbatim(tmp_path: Path) -> None:
    message = "error: Unable to find lockfile at `uv.lock`, but `--frozen` was provided."
    result = _run_gate(tmp_path, output=message, exit_code=2)

    assert result.returncode == 1
    assert result.stderr == message + "\n"
    assert "upgrade-package" not in result.stderr


@pytest.mark.parametrize("output", ["science malformed", "science 0.2.0"])
def test_malformed_or_below_floor_version_is_blocked(tmp_path: Path, output: str) -> None:
    result = _run_gate(tmp_path, output=output, exit_code=0)

    assert result.returncode == 1
    assert "requires science >=0.3.0" in result.stderr
    assert "upgrade-package science" in result.stderr


@pytest.mark.parametrize(
    "version",
    ["0.3.0", "0.3.1rc1", "0.3.0.dev1", "0.3.0+g8bf7829", "0.4.0", "1.0.0"],
)
def test_floor_and_newer_suffixed_versions_pass(tmp_path: Path, version: str) -> None:
    result = _run_gate(tmp_path, output=f"science {version}", exit_code=0)

    assert result.returncode == 0
    assert result.stderr == ""


def test_release_versions_and_command_floor_obey_contract() -> None:
    package = tomllib.loads((ROOT / "science" / "pyproject.toml").read_text(encoding="utf-8"))
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    floor_match = FLOOR_RE.search(PREAMBLE.read_text(encoding="utf-8"))
    assert floor_match is not None

    package_version = package["project"]["version"]
    assert plugin["version"] == package_version
    assert _release(floor_match.group(1)) <= _release(package_version)


def test_commands_that_invoke_cli_load_the_shared_preamble() -> None:
    missing: list[str] = []
    for path in sorted((ROOT / "commands").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if COMMAND_RE.search(text) and "references/command-preamble.md" not in text:
            missing.append(path.relative_to(ROOT).as_posix())

    assert missing == []


def test_documented_top_level_commands_exist_in_current_cli() -> None:
    referenced: set[str] = set()
    for path in sorted((ROOT / "commands").glob("*.md")):
        referenced.update(COMMAND_RE.findall(path.read_text(encoding="utf-8")))

    assert referenced <= set(main.commands)
```

- [ ] **Step 2: Run the tests and confirm the missing gate and command declarations fail**

Run:

```bash
cd science && uv run --frozen pytest tests/test_agent_cli_compatibility.py -q
```

Expected: FAIL because the preamble has no `SCIENCE_REQUIRED_VERSION`, and eight CLI-invoking command files do not name the shared preamble.

- [ ] **Step 3: Replace command-preamble step 8 with the executable gate**

In `references/command-preamble.md`, replace the current editable-path, main-environment, and fallback instructions in step 8 with the short instruction below, then add the top-level compatibility section after the numbered preamble. Keeping the fenced block top-level is required so its heredoc delimiters remain column-aligned when an agent executes it:

````markdown
8. **Verify the project-local Science CLI:** Execute the top-level CLI
   Compatibility Gate below before the command's first Science invocation. It
   uses the consumer's frozen lock; do not route through a toolkit checkout or
   another environment.

## CLI Compatibility Gate

```bash
SCIENCE_REQUIRED_VERSION=0.3.0
if output=$(uv run --frozen science --version 2>&1); then
  SCIENCE_INSTALLED_VERSION=${output##* }
elif printf '%s\n' "$output" | grep -Fq 'Error: No such option: --version'; then
  SCIENCE_INSTALLED_VERSION=
else
  printf '%s\n' "$output" >&2
  exit 1
fi

if ! SCIENCE_INSTALLED_VERSION="$SCIENCE_INSTALLED_VERSION" \
     SCIENCE_REQUIRED_VERSION="$SCIENCE_REQUIRED_VERSION" \
     uv run --no-project python - <<'PY'
import os
import re
import sys

def release(name: str) -> tuple[int, int, int] | None:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", name)
    return tuple(map(int, match.groups())) if match else None

installed = release(os.environ["SCIENCE_INSTALLED_VERSION"])
required = release(os.environ["SCIENCE_REQUIRED_VERSION"])
sys.exit(0 if installed is not None and required is not None and installed >= required else 1)
PY
then
  display=${SCIENCE_INSTALLED_VERSION:-unknown-or-pre-0.3.0}
  echo "This Science agent command requires science >=$SCIENCE_REQUIRED_VERSION; found $display." >&2
  echo "upgrade with: uv lock --upgrade-package science && uv sync --frozen" >&2
  exit 1
fi
```

A recognized pre-`0.3.0` Click response, malformed successful output, or a
version below the floor stops with the upgrade command. Any other failure is
printed verbatim and must be fixed as reported. The root `--version` probe is
the permanent bootstrap surface; do not replace it with a preflight subcommand.
````

- [ ] **Step 4: Make every CLI-invoking command load the authoritative preamble**

Add this sentence immediately after the top-level introduction or before the first workflow/setup section in each of the eight files listed for this task:

```markdown
Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` before executing this command.
```

Where `commands/curate.md` currently says “Follow the standard Science command preamble,” replace that sentence with the exact path-bearing sentence rather than adding a duplicate.

- [ ] **Step 5: Run the executable contract tests**

Run:

```bash
cd science && uv run --frozen pytest tests/test_agent_cli_compatibility.py -q
```

Expected: all compatibility and command-contract tests pass. The executable tests parse and run the exact fenced block, which subsumes a syntax-only `bash -n` check.

- [ ] **Step 6: Commit the compatibility gate**

```bash
git add science/tests/test_agent_cli_compatibility.py references/command-preamble.md commands/annotate-paper.md commands/big-picture.md commands/curate.md commands/health.md commands/review-tasks.md commands/synthesize-propositions.md commands/tasks.md commands/wander.md
git commit -m "feat: enforce agent CLI compatibility floor"
```

---

### Task 3: Classify Science dependency sources structurally

**Files:**
- Create: `science/src/science_tool/tooling_dependency.py`
- Create: `science/tests/test_tooling_dependency.py`
- Modify: `science/src/science_tool/graph/health_checks/tooling_scaffold.py`
- Modify: `science/src/science_tool/validate/checks/tooling.py`
- Modify: `science/tests/test_health_preconditions.py`
- Modify: `science/tests/test_health.py`
- Modify: `science/tests/validate/test_checks_basic.py`

**Interfaces:**
- Produces: `inspect_science_dependency(project_root: Path) -> ScienceDependency`.
- Produces: `ScienceSourceKind` values `missing`, `git`, `same-repo-path`, and `external-path`.
- Produces: `CANONICAL_SCIENCE_SOURCE`, the exact TOML fix used by health and validation diagnostics.
- Consumes: a root `pyproject.toml`; parsing errors propagate to the caller so each surface emits one parse finding and no misleading source finding.

- [ ] **Step 1: Write failing structural-inspection tests**

Create `science/tests/test_tooling_dependency.py`:

```python
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from science_tool.tooling_dependency import ScienceSourceKind, inspect_science_dependency


def _write_pyproject(project: Path, source: str, *, include_dependency: bool = True) -> None:
    project.mkdir(parents=True, exist_ok=True)
    dependency = 'dev = ["science"]' if include_dependency else "dev = []"
    project.joinpath("pyproject.toml").write_text(
        f"[project]\nname = \"fixture\"\nversion = \"0.1.0\"\n"
        f"[dependency-groups]\n{dependency}\n"
        f"[tool.uv.sources]\n{source}\n",
        encoding="utf-8",
    )


def test_git_source_is_worktree_safe(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        'science = { git = "https://github.com/khughitt/science.git", subdirectory = "science" }',
    )

    result = inspect_science_dependency(tmp_path)

    assert result.dev_dependency_present is True
    assert result.source_kind is ScienceSourceKind.GIT


def test_same_repository_path_source_is_worktree_safe(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "science").mkdir()
    project = repo / "meta"
    _write_pyproject(project, 'science = { path = "../science", editable = true }')

    result = inspect_science_dependency(project)

    assert result.source_kind is ScienceSourceKind.SAME_REPO_PATH
    assert result.resolved_path == (repo / "science").resolve()


def test_external_path_source_is_worktree_unsafe(tmp_path: Path) -> None:
    consumer_repo = tmp_path / "consumer"
    (consumer_repo / ".git").mkdir(parents=True)
    toolkit_repo = tmp_path / "toolkit"
    (toolkit_repo / ".git").mkdir(parents=True)
    (toolkit_repo / "science").mkdir()
    _write_pyproject(
        consumer_repo,
        'science = { path = "../toolkit/science", editable = true }',
    )

    result = inspect_science_dependency(consumer_repo)

    assert result.source_kind is ScienceSourceKind.EXTERNAL_PATH
    assert result.resolved_path == (toolkit_repo / "science").resolve()


def test_missing_dev_dependency_is_distinct_from_missing_source(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, "", include_dependency=False)

    result = inspect_science_dependency(tmp_path)

    assert result.dev_dependency_present is False
    assert result.source_kind is ScienceSourceKind.MISSING


def test_present_dependency_without_uv_source_reports_missing_source(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, "")

    result = inspect_science_dependency(tmp_path)

    assert result.dev_dependency_present is True
    assert result.source_kind is ScienceSourceKind.MISSING


def test_malformed_pyproject_fails_parsing(tmp_path: Path) -> None:
    tmp_path.joinpath("pyproject.toml").write_text("[project\n", encoding="utf-8")

    with pytest.raises(tomllib.TOMLDecodeError):
        inspect_science_dependency(tmp_path)
```

- [ ] **Step 2: Run the structural tests and confirm the module is missing**

Run:

```bash
cd science && uv run --frozen pytest tests/test_tooling_dependency.py -q
```

Expected: collection ERROR with `ModuleNotFoundError: science_tool.tooling_dependency`.

- [ ] **Step 3: Implement the shared structural inspector**

Create `science/src/science_tool/tooling_dependency.py`:

```python
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


CANONICAL_SCIENCE_SOURCE = (
    'science = { git = "https://github.com/khughitt/science.git", '
    'subdirectory = "science" }'
)


class ScienceSourceKind(StrEnum):
    MISSING = "missing"
    GIT = "git"
    SAME_REPO_PATH = "same-repo-path"
    EXTERNAL_PATH = "external-path"


@dataclass(frozen=True)
class ScienceDependency:
    dev_dependency_present: bool
    source_kind: ScienceSourceKind
    resolved_path: Path | None = None


def inspect_science_dependency(project_root: Path) -> ScienceDependency:
    pyproject_path = project_root / "pyproject.toml"
    with pyproject_path.open("rb") as stream:
        data = tomllib.load(stream)

    dev_group = data.get("dependency-groups", {}).get("dev", [])
    dev_dependency_present = isinstance(dev_group, list) and any(
        isinstance(entry, str) and _requirement_name(entry) == "science"
        for entry in dev_group
    )
    if not dev_dependency_present:
        return ScienceDependency(False, ScienceSourceKind.MISSING)

    source = _science_source(data)
    if not isinstance(source, dict):
        return ScienceDependency(True, ScienceSourceKind.MISSING)
    if isinstance(source.get("git"), str):
        return ScienceDependency(True, ScienceSourceKind.GIT)

    raw_path = source.get("path")
    if not isinstance(raw_path, str):
        return ScienceDependency(True, ScienceSourceKind.MISSING)

    resolved_path = (project_root / raw_path).resolve()
    project_repo = _git_worktree_root(project_root)
    source_repo = _git_worktree_root(resolved_path)
    kind = (
        ScienceSourceKind.SAME_REPO_PATH
        if project_repo is not None and project_repo == source_repo
        else ScienceSourceKind.EXTERNAL_PATH
    )
    return ScienceDependency(True, kind, resolved_path)


def _science_source(data: dict[str, Any]) -> object:
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return None
    uv = tool.get("uv")
    if not isinstance(uv, dict):
        return None
    sources = uv.get("sources")
    if not isinstance(sources, dict):
        return None
    return sources.get("science")


def _requirement_name(requirement: str) -> str:
    return re.split(r"\s*(?:\[|@|===|==|~=|!=|<=|>=|<|>)", requirement.strip(), maxsplit=1)[0]


def _git_worktree_root(path: Path) -> Path | None:
    current = path.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None
```

- [ ] **Step 4: Run the inspector tests**

Run:

```bash
cd science && uv run --frozen pytest tests/test_tooling_dependency.py -q
```

Expected: 6 tests pass.

- [ ] **Step 5: Replace health's local parser and `.env` requirements**

Update `science/src/science_tool/graph/health_checks/tooling_scaffold.py` to import the shared contract:

```python
import tomllib

from science_tool.tooling_dependency import (
    CANONICAL_SCIENCE_SOURCE,
    ScienceSourceKind,
    inspect_science_dependency,
)
```

Keep the existing `pyproject_missing` finding. For a present manifest, call `inspect_science_dependency(project_root)` and map its result exactly as follows:

```python
try:
    dependency = inspect_science_dependency(project_root)
except (OSError, tomllib.TOMLDecodeError) as exc:
    findings.append(
        {
            "code": "pyproject_unreadable",
            "detail": f"pyproject.toml could not be parsed: {exc}",
            "fix": "Repair pyproject.toml — see commands/create-project.md for canonical shape.",
        }
    )
else:
    if not dependency.dev_dependency_present:
        findings.append(
            {
                "code": "science_tool_dep_missing",
                "detail": "pyproject.toml does not list `science` under [dependency-groups].dev.",
                "fix": "Add `science` to the dev group and configure: " + CANONICAL_SCIENCE_SOURCE,
            }
        )
    elif dependency.source_kind is ScienceSourceKind.MISSING:
        findings.append(
            {
                "code": "science_source_missing",
                "detail": "The `science` dev dependency has no supported [tool.uv.sources] entry.",
                "fix": "Configure: " + CANONICAL_SCIENCE_SOURCE,
            }
        )
    elif dependency.source_kind is ScienceSourceKind.EXTERNAL_PATH:
        findings.append(
            {
                "code": "science_source_external_path",
                "detail": "The external path source for `science` is not safe from nested worktrees.",
                "fix": "Replace it with: " + CANONICAL_SCIENCE_SOURCE,
            }
        )
```

Delete all `.env` and `SCIENCE_TOOL_PATH` inspection from this check. Update its docstring and `ToolingScaffoldFinding` code comment so compliance requires only the root manifest, the dev dependency, and a Git or same-repository path source.

- [ ] **Step 6: Replace validation's text search and `.env` requirements**

Update `science/src/science_tool/validate/checks/tooling.py` to import `tomllib` plus the same shared symbols and use the structured result. Preserve the leading `pyproject.toml present` INFO result. Emit exactly one WARN for a parse failure, missing dev dependency, missing source, or external source; emit INFO for `Git source is worktree-safe` and `same-repository path source is worktree-safe`. Delete the entire `.env` branch.

The source mapping should be:

```python
if not dependency.dev_dependency_present:
    yield _result(
        Severity.WARN,
        "pyproject.toml",
        "pyproject.toml does not list science under [dependency-groups].dev "
        f"(fix: add the dependency and configure `{CANONICAL_SCIENCE_SOURCE}`)",
    )
elif dependency.source_kind is ScienceSourceKind.MISSING:
    yield _result(
        Severity.WARN,
        "pyproject.toml",
        f"science has no supported uv source (fix: `{CANONICAL_SCIENCE_SOURCE}`)",
    )
elif dependency.source_kind is ScienceSourceKind.EXTERNAL_PATH:
    yield _result(
        Severity.WARN,
        "pyproject.toml",
        "science uses an external path source that breaks in nested worktrees "
        f"(fix: `{CANONICAL_SCIENCE_SOURCE}`)",
    )
elif dependency.source_kind is ScienceSourceKind.GIT:
    yield _result(Severity.INFO, "pyproject.toml", "  science Git source is worktree-safe")
else:
    yield _result(Severity.INFO, "pyproject.toml", "  science same-repository path source is worktree-safe")
```

- [ ] **Step 7: Rewrite health and validation tests around the source contract**

In `science/tests/test_health_preconditions.py`, make the clean fixture use:

```toml
[project]
name = "t"
version = "0.0"

[dependency-groups]
dev = ["science"]

[tool.uv.sources]
science = { git = "https://github.com/khughitt/science.git", subdirectory = "science" }
```

Remove `.env` setup and change the bare-directory expectation to `{"pyproject_missing"}`. Add focused health assertions for `pyproject_unreadable`, `science_source_missing`, and `science_source_external_path`, including the canonical source in each actionable fix. Update the clean-project fixture in `science/tests/test_health.py` to use the same Git source and delete the obsolete unreadable-`.env` test.

In `science/tests/validate/test_checks_basic.py`, replace the `.env` tests with these cases:

```python
def test_tooling_accepts_git_source(tmp_path: Path) -> None:
    from science_tool.validate.checks.tooling import check_tooling

    ctx = _ctx(tmp_path)
    tmp_path.joinpath("pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n'
        '[dependency-groups]\ndev = ["science"]\n'
        '[tool.uv.sources]\n'
        'science = { git = "https://github.com/khughitt/science.git", subdirectory = "science" }\n',
        encoding="utf-8",
    )

    results = list(check_tooling(ctx))

    assert _messages(results) == [
        "pyproject.toml present",
        "  science Git source is worktree-safe",
    ]
    assert all(result.severity is Severity.INFO for result in results)


def test_tooling_reports_malformed_pyproject_once(tmp_path: Path) -> None:
    from science_tool.validate.checks.tooling import check_tooling

    ctx = _ctx(tmp_path)
    tmp_path.joinpath("pyproject.toml").write_text("[project\n", encoding="utf-8")

    results = list(check_tooling(ctx))

    warnings = [result for result in results if result.severity is Severity.WARN]
    assert len(warnings) == 1
    assert "could not be parsed" in warnings[0].message


def test_tooling_rejects_external_path_source(tmp_path: Path) -> None:
    from science_tool.validate.checks.tooling import check_tooling

    consumer = tmp_path / "consumer"
    (consumer / ".git").mkdir(parents=True)
    external = tmp_path / "external-toolkit"
    (external / ".git").mkdir(parents=True)
    (external / "science").mkdir()
    ctx = _ctx(consumer)
    consumer.joinpath("pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n'
        '[dependency-groups]\ndev = ["science"]\n'
        '[tool.uv.sources]\nscience = { path = "../external-toolkit/science", editable = true }\n',
        encoding="utf-8",
    )

    results = list(check_tooling(ctx))

    assert any(
        result.severity is Severity.WARN and "breaks in nested worktrees" in result.message
        for result in results
    )
```

- [ ] **Step 8: Run the structural, health, and validation test slices**

Run:

```bash
cd science && uv run --frozen pytest tests/test_tooling_dependency.py tests/test_health_preconditions.py tests/test_health.py tests/validate/test_checks_basic.py -q
```

Expected: all selected tests pass; malformed TOML produces one parse diagnosis, Git and same-repository sources pass, and an external path source reports the canonical fix.

- [ ] **Step 9: Commit the structural dependency checks**

```bash
git add science/src/science_tool/tooling_dependency.py science/src/science_tool/graph/health_checks/tooling_scaffold.py science/src/science_tool/validate/checks/tooling.py science/tests/test_tooling_dependency.py science/tests/test_health_preconditions.py science/tests/test_health.py science/tests/validate/test_checks_basic.py
git commit -m "feat: validate worktree-safe Science sources"
```

---

### Task 4: Change scaffolding and worktree guidance to the Git source

**Files:**
- Modify: `science/tests/test_command_docs.py`
- Modify: `commands/create-project.md`
- Modify: `commands/import-project.md`
- Modify: `references/project-structure.md`
- Modify: `references/command-preamble.md`
- Modify: `templates/agents-md.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: canonical source constant and compatibility behavior established in Tasks 2–3.
- Produces: new-project and import instructions that write `[dependency-groups].dev = ["science"]`, the canonical Git source, and a tracked `uv.lock`.
- Produces: nested `.worktrees/<name>/` as the normal consumer worktree location.

- [ ] **Step 1: Replace the bootstrap documentation assertions**

In `science/tests/test_command_docs.py`, define:

```python
SCIENCE_GIT_SOURCE = (
    'science = { git = "https://github.com/khughitt/science.git", '
    'subdirectory = "science" }'
)
RETIRED_TOOLING_GUIDANCE = (
    'uv add --dev --editable "$SCIENCE_TOOL_PATH"',
    "SCIENCE_TOOL_PATH=<absolute-path-to-science>",
    "same filesystem depth",
    "git worktree add ../<project>--<branch>",
    "UV_PROJECT=$MAIN",
    "$MAIN/.venv/bin/science",
)
```

Replace `test_project_bootstrap_docs_cover_science_tool_install_contract` with:

```python
@pytest.mark.parametrize(
    "path",
    [
        "commands/create-project.md",
        "commands/import-project.md",
        "references/project-structure.md",
    ],
)
def test_project_bootstrap_docs_use_canonical_git_source(path: str) -> None:
    text = _read(path)

    assert SCIENCE_GIT_SOURCE in text
    assert 'dev = ["science"]' in text
    assert "uv lock" in text


def test_active_tooling_docs_drop_relative_editable_workarounds() -> None:
    paths = [
        "commands/create-project.md",
        "commands/import-project.md",
        "references/project-structure.md",
        "references/command-preamble.md",
        "templates/agents-md.md",
        "AGENTS.md",
    ]

    offenders = {
        path: token
        for path in paths
        for token in RETIRED_TOOLING_GUIDANCE
        if token in _read(path)
    }
    assert offenders == {}


def test_agents_template_recommends_nested_worktrees_and_local_overlay() -> None:
    text = _read("templates/agents-md.md")

    assert ".worktrees/<name>/" in text
    assert "location-independent" in text
    assert "uv sync --frozen" in text
    assert "uv run --with-editable ~/d/science/science <command>" in text
    assert "--no-verify" not in text
```

- [ ] **Step 2: Run the doc tests and confirm they fail on editable-path guidance**

Run:

```bash
cd science && uv run --frozen pytest tests/test_command_docs.py -q
```

Expected: the new bootstrap and retired-guidance assertions fail.

- [ ] **Step 3: Update create/import/project-structure dependency instructions**

In each of `commands/create-project.md`, `commands/import-project.md`, and `references/project-structure.md`, replace the empty dev group plus `uv add --dev --editable` flow with this minimum manifest shape:

```toml
[project]
name = "<project-slug>-sciences"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[dependency-groups]
dev = ["science"]

[tool.uv.sources]
science = { git = "https://github.com/khughitt/science.git", subdirectory = "science" }
```

Immediately follow the manifest with:

```bash
uv lock
uv sync --frozen
uv run --frozen science --version
```

State that `uv.lock` must be committed because it records the selected Git SHA. Remove instructions to resolve `${CLAUDE_PLUGIN_ROOT}/science`, populate `SCIENCE_TOOL_PATH`, or create `.env` solely for Science. Preserve guidance that an existing root manifest must be extended rather than replaced, and preserve `.env` in `.gitignore` for unrelated project secrets.

- [ ] **Step 4: Rewrite the consumer Worktrees template section**

Replace the `## Worktrees` section in `templates/agents-md.md` with:

```markdown
## Worktrees

This project installs the `science` toolkit from its public Git source, with the
exact revision pinned in `uv.lock`. The dependency is location-independent, so
nested worktrees under `.worktrees/<name>/` are the preferred default and run
the same project-local toolchain as the main checkout.

After creating a worktree, initialize it from that checkout:

```bash
uv sync --frozen
uv run --frozen science --version
bash validate.sh --verbose
```

Do not route commands through the main checkout's `.venv`, rewrite the source
path, or move the worktree outside the repository. When deliberately testing
uncommitted toolkit code, overlay it for that invocation only:

```bash
uv run --with-editable ~/d/science/science <command>
```
```

- [ ] **Step 5: Mirror the new rule in the toolkit guide and simplify preamble invocation guidance**

Rewrite the consumer half of `AGENTS.md`'s Worktrees section to say that external consumers now use a Git source and therefore support nested `.worktrees/`, while this repository's `science-model`, `science-qa`, and `meta/` sources remain safe because they resolve within the same Git worktree.

In `references/command-preamble.md`, keep `uv run science <command>` as the project-local invocation after the compatibility gate. Delete the main-checkout environment, plugin-root fallback, and relative-source workaround. State that missing dependency or lock failures are surfaced directly and fixed in the consumer project.

- [ ] **Step 6: Run documentation tests and scan active surfaces**

Run:

```bash
cd science && uv run --frozen pytest tests/test_command_docs.py -q
rg -n 'SCIENCE_TOOL_PATH|uv add --dev --editable|same filesystem depth|git worktree add ../<project>--<branch>|UV_PROJECT=\$MAIN|\$MAIN/.venv/bin/science' commands references templates AGENTS.md
```

Expected: tests pass and `rg` returns no matches.

- [ ] **Step 7: Commit scaffolding and worktree guidance**

```bash
git add science/tests/test_command_docs.py commands/create-project.md commands/import-project.md references/project-structure.md references/command-preamble.md templates/agents-md.md AGENTS.md
git commit -m "docs: make nested consumer worktrees the default"
```

---

### Task 5: Regenerate Codex skills from the compatibility-aware preamble

**Files:**
- Modify: `science/tests/test_codex_skills.py`
- Regenerate: `codex-skills/INDEX.md`
- Regenerate: every tracked `codex-skills/science-*/SKILL.md`

**Interfaces:**
- Consumes: `generate_codex_skills(repo_root: Path, output_root: Path)` and the authoritative preamble from Task 2.
- Produces: committed Codex skills byte-for-byte equal to a fresh generator run.
- Produces: every generated command skill embeds `SCIENCE_REQUIRED_VERSION=0.3.0` and contains none of the retired routing workarounds.

- [ ] **Step 1: Add generated-preamble and committed-parity tests**

Append to `science/tests/test_codex_skills.py`:

```python
def test_generated_command_skills_embed_cli_compatibility_gate(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)

    for name, path in generated.items():
        if name in {"science-research-methodology", "science-scientific-writing"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert "SCIENCE_REQUIRED_VERSION=0.3.0" in text, name
        assert "uv run --frozen science --version" in text, name
        assert "UV_PROJECT=$MAIN" not in text, name
        assert "$MAIN/.venv/bin/science" not in text, name


def test_committed_codex_skills_match_fresh_generation(tmp_path: Path) -> None:
    generated_root = tmp_path / "codex-skills"
    generate_codex_skills(ROOT, generated_root)

    expected = {
        path.relative_to(generated_root): path.read_bytes()
        for path in generated_root.rglob("*")
        if path.is_file()
    }
    actual = {
        path.relative_to(CODEX_SKILLS_ROOT): path.read_bytes()
        for path in CODEX_SKILLS_ROOT.rglob("*")
        if path.is_file() and path.name != "INSTALL.codex.md"
    }

    assert actual == expected
```

- [ ] **Step 2: Run the focused tests and confirm committed skills are stale**

Run:

```bash
cd science && uv run --frozen pytest tests/test_codex_skills.py -q
```

Expected: generated temporary skills contain the gate; committed parity fails because tracked skills still contain the old preamble.

- [ ] **Step 3: Regenerate the committed skills**

Run from the repository root:

```bash
uv run --project science python scripts/generate_codex_skills.py
```

Expected: `Generated Codex skills in .../codex-skills`.

- [ ] **Step 4: Run parity and inspect the generated diff**

Run:

```bash
cd science && uv run --frozen pytest tests/test_codex_skills.py -q
git diff --stat -- codex-skills science/tests/test_codex_skills.py
git diff --check
```

Expected: all Codex-skill tests pass; generated command skills change only through the shared preamble and source-command edits; whitespace check passes.

- [ ] **Step 5: Commit generated skill parity**

```bash
git add science/tests/test_codex_skills.py codex-skills
git commit -m "build: regenerate compatibility-aware Codex skills"
```

---

### Task 6: Lock uv's nested Git-source rewrite into an integration test

**Files:**
- Create: `science/tests/test_git_source_worktree.py`

**Interfaces:**
- Consumes: local `git` and `uv`; the toolkit source itself is a local `file://` Git URL, so the regression never contacts GitHub.
- Produces: regression proof that a consumer Git source at subdirectory `science/` rewrites an editable nested `model/` source to `subdirectory=science/model` at the same commit.
- Produces: regression proof that `uv sync --frozen`, CLI execution, standard-library tests, and `validate.sh` all run from `.worktrees/feature/`.

- [ ] **Step 1: Create the local-Git integration fixture**

Create `science/tests/test_git_source_worktree.py`:

```python
from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _commit(repo: Path) -> str:
    _run("git", "init", "-q", cwd=repo)
    _run("git", "config", "user.email", "science-test@example.invalid", cwd=repo)
    _run("git", "config", "user.name", "Science Test", cwd=repo)
    _run("git", "add", ".", cwd=repo)
    _run("git", "commit", "-q", "-m", "fixture", cwd=repo)
    return _run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()


def _toolkit_repo(root: Path) -> tuple[Path, str]:
    repo = root / "toolkit"
    repo.mkdir()
    _write(
        repo / "science" / "pyproject.toml",
        """[project]
name = "science"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = ["science-model"]

[project.scripts]
science = "science.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv.sources]
science-model = { path = "model", editable = true }
""",
    )
    _write(repo / "science" / "src" / "science" / "__init__.py", "")
    _write(
        repo / "science" / "src" / "science" / "cli.py",
        """from __future__ import annotations

import sys

from science_model import MODEL_SENTINEL


def main() -> None:
    if sys.argv[1:] == ["validate", "--verbose"]:
        print(f"validated:{MODEL_SENTINEL}")
        return
    print(f"science-fixture:{MODEL_SENTINEL}")
""",
    )
    _write(
        repo / "science" / "model" / "pyproject.toml",
        """[project]
name = "science-model"
version = "1.0.0"
requires-python = ">=3.11"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
""",
    )
    _write(
        repo / "science" / "model" / "src" / "science_model" / "__init__.py",
        'MODEL_SENTINEL = "same-sha-model"\n',
    )
    return repo, _commit(repo)


def _consumer_repo(root: Path, toolkit: Path) -> Path:
    repo = root / "consumer"
    repo.mkdir()
    git_url = toolkit.resolve().as_uri()
    _write(
        repo / "pyproject.toml",
        f"""[project]
name = "consumer"
version = "0.1.0"
requires-python = ">=3.11"

[dependency-groups]
dev = ["science"]

[tool.uv.sources]
science = {{ git = "{git_url}", subdirectory = "science" }}
""",
    )
    _write(
        repo / "tests" / "test_install.py",
        """import unittest

from science_model import MODEL_SENTINEL


class InstallTest(unittest.TestCase):
    def test_nested_model_is_installed(self) -> None:
        self.assertEqual(MODEL_SENTINEL, "same-sha-model")
""",
    )
    _write(
        repo / "validate.sh",
        '#!/usr/bin/env bash\nset -euo pipefail\nexec uv run science validate "$@"\n',
    )
    (repo / "validate.sh").chmod(0o755)
    _write(repo / ".gitignore", ".venv/\n.worktrees/\n")
    _commit(repo)
    return repo


def test_git_source_with_nested_editable_source_runs_in_nested_worktree(tmp_path: Path) -> None:
    toolkit, toolkit_sha = _toolkit_repo(tmp_path)
    consumer = _consumer_repo(tmp_path, toolkit)

    _run("uv", "lock", cwd=consumer)
    lock = tomllib.loads((consumer / "uv.lock").read_text(encoding="utf-8"))
    packages = {package["name"]: package for package in lock["package"]}
    science_source = packages["science"]["source"]["git"]
    model_source = packages["science-model"]["source"]["git"]

    assert f"subdirectory=science#{toolkit_sha}" in science_source
    assert f"subdirectory=science%2Fmodel#{toolkit_sha}" in model_source

    _run("git", "add", "uv.lock", cwd=consumer)
    _run("git", "commit", "-q", "-m", "lock", cwd=consumer)
    worktree = consumer / ".worktrees" / "feature"
    worktree.parent.mkdir()
    _run("git", "worktree", "add", "-q", "-b", "feature", str(worktree), cwd=consumer)

    _run("uv", "sync", "--frozen", cwd=worktree)
    cli = _run("uv", "run", "--frozen", "science", cwd=worktree)
    tests = _run("uv", "run", "--frozen", "python", "-m", "unittest", "discover", "-s", "tests", cwd=worktree)
    validation = _run("bash", "validate.sh", "--verbose", cwd=worktree)

    assert cli.stdout.strip() == "science-fixture:same-sha-model"
    assert "OK" in tests.stderr
    assert validation.stdout.strip() == "validated:same-sha-model"
```

- [ ] **Step 2: Run the integration fixture**

Run:

```bash
cd science && uv run --frozen pytest tests/test_git_source_worktree.py -q
```

Expected: PASS. The fixture's Science Git source is local and deterministic; the lock assertions prove both packages use the fixture commit and the nested model source uses `subdirectory=science%2Fmodel`.

- [ ] **Step 3: Commit the uv regression fixture**

```bash
git add science/tests/test_git_source_worktree.py
git commit -m "test: cover Git-sourced nested worktrees"
```

---

### Task 7: Run the complete toolkit gates and prepare publication

**Files:**
- Modify only if a gate exposes a defect in a file changed by Tasks 1–6.

**Interfaces:**
- Consumes: all toolkit work from Tasks 1–6.
- Produces: a clean, validated toolkit commit that is eligible to publish.

- [ ] **Step 1: Run the full Python test suite**

```bash
cd science && uv run --frozen pytest
```

Expected: PASS with the default `snapshot` and `real_projects` exclusions.

- [ ] **Step 2: Run lint and type checking**

```bash
cd science && uv run --frozen ruff check
cd science && uv run --frozen pyright
```

Expected: both commands exit 0.

- [ ] **Step 3: Verify generated artifacts and active-document cleanup**

```bash
cd science && uv run --frozen pytest tests/test_codex_skills.py tests/test_command_docs.py tests/test_agent_cli_compatibility.py -q
rg -n 'SCIENCE_TOOL_PATH|uv add --dev --editable|same filesystem depth|git worktree add ../<project>--<branch>|UV_PROJECT=\$MAIN|\$MAIN/.venv/bin/science' commands references templates AGENTS.md codex-skills
git diff --check
git status --short
```

Expected: tests pass; `rg` returns no matches; whitespace check passes; status contains no uncommitted task files. The pre-existing `meta/knowledge/graph.trig` modification may remain and must not be staged.

If any gate fails, stop publication, use the systematic-debugging skill, return to the task that owns the failing behavior, and rerun all three steps after its focused fix is committed. Do not create an empty verification commit.

---

### Task 8: Publish the toolkit before changing consumers

**Files:**
- None.

**Interfaces:**
- Consumes: the validated toolkit HEAD from Task 7.
- Produces: an `origin/main` commit reachable by normal HTTPS Git dependency resolution.

- [ ] **Step 1: Record and inspect the publication candidate**

```bash
git status --short
git log -1 --oneline
TOOLKIT_SHA=$(git rev-parse HEAD)
printf '%s\n' "$TOOLKIT_SHA"
```

Expected: only known unrelated user changes may be dirty; record the 40-character HEAD as `TOOLKIT_SHA`.

- [ ] **Step 2: Push the validated toolkit history**

```bash
git push origin main
```

Expected: push succeeds. If credentials, policy, or remote state blocks the push, stop here; do not start consumer conversion and do not substitute `--with-editable` as the normal path.

- [ ] **Step 3: Confirm the deployment boundary**

```bash
git fetch origin main
git merge-base --is-ancestor "$TOOLKIT_SHA" origin/main
git rev-parse origin/main
```

Expected: `merge-base --is-ancestor` exits 0. Only then continue.

---

### Task 9: Pilot the downstream conversion in shallow and deep layouts

**Files:**
- Modify in `~/d/cats`: `pyproject.toml`, `uv.lock`, `AGENTS.md` when stale guidance exists, `.env` only when it contains `SCIENCE_TOOL_PATH`.
- Modify in `~/d/cancer/cancer-types/multiple-myeloma`: the same file set.
- Create transiently: `.worktrees/science-git-source-smoke/` in each pilot; remove it with `git worktree remove` after verification.

**Interfaces:**
- Consumes: published `TOOLKIT_SHA` from Task 8.
- Produces: one independent conversion commit in each pilot repository.
- Produces: real nested-worktree proof for one shallow and one deep registry layout.

- [ ] **Step 1: Confirm both pilot repositories are clean and use external path sources**

```bash
git -C ~/d/cats status --short
git -C ~/d/cancer/cancer-types/multiple-myeloma status --short
rg -n 'science\s*=\s*\{\s*path\s*=|SCIENCE_TOOL_PATH|same filesystem depth|git worktree add \.\./' ~/d/cats/pyproject.toml ~/d/cats/AGENTS.md ~/d/cats/.env ~/d/cancer/cancer-types/multiple-myeloma/pyproject.toml ~/d/cancer/cancer-types/multiple-myeloma/AGENTS.md ~/d/cancer/cancer-types/multiple-myeloma/.env
```

Expected: both repos are clean before editing; each manifest has the old external path. Missing optional `.env` files are acceptable.

- [ ] **Step 2: Convert `~/d/cats`**

Use `apply_patch` in that repository to replace only its `science` source with:

```toml
science = { git = "https://github.com/khughitt/science.git", subdirectory = "science" }
```

Replace stale sibling-worktree text in `AGENTS.md` with the nested-worktree text from `templates/agents-md.md`. Remove only lines matching `^(export )?SCIENCE_TOOL_PATH=` from `.env`; preserve all other lines and delete `.env` only if no non-comment content remains.

Then run:

```bash
cd ~/d/cats && uv lock --upgrade-package science
cd ~/d/cats && uv sync --frozen
cd ~/d/cats && uv run --frozen science --version
cd ~/d/cats && bash validate.sh --verbose
```

Expected: the version is at least `0.3.0`, validation passes, and `uv.lock` records a Git source whose commit is reachable from `origin/main`.

- [ ] **Step 3: Prove the shallow pilot in a nested worktree**

```bash
git -C ~/d/cats worktree add -b science-git-source-smoke ~/d/cats/.worktrees/science-git-source-smoke
cd ~/d/cats/.worktrees/science-git-source-smoke && uv sync --frozen
cd ~/d/cats/.worktrees/science-git-source-smoke && uv run --frozen science --version
cd ~/d/cats/.worktrees/science-git-source-smoke && bash validate.sh --verbose
git -C ~/d/cats worktree remove ~/d/cats/.worktrees/science-git-source-smoke
git -C ~/d/cats branch -D science-git-source-smoke
```

Expected: all three commands run from the nested checkout without an external-path or sandbox workaround.

- [ ] **Step 4: Commit the shallow pilot independently**

```bash
git -C ~/d/cats add pyproject.toml uv.lock AGENTS.md .env
git -C ~/d/cats commit -m "chore: pin Science to its Git source"
```

If `.env` was absent or deleted, adjust the explicit `git add` paths to the files actually changed; do not use `git add -A`.

- [ ] **Step 5: Convert and validate the deep multiple-myeloma pilot**

Repeat Step 2 against `~/d/cancer/cancer-types/multiple-myeloma`, using the exact same Git source and `.env` preservation rule. Then run:

```bash
cd ~/d/cancer/cancer-types/multiple-myeloma && uv lock --upgrade-package science
cd ~/d/cancer/cancer-types/multiple-myeloma && uv sync --frozen
cd ~/d/cancer/cancer-types/multiple-myeloma && uv run --frozen science --version
cd ~/d/cancer/cancer-types/multiple-myeloma && bash validate.sh --verbose
```

Expected: all commands pass from the deep main checkout.

- [ ] **Step 6: Prove the deep pilot and commit it independently**

```bash
git -C ~/d/cancer/cancer-types/multiple-myeloma worktree add -b science-git-source-smoke ~/d/cancer/cancer-types/multiple-myeloma/.worktrees/science-git-source-smoke
cd ~/d/cancer/cancer-types/multiple-myeloma/.worktrees/science-git-source-smoke && uv sync --frozen
cd ~/d/cancer/cancer-types/multiple-myeloma/.worktrees/science-git-source-smoke && uv run --frozen science --version
cd ~/d/cancer/cancer-types/multiple-myeloma/.worktrees/science-git-source-smoke && bash validate.sh --verbose
git -C ~/d/cancer/cancer-types/multiple-myeloma worktree remove ~/d/cancer/cancer-types/multiple-myeloma/.worktrees/science-git-source-smoke
git -C ~/d/cancer/cancer-types/multiple-myeloma branch -D science-git-source-smoke
git -C ~/d/cancer/cancer-types/multiple-myeloma add pyproject.toml uv.lock AGENTS.md .env
git -C ~/d/cancer/cancer-types/multiple-myeloma commit -m "chore: pin Science to its Git source"
```

Expected: nested worktree verification passes and the deep pilot has its own conversion commit. Adjust the explicit `git add` list for absent/deleted `.env` exactly as in Step 4.

---

### Task 10: Convert the remaining 18 persistent external consumers

**Files:**
- Modify in each repository: `pyproject.toml`, `uv.lock`, `AGENTS.md` only when stale guidance exists, `.env` only when it contains `SCIENCE_TOOL_PATH`.

**Interfaces:**
- Consumes: the pilot procedure proven in Task 9.
- Produces: one separate conversion commit in each of the 18 repositories listed below.
- Preserves: all unrelated manifest configuration, environment entries, project-specific guidance, and user changes.

The remaining repositories are:

```text
~/d/3d-attention-bias
~/d/protein-landscape
~/d/natural-systems
~/d/cancer/meta
~/d/cancer/mechanisms/evolution
~/d/cancer/conditions/pre-cancer
~/d/cancer/data-sources/cbioportal
~/d/seq-feats
~/d/health/meta
~/d/health/comparisons/pan-disease
~/d/health/processes/cycles
~/d/cancer/cancer-types/ovarian
~/d/cancer/cancer-types/head-and-neck
~/d/cancer/cancer-types/prostate
~/d/cancer/cancer-types/breast
~/d/health/processes/immunity
~/d/health/processes/post-acute-infection
~/d/cancer/therapeutics
```

- [ ] **Step 1: Audit cleanliness before editing any remaining repository**

Run this read-only sweep over the exact list:

```bash
repos=(
  ~/d/3d-attention-bias
  ~/d/protein-landscape
  ~/d/natural-systems
  ~/d/cancer/meta
  ~/d/cancer/mechanisms/evolution
  ~/d/cancer/conditions/pre-cancer
  ~/d/cancer/data-sources/cbioportal
  ~/d/seq-feats
  ~/d/health/meta
  ~/d/health/comparisons/pan-disease
  ~/d/health/processes/cycles
  ~/d/cancer/cancer-types/ovarian
  ~/d/cancer/cancer-types/head-and-neck
  ~/d/cancer/cancer-types/prostate
  ~/d/cancer/cancer-types/breast
  ~/d/health/processes/immunity
  ~/d/health/processes/post-acute-infection
  ~/d/cancer/therapeutics
)
for repo in "${repos[@]}"; do
  git -C "$repo" status --short
done
```

Expected: clean. If a repository is dirty, record it and skip mutation until the owner's change is resolved; do not stash, reset, or fold it into the conversion.

- [ ] **Step 2: Apply the canonical source and cleanup rules one repository at a time**

For each clean repository, use `apply_patch` to replace only the `science` entry in `[tool.uv.sources]` with:

```toml
science = { git = "https://github.com/khughitt/science.git", subdirectory = "science" }
```

Update only stale worktree paragraphs in `AGENTS.md`. Remove only `^(export )?SCIENCE_TOOL_PATH=` lines from `.env`; preserve every other line and delete the file only if no non-comment content remains.

- [ ] **Step 3: Lock, sync, and validate each repository before moving to the next**

Set `repo` to the repository currently being converted—for example, `repo=~/d/3d-attention-bias`—and run this block before advancing `repo` to the next exact path in the list:

```bash
cd "$repo"
uv lock --upgrade-package science
uv sync --frozen
uv run --frozen science --version
bash validate.sh --verbose
```

Expected: every command passes and the reported Science version is at least `0.3.0`. If one fails, keep that repository uncommitted, diagnose it independently, and do not obscure the error with a local editable overlay.

- [ ] **Step 4: Commit each validated repository independently**

For each repository, keep `repo` set to its exact path, explicitly stage the two required files, add an optional file only when `git -C "$repo" diff --name-only` shows it changed, and commit:

```bash
git -C "$repo" add pyproject.toml uv.lock
git -C "$repo" diff --name-only
git -C "$repo" add AGENTS.md
git -C "$repo" add -u .env
git -C "$repo" commit -m "chore: pin Science to its Git source"
```

Run the `AGENTS.md` or `.env` add line only when that path appears in the preceding diff. `git add -u .env` records deletion without staging unrelated files. Do not use `git add -A`, and do not combine repositories into a shared commit operation.

- [ ] **Step 5: Verify the 18-repository checklist is complete**

Reuse the `repos` array from Step 1 and run:

```bash
for repo in "${repos[@]}"; do
  files=("$repo/pyproject.toml" "$repo/AGENTS.md")
  if [[ -e "$repo/.env" ]]; then
    files+=("$repo/.env")
  fi
  git -C "$repo" status --short
  rg -n 'science\s*=\s*\{\s*git\s*=\s*"https://github.com/khughitt/science.git"' "$repo/pyproject.toml"
  rg -n 'science\s*=\s*\{\s*path\s*=|SCIENCE_TOOL_PATH|same filesystem depth|git worktree add \.\./' "${files[@]}"
done
```

Expected: clean status; canonical Git source present; final `rg` has no matches. A missing optional `.env` is not a failure.

---

### Task 11: Audit the registry and record explicit exclusions

**Files:**
- Create: `docs/audits/git-sourced-science-conversion-2026-07-13.md`

**Interfaces:**
- Consumes: `~/.config/science/config.yaml` and all downstream results from Tasks 9–10.
- Produces: a durable receipt covering every persistent registered entry plus the transient `/tmp` registrations currently present.

- [ ] **Step 1: Re-read the live registry and classify every entry**

Run:

```bash
sed -n '1,280p' ~/.config/science/config.yaml
```

Expected classification:

- 20 persistent external consumers converted and validated.
- `~/d/science/meta` excluded because it deliberately uses the same-repository `../science` editable source.
- `~/d/science-commons` excluded because it has no root `pyproject.toml` and is not an ordinary consumer.
- `/tmp/tmpe4t7vbzt` and `/tmp/tmpgwijrm7p` recorded as transient stale registrations if still present; do not treat them as persistent consumers or silently omit them.

- [ ] **Step 2: Create the conversion receipt**

After all listed validations have passed, create `docs/audits/git-sourced-science-conversion-2026-07-13.md` with this complete content:

```markdown
# Git-Sourced Science Conversion Receipt

**Date:** 2026-07-13
**Toolkit publication:** Verified reachable from `origin/main` before consumer conversion.
**Registry:** `~/.config/science/config.yaml`

| Project | Classification | Validation |
|---|---|---|
| `~/d/3d-attention-bias` | external consumer | passed |
| `~/d/cats` | external consumer; shallow nested-worktree smoke | passed |
| `~/d/protein-landscape` | external consumer | passed |
| `~/d/natural-systems` | external consumer | passed |
| `~/d/cancer/cancer-types/multiple-myeloma` | external consumer; deep nested-worktree smoke | passed |
| `~/d/cancer/meta` | external consumer | passed |
| `~/d/cancer/mechanisms/evolution` | external consumer | passed |
| `~/d/cancer/conditions/pre-cancer` | external consumer | passed |
| `~/d/cancer/data-sources/cbioportal` | external consumer | passed |
| `~/d/seq-feats` | external consumer | passed |
| `~/d/health/meta` | external consumer | passed |
| `~/d/health/comparisons/pan-disease` | external consumer | passed |
| `~/d/health/processes/cycles` | external consumer | passed |
| `~/d/cancer/cancer-types/ovarian` | external consumer | passed |
| `~/d/cancer/cancer-types/head-and-neck` | external consumer | passed |
| `~/d/cancer/cancer-types/prostate` | external consumer | passed |
| `~/d/cancer/cancer-types/breast` | external consumer | passed |
| `~/d/health/processes/immunity` | external consumer | passed |
| `~/d/health/processes/post-acute-infection` | external consumer | passed |
| `~/d/cancer/therapeutics` | external consumer | passed |
| `~/d/science/meta` | excluded: same-repository editable source | not converted |
| `~/d/science-commons` | excluded: no root Python manifest | not converted |
| `/tmp/tmpe4t7vbzt` | transient stale registry entry | excluded as nonpersistent |
| `/tmp/tmpgwijrm7p` | transient stale registry entry | excluded as nonpersistent |

Both representative nested worktree smoke tests passed `uv sync --frozen`,
`uv run --frozen science --version`, and `bash validate.sh --verbose` without
main-checkout routing or sandbox exceptions.
```

- [ ] **Step 3: Verify the published toolkit SHA is present in consumer locks**

For each of the 20 external consumers, inspect its `uv.lock` and confirm the selected Science commit is reachable from `origin/main`. It may be the publication candidate or a later published commit, but never an unpublished local SHA. Use this exact project list and lock parser:

```bash
all_repos=(
  ~/d/3d-attention-bias
  ~/d/cats
  ~/d/protein-landscape
  ~/d/natural-systems
  ~/d/cancer/cancer-types/multiple-myeloma
  ~/d/cancer/meta
  ~/d/cancer/mechanisms/evolution
  ~/d/cancer/conditions/pre-cancer
  ~/d/cancer/data-sources/cbioportal
  ~/d/seq-feats
  ~/d/health/meta
  ~/d/health/comparisons/pan-disease
  ~/d/health/processes/cycles
  ~/d/cancer/cancer-types/ovarian
  ~/d/cancer/cancer-types/head-and-neck
  ~/d/cancer/cancer-types/prostate
  ~/d/cancer/cancer-types/breast
  ~/d/health/processes/immunity
  ~/d/health/processes/post-acute-infection
  ~/d/cancer/therapeutics
)
for repo in "${all_repos[@]}"; do
  locked_science_sha=$(uv run --no-project python - "$repo/uv.lock" <<'PY'
import sys
import tomllib
from pathlib import Path

lock = tomllib.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
science = next(package for package in lock["package"] if package["name"] == "science")
source = science["source"]["git"]
assert "github.com/khughitt/science.git" in source
print(source.rsplit("#", 1)[1])
PY
  )
  git -C ~/d/science merge-base --is-ancestor "$locked_science_sha" origin/main
done
```

Expected: every reachability check exits 0.

- [ ] **Step 4: Commit the audit receipt without staging unrelated toolkit changes**

```bash
git add docs/audits/git-sourced-science-conversion-2026-07-13.md
git commit -m "docs: record Git-source consumer conversion"
```

- [ ] **Step 5: Run the final cross-repository status check**

Run `git status --short` in the toolkit and all 20 converted consumers.

Expected: consumers are clean. The toolkit may still show the pre-existing unrelated `meta/knowledge/graph.trig` change; the conversion work must not modify or stage it.
