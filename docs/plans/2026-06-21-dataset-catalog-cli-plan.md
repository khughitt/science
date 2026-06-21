# Dataset Catalog CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the singular `science dataset` group ergonomic catalog commands — author a candidate, list/filter, show one, list its consumers — plus a validate check enforcing "acquired ⇒ has a data pointer".

**Architecture:** New logic lives in `science/src/science_tool/datasets_catalog.py`; the existing `dataset` Click group in `cli.py` gains thin command wrappers that delegate to it. A new validate check `dataset_acquisition.py` mirrors the existing `dataset_taxonomy.py` pure-core + `@Check` pattern. The hand-author template default flips to `candidate`. The plural `datasets` discovery group and `register-run`/`reconcile` are untouched.

**Tech Stack:** Python 3.12+, Click, rich, pytest. `uv run --frozen` for all commands.

**Spec:** `docs/plans/2026-06-21-dataset-catalog-cli-design.md`

## Global Constraints

- Run every command from the science repo root (`~/d/science`). Prefix tool invocations with `uv run --frozen`.
- Work on branch `dataset-catalog-cli` (already checked out).
- One commit per task. **Do NOT** add `Co-Authored-By` trailers.
- Use `~/d/` (not `/home/keith/d/` or `/mnt/ssd/...`) in any doc/code path text.
- CLI tests use `click.testing.CliRunner().invoke(science_cli, [...], catch_exceptions=False, env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})`. CliRunner mixes stderr into `res.output` by default.
- Validate checks read **raw frontmatter** via `dataset_frontmatters(ctx)`; each fm dict carries `_path`, `id`, and either `kind` or `type` (accept either, value `"dataset"`).
- `Result(severity, path_or_None, None, message, rule, None)`; `Severity` enum is `ERROR | WARN | INFO` (no `FAIL`).
- `dataset` has **no path policy** — never call `generate_entity_id`/`validate_entity_id`/`path_for_entity` for it; synthesize `f"dataset:{slug}"` and validate the slug with `validate_slug`.

---

## File Structure

- Create: `science/src/science_tool/datasets_catalog.py` — `add_dataset`, `list_datasets`, `resolve_dataset`, `show_dataset`, `list_consumers` (pure-ish functions; CLI wrappers stay in `cli.py`).
- Create: `science/src/science_tool/validate/checks/dataset_acquisition.py` — the acquisition check.
- Modify: `science/src/science_tool/validate/checks/__init__.py` — register the new check module.
- Modify: `science/src/science_tool/cli.py` — add `dataset add|show|consumers` commands; rework `dataset list`.
- Modify: `science/model/src/science_model/templates/dataset.md` — default `status: "active"` → `"candidate"`.
- Create tests: `science/tests/test_dataset_acquisition_check.py`, `science/tests/test_dataset_add_cli.py`, `science/tests/test_dataset_show_consumers_cli.py`.
- Modify tests: `science/tests/test_datasets_list_cli.py` — add filter + type-filter coverage.

---

## Task 1: Acquisition check + template default flip

**Files:**
- Create: `science/src/science_tool/validate/checks/dataset_acquisition.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py` (add `"dataset_acquisition"` to `CANONICAL_CHECK_MODULES`)
- Modify: `science/model/src/science_model/templates/dataset.md:5`
- Test: `science/tests/test_dataset_acquisition_check.py`

**Interfaces:**
- Produces: `evaluate_dataset_acquisition(datasets: Iterable[dict]) -> Iterator[Result]` and `@Check`-decorated `check_dataset_acquisition(ctx) -> Iterator[Result]`. Rule string: `"dataset.acquired-without-pointer"`.

- [ ] **Step 1: Write the failing unit test**

Create `science/tests/test_dataset_acquisition_check.py`:

```python
"""Tests for the dataset acquisition check (acquired ⇒ datapackage|local_path)."""

from __future__ import annotations

from science_tool.validate.checks.dataset_acquisition import evaluate_dataset_acquisition
from science_tool.validate.result import Severity


def _fm(**kw):
    base = {"type": "dataset", "id": "dataset:x", "_path": "doc/datasets/x.md"}
    base.update(kw)
    return base


def test_candidate_without_pointer_is_ok():
    assert list(evaluate_dataset_acquisition([_fm(status="candidate")])) == []


def test_active_without_pointer_errors():
    results = list(evaluate_dataset_acquisition([_fm(status="active")]))
    assert len(results) == 1
    assert results[0].severity is Severity.ERROR
    assert results[0].rule == "dataset.acquired-without-pointer"


def test_active_with_datapackage_is_ok():
    assert list(evaluate_dataset_acquisition([_fm(status="active", datapackage="r/dp.yaml")])) == []


def test_active_with_local_path_is_ok():
    assert list(evaluate_dataset_acquisition([_fm(status="active", local_path="x.csv")])) == []


def test_non_dataset_is_skipped():
    assert list(evaluate_dataset_acquisition([{"type": "paper", "status": "active", "_path": "p"}])) == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --frozen pytest science/tests/test_dataset_acquisition_check.py -v`
