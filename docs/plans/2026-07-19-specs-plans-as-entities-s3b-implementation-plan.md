# `migrate-specs` (S3b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `science entity migrate-specs`, a command that canonicalizes a project's legacy / loose `spec`-typed docs into numeric `entities/specs/NNNN-slug.md` entities (old id preserved as an alias), repoints the references the rewrite engine can safely rewrite, and reports a machine-checkable `flip_ready` verdict — while `spec` stays annotation-only (the resolution flip is a separate later effort).

**Architecture:** A new `migrate_specs.py` module composes the existing audited primitives (`_snapshot`/`_restore`, `claim_number_in_dir`, `plan_reference_rewrite`/`apply_reference_rewrite`, `audit_moved_references`) into a **new batch coordinator** — none of them welded into per-doc order. Legacy frontmatter is *projected* to the canonical spec schema (not imported), files are relocated with deterministic numeric ids, references are classified on two axes (surface × target) into five report groups, and the whole batch is one crash-safe transaction with a per-path role-tagged recovery journal. The one edit to an existing primitive is a behavior-preserving self-cleanup in `claim_number_in_dir`.

**Tech Stack:** Python 3.12, `click` CLI, `pydantic` (`RewriteReport`), `pytest`. Package is `science` under `science/` (run everything from `science/`). Design doc: `docs/plans/2026-07-18-specs-plans-as-entities-s3b-design.md` (read it; this plan implements it verbatim).

## Global Constraints

- **The switch is NOT flipped.** `graph/sources.py:809` `_ANNOTATION_REF_PREFIXES = frozenset({"meta", "spec"})` is left **exactly** as-is. Do not edit `sources.py`. The S3a guard tests (`test_spec_materialization.py`, `test_meta_reference.py:26-28`, `test_membership_materialize.py`) are left **untouched** and must still pass.
- **Run from `science/`:** `cd science && uv run --frozen pytest` (model work, if any, from `science/model/`). Default pytest excludes `snapshot`/`real_projects` markers. Lint from `science/`: `uv run ruff check`; types: `uv run pyright`.
- **Never `git add science/uv.lock`.** Commit only the files each task names.
- **No AI-attribution trailers** on any commit (no `Co-Authored-By`, no "Generated with Claude Code").
- **Use `~/d/` in docs/code**, never `/home/keith/d/` or `/mnt/ssd/Dropbox/`.
- **Conventions:** composition over inheritance; explicit over defensive; fail early, no silent fallbacks; no "legacy"/"compatibility" layers; no `Unified` prefix.
- **`RUNTIME_ONLY` is exactly** `{project, file_path, content, content_preview, canonical_id}` — no more, no less.
- **Token boundary is deterministic:** a `spec:` token matches only with a left boundary (not preceded by `[A-Za-z0-9_-]`, so `science-spec:` never matches) and trailing punctuation trimmed.
- **Canonical id vocabulary (S3a):** `draft / active / complete / superseded / retired / archived`.
- **The five report groups** are exactly: `rewritten`, `alias_resolved`, `identity_preserved`, `unchanged`, `manual_retarget`. Only `manual_retarget` (plus singletons and un-relocated legacy specs) blocks `flip_ready`.
- **Journal path:** `.science/spec-migration.journal` (constant `JOURNAL_PATH`).
- Follow the `test_migrate_hypothesis.py` layout for plan/apply/resume coverage.

---

## File Structure

- **Create `science/src/science_tool/migrate_specs.py`** — the whole feature: constants, `SpecMigrationRefused`, projection, discovery, id allocation, reference classification, report assembly, the batch coordinator (plan / apply / resume), and the journal. One module because these pieces share the projection/allocation/classification data and change together.
- **Create `science/tests/test_migrate_specs.py`** — all tests (projection, discovery, allocation, classification, report/schema, transaction, resume, guard).
- **Modify `science/src/science_tool/entity_reservation.py:200-205`** — `claim_number_in_dir` self-cleaning partial-dest (Task 1).
- **Modify `science/src/science_tool/entities_cli.py`** — register `@entity_group.command("migrate-specs")` (Task 10).
- **Modify `docs/user-guide/entities.md`** (repo-root tree) — document the command (Task 12).

### Module public surface (pin these names; later tasks depend on them verbatim)

```python
JOURNAL_PATH: Path = Path(".science/spec-migration.journal")
RUNTIME_ONLY: frozenset[str]          # {project,file_path,content,content_preview,canonical_id}
LEGACY_ALIAS: frozenset[str]          # {type,date,related_questions,related_specs}
CANONICAL_SPEC_STATUS: frozenset[str] # {draft,active,complete,superseded,retired,archived}
_STATUS_MAP: dict[str, str]

class SpecMigrationRefused(RuntimeError): ...

def project_legacy_frontmatter(frontmatter: Mapping[str, Any], *, source_rel: str) -> tuple[str, dict]: ...

@dataclass(frozen=True) class LegacySpec:  source_rel: str; old_id: str; frontmatter: dict; body: str; already_numeric: int | None
@dataclass(frozen=True) class Singleton:   rel_path: str; old_id: str
@dataclass(frozen=True) class ScanSkip:    path: str; reason: str
@dataclass(frozen=True) class Discovery:   legacy: list[LegacySpec]; singletons: list[Singleton]; scan_skips: list[ScanSkip]
def discover_specs(project_root: Path) -> Discovery: ...

@dataclass(frozen=True) class Allocation:
    id_substitutions: dict[str, str]  # old_id -> new spec:NNNN-slug (MINTED docs only)
    dest_rel: dict[str, str]          # old_id -> "entities/specs/NNNN-slug.md" (ALL legacy)
    new_local_part: dict[str, str]    # old_id -> "NNNN-slug" (ALL legacy)
    aliased: frozenset[str]           # old_ids whose old id is appended to aliases (minted)
    preserved_ids: frozenset[str]     # old_ids kept verbatim (already-numeric relocations)
def allocate_ids(project_root: Path, legacy: list[LegacySpec]) -> Allocation: ...

@dataclass(frozen=True) class RefRecord: ref: str; surface: str; target: str; group: str; in_file: str
def classify_references(project_root: Path, *, id_substitutions: dict[str, str],
                        live_spec_ids: set[str], source_rels: frozenset[str]) -> list[RefRecord]: ...

def build_report(project_root: Path) -> dict: ...          # the JSON contract; read-only
def migrate(project_root: Path, *, apply: bool = False) -> dict: ...
def resume(project_root: Path) -> dict: ...
```

---

### Task 1: Self-cleaning `claim_number_in_dir`

**Files:**
- Modify: `science/src/science_tool/entity_reservation.py:200-205`
- Test: `science/tests/test_migrate_specs.py`

**Interfaces:**
- Consumes: nothing (foundational).
- Produces: `claim_number_in_dir(project_root, kind, number, local_part, text) -> Path` — unchanged signature; new behavior: if the write fails **after** the `open(path,"x")` proves ownership, the partial file is unlinked before the exception propagates.

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_migrate_specs.py` (create the file with this content):

```python
"""Tests for `science entity migrate-specs` (S3b)."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from science_tool.entities import EntityCommandError
from science_tool.entity_reservation import claim_number_in_dir


def _spec_project(tmp_path: Path) -> Path:
    """A minimal project root with a spec home and a valid science.yaml."""
    import yaml

    (tmp_path / "science.yaml").write_text(
        yaml.safe_dump({"name": "p", "id": "p"}), encoding="utf-8"
    )
    (tmp_path / "entities/specs").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_claim_number_unlinks_its_own_partial_on_write_failure(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    dest = project / "entities/specs" / "0001-x.md"
    boom = OSError("disk full")

    real_write = Path.write_text

    def _explode(self: Path, *args: object, **kwargs: object) -> int:
        if self == dest:
            raise boom
        return real_write(self, *args, **kwargs)  # type: ignore[arg-type]

    # The write inside claim goes through the open("x") handle, not Path.write_text,
    # so patch the handle's write instead: fail once ownership is proven.
    import builtins

    real_open = builtins.open

    def _open(path: object, *args: object, **kwargs: object):  # noqa: ANN002
        handle = real_open(path, *args, **kwargs)
        if Path(str(path)) == dest:
            handle.write = mock.Mock(side_effect=boom)  # type: ignore[method-assign]
        return handle

    with mock.patch("builtins.open", _open):
        with pytest.raises(OSError, match="disk full"):
            claim_number_in_dir(project, "spec", 1, "0001-x", "body")

    assert not dest.exists(), "a caught write failure must leave no partial destination"
    assert not (project / "entities/specs" / ".0001.reserving").exists(), "sentinel cleared"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py::test_claim_number_unlinks_its_own_partial_on_write_failure -v`
Expected: FAIL — the partial `0001-x.md` is left on disk (assert `not dest.exists()` fails).

- [ ] **Step 3: Implement the self-cleanup**

In `science/src/science_tool/entity_reservation.py`, replace the write body of `claim_number_in_dir` (currently lines 200-203):

```python
        path = directory / f"{local_part}.md"
        with open(path, "x", encoding="utf-8") as handle:
            handle.write(text)
        return path
```

with:

```python
        path = directory / f"{local_part}.md"
        # `open(..., "x")` == O_CREAT|O_EXCL: reaching this line PROVES we own the
        # path (no bystander held it). So a write failure is ours to clean up --
        # leaving the partial file would strand debris a caller's rollback (which
        # snapshotted this path absent) cannot see. This covers the in-process
        # exception path only; a SIGKILL mid-write leaves a partial that resume
        # classifies as a third state and refuses on.
        with open(path, "x", encoding="utf-8") as handle:
            try:
                handle.write(text)
            except BaseException:
                path.unlink(missing_ok=True)
                raise
        return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py::test_claim_number_unlinks_its_own_partial_on_write_failure -v`
Expected: PASS.

- [ ] **Step 5: Run the existing reservation tests to prove no regression**

Run: `cd science && uv run --frozen pytest -k "reserv or claim or import" -q`
Expected: PASS (all previously-passing reservation/import tests still green).

- [ ] **Step 6: Commit**

```bash
cd science
git add src/science_tool/entity_reservation.py tests/test_migrate_specs.py
git commit -m "fix(reservation): claim_number_in_dir unlinks its own partial dest on write failure"
```

---

### Task 2: Legacy frontmatter projection

**Files:**
- Create: `science/src/science_tool/migrate_specs.py`
- Test: `science/tests/test_migrate_specs.py`

**Interfaces:**
- Consumes: `derive_slug`, `EntityCommandError` from `science_tool.entities`; `split_frontmatter` from `science_model.frontmatter`.
- Produces: the constants, `SpecMigrationRefused`, and `project_legacy_frontmatter(frontmatter, *, source_rel) -> (old_id, projected_fm)`. `projected_fm` keeps `id: <old>` and `kind: spec`; the old id is **not** yet appended to aliases (that is the mint step, Task 4/Task 7). Raises `SpecMigrationRefused` on any refusal, naming the file.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_migrate_specs.py`:

```python
from science_tool.migrate_specs import (
    CANONICAL_SPEC_STATUS,
    LEGACY_ALIAS,
    RUNTIME_ONLY,
    SpecMigrationRefused,
    project_legacy_frontmatter,
)


def test_runtime_only_set_is_exact() -> None:
    assert RUNTIME_ONLY == frozenset(
        {"project", "file_path", "content", "content_preview", "canonical_id"}
    )
    assert LEGACY_ALIAS == frozenset({"type", "date", "related_questions", "related_specs"})
    assert CANONICAL_SPEC_STATUS == frozenset(
        {"draft", "active", "complete", "superseded", "retired", "archived"}
    )


def test_projection_maps_type_date_status_related_and_preserves_supersedes() -> None:
    old_id, fm = project_legacy_frontmatter(
        {
            "id": "spec:2026-03-16-meta-model-design",
            "type": "spec",
            "title": "Meta-Model Design",
            "date": "2026-03-16",
            "status": "design",
            "related": ["question:0001-x"],
            "related_questions": ["question:0005-y"],
            "aliases": ["spec:old-alias"],
            "supersedes": ["spec:2026-01-01-older"],
        },
        source_rel="doc/plans/meta-model.md",
    )
    assert old_id == "spec:2026-03-16-meta-model-design"
    assert fm["kind"] == "spec"
    assert "type" not in fm
    assert fm["created"] == "2026-03-16" and fm["updated"] == "2026-03-16"
    assert fm["status"] == "draft"  # design -> draft
    assert fm["related"] == ["question:0001-x", "question:0005-y"]  # folded, order-preserving
    assert "related_questions" not in fm
    assert fm["aliases"] == ["spec:old-alias"]  # old id NOT appended here (mint step does that)
    assert fm["supersedes"] == ["spec:2026-01-01-older"]  # extension key preserved untouched
    assert fm["id"] == old_id  # still the OLD id; the coordinator renumbers


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [
        ("proposed", "draft"),
        ("in-progress", "active"),
        ("implemented", "complete"),
        ("superseded", "superseded"),  # identity
        ("active", "active"),
    ],
)
def test_projection_status_adjudication(legacy: str, canonical: str) -> None:
    _old, fm = project_legacy_frontmatter(
        {"id": "spec:x", "type": "spec", "title": "T", "created": "2026-01-01", "updated": "2026-01-01", "status": legacy},
        source_rel="doc/x.md",
    )
    assert fm["status"] == canonical


def test_projection_refuses_unmappable_status() -> None:
    with pytest.raises(SpecMigrationRefused, match="approved"):
        project_legacy_frontmatter(
            {"id": "spec:x", "type": "spec", "title": "T", "date": "2026-01-01", "status": "approved"},
            source_rel="doc/x.md",
        )


def test_projection_refuses_runtime_only_key() -> None:
    with pytest.raises(SpecMigrationRefused, match="content"):
        project_legacy_frontmatter(
            {"id": "spec:x", "type": "spec", "title": "T", "date": "2026-01-01", "content": "x"},
            source_rel="doc/x.md",
        )


def test_projection_refuses_authored_canonical_id() -> None:
    with pytest.raises(SpecMigrationRefused, match="canonical_id"):
        project_legacy_frontmatter(
            {"id": "spec:x", "type": "spec", "title": "T", "date": "2026-01-01", "canonical_id": "spec:x"},
            source_rel="doc/x.md",
        )


def test_projection_refuses_created_without_updated_or_date() -> None:
    with pytest.raises(SpecMigrationRefused, match="updated"):
        project_legacy_frontmatter(
            {"id": "spec:x", "type": "spec", "title": "T", "created": "2026-01-01"},
            source_rel="doc/x.md",
        )


def test_projection_refuses_kind_type_disagreement() -> None:
    with pytest.raises(SpecMigrationRefused, match="disagree"):
        project_legacy_frontmatter(
            {"id": "spec:x", "kind": "design", "type": "spec", "title": "T", "date": "2026-01-01"},
            source_rel="doc/x.md",
        )


def test_projection_refuses_missing_id_or_title() -> None:
    with pytest.raises(SpecMigrationRefused, match="id"):
        project_legacy_frontmatter(
            {"type": "spec", "title": "T", "date": "2026-01-01"}, source_rel="doc/x.md"
        )
    with pytest.raises(SpecMigrationRefused, match="title"):
        project_legacy_frontmatter(
            {"id": "spec:x", "type": "spec", "date": "2026-01-01"}, source_rel="doc/x.md"
        )
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k projection -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.migrate_specs'` / import errors.

- [ ] **Step 3: Create the module with constants + projection**

Create `science/src/science_tool/migrate_specs.py`:

```python
"""`science entity migrate-specs` (S3b) — canonicalize legacy/loose spec docs to numeric entities.

