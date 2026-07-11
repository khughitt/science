# Convergence Phase 4 — Finish the CLI Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `science/src/science_tool/cli.py` to a registration-only entrypoint by moving all 22 inline `@main.group`/`@main.command` definitions into per-domain modules, pushing 5 business-logic clusters *down* out of the CLI layer as they move, and landing an AST guard that keeps `cli.py` thin.

**Architecture:** Each inline group becomes a module-level `@click.group(...)`/`@click.command(...)` in `science_tool/<domain>_cli.py` (or an existing package's `cli.py`), exposing a `<name>_group`/`<name>_command` symbol that `cli.py` registers with a single `main.add_command(...)` line — exactly the pattern the 24 already-extracted groups follow (`cli.py:249-272`). Extraction is behavior-preserving relocation; five commands additionally get their embedded domain logic pushed into the service/store layer they belong to. A final guard test fails if `cli.py` regrows an inline command body or exceeds its line budget.

**Tech Stack:** Python 3, Click, pytest, `ast` (guard). Packages: run CLI tests from `science/` with `uv run --frozen pytest`; lint with `uv run ruff check`, types with `uv run pyright`.

## Global Constraints

Every task's requirements implicitly include this section. Values copied verbatim from `docs/plans/2026-07-10-half-applied-pattern-convergence-design.md` (Phase 4 + Test strategy) and the two prior phase plans.

- **Behavior-preserving.** No command's behavior, options, help text, arguments, exit codes, or output may change. Relocation only, except the five explicit push-downs — and those preserve observable behavior too.
- **Byte-identical `--format json` stdout.** JSON output must stay byte-for-byte identical. Run the snapshot suite (`-m snapshot`, excluded by default) at *each* commit, not just at the end.
- **JSON-only on stdout.** Human diagnostics go to stderr (`err=True`); `docs/conventions/cli-behavior.md` governs. Do not move an `err=True` to stdout or vice-versa.
- **No import back from `cli.py`.** An extracted module MUST NOT `from science_tool.cli import ...`. `cli.py` imports the group from the module; the reverse edge is a circular import. Group-exclusive helpers move *with* the group; genuinely shared helpers are imported from their non-`cli` home (or promoted to one).
- **`science_model` must not import `science_tool`.** Unchanged by this phase; do not introduce such an edge.
- **Business logic moves down; CLI adapters consolidate sideways.** Tasks 3 (benchmark review-file), 4 (graph-build registration), 5 (dataset store reaches), and 6 (health rollup) relocate genuine domain logic into the service/store layer, not verbatim into the new CLI module. Task 1 is different: the typed-entity helpers — including `build_origin_frontmatter`, which raises `click.BadParameter` on a bad `--origin` — are CLI *adapters*; they all consolidate into one CLI-support module (`typed_entity_cli.py`). Task 1 does **not** touch `entities.py`; do not push `click`/output code into any domain module.
- **Do NOT rename `dataset` vs `datasets`.** The two sibling groups keep their CLI-invocation names (`science dataset …`, `science datasets …`) — renaming is a CLI-contract change, out of scope. Disambiguate only by *module* name and record the collision as a follow-up (Task 12).
- **Guard is written LAST, against the migrated tree** (Task 12), keyed on AST structure, not text. A guard authored from this document rather than from the migrated code will out-scope the migration and land red.
- **The 95 `raise click.ClickException(str(exc))` wrappers stay as-is.** They are the correct CLI-layer job (domain error → exit code); do not factor them into a decorator.
- **No AI-attribution trailers** on commits (no `Co-Authored-By`, no `🤖 Generated with…`). No `Unified` prefix on new symbols. No "legacy"/"compatibility" shims. Composition over inheritance; explicit over defensive; fail early.

---

## File Structure

The 24 groups already extracted register at `cli.py:249-272`. The 22 inline groups map to these destinations (final names — the plan locks these in). Line spans are current-tree (post-Phase-3), largest first.

| # | Inline symbol (cli.py) | group name | span | Destination module | Exposed symbol |
|---|---|---|---|---|---|
| benchmark | `benchmark_group` @5499 | `benchmark` | ~1258 | `benchmark_cli.py` (new flat, sibling of `benchmark_opportunities.py`) | `benchmark_group` |
| graph | `graph` @1575 | (default `graph`) | ~1164 | `graph/cli.py` (new) | `graph_group` |
| tasks | `tasks` @3623 | (default `tasks`) | ~687 | `tasks_cli.py` (new flat) | `tasks_group` |
| dataset | `dataset_group` @6757 | `dataset` | ~668 | `datasets/cli.py` (new, inside existing adapters pkg) | `dataset_group` |
| health | `health_command` @4585 | (`@main.command`) | ~433 | `graph/health_cli.py` (new) | `health_command` |
| entity | `entity_group` @483 | `entity` | ~364 | `entities_cli.py` (new flat) | `entity_group` |
| explore-ideas | `explore_ideas_group` @1239 | `explore-ideas` | ~336 | `explore_ideas_cli.py` (new flat) | `explore_ideas_group` |
| datasets | `datasets` @3238 | (default `datasets`) | ~385 | `datasets_discovery_cli.py` (new flat) | `datasets_group` |
| inquiry | `inquiry` @2858 | (default `inquiry`) | ~380 | `inquiry_cli.py` (new flat) | `inquiry_group` |
| project | `project` @4310 | (default `project`) | ~275 | `project_cli.py` (new flat) | `project_group` |
| entities | `entities_group` @275 | `entities` | ~208 | `entities_inventory_cli.py` (new flat) | `entities_group` |
| questions | `question` @5127 | `questions` | ~166 | `questions_cli.py` (new flat) | `question_group` |
| belief | `belief_group` @2739 | `belief` | ~119 | `belief_cli.py` (new flat) | `belief_group` |
| interpretations | `interpretation_group` @1180 | `interpretations` | ~59 | `interpretations_cli.py` (new flat) | `interpretation_group` |
| propositions | `proposition_group` @847 | `propositions` | ~59 | `propositions_cli.py` (new flat) | `proposition_group` |
| discussions | `discussion_group` @1121 | `discussions` | ~59 | `discussions_cli.py` (new flat) | `discussion_group` |
| evidence-lines | `evidence_line_group` @906 | `evidence-lines` | ~131 | `evidence_lines_cli.py` (new flat) | `evidence_line_group` |
| hypotheses | `hypothesis_group` @1037 | `hypotheses` | ~84 | `hypotheses_cli.py` (new flat) | `hypothesis_group` |
| bib | `bib` @5293 | (default `bib`) | ~76 | `bib_cli.py` (new flat) | `bib_group` |
| sync | `sync` @5369 | (default `sync`) | ~130 | `sync_cli.py` (new flat) | `sync_group` |
| paper | `paper` @5071 | `paper` | ~56 | `paper_cli.py` (new flat) | `paper_group` |
| paper-fetch | `paper_fetch` @5018 | (`@main.command`) | ~53 | `paper_cli.py` (joins `paper`) | `paper_fetch_command` |

**Shared CLI adapter layer (Task 1 moves this first, out of band) → a new CLI-support module `science_tool/typed_entity_cli.py`.** The full set:
- `_create_typed_entity`, `_show_typed_entity`, `_list_typed_entities`, `_ENTITY_LIST_TITLES` (`cli.py:1416-1484`) — the per-kind adapters, used by the six entity-kind groups;
- the two shared emit adapters `_emit_entity_show` and `_emit_entity_warnings` → **public** `emit_entity_show` / `emit_entity_warnings` (drop the `_`): they are consumed *beyond* the typed cluster — `emit_entity_warnings` by `entity create` (`cli.py:533`) and `explore-ideas apply` (`cli.py:1302`), `emit_entity_show` by `entity show` (`cli.py:1500`+) — so they must be a public part of this module's API;
- the show-path private sub-helpers `emit_entity_show` calls (all `cli.py`-only, used nowhere else): `_entity_show_payload`, `_print_entity_field`, `_print_entity_refs_field`, `_frontmatter_string_list` (`cli.py:1487`+) — move with `emit_entity_show`, stay `_`-prefixed;
- `_build_origin_frontmatter` (`cli.py:1398`) → public `build_origin_frontmatter`. It is **not** domain-pure: it catches `ValidationError` and raises `click.BadParameter` on a malformed `--origin`, so it is a CLI adapter and belongs here, next to the others — **not** in `entities.py`.

These are all CLI adapters (raise `click.ClickException`/`click.BadParameter`, write stdout, call `emit_query_rows`/Rich), so they must NOT land in a domain module — polluting `entities.py` with `click` would be the same defect Phase 6's domain-purity guard bans. Consumers span most of the extracted groups: the per-kind adapters by `propositions`/`evidence-lines`/`hypotheses`/`discussions`/`interpretations`/`questions`; `emit_entity_show`/`emit_entity_warnings` by `entity`/`entities` and `emit_entity_warnings` by `explore-ideas`; `build_origin_frontmatter` by `hypotheses`/`questions`. So `typed_entity_cli.py` must land before those groups move, or each new module would import them back from `cli.py`. Any adapter still needed by a command that *remains* in `cli.py` is imported from `typed_entity_cli.py` (`cli.py → typed_entity_cli.py` is the intended edge; the forbidden one is the reverse).

**Registration site:** all new `main.add_command(...)` lines join the existing block at `cli.py:249-272`. The `@main.command("health")` and `@main.command("paper-fetch")` decorators auto-register today; after extraction they need explicit `main.add_command(health_command)` / `main.add_command(paper_fetch_command)`.

---

## The Extraction Recipe (Tasks 2, 7–11)

Every pure relocation follows this recipe. It is the "code" for those tasks — apply it per group; do not paste group bodies into the plan.

**BEFORE (in `cli.py`):**
```python
@main.group("entity")
def entity_group() -> None:
    """Create, edit, note, list, and inspect source-authored entities."""


@entity_group.command("create")
@click.argument("kind")
...
def entity_create(...) -> None:
    ...
```

**AFTER (new `entities_cli.py`):**
```python
"""`science entity` command group — source-authored entity CRUD."""
from __future__ import annotations

import click
# ... only the imports this group actually uses (see step 2) ...


@click.group("entity")
def entity_group() -> None:
    """Create, edit, note, list, and inspect source-authored entities."""


@entity_group.command("create")
@click.argument("kind")
...
def entity_create(...) -> None:
    ...
```

**AFTER (in `cli.py`):** delete the whole block; add one line in the registration block:
```python
from science_tool.entities_cli import entity_group
...
main.add_command(entity_group)
```

**Per-group steps:**

1. **Change the decorator.** `@main.group("x")` → `@click.group("x")`; `@main.group()` → `@click.group()` **but keep the invocation name explicit** — a bare `@main.group()` on `def graph()` is invoked as `graph`, so in the new module write `@click.group("graph")` on a symbol renamed to `graph_group` (see naming note below). Same for `datasets`, `tasks`, `inquiry`, `project`, `bib`, `sync`: pass the original command name as the first arg so the CLI path is unchanged. `@main.command("health")` → `@click.command("health")`.
2. **Compute the helper closure.** List every name the group's functions reference that is defined in `cli.py` (module-level helpers, constants, `_ENTITY_LIST_TITLES`-style dicts). For each:
   - **group-exclusive** (used only by this group) → move it into the new module with the group.
   - **shared** (also used by commands staying in `cli.py` or by another group) → import it from its real home. If its real home *is* `cli.py`, that is a latent problem: promote it to a neutral module (e.g. `entities.py`, `output.py`) in this task and import from there. **Never** `from science_tool.cli import …` in the new module.
3. **Move imports.** Copy only the imports the moved code needs into the new module (ruff `F401` will flag extras; run it). Leave `cli.py`'s imports alone unless an import becomes wholly unused there — then delete it (ruff will flag).
4. **Rename the symbol if it collides with its module or the design table** (e.g. `def graph` → `graph_group`, `def datasets` → `datasets_group`, `def tasks` → `tasks_group`, `def inquiry` → `inquiry_group`, `def project` → `project_group`, `def bib` → `bib_group`, `def sync` → `sync_group`). Update all in-module references (`@graph_group.command(...)`). The **CLI-visible name does not change** (it is the `@click.group("graph")` arg).
5. **Register.** Add `from science_tool.<module> import <symbol>` near the other group imports and `main.add_command(<symbol>)` in the `cli.py:249-272` block.
6. **Delete** the original inline block from `cli.py`.
7. **Stage explicitly.** Every extraction creates a *new* module, which `git commit -am` will NOT stage — always `git add <new module> <cli.py> [moved-into files] [tests]` and run `git status --short` to confirm the new file is staged before committing. Never use `git commit -am` in this phase.

**Naming note — the two collisions:** `entity` (CRUD) → `entities_cli.py`; `entities` (inventory/audit) → `entities_inventory_cli.py`. `dataset` (lifecycle) → `datasets/cli.py`; `datasets` (discovery/download) → `datasets_discovery_cli.py`. Module names disambiguate; CLI names (`entity`/`entities`, `dataset`/`datasets`) are untouched.

**Verification for every extraction task:**
```bash
cd science && uv run --frozen pytest -q && uv run --frozen pytest -m snapshot -q && uv run ruff check && uv run pyright
```
Expected: full suite green (same count as before the task), snapshot green, ruff clean, pyright clean. Then `science --help` and the moved group's `--help` list the same commands as before (spot-check one).

---

### Task 1: Consolidate the typed-entity CLI adapters into `typed_entity_cli.py`

One CLI-support module receives the whole shared typed-entity adapter cluster (prerequisite for the `entity`/`entities` groups and the six entity-kind groups). **This task does not touch `entities.py` — every helper here is CLI-layer.**

**Files:**
- Create: `science/src/science_tool/typed_entity_cli.py`
- Modify: `science/src/science_tool/cli.py` (delete the moved defs; import them back)
- Test: `science/tests/test_typed_entity_cli.py` (new)

**Interfaces — produced by `science_tool.typed_entity_cli` (public names drop the leading `_`; private sub-helpers keep it):**
- `create_typed_entity(*, kind: str, title: str, entity_id: str | None, slug: str | None, status: str | None, related: list[str], source_refs: list[str], phase: str | None = None, with_sections: list[str] | None = None, without_sections: list[str] | None = None, no_hints: bool = False, extra_frontmatter: dict[str, object] | None = None) -> None`
- `show_typed_entity(kind: str, ref: str, output_format: str) -> None`
- `list_typed_entities(kind: str, status: str | None, related: str | None, output_format: str) -> None`
- `ENTITY_LIST_TITLES: dict[str, str]`
- `build_origin_frontmatter(origins: tuple[str, ...], added_by: str | None) -> dict[str, object]` (was `_build_origin_frontmatter`, `cli.py:1398` — **CLI adapter**: catches `ValidationError`, raises `click.BadParameter`; needs `parse_origin_spec` + `ValidationError` imports moved with it)
- `emit_entity_show(location: Any, output_format: str) -> None` (was `_emit_entity_show`) — **shared** by `entity show` (Task 2)
- `emit_entity_warnings(warnings: list[str]) -> None` (was `_emit_entity_warnings`, `cli.py:1555`) — **shared** by `entity create` (Task 2) and `explore-ideas apply` (Task 8)

**Private sub-helpers that move with `emit_entity_show` (all `cli.py`-only today — confirmed by grep; keep `_`-prefixed):** `_entity_show_payload`, `_print_entity_field`, `_print_entity_refs_field`, `_frontmatter_string_list` (`cli.py:1487`+). The adapters also call `create_entity`, `find_entity`, `list_entities`, `emit_query_rows`, `entity_table_renderers` — import those from their existing homes, never from `cli.py`.

- [ ] **Step 1: Write the characterization test**

```python
# tests/test_typed_entity_cli.py (new)
import inspect
from science_tool import typed_entity_cli as tec
from science_tool import entities as ent

def test_typed_entity_adapters_present():
    for name in ("create_typed_entity", "show_typed_entity", "list_typed_entities",
                 "ENTITY_LIST_TITLES", "build_origin_frontmatter",
                 "emit_entity_show", "emit_entity_warnings"):
        assert hasattr(tec, name), name
    assert tec.ENTITY_LIST_TITLES["hypothesis"] == "Hypotheses"

def test_entities_domain_module_stays_click_free():
    # Task 1 must not push CLI code into the domain module.
    assert "import click" not in inspect.getsource(ent)
```

- [ ] **Step 2: Run it — expect FAIL** (`typed_entity_cli` module / attrs absent).

Run: `cd science && uv run --frozen pytest tests/test_typed_entity_cli.py -q`

- [ ] **Step 3: Move the code.** Cut into the new `typed_entity_cli.py`: the three per-kind adapters (`_create_typed_entity`/`_show_typed_entity`/`_list_typed_entities`), `_ENTITY_LIST_TITLES`, `_build_origin_frontmatter`, the two shared emit adapters (`_emit_entity_show`, `_emit_entity_warnings`), and the four private sub-helpers (`_entity_show_payload`, `_print_entity_field`, `_print_entity_refs_field`, `_frontmatter_string_list`). Drop the leading `_` on the seven public names (`create_typed_entity`, `show_typed_entity`, `list_typed_entities`, `ENTITY_LIST_TITLES`, `build_origin_frontmatter`, `emit_entity_show`, `emit_entity_warnings`); keep the four sub-helpers `_`-prefixed. Move the imports they need (including `parse_origin_spec`, `ValidationError`). `typed_entity_cli.py` may `import click`; it must NOT import `cli.py`. In `cli.py`, add `from science_tool.typed_entity_cli import create_typed_entity, show_typed_entity, list_typed_entities, ENTITY_LIST_TITLES, build_origin_frontmatter, emit_entity_show, emit_entity_warnings` and rewrite every call site (`_create_typed_entity(`→`create_typed_entity(`, `_emit_entity_warnings(`→`emit_entity_warnings(` at `:533`/`:579`/`:598`/`:1302`, `_emit_entity_show(`→`emit_entity_show(`, the two `_build_origin_frontmatter(` at `:1086`/`:5164`, etc.).

- [ ] **Step 4: Run the test + full suite — expect PASS/green.**

Run: `cd science && uv run --frozen pytest -q && uv run ruff check && uv run pyright`
Expected: same pass count as pre-task, ruff+pyright clean.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/typed_entity_cli.py \
        science/src/science_tool/cli.py \
        science/tests/test_typed_entity_cli.py
git status --short   # confirm typed_entity_cli.py (new) is staged
git commit -m "Consolidate the typed-entity CLI adapter cluster into typed_entity_cli.py (t-phase4)"
```

---

### Task 2: Extract the `entity` group → `entities_cli.py`

First extraction — the worked example of the recipe. Depends on Task 1 (the group's `create`/`show`/`list` subcommands call the now-public `create_typed_entity` etc.).

**Files:**
- Create: `science/src/science_tool/entities_cli.py`
- Modify: `science/src/science_tool/cli.py` (delete block @483-846; add import + `main.add_command`)

**Interfaces:**
- Consumes: `create_entity`, `find_entity`, `list_entities`, `EntityCommandError` from `science_tool.entities` (already public), and the shared emit adapters `emit_entity_show`, `emit_entity_warnings` from `science_tool.typed_entity_cli` (Task 1). The `entity create/show/list` commands call `create_entity`/`find_entity`/`list_entities` **directly** (`cli.py:515`+) — they do **not** use the per-kind `create_typed_entity`/`show_typed_entity`/`list_typed_entities` adapters (those are for the entity-*kind* groups in Task 9). If `entity list` renders via `emit_query_rows` + `entity_table_renderers`, import those from their existing homes too.
- Produces: `entity_group` (a `click.Group` named `"entity"`) importable from `science_tool.entities_cli`.

- [ ] **Step 1: Apply the recipe** to the `entity` group (`cli.py:483-846`). New module docstring, `from __future__ import annotations`, `import click`, the group's import closure, `@click.group("entity")` on `entity_group`, all `@entity_group.command(...)` bodies verbatim. Delete the block from `cli.py`.
- [ ] **Step 2: Register** — add `from science_tool.entities_cli import entity_group` and `main.add_command(entity_group)` in the `cli.py:249-272` block.
- [ ] **Step 3: Verify** (recipe verification block above). Also: `cd science && uv run --frozen python -m science_tool.cli entity --help` lists the same subcommands as before.
- [ ] **Step 4: Commit**

```bash
git add science/src/science_tool/entities_cli.py science/src/science_tool/cli.py
git commit -m "Extract entity group to entities_cli.py (t-phase4)"
```

---

### Task 3: Extract `benchmark` → `benchmark_cli.py` + push down the review-file cluster

**Files:**
- Create: `science/src/science_tool/benchmark_cli.py`
- Modify: `science/src/science_tool/benchmark_opportunities.py` (receive the review-file writers)
- Modify: `science/src/science_tool/cli.py` (delete block @5499-6756; register)

**Interfaces:**
- Consumes: `benchmark_opportunities.py` public API.
- Produces: `benchmark_group` (`click.Group` `"benchmark"`) from `science_tool.benchmark_cli`.

**Push-down:** the review-file cluster in `cli.py` (`_default_hint_candidates_review_path` @6306, `_write_hint_candidates_review_file` @6351, `_default_test_triage_review_path` @6386, `_write_test_triage_review_file` @6455, and the path/serialize logic the `benchmark_opportunities` command invokes at @6072-6096) computes output paths and serializes review artifacts — domain output. Move those helpers into `benchmark_opportunities.py` and have the command call them. The command keeps only: parse options → call domain → `emit`/`click.echo(..., err=True)`.

- [ ] **Step 1: Move the review-file writers** (`_default_hint_candidates_review_path`, `_write_hint_candidates_review_file`, `_default_test_triage_review_path`, `_write_test_triage_review_file`) from `cli.py` into `benchmark_opportunities.py` as public functions (drop the leading `_`), with a characterization test asserting the written YAML for a fixed input is unchanged.

```python
# tests/test_benchmark_opportunities.py (append)
def test_review_path_default_is_stable(tmp_path):
    from datetime import date
    from science_tool.benchmark_opportunities import default_test_triage_review_path
    p = default_test_triage_review_path(tmp_path, date(2026, 1, 2))
    assert p.parent == tmp_path or tmp_path in p.parents
```
Run it to see it FAIL (function not yet public), then make it pass.

- [ ] **Step 2: Apply the extraction recipe** to the `benchmark` group; the moved command now imports the review-file writers from `benchmark_opportunities`.
- [ ] **Step 3: Register** (`main.add_command(benchmark_group)`).
- [ ] **Step 4: Verify** (recipe block) + `benchmark --help` unchanged + snapshot green (benchmark has JSON output).
- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/benchmark_cli.py science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py
git status --short   # confirm benchmark_cli.py (new) is staged
git commit -m "Extract benchmark group to benchmark_cli.py; push review-file writers into benchmark_opportunities (t-phase4)"
```

---

### Task 4: Extract `graph` → `graph/cli.py` + push `graph_build` registration into a CLI-facing build service

**Files:**
- Create: `science/src/science_tool/graph/cli.py`
- Create: `science/src/science_tool/graph/build.py` (the CLI-facing wrapper that owns registration)
- Modify: `science/src/science_tool/cli.py` (delete block @1575-2738; register)
- Test: `science/tests/` (build-service registration characterization)

**Interfaces:**
- Produces: `graph_group` (`click.Group` `"graph"`) from `science_tool.graph.cli`.
- Produces: `build_project_graph(project_root: Path) -> LocalGraphBuild` from `science_tool.graph.build`, where `LocalGraphBuild` is a small dataclass `(local_path: Path, config: ProjectConfig | None)`. **Narrow contract on purpose:** it resolves the project root, loads config if `science.yaml` exists, runs `ensure_registered`, calls `materialize_graph`, and returns the local graph path plus the loaded config. It does **not** take `local_only` and does **not** touch composite graphs.

**Push-down — extract ONLY the registration policy; do NOT widen `materialize_graph`, and do NOT swallow the rest of the command.** `graph_build` (`cli.py:1608`) today does five things: (1) resolve root + load config, (2) `ensure_registered` (`cli.py:1613-1620`), (3) `materialize_graph` (`cli.py:1629`), (4) composite refresh / stale-`composite.trig` deletion gated on `local_only` and `_cfg.peers` (`cli.py:1634`+), (5) non-blocking ontology suggestions. Only (1)–(3) move into the service; **(4) and (5) stay in the command** (they are user-facing orchestration with `click.echo`s and `--local-only` semantics that `tests/test_graph_cli.py:252` covers). Putting `ensure_registered` *inside* `materialize_graph` is forbidden: `materialize_graph` (`graph/materialize.py:601`) has **non-CLI callers** (`annotation/proposition_archive.py`, `graph/source_snapshots.py`, `graph/freshness.py`, `graph/store/inquiry.py`, `graph/__init__.py`) and would then mutate the registry for every library/test build.

- [ ] **Step 1:** Create `graph/build.py` with the `LocalGraphBuild` dataclass and `build_project_graph(project_root)` performing exactly steps (1)–(3): resolve `_project_root`, load config via `load_project_config` iff `project_config_path(...).is_file()`, `ensure_registered(...)` with the identical args at `cli.py:1614-1620`, then `local_path = materialize_graph(_project_root)`, returning `LocalGraphBuild(local_path, _cfg)`. Let `materialize_graph`'s `ValueError` propagate (the command keeps its `except ValueError → ClickException` wrapper). Characterization test: on an unregistered fixture project, `build_project_graph` registers it (assert the registry side-effect) and returns a `LocalGraphBuild` with the materialized path + config; a **direct** `materialize_graph` on an unregistered project does **not** register it (locks in that the wrapper, not the API, owns registration).
- [ ] **Step 2:** Apply the extraction recipe to the `graph` group (rename `def graph` → `graph_group`, `@click.group("graph")`). Rewrite `graph_build` to: `result = build_project_graph(_project_root)` inside the existing `try/except ValueError`, `click.echo(f"Materialized local graph at {result.local_path}")`, then keep the composite-refresh block (4) and ontology-suggestions block (5) verbatim, reading `_cfg` from `result.config`. No inline `ensure_registered`, no direct `materialize_graph`.
- [ ] **Step 3: Register** (`main.add_command(graph_group)`).
- [ ] **Step 4: Verify** (recipe block) + `graph --help` unchanged + snapshot green + `tests/test_graph_cli.py` green (it pins the composite/`--local-only` behavior that stays in the command).
- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/cli.py science/src/science_tool/graph/build.py science/src/science_tool/cli.py science/tests/
git status --short   # confirm graph/cli.py and graph/build.py are staged
git commit -m "Extract graph group to graph/cli.py; own graph-build registration in a CLI-facing build_project_graph service (t-phase4)"
```

---

### Task 5: Extract `dataset` (lifecycle) → `datasets/cli.py` + public store accessors for `dataset_prioritize`

**Files:**
- Create: `science/src/science_tool/datasets/cli.py`
- Modify: `science/src/science_tool/graph/store/dataset.py` and `science/src/science_tool/graph/store/identity.py` (add public accessors)
- Modify: `science/src/science_tool/cli.py` (delete block @6757-end; register)

**Interfaces:**
- Produces: `dataset_group` (`click.Group` `"dataset"`) from `science_tool.datasets.cli`. The group re-adds `dataset_identity_group` as a subcommand (as it does today at `cli.py:6760`).
- New public store accessors (names — implementer confirms signatures against the private ones):
  - `graph.store.dataset.load_dataset(graph_path: Path) -> <Dataset>` (wraps `_load_dataset`)
  - `graph.store.identity.graph_uri(suffix: str) -> <URIRef>` (wraps `_graph_uri`)

**Push-down:** `dataset_prioritize` (`cli.py:6867`) reaches into private store internals `graph.store.dataset._load_dataset` and `graph.store.identity._graph_uri` (`cli.py:6886-6890`). A CLI command may not depend on `_`-private store internals across a module boundary. Add public accessors in the store package, migrate the command to them.

- [ ] **Step 1:** Add public accessors (`load_dataset`, `graph_uri`) in `graph/store/dataset.py` / `graph/store/identity.py` — one-line delegations to the existing private functions (keep the private ones; the public name is the boundary). Test: `from science_tool.graph.store.dataset import load_dataset` imports; behaviour matches `_load_dataset` on a fixture graph.
- [ ] **Step 2:** Apply the extraction recipe to the `dataset` group; `dataset_prioritize` imports `load_dataset`/`graph_uri` (public) instead of the `_`-private names.
- [ ] **Step 3: Register** (`main.add_command(dataset_group)`).
- [ ] **Step 4: Verify** (recipe block) + `dataset --help` unchanged (including the nested `identity` subcommand) + snapshot green.
- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/cli.py science/src/science_tool/graph/store/dataset.py science/src/science_tool/graph/store/identity.py science/src/science_tool/cli.py science/tests/
git status --short   # confirm datasets/cli.py (new) is staged
git commit -m "Extract dataset group to datasets/cli.py; add public store accessors for dataset_prioritize (t-phase4)"
```

---

### Task 6: Extract `health` → `graph/health_cli.py` + push aggregate tally into `build_health_report`

**Files:**
- Create: `science/src/science_tool/graph/health_cli.py`
- Modify: `science/src/science_tool/graph/health.py:669` (`build_health_report` returns the rollup)
- Modify: `science/src/science_tool/cli.py` (delete block @4585-5017; register)

**Interfaces:**
- Produces: `health_command` (`click.Command` `"health"`) from `science_tool.graph.health_cli`.
- `build_health_report(...)` **already computes and returns `total_issues`** (`graph/health.py:794` computes `archive_lag_total`, `:798` the ~20-term `total_issues` sum, `:837` returns `"total_issues"` in the report dict). It does **not** yet return `archive_lag_total`. Add `archive_lag_total` (and `layered_claim_issue_count` if a CLI rendering branch reads it) to the returned dict.

**Push-down (correction — this is de-duplication, not new computation):** `health_command` (`cli.py:4626`) **redundantly recomputes** `total_issues` inline (`cli.py:4724`) even though the report already carries it, and recomputes `archive_lag_total` (`cli.py` ~4695) / `layered_claim_issue_count` (~4683) for its rendering branches. Reframe: **delete the CLI's recomputation** and read `report["total_issues"]`; add only the *missing* sub-rollups (`archive_lag_total`, and `layered_claim_issue_count` iff a render branch needs it) to `build_health_report`'s return so the command reads them too. Net effect: the CLI stops duplicating the service's tally.

- [ ] **Step 1:** Add the missing sub-rollups (`archive_lag_total`; `layered_claim_issue_count` iff used by a CLI render branch) to `build_health_report`'s returned dict — the values it already computes internally, now surfaced. Characterization test: for a fixture project `report["total_issues"]` and `report["archive_lag_total"]` equal the numbers the CLI prints today (capture the current stdout numbers first, assert the service returns them).
- [ ] **Step 2:** Apply the extraction recipe to `health_command` (`@click.command("health")`); delete the inline `total_issues`/`archive_lag_total`/`layered_claim_issue_count` recomputation and read them off the report. Preserve the `total_issues == 0` early-return and `if archive_lag_total:` branches (`cli.py` ~4742) — same control flow, values sourced from the report.
- [ ] **Step 3: Register** — `from science_tool.graph.health_cli import health_command` + `main.add_command(health_command)`.
- [ ] **Step 4: Verify** (recipe block) + `health --help` unchanged + snapshot green + a `health --format json` run is byte-identical to a pre-task capture.
- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/health_cli.py science/src/science_tool/graph/health.py science/src/science_tool/cli.py science/tests/
git status --short   # confirm graph/health_cli.py is staged
git commit -m "Extract health command to graph/health_cli.py; stop recomputing the issue tally, read it from build_health_report (t-phase4)"
```

---

### Task 7: Extract `tasks` → `tasks_cli.py`

Pure relocation via the recipe (rename `def tasks` → `tasks_group`, `@click.group("tasks")`). Note `cli.py:4117` has a function-local `from science_tool.tasks import list_tasks, parse_tasks_for_cli` — move it into the new module.

- [ ] **Step 1:** Apply the recipe to `tasks` (`cli.py:3623-4309`).
- [ ] **Step 2:** Register (`main.add_command(tasks_group)`).
- [ ] **Step 3:** Verify (recipe block) + `tasks --help` unchanged.
- [ ] **Step 4: Commit** — `git add science/src/science_tool/tasks_cli.py science/src/science_tool/cli.py && git status --short && git commit -m "Extract tasks group to tasks_cli.py (t-phase4)"`

---

### Task 8: Extract `explore-ideas` → `explore_ideas_cli.py`

Pure relocation via the recipe. `explore_ideas_group` already has the target name; `@click.group("explore-ideas")`.

**Consumes:** `explore-ideas apply` calls `_emit_entity_warnings` (`cli.py:1302`) — import it as public `emit_entity_warnings` from `science_tool.typed_entity_cli` (Task 1), never from `cli.py`.

- [ ] **Step 1:** Apply the recipe to `explore-ideas` (`cli.py:1239-1574`).
- [ ] **Step 2:** Register (`main.add_command(explore_ideas_group)`).
- [ ] **Step 3:** Verify (recipe block) + `explore-ideas --help` unchanged.
- [ ] **Step 4: Commit** — `git add science/src/science_tool/explore_ideas_cli.py science/src/science_tool/cli.py && git status --short && git commit -m "Extract explore-ideas group to explore_ideas_cli.py (t-phase4)"`

---

### Task 9: Extract the entity-kind groups → per-kind modules (batch A)

Six pure relocations, **one commit each**. All consume the Task-1 adapters (`create_typed_entity`/`show_typed_entity`/`list_typed_entities`/`ENTITY_LIST_TITLES` from `science_tool.typed_entity_cli`). **`hypotheses` and `questions` additionally consume `build_origin_frontmatter` from `science_tool.typed_entity_cli`** (Task 1) — import it there, never from `cli.py`. Apply the recipe per group; each becomes its own module. Reviewer reviews the batch together (identical mechanical shape) but each is a separate commit so a single bad move is revertible.

Groups (source span → module → exposed symbol):
- `propositions` (@847-905) → `propositions_cli.py` → `proposition_group`
- `evidence-lines` (@906-1036) → `evidence_lines_cli.py` → `evidence_line_group`
- `hypotheses` (@1037-1120) → `hypotheses_cli.py` → `hypothesis_group` (also imports `build_origin_frontmatter`)
- `discussions` (@1121-1179) → `discussions_cli.py` → `discussion_group`
- `interpretations` (@1180-1238) → `interpretations_cli.py` → `interpretation_group`
- `questions` (@5127-5292) → `questions_cli.py` → `question_group` (also imports `build_origin_frontmatter`)

- [ ] **Step 1–6 (per group):** apply the recipe; register; `git add` the new module + `cli.py`; verify `pytest -q` green + `<group> --help` unchanged; commit `Extract <group> group to <module> (t-phase4)`. Repeat for all six.
- [ ] **Step 7:** After all six, run the full verification block (`pytest -q && pytest -m snapshot -q && ruff check && pyright`) once.

---

### Task 10: Extract the remaining default-named groups → per-domain modules (batch B)

Seven pure relocations, **one commit each**. These use bare `@main.group()` (invocation name = function name) — pass the name explicitly in the new module (`@click.group("inquiry")` etc.) and rename the symbol to `<name>_group`.

- `inquiry` (@2858-3237) → `inquiry_cli.py` → `inquiry_group` (`@click.group("inquiry")`)
- `datasets` discovery (@3238-3622) → `datasets_discovery_cli.py` → `datasets_group` (`@click.group("datasets")`)
- `project` (@4310-4584) → `project_cli.py` → `project_group` (`@click.group("project")`)
- `belief` (@2739-2857) → `belief_cli.py` → `belief_group` (already named)
- `bib` (@5293-5368) → `bib_cli.py` → `bib_group` (`@click.group("bib")`)
- `sync` (@5369-5498) → `sync_cli.py` → `sync_group` (`@click.group("sync")`)
- `entities` inventory (@275-482) → `entities_inventory_cli.py` → `entities_group` (already named `entities_group`; `@click.group("entities")`)

- [ ] **Step 1–6 (per group):** apply the recipe; register; `git add` the new module + `cli.py` (`git status --short` before commit); verify green + `<group> --help` unchanged; commit `Extract <group> group to <module> (t-phase4)`. Repeat for all seven.
- [ ] **Step 7:** Run the full verification block once after the batch.

---

### Task 11: Extract `paper` + `paper-fetch` → `paper_cli.py`

The `paper` group (@5071-5126) and the standalone `paper-fetch` command (@5018-5070) are adjacent and topical; both go to `paper_cli.py`.

- [ ] **Step 1:** Apply the recipe to `paper` group → `paper_group` (`@click.group("paper")`).
- [ ] **Step 2:** Move `paper-fetch` (`@main.command("paper-fetch")` → `@click.command("paper-fetch")`, symbol `paper_fetch_command`) into the same module.
- [ ] **Step 3:** Register both — `from science_tool.paper_cli import paper_group, paper_fetch_command`; `main.add_command(paper_group)`; `main.add_command(paper_fetch_command)`.
- [ ] **Step 4:** Verify (recipe block) + `paper --help` and `paper-fetch --help` unchanged.
- [ ] **Step 5: Commit** — `git add science/src/science_tool/paper_cli.py science/src/science_tool/cli.py && git status --short && git commit -m "Extract paper group and paper-fetch command to paper_cli.py (t-phase4)"`

---

### Task 12: Land the registration-only guard + record the `dataset`/`datasets` follow-up

**Files:**
- Create: `science/tests/test_cli_is_registration_only.py`
- Modify: `docs/plans/2026-07-10-half-applied-pattern-convergence-design.md` (or a follow-ups doc) — record the `dataset`/`datasets` naming collision as a deferred rename.

**Write the guard LAST, against the migrated `cli.py`.** Model it on `tests/test_store_package_structure.py`. The guard parses `cli.py` and fails if it defines **any** command or group other than the root `main`.

**The guard must be decorator-owner-blind.** Inline subcommands today are decorated by many owners — `@main.group`, `@main.command`, `@entity_group.command`, `@graph.command`, `@graph_add.command`, `@datasets.command`, `@inquiry.command`, `@tasks.command`, … (verified by an AST census of the current tree). A guard keyed on `main.*` alone would let a future inline subcommand on an *imported* group slip through. So: flag every function whose decorator is a `*.group(...)`/`*.command(...)` attribute call **or** a `click.group(...)`/`click.command(...)` call — regardless of the owner name — and allow exactly one: the root group `main` (declared `@click.group(cls=TelemetryGroup)` at `cli.py:230`). Exempt it by function name (`main`), not by matching its exact decorator.

- [ ] **Step 1: Write the guard.** Parse `science_tool/cli.py` with `ast`.

```python
# tests/test_cli_is_registration_only.py (shape — finalize against the migrated tree)
import ast
from pathlib import Path

_CLI = Path(__file__).resolve().parents[1] / "src" / "science_tool" / "cli.py"
_ROOT_GROUP = "main"  # the one allowed group/command definition (the Click root)

def _is_group_or_command_decorator(dec: ast.expr) -> bool:
    """True for @X.group(...)/@X.command(...) and @click.group(...)/@click.command(...),
    for ANY owner X — decorator-owner-blind on purpose."""
    target = dec.func if isinstance(dec, ast.Call) else dec
    return isinstance(target, ast.Attribute) and target.attr in {"group", "command"}

def _command_defs(tree: ast.Module) -> list[str]:
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(_is_group_or_command_decorator(d) for d in node.decorator_list)
    ]

