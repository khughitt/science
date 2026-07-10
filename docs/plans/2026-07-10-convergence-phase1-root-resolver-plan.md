# Convergence Phase 1: One Project-Root Resolver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `science_model/frontmatter.py` the single site of the `science.yaml` filename literal, so no other module hard-codes it, and enforce it with a structural guard test.

**Architecture:** Introduce `PROJECT_CONFIG_FILENAME` and `project_config_path(root)` in `science_model/frontmatter.py` (re-exported from `data_root`). Route every `project_root / "science.yaml"` construction and every inline "walk up to find science.yaml" loop through them — including inside `data_root.py` and `project_config.py` themselves, so the literal genuinely lives in one place. Rename two registry lookups so nothing *reads like* a competing resolver. Land an AST guard that fails if the `"science.yaml"` literal appears anywhere but that one module.

**Tech Stack:** Python 3, Click, Pydantic, PyYAML, ruamel.yaml, pytest. Package under `science/` (run `uv run --frozen` from `science/`).

## Global Constraints

- Run all commands from `science/` unless a step says otherwise: `cd /home/keith/d/science/.worktrees/toolkit-convergence-design/science`.
- Tests: `uv run --frozen pytest`. Lint: `uv run ruff check`. Types: `uv run pyright`.
- `science_model` (`model/src/science_model/`) MUST NOT import `science_tool`. The dependency runs one way only.
- No behavior change: every command and function must produce identical output and side effects before and after. This is a pure refactor.
- No AI-attribution trailers on commits.
- The guard's **one** sanctioned module — the sole place the `"science.yaml"` literal is permitted — is `model/src/science_model/frontmatter.py` (where `PROJECT_CONFIG_FILENAME` is defined). `data_root.py` and `project_config.py` consume the constant/function like everyone else; they are **not** exempt.
- Behave under `explicit over defensive` / `fail early`: do not add silent fallbacks when migrating a raw config read.

---

## Task 1: Define `project_config_path` in `science_model`, re-export from `data_root`

The filename must live in one place. Because a `science_model` module (`aspects.py`,
Task 6) also needs it and `science_model` cannot import `science_tool`, the single
definition lives in the allowlisted `science_model/frontmatter.py` and `data_root`
re-exports it — the same inversion Task 2 uses for `nearest_project_root`. Defining
it in `data_root` instead would force a second definition in `science_model` and
defeat the guard's "one place" premise.

**Files:**
- Modify: `model/src/science_model/frontmatter.py`
- Modify: `src/science_tool/data_root.py` (add the re-export **and** migrate its own two `"science.yaml"` literals at `:26,:56`)
- Modify: `src/science_tool/project_config.py` (migrate its own literal at `:235`)
- Test: `model/tests/test_frontmatter.py`, `tests/test_data_root.py`

**The two shapes the literal takes.** A fresh scan finds 43 `"science.yaml"`
literals across the tree (outside the one sanctioned module): **33** are path
constructions `root / "science.yaml"` (want an absolute path), and **10** are
*relative filename tokens* — `["git", "add", "science.yaml"]`,
`("README.md", "science.yaml", ...)` inventory tuples, `if "science.yaml" not in
tracked`, `Path("science.yaml")` for a display path. The token sites must **not**
become `project_config_path(root)` (that yields an absolute path — wrong type).
The design doc's Rule 1 assumed every use was a path join; it is not. So the single
sanctioned literal is a *filename constant*, and `project_config_path` is built on
it. Both live in `science_model/frontmatter.py`; both are re-exported from
`data_root`.

**Interfaces:**
- Produces: `science_model.frontmatter.PROJECT_CONFIG_FILENAME: str = "science.yaml"` — the one place the literal appears.
- Produces: `science_model.frontmatter.project_config_path(root: Path) -> Path` — returns `root / PROJECT_CONFIG_FILENAME`. Pure path join; does not resolve, expand, or touch disk.
- Produces: `data_root.PROJECT_CONFIG_FILENAME`, `data_root.project_config_path` — re-exports of the above.

