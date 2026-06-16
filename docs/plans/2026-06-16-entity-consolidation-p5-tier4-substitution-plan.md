# Entity Consolidation P5 — Tier 4 Consumer Substitution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the big-picture programmatic surfaces consume P4 `cluster-digest`
entities natively — restore the transitive q↔h bridges lost when an interpretation
family is consolidated, and expose a recognition registry (`+ --deep` index-only
member descent) for the `/science:big-picture` skill.

**Architecture:** A new read-only leaf `big_picture/digests.py` (reads
`cluster-digest` syntheses + the archive index); a single **digest-as-bridge**
addition to `resolver.py`; a new `big-picture cluster-digests` CLI subcommand
emitting `{digests, member_to_digest}`. `knowledge_gaps.py` inherits correctness
through `resolve_questions` with **no module change**. No schema, graph, or
data-model change — P4 already shipped every field this reads. Design:
`docs/plans/2026-06-16-entity-consolidation-p5-tier4-substitution-design.md`.

**Tech Stack:** Python 3, `click` CLI, `pydantic` (only via the existing
`archive.py` API), `pytest`. Two-package repo (`science_tool` under `science/src/`,
`science_model` under `science/model/src/`).

---

## Execution preamble — READ FIRST (environment + conventions)

- **Worktree & branch.** All work happens in the worktree
  `~/d/science/.worktrees/entity-consolidation-p5-tier4-substitution` on branch
  `feat/entity-consolidation-p5-tier4-substitution`. Before any commit, verify:
  `cd ~/d/science/.worktrees/entity-consolidation-p5-tier4-substitution && rtk git branch --show-current`
  must print `feat/entity-consolidation-p5-tier4-substitution`. The repo is
  Dropbox-synced and `~/d/science` is the MAIN checkout — never edit there; edit the
  worktree path explicitly.
- **Tests.** The worktree has **no `.venv`**. Run the MAIN venv's pytest with the
  worktree's source on the path, from the worktree's `science/` dir:
  ```bash
  cd ~/d/science/.worktrees/entity-consolidation-p5-tier4-substitution/science
  rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/<file> -q
  ```
  `PYTHONPATH=src:model/src` is the standing convention (the `science_model`
  editable-install-from-main shadowing gotcha). P5 touches **no** `science_model`
  file, so `src` alone would also work — keep `src:model/src` for safety/consistency.
- **Commits.** One commit per task. **Do NOT add any `Co-Authored-By` trailer.**
  Conventional-commit style (`feat(...)`, `test(...)`), matching P1–P4.
- **Paths in code/docs** use the `~/d/` form, never `/home/keith/` or
  `/mnt/ssd/Dropbox/`.
- **Layout facts** (resolved via `resolve_path_policy`): questions →
  `entities/questions/`, hypotheses → `entities/hypotheses/`, interpretations →
  `entities/interpretations/`, topics → `entities/topics/`, synthesis →
  `entities/synthesis/` (singular). Entity ids follow `<kind>:0001-x`; the file stem
  is the id with the `<kind>:` prefix stripped (e.g. `synthesis:0001-d` →
  `entities/synthesis/0001-d.md`), exactly as P4's `test_consolidate_acceptance.py`.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `science/src/science_tool/big_picture/digests.py` | Read-only digest-awareness leaf: dataclasses, `redirect_refs`, `member_to_digest`, `load_cluster_digests`. | **Create** |
| `science/src/science_tool/big_picture/resolver.py` | Question→hypothesis resolver. | **Modify** — add digest-as-bridge transitive pass. |
| `science/src/science_tool/big_picture/cli.py` | big-picture CLI group. | **Modify** — add `cluster-digests` subcommand. |
| `science/src/science_tool/big_picture/knowledge_gaps.py` | Topic-coverage gaps. | **No change** — inherits via resolver (Task 5 is a test only). |
| `science/tests/test_big_picture_digests.py` | Unit tests for `digests.py`. | **Create** (Tasks 1–3). |
| `science/tests/test_resolver_digest_bridge.py` | digest-as-bridge resolver tests. | **Create** (Task 4). |
| `science/tests/test_knowledge_gaps_digest_bridge.py` | Inherited-bridge behavioral test. | **Create** (Task 5). |
| `science/tests/test_cluster_digests_cli.py` | `cluster-digests` CLI contract. | **Create** (Task 6). |
| `science/tests/test_p5_tier4_acceptance.py` | End-to-end residual-risk acceptance. | **Create** (Task 7). |

