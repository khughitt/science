# Phase 4e Live Lineage Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make live `superseded_by` and `resynthesized_into` proposition frontmatter graph-visible as `sci:supersededBy` edges while preserving current archive tombstone behavior.

**Architecture:** Materialization will read live lineage from the raw markdown frontmatter already present in `ProjectSources.markdown_documents`, reconcile each owner with the typed `entity_index`, validate lineage shape fail-loud, and emit edges into the knowledge graph. The typed entity model stays unchanged; this is a graph-only, read-only phase.

**Tech Stack:** Python, rdflib `Dataset`, existing `science_tool.graph.materialize`, existing `ProjectSources.markdown_documents`, pytest, ruff, pyright.

---

## Design Reference

Implement:

- `docs/plans/2026-07-02-phase4e-live-lineage-visibility-design.md`

Key requirements:

- Use existing `SCI_NS.supersededBy`.
- Read `superseded_by` and `resynthesized_into` from raw frontmatter, not typed entity fields.
- Require lineage owners to be loaded live entities in `entity_index`.
- Require lineage fields only on `status: superseded`.
- Fail loud on malformed targets, dangling targets, duplicate targets, self-supersession, and both lineage fields on one owner.
- Preserve existing archive-index `superseded_by` behavior.
- Audit graph consumers before implementation.

## File Structure

Modify:

- `science/src/science_tool/graph/materialize.py`
  - Add live-lineage validation/emission helper functions.
  - Call the helper in `_emit_phase` after authored relation emission and before archive tombstone emission.
  - Keep archive tombstone code unchanged except for sharing `referenced_archived` with live-lineage archived targets.

Create:

- `science/tests/test_live_lineage_visibility_graph.py`
  - End-to-end materialization tests for live `superseded_by`, live `resynthesized_into`, invalid live lineage, archive target resolution, and owner/raw-frontmatter mismatch.

Do not modify:

- Half C/D apply modules.
- Entity Pydantic models.
- Belief aggregation.
- Archive storage behavior.

## Task 1: Consumer Audit And Red Graph Tests

**Files:**

- Create: `science/tests/test_live_lineage_visibility_graph.py`
- Read-only audit: `science/src/**`

- [ ] **Step 1: Audit graph consumers before changing graph content**

Run:

```bash
rtk rg -n "supersededBy|SCI_NS\\.supersededBy|sci:supersededBy" science/src -g '*.py'
```

Expected before implementation:

```text
science/src/science_tool/graph/materialize.py:273:            knowledge.add((uri, SCI_NS.supersededBy, _entity_uri(row.superseded_by)))
```

If any resolver, health, belief, query, or graph validation code reads `supersededBy`, stop and review that consumer before continuing. The design's consumer-neutrality claim depends on this audit.

- [ ] **Step 2: Add failing end-to-end graph tests**

Create `science/tests/test_live_lineage_visibility_graph.py` with this content:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.archive import ArchiveRow, append_row, archive_index_path

rdflib = pytest.importorskip("rdflib")


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )


def _proposition(
    root: Path,
    slug: str,
    title: str | None = None,
    *,
    status: str = "active",
    extra_frontmatter: str = "",
    kind: str = "proposition",
) -> Path:
    path = root / "entities" / "propositions" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"id: proposition:{slug}\n"
        f"type: {kind}\n"
        f"title: {title or slug}\n"
        f"status: {status}\n"
        f"{extra_frontmatter}"
        "---\n\n"
        "Claim.\n",
        encoding="utf-8",
    )
    return path


def _build_graph_text(root: Path) -> str:
    from science_tool.graph.materialize import materialize_graph

    out_path = materialize_graph(root, strict=False)
    return out_path.read_text(encoding="utf-8")


def test_live_superseded_without_lineage_is_graph_neutral(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "old", status="superseded")
    _proposition(tmp_path, "new")

    text = _build_graph_text(tmp_path)

    assert "supersededBy" not in text