- [ ] **Step 1: Write the failing test**

Add to `model/tests/test_frontmatter.py`:

```python
from pathlib import Path

from science_model.frontmatter import PROJECT_CONFIG_FILENAME, project_config_path


def test_project_config_filename_value():
    assert PROJECT_CONFIG_FILENAME == "science.yaml"


def test_project_config_path_appends_filename():
    root = Path("/tmp/some/project")
    assert project_config_path(root) == root / "science.yaml"


def test_project_config_path_is_a_pure_join():
    # No expanduser, no resolve, no filesystem access.
    root = Path("~/rel/proj")
    assert project_config_path(root) == root / "science.yaml"
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `science/model/`): `uv run --frozen pytest tests/test_frontmatter.py::test_project_config_filename_value -v`
Expected: FAIL with `ImportError: cannot import name 'PROJECT_CONFIG_FILENAME'`.

- [ ] **Step 3: Write minimal implementation**

In `model/src/science_model/frontmatter.py`, add near the top (after imports):

```python
PROJECT_CONFIG_FILENAME = "science.yaml"
"""The project manifest filename. The single place this literal appears across
both packages; path builders call ``project_config_path`` and filename-token
sites (git args, inventory tuples, membership checks) import this constant, so
``tests/test_project_root_boundary.py`` can ban the bare literal everywhere else."""


def project_config_path(root: Path) -> Path:
    """Return the path to a project's ``science.yaml`` manifest.

    The single sanctioned constructor of the absolute manifest path. Callers in
    ``science_tool`` reach it via the ``data_root`` re-export. It lives in
    ``science_model`` because ``science_model`` needs it and must not import
    ``science_tool``.
    """
    return root / PROJECT_CONFIG_FILENAME
```

- [ ] **Step 4: Re-export from `data_root` and migrate its own two literals**

In `src/science_tool/data_root.py`, add to the top-level imports:

```python
from science_model.frontmatter import PROJECT_CONFIG_FILENAME, project_config_path
```

(`data_root` has no `__all__`; the import alone makes both available as `data_root.PROJECT_CONFIG_FILENAME` / `data_root.project_config_path`.) Then replace this module's own two hand-built literals so `data_root.py` holds none:

- `discover_project_root` `:26`: `if project_config_path(root).is_file():`
- `_load_project_config_if_present` `:56`: `if not project_config_path(project_root).is_file():`

Add to `tests/test_data_root.py`:

```python
from pathlib import Path


def test_project_config_path_reexported():
    from science_tool.data_root import PROJECT_CONFIG_FILENAME, project_config_path
    assert PROJECT_CONFIG_FILENAME == "science.yaml"
    assert project_config_path(Path("/x/y")) == Path("/x/y/science.yaml")
```

- [ ] **Step 5: Migrate `project_config.py`'s own literal**

`project_config.py:235` (`yaml_path = project_root / "science.yaml"`) is the typed loader itself; it must not be exempt from the "one place" rule. It already imports from `science_model.frontmatter` (`parse_frontmatter`), so extend that import and use it — no cycle (`science_model.frontmatter` imports no `science_tool`):

```python
from science_model.frontmatter import parse_frontmatter, project_config_path
...
    yaml_path = project_config_path(project_root)