All test paths below are relative to the worktree's `science/` dir.

---

## Task 1: `digests.py` — dataclasses + `redirect_refs` + helpers

**Files:**
- Create: `src/science_tool/big_picture/digests.py`
- Test: `tests/test_big_picture_digests.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_big_picture_digests.py
from __future__ import annotations

import dataclasses as dc

from science_tool.big_picture.digests import (
    ClusterDigest,
    MemberSummary,
    redirect_refs,
)


def test_redirect_refs_rewrites_mapped_and_passes_through() -> None:
    remap = {"interpretation:i01-old": "synthesis:d1", "old-alias": "synthesis:d1"}
    out = redirect_refs(
        ["question:q1", "interpretation:i01-old", "old-alias", "hypothesis:h1"],
        remap,
    )
    # i01-old and old-alias both collapse to synthesis:d1, de-duped, order kept.
    assert out == ["question:q1", "synthesis:d1", "hypothesis:h1"]


def test_redirect_refs_identity_on_empty_remap_still_dedups() -> None:
    assert redirect_refs(["a", "b", "a", "c"], {}) == ["a", "b", "c"]


def test_dataclasses_are_frozen_with_defaults() -> None:
    cd = ClusterDigest(id="synthesis:d1", title="T")
    ms = MemberSummary(id="x", kind="finding", title="t", digest_insight="i", archived=True)
    assert dc.is_dataclass(cd) and cd.__dataclass_params__.frozen
    assert dc.is_dataclass(ms) and ms.__dataclass_params__.frozen
    assert cd.member_count == 0 and cd.members == [] and cd.member_ids == [] and cd.related == []
```

- [ ] **Step 2: Run it; expect failure**

Run: `rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_big_picture_digests.py -q`
Expected: FAIL — `ModuleNotFoundError: science_tool.big_picture.digests`.

- [ ] **Step 3: Create the module**

```python
# src/science_tool/big_picture/digests.py
"""Tier 4 (P5): big-picture digest-awareness leaf.

Reads live ``report_kind: cluster-digest`` synthesis entities and the archive
index to support consumer substitution in the big-picture programmatic surfaces.
Pure read-only helpers; index-only descent (``ArchiveRow`` fields) per the P5 design.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from science_tool.archive import load_archive_index
from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.big_picture.layout import entity_dir
from science_tool.consolidate import (
    CLUSTER_DIGEST_REPORT_KIND,
    CONSOLIDATES_PREDICATE,
    SYNTHESIS_KIND,
)
from science_tool.entities import is_default_visible


@dataclass(frozen=True)
class MemberSummary:
    """Index-only view of one archived, consolidated member."""

    id: str
    kind: str | None
    title: str | None
    digest_insight: str | None
    archived: bool


@dataclass(frozen=True)
class ClusterDigest:
    """A live ``report_kind: cluster-digest`` synthesis entity."""

    id: str
    title: str | None
    related: list[str] = field(default_factory=list)
    member_ids: list[str] = field(default_factory=list)
    member_count: int = 0
    members: list[MemberSummary] = field(default_factory=list)


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _consolidates_targets(fm: dict) -> list[str]:
    """Member ids = targets of the digest's ``sci:consolidates`` relations, read off
    the frontmatter dict in the same shape P4 ``scaffold_digest`` writes."""
    targets: list[str] = []
    for rel in fm.get("relations") or []:
        if isinstance(rel, dict) and rel.get("predicate") == CONSOLIDATES_PREDICATE:
            target = rel.get("target")
            if isinstance(target, str):
                targets.append(target)
    return targets


def redirect_refs(refs: Iterable[str], remap: Mapping[str, str]) -> list[str]:
    """Rewrite each ref through ``remap`` (archived member id -> digest id),
    pass-through otherwise; de-dup preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for ref in refs:
        target = remap.get(ref, ref)
        if target not in seen:
            seen.add(target)
            out.append(target)
    return out
```

- [ ] **Step 4: Run it; expect pass**

Run: `rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_big_picture_digests.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
rtk git add src/science_tool/big_picture/digests.py tests/test_big_picture_digests.py
rtk git commit -m "feat(big-picture): digests leaf — ClusterDigest/MemberSummary + redirect_refs"
```

---

## Task 2: `digests.py` — `member_to_digest` (index-built, alias-seeded)

**Files:**
- Modify: `src/science_tool/big_picture/digests.py`
- Test: `tests/test_big_picture_digests.py`

- [ ] **Step 1: Append the failing tests**

