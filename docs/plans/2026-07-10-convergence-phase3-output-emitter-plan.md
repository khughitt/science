# Convergence Phase 3 — One Output Emitter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the toolkit one canonical JSON/human output emitter (`science_tool.output.emit`), migrate the ~95 functions that hand-roll the `if output_format == "json": click.echo(json.dumps(...)); return` shape onto it, and land an additive AST guard that bans new hand-rolled emitters — all with byte-identical `--format json` stdout.

**Architecture:** `output.py` already owns the shared *tabular* path (`emit_query_rows`, 48 call sites). This phase extends it with the non-tabular case that authors bypass: a single `emit(*, output_format, payload, render_text, …json-kwargs)` that emits `payload` as JSON on stdout when `output_format == "json"`, else calls `render_text()` for human output. `emit_query_rows` is re-expressed on top of `emit`. Every inline `echo(json.dumps(...))` command is migrated to call `emit`. A function-scoped AST guard (`tests/test_output_boundary.py`) then fails if any function *outside* `output.py` contains both an emission call and a `.dumps` attribute call, with a reason-tagged allowlist for the handful that legitimately keep a stderr `echo` beside a file/hash `dumps`.

**Tech Stack:** Python 3, `click`, `rich`, `pytest`, `ast` (stdlib) for the structural guard. Package: `science/` (`src/science_tool/`); tests run from `science/` with `uv run --frozen pytest`.

## Global Constraints

- **Byte-identity is the hard contract.** `--format json` stdout must be byte-for-byte identical before and after every migration. `emit` therefore carries the per-site serialization kwargs (`indent`, `sort_keys`, `ensure_ascii`, `default`) — a single hard-coded `indent=2` would move bytes at every site that uses a different form. Proof gate: the full suite + `-m snapshot` stay green, and the emit characterization test pins the kwarg matrix.
- **`--format json` emits machine-readable JSON on stdout only** (`docs/conventions/cli-behavior.md`). Human diagnostics during a JSON run go to **stderr** (`click.echo(..., err=True)`) or are represented structurally in the payload. Migrations must preserve each site's existing stderr diagnostics unchanged.
- **`science_model` must never import `science_tool`.** `emit` lives in `science_tool/output.py`; nothing moves into the model package.
- **The guard is written LAST, against the migrated tree** — not against this plan's prose. Run the detector on the migrated source; allowlist exactly what it reports, each entry with a reason. A function the detector reports that *should* have been fully migrated is a migration miss — fix the migration, do not allowlist it.
- **Guards key on structure (AST), not text.** Match `dumps` by *attribute name* (alias-blind: catches `json.dumps`, `_json.dumps`, `yaml.dumps`), scoped to the enclosing function. Include `sys.stdout.write` in the emission set alongside `click.echo`/`print`/`console.print`.
- **No behavior changes beyond the emitter.** No new CLI flags, no renamed flags, no reordered payload keys, no changed table rendering. YAGNI: do **not** build a generic table DSL — the hand-written `Table(...)` blocks stay hand-written, moved verbatim into `render_text` callbacks.
- **Conventions:** composition over inheritance; explicit over defensive; fail early; no "legacy"/"compatibility" layers; no `Unified` prefix; no AI-attribution trailers on commits; use `~/d/` (not absolute Dropbox paths) in any docs/code.

---

## Migration recipe (applies to Tasks 2–6)

Every migration target is one of a few variants of the same shape. Apply this recipe mechanically; the worked examples below cover every variant present in the tree.

**The canonical shape** — an inline JSON branch followed by table/text construction:

```python
# BEFORE
def some_cmd(..., output_format: str) -> None:
    payload = _build_payload(...)
    if output_format == "json":
        click.echo(json.dumps(payload, indent=2))
        return
    table = Table(title="...")
    ...
    get_console().print(table)

# AFTER
def some_cmd(..., output_format: str) -> None:
    payload = _build_payload(...)

    def _render() -> None:
        table = Table(title="...")
        ...
        get_console().print(table)

    emit(output_format=output_format, payload=payload, render_text=_render)
```

**CRITICAL — match every kwarg.** `emit`'s defaults are `indent=2, sort_keys=False, ensure_ascii=True, default=None`. Read each site's **exact** `json.dumps(...)` call and pass every kwarg that differs from those defaults. **`sort_keys=True` is common in this tree** — omitting it silently reorders JSON object keys and moves bytes. Do not assume a site is `indent=2`-only; look.

**Variant table — how each observed `json.dumps(...)` maps to an `emit(...)` call:**

| Site's current dumps | `emit(...)` kwargs to pass |
|---|---|
| `json.dumps(payload, indent=2)` | *(none — `indent=2` is the default)* |
| `json.dumps(payload, indent=2, sort_keys=True)` *(very common — `datasets_qa`, `_emit_entity_show`, `graph_cross_impact`, `graph_export_json`, `tasks_show`, `project_verify`, `search_command`, `qa_audit_command`, …)* | `sort_keys=True` |
| `json.dumps(payload)` *(no indent — e.g. `bib_add`, `stats_cmd`, `search`)* | `indent=None` |
| `json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)` *(`verdict/cli.py:_emit_json`)* | `sort_keys=True, ensure_ascii=False` |
| `json.dumps(info, indent=2, default=str)` *(`inquiry_show`)* | `default=str` |
| `_json.dumps(report, indent=2)` *(function-local `import json as _json`)* | *(none)* — and delete the now-unused `import json as _json` |