```

- [ ] **Step 6: Run tests to verify they pass**

Run (from `science/model/`): `uv run --frozen pytest tests/test_frontmatter.py -v`
Run (from `science/`): `uv run --frozen pytest tests/test_data_root.py -v`
Then confirm nothing broke in the two touched loaders: `uv run --frozen pytest tests/ -k 'project_config or data_root' -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add model/src/science_model/frontmatter.py model/tests/test_frontmatter.py src/science_tool/data_root.py src/science_tool/project_config.py tests/test_data_root.py
git commit -m "feat: PROJECT_CONFIG_FILENAME + project_config_path (sole literal site) in science_model"
```

---

## Task 2: Add a project-root walk-up primitive in `science_model`, re-export from `data_root`

The walk-up at `model/src/science_model/frontmatter.py:358-361` locates a project root by ascending until a `science.yaml` appears. `science_model` cannot import `science_tool`, so the primitive must live in `science_model` and be re-exported downward. `data_root.discover_project_root` then composes it with the env-var handling.

**Files:**
- Modify: `model/src/science_model/frontmatter.py`
- Modify: `src/science_tool/data_root.py`
- Test: `model/tests/test_frontmatter.py` (create if absent), `tests/test_data_root.py`

**Interfaces:**
- Consumes: `science_model.frontmatter.project_config_path` (Task 1).
- Produces: `science_model.frontmatter.nearest_project_root(start: Path) -> Path | None` — the nearest ancestor of `start` (inclusive) containing the manifest, else `None`. Does not read env vars.
- Produces: `data_root.nearest_project_root` — re-export of the above, so `science_tool` callers import it from `data_root`.

- [ ] **Step 1: Write the failing test**

Add to `model/tests/test_frontmatter.py`:

```python
from pathlib import Path

from science_model.frontmatter import nearest_project_root


def test_nearest_project_root_finds_ancestor(tmp_path: Path):
    (tmp_path / "science.yaml").write_text("id: p\n", encoding="utf-8")
    nested = tmp_path / "entities" / "hypotheses"
    nested.mkdir(parents=True)
    assert nearest_project_root(nested) == tmp_path


def test_nearest_project_root_returns_none_when_absent(tmp_path: Path):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert nearest_project_root(nested) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `science/model/`): `uv run --frozen pytest tests/test_frontmatter.py::test_nearest_project_root_finds_ancestor -v`
Expected: FAIL with `ImportError: cannot import name 'nearest_project_root'`.

- [ ] **Step 3: Write minimal implementation**

In `model/src/science_model/frontmatter.py`, add near the top (after imports):

```python
def nearest_project_root(start: Path) -> Path | None:
    """Nearest ancestor of ``start`` (inclusive) containing the project manifest.

    Lives here — not in ``science_tool`` — because ``science_model`` must not
    import ``science_tool`` and this locates the file the schema describes.
    ``science_tool.data_root`` re-exports it and composes the env-var layer.
    """
    candidate = start if start.is_dir() else start.parent
    for root in (candidate, *candidate.parents):
        if project_config_path(root).is_file():
            return root
    return None
```

Then replace the inline walk-up at the former lines 358-361:

```python
    rel_path = str(path)
    project_root = nearest_project_root(path)
    if project_root is not None:
        rel_path = str(path.relative_to(project_root))
```

- [ ] **Step 4: Re-export from `data_root` and add its test**

In `src/science_tool/data_root.py`, add to the imports at the top:

```python
from science_model.frontmatter import nearest_project_root
```

and add `nearest_project_root` to the module's public surface by referencing it in `__all__` if one exists, or leave the import (re-export) as-is if not. Add to `tests/test_data_root.py`:

```python
def test_nearest_project_root_reexported(tmp_path):
    from science_tool.data_root import nearest_project_root
    (tmp_path / "science.yaml").write_text("id: p\n", encoding="utf-8")
    assert nearest_project_root(tmp_path) == tmp_path
```

- [ ] **Step 5: Run tests to verify they pass**

Run (from `science/model/`): `uv run --frozen pytest tests/test_frontmatter.py -v`
Run (from `science/`): `uv run --frozen pytest tests/test_data_root.py -v`
Expected: PASS. Also run the existing frontmatter suite to confirm no behavior change: `cd model && uv run --frozen pytest tests/ -k frontmatter -v`

- [ ] **Step 6: Commit**

```bash
git add model/src/science_model/frontmatter.py model/tests/test_frontmatter.py src/science_tool/data_root.py tests/test_data_root.py
git commit -m "feat(frontmatter): extract nearest_project_root primitive, re-export from data_root"
```

---

## Task 3: Replace the `feedback.py` walk-up with the shared primitive

