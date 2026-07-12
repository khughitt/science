# Convergence Phase 6 — Decompose `commons/promote.py` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `commons/promote.py` (3,490 lines) into a shared type vocabulary plus three
single-purpose modules, and evict `click` from the domain layer — so that a conflict prompt,
a git transaction, a YAML renderer, and the dataset subsystem stop living in the same file.

**Architecture:** Land the shared vocabulary (`promote_types.py`) FIRST, then three independent
leaves (`git.py`, `promote_render.py`, `promote_dataset.py`) that each import only from it, then
invert the `prompt_resolve` dependency so `cli.py` owns the only `click` import under `commons/`.
`plan_promote`, `apply_promote`, and `_scan_project` stay in `promote.py` by design.

**Tech Stack:** Python 3.12, uv, pytest, ruff, pyright. Run from `science/`.

---

## Global Constraints

These bind every task. A reviewer checks each one on every diff.

- **Behavior-neutral.** This is a decomposition, not a redesign. Every moved symbol keeps its
  body **byte-for-byte** (imports and formatting aside). Do not "improve" a function while
  moving it — no renames, no signature changes, no added validation, no docstring rewrites.
  The single intentional behavior change is Task 5's `abort_on_conflict` default, specified
  there and nowhere else.
- **The import DAG is one-way and must stay acyclic:**
  ```
  promote_types.py                      (imports nothing from commons/promote*)
      ↑            ↑            ↑
   git.py   promote_render.py   promote_dataset.py     (leaves; import ONLY promote_types)
      ↑            ↑            ↑
              promote.py                (imports all three)
                   ↑
               cli.py                   (imports promote.py; owns the only `click`)
  ```
  **An extracted module must never import from `science_tool.commons.promote`.** That back-edge
  is the exact cycle this phase exists to prevent. If a moved symbol needs something still in
  `promote.py`, the answer is to move that something into `promote_types.py` — never to import
  backwards.
- **No `click` anywhere under `commons/` except `cli.py`.** Task 6 makes this a guard.
- Do not add "legacy", "compat", or "shim" layers. Do not prefix anything `Unified`.
- Composition over inheritance; explicit over defensive; fail early, never silently fall back.
- No AI-attribution trailers on commit messages.
- Use `~/d/` (not `/home/keith/d/` or `/mnt/ssd/Dropbox/`) for any filepath written into docs
  or code.

## Verification commands (run from `science/`)

`FORCE_COLOR` is set in this shell and leaks ANSI codes into CLI-output tests. Unset it per-run:

```bash
cd science
env -u FORCE_COLOR uv run --frozen pytest tests/ -k commons -q     # targeted (implementers)
env -u FORCE_COLOR uv run --frozen pytest -q                      # full gate (controller)
env -u FORCE_COLOR uv run --frozen pytest -m snapshot -q          # byte-identity gate
uv run ruff check
uv run pyright
```

---

## The shared move recipe

**Every extraction task (2, 3, 4) follows exactly these steps.** It is repeated in each task
brief; follow it literally.

1. **Create the new module** with the standard header: `from __future__ import annotations`,
   then stdlib imports, then `science_model` imports, then `science_tool.commons.*` imports.
   Import shared vocabulary from `science_tool.commons.promote_types`.
2. **Move each symbol listed in the task, body unchanged.** Cut from `promote.py`, paste into
   the new module, preserving definition order as listed.
3. **In `promote.py`, add one import** pulling the moved names back:
   `from science_tool.commons.promote_module import _name_a, _name_b, ...`
   Keep the names private (leading underscore) — they stay internal.
4. **Re-point test imports.** Tests import these privates directly by module path. Find them:
   ```bash
   grep -rn "from science_tool.commons.promote import" science/tests | grep -E "_name_a|_name_b"
   ```
   Change the module, never the symbol name.
5. **Verify no back-edge:** the new module must contain zero occurrences of
   `science_tool.commons.promote ` / `commons.promote import`:
   ```bash
   grep -n "commons\.promote\b" science/src/science_tool/commons/<new_module>.py   # must print nothing
   ```
6. **Run** `ruff check`, `pyright`, and the targeted commons tests. Report results.

---

## Symbol ownership map (derived from an AST call map of `promote.py` @ `d2fc4d13`)

This map is authoritative. It supersedes the line numbers in
`2026-07-10-half-applied-pattern-convergence-design.md`, which predate Phase 5 and are stale.

### → `commons/promote_types.py` (Task 1)

Dataclasses / enums / sentinels / constants — the vocabulary every layer speaks. Plus one pure
path guard needed by both the render layer and `apply_promote`.

