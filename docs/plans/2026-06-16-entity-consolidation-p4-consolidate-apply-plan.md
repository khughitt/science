# Entity Consolidation P4 — `entities consolidate` (Tier 3 cluster digest) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-step, opt-in, reversible `science entities consolidate` command that collapses a human-chosen cluster of live entities into one canonical `cluster-digest` synthesis entity plus N archived originals, reusing P3's archive index/relocation machinery.

**Architecture:** A new `consolidate.py` apply-module orchestrates: validate members → `scaffold` mints a live digest (create-then-rewrite, atomic) carrying a typed `sci:consolidates` authored relation per member → `apply` stamps each member `status: archived` + `consolidated_into`, relocates it via a shared `archive._relocate_rows` primitive, and appends an index row. The digest→member link is a typed authored relation (archive-aware emission already exists from P3); the member→digest `consolidated_into` is provenance-only (frontmatter + index, never emitted).

**Tech Stack:** Python 3.13, Pydantic v2, Click, pytest, rdflib (TriG named graphs), PyYAML.

---

## Working conventions (read first)

- **Worktree:** all work happens in
  `~/d/science/.worktrees/entity-consolidation-p4-consolidate-apply`
  on branch `feat/entity-consolidation-p4-consolidate-apply`. **Subagents: `cd`
  into this worktree path and confirm `git branch --show-current` before editing —
  commits must not land on `main`.**
- **The package lives under `science/`** inside the worktree. Source is
  `science/src/science_tool/...` and `science/model/src/science_model/...`; tests
  are `science/tests/...`.
- **Test command** (the worktree has no `.venv`; use the main repo's venv with
  `PYTHONPATH=src`), run from the `science/` subdir:
  ```bash
  cd ~/d/science/.worktrees/entity-consolidation-p4-consolidate-apply/science
  PYTHONPATH=src ~/d/science/science/.venv/bin/pytest <path> -v
  ```
- **Commits:** do NOT include any `Co-Authored-By` trailer. One commit per task.
- **rtk:** shell commands are auto-rewritten through the `rtk` proxy by the Claude
  Code hook (transparent — `pytest …` → `rtk pytest …`). Run the commands as
  written below; do **not** hand-prefix `rtk` yourself (that would double it).
- **Design reference:** `docs/plans/2026-06-16-entity-consolidation-p4-consolidate-apply-design.md`.

## File Structure

- **Create `science/src/science_tool/consolidate.py`** — the Tier-3 *apply* half:
  `ConsolidateError`, `scaffold_digest(...)`, `apply_consolidation(...)`, and the
  member validation helpers. Distinct from the read-only detector
  `consolidation.py`; never imports it.
- **Modify `science/src/science_tool/archive.py`** — add `consolidated_into` /
  `digest_insight` optional fields to `ArchiveRow`; extract the per-row
  move→append→rollback loop into a content-agnostic `_relocate_rows(...)` primitive
  that `archive_entities` and `apply_consolidation` both call.
- **Modify `science/model/src/science_model/profiles/core.py`** — add `archived`
  to 18 enumerated kinds' `statuses`; add a `consolidates` `RelationKind`.
- **Modify `science/src/science_tool/validate/checks/discussions.py`** — add
  `cluster-digest` to `_VALID_SYNTHESIS_KINDS`.
- **Modify `science/model/src/science_model/templates/synthesis.md`** — extend the
  `report_kind` enum comment with `cluster-digest`.
- **Modify `science/src/science_tool/cli.py`** — add the `entities consolidate`
  sub-group with `scaffold` and `apply` subcommands.

## Key existing APIs (verified against the current tree)

- `science_tool.entities`:
  - `create_entity(project_root, kind, title, *, entity_id=None, ...) -> EntityWriteResult` (fields `entity_id`, `path`, `warnings`).
  - `find_entity(project_root, ref) -> EntityLocation` (fields `entity_id`, `kind`, `title`, `status`, `path`, `rel_path`, `frontmatter: dict`, `body: str`).
  - `_parse_markdown_file(path) -> (frontmatter: dict, body: str)`.
  - `_render_markdown(frontmatter: dict, body: str) -> str` and `_atomic_replace_text(path, text)`.
  - `valid_statuses(kind, *, project_root=None) -> frozenset[str] | None` (None ⇒ open vocab).
  - `EntityCommandError(ValueError)`.
- `science_tool.archive`: `ArchiveRow`, `archive_index_path`, `derive_archive_path`,
  `append_row`, `load_archive_index`, `archive_entities`, `ArchiveError`,
  `_fsync_dir`.
- `science_model.profiles.schema.RelationKind(name, predicate, source_kinds, target_kinds, allowed_kind_pairs=[], layer, description="")`.
- `science_model.relations.relation_allows_kinds(relation, source_kind, target_kind)`.
- Graph: `science_tool.graph.materialize.materialize_graph(...)`; the authored-relation
  emitter `_add_authored_relation` already receives `archive_active`/`referenced_archived`
  (archive-aware); tombstone stub type is `SCI_NS.ArchivedEntity`.

---

### Task 1: Add `archived` to consolidatable core kinds' status vocab

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py` (the `statuses=[...]` lists of 18 kinds)
- Modify: `science/tests/test_kind_map_equivalence.py` (the `FROZEN_STATUS_VALUES` parity literal — it asserts `_STATUS_VALUES == FROZEN_STATUS_VALUES`, so it MUST be updated in lockstep or it breaks)
- Test: `science/tests/test_archived_status_vocab.py`

The 18 consolidatable kinds (explicit enumeration — do NOT prune by `entity_class`):
`hypothesis`, `question`, `proposition`, `observation`, `finding`,
`interpretation`, `synthesis`, `report`, `discussion`, `inquiry`, `mechanism`,
`theme`, `topic`, `method`, `plan`, `search`, `decision`, `evidence-line`.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_archived_status_vocab.py`:

```python
"""archived is a valid status on the consolidatable core kinds (P4)."""
from __future__ import annotations

import pytest

from science_tool.entities import (
    _HIDDEN_STATUSES,
    _LIVE_STATUSES,
    _STATUS_VALUES,
    valid_statuses,
)

CONSOLIDATABLE_KINDS = [
    "hypothesis", "question", "proposition", "observation", "finding",
    "interpretation", "synthesis", "report", "discussion", "inquiry",
    "mechanism", "theme", "topic", "method", "plan", "search", "decision",
    "evidence-line",
]


@pytest.mark.parametrize("kind", CONSOLIDATABLE_KINDS)
def test_consolidatable_kind_accepts_archived(kind: str) -> None:
    vs = valid_statuses(kind)
    assert vs is not None and "archived" in vs


def test_reference_kinds_do_not_gain_archived() -> None:
    for kind in ("paper", "book", "talk"):
        vs = valid_statuses(kind)
        assert vs is not None and "archived" not in vs


def test_every_declared_status_still_classified() -> None:
    classified = _LIVE_STATUSES | _HIDDEN_STATUSES
    declared = {s for statuses in _STATUS_VALUES.values() for s in statuses}
    assert declared - classified == set()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_archived_status_vocab.py -v`
Expected: FAIL — `test_consolidatable_kind_accepts_archived` fails (no kind has `archived` yet).

- [ ] **Step 3: Implement — add `archived` to each of the 18 kinds**

In `science/model/src/science_model/profiles/core.py`, for each of the 18 kinds
above, append `"archived"` to its `statuses=[...]` list. Example edits (apply the
same pattern to all 18; keep existing order, add `"archived"` at the end of each
list):

```python
# hypothesis (currently statuses=[ ... ]): add "archived"
# question:        statuses=["active", "partially-answered", "answered", "deferred", "retired", "archived"],
# observation:     statuses=["active", "superseded", "retired", "archived"],
# finding:         statuses=["active", "superseded", "retired", "archived"],
# interpretation:  statuses=["active", "complete", "superseded", "archived"],
# synthesis:       statuses=["active", "superseded", "retired", "archived"],
# report:          statuses=["active", "superseded", "retired", "archived"],
# discussion:      statuses=["active", "complete", "superseded", "archived"],
# inquiry:         statuses=["active", "complete", "superseded", "archived"],
# mechanism:       statuses=["active", "superseded", "retired", "archived"],
# theme:           statuses=["draft", "active", "superseded", "retired", "archived"],
# topic:           statuses=["active", "superseded", "retired", "archived"],
# method:          statuses=["active", "superseded", "retired", "archived"],
# plan:            statuses=["active", "complete", "superseded", "retired", "archived"],
# search:          statuses=["active", "complete", "retired", "archived"],
# decision:        statuses=["active", "superseded", "abandoned", "archived"],
# proposition:     statuses=["draft", "active", "supported", "contested", "weakened", "retired", "superseded", "archived"],
# evidence-line:   statuses=["draft", "active", "retired", "archived"],
```

For each kind, locate its `EntityKind(... name="<kind>" ...)` block and add
`"archived"` to the existing `statuses=[...]` list (do not reorder existing
values; do not touch `default_status`).

- [ ] **Step 3b: Update the frozen parity literal in lockstep**

`science/tests/test_kind_map_equivalence.py` asserts `_STATUS_VALUES ==
FROZEN_STATUS_VALUES` (around line 138). `_STATUS_VALUES` is profile-derived, so
the 18 edits above will break that assertion unless the frozen literal is updated
intentionally. In `FROZEN_STATUS_VALUES`, add `"archived"` to the `frozenset({...})`
of **exactly these 18 keys** (leave `patch-definition`, `pre-registration`,
`paper`, `book`, `talk`, `concept`, `construct`, `outcome` UNCHANGED):
`hypothesis`, `question`, `proposition`, `observation`, `finding`,
`interpretation`, `synthesis`, `report`, `discussion`, `inquiry`, `mechanism`,
`theme`, `topic`, `method`, `plan`, `search`, `decision`, `evidence-line`.
Example:
```python
    "finding": frozenset({"active", "superseded", "retired", "archived"}),
    "hypothesis": frozenset(
        {"proposed", "under-investigation", "partially-supported", "supported", "weakened", "refuted", "archived"}
    ),
```

- [ ] **Step 4: Run the new test + the parity + visibility guards**

Run:
```
PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_archived_status_vocab.py tests/test_kind_map_equivalence.py tests/test_status_visibility.py -v
```
Expected: PASS (all). `archived` is already in `_HIDDEN_STATUSES`, so the
classification guard stays green; the parity literal now matches the profile.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/.worktrees/entity-consolidation-p4-consolidate-apply
git add science/model/src/science_model/profiles/core.py science/tests/test_kind_map_equivalence.py science/tests/test_archived_status_vocab.py
git commit -m "feat(consolidation): add archived status to consolidatable core kinds (P4)"
```

---

### Task 2: Register `cluster-digest` as a valid synthesis report_kind

**Files:**
- Modify: `science/src/science_tool/validate/checks/discussions.py` (`_VALID_SYNTHESIS_KINDS`, around line 38)
- Modify: `science/model/src/science_model/templates/synthesis.md` (the `report_kind` enum comment, lines 6 and 18)
- Test: `science/tests/test_cluster_digest_report_kind.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_cluster_digest_report_kind.py`:

```python
"""cluster-digest is an accepted synthesis report_kind (P4)."""
from __future__ import annotations

from science_tool.validate.checks.discussions import _VALID_SYNTHESIS_KINDS


def test_cluster_digest_is_a_valid_report_kind() -> None:
    assert "cluster-digest" in _VALID_SYNTHESIS_KINDS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_cluster_digest_report_kind.py -v`
Expected: FAIL — `cluster-digest` not in the set.

- [ ] **Step 3: Implement**

In `science/src/science_tool/validate/checks/discussions.py`, change:

```python
_VALID_SYNTHESIS_KINDS = {"hypothesis-synthesis", "synthesis-rollup", "emergent-threads"}
```
to:
```python
_VALID_SYNTHESIS_KINDS = {"hypothesis-synthesis", "synthesis-rollup", "emergent-threads", "cluster-digest"}
```

In `science/model/src/science_model/templates/synthesis.md`, extend both
`report_kind` enum comments to list `cluster-digest`:

- line 6: `report_kind: "hypothesis-synthesis"   # hypothesis-synthesis | synthesis-rollup | emergent-threads | cluster-digest`
- the `_template.frontmatter` comment at line ~18 keeps `default: "hypothesis-synthesis"` (do not change the default); only update any inline enum comment text if present.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_cluster_digest_report_kind.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/discussions.py science/model/src/science_model/templates/synthesis.md science/tests/test_cluster_digest_report_kind.py
git commit -m "feat(consolidation): accept cluster-digest synthesis report_kind (P4)"
```

---

### Task 3: Register the `consolidates` RelationKind

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py` (the `relation_kinds=[...]` list, around line 551)
- Test: `science/tests/test_consolidates_relation_kind.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_consolidates_relation_kind.py`:

```python
"""consolidates RelationKind: registered, synthesis->any allowed (P4)."""
from __future__ import annotations

from science_model.profiles.core import CORE_PROFILE
from science_model.relations import build_relation_registry, relation_allows_kinds


def _consolidates():
    registry = build_relation_registry(CORE_PROFILE.relation_kinds)
    assert "consolidates" in registry
    return registry["consolidates"]


def test_consolidates_predicate_is_sci_consolidates() -> None:
    assert _consolidates().predicate == "sci:consolidates"


def test_consolidates_source_is_synthesis_target_unrestricted() -> None:
    rel = _consolidates()
    assert rel.source_kinds == ["synthesis"]
    assert rel.target_kinds == []  # empty == unrestricted target


def test_consolidates_allows_synthesis_to_any_member_kind() -> None:
    rel = _consolidates()
    assert relation_allows_kinds(rel, "synthesis", "finding") is True
    assert relation_allows_kinds(rel, "synthesis", "hypothesis") is True
    assert relation_allows_kinds(rel, "finding", "hypothesis") is False  # wrong source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_consolidates_relation_kind.py -v`
Expected: FAIL — `"consolidates" in registry` assertion fails.

- [ ] **Step 3: Implement — add the RelationKind**

In `science/model/src/science_model/profiles/core.py`, inside the
`relation_kinds=[ ... ]` list (alongside `tests`, `blocked_by`, `supports`, …),
add a new entry (place it after the existing entries, before the closing `]`):

```python
        RelationKind(
            name="consolidates",
            predicate="sci:consolidates",
            source_kinds=["synthesis"],
            target_kinds=[],  # unrestricted target: a digest may consolidate any consolidatable kind
            layer="layer/core",
            description="A cluster-digest synthesis subsumes the entities it consolidates (live->archived).",
        ),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_consolidates_relation_kind.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/profiles/core.py science/tests/test_consolidates_relation_kind.py
git commit -m "feat(consolidation): register consolidates RelationKind (sci:consolidates) (P4)"
```

---

### Task 4: ArchiveRow consolidation fields + extract `_relocate_rows`

**Files:**
- Modify: `science/src/science_tool/archive.py`
- Test: `science/tests/test_relocate_rows_primitive.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_relocate_rows_primitive.py`:

```python
"""ArchiveRow gains consolidation fields; _relocate_rows is the shared move primitive."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.archive import (
    ArchiveRow,
    _relocate_rows,
    archive_index_path,
    derive_archive_path,
    load_archive_index,
)


def test_archive_row_has_consolidation_fields() -> None:
    row = ArchiveRow(op="archive", id="finding:0001-x", consolidated_into="synthesis:0001-d", digest_insight="X")
    assert row.consolidated_into == "synthesis:0001-d"
    assert row.digest_insight == "X"
    # round-trips through json
    assert ArchiveRow.model_validate_json(row.model_dump_json()).consolidated_into == "synthesis:0001-d"


def test_old_rows_without_new_fields_load_as_none() -> None:
    row = ArchiveRow.model_validate_json('{"op": "archive", "id": "finding:0001-x"}')
    assert row.consolidated_into is None
    assert row.digest_insight is None


def test_relocate_rows_moves_and_appends(tmp_path: Path) -> None:
    src_rel = "entities/findings/0001-x.md"
    src = tmp_path / src_rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("---\nid: finding:0001-x\n---\nbody\n", encoding="utf-8")
    row = ArchiveRow(op="archive", id="finding:0001-x", kind="finding", original_path=src_rel,
                     consolidated_into="synthesis:0001-d", digest_insight="X")
    result = _relocate_rows(archive_index_path(tmp_path), tmp_path, [row], now="T1")
    assert result["applied"] == ["finding:0001-x"]
    assert not src.exists()
    assert (tmp_path / derive_archive_path(src_rel)).exists()
    idx = load_archive_index(tmp_path)
    assert idx.active_by_id["finding:0001-x"].consolidated_into == "synthesis:0001-d"
    assert idx.active_by_id["finding:0001-x"].archived_at == "T1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_relocate_rows_primitive.py -v`
Expected: FAIL — `consolidated_into` not a field and `_relocate_rows` does not exist.

- [ ] **Step 3: Implement — add fields + extract primitive**

In `science/src/science_tool/archive.py`, add two fields to `ArchiveRow` (after
`unarchived_at`):

```python
    consolidated_into: str | None = None
    digest_insight: str | None = None
```

Add the extracted primitive (place it just above `archive_entities`):

```python
def _relocate_rows(
    index_path: Path,
    project_root: Path,
    rows: list[ArchiveRow],
    *,
    now: str | None,
) -> dict:
    """Content-agnostic relocation: move each row's file under _archive/ (move-first),
    append its index row, and roll the move back if the append fails. Performs NO
    frontmatter edits and owns no content snapshot — callers that mutate file content
    (e.g. consolidation) snapshot/restore around this call. Raises ArchiveError on a
    destination collision (never overwrites)."""
    applied: list[str] = []
    skipped: list[str] = []
    for row in rows:
        assert row.original_path is not None
        src = project_root / row.original_path
        dst = project_root / derive_archive_path(row.original_path)
        if not src.exists():
            skipped.append(row.id)
            continue
        if dst.exists():
            raise ArchiveError(
                f"cannot archive {row.id!r}: archive path {derive_archive_path(row.original_path)} "
                "already exists (run `science validate` to reconcile the archive index)"
            )
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))  # move first
        _fsync_dir(dst.parent)
        try:
            append_row(index_path, row.model_copy(update={"archived_at": now}))
        except Exception:
            shutil.move(str(dst), str(src))  # roll back the move
            raise
        applied.append(row.id)
    return {"applied": applied, "skipped": skipped}
```