`feedback.py:534` `detect_project` walks up to `science.yaml` and returns the directory *name*. Replace its loop with `nearest_project_root`, preserving the exact return contract (name of nearest project root, else `start` directory name).

**Files:**
- Modify: `src/science_tool/feedback.py`
- Test: `tests/test_feedback.py` (add a case if the function is untested)

**Interfaces:**
- Consumes: `data_root.nearest_project_root` (Task 2).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_feedback.py`:

```python
from science_tool.feedback import detect_project


def test_detect_project_returns_nearest_root_name(tmp_path):
    (tmp_path / "science.yaml").write_text("id: p\n", encoding="utf-8")
    nested = tmp_path / "sub"
    nested.mkdir()
    assert detect_project(nested) == tmp_path.name


def test_detect_project_falls_back_to_start_name(tmp_path):
    nested = tmp_path / "loose"
    nested.mkdir()
    assert detect_project(nested) == nested.name
```

- [ ] **Step 2: Run test to verify current behavior is preserved**

Run: `uv run --frozen pytest tests/test_feedback.py -k detect_project -v`
Expected: PASS against the *current* implementation (these tests document existing behavior before the refactor).

- [ ] **Step 3: Refactor `detect_project`**

Replace the walk-up body (the `while current != current.parent:` loop, ~lines 542-548) with:

```python
def detect_project(start: Path) -> str:
    """Detect the project name by walking up to find science.yaml.

    Returns the directory name of the nearest ancestor containing science.yaml,
    or the start directory name if none found.
    """
    from science_tool.data_root import nearest_project_root

    resolved = start.resolve()
    root = nearest_project_root(resolved)
    return root.name if root is not None else resolved.name
```

Note the `$HOME` stop in the original was an early-exit optimization; `nearest_project_root` walks to the filesystem root. The returned value is identical unless a `science.yaml` exists *above* `$HOME`, which is not a supported project layout. If a test in the existing suite relied on the `$HOME` stop, preserve it explicitly instead — but first confirm none does.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --frozen pytest tests/test_feedback.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/feedback.py tests/test_feedback.py
git commit -m "refactor(feedback): route detect_project through nearest_project_root"
```

---

## Task 4: Rename the two registry lookups in `commons/config.py`

`resolve_project_root(name)` and `resolve_project_by_id(project_id)` resolve a root from a *registry key*, not a filesystem walk. Rename them to `registry_root_for_name` / `registry_root_for_id` so they stop reading as competing resolvers. Pure rename — no logic change.

**Files:**
- Modify: `src/science_tool/commons/config.py:251,273`
- Modify callers: `src/science_tool/commons/overlay.py:323,351` (`resolve_project_root`), `src/science_tool/commons/promote.py:41,533` (`resolve_project_by_id`)
- Modify exports: `src/science_tool/commons/__init__.py:26-27,182-183`
- Test: existing `tests/` referencing the old names

**Interfaces:**
- Produces: `commons.config.registry_root_for_name(name: str) -> Path` (was `resolve_project_root`), `commons.config.registry_root_for_id(project_id: str) -> Path` (was `resolve_project_by_id`). Signatures and bodies unchanged.

- [ ] **Step 1: Find every reference**

Run: `rg -n 'resolve_project_root|resolve_project_by_id' src/ tests/`
Record the full list. Expected non-test: `commons/config.py` (defs + a docstring mention at :286), `commons/overlay.py` (x2), `commons/promote.py` (x2), `commons/__init__.py` (import + `__all__`).

- [ ] **Step 2: Rename the definitions and update the docstring**

In `commons/config.py`: rename `def resolve_project_root` → `def registry_root_for_name`, `def resolve_project_by_id` → `def registry_root_for_id`. Update the prose at `:286` ("The legacy `resolve_project_root(name)`...") to the new name.

- [ ] **Step 3: Update all callers and exports**

- `commons/overlay.py:30` import and `:323,:351` call sites → `registry_root_for_name`.
- `commons/promote.py:41` import and `:533` call site → `registry_root_for_id`.
- `commons/__init__.py:26-27` imports and `:182-183` `__all__` entries → new names.