```python
# append to tests/test_big_picture_digests.py
from science_tool.archive import ArchiveRow, append_row, archive_index_path
from science_tool.big_picture.digests import member_to_digest


def test_member_to_digest_built_from_index_with_aliases(tmp_path) -> None:
    idx = archive_index_path(tmp_path)
    append_row(idx, ArchiveRow(
        op="archive", id="interpretation:i01-old", kind="interpretation",
        title="Old", aliases=["i01-alias"], same_as=["interpretation:i01-sameas"],
        status="archived", consolidated_into="synthesis:d1", archived_at="T1"))
    append_row(idx, ArchiveRow(
        op="archive", id="interpretation:i02-old", kind="interpretation",
        status="archived", consolidated_into="synthesis:d1", archived_at="T1"))
    assert member_to_digest(tmp_path) == {
        "interpretation:i01-old": "synthesis:d1",
        "i01-alias": "synthesis:d1",
        "interpretation:i01-sameas": "synthesis:d1",
        "interpretation:i02-old": "synthesis:d1",
    }


def test_member_to_digest_excludes_plain_archives(tmp_path) -> None:
    # A plain P3 archive (no consolidated_into) must NOT appear in the map.
    append_row(archive_index_path(tmp_path), ArchiveRow(
        op="archive", id="finding:f1", kind="finding", status="archived", archived_at="T1"))
    assert member_to_digest(tmp_path) == {}


def test_member_to_digest_empty_when_no_index(tmp_path) -> None:
    assert member_to_digest(tmp_path) == {}
```

- [ ] **Step 2: Run; expect failure**

Run: `rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_big_picture_digests.py -q`
Expected: FAIL — `ImportError: cannot import name 'member_to_digest'`.

- [ ] **Step 3: Add the function to `digests.py`**

```python
def member_to_digest(project_root: Path) -> dict[str, str]:
    """``member_id -> digest_id`` built from the ACTIVE archive index.

    For each active ``ArchiveRow`` whose ``consolidated_into`` is set, map
    ``row.id`` plus each of ``row.aliases`` / ``row.same_as`` to
    ``consolidated_into``. Building from the index (not from digest
    ``sci:consolidates`` relations) guarantees only genuinely-archived members
    redirect; a scaffolded-but-unapplied digest's members are absent from the index
    and resolve normally as live.

    Raises ``ValueError`` if a key maps to two different digests — an index
    integrity violation P4 ``apply_consolidation`` makes impossible for applied
    members (it fails loud on an already-archived member)."""
    index = load_archive_index(project_root)
    out: dict[str, str] = {}
    for canonical, row in index.active_by_id.items():
        digest = row.consolidated_into
        if not digest:
            continue
        for key in (canonical, *row.aliases, *row.same_as):
            existing = out.get(key)
            if existing is not None and existing != digest:
                raise ValueError(
                    f"member {key!r} maps to two digests: {existing!r} and {digest!r}"
                )
            out[key] = digest
    return out
```

- [ ] **Step 4: Run; expect pass**

Run: `rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_big_picture_digests.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
rtk git add src/science_tool/big_picture/digests.py tests/test_big_picture_digests.py
rtk git commit -m "feat(big-picture): member_to_digest map from the active archive index"
```

---

## Task 3: `digests.py` — `load_cluster_digests` (default + `--deep`)

**Files:**
- Modify: `src/science_tool/big_picture/digests.py`
- Test: `tests/test_big_picture_digests.py`

- [ ] **Step 1: Append the failing tests**