**Compound-condition commands (`--json` alias).** Several commands trigger JSON on `if as_json or output_format == "json":`, or precompute `emit_json = as_json or output_format == "json"` and branch on that (`project_verify`, `question_reserve_cmd`, `bib_add`, `qa_audit_command`, `project_artifacts/cli.py:check_cmd`). `emit` triggers JSON only when its `output_format` argument equals `"json"`, so passing the raw `output_format` would emit human output when `as_json=True` and `output_format` is still `"table"`/`"text"`. **Compute an effective format that is `"json"` exactly when the original branch fired:**

```python
# BEFORE
if as_json or output_format == "json":
    click.echo(json.dumps(payload, indent=2, sort_keys=True))
    return
_render_human(...)

# AFTER
effective_format = "json" if (as_json or output_format == "json") else output_format
emit(output_format=effective_format, payload=payload, render_text=lambda: _render_human(...), sort_keys=True)
```

For `project_verify`, which already binds `emit_json`, pass `output_format="json" if emit_json else output_format`. Preserve the site's exact original condition — do not simplify it.

**Helper-fold rule.** Several files have a private `_emit_json(payload)` / `_emit_list_json(payload)` helper that is *only* called from inside a `if output_format == "json":` branch (e.g. `verdict/cli.py:240`, `annotation/cli.py:1449,2048`). Migrate the **outer** command to call `emit(output_format=..., payload=..., render_text=<the table/text builder>)` and **delete** the now-unused helper once no caller remains. Do not keep the helper as an `emit(..., render_text=lambda: None)` wrapper — folding it into the outer command is the point.

**Two-branch commands** (e.g. `health_command` has both a `list_checks` JSON branch and a main JSON branch; `dataset_prioritize` has two `_json.dumps` branches): each `if output_format == "json": … return` site becomes its own `emit(...)` call with its own `render_text`. Migrate every branch in the function.

**Do NOT touch:**
- `emit_query_rows` call sites (48 of them) — they already route through `output.py`.
- Section-B "COMPLEX" `== "json"` branches that do **not** contain an inline `dumps` (they delegate to `emit_query_rows` or a `.to_json()` string writer, e.g. `cli.py:3540` uses `_infer_schema.result_to_json`). These are not `echo(dumps)` emitters; leave them. The guard will not flag them (no `.dumps` call).
- `.dumps` calls that write to files or build hashes and are **not** echoed (they live in functions with no emission call, so the guard never sees them).

**Per-site verification.** After migrating a file, run that file's CLI tests and confirm the JSON output assertions still pass. Byte-identity across the whole phase is proven by the full suite + `-m snapshot` staying green (Task 7 gate), not re-derived per site.

---

## File structure

| File | Responsibility | Touched by |
|---|---|---|
| `src/science_tool/output.py` | Canonical emitter: `OUTPUT_FORMATS`, `emit`, `emit_query_rows` (re-expressed on `emit`) | Task 1 |
| `tests/test_output_emit.py` (new) | Characterization/golden test pinning `emit`'s byte output across the kwarg matrix; `emit_query_rows` byte-identity | Task 1 |
| `src/science_tool/cli.py` | 36 inline emitters (entities/graph/inquiry/tasks/project + benchmark/dataset/paper/health) | Tasks 2, 3 |
| `src/science_tool/annotation/cli.py` | 26 inline emitters | Task 4 |
| `src/science_tool/commons/cli.py`, `dag/cli.py`, `big_picture/cli.py`, `curate/cli.py`, `peers_cli.py` | 21 inline emitters across 5 files | Task 5 |
| `book_split_cli.py`, `markers_cli.py`, `prose_lint_cli.py`, `qa_audit/cli.py`, `refs_cli.py`, `research_package/cli.py`, `search_cli.py`, `skills_lint/cli.py`, `validate/cli.py`, `verdict/cli.py`, `project_artifacts/cli.py` | 12 single-emitter files | Task 6 |
| `tests/test_output_boundary.py` (new) | Function-scoped AST guard + reason-tagged allowlist, written against the migrated tree | Task 7 |

---

## Task 1: The `emit` primitive

**Files:**
- Modify: `science/src/science_tool/output.py`
- Test: `science/tests/test_output_emit.py`

**Interfaces:**
- Produces:
  - `emit(*, output_format: str, payload: Any, render_text: Callable[[], None], indent: int | None = 2, sort_keys: bool = False, ensure_ascii: bool = True, default: Callable[[Any], Any] | None = None) -> None` — when `output_format == "json"`, prints `json.dumps(payload, indent=indent, sort_keys=sort_keys, ensure_ascii=ensure_ascii, default=default)` via `click.echo`; otherwise calls `render_text()`.
  - `emit_query_rows(...)` — unchanged signature, now implemented on top of `emit`.

- [ ] **Step 1: Write the failing characterization test**

Create `science/tests/test_output_emit.py`. `click.echo` with no active click context writes straight to `sys.stdout`, so `capsys` captures its bytes directly — no `CliRunner` needed:

```python
from __future__ import annotations

import json

import pytest

from science_tool.output import emit, emit_query_rows

PAYLOAD = {"b": "x", "a": [1, 2], "u": "café"}


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({}, json.dumps(PAYLOAD, indent=2)),
        ({"indent": None}, json.dumps(PAYLOAD)),
        ({"sort_keys": True, "ensure_ascii": False}, json.dumps(PAYLOAD, ensure_ascii=False, indent=2, sort_keys=True)),
        ({"default": str}, json.dumps(PAYLOAD, indent=2, default=str)),
    ],
)
def test_emit_json_is_byte_identical_to_manual_dumps(kwargs, expected, capsys) -> None:
    emit(output_format="json", payload=PAYLOAD, render_text=lambda: None, **kwargs)
    assert capsys.readouterr().out == expected + "\n"  # click.echo appends one newline


def test_emit_calls_render_text_for_non_json(capsys) -> None:
    calls: list[str] = []
    emit(output_format="table", payload=PAYLOAD, render_text=lambda: calls.append("rendered"))
    assert calls == ["rendered"]
    assert capsys.readouterr().out == ""  # render_text wrote nothing; no JSON leaked to stdout


def test_emit_json_does_not_call_render_text(capsys) -> None:
    calls: list[str] = []
    emit(output_format="json", payload=PAYLOAD, render_text=lambda: calls.append("x"))
    assert calls == []


def test_emit_query_rows_json_unchanged(capsys) -> None:
    rows = [{"name": "a", "n": 1}, {"name": "b", "n": 2}]
    emit_query_rows(
        output_format="json", title="T", columns=[("name", "Name"), ("n", "N")], rows=rows, meta={"total": 2}
    )
    expected = json.dumps({"format": "json", "rows": rows, "meta": {"total": 2}}, indent=2)
    assert capsys.readouterr().out == expected + "\n"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_output_emit.py -q`
Expected: FAIL — `ImportError: cannot import name 'emit'`.

- [ ] **Step 3: Implement `emit` and re-express `emit_query_rows`**

Edit `science/src/science_tool/output.py`. Add `emit` above `emit_query_rows` and rewrite `emit_query_rows`'s JSON branch to call it. The table-building code moves verbatim into a nested `_render`:

```python
def emit(
    *,
    output_format: str,
    payload: Any,
    render_text: Callable[[], None],
    indent: int | None = 2,
    sort_keys: bool = False,
    ensure_ascii: bool = True,
    default: Callable[[Any], Any] | None = None,
) -> None:
    """Emit ``payload`` as JSON on stdout when ``output_format == "json"``, else
    invoke ``render_text`` for human output.

    Serialization kwargs mirror ``json.dumps`` so existing call sites keep their
    exact byte output. Diagnostics must never reach stdout through this function:
    the JSON branch writes only ``json.dumps(payload, ...)``.
    """
    if output_format == "json":
        click.echo(json.dumps(payload, indent=indent, sort_keys=sort_keys, ensure_ascii=ensure_ascii, default=default))
        return
    render_text()


def emit_query_rows(
    *,
    output_format: str,
    title: str,
    columns: Sequence[tuple[str, str] | tuple[str, str, dict[str, Any]]],
    rows: Sequence[Mapping[str, Any]],
    meta: Mapping[str, Any] | None = None,
    renderers: Mapping[str, Callable[[Any, Mapping[str, Any]], Any]] | None = None,
) -> None:
    payload: dict[str, Any] = {"format": "json", "rows": list(rows)}
    if meta is not None:
        payload["meta"] = dict(meta)

    def _render() -> None:
        table = Table(title=title)
        for col in columns:
            _, label, *rest = col
            col_kwargs: dict[str, Any] = rest[0] if rest else {}
            table.add_column(label, **col_kwargs)

        cell_renderers = renderers or {}
        for row in rows:
            cells: list[Any] = []
            for key, *_ in columns:
                value = row.get(key, "")
                renderer = cell_renderers.get(key)
                cells.append(renderer(value, row) if renderer is not None else str(value))
            table.add_row(*cells)

        console = get_console(file=click.get_text_stream("stdout"))
        console.print(table)

    emit(output_format=output_format, payload=payload, render_text=_render)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_output_emit.py -q`
Expected: PASS (all parametrizations).

- [ ] **Step 5: Run the existing emit_query_rows consumers + lint/types**

