# Phase 4e Superseded Proposition Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a proposition-aware archive command that safely relocates settled `status: superseded` propositions while preserving scalar and multi-successor lineage in the archive index and graph.

**Architecture:** First extend the generic archive row and graph materializer so lineage-bearing archived rows remain graph-visible even when no live entity points at them. Then add a narrow `science annotate archive-superseded-propositions` surface that reports/apply-moves only 4e-ready superseded propositions, with live sidecar backlink checks before relocation.

**Tech Stack:** Python 3.12, Click, Pydantic, rdflib, pytest, existing `science_tool.archive`, `science_tool.graph.materialize`, and W3C annotation sidecar helpers.

---

## File Structure

- Modify `science/src/science_tool/archive.py`
  - Add `ArchiveRow.resynthesized_into`.
  - Preserve `resynthesized_into` in generic `_candidate_rows` when present.
  - Include it in generic archive dry-run JSON for visibility without adding proposition-specific checks.
- Modify `science/src/science_tool/graph/materialize.py`
  - Add archive-row lineage helpers.
  - Seed archived tombstone emission from lineage-bearing active archive rows, not only live inbound refs.
  - Emit one `sci:supersededBy` per `ArchiveRow.resynthesized_into` target.
- Create `science/src/science_tool/annotation/proposition_archive.py`
  - Own 4e candidate detection, sidecar backlink scan, report shaping, archive row construction, apply, and postflight.
- Modify `science/src/science_tool/annotation/cli.py`
  - Add flat command `archive-superseded-propositions`.
- Modify or create tests:
  - `science/tests/test_archive_index.py`
  - `science/tests/test_archive_mutators.py`
  - `science/tests/test_archive_resolution_graph.py`
  - `science/tests/test_proposition_archive.py`
  - `science/tests/test_proposition_archive_cli.py`

Keep the generic archive command content-agnostic. Do not make `science entities archive` scan annotation sidecars.

---

### Task 1: Archive Row Schema Preserves Multi-Successor Lineage

**Files:**
- Modify: `science/src/science_tool/archive.py`
- Test: `science/tests/test_archive_index.py`
- Test: `science/tests/test_archive_mutators.py`

- [ ] **Step 1: Add failing schema/index tests**

Append these tests to `science/tests/test_archive_index.py`:

```python
def test_archive_row_round_trips_resynthesized_into() -> None:
    row = ArchiveRow(
        op="archive",
        id="proposition:broad",
        kind="proposition",
        status="superseded",
        original_path="entities/propositions/broad.md",
        resynthesized_into=["proposition:negative", "proposition:positive"],
    )

    loaded = ArchiveRow.model_validate_json(row.model_dump_json())

    assert loaded.resynthesized_into == ["proposition:negative", "proposition:positive"]


def test_archive_row_backfills_empty_resynthesized_into_for_existing_rows() -> None:
    loaded = ArchiveRow.model_validate_json('{"op": "archive", "id": "proposition:old"}')

    assert loaded.resynthesized_into == []
```

Append this test to `science/tests/test_archive_mutators.py`:

```python
def test_generic_archive_preserves_resynthesized_into_when_present(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "propositions",
        "broad",
        "---\n"
        "id: proposition:broad\n"
        "type: proposition\n"
        "status: superseded\n"
        "resynthesized_into:\n"
        "  - proposition:negative\n"
        "  - proposition:positive\n"
        "---\n"
        "Broad claim.\n",
    )

    report = archive_entities(tmp_path, apply=True, now="T1")

    assert report["applied"] == ["proposition:broad"]
    row = load_archive_index(tmp_path).active_by_id["proposition:broad"]
    assert row.resynthesized_into == ["proposition:negative", "proposition:positive"]
```

- [ ] **Step 2: Run the new tests and confirm RED**

Run:

```bash
rtk uv run --frozen pytest \
  science/tests/test_archive_index.py::test_archive_row_round_trips_resynthesized_into \
  science/tests/test_archive_index.py::test_archive_row_backfills_empty_resynthesized_into_for_existing_rows \
  science/tests/test_archive_mutators.py::test_generic_archive_preserves_resynthesized_into_when_present -q
```

Expected: FAIL because `ArchiveRow` has no `resynthesized_into` attribute.

- [ ] **Step 3: Add the schema field**

In `science/src/science_tool/archive.py`, add this field to `ArchiveRow` immediately after `superseded_by`:

```python
    resynthesized_into: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Preserve the field in generic candidate rows**

In `_candidate_rows`, replace the `superseded_by=fm.get("superseded_by"),` line with:

```python
                superseded_by=fm.get("superseded_by") if isinstance(fm.get("superseded_by"), str) else None,
                resynthesized_into=[
                    ref for ref in (fm.get("resynthesized_into") or []) if isinstance(ref, str)
                ],
```

In `archive_entities`, extend each candidate dict to expose the field:

```python
    report: dict = {
        "candidates": [
            {
                "id": r.id,
                "kind": r.kind,
                "status": r.status,
                "original_path": r.original_path,
                "superseded_by": r.superseded_by,
                "resynthesized_into": r.resynthesized_into,
                "inbound_live_refs": inbound.get(r.id, []),
            }
            for r in rows
        ],
        "applied": [],
        "skipped": [],
    }
```

Keep this generic: do not validate proposition lineage shapes here.

- [ ] **Step 5: Run tests and confirm GREEN**

Run:

```bash
rtk uv run --frozen pytest \
  science/tests/test_archive_index.py::test_archive_row_round_trips_resynthesized_into \
  science/tests/test_archive_index.py::test_archive_row_backfills_empty_resynthesized_into_for_existing_rows \
  science/tests/test_archive_mutators.py::test_generic_archive_preserves_resynthesized_into_when_present -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/archive.py science/tests/test_archive_index.py science/tests/test_archive_mutators.py
git commit -m "feat(archive): preserve resynthesis lineage in rows"
```

---

### Task 2: Archived Lineage Materialization

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py`
- Test: `science/tests/test_archive_resolution_graph.py`

- [ ] **Step 1: Add graph helper imports and tests**

Modify the imports near the top of `science/tests/test_archive_resolution_graph.py`. Place
these *after* the existing `rdflib = pytest.importorskip("rdflib")` line so the module still
skips cleanly if rdflib is absent, matching the file's existing pattern:

```python
from rdflib import Dataset
from rdflib.namespace import RDF

from science_tool.graph.store import PROJECT_NS, SCI_NS
```

Add these helpers below `_build_graph_text`:

```python
def _build_knowledge_graph(tmp_path: Path):
    from science_tool.graph.materialize import materialize_graph

    out_path = materialize_graph(tmp_path, strict=False)
    dataset = Dataset()
    dataset.parse(source=str(out_path), format="trig")
    return dataset.graph(PROJECT_NS["graph/knowledge"])


def _entity_uri(ref: str):
    kind, slug = ref.split(":", 1)
    return PROJECT_NS[f"{kind}/{slug}"]


def _proposition(tmp_path: Path, slug: str, title: str | None = None) -> None:
    d = tmp_path / "entities" / "propositions"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(
        "---\n"
        f"id: proposition:{slug}\n"
        "type: proposition\n"
        f"title: {title or slug}\n"
        "---\n"
        "Claim.\n",
        encoding="utf-8",
    )
```

Append these tests:

```python
def test_unreferenced_archived_scalar_lineage_emits_stub_and_edge(tmp_path: Path) -> None:
    _seed(tmp_path)
    _live(
        tmp_path,
        "---\n"
        "id: interpretation:0001-live\n"
        "type: interpretation\n"
        "title: Live\n"
        "---\n",
    )
    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="interpretation:0002-gone",
            kind="interpretation",
            title="Gone",
            superseded_by="interpretation:0003-new",
            original_path="entities/interpretations/0002-gone.md",
            archived_at="T1",
        ),
    )
    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="interpretation:0003-new",
            kind="interpretation",
            title="New",
            original_path="entities/interpretations/0003-new.md",
            archived_at="T1",
        ),
    )

    knowledge = _build_knowledge_graph(tmp_path)

    gone = _entity_uri("interpretation:0002-gone")
    new = _entity_uri("interpretation:0003-new")
    assert (gone, RDF.type, SCI_NS.ArchivedEntity) in knowledge
    assert (gone, SCI_NS.supersededBy, new) in knowledge
    assert (new, RDF.type, SCI_NS.ArchivedEntity) in knowledge


def test_unreferenced_archived_resynthesized_into_emits_all_lineage_edges(tmp_path: Path) -> None:
    _seed(tmp_path)
    _live(
        tmp_path,
        "---\n"
        "id: interpretation:0001-live\n"
        "type: interpretation\n"
        "title: Live\n"
        "---\n",
    )
    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="proposition:broad",
            kind="proposition",
            title="Broad",
            status="superseded",
            resynthesized_into=["proposition:negative", "proposition:positive"],
            original_path="entities/propositions/broad.md",
            archived_at="T1",
        ),
    )
    _proposition(tmp_path, "negative", "Negative")
    _proposition(tmp_path, "positive", "Positive")

    knowledge = _build_knowledge_graph(tmp_path)

    broad = _entity_uri("proposition:broad")
    assert (broad, RDF.type, SCI_NS.ArchivedEntity) in knowledge
    assert set(knowledge.objects(broad, SCI_NS.supersededBy)) == {
        _entity_uri("proposition:negative"),
        _entity_uri("proposition:positive"),
    }


def test_archived_resynthesized_into_rejects_unknown_target(tmp_path: Path) -> None:
    _seed(tmp_path)
    _live(
        tmp_path,
        "---\n"
        "id: interpretation:0001-live\n"
        "type: interpretation\n"
        "title: Live\n"
        "---\n",
    )
    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="proposition:broad",
            kind="proposition",
            title="Broad",
            resynthesized_into=["proposition:missing"],
            original_path="entities/propositions/broad.md",
            archived_at="T1",
        ),
    )

    with pytest.raises(ValueError, match="unknown archived lineage target proposition:missing"):
        _build_knowledge_graph(tmp_path)
```

- [ ] **Step 2: Run the graph tests and confirm RED**

Run:

```bash
rtk uv run --frozen pytest \
  science/tests/test_archive_resolution_graph.py::test_unreferenced_archived_scalar_lineage_emits_stub_and_edge \
  science/tests/test_archive_resolution_graph.py::test_unreferenced_archived_resynthesized_into_emits_all_lineage_edges \
  science/tests/test_archive_resolution_graph.py::test_archived_resynthesized_into_rejects_unknown_target -q
```

Expected: FAIL. The scalar test has no tombstone because nothing live references the archive row. The multi-successor tests fail because the materializer does not read `resynthesized_into`.

- [ ] **Step 3: Add archive lineage helpers**

In `science/src/science_tool/graph/materialize.py`, add these helpers after `_add_live_lineage_edges`:

```python
def _archive_lineage_targets(
    archived_id: str,
    row,
    *,
    entity_index: Mapping[str, Entity],
    archive_active: Mapping[str, object],
) -> tuple[str, ...]:
    targets: list[str] = []
    if row.superseded_by and (row.superseded_by in entity_index or row.superseded_by in archive_active):
        targets.append(row.superseded_by)

    resynthesized_into = getattr(row, "resynthesized_into", [])
    if resynthesized_into:
        if not isinstance(resynthesized_into, list):
            raise ValueError(f"archived lineage {archived_id} has malformed resynthesized_into")
        seen: set[str] = set()
        for target in resynthesized_into:
            if not isinstance(target, str) or not target:
                raise ValueError(f"archived lineage {archived_id} has malformed resynthesized_into")
            if target == archived_id:
                raise ValueError(f"archived lineage {archived_id} cannot supersede itself")
            if target in seen:
                raise ValueError(f"archived lineage {archived_id} has duplicate successor {target}")
            seen.add(target)
            if target not in entity_index and target not in archive_active:
                raise ValueError(f"archived lineage {archived_id} points to unknown archived lineage target {target}")
            targets.append(target)
    return tuple(targets)


def _seed_archived_lineage_stubs(
    *,
    entity_index: Mapping[str, Entity],
    archive_active: Mapping[str, object],
    referenced_archived: set[str],
) -> dict[str, tuple[str, ...]]:
    lineage_targets: dict[str, tuple[str, ...]] = {}
    for archived_id in sorted(archive_active):
        row = archive_active[archived_id]
        targets = _archive_lineage_targets(
            archived_id,
            row,
            entity_index=entity_index,
            archive_active=archive_active,
        )
        if not targets:
            continue
        referenced_archived.add(archived_id)
        for target in targets:
            if target in archive_active:
                referenced_archived.add(target)
        lineage_targets[archived_id] = targets
    return lineage_targets
```