`EligibilityVerdict`, `SideChannelContext`, `SideChannelResult`, `PromoteKindConfig` (the CLASS
only — see note), `PromoteCandidate`, `FieldConflict`, `ExistingCanonicalConflict`,
`_KeepExisting`, `KEEP_EXISTING`, `ConflictResolution`, `OverlayRewrite`, `CanonicalArtifact`,
`PromoteDecision`, `FailedCandidate`, `DiscoveryResult`, `PromotePlan`, `ResourceVerification`,
`PerResourceResult`, `PromoteResult`, `_RAW_FRONTMATTER_KEY`, `_RAW_BODY_KEY`,
`_OVERLAY_ONLY_KEYS`, `_GENERATED_BY_PROMOTE_KEYS`, `_PROMOTE_DERIVED_IDENTITY_KEYS`,
`_STRUCTURAL_BIO_EXTENSIONS`, `_DOMAIN_BIO_EXTENSIONS`, `_resolve_canonical_artifact_path`

> **Note — the four `PROMOTE_KIND_*` instances do NOT move.** `PROMOTE_KIND_DATASET` holds a
> reference to `_dataset_side_channel_apply` and `PROMOTE_KIND_THEME` to `_theme_eligibility`.
> Moving the instances into a types module would force it to import the modules that import it.
> The `PromoteKindConfig` **class** moves; its four **instances** stay in `promote.py`.

### → `commons/git.py` (Task 2)

The subprocess/transaction layer. ~230 lines.

`_git`, `_commons_is_clean`, `_project_target_files_clean`, `_repo_is_idle`,
`_project_root_from_overlay_path`, `_paths_for_overlay_rollback`,
`_restore_project_rewrites_to_head`, `_restore_paths_to_head`, `_restore_side_channel_backups`,
`_rollback_step5`

> `_write_audit_log` / `_write_failure_audit_log` do NOT move — they orchestrate render + git and
> belong with `apply_promote`. Keeping them out leaves `git.py` a clean leaf.

### → `commons/promote_render.py` (Task 3)

Pure string builders. ~250 lines.

`_rewrite_rendered_frontmatter`, `_render_body`, `_render_canonical`, `_render_overlay`,
`_build_project_rollback_command`, `_audit_canonical_paths`, `_render_audit_log_yaml`,
`_audit_decision_entry`

> `_split_body_by_headings`, `_merge_canonical_fields`, `_dedupe_sorted`,
> `_pick_canonical_bibkey_case`, and `_canonical_fields_equal_or_subset` are **domain logic that
> happens to touch strings** — they stay in `promote.py`.

### → `commons/promote_dataset.py` (Task 4)

The dataset/datapackage subsystem. ~700 lines — the largest extraction.

`_dataset_side_channel_apply`, `_project_relative_path`, `_datapackage_relative_path`,
`_load_project_datapackage`, `_resource_name`, `_validate_datapackage_resources`,
`_dataset_class_for_promotion`, `_dataset_access_for_promotion`,
`_validate_reference_pointer_promotion`, `_normalize_derivation_for_commons`,
`_dataset_dropped_fields`, `_candidate_dataset_class`, `_dataset_per_resource`,
`_stamped_metadata`, `_verify_sourced_resource`, `_validate_dataset_group_datapackages`,
`_dataset_recipe_source_hint`, `_render_dataset_recipe_stub`

### Stays in `commons/promote.py`

`PROMOTE_KIND_PAPER/TOPIC/THEME/DATASET`, `_theme_eligibility`, `_canonical_mixin_extensions`,
`_validate_mixin_stacking`, `_active_profile`, `discover_candidates`, `plan_promote`,
`_validate_decision`, `_validate_plan`, `_validate_artifact`, `_write_audit_log`,
`_write_failure_audit_log`, `_audit_failure_detail`, `apply_promote`, `_normalize_slug_for_match`,
`_semver_key`, `_existing_canonical_for_slug`, `_classify_file_kind`, `logger`,
`_parse_entity_file`, `_parse_frontmatter_only`, `_scan_project`, `_split_body_by_headings`,
`_classify_entity`, `_primary_candidate_for_plan`, `_project_relative_posix`,
`_overlay_target_path`, `_dedupe_sorted`, `_merge_canonical_fields`, `_pick_canonical_bibkey_case`,
`_canonical_fields_equal_or_subset`, and (new, Task 5) `abort_on_conflict`.

Projected final size: **~2,050 lines**, down from 3,490.

---

## Task 1: The shared vocabulary — `commons/promote_types.py`

**Files:**
- Create: `science/src/science_tool/commons/promote_types.py`
- Modify: `science/src/science_tool/commons/promote.py`
- Modify: `science/src/science_tool/commons/__init__.py` (re-export block, line ~86)

**Interfaces:**
- Produces: every symbol in the "→ `commons/promote_types.py`" list above, importable as
  `from science_tool.commons.promote_types import PromoteDecision, ...`. Tasks 2-4 import their
  shared vocabulary from here and from nowhere else.

This task lands FIRST and alone because every later task depends on it. Without it, each
extraction would need to import its dataclasses back from `promote.py` — the cycle.

- [ ] **Step 1: Create `promote_types.py` and move the symbols**

Move every symbol in the Task 1 list, **bodies unchanged**, preserving their current relative
order. The module imports only stdlib + `science_model` + `science_tool.commons.errors` /
`science_tool.commons.datapackage` as needed. It must import **nothing** from
`science_tool.commons.promote`.

Header:

```python
"""Shared vocabulary for the promote pipeline.

Every promote layer — discovery, planning, rendering, the git transaction, and the
dataset subsystem — speaks these types. It lives in its own module so those layers
can each import the vocabulary without importing each other.

Nothing here imports from `commons.promote`: this module is the bottom of the DAG.
"""
```

- [ ] **Step 2: Import them back into `promote.py`**

Replace the moved definitions with a single import:

```python
from science_tool.commons.promote_types import (
    KEEP_EXISTING,
    CanonicalArtifact,
    ConflictResolution,
    DiscoveryResult,
    EligibilityVerdict,
    ExistingCanonicalConflict,
    FailedCandidate,
    FieldConflict,
    OverlayRewrite,
    PerResourceResult,
    PromoteCandidate,
    PromoteDecision,
    PromoteKindConfig,
    PromotePlan,
    PromoteResult,
    ResourceVerification,
    SideChannelContext,
    SideChannelResult,
    _DOMAIN_BIO_EXTENSIONS,
    _GENERATED_BY_PROMOTE_KEYS,
    _KeepExisting,
    _OVERLAY_ONLY_KEYS,
    _PROMOTE_DERIVED_IDENTITY_KEYS,
    _RAW_BODY_KEY,
    _RAW_FRONTMATTER_KEY,
    _STRUCTURAL_BIO_EXTENSIONS,
    _resolve_canonical_artifact_path,
)
```

`commons/__init__.py` already re-exports `ConflictResolution`, `DiscoveryResult`,
`FailedCandidate`, `FieldConflict`, `OverlayRewrite`, `PromoteCandidate`, `PromoteDecision`,
`PromoteKindConfig`, `PromotePlan`, and `PromoteResult` from `commons.promote`. Because
`promote.py` re-imports them, **that block keeps working untouched** — leave it alone. Verify,
don't assume:

```bash
cd science && env -u FORCE_COLOR uv run --frozen python -c "
from science_tool.commons import PromoteDecision, PromotePlan, PromoteResult, plan_promote
print('public API intact')"
```

- [ ] **Step 3: Verify no back-edge**

```bash
grep -n "commons\.promote\b" science/src/science_tool/commons/promote_types.py
```
Expected: **no output.** Any hit is the cycle — fix before continuing.

- [ ] **Step 4: Run the gate**

```bash
cd science
uv run ruff check && uv run pyright
env -u FORCE_COLOR uv run --frozen pytest tests/ -k commons -q
```
Expected: ruff clean, pyright 0 errors, all commons tests pass. This is a pure move — a single
test failure means a symbol was dropped or a body was altered.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote_types.py science/src/science_tool/commons/promote.py
git commit -m "refactor(commons): extract the promote type vocabulary into promote_types

Every promote layer speaks these types. Giving them their own module at the
bottom of the import DAG lets the git, render, and dataset layers each import
the vocabulary without importing each other."
```

---

## Task 2: The transaction layer — `commons/git.py`

**Files:**
- Create: `science/src/science_tool/commons/git.py`
- Modify: `science/src/science_tool/commons/promote.py`
- Modify: tests importing `_rollback_step5` (2 sites), `_repo_is_idle` (1 site)

**Interfaces:**
- Consumes: `promote_types` (Task 1) — `OverlayRewrite`, `SideChannelResult`, `PromoteKindConfig`.
- Produces: `_git(commons_root, *args, check=True) -> subprocess.CompletedProcess` and the
  restore/rollback helpers, importable from `science_tool.commons.git`.

Follow **the shared move recipe** (above). Symbols: the Task 2 list in the ownership map.

- [ ] **Step 1: Create `git.py`, move the 10 symbols, bodies unchanged**

Header:

```python
"""Git transaction primitives for commons promotion.

`_git` is the single subprocess entry point; everything else here is a repo guard
(is the tree clean? is the repo idle?) or a rollback step that returns the working
tree to HEAD after a failed promotion.

This module is a leaf: it imports the promote vocabulary, never the promote pipeline.
"""
```

Note `_git` is used from ~18 call sites inside `apply_promote` and once from
`_existing_canonical_for_slug` — all of which stay in `promote.py` and reach it via the import
added in Step 2. Do not change any call site.

- [ ] **Step 2: Import back into `promote.py`**

```python
from science_tool.commons.git import (
    _commons_is_clean,
    _git,
    _paths_for_overlay_rollback,
    _project_root_from_overlay_path,
    _project_target_files_clean,
    _repo_is_idle,
    _restore_paths_to_head,
    _restore_project_rewrites_to_head,
    _restore_side_channel_backups,
    _rollback_step5,
)
```

- [ ] **Step 3: Re-point the test imports**

```bash
grep -rn "from science_tool.commons.promote import" science/tests | grep -E "_rollback_step5|_repo_is_idle"
```
Change the module to `science_tool.commons.git`. Symbol names are unchanged.

- [ ] **Step 4: Verify no back-edge, then gate**

```bash
grep -n "commons\.promote\b" science/src/science_tool/commons/git.py   # must print nothing
cd science
uv run ruff check && uv run pyright
env -u FORCE_COLOR uv run --frozen pytest tests/ -k commons -q
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(commons): extract the git transaction layer into commons/git