Ships the migration; does NOT flip `spec:` resolution (`_ANNOTATION_REF_PREFIXES` is untouched).
The command projects legacy frontmatter to the canonical spec schema, relocates each doc to
`entities/specs/NNNN-slug.md` with a deterministic numeric id (old id preserved as an alias),
rewrites the references the engine can safely rewrite, and reports a machine-checkable `flip_ready`.

WHY A NEW COORDINATOR. `apply_import` is a complete PER-DOCUMENT transaction; it cannot do
"all moves, then one batch rewrite." So this composes the low-level primitives (`_snapshot`/
`_restore`, `claim_number_in_dir`, `plan/apply_reference_rewrite`, `audit_moved_references`) into a
batch transaction with a per-path role-tagged recovery journal. The design is
`docs/plans/2026-07-18-specs-plans-as-entities-s3b-design.md`.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from science_tool.entities import EntityCommandError, derive_slug

JOURNAL_PATH: Path = Path(".science/spec-migration.journal")

# The load-derived keys, enumerated EXACTLY (design Component 2). A legacy doc authoring any of
# these refuses: the first four are derived by `_enrich_raw`, and `canonical_id` there OVERRIDES the
# id-derived value, so an authored one would disagree with the freshly minted numeric id.
RUNTIME_ONLY: frozenset[str] = frozenset(
    {"project", "file_path", "content", "content_preview", "canonical_id"}
)

# The legacy spellings the projection rewrites.
LEGACY_ALIAS: frozenset[str] = frozenset({"type", "date", "related_questions", "related_specs"})

CANONICAL_SPEC_STATUS: frozenset[str] = frozenset(
    {"draft", "active", "complete", "superseded", "retired", "archived"}
)

# Unambiguous legacy -> canonical only. Anything outside this table AND the canonical set refuses:
# `approved`/`ready-with-caveats`/... straddle draft and active, and auto-choosing would be tuning
# metadata to pass. The operator pre-edits the doc's status.
_STATUS_MAP: dict[str, str] = {
    "draft": "draft",
    "proposed": "draft",
    "design": "draft",
    "active": "active",
    "in-progress": "active",
    "current": "active",
    "complete": "complete",
    "completed": "complete",
    "implemented": "complete",
}


class SpecMigrationRefused(RuntimeError):
    """The migration will not proceed. NOTHING has been written."""


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _dedup(items: list[Any]) -> list[Any]:
    """Order-preserving dedup (first occurrence wins)."""
    seen: set[Any] = set()
    out: list[Any] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def project_legacy_frontmatter(
    frontmatter: Mapping[str, Any], *, source_rel: str
) -> tuple[str, dict]:
    """Project ONE legacy spec doc's frontmatter to the canonical spec schema.

    Returns ``(old_id, projected_frontmatter)``. The projected frontmatter keeps ``id: <old_id>``
    and ``kind: spec``; the old id is appended to ``aliases`` only when the doc is renumbered (the
    coordinator's mint step), so a pure relocation preserves its id with no alias churn. Refuses,
    naming the file, on any ambiguity — it never invents a value.
    """
    fm = dict(frontmatter)

    present_runtime = sorted(RUNTIME_ONLY & set(fm))
    if present_runtime:
        raise SpecMigrationRefused(
            f"{source_rel}: authors load-derived key(s) {present_runtime!r}, which are not "
            "authorable frontmatter (they are derived at load)."
        )

    declared_kind = fm.get("kind")
    declared_type = fm.get("type")
    if declared_kind is not None and declared_type is not None and declared_kind != declared_type:
        raise SpecMigrationRefused(
            f"{source_rel}: kind {declared_kind!r} and type {declared_type!r} disagree."
        )
    kind = declared_kind if declared_kind is not None else declared_type
    if kind != "spec":
        raise SpecMigrationRefused(f"{source_rel}: not a spec (kind/type {kind!r}).")
    fm["kind"] = "spec"
    fm.pop("type", None)

    old_id = fm.get("id")
    if not isinstance(old_id, str) or not old_id.startswith("spec:"):
        raise SpecMigrationRefused(
            f"{source_rel}: a spec doc without a declared `spec:` id; identity is authoritative "
            "and never guessed from a filename."
        )
    title = fm.get("title")
    if not isinstance(title, str) or not title.strip():
        raise SpecMigrationRefused(f"{source_rel}: missing `title:`.")

    date = fm.pop("date", None)
    for field in ("created", "updated"):
        if fm.get(field):
            continue
        if date:
            fm[field] = date
        else:
            raise SpecMigrationRefused(
                f"{source_rel}: `{field}` is absent and there is no `date:` to seed it."
            )

    status = fm.get("status")
    if status is not None:
        if status in CANONICAL_SPEC_STATUS:
            pass
        elif status in _STATUS_MAP:
            fm["status"] = _STATUS_MAP[status]
        else:
            raise SpecMigrationRefused(
                f"{source_rel}: status {status!r} maps to no canonical spec status. "
                "Pre-edit the doc's status; the migration will not guess."
            )

    related = _dedup(
        [
            *_as_list(fm.get("related")),
            *_as_list(fm.pop("related_questions", None)),
            *_as_list(fm.pop("related_specs", None)),
        ]
    )
    if related:
        fm["related"] = related

    return old_id, fm
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k "projection or runtime_only" -v`
Expected: PASS (all projection tests green).

- [ ] **Step 5: Lint + types**

Run: `cd science && uv run ruff check src/science_tool/migrate_specs.py && uv run pyright src/science_tool/migrate_specs.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
cd science
git add src/science_tool/migrate_specs.py tests/test_migrate_specs.py
git commit -m "feat(migrate-specs): legacy frontmatter projection to canonical spec schema"
```

---

### Task 3: Discovery (legacy specs, singletons, scan skips)

**Files:**
- Modify: `science/src/science_tool/migrate_specs.py`
- Test: `science/tests/test_migrate_specs.py`

**Interfaces:**
- Consumes: `resolve_path_policy`, `markdown_entity_kinds`, `local_part_conforms` from `science_tool.entities`; `MAX_SCANNABLE_BYTES` from `science_tool.text_scan`; `_REFERENCE_SCAN_SKIP_DIRS` from `science_tool.entities`; `split_frontmatter` from `science_model.frontmatter`.
- Produces: `LegacySpec`, `Singleton`, `ScanSkip`, `Discovery` dataclasses and `discover_specs(project_root) -> Discovery`. `discover_specs` refuses (raises `SpecMigrationRefused`) on a legacy spec doc lacking a declared `spec:` id.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_migrate_specs.py`:

```python
from science_tool.migrate_specs import (
    Discovery,
    ScanSkip,
    discover_specs,
)


def _write(path: Path, frontmatter: dict, body: str = "Body.\n") -> Path:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\n{body}", encoding="utf-8"
    )
    return path


def test_discovery_finds_loose_specs_and_skips_conforming(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:2026-01-01-a", "type": "spec", "title": "A"})
    _write(project / "doc/specs/b.md", {"id": "spec:semantic-b", "kind": "spec", "title": "B"})
    # already conforming — must be skipped
    _write(project / "entities/specs/0009-c.md", {"id": "spec:0009-c", "kind": "spec", "title": "C"})
    # not a spec — ignored
    _write(project / "doc/plans/d.md", {"id": "design:0001-d", "kind": "design", "title": "D"})

    disc = discover_specs(project)
    old_ids = {ls.old_id for ls in disc.legacy}
    assert old_ids == {"spec:2026-01-01-a", "spec:semantic-b"}
    assert disc.singletons == []
    assert disc.scan_skips == []


def test_discovery_reports_singleton_home_not_relocated(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "entities/research-question.md", {"id": "spec:research-question", "kind": "spec", "title": "RQ"})
    disc = discover_specs(project)
    assert [s.rel_path for s in disc.singletons] == ["entities/research-question.md"]
    assert disc.legacy == []


def test_discovery_already_numeric_out_of_home_carries_number(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/keep.md", {"id": "spec:0007-keep", "type": "spec", "title": "Keep"})
    disc = discover_specs(project)
    assert len(disc.legacy) == 1
    assert disc.legacy[0].already_numeric == 7


def test_discovery_refuses_spec_doc_without_id(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/noid.md", {"type": "spec", "title": "No Id"})
    with pytest.raises(SpecMigrationRefused, match="without a declared"):
        discover_specs(project)


def test_discovery_oversized_markdown_becomes_scan_skip(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    big = project / "doc/plans/huge.md"
    big.parent.mkdir(parents=True, exist_ok=True)
    from science_tool.text_scan import MAX_SCANNABLE_BYTES

    big.write_text("x" * (MAX_SCANNABLE_BYTES + 1), encoding="utf-8")
    disc = discover_specs(project)
    assert any(s.path == "doc/plans/huge.md" for s in disc.scan_skips)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k discovery -v`
Expected: FAIL (import errors for `discover_specs`/`Discovery`).

- [ ] **Step 3: Implement discovery**

Append to `science/src/science_tool/migrate_specs.py` (add the new imports to the existing import block at the top of the file, then the code):

Add these imports near the top (with the other imports):

```python
import re
from dataclasses import dataclass

from science_model.frontmatter import split_frontmatter

from science_tool.entities import (
    _REFERENCE_SCAN_SKIP_DIRS,
    local_part_conforms,
    markdown_entity_kinds,
    resolve_path_policy,
)
from science_tool.text_scan import MAX_SCANNABLE_BYTES
```

Append the code:

```python
_NUMERIC_LOCAL_RE = re.compile(r"^(\d{4})-")


@dataclass(frozen=True)
class LegacySpec:
    source_rel: str
    old_id: str
    frontmatter: dict
    body: str
    already_numeric: int | None  # the NNNN if the id is already spec:NNNN-slug, else None


@dataclass(frozen=True)
class Singleton:
    rel_path: str
    old_id: str


@dataclass(frozen=True)
class ScanSkip:
    path: str
    reason: str


@dataclass(frozen=True)
class Discovery:
    legacy: list[LegacySpec]
    singletons: list[Singleton]
    scan_skips: list[ScanSkip]


def _spec_root(project_root: Path) -> str:
    return str(resolve_path_policy("spec", project_root=project_root).root)


def _singleton_homes(project_root: Path) -> set[str]:
    """Rel paths of every singleton-strategy kind's home (e.g. entities/research-question.md)."""
    homes: set[str] = set()
    for kind in markdown_entity_kinds(project_root):
        policy = resolve_path_policy(kind, project_root=project_root)
        if policy.strategy == "singleton":
            homes.add(str(policy.root))
    return homes


def _numeric_of(old_id: str) -> int | None:
    """The NNNN of a `spec:NNNN-slug` id, else None."""
    local = old_id.split(":", 1)[1] if ":" in old_id else old_id
    match = _NUMERIC_LOCAL_RE.match(local)
    return int(match.group(1)) if match is not None else None


def discover_specs(project_root: Path) -> Discovery:
    """Discover legacy spec docs to relocate, singleton-home spec files, and scan skips.

    A COMPLETE Markdown walk (not `iter_scannable_files`, which silently drops oversized files):
    an oversized or unreadable candidate is a `scan_skip`, which later forces `flip_ready=false`.
    """
    project_root = Path(project_root).resolve()
    spec_root = _spec_root(project_root)
    singleton_homes = _singleton_homes(project_root)

    legacy: list[LegacySpec] = []
    singletons: list[Singleton] = []
    scan_skips: list[ScanSkip] = []

    for path in sorted(project_root.rglob("*.md")):
        rel = path.relative_to(project_root).as_posix()
        if any(part in _REFERENCE_SCAN_SKIP_DIRS for part in path.relative_to(project_root).parts):
            continue
        try:
            if path.stat().st_size > MAX_SCANNABLE_BYTES:
                scan_skips.append(ScanSkip(path=rel, reason="exceeds MAX_SCANNABLE_BYTES"))
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            scan_skips.append(ScanSkip(path=rel, reason=str(exc)))
            continue

        frontmatter, body = split_frontmatter(text)
        if not frontmatter:
            continue
        if frontmatter.get("type") != "spec" and frontmatter.get("kind") != "spec":
            continue

        old_id = frontmatter.get("id")
        if rel in singleton_homes:
            singletons.append(
                Singleton(rel_path=rel, old_id=old_id if isinstance(old_id, str) else "")
            )
            continue
        if rel.startswith(f"{spec_root}/") and local_part_conforms(
            "spec", path.stem, project_root=project_root
        ):
            continue  # already a conforming numeric spec entity

        if not isinstance(old_id, str) or not old_id.startswith("spec:"):
            raise SpecMigrationRefused(
                f"{rel}: a spec doc without a declared `spec:` id; identity is authoritative "
                "and never guessed from a filename."
            )
        legacy.append(
            LegacySpec(
                source_rel=rel,
                old_id=old_id,
                frontmatter=frontmatter,
                body=body,
                already_numeric=_numeric_of(old_id),
            )
        )

    return Discovery(legacy=legacy, singletons=singletons, scan_skips=scan_skips)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k discovery -v`
Expected: PASS.

- [ ] **Step 5: Lint + types**

Run: `cd science && uv run ruff check src/science_tool/migrate_specs.py && uv run pyright src/science_tool/migrate_specs.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
cd science
git add src/science_tool/migrate_specs.py tests/test_migrate_specs.py
git commit -m "feat(migrate-specs): tree discovery of legacy specs, singletons, and scan skips"
```

---

### Task 4: Deterministic id allocation (number + slug + relocations)

**Files:**
- Modify: `science/src/science_tool/migrate_specs.py`
- Test: `science/tests/test_migrate_specs.py`

**Interfaces:**
- Consumes: `discover_specs`/`LegacySpec` (Task 3); `propose_number` from `science_tool.entity_reservation`; `derive_slug`, `resolve_path_policy` from `science_tool.entities`; `load_archive_index` from `science_tool.archive`.
- Produces: `Allocation` dataclass and `allocate_ids(project_root, legacy) -> Allocation`. Minted docs get sequential free numbers skipping the forbidden set (`committed ∪ archived ∪ preserved-relocation numbers`); preserved (already-numeric out-of-home) docs keep their id, no alias, and refuse if their number is taken at the canonical home.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_migrate_specs.py`:

```python
from science_tool.migrate_specs import Allocation, allocate_ids, discover_specs