- [ ] **Step 4: Seed and emit archive lineage in `_emit_phase`**

In `_emit_phase`, after `_add_live_lineage_edges(...)` and before the tombstone loop, add:

```python
    archive_lineage_targets = _seed_archived_lineage_stubs(
        entity_index=entity_index,
        archive_active=archive_active,
        referenced_archived=referenced_archived,
    )
```

Then replace the existing scalar-only tombstone lineage block:

```python
        # superseded_by emitted only when it resolves to a known id — a live entity OR
        # another active archived id. Unresolvable/dangling successor -> omitted.
        if row.superseded_by and (row.superseded_by in entity_index or row.superseded_by in archive_active):
            knowledge.add((uri, SCI_NS.supersededBy, _entity_uri(row.superseded_by)))
```

with:

```python
        for target in archive_lineage_targets.get(archived_id, ()):
            knowledge.add((uri, SCI_NS.supersededBy, _entity_uri(target)))
```

`_seed_archived_lineage_stubs` already applied scalar lenience and multi-successor
strictness during seeding: an unresolved scalar `superseded_by` was dropped (so it
never reaches `archive_lineage_targets` and emits no edge — the historical lenient
behavior), and an unresolved `resynthesized_into` target raised. No separate fallback
branch is needed. Every row with a resolvable scalar successor is already in
`archive_lineage_targets`; a row with no resolvable lineage still gets its stub above
but emits no edge.

- [ ] **Step 5: Run graph tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_archive_resolution_graph.py science/tests/test_live_lineage_visibility_graph.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_archive_resolution_graph.py
git commit -m "feat(graph): materialize archived lineage stubs"
```

---

### Task 3: Superseded Proposition Archive Report

**Files:**
- Create: `science/src/science_tool/annotation/proposition_archive.py`
- Create: `science/tests/test_proposition_archive.py`

- [ ] **Step 1: Create focused RED tests for dry-run reporting**

Create `science/tests/test_proposition_archive.py` with:

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from science_tool.annotation import io as anno_io
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.proposition_archive import (
    PropositionArchiveError,
    archive_superseded_propositions,
    build_superseded_proposition_archive_report,
)
from science_tool.archive import (
    ArchiveRow,
    append_row,
    archive_index_path,
    derive_archive_path,
    load_archive_index,
)


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: test\n", encoding="utf-8")


def _entity(root: Path, rel: str, frontmatter: str, body: str = "Body.\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return path


def _proposition(
    root: Path,
    slug: str,
    *,
    status: str = "active",
    extra_frontmatter: str = "",
) -> Path:
    return _entity(
        root,
        f"entities/propositions/{slug}.md",
        f"id: proposition:{slug}\n"
        "type: proposition\n"
        f"title: {slug}\n"
        f"status: {status}\n"
        f"{extra_frontmatter}",
        "Claim.\n",
    )


def _paper_sidecar(root: Path, citekey: str, annotations: list[Annotation]) -> None:
    md = root / "entities" / "papers" / f"{citekey}.source.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("Paper body.\n", encoding="utf-8")
    anno_io.write_sidecar(anno_io.sidecar_for_markdown(md), anno_io.Sidecar(annotations=tuple(annotations)))


def _ann(
    annotation_id: str,
    *,
    promoted_to: str,
    status: Status = Status.OPEN,
    annotation_type: str = "proposition",
) -> Annotation:
    created = datetime(2026, 7, 2, tzinfo=timezone.utc)
    non_open = status is not Status.OPEN
    return Annotation(
        id=annotation_id,
        target=SpecificResource(
            source="x.source.md",
            selector=TextQuoteSelector(exact=annotation_id, prefix="", suffix=""),
        ),
        bodies=(TextualBody(value='{"section":"abstract","stance":"asserted"}', format="application/json"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type=annotation_type,
        source="llm-annot:m:paper-annotate-v1",
        status=status,
        creator="paper-annotate",
        created=created,
        content_hash="0" * 64,
        modified=created if non_open else None,
        modified_by="curator" if non_open else None,
        promoted_to=promoted_to,
    )


def _candidate_by_id(report: dict, ref: str) -> dict:
    return next(candidate for candidate in report["candidates"] if candidate["id"] == ref)


def test_dry_run_reports_ready_scalar_superseded_proposition(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")

    report = build_superseded_proposition_archive_report(tmp_path)

    assert report["summary"] == {"ready": 1, "blocked": 0, "skipped": 0}
    candidate = _candidate_by_id(report, "proposition:duplicate")
    assert candidate["status"] == "ready"
    assert candidate["lineage_kind"] == "superseded_by"
    assert candidate["successors"] == ["proposition:canonical"]
    assert candidate["archive_path"] == "entities/_archive/propositions/duplicate.md"
    assert candidate["blocking_annotation_refs"] == []


def test_dry_run_reports_ready_multi_successor_superseded_proposition(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "negative")
    _proposition(tmp_path, "positive")
    _proposition(
        tmp_path,
        "broad",
        status="superseded",
        extra_frontmatter=(
            "resynthesized_into:\n"
            "  - proposition:positive\n"
            "  - proposition:negative\n"
        ),
    )

    report = build_superseded_proposition_archive_report(tmp_path)

    candidate = _candidate_by_id(report, "proposition:broad")
    assert candidate["status"] == "ready"
    assert candidate["lineage_kind"] == "resynthesized_into"
    assert candidate["successors"] == ["proposition:negative", "proposition:positive"]


def test_dry_run_blocks_missing_lineage(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "old", status="superseded")

    report = build_superseded_proposition_archive_report(tmp_path)

    candidate = _candidate_by_id(report, "proposition:old")
    assert candidate["status"] == "blocked"
    assert "missing lineage" in candidate["blockers"]


def test_dry_run_blocks_active_archive_alias_collision(tmp_path: Path) -> None:
    # An active archive row whose *alias* equals the candidate id is not caught by the
    # "archive id already active" check (active_by_id is keyed by canonical id), and
    # load_project_sources does not reject it. Readiness check 9 must still block it.
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")
    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="proposition:ghost",
            aliases=["proposition:duplicate"],
            original_path="entities/_archive/propositions/ghost.md",
            archived_at="T1",
        ),
    )

    report = build_superseded_proposition_archive_report(tmp_path)

    candidate = _candidate_by_id(report, "proposition:duplicate")
    assert candidate["status"] == "blocked"
    assert any("id/alias collision" in blocker for blocker in candidate["blockers"])
```