def test_live_superseded_by_emits_superseded_by_edge(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(
        tmp_path,
        "old",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:new\n",
    )
    _proposition(tmp_path, "new")

    text = _build_graph_text(tmp_path)

    assert "supersededBy" in text
    assert "proposition/old" in text
    assert "proposition/new" in text


def test_live_resynthesized_into_emits_one_superseded_by_edge_per_target(tmp_path: Path) -> None:
    _seed(tmp_path)
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
    _proposition(tmp_path, "positive")
    _proposition(tmp_path, "negative")

    text = _build_graph_text(tmp_path)

    assert text.count("supersededBy") == 2
    assert "proposition/broad" in text
    assert "proposition/positive" in text
    assert "proposition/negative" in text


def test_live_lineage_can_target_active_archived_entity(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(
        tmp_path,
        "old",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:archived-successor\n",
    )
    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="proposition:archived-successor",
            kind="proposition",
            title="Archived successor",
            original_path="entities/propositions/archived-successor.md",
            archived_at="T1",
        ),
    )

    text = _build_graph_text(tmp_path)

    assert "supersededBy" in text
    assert "archived-successor" in text
    assert "ArchivedEntity" in text


@pytest.mark.parametrize(
    ("extra_frontmatter", "match"),
    [
        ("superseded_by: proposition:new\n", "status"),
        (
            "superseded_by: proposition:new\n"
            "resynthesized_into:\n"
            "  - proposition:other\n",
            "both superseded_by and resynthesized_into",
        ),
    ],
)
def test_live_lineage_rejects_invalid_owner_state(
    tmp_path: Path,
    extra_frontmatter: str,
    match: str,
) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "old", status="active", extra_frontmatter=extra_frontmatter)
    _proposition(tmp_path, "new")
    _proposition(tmp_path, "other")

    with pytest.raises(ValueError, match=match):
        _build_graph_text(tmp_path)


@pytest.mark.parametrize(
    ("extra_frontmatter", "match"),
    [
        ("superseded_by: proposition:missing\n", "unknown live lineage target"),
        (
            "resynthesized_into:\n"
            "  - proposition:new\n"
            "  - proposition:new\n",
            "duplicate",
        ),
        ("superseded_by: proposition:old\n", "cannot supersede itself"),
        ("superseded_by:\n", "malformed superseded_by"),
        ("resynthesized_into: proposition:new\n", "malformed resynthesized_into"),
    ],
)
def test_live_lineage_rejects_invalid_targets(
    tmp_path: Path,
    extra_frontmatter: str,
    match: str,
) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "old", status="superseded", extra_frontmatter=extra_frontmatter)
    _proposition(tmp_path, "new")

    with pytest.raises(ValueError, match=match):
        _build_graph_text(tmp_path)