_git is now the single subprocess entry point, sitting with the repo guards and
the rollback steps that undo a failed promotion."
```

---

## Task 3: The renderers — `commons/promote_render.py`

**Files:**
- Create: `science/src/science_tool/commons/promote_render.py`
- Modify: `science/src/science_tool/commons/promote.py`
- Modify: tests importing `_render_canonical` (2), `_render_overlay` (1)

**Interfaces:**
- Consumes: `promote_types` (Task 1) — `PromoteDecision`, `PromotePlan`, `PromoteResult`,
  `CanonicalArtifact`, `OverlayRewrite`, `_OVERLAY_ONLY_KEYS`, `_resolve_canonical_artifact_path`.
- Produces: `_render_canonical`, `_render_overlay`, `_render_audit_log_yaml`, and the audit
  helpers, importable from `science_tool.commons.promote_render`.

Follow **the shared move recipe**. Symbols: the Task 3 list in the ownership map.

`_audit_canonical_paths` calls `_resolve_canonical_artifact_path`, which is why Task 1 put that
path guard in `promote_types` — import it from there, do **not** import it from `promote`.

The audit-YAML renderers (`_render_audit_log_yaml`, `_audit_decision_entry`,
`_audit_canonical_paths`, `_build_project_rollback_command`) build strings only; they run no
subprocess. `promote_render.py` must **not** import `commons/git.py`.

- [ ] **Step 1: Create `promote_render.py`, move the 8 symbols, bodies unchanged**

Header:

```python
"""String builders for commons promotion.

Canonical entities, project overlays, and the audit log are all rendered here.
Every function is a pure string builder: it takes a decision or a plan and returns
text. No I/O, no subprocess, no git.
"""
```

- [ ] **Step 2: Import back into `promote.py`**

```python
from science_tool.commons.promote_render import (
    _audit_canonical_paths,
    _audit_decision_entry,
    _build_project_rollback_command,
    _render_audit_log_yaml,
    _render_body,
    _render_canonical,
    _render_overlay,
    _rewrite_rendered_frontmatter,
)
```

- [ ] **Step 3: Re-point the test imports**

```bash
grep -rn "from science_tool.commons.promote import" science/tests | grep -E "_render_canonical|_render_overlay"
```
Change the module to `science_tool.commons.promote_render`.

Note `tests/test_promote_render_frontmatter_golden.py` is a **golden/byte-identity** test on
rendered frontmatter. It must stay green without edits to its expected values. If it fails, a
body was altered during the move — revert and re-move, do not update the golden.

- [ ] **Step 4: Verify no back-edge, then gate**

```bash
grep -nE "commons\.promote\b|commons\.git\b" science/src/science_tool/commons/promote_render.py   # must print nothing
cd science
uv run ruff check && uv run pyright
env -u FORCE_COLOR uv run --frozen pytest tests/ -k commons -q
env -u FORCE_COLOR uv run --frozen pytest tests/test_promote_render_frontmatter_golden.py -q
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(commons): extract the promote renderers into promote_render

Canonical, overlay, and audit-log rendering are pure string builders. They no
longer share a file with the git transaction that writes their output."
```

---

## Task 4: The dataset subsystem — `commons/promote_dataset.py`

**Files:**
- Create: `science/src/science_tool/commons/promote_dataset.py`
- Modify: `science/src/science_tool/commons/promote.py`
- Modify: tests importing `_dataset_dropped_fields` (1), `_normalize_derivation_for_commons` (1),
  `_render_dataset_recipe_stub` (2)

**Interfaces:**
- Consumes: `promote_types` (Task 1) — `PromoteCandidate`, `ResourceVerification`,
  `PerResourceResult`, `SideChannelContext`, `SideChannelResult`, `PromoteDecision`.
  Also `commons.datapackage` (already imported by `promote.py` today).
- Produces: the 18 dataset symbols, importable from `science_tool.commons.promote_dataset`.

This is the largest extraction (~700 lines) and the one the design doc singles out: *"It shares
no logic with paper/theme promotion; it is a second module inlined into the first."*

Follow **the shared move recipe**. Symbols: the Task 4 list in the ownership map.

- [ ] **Step 1: Create `promote_dataset.py`, move the 18 symbols, bodies unchanged**

Header:

```python
"""The dataset/datapackage half of commons promotion.

Datasets promote differently from papers, topics, and themes: they carry a
datapackage whose resources must be verified (hash, size, reachability) and a
side-channel payload that lands outside the entity file. None of that logic is
shared with the other kinds — it reached the generic pipeline through
`dataset`-kind conditionals, which is why it can live in its own module.
"""
```

`_dataset_side_channel_apply` is referenced by the `PROMOTE_KIND_DATASET` config literal, which
**stays in `promote.py`**. After the move, `promote.py` imports the function and the literal
keeps working. This is why the kind instances did not move in Task 1 — re-read that note if the
import looks circular.

- [ ] **Step 2: Import back into `promote.py`**

```python
from science_tool.commons.promote_dataset import (
    _candidate_dataset_class,
    _dataset_access_for_promotion,
    _dataset_class_for_promotion,
    _dataset_dropped_fields,
    _dataset_per_resource,
    _dataset_recipe_source_hint,
    _dataset_side_channel_apply,
    _datapackage_relative_path,
    _load_project_datapackage,
    _normalize_derivation_for_commons,
    _project_relative_path,
    _render_dataset_recipe_stub,
    _resource_name,
    _stamped_metadata,
    _validate_datapackage_resources,
    _validate_dataset_group_datapackages,
    _validate_reference_pointer_promotion,
    _verify_sourced_resource,
)
```

- [ ] **Step 3: Re-point the test imports**

```bash
grep -rn "from science_tool.commons.promote import" science/tests \
  | grep -E "_dataset_dropped_fields|_normalize_derivation_for_commons|_render_dataset_recipe_stub"