- [ ] **Step 2: Run reporting tests and confirm RED**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_archive.py::test_dry_run_reports_ready_scalar_superseded_proposition -q
```

Expected: FAIL with `ModuleNotFoundError` or import error for `science_tool.annotation.proposition_archive`.

- [ ] **Step 3: Implement report types and lineage validation**

Create `science/src/science_tool/annotation/proposition_archive.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.archive import (
    ArchiveRow,
    archive_index_path,
    derive_archive_path,
    load_archive_index,
)
from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.entity_scan import iter_entity_markdown
from science_tool.graph.sources import load_project_sources


class PropositionArchiveError(ValueError):
    """Raised when superseded proposition archive cannot proceed safely."""


@dataclass(frozen=True)
class _RawEntity:
    id: str
    kind: str
    path: Path
    relpath: str
    frontmatter: dict[str, Any]


def _raw_entities(project_root: Path) -> dict[str, _RawEntity]:
    rows: dict[str, _RawEntity] = {}
    entities_root = project_root / "entities"
    if not entities_root.is_dir():
        return rows
    for path in iter_entity_markdown(entities_root):
        fm = read_frontmatter(path)
        if not isinstance(fm, dict):
            continue
        raw_id = fm.get("id")
        if not isinstance(raw_id, str) or not raw_id:
            continue
        kind = fm.get("type") or fm.get("kind")
        if not isinstance(kind, str) or not kind:
            continue
        rows[raw_id] = _RawEntity(
            id=raw_id,
            kind=kind,
            path=path,
            relpath=path.relative_to(project_root).as_posix(),
            frontmatter=dict(fm),
        )
    return rows


def _alias_tokens(entity_id: str, frontmatter: dict[str, Any]) -> set[str]:
    tokens = {entity_id}
    for field in ("aliases", "same_as"):
        tokens.update(t for t in (frontmatter.get(field) or []) if isinstance(t, str) and t)
    return tokens


def _collision_owner_index(raw: dict[str, _RawEntity], archive: Any) -> dict[str, set[str]]:
    """token -> owning ids across live entities and ACTIVE archive rows.

    load_project_sources does not reject a live id/alias that collides with an active
    archive id/alias, so this is the archive command's own readiness guard (check 9),
    mirroring `verify_archive` token logic but at archive time.
    """
    owners: dict[str, set[str]] = {}
    for entity_id, entity in raw.items():
        for token in _alias_tokens(entity_id, entity.frontmatter):
            owners.setdefault(token, set()).add(entity_id)
    for archived_id, archived_row in archive.active_by_id.items():
        for token in (archived_id, *archived_row.aliases, *archived_row.same_as):
            owners.setdefault(token, set()).add(archived_id)
    return owners


def _lineage_for_candidate(candidate: _RawEntity, resolvable_ids: set[str]) -> tuple[str | None, list[str], list[str]]:
    fm = candidate.frontmatter
    has_scalar = "superseded_by" in fm
    has_multi = "resynthesized_into" in fm
    blockers: list[str] = []
    if has_scalar and has_multi:
        return None, [], ["declares both superseded_by and resynthesized_into"]
    if not has_scalar and not has_multi:
        return None, [], ["missing lineage"]

    if has_scalar:
        target = fm.get("superseded_by")
        if not isinstance(target, str) or not target:
            return "superseded_by", [], ["malformed superseded_by"]
        successors = [target]
        lineage_kind = "superseded_by"
    else:
        raw_targets = fm.get("resynthesized_into")
        if not isinstance(raw_targets, list) or not raw_targets:
            return "resynthesized_into", [], ["malformed resynthesized_into"]
        successors = []
        for target in raw_targets:
            if not isinstance(target, str) or not target:
                return "resynthesized_into", [], ["malformed resynthesized_into"]
            successors.append(target)
        lineage_kind = "resynthesized_into"

    seen: set[str] = set()
    for target in successors:
        if target == candidate.id:
            blockers.append("lineage points to itself")
        if target in seen:
            blockers.append(f"duplicate successor {target}")
        seen.add(target)
        if target not in resolvable_ids:
            blockers.append(f"unknown successor {target}")
    return lineage_kind, sorted(successors), blockers


def _row_for_candidate(candidate: _RawEntity, lineage_kind: str, successors: list[str]) -> ArchiveRow:
    return ArchiveRow(
        op="archive",
        id=candidate.id,
        kind=candidate.kind,
        title=candidate.frontmatter.get("title") if isinstance(candidate.frontmatter.get("title"), str) else None,
        aliases=[a for a in (candidate.frontmatter.get("aliases") or []) if isinstance(a, str)],
        same_as=[s for s in (candidate.frontmatter.get("same_as") or []) if isinstance(s, str)],
        status="superseded",
        superseded_by=successors[0] if lineage_kind == "superseded_by" else None,
        resynthesized_into=successors if lineage_kind == "resynthesized_into" else [],
        original_path=candidate.relpath,
        reason="status:superseded",
    )


def build_superseded_proposition_archive_report(project_root: Path) -> dict:
    project_root = Path(project_root).resolve()
    sources = load_project_sources(project_root)
    live_ids = {entity.canonical_id or entity.id for entity in sources.entities}
    archive = load_archive_index(project_root)
    resolvable_ids = live_ids | set(archive.resolvable_ids())
    raw = _raw_entities(project_root)
    collision_owners = _collision_owner_index(raw, archive)

    candidates: list[dict[str, Any]] = []
    for ref in sorted(live_ids):
        if not ref.startswith("proposition:"):
            continue
        row = raw.get(ref)
        if row is None or row.frontmatter.get("status") != "superseded":
            continue

        lineage_kind, successors, blockers = _lineage_for_candidate(row, resolvable_ids)
        archive_path = derive_archive_path(row.relpath)
        if (project_root / archive_path).exists():
            blockers.append(f"archive destination exists: {archive_path}")
        if row.id in archive.active_by_id:
            blockers.append(f"archive id already active: {row.id}")
        for token in sorted(_alias_tokens(row.id, row.frontmatter)):
            colliding = collision_owners.get(token, set()) - {row.id}
            if colliding:
                blockers.append(f"id/alias collision on {token}: {sorted(colliding)}")
        status = "ready" if not blockers else "blocked"
        candidates.append(
            {
                "id": row.id,
                "original_path": row.relpath,
                "archive_path": archive_path,
                "lineage_kind": lineage_kind,
                "successors": successors,
                "status": status,
                "blockers": sorted(blockers),
                "blocking_annotation_refs": [],
                "inbound_live_refs": [],
            }
        )

    summary = {
        "ready": sum(1 for candidate in candidates if candidate["status"] == "ready"),
        "blocked": sum(1 for candidate in candidates if candidate["status"] == "blocked"),
        "skipped": 0,
    }
    return {"summary": summary, "candidates": candidates, "applied": [], "skipped": []}