```python
# append to tests/test_big_picture_digests.py
from science_tool.big_picture.digests import load_cluster_digests


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_load_cluster_digests_default_ignores_non_digest_synthesis(tmp_path) -> None:
    syn = tmp_path / "entities" / "synthesis"
    _write(syn / "0001-d.md",
        '---\nid: "synthesis:0001-d"\ntitle: "Partition digest"\n'
        'report_kind: "cluster-digest"\nstatus: "active"\n'
        'related: ["question:q01", "hypothesis:h01"]\n'
        'relations:\n  - predicate: "sci:consolidates"\n    target: "interpretation:i01-old"\n'
        '  - predicate: "sci:consolidates"\n    target: "interpretation:i02-old"\n---\nbody\n')
    _write(syn / "0002-roll.md",
        '---\nid: "synthesis:0002-roll"\nreport_kind: "synthesis-rollup"\nstatus: "active"\n---\nx\n')

    digests = load_cluster_digests(tmp_path)
    assert set(digests) == {"synthesis:0001-d"}
    d = digests["synthesis:0001-d"]
    assert d.title == "Partition digest"
    assert d.related == ["question:q01", "hypothesis:h01"]
    assert d.member_ids == ["interpretation:i01-old", "interpretation:i02-old"]
    assert d.member_count == 2
    assert d.members == []  # default is not deep


def test_load_cluster_digests_deep_pulls_index_only_summaries(tmp_path) -> None:
    syn = tmp_path / "entities" / "synthesis"
    _write(syn / "0001-d.md",
        '---\nid: "synthesis:0001-d"\ntitle: "D"\nreport_kind: "cluster-digest"\nstatus: "active"\n'
        'relations:\n  - predicate: "sci:consolidates"\n    target: "interpretation:i01-old"\n'
        '  - predicate: "sci:consolidates"\n    target: "interpretation:i02-old"\n---\nx\n')
    append_row(archive_index_path(tmp_path), ArchiveRow(
        op="archive", id="interpretation:i01-old", kind="interpretation",
        title="Old i01", status="archived", consolidated_into="synthesis:0001-d",
        digest_insight="i01 says X", archived_at="T1"))

    d = load_cluster_digests(tmp_path, deep=True)["synthesis:0001-d"]
    # i01 is archived+indexed; i02 absent (e.g. not yet applied) -> archived=False.
    assert [(m.id, m.archived, m.digest_insight) for m in d.members] == [
        ("interpretation:i01-old", True, "i01 says X"),
        ("interpretation:i02-old", False, None),
    ]


def test_load_cluster_digests_empty_without_synthesis_dir(tmp_path) -> None:
    assert load_cluster_digests(tmp_path) == {}
```

- [ ] **Step 2: Run; expect failure**

Run: `rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_big_picture_digests.py -q`
Expected: FAIL — `ImportError: cannot import name 'load_cluster_digests'`.

- [ ] **Step 3: Add the function to `digests.py`**

```python
def load_cluster_digests(project_root: Path, *, deep: bool = False) -> dict[str, ClusterDigest]:
    """Scan ``entities/synthesis/`` for visible ``report_kind: cluster-digest``
    entities. ``member_ids`` come from each digest's ``sci:consolidates`` relations.
    When ``deep`` is True, each member is resolved against the active archive index
    into a ``MemberSummary`` (``archived=False`` when the id is absent — e.g. a
    scaffolded-but-unapplied digest whose members are still live)."""
    directory = entity_dir(project_root, SYNTHESIS_KIND)
    if not directory.is_dir():
        return {}
    index = load_archive_index(project_root) if deep else None
    out: dict[str, ClusterDigest] = {}
    for path in sorted(directory.glob("*.md")):
        fm = read_frontmatter(path)
        if not fm or "id" not in fm:
            continue
        if fm.get("report_kind") != CLUSTER_DIGEST_REPORT_KIND:
            continue
        if not is_default_visible(fm.get("status")):
            continue
        member_ids = _consolidates_targets(fm)
        members: list[MemberSummary] = []
        if deep:
            assert index is not None
            for mid in member_ids:
                row = index.active_by_id.get(mid)
                if row is None:
                    members.append(MemberSummary(
                        id=mid, kind=None, title=None, digest_insight=None, archived=False))
                else:
                    members.append(MemberSummary(
                        id=mid, kind=row.kind, title=row.title,
                        digest_insight=row.digest_insight, archived=True))
        digest_id = str(fm["id"])
        title = str(fm["title"]) if fm.get("title") is not None else None
        out[digest_id] = ClusterDigest(
            id=digest_id, title=title, related=_as_list(fm.get("related")),
            member_ids=member_ids, member_count=len(member_ids), members=members)
    return out
```

- [ ] **Step 4: Run; expect pass**

Run: `rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_big_picture_digests.py -q`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
rtk git add src/science_tool/big_picture/digests.py tests/test_big_picture_digests.py
rtk git commit -m "feat(big-picture): load_cluster_digests (default + index-only --deep)"
```

---

## Task 4: `resolver.py` — digest-as-bridge

**Files:**
- Modify: `src/science_tool/big_picture/resolver.py`
- Test: `tests/test_resolver_digest_bridge.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_resolver_digest_bridge.py
from __future__ import annotations

from science_tool.big_picture.resolver import resolve_questions