- [ ] **Step 4: Update the tests — three shapes, not just imports**

Step 1's list includes tests that reference the names three different ways; a rename that only fixes `import` statements leaves a large red surface. Handle all three:

1. **Direct imports/calls** in tests → new names.
2. **Monkeypatch string targets.** Several tests patch the name as a *string* attribute on the module that imported it, e.g. `monkeypatch.setattr("science_tool.commons.promote.resolve_project_by_id", ...)` in `test_commons_promote_overlay_plan.py:87`, `test_commons_promote_dataset_integration.py:54`, `test_commons_promote_topic_discovery.py:12`, `test_commons_cli_promote.py:40,74,103`. After the rename `promote.resolve_project_by_id` no longer exists — each string must become `...promote.registry_root_for_id`. `rg` for these: `rg -n '"science_tool\.[^"]*resolve_project' tests/`.
3. **Test function names** like `test_resolve_project_by_id_*` in `test_commons_config.py:638,657,676,695` — rename for clarity (cosmetic, but leaving them is misleading).

- [ ] **Step 5: Verify no old name remains anywhere**

Run: `rg -n 'resolve_project_root|resolve_project_by_id' src/ tests/`
Expected: no matches (this catches string targets and function names too, which is why it is the acceptance check).

- [ ] **Step 6: Run the commons suite**

Run: `uv run --frozen pytest tests/ -k 'commons or overlay or promote' -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/science_tool/commons/ tests/
git commit -m "refactor(commons): rename resolve_project_{root,by_id} -> registry_root_for_{name,id}"
```

---

## Task 5: Route the six raw config reads through `project_config_path` (path only)

Six sites `yaml.safe_load` a hand-built `science.yaml` path. This task centralizes the **path** and leaves the raw loads in place.

**Scope decision (narrows the design doc).** The design doc's Phase 1 also called for migrating these raw reads to `load_project_config` and extending `ProjectConfig` with typed fields for the keys they read (`dag`, `layout_version`, `graph.revision_manifest_excludes`, `last_modified`/`version`). This plan **defers** that, for three concrete reasons:

1. **Not a correctness problem.** `ProjectConfig` is declared `model_config = ConfigDict(extra="allow")`, so `load_project_config` already parses and preserves these extra keys today. The raw reads are a tidiness issue, not a bug.
2. **It breaks this plan's invariant.** Adding typed fields changes how config is parsed and validated — a behavior change, which this plan's Global Constraints forbid ("pure refactor"). Typed-schema work belongs in its own plan with its own before/after fixtures.
3. **One read wants the whole dict.** `labnote_export.py:578` returns the *entire* raw mapping; there is no single typed field to migrate it to.

The typed-config-accessor consolidation is recorded as a follow-on in the design doc's Phase 1. This task does only the path centralization the guard actually requires.

**Files:**
- Modify: `src/science_tool/project_package/serialize.py:92`, `src/science_tool/labnote_export.py:578`, `src/science_tool/dag/paths.py:26`, `src/science_tool/project_artifacts/pin.py:25`, `src/science_tool/cli.py:437`, `src/science_tool/graph/io.py:354`

**Interfaces:**
- Consumes: `data_root.project_config_path` (Task 1).

- [ ] **Step 1: Migrate the five plain reads**

For each, replace the inline `(project_root / "science.yaml")` with `project_config_path(project_root)` (import `from science_tool.data_root import project_config_path`), leaving the `yaml.safe_load(...read_text())` as-is:

- `project_package/serialize.py:92`: `raw = yaml.safe_load(project_config_path(project_root).read_text(encoding="utf-8")) or {}`
- `labnote_export.py:577-578`: `science_yaml = project_config_path(project_root)` then keep the existence check and `yaml.safe_load`.
- `dag/paths.py:26`: `cfg = yaml.safe_load(project_config_path(project_root).read_text()) or {}`
- `cli.py:437`: `_manifest = _yaml.safe_load(project_config_path(project_root).read_text(encoding="utf-8")) or {}`
- `graph/io.py:353-357`: `config_path = project_config_path(project_root)` then keep `is_file()` guard and `yaml.safe_load`.