Run: `cd science && uv run --frozen pytest tests/ -q -k "output or emit or color" && uv run ruff check src/science_tool/output.py && uv run pyright`
Expected: PASS; no new ruff/pyright findings in `output.py`.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/output.py science/tests/test_output_emit.py
git commit -m "Add output.emit primitive; re-express emit_query_rows on it (convergence Phase 3)"
```

---

## Task 2: Migrate `cli.py` — entities / graph / inquiry / tasks / project group

**Files:**
- Modify: `science/src/science_tool/cli.py`

**Interfaces:**
- Consumes: `emit` from Task 1 (`from science_tool.output import emit` — add to the existing `output` import if one exists, else add the import).

**Target functions** (all in `cli.py`; apply the migration recipe to each — plain `indent=2` unless noted):
`entities_audit_identifiers_command:314`, `entities_mark_superseded_command:326`, `entities_archive_command:343`, `entities_unarchive_command:364`, `entities_consolidate_scaffold_command:395`, `entities_consolidate_apply_command:413`, `explore_ideas_apply:1255`, `explore_ideas_gaps:1336`, `explore_ideas_resolve_anchors:1358`, `_emit_entity_show:1503` *(`sort_keys=True`; also has a `console.print(Text(...))` — leave that; only the JSON `echo(dumps)` moves)*, `graph_cross_impact:1908` *(`sort_keys=True`)*, `graph_export_json:2308` *(`sort_keys=True`; `payload.model_dump(mode="json")` stays as the payload expression)*, `inquiry_show:3138` *(`default=str`)*, `inquiry_validate:3184`, `tasks_blockers:3794`, `tasks_show:4223` *(`sort_keys=True`)*, `tasks_summary:4273`, `project_topic_coverage:4344`, `project_resolve_refs:4393`, `project_verify:4477` *(`sort_keys=True`; gates on precomputed `emit_json = as_json or output_format == "json"` — pass `output_format="json" if emit_json else output_format`; keep the stderr echo at :4509)*, `_emit_verify_error:4513` *(keep stderr echo at :4523)*.

**Worked example** (the one-liner form — most of this group):

```python
# BEFORE  (cli.py:314)
def entities_audit_identifiers_command(project_path: Path) -> None:
    click.echo(json.dumps(audit_identifiers(project_path), indent=2))

# AFTER
def entities_audit_identifiers_command(project_path: Path) -> None:
    emit(output_format="json", payload=audit_identifiers(project_path), render_text=lambda: None)
```

For this command there is no `output_format` parameter — it is JSON-only, so `output_format="json"` is passed literally and `render_text` is a no-op. Where the command *does* take `output_format` and builds a table (e.g. `tasks_show`, `project_verify`), pass the real `output_format` and move the table code into a nested `_render` per the recipe.

- [ ] **Step 1: Migrate every listed function** using the recipe and variant table. Preserve all stderr `click.echo(..., err=True)` calls verbatim. For `inquiry_show`, pass `default=str`.

- [ ] **Step 2: Run the covering tests**

Run: `cd science && uv run --frozen pytest tests/ -q -k "entities or graph or inquiry or task or project or explore_ideas or verify"`
Expected: PASS.

- [ ] **Step 3: Full suite + snapshot gate (byte-identity proof for this file)**

Run: `cd science && uv run --frozen pytest -q && uv run --frozen pytest -m snapshot -q`
Expected: PASS; zero failures. Any moved byte in a `--format json` output surfaces here.

- [ ] **Step 4: Lint**

Run: `cd science && uv run ruff check src/science_tool/cli.py && uv run pyright`
Expected: no new findings. Remove any now-unused `json` references only if `json` is unused in the whole file (it is not — leave the module import).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py
git commit -m "Migrate cli.py entities/graph/inquiry/tasks/project emitters onto output.emit (convergence Phase 3)"
```

---

## Task 3: Migrate `cli.py` — benchmark / dataset / paper / health group

**Files:**
- Modify: `science/src/science_tool/cli.py`

**Interfaces:**
- Consumes: `emit` (Task 1); the `import` added in Task 2.

**Target functions** (all `cli.py`; several use a function-local `import json as _json` — migrate the emitter AND delete the now-unused `import json as _json` line):
`datasets_qa:3467` *(`sort_keys=True`; keep the stderr echo at :3490)*, `health_command:4635` *(TWO json branches — `list_checks` at :4655 and main at :4681; migrate both; keep the stderr "Health timings:" echo; delete `import json as _json`)*, `paper_fetch_cmd:5050` *(`_json` alias)*, `question_reserve_cmd:5251` *(`_json` alias; compound `as_json or output_format == "json"` — use `effective_format`)*, `bib_add:5336` *(`_json` alias; `indent=None` — no indent in current form; compound `as_json or output_format == "json"` — use `effective_format`)*, `benchmark_list:5535` *(keep stderr echo :5561)*, `benchmark_opportunities:5621` *(keep the intermediate `json.dumps(value, sort_keys=True)` at :5685 — it feeds the payload, is not emitted)*, `benchmark_gap_calibration:5738`, `benchmark_tests:5883` *(keep stderr echo :5934)*, `benchmark_test_triage:6024` *(keep stderr echoes)*, `benchmark_hint_candidates:6517` *(keep stderr echoes)*, `benchmark_gaps:6622` *(keep intermediate sort-key dumps at :6731,:6740)*, `dataset_prioritize:6871` *(`_json` alias; TWO branches at :6939 and :6961)*, `dataset_reconcile_links:7222` *(`_json` alias)*, `dataset_stochasticity:7351` *(`_json` alias; keep stderr echo :7370)*.

**Worked example** (`_json` alias + delete the local import):

```python
# BEFORE  (cli.py:4635 health_command, abridged)
def health_command(...) -> None:
    import json as _json
    ...
    if output_format == "json":
        click.echo(_json.dumps({"checks": available_checks}, indent=2))
        return
    table = Table(title="Health checks")
    ...
    get_console().print(table)
    return
    ...
    if output_format == "json":
        click.echo(_json.dumps(report, indent=2))
        return
    ...

# AFTER
def health_command(...) -> None:
    ...  # `import json as _json` deleted
    if list_checks:
        def _render_checks() -> None:
            table = Table(title="Health checks")
            ...
            get_console().print(table)
        emit(output_format=output_format, payload={"checks": available_checks}, render_text=_render_checks)
        return
    ...
    def _render_report() -> None:
        ...  # the existing human-report code, verbatim
    emit(output_format=output_format, payload=report, render_text=_render_report)
```