```
Change the module to `science_tool.commons.promote_dataset`.

- [ ] **Step 4: Verify no back-edge, then gate**

```bash
grep -n "commons\.promote\b" science/src/science_tool/commons/promote_dataset.py   # must print nothing
cd science
uv run ruff check && uv run pyright
env -u FORCE_COLOR uv run --frozen pytest tests/ -k "commons or dataset" -q
```

The dataset integration tests (`test_commons_promote_dataset_integration.py`,
`test_commons_promote_dataset_plan.py`, `test_commons_cli_promote_dataset.py`) are the real
proof here. All must pass unchanged.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(commons): extract the dataset subsystem into promote_dataset

Dataset promotion shares no logic with paper/topic/theme promotion -- it reached
the generic pipeline through dataset-kind conditionals. It is now its own module."
```

---

## Task 5: Evict `click` from the domain — `prompt_resolve` moves to `cli.py`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (remove `prompt_resolve` + the `click`
  import at line 28; add `abort_on_conflict`)
- Modify: `science/src/science_tool/commons/cli.py` (gains `prompt_resolve`; passes it explicitly)
- Modify: `science/src/science_tool/commons/__init__.py` (drop `prompt_resolve` from the
  re-export and from `__all__`)
- Modify: 5 test files that monkeypatch `science_tool.commons.promote.prompt_resolve`

**Interfaces:**
- Consumes: `promote_types` — `FieldConflict`, `ExistingCanonicalConflict`, `KEEP_EXISTING`.
- Produces: `prompt_resolve` at `science_tool.commons.cli.prompt_resolve`;
  `abort_on_conflict` at `science_tool.commons.promote.abort_on_conflict`.

**This is the load-bearing task.** `click` appears in `promote.py` at exactly 16 places, **all of
them inside `prompt_resolve`** (lines 555-609). Move that one function and the domain module
stops importing a CLI framework.

The cycle to avoid: `plan_promote` currently *calls* `prompt_resolve`. If `prompt_resolve` moves
to `cli.py` and `plan_promote` still calls it, `promote.py` would import `cli.py`, which imports
`promote.py`. **Invert it instead** — `plan_promote` already accepts the resolver as a parameter:

```python
resolve_conflict: Callable[[FieldConflict | ExistingCanonicalConflict], Any] | None = None
...
if resolve_conflict is None:
    resolve_conflict = prompt_resolve   # <-- the only edge that binds the cycle
```

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_commons_promote_no_click.py`:

```python
"""The domain module must not import a CLI framework."""

from __future__ import annotations

import ast
from pathlib import Path

_PROMOTE = Path(__file__).resolve().parents[1] / "src" / "science_tool" / "commons" / "promote.py"


def test_promote_does_not_import_click() -> None:
    tree = ast.parse(_PROMOTE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "click" for a in node.names), (
                "commons/promote.py imports click; the interactive prompt belongs in cli.py"
            )
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "click":
            raise AssertionError(
                "commons/promote.py imports click; the interactive prompt belongs in cli.py"
            )
```

- [ ] **Step 2: Run it — watch it fail**

```bash
cd science && env -u FORCE_COLOR uv run --frozen pytest tests/test_commons_promote_no_click.py -q
```
Expected: **FAIL** — "commons/promote.py imports click". (`promote.py:28` is `import click`.)

- [ ] **Step 3: Add `abort_on_conflict` to `promote.py`**

Replace the `None`-default indirection with a real domain default. Put this where
`prompt_resolve` used to be:

```python
def abort_on_conflict(conflict: FieldConflict | ExistingCanonicalConflict) -> Any:
    """Default conflict resolver: refuse to guess.

    Resolving a field conflict needs a human. A caller that wants one wires an
    interactive resolver in (`cli.py` passes `prompt_resolve`); a caller that has
    no human — a test, a script, a piped run — aborts the batch instead.
    """
    raise PromoteConflictAbort(
        f"conflict for {conflict.kind}:{conflict.slug} needs an interactive resolver"
    )