Refactor `archive_entities` to delegate its apply loop to `_relocate_rows`
(replace the existing `for row in rows: ...` apply block):

```python
    if not apply:
        return report

    index_path = archive_index_path(project_root)
    result = _relocate_rows(index_path, project_root, rows, now=now)
    report["applied"] = result["applied"]
    report["skipped"] = result["skipped"]
    return report
```

(Keep the report construction, `_candidate_rows`, and `_inbound_live_refs` calls
above unchanged.)

- [ ] **Step 4: Run the new test + the existing archive suite (no regression)**

Run:
```
PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_relocate_rows_primitive.py tests/test_archive_mutators.py tests/test_archive_index.py -v
```
Expected: PASS (all). `archive_entities` behavior is unchanged.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/archive.py science/tests/test_relocate_rows_primitive.py
git commit -m "feat(consolidation): ArchiveRow consolidation fields + shared _relocate_rows primitive (P4)"
```

---

### Task 5: `consolidate.scaffold_digest` (create-then-rewrite, atomic)

**Files:**
- Create: `science/src/science_tool/consolidate.py`
- Test: `science/tests/test_consolidate_scaffold.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_consolidate_scaffold.py`:

```python
"""scaffold_digest: mint a cluster-digest with typed consolidates relations (P4)."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.archive import ArchiveRow, append_row, archive_index_path
from science_tool.consolidate import ConsolidateError, scaffold_digest
from science_tool.entities import _parse_markdown_file, create_entity


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    return tmp_path


def _member(root: Path, kind: str, eid: str, title: str) -> None:
    create_entity(root, kind, title, entity_id=eid)


def test_scaffold_mints_digest_with_consolidates_relations(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _member(root, "finding", "finding:0001-a", "A")
    _member(root, "finding", "finding:0002-b", "B")
    report = scaffold_digest(
        root, digest_id="synthesis:0001-digest", member_ids=["finding:0001-a", "finding:0002-b"], title="Digest"
    )
    path = Path(report["digest_path"])
    assert path.exists()
    fm, _ = _parse_markdown_file(path)
    assert fm["report_kind"] == "cluster-digest"
    rels = fm["relations"]
    assert {r["target"] for r in rels} == {"finding:0001-a", "finding:0002-b"}
    assert all(r["predicate"] == "sci:consolidates" for r in rels)


def test_scaffold_rejects_unknown_member(tmp_path: Path) -> None:
    root = _project(tmp_path)
    with pytest.raises(ConsolidateError, match="not a known live entity"):
        scaffold_digest(root, digest_id="synthesis:0001-digest", member_ids=["finding:9999-x"], title="D")


def test_scaffold_rejects_digest_id_among_members(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _member(root, "finding", "finding:0001-a", "A")
    with pytest.raises(ConsolidateError, match="digest id"):
        scaffold_digest(
            root, digest_id="synthesis:0001-digest",
            member_ids=["finding:0001-a", "synthesis:0001-digest"], title="D",
        )


def test_consolidatable_predicate_fails_loud_for_closed_vocab_without_archived(tmp_path: Path) -> None:
    from science_tool.consolidate import _is_consolidatable

    root = _project(tmp_path)
    assert _is_consolidatable(root, "finding") is True   # gained archived in Task 1
    assert _is_consolidatable(root, "paper") is False     # closed vocab ["active","retired"], no archived


def test_scaffold_rejects_digest_id_colliding_with_archived(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _member(root, "finding", "finding:0001-a", "A")
    # An entity with the chosen digest id is already ACTIVE in the archive index.
    append_row(
        archive_index_path(root),
        ArchiveRow(op="archive", id="synthesis:0001-digest", kind="synthesis",
                   original_path="entities/synthesis/0001-digest.md", archived_at="T1"),
    )
    with pytest.raises(ConsolidateError, match="collides with an archived"):
        scaffold_digest(root, digest_id="synthesis:0001-digest", member_ids=["finding:0001-a"], title="D")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_consolidate_scaffold.py -v`
Expected: FAIL — `science_tool.consolidate` does not exist.

- [ ] **Step 3: Implement `consolidate.py` (scaffold half)**

Create `science/src/science_tool/consolidate.py`:

```python
# science/src/science_tool/consolidate.py
"""Entity consolidation — Tier 3 *apply* half (P4).

`scaffold_digest` mints a live `cluster-digest` synthesis entity carrying one typed
`sci:consolidates` authored relation per member; `apply_consolidation` stamps each
member `status: archived` + `consolidated_into`, relocates it via the P3 archive
machinery, and appends an index row. The digest stays live.