These read raw manifest keys (`last_modified`, `version`, `dag`, `layout_version`, `graph`) the typed `ProjectConfig` may not model; keeping the raw load is correct. Do **not** add a silent fallback if the file is missing where the original did not have one — preserve the original guard exactly.

- [ ] **Step 2: Migrate `pin.py` (round-trip loader stays)**

`project_artifacts/pin.py:22-25` uses ruamel round-trip YAML to preserve formatting for write-back. Change only the path construction:

```python
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    text = project_config_path(project_root).read_text(encoding="utf-8")
    return yaml, yaml.load(text) or {}
```

Do not replace the ruamel loader with `load_project_config` — it must round-trip the file for a later write.

- [ ] **Step 3: Verify no `"science.yaml"` literal remains in these six files**

Run: `rg -n '"science\.yaml"' src/science_tool/project_package/serialize.py src/science_tool/labnote_export.py src/science_tool/dag/paths.py src/science_tool/project_artifacts/pin.py src/science_tool/cli.py src/science_tool/graph/io.py`
Expected: no matches.

- [ ] **Step 4: Run the affected suites**

Run: `uv run --frozen pytest tests/ -k 'serialize or labnote or dag or pin or artifacts or graph_io or cli' -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/
git commit -m "refactor: route the six raw science.yaml reads through project_config_path"
```

---

## Task 6: Sweep the remaining `"science.yaml"` literals (both shapes)

After Task 5, ~two dozen more non-test modules still name the file directly, in the
two shapes Task 1 identified: **path joins** → `project_config_path(...)`, and
**filename tokens** → `PROJECT_CONFIG_FILENAME`. The Task 7 guard is the acceptance
test.

**Files:**
- Modify: all non-test `src/` and `model/src/` modules containing the `"science.yaml"` literal except `data_root.py`, `project_config.py`, `science_model/frontmatter.py`.

**Interfaces:**
- Consumes: `data_root.project_config_path`, `data_root.PROJECT_CONFIG_FILENAME` (or the `science_model.frontmatter` originals for `science_model` modules).

- [ ] **Step 1: Enumerate the surface freshly (do not trust a transcribed list)**

Run:

```bash
# path-join shape -> project_config_path
rg -n '/ ?"science\.yaml"' src model/src | grep -v test | grep -v 'frontmatter\.py'
# everything else that names the file -> filename token
rg -n '"science\.yaml"' src model/src | grep -v test | grep -v 'frontmatter\.py' \
  | grep -vE '/ ?"science\.yaml"'
```

Only `frontmatter.py` is excluded now: `data_root.py` and `project_config.py` were migrated in Task 1 and are no longer exempt, so any `"science.yaml"` they still contain is a real miss the sweep must catch. At authoring time (before Task 1): 33 path-join occurrences, 10 filename-token occurrences across the tree. Regenerate rather than assume.

- [ ] **Step 2: Migrate the path-join shape**

For each `X / "science.yaml"`, substitute `project_config_path(X)` and add `from science_tool.data_root import project_config_path`. Two sub-cases need judgment:

- **Walk-up loops** (`while ... (dir / "science.yaml").exists()`, or `for parent in path.parents: if (parent / "science.yaml")...`): replace the *whole loop* with `nearest_project_root(...)` (Task 2), not just the literal — otherwise the literal merely moves into a helper and the guard still fails.
- **`science_model/` modules other than `frontmatter.py`** cannot import `science_tool.data_root`; import from `science_model.frontmatter` instead. At authoring time the only one is `model/src/science_model/aspects.py:93` (`yaml_path = project_root / "science.yaml"`) →

  ```python
  from science_model.frontmatter import project_config_path
  ...
      yaml_path = project_config_path(project_root)
  ```

- [ ] **Step 3: Migrate the filename-token shape**