```

Then change `plan_promote`'s signature and delete the `None` branch:

```python
    resolve_conflict: Callable[
        [FieldConflict | ExistingCanonicalConflict], Any
    ] = abort_on_conflict,
```

and remove these two lines from the body:

```python
    if resolve_conflict is None:
        resolve_conflict = prompt_resolve
```

Update the docstring line `` `resolve_conflict` defaults to `prompt_resolve`. `` to
`` `resolve_conflict` defaults to `abort_on_conflict`; `cli.py` passes `prompt_resolve`. ``
Update the module docstring at line 9 the same way.

> **Why this is behavior-neutral.** Today, a non-interactive caller that hits a conflict reaches
> `prompt_resolve` → `click.prompt` → stdin is not a tty → `click.Abort` → caught → re-raised as
> `PromoteConflictAbort`. `abort_on_conflict` raises `PromoteConflictAbort` directly. Same
> exception, same callers, one less layer — and no `click` in the domain. Do **not** make the
> parameter required; that would churn ~10 test call sites for no behavioral gain.

- [ ] **Step 4: Move `prompt_resolve` into `cli.py`, body unchanged**

Cut `prompt_resolve` (lines 543-609) from `promote.py` and paste it into `cli.py`. Delete
`import click` from `promote.py` (line 28) — `cli.py` already imports click. `prompt_resolve`
needs `FieldConflict`, `ExistingCanonicalConflict`, and `KEEP_EXISTING`; import them in `cli.py`
from `science_tool.commons.promote_types`.

- [ ] **Step 5: Have `cli.py` pass the resolver explicitly**

At `cli.py:1214`, `plan_promote(...)` is called **without** `resolve_conflict` — it relies on the
default that is now `abort_on_conflict`. Add the argument so the interactive path keeps working:

```python
        plan = plan_promote(
            discovery,
            commons_root=root,
            kind=kind,
            from_order=list(from_),
            mixin_extensions=mixin_extensions,
            verify_digests=verify_digests,
            resolve_conflict=prompt_resolve,
            skip_on_conflict=non_interactive,
            skip_on_invalid=non_interactive,
        )
```

This is the one line that makes the CLI — and only the CLI — interactive.

- [ ] **Step 6: Drop `prompt_resolve` from the package's public API**

In `commons/__init__.py`, remove `prompt_resolve` from the `from science_tool.commons.promote
import (...)` block (line ~100) and from `__all__` (line ~174).

Do **not** re-export it from `cli.py` instead: `commons/__init__.py` importing `commons/cli.py`
would pull `click` into the package's import graph and risks a cycle. An interactive prompt has
no place in a domain package's public API — removing it is the correct outcome, not a compromise.

- [ ] **Step 7: Re-point the 5 monkeypatch targets**

```bash
grep -rln "science_tool.commons.promote.prompt_resolve\|from science_tool.commons.promote import.*prompt_resolve" science/tests
```
Expected files: `test_commons_cli_promote.py` (3 sites), `test_commons_cli_promote_topic.py`,
`test_commons_cli_promote_theme.py`, `test_commons_promote_overlay_plan.py`,
`test_commons_promote_discovery.py`, `test_commons_promote_plan.py`.

Change the patch target string `"science_tool.commons.promote.prompt_resolve"` →
`"science_tool.commons.cli.prompt_resolve"`, and the import
`from science_tool.commons.promote import ... prompt_resolve` →
`from science_tool.commons.cli import prompt_resolve`.

The monkeypatch still works: `cli.py` looks `prompt_resolve` up as a module global at call time.

- [ ] **Step 8: Run the guard, then the gate**

```bash
cd science
env -u FORCE_COLOR uv run --frozen pytest tests/test_commons_promote_no_click.py -q   # now PASSES
uv run ruff check && uv run pyright
env -u FORCE_COLOR uv run --frozen pytest tests/ -k commons -q
```

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "refactor(commons): the conflict prompt moves to the CLI

promote.py imported click for exactly one function: the interactive conflict
prompt. plan_promote already took the resolver as a parameter -- it just defaulted
to the prompt, and that default was the only thing binding a domain module to a CLI
framework. The default is now abort_on_conflict (same PromoteConflictAbort a
non-interactive run already got), and cli.py passes prompt_resolve explicitly."
```

---

## Task 6: The guard — `tests/test_commons_domain_purity.py`