This is the apply counterpart to the read-only detector in `consolidation.py`; the
two never import each other.
"""
from __future__ import annotations

from pathlib import Path

from science_tool.archive import (
    ArchiveRow,
    archive_index_path,
    derive_archive_path,
    load_archive_index,
    _relocate_rows,
)
from science_tool.entities import (
    EntityLocation,
    _atomic_replace_text,
    _parse_markdown_file,
    _render_markdown,
    create_entity,
    find_entity,
    valid_statuses,
)

CONSOLIDATES_PREDICATE = "sci:consolidates"
CLUSTER_DIGEST_REPORT_KIND = "cluster-digest"
SYNTHESIS_KIND = "synthesis"


class ConsolidateError(Exception):
    """Raised on an invalid or unsafe consolidate operation (fail-loud)."""


def _is_consolidatable(project_root: Path, kind: str) -> bool:
    """A kind is consolidatable iff its status vocab is open (None) or includes
    `archived`. A closed vocab lacking `archived` fails loud (no auto-patch)."""
    vs = valid_statuses(kind, project_root=project_root)
    return vs is None or "archived" in vs


def _resolve_member(project_root: Path, eid: str) -> EntityLocation:
    try:
        return find_entity(project_root, eid)
    except Exception as exc:  # find_entity raises when the ref is unknown
        raise ConsolidateError(f"member {eid!r} is not a known live entity") from exc


def _validate_members(
    project_root: Path, member_ids: list[str], digest_id: str
) -> list[EntityLocation]:
    if not member_ids:
        raise ConsolidateError("no members supplied to consolidate")
    idx = load_archive_index(project_root)
    locs: list[EntityLocation] = []
    seen: set[str] = set()
    for eid in member_ids:
        if eid == digest_id:
            raise ConsolidateError(f"the digest id {digest_id!r} cannot be one of its own members")
        if eid in seen:
            raise ConsolidateError(f"duplicate member {eid!r}")
        seen.add(eid)
        if eid in idx.active_by_id:
            raise ConsolidateError(f"member {eid!r} is already archived")
        loc = _resolve_member(project_root, eid)
        if not _is_consolidatable(project_root, loc.kind):
            raise ConsolidateError(
                f"member {eid!r} of kind {loc.kind!r} has a closed status vocabulary lacking "
                f"'archived'; add 'archived' to that kind's statuses before consolidating"
            )
        locs.append(loc)
    return locs


def scaffold_digest(
    project_root: Path,
    *,
    digest_id: str,
    member_ids: list[str],
    title: str,
) -> dict:
    """Mint a live cluster-digest synthesis entity (create-then-rewrite, atomic)."""
    project_root = Path(project_root).resolve()
    _validate_members(project_root, member_ids, digest_id)
    # The digest id must not collide with an ACTIVE archived id/alias. create_entity
    # only guards against a live destination path, so without this an archived id
    # could be reborn as a live digest with the same canonical id (validate would
    # only catch it after the bad state was written).
    if digest_id in load_archive_index(project_root).resolvable_ids():
        raise ConsolidateError(
            f"digest id {digest_id!r} collides with an archived entity id/alias; "
            "choose a fresh id or unarchive the colliding entity first"
        )

    result = create_entity(project_root, SYNTHESIS_KIND, title, entity_id=digest_id)
    path = result.path
    try:
        fm, body = _parse_markdown_file(path)
        fm["report_kind"] = CLUSTER_DIGEST_REPORT_KIND
        fm["relations"] = [
            {"predicate": CONSOLIDATES_PREDICATE, "target": m} for m in member_ids
        ]
        _atomic_replace_text(path, _render_markdown(fm, body))
        # Re-validate: the rewritten file must still load as an entity.
        find_entity(project_root, digest_id)
    except Exception:
        # Scaffold rollback: the digest file is brand-new this command — remove it.
        path.unlink(missing_ok=True)
        raise
    return {
        "digest_id": digest_id,
        "digest_path": str(path),
        "members": list(member_ids),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_consolidate_scaffold.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/consolidate.py science/tests/test_consolidate_scaffold.py
git commit -m "feat(consolidation): scaffold_digest mints cluster-digest with consolidates relations (P4)"
```

---

### Task 6: `consolidate.apply_consolidation` (dry-run + atomic apply)

**Files:**
- Modify: `science/src/science_tool/consolidate.py`
- Test: `science/tests/test_consolidate_apply.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_consolidate_apply.py`:

```python
"""apply_consolidation: dry-run + apply demote/relocate/index (P4)."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.archive import derive_archive_path, load_archive_index
from science_tool.consolidate import ConsolidateError, apply_consolidation, scaffold_digest
from science_tool.entities import _parse_markdown_file, create_entity


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    return tmp_path


def _scaffolded(root: Path) -> str:
    create_entity(root, "finding", "A", entity_id="finding:0001-a")
    create_entity(root, "finding", "B", entity_id="finding:0002-b")
    scaffold_digest(root, digest_id="synthesis:0001-d",
                    member_ids=["finding:0001-a", "finding:0002-b"], title="Digest")
    return "synthesis:0001-d"


def test_dry_run_reports_without_mutation(tmp_path: Path) -> None:
    root = _project(tmp_path)
    digest = _scaffolded(root)
    report = apply_consolidation(root, digest, apply=False, now="T1")
    assert set(report["members"]) == {"finding:0001-a", "finding:0002-b"}
    assert report["applied"] == []
    assert (root / "entities" / "findings" / "0001-a.md").exists()  # not moved
    assert not load_archive_index(root).active_by_id


def test_apply_demotes_relocates_indexes(tmp_path: Path) -> None:
    root = _project(tmp_path)
    digest = _scaffolded(root)
    report = apply_consolidation(root, digest, apply=True, now="T1")
    assert set(report["applied"]) == {"finding:0001-a", "finding:0002-b"}
    # members relocated
    assert not (root / "entities" / "findings" / "0001-a.md").exists()
    moved = root / derive_archive_path("entities/findings/0001-a.md")
    assert moved.exists()
    fm, _ = _parse_markdown_file(moved)
    assert fm["status"] == "archived"
    assert fm["consolidated_into"] == digest
    # index rows carry consolidation provenance
    idx = load_archive_index(root)
    row = idx.active_by_id["finding:0001-a"]
    assert row.consolidated_into == digest
    assert row.digest_insight == "A"
    # digest stays live, unmoved
    assert (root / "entities" / "synthesis" / "0001-d.md").exists()