These reference the file as a *relative name*, where an absolute path would be wrong. Substitute `PROJECT_CONFIG_FILENAME`, importing `from science_tool.data_root import PROJECT_CONFIG_FILENAME` (or from `science_model.frontmatter` in `science_model` modules). At authoring time the ten sites are shapes like:

- `project_artifacts/cli.py:330,353,396,406` — `["git", "add", PROJECT_CONFIG_FILENAME]`, `paths_intersect([PROJECT_CONFIG_FILENAME], ...)`.
- `graph/io.py:317` — `include_files = ("README.md", PROJECT_CONFIG_FILENAME, "CLAUDE.md", "AGENTS.md")`.
- `project_package/serialize.py:32,223` — `TOP_LEVEL_SINGLES = (PROJECT_CONFIG_FILENAME, ...)`, `if PROJECT_CONFIG_FILENAME not in tracked:`.
- `validate/checks/registration_consistency.py:22`, `validate/checks/manifest.py:17` — `Path(PROJECT_CONFIG_FILENAME)`.

Regenerate from Step 1; do not trust this list. Note: a `"science.yaml"` embedded inside a larger string (e.g. the heredoc in `validate/checks/cross_references.py:6`) is not an exact `"science.yaml"` constant and the guard does not flag it — leave such cases alone.

- [ ] **Step 4: Run the full suite**

Run: `uv run --frozen pytest` (from `science/`), then `cd model && uv run --frozen pytest` (from `science/model/`).
Expected: PASS. Investigate any failure as a real behavior change, not a test to adjust.

- [ ] **Step 5: Types and lint**

Run: `uv run ruff check && uv run pyright`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src model/src
git commit -m "refactor: route remaining science.yaml literals through project_config_path / PROJECT_CONFIG_FILENAME"
```

---

## Task 7: Land the structural guard

The guard makes the canonicalization permanent. It is written *last*, against the migrated tree, so it does not out-scope the migration (the repeated lesson from the design review). Two rules; rule 1 does the work.

**Files:**
- Create: `tests/test_project_root_boundary.py`

**Interfaces:**
- Consumes: nothing at runtime — a static AST/text scan of the source tree.

- [ ] **Step 1: Write the guard test**

Create `tests/test_project_root_boundary.py`:

```python
"""Project-config path boundary guard (convergence Phase 1).

Static ratchet: the ``"science.yaml"`` filename is defined in exactly one
place, ``science_model/frontmatter.py``'s ``PROJECT_CONFIG_FILENAME``. Every
other module must reach the path via that constant or ``project_config_path``.
This guards against the filename regrowing across the tree.

This is a literal-string scan: no exception can be dodged by aliasing the path
into a variable, because every builder must name the file *somewhere*. The literal
is permitted in exactly ONE module — `science_model/frontmatter.py`, which defines
`PROJECT_CONFIG_FILENAME`. `data_root.py` and `project_config.py` are deliberately
NOT exempt (they consume the constant like everyone else), so "one place" is
literally true rather than "three places we trust."
"""

from __future__ import annotations

import ast
from pathlib import Path

_SCIENCE_SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"
_MODEL_SRC = Path(__file__).resolve().parents[1] / "model" / "src" / "science_model"

# The single module permitted to name the manifest file: where the constant lives.
_ALLOWED = {
    _MODEL_SRC / "frontmatter.py",
}


def _source_files() -> list[Path]:
    files: list[Path] = []
    for root in (_SCIENCE_SRC, _MODEL_SRC):
        files.extend(p for p in root.rglob("*.py"))
    return files


def _literal_offenders() -> list[str]:
    offenders: list[str] = []
    for path in _source_files():
        if path in _ALLOWED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == "science.yaml":
                offenders.append(f"{path.name}:{node.lineno}")
    return offenders


def test_science_yaml_literal_is_centralized() -> None:
    offenders = _literal_offenders()
    assert not offenders, (
        'the "science.yaml" literal is permitted only in '
        "science_model/frontmatter.py (where PROJECT_CONFIG_FILENAME is "
        "defined); every other module must use PROJECT_CONFIG_FILENAME or "
        "call project_config_path(root). Offenders: "
        f"{sorted(offenders)}"
    )