Expected: FAIL — `ModuleNotFoundError: ... dataset_acquisition`.

- [ ] **Step 3: Implement the check**

Create `science/src/science_tool/validate/checks/dataset_acquisition.py`:

```python
"""Dataset acquisition check: an acquired dataset must carry a data pointer.

Acquisition lifecycle lives on `status` (candidate = not yet acquired); the data
pointer is `datapackage` OR `local_path` (the single-file escape hatch). Reads raw
frontmatter like dataset_taxonomy, re-enforcing the rule with a friendly message.
See docs/plans/2026-06-21-dataset-catalog-cli-design.md.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def evaluate_dataset_acquisition(datasets: Iterable[dict[str, Any]]) -> Iterator[Result]:
    """Pure core: `datasets` are raw frontmatter dicts (each with `_path`)."""
    for fm in datasets:
        if (fm.get("kind") or fm.get("type")) != "dataset":
            continue
        if fm.get("status") == "candidate":
            continue  # not-yet-acquired: pointer optional
        if fm.get("datapackage") or fm.get("local_path"):
            continue  # acquired and pointed
        ident = fm.get("id", "?")
        path = fm.get("_path")
        yield Result(
            Severity.ERROR,
            Path(path) if path else None,
            None,
            f"{ident}: acquired dataset (status={fm.get('status')!r}) has no "
            f"datapackage or local_path; set status: candidate if not yet acquired, "
            f"or add a datapackage/local_path pointer",
            "dataset.acquired-without-pointer",
            None,
        )


@Check(section="dataset acquisition", order=32)
def check_dataset_acquisition(ctx: ValidateContext) -> Iterator[Result]:
    yield from evaluate_dataset_acquisition(dataset_frontmatters(ctx))
```

- [ ] **Step 4: Register the check module**

In `science/src/science_tool/validate/checks/__init__.py`, add `"dataset_acquisition"` to `CANONICAL_CHECK_MODULES` immediately after `"dataset_taxonomy"`:

```python
    "dataset_taxonomy",
    "dataset_acquisition",
    "dataset_metadata",
```

- [ ] **Step 5: Flip the template default**

In `science/model/src/science_model/templates/dataset.md`, change line 5 from `status: "active"` to:

```yaml
status: "candidate"               # candidate (not yet acquired) | active (acquired, has datapackage/local_path)
```

- [ ] **Step 6: Add a template-default regression test**

Append to `science/tests/test_dataset_acquisition_check.py`:

```python
def test_template_default_status_is_candidate():
    from importlib.resources import files

    text = files("science_model").joinpath("templates/dataset.md").read_text(encoding="utf-8")
    assert 'status: "candidate"' in text
    assert 'status: "active"' not in text
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run --frozen pytest science/tests/test_dataset_acquisition_check.py -v`
Expected: PASS (6 tests).

- [ ] **Step 8: Verify the check is wired and existing validation still passes**

Run: `uv run --frozen pytest science/tests/test_datasets_validate_cli.py science/tests/test_dataset_register_run.py -q`
Expected: PASS (registration of the new module does not break the suite).

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/validate/checks/dataset_acquisition.py \
        science/src/science_tool/validate/checks/__init__.py \
        science/model/src/science_model/templates/dataset.md \
        science/tests/test_dataset_acquisition_check.py
git commit -m "feat(validate): dataset acquisition check + candidate template default"
```

---

## Task 2: `dataset add`

**Files:**
- Create: `science/src/science_tool/datasets_catalog.py`
- Modify: `science/src/science_tool/cli.py` (add `dataset_add` command in the `dataset` group, near line 5208)
- Test: `science/tests/test_dataset_add_cli.py`

**Interfaces:**
- Produces: `add_dataset(project_root: Path, slug: str, *, title: str, origin="external", tier="track", level="controlled", source_url="", ontology_terms=(), related=(), today=None) -> tuple[str, Path, list[str]]` returning `(entity_id, dest_path, warnings)`. Raises `science_tool.entities.EntityCommandError` on bad slug, derived origin, or existing destination.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_dataset_add_cli.py`:

```python
"""Tests for `science dataset add`."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _add(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["dataset", "add", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )


def test_add_creates_candidate_entity(tmp_path: Path) -> None:
    res = _add(tmp_path, "my-set", "--title", "My Set", "--source-url", "https://example.org")
    assert res.exit_code == 0, res.output
    p = tmp_path / "doc" / "datasets" / "my-set.md"
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    assert "dataset:my-set" in text
    assert "status: candidate" in text
    assert "origin: external" in text
    assert "license: unknown" in text
    assert "verified: false" in text


def test_add_rejects_derived(tmp_path: Path) -> None:
    res = _add(tmp_path, "x", "--title", "X", "--origin", "derived")
    assert res.exit_code == 1
    assert "register-run" in res.output


def test_add_rejects_existing_destination(tmp_path: Path) -> None:
    _add(tmp_path, "dup", "--title", "Dup")
    res = _add(tmp_path, "dup", "--title", "Dup again")
    assert res.exit_code == 1
    assert "already exists" in res.output


def test_add_rejects_bad_slug(tmp_path: Path) -> None:
    res = _add(tmp_path, "Bad_Slug", "--title", "Bad")
    assert res.exit_code == 1
    assert "slug" in res.output.lower()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --frozen pytest science/tests/test_dataset_add_cli.py -v`
Expected: FAIL — `dataset add` is not a command (Click usage error / exit 2).

- [ ] **Step 3: Implement `add_dataset` in the new module**

Create `science/src/science_tool/datasets_catalog.py`:

```python
"""Catalog commands for the singular `dataset` group: add / list / show / consumers.

`dataset` has no path policy, so ids are synthesized directly (validate_slug +
f-string) rather than via generate_entity_id. See
docs/plans/2026-06-21-dataset-catalog-cli-design.md.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import yaml

from science_tool.entities import (
    EntityCommandError,
    _validate_prospective_write,
    validate_slug,
)


def _render_candidate(
    entity_id: str,
    *,
    title: str,
    origin: str,
    tier: str,
    level: str,
    source_url: str,
    ontology_terms,
    related,
    today: date,
) -> str:
    # Build the frontmatter as a dict and serialize with yaml.safe_dump so any
    # quote/newline/colon in user input cannot break the document or inject
    # fields ahead of _validate_prospective_write's parse.
    iso = today.isoformat()
    fm: dict = {
        "id": entity_id,
        "type": "dataset",
        "title": title,
        "status": "candidate",
        "created": iso,
        "updated": iso,
        "origin": origin,
        "source_class": "observational",
        "tier": tier,
        "license": "unknown",
        "access": {
            "level": level,
            "availability": "available",
            "verified": False,
            "source_url": source_url,
        },
        "accessions": [],
        "ontology_terms": list(ontology_terms),
        "related": list(related),
    }
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    body = (
        f"# {title}\n\n"
        "**Candidate dataset.** `status: candidate` — catalogued but not yet acquired.\n\n"
        "## What it is\n\n_One-paragraph description (fill in)._\n\n"
        "## Why it fits\n\n_Relevance to the task/question that motivated cataloguing it (fill in)._\n\n"
        "## Access / caveats\n\n_Access level, gating, and known limitations (fill in)._\n"
    )
    return f"---\n{front}---\n\n{body}"


def add_dataset(
    project_root: Path,
    slug: str,
    *,
    title: str,
    origin: str = "external",
    tier: str = "track",
    level: str = "controlled",
    source_url: str = "",
    ontology_terms=(),
    related=(),
    today: date | None = None,
) -> tuple[str, Path, list[str]]:
    if origin != "external":
        raise EntityCommandError(
            "dataset add authors external candidate entities only; derived datasets "
            "are machine-authored by `science dataset register-run`."
        )
    slug = validate_slug(slug)
    entity_id = f"dataset:{slug}"
    today = today or date.today()
    rel_path = Path("doc") / "datasets" / f"{slug}.md"
    dest = project_root / rel_path
    if dest.exists():
        raise EntityCommandError(f"Destination already exists: {rel_path}")

    text = _render_candidate(
        entity_id,
        title=title,
        origin=origin,
        tier=tier,
        level=level,
        source_url=source_url,
        ontology_terms=ontology_terms,
        related=related,
        today=today,
    )
    warnings = _validate_prospective_write(
        project_root=project_root,
        rel_path=rel_path,
        text=text,
        target_entity_id=entity_id,
    )
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()
    return entity_id, dest, warnings
```

- [ ] **Step 4: Wire the `dataset add` CLI command**

