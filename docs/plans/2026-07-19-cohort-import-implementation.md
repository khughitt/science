# Cohort Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a cohort mode to `science entities import` that imports 2+ loose documents of one uniform kind as a single previewable, atomically-appliable plan with a contiguous number block and one combined inbound reference rewrite.

**Architecture:** A sibling `CohortImportPlan` (discriminated from the single `ImportPlan` by a `plan_type` field) travels through the same save-plan/apply-plan envelope. Planning reads each source once, assigns a number block, plans each member from the cached bytes with no per-member inbound scan, and runs one combined reference scan that doubles as the cross-member independence guard and the external inbound report. Apply mirrors single `apply_import`'s snapshot + mutated-set self-rollback, cohort-wide, and is exception-atomic (crash-durability is delegated to the downstream caller's journal). Two behavior-preserving primitive changes to shared code support it: a self-cleaning number claim and a content-override on the reference scanner.

**Tech Stack:** Python 3.13, Pydantic v2 (`BaseModel`, `extra="forbid"`), Click, pytest. Package lives under the nested `science/` directory.

## Global Constraints

- **Run everything from the nested `science/` subdir** (there is no root `pyproject.toml`): `cd science && uv run --frozen pytest ...`, `uv run --frozen python -m ...`. The repo root is one level up.
- **Version floor:** this change bumps `0.5.1 → 0.5.2`. Exact strings updated in `science/pyproject.toml`, `.claude-plugin/plugin.json`, `science/tests/test_cli_version.py`, and `science/uv.lock` (re-locked). Only Task 9 touches versions.
- **Single-import contract is preserved** with exactly one deliberate tightening: `--apply-plan` now rejects the preview-only options it previously ignored. The single `ImportPlan` saved bytes and the object-shaped `applied` result are byte-for-byte unchanged.
- **Cohorts are reference-independent:** a member may not link to or bare-path-mention another member (or itself); this is rejected at plan time, never assumed.
- **Standalone cohort apply is exception-atomic, not crash-durable:** caught failures roll back everything already mutated; SIGKILL durability is out of scope (delegated to the downstream journal).
- **No AI-attribution trailers or footers** in any commit message.
- **The design is the source of truth:** `docs/plans/2026-07-19-cohort-import-design.md` (revision v4). Where this plan and the design disagree, stop and ask.

The canonical source signatures this plan builds on (verified against the pinned tree):
- `claim_number_in_dir(project_root, kind, number, local_part, text) -> Path` — `entity_reservation.py:165`.
- `propose_number(project_root, kind) -> int` — `entity_reservation.py:149`.
- `plan_reference_rewrite(project_root, *, id_substitutions, path_substitutions, exclude=frozenset()) -> RewriteReport` — `reference_rewrite.py:371`.
- `_scan(project_root, *, id_substitutions, path_substitutions, exclude=frozenset()) -> RewriteReport` — `reference_rewrite.py:285`.
- `apply_reference_rewrite(project_root, plan, *, exclude=frozenset(), written=None) -> RewriteReport` — `reference_rewrite.py:387`.
- `iter_scannable_files(project_root, *, exclude=frozenset()) -> list[Path]` — `text_scan.py:66`.
- `RewriteReport` fields: `id_substitutions`, `path_substitutions`, `hits: list[RefHit]`, `manual: list[ManualHit]`, `skipped: list[Skip]`, `edits: list[FileEdit]` — `reference_rewrite.py:93`. `RefHit`/`ManualHit` both carry `rel_path`.
- `_validate_plan_for_apply(project_root, plan: ImportPlan) -> Path` — `entity_import.py:487` (per-member reused via a small shared core in Task 6).
- `_snapshot(paths) -> _TreeSnapshot`, `_restore(snapshot, *, restrict=None)`, `audit_moved_references(project_root, moved_rel, *, exclude=frozenset())` — `entity_import.py:301/318/359`.
- CLI import command: `entities_inventory_cli.py:449` (`entities_import_command`). Envelope helpers `read_plan_bytes`, `verify_envelope`, `plan_sha256` — `plan_common.py:167/176/172`.

Test fixtures reused throughout (already in `tests/test_entity_import.py`):
```python
def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    (tmp_path / "entities" / "plans").mkdir(parents=True, exist_ok=True)
    return tmp_path

def _loose(root: Path, rel: str, text: str = "# A Thing\n\nbody\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
```

---

### Task 1: Self-cleaning number claim

**Files:**
- Modify: `science/src/science_tool/entity_reservation.py:191-205` (the `try/finally` inside `claim_number_in_dir`)
- Test: `science/tests/test_entity_reservation.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `claim_number_in_dir(project_root, kind, number, local_part, text) -> Path` — signature unchanged; new guarantee: on any exception **after** the exclusive create of the destination, the partial destination it created is unlinked before re-raising. A `FileExistsError` from the exclusive create itself is untouched (that file predates the call).

- [ ] **Step 1: Write the failing test**

```python
# in tests/test_entity_reservation.py
import builtins
import pytest
from pathlib import Path
from science_tool.entity_reservation import claim_number_in_dir


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    (tmp_path / "entities" / "plans").mkdir(parents=True, exist_ok=True)
    return tmp_path


class _ExplodingHandle:
    """A context-manager handle whose write() raises, but which really created the file."""
    def __init__(self, real):
        self._real = real
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return self._real.__exit__(*exc)
    def write(self, _data):
        raise OSError("simulated disk-full during write")


def test_claim_self_cleans_partial_destination_on_write_failure(tmp_path, monkeypatch):
    root = _project(tmp_path)
    real_open = builtins.open

    def exploding_open(file, mode="r", *args, **kwargs):
        handle = real_open(file, mode, *args, **kwargs)
        if "x" in mode:  # the exclusive destination create — file now exists on disk
            return _ExplodingHandle(handle)
        return handle

    monkeypatch.setattr(builtins, "open", exploding_open)

    with pytest.raises(OSError):
        claim_number_in_dir(root, "plan", 1, "0001-a-thing", "# A Thing\n\nbody\n")

    plans_dir = root / "entities" / "plans"
    assert not (plans_dir / "0001-a-thing.md").exists(), "partial destination survived a failed write"
    assert not list(plans_dir.glob(".*.reserving")), "sentinel leaked"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_entity_reservation.py::test_claim_self_cleans_partial_destination_on_write_failure -v`
Expected: FAIL — the partial `0001-a-thing.md` remains on disk (current code leaves it).

- [ ] **Step 3: Write minimal implementation**

Replace the destination-write block inside `claim_number_in_dir` (currently):
```python
        path = directory / f"{local_part}.md"
        with open(path, "x", encoding="utf-8") as handle:
            handle.write(text)
        return path
```
with:
```python
        path = directory / f"{local_part}.md"
        # Exclusive create first: a FileExistsError here means the file predates us
        # (another writer holds the number) and must propagate untouched.
        handle = open(path, "x", encoding="utf-8")
        try:
            with handle:
                handle.write(text)
        except Exception:
            # We exclusively created this path, so a write/close failure leaves a
            # partial file we own. Remove it before re-raising; the returned path is
            # thereafter always a complete file or the call raised leaving no dest.
            path.unlink(missing_ok=True)
            raise
        return path
```
The enclosing `finally: sentinel.unlink(missing_ok=True)` is unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_entity_reservation.py tests/test_entity_reservation_propose.py -v`
Expected: PASS (new test plus all existing reservation tests — behavior-preserving on the success path).

- [ ] **Step 5: Commit**

```bash
cd science && git add src/science_tool/entity_reservation.py tests/test_entity_reservation.py
git commit -m "feat(reservation): self-clean partial destination on failed claim write"
```

---

### Task 2: Content-override on the reference scanner

**Files:**
- Modify: `science/src/science_tool/reference_rewrite.py` — `_scan` (`:285`) and `plan_reference_rewrite` (`:371`)
- Test: `science/tests/test_reference_rewrite.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `_scan(project_root, *, id_substitutions, path_substitutions, exclude=frozenset(), source_overrides: Mapping[str, str] = {}) -> RewriteReport`
  - `plan_reference_rewrite(project_root, *, id_substitutions, path_substitutions, exclude=frozenset(), source_overrides: Mapping[str, str] = {}) -> RewriteReport`
  - Contract: each `source_overrides` key is a contained project-relative path that becomes an **authoritative virtual scan entry** — examined even if absent/oversize on disk, examined exactly once, deduped against disk enumeration, using the supplied text instead of a disk read. `exclude` still wins (an excluded path is never scanned even with an override). Default empty ⇒ byte-identical current behavior.

- [ ] **Step 1: Write the failing tests**

```python
# in tests/test_reference_rewrite.py
from collections.abc import Mapping  # noqa: F401  (documentation of the new param type)
from pathlib import Path
from science_tool.reference_rewrite import plan_reference_rewrite