def _mk(tmp_path):
    (tmp_path / "science.yaml").write_text("name: vis\n", encoding="utf-8")
    for sub in ("questions", "hypotheses", "synthesis"):
        (tmp_path / "entities" / sub).mkdir(parents=True)
    (tmp_path / "entities" / "questions" / "q01.md").write_text(
        '---\nid: "question:q01"\ntype: "question"\n---\nQ.\n', encoding="utf-8")
    (tmp_path / "entities" / "hypotheses" / "h01.md").write_text(
        '---\nid: "hypothesis:h01"\ntype: "hypothesis"\n---\nH.\n', encoding="utf-8")
    return tmp_path


def test_digest_bridges_question_to_hypothesis(tmp_path) -> None:
    root = _mk(tmp_path)
    (root / "entities" / "synthesis" / "0001-d.md").write_text(
        '---\nid: "synthesis:0001-d"\ntitle: "D"\nreport_kind: "cluster-digest"\n'
        'status: "active"\nrelated: ["question:q01", "hypothesis:h01"]\n'
        'relations:\n  - predicate: "sci:consolidates"\n    target: "interpretation:i01-old"\n---\nx\n',
        encoding="utf-8")
    out = resolve_questions(root)
    assert out["question:q01"].primary_hypothesis == "hypothesis:h01"
    m = next(x for x in out["question:q01"].hypotheses if x.id == "hypothesis:h01")
    assert m.confidence == "transitive" and m.score == 0.5


def test_no_digest_means_no_bridge(tmp_path) -> None:
    root = _mk(tmp_path)
    out = resolve_questions(root)
    assert out["question:q01"].hypotheses == []


def test_non_cluster_digest_synthesis_does_not_bridge(tmp_path) -> None:
    root = _mk(tmp_path)
    (root / "entities" / "synthesis" / "0001-r.md").write_text(
        '---\nid: "synthesis:0001-r"\nreport_kind: "synthesis-rollup"\nstatus: "active"\n'
        'related: ["question:q01", "hypothesis:h01"]\n---\nx\n', encoding="utf-8")
    out = resolve_questions(root)
    assert out["question:q01"].hypotheses == []  # only cluster-digests bridge
```

- [ ] **Step 2: Run; expect failure**

Run: `rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_resolver_digest_bridge.py -q`
Expected: FAIL on `test_digest_bridges_question_to_hypothesis` (no bridge yet → empty hypotheses).

- [ ] **Step 3: Add the digest-as-bridge pass to `resolve_questions`**

Add the import near the other `big_picture` imports at the top of `resolver.py`:

```python
from science_tool.big_picture.digests import load_cluster_digests
```

Then, immediately AFTER the existing transitive-via-interpretation loop (the block
that ends the four-line nested `for qid in q_refs: for hid in h_refs:` over
`interpretations`) and BEFORE the `out: dict[str, ResolverOutput] = {}` assembly,
insert:

```python
    # Transitive via cluster-digests: a digest authored to bridge a question and a
    # hypothesis inherits the bridging role its archived members used to play (P5
    # Tier 4). Same confidence as an interpretation bridge.
    for digest in load_cluster_digests(project_root).values():
        refs = digest.related
        q_refs = [r for r in refs if r in results]
        h_refs = [r for r in refs if r in hypotheses]
        for qid in q_refs:
            for hid in h_refs:
                if hid not in results[qid]:
                    results[qid][hid] = HypothesisMatch(hid, "transitive", 0.5)
```

(No `redirect_refs` here — redirect is a provable no-op in the resolver, design §3.2.)

- [ ] **Step 4: Run; expect pass**

Run: `rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_resolver_digest_bridge.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Regression — the existing resolver suite must stay green**

Run: `rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_big_picture_resolver.py -q`
Expected: PASS, unchanged count. (The `minimal_project` fixture has no
`cluster-digest` synthesis, so the new pass is a no-op there — this is the
zero-consolidation regression guard.)

- [ ] **Step 6: Commit**

```bash
rtk git add src/science_tool/big_picture/resolver.py tests/test_resolver_digest_bridge.py
rtk git commit -m "feat(big-picture): digest-as-bridge in question->hypothesis resolver"
```

---

## Task 5: `knowledge_gaps.py` inherits the restored bridge (test only)

**Files:**
- Test: `tests/test_knowledge_gaps_digest_bridge.py`
- **No production change** — `knowledge_gaps` consumes `resolve_questions`, so the
  digest bridge flows into `TopicGap.hypotheses` via `_hypotheses_for` for free
  (design §3.3).

- [ ] **Step 1: Write the behavioral test**