**Files:**
- Create: `science/tests/test_commons_domain_purity.py`
- Delete: `science/tests/test_commons_promote_no_click.py` (Task 5's scaffold — subsumed here)

**Interfaces:**
- Consumes: the migrated tree from Tasks 1-5. Written LAST, against what actually shipped.

A phase that migrates without landing its guard is not done. The guard keys on **AST structure**,
never on text, and it must be **proven to bite** — not merely observed to pass.

- [ ] **Step 1: Measure the migrated tree**

```bash
cd science
wc -l src/science_tool/commons/promote.py src/science_tool/commons/promote_types.py \
      src/science_tool/commons/git.py src/science_tool/commons/promote_render.py \
      src/science_tool/commons/promote_dataset.py
```
Record `promote.py`'s real line count. The budget below is that number + ~20%, rounded up to a
clean hundred. **Do not copy a number from this plan** — measure it.

- [ ] **Step 2: Write the guard**

Create `science/tests/test_commons_domain_purity.py`:

```python
"""Structural guard: the promote pipeline stays decomposed.

Phase 6 split commons/promote.py into a shared type vocabulary plus three
single-purpose layers. Two invariants keep it split:

  1. No module under commons/ except cli.py imports click. An interactive prompt
     in a domain module is what made promote.py import a CLI framework.
  2. The extracted layers never import back from commons/promote. That back-edge
     is the cycle the decomposition exists to prevent.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_COMMONS = Path(__file__).resolve().parents[1] / "src" / "science_tool" / "commons"
_PROMOTE = _COMMONS / "promote.py"

# cli.py is the ONLY module under commons/ allowed to import click.
_CLICK_ALLOWED = {"cli.py"}

# The layers extracted out of promote.py. Each may import promote_types; none may
# import promote.
_EXTRACTED_LAYERS = ("promote_types.py", "git.py", "promote_render.py", "promote_dataset.py")

# Set from the measured post-migration size of promote.py, plus ~20% headroom.
# MEASURE IT (Step 1) — do not carry a number over from the plan.
_PROMOTE_LINE_BUDGET = 0  # <-- replace


def _commons_modules() -> list[Path]:
    return sorted(p for p in _COMMONS.glob("*.py") if p.name != "__init__.py")


def _imports_click(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == "click" for alias in node.names):
                return True
        if isinstance(node, ast.ImportFrom):
            if node.level == 0 and (node.module or "").split(".")[0] == "click":
                return True
    return False


def _imports_promote(tree: ast.Module) -> bool:
    """True if the module imports from science_tool.commons.promote (the back-edge).

    Catches every spelling: the absolute module, the absolute package-with-alias
    form, and relative escapes — including function-local imports, since ast.walk
    descends into function bodies.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "science_tool.commons.promote":
                return True
            imported = {alias.name for alias in node.names}
            if node.level == 0 and node.module == "science_tool.commons" and "promote" in imported:
                return True
            if node.level > 0 and (node.module == "promote" or "promote" in imported):
                return True
        if isinstance(node, ast.Import):
            if any(alias.name == "science_tool.commons.promote" for alias in node.names):
                return True
    return False


@pytest.mark.parametrize(
    "module", _commons_modules(), ids=lambda p: p.name
)
def test_only_the_cli_imports_click(module: Path) -> None:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    if module.name in _CLICK_ALLOWED:
        return
    assert not _imports_click(tree), (
        f"commons/{module.name} imports click. Only commons/cli.py may depend on a CLI "
        f"framework -- an interactive prompt does not belong in a domain module."
    )


@pytest.mark.parametrize("name", _EXTRACTED_LAYERS)
def test_extracted_layer_does_not_import_promote(name: str) -> None:
    """The import DAG is one-way: promote_types <- {git, render, dataset} <- promote."""
    tree = ast.parse((_COMMONS / name).read_text(encoding="utf-8"))
    assert not _imports_promote(tree), (
        f"commons/{name} imports from commons.promote, which imports it back. "
        f"Shared vocabulary belongs in commons/promote_types.py."
    )


def test_promote_types_is_the_bottom_of_the_dag() -> None:
    """promote_types imports none of the layers that import it."""
    tree = ast.parse((_COMMONS / "promote_types.py").read_text(encoding="utf-8"))
    forbidden = {"git", "promote_render", "promote_dataset", "promote", "cli"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "science_tool.commons."
        ):
            leaf = node.module.removeprefix("science_tool.commons.")
            assert leaf not in forbidden, (
                f"promote_types imports commons.{leaf}, which imports promote_types back. "
                f"promote_types is the bottom of the DAG and must stay a leaf."
            )


def test_promote_stays_within_its_line_budget() -> None:
    lines = len(_PROMOTE.read_text(encoding="utf-8").splitlines())
    assert lines <= _PROMOTE_LINE_BUDGET, (
        f"promote.py is {lines} lines (budget {_PROMOTE_LINE_BUDGET}). A renderer belongs in "
        f"promote_render.py, a git call in git.py, a dataset rule in promote_dataset.py, and a "
        f"shared type in promote_types.py."
    )
```

- [ ] **Step 3: Fill in the measured budget**

Replace `_PROMOTE_LINE_BUDGET = 0` with the Step 1 measurement + ~20%, and update the comment to
state the measured number, e.g. `# 2,050 measured + ~20% headroom`.

- [ ] **Step 4: Delete Task 5's scaffold**

`test_commons_promote_no_click.py` is now a strict subset of `test_only_the_cli_imports_click`.
Delete it — two tests asserting one invariant is one test too many.

```bash
git rm science/tests/test_commons_promote_no_click.py
```

- [ ] **Step 5: PROVE each guard bites**

A guard that has never failed is a guard you have not tested. For **each** of the four
invariants, temporarily inject the violation, run the guard, confirm it FAILS, then revert.
Report the observed failure message for each.

```bash
cd science
# 1. click in a domain module
sed -i '1i import click' src/science_tool/commons/promote_dataset.py
env -u FORCE_COLOR uv run --frozen pytest tests/test_commons_domain_purity.py -q   # expect FAIL
git checkout src/science_tool/commons/promote_dataset.py

# 2. back-edge into promote -- try ALL FOUR spellings, one at a time.
#    (Phase 5 shipped a guard that missed the third form. Do not skip any.)
#      a) from science_tool.commons.promote import plan_promote
#      b) from science_tool.commons import promote
#      c) import science_tool.commons.promote
#      d) from ..commons.promote import plan_promote     (relative)
#    Inject each into git.py, run the guard, confirm FAIL, revert.

# 3. promote_types imports a layer above it
sed -i '1i from science_tool.commons.git import _git' src/science_tool/commons/promote_types.py
env -u FORCE_COLOR uv run --frozen pytest tests/test_commons_domain_purity.py -q   # expect FAIL
git checkout src/science_tool/commons/promote_types.py

# 4. line budget -- append filler to promote.py, confirm FAIL, revert.
```

**Report the failure message you observed for each of the 7 injections.** If any injection
passes, the guard has a hole — fix the predicate and re-run all 7.

- [ ] **Step 6: Full gate**

```bash
cd science
uv run ruff check && uv run pyright
env -u FORCE_COLOR uv run --frozen pytest -q
env -u FORCE_COLOR uv run --frozen pytest -m snapshot -q
```
Expected: all green, snapshot byte-identical, pyright 0 errors.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "test(commons): guard the promote decomposition

Two invariants, both keyed on AST structure: only cli.py may import click, and no
extracted layer may import back from promote. Each guard was proven to fail against
an injected violation -- including all four spellings of the back-edge import."
```

---

## Outcome (2026-07-12)

Shipped. `promote.py` 3,490 → 2,193 lines, on four extracted modules
(`promote_types.py` 313, `git.py` 214, `promote_render.py` 308,
`promote_dataset.py` 547). `commons/cli.py` is the only module under `commons/`
that imports `click`. 8,076 tests pass; snapshot byte-identity gate green.

The whole-branch review AST-diffed all 98 top-level symbols of `promote.py`
against their landing sites and found **zero** body differences — the moves were
byte-for-byte, as required. It then broke the guard three ways (see `b32ae0ba`);
both back-edge checks now derive their scope from the import closure rather than
a hand-written list.

**Behavior-change residual — the neutrality claim was narrower than Task 5 stated.**
Task 5 argued `abort_on_conflict` is behavior-neutral because a *non-interactive*
caller hitting a conflict already ended in `PromoteConflictAbort`. That holds, and
it covers every caller in this repo. It does not cover two paths that have no
callers today but are reachable through the public API (`plan_promote` is exported
from `commons/__init__.py`):

- A **library caller on a live tty** that omitted `resolve_conflict` used to get an
  interactive prompt. It now gets an immediate `PromoteConflictAbort`. Interactivity
  is opt-in now; only `cli.py` opts in.
- `resolve_conflict=None` passed **explicitly** used to mean "use the prompt". It is
  now a `TypeError`.

Both are intended consequences of making the domain layer non-interactive. They are
recorded here because "behavior-neutral" was the phase's contract, and these are the
two places it bends.

## Self-review notes

- **Task 1 must land alone and first.** Tasks 2-4 all import `promote_types`; running them
  before it exists forces the back-edge this phase exists to remove.
- **Tasks 2, 3, 4 are mutually independent** — each imports only `promote_types`. They are
  ordered smallest-to-largest to fail cheap, but a reviewer can reject one without the others.
- **The design doc's line numbers are stale** (written pre-Phase-5, and it lists `promote.py` at
  3,543 lines; it is 3,490 today). The ownership map above was re-derived from an AST call map at
  `d2fc4d13` and supersedes it. Two things the design doc got wrong, both caught by the call map:
  the four `PROMOTE_KIND_*` instances cannot move to a types module (they hold callables into the
  dataset layer), and `_resolve_canonical_artifact_path` is shared by the render layer and
  `apply_promote` (so it must sit in `promote_types`, not in either).
- **No existing guard keys on `commons/promote.py` by path** — verified against
  `instruments.py::INSTRUMENT_MODULES`, `test_instrument_boundary.py`, `test_entity_scan_guard.py`,
  and every other structural guard under `tests/`. Phase 5's silent-coverage-narrowing hazard does
  not apply here. Do not add `commons/` paths to `INSTRUMENT_MODULES`.
- **16 private symbols are imported directly by tests.** Eight of them move; each moving task
  re-points its own. `_classify_file_kind`, `_existing_canonical_for_slug`,
  `_normalize_slug_for_match`, `_semver_key`, `_scan_project`, `_parse_entity_file`,
  `_validate_mixin_stacking`, `_validate_artifact`, and `_canonical_fields_equal_or_subset` all
  stay in `promote.py` — their test imports must NOT change.