def test_allocation_mints_distinct_sequential_numbers(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:date-a", "type": "spec", "title": "Alpha Title"})
    _write(project / "doc/plans/b.md", {"id": "spec:date-b", "type": "spec", "title": "Beta Title"})
    alloc = allocate_ids(project, discover_specs(project).legacy)
    assert alloc.id_substitutions == {
        "spec:date-a": "spec:0001-alpha-title",
        "spec:date-b": "spec:0002-beta-title",
    }
    assert alloc.dest_rel["spec:date-a"] == "entities/specs/0001-alpha-title.md"
    assert alloc.aliased == frozenset({"spec:date-a", "spec:date-b"})


def test_allocation_slug_is_from_title_not_id(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/drift.md", {"id": "spec:2026-01-01-old-filename", "type": "spec", "title": "A Wholly Different Title"})
    alloc = allocate_ids(project, discover_specs(project).legacy)
    assert alloc.new_local_part["spec:2026-01-01-old-filename"] == "0001-a-wholly-different-title"


def test_allocation_preserves_already_numeric_relocation(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/keep.md", {"id": "spec:0007-keep", "type": "spec", "title": "Keep It"})
    alloc = allocate_ids(project, discover_specs(project).legacy)
    assert alloc.id_substitutions == {}  # no renumber
    assert alloc.preserved_ids == frozenset({"spec:0007-keep"})
    assert alloc.dest_rel["spec:0007-keep"] == "entities/specs/0007-keep.md"
    assert "spec:0007-keep" not in alloc.aliased


def test_allocation_refuses_relocation_number_taken_at_home(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "entities/specs/0007-existing.md", {"id": "spec:0007-existing", "kind": "spec", "title": "Existing"})
    _write(project / "doc/plans/keep.md", {"id": "spec:0007-keep", "type": "spec", "title": "Keep It"})
    with pytest.raises(SpecMigrationRefused, match="0007"):
        allocate_ids(project, discover_specs(project).legacy)


def test_allocation_mixed_batch_skips_preserved_number(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/keep.md", {"id": "spec:0001-keep", "type": "spec", "title": "Keep It"})
    _write(project / "doc/plans/mint.md", {"id": "spec:date-mint", "type": "spec", "title": "Mint Me"})
    alloc = allocate_ids(project, discover_specs(project).legacy)
    # 0001 is spent by the preserved relocation; the minted doc must be 0002.
    assert alloc.id_substitutions == {"spec:date-mint": "spec:0002-mint-me"}
    assert alloc.preserved_ids == frozenset({"spec:0001-keep"})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k allocation -v`
Expected: FAIL (import errors for `allocate_ids`/`Allocation`).

- [ ] **Step 3: Implement allocation**

Append to `science/src/science_tool/migrate_specs.py` (add `from science_tool.entity_reservation import propose_number` to the imports):

```python
@dataclass(frozen=True)
class Allocation:
    id_substitutions: dict[str, str]  # old_id -> new spec:NNNN-slug (MINTED docs only)
    dest_rel: dict[str, str]          # old_id -> "entities/specs/NNNN-slug.md" (ALL legacy)
    new_local_part: dict[str, str]    # old_id -> "NNNN-slug" (ALL legacy)
    aliased: frozenset[str]           # old_ids whose old id is appended to aliases (minted)
    preserved_ids: frozenset[str]     # old_ids kept verbatim (already-numeric relocations)


def _number_taken_at_home(project_root: Path, number: int) -> bool:
    """True iff `number` is backed by a committed spec .md OR an archived spec id."""
    from science_tool.archive import load_archive_index

    directory = Path(project_root) / _spec_root(Path(project_root))
    if directory.is_dir():
        for entry in directory.glob("*.md"):
            match = _NUMERIC_LOCAL_RE.match(entry.stem)
            if match is not None and int(match.group(1)) == number:
                return True
    for entity_id in load_archive_index(Path(project_root)).resolvable_ids():
        prefix, _, local = entity_id.partition(":")
        if prefix != "spec":
            continue
        match = _NUMERIC_LOCAL_RE.match(local)
        if match is not None and int(match.group(1)) == number:
            return True
    return False


def allocate_ids(project_root: Path, legacy: list[LegacySpec]) -> Allocation:
    """Assign a deterministic `spec:NNNN-slug` to each legacy doc.

    Minted docs (id not already numeric) get sequential free numbers skipping the forbidden set
    (`committed ∪ archived ∪ preserved-relocation numbers`), sorted by old id. Already-numeric
    out-of-home docs are PURE RELOCATIONS: keep the id, no alias, no renumber; refuse if the number
    is taken at the canonical home.
    """
    project_root = Path(project_root).resolve()
    spec_root = _spec_root(project_root)
    start = propose_number(project_root, "spec")

    id_subs: dict[str, str] = {}
    dest_rel: dict[str, str] = {}
    new_local: dict[str, str] = {}
    aliased: set[str] = set()
    preserved: set[str] = set()

    # Preserved relocations first: keep the id, spend its number.
    forbidden: set[int] = set()
    for spec in legacy:
        if spec.already_numeric is None:
            continue
        if _number_taken_at_home(project_root, spec.already_numeric):
            raise SpecMigrationRefused(
                f"{spec.source_rel}: already-numeric spec {spec.old_id} keeps number "
                f"{spec.already_numeric:04d}, which is taken at {spec_root}/. Resolve the clash."
            )
        local = spec.old_id.split(":", 1)[1]  # the id's own NNNN-slug
        new_local[spec.old_id] = local
        dest_rel[spec.old_id] = f"{spec_root}/{local}.md"
        preserved.add(spec.old_id)
        forbidden.add(spec.already_numeric)

    # Minted docs: next free numbers >= start, skipping the forbidden set.
    number = start
    for spec in sorted(
        (s for s in legacy if s.already_numeric is None), key=lambda s: s.old_id
    ):
        while number in forbidden:
            number += 1
        local = f"{number:04d}-{derive_slug(spec.frontmatter['title'])}"
        new_id = f"spec:{local}"
        id_subs[spec.old_id] = new_id
        new_local[spec.old_id] = local
        dest_rel[spec.old_id] = f"{spec_root}/{local}.md"
        aliased.add(spec.old_id)
        forbidden.add(number)
        number += 1

    return Allocation(
        id_substitutions=id_subs,
        dest_rel=dest_rel,
        new_local_part=new_local,
        aliased=frozenset(aliased),
        preserved_ids=frozenset(preserved),
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k allocation -v`
Expected: PASS.

- [ ] **Step 5: Lint + types + commit**

```bash
cd science
uv run ruff check src/science_tool/migrate_specs.py && uv run pyright src/science_tool/migrate_specs.py
git add src/science_tool/migrate_specs.py tests/test_migrate_specs.py
git commit -m "feat(migrate-specs): deterministic numeric id allocation with preserved relocations"
```

---

### Task 5: Reference classification (two axes → five groups)

**Files:**
- Modify: `science/src/science_tool/migrate_specs.py`
- Test: `science/tests/test_migrate_specs.py`

**Interfaces:**
- Consumes: `iter_scannable_files`, `read_text_or_skip`, `_CODE_SUFFIXES` from `science_tool.text_scan`; `iter_prose_matches` from `science_tool.markdown_scan`; `_LINK_RE`, `_split_target`, `_resolve_link` from `science_tool.reference_rewrite`; `_REMOVABLE_FRONTMATTER_REF_KEYS` from `science_tool.entities`.
- Produces: `RefRecord` and `classify_references(project_root, *, id_substitutions, live_spec_ids, source_rels) -> list[RefRecord]`, plus `_live_spec_ids(project_root) -> set[str]`. Group assignment is the design's rewrite rule: `discusses` is always `manual_retarget`; unresolved is `manual_retarget`; already-canonical is `unchanged`; a migrated target is `rewritten` (rewriter-handled surface), `alias_resolved` (materializer-read-but-invisible field), or `identity_preserved` (inert surface).

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_migrate_specs.py`:

```python
from science_tool.migrate_specs import RefRecord, classify_references


def _by_group(records: list[RefRecord]) -> dict[str, list[RefRecord]]:
    out: dict[str, list[RefRecord]] = {}
    for record in records:
        out.setdefault(record.group, []).append(record)
    return out


def test_classification_two_axes(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(
        project / "doc/ref.md",
        {
            "id": "design:0001-r",
            "kind": "design",
            "title": "R",
            "related": ["spec:old-a"],
            "discusses": ["spec:old-a"],
            "same_as": ["spec:old-a"],
        },
        body="Prose mention of spec:old-a and spec:ghost and spec:0009-live here.\n",
    )
    _write(project / "entities/specs/0009-live.md", {"id": "spec:0009-live", "kind": "spec", "title": "Live"})
    records = classify_references(
        project,
        id_substitutions={"spec:old-a": "spec:0001-a"},
        live_spec_ids={"spec:0009-live"},
        source_rels=frozenset(),
    )
    groups = _by_group(records)
    assert any(r.surface == "related" for r in groups["rewritten"])
    assert any(r.surface == "same_as" for r in groups["alias_resolved"])
    assert any(r.surface == "discusses" for r in groups["manual_retarget"])  # always manual
    assert any(r.ref == "spec:ghost" for r in groups["manual_retarget"])  # unresolved
    assert any(r.surface == "mention" and r.ref == "spec:old-a" for r in groups["identity_preserved"])
    assert any(r.ref == "spec:0009-live" for r in groups["unchanged"])  # already-canonical


def test_classification_token_boundary(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(
        project / "doc/b.md",
        {"id": "design:0001-b", "kind": "design", "title": "B"},
        body="ignore science-spec:old-a here. But spec:old-a. ends a sentence.\n",
    )
    records = classify_references(
        project, id_substitutions={"spec:old-a": "spec:0001-a"}, live_spec_ids=set(), source_rels=frozenset()
    )
    mentions = [r for r in records if r.surface == "mention"]
    assert {r.ref for r in mentions} == {"spec:old-a"}  # science-spec:… not matched; trailing "." trimmed
    assert all(not r.ref.endswith(".") for r in mentions)


def test_classification_markdown_link_to_migrating_source_is_rewritten(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(
        project / "doc/plans/a.md",
        {"id": "spec:old-a", "type": "spec", "title": "A"},
        body="See [B](b.md#sec).\n",
    )
    # b.md is a migrating source (in source_rels), so the link is a path substitution -> rewritten
    records = classify_references(
        project,
        id_substitutions={},
        live_spec_ids=set(),
        source_rels=frozenset({"doc/plans/b.md"}),
    )
    assert any(r.surface == "markdown-link" and r.group == "rewritten" for r in records)


def test_classification_excludes_migrating_source_own_identity(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(
        project / "doc/plans/src.md",
        {"id": "spec:old-a", "type": "spec", "title": "A", "aliases": ["spec:old-a-alias"]},
        body="Body.\n",
    )
    records = classify_references(
        project,
        id_substitutions={"spec:old-a": "spec:0001-a"},
        live_spec_ids=set(),
        source_rels=frozenset({"doc/plans/src.md"}),
    )
    assert not any(r.ref in {"spec:old-a", "spec:old-a-alias"} for r in records)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k classification -v`
Expected: FAIL (import errors for `RefRecord`/`classify_references`).

- [ ] **Step 3: Implement classification**

Add to the imports of `migrate_specs.py`:

```python
from pathlib import PurePosixPath

from science_tool.entities import _REMOVABLE_FRONTMATTER_REF_KEYS
from science_tool.markdown_scan import iter_prose_matches
from science_tool.reference_rewrite import _LINK_RE, _resolve_link, _split_target
from science_tool.text_scan import _CODE_SUFFIXES, iter_scannable_files, read_text_or_skip
```

Append the code:

```python
_SPEC_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_-])spec:[A-Za-z0-9._/-]+")
_TRAILING_PUNCT = ".,;:)"
_READ_INVISIBLE_FIELDS = (
    "same_as",
    "blocked_by",
    "evidence_refs",
    "participants",
    "propositions",
    "source",
    "commits_to",
)


@dataclass(frozen=True)
class RefRecord:
    ref: str
    surface: str
    target: str  # "migrated" | "canonical" | "unresolved"
    group: str   # rewritten | alias_resolved | identity_preserved | unchanged | manual_retarget
    in_file: str


def _live_spec_ids(project_root: Path) -> set[str]:
    """Ids + aliases of the specs already living under entities/specs/ (already-canonical targets)."""
    ids: set[str] = set()
    directory = Path(project_root) / _spec_root(Path(project_root))
    if not directory.is_dir():
        return ids
    for path in directory.glob("*.md"):
        try:
            frontmatter, _body = split_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if isinstance(frontmatter.get("id"), str):
            ids.add(frontmatter["id"])
        for alias in frontmatter.get("aliases") or []:
            if isinstance(alias, str):
                ids.add(alias)
    return ids


def _iter_fm_ref_values(frontmatter: dict) -> list[tuple[str, str]]:
    """(surface, token) for every structured frontmatter reference surface. Skips id/aliases."""
    def _tokens(value: Any) -> list[str]:
        return [item for item in _as_list(value) if isinstance(item, str)]

    out: list[tuple[str, str]] = []
    for key in _REMOVABLE_FRONTMATTER_REF_KEYS:
        out.extend((key, token) for token in _tokens(frontmatter.get(key)))
    for relation in frontmatter.get("relations") or []:
        if isinstance(relation, dict) and isinstance(relation.get("target"), str):
            out.append(("relations[].target", relation["target"]))
    out.extend(("discusses", token) for token in _tokens(frontmatter.get("discusses")))
    if "spec" in frontmatter:
        out.extend(("spec-key", token) for token in _tokens(frontmatter.get("spec")))
    for key in _READ_INVISIBLE_FIELDS:
        out.extend((key, token) for token in _tokens(frontmatter.get(key)))
    return out


def _group_for(surface: str, target_class: str) -> str:
    if surface == "discusses":
        return "manual_retarget"  # never a valid bundle frame, regardless of target
    if target_class == "unresolved":
        return "manual_retarget"
    if target_class == "canonical":
        return "unchanged"
    # target_class == "migrated"
    if surface in _REMOVABLE_FRONTMATTER_REF_KEYS or surface in ("relations[].target", "markdown-link"):
        return "rewritten"
    if surface in _READ_INVISIBLE_FIELDS:
        return "alias_resolved"
    return "identity_preserved"  # spec-key, prose/code mention


def classify_references(
    project_root: Path,
    *,
    id_substitutions: dict[str, str],
    live_spec_ids: set[str],
    source_rels: frozenset[str],
) -> list[RefRecord]:
    """Classify every inbound `spec:` reference on two axes (surface × target) into the five groups.

    Reuses the canonical `iter_scannable_files` so the rewrite and audit see an identical file set.
    A migrating source's own `id`/`aliases` are never scanned, so they never count as inbound refs.
    """
    project_root = Path(project_root).resolve()
    records: list[RefRecord] = []

    def target_class(token: str) -> str:
        if token in id_substitutions:
            return "migrated"
        if token in live_spec_ids:
            return "canonical"
        return "unresolved"

    for path in iter_scannable_files(project_root):
        rel = path.relative_to(project_root).as_posix()
        text, _skip = read_text_or_skip(path, rel)
        if text is None:
            continue  # discovery already recorded oversized/unreadable markdown as a scan_skip
        is_code = path.suffix.lower() in _CODE_SUFFIXES
        is_markdown = path.suffix.lower() in {".md", ".markdown"}
        frontmatter: dict = {}
        body = text
        if is_markdown:
            frontmatter, body = split_frontmatter(text)

        for surface, token in _iter_fm_ref_values(frontmatter):
            if not token.startswith("spec:"):
                continue
            tclass = target_class(token)
            records.append(
                RefRecord(ref=token, surface=surface, target=tclass, group=_group_for(surface, tclass), in_file=rel)
            )

        if is_markdown:
            referrer_dir = PurePosixPath(rel).parent
            for match in iter_prose_matches(_LINK_RE, body):
                head, _tail = _split_target(match.group("target"))
                resolved = _resolve_link(head, referrer_dir) if head else None
                if resolved is not None and resolved in source_rels:
                    records.append(
                        RefRecord(
                            ref=match.group("target"),
                            surface="markdown-link",
                            target="migrated",
                            group="rewritten",
                            in_file=rel,
                        )
                    )

        scan_text = text if is_code else body
        matches = (
            _SPEC_TOKEN_RE.finditer(scan_text)
            if is_code
            else iter_prose_matches(_SPEC_TOKEN_RE, scan_text)
        )
        for match in matches:
            token = match.group(0).rstrip(_TRAILING_PUNCT)
            tclass = target_class(token)
            records.append(
                RefRecord(ref=token, surface="mention", target=tclass, group=_group_for("mention", tclass), in_file=rel)
            )

    return records
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k classification -v`
Expected: PASS.

- [ ] **Step 5: Lint + types + commit**

```bash
cd science
uv run ruff check src/science_tool/migrate_specs.py && uv run pyright src/science_tool/migrate_specs.py
git add src/science_tool/migrate_specs.py tests/test_migrate_specs.py
git commit -m "feat(migrate-specs): two-axis reference classification into five report groups"
```

---

### Task 6: Report assembly + `flip_ready` (the JSON contract)

**Files:**
- Modify: `science/src/science_tool/migrate_specs.py`
- Test: `science/tests/test_migrate_specs.py`

**Interfaces:**
- Consumes: `discover_specs`, `allocate_ids`, `classify_references`, `_live_spec_ids`, `project_legacy_frontmatter`.
- Produces: `build_report(project_root) -> dict` — the pinned JSON schema. Read-only. Projects every legacy doc first so a dry run **refuses** (raises `SpecMigrationRefused`) on an unprojectable doc; `flip_ready` is `true` iff `legacy_spec_count == singleton_count == manual_retarget_count == 0` **and** `scan_complete`.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_migrate_specs.py`:

```python
from science_tool.migrate_specs import build_report

_SCHEMA_KEYS = {
    "flip_ready",
    "legacy_spec_count",
    "singleton_count",
    "manual_retarget_count",
    "singletons",
    "migrated",
    "references",
    "manual_retarget",
    "scan_complete",
    "scan_skips",
}


def test_report_dry_run_has_schema_and_is_not_flip_ready(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:date-a", "type": "spec", "title": "Alpha"})
    report = build_report(project)
    assert set(report) == _SCHEMA_KEYS
    assert set(report["references"]) == {
        "rewritten",
        "alias_resolved",
        "identity_preserved",
        "unchanged",
        "manual_retarget",
    }
    assert report["legacy_spec_count"] == 1
    assert report["flip_ready"] is False  # discovered a legacy spec, has not applied
    assert report["migrated"][0]["old_id"] == "spec:date-a"
    assert report["manual_retarget_count"] == report["references"]["manual_retarget"]


def test_report_clean_project_is_flip_ready(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "entities/specs/0001-a.md", {"id": "spec:0001-a", "kind": "spec", "title": "A"})
    report = build_report(project)
    assert report["legacy_spec_count"] == 0
    assert report["singleton_count"] == 0
    assert report["manual_retarget_count"] == 0
    assert report["scan_complete"] is True
    assert report["flip_ready"] is True


def test_report_singleton_blocks_flip_ready(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "entities/research-question.md", {"id": "spec:research-question", "kind": "spec", "title": "RQ"})
    report = build_report(project)
    assert report["singleton_count"] == 1
    assert report["flip_ready"] is False


def test_report_manual_retarget_blocks_flip_ready(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "entities/specs/0001-a.md", {"id": "spec:0001-a", "kind": "spec", "title": "A"})
    _write(project / "doc/ref.md", {"id": "design:0001-r", "kind": "design", "title": "R", "discusses": ["spec:0001-a"]})
    report = build_report(project)
    assert report["manual_retarget_count"] >= 1
    assert report["flip_ready"] is False


def test_report_oversized_file_forces_scan_incomplete(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    from science_tool.text_scan import MAX_SCANNABLE_BYTES

    (project / "doc/plans").mkdir(parents=True, exist_ok=True)
    (project / "doc/plans/huge.md").write_text("x" * (MAX_SCANNABLE_BYTES + 1), encoding="utf-8")
    report = build_report(project)
    assert report["scan_complete"] is False
    assert report["flip_ready"] is False
    assert any(s["path"] == "doc/plans/huge.md" for s in report["scan_skips"])


def test_report_refuses_unprojectable_legacy_doc(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:date-a", "type": "spec", "title": "A", "status": "approved"})
    with pytest.raises(SpecMigrationRefused, match="approved"):
        build_report(project)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k report -v`
Expected: FAIL (import error for `build_report`).

- [ ] **Step 3: Implement `build_report`**

Append to `science/src/science_tool/migrate_specs.py`:

```python
def build_report(project_root: Path) -> dict:
    """The read-only flip-readiness report (the pinned JSON contract). Refuses on an unprojectable doc."""
    project_root = Path(project_root).resolve()
    disc = discover_specs(project_root)
    for spec in disc.legacy:  # project every legacy doc so planning refuses early on any bad one
        project_legacy_frontmatter(spec.frontmatter, source_rel=spec.source_rel)
    alloc = allocate_ids(project_root, disc.legacy)

    source_rels = frozenset(spec.source_rel for spec in disc.legacy)
    live = _live_spec_ids(project_root) | set(alloc.preserved_ids)
    records = classify_references(
        project_root,
        id_substitutions=alloc.id_substitutions,
        live_spec_ids=live,
        source_rels=source_rels,
    )

    counts = {group: 0 for group in ("rewritten", "alias_resolved", "identity_preserved", "unchanged", "manual_retarget")}
    for record in records:
        counts[record.group] += 1

    manual = [
        {
            "ref": record.ref,
            "surface": record.surface,
            "reason": "discusses" if record.surface == "discusses" else record.target,
            "in": record.in_file,
        }
        for record in records
        if record.group == "manual_retarget"
    ]
    migrated = [
        {
            "old_id": spec.old_id,
            "new_id": alloc.id_substitutions.get(spec.old_id, spec.old_id),
            "dest": alloc.dest_rel[spec.old_id],
        }
        for spec in disc.legacy
    ]

    legacy_spec_count = len(disc.legacy)
    singleton_count = len(disc.singletons)
    manual_retarget_count = counts["manual_retarget"]
    scan_complete = not disc.scan_skips
    flip_ready = (
        legacy_spec_count == 0
        and singleton_count == 0
        and manual_retarget_count == 0
        and scan_complete
    )

    return {
        "flip_ready": flip_ready,
        "legacy_spec_count": legacy_spec_count,
        "singleton_count": singleton_count,
        "manual_retarget_count": manual_retarget_count,
        "singletons": [singleton.rel_path for singleton in disc.singletons],
        "migrated": migrated,
        "references": {
            "rewritten": counts["rewritten"],
            "alias_resolved": counts["alias_resolved"],
            "identity_preserved": counts["identity_preserved"],
            "unchanged": counts["unchanged"],
            "manual_retarget": counts["manual_retarget"],
        },
        "manual_retarget": manual,
        "scan_complete": scan_complete,
        "scan_skips": [{"path": skip.path, "reason": skip.reason} for skip in disc.scan_skips],
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k report -v`
Expected: PASS.

- [ ] **Step 5: Lint + types + commit**

```bash
cd science
uv run ruff check src/science_tool/migrate_specs.py && uv run pyright src/science_tool/migrate_specs.py
git add src/science_tool/migrate_specs.py tests/test_migrate_specs.py
git commit -m "feat(migrate-specs): flip-readiness report assembly (pinned JSON schema)"
```

---

### Task 7: Transaction plan builder (render + substitute + collision preflight)

**Files:**
- Modify: `science/src/science_tool/migrate_specs.py`
- Test: `science/tests/test_migrate_specs.py`

**Interfaces:**
- Consumes: `plan_reference_rewrite`, `rewrite_outbound_links`, `_relative_link`, `_sub_prose_matches` from `science_tool.reference_rewrite`; `_validate_prospective_write` from `science_tool.entities`; `render_frontmatter` from `science_model.frontmatter`; `load_archive_index` from `science_tool.archive`; `hashlib`.
- Produces: `Destination`, `Transaction`, `_plan_transaction(project_root, disc, alloc) -> Transaction`, `_render_destination(...)`, `_collision_preflight(...)`. `_plan_transaction` renders each destination (projected frontmatter with minted id + old-id alias, intra-batch id substitution, outbound-link rebase, intra-batch path substitution), validates it via `_validate_prospective_write`, runs the batch collision preflight, and builds the single merged `RewriteReport` excluding `{sources ∪ destinations}`.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_migrate_specs.py`:

```python
from science_tool.migrate_specs import _plan_transaction, allocate_ids, discover_specs


def _plan(project: Path):
    disc = discover_specs(project)
    return _plan_transaction(project, disc, allocate_ids(project, disc.legacy))


def test_transaction_renders_new_id_and_old_id_alias(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:date-a", "type": "spec", "title": "Alpha"})
    txn = _plan(project)
    dest = next(d for d in txn.destinations if d.old_id == "spec:date-a")
    from science_model.frontmatter import split_frontmatter

    fm, _body = split_frontmatter(dest.rendered_text)
    assert fm["id"] == "spec:0001-alpha"
    assert "spec:date-a" in fm["aliases"]
    assert dest.dest_rel == "entities/specs/0001-alpha.md"


def test_transaction_intra_batch_id_substitution(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:date-a", "type": "spec", "title": "Alpha", "related": ["spec:date-b"]})
    _write(project / "doc/plans/b.md", {"id": "spec:date-b", "type": "spec", "title": "Beta"})
    txn = _plan(project)
    from science_model.frontmatter import split_frontmatter

    dest_a = next(d for d in txn.destinations if d.old_id == "spec:date-a")
    fm, _ = split_frontmatter(dest_a.rendered_text)
    assert fm["related"] == ["spec:0002-beta"]  # B's new numeric id


def test_transaction_intra_batch_path_substitution_with_anchor(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:date-a", "type": "spec", "title": "Alpha"}, body="See [B](b.md#sec).\n")
    _write(project / "doc/plans/b.md", {"id": "spec:date-b", "type": "spec", "title": "Beta"})
    txn = _plan(project)
    dest_a = next(d for d in txn.destinations if d.old_id == "spec:date-a")
    assert "0002-beta.md#sec" in dest_a.rendered_text  # link repointed to B's NEW location, anchor kept


def test_transaction_collision_preflight_refuses_duplicate_old_ids(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:dup", "type": "spec", "title": "Alpha"})
    _write(project / "doc/specs/a.md", {"id": "spec:dup", "kind": "spec", "title": "Alpha Two"})
    with pytest.raises(SpecMigrationRefused, match="duplicate old id"):
        _plan(project)
```

> **Executor note (fixture for `_validate_prospective_write`):** `_plan_transaction` validates each rendered destination through `entities._validate_prospective_write`, which loads the project's sources and runs the source audit. If the minimal `_spec_project` fixture makes that audit report "unwired" (raising `EntityCommandError`), enrich the fixture's `science.yaml` to mirror the project config used by the repo's existing entity import/create tests (search `tests/` for the fixture that exercises `apply_import`/`create_entity`), rather than weakening the validation. Do **not** switch the call to a lighter validator — the design mandates `_validate_prospective_write`.

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k transaction -v`
Expected: FAIL (import error for `_plan_transaction`).

- [ ] **Step 3: Implement the transaction plan builder**

Add to the imports of `migrate_specs.py`:

```python
import hashlib

from science_model.frontmatter import render_frontmatter

from science_tool.entities import _validate_prospective_write
from science_tool.reference_rewrite import (
    RewriteReport,
    _relative_link,
    _sub_prose_matches,
    plan_reference_rewrite,
    rewrite_outbound_links,
)
```

Append the code:

```python
@dataclass(frozen=True)
class Destination:
    old_id: str
    new_id: str
    source_rel: str
    dest_rel: str
    number: int
    local_part: str
    rendered_text: str
    preimage_sha256: str  # of the source at plan time


@dataclass(frozen=True)
class Transaction:
    destinations: list[Destination]
    ref_report: RewriteReport
    source_rels: frozenset[str]
    dest_rels: frozenset[str]


def _apply_path_subs_to_body(body: str, new_dir: PurePosixPath, path_subs: dict[str, str]) -> str:
    """Repoint a moved body's links whose (rebased) target is another migrating source's old path."""
    def _replace(match: re.Match[str]) -> str:
        target = match.group("target")
        head, tail = _split_target(target)
        resolved = _resolve_link(head, new_dir) if head else None
        if resolved is not None and resolved in path_subs:
            return f"[{match.group('text')}]({_relative_link(new_dir, path_subs[resolved]) + tail})"
        return match.group(0)

    return _sub_prose_matches(_LINK_RE, body, _replace)


def _render_destination(
    spec: LegacySpec,
    alloc: Allocation,
    id_subs: dict[str, str],
    path_subs: dict[str, str],
    new_id: str,
    dest_rel: str,
) -> str:
    """Project + assign identity + intra-batch substitute + rebase links -> the destination's text."""
    _old_id, fm = project_legacy_frontmatter(spec.frontmatter, source_rel=spec.source_rel)

    if spec.old_id in alloc.aliased:  # minted: new id, old id appended to aliases
        fm["id"] = new_id
        fm["aliases"] = _dedup([*_as_list(fm.get("aliases")), spec.old_id])

    for key in _REMOVABLE_FRONTMATTER_REF_KEYS:  # intra-batch id substitution
        value = fm.get(key)
        if isinstance(value, list):
            fm[key] = [id_subs.get(item, item) if isinstance(item, str) else item for item in value]
    for relation in fm.get("relations") or []:
        if isinstance(relation, dict) and isinstance(relation.get("target"), str):
            relation["target"] = id_subs.get(relation["target"], relation["target"])

    old_dir = PurePosixPath(spec.source_rel).parent
    new_dir = PurePosixPath(dest_rel).parent
    body, _hits = rewrite_outbound_links(spec.body, old_dir, new_dir)
    body = _apply_path_subs_to_body(body, new_dir, path_subs)
    return render_frontmatter(fm, body)


def _collision_preflight(project_root: Path, disc: Discovery, alloc: Allocation) -> None:
    """Refuse if any new canonical id / preserved alias / appended old id clashes with an existing
    id/alias/archive token or with another batch member."""
    from science_tool.archive import load_archive_index

    existing = _live_spec_ids(project_root) | set(load_archive_index(project_root).resolvable_ids())
    seen: dict[str, str] = {}

    def _check(token: str, where: str) -> None:
        if token in existing:
            raise SpecMigrationRefused(
                f"{where}: {token!r} collides with an existing id/alias/archive token."
            )
        if token in seen:
            raise SpecMigrationRefused(f"{where}: {token!r} collides with {seen[token]}.")
        seen[token] = where

    old_ids = [spec.old_id for spec in disc.legacy]
    if len(old_ids) != len(set(old_ids)):
        raise SpecMigrationRefused("duplicate old id(s) in the discovered batch.")

    for spec in disc.legacy:
        _check(alloc.id_substitutions.get(spec.old_id, spec.old_id), spec.source_rel)
        for alias in _as_list(spec.frontmatter.get("aliases")):
            if isinstance(alias, str):
                _check(alias, spec.source_rel)
        if spec.old_id in alloc.aliased:
            _check(spec.old_id, spec.source_rel)


def _plan_transaction(project_root: Path, disc: Discovery, alloc: Allocation) -> Transaction:
    """Build the frozen batch plan. Writes nothing; any refusal aborts the whole batch."""
    project_root = Path(project_root).resolve()
    id_subs = dict(alloc.id_substitutions)
    path_subs = {spec.source_rel: alloc.dest_rel[spec.old_id] for spec in disc.legacy}

    _collision_preflight(project_root, disc, alloc)

    destinations: list[Destination] = []
    for spec in disc.legacy:
        new_id = id_subs.get(spec.old_id, spec.old_id)
        dest_rel = alloc.dest_rel[spec.old_id]
        local_part = alloc.new_local_part[spec.old_id]
        rendered = _render_destination(spec, alloc, id_subs, path_subs, new_id, dest_rel)
        _validate_prospective_write(
            project_root=project_root,
            rel_path=Path(dest_rel),
            text=rendered,
            target_entity_id=new_id,
        )
        preimage = hashlib.sha256((project_root / spec.source_rel).read_bytes()).hexdigest()
        destinations.append(
            Destination(
                old_id=spec.old_id,
                new_id=new_id,
                source_rel=spec.source_rel,
                dest_rel=dest_rel,
                number=int(local_part[:4]),
                local_part=local_part,
                rendered_text=rendered,
                preimage_sha256=preimage,
            )
        )

    source_rels = frozenset(spec.source_rel for spec in disc.legacy)
    dest_rels = frozenset(alloc.dest_rel[spec.old_id] for spec in disc.legacy)
    exclude = frozenset((project_root / rel) for rel in (source_rels | dest_rels))
    ref_report = plan_reference_rewrite(
        project_root, id_substitutions=id_subs, path_substitutions=path_subs, exclude=exclude
    )
    return Transaction(
        destinations=destinations,
        ref_report=ref_report,
        source_rels=source_rels,
        dest_rels=dest_rels,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k transaction -v`
Expected: PASS.

- [ ] **Step 5: Lint + types + commit**

```bash
cd science
uv run ruff check src/science_tool/migrate_specs.py && uv run pyright src/science_tool/migrate_specs.py
git add src/science_tool/migrate_specs.py tests/test_migrate_specs.py
git commit -m "feat(migrate-specs): frozen batch plan — render, substitute, collision preflight"
```

---

### Task 8: Batch apply transaction + journal + `migrate()`

**Files:**
- Modify: `science/src/science_tool/migrate_specs.py`
- Test: `science/tests/test_migrate_specs.py`

**Interfaces:**
- Consumes: `_snapshot`, `_restore`, `apply_reference_rewrite` (via `entity_import`), `audit_moved_references` from `science_tool.entity_import`; `claim_number_in_dir` from `science_tool.entity_reservation`; `atomic_write_text` from `science_model.frontmatter`; `json`.
- Produces: `_journal_write(project_root, txn)`, `_apply_transaction(project_root, txn)`, and `migrate(project_root, *, apply=False) -> dict`. `migrate` refuses if a journal exists (an interrupted pass must be `resume`d). Plan-only returns `build_report`; `--apply` runs the transaction then returns a fresh post-apply `build_report`.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_migrate_specs.py`:

```python
from science_tool.migrate_specs import JOURNAL_PATH, migrate


def test_migrate_apply_relocates_rewrites_and_leaves_clean_tree(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:date-a", "type": "spec", "title": "Alpha", "related": ["spec:date-b"]})
    _write(project / "doc/plans/b.md", {"id": "spec:date-b", "type": "spec", "title": "Beta"}, body="See [A](a.md).\n")
    _write(project / "doc/ref.md", {"id": "design:0001-r", "kind": "design", "title": "R", "related": ["spec:date-a"]})

    report = migrate(project, apply=True)

    assert not (project / "doc/plans/a.md").exists()
    assert (project / "entities/specs/0001-alpha.md").exists()
    assert (project / "entities/specs/0002-beta.md").exists()

    from science_model.frontmatter import split_frontmatter

    fm_a, _ = split_frontmatter((project / "entities/specs/0001-alpha.md").read_text(encoding="utf-8"))
    assert fm_a["related"] == ["spec:0002-beta"]  # intra-batch id substitution landed
    assert "spec:date-a" in fm_a["aliases"]

    fm_ref, _ = split_frontmatter((project / "doc/ref.md").read_text(encoding="utf-8"))
    assert fm_ref["related"] == ["spec:0001-alpha"]  # non-migrating referrer rewritten

    body_b = (project / "entities/specs/0002-beta.md").read_text(encoding="utf-8")
    assert "0001-alpha.md" in body_b  # B's link to A repointed

    assert not (project / JOURNAL_PATH).exists()  # journal cleared on success
    # a fresh dry run now sees a clean tree
    assert build_report(project)["legacy_spec_count"] == 0


def test_migrate_apply_rolls_back_on_injected_claim_failure(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:date-a", "type": "spec", "title": "Alpha"})
    _write(project / "doc/plans/b.md", {"id": "spec:date-b", "type": "spec", "title": "Beta"})

    from science_tool import migrate_specs

    real_claim = migrate_specs.claim_number_in_dir
    calls = {"n": 0}

    def _flaky(*args: object, **kwargs: object):
        calls["n"] += 1
        if calls["n"] == 2:  # let the first claim land, blow up the second
            raise OSError("disk full")
        return real_claim(*args, **kwargs)  # type: ignore[arg-type]

    with mock.patch.object(migrate_specs, "claim_number_in_dir", _flaky):
        with pytest.raises(OSError, match="disk full"):
            migrate(project, apply=True)

    # whole batch rolled back: both sources restored, no destinations, no journal
    assert (project / "doc/plans/a.md").exists()
    assert (project / "doc/plans/b.md").exists()
    assert not list((project / "entities/specs").glob("*.md"))
    assert not (project / JOURNAL_PATH).exists()


def test_migrate_refuses_when_journal_exists(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    journal = project / JOURNAL_PATH
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text("{}", encoding="utf-8")
    with pytest.raises(SpecMigrationRefused, match="INTERRUPTED"):
        migrate(project, apply=True)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k "migrate_apply or migrate_refuses" -v`
Expected: FAIL (import error for `migrate`).

- [ ] **Step 3: Implement apply + journal + `migrate`**

Add to the imports of `migrate_specs.py`:

```python
import json

from science_model.frontmatter import atomic_write_text

from science_tool.entity_import import _restore, _snapshot, apply_reference_rewrite, audit_moved_references
from science_tool.entity_reservation import claim_number_in_dir
```

Append the code:

```python
def _journal_write(project_root: Path, txn: Transaction) -> None:
    """The recovery journal: every path's role and both its preimage and postimage (content|absent).

    Written atomically BEFORE the first mutation. `preimage_sha256=None` means absent; `postimage=None`
    means absent. moved-dest carries the number + local_part so resume can re-`claim` it.
    """
    entries: list[dict] = []
    for dest in txn.destinations:
        source = project_root / dest.source_rel
        entries.append(
            {
                "role": "moved-source",
                "rel": dest.source_rel,
                "preimage_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "postimage": None,
            }
        )
        entries.append(
            {
                "role": "moved-dest",
                "rel": dest.dest_rel,
                "preimage_sha256": None,
                "postimage": dest.rendered_text,
                "number": dest.number,
                "local_part": dest.local_part,
            }
        )
    for edit in txn.ref_report.edits:
        entries.append(
            {
                "role": "referrer",
                "rel": edit.rel_path,
                "preimage_sha256": edit.preimage_sha256,
                "postimage": edit.postimage,
            }
        )
    journal = project_root / JOURNAL_PATH
    journal.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(journal, json.dumps({"entries": entries}, indent=2) + "\n")


def _apply_transaction(project_root: Path, txn: Transaction) -> None:
    """Snapshot-all → journal → move-all → replay-once → audit-all → global restore on any failure."""
    project_root = Path(project_root).resolve()
    sources = [project_root / dest.source_rel for dest in txn.destinations]
    dests = [project_root / dest.dest_rel for dest in txn.destinations]
    referrers = [project_root / edit.rel_path for edit in txn.ref_report.edits]
    snapshot = _snapshot([*sources, *dests, *referrers])
    _journal_write(project_root, txn)

    exclude = frozenset((project_root / rel) for rel in (txn.source_rels | txn.dest_rels))
    mutated: set[Path] = set()
    written: list[str] = []
    try:
        for dest in txn.destinations:
            source = project_root / dest.source_rel
            current = source.read_text(encoding="utf-8")
            if hashlib.sha256(current.encode("utf-8")).hexdigest() != dest.preimage_sha256:
                raise SpecMigrationRefused(
                    f"{dest.source_rel} changed since planning; re-run the preview."
                )
            # dest joins `mutated` only AFTER the claim returns (claim self-cleans its own partial).
            claim_number_in_dir(project_root, "spec", dest.number, dest.local_part, dest.rendered_text)
            mutated.add(project_root / dest.dest_rel)
            source.unlink()
            mutated.add(source)
        apply_reference_rewrite(project_root, txn.ref_report, exclude=exclude, written=written)
        for dest in txn.destinations:
            problems = audit_moved_references(project_root, dest.dest_rel, exclude=exclude)
            if problems:
                raise SpecMigrationRefused(
                    "post-move reference audit failed; the batch was rolled back:\n  "
                    + "\n  ".join(problems)
                )
    except BaseException:
        _restore(snapshot, restrict={*mutated, *(project_root / rel for rel in written)})
        (project_root / JOURNAL_PATH).unlink(missing_ok=True)
        raise
    (project_root / JOURNAL_PATH).unlink()


def migrate(project_root: Path, *, apply: bool = False) -> dict:
    """Plan the whole batch, then — and only then — write it. Returns the flip-readiness report."""
    project_root = Path(project_root).resolve()
    if (project_root / JOURNAL_PATH).is_file():
        raise SpecMigrationRefused(
            f"{JOURNAL_PATH} exists: a previous write pass was INTERRUPTED. Finish it with --resume."
        )
    if not apply:
        return build_report(project_root)

    disc = discover_specs(project_root)
    for spec in disc.legacy:
        project_legacy_frontmatter(spec.frontmatter, source_rel=spec.source_rel)
    alloc = allocate_ids(project_root, disc.legacy)
    txn = _plan_transaction(project_root, disc, alloc)
    _apply_transaction(project_root, txn)
    return build_report(project_root)  # recompute against the mutated tree
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k "migrate_apply or migrate_refuses" -v`
Expected: PASS.

- [ ] **Step 5: Lint + types + commit**

```bash
cd science
uv run ruff check src/science_tool/migrate_specs.py && uv run pyright src/science_tool/migrate_specs.py
git add src/science_tool/migrate_specs.py tests/test_migrate_specs.py
git commit -m "feat(migrate-specs): crash-safe batch apply transaction with recovery journal"
```

---

### Task 9: Resume (per-role state machine)

**Files:**
- Modify: `science/src/science_tool/migrate_specs.py`
- Test: `science/tests/test_migrate_specs.py`

**Interfaces:**
- Consumes: `claim_number_in_dir`, `audit_moved_references`, `atomic_write_text`, `hashlib`, `json` (already imported).
- Produces: `resume(project_root) -> dict`. Classifies every journaled path first (content|absent); refuses on a third state (neither preimage nor postimage — e.g. a `SIGKILL` partial moved-dest); clears every journaled number's sentinel at both crash points; replays each not-yet-done path by its role's op; runs `audit_moved_references` per destination; then deletes the journal. Refuses "no interrupted transaction" when no journal exists; refuses a sentinel for a non-journaled number (single-writer).

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_migrate_specs.py`:

```python
import json as _json

from science_tool.migrate_specs import resume


def _journal(project: Path, entries: list[dict]) -> None:
    journal = project / JOURNAL_PATH
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(_json.dumps({"entries": entries}, indent=2) + "\n", encoding="utf-8")


def _sha(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_resume_finishes_interrupted_pass(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    # State: source still present (pre-image), dest absent (pre-image), referrer at pre-image.
    src = _write(project / "doc/plans/a.md", {"id": "spec:date-a", "type": "spec", "title": "Alpha"})
    src_text = src.read_text(encoding="utf-8")
    ref = _write(project / "doc/ref.md", {"id": "design:0001-r", "kind": "design", "title": "R", "related": ["spec:date-a"]})
    ref_pre = ref.read_text(encoding="utf-8")
    dest_text = "---\nid: spec:0001-alpha\nkind: spec\ntitle: Alpha\naliases:\n- spec:date-a\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n\nBody.\n"
    ref_post = ref_pre.replace("spec:date-a", "spec:0001-alpha")
    _journal(
        project,
        [
            {"role": "moved-source", "rel": "doc/plans/a.md", "preimage_sha256": _sha(src_text), "postimage": None},
            {"role": "moved-dest", "rel": "entities/specs/0001-alpha.md", "preimage_sha256": None, "postimage": dest_text, "number": 1, "local_part": "0001-alpha"},
            {"role": "referrer", "rel": "doc/ref.md", "preimage_sha256": _sha(ref_pre), "postimage": ref_post},
        ],
    )

    resume(project)

    assert not (project / "doc/plans/a.md").exists()  # moved-source unlinked
    assert (project / "entities/specs/0001-alpha.md").read_text(encoding="utf-8") == dest_text  # dest claimed
    assert (project / "doc/ref.md").read_text(encoding="utf-8") == ref_post  # referrer replaced
    assert not (project / JOURNAL_PATH).exists()  # journal cleared


def test_resume_refuses_partial_moved_dest_third_state(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    # A partial dest exists: content that is neither absent (preimage) nor the recorded postimage.
    partial = project / "entities/specs/0001-alpha.md"
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text("PARTIAL", encoding="utf-8")
    _journal(
        project,
        [
            {"role": "moved-dest", "rel": "entities/specs/0001-alpha.md", "preimage_sha256": None, "postimage": "FULL", "number": 1, "local_part": "0001-alpha"},
        ],
    )
    with pytest.raises(SpecMigrationRefused, match="neither"):
        resume(project)


def test_resume_refuses_with_no_journal(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    with pytest.raises(SpecMigrationRefused, match="no interrupted"):
        resume(project)


def test_resume_refuses_stray_sentinel_for_non_journaled_number(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    (project / "entities/specs").mkdir(parents=True, exist_ok=True)
    (project / "entities/specs/.0009.reserving").write_text("", encoding="utf-8")
    _journal(
        project,
        [
            {"role": "moved-dest", "rel": "entities/specs/0001-a.md", "preimage_sha256": None, "postimage": "FULL", "number": 1, "local_part": "0001-a"},
        ],
    )
    with pytest.raises(SpecMigrationRefused, match="does not own"):
        resume(project)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k resume -v`
Expected: FAIL (import error for `resume`).

- [ ] **Step 3: Implement resume**

Append to `science/src/science_tool/migrate_specs.py`:

```python
_SENTINEL_RE = re.compile(r"^\.(\d+)\.reserving$")


def _disk_state(path: Path) -> tuple[str, str | None]:
    """('absent', None) or ('content', sha256)."""
    if not path.exists() and not path.is_symlink():
        return ("absent", None)
    return ("content", hashlib.sha256(path.read_bytes()).hexdigest())


def _journal_state(sha_or_none: str | None) -> tuple[str, str | None]:
    return ("absent", None) if sha_or_none is None else ("content", sha_or_none)


def _postimage_state(entry: dict) -> tuple[str, str | None]:
    post = entry["postimage"]
    if post is None:
        return ("absent", None)
    return ("content", hashlib.sha256(post.encode("utf-8")).hexdigest())


def resume(project_root: Path) -> dict:
    """Finish an INTERRUPTED write pass from its journal. Never re-plans."""
    project_root = Path(project_root).resolve()
    journal = project_root / JOURNAL_PATH
    if not journal.is_file():
        raise SpecMigrationRefused(f"{JOURNAL_PATH} does not exist: there is no interrupted transaction.")

    entries = json.loads(journal.read_text(encoding="utf-8"))["entries"]
    spec_dir = project_root / _spec_root(project_root)

    # Single-writer: a sentinel for a number this migration does not own is unsupported.
    journaled_numbers = {entry["number"] for entry in entries if entry["role"] == "moved-dest"}
    if spec_dir.is_dir():
        for sentinel in spec_dir.glob(".*.reserving"):
            match = _SENTINEL_RE.match(sentinel.name)
            if match is not None and int(match.group(1)) not in journaled_numbers:
                raise SpecMigrationRefused(
                    f"{sentinel.name}: a reservation sentinel for a number this migration does not "
                    "own; refusing (single-writer assumption)."
                )

    # Classify every path first; refuse on any third state before writing anything.
    todo: list[dict] = []
    refusals: list[str] = []
    for entry in entries:
        path = project_root / entry["rel"]
        state = _disk_state(path)
        if state == _postimage_state(entry):
            continue  # already done
        if state == _journal_state(entry["preimage_sha256"]):
            todo.append(entry)
            continue
        refusals.append(
            f"{entry['rel']}: neither the pre-image nor the post-image the migration planned "
            "(a partial or externally-changed file). Restore it and re-run."
        )
    if refusals:
        raise SpecMigrationRefused(
            "The interrupted migration cannot be resumed. NOTHING further was written.\n  "
            + "\n  ".join(refusals)
        )

    # Clear every journaled number's sentinel at BOTH crash points (dest-absent and dest-committed).
    for number in journaled_numbers:
        (spec_dir / f".{number:04d}.reserving").unlink(missing_ok=True)

    for entry in todo:
        path = project_root / entry["rel"]
        if entry["role"] == "moved-source":
            path.unlink(missing_ok=True)
        elif entry["role"] == "moved-dest":
            claim_number_in_dir(project_root, "spec", entry["number"], entry["local_part"], entry["postimage"])
        elif entry["role"] == "referrer":
            atomic_write_text(path, entry["postimage"])

    for entry in entries:
        if entry["role"] != "moved-dest":
            continue
        problems = audit_moved_references(project_root, entry["rel"])
        if problems:
            raise SpecMigrationRefused(
                "post-move reference audit failed after resume:\n  " + "\n  ".join(problems)
            )

    journal.unlink()
    return build_report(project_root)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k resume -v`
Expected: PASS.

- [ ] **Step 5: Run the whole module test file**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -q`
Expected: PASS (all tasks 1–9 green together).

- [ ] **Step 6: Lint + types + commit**

```bash
cd science
uv run ruff check src/science_tool/migrate_specs.py && uv run pyright src/science_tool/migrate_specs.py
git add src/science_tool/migrate_specs.py tests/test_migrate_specs.py
git commit -m "feat(migrate-specs): per-role resume state machine with sentinel recovery"
```

---

### Task 10: CLI command `science entity migrate-specs`

**Files:**
- Modify: `science/src/science_tool/entities_cli.py` (register a new command on `entity_group`, near `entity_migrate_hypothesis` at line 327)
- Test: `science/tests/test_migrate_specs.py`

**Interfaces:**
- Consumes: `migrate`, `resume`, `SpecMigrationRefused` from `science_tool.migrate_specs`; `entity_group` (existing click group).
- Produces: the `migrate-specs` subcommand with `--apply`, `--resume`, `--format {text,json}`. Turns `SpecMigrationRefused` into a `click.ClickException`.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_migrate_specs.py`:

```python
from click.testing import CliRunner

from science_tool.entities_cli import entity_group


def test_cli_json_dry_run_emits_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:date-a", "type": "spec", "title": "Alpha"})
    monkeypatch.chdir(project)
    result = CliRunner().invoke(entity_group, ["migrate-specs", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = _json.loads(result.output)
    assert payload["flip_ready"] is False
    assert payload["legacy_spec_count"] == 1
    assert list((project / "entities/specs").glob("*.md")) == []  # dry run wrote nothing


def test_cli_apply_then_dry_run_reports_flip_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:date-a", "type": "spec", "title": "Alpha"})
    monkeypatch.chdir(project)
    runner = CliRunner()
    applied = runner.invoke(entity_group, ["migrate-specs", "--apply", "--format", "json"])
    assert applied.exit_code == 0, applied.output
    assert _json.loads(applied.output)["flip_ready"] is True
    assert (project / "entities/specs/0001-alpha.md").exists()


def test_cli_refusal_becomes_click_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:date-a", "type": "spec", "title": "A", "status": "approved"})
    monkeypatch.chdir(project)
    result = CliRunner().invoke(entity_group, ["migrate-specs", "--format", "json"])
    assert result.exit_code != 0
    assert "approved" in result.output
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k cli -v`
Expected: FAIL — `migrate-specs` is not a registered command (`Usage` / no such command).

- [ ] **Step 3: Register the command**

In `science/src/science_tool/entities_cli.py`, after the `entity_migrate_hypothesis` function (ends near line 396), add:

```python
@entity_group.command("migrate-specs")
@click.option("--apply", "apply_changes", is_flag=True, help="Write. Without this, plan only.")
@click.option(
    "--resume",
    "resume_interrupted",
    is_flag=True,
    help="Finish an INTERRUPTED write pass from its journal. Never re-plans.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def entity_migrate_specs(apply_changes: bool, resume_interrupted: bool, output_format: str) -> None:
    """Canonicalize this project's legacy/loose spec docs to numeric `entities/specs/NNNN-slug.md`.

    `spec:` references still resolve as annotation-only today — this command makes a project
    flip-ready; it does not change resolution. Plan-then-`--apply`; an interrupted apply is `--resume`d.
    """
    import json as _json

    from science_tool.migrate_specs import SpecMigrationRefused, migrate, resume

    try:
        report = resume(Path.cwd()) if resume_interrupted else migrate(Path.cwd(), apply=apply_changes)
    except SpecMigrationRefused as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        click.echo(_json.dumps(report, indent=2))
        return

    if apply_changes or resume_interrupted:
        click.echo(f"migration applied; flip_ready={report['flip_ready']}")
        click.echo(f"references now: {report['references']}")
    else:
        click.echo(
            f"would migrate {len(report['migrated'])} legacy spec(s); flip_ready={report['flip_ready']}"
        )
        if report["manual_retarget_count"]:
            click.echo(f"manual-retarget ({report['manual_retarget_count']}): see --format json")
        click.echo("(dry run — nothing written; re-run with --apply)")
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py -k cli -v`
Expected: PASS.

- [ ] **Step 5: Lint + types + commit**

```bash
cd science
uv run ruff check src/science_tool/entities_cli.py && uv run pyright src/science_tool/entities_cli.py
git add src/science_tool/entities_cli.py tests/test_migrate_specs.py
git commit -m "feat(migrate-specs): science entity migrate-specs CLI command"
```

---

### Task 11: Guard — the switch stays annotation-only

**Files:**
- Test: `science/tests/test_migrate_specs.py`

**Interfaces:**
- Consumes: `_ANNOTATION_REF_PREFIXES` from `science_tool.graph.sources`.
- Produces: a guard test asserting the resolution switch is untouched; plus a run of the S3a guard suites to prove they still pass unchanged.

- [ ] **Step 1: Write the guard test**

Add to `science/tests/test_migrate_specs.py`:

```python
def test_spec_remains_annotation_only() -> None:
    """S3b ships the migration only; the resolution flip is a separate later effort."""
    from science_tool.graph.sources import _ANNOTATION_REF_PREFIXES

    assert _ANNOTATION_REF_PREFIXES == frozenset({"meta", "spec"})
```

- [ ] **Step 2: Run the guard test**

Run: `cd science && uv run --frozen pytest tests/test_migrate_specs.py::test_spec_remains_annotation_only -v`
Expected: PASS.

- [ ] **Step 3: Prove the S3a guard suites still pass unchanged**

Run: `cd science && uv run --frozen pytest tests/test_spec_materialization.py tests/test_meta_reference.py tests/test_membership_materialize.py -q`
Expected: PASS (0 failures) — no S3a guard file was edited.

- [ ] **Step 4: Full suite**

Run: `cd science && uv run --frozen pytest -q`
Expected: PASS (default markers; snapshot/real_projects excluded).

- [ ] **Step 5: Commit**

```bash
cd science
git add tests/test_migrate_specs.py
git commit -m "test(migrate-specs): guard that spec stays annotation-only (switch untouched)"
```

---

### Task 12: User-guide documentation

**Files:**
- Modify: `docs/user-guide/entities.md` (repo-root docs tree)

**Interfaces:**
- Consumes: nothing (prose).
- Produces: a `migrate-specs` section documenting plan-then-`--apply`, the projection rules, the five report groups, `flip_ready`, the singleton report, refusals, and the annotation-only sequencing statement.

- [ ] **Step 1: Read the current doc to find the right insertion point**

Run: `sed -n '1,60p' docs/user-guide/entities.md` and locate the Source Entity / spec CLI material. Insert the new section after that material, matching the file's existing heading depth (use `##` if top-level sections are `##`).

- [ ] **Step 2: Add the section**

Insert this section (adjust the heading level to match the file):

```markdown
## Migrating legacy specs (`science entity migrate-specs`)

Older projects hold `spec`-typed design docs at loose paths (`doc/plans/…`,
`doc/specs/…`) with date-slug or semantic ids. `science entity migrate-specs`
canonicalizes them into numeric `entities/specs/NNNN-slug.md` entities, preserving
each old id as an alias and repointing the references it can safely rewrite.

**`spec:` references still resolve as annotation-only today.** This command makes a
project *flip-ready*; it does not change resolution. Turning on `spec:` resolution
is a separate, later, gated step — run the migration first, land clean, then adopt
the revision that flips resolution (migrate-then-flip across revisions).

Plan first (writes nothing), then apply:

```bash
science entity migrate-specs                 # dry run: the plan + a flip-readiness report
science entity migrate-specs --format json   # the machine-readable report (flip_ready, counts)
science entity migrate-specs --apply         # relocate, rewrite, and report
science entity migrate-specs --resume        # finish an interrupted --apply from its journal
```

**What it projects.** Legacy frontmatter is mapped to the canonical spec schema:
`type: spec` → `kind: spec`; `date:` seeds `created`/`updated`; `related_questions`
/ `related_specs` fold into `related`; unambiguous legacy statuses map to the
canonical vocabulary (`draft/active/complete/superseded/retired/archived`).
Anything ambiguous — an unmappable status like `approved`, a missing `id:`/`title`,
an authored load-derived key — is **refused, per file**; the migration never guesses.

**How references are reported.** Each `spec:` reference is classified into five
groups: **rewritten** (auto-repointed), **alias_resolved** (resolves via the old-id
alias, optional cleanup), **identity_preserved** (inert prose/key mentions),
**unchanged** (already points at a live numeric spec), and **manual_retarget**
(`discusses`/membership refs and unresolved ids — a human must fix these).

**Flip-readiness.** `flip_ready` is `true` only when no un-relocated legacy spec, no
`kind: spec` file at a singleton home, and no `manual_retarget` reference remains,
and the scan was complete. A singleton-home `spec` file is **reported, never
auto-relocated** — reconciling it is a project judgment.
```

- [ ] **Step 3: Commit**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/specs-plans-as-entities-s3b
git add docs/user-guide/entities.md
git commit -m "docs(entities): document science entity migrate-specs"
```

---

## Self-Review

**1. Spec coverage** — every design section maps to a task:

| Design section | Task |
|---|---|
| Rollout staging (switch untouched) | Global Constraints + Task 11 |
| The `discusses` correction | Task 5 (`_group_for` special-cases discusses) |
| Component 1 — discovery + singleton + scan_skips | Task 3 |
| Component 2 — projection (RUNTIME_ONLY/LEGACY_ALIAS/status/dates/related/aliases) | Task 2 |
| Component 3 — two-axis classification + token boundary + five groups | Task 5 |
| Component 4 — id allocation (number/slug/relocation) | Task 4 |
| Component 4 — `claim_number_in_dir` hardening | Task 1 |
| Component 4 — render/rebase/substitute + collision preflight | Task 7 |
| Component 4 — batch transaction + journal | Task 8 |
| Journal + resume (per-role state machine, sentinels, third-state refusal) | Task 9 |
| Flip-readiness contract + JSON schema | Task 6 |
| Component 5 — docs + sequencing | Task 12 |
| Error handling / refusals | Tasks 2, 4, 6, 7, 8, 9 (each raises `SpecMigrationRefused`) |
| CLI | Task 10 |

**2. Placeholder scan** — no `TBD`/`TODO`; every code step carries complete code; every test step carries the assertion. The one prose insertion (Task 12) supplies the full section text.

**3. Type consistency** — names are pinned in the "Module public surface" block and reused verbatim: `project_legacy_frontmatter -> (old_id, fm)`; `discover_specs -> Discovery(legacy, singletons, scan_skips)`; `allocate_ids -> Allocation(id_substitutions, dest_rel, new_local_part, aliased, preserved_ids)`; `classify_references(..., id_substitutions, live_spec_ids, source_rels) -> list[RefRecord]`; `_plan_transaction -> Transaction(destinations, ref_report, source_rels, dest_rels)`; `Destination(old_id,new_id,source_rel,dest_rel,number,local_part,rendered_text,preimage_sha256)`; `build_report/migrate/resume -> dict`. The journal entry shape (`role`, `rel`, `preimage_sha256`, `postimage`, and `number`/`local_part` for moved-dest) is written by Task 8 and read by Task 9 identically.

**Notes for the executor:**
- Run everything from `science/`. Never `git add science/uv.lock`.
- The imports in Tasks 3, 5, 7, 8 are *added to the existing top-of-file import block* in `migrate_specs.py` — consolidate them; do not create duplicate `from … import …` lines. Run `uv run ruff check` after each task to catch import/order issues.
- Do not touch `graph/sources.py` or any S3a guard test. Task 11 proves this held.
