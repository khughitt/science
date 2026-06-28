# Remove One-Shot v2→v3 Migration Code Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the dead one-shot v2→v3 migration modules, their CLI commands, tests, and migration guide docs, while keeping the generic managed-artifact update runner and all live audit/report code.

**Architecture:** Each task removes one migrator (module + its CLI command + its tests) or performs a surgical split that keeps live code and removes only the one-shot apply path. Retained legacy-shape guards and current docs that referenced removed commands are rewritten as plain hard errors / updated prose. Work happens on branch `remove-v3-migration-code`, merged to `main`. Repo root is `~/d/science`.

**Tech Stack:** Python 3.11+, Click CLI, pytest, `uv`. Spec: `docs/plans/2026-06-20-remove-v3-migration-code-design.md`.

## Global Constraints

- **Locate code by anchor, not absolute line number.** All line numbers below are from the pre-change tree. Earlier tasks edit shared files (especially `science/src/science_tool/cli.py`), shifting later line numbers. Always find the quoted decorator/symbol/string, not the line number.
- **Test command:** pytest runs from the `science/` package directory, NOT the repo root: `cd ~/d/science/science && uv run --frozen pytest tests`. Single test: `cd ~/d/science/science && uv run --frozen pytest tests/<file>::<test> -v`. **Path rule:** test paths below are written repo-relative as `science/tests/<file>`; when invoking pytest from `science/`, strip the leading `science/` (use `tests/<file>`). `git grep` commands run from the repo root `~/d/science` exactly as written.
- **Clean break:** no compatibility shims, no retired-command stubs, no deprecation messages.
- **Keep, never touch:** `project_artifacts/migrations/` + `project_artifacts/update.py` (managed-artifact runner), `graph/aggregate_retire.py`, `graph migrate-addresses` + `migrate_addresses_direction`, `entity_migrations.audit_identifiers`, and `graph/migrate.py`'s `audit_project_sources` / `AuditRow` / `_audit_*` and `build_layered_claim_migration_report` / `LayeredClaimMigrationReport`. (Note: `write_migration_report` and `audit_project_graph` in `graph/migrate.py` *are* removed in Task 2 — they were used only by the removed `graph migrate` command.)
- **Commit after each task.** Do not include `Co-Authored-By` trailers.
- After every task: `uv run --frozen pytest science/tests` must be green before committing.

---

### Task 1: Inline the paper-dataset role-conflict predicate, then remove `paper_dataset_migration`

`graph/paper_dataset_migration.py` is one-shot except for `is_paper_dataset_role_conflict`, which `validate/checks/dataset_influence.py` uses live. Move that one-line predicate into the validation check, then delete the module and its `graph migrate-paper-datasets` command.

Do not execute this task until the `paper.datasets` migration campaign has completed for local and
downstream projects. As of the B-migration implementation, `science graph migrate-paper-datasets` is the
live migration surface, not dead v2→v3 cleanup code.

**Files:**
- Modify: `science/src/science_tool/validate/checks/dataset_influence.py` (import at line 16, call at line 165)
- Delete: `science/src/science_tool/graph/paper_dataset_migration.py`
- Modify: `science/src/science_tool/cli.py` (remove `graph migrate-paper-datasets` command ~1485-1533 and the import at line 50)
- Delete: `science/tests/test_paper_dataset_migration.py`

**Interfaces:**
- The predicate is `is_paper_dataset_role_conflict(entry: Mapping[str, Any]) -> bool` and its full body is `return entry.get("role") != "analyzed"`.

- [ ] **Step 1: Add a local predicate test in the validation suite**

Find the test module covering `dataset_influence` (`git grep -l "dataset_influence\|dataset-influence" -- 'science/tests/**'`). Add the cases to that module; if none exists, create `science/tests/validate/test_dataset_influence_role_conflict.py`. Note the path of the module you chose — call it `<CHOSEN_TEST>` for the run commands below. Add:

```python
from science_tool.validate.checks.dataset_influence import _is_paper_dataset_role_conflict


def test_role_conflict_true_when_not_analyzed():
    assert _is_paper_dataset_role_conflict({"role": "compared"}) is True
    assert _is_paper_dataset_role_conflict({}) is True


def test_role_conflict_false_when_analyzed():
    assert _is_paper_dataset_role_conflict({"role": "analyzed"}) is False
```

- [ ] **Step 2: Run the test, expect failure**

Run: `uv run --frozen pytest <CHOSEN_TEST> -v` (the module from Step 1)
Expected: FAIL — `ImportError: cannot import name '_is_paper_dataset_role_conflict'`.

- [ ] **Step 3: Inline the predicate into `dataset_influence.py`**

Remove the import line:

```python
from science_tool.graph.paper_dataset_migration import is_paper_dataset_role_conflict
```