In `science/src/science_tool/cli.py`, after the `dataset_list` command (around line 5208), add:

```python
@dataset_group.command("add")
@click.argument("slug")
@click.option("--title", required=True, help="Human-readable dataset title")
@click.option("--origin", type=click.Choice(["external", "derived"]), default="external")
@click.option("--tier", type=click.Choice(["use-now", "evaluate-next", "track"]), default="track")
@click.option(
    "--level",
    type=click.Choice(["public", "registration", "controlled", "commercial", "mixed"]),
    default="controlled",
)
@click.option("--source-url", default="", help="Landing page / accession URL")
@click.option("--ontology-term", "ontology_terms", multiple=True)
@click.option("--related", "related", multiple=True, help="Related entity ref (repeatable)")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
def dataset_add(
    slug: str,
    title: str,
    origin: str,
    tier: str,
    level: str,
    source_url: str,
    ontology_terms: tuple[str, ...],
    related: tuple[str, ...],
    project_root: Path | None,
) -> None:
    """Author a candidate external dataset entity under doc/datasets/."""
    from science_tool.datasets_catalog import add_dataset
    from science_tool.entities import EntityCommandError

    root = project_root.resolve() if project_root else _project_root_from_env()
    try:
        entity_id, dest, warnings = add_dataset(
            root,
            slug,
            title=title,
            origin=origin,
            tier=tier,
            level=level,
            source_url=source_url,
            ontology_terms=ontology_terms,
            related=related,
        )
    except EntityCommandError as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(1)
    for w in warnings:
        click.echo(f"warning: {w}", err=True)
    click.echo(f"created {entity_id} -> {dest.relative_to(root)}")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --frozen pytest science/tests/test_dataset_add_cli.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Verify a created entity validates clean**

Run (write a **full** minimal `science.yaml` — the manifest check requires `name`, `created`,
`last_modified`, `status`, `summary`, `profile`, `layout_version` ≥ 3, and `knowledge_profiles.local`,
else it emits its own `Severity.ERROR` that would mask the dataset signal):
```bash
TMP=$(mktemp -d)
cat > "$TMP/science.yaml" <<'YAML'
name: smoke
created: 2026-06-21
last_modified: 2026-06-21
status: active
summary: smoke test project
profile: research
layout_version: 3
knowledge_profiles:
  local: local
YAML
uv run --frozen science dataset add demo-set --title "Demo Set" --project-root "$TMP"
uv run --frozen science validate --project-root "$TMP" --verbose 2>&1 \
  | grep -i "acquired-without-pointer" && echo "UNEXPECTED: candidate flagged" || echo "OK: candidate not flagged"
rm -rf "$TMP"
```
Expected: the entity is written and the run prints `OK: candidate not flagged` — the candidate's
`status: candidate` exempts it from the acquisition check. (Other unrelated structure warnings for a
bare temp project are fine; this assertion targets only the rule under test.)

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/datasets_catalog.py science/src/science_tool/cli.py \
        science/tests/test_dataset_add_cli.py
git commit -m "feat(dataset): add command to author candidate dataset entities"
```

---

## Task 3: `dataset list` rework (table, filters, type-filter, --commons)

**Files:**
- Modify: `science/src/science_tool/datasets_catalog.py` (add `list_datasets`)
- Modify: `science/src/science_tool/cli.py` (rewrite `dataset_list`)
- Modify: `science/tests/test_datasets_list_cli.py`

**Interfaces:**
- Consumes: `add_dataset` module from Task 2.
- Produces: `list_datasets(project_root: Path, *, origin=None, status=None, tier=None, unverified=False, level=None, include_commons=False) -> tuple[list[dict], str | None]` returning `(filtered row dicts, commons-unavailable notice)`. Row keys: `id, title, status, tier, origin, level, verified, scope` (`scope` is `"local"` or `"commons"`). Skips frontmatter whose `type != "dataset"`. Local rows are always returned; a commons read failure sets the notice and degrades gracefully.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_datasets_list_cli.py`:

```python
def _seed_filterable(root: Path) -> None:
    d = root / "doc" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cand.md").write_text(
        '---\nid: "dataset:cand"\ntype: "dataset"\ntitle: "Cand"\nstatus: "candidate"\n'
        'origin: "external"\ntier: "use-now"\naccess: {level: "public", verified: false}\n---\n',
        encoding="utf-8",
    )
    (d / "acq.md").write_text(
        '---\nid: "dataset:acq"\ntype: "dataset"\ntitle: "Acq"\nstatus: "active"\n'
        'origin: "external"\ntier: "track"\ndatapackage: "r/dp.yaml"\n'
        'access: {level: "controlled", verified: true}\n---\n',
        encoding="utf-8",
    )
    # A non-entity note with frontmatter but type != dataset — must be excluded.
    (d / "note.md").write_text(
        '---\ntitle: "Combined note"\ntype: "note"\n---\nfree text\n',
        encoding="utf-8",
    )