def test_apply_rejects_non_cluster_digest(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_entity(root, "synthesis", "Not a digest", entity_id="synthesis:0002-plain")
    with pytest.raises(ConsolidateError, match="cluster-digest"):
        apply_consolidation(root, "synthesis:0002-plain", apply=True, now="T1")


def test_apply_rejects_digest_without_consolidates_relation(tmp_path: Path) -> None:
    # A cluster-digest with no sci:consolidates relations -> fail loud.
    root = _project(tmp_path)
    create_entity(root, "synthesis", "Empty digest", entity_id="synthesis:0003-empty")
    path = root / "entities" / "synthesis" / "0003-empty.md"
    fm, body = _parse_markdown_file(path)
    fm["report_kind"] = "cluster-digest"  # but no relations
    from science_tool.entities import _atomic_replace_text, _render_markdown
    _atomic_replace_text(path, _render_markdown(fm, body))
    with pytest.raises(ConsolidateError, match="no sci:consolidates"):
        apply_consolidation(root, "synthesis:0003-empty", apply=True, now="T1")


def test_apply_rejects_already_archived_member(tmp_path: Path) -> None:
    root = _project(tmp_path)
    digest = _scaffolded(root)
    apply_consolidation(root, digest, apply=True, now="T1")  # finding:0001-a now archived
    # A new digest cannot re-consolidate the already-archived member.
    create_entity(root, "finding", "C", entity_id="finding:0003-c")
    with pytest.raises(ConsolidateError, match="already archived"):
        scaffold_digest(root, digest_id="synthesis:0009-d2",
                        member_ids=["finding:0003-c", "finding:0001-a"], title="D2")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_consolidate_apply.py -v`
Expected: FAIL — `apply_consolidation` does not exist.

- [ ] **Step 3: Implement `apply_consolidation`**

Append to `science/src/science_tool/consolidate.py`:

```python
def _consolidates_targets(loc: EntityLocation) -> list[str]:
    """Member ids = targets of the digest's `sci:consolidates` authored relations."""
    targets: list[str] = []
    for rel in loc.frontmatter.get("relations") or []:
        if isinstance(rel, dict) and rel.get("predicate") == CONSOLIDATES_PREDICATE:
            target = rel.get("target")
            if isinstance(target, str):
                targets.append(target)
    return targets


def apply_consolidation(
    project_root: Path,
    digest_id: str,
    *,
    apply: bool = False,
    now: str | None = None,
) -> dict:
    """Demote + relocate the digest's consolidated members (report, then --apply).

    Per-member transaction: snapshot bytes -> rewrite frontmatter (status/consolidated_into)
    -> relocate via _relocate_rows. On any exception, restore the snapshotted bytes at the
    live original_path (the move-rollback / un-executed move leaves the file there)."""
    project_root = Path(project_root).resolve()
    digest = find_entity(project_root, digest_id)
    if digest.frontmatter.get("report_kind") != CLUSTER_DIGEST_REPORT_KIND:
        raise ConsolidateError(f"{digest_id!r} is not a cluster-digest (report_kind)")
    member_ids = _consolidates_targets(digest)
    if not member_ids:
        raise ConsolidateError(f"{digest_id!r} has no sci:consolidates relation entries")
    locs = _validate_members(project_root, member_ids, digest_id)

    report: dict = {
        "digest_id": digest_id,
        "members": [loc.entity_id for loc in locs],
        "destinations": {loc.entity_id: derive_archive_path(loc.rel_path) for loc in locs},
        "applied": [],
        "skipped": [],
    }
    if not apply:
        return report

    index_path = archive_index_path(project_root)
    for loc in locs:
        original_bytes = loc.path.read_bytes()
        fm = dict(loc.frontmatter)
        fm["status"] = "archived"
        fm["consolidated_into"] = digest_id
        _atomic_replace_text(loc.path, _render_markdown(fm, loc.body))
        row = ArchiveRow(
            op="archive",
            id=loc.entity_id,
            kind=loc.kind,
            title=loc.title or None,
            aliases=[a for a in (loc.frontmatter.get("aliases") or []) if isinstance(a, str)],
            same_as=[s for s in (loc.frontmatter.get("same_as") or []) if isinstance(s, str)],
            status="archived",
            original_path=loc.rel_path,
            consolidated_into=digest_id,
            digest_insight=loc.title or None,
            reason="consolidated",
        )
        try:
            _relocate_rows(index_path, project_root, [row], now=now)
        except Exception:
            loc.path.write_bytes(original_bytes)  # restore the frontmatter rewrite
            raise
        report["applied"].append(loc.entity_id)
    return report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_consolidate_apply.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/consolidate.py science/tests/test_consolidate_apply.py
git commit -m "feat(consolidation): apply_consolidation demote+relocate+index members (P4)"
```

---

### Task 7: Per-member atomic rollback on append failure

**Files:**
- Test: `science/tests/test_consolidate_rollback.py`
- (No source change expected — this verifies the Task 6 transaction. If it fails, fix `apply_consolidation`.)

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_consolidate_rollback.py`:

```python
"""apply_consolidation restores member bytes if relocation fails mid-apply (P4)."""
from __future__ import annotations

from pathlib import Path

import pytest

import science_tool.consolidate as consolidate
from science_tool.archive import load_archive_index
from science_tool.consolidate import apply_consolidation, scaffold_digest
from science_tool.entities import _parse_markdown_file, create_entity


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    return tmp_path


def test_append_failure_restores_member(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    create_entity(root, "finding", "A", entity_id="finding:0001-a")
    scaffold_digest(root, digest_id="synthesis:0001-d", member_ids=["finding:0001-a"], title="D")
    member_path = root / "entities" / "findings" / "0001-a.md"
    before = member_path.read_bytes()

    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    # Force the index append (inside _relocate_rows) to fail.
    monkeypatch.setattr(consolidate, "_relocate_rows", boom)
    with pytest.raises(RuntimeError, match="disk full"):
        apply_consolidation(root, "synthesis:0001-d", apply=True, now="T1")

    # Member file restored exactly (status reverted, still at original path).
    assert member_path.exists()
    assert member_path.read_bytes() == before
    fm, _ = _parse_markdown_file(member_path)
    assert fm["status"] != "archived"
    assert "consolidated_into" not in fm
    assert not load_archive_index(root).active_by_id
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_consolidate_rollback.py -v`
Expected: PASS if Task 6's transaction is correct. (The test monkeypatches
`_relocate_rows` to raise *after* the frontmatter rewrite, exercising the
`except: loc.path.write_bytes(original_bytes)` restore path.) If it FAILS,
the restore in `apply_consolidation` is wrong — fix it so the original bytes are
written back to `loc.path` on any exception.

- [ ] **Step 3: Fix if needed**

Only if Step 2 failed: ensure the `try/except` in `apply_consolidation` wraps the
`_relocate_rows` call and restores `original_bytes` to `loc.path` before
re-raising (see Task 6 code).

- [ ] **Step 4: Re-run to confirm PASS**

Run: `PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_consolidate_rollback.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/tests/test_consolidate_rollback.py science/src/science_tool/consolidate.py
git commit -m "test(consolidation): per-member atomic rollback on relocation failure (P4)"
```

---