Add a module-level private function near the top of `dataset_influence.py` (after the existing imports):

```python
def _is_paper_dataset_role_conflict(entry: Mapping[str, Any]) -> bool:
    return entry.get("role") != "analyzed"
```

Ensure `Mapping` and `Any` are imported (add `from collections.abc import Mapping` and `from typing import Any` if not already present — check the existing import block first and reuse it).

Update the call site (line ~165) from `if is_paper_dataset_role_conflict(entry):` to `if _is_paper_dataset_role_conflict(entry):`.

- [ ] **Step 4: Run the predicate test, expect pass**

Run: `uv run --frozen pytest <CHOSEN_TEST> -v` (the module from Step 1)
Expected: PASS.

- [ ] **Step 5: Remove the module, command, and import**

Delete `science/src/science_tool/graph/paper_dataset_migration.py`.

In `cli.py`, delete the import `from science_tool.graph.paper_dataset_migration import plan_paper_dataset_migration` (line 50) and the entire `@graph.command("migrate-paper-datasets")` block (decorator + `def graph_migrate_paper_datasets(...)`, ~1485-1533).

Delete `science/tests/test_paper_dataset_migration.py`.

- [ ] **Step 6: Verify no stragglers + suite green**

Run two separate checks (a single trailing-`\b` pattern would false-positive, since `is_paper_dataset_role_conflict` is a substring of the new `_is_paper_dataset_role_conflict`):
```bash
# 1. Module + command must be fully gone:
git grep -n "paper_dataset_migration\|migrate-paper-datasets" -- 'science/src/**'
# 2. No leftover use of the OLD public predicate name (filter out the new private one):
git grep -n "is_paper_dataset_role_conflict" -- 'science/src/**' | grep -v "_is_paper_dataset_role_conflict"
```
Expected: both produce no output. (Check 2's filter drops the inlined `_is_paper_dataset_role_conflict`, which is the only allowed match.)

Run: `uv run --frozen pytest science/tests`
Expected: PASS.

Run: `uv run --frozen python -m science_tool.cli graph --help`
Expected: lists graph subcommands, no `migrate-paper-datasets`.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor: inline paper-dataset role-conflict check, remove paper_dataset migrator"
```

---

### Task 2: Remove the identifier-migration paths (`graph migrate` + `entities migrate-identifiers`)

Two one-shot identifier migrators exist. `graph migrate` (cli.py:1417) drives the project-id rewrite functions in `graph/migrate.py`; `entities migrate-identifiers` (cli.py:281) drives `entity_migrations.migrate_identifiers`. Remove both commands and the apply-only code, **keeping** `audit_project_sources`, `build_layered_claim_migration_report`, and `audit_identifiers`.

**Files:**
- Modify: `science/src/science_tool/cli.py` (remove `graph migrate` ~1417-1483, `entities migrate-identifiers` ~281-289, import edits at lines 38 and 42-49, guard text at line 522)
- Modify: `science/src/science_tool/graph/migrate.py` (remove `audit_project_graph`, `rewrite_project_ids_in_sources`, `preview_project_id_rewrites`, `write_local_sources`, `write_migration_report`, and helpers used only by them — e.g. `_merge_entities`)
- Modify: `science/src/science_tool/entity_migrations.py` (remove `migrate_identifiers`, `_existing_canonical_ids`, `_write_frontmatter_id`)
- Modify: `science/tests/test_entity_migrations.py` (drop `migrate_identifiers` cases)
- Modify/Delete: `science/tests/test_graph_migrate.py` (see Step 7)

**Interfaces:**
- Kept and still importable after this task: `entity_migrations.audit_identifiers`, `graph.migrate.audit_project_sources`, `graph.migrate.AuditRow`, `graph.migrate.build_layered_claim_migration_report`, `graph.migrate.write_migration_report` is **removed** (only `graph migrate` used it — confirm in Step 4).

- [ ] **Step 1: Confirm removable-symbol importers**

Run:
```bash
for f in audit_project_graph rewrite_project_ids_in_sources preview_project_id_rewrites write_local_sources write_migration_report migrate_identifiers _existing_canonical_ids _write_frontmatter_id; do
  echo "--- $f ---"; git grep -ln "\b$f\b" -- 'science/src/**' | grep -v "/tests/"
done
```
Expected: each prints only `cli.py` and/or its own defining module (`graph/migrate.py`, `entity_migrations.py`). If any other live module appears, STOP and reassess — that symbol is not dead.

- [ ] **Step 2: Edit cli.py imports**

Change line 38 from:
```python
from science_tool.entity_migrations import audit_identifiers, migrate_identifiers
```
to:
```python
from science_tool.entity_migrations import audit_identifiers
```

Delete the entire `graph.migrate` import block (lines 42-49):
```python
from science_tool.graph.migrate import (
    audit_project_graph,
    build_layered_claim_migration_report,
    preview_project_id_rewrites,
    rewrite_project_ids_in_sources,
    write_local_sources,
    write_migration_report,
)
```
(None of these symbols are used elsewhere in `cli.py` — they were only used by the two commands removed in Step 3. `build_layered_claim_migration_report` stays *defined* in `graph/migrate.py` for the health check; `cli.py` simply no longer imports it. Confirm with `git grep -n "build_layered_claim_migration_report" -- science/src/science_tool/cli.py` returning nothing after Step 3.)

- [ ] **Step 3: Remove the two CLI commands and fix the guard**

In `cli.py`:
- Delete the `@graph.command("migrate")` block (decorator + `def graph_migrate(...)`, ~1417-1483).
- Delete the `@entities_group.command("migrate-identifiers")` block (decorator + options + `def entities_migrate_identifiers_command(...)`, ~281-289).
- Rewrite the guard at line ~519-523. Change:
```python
        if version is None or version < 3:
            raise click.ClickException(
                f"promotion needs an `entities/` owner root; this project is layout_version {version} — "
                "complete the v2->v3 migration (`science entities migrate`) first."
            )
```
to:
```python
        if version is None or version < 3:
            raise click.ClickException(
                f"promotion needs an `entities/` owner root, but this project is layout_version {version}. "
                "This Science version supports layout_version 3 only; the v2 layout is no longer supported."
            )
```

- [ ] **Step 4: Remove the dead functions from `graph/migrate.py`**

Delete the definitions of `audit_project_graph`, `rewrite_project_ids_in_sources`, `preview_project_id_rewrites`, `write_local_sources`, and `write_migration_report`. Then delete any private helper (e.g. `_merge_entities`) that Step 1 / a follow-up `git grep` shows is now unreferenced. Keep `audit_project_sources`, `AuditRow`, all `_audit_*`, `build_layered_claim_migration_report`, `LayeredClaimMigrationReport`, and `LayeredClaimMigrationRow`.

After editing, confirm nothing dangles:
```bash
git grep -n "_merge_entities\|write_migration_report\|audit_project_graph" -- 'science/src/**'
```
Expected: no output (or only commented/unrelated). If a helper is still referenced by kept code, leave it.

- [ ] **Step 5: Trim `entity_migrations.py`**

Delete `migrate_identifiers` (lines 29-68), `_existing_canonical_ids` (71-79), and `_write_frontmatter_id` (103-110). Keep `CANONICAL_ID_PATTERN`, `audit_identifiers`, `_markdown_paths`, `_frontmatter`, and the `re`/`yaml`/`Path`/`Any` imports (still used by the kept code).

- [ ] **Step 6: Trim `test_entity_migrations.py`**

Open `science/tests/test_entity_migrations.py`. Remove every test that calls `migrate_identifiers` and update the import line `from science_tool.entity_migrations import audit_identifiers, migrate_identifiers` to `from science_tool.entity_migrations import audit_identifiers`. Keep the `audit_identifiers` tests.

- [ ] **Step 7: Handle `test_graph_migrate.py`**

Inspect it: `uv run --frozen pytest science/tests/test_graph_migrate.py -v` and read the file. If every test exercises the removed `graph migrate` command / id-rewrite functions, delete the file. If any test exercises retained behavior (`audit_project_sources`, layered-claim report), keep those tests and delete only the removed-command cases.

- [ ] **Step 8: Suite green + CLI smoke**

Run: `uv run --frozen pytest science/tests`
Expected: PASS.

Run:
```bash
uv run --frozen python -m science_tool.cli graph --help
uv run --frozen python -m science_tool.cli entities --help
```
Expected: no `migrate` under `graph`, no `migrate-identifiers` under `entities` (`migrate-addresses` and `migrate-model`/`migrate-tags` still present — they are removed in later tasks).

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "refactor: remove one-shot identifier migration (graph migrate, entities migrate-identifiers)"
```

---

### Task 3: Remove `entity_layout_migration` (`entities migrate`) + fix layout-version guard

**Files:**
- Delete: `science/src/science_tool/entity_layout_migration.py`
- Modify: `science/src/science_tool/cli.py` (remove `@entities_group.command("migrate")` block ~397-413)
- Modify: `science/src/science_tool/validate/checks/manifest.py` (guard at line ~31-35)
- Delete: `science/tests/test_entity_layout_migration.py`, `science/tests/test_migrate_local_kinds_integration.py`

- [ ] **Step 1: Confirm no live importers**

Run: `git grep -ln "entity_layout_migration" -- 'science/src/**' | grep -v "/tests/"`
Expected: only `cli.py` (the `entities migrate` command imports it locally inside the function). No other live module.

- [ ] **Step 2: Update the manifest guard test, then the message**

In the test module for the manifest check (find via `git grep -ln "layout_version must be" -- 'science/tests/**'`), update the asserted message text to the new wording. Then change `validate/checks/manifest.py` (line ~34) from:
```python
            "science.yaml: layout_version must be >= 3 — run `science entities migrate`",
```
to:
```python
            "science.yaml: layout_version must be >= 3; the v2 layout is no longer supported by this Science version.",
```

- [ ] **Step 3: Remove the command and module**

Delete the `@entities_group.command("migrate")` block in `cli.py` (decorator + `def entities_migrate_command(...)`, including the local `from science_tool.entity_layout_migration import migrate_layout`).

Delete `science/src/science_tool/entity_layout_migration.py`, `science/tests/test_entity_layout_migration.py`, and `science/tests/test_migrate_local_kinds_integration.py`.

- [ ] **Step 4: Verify + suite green**

Run:
```bash
git grep -n "entity_layout_migration\|entities migrate\b\|migrate_layout" -- 'science/src/**'
uv run --frozen pytest science/tests
uv run --frozen python -m science_tool.cli entities --help
```
Expected: first grep empty; suite PASS; `entities` help has no `migrate` command.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: remove entity-layout v2->v3 migrator and entities migrate command"
```

---

### Task 4: Remove `peers_migrate` (`peers migrate`) + fix `science.yaml` guard

**Files:**
- Delete: `science/src/science_tool/peers_migrate.py`
- Modify: `science/src/science_tool/peers_cli.py` (remove `@peers_group.command("migrate")` block ~121-152)
- Modify: `science/src/science_tool/project_config.py` (guard at line ~128-132)
- Modify: `docs/federation.md` (remove `science peers migrate` references at lines ~116, ~123, ~130)
- Delete: `science/tests/test_peers_migrate.py`
- Modify: `science/tests/test_peers_cli.py` (remove `test_peers_migrate*` cases)

- [ ] **Step 1: Confirm importers**

Run: `git grep -ln "peers_migrate" -- 'science/src/**' | grep -v "/tests/"`
Expected: only `peers_cli.py`.

- [ ] **Step 2: Fix the project_config guard**

In `project_config.py`, change (line ~128-132):
```python
            if illegal:
                raise ValueError(
                    f"science.yaml uses removed field(s) {illegal!r}. "
                    "Run `science peers migrate` to migrate to `peers:`."
                )
```
to:
```python
            if illegal:
                raise ValueError(
                    f"science.yaml uses removed field(s) {illegal!r}. "
                    "Use `peers:` instead; the legacy parent/children fields are no longer supported."
                )
```

If a test asserts the old message (`git grep -ln "Run .science peers migrate" -- 'science/tests/**'`), update it to the new text.

- [ ] **Step 3: Remove command, module, tests**

Delete the `@peers_group.command("migrate")` block in `peers_cli.py` (decorator + options + `def peers_migrate(...)`, including the local `from science_tool.peers_migrate import MigrationError, migrate_project`).

Delete `science/src/science_tool/peers_migrate.py` and `science/tests/test_peers_migrate.py`.

In `science/tests/test_peers_cli.py`, delete the migration test functions (`test_peers_migrate_single`, `test_peers_migrate_dry_run`, `test_peers_migrate_all_*`, `test_peers_migrate_single_error_is_wrapped_as_cli_error` — everything from ~line 583 to the end of those functions). Also remove the now-unused `_legacy_child_project_roots` helper in `peers_cli.py` if it was only used by the removed command (`git grep -n "_legacy_child_project_roots" -- 'science/src/**'`).

- [ ] **Step 4: Update `docs/federation.md`**

In the `## CLI` code block (line ~116), delete the `science peers migrate` line so it lists only `list` / `check` / `show <peer-id>`. Delete the bullet (line ~123):
```markdown
- `science peers migrate` converts old relationship fields to `peers:`.
```
In `## Historical Context` (line ~128-131), change:
```markdown
commands described a tree-shaped relationship and are no longer current
guidance. Run `science peers migrate` for projects that still carry those
legacy fields.
```
to:
```markdown
commands described a tree-shaped relationship and are no longer supported.
Use `peers:` directly; the legacy parent/children fields are not migrated
automatically.
```

- [ ] **Step 5: Verify + suite green**

Run:
```bash
git grep -n "peers_migrate\|peers migrate\b" -- 'science/src/**' docs/federation.md
uv run --frozen pytest science/tests/test_peers_cli.py
uv run --frozen pytest science/tests
uv run --frozen python -m science_tool.cli peers --help
```
Expected: grep empty; tests PASS; no `migrate` under `peers`.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor: remove peers parent/children migrator and peers migrate command"
```

---

### Task 5: Remove `datapackage_migrate` (`data-package migrate`) + fix data-package guards

**Files:**
- Delete: `science/src/science_tool/datapackage_migrate.py`
- Modify: `science/src/science_tool/cli.py` (remove `@data_package_group.command(name="migrate")` block ~5581-5600)
- Modify: `science/src/science_tool/graph/materialize.py` (guard ~371-376; docstring ~455-460)
- Modify: `science/src/science_tool/graph/health.py` (message at line ~1614)
- Delete: `science/tests/test_data_package_migrate.py`, `science/tests/test_data_package_migrate_e2e.py`

- [ ] **Step 1: Confirm importers**

Run: `git grep -ln "datapackage_migrate" -- 'science/src/**' | grep -v "/tests/"`
Expected: only `cli.py`.

- [ ] **Step 2: Fix the materialize guard + docstring**

In `graph/materialize.py`, change the `raise RuntimeError(...)` (the unmigrated data-package preflight, ~371-376) from:
```python
        raise RuntimeError(
            f"unmigrated data-package entities: {slugs}. "
            f"Run `science data-package migrate <slug>` to split each into "
            f"derived dataset(s) + research-package."
        )
```
to:
```python
        raise RuntimeError(
            f"unmigrated data-package entities: {slugs}. "
            f"Legacy data-package entities are no longer supported; split each into "
            f"derived dataset(s) + a research-package by hand."
        )
```

Update the `materialize_graph` docstring (~455-460) to drop the command name:
```python
    When `strict=True` (the default), the project-root preflight raises
    RuntimeError if any legacy (unmigrated) data-package entities remain;
    the v2 data-package layout is no longer supported.
```

- [ ] **Step 3: Fix the health message**

In `graph/health.py` (~line 1614), change:
```python
                        "message": "unmigrated data-package; run `science data-package migrate` to split into derived dataset(s) + research-package",
```
to:
```python
                        "message": "unmigrated data-package; the legacy data-package layout is no longer supported — split into derived dataset(s) + research-package by hand",
```

If tests assert these message strings, update them (`git grep -ln "data-package migrate" -- 'science/tests/**'`).

- [ ] **Step 4: Remove command, module, tests**

Delete the `@data_package_group.command(name="migrate")` block in `cli.py` (decorator + `def data_package_migrate_cmd(...)`, including the local `from science_tool.datapackage_migrate import ...`).

Delete `science/src/science_tool/datapackage_migrate.py`, `science/tests/test_data_package_migrate.py`, and `science/tests/test_data_package_migrate_e2e.py`.

- [ ] **Step 5: Verify + suite green**

Run:
```bash
git grep -n "datapackage_migrate\|data-package migrate\b" -- 'science/src/**'
uv run --frozen pytest science/tests
uv run --frozen python -m science_tool.cli data-package --help
```
Expected: grep empty; suite PASS; no `migrate` under `data-package`.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor: remove data-package migrator and data-package migrate command"
```

---

### Task 6: Remove `refs_migrate` (`refs migrate-paper`)

**Files:**
- Delete: `science/src/science_tool/refs_migrate.py`
- Modify: `science/src/science_tool/refs_cli.py` (remove import block lines 14-19 and `@refs_group.command("migrate-paper")` block ~192-233)
- Delete: `science/tests/test_refs_migrate_cli.py`, `science/tests/test_refs_migrate_paper.py`

- [ ] **Step 1: Confirm importers**

Run: `git grep -ln "refs_migrate" -- 'science/src/**' | grep -v "/tests/"`
Expected: only `refs_cli.py`.

- [ ] **Step 2: Remove the command, its import, the module, and tests**

In `refs_cli.py`, delete the import block (lines 14-19):
```python
from science_tool.refs_migrate import (
    apply_rewrites,
    check_git_clean,
    render_diff,
    scan_project,
)
```
and the `@refs_group.command("migrate-paper")` block (decorator + `def migrate_paper(...)`, ~192-233 to end of file).

Delete `science/src/science_tool/refs_migrate.py`, `science/tests/test_refs_migrate_cli.py`, `science/tests/test_refs_migrate_paper.py`.

- [ ] **Step 3: Verify + suite green**

Run:
```bash
git grep -n "refs_migrate\|migrate-paper\b" -- 'science/src/**'
uv run --frozen pytest science/tests
uv run --frozen python -m science_tool.cli refs --help
```
Expected: grep empty; suite PASS; no `migrate-paper` under `refs`.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor: remove refs migrate-paper migrator"
```

---

### Task 7: Remove `tasks_id_migration` (`tasks migrate-ids`)

**Files:**
- Delete: `science/src/science_tool/tasks_id_migration.py`
- Modify: `science/src/science_tool/cli.py` (remove `@tasks.command("migrate-ids")` block ~3618-end-of-handler)
- Delete: `science/tests/test_tasks_id_migration.py`

- [ ] **Step 1: Confirm importers**

Run: `git grep -ln "tasks_id_migration" -- 'science/src/**' | grep -v "/tests/"`
Expected: only `cli.py`.

- [ ] **Step 2: Remove command, module, test**

Delete the `@tasks.command("migrate-ids")` block in `cli.py` (decorator + `def tasks_migrate_ids(...)`, including its local `from science_tool.tasks_id_migration import ...`).

Delete `science/src/science_tool/tasks_id_migration.py` and `science/tests/test_tasks_id_migration.py`.

- [ ] **Step 3: Verify + suite green**

Run:
```bash
git grep -n "tasks_id_migration\|migrate-ids\b" -- 'science/src/**'
uv run --frozen pytest science/tests
uv run --frozen python -m science_tool.cli tasks --help
```
Expected: grep empty; suite PASS; no `migrate-ids` under `tasks`.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor: remove tasks id migrator and tasks migrate-ids command"
```

---

### Task 8: Remove `graph/project_model_migration` (`graph migrate-model`)

**Files:**
- Delete: `science/src/science_tool/graph/project_model_migration.py`
- Modify: `science/src/science_tool/cli.py` (remove `@graph.command("migrate-model")` block ~1534-1553)
- Delete: `science/tests/test_project_model_migration.py`

- [ ] **Step 1: Confirm importers**

Run: `git grep -ln "project_model_migration" -- 'science/src/**' | grep -v "/tests/"`
Expected: only `cli.py`.

- [ ] **Step 2: Remove command, module, test**

Delete the `@graph.command("migrate-model")` block in `cli.py` (decorator + `def graph_migrate_model(...)`, including its local `from science_tool.graph.project_model_migration import migrate_entity_sources`).

Delete `science/src/science_tool/graph/project_model_migration.py` and `science/tests/test_project_model_migration.py`.

- [ ] **Step 3: Verify + suite green**

Run:
```bash
git grep -n "project_model_migration\|migrate-model\b" -- 'science/src/**'
uv run --frozen pytest science/tests
uv run --frozen python -m science_tool.cli graph --help
```
Expected: grep empty; suite PASS; no `migrate-model` under `graph`.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor: remove project-model migrator and graph migrate-model command"
```

---

### Task 9: Remove `graph/tags_migration` (`graph migrate-tags`)

**Files:**
- Delete: `science/src/science_tool/graph/tags_migration.py`
- Modify: `science/src/science_tool/cli.py` (remove `@graph.command("migrate-tags")` block ~1582-1610)
- Delete: `science/tests/test_tags_migration.py`

- [ ] **Step 1: Confirm importers**

Run: `git grep -ln "tags_migration" -- 'science/src/**' | grep -v "/tests/"`
Expected: only `cli.py`.

- [ ] **Step 2: Remove command, module, test**

Delete the `@graph.command("migrate-tags")` block in `cli.py` (decorator + `def graph_migrate_tags(...)`, including its local `from science_tool.graph.tags_migration import migrate_tags_to_related`).

Delete `science/src/science_tool/graph/tags_migration.py` and `science/tests/test_tags_migration.py`.

- [ ] **Step 3: Verify + suite green**

Run:
```bash
git grep -n "tags_migration\|migrate-tags\b" -- 'science/src/**'
uv run --frozen pytest science/tests
uv run --frozen python -m science_tool.cli graph --help
```
Expected: grep empty; suite PASS; no `migrate-tags` under `graph`.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor: remove tags migrator and graph migrate-tags command"
```

---

### Task 10: Remove `aspects/migrate` (`aspects migrate`) + its now-empty CLI group

`aspects/cli.py` contains only the `migrate` command, so removing it empties the whole `aspects` CLI group; delete the file and its registration.

**Files:**
- Delete: `science/src/science_tool/aspects/migrate.py`
- Delete: `science/src/science_tool/aspects/cli.py` (only the migrate command lives here)
- Modify: `science/src/science_tool/cli.py` (remove import at line 13 and `main.add_command(aspects_group)` at line 233)
- Delete: `science/tests/test_aspects_migrate.py`
- Delete or trim: `science/tests/test_aspects_cli.py`

- [ ] **Step 1: Confirm `aspects/cli.py` has only the migrate command, and importers**

Run:
```bash
git grep -n "@aspects_group.command" -- science/src/science_tool/aspects/cli.py
git grep -ln "aspects.migrate\|from science_tool.aspects.migrate\|aspects.cli\|aspects_group" -- 'science/src/**' | grep -v "aspects/migrate.py" | grep -v "aspects/cli.py"
```
Expected: exactly one `@aspects_group.command("migrate")`; the only external references are `cli.py` (import line 13, registration line 233). If `aspects/cli.py` has other commands, STOP — instead remove just the migrate command and keep the file.

- [ ] **Step 2: Remove registration and import in cli.py**

Delete line 13 `from science_tool.aspects.cli import aspects_group` and line 233 `main.add_command(aspects_group)`.

- [ ] **Step 3: Delete the files**

Delete `science/src/science_tool/aspects/cli.py`, `science/src/science_tool/aspects/migrate.py`, and `science/tests/test_aspects_migrate.py`.

For `science/tests/test_aspects_cli.py`: inspect it. If every test targets the migrate command (`test_migrate_group_registered`, `test_migrate_dry_run_prints_plan_without_writing`, `test_migrate_apply_rewrites_file`), delete the whole file. Otherwise remove only the `test_migrate_*` functions.

- [ ] **Step 4: Verify + suite green**

Run:
```bash
git grep -n "aspects.migrate\|aspects_group\|aspects migrate\b" -- 'science/src/**'
uv run --frozen pytest science/tests
uv run --frozen python -m science_tool.cli --help
```
Expected: grep empty; suite PASS; top-level help has no `aspects` group.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: remove aspects task migrator and empty aspects CLI group"
```

---

### Task 11: Trim the scan-guard allowlist, delete the dead script and migration guide docs

This task runs after all module deletions (Tasks 1-10), so the entity-scan guard allowlist can be reconciled in one place.

**Files:**
- Modify: `science/tests/test_entity_scan_guard.py` (remove deleted-module entries from `ALLOWLIST`)
- Delete: `scripts/migrate_downstream_conventions.py`
- Delete: `docs/entity-layout-migration-guide.md`
- Delete: `docs/migration/2026-05-26-assembly-identity.md`
- Delete: `docs/migration/2026-05-27-gene-crosswalk-identity.md`
- Delete: `docs/migration/2026-05-27-protein-crosswalk-identity.md`
- Delete: `docs/audits/2026-06-06-layout-v3-migration-readiness-audit.md`
- **Keep:** `docs/migration/2026-05-19-validate-local-sh-porting-guide.md`, `docs/migration/managed-artifacts-template.md`

- [ ] **Step 1: Trim the entity-scan guard allowlist**

In `science/tests/test_entity_scan_guard.py`, the `ALLOWLIST: set[str]` names recursive-markdown scanners. Tasks 1-10 deleted six of them. Remove these entries:
```python
    "graph/paper_dataset_migration.py",
    "graph/project_model_migration.py",
    "graph/tags_migration.py",
    "entity_layout_migration.py",           # legacy migration roots
```
and remove `"refs_migrate.py"` and `"datapackage_migrate.py"` from the combined line:
```python
    "prose.py", "prose_lint.py", "markers.py", "refs.py", "refs_migrate.py",
    "datapackage_migrate.py", "skills_lint/lint.py", "cli.py",
```
so it reads:
```python
    "prose.py", "prose_lint.py", "markers.py", "refs.py",
    "skills_lint/lint.py", "cli.py",
```
Keep `"graph/migrate.py"` and `"graph/materialize.py"` (both retained). Run `uv run --frozen pytest science/tests/test_entity_scan_guard.py -v` — expected PASS (the deleted files no longer appear in the scanner inventory, so dropping them from the allowlist keeps it exact).

- [ ] **Step 2: Confirm the script has no code importers (historical-doc references are expected)**

Run: `git grep -ln "migrate_downstream_conventions" -- 'science/src/**' 'science/tests/**'`
Expected: no output.

Note: `docs/audits/downstream-project-conventions/synthesis-shape-investigation-2026-04-25.md` and files under `docs/plans/**` cite this script as a historical record of past work. Those are intentionally left as-is (the citation documents what was done at the time); do not edit or delete them.

- [ ] **Step 3: Confirm the kept docs are still referenced and the deleted ones are not**

Run:
```bash
git grep -n "2026-05-19-validate-local-sh-porting-guide" -- 'science/src/**'
git grep -n "entity-layout-migration-guide\|assembly-identity\|crosswalk-identity\|layout-v3-migration-readiness-audit" -- 'science/src/**' ':!docs/**' ':!archive/**'
```
Expected: first prints the live references in `validate/runner.py` and `project_artifacts/registry.yaml` (proves the porting guide must stay); second prints nothing (proves the deletions are safe).

`managed-artifacts-template.md` is retained by decision (managed-artifact authoring doc), not by source consumption — it has **no** `science/src` references, and that is expected, not suspicious. Do not delete it.

- [ ] **Step 4: Delete**

```bash
git rm scripts/migrate_downstream_conventions.py \
  docs/entity-layout-migration-guide.md \
  docs/migration/2026-05-26-assembly-identity.md \
  docs/migration/2026-05-27-gene-crosswalk-identity.md \
  docs/migration/2026-05-27-protein-crosswalk-identity.md \
  docs/audits/2026-06-06-layout-v3-migration-readiness-audit.md
```

- [ ] **Step 5: Verify suite still green (docs/script removal can break doc-driven tests)**

Run: `uv run --frozen pytest science/tests`
Expected: PASS. If a test references a deleted doc path, update it to point at retained docs or remove the stale assertion.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore: trim scan-guard allowlist; remove v3 migration guides and dead downstream-conventions script"
```

---

### Task 12: Final validation sweep

**Files:** none (verification only).

- [ ] **Step 1: No removed module/symbol references remain**

Run (from the spec's validation block):
```bash
git grep -n "entity_layout_migration\|datapackage_migrate\|peers_migrate\|refs_migrate\|tasks_id_migration\|project_model_migration\|tags_migration\|aspects\.migrate\|migrate_identifiers\|rewrite_project_ids_in_sources\|plan_paper_dataset_migration" -- 'science/src/**'
```
Expected: no output.

- [ ] **Step 2: Kept symbols still resolve**

Run:
```bash
uv run --frozen python -c "from science_tool.graph.migrate import audit_project_sources, build_layered_claim_migration_report, AuditRow; from science_tool.entity_migrations import audit_identifiers; print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: No retained source OR current docs tells users to run a removed command**

Run (note: `docs/plans/**` and `archive/**` are excluded as historical record):
```bash
git grep -n "science peers migrate\|science entities migrate\|migrate-identifiers\|data-package migrate\|aspects migrate\|migrate-paper\b\|graph migrate\b\|migrate-model\|migrate-tags\|tasks migrate-ids" \
  -- 'science/src/**' 'docs/**' ':!docs/plans/**'
```
Expected: no output. (If a hit appears in a kept doc such as `docs/federation.md`, update that doc the same way as the source guards.)

- [ ] **Step 3b: Scan-guard allowlist has no dangling deleted-file names**

Run:
```bash
git grep -n "paper_dataset_migration\|project_model_migration\|tags_migration\|entity_layout_migration\|refs_migrate\|datapackage_migrate" -- science/tests/test_entity_scan_guard.py
```
Expected: no output (Task 11 Step 1 trimmed them).

- [ ] **Step 4: Deleted guides gone, kept guides present**

Run:
```bash
git grep -n "entity-layout-migration-guide\|assembly-identity\|crosswalk-identity\|layout-v3-migration-readiness-audit" -- ':!archive/**' ':!docs/plans/**'
ls docs/migration/
```
Expected: first empty; second lists exactly `2026-05-19-validate-local-sh-porting-guide.md` and `managed-artifacts-template.md`.

- [ ] **Step 5: Full suite + CLI smoke + a real-project audit path**

Run:
```bash
uv run --frozen pytest science/tests
uv run --frozen python -m science_tool.cli --help
uv run --frozen python -m science_tool.cli graph --help
uv run --frozen python -m science_tool.cli entities --help
```
Expected: suite PASS; `graph` still shows `migrate-addresses` (kept) but no `migrate`/`migrate-model`/`migrate-tags`/`migrate-paper-datasets`; `entities` shows no `migrate`/`migrate-identifiers`.

On a real v3 project (pick one from the working tree), confirm the audit/build paths still work:
```bash
uv run --frozen python -m science_tool.cli validate --help
# in a project dir: science validate && science graph build
```

- [ ] **Step 6: Finish the branch**

Use the `superpowers:finishing-a-development-branch` skill to merge `remove-v3-migration-code` into `main` (the user chose: one branch, merge to main). Do not push unless the user asks.

---

## Notes on retained-but-similarly-named code (do NOT remove)

- `project_artifacts/migrations/` (`__init__.py`, `bash.py`, `python.py`, `transaction.py`) and `project_artifacts/update.py` — managed-artifact update runner. Tests `test_update_with_migration.py`, `test_update_no_migration.py`, `test_migration_runner.py`, `test_migration_bash.py`, `test_migration_python.py` stay.
- `graph migrate-addresses` + `graph/store/mutations.py::migrate_addresses_direction` + its `store/__init__.py` export + the `test_graph_cli.py` case — out of scope per the approved spec.
- `graph/aggregate_retire.py` + `test_aggregate_retire_curie_migration.py` — live aggregate-triage.
- `test_graph_migrate_identity_audit.py` and `test_layered_claim_migration.py` — cover retained audit/report code.