```python
# tests/test_knowledge_gaps_digest_bridge.py
from __future__ import annotations

from science_tool.big_picture.knowledge_gaps import compute_topic_gaps
from science_tool.big_picture.resolver import resolve_questions


def test_topic_gap_hypotheses_include_a_digest_bridged_hypothesis(tmp_path) -> None:
    (tmp_path / "science.yaml").write_text("name: vis\n", encoding="utf-8")

    def w(rel, txt):
        p = tmp_path / "entities" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, encoding="utf-8")

    # topic t01 has demand (q01 references it) and zero paper coverage -> a gap.
    w("topics/t01.md", '---\nid: "topic:t01"\ntype: "topic"\nrelated: []\n---\n')
    w("questions/q01.md", '---\nid: "question:q01"\ntype: "question"\nrelated: ["topic:t01"]\n---\n')
    w("hypotheses/h01.md", '---\nid: "hypothesis:h01"\ntype: "hypothesis"\n---\n')
    # q01 reaches h01 ONLY through the digest bridge (no live interpretation exists).
    w("synthesis/0001-d.md",
      '---\nid: "synthesis:0001-d"\ntitle: "D"\nreport_kind: "cluster-digest"\nstatus: "active"\n'
      'related: ["question:q01", "hypothesis:h01"]\n'
      'relations:\n  - predicate: "sci:consolidates"\n    target: "interpretation:i01-old"\n---\n')

    resolved = resolve_questions(tmp_path)
    assert resolved["question:q01"].primary_hypothesis == "hypothesis:h01"
    gaps = compute_topic_gaps(tmp_path, resolved, included_question_ids=set(resolved))
    t01 = next(g for g in gaps if g.topic_id == "topic:t01")
    assert t01.demand >= 1 and t01.gap_score >= 1
    assert "hypothesis:h01" in t01.hypotheses  # inherited from the resolver's digest bridge
```

- [ ] **Step 2: Run; expect pass with NO production change**

Run: `rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_knowledge_gaps_digest_bridge.py -q`
Expected: PASS. If it fails, do NOT add redirect plumbing to `knowledge_gaps.py`
(that would be the dead code §3.3 rejects); instead verify Task 4 landed correctly
— the bridge must come through `resolve_questions`.

- [ ] **Step 3: Regression — existing knowledge-gaps suite stays green**

Run: `rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_knowledge_gaps.py tests/test_knowledge_gaps_visibility.py -q`
Expected: PASS, unchanged.

- [ ] **Step 4: Commit**

```bash
rtk git add tests/test_knowledge_gaps_digest_bridge.py
rtk git commit -m "test(big-picture): knowledge-gaps inherits the digest q<->h bridge"
```

---

## Task 6: `cli.py` — `big-picture cluster-digests` subcommand

**Files:**
- Modify: `src/science_tool/big_picture/cli.py`
- Test: `tests/test_cluster_digests_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cluster_digests_cli.py
from __future__ import annotations

import json

from click.testing import CliRunner

from science_tool.archive import ArchiveRow, append_row, archive_index_path
from science_tool.cli import main


def _project(tmp_path):
    syn = tmp_path / "entities" / "synthesis"
    syn.mkdir(parents=True)
    (syn / "0001-d.md").write_text(
        '---\nid: "synthesis:0001-d"\ntitle: "Partition digest"\n'
        'report_kind: "cluster-digest"\nstatus: "active"\n'
        'related: ["question:q01", "hypothesis:h01"]\n'
        'relations:\n  - predicate: "sci:consolidates"\n    target: "interpretation:i01-old"\n'
        '  - predicate: "sci:consolidates"\n    target: "interpretation:i02-old"\n---\nbody\n',
        encoding="utf-8")
    append_row(archive_index_path(tmp_path), ArchiveRow(
        op="archive", id="interpretation:i01-old", kind="interpretation", title="Old i01",
        aliases=["i01-alias"], status="archived", consolidated_into="synthesis:0001-d",
        digest_insight="i01 says X", archived_at="T1"))
    return tmp_path


def test_cluster_digests_group_lists_subcommand() -> None:
    result = CliRunner().invoke(main, ["big-picture", "--help"])
    assert result.exit_code == 0
    assert "cluster-digests" in result.output


def test_cluster_digests_default_contract(tmp_path) -> None:
    root = _project(tmp_path)
    result = CliRunner().invoke(main, ["big-picture", "cluster-digests", "--project-root", str(root)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert set(payload) == {"digests", "member_to_digest"}
    d = payload["digests"]["synthesis:0001-d"]
    assert d["member_count"] == 2
    assert d["member_ids"] == ["interpretation:i01-old", "interpretation:i02-old"]
    assert d["members"] == []  # default: not deep
    assert payload["member_to_digest"] == {
        "interpretation:i01-old": "synthesis:0001-d",
        "i01-alias": "synthesis:0001-d",
    }


def test_cluster_digests_deep_attaches_member_summaries(tmp_path) -> None:
    root = _project(tmp_path)
    result = CliRunner().invoke(
        main, ["big-picture", "cluster-digests", "--project-root", str(root), "--deep"])
    assert result.exit_code == 0, result.output
    members = json.loads(result.output)["digests"]["synthesis:0001-d"]["members"]
    by_id = {m["id"]: m for m in members}
    assert by_id["interpretation:i01-old"]["archived"] is True
    assert by_id["interpretation:i01-old"]["digest_insight"] == "i01 says X"
    assert by_id["interpretation:i02-old"]["archived"] is False
```