def archive_superseded_propositions(
    project_root: Path,
    *,
    apply: bool = False,
    now: str | None = None,
) -> dict:
    report = build_superseded_proposition_archive_report(project_root)
    if not apply:
        return report
    raise PropositionArchiveError("apply is implemented in Task 5")
```

- [ ] **Step 4: Run dry-run tests**

Run:

```bash
rtk uv run --frozen pytest \
  science/tests/test_proposition_archive.py::test_dry_run_reports_ready_scalar_superseded_proposition \
  science/tests/test_proposition_archive.py::test_dry_run_reports_ready_multi_successor_superseded_proposition \
  science/tests/test_proposition_archive.py::test_dry_run_blocks_missing_lineage \
  science/tests/test_proposition_archive.py::test_dry_run_blocks_active_archive_alias_collision -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/proposition_archive.py science/tests/test_proposition_archive.py
git commit -m "feat(4e): report superseded proposition archive readiness"
```

---

### Task 4: Sidecar Backlink and Inbound Reference Reporting

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_archive.py`
- Test: `science/tests/test_proposition_archive.py`

- [ ] **Step 1: Add RED tests for blockers and inbound refs**

Append these tests to `science/tests/test_proposition_archive.py`:

```python
def test_live_sidecar_backlink_blocks_archive(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")
    _paper_sidecar(tmp_path, "Smith2020", [_ann("a-1", promoted_to="proposition:duplicate")])

    report = build_superseded_proposition_archive_report(tmp_path)

    candidate = _candidate_by_id(report, "proposition:duplicate")
    assert candidate["status"] == "blocked"
    assert candidate["blocking_annotation_refs"] == ["annotation:entities/papers/Smith2020.source#a-1"]
    assert "live annotation backlink" in candidate["blockers"][0]


def test_inactive_sidecar_backlink_does_not_block_archive(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")
    _paper_sidecar(
        tmp_path,
        "Smith2020",
        [_ann("a-1", promoted_to="proposition:duplicate", status=Status.FIXED)],
    )

    report = build_superseded_proposition_archive_report(tmp_path)

    candidate = _candidate_by_id(report, "proposition:duplicate")
    assert candidate["status"] == "ready"
    assert candidate["blocking_annotation_refs"] == []


def test_report_surfaces_generic_inbound_live_refs_as_context(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")
    _entity(
        tmp_path,
        "entities/propositions/observer.md",
        "id: proposition:observer\n"
        "type: proposition\n"
        "title: Observer\n"
        "status: active\n"
        "related:\n"
        "  - proposition:duplicate\n",
    )

    report = build_superseded_proposition_archive_report(tmp_path)

    candidate = _candidate_by_id(report, "proposition:duplicate")
    assert candidate["status"] == "ready"
    assert candidate["inbound_live_refs"] == ["proposition:observer"]
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
rtk uv run --frozen pytest \
  science/tests/test_proposition_archive.py::test_live_sidecar_backlink_blocks_archive \
  science/tests/test_proposition_archive.py::test_inactive_sidecar_backlink_does_not_block_archive \
  science/tests/test_proposition_archive.py::test_report_surfaces_generic_inbound_live_refs_as_context -q
```

Expected: FAIL because sidecars and inbound refs are not scanned yet.

- [ ] **Step 3: Add sidecar and inbound scans**

In `science/src/science_tool/annotation/proposition_archive.py`, add imports:

```python
from science_tool.annotation.io import read_sidecar, sidecar_for_markdown
from science_tool.annotation.model import Status
from science_tool.annotation.query import entity_relpath_for_sidecar
from science_tool.archive import _inbound_live_refs
```

Add constants and helper functions after `_raw_entities`:

```python
_ACTIVE_ANNOTATION_STATUSES = frozenset({Status.OPEN.value, Status.ACK.value})


def _annotation_status_value(status: object) -> str:
    if isinstance(status, Status):
        return status.value
    return str(status)


def _annotation_ref_for_sidecar(project_root: Path, sidecar_path: Path, annotation_id: str) -> str:
    # Reuse the canonical helper so blocker refs match the format that
    # `science annotate cross-paper-evidence` emits (annotation:<relpath>#<id>).
    return f"annotation:{entity_relpath_for_sidecar(sidecar_path, project_root)}#{annotation_id}"


def _live_promoted_backlinks(project_root: Path, candidate_ids: set[str]) -> dict[str, list[str]]:
    backlinks: dict[str, set[str]] = {candidate_id: set() for candidate_id in candidate_ids}
    entities_root = project_root / "entities"
    if not entities_root.is_dir():
        return {candidate_id: [] for candidate_id in candidate_ids}
    for markdown_path in iter_entity_markdown(entities_root):
        sidecar_path = sidecar_for_markdown(markdown_path)
        if not sidecar_path.is_file():
            continue
        try:
            sidecar = read_sidecar(sidecar_path)
        except Exception as exc:
            raise PropositionArchiveError(f"could not read sidecar {sidecar_path}: {exc}") from exc
        for ann in sidecar.annotations:
            if ann.annotation_type != "proposition":
                continue
            promoted_to = ann.promoted_to
            if promoted_to not in candidate_ids:
                continue
            if _annotation_status_value(ann.status) not in _ACTIVE_ANNOTATION_STATUSES:
                continue
            backlinks[promoted_to].add(_annotation_ref_for_sidecar(project_root, sidecar_path, ann.id))
    return {candidate_id: sorted(refs) for candidate_id, refs in backlinks.items()}
```