```

- [ ] **Step 2: Run the guard — it must pass on the migrated tree**

Run: `uv run --frozen pytest tests/test_project_root_boundary.py -v`
Expected: PASS. If it FAILs, the failure lists the modules Task 5/6 missed — migrate them (do not add them to `_ALLOWED`), then re-run.

- [ ] **Step 3: Prove the guard bites (temporary negative check)**

Temporarily add `_ = "science.yaml"` to any non-allowlisted module (e.g. `src/science_tool/tasks.py`), run the guard, confirm it FAILs naming that file, then revert the edit. This confirms the ratchet is live, not vacuously green.

- [ ] **Step 4: Commit**

```bash
git add tests/test_project_root_boundary.py
git commit -m "test: guard the science.yaml path against decentralization (convergence Phase 1)"
```

---

## Task 8: Full validation sweep

**Files:** none — verification only.

- [ ] **Step 1: Full test suites**

Run: `uv run --frozen pytest` (from `science/`)
Run: `cd model && uv run --frozen pytest` (from `science/model/`)
Expected: PASS.

- [ ] **Step 2: Snapshot suite (behavior-preservation)**

Run: `uv run --frozen pytest -m snapshot`
Expected: PASS — no snapshot changed. A changed snapshot means the refactor altered output and must be investigated, not accepted.

- [ ] **Step 3: Lint and types**

Run: `uv run ruff check && uv run pyright`
Expected: clean.

- [ ] **Step 4: Final guard confirmation**

Run: `uv run --frozen pytest tests/test_project_root_boundary.py tests/test_data_root.py -v`
Expected: PASS.

---

## Self-Review Notes

- **Spec coverage — and one deliberate narrowing.** This plan implements the design doc's Phase 1 filename-centralization in full: the constant + `project_config_path` as the sole literal site incl. `data_root`/`project_config`'s own migration (Task 1); the `science_model` walk-up primitive + re-export and both walk-up replacements (Tasks 2-3); the two registry renames with monkeypatch-string handling (Task 4); the six raw-read **path** migrations incl. the `pin.py` round-trip exception (Task 5); the full literal sweep in both shapes (Task 6); the structural guard (Task 7). **Narrowed:** the design's "one config accessor" clause (migrate raw reads to a typed `load_project_config` + extend `ProjectConfig`) is deferred to a follow-on — see Task 5's scope decision and the design doc's annotated Phase 1. It is a behavior-changing schema refactor and does not belong in this behavior-neutral plan. Phase 0 is retracted in the design doc (deletes nothing) and is intentionally absent here. Phases 2-6 are separate plans.
- **A refinement to the design doc's Rule 1.** The doc's guard said "no module may contain the string literal `"science.yaml"`" and assumed every use is a path build. Implementation found 10 of 43 uses are relative *filename tokens* (git args, inventory tuples, membership tests, display paths) where an absolute `project_config_path(root)` is the wrong type. The plan resolves this with a single `PROJECT_CONFIG_FILENAME` constant that both the path function and the token sites consume, so "the literal lives in one place" holds honestly and the guard stays exactly as strong. The design doc's Phase 1 is annotated with this.
- **The guard is written last, against the migrated tree** (Task 7 after Tasks 5-6), per the review lesson that a guard authored from the doc out-scopes its migration and lands red.
- **Rule 2 of the guard** (the `.read_text()`-of-aliased-path backstop) from the design doc is intentionally *not* implemented as a test here: rule 1 (literal scan) already catches every current site including the `io.py:353` alias, because the alias still contains the literal. Adding rule 2 now would be dead code guarding a hole that does not exist in the tree. Its absence is noted in the guard docstring rather than pretended complete.
- **Behavior preservation** is checked three ways: existing suites (every task), the snapshot suite (Task 8), and the pre-refactor characterization tests in Tasks 3 (feedback) that pin current behavior before the change.