### Task 8: Graph emits `sci:consolidates` → tombstone; validate stays clean

**Files:**
- Test: `science/tests/test_consolidates_graph_resolution.py`
- Possibly modify: `science/src/science_tool/graph/materialize.py` (only if the
  authored-relation path mis-handles an active-archived target — design §7 flag).

This verifies the central claim: after consolidation, the digest's typed
`sci:consolidates` relation to a now-archived member resolves to the archived
tombstone stub (not dangling, not force-loaded).

`materialize_graph(project_root, *, strict=True) -> Path` writes `graph.trig` and
returns its path; the P3 test (`tests/test_archive_resolution_graph.py`) asserts on
the serialized TriG **text** via substring checks. Mirror that idiom exactly.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_consolidates_graph_resolution.py`:

```python
"""Graph build: digest sci:consolidates -> archived member tombstone (P4)."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.consolidate import apply_consolidation, scaffold_digest
from science_tool.entities import create_entity

rdflib = pytest.importorskip("rdflib")


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    return tmp_path


def test_digest_consolidates_edge_targets_tombstone(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_entity(root, "finding", "A", entity_id="finding:0001-a")
    scaffold_digest(root, digest_id="synthesis:0001-d", member_ids=["finding:0001-a"], title="D")
    apply_consolidation(root, "synthesis:0001-d", apply=True, now="T1")

    from science_tool.graph.materialize import materialize_graph

    out_path = materialize_graph(root, strict=False)
    text = out_path.read_text(encoding="utf-8")

    assert "consolidates" in text          # the sci:consolidates edge (predicate) is emitted
    assert "0001-a" in text                # the archived member id appears as the edge target
    assert "ArchivedEntity" in text        # the member is a typed tombstone stub, not rehydrated
    # the archived member markdown is NOT pulled back into the live tree
    assert not (root / "entities" / "findings" / "0001-a.md").exists()
```

- [ ] **Step 2: Run test to verify it fails (or surfaces a real gap)**

Run: `PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_consolidates_graph_resolution.py -v`
Expected: the test should PASS *without* any materialize change — the
authored-relation emitter already receives `archive_active`/`referenced_archived`
(P3). **If `"consolidates"`/`"ArchivedEntity"` is missing or the build raises**,
the authored-relation resolution/validation path is not archive-aware for this
case: investigate `_add_authored_relation` / `_validate_authored_relation_endpoint`
in `materialize.py` and apply the minimal fix so an active-archived `consolidates`
target resolves to the tombstone (mirror how `related:`/`source_refs:` already do
via `_archived_uri_if_active`). Use `strict=False` (as the P3 test does) so the
build does not fail the audit on unrelated synthesis-template fields.

- [ ] **Step 3: Make it pass**

If Step 2 already passes, no source change is needed — proceed. Apply a
`materialize.py` fix only if Step 2 proved a real gap (missing edge / build raises),
keeping it minimal and mirroring the existing `_archived_uri_if_active` handling.

- [ ] **Step 4: Run the broader graph regression**

Run:
```
PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_consolidates_graph_resolution.py tests/test_archive_resolution_graph.py tests/test_archive_resolution_validate.py -v
```
Expected: PASS (all). The archived member must not be forced into the live graph,
and validate must report no nonexistent-reference error for the `consolidates`
target.

- [ ] **Step 5: Commit**

```bash
git add science/tests/test_consolidates_graph_resolution.py science/src/science_tool/graph/materialize.py
git commit -m "test(consolidation): graph emits sci:consolidates to archived tombstone (P4)"
```

---

### Task 9: CLI — `entities consolidate {scaffold,apply}`

**Files:**
- Modify: `science/src/science_tool/cli.py` (near the `entities archive`/`unarchive` commands, ~line 307–348)
- Test: `science/tests/test_consolidate_cli.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_consolidate_cli.py`:

```python
"""CLI: science entities consolidate scaffold / apply (P4)."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.entities import create_entity


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    return tmp_path


