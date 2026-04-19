# Knowledge Gaps in Project Synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a topic-coverage gap metric to `/science:big-picture` output, exposing topics where the project's questions demand more literature than the project has read. Render at two scales — a per-hypothesis Knowledge Gaps sub-bullet inside Research Fronts, and a project-rollup Knowledge Gaps section between Research Fronts and Emergent Threads.

**Architecture:** New module `science_tool.big_picture.knowledge_gaps` with a pure `compute_topic_gaps` function and `TopicGap` dataclass. Caller (the Opus orchestrator in Phase 1 of `commands/big-picture.md`) invokes it once per run, slicing the result per hypothesis for bundle assembly and reusing the full list for the Phase 3 rollup. A new `science-tool big-picture knowledge-gaps` CLI subcommand emits the full `TopicGap` list as JSON for inspection/debugging. The big-picture validator is extended to recognize `topic:<id>` references. The transition-window canonicalization helper from the sibling rename spec is consumed at comparison boundaries.

**Tech Stack:** Python 3.11+, pydantic v2 (existing), click (existing), pytest, PyYAML. No new runtime dependencies.

**Spec:** `docs/specs/2026-04-19-knowledge-gaps-design.md`

**Prerequisite:** `docs/plans/2026-04-19-manuscript-paper-rename.md` — Tasks 11 (literature_prefix helper) and 1–13 must land first or in the same PR.

---

## File Structure

### New files

- `science-tool/src/science_tool/big_picture/knowledge_gaps.py` — `TopicGap`, `compute_topic_gaps`, internal loaders.
- `science-tool/tests/test_knowledge_gaps.py` — unit tests for `compute_topic_gaps`.
- `science-tool/tests/test_knowledge_gaps_cli.py` — integration tests for the CLI subcommand.
- `science-tool/tests/fixtures/big_picture/minimal_project/doc/background/topics/t01-covered.md`
- `science-tool/tests/fixtures/big_picture/minimal_project/doc/background/topics/t02-thin.md`
- `science-tool/tests/fixtures/big_picture/minimal_project/doc/background/topics/t03-bibtex-covered.md`
- `science-tool/tests/fixtures/big_picture/minimal_project/doc/background/topics/t04-legacy-covered.md`
- `science-tool/tests/fixtures/big_picture/minimal_project/doc/papers/p01-example.md`
- `science-tool/tests/fixtures/big_picture/minimal_project/doc/papers/p02-legacy-article.md`

### Modified files

- `science-tool/src/science_tool/big_picture/cli.py` — register `knowledge-gaps` subcommand.
- `science-tool/src/science_tool/big_picture/validator.py` — extend `REFERENCE_PATTERN` with `topic`; extend `_collect_project_ids` to scan topic directories.
- `science-tool/tests/fixtures/big_picture/minimal_project/doc/questions/q01-direct-to-h1.md` — add topic refs.
- `science-tool/tests/fixtures/big_picture/minimal_project/doc/questions/q02-inverse-via-h1.md` — add topic refs.
- `commands/big-picture.md` — Phase 1 bundle-assembly prose; Phase 3 rollup prose.
- `science-tool/tests/test_big_picture_validator.py` — cover topic reference recognition.

### Unchanged

- `science_model.aspects` module — caller reuses the existing aspect filter.
- Resolver (`science_tool.big_picture.resolver`) — no new fields; this feature consumes its existing output.

---

## Task 1: Scaffold `knowledge_gaps` module with `TopicGap` dataclass

**Files:**
- Create: `science-tool/src/science_tool/big_picture/knowledge_gaps.py`
- Test: `science-tool/tests/test_knowledge_gaps.py`

- [ ] **Step 1: Write the failing test**

Create `science-tool/tests/test_knowledge_gaps.py`:

```python
from __future__ import annotations

from science_tool.big_picture.knowledge_gaps import TopicGap


def test_topic_gap_is_frozen_dataclass() -> None:
    tg = TopicGap(
        topic_id="topic:foo",
        coverage=1,
        demand=3,
        gap_score=2,
        demanding_questions=["question:q01"],
        hypotheses=["h1"],
    )
    assert tg.topic_id == "topic:foo"
    assert tg.gap_score == 2
    # Frozen: mutation raises.
    import dataclasses as dc
    assert dc.is_dataclass(tg) and tg.__dataclass_params__.frozen
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science-tool/tests/test_knowledge_gaps.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create the module**

Create `science-tool/src/science_tool/big_picture/knowledge_gaps.py`:

```python
"""Knowledge-gap computation for `/science:big-picture` synthesis.

Identifies topics where the project's question demand exceeds its reading
coverage. See docs/specs/2026-04-19-knowledge-gaps-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TopicGap:
    """A topic where reading lags investigation.

    Attributes
    ----------
    topic_id:
        Canonical entity ID (``topic:<slug>``).
    coverage:
        Count of distinct papers covering the topic (union of
        entity-linked + bibtex-referenced, deduplicated by bibkey).
    demand:
        Count of aspect-filtered questions whose ``related:`` field
        references this topic.
    gap_score:
        ``max(0, demand - coverage)``. Topics with ``gap_score == 0``
        are not emitted.
    demanding_questions:
        Sorted (alphabetical) list of question IDs driving the demand.
    hypotheses:
        Sorted list of hypothesis IDs whose bucket contains at least
        one demanding question.
    """

    topic_id: str
    coverage: int
    demand: int
    gap_score: int
    demanding_questions: list[str]
    hypotheses: list[str]
```

- [ ] **Step 4: Run test to verify it passes**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/knowledge_gaps.py science-tool/tests/test_knowledge_gaps.py
git commit -m "feat(knowledge_gaps): scaffold TopicGap dataclass"
```

---

## Task 2: Extend the minimal_project fixture with topic + paper files

**Files:**
- Create: `science-tool/tests/fixtures/big_picture/minimal_project/doc/background/topics/t01-covered.md`
- Create: `.../topics/t02-thin.md`
- Create: `.../topics/t03-bibtex-covered.md`
- Create: `.../topics/t04-legacy-covered.md`
- Create: `.../doc/papers/p01-example.md`
- Create: `.../doc/papers/p02-legacy-article.md`
- Modify: `.../doc/questions/q01-direct-to-h1.md`
- Modify: `.../doc/questions/q02-inverse-via-h1.md`

- [ ] **Step 1: Create topic files**

`t01-covered.md`:

```markdown
---
id: "topic:t01-covered"
type: "topic"
related: [paper:p01-example]
source_refs: []
---

# Covered topic

Has an entity-linked paper.
```

`t02-thin.md`:

```markdown
---
id: "topic:t02-thin"
type: "topic"
related: []
source_refs: []
---

# Thin topic

No coverage.
```

`t03-bibtex-covered.md`:

```markdown
---
id: "topic:t03-bibtex-covered"
type: "topic"
related: []
source_refs: [cite:Smith2024]
---

# Bibtex-covered topic

Covered only via a `cite:` source_refs entry.
```

`t04-legacy-covered.md`:

```markdown
---
id: "topic:t04-legacy-covered"
type: "topic"
related: []
source_refs: []
---

# Legacy-covered topic

Covered via a paper entity using the legacy `article:` prefix.
```

- [ ] **Step 2: Create paper files**

`doc/papers/p01-example.md`:

```markdown
---
id: "paper:p01-example"
type: "paper"
related: [topic:t01-covered]
source_refs: [cite:Example2024]
---

# Example paper
```

`doc/papers/p02-legacy-article.md`:

```markdown
---
id: "article:p02-legacy-article"
type: "article"
related: [topic:t04-legacy-covered]
source_refs: []
---

# Legacy-prefixed paper (transition-window test fixture)
```

- [ ] **Step 3: Update question files**

Add to `q01-direct-to-h1.md` frontmatter's `related:` list (preserve existing entries):

```yaml
related:
  - topic:t01-covered
  - topic:t02-thin
  - topic:t03-bibtex-covered
  - topic:t04-legacy-covered
```

Add to `q02-inverse-via-h1.md` frontmatter's `related:` list:

```yaml
related:
  - topic:t02-thin
```

These seed the expected counts:
- `t01-covered`: demand=1 (q01), coverage=1 (paper p01) → no gap.
- `t02-thin`: demand=2 (q01, q02), coverage=0 → gap_score=2.
- `t03-bibtex-covered`: demand=1, coverage=1 (cite:Smith2024) → no gap.
- `t04-legacy-covered`: demand=1, coverage=1 (via article:p02 alias) → no gap.

- [ ] **Step 4: Commit**

```bash
git add science-tool/tests/fixtures/big_picture/minimal_project
git commit -m "test(knowledge_gaps): extend minimal_project fixture with topics + papers"
```

---

## Task 3: Implement topic and paper loaders with duplicate-ID detection

**Files:**
- Modify: `science-tool/src/science_tool/big_picture/knowledge_gaps.py`
- Test: `science-tool/tests/test_knowledge_gaps.py`

- [ ] **Step 1: Write the failing tests**

Append to `science-tool/tests/test_knowledge_gaps.py`:

```python
from pathlib import Path

import pytest

from science_tool.big_picture.knowledge_gaps import _load_topics, _load_papers

FIXTURE = Path(__file__).parent / "fixtures" / "big_picture" / "minimal_project"


def test_load_topics_finds_all_fixture_topics() -> None:
    topics = _load_topics(FIXTURE)
    assert set(topics) == {
        "topic:t01-covered",
        "topic:t02-thin",
        "topic:t03-bibtex-covered",
        "topic:t04-legacy-covered",
    }


def test_load_papers_finds_both_prefix_styles() -> None:
    papers = _load_papers(FIXTURE)
    # Legacy `article:` entity canonicalizes to `paper:` in the returned keys.
    assert "paper:p01-example" in papers
    assert "paper:p02-legacy-article" in papers


def test_duplicate_topic_ids_across_topic_directories_raise(tmp_path: Path) -> None:
    import shutil
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    # Place a duplicate topic in doc/topics/ (second scanned root).
    (project / "doc" / "topics").mkdir(parents=True)
    (project / "doc" / "topics" / "t01-covered.md").write_text(
        '---\nid: "topic:t01-covered"\ntype: "topic"\nrelated: []\n---\n'
    )
    with pytest.raises(ValueError, match="t01-covered"):
        _load_topics(project)


def test_duplicate_paper_ids_across_paper_directories_raise(tmp_path: Path) -> None:
    import shutil
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    (project / "doc" / "background" / "papers").mkdir(parents=True)
    (project / "doc" / "background" / "papers" / "p01-example.md").write_text(
        '---\nid: "paper:p01-example"\ntype: "paper"\nrelated: []\n---\n'
    )
    with pytest.raises(ValueError, match="p01-example"):
        _load_papers(project)
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement loaders**

Append to `science-tool/src/science_tool/big_picture/knowledge_gaps.py`:

```python
from pathlib import Path

from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.big_picture.literature_prefix import (
    canonical_paper_id,
    is_external_paper_id,
)

_TOPIC_DIRS = ("doc/topics", "doc/background/topics")
_PAPER_DIRS = ("doc/papers", "doc/background/papers")


def _load_topics(project_root: Path) -> dict[str, dict]:
    """Return ``{topic_id: frontmatter_dict}`` for every topic in the project.

    Raises ``ValueError`` if two topic files share an entity ID.
    """
    topics: dict[str, dict] = {}
    origins: dict[str, Path] = {}
    for rel in _TOPIC_DIRS:
        root = project_root / rel
        if not root.is_dir():
            continue
        for md in sorted(root.glob("*.md")):
            fm = read_frontmatter(md) or {}
            eid = fm.get("id")
            if not eid:
                continue
            if eid in topics:
                raise ValueError(
                    f"Duplicate topic id {eid!r}: {origins[eid]} vs {md}"
                )
            topics[eid] = fm
            origins[eid] = md
    return topics


def _load_papers(project_root: Path) -> dict[str, dict]:
    """Return ``{canonical_paper_id: frontmatter_dict}`` for every paper.

    External-literature IDs are normalized via
    :func:`literature_prefix.canonical_paper_id` before use as keys. A raw
    ``article:X`` file and a raw ``paper:X`` file across the scanned
    directories would collide at the canonical form — that collision raises.
    """
    papers: dict[str, dict] = {}
    origins: dict[str, Path] = {}
    for rel in _PAPER_DIRS:
        root = project_root / rel
        if not root.is_dir():
            continue
        for md in sorted(root.glob("*.md")):
            fm = read_frontmatter(md) or {}
            raw_id = fm.get("id")
            if not raw_id or not is_external_paper_id(raw_id):
                continue
            canonical = canonical_paper_id(raw_id)
            if canonical in papers:
                raise ValueError(
                    f"Duplicate paper id {canonical!r} (via {raw_id}): "
                    f"{origins[canonical]} vs {md}"
                )
            papers[canonical] = fm
            origins[canonical] = md
    return papers
```

- [ ] **Step 4: Run tests to verify they pass**

Expected: PASS (4 new tests).

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/knowledge_gaps.py science-tool/tests/test_knowledge_gaps.py
git commit -m "feat(knowledge_gaps): add topic/paper loaders with dup-ID detection"
```

---

## Task 4: Implement per-topic coverage computation

**Files:**
- Modify: `science-tool/src/science_tool/big_picture/knowledge_gaps.py`
- Test: `science-tool/tests/test_knowledge_gaps.py`

- [ ] **Step 1: Write the failing tests**

Append to `science-tool/tests/test_knowledge_gaps.py`:

```python
from science_tool.big_picture.knowledge_gaps import _compute_coverage


def test_coverage_via_entity_linked_paper() -> None:
    topics = _load_topics(FIXTURE)
    papers = _load_papers(FIXTURE)
    cov = _compute_coverage("topic:t01-covered", topics, papers)
    assert cov == 1


def test_coverage_zero_for_uncovered_topic() -> None:
    topics = _load_topics(FIXTURE)
    papers = _load_papers(FIXTURE)
    assert _compute_coverage("topic:t02-thin", topics, papers) == 0


def test_coverage_via_bibtex_source_refs() -> None:
    topics = _load_topics(FIXTURE)
    papers = _load_papers(FIXTURE)
    assert _compute_coverage("topic:t03-bibtex-covered", topics, papers) == 1


def test_coverage_accepts_article_prefix_paper_as_legacy_alias() -> None:
    topics = _load_topics(FIXTURE)
    papers = _load_papers(FIXTURE)
    # p02 has id: article:... which canonicalizes to paper:p02-legacy-article
    # and lists topic:t04 as a relation.
    assert _compute_coverage("topic:t04-legacy-covered", topics, papers) == 1


def test_coverage_dedupes_bibkey_across_entity_and_source_refs(tmp_path: Path) -> None:
    # Same bibkey reached via both paper entity AND topic's source_refs:
    # should count as 1, not 2.
    import shutil
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    # Edit t01 to also source_refs the same bibkey as its entity-linked paper.
    t01 = project / "doc" / "background" / "topics" / "t01-covered.md"
    text = t01.read_text()
    text = text.replace(
        "source_refs: []",
        "source_refs: [cite:p01-example]",
    )
    t01.write_text(text)

    topics = _load_topics(project)
    papers = _load_papers(project)
    assert _compute_coverage("topic:t01-covered", topics, papers) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `_compute_coverage`**

Append to `science-tool/src/science_tool/big_picture/knowledge_gaps.py`:

```python
def _bibkey_of(entity_id: str) -> str | None:
    """Return the bibkey substring (after first colon) or None."""
    _, _, rest = entity_id.partition(":")
    return rest or None


def _compute_coverage(
    topic_id: str,
    topics: dict[str, dict],
    papers: dict[str, dict],
) -> int:
    """Compute |related_papers(T) ∪ inverse_papers(T) ∪ bibtex_refs(T)|.

    Dedup uses bibkey-based comparison per the canonical rule in the
    manuscript+paper rename spec (§Canonical bibkey extraction).
    """
    topic_fm = topics.get(topic_id)
    if topic_fm is None:
        return 0

    covering_bibkeys: set[str] = set()

    # related_papers(T): T.related entries that are external paper IDs.
    for ref in topic_fm.get("related", []) or []:
        if is_external_paper_id(ref):
            canonical = canonical_paper_id(ref)
            bibkey = _bibkey_of(canonical)
            if bibkey:
                covering_bibkeys.add(bibkey)

    # inverse_papers(T): papers whose .related lists T.
    for canonical_pid, paper_fm in papers.items():
        for ref in paper_fm.get("related", []) or []:
            if ref == topic_id:
                bibkey = _bibkey_of(canonical_pid)
                if bibkey:
                    covering_bibkeys.add(bibkey)

    # bibtex_refs(T): T.source_refs entries of the form cite:<key>.
    for ref in topic_fm.get("source_refs", []) or []:
        if isinstance(ref, str) and ref.startswith("cite:"):
            bibkey = ref[len("cite:"):]
            if bibkey:
                covering_bibkeys.add(bibkey)

    return len(covering_bibkeys)
```

- [ ] **Step 4: Run tests to verify they pass**

Expected: PASS (5 new tests).

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/knowledge_gaps.py science-tool/tests/test_knowledge_gaps.py
git commit -m "feat(knowledge_gaps): implement coverage computation with bibkey dedup"
```

---

## Task 5: Implement demand computation from resolved questions

**Files:**
- Modify: `science-tool/src/science_tool/big_picture/knowledge_gaps.py`
- Test: `science-tool/tests/test_knowledge_gaps.py`

- [ ] **Step 1: Write the failing tests**

Append to `science-tool/tests/test_knowledge_gaps.py`:

```python
from science_tool.big_picture.knowledge_gaps import _compute_demand
from science_tool.big_picture.resolver import resolve_questions


def test_demand_counts_direct_references() -> None:
    resolved = resolve_questions(FIXTURE)
    included = set(resolved.keys())
    # q01 references t02-thin (per fixture task); q02 also references it.
    demand, demanders = _compute_demand(FIXTURE, "topic:t02-thin", included)
    assert demand == 2
    assert set(demanders) == {"question:q01-direct-to-h1", "question:q02-inverse-via-h1"}


def test_demand_respects_included_question_ids_filter() -> None:
    resolved = resolve_questions(FIXTURE)
    # Exclude q02 via the filter argument; demand for t02 drops to 1.
    included = {qid for qid in resolved if qid != "question:q02-inverse-via-h1"}
    demand, demanders = _compute_demand(FIXTURE, "topic:t02-thin", included)
    assert demand == 1
    assert demanders == ["question:q01-direct-to-h1"]


def test_demand_zero_for_unreferenced_topic(tmp_path: Path) -> None:
    import shutil
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    # Add an orphan topic nobody references.
    (project / "doc" / "background" / "topics" / "t99-orphan.md").write_text(
        '---\nid: "topic:t99-orphan"\ntype: "topic"\nrelated: []\n---\n'
    )
    resolved = resolve_questions(project)
    demand, demanders = _compute_demand(project, "topic:t99-orphan", set(resolved))
    assert demand == 0
    assert demanders == []
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `_compute_demand`**

Append to `science-tool/src/science_tool/big_picture/knowledge_gaps.py`:

```python
import logging

_logger = logging.getLogger(__name__)


def _compute_demand(
    project_root: Path,
    topic_id: str,
    included_question_ids: set[str],
) -> tuple[int, list[str]]:
    """Return ``(count, sorted_list)`` of aspect-filtered questions
    referencing ``topic_id`` in their ``related:`` field.

    Only considers questions present in ``included_question_ids`` (aspect
    filter already applied by the caller).
    """
    questions_dir = project_root / "doc" / "questions"
    if not questions_dir.is_dir():
        return 0, []

    demanders: list[str] = []
    for md in sorted(questions_dir.glob("*.md")):
        fm = read_frontmatter(md) or {}
        qid = fm.get("id")
        if not qid or qid not in included_question_ids:
            continue
        related = fm.get("related", []) or []
        if topic_id in related:
            demanders.append(qid)
    return len(demanders), sorted(demanders)
```

- [ ] **Step 4: Run tests to verify they pass**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/knowledge_gaps.py science-tool/tests/test_knowledge_gaps.py
git commit -m "feat(knowledge_gaps): implement demand computation"
```

---

## Task 6: Wire `compute_topic_gaps` (public entry point)

**Files:**
- Modify: `science-tool/src/science_tool/big_picture/knowledge_gaps.py`
- Test: `science-tool/tests/test_knowledge_gaps.py`

- [ ] **Step 1: Write the failing tests**

Append to `science-tool/tests/test_knowledge_gaps.py`:

```python
from science_tool.big_picture.knowledge_gaps import compute_topic_gaps


def test_compute_topic_gaps_end_to_end_on_fixture() -> None:
    resolved = resolve_questions(FIXTURE)
    included = set(resolved.keys())
    gaps = compute_topic_gaps(FIXTURE, resolved, included)

    # Only t02-thin has demand > coverage in the seeded fixture.
    assert [g.topic_id for g in gaps] == ["topic:t02-thin"]
    gap = gaps[0]
    assert gap.demand == 2
    assert gap.coverage == 0
    assert gap.gap_score == 2
    assert gap.demanding_questions == [
        "question:q01-direct-to-h1",
        "question:q02-inverse-via-h1",
    ]


def test_compute_topic_gaps_excludes_zero_demand() -> None:
    resolved = resolve_questions(FIXTURE)
    gaps = compute_topic_gaps(FIXTURE, resolved, set(resolved))
    # No gap entry for t03 (bibtex-covered, demand=coverage), t01, t04.
    assert all(g.topic_id != "topic:t01-covered" for g in gaps)
    assert all(g.topic_id != "topic:t03-bibtex-covered" for g in gaps)
    assert all(g.topic_id != "topic:t04-legacy-covered" for g in gaps)


def test_compute_topic_gaps_sort_order_stable(tmp_path: Path) -> None:
    # Two topics with equal gap_score → alphabetical tiebreak.
    import shutil
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    (project / "doc" / "background" / "topics" / "t05-alpha-gap.md").write_text(
        '---\nid: "topic:t05-alpha-gap"\ntype: "topic"\nrelated: []\nsource_refs: []\n---\n'
    )
    q01 = project / "doc" / "questions" / "q01-direct-to-h1.md"
    text = q01.read_text()
    text = text.replace(
        "- topic:t02-thin",
        "- topic:t02-thin\n  - topic:t05-alpha-gap",
    )
    q01.write_text(text)

    resolved = resolve_questions(project)
    gaps = compute_topic_gaps(project, resolved, set(resolved))
    # t02-thin has gap_score=2; t05 has gap_score=1. Sort: 2 first, then 1.
    # If fixtures yielded equal gap_scores, t02 would sort before t05 alphabetically.
    ordered = [g.topic_id for g in gaps]
    assert ordered == sorted(ordered, key=lambda x: (-next(g.gap_score for g in gaps if g.topic_id == x), x))


def test_article_prefix_accepted_during_transition() -> None:
    # t04-legacy-covered has demand=1 and coverage=1 only via article:p02.
    # Ensure NO gap is flagged (transition-window alias must count).
    resolved = resolve_questions(FIXTURE)
    gaps = compute_topic_gaps(FIXTURE, resolved, set(resolved))
    assert all(g.topic_id != "topic:t04-legacy-covered" for g in gaps)
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: FAIL.

- [ ] **Step 3: Implement `compute_topic_gaps`**

Append to `science-tool/src/science_tool/big_picture/knowledge_gaps.py`:

```python
from science_tool.big_picture.resolver import ResolverOutput


def compute_topic_gaps(
    project_root: Path,
    resolved_questions: dict[str, ResolverOutput],
    included_question_ids: set[str],
) -> list[TopicGap]:
    """Return all topics with demand > 0 and coverage < demand.

    Sorted by ``gap_score`` descending; ties broken by ``topic_id`` ascending.

    The caller (typically the Opus orchestrator) is responsible for computing
    ``included_question_ids`` via the big-picture aspect filter before
    invoking this function. See the knowledge-gaps spec §Aspect Integration.
    """
    topics = _load_topics(project_root)
    papers = _load_papers(project_root)

    gaps: list[TopicGap] = []
    for topic_id in topics:
        demand, demanders = _compute_demand(project_root, topic_id, included_question_ids)
        if demand == 0:
            continue
        coverage = _compute_coverage(topic_id, topics, papers)
        if coverage >= demand:
            continue
        hypotheses = _hypotheses_for(demanders, resolved_questions)
        gaps.append(
            TopicGap(
                topic_id=topic_id,
                coverage=coverage,
                demand=demand,
                gap_score=max(0, demand - coverage),
                demanding_questions=demanders,
                hypotheses=hypotheses,
            )
        )

    gaps.sort(key=lambda g: (-g.gap_score, g.topic_id))
    return gaps


def _hypotheses_for(
    demander_question_ids: list[str],
    resolved: dict[str, ResolverOutput],
) -> list[str]:
    """Return sorted hypothesis IDs associated with any demanding question."""
    ids: set[str] = set()
    for qid in demander_question_ids:
        out = resolved.get(qid)
        if out is None:
            continue
        for match in out.hypotheses:
            ids.add(match.id)
    return sorted(ids)
```

- [ ] **Step 4: Run tests to verify they pass**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/knowledge_gaps.py science-tool/tests/test_knowledge_gaps.py
git commit -m "feat(knowledge_gaps): wire compute_topic_gaps entry point"
```

---

## Task 7: Add warning logs for dangling refs and malformed source_refs

**Files:**
- Modify: `science-tool/src/science_tool/big_picture/knowledge_gaps.py`
- Test: `science-tool/tests/test_knowledge_gaps.py`

- [ ] **Step 1: Write the failing tests**

Append to `science-tool/tests/test_knowledge_gaps.py`:

```python
def test_dangling_topic_ref_logs_warning(tmp_path: Path, caplog) -> None:
    import shutil
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    # Add a dangling topic ref to q01.
    q01 = project / "doc" / "questions" / "q01-direct-to-h1.md"
    text = q01.read_text()
    text = text.replace(
        "- topic:t02-thin",
        "- topic:t02-thin\n  - topic:does-not-exist",
    )
    q01.write_text(text)

    resolved = resolve_questions(project)
    with caplog.at_level("WARNING", logger="science_tool.big_picture.knowledge_gaps"):
        gaps = compute_topic_gaps(project, resolved, set(resolved))
    assert any("does-not-exist" in r.getMessage() for r in caplog.records)
    # Does not raise; does not count toward any topic's demand.
    assert all(g.topic_id != "topic:does-not-exist" for g in gaps)


def test_malformed_source_refs_logs_warning(tmp_path: Path, caplog) -> None:
    import shutil
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    t03 = project / "doc" / "background" / "topics" / "t03-bibtex-covered.md"
    text = t03.read_text()
    text = text.replace(
        "source_refs: [cite:Smith2024]",
        "source_refs: [cite:Smith2024, not-a-cite-entry]",
    )
    t03.write_text(text)

    resolved = resolve_questions(project)
    with caplog.at_level("WARNING", logger="science_tool.big_picture.knowledge_gaps"):
        compute_topic_gaps(project, resolved, set(resolved))
    assert any("not-a-cite-entry" in r.getMessage() for r in caplog.records)
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: FAIL.

- [ ] **Step 3: Add warning emission**

In `science-tool/src/science_tool/big_picture/knowledge_gaps.py`, modify `_compute_coverage` to warn on malformed `source_refs:` entries:

```python
# Inside _compute_coverage, replace the source_refs loop:
for ref in topic_fm.get("source_refs", []) or []:
    if not isinstance(ref, str):
        _logger.warning(
            "topic %s has non-string source_refs entry %r; ignoring",
            topic_id, ref,
        )
        continue
    if ref.startswith("cite:"):
        bibkey = ref[len("cite:"):]
        if bibkey:
            covering_bibkeys.add(bibkey)
    else:
        _logger.warning(
            "topic %s has malformed source_refs entry %r (expected cite:<key>); ignoring",
            topic_id, ref,
        )
```

Add to `_compute_demand` a warning pass for `topic:<X>` references that do not correspond to any loaded topic file. Rewrite `_compute_demand` to accept the loaded topics dict (so it knows which topic IDs are valid):

```python
def _compute_demand(
    project_root: Path,
    topic_id: str,
    included_question_ids: set[str],
    *,
    known_topic_ids: set[str] | None = None,
) -> tuple[int, list[str]]:
    """See module docstring.

    If ``known_topic_ids`` is provided, any question's ``related:`` entry of
    the form ``topic:<X>`` that is not in ``known_topic_ids`` is logged as a
    warning (once per unknown topic ID across the call).
    """
    questions_dir = project_root / "doc" / "questions"
    if not questions_dir.is_dir():
        return 0, []

    demanders: list[str] = []
    warned: set[str] = set()
    for md in sorted(questions_dir.glob("*.md")):
        fm = read_frontmatter(md) or {}
        qid = fm.get("id")
        if not qid or qid not in included_question_ids:
            continue
        related = fm.get("related", []) or []
        if topic_id in related:
            demanders.append(qid)
        if known_topic_ids is not None:
            for ref in related:
                if (
                    isinstance(ref, str)
                    and ref.startswith("topic:")
                    and ref not in known_topic_ids
                    and ref not in warned
                ):
                    _logger.warning(
                        "question %s references unknown %s; excluded from demand",
                        qid, ref,
                    )
                    warned.add(ref)
    return len(demanders), sorted(demanders)
```

Update `compute_topic_gaps` to pass `known_topic_ids=set(topics)` into `_compute_demand`.

- [ ] **Step 4: Run tests to verify they pass**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/knowledge_gaps.py science-tool/tests/test_knowledge_gaps.py
git commit -m "feat(knowledge_gaps): warn on dangling topic refs + malformed source_refs"
```

---

## Task 8: Register `knowledge-gaps` CLI subcommand

**Files:**
- Modify: `science-tool/src/science_tool/big_picture/cli.py`
- Create: `science-tool/tests/test_knowledge_gaps_cli.py`

- [ ] **Step 1: Write the failing test**

Create `science-tool/tests/test_knowledge_gaps_cli.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.big_picture.cli import big_picture_group

FIXTURE = Path(__file__).parent / "fixtures" / "big_picture" / "minimal_project"


def test_knowledge_gaps_cli_emits_json() -> None:
    result = CliRunner().invoke(
        big_picture_group,
        ["knowledge-gaps", "--project-root", str(FIXTURE)],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert isinstance(payload, list)
    ids = [entry["topic_id"] for entry in payload]
    assert "topic:t02-thin" in ids


def test_knowledge_gaps_cli_respects_limit() -> None:
    result = CliRunner().invoke(
        big_picture_group,
        ["knowledge-gaps", "--project-root", str(FIXTURE), "--limit", "1"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) <= 1


def test_knowledge_gaps_cli_empty_project(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: empty\naspects: []\n")
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "questions").mkdir()
    result = CliRunner().invoke(
        big_picture_group,
        ["knowledge-gaps", "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert json.loads(result.output) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: FAIL with `No such command 'knowledge-gaps'`.

- [ ] **Step 3: Register the subcommand**

Append to `science-tool/src/science_tool/big_picture/cli.py`:

```python
from dataclasses import asdict

from science_tool.big_picture.knowledge_gaps import compute_topic_gaps
from science_model.aspects import SOFTWARE_ASPECT, matches_aspect_filter


@big_picture_group.command("knowledge-gaps")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Path to the project root.",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Cap the JSON list to the top N entries (default: no limit).",
)
def knowledge_gaps_cmd(project_root: Path, limit: int | None) -> None:
    """Emit topic-level knowledge gaps as JSON.

    Applies the same research-only aspect filter used by big-picture synthesis
    (excluding pure software-only questions) before computing demand.
    """
    resolved = resolve_questions(project_root)
    included = {
        qid
        for qid, out in resolved.items()
        if matches_aspect_filter(out.resolved_aspects, exclude=[SOFTWARE_ASPECT])
    }
    gaps = compute_topic_gaps(project_root, resolved, included)
    if limit is not None:
        gaps = gaps[:limit]
    click.echo(json.dumps([asdict(g) for g in gaps], indent=2, sort_keys=True))
```

If the exact `matches_aspect_filter` signature differs in this codebase, adapt the call to match — consult `science-model/src/science_model/aspects.py`. Goal: exclude questions whose `resolved_aspects` is `["software-development"]` only.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --frozen pytest science-tool/tests/test_knowledge_gaps_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/cli.py science-tool/tests/test_knowledge_gaps_cli.py
git commit -m "feat(big_picture): add knowledge-gaps CLI subcommand"
```

---

## Task 9: Extend validator with `topic` REFERENCE_PATTERN + topic-dir scanning

**Files:**
- Modify: `science-tool/src/science_tool/big_picture/validator.py`
- Modify: `science-tool/tests/test_big_picture_validator.py` (or create if absent)

- [ ] **Step 1: Write the failing tests**

Create (or extend) `science-tool/tests/test_big_picture_validator.py`:

```python
from pathlib import Path

from science_tool.big_picture.validator import REFERENCE_PATTERN, _collect_project_ids

FIXTURE = Path(__file__).parent / "fixtures" / "big_picture" / "minimal_project"


def test_reference_pattern_matches_topic_refs() -> None:
    text = "See topic:ribosome-biogenesis for more."
    matches = [m.group(0) for m in REFERENCE_PATTERN.finditer(text)]
    assert "topic:ribosome-biogenesis" in matches


def test_collect_project_ids_includes_topic_entities() -> None:
    ids = _collect_project_ids(FIXTURE)
    assert "topic:t01-covered" in ids
    assert "topic:t04-legacy-covered" in ids
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: FAIL — the current pattern lacks `topic`, and `_collect_project_ids` doesn't scan topic dirs.

- [ ] **Step 3: Extend the validator**

In `science-tool/src/science_tool/big_picture/validator.py`:

Change `REFERENCE_PATTERN`:

```python
# Before
REFERENCE_PATTERN = re.compile(r"\b(interpretation|task|question|hypothesis):([a-zA-Z0-9_\-.]+)\b")

# After
REFERENCE_PATTERN = re.compile(r"\b(interpretation|task|question|hypothesis|topic):([a-zA-Z0-9_\-.]+)\b")
```

Extend `_collect_project_ids` to scan topic directories. Find the loop over relative directories and add the topic dirs:

```python
def _collect_project_ids(project_root: Path) -> set[str]:
    ids: set[str] = set()
    for relative in (
        "specs/hypotheses",
        "doc/questions",
        "doc/interpretations",
        "doc/topics",
        "doc/background/topics",
        "tasks",
    ):
        directory = project_root / relative
        if not directory.is_dir():
            continue
        # ... existing loading logic ...
```

Preserve the existing frontmatter-read behavior for the added dirs.

- [ ] **Step 4: Run tests to verify they pass**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/validator.py science-tool/tests/test_big_picture_validator.py
git commit -m "feat(big_picture/validator): recognize topic: references and scan topic dirs"
```

---

## Task 10: Update `commands/big-picture.md` Phase 1 + Phase 3 prose

**Files:**
- Modify: `commands/big-picture.md`

- [ ] **Step 1: Find Phase 1 bundle-assembly section**

Run: `grep -n "Phase 1\|bundle" commands/big-picture.md`

- [ ] **Step 2: Add the `topic_gaps` bundle slice to Phase 1 prose**

In the Phase 1 section, find the "Bundle assembly" passage and append after the existing slices:

```markdown
**Topic gaps** — in a single call before slicing per hypothesis:

```python
from science_tool.big_picture.knowledge_gaps import compute_topic_gaps

all_gaps = compute_topic_gaps(project_root, resolved_questions, included_question_ids)
```

Then for each hypothesis bundle, filter `all_gaps` to topics whose `hypotheses` list includes this hypothesis's ID. Pass the filtered list to the hypothesis-synthesizer agent as `topic_gaps`.

`included_question_ids` is the exact set already computed earlier in Phase 1 for aspect filtering — DO NOT recompute it here.
```

- [ ] **Step 3: Add the Phase 3 rollup prose**

Find the Phase 3 synthesis render section. Insert a new subsection between Research Fronts and Emergent Threads:

```markdown
### Knowledge Gaps (rollup)

The orchestrator reuses the `all_gaps` list computed in Phase 1 (no second call to `compute_topic_gaps`). Render the top 10 entries (by `gap_score` desc, ties broken by topic ID asc) as a markdown table with columns: Topic, Coverage, Demand, Gap, Hypotheses. If `all_gaps` is empty, emit the one-liner: "No knowledge gaps detected this run." and skip the table.

Per-hypothesis files render their own Knowledge Gaps sub-bullet inside Research Fronts per the spec (with a rendering cap of 5 `demanding_questions` IDs + "… and N more" tail).
```

- [ ] **Step 4: Commit**

```bash
git add commands/big-picture.md
git commit -m "docs(big-picture): wire knowledge-gaps into Phase 1 bundle + Phase 3 rollup"
```

---

## Task 11: Add hypothesis-synthesizer agent instruction

**Files:**
- Modify: `commands/big-picture.md` (the agent-prompt section) OR the agent-prompt file if it lives elsewhere.

- [ ] **Step 1: Find the hypothesis-synthesizer agent prompt**

Run: `grep -nr "hypothesis-synthesizer\|hypothesis synthesizer" commands/ references/`

- [ ] **Step 2: Add the rendering instruction**

Add this bullet to the agent's instruction list:

```markdown
- If the bundle includes `topic_gaps`, render them as a `**Knowledge gaps**:` sub-bullet inside the Research Fronts section. Format per topic:
  ``- `topic:<id>` — N papers vs M questions referencing it (question:q01, question:q12, …)``
  Cap the rendered question list at 5 IDs followed by `… and K more` if longer. Omit the entire sub-bullet if `topic_gaps` is empty.
```

- [ ] **Step 3: Commit**

```bash
git add commands/big-picture.md
git commit -m "docs(big-picture): instruct hypothesis-synthesizer agent to render topic_gaps"
```

---

## Task 12: Smoke-test on tracked projects (manual)

**Files:**
- No repo changes. Validation on mm30 + natural-systems.

- [ ] **Step 1: On mm30**

```bash
cd ~/d/mm30
uv run science-tool big-picture knowledge-gaps --project-root .
```

Expected: JSON with topics where reading lags. Check for plausibility — topics with heavy bibtex coverage should NOT appear; topics with many questions and thin `source_refs` SHOULD appear.

- [ ] **Step 2: On natural-systems**

```bash
cd ~/d/natural-systems
uv run science-tool big-picture knowledge-gaps --project-root .
```

Expected: per-paper-entity coverage dominates the metric (natural-systems has per-paper files and sparse bibtex).

- [ ] **Step 3: Run the full `/science:big-picture`**

In one of the two projects, run the full big-picture synthesis. Verify:
- A new Knowledge Gaps section appears between Research Fronts and Emergent Threads in `synthesis.md`.
- Per-hypothesis files have a Knowledge Gaps sub-bullet inside Research Fronts (when gaps exist).
- The validator passes (`science-tool big-picture validate --project-root .`).

---

## Self-Review

- [ ] **Spec coverage**: every section of `docs/specs/2026-04-19-knowledge-gaps-design.md` maps to a task — `TopicGap` (Task 1); loaders + dup detection (Task 3); coverage (Task 4); demand (Task 5); `compute_topic_gaps` + sort (Task 6); warning behavior (Task 7); CLI (Task 8); validator (Task 9); `commands/big-picture.md` integration (Tasks 10–11); fixture (Task 2); smoke (Task 12); transition-window alias (Tasks 2, 3, 4, 6 — exercised via `p02-legacy-article` + `t04-legacy-covered`).
- [ ] **No placeholders**: every step has concrete code or an exact command.
- [ ] **Type consistency**: `TopicGap`, `compute_topic_gaps`, `_load_topics`, `_load_papers`, `_compute_coverage`, `_compute_demand`, `_bibkey_of`, `_hypotheses_for`, `canonical_paper_id`, `is_external_paper_id` — names reused consistently.
- [ ] **Prerequisite clear**: Tasks depend on `science_tool.big_picture.literature_prefix` (Task 11 of the rename plan) and on the fixture containing both `paper:` and `article:` paper files (Task 2 here).