def _list(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["dataset", "list", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )


def test_list_excludes_non_dataset_notes(tmp_path: Path) -> None:
    _seed_filterable(tmp_path)
    res = _list(tmp_path)
    assert res.exit_code == 0
    assert "dataset:cand" in res.output
    assert "Combined note" not in res.output


def test_list_candidate_filter(tmp_path: Path) -> None:
    _seed_filterable(tmp_path)
    res = _list(tmp_path, "--candidate")
    assert "dataset:cand" in res.output
    assert "dataset:acq" not in res.output


def test_list_tier_and_unverified_filters(tmp_path: Path) -> None:
    _seed_filterable(tmp_path)
    assert "dataset:cand" in _list(tmp_path, "--tier", "use-now").output
    assert "dataset:acq" not in _list(tmp_path, "--tier", "use-now").output
    assert "dataset:cand" in _list(tmp_path, "--unverified").output
    assert "dataset:acq" not in _list(tmp_path, "--unverified").output


def test_list_commons_missing_registry_degrades(tmp_path: Path) -> None:
    _seed_filterable(tmp_path)
    commons = tmp_path / "empty-commons"
    commons.mkdir()
    res = CliRunner().invoke(
        science_cli,
        ["dataset", "list", "--commons"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(commons)},
    )
    assert res.exit_code == 0
    assert "dataset:cand" in res.output  # local rows still shown
    assert "commons" in res.output.lower()  # a notice about commons unavailability
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --frozen pytest science/tests/test_datasets_list_cli.py -v`
Expected: FAIL — new options/behaviour not present.

- [ ] **Step 3: Implement `list_datasets`**

Append to `science/src/science_tool/datasets_catalog.py`:

```python
from science_model.frontmatter import parse_frontmatter


def _local_rows(project_root: Path) -> list[dict]:
    ds_dir = project_root / "doc" / "datasets"
    rows: list[dict] = []
    if not ds_dir.is_dir():
        return rows
    for md in sorted(ds_dir.glob("*.md")):
        parsed = parse_frontmatter(md)
        if parsed is None:
            continue
        fm, _ = parsed
        if (fm.get("kind") or fm.get("type")) != "dataset":
            continue
        access = fm.get("access") or {}
        rows.append(
            {
                "id": fm.get("id", md.stem),
                "title": fm.get("title", ""),
                "status": fm.get("status", ""),
                "tier": fm.get("tier", ""),
                "origin": fm.get("origin", ""),
                "level": access.get("level", "") if isinstance(access, dict) else "",
                "verified": bool(access.get("verified")) if isinstance(access, dict) else False,
                "scope": "local",
            }
        )
    return rows


def _matches(row: dict, *, origin, status, tier, unverified, level) -> bool:
    if origin is not None and row["origin"] != origin:
        return False
    if status is not None and row["status"] != status:
        return False
    if tier is not None and row["tier"] != tier:
        return False
    if level is not None and row["level"] != level:
        return False
    if unverified and row["verified"]:
        return False
    return True


def list_datasets(
    project_root: Path,
    *,
    origin: str | None = None,
    status: str | None = None,
    tier: str | None = None,
    unverified: bool = False,
    level: str | None = None,
    include_commons: bool = False,
) -> tuple[list[dict], str | None]:
    """Return (filtered rows, commons-unavailable notice). Local rows are always
    returned; if `include_commons` and the commons registry can't be read, the
    notice is set and local rows still come back (graceful degradation)."""
    rows = _local_rows(project_root)
    notice: str | None = None
    if include_commons:
        try:
            rows.extend(_commons_rows())
        except CommonsUnavailable as exc:
            notice = str(exc)
    filtered = [
        r
        for r in rows
        if _matches(r, origin=origin, status=status, tier=tier, unverified=unverified, level=level)
    ]
    return filtered, notice


def _commons_rows() -> list[dict]:
    """Commons catalog rows via CommonsQuery.find('dataset'); [] if unavailable.

    Raises CommonsUnavailable so the CLI can print a single notice. The registry
    must exist; CommonsQuery warns on staleness.
    """
    from science_tool.commons.config import resolve_commons_root
    from science_tool.commons.errors import CommonsRegistryError
    from science_tool.commons.query import CommonsQuery

    try:
        records = CommonsQuery(resolve_commons_root()).find("dataset")
    except (CommonsRegistryError, FileNotFoundError) as exc:
        raise CommonsUnavailable(str(exc)) from exc
    rows: list[dict] = []
    for rec in records:
        fm = rec.frontmatter or {}
        access = fm.get("access") or {}
        rows.append(
            {
                "id": rec.canonical_id,
                "title": fm.get("title", ""),
                "status": fm.get("status", ""),
                "tier": fm.get("tier", ""),
                "origin": fm.get("origin", ""),
                "level": access.get("level", "") if isinstance(access, dict) else "",
                "verified": bool(access.get("verified")) if isinstance(access, dict) else False,
                "scope": "commons",
            }
        )
    return rows


class CommonsUnavailable(Exception):
    """Raised when the commons registry cannot be read for a --commons listing."""
```

- [ ] **Step 4: Rewrite the `dataset_list` CLI command**

Replace `dataset_list` (cli.py:5176-5208) with:

```python
@dataset_group.command("list")
@click.option("--origin", default=None, type=click.Choice(["external", "derived"]))
@click.option("--status", default=None, help="Filter by status (e.g. candidate, active)")
@click.option("--candidate", is_flag=True, help="Shorthand for --status candidate")
@click.option("--tier", default=None, type=click.Choice(["use-now", "evaluate-next", "track"]))
@click.option("--unverified", is_flag=True, help="Only external entities with access.verified false")
@click.option(
    "--level",
    default=None,
    type=click.Choice(["public", "registration", "controlled", "commercial", "mixed"]),
)
@click.option("--commons", "include_commons", is_flag=True, help="Also list commons dataset entities")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
def dataset_list(
    origin: str | None,
    status: str | None,
    candidate: bool,
    tier: str | None,
    unverified: bool,
    level: str | None,
    include_commons: bool,
    project_root: Path | None,
) -> None:
    """List dataset entities as a table, with filters."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.datasets_catalog import list_datasets

    root = project_root.resolve() if project_root else _project_root_from_env()
    if candidate:
        status = "candidate"

    rows, notice = list_datasets(
        root,
        origin=origin,
        status=status,
        tier=tier,
        unverified=unverified,
        level=level,
        include_commons=include_commons,
    )
    if notice:
        click.echo(f"notice: commons datasets unavailable ({notice})", err=True)

    if not rows:
        click.echo("No matching dataset entities.")
        return

    table = Table(show_header=True, header_style="bold")
    for col in ("id", "title", "status", "tier", "origin", "level", "verified", "scope"):
        table.add_column(col, overflow="fold", no_wrap=False)
    for r in rows:
        table.add_row(
            r["id"], r["title"], r["status"], r["tier"], r["origin"], r["level"],
            "yes" if r["verified"] else "no", r["scope"],
        )
    Console(width=200).print(table)
```

- [ ] **Step 5: Run the full list test file**

Run: `uv run --frozen pytest science/tests/test_datasets_list_cli.py -v`
Expected: PASS — both the pre-existing `--origin` tests and the new filter/type-filter/commons-degrade tests.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/datasets_catalog.py science/src/science_tool/cli.py \
        science/tests/test_datasets_list_cli.py
git commit -m "feat(dataset): rich list table with status/tier/level/--commons filters"
```

---

## Task 4: `dataset show` + `dataset consumers`

**Files:**
- Modify: `science/src/science_tool/datasets_catalog.py` (add `resolve_dataset`, `show_dataset`, `list_consumers`)
- Modify: `science/src/science_tool/cli.py` (add `dataset_show`, `dataset_consumers`)
- Test: `science/tests/test_dataset_show_consumers_cli.py`

**Interfaces:**
- Consumes: `list_datasets` module from Task 3.
- Produces: `resolve_dataset(project_root, ref) -> tuple[str, dict, str] | None` returning `(scope, frontmatter, body)` or `None`; `ref` accepts `foo` or `dataset:foo`. Resolves local `doc/datasets/<slug>.md` first, then commons via `CommonsQuery.show`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_dataset_show_consumers_cli.py`:

```python
"""Tests for `science dataset show` and `dataset consumers`."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed(root: Path) -> None:
    d = root / "doc" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / "foo.md").write_text(
        '---\nid: "dataset:foo"\ntype: "dataset"\ntitle: "Foo"\nstatus: "candidate"\n'
        'origin: "external"\ntier: "track"\nconsumed_by: ["plan:p1", "workflow-run:r1"]\n'
        'access: {level: "public", verified: false}\n---\n\nBody text here.\n',
        encoding="utf-8",
    )