- [ ] **Step 2: Run; expect failure**

Run: `rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_cluster_digests_cli.py -q`
Expected: FAIL — `cluster-digests` not a registered command.

- [ ] **Step 3: Add the subcommand to `cli.py`**

Add the import beside the other `big_picture` imports at the top:

```python
from science_tool.big_picture.digests import load_cluster_digests, member_to_digest
```

(`asdict` and `json` are already imported.) Append this command to the group:

```python
@big_picture_group.command("cluster-digests")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Path to the project root.",
)
@click.option(
    "--deep",
    is_flag=True,
    default=False,
    help="Attach index-only member summaries (id/kind/title/digest_insight) per digest.",
)
def cluster_digests_cmd(project_root: Path, deep: bool) -> None:
    """Emit the cluster-digest registry + member->digest map as JSON.

    Recognition surface for /science:big-picture: substitute one digest for its N
    archived members (and label it); --deep descends into the members index-only.
    """
    digests = load_cluster_digests(project_root, deep=deep)
    payload = {
        "digests": {did: asdict(cd) for did, cd in sorted(digests.items())},
        "member_to_digest": member_to_digest(project_root),
    }
    click.echo(json.dumps(payload, indent=2, sort_keys=True))
```

- [ ] **Step 4: Run; expect pass**

Run: `rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_cluster_digests_cli.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Regression — existing big-picture CLI suite stays green**

Run: `rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_big_picture_cli.py -q`
Expected: PASS, unchanged (`resolve-questions` / `validate` output shapes intact).

- [ ] **Step 6: Commit**

```bash
rtk git add src/science_tool/big_picture/cli.py tests/test_cluster_digests_cli.py
rtk git commit -m "feat(big-picture): cluster-digests CLI emitting {digests, member_to_digest}"
```

---

## Task 7: End-to-end acceptance — the bridge survives the real P4 path

**Files:**
- Test: `tests/test_p5_tier4_acceptance.py`

This proves the residual risk the reviewer flagged: the restored bridge depends on
the digest being **authored with the relevant `related:` q/h edges**. The test
drives the genuine P4 `scaffold` → author `related:` → `apply` path, then asserts
the q↔h resolution that previously ran through the (now-archived) interpretation
family survives via the digest.

- [ ] **Step 1: Write the acceptance test**

```python
# tests/test_p5_tier4_acceptance.py
"""P5 Tier-4 acceptance: consolidating a bridging interpretation family leaves
big-picture seeing ONE labeled digest with N descendable members, and the q<->h
bridge SURVIVES via the digest's authored related: edges (the residual-risk path)."""
from __future__ import annotations

from pathlib import Path

from science_tool.big_picture.digests import load_cluster_digests
from science_tool.big_picture.resolver import resolve_questions
from science_tool.consolidate import apply_consolidation, scaffold_digest
from science_tool.entities import _parse_markdown_file, _render_markdown, create_entity


def _set_related(path: Path, refs: list[str]) -> None:
    fm, body = _parse_markdown_file(path)
    fm["related"] = refs
    path.write_text(_render_markdown(fm, body), encoding="utf-8")