def test_scaffold_then_apply_via_cli(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_entity(root, "finding", "A", entity_id="finding:0001-a")
    runner = CliRunner()

    r1 = runner.invoke(main, [
        "entities", "consolidate", "scaffold",
        "--project-root", str(root),
        "--into", "synthesis:0001-d",
        "--members", "finding:0001-a",
        "--title", "Digest",
    ])
    assert r1.exit_code == 0, r1.output
    assert (root / "entities" / "synthesis" / "0001-d.md").exists()

    # dry-run apply: no mutation
    r2 = runner.invoke(main, [
        "entities", "consolidate", "apply", "synthesis:0001-d",
        "--project-root", str(root),
    ])
    assert r2.exit_code == 0, r2.output
    assert json.loads(r2.output)["applied"] == []
    assert (root / "entities" / "findings" / "0001-a.md").exists()

    # apply
    r3 = runner.invoke(main, [
        "entities", "consolidate", "apply", "synthesis:0001-d",
        "--project-root", str(root), "--apply",
    ])
    assert r3.exit_code == 0, r3.output
    assert json.loads(r3.output)["applied"] == ["finding:0001-a"]
    assert not (root / "entities" / "findings" / "0001-a.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_consolidate_cli.py -v`
Expected: FAIL — no `consolidate` subcommand under `entities`.

- [ ] **Step 3: Implement the CLI sub-group**

In `science/src/science_tool/cli.py`, after the `entities_unarchive_command`
definition (right before `@entities_group.command("migrate")`), add:

```python
@entities_group.group("consolidate")
def entities_consolidate_group() -> None:
    """Collapse a cluster of entities into one cluster-digest (scaffold, then apply)."""


@entities_consolidate_group.command("scaffold")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--into", "digest_id", required=True, help="Id to mint for the cluster-digest entity.")
@click.option("--members", "members", required=True, help="Comma-separated member entity ids.")
@click.option("--title", default=None, help="Digest title (default: derived placeholder).")
def entities_consolidate_scaffold_command(
    project_root: Path, digest_id: str, members: str, title: str | None
) -> None:
    """Mint a cluster-digest stub with consolidates relations (touches no members)."""
    from science_tool.consolidate import scaffold_digest

    member_ids = [m.strip() for m in members.split(",") if m.strip()]
    report = scaffold_digest(
        project_root, digest_id=digest_id, member_ids=member_ids, title=title or digest_id
    )
    click.echo(json.dumps(report, indent=2))


@entities_consolidate_group.command("apply")
@click.argument("digest_id")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply changes (default: dry-run report).")
def entities_consolidate_apply_command(digest_id: str, project_root: Path, apply_changes: bool) -> None:
    """Demote + relocate the digest's consolidated members (report, then --apply)."""
    from datetime import datetime, timezone

    from science_tool.consolidate import apply_consolidation

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = apply_consolidation(project_root, digest_id, apply=apply_changes, now=now)
    click.echo(json.dumps(report, indent=2))
```

(If `ConsolidateError`/`ArchiveError` should surface as clean CLI errors rather
than tracebacks, wrap the calls in `try/except (ConsolidateError, ArchiveError) as
exc: raise click.ClickException(str(exc))` — mirror whatever the surrounding
`entities` commands do; if they let exceptions propagate, match that.)

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_consolidate_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_consolidate_cli.py
git commit -m "feat(consolidation): science entities consolidate scaffold/apply CLI (P4)"
```

---

### Task 10: End-to-end acceptance

**Files:**
- Test: `science/tests/test_consolidate_acceptance.py`

- [ ] **Step 1: Write the acceptance test**

Create `science/tests/test_consolidate_acceptance.py`:

```python
"""End-to-end: scaffold -> fill body -> apply -> graph + validate clean (P4)."""
from __future__ import annotations

from pathlib import Path

from science_tool.archive import load_archive_index, unarchive_entities, verify_archive
from science_tool.consolidate import apply_consolidation, scaffold_digest
from science_tool.entities import _parse_markdown_file, _render_markdown, create_entity
from science_tool.graph.materialize import materialize_graph
from science_tool.validate.checks.cross_references import check_archive_index, check_cross_references
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    return tmp_path


def test_full_consolidation_lifecycle(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_entity(root, "finding", "Partition test A", entity_id="finding:0001-a")
    create_entity(root, "finding", "Partition test B", entity_id="finding:0002-b")

    # 1. scaffold
    rep = scaffold_digest(root, digest_id="synthesis:0001-d",
                          member_ids=["finding:0001-a", "finding:0002-b"], title="Partition tests digest")
    digest_path = Path(rep["digest_path"])

    # 2. a human/agent fills the digest body
    fm, body = _parse_markdown_file(digest_path)
    digest_path.write_text(_render_markdown(fm, body.rstrip() + "\n\nThe partition tests converge.\n"), encoding="utf-8")

    # 3. apply
    out = apply_consolidation(root, "synthesis:0001-d", apply=True, now="T1")
    assert set(out["applied"]) == {"finding:0001-a", "finding:0002-b"}

    # 4. members archived + indexed; archive index self-consistent
    idx = load_archive_index(root)
    assert set(idx.active_by_id) == {"finding:0001-a", "finding:0002-b"}
    live_space = {"synthesis:0001-d"}
    assert verify_archive(root, live_space) == []

    # 5. graph builds; digest still live, members are tombstones (not rehydrated)
    out_path = materialize_graph(root, strict=False)
    text = out_path.read_text(encoding="utf-8")
    assert "consolidates" in text and "ArchivedEntity" in text
    assert (root / "entities" / "synthesis" / "0001-d.md").exists()
    assert not (root / "entities" / "findings" / "0001-a.md").exists()

    # 6. validate is clean: archive index reconciles + no broken cross-references.
    #    (check_archive_index yields one INFO "consistent" when clean, ERROR on a problem.)
    ctx = ValidateContext.from_project_root(root, strict=True, verbose=False)
    arch_results = list(check_archive_index(ctx))
    assert not any(r.severity == Severity.ERROR for r in arch_results)
    assert any("consistent" in r.message for r in arch_results)
    xref_results = list(check_cross_references(ctx))
    assert not any(r.severity == Severity.ERROR for r in xref_results)

    # 7. reversibility: unarchive restores a member to its original path (location only)
    unarchive_entities(root, ["finding:0001-a"], apply=True, now="T2")
    assert (root / "entities" / "findings" / "0001-a.md").exists()
    assert "finding:0001-a" not in load_archive_index(root).active_by_id
```

- [ ] **Step 2: Run test to verify it passes**

Run: `PYTHONPATH=src ~/d/science/science/.venv/bin/pytest tests/test_consolidate_acceptance.py -v`
Expected: PASS. (If `verify_archive`'s signature differs, mirror its call in
`tests/test_archive_verify.py`.)

- [ ] **Step 3: Run the full consolidation + archive + status suite**

Run:
```
PYTHONPATH=src ~/d/science/science/.venv/bin/pytest \
  tests/test_archived_status_vocab.py tests/test_cluster_digest_report_kind.py \
  tests/test_consolidates_relation_kind.py tests/test_relocate_rows_primitive.py \
  tests/test_consolidate_scaffold.py tests/test_consolidate_apply.py \
  tests/test_consolidate_rollback.py tests/test_consolidates_graph_resolution.py \
  tests/test_consolidate_cli.py tests/test_consolidate_acceptance.py \
  tests/test_archive_mutators.py tests/test_archive_index.py \
  tests/test_archive_resolution_graph.py tests/test_archive_resolution_validate.py \
  tests/test_status_visibility.py -q
```
Expected: PASS (all).

- [ ] **Step 4: Commit**

```bash
git add science/tests/test_consolidate_acceptance.py
git commit -m "test(consolidation): end-to-end consolidate lifecycle acceptance (P4)"
```

---

## Final verification (after all tasks)

Run the full suite to confirm no regressions beyond the known-pre-existing
failures (6× `test_codex_skills.py` frontmatter, `test_shims.py::test_meta_validate_smoke_runs`,
`test_acceptance_managed_artifacts.py::test_full_lifecycle` — all environmental,
reproduce on `main`):

```bash
cd ~/d/science/.worktrees/entity-consolidation-p4-consolidate-apply/science
PYTHONPATH=src ~/d/science/science/.venv/bin/pytest -q
```

Then dispatch a final whole-feature code review before finishing the branch.