> **Note for the implementer:** where an intermediate `json.dumps(value, sort_keys=True)` builds part of the payload (benchmark_opportunities/gaps), it is *not* an emission and must stay. After migration these functions still contain a `.dumps` call, so the Task 7 guard will report them; that is expected and they are resolved in Task 7 (either the residual dumps has no co-located echo → not flagged, or it does → allowlisted with a reason). Do not contort the code to remove a legitimate intermediate `dumps`.

- [ ] **Step 1: Migrate every listed function.** Delete each now-unused `import json as _json`. Keep every stderr echo and every intermediate (non-emitted) `dumps`. `bib_add` uses `indent=None`.

- [ ] **Step 2: Covering tests**

Run: `cd science && uv run --frozen pytest tests/ -q -k "health or benchmark or dataset or paper or question or bib"`
Expected: PASS.

- [ ] **Step 3: Full suite + snapshot gate**

Run: `cd science && uv run --frozen pytest -q && uv run --frozen pytest -m snapshot -q`
Expected: PASS.

- [ ] **Step 4: Lint / types**

Run: `cd science && uv run ruff check src/science_tool/cli.py && uv run pyright`
Expected: no new findings (deleting the unused `import json as _json` clears any F401).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py
git commit -m "Migrate cli.py benchmark/dataset/paper/health emitters onto output.emit (convergence Phase 3)"
```

---

## Task 4: Migrate `annotation/cli.py`

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`

**Interfaces:**
- Consumes: `emit` (Task 1) — add `from science_tool.output import emit`.

**Target functions** (26; all in `annotation/cli.py`). Most are the one-liner `click.echo(json.dumps(payload, indent=2[, sort_keys=True]))` form; two are private helpers to fold-and-delete:
`ingest_prose_decomposition_cmd:119`, `check_prose_decomposition_cmd:176`, `validate_prose_decomposition_artifact_cmd:221`, `promote_prose_decomposition_cmd:278`, `apply_prose_promotion_plan_cmd:347`, `ground_prose_decomposition_cmd:385` *(`sort_keys=True`)*, `cross_paper_evidence_cmd:443` *(`sort_keys=True`)*, `archive_superseded_propositions_cmd:490` *(`sort_keys=True`)*, `reconcile_propositions_cmd:553` *(`sort_keys=True`)*, `validate_proposition_reconciliation_cmd:654`, `plan_proposition_reconciliation_cmd:707` *(one-hop: `json_text = json.dumps(...)` then `click.echo(json_text)` — collapse to `emit(..., payload=payload, ...)`)*, `record_proposition_reconciliation_decisions_cmd:804`, `scaffold_proposition_resynthesis_cmd:887` *(migrate the **emission** at :948 only; the file-write `json.dumps` at :933 stays → guard-allowlisted in Task 7; keep the "wrote JSON draft" status echo)*, `resynthesis_draft_context_cmd:976` *(one-hop: `output_text = json.dumps(...)` then `click.echo(output_text, nl=False)` — this uses `nl=False`; see note)*, `validate_proposition_resynthesis_cmd:1032`, `apply_proposition_resynthesis_cmd:1078`, `apply_proposition_reconciliation_cmd:1138`, `build_prose_health_cmd:1226`, `_emit_json:1449` *(private helper — fold into callers, delete)*, `audit_cmd:1547` *(keep stderr echo :1560)*, `lift_tokens_cmd:1664` *(keep stderr echo :1691)*, `_emit_list_json:2048` *(private helper — fold into callers, delete)*, `stats_cmd:2244` *(`indent` present? current is `json.dumps({...})` — check; pass `indent=None` if no indent)*, `extract_cmd:2386`, `promote_cmd:2505`, `synthesize_cmd:2630`.

> **`nl=False` sites** (`resynthesis_draft_context_cmd:1020`): the current code writes `click.echo(output_text, nl=False)` — no trailing newline. `emit` uses `click.echo(...)` which appends `\n`. To preserve bytes, **do not migrate the `nl=False` site to `emit`** (it is not the canonical `echo(dumps)+newline` shape). Leave it as-is and record it as a Task 7 allowlist entry with reason `"nl=False: byte output intentionally omits trailing newline"`. Verify whether `resynthesis_draft_context_cmd` is JSON-only or has a human branch before deciding; if JSON-only with `nl=False`, allowlist rather than migrate.

> **Helper-fold** (`_emit_json:1449`, `_emit_list_json:2048`): find every caller (they are called from inside `if ... == "json":` branches), replace each caller's branch with an `emit(...)` call whose `render_text` is that command's existing human-output code, then delete the helper. If a helper is called from many commands and folding each is impractical in one pass, keep the helper but re-express its body as `emit(output_format="json", payload=payload, render_text=lambda: None, **kwargs)` and record the helper as a Task 7 allowlist... — **no**: a helper re-expressed on `emit` contains no `echo`/`dumps` and needs no allowlist. Prefer that form if folding-into-callers is impractical.

- [ ] **Step 1: Migrate every listed function.** Fold-and-delete the two private helpers (or re-express them on `emit`). Handle `sort_keys=True` sites and any `indent=None` sites per the variant table. Leave the `nl=False` site unmigrated (Task 7 allowlist). Keep all stderr echoes.