def test_cli_defines_only_the_root_group():
    tree = ast.parse(_CLI.read_text(encoding="utf-8"))
    offenders = [name for name in _command_defs(tree) if name != _ROOT_GROUP]
    assert not offenders, (
        "cli.py must be registration-only: the only command/group definition allowed "
        f"is the root '{_ROOT_GROUP}'. Every other group/command lives in a <domain>_cli.py "
        f"registered via main.add_command. Inline definitions found: {offenders}"
    )

def test_cli_within_line_budget():
    lines = _CLI.read_text(encoding="utf-8").count("\n") + 1
    assert lines <= 900, f"cli.py is {lines} lines; extract inline logic (budget 900)"
```

- [ ] **Step 2: Run it — expect PASS** against the fully-migrated tree. If `test_cli_defines_only_the_root_group` fails, the migration is incomplete (a group or subcommand was missed) — fix the migration, not the guard. If a legitimately-inline top-level command survives that you did not extract, do not add owner-name exceptions; extract it. Set the line budget from the real post-migration count (`wc -l cli.py`) plus a small margin; record the chosen number in the test docstring.
- [ ] **Step 3: Record the `dataset`/`datasets` collision** as a follow-up (a short note in the design doc's Phase 4 section or a `docs/plans/` follow-ups list): the two groups are placed in disambiguating modules but keep colliding CLI names; a rename is a separate CLI-contract change.
- [ ] **Step 4: Full verification** — `pytest -q && pytest -m snapshot -q && ruff check && pyright`, all green.
- [ ] **Step 5: Commit**

```bash
git add science/tests/test_cli_is_registration_only.py docs/plans/2026-07-10-half-applied-pattern-convergence-design.md
git commit -m "Guard cli.py as registration-only; record dataset/datasets rename follow-up (t-phase4)"
```

---

## Test strategy

Behavior-preserving phase → the existing suite (~7854 tests) is the primary oracle at **every** commit. Two additions carry the real risk and get explicit attention:

- **`--format json` byte-identity.** Run `-m snapshot` at each commit (not just the end). For the five push-down commands, capture a `--format json` run before the task and diff it after.
- **Circular-import breakage.** The most likely new-failure mode is an extracted module importing back from `cli.py`. `pyright` + import-time collection in pytest catch this immediately; the recipe forbids the edge.

```bash
cd science && uv run --frozen pytest -q
cd science && uv run --frozen pytest -m snapshot -q
cd science && uv run ruff check && uv run pyright
cd science/model && uv run --frozen pytest -q   # unchanged; sanity only
```

The guard (Task 12) is the deliverable as much as the migrations are: a phase that moves the groups without landing the guard buys a temporary improvement at the cost of a permanent one.

## Order and independence

Task 1 (service push-down) is a hard prerequisite for Tasks 2, 9 (entity-kind groups consume it). Tasks 3–8, 10, 11 are mutually independent relocations (each touches its own new module + the `cli.py` registration block) — but because they all edit `cli.py`, they must run **sequentially**, never in parallel (the skill already forbids parallel implementers). Task 12 (guard) is strictly last, written against the migrated tree.