def _corpus(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    return tmp_path


def test_override_drives_enumeration_for_absent_source(tmp_path):
    """An override is scanned even when its file no longer exists on disk."""
    root = _corpus(tmp_path)
    # No file at doc/loose.md exists; the override supplies its bytes. Its body
    # links to another loose doc's path, which we are substituting.
    report = plan_reference_rewrite(
        root,
        id_substitutions={"doc/other.md": "plan:0002-other"},
        path_substitutions={"doc/other.md": "entities/plans/0002-other.md"},
        source_overrides={"doc/loose.md": "# L\n\nsee [other](other.md)\n"},
    )
    # The override was examined: its link to other.md is reported (a hit),
    # proving enumeration used the virtual entry, not the (absent) disk file.
    assert any(h.rel_path == "doc/loose.md" for h in report.hits)


def test_override_examined_once_when_also_on_disk(tmp_path):
    """A key present both on disk and as an override is scanned once, from override bytes."""
    root = _corpus(tmp_path)
    (root / "doc").mkdir()
    (root / "doc/loose.md").write_text("# L\n\nno links here\n", encoding="utf-8")
    report = plan_reference_rewrite(
        root,
        id_substitutions={"doc/other.md": "plan:0002-other"},
        path_substitutions={"doc/other.md": "entities/plans/0002-other.md"},
        source_overrides={"doc/loose.md": "# L\n\nsee [other](other.md)\n"},
    )
    hits_for_loose = [h for h in report.hits if h.rel_path == "doc/loose.md"]
    assert len(hits_for_loose) == 1  # examined once, and from the override bytes (which DO link)


def test_exclude_wins_over_override(tmp_path):
    """An excluded path is not scanned even if an override names it."""
    root = _corpus(tmp_path)
    report = plan_reference_rewrite(
        root,
        id_substitutions={"doc/other.md": "plan:0002-other"},
        path_substitutions={"doc/other.md": "entities/plans/0002-other.md"},
        exclude=frozenset({(root / "doc/loose.md").resolve()}),
        source_overrides={"doc/loose.md": "# L\n\nsee [other](other.md)\n"},
    )
    assert not any(h.rel_path == "doc/loose.md" for h in report.hits)


def test_override_examines_oversize_file_the_disk_scan_would_drop(tmp_path):
    """A file too big for the disk size filter is still examined via its override."""
    from science_tool.text_scan import MAX_SCANNABLE_BYTES
    root = _corpus(tmp_path)
    (root / "doc").mkdir()
    # On-disk file exceeds the scan-size limit, so iter_scannable_files drops it.
    big = "# L\n\n" + ("x " * MAX_SCANNABLE_BYTES) + "\nsee [other](other.md)\n"
    (root / "doc/loose.md").write_text(big, encoding="utf-8")
    assert (root / "doc/loose.md").stat().st_size > MAX_SCANNABLE_BYTES
    # The override supplies a small text with the link; enumeration must include it.
    report = plan_reference_rewrite(
        root,
        id_substitutions={"doc/other.md": "plan:0002-other"},
        path_substitutions={"doc/other.md": "entities/plans/0002-other.md"},
        source_overrides={"doc/loose.md": "# L\n\nsee [other](other.md)\n"},
    )
    assert any(h.rel_path == "doc/loose.md" for h in report.hits)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_reference_rewrite.py -k "override or exclude" -v` (the four new tests; the bare `override_or_exclude` token matches no test name and would deselect everything)
Expected: FAIL — `plan_reference_rewrite() got an unexpected keyword argument 'source_overrides'`.

- [ ] **Step 3: Write minimal implementation**

In `reference_rewrite.py`, add `Mapping` to the typing import at the top:
```python
from collections.abc import Callable, Mapping
```
Change `_scan`'s signature and its enumeration head. Replace:
```python
def _scan(
    project_root: Path,
    *,
    id_substitutions: dict[str, str],
    path_substitutions: dict[str, str],
    exclude: frozenset[Path] = frozenset(),
) -> RewriteReport:
```
with:
```python
def _scan(
    project_root: Path,
    *,
    id_substitutions: dict[str, str],
    path_substitutions: dict[str, str],
    exclude: frozenset[Path] = frozenset(),
    source_overrides: Mapping[str, str] = {},
) -> RewriteReport:
```
Then replace the enumeration loop head. Replace:
```python
    project_root = Path(project_root).resolve()
    report = RewriteReport(
        id_substitutions=dict(id_substitutions),
        path_substitutions=dict(path_substitutions),
    )

    for path in iter_scannable_files(project_root, exclude=exclude):
        rel_path = path.relative_to(project_root).as_posix()
        text, skip = read_text_or_skip(path, rel_path)  # the ONLY read of this file
```
with:
```python
    project_root = Path(project_root).resolve()
    report = RewriteReport(
        id_substitutions=dict(id_substitutions),
        path_substitutions=dict(path_substitutions),
    )

    excluded = {p.resolve() for p in exclude}
    # Disk enumeration, then override virtual entries unioned in. Overrides are
    # authoritative: included even if absent/oversize on disk, deduped against the
    # disk set, and always sourced from the supplied bytes. exclude still wins.
    entries: dict[Path, str] = {
        path: path.relative_to(project_root).as_posix()
        for path in iter_scannable_files(project_root, exclude=exclude)
    }
    override_texts: dict[str, str] = {}
    for rel, text in source_overrides.items():
        pure = PurePosixPath(rel)
        if pure.is_absolute() or rel.startswith("/") or ".." in pure.parts:
            raise ValueError(f"source_overrides key {rel!r} is not a project-relative path")
        resolved = (project_root / rel).resolve()
        if not resolved.is_relative_to(project_root):
            raise ValueError(f"source_overrides key {rel!r} escapes the project root")
        if resolved in excluded:
            continue  # exclude wins over an override
        entries[resolved] = rel
        override_texts[rel] = text

    for path in sorted(entries):
        rel_path = entries[path]
        if rel_path in override_texts:
            text, skip = override_texts[rel_path], None
        else:
            text, skip = read_text_or_skip(path, rel_path)  # the ONLY read of this file
```
Update `plan_reference_rewrite` to accept and forward the parameter. Replace:
```python
def plan_reference_rewrite(
    project_root: Path,
    *,
    id_substitutions: dict[str, str],
    path_substitutions: dict[str, str],
    exclude: frozenset[Path] = frozenset(),
) -> RewriteReport:
    """Report every reference a rewrite would change. Touches nothing."""
    return _scan(
        project_root,
        id_substitutions=id_substitutions,
        path_substitutions=path_substitutions,
        exclude=exclude,
    )
```
with:
```python
def plan_reference_rewrite(
    project_root: Path,
    *,
    id_substitutions: dict[str, str],
    path_substitutions: dict[str, str],
    exclude: frozenset[Path] = frozenset(),
    source_overrides: Mapping[str, str] = {},
) -> RewriteReport:
    """Report every reference a rewrite would change. Touches nothing.

    `source_overrides` (rel_path -> already-read text) makes a caller's cached bytes
    authoritative virtual scan entries: examined even if absent/oversize on disk,
    deduped against disk enumeration, sourced from the supplied bytes. `exclude`
    still wins. Default empty -> disk-only behavior.
    """
    return _scan(
        project_root,
        id_substitutions=id_substitutions,
        path_substitutions=path_substitutions,
        exclude=exclude,
        source_overrides=source_overrides,
    )
```
`PurePosixPath` is already imported in this module (`from pathlib import Path, PurePosixPath`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_reference_rewrite.py tests/test_text_scan.py tests/test_references.py -v`
Expected: PASS (new tests plus all existing rewrite/scan tests — default-empty override is behavior-preserving).

- [ ] **Step 5: Commit**

```bash
cd science && git add src/science_tool/reference_rewrite.py tests/test_reference_rewrite.py
git commit -m "feat(reference-rewrite): source_overrides as authoritative virtual scan entries"
```

---

### Task 3: Extract `_plan_member` and `PlannedMember`; refactor `plan_import`

**Files:**
- Modify: `science/src/science_tool/entity_import.py` (add `PlannedMember`, `_plan_member`, `ImportMember`; refactor `plan_import`)
- Test: `science/tests/test_entity_import.py`

**Interfaces:**
- Consumes: `plan_reference_rewrite(..., source_overrides=...)` (Task 2).
- Produces:
  - `class ImportMember(BaseModel)` with `model_config = ConfigDict(extra="forbid")` and fields `source_rel: str`, `source_sha256: str`, `entity_id: str`, `number: int`, `dest_rel: str`, `title: str`, `status: str`, `frontmatter: dict[str, Any]`, `rendered_text: str` (no `kind`, no warnings).
  - `@dataclass(frozen=True) class PlannedMember` with `member: ImportMember`, `warnings: list[str]`.
  - `_plan_member(project_root: Path, source_rel: str, text: str, *, kind: str, number: int, status: str | None = None, title: str | None = None, slug: str | None = None, today: date | None = None) -> PlannedMember` — from already-read bytes: loose check, identity, own outbound-link rebase into `rendered_text`, prospective-write validation. No inbound scan; no second read.
  - `plan_import(...)` unchanged public signature and unchanged `ImportPlan` output bytes.

- [ ] **Step 1: Write the failing test**

```python
# in tests/test_entity_import.py
from science_tool.entity_import import _plan_member, PlannedMember


def test_plan_member_from_cached_bytes(tmp_path):
    root = _project(tmp_path)
    text = "# A Thing\n\nbody\n"
    planned = _plan_member(root, "doc/plans/x.md", text, kind="plan", number=7)
    assert isinstance(planned, PlannedMember)
    m = planned.member
    assert m.entity_id == "plan:0007-a-thing"
    assert m.number == 7
    assert m.dest_rel == "entities/plans/0007-a-thing.md"
    assert m.source_rel == "doc/plans/x.md"
    assert "id: plan:0007-a-thing" in m.rendered_text
    # No 'kind' field on the member model.
    assert "kind" not in ImportMember.model_fields  # noqa: F821 (imported below)


def test_plan_member_honors_title_and_slug(tmp_path):
    root = _project(tmp_path)
    planned = _plan_member(root, "doc/plans/x.md", "# Ignored\n\nbody\n",
                           kind="plan", number=1, title="Custom Title", slug="custom-slug")
    assert planned.member.title == "Custom Title"
    assert planned.member.entity_id == "plan:0001-custom-slug"


def test_plan_member_rejects_document_with_frontmatter(tmp_path):
    root = _project(tmp_path)
    with pytest.raises(EntityImportError):
        _plan_member(root, "doc/plans/x.md", "---\nid: x\n---\n# T\n", kind="plan", number=1)
```
Add `from science_tool.entity_import import ImportMember` to the test imports.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_entity_import.py -k plan_member -v`
Expected: FAIL — `cannot import name '_plan_member'`.

- [ ] **Step 3: Write minimal implementation**

Add imports at the top of `entity_import.py` if missing: `from pydantic import BaseModel, ConfigDict` (currently only `BaseModel` is imported — add `ConfigDict`).

Add the models and helper (place `ImportMember`/`PlannedMember` just after `ImportPlan`, and `_plan_member` just before `plan_import`):
```python
class ImportMember(BaseModel):
    """One member of a cohort. Carries no `kind`: the cohort plan's `kind` is the
    single authority for every member's directory and number claim."""

    model_config = ConfigDict(extra="forbid")

    source_rel: str
    source_sha256: str
    entity_id: str
    number: int
    dest_rel: str
    title: str
    status: str
    frontmatter: dict[str, Any]
    rendered_text: str


@dataclass(frozen=True)
class PlannedMember:
    """Internal, not persisted: a member plus the warnings its render raised."""

    member: ImportMember
    warnings: list[str]


def _plan_member(
    project_root: Path,
    source_rel: str,
    text: str,
    *,
    kind: str,
    number: int,
    status: str | None = None,
    title: str | None = None,
    slug: str | None = None,
    today: date | None = None,
) -> PlannedMember:
    """Plan one member from ALREADY-READ source bytes with a FORCED number.

    Does the loose check, identity resolution, own-outbound-link rebase, render,
    and prospective-write validation. Runs NO inbound scan and does NOT re-read the
    source. Both single import and cohort import build their members through here.
    """
    project_root = Path(project_root).resolve()
    source_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    try:
        frontmatter, body = split_frontmatter(text)
    except yaml.YAMLError as exc:
        raise EntityImportError(f"{source_rel} has a malformed frontmatter block: {exc}") from exc
    if frontmatter:
        raise EntityImportError(
            f"{source_rel} already has frontmatter; import is for loose documents. "
            "An entity that already carries an id needs a move, not an import."
        )

    resolved_title = title if title is not None else _derive_title(text, Path(source_rel))

    try:
        resolved_status = status if status is not None else default_status(kind, project_root=project_root)
        allowed = valid_statuses(kind, project_root=project_root)
        if allowed is not None and resolved_status not in allowed:
            raise EntityImportError(
                f"status {resolved_status!r} is not in the {kind} vocabulary {sorted(allowed)}"
            )
        slug_value = validate_slug(slug) if slug is not None else derive_slug(resolved_title)
        policy = resolve_path_policy(kind)
    except KeyError as exc:
        raise EntityImportError(f"unknown entity kind: {kind}") from exc
    except EntityCommandError as exc:
        raise EntityImportError(str(exc)) from exc

    local_part = f"{number:0{LOCAL_PART_WIDTH}d}-{slug_value}"
    entity_id = f"{kind}:{local_part}"
    dest = project_root / policy.root / f"{local_part}.md"
    dest_rel = dest.relative_to(project_root).as_posix()

    body_rebased, _outbound_hits = rewrite_outbound_links(
        body, PurePosixPath(source_rel).parent, PurePosixPath(dest_rel).parent
    )
    stamp = (today or date.today()).isoformat()
    new_frontmatter: dict[str, Any] = {
        "kind": kind,
        "title": resolved_title,
        "status": resolved_status,
        "created": stamp,
        "updated": stamp,
        "id": entity_id,
    }
    rendered_text = _render_markdown(new_frontmatter, body_rebased)
    warnings, _sources = _validate_prospective_write(
        project_root=project_root,
        rel_path=Path(dest_rel),
        text=rendered_text,
        target_entity_id=entity_id,
    )
    return PlannedMember(
        member=ImportMember(
            source_rel=source_rel,
            source_sha256=source_sha256,
            entity_id=entity_id,
            number=number,
            dest_rel=dest_rel,
            title=resolved_title,
            status=resolved_status,
            frontmatter=new_frontmatter,
            rendered_text=rendered_text,
        ),
        warnings=list(warnings),
    )
```
Note `_derive_title` currently takes `(text, source: Path)` and uses `source` only in its error message; passing `Path(source_rel)` keeps the message sensible.

Now refactor `plan_import` to delegate. Replace its body from the source read through the `return ImportPlan(...)` with:
```python
    project_root = Path(project_root).resolve()
    source = Path(source).resolve()
    if not source.is_file():
        raise EntityImportError(f"source not found: {source}")
    try:
        text = source.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise EntityImportError(f"{source} is not valid UTF-8: {exc}") from exc

    source_rel = source.relative_to(project_root).as_posix()
    # propose_number resolves the path policy and can raise a bare KeyError (kind
    # unknown to both the built-in table and the local manifest) or EntityCommandError
    # (non-numeric kind); translate both, as the pre-refactor plan_import did, so the
    # bad-kind regression test still sees EntityImportError.
    try:
        number = propose_number(project_root, kind)
    except KeyError as exc:
        raise EntityImportError(f"unknown entity kind: {kind}") from exc
    except EntityCommandError as exc:
        raise EntityImportError(str(exc)) from exc
    planned = _plan_member(
        project_root, source_rel, text,
        kind=kind, number=number, status=status, title=title, slug=slug, today=today,
    )
    member = planned.member

    # Single-import inbound scan: exclude the moved source (its own links are
    # rebased above; scanning it as a referrer would drift against its own plan).
    # It stays in `exclude`, so it passes NO override for itself.
    ref_report = plan_reference_rewrite(
        project_root,
        id_substitutions={source_rel: member.entity_id},
        path_substitutions={source_rel: member.dest_rel},
        exclude=exclude | frozenset({source}),
    )

    return ImportPlan(
        project_root=str(project_root),
        source_rel=member.source_rel,
        source_sha256=member.source_sha256,
        entity_id=member.entity_id,
        kind=kind,
        number=member.number,
        dest_rel=member.dest_rel,
        title=member.title,
        status=member.status,
        frontmatter=member.frontmatter,
        rendered_text=member.rendered_text,
        ref_report=ref_report,
        warnings=planned.warnings,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_entity_import.py tests/test_entity_import_cli.py -v`
Expected: PASS (new `_plan_member` tests plus the entire existing single-import suite — the refactor is behavior-preserving; `ImportPlan` output is unchanged).

- [ ] **Step 5: Commit**

```bash
cd science && git add src/science_tool/entity_import.py tests/test_entity_import.py
git commit -m "refactor(import): extract _plan_member/ImportMember; plan_import delegates"
```

---

### Task 4: Cohort plan model, error type, and parser

**Files:**
- Modify: `science/src/science_tool/entity_import.py` (add `AttributedWarning`, `CohortImportPlan`, `RefDependentCohortError`, `parse_cohort_import_plan`)
- Test: `science/tests/test_cohort_import.py` (new file)

**Interfaces:**
- Consumes: `ImportMember`, `RewriteReport`.
- Produces:
  - `class AttributedWarning(BaseModel)` — `extra="forbid"`, fields `source_rel: str`, `message: str`.
  - `class CohortImportPlan(BaseModel)` — `extra="forbid"`, fields `plan_type: Literal["cohort-import"] = "cohort-import"`, `schema_version: int = 1`, `project_root: str`, `kind: str`, `members: list[ImportMember]`, `ref_report: RewriteReport = RewriteReport()`, `warnings: list[AttributedWarning] = []`.
  - `class RefDependentCohortError(EntityImportError)`.
  - `parse_cohort_import_plan(raw: bytes) -> CohortImportPlan`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cohort_import.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from science_tool.entity_import import (
    AttributedWarning,
    CohortImportPlan,
    EntityImportError,
    ImportMember,
    RefDependentCohortError,
    parse_cohort_import_plan,
)


def _member(n: int) -> ImportMember:
    return ImportMember(
        source_rel=f"doc/plans/x{n}.md", source_sha256="0" * 64,
        entity_id=f"plan:{n:04d}-x{n}", number=n,
        dest_rel=f"entities/plans/{n:04d}-x{n}.md", title=f"X{n}", status="proposed",
        frontmatter={"id": f"plan:{n:04d}-x{n}", "kind": "plan"}, rendered_text="body",
    )


def test_cohort_plan_defaults_and_discriminator():
    plan = CohortImportPlan(project_root="/r", kind="plan", members=[_member(1), _member(2)])
    assert plan.plan_type == "cohort-import"
    assert plan.schema_version == 1


def test_cohort_plan_forbids_extra_fields():
    with pytest.raises(Exception):
        CohortImportPlan(project_root="/r", kind="plan", members=[_member(1), _member(2)], bogus=1)


def test_member_forbids_extra_fields():
    with pytest.raises(Exception):
        ImportMember(source_rel="s", source_sha256="0" * 64, entity_id="plan:0001-x",
                     number=1, dest_rel="d", title="t", status="proposed",
                     frontmatter={}, rendered_text="b", kind="plan")


def test_parse_cohort_round_trips():
    plan = CohortImportPlan(project_root="/r", kind="plan",
                            members=[_member(1), _member(2)],
                            warnings=[AttributedWarning(source_rel="doc/plans/x1.md", message="w")])
    raw = plan.model_dump_json().encode("utf-8")
    assert parse_cohort_import_plan(raw) == plan


def test_parse_cohort_rejects_garbage():
    with pytest.raises(EntityImportError):
        parse_cohort_import_plan(b'{"not": "a plan"}')


def test_ref_dependent_error_is_import_error():
    assert issubclass(RefDependentCohortError, EntityImportError)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_cohort_import.py -v`
Expected: FAIL — `cannot import name 'CohortImportPlan'`.

- [ ] **Step 3: Write minimal implementation**

Add `Literal` to typing imports: `from typing import Any, Literal`. Add after `ImportMember`/`PlannedMember`:
```python
class AttributedWarning(BaseModel):
    """A cohort warning tagged with the source that raised it."""

    model_config = ConfigDict(extra="forbid")

    source_rel: str
    message: str


class CohortImportPlan(BaseModel):
    """What a cohort import would do. Sibling to ImportPlan, discriminated by
    `plan_type`. One `kind` authority for every member; one combined inbound
    `ref_report` over external referrers only."""

    model_config = ConfigDict(extra="forbid")

    plan_type: Literal["cohort-import"] = "cohort-import"
    schema_version: int = 1
    project_root: str
    kind: str
    members: list[ImportMember]
    ref_report: RewriteReport = RewriteReport()
    warnings: list[AttributedWarning] = []


class RefDependentCohortError(EntityImportError):
    """A cohort member references another member (or itself); import them separately."""


def parse_cohort_import_plan(raw: bytes) -> CohortImportPlan:
    """Parse cohort plan bytes the caller already read for the approval envelope.

    Proves the bytes are well-TYPED only; path/identity safety is untrusted until
    apply validates it. Mirrors `parse_import_plan`.
    """
    try:
        return CohortImportPlan.model_validate_json(raw)
    except PydanticValidationError as exc:
        raise EntityImportError(f"plan bytes are not a readable cohort import plan: {exc}") from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_cohort_import.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd science && git add src/science_tool/entity_import.py tests/test_cohort_import.py
git commit -m "feat(import): CohortImportPlan model, RefDependentCohortError, parser"
```

---

### Task 5: `plan_cohort_import`

**Files:**
- Modify: `science/src/science_tool/entity_import.py` (add `plan_cohort_import`)
- Test: `science/tests/test_cohort_import.py`

**Interfaces:**
- Consumes: `_plan_member` (Task 3), `plan_reference_rewrite(..., source_overrides=...)` (Task 2), `propose_number`, `CohortImportPlan`, `AttributedWarning`, `RefDependentCohortError`.
- Produces: `plan_cohort_import(project_root: Path, sources: Sequence[Path], *, kind: str, status: str | None = None, exclude: frozenset[Path] = frozenset(), today: date | None = None) -> CohortImportPlan`.

- [ ] **Step 1: Write the failing tests**

```python
# in tests/test_cohort_import.py
from science_tool.entity_import import plan_cohort_import


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    (tmp_path / "entities" / "plans").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _loose(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_cohort_assigns_contiguous_number_block(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    c = _loose(root, "doc/plans/c.md", "# Gamma\n\nbody\n")
    plan = plan_cohort_import(root, [a, b, c], kind="plan")
    assert [m.number for m in plan.members] == [1, 2, 3]
    assert [m.entity_id for m in plan.members] == [
        "plan:0001-alpha", "plan:0002-beta", "plan:0003-gamma",
    ]
    # members stay in input order
    assert [m.source_rel for m in plan.members] == [
        "doc/plans/a.md", "doc/plans/b.md", "doc/plans/c.md",
    ]


def test_cohort_one_combined_inbound_rewrite(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    # One external referrer links BOTH members; both must be repointed in one pass.
    _loose(root, "doc/notes.md",
           "see [a](plans/a.md) and [b](plans/b.md)\n")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    edited = [e.rel_path for e in plan.ref_report.edits]
    assert "doc/notes.md" in edited
    news = {h.new for h in plan.ref_report.hits if h.rel_path == "doc/notes.md"}
    assert any("0001-alpha" in n for n in news)
    assert any("0002-beta" in n for n in news)


def test_cohort_rejects_member_linking_member(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nsee [b](b.md)\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    with pytest.raises(RefDependentCohortError) as excinfo:
        plan_cohort_import(root, [a, b], kind="plan")
    # The error names the offending source -> target PAIR (design v4).
    msg = str(excinfo.value)
    assert "doc/plans/a.md" in msg and "doc/plans/b.md" in msg


def test_cohort_rejects_bare_path_mention_of_member(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nmentions doc/plans/b.md inline\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    with pytest.raises(RefDependentCohortError) as excinfo:
        plan_cohort_import(root, [a, b], kind="plan")
    assert "doc/plans/a.md" in str(excinfo.value) and "doc/plans/b.md" in str(excinfo.value)


def test_cohort_rejects_self_link(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nsee [me](a.md)\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    with pytest.raises(RefDependentCohortError) as excinfo:
        plan_cohort_import(root, [a, b], kind="plan")
    # A self-reference maps the offending source to itself.
    assert "doc/plans/a.md -> doc/plans/a.md" in str(excinfo.value)


def test_cohort_pair_attribution_disambiguates_shared_basenames(tmp_path):
    """Two members sharing a basename must report the EXACT target, not the first
    basename match."""
    root = _project(tmp_path)
    # doc/a/x.md links the OTHER member (draft/x.md), which shares its basename.
    a = _loose(root, "doc/a/x.md", "# A\n\nsee [t](../../draft/x.md)\n")
    b = _loose(root, "draft/x.md", "# B\n\nbody\n")
    with pytest.raises(RefDependentCohortError) as excinfo:
        plan_cohort_import(root, [a, b], kind="plan")
    msg = str(excinfo.value)
    assert "doc/a/x.md -> draft/x.md" in msg  # resolved to the real target
    assert "doc/a/x.md -> doc/a/x.md" not in msg  # not misattributed to itself


def test_cohort_runs_one_combined_scan_with_cached_overrides(tmp_path, monkeypatch):
    """The planner reads each source once and feeds those exact bytes to ONE scan
    via source_overrides — no per-member scan, no second read of any source."""
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    import science_tool.entity_import as ei
    calls: list[dict] = []
    real = ei.plan_reference_rewrite

    def spy(project_root, **kwargs):
        calls.append(kwargs)
        return real(project_root, **kwargs)

    monkeypatch.setattr(ei, "plan_reference_rewrite", spy)
    plan_cohort_import(root, [a, b], kind="plan")
    assert len(calls) == 1  # ONE combined scan, not one per member
    overrides = calls[0]["source_overrides"]
    assert set(overrides) == {"doc/plans/a.md", "doc/plans/b.md"}
    assert overrides["doc/plans/a.md"] == "# Alpha\n\nbody\n"  # the cached bytes


def test_cohort_preserves_external_manual_finding(tmp_path):
    """An auto-unrewritable reference in an EXTERNAL file (a bare prose path
    mention of a member) is surfaced in ref_report.manual, not a rejection."""
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    _loose(root, "doc/notes.md", "the file doc/plans/a.md is worth reading\n")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    assert any(m.rel_path == "doc/notes.md" for m in plan.ref_report.manual)


def test_cohort_requires_two_sources(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    with pytest.raises(EntityImportError):
        plan_cohort_import(root, [a], kind="plan")


def test_cohort_rejects_duplicate_sources(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    with pytest.raises(EntityImportError):
        plan_cohort_import(root, [a, a], kind="plan")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_cohort_import.py -k cohort -v`
Expected: FAIL — `cannot import name 'plan_cohort_import'`.

- [ ] **Step 3: Write minimal implementation**

Add `Sequence` to imports: `from collections.abc import Iterator, Sequence`. Also add
`RefHit` and `ManualHit` to the existing `from science_tool.reference_rewrite import (...)`
block (the pair-attribution helpers annotate them). Add:
```python
def plan_cohort_import(
    project_root: Path,
    sources: Sequence[Path],
    *,
    kind: str,
    status: str | None = None,
    exclude: frozenset[Path] = frozenset(),
    today: date | None = None,
) -> CohortImportPlan:
    """Plan a cohort import of 2+ loose documents of ONE uniform kind. Touches nothing.

    Reads each source exactly once; assigns a contiguous number block; plans each
    member from the cached bytes with no per-member inbound scan; runs ONE combined
    reference scan that is both the cross-member independence guard and the external
    inbound report.
    """
    project_root = Path(project_root).resolve()
    if len(sources) < 2:
        raise EntityImportError("a cohort import needs at least 2 sources")

    resolved = [Path(s).resolve() for s in sources]
    if len(set(resolved)) != len(resolved):
        raise EntityImportError("cohort sources contain a duplicate")

    # Read each source once into the cache both the planner and the scan consume.
    cache: dict[str, str] = {}
    order: list[str] = []
    for src in resolved:
        if not src.is_file():
            raise EntityImportError(f"source not found: {src}")
        try:
            text = src.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise EntityImportError(f"{src} is not valid UTF-8: {exc}") from exc
        rel = src.relative_to(project_root).as_posix()
        cache[rel] = text
        order.append(rel)

    try:
        base = propose_number(project_root, kind)
    except KeyError as exc:
        raise EntityImportError(f"unknown entity kind: {kind}") from exc
    except EntityCommandError as exc:
        raise EntityImportError(str(exc)) from exc
    planned: list[PlannedMember] = []
    for i, rel in enumerate(order):
        planned.append(
            _plan_member(project_root, rel, cache[rel],
                         kind=kind, number=base + i, status=status,
                         title=None, slug=None, today=today)
        )
    members = [p.member for p in planned]
    member_rels = set(order)

    # ONE scan: independence guard + external inbound report. Members are NOT
    # excluded (so a member linking another member is visible); only the eventual
    # saved-plan artifact is excluded (passed in via `exclude`). Cached bytes drive
    # enumeration so no source is read twice.
    report = plan_reference_rewrite(
        project_root,
        id_substitutions={m.source_rel: m.entity_id for m in members},
        path_substitutions={m.source_rel: m.dest_rel for m in members},
        exclude=exclude,
        source_overrides=cache,
    )
    # Name the offending (source -> target) PAIRS by EXACT source path, per design
    # v4. Cross-member references in loose documents are PATH-based (a member is not
    # yet an entity, so it has no id to cite). Resolve each finding to a member
    # source_rel exactly — basename matching is ambiguous when two members share a
    # filename (doc/a/x.md vs draft/x.md). For a link hit, `RefHit.old` is a link
    # target resolved against the referrer's directory; for a frontmatter hit it is
    # the repo-relative substitution key itself. A manual hit's text may name more
    # than one member; report every target present.
    member_sources = set(member_rels)

    def _hit_target(h: RefHit) -> str | None:
        head, _tail = _split_target(h.old)
        if head in member_sources:  # frontmatter path ref: the key is the source_rel
            return head
        resolved = _resolve_link(head, PurePosixPath(h.rel_path).parent) if head else None
        return resolved if resolved in member_sources else None

    def _manual_targets(man: ManualHit) -> list[str]:
        return sorted(rel for rel in member_sources if rel in man.text)

    pairs: list[tuple[str, str]] = []
    for h in report.hits:
        if h.rel_path in member_rels:
            target = _hit_target(h)
            pairs.append((h.rel_path, target if target is not None else h.old))
    for man in report.manual:
        if man.rel_path in member_rels:
            targets = _manual_targets(man) or [man.text.strip()]
            pairs.extend((man.rel_path, t) for t in targets)
    if pairs:
        rendered = ", ".join(f"{src} -> {tgt}" for src, tgt in sorted(set(pairs)))
        raise RefDependentCohortError(
            "cohort members reference each other or themselves; import them in "
            f"separate batches. Offending source -> target pairs: {rendered}"
        )

    warnings = sorted(
        (AttributedWarning(source_rel=p.member.source_rel, message=w)
         for p in planned for w in p.warnings),
        key=lambda a: (a.source_rel, a.message),
    )
    return CohortImportPlan(
        project_root=str(project_root),
        kind=kind,
        members=members,
        ref_report=report,
        warnings=warnings,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_cohort_import.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd science && git add src/science_tool/entity_import.py tests/test_cohort_import.py
git commit -m "feat(import): plan_cohort_import with independence guard and combined report"
```

---

### Task 6: Cohort apply-time shape validation

**Files:**
- Modify: `science/src/science_tool/entity_import.py` (add `_validate_cohort_plan_for_apply`; extract a per-member core from `_validate_plan_for_apply`)
- Test: `science/tests/test_cohort_import.py`

**Interfaces:**
- Consumes: `CohortImportPlan`, existing `_validate_plan_for_apply` logic.
- Produces: `_validate_cohort_plan_for_apply(project_root: Path, plan: CohortImportPlan) -> list[Path]` — returns the validated resolved source paths in member order; raises `EntityImportError` on any structural defect (non-contiguous numbers, duplicate ids/sources/dests, source∩dest overlap, per-member containment / canonical-destination / identity-coherence failure, using `plan.kind` for every member).

- [ ] **Step 1: Write the failing tests**

```python
# in tests/test_cohort_import.py
from science_tool.entity_import import _validate_cohort_plan_for_apply


def _valid_plan(root: Path) -> CohortImportPlan:
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    return plan_cohort_import(root, [a, b], kind="plan")


def test_validate_accepts_a_fresh_plan(tmp_path):
    root = _project(tmp_path)
    plan = _valid_plan(root)
    sources = _validate_cohort_plan_for_apply(root, plan)
    assert [s.name for s in sources] == ["a.md", "b.md"]


def test_validate_rejects_non_contiguous_numbers(tmp_path):
    root = _project(tmp_path)
    plan = _valid_plan(root)
    plan.members[1].number = 9  # break contiguity
    with pytest.raises(EntityImportError):
        _validate_cohort_plan_for_apply(root, plan)


def test_validate_rejects_duplicate_entity_ids(tmp_path):
    root = _project(tmp_path)
    plan = _valid_plan(root)
    plan.members[1].entity_id = plan.members[0].entity_id
    with pytest.raises(EntityImportError):
        _validate_cohort_plan_for_apply(root, plan)


def test_validate_rejects_source_dest_overlap(tmp_path):
    root = _project(tmp_path)
    plan = _valid_plan(root)
    plan.members[0].dest_rel = plan.members[1].source_rel  # a dest that is another source
    with pytest.raises(EntityImportError):
        _validate_cohort_plan_for_apply(root, plan)


def test_validate_rejects_tampered_destination(tmp_path):
    root = _project(tmp_path)
    plan = _valid_plan(root)
    plan.members[0].dest_rel = "entities/plans/9999-evil.md"  # not canonical for its id
    with pytest.raises(EntityImportError):
        _validate_cohort_plan_for_apply(root, plan)


def test_validate_translates_unknown_kind(tmp_path):
    """resolve_path_policy's bare KeyError must surface as EntityImportError.

    The entity_id prefix is set to the bad kind too, so the id-vs-kind check passes
    and execution actually reaches resolve_path_policy (the code path under test).
    """
    root = _project(tmp_path)
    plan = _valid_plan(root)
    plan.kind = "notarealkind"
    for i, m in enumerate(plan.members, start=1):
        m.entity_id = f"notarealkind:{i:04d}-x"
    with pytest.raises(EntityImportError):
        _validate_cohort_plan_for_apply(root, plan)


def test_validate_rejects_rendered_kind_tamper(tmp_path):
    """A rendered_text whose frontmatter kind disagrees with plan.kind is refused,
    even when its id is correct."""
    root = _project(tmp_path)
    plan = _valid_plan(root)
    m = plan.members[0]
    # Keep the id line, corrupt only the kind line in the rendered frontmatter.
    m.rendered_text = m.rendered_text.replace("kind: plan", "kind: question")
    with pytest.raises(EntityImportError):
        _validate_cohort_plan_for_apply(root, plan)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_cohort_import.py -k validate -v`
Expected: FAIL — `cannot import name '_validate_cohort_plan_for_apply'`.

- [ ] **Step 3: Write minimal implementation**

Refactor `_validate_plan_for_apply` to expose a reusable per-member core. Add this helper (it factors out the containment + identity + canonical-destination + prospective-write checks, parameterized by the fields rather than an `ImportPlan`), placed above `_validate_plan_for_apply`:
```python
def _validate_member_identity(
    project_root: Path, *, kind: str, source_rel: str, dest_rel: str,
    entity_id: str, number: int, frontmatter: dict[str, Any], rendered_text: str,
) -> Path:
    """Containment, canonical destination, and identity coherence for one moved
    document. Returns the validated resolved source path. Shared by single and
    cohort apply so both enforce identical safety."""
    def _contained(rel: str, label: str) -> Path:
        pure = PurePosixPath(rel)
        if pure.is_absolute() or rel.startswith("/") or ".." in pure.parts:
            raise EntityImportError(f"plan {label} {rel!r} is not a project-relative path")
        resolved = (project_root / rel).resolve()
        if not resolved.is_relative_to(project_root):
            raise EntityImportError(f"plan {label} {rel!r} escapes the project root")
        return resolved

    source = _contained(source_rel, "source")
    _contained(dest_rel, "destination")
    if not source_rel.endswith(".md"):
        raise EntityImportError(f"plan source {source_rel!r} is not a markdown file")

    id_kind, sep, local_part = entity_id.partition(":")
    if not sep or id_kind != kind:
        raise EntityImportError(f"plan entity_id {entity_id!r} disagrees with kind {kind!r}")
    match = re.match(rf"(\d{{{LOCAL_PART_WIDTH}}})-", local_part)
    if match is None or int(match.group(1)) != number:
        raise EntityImportError(f"plan entity_id {entity_id!r} does not carry number {number}")
    # resolve_path_policy raises a bare KeyError (unknown kind) / EntityCommandError
    # (non-numeric kind); translate both so this function only ever raises
    # EntityImportError, matching its contract and the pre-refactor behavior.
    try:
        policy_root = resolve_path_policy(kind).root
    except KeyError as exc:
        raise EntityImportError(f"unknown entity kind: {kind}") from exc
    except EntityCommandError as exc:
        raise EntityImportError(str(exc)) from exc
    expected_dest = f"{policy_root}/{local_part}.md"
    if dest_rel != expected_dest:
        raise EntityImportError(
            f"plan destination {dest_rel!r} is not canonical for {entity_id!r} (expected {expected_dest!r})"
        )
    if frontmatter.get("id") != entity_id or frontmatter.get("kind") != kind:
        raise EntityImportError("plan frontmatter id/kind disagree with the entity_id")
    # Validate BOTH id and kind of the rendered frontmatter: apply writes rendered_text
    # verbatim, so a plan whose rendered kind disagrees with plan.kind would land an
    # entity in the wrong-kind body under a right-kind path.
    rendered_fm, _body = split_frontmatter(rendered_text)
    if rendered_fm.get("id") != entity_id or rendered_fm.get("kind") != kind:
        raise EntityImportError("plan rendered_text frontmatter id/kind disagree with the entity_id")
    _validate_prospective_write(
        project_root=project_root, rel_path=Path(dest_rel),
        text=rendered_text, target_entity_id=entity_id,
    )
    return source
```
Rewrite `_validate_plan_for_apply` to call it (behavior-preserving):
```python
def _validate_plan_for_apply(project_root: Path, plan: ImportPlan) -> Path:
    return _validate_member_identity(
        project_root, kind=plan.kind, source_rel=plan.source_rel, dest_rel=plan.dest_rel,
        entity_id=plan.entity_id, number=plan.number, frontmatter=plan.frontmatter,
        rendered_text=plan.rendered_text,
    )
```
Add the cohort validator:
```python
def _validate_cohort_plan_for_apply(project_root: Path, plan: CohortImportPlan) -> list[Path]:
    """Reject a persisted cohort plan that is not a safe, self-consistent block,
    BEFORE any mutation. Returns validated resolved source paths in member order."""
    if len(plan.members) < 2:
        raise EntityImportError("cohort plan has fewer than 2 members")

    numbers = [m.number for m in plan.members]
    if numbers != list(range(numbers[0], numbers[0] + len(numbers))):
        raise EntityImportError(f"cohort numbers are not contiguous and ordered: {numbers}")

    for field in ("entity_id", "source_rel", "dest_rel"):
        values = [getattr(m, field) for m in plan.members]
        if len(set(values)) != len(values):
            raise EntityImportError(f"cohort members share a {field}")

    sources = {m.source_rel for m in plan.members}
    dests = {m.dest_rel for m in plan.members}
    if sources & dests:
        raise EntityImportError(f"cohort source and destination sets overlap: {sorted(sources & dests)}")

    return [
        _validate_member_identity(
            project_root, kind=plan.kind, source_rel=m.source_rel, dest_rel=m.dest_rel,
            entity_id=m.entity_id, number=m.number, frontmatter=m.frontmatter,
            rendered_text=m.rendered_text,
        )
        for m in plan.members
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_cohort_import.py tests/test_entity_import.py -v`
Expected: PASS (cohort validation tests plus the existing single-import apply tests, since `_validate_plan_for_apply` is behavior-preserving).

- [ ] **Step 5: Commit**

```bash
cd science && git add src/science_tool/entity_import.py tests/test_cohort_import.py
git commit -m "feat(import): _validate_cohort_plan_for_apply via shared member-identity core"
```

---

### Task 7: `apply_cohort_import`

**Files:**
- Modify: `science/src/science_tool/entity_import.py` (add `apply_cohort_import`)
- Test: `science/tests/test_cohort_import.py`

**Interfaces:**
- Consumes: `_validate_cohort_plan_for_apply` (Task 6), `plan_reference_rewrite(..., source_overrides=...)` unused here (apply re-derives from live corpus, no overrides), `apply_reference_rewrite`, `claim_number_in_dir` (self-cleaning, Task 1), `_snapshot`, `_restore`, `audit_moved_references`.
- Produces: `apply_cohort_import(project_root: Path, plan: CohortImportPlan, *, exclude: frozenset[Path] = frozenset()) -> list[str]` — returns entity ids in member order. Exception-atomic: any caught failure restores everything mutated.

- [ ] **Step 1: Write the failing tests**

```python
# in tests/test_cohort_import.py
import hashlib
from science_tool.entity_import import apply_cohort_import


def test_cohort_apply_happy_path(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    _loose(root, "doc/notes.md", "see [a](plans/a.md) and [b](plans/b.md)\n")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    ids = apply_cohort_import(root, plan)
    assert ids == ["plan:0001-alpha", "plan:0002-beta"]
    assert (root / "entities/plans/0001-alpha.md").exists()
    assert (root / "entities/plans/0002-beta.md").exists()
    assert not a.exists() and not b.exists()
    notes = (root / "doc/notes.md").read_text(encoding="utf-8")
    assert "0001-alpha.md" in notes and "0002-beta.md" in notes


def test_cohort_apply_rolls_back_on_preclaimed_number(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    referrer = _loose(root, "doc/notes.md", "see [b](plans/b.md)\n")
    before_referrer = referrer.read_text(encoding="utf-8")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    # Someone commits 0002 between preview and apply.
    (root / "entities/plans/0002-someone.md").write_text(
        "---\nid: plan:0002-someone\nkind: plan\n---\n# S\n", encoding="utf-8")
    with pytest.raises(EntityImportError):
        apply_cohort_import(root, plan)
    # Full rollback: first member's dest gone, both sources intact, referrer intact.
    assert not (root / "entities/plans/0001-alpha.md").exists()
    assert a.exists() and b.exists()
    assert referrer.read_text(encoding="utf-8") == before_referrer


def test_cohort_apply_survives_mid_claim_source_edit(tmp_path):
    """A source edited AFTER the initial drift gate but during the claim block:
    the pre-unlink re-hash catches it, the edit survives, everything rolls back."""
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    plan = plan_cohort_import(root, [a, b], kind="plan")

    # Monkeypatch claim to mutate source b right after member a's dest is claimed,
    # simulating a concurrent edit inside the claim block.
    import science_tool.entity_import as ei
    real_claim = ei.claim_number_in_dir
    state = {"n": 0}
    def hooked_claim(pr, kind, number, local_part, text):
        path = real_claim(pr, kind, number, local_part, text)
        state["n"] += 1
        if state["n"] == 1:
            b.write_text("# Beta EDITED\n\nnew body\n", encoding="utf-8")
        return path
    import pytest as _pytest
    monkeypatch = _pytest.MonkeyPatch()
    monkeypatch.setattr(ei, "claim_number_in_dir", hooked_claim)
    try:
        with pytest.raises(EntityImportError):
            apply_cohort_import(root, plan)
    finally:
        monkeypatch.undo()
    assert b.read_text(encoding="utf-8") == "# Beta EDITED\n\nnew body\n"  # edit survived
    assert a.exists()  # source a restored
    assert not (root / "entities/plans/0001-alpha.md").exists()  # claimed dest rolled back


def test_cohort_apply_refuses_hand_edited_ref_report_before_snapshot(tmp_path, monkeypatch):
    """A re-enveloped plan whose ref_report was tampered is refused BEFORE snapshot.

    Proven by making _snapshot fail if reached: the equality check must reject first.
    """
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    from science_tool.reference_rewrite import FileEdit
    plan.ref_report.edits.append(
        FileEdit(rel_path="doc/evil.md", preimage_sha256="0" * 64, postimage="x"))
    import science_tool.entity_import as ei

    def unreached_snapshot(_paths):
        raise AssertionError("_snapshot reached; the tampered report was not rejected first")

    monkeypatch.setattr(ei, "_snapshot", unreached_snapshot)
    with pytest.raises(EntityImportError):
        apply_cohort_import(root, plan)
    assert a.exists() and b.exists()  # nothing moved


def test_cohort_apply_refuses_initial_source_drift(tmp_path):
    """A source edited BEFORE apply is refused by the initial drift gate."""
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    a.write_text("# Alpha CHANGED\n\nbody\n", encoding="utf-8")
    with pytest.raises(EntityImportError):
        apply_cohort_import(root, plan)
    assert a.exists() and b.exists()
    assert not (root / "entities/plans/0001-alpha.md").exists()


def test_cohort_apply_cleans_up_on_claim_path_mismatch(tmp_path, monkeypatch):
    """If the claim primitive returns an unexpected path, apply unlinks that
    exclusively-created file and rolls back (nothing escapes the mutated set)."""
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    import science_tool.entity_import as ei
    real_claim = ei.claim_number_in_dir

    def wrong_path_claim(pr, kind, number, local_part, text):
        canonical = real_claim(pr, kind, number, local_part, text)
        canonical.unlink(missing_ok=True)  # leave the canonical slot clean
        rogue = root / "entities/plans" / f"{number:04d}-rogue.md"
        rogue.write_text(text, encoding="utf-8")
        return rogue  # a path apply did not expect

    monkeypatch.setattr(ei, "claim_number_in_dir", wrong_path_claim)
    with pytest.raises(EntityImportError):
        apply_cohort_import(root, plan)
    assert not (root / "entities/plans/0001-rogue.md").exists()  # defensively cleaned up
    assert a.exists() and b.exists()  # sources never unlinked


def test_cohort_apply_rolls_back_on_inbound_rewrite_failure(tmp_path, monkeypatch):
    """A raised inbound rewrite restores claimed dests and unlinked sources."""
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    referrer = _loose(root, "doc/notes.md", "see [a](plans/a.md)\n")
    before = referrer.read_text(encoding="utf-8")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    import science_tool.entity_import as ei
    from science_tool.reference_rewrite import ReferenceDriftError

    def boom(*args, **kwargs):
        raise ReferenceDriftError("simulated mid-rewrite failure")

    monkeypatch.setattr(ei, "apply_reference_rewrite", boom)
    with pytest.raises(ReferenceDriftError):
        apply_cohort_import(root, plan)
    assert a.exists() and b.exists()
    assert not (root / "entities/plans/0001-alpha.md").exists()
    assert not (root / "entities/plans/0002-beta.md").exists()
    assert referrer.read_text(encoding="utf-8") == before


def test_cohort_apply_rolls_back_on_dangling_audit(tmp_path, monkeypatch):
    """A post-move audit failure rolls the whole cohort back — INCLUDING a referrer
    the real inbound rewrite already modified, restored to its exact preimage. This
    is the path that catches a missing snapshot or broken written_refs bookkeeping;
    audit runs AFTER apply_reference_rewrite, so the referrer has really been written.
    """
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    referrer = _loose(root, "doc/notes.md", "see [a](plans/a.md)\n")
    before = referrer.read_text(encoding="utf-8")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    # Sanity: the plan really rewrites this referrer, so the rollback assertion below
    # exercises the written_refs restore path, not a no-op.
    assert any(e.rel_path == "doc/notes.md" for e in plan.ref_report.edits)
    import science_tool.entity_import as ei
    monkeypatch.setattr(ei, "audit_moved_references", lambda *a, **k: ["dangling ref"])
    with pytest.raises(EntityImportError):
        apply_cohort_import(root, plan)
    assert a.exists() and b.exists()
    assert not (root / "entities/plans/0001-alpha.md").exists()
    assert not (root / "entities/plans/0002-beta.md").exists()
    assert referrer.read_text(encoding="utf-8") == before  # written, then restored exactly
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_cohort_import.py -k apply -v`
Expected: FAIL — `cannot import name 'apply_cohort_import'`.

- [ ] **Step 3: Write minimal implementation**

```python
def _source_digest(source: Path, rel: str) -> str:
    """Read a source and return its sha256, translating I/O and decode faults into
    EntityImportError so apply never leaks a raw OSError/UnicodeDecodeError. Used by
    both source-drift passes so their failure surface is identical (FileNotFoundError
    is an OSError subclass, so a source that vanishes mid-apply is covered)."""
    try:
        text = source.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise EntityImportError(f"{rel} is not valid UTF-8: {exc}") from exc
    except OSError as exc:
        raise EntityImportError(f"{rel} could not be read: {exc}") from exc
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def apply_cohort_import(
    project_root: Path, plan: CohortImportPlan, *, exclude: frozenset[Path] = frozenset()
) -> list[str]:
    """Execute a CohortImportPlan as one unit, restoring what IT changed on failure.

    Exception-atomic: caught failures roll back every mutated path. Crash-durability
    (SIGKILL) is out of scope and delegated to the caller's journal.
    """
    project_root = Path(project_root).resolve()
    if plan.plan_type != "cohort-import" or plan.schema_version != 1:
        raise EntityImportError(
            f"unsupported cohort plan (plan_type={plan.plan_type!r}, schema_version={plan.schema_version})"
        )
    if plan.project_root != str(project_root):
        raise EntityImportError(
            f"plan was built against {plan.project_root}, not {project_root}; re-run the preview here"
        )

    # 1. Shape + per-member identity (containment, canonical dest, coherence).
    sources = _validate_cohort_plan_for_apply(project_root, plan)

    # 2. Source drift, initial gate. Re-hashed again per source before its unlink.
    for member, source in zip(plan.members, sources, strict=True):
        if not source.is_file():
            raise EntityImportError(f"source not found: {member.source_rel}")
        if _source_digest(source, member.source_rel) != member.source_sha256:
            raise EntityImportError(
                f"{member.source_rel} changed since the preview; re-run the preview"
            )

    all_sources = {project_root / m.source_rel for m in plan.members}
    all_dests = {project_root / m.dest_rel for m in plan.members}

    # 3. Re-derive the external report from the LIVE corpus and require it to equal
    # the frozen report IN ITS ENTIRETY, before any snapshot. Members and dests are
    # excluded so only external referrers contribute (matching planning, where
    # members contributed nothing once the independence guard passed).
    fresh = plan_reference_rewrite(
        project_root,
        id_substitutions={m.source_rel: m.entity_id for m in plan.members},
        path_substitutions={m.source_rel: m.dest_rel for m in plan.members},
        exclude=exclude | all_sources | all_dests,
    )
    if fresh != plan.ref_report:
        raise EntityImportError(
            "the corpus changed since the preview (external references no longer match); re-run the preview"
        )

    # 4. Snapshot the verified read set: every source, every dest, every edited referrer.
    touched = [
        *all_sources, *all_dests,
        *{project_root / e.rel_path for e in plan.ref_report.edits},
    ]
    snapshot = _snapshot(touched)

    mutated: set[Path] = set()
    written_refs: list[str] = []
    try:
        # 5. Claim the number block. Prove the destination BEFORE the primitive; on
        # a successful return record it immediately so rollback owns it.
        for member in plan.members:
            dest = project_root / member.dest_rel
            expected = f"{resolve_path_policy(plan.kind).root}/{dest.stem}.md"
            if member.dest_rel != expected:  # proven pre-creation
                raise EntityImportError(
                    f"member destination {member.dest_rel!r} is not canonical for {member.entity_id!r}"
                )
            claimed = claim_number_in_dir(
                project_root, plan.kind, member.number, dest.stem, member.rendered_text
            )
            mutated.add(claimed)  # record the file the claim just created
            if claimed != dest:
                claimed.unlink(missing_ok=True)  # defensive: never leave an unexpected file
                raise EntityImportError(
                    f"claim returned {claimed} for member {member.entity_id!r}, expected {dest}"
                )

        # 6. Unlink sources. Re-hash each immediately before its own unlink: the
        # initial gate (step 2) is far away, so a source edited in between must not
        # be deleted. Match -> unlink in the adjacent statement and mark mutated.
        for member in plan.members:
            source = project_root / member.source_rel
            if _source_digest(source, member.source_rel) != member.source_sha256:
                raise EntityImportError(
                    f"{member.source_rel} changed during apply; rolled back — re-run the preview"
                )
            source.unlink()
            mutated.add(source)

        # 7. Inbound rewrite: repoint external referrers in one pass.
        apply_reference_rewrite(
            project_root, plan.ref_report,
            exclude=exclude | all_sources | all_dests, written=written_refs,
        )

        # 8. Post-move audit for every destination.
        for member in plan.members:
            if problems := audit_moved_references(project_root, member.dest_rel, exclude=exclude):
                raise EntityImportError(
                    "post-move reference audit failed; the cohort import was rolled back:\n  "
                    + "\n  ".join(problems)
                )
    except Exception:
        restrict = {*mutated, *(project_root / rel for rel in written_refs)}
        _restore(snapshot, restrict=restrict)
        raise

    # 9. Return ids in member (input) order.
    return [m.entity_id for m in plan.members]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_cohort_import.py -v`
Expected: PASS (all cohort tests, including the mid-claim-edit rollback and hand-edited-report refusal).

- [ ] **Step 5: Commit**

```bash
cd science && git add src/science_tool/entity_import.py tests/test_cohort_import.py
git commit -m "feat(import): apply_cohort_import — atomic block claim with per-source pre-unlink re-hash"
```

---

### Task 8: CLI — variadic sources, option matrix, cohort + discriminated apply dispatch

**Files:**
- Modify: `science/src/science_tool/entities_inventory_cli.py:449-577` (`entities_import_command`)
- Test: `science/tests/test_entity_import_cli.py`

**Interfaces:**
- Consumes: `plan_cohort_import`, `apply_cohort_import`, `parse_cohort_import_plan`, `CohortImportPlan` (Tasks 4-7); existing `plan_import`, `apply_import`, `parse_import_plan`; envelope helpers.
- Produces: the `import` command accepting `SOURCE...` (0 = apply-plan, 1 = single, 2+ = cohort). Enforced matrix: `--title`/`--slug` rejected with 2+ sources; `--save-plan` must differ from **every** resolved source (even with `--overwrite-plan`); `--apply-plan` rejects `--title`/`--status`/`--slug`/`--save-plan`/`--overwrite-plan`. Apply-plan dispatches on the discriminator: `plan_type=="cohort-import"` + known `schema_version` → cohort; **no** `plan_type` **and no** `schema_version` → single; anything else → clean error.

- [ ] **Step 1: Write the failing tests**

```python
# in tests/test_entity_import_cli.py — reuse the file's existing runner/fixtures.
import json
from click.testing import CliRunner
from science_tool.cli import main


def _run(args, cwd):
    return CliRunner().invoke(main, args, catch_exceptions=False)


def test_cli_cohort_save_and_apply(tmp_path, monkeypatch):
    root = tmp_path
    (root / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    (root / "entities" / "plans").mkdir(parents=True)
    (root / "doc").mkdir()
    (root / "doc/a.md").write_text("# Alpha\n\nbody\n", encoding="utf-8")
    (root / "doc/b.md").write_text("# Beta\n\nbody\n", encoding="utf-8")
    monkeypatch.chdir(root)
    save = root / "cohort.json"
    res = _run(["entities", "import", "doc/a.md", "doc/b.md", "--kind", "plan",
                "--save-plan", str(save)], root)
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    sha = payload["plan_sha256"]
    assert payload["plan_type"] == "cohort-import"
    res2 = _run(["entities", "import", "--apply-plan", str(save),
                 "--expected-plan-sha256", sha], root)
    assert res2.exit_code == 0, res2.output
    assert (root / "entities/plans/0001-alpha.md").exists()
    assert (root / "entities/plans/0002-beta.md").exists()


def test_cli_cohort_rejects_title(tmp_path, monkeypatch):
    root = tmp_path
    (root / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    (root / "doc").mkdir()
    (root / "doc/a.md").write_text("# A\n\nb\n", encoding="utf-8")
    (root / "doc/b.md").write_text("# B\n\nb\n", encoding="utf-8")
    monkeypatch.chdir(root)
    res = CliRunner().invoke(main, ["entities", "import", "doc/a.md", "doc/b.md",
                                    "--kind", "plan", "--title", "X"])
    assert res.exit_code != 0
    assert "title" in res.output.lower()


def test_cli_cohort_save_plan_equal_to_a_source_is_rejected(tmp_path, monkeypatch):
    root = tmp_path
    (root / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    (root / "doc").mkdir()
    (root / "doc/a.md").write_text("# A\n\nb\n", encoding="utf-8")
    (root / "doc/b.md").write_text("# B\n\nb\n", encoding="utf-8")
    monkeypatch.chdir(root)
    res = CliRunner().invoke(main, ["entities", "import", "doc/a.md", "doc/b.md",
                                    "--kind", "plan", "--save-plan", "doc/a.md", "--overwrite-plan"])
    assert res.exit_code != 0
    assert "source" in res.output.lower()


def test_cli_apply_plan_rejects_preview_options(tmp_path, monkeypatch):
    root = tmp_path
    (root / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    (root / "p.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(root)
    res = CliRunner().invoke(main, ["entities", "import", "--apply-plan", "p.json",
                                    "--expected-plan-sha256", "x", "--title", "T"])
    assert res.exit_code != 0


def test_cli_legacy_single_plan_still_applies(tmp_path, monkeypatch):
    """A single-import plan (no plan_type) still routes to the single path."""
    root = tmp_path
    (root / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    (root / "entities" / "plans").mkdir(parents=True)
    (root / "doc").mkdir()
    (root / "doc/a.md").write_text("# Alpha\n\nbody\n", encoding="utf-8")
    monkeypatch.chdir(root)
    save = root / "single.json"
    res = _run(["entities", "import", "doc/a.md", "--kind", "plan", "--save-plan", str(save)], root)
    assert res.exit_code == 0, res.output
    sha = json.loads(res.output)["plan_sha256"]
    assert "plan_type" not in json.loads(save.read_text())  # legacy shape
    res2 = _run(["entities", "import", "--apply-plan", str(save), "--expected-plan-sha256", sha], root)
    assert res2.exit_code == 0, res2.output
    assert (root / "entities/plans/0001-alpha.md").exists()


def _envelope_sha(raw: bytes) -> str:
    from science_tool.plan_common import plan_sha256
    return plan_sha256(raw)


def test_cli_apply_plan_rejects_unknown_plan_type(tmp_path, monkeypatch):
    root = tmp_path
    (root / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    raw = json.dumps({"plan_type": "something-else", "schema_version": 1}).encode("utf-8")
    (root / "p.json").write_bytes(raw)
    monkeypatch.chdir(root)
    res = CliRunner().invoke(main, ["entities", "import", "--apply-plan", "p.json",
                                    "--expected-plan-sha256", _envelope_sha(raw)])
    assert res.exit_code != 0
    assert "unsupported plan" in res.output.lower()


def test_cli_apply_plan_rejects_unknown_schema_version(tmp_path, monkeypatch):
    root = tmp_path
    (root / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    raw = json.dumps({"plan_type": "cohort-import", "schema_version": 999}).encode("utf-8")
    (root / "p.json").write_bytes(raw)
    monkeypatch.chdir(root)
    res = CliRunner().invoke(main, ["entities", "import", "--apply-plan", "p.json",
                                    "--expected-plan-sha256", _envelope_sha(raw)])
    assert res.exit_code != 0
    assert "unsupported plan" in res.output.lower()


def test_cli_apply_plan_rejects_schema_version_without_plan_type(tmp_path, monkeypatch):
    """A version stamp with no discriminator is rejected, not routed to the single parser."""
    root = tmp_path
    (root / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    raw = json.dumps({"schema_version": 1, "source_rel": "x"}).encode("utf-8")
    (root / "p.json").write_bytes(raw)
    monkeypatch.chdir(root)
    res = CliRunner().invoke(main, ["entities", "import", "--apply-plan", "p.json",
                                    "--expected-plan-sha256", _envelope_sha(raw)])
    assert res.exit_code != 0
    assert "unsupported plan" in res.output.lower()


def test_cli_apply_plan_rejects_non_object_json(tmp_path, monkeypatch):
    """A JSON list/scalar must be refused cleanly, not crash on .get()."""
    root = tmp_path
    (root / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    raw = b"[1, 2, 3]"
    (root / "p.json").write_bytes(raw)
    monkeypatch.chdir(root)
    res = CliRunner().invoke(main, ["entities", "import", "--apply-plan", "p.json",
                                    "--expected-plan-sha256", _envelope_sha(raw)])
    assert res.exit_code != 0  # a clean ClickException, not an AttributeError traceback


def test_cli_apply_plan_rejects_invalid_utf8(tmp_path, monkeypatch):
    """Non-UTF-8 plan bytes are refused cleanly, not with a raw UnicodeDecodeError."""
    root = tmp_path
    (root / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    raw = b"\xff\xfe not valid utf-8"
    (root / "p.json").write_bytes(raw)
    monkeypatch.chdir(root)
    res = CliRunner().invoke(main, ["entities", "import", "--apply-plan", "p.json",
                                    "--expected-plan-sha256", _envelope_sha(raw)])
    assert res.exit_code != 0
    assert "not valid json" in res.output.lower()


def test_cli_apply_plan_rejects_boolean_schema_version(tmp_path, monkeypatch):
    """`"schema_version": true` must not satisfy the cohort discriminator (True == 1)."""
    root = tmp_path
    (root / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    raw = json.dumps({"plan_type": "cohort-import", "schema_version": True}).encode("utf-8")
    (root / "p.json").write_bytes(raw)
    monkeypatch.chdir(root)
    res = CliRunner().invoke(main, ["entities", "import", "--apply-plan", "p.json",
                                    "--expected-plan-sha256", _envelope_sha(raw)])
    assert res.exit_code != 0
    assert "unsupported plan" in res.output.lower()


def test_cli_single_import_preserves_explicit_slug(tmp_path, monkeypatch):
    """A single-source --slug flows end-to-end to the applied entity id."""
    root = tmp_path
    (root / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    (root / "entities" / "plans").mkdir(parents=True)
    (root / "doc").mkdir()
    (root / "doc/a.md").write_text("# Alpha\n\nbody\n", encoding="utf-8")
    monkeypatch.chdir(root)
    save = root / "single.json"
    res = _run(["entities", "import", "doc/a.md", "--kind", "plan",
                "--slug", "custom-slug", "--save-plan", str(save)], root)
    assert res.exit_code == 0, res.output
    sha = json.loads(res.output)["plan_sha256"]
    res2 = _run(["entities", "import", "--apply-plan", str(save), "--expected-plan-sha256", sha], root)
    assert res2.exit_code == 0, res2.output
    assert (root / "entities/plans/0001-custom-slug.md").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_entity_import_cli.py -k "cohort or apply_plan_rejects or legacy_single or explicit_slug or non_object" -v`
Expected: FAIL — the command takes a single `SOURCE` and cannot accept two.

- [ ] **Step 3: Write minimal implementation**

Change the argument to variadic and rework the body. Replace the `@click.argument(...)` line and `source: Path | None` parameter:
```python
@click.argument("sources", nargs=-1, type=click.Path(exists=True, dir_okay=False, path_type=Path))
```
and in the signature `source: Path | None,` becomes `sources: tuple[Path, ...],`.

Add the cohort imports to the in-function import block:
```python
    from science_tool.entity_import import (
        EntityImportError,
        CohortImportPlan,
        apply_cohort_import,
        apply_import,
        parse_cohort_import_plan,
        parse_import_plan,
        plan_cohort_import,
        plan_import,
    )
```
Replace the command body (from `if apply_plan_path is not None:` to the end) with:
```python
    if apply_plan_path is not None:
        if sources or kind is not None:
            raise click.UsageError("--apply-plan takes the saved plan only; do not repeat SOURCE or --kind.")
        # The one deliberate tightening: reject the preview-only options apply
        # previously ignored, so an operator cannot believe they had any effect.
        # Use `is not None` for value options so an explicit empty string (--title "")
        # is still rejected; overwrite_plan is a bool flag, so truthiness is correct.
        for bad, name in [(title is not None, "--title"), (status is not None, "--status"),
                          (slug is not None, "--slug"), (save_plan is not None, "--save-plan"),
                          (overwrite_plan, "--overwrite-plan")]:
            if bad:
                raise click.UsageError(f"{name} may not be combined with --apply-plan")
        if not expected_plan_sha256:
            raise click.UsageError("--apply-plan requires --expected-plan-sha256")
        exclude = frozenset({apply_plan_path.resolve()})
        raw = read_plan_bytes(apply_plan_path)
        try:
            verify_envelope(raw, expected_plan_sha256)
        except EnvelopeError as exc:
            raise click.ClickException(str(exc)) from exc
        # Discriminate. Parse once as generic JSON to read the discriminator, then
        # dispatch. no plan_type AND no schema_version -> legacy single; the cohort
        # discriminator -> cohort; anything else -> clean refusal.
        try:
            probe = json.loads(raw)  # json.loads on bytes may raise UnicodeDecodeError
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise click.ClickException(f"plan is not valid JSON: {exc}") from exc
        if not isinstance(probe, dict):  # a JSON list/scalar has no discriminator
            raise click.ClickException("plan is not a JSON object")
        plan_type = probe.get("plan_type")
        schema_version = probe.get("schema_version")
        # A GENUINE integer 1, not JSON true: `True == 1` in Python and Pydantic's int
        # field would coerce a bool, so a `"schema_version": true` plan must not pass.
        cohort_version = isinstance(schema_version, int) and not isinstance(schema_version, bool) and schema_version == 1
        try:
            if plan_type == "cohort-import" and cohort_version:
                cohort = parse_cohort_import_plan(raw)
                payload = {**cohort.model_dump(),
                           "applied": apply_cohort_import(project_root, cohort, exclude=exclude)}
            elif plan_type is None and schema_version is None:
                single = parse_import_plan(raw)
                payload = {**single.model_dump(),
                           "applied": apply_import(project_root, single, exclude=exclude)}
            else:
                raise click.ClickException(
                    f"unsupported plan (plan_type={plan_type!r}, schema_version={schema_version!r})"
                )
        except (EntityImportError, EntityCommandError, ReferenceDriftError) as exc:
            raise click.ClickException(str(exc)) from exc
        emit(output_format="json", payload=payload, render_text=lambda: None)
        return

    if not sources or kind is None:
        raise click.UsageError("SOURCE and --kind are required unless --apply-plan is given.")
    if expected_plan_sha256:
        raise click.UsageError("--expected-plan-sha256 requires --apply-plan")

    # --save-plan must never clobber a source (even with --overwrite-plan).
    if save_plan is not None:
        save_resolved = save_plan.resolve()
        if any(save_resolved == s.resolve() for s in sources):
            raise click.UsageError("--save-plan would overwrite a source document; choose another path")
    preview_exclude = frozenset({save_plan.resolve()}) if save_plan is not None else frozenset()

    is_cohort = len(sources) >= 2
    if is_cohort and (title is not None or slug is not None):
        raise click.UsageError("--title/--slug are per-document and not allowed with multiple sources")

    try:
        if is_cohort:
            plan_obj: CohortImportPlan | ImportPlan = plan_cohort_import(
                project_root, list(sources), kind=kind, status=status, exclude=preview_exclude,
            )
        else:
            plan_obj = plan_import(
                project_root, sources[0], kind=kind, title=title, status=status, slug=slug,
                exclude=preview_exclude,
            )
    except (EntityImportError, EntityCommandError) as exc:
        raise click.ClickException(str(exc)) from exc

    if save_plan is not None:
        payload_bytes = plan_obj.model_dump_json(indent=2).encode("utf-8")
        try:
            with open(save_plan, "xb") as fh:
                fh.write(payload_bytes)
        except FileExistsError:
            if not overwrite_plan:
                raise click.UsageError(
                    f"--save-plan target {save_plan} exists; pass --overwrite-plan to replace it"
                ) from None
            save_plan.write_bytes(payload_bytes)
        except OSError as exc:
            raise click.UsageError(f"cannot write --save-plan to {save_plan}: {exc}") from exc
        emit(output_format="json",
             payload={**plan_obj.model_dump(), "plan_sha256": plan_sha256(payload_bytes)},
             render_text=lambda: None)
        return
    emit(output_format="json", payload=plan_obj.model_dump(), render_text=lambda: None)
```
Add `import json` and `from science_tool.entity_import import ImportPlan` at the top of the function's import block (or module top if already importing there). Ensure `EntityCommandError` and `ReferenceDriftError` imports (already present).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_entity_import_cli.py -v`
Expected: PASS (new cohort/discriminator tests plus the full existing single-import CLI suite).

- [ ] **Step 5: Commit**

```bash
cd science && git add src/science_tool/entities_inventory_cli.py tests/test_entity_import_cli.py
git commit -m "feat(cli): cohort import via variadic sources + discriminated apply-plan dispatch"
```

---

### Task 9: Version bump 0.5.1 → 0.5.2

**Files:**
- Modify: `science/pyproject.toml:3`, `.claude-plugin/plugin.json:3`, `science/tests/test_cli_version.py`
- Regenerate: `science/uv.lock`
- Test: `science/tests/test_cli_version.py`

**Interfaces:** none (release metadata).

- [ ] **Step 1: Update the version baseline test**

In `science/tests/test_cli_version.py`, change the baseline assertion:
```python
def test_package_and_plugin_establish_0_5_1_baseline() -> None:
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert _package_version() == "0.5.2"
    assert plugin["version"] == "0.5.2"
```
(Rename the function to `..._0_5_2_baseline` for accuracy.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_cli_version.py -v`
Expected: FAIL — sources still say `0.5.1`.

- [ ] **Step 3: Bump the version strings**

- `science/pyproject.toml`: `version = "0.5.1"` → `version = "0.5.2"`.
- `.claude-plugin/plugin.json`: `"version": "0.5.1",` → `"version": "0.5.2",`.

- [ ] **Step 4: Re-lock and run the version test**

Run: `cd science && uv lock && uv run --frozen pytest tests/test_cli_version.py -v`
Expected: PASS. (`uv lock` updates the `science` package version pin in `uv.lock`.)

- [ ] **Step 5: Commit**

```bash
cd science && git add pyproject.toml ../.claude-plugin/plugin.json tests/test_cli_version.py uv.lock
git commit -m "chore(release): bump science 0.5.1 -> 0.5.2 (cohort import)"
```

---

## Final verification (before the whole-branch review)

Run the full suite AND the linters from the nested dir (the suite alone is not enough — the branch touches type-checked modules). One `cd`, then the three commands:
```bash
cd science
uv run --frozen pytest -q
uv run --frozen ruff check
uv run --frozen pyright
```
Expected: green tests with no regressions in the single-import, reservation, or reference-rewrite suites; ruff and pyright both clean on the changed modules.

## Post-merge consumer delivery (out of scope for this plan, tracked separately)

After merge + push, natural-systems re-pins science `0.5.2` (surgical `uv.lock` edit + `expected_science_revision.txt` + a surface test exercising cohort save-plan/apply-plan). Plan 2 v5 then drops the overlay and calls cohort import for its batch's import moves. This is natural-systems work, not part of this branch.