def _run(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli, list(args), catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )


def test_show_accepts_bare_and_prefixed_ref(tmp_path: Path) -> None:
    _seed(tmp_path)
    for ref in ("foo", "dataset:foo"):
        res = _run(tmp_path, "dataset", "show", ref)
        assert res.exit_code == 0, res.output
        assert "dataset:foo" in res.output
        assert "Body text here." in res.output


def test_show_missing_exits_2_naming_scopes(tmp_path: Path) -> None:
    _seed(tmp_path)
    res = _run(tmp_path, "dataset", "show", "nope")
    assert res.exit_code == 2
    assert "local" in res.output.lower() and "commons" in res.output.lower()


def test_consumers_lists_consumed_by(tmp_path: Path) -> None:
    _seed(tmp_path)
    res = _run(tmp_path, "dataset", "consumers", "dataset:foo")
    assert res.exit_code == 0
    assert "plan:p1" in res.output
    assert "workflow-run:r1" in res.output


def test_consumers_empty(tmp_path: Path) -> None:
    d = tmp_path / "doc" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / "bar.md").write_text(
        '---\nid: "dataset:bar"\ntype: "dataset"\ntitle: "Bar"\nstatus: "candidate"\n---\n',
        encoding="utf-8",
    )
    res = _run(tmp_path, "dataset", "consumers", "bar")
    assert res.exit_code == 0
    assert "no recorded consumers" in res.output.lower()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --frozen pytest science/tests/test_dataset_show_consumers_cli.py -v`
Expected: FAIL — `show`/`consumers` are not commands.

- [ ] **Step 3: Implement the resolver + readers**

Append to `science/src/science_tool/datasets_catalog.py`:

```python
def resolve_dataset(project_root: Path, ref: str) -> tuple[str, dict, str] | None:
    """Resolve `foo` or `dataset:foo` to (scope, frontmatter, body); local then commons."""
    slug = ref[len("dataset:"):] if ref.startswith("dataset:") else ref
    local = project_root / "doc" / "datasets" / f"{slug}.md"
    if local.exists():
        parsed = parse_frontmatter(local)
        if parsed is not None:
            fm, body = parsed
            # Same guard as `list`: a non-dataset file under doc/datasets/ is a
            # local miss, not a match — fall through to commons.
            if (fm.get("kind") or fm.get("type")) == "dataset":
                return ("local", fm, body)
    from science_tool.commons.config import resolve_commons_root
    from science_tool.commons.errors import CommonsEntityError, CommonsRegistryError
    from science_tool.commons.query import CommonsQuery

    try:
        rec = CommonsQuery(resolve_commons_root()).show(f"dataset:{slug}")
    except (CommonsEntityError, CommonsRegistryError, FileNotFoundError):
        return None
    fm = rec.frontmatter or {}
    # body_path is the full entity.md (frontmatter + body); strip the frontmatter
    # so `show` prints body-only, matching the local path's parse_frontmatter result.
    body = ""
    if rec.body_path and Path(rec.body_path).exists():
        parsed_commons = parse_frontmatter(Path(rec.body_path))
        body = parsed_commons[1] if parsed_commons else ""
    return ("commons", fm, body)