Then in `build_superseded_proposition_archive_report`, after `raw = _raw_entities(project_root)`, add:

```python
    candidate_ids = {
        ref
        for ref in live_ids
        if ref.startswith("proposition:")
        and ref in raw
        and raw[ref].frontmatter.get("status") == "superseded"
    }
    backlinks = _live_promoted_backlinks(project_root, candidate_ids)
    inbound = _inbound_live_refs(project_root, candidate_ids)
```

Inside the candidate loop, after destination/archive-id blockers, add:

```python
        annotation_refs = backlinks.get(row.id, [])
        if annotation_refs:
            blockers.append(f"live annotation backlink(s): {', '.join(annotation_refs)}")
```

Then replace the candidate fields:

```python
                "blocking_annotation_refs": [],
                "inbound_live_refs": [],
```

with:

```python
                "blocking_annotation_refs": annotation_refs,
                "inbound_live_refs": inbound.get(row.id, []),
```

- [ ] **Step 4: Run reporting tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_archive.py -q
```

Expected: PASS for all dry-run/reporting tests currently in the file.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/proposition_archive.py science/tests/test_proposition_archive.py
git commit -m "feat(4e): block archive on live annotation backlinks"
```

---

### Task 5: Apply Relocation and Postflight

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_archive.py`
- Test: `science/tests/test_proposition_archive.py`

- [ ] **Step 1: Add RED apply tests**

Append these tests to `science/tests/test_proposition_archive.py`:

```python
def test_apply_moves_ready_proposition_and_writes_scalar_archive_row(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    original = _proposition(
        tmp_path,
        "duplicate",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:canonical\n",
    )

    report = archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:00:00Z")

    assert report["applied"] == ["proposition:duplicate"]
    assert not original.exists()
    archived = tmp_path / derive_archive_path("entities/propositions/duplicate.md")
    assert archived.exists()
    row = load_archive_index(tmp_path).active_by_id["proposition:duplicate"]
    assert row.superseded_by == "proposition:canonical"
    assert row.resynthesized_into == []
    assert row.archived_at == "2026-07-02T12:00:00Z"


def test_apply_moves_ready_proposition_and_writes_resynthesis_archive_row(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "negative")
    _proposition(tmp_path, "positive")
    original = _proposition(
        tmp_path,
        "broad",
        status="superseded",
        extra_frontmatter=(
            "resynthesized_into:\n"
            "  - proposition:positive\n"
            "  - proposition:negative\n"
        ),
    )

    report = archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:00:00Z")

    assert report["applied"] == ["proposition:broad"]
    assert not original.exists()
    row = load_archive_index(tmp_path).active_by_id["proposition:broad"]
    assert row.superseded_by is None
    assert row.resynthesized_into == ["proposition:negative", "proposition:positive"]


def test_apply_moves_ready_candidates_and_leaves_blocked_candidates_live(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    ready = _proposition(tmp_path, "ready", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")
    blocked = _proposition(tmp_path, "blocked", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")
    _paper_sidecar(tmp_path, "Smith2020", [_ann("a-1", promoted_to="proposition:blocked")])

    report = archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:00:00Z")

    assert report["applied"] == ["proposition:ready"]
    assert not ready.exists()
    assert blocked.exists()
    assert set(load_archive_index(tmp_path).active_by_id) == {"proposition:ready"}


def test_apply_is_idempotent_after_success(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")
    archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:00:00Z")

    report = archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:01:00Z")

    assert report["summary"] == {"ready": 0, "blocked": 0, "skipped": 0}
    assert report["applied"] == []
```

- [ ] **Step 2: Run apply tests and confirm RED**

Run:

```bash
rtk uv run --frozen pytest \
  science/tests/test_proposition_archive.py::test_apply_moves_ready_proposition_and_writes_scalar_archive_row \
  science/tests/test_proposition_archive.py::test_apply_moves_ready_proposition_and_writes_resynthesis_archive_row \
  science/tests/test_proposition_archive.py::test_apply_moves_ready_candidates_and_leaves_blocked_candidates_live \
  science/tests/test_proposition_archive.py::test_apply_is_idempotent_after_success -q
```

Expected: FAIL because `archive_superseded_propositions(..., apply=True)` still raises the temporary Task 3 error.

- [ ] **Step 3: Add row reconstruction and postflight helpers**

In `science/src/science_tool/annotation/proposition_archive.py`, extend the archive import:

```python
from science_tool.archive import (
    ArchiveRow,
    _relocate_rows,
    archive_index_path,
    derive_archive_path,
    load_archive_index,
)
```

Add this helper below `_row_for_candidate`:

```python
def _rows_for_ready_candidates(project_root: Path, report: dict) -> list[ArchiveRow]:
    raw = _raw_entities(project_root)
    rows: list[ArchiveRow] = []
    for candidate in report["candidates"]:
        if candidate["status"] != "ready":
            continue
        raw_entity = raw.get(candidate["id"])
        if raw_entity is None:
            raise PropositionArchiveError(f"{candidate['id']} disappeared before archive apply")
        lineage_kind = candidate["lineage_kind"]
        successors = candidate["successors"]
        if lineage_kind not in {"superseded_by", "resynthesized_into"}:
            raise PropositionArchiveError(f"{candidate['id']} has invalid lineage kind at apply")
        rows.append(_row_for_candidate(raw_entity, lineage_kind, successors))
    return rows
```

Add this postflight helper:

```python
def _postflight(project_root: Path, rows: list[ArchiveRow]) -> None:
    from science_tool.graph.materialize import materialize_graph

    index = load_archive_index(project_root)
    for row in rows:
        if row.id not in index.active_by_id:
            raise PropositionArchiveError(f"{row.id} missing from archive index after apply")
        assert row.original_path is not None
        live_path = project_root / row.original_path
        archive_path = project_root / derive_archive_path(row.original_path)
        if live_path.exists():
            raise PropositionArchiveError(f"{row.id} live file still exists after archive apply")
        if not archive_path.exists():
            raise PropositionArchiveError(f"{row.id} archived file missing after archive apply")
    try:
        materialize_graph(project_root, strict=False)
    except Exception as exc:
        raise PropositionArchiveError(f"postflight materialization failed: {exc}") from exc
```

- [ ] **Step 4: Implement apply**

Replace `archive_superseded_propositions` with:

```python
def archive_superseded_propositions(
    project_root: Path,
    *,
    apply: bool = False,
    now: str | None = None,
) -> dict:
    project_root = Path(project_root).resolve()
    report = build_superseded_proposition_archive_report(project_root)
    if not apply:
        return report

    rows = _rows_for_ready_candidates(project_root, report)
    if not rows:
        return report

    result = _relocate_rows(archive_index_path(project_root), project_root, rows, now=now)
    report["applied"] = result["applied"]
    report["skipped"] = result["skipped"]
    _postflight(project_root, rows)
    return report
```

- [ ] **Step 5: Run apply tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_archive.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/proposition_archive.py science/tests/test_proposition_archive.py
git commit -m "feat(4e): archive ready superseded propositions"
```

---

### Task 6: Graph Stability Before and After Proposition Archive

**Files:**
- Modify: `science/tests/test_proposition_archive.py`

- [ ] **Step 1: Add end-to-end graph stability tests**

Add imports near the top of `science/tests/test_proposition_archive.py`:

```python
from rdflib import Dataset
from rdflib.namespace import RDF

from science_tool.graph.store import PROJECT_NS, SCI_NS
```

Add helpers near `_candidate_by_id`:

```python
def _knowledge_graph(root: Path):
    from science_tool.graph.materialize import materialize_graph

    out_path = materialize_graph(root, strict=False)
    dataset = Dataset()
    dataset.parse(source=str(out_path), format="trig")
    return dataset.graph(PROJECT_NS["graph/knowledge"])


def _entity_uri(ref: str):
    kind, slug = ref.split(":", 1)
    return PROJECT_NS[f"{kind}/{slug}"]
```

Append these tests:

```python
def test_scalar_lineage_graph_triple_survives_archive_movement(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")

    before = _knowledge_graph(tmp_path)
    archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:00:00Z")
    after = _knowledge_graph(tmp_path)

    triple = (
        _entity_uri("proposition:duplicate"),
        SCI_NS.supersededBy,
        _entity_uri("proposition:canonical"),
    )
    assert triple in before
    assert triple in after
    assert (_entity_uri("proposition:duplicate"), RDF.type, SCI_NS.ArchivedEntity) in after


def test_multi_successor_graph_triples_survive_archive_movement(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "negative")
    _proposition(tmp_path, "positive")
    _proposition(
        tmp_path,
        "broad",
        status="superseded",
        extra_frontmatter=(
            "resynthesized_into:\n"
            "  - proposition:positive\n"
            "  - proposition:negative\n"
        ),
    )

    before = _knowledge_graph(tmp_path)
    archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:00:00Z")
    after = _knowledge_graph(tmp_path)

    broad = _entity_uri("proposition:broad")
    expected = {_entity_uri("proposition:negative"), _entity_uri("proposition:positive")}
    assert set(before.objects(broad, SCI_NS.supersededBy)) == expected
    assert set(after.objects(broad, SCI_NS.supersededBy)) == expected
    assert (broad, RDF.type, SCI_NS.ArchivedEntity) in after
```

- [ ] **Step 2: Run graph stability tests**

Run:

```bash
rtk uv run --frozen pytest \
  science/tests/test_proposition_archive.py::test_scalar_lineage_graph_triple_survives_archive_movement \
  science/tests/test_proposition_archive.py::test_multi_successor_graph_triples_survive_archive_movement -q
```

Expected: PASS. If this fails, inspect whether Task 2 lineage seeding is missing or whether postflight materialization is failing before assertions.

- [ ] **Step 3: Commit**

```bash
git add science/tests/test_proposition_archive.py
git commit -m "test(4e): pin archive lineage graph stability"
```

---

### Task 7: CLI Surface

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Create: `science/tests/test_proposition_archive_cli.py`

- [ ] **Step 1: Add RED CLI tests**

Create `science/tests/test_proposition_archive_cli.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.archive import load_archive_index


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: test\n", encoding="utf-8")


def _proposition(root: Path, slug: str, *, status: str = "active", extra_frontmatter: str = "") -> Path:
    path = root / "entities" / "propositions" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"id: proposition:{slug}\n"
        "type: proposition\n"
        f"title: {slug}\n"
        f"status: {status}\n"
        f"{extra_frontmatter}"
        "---\n"
        "Claim.\n",
        encoding="utf-8",
    )
    return path


def test_archive_superseded_propositions_cli_json_dry_run(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")

    result = CliRunner().invoke(
        main,
        ["annotate", "archive-superseded-propositions", "--root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"] == {"ready": 1, "blocked": 0, "skipped": 0}
    assert payload["candidates"][0]["id"] == "proposition:duplicate"
    assert load_archive_index(tmp_path).active_by_id == {}


def test_archive_superseded_propositions_cli_apply_moves_ready_candidate(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")

    result = CliRunner().invoke(
        main,
        ["annotate", "archive-superseded-propositions", "--root", str(tmp_path), "--apply", "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["applied"] == ["proposition:duplicate"]
    assert "proposition:duplicate" in load_archive_index(tmp_path).active_by_id
```

- [ ] **Step 2: Run CLI tests and confirm RED**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_archive_cli.py -q
```

Expected: FAIL because the Click command does not exist.

- [ ] **Step 3: Add the Click command**

In `science/src/science_tool/annotation/cli.py`, add this command after `cross_paper_evidence_cmd`:

```python
@annotate_group.command("archive-superseded-propositions")
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--apply", "apply_changes", is_flag=True, default=False)
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def archive_superseded_propositions_cmd(root: Path | None, apply_changes: bool, fmt: str) -> None:
    """Archive 4e-ready superseded propositions after evidence-backlink checks."""
    from datetime import datetime, timezone

    from science_tool.annotation.proposition_archive import (
        PropositionArchiveError,
        archive_superseded_propositions,
    )
    from science_tool.archive import ArchiveError

    project_root = (root or Path.cwd()).resolve()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        payload = archive_superseded_propositions(project_root, apply=apply_changes, now=now)
    except (PropositionArchiveError, ArchiveError) as exc:
        # ArchiveError escapes from `_relocate_rows` on a destination-collision race or
        # an index-write failure (after the move is rolled back); surface it cleanly.
        raise click.ClickException(str(exc)) from exc

    if fmt == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    summary = payload["summary"]
    mode = "apply" if apply_changes else "dry-run"
    click.echo(
        "superseded proposition archive "
        f"({mode}): ready={summary['ready']} blocked={summary['blocked']} skipped={summary['skipped']}"
    )
    for candidate in payload["candidates"]:
        click.echo(
            f"{candidate['status']:8s} {candidate['id']} "
            f"{candidate['lineage_kind'] or '-'} -> {','.join(candidate['successors']) or '-'}"
        )
        for blocker in candidate["blockers"]:
            click.echo(f"  blocker: {blocker}")
        if candidate["inbound_live_refs"]:
            click.echo(f"  inbound refs: {','.join(candidate['inbound_live_refs'])}")
    if payload["applied"]:
        click.echo(f"applied: {','.join(payload['applied'])}")
    if payload["skipped"]:
        click.echo(f"skipped: {','.join(payload['skipped'])}")
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_archive_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/cli.py science/tests/test_proposition_archive_cli.py
git commit -m "feat(4e): add superseded proposition archive CLI"
```

---

### Task 8: Full Verification and Review Prep

**Files:**
- Verify only unless a failure identifies a concrete bug in touched files.

- [ ] **Step 1: Run focused archive and lineage suites**

Run:

```bash
rtk uv run --frozen pytest \
  science/tests/test_archive_index.py \
  science/tests/test_archive_mutators.py \
  science/tests/test_archive_resolution_graph.py \
  science/tests/test_live_lineage_visibility_graph.py \
  science/tests/test_proposition_archive.py \
  science/tests/test_proposition_archive_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run adjacent reconciliation/resynthesis suites**

Run:

```bash
rtk uv run --frozen pytest \
  science/tests/test_proposition_reconciliation_apply.py \
  science/tests/test_proposition_resynthesis_apply.py \
  science/tests/test_cross_paper_evidence.py -q
```

Expected: PASS.

- [ ] **Step 3: Run the full suite to catch the global materialization change**

The Task 2 lineage seeding is NOT proposition-scoped: it makes *every* active archive
row with a resolvable `superseded_by`/`resynthesized_into` emit a tombstone stub and
`sci:supersededBy`, including pre-existing rows produced by generic `science entities
archive`. Any test that materializes a graph containing an already-archived entity with
a resolvable scalar successor can gain triples. Focused suites do not cover that blast
radius (health, big-picture, and P3/P4 consolidation suites archive entities and snapshot
graphs), so run the whole suite once:

```bash
rtk uv run --frozen pytest science/tests -q
```

Expected: PASS. If a pre-existing graph-snapshot test now sees an added `ArchivedEntity`
stub or `sci:supersededBy` edge for an already-archived entity, re-baseline that
assertion — the new triples are the intended, more-correct rendering per the design.
Do NOT suppress the emission to make an old snapshot pass. If a failure is instead a real
regression (e.g. a strict `resynthesized_into` raise firing on unexpected data), fix the
code, not the test.

- [ ] **Step 4: Run lint and type checks**

Run:

```bash
rtk uv run --frozen ruff check science/src/science_tool/archive.py \
  science/src/science_tool/graph/materialize.py \
  science/src/science_tool/annotation/proposition_archive.py \
  science/src/science_tool/annotation/cli.py \
  science/tests/test_archive_index.py \
  science/tests/test_archive_mutators.py \
  science/tests/test_archive_resolution_graph.py \
  science/tests/test_proposition_archive.py \
  science/tests/test_proposition_archive_cli.py
rtk uv run --frozen pyright science/src/science_tool/archive.py \
  science/src/science_tool/graph/materialize.py \
  science/src/science_tool/annotation/proposition_archive.py \
  science/src/science_tool/annotation/cli.py
```

Expected: both commands exit 0.

- [ ] **Step 5: Inspect final diff**

Run:

```bash
git diff --stat
git diff -- science/src/science_tool/archive.py science/src/science_tool/graph/materialize.py science/src/science_tool/annotation/proposition_archive.py science/src/science_tool/annotation/cli.py
```

Expected:
- `archive.py` only adds `resynthesized_into` preservation and report exposure.
- `materialize.py` only adds archive-row lineage seeding/emission.
- `proposition_archive.py` owns all sidecar-specific readiness logic.
- `cli.py` only adds the flat `archive-superseded-propositions` command.

- [ ] **Step 6: Commit verification fixes if any**

If Step 1-4 found a bug and you changed code, commit it:

```bash
git add science/src/science_tool science/tests
git commit -m "fix(4e): tighten superseded proposition archive"
```

If no code changed, do not create an empty commit.

---

## Self-Review Checklist

- Spec coverage:
  - Archive row preserves `resynthesized_into`: Task 1.
  - Unreferenced archived lineage stays graph-visible: Task 2.
  - Archived-to-archived lineage emits successor stubs: Task 2.
  - Readiness checks 1-8 (lineage shape/validity, sidecar backlink, destination): Tasks 3-4.
  - Readiness check 9 (id/alias collision vs live entities and active archive rows,
    which load_project_sources does NOT reject): Task 3, `_collision_owner_index`.
  - 4e-specific sidecar backlink blockers: Task 4.
  - Report/apply command with deterministic JSON and timestamp only on apply rows: Tasks 3, 5, 7.
  - Graph stability before/after archive movement: Task 6.
  - Generic archive command remains content-agnostic: Task 1 only preserves raw fields; Task 4 sidecar logic lives in `annotation/proposition_archive.py`.
  - Full-suite verification for the global (non-proposition-scoped) materialization change: Task 8 Step 3.
- Fail-loud split (design §4 vs §10): candidate-level lineage/collision problems are
  reported as `status: blocked` (never silently dropped, never an exception) so the user
  can fix frontmatter; the graph layer (Task 2) still hard-raises on malformed/unresolved
  archived `resynthesized_into`, and apply-time filesystem/index faults raise
  `ArchiveError` (caught by the CLI in Task 7).
- Placeholder scan:
  - No task uses forbidden placeholder wording or unspecified validation.
  - Every code-changing step names exact files and snippets.
- Type consistency:
  - Public functions: `build_superseded_proposition_archive_report(project_root: Path) -> dict` and `archive_superseded_propositions(project_root: Path, *, apply: bool = False, now: str | None = None) -> dict`.
  - Error type: `PropositionArchiveError`.
  - CLI command imports those exact names.