def test_bridge_survives_consolidation(tmp_path: Path) -> None:
    root = tmp_path
    (root / "science.yaml").write_text(
        "name: t\nknowledge_profiles:\n  local: local\n", encoding="utf-8")

    create_entity(root, "question", "Q one", entity_id="question:0001-q")
    create_entity(root, "hypothesis", "H one", entity_id="hypothesis:0001-h")
    create_entity(root, "interpretation", "Interp 1", entity_id="interpretation:0001-i1")
    create_entity(root, "interpretation", "Interp 2", entity_id="interpretation:0002-i2")
    # Both interpretations bridge q01 <-> h01.
    for stem in ("0001-i1", "0002-i2"):
        _set_related(root / "entities" / "interpretations" / f"{stem}.md",
                     ["question:0001-q", "hypothesis:0001-h"])

    # BEFORE: q resolves to h transitively, via the live interpretations.
    before = resolve_questions(root)
    assert before["question:0001-q"].primary_hypothesis == "hypothesis:0001-h"

    # Consolidate the family into a digest authored WITH the same q/h related: edges.
    scaffold_digest(root, digest_id="synthesis:0001-d",
                    member_ids=["interpretation:0001-i1", "interpretation:0002-i2"],
                    title="Interp digest")
    _set_related(root / "entities" / "synthesis" / "0001-d.md",
                 ["question:0001-q", "hypothesis:0001-h"])
    applied = apply_consolidation(root, "synthesis:0001-d", apply=True, now="T1")
    assert set(applied["applied"]) == {"interpretation:0001-i1", "interpretation:0002-i2"}

    # Members are gone from the live scan; the digest stands in as ONE entry with
    # N descendable members (index-only).
    assert not (root / "entities" / "interpretations" / "0001-i1.md").exists()
    digests = load_cluster_digests(root, deep=True)
    assert set(digests) == {"synthesis:0001-d"}
    d = digests["synthesis:0001-d"]
    assert d.member_count == 2
    assert {m.id for m in d.members} == {"interpretation:0001-i1", "interpretation:0002-i2"}
    assert all(m.archived for m in d.members)

    # AFTER: the q<->h bridge SURVIVES — now carried by the digest.
    after = resolve_questions(root)
    assert after["question:0001-q"].primary_hypothesis == "hypothesis:0001-h"
    m = next(x for x in after["question:0001-q"].hypotheses if x.id == "hypothesis:0001-h")
    assert m.confidence == "transitive"
```

- [ ] **Step 2: Run; expect pass**

Run: `rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_p5_tier4_acceptance.py -q`
Expected: PASS. If `create_entity` rejects an id (format/slug), keep the
`<kind>:0001-x` shape used here (P4's `test_consolidate_acceptance.py` proves it),
and adjust only the stem — do not change the assertions.

- [ ] **Step 3: Commit**

```bash
rtk git add tests/test_p5_tier4_acceptance.py
rtk git commit -m "test(big-picture): P5 acceptance — q<->h bridge survives consolidation via authored digest"
```

---

## Final verification (after all tasks; before finishing-a-development-branch)

- [ ] Run the full P5 surface together:

```bash
cd ~/d/science/.worktrees/entity-consolidation-p5-tier4-substitution/science
rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest \
  tests/test_big_picture_digests.py tests/test_resolver_digest_bridge.py \
  tests/test_knowledge_gaps_digest_bridge.py tests/test_cluster_digests_cli.py \
  tests/test_p5_tier4_acceptance.py tests/test_big_picture_resolver.py \
  tests/test_big_picture_cli.py tests/test_knowledge_gaps.py -q
```
Expected: all green.

- [ ] Sanity-check the broader suite for collateral damage (big-picture + consolidate
  + archive neighborhoods), tolerating only the known-pre-existing failures
  (6× `test_codex_skills`, `test_full_lifecycle`, `test_meta_validate_smoke_runs`):

```bash
rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest \
  tests/ -k "big_picture or consolidate or archive or knowledge_gaps or digest" -q
```

- [ ] Final whole-feature review, then **superpowers:finishing-a-development-branch**.

## Self-review notes (consistency)

- Type/name consistency: `ClusterDigest(id,title,related,member_ids,member_count,members)`
  and `MemberSummary(id,kind,title,digest_insight,archived)` are used identically in
  Tasks 1, 3, 6, 7. `member_to_digest(project_root) -> dict[str,str]` and
  `load_cluster_digests(project_root, *, deep=False)` signatures are stable across
  Tasks 2–7. The registry JSON keys `digests` / `member_to_digest` match design §3.4.
- No placeholders: every code/test step is complete and runnable.
- Scope: only `digests.py` (new), `resolver.py` (+1 pass), `cli.py` (+1 command);
  `knowledge_gaps.py` unchanged — matches the design exactly.