```

- [ ] **Step 4: Wire the `dataset show` and `dataset consumers` CLI commands**

In `science/src/science_tool/cli.py`, after `dataset_add`, add:

```python
def _resolve_dataset_or_exit(root: Path, ref: str):
    from science_tool.datasets_catalog import resolve_dataset

    resolved = resolve_dataset(root, ref)
    if resolved is None:
        click.echo(
            f"no such dataset {ref!r} (searched local doc/datasets/ and commons)", err=True
        )
        raise click.exceptions.Exit(2)
    return resolved


@dataset_group.command("show")
@click.argument("ref")
@click.option(
    "--project-root", default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def dataset_show(ref: str, project_root: Path | None) -> None:
    """Show a dataset entity (accepts `slug` or `dataset:slug`)."""
    root = project_root.resolve() if project_root else _project_root_from_env()
    scope, fm, body = _resolve_dataset_or_exit(root, ref)
    access = fm.get("access") or {}
    click.echo(f"id:       {fm.get('id', '?')}  ({scope})")
    click.echo(f"title:    {fm.get('title', '')}")
    click.echo(f"status:   {fm.get('status', '')}    tier: {fm.get('tier', '')}")
    click.echo(f"origin:   {fm.get('origin', '')}    license: {fm.get('license', '')}")
    if isinstance(access, dict) and access:
        click.echo(f"access:   level={access.get('level', '')} verified={access.get('verified')}")
        if access.get("source_url"):
            click.echo(f"url:      {access['source_url']}")
    if fm.get("accessions"):
        click.echo(f"accessions: {fm['accessions']}")
    if fm.get("related"):
        click.echo(f"related:  {fm['related']}")
    if fm.get("consumed_by"):
        click.echo(f"consumed_by: {fm['consumed_by']}")
    click.echo("")
    click.echo(body.strip())


@dataset_group.command("consumers")
@click.argument("ref")
@click.option(
    "--project-root", default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def dataset_consumers(ref: str, project_root: Path | None) -> None:
    """List entities that consume this dataset (via consumed_by)."""
    root = project_root.resolve() if project_root else _project_root_from_env()
    _scope, fm, _body = _resolve_dataset_or_exit(root, ref)
    consumers = fm.get("consumed_by") or []
    if not consumers:
        click.echo("no recorded consumers")
        return
    for c in consumers:
        click.echo(c)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --frozen pytest science/tests/test_dataset_show_consumers_cli.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/datasets_catalog.py science/src/science_tool/cli.py \
        science/tests/test_dataset_show_consumers_cli.py
git commit -m "feat(dataset): show and consumers commands with local→commons ref resolution"
```

---

## Task 5: Full-suite validation + design-doc cross-check

**Files:** none (verification + optional doc touch-ups).

- [ ] **Step 1: Run the full dataset-related test set**

Run:
```bash
uv run --frozen pytest \
  science/tests/test_dataset_acquisition_check.py \
  science/tests/test_dataset_add_cli.py \
  science/tests/test_datasets_list_cli.py \
  science/tests/test_dataset_show_consumers_cli.py \
  science/tests/test_dataset_register_run.py \
  science/tests/test_dataset_reconcile.py -v
```
Expected: all PASS — including the untouched `register-run`/`reconcile` suites (proving no regression).

- [ ] **Step 2: Run the broader validate/CLI smoke**

Run: `uv run --frozen pytest science/tests/ -q -k "dataset or validate"`
Expected: PASS. Investigate any failure before proceeding.

- [ ] **Step 3: Manual commons happy-path check (not unit-tested)**

The `--commons` populated path and the `show`/`consumers` commons fallback are exercised against a real commons registry, which the unit tests deliberately do not build. Manually verify once, picking a real commons dataset slug from the first command:
```bash
uv run --frozen science dataset list --commons | head
# pick a dataset:<slug> shown with scope=commons above, then:
uv run --frozen science dataset show dataset:<commons-slug>
uv run --frozen science dataset consumers dataset:<commons-slug>
```
Expected: `list --commons` shows local rows plus commons `dataset:` rows tagged `commons` (or the "commons datasets unavailable" notice if no registry); `show`/`consumers` resolve the commons-only slug via the fallback (not exit 2). Note in the commit message **which path was observed** — if the commons store has no dataset entities, say so explicitly rather than treating the empty result as a pass.

- [ ] **Step 4: Cross-check against the design acceptance criteria**

Open `docs/plans/2026-06-21-dataset-catalog-cli-design.md` and confirm each Acceptance-Criteria checkbox is met by the implemented tasks. If any is unmet, file a follow-up task rather than silently dropping it.

- [ ] **Step 5: Commit (if any doc touch-ups were needed)**

```bash
git add -A && git commit -m "test(dataset): full catalog-CLI suite green; note manual commons check"
```

---

## Self-Review Notes (author)

- **Spec coverage:** `add` (T2), `show`/`consumers` (T4), `list` rework + filters + `--commons` + type-filter (T3), acquisition check + template flip (T1), tests throughout, final smoke (T5). Deferred items (`--stale-review`, `dataset verify`, group collapse, schema-mixin change) are correctly absent.
- **Open question 3** (commons root + record shape) is resolved inline: `resolve_commons_root()` + `CommonsQuery.find/show`; `CommonsEntityRecord.frontmatter` (a dict) supplies the fields and `body_path` the body — the record has no `frontmatter_json`/`title`. The populated-commons path is covered by T5 Step 3's manual check (flagged, not silently capped).
- **Type consistency:** row dict keys (`id/title/status/tier/origin/level/verified/scope`) are identical across `_local_rows`, `_commons_rows`, `_matches`, and the table render. `resolve_dataset` returns `(scope, fm, body)` consumed uniformly by `show`/`consumers`.