def test_live_lineage_rejects_raw_owner_not_loaded_as_live_entity(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(
        tmp_path,
        "old",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:new\n",
        kind="not-a-real-kind",
    )
    _proposition(tmp_path, "new")

    with pytest.raises(ValueError, match="not a loaded live entity"):
        _build_graph_text(tmp_path)
```

- [ ] **Step 3: Run the new tests and verify they fail for missing live lineage**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_live_lineage_visibility_graph.py -q
```

Expected before implementation:

- `test_live_superseded_by_emits_superseded_by_edge` fails because `"supersededBy"` is not emitted for live frontmatter.
- `test_live_resynthesized_into_emits_one_superseded_by_edge_per_target` fails for the same reason.
- Invalid-lineage tests may fail with `DID NOT RAISE`.

Do not commit failing tests.

## Task 2: Implement Live Lineage Emission

**Files:**

- Modify: `science/src/science_tool/graph/materialize.py`
- Test: `science/tests/test_live_lineage_visibility_graph.py`

- [ ] **Step 1: Add imports for raw frontmatter typing**

In `science/src/science_tool/graph/materialize.py`, change:

```python
from collections.abc import Iterable
```

to:

```python
from collections.abc import Iterable, Mapping
```

- [ ] **Step 2: Add live lineage helper functions**

In `science/src/science_tool/graph/materialize.py`, add this block immediately after `_archived_uri_if_active`:

```python
_LIVE_LINEAGE_FIELDS = ("superseded_by", "resynthesized_into")


def _has_live_lineage(frontmatter: Mapping[str, object]) -> bool:
    return any(field in frontmatter for field in _LIVE_LINEAGE_FIELDS)


def _lineage_context(owner: str | None, path: str) -> str:
    if owner:
        return f"{owner} ({path})"
    return f"<missing id> ({path})"


def _live_lineage_targets(owner: str, path: str, frontmatter: Mapping[str, object]) -> tuple[str, ...]:
    has_superseded_by = "superseded_by" in frontmatter
    has_resynthesized_into = "resynthesized_into" in frontmatter
    context = _lineage_context(owner, path)

    if has_superseded_by and has_resynthesized_into:
        raise ValueError(f"live lineage {context} cannot declare both superseded_by and resynthesized_into")

    status = frontmatter.get("status")
    if status != "superseded":
        fields = ", ".join(field for field in _LIVE_LINEAGE_FIELDS if field in frontmatter)
        raise ValueError(f"live lineage {context} declares {fields} but status is {status!r}, expected 'superseded'")

    if has_superseded_by:
        target = frontmatter.get("superseded_by")
        if not isinstance(target, str) or not target:
            raise ValueError(f"live lineage {context} has malformed superseded_by")
        targets = (target,)
    elif has_resynthesized_into:
        raw_targets = frontmatter.get("resynthesized_into")
        if not isinstance(raw_targets, list) or not raw_targets:
            raise ValueError(f"live lineage {context} has malformed resynthesized_into")
        bad_targets = [target for target in raw_targets if not isinstance(target, str) or not target]
        if bad_targets:
            raise ValueError(f"live lineage {context} has malformed resynthesized_into")
        targets = tuple(raw_targets)
    else:
        return ()

    seen: set[str] = set()
    for target in targets:
        if target == owner:
            raise ValueError(f"live lineage {context} cannot supersede itself")
        if target in seen:
            raise ValueError(f"live lineage {context} has duplicate successor {target}")
        seen.add(target)
    return targets


def _add_live_lineage_edges(
    sources: ProjectSources,
    *,
    entity_index: Mapping[str, Entity],
    archive_active: Mapping[str, object],
    referenced_archived: set[str],
    knowledge,
) -> None:
    for document in sorted(sources.markdown_documents, key=lambda doc: doc.path):
        frontmatter = document.frontmatter
        if not _has_live_lineage(frontmatter):
            continue

        raw_owner = frontmatter.get("id")
        owner = raw_owner if isinstance(raw_owner, str) and raw_owner else None
        context = _lineage_context(owner, document.path)
        if owner is None:
            raise ValueError(f"live lineage owner {context} has missing or invalid id")
        if owner not in entity_index:
            raise ValueError(f"live lineage owner {context} is not a loaded live entity")

        for target in _live_lineage_targets(owner, document.path, frontmatter):
            if target not in entity_index and target not in archive_active:
                raise ValueError(f"live lineage {context} points to unknown live lineage target {target}")
            if target in archive_active:
                referenced_archived.add(target)
            knowledge.add((_entity_uri(owner), SCI_NS.supersededBy, _entity_uri(target)))
```

Why this shape:

- `document.frontmatter` is the raw source of truth for `superseded_by` and `resynthesized_into`.
- `owner not in entity_index` catches raw-vs-typed mismatch.
- Adding archived targets to `referenced_archived` preserves tombstone stub emission for lineage targets that resolve through the archive index.

- [ ] **Step 3: Call the helper before archive tombstone emission**

In `_emit_phase`, after the authored relation loop and before the comment `# Emit one tombstone stub node per referenced active archived id`, add:

```python
    _add_live_lineage_edges(
        sources,
        entity_index=entity_index,
        archive_active=archive_active,
        referenced_archived=referenced_archived,
        knowledge=knowledge,
    )
```

The surrounding code should look like this:

```python
    for relation in sources.relations:
        _add_authored_relation(
            relation,
            dataset=dataset,
            entity_index=entity_index,
            resolver=resolver,
            bridge=bridge,
            ontology_catalogs=sources.ontology_catalogs,
            ext_prefixes=ext_prefixes,
            kind_class=kind_class,
            archive_active=archive_active,
            referenced_archived=referenced_archived,
        )

    _add_live_lineage_edges(
        sources,
        entity_index=entity_index,
        archive_active=archive_active,
        referenced_archived=referenced_archived,
        knowledge=knowledge,
    )

    # Emit one tombstone stub node per referenced active archived id into the
```

- [ ] **Step 4: Run the new test file and verify it passes**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_live_lineage_visibility_graph.py -q
```

Expected: PASS.

- [ ] **Step 5: Run the existing archive lineage test**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_archive_resolution_graph.py -q
```

Expected: PASS. This confirms archive-index tombstone lineage still emits.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
rtk git add science/src/science_tool/graph/materialize.py science/tests/test_live_lineage_visibility_graph.py
rtk git commit -m "feat(4e): materialize live proposition lineage"
```

## Task 3: Affected Verification And Cleanup

**Files:**

- Verify: `science/src/science_tool/graph/materialize.py`
- Verify: `science/tests/test_live_lineage_visibility_graph.py`
- Verify: `science/tests/test_archive_resolution_graph.py`
- Verify: `science/tests/test_graph_build_strict.py`

- [ ] **Step 1: Re-run the consumer audit after implementation**

Run:

```bash
rtk rg -n "supersededBy|SCI_NS\\.supersededBy|sci:supersededBy" science/src -g '*.py'
```

Expected:

- `science/src/science_tool/graph/materialize.py` contains the archive tombstone writer.
- `science/src/science_tool/graph/materialize.py` contains the new live lineage writer.
- No resolver, health, belief, query, or graph validation code reads the predicate as control flow.

If a consumer appears, stop and review whether it assumes `supersededBy` subjects are archived.

- [ ] **Step 2: Run focused graph tests**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_live_lineage_visibility_graph.py \
  science/tests/test_archive_resolution_graph.py \
  science/tests/test_graph_build_strict.py \
  -q
```

Expected: PASS.

- [ ] **Step 3: Run broader materialization tests likely to catch graph regressions**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_graph_materialize.py \
  science/tests/test_graph_cli.py \
  science/tests/test_archive_resolution_graph.py \
  -q
```

Expected: PASS.

- [ ] **Step 4: Run static checks**

Run:

```bash
rtk uv run --frozen --project science ruff check \
  science/src/science_tool/graph/materialize.py \
  science/tests/test_live_lineage_visibility_graph.py
```

Expected:

```text
All checks passed!
```

Run:

```bash
rtk uv run --frozen --project science pyright science/src/science_tool/graph/materialize.py
```

Expected:

```text
0 errors, 0 warnings, 0 informations
```

- [ ] **Step 5: Check git state**

Run:

```bash
rtk git status --short
```

Expected:

- clean if Task 2 was committed and no unrelated files are present; or
- only known unrelated user files are listed.

Do not stage or revert unrelated files.

## Acceptance Checklist

- [ ] Live `status: superseded` + `superseded_by` emits `sci:supersededBy`.
- [ ] Live `status: superseded` + `resynthesized_into` emits one `sci:supersededBy` edge per target.
- [ ] Live `status: superseded` without lineage remains graph-neutral.
- [ ] Live lineage owners must exist in `entity_index`.
- [ ] Live lineage targets must resolve to a live entity or active archived id.
- [ ] Archived targets referenced by live lineage get tombstone stubs.
- [ ] Invalid live lineage fails materialization with actionable errors.
- [ ] Existing archive-index lineage behavior remains unchanged.
- [ ] No Half C/D apply code changes.
- [ ] Consumer audit confirms no current graph consumer treats `sci:supersededBy` as archive-only control flow.

## Notes For Implementers

- Work in an isolated worktree when executing this plan.
- Keep the raw-frontmatter helper private to `materialize.py`.
- Do not add a typed `resynthesized_into` field to entity models in this phase.
- Do not add `sci:resynthesizedInto`.
- Do not silently skip dangling live lineage. Live frontmatter drift should block materialization.