- [ ] **Step 2: Covering tests**

Run: `cd science && uv run --frozen pytest tests/ -q -k "annotat or prose or proposition or resynth or reconcil"`
Expected: PASS.

- [ ] **Step 3: Full suite + snapshot gate**

Run: `cd science && uv run --frozen pytest -q && uv run --frozen pytest -m snapshot -q`
Expected: PASS.

- [ ] **Step 4: Lint / types**

Run: `cd science && uv run ruff check src/science_tool/annotation/cli.py && uv run pyright`
Expected: no new findings.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/cli.py
git commit -m "Migrate annotation/cli.py emitters onto output.emit (convergence Phase 3)"
```

---

## Task 5: Migrate the mid-size CLI modules

**Files:**
- Modify: `science/src/science_tool/commons/cli.py`, `science/src/science_tool/dag/cli.py`, `science/src/science_tool/big_picture/cli.py`, `science/src/science_tool/curate/cli.py`, `science/src/science_tool/peers_cli.py`

**Interfaces:**
- Consumes: `emit` (Task 1) — add `from science_tool.output import emit` to each file.

**Target functions:**
- `commons/cli.py` (11): `index_rebuild_cmd:107`, `show_cmd:159` *(also has a non-emitted `dumps` at :184 — check whether it is echoed; if not, leave it)*, `find_cmd:235`, `validate_cmd:375` *(non-emitted dumps at :430 — leave if not echoed)*, `dataset_init_cmd:487`, `dataset_status_cmd:585`, `dataset_validate_cmd:630`, `data_resolve_cmd:696`, `member_payload_cmd:731`, `reference_graph_scaffold_member_cmd:779`, `reference_graph_resolve_member_cmd:827`.
- `dag/cli.py` (3): `audit_cmd:184`, `validate_cmd:290`, `apply_workbench_cmd:354`.
- `big_picture/cli.py` (3): `resolve_questions_cmd:38` *(`sort_keys=True`)*, `knowledge_gaps_cmd:98` *(`sort_keys=True`)*, `cluster_digests_cmd:138`.
- `curate/cli.py` (2): `inventory_cmd:33`, `consolidation_candidates_cmd:55` *(`report.model_dump(mode="json")` is the payload expression)*.
- `peers_cli.py` (2): `peers_list:49`, `peers_check:74`.

- [ ] **Step 1: Migrate every listed function** across the five files, applying the recipe and variant table. Where a function has a second `dumps` that is *not* echoed (builds part of the payload or writes a file), leave it — the guard will not flag a `dumps` in a function that no longer has a co-located emission.

- [ ] **Step 2: Covering tests**

Run: `cd science && uv run --frozen pytest tests/ -q -k "commons or dag or big_picture or curate or peer"`
Expected: PASS.

- [ ] **Step 3: Full suite + snapshot gate**

Run: `cd science && uv run --frozen pytest -q && uv run --frozen pytest -m snapshot -q`
Expected: PASS.

- [ ] **Step 4: Lint / types**

Run: `cd science && uv run ruff check src/science_tool/commons/cli.py src/science_tool/dag/cli.py src/science_tool/big_picture/cli.py src/science_tool/curate/cli.py src/science_tool/peers_cli.py && uv run pyright`
Expected: no new findings.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/cli.py science/src/science_tool/dag/cli.py science/src/science_tool/big_picture/cli.py science/src/science_tool/curate/cli.py science/src/science_tool/peers_cli.py
git commit -m "Migrate commons/dag/big_picture/curate/peers emitters onto output.emit (convergence Phase 3)"
```

---

## Task 6: Migrate the single-emitter files

**Files:**
- Modify: `book_split_cli.py`, `markers_cli.py`, `prose_lint_cli.py`, `qa_audit/cli.py`, `refs_cli.py`, `research_package/cli.py`, `search_cli.py`, `skills_lint/cli.py`, `validate/cli.py`, `verdict/cli.py`, `project_artifacts/cli.py` (all under `science/src/science_tool/`)

**Interfaces:**
- Consumes: `emit` (Task 1) — add `from science_tool.output import emit` to each file.

**Target functions (one each unless noted):**
- `book_split_cli.py`: `book_split_command:20` *(compound `as_json or output_format == "json"` — use `effective_format`)*.
- `markers_cli.py`: `scan:48` *(there is also a COMPLEX `== "json"` branch at :62 with no inline dumps — leave it)*.
- `prose_lint_cli.py`: `lint_cmd:34`.
- `qa_audit/cli.py`: `qa_audit_command:27` *(`sort_keys=True`; compound `as_json or output_format == "json"` — use `effective_format`; the human branch's `click.echo(md, nl=False)` moves verbatim into `render_text`)*.
- `refs_cli.py`: `check:85`.
- `research_package/cli.py`: `validate_cmd:61` *(compound `as_json or output_format == "json"` — use `effective_format`)*.
- `search_cli.py`: `search_command:24` *(`sort_keys=True`)*.
- `skills_lint/cli.py`: `lint_cmd:17`.
- `validate/cli.py`: `validate_cmd:68` *(keep stderr sidecar echo :98)*.
- `verdict/cli.py`: `_emit_json:240` *(private helper `json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)` — fold into its callers at the `if output_format == "json": _emit_json(payload); return` sites, e.g. :113, then delete; or re-express on `emit` with `sort_keys=True, ensure_ascii=False`)*.
- `project_artifacts/cli.py`: `check_cmd:88` *(`_json` alias — migrate and delete `import json as _json`; compound `as_json or output_format == "json"` — use `effective_format`)*.

- [ ] **Step 1: Migrate every listed function.** For `verdict/cli.py:_emit_json`, prefer folding into its callers with `sort_keys=True, ensure_ascii=False`; if impractical, re-express the helper as `emit(output_format="json", payload=payload, render_text=lambda: None, sort_keys=True, ensure_ascii=False)`. Delete `import json as _json` in `project_artifacts/cli.py`.

- [ ] **Step 2: Covering tests**

Run: `cd science && uv run --frozen pytest tests/ -q -k "book_split or marker or prose_lint or qa_audit or refs or research_package or search or skills_lint or validate or verdict or project_artifact"`
Expected: PASS.

- [ ] **Step 3: Full suite + snapshot gate**

Run: `cd science && uv run --frozen pytest -q && uv run --frozen pytest -m snapshot -q`
Expected: PASS.

- [ ] **Step 4: Lint / types**

Run: `cd science && uv run ruff check src/science_tool && uv run pyright`
Expected: no new findings.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool
git commit -m "Migrate remaining single-emitter CLI modules onto output.emit (convergence Phase 3)"
```

---

## Task 7: The output-boundary AST guard

**Files:**
- Create: `science/tests/test_output_boundary.py`

**Interfaces:**
- Consumes: the fully-migrated tree from Tasks 2–6.

**The rule:** outside `science_tool/output.py`, no single function may contain BOTH (a) an emission call — `click.echo`, bare `print`, `console.print`, or `sys.stdout.write` — AND (b) a call to any attribute named `dumps` (alias-blind). Function-scoped, so file-writing/hashing `dumps` (in functions with no emission) and stderr-only functions (no `dumps`) both pass. `.dumps` matched by attribute name, not module binding, so `json.dumps`/`_json.dumps`/`yaml.dumps` all match.

- [ ] **Step 1: Write the guard test** (model it on `tests/test_frontmatter_boundary.py`).

Create `science/tests/test_output_boundary.py`:

```python
"""Output-emitter boundary guard (convergence Phase 3).

Additive ratchet: a *new* hand-rolled JSON emitter must not appear outside the
canonical module (science_tool/output.py) and the named allowlist below.

Detection: a function violates the boundary if its body contains BOTH an
emission call (click.echo / bare print / console.print / sys.stdout.write) AND a
call to any attribute named ``dumps`` (json.dumps, _json.dumps, yaml.dumps — any
alias; matched by attribute name so it is binding-blind). Function-scoped, so a
``dumps`` that writes a file or builds a hash in a function with no emission call
passes, and a function with only stderr echoes and no ``dumps`` passes. Nested
defs/lambdas bind to their own nearest enclosing function.

Known gap, stated rather than hidden: a helper that returns a JSON *string*
echoed by a different function evades this (cross-function). So would a fence
built via ``str.format``. This is a ratchet against the bare ``echo(dumps(...))``
form that recurred across the tree, not a sandbox — the same class of limit the
durable-write and frontmatter guards document candidly.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SCIENCE_SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"
_CANONICAL = _SCIENCE_SRC / "output.py"

_EMISSION_ATTRS = {"echo", "print"}  # click.echo, console.print, sys.stdout.<write> handled below


def _is_emission_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    # bare print(...)
    if isinstance(func, ast.Name) and func.id == "print":
        return True
    if isinstance(func, ast.Attribute):
        # click.echo(...), console.print(...), <anything>.print(...)
        if func.attr in {"echo", "print"}:
            return True
        # sys.stdout.write(...)  /  <stream>.write(...) on stdout
        if func.attr == "write" and isinstance(func.value, ast.Attribute) and func.value.attr == "stdout":
            return True
    return False


def _is_dumps_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "dumps"


def _nearest_function_bodies(tree: ast.Module) -> list[ast.AST]:
    """Every FunctionDef/AsyncFunctionDef node in the module."""
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _direct_children_calls(func: ast.AST) -> list[ast.AST]:
    """Calls bound to THIS function, not descending into nested def/lambda."""
    calls: list[ast.AST] = []

    class _Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node is func:
                self.generic_visit(node)  # descend into the target itself

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node is func:
                self.generic_visit(node)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            return  # lambdas bind to themselves

        def visit_Call(self, node: ast.Call) -> None:
            calls.append(node)
            self.generic_visit(node)

    _Visitor().visit(func)
    return calls


def _function_is_emitter(func: ast.AST) -> bool:
    calls = _direct_children_calls(func)
    return any(_is_emission_call(c) for c in calls) and any(_is_dumps_call(c) for c in calls)


def _emitter_functions() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    repo_root = Path(__file__).resolve().parents[1]
    for path in _SCIENCE_SRC.rglob("*.py"):
        if path == _CANONICAL:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = str(path.relative_to(repo_root))
        for func in _nearest_function_bodies(tree):
            if _function_is_emitter(func):
                found.append((rel, func.name))
    return found


# (rel_path, function_name) -> reason. Functions that legitimately keep a stderr
# echo beside a file/hash dumps, or a byte-form the canonical emitter cannot
# reproduce. Fill from the Step-2 detector run against the migrated tree.
_ALLOWED_EMITTERS: dict[tuple[str, str], str] = {
    # Fill in Step 2 — expected members:
    #   ("src/science_tool/datasets_identity.py", "_stamp_datapackage"):
    #       "stderr-only echoes; dumps serializes a datapackage descriptor to disk",
    #   ("src/science_tool/annotation/cli.py", "scaffold_proposition_resynthesis_cmd"):
    #       "emission migrated; residual dumps writes a JSON draft file beside a status echo",
    #   ("src/science_tool/annotation/cli.py", "resynthesis_draft_context_cmd"):
    #       "nl=False: byte output intentionally omits trailing newline",
}


def test_no_new_output_emitters() -> None:
    offenders = [pair for pair in _emitter_functions() if pair not in _ALLOWED_EMITTERS]
    assert not offenders, (
        "New hand-rolled JSON emitter(s) found outside science_tool/output.py and "
        "the named allowlist. Route output through science_tool.output.emit(...); "
        "if a stderr echo legitimately shares a function with a file/hash dumps, "
        f"add an _ALLOWED_EMITTERS entry with a reason. Offenders: {sorted(offenders)}"
    )


def test_allowlist_has_no_stale_entries() -> None:
    live = set(_emitter_functions())
    stale = [pair for pair in _ALLOWED_EMITTERS if pair not in live]
    assert not stale, (
        "Allowlisted entries no longer detected as emitters (migrated or removed?). "
        f"Delete these stale entries: {sorted(stale)}"
    )
```

- [ ] **Step 2: Run the detector against the migrated tree and fill the allowlist**

Run: `cd science && uv run --frozen pytest tests/test_output_boundary.py::test_no_new_output_emitters -q`
Expected initially: FAIL, listing the functions that still trip the rule. For **each** offender, decide:
- It is a genuine stderr-echo + file/hash `dumps` survivor (e.g. `datasets_identity._stamp_datapackage`, `annotation/cli.py:scaffold_proposition_resynthesis_cmd`, the `nl=False` site) → add an `_ALLOWED_EMITTERS` entry with a specific reason.
- It is a migration miss (a real `echo(json.dumps(payload))` that should have moved to `emit`) → **go back and migrate it** in the appropriate file; do not allowlist it.

Iterate until `test_no_new_output_emitters` passes with a fully-populated, reason-tagged allowlist.

- [ ] **Step 3: Verify the guard actually bites (sanity check)**

Temporarily add to any non-`output.py` module a function `def _probe(): click.echo(json.dumps({}))`, run `pytest tests/test_output_boundary.py::test_no_new_output_emitters -q`, confirm it FAILS naming `_probe`, then remove the probe. (Do not commit the probe.)

- [ ] **Step 4: Run the guard + full suite**

Run: `cd science && uv run --frozen pytest tests/test_output_boundary.py -q && uv run --frozen pytest -q && uv run --frozen pytest -m snapshot -q && uv run ruff check tests/test_output_boundary.py && uv run pyright`
Expected: PASS across the board; the allowlist has no stale entries.

- [ ] **Step 5: Commit**

```bash
git add science/tests/test_output_boundary.py
git commit -m "Guard: ban new hand-rolled JSON emitters outside output.py (convergence Phase 3)"
```

---

## Deferred / explicitly out of scope

- **A generic table DSL.** The ~37 hand-written `Table(...)` blocks in `cli.py` are genuinely different; they move into `render_text` callbacks verbatim and stay hand-written. They are extracted with their command groups in Phase 4, not here.
- **CLI extraction (Phase 4).** Moving inline command groups out of `cli.py` into `<domain>/cli.py` modules is a separate phase that depends on Phases 1–3.
- **The cross-function emission gap.** A helper returning a JSON string echoed elsewhere evades the guard; documented in the guard docstring, not closed here.
- **Rewriting stderr diagnostic style.** Existing `click.echo(..., err=True)` diagnostics are preserved exactly; converging *those* is not this phase.

---

## Self-review notes

- **Spec coverage:** design's `emit` signature (extended with byte-identity kwargs, justified in Global Constraints) → Task 1; migrate 89-inline/95-function surface → Tasks 2–6; guard keyed on attribute-named `dumps` + `sys.stdout.write`, scoped to function, allowlist written against migrated tree → Task 7; byte-identity contract → per-task snapshot gate; "not a table DSL" → Deferred.
- **Count reconciliation:** the design cites "55 `emit_query_rows` call sites" and "89 `== "json"`"; the actual in-tree figures are 48 and 48 respectively (design over-counted, likely counting test callers and planned sites). The migration is scoped to the **95 functions that contain both an emission and an inline `dumps`**, enumerated per task — that surface, not the design's round numbers, is authoritative.
- **Known residuals handed to Task 7:** `nl=False` site (`resynthesis_draft_context_cmd`), stderr-echo + file-dumps survivors (`_stamp_datapackage`, `scaffold_proposition_resynthesis_cmd`), and intermediate sort-key dumps (`benchmark_opportunities`/`benchmark_gaps`) — each explicitly noted at its task and expected in the allowlist or as a no-longer-co-located `dumps`.
