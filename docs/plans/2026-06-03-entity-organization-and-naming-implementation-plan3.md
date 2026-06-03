# Entity Organization & Naming — Implementation Plan 3: Migrate Command, Guide & Cutover

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Design:** `docs/plans/2026-06-03-entity-organization-and-naming-design.md`
**Predecessors:** Plan 1 (foundation) and Plan 2 (validation/hardening) must have landed. The policy table is SSOT, `entities/` is discovered additively, the five conformance checks exist as WARN, and atomic reservation + templates are in place.

**Goal:** Ship `science entities migrate [--apply]` (with frontmatter synthesis → id-map → raw reference rewrite → `git mv` → re-validate), write the migration guide, pilot it on a real project, then perform the irreversible **no-fallback cutover** that makes `entities/` the only supported layout.

**Architecture:** A new pure-function library `entity_layout_migration.py` does all the work (discover → synthesize → plan → rewrite), so every step is unit-testable on `tmp_path`. A thin CLI command orchestrates it: dry-run by default (returns a report), `--apply` performs `git mv` + writes + sets `layout_version: 3`. Reference rewriting is **full-id token replacement** (robust, formatting-preserving) plus `related:` canonicalization via the graph `ReferenceResolver`; any token it cannot confidently rewrite is **reported for manual review, never silently dropped**, and a final graph re-validation **fails loud** on unresolved references. The cutover (last task) reverses every `doc/`/`specs/` fallback added in Plans 1–2 and promotes the conformance WARNs to ERROR.

**Tech Stack:** Python 3.13, pytest, Click, PyYAML, git. Tests run from `science/`: `cd science && uv run pytest`.

**Ordering invariant:** Tasks 1–8 keep the repo and downstream projects working (the migrate command is additive; nothing is forced). **Task 9 is the only irreversible step and must be done last**, after the pilot (Task 8) confirms a real project migrates cleanly.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `science/src/science_tool/entity_layout_migration.py` | Discover, synthesize, plan, rewrite (pure functions) + `migrate_layout` orchestrator | Create |
| `science/src/science_tool/cli.py` | `entities migrate` command | Modify |
| `science/src/science_tool/graph/storage_adapters/markdown.py` | Cutover: scan roots → `entities` only | Modify |
| `science/src/science_tool/validate/checks/research_scope.py` | Cutover: drop `specs/` fallback | Modify |
| `science/src/science_tool/verdict/registry.py`, `verdict/cli.py` | Cutover: drop `specs/` fallback | Modify |
| `science/src/science_tool/entities.py` | Cutover: `_ALLOWED_EXPLICIT_ROOTS` → `entities` | Modify |
| `science/src/science_tool/validate/checks/manifest.py` | Cutover: `layout_version < 3` → ERROR | Modify |
| `science/src/science_tool/validate/checks/entity_conformance.py` | Cutover: WARN → severity gated on `layout_version` | Modify |
| `science/src/science_tool/validate/checks/{hypotheses,discussions,document_structure,papers}.py` | Cutover: drop legacy-dir fallback | Modify |
| `docs/entity-layout-migration-guide.md` | Migration guide | Create |
| `science/tests/test_entity_layout_migration.py` | Library unit tests | Create |

---

## Task 1: Legacy discovery

**Files:**
- Create: `science/src/science_tool/entity_layout_migration.py`
- Test: `science/tests/test_entity_layout_migration.py` (create)

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_entity_layout_migration.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.entity_layout_migration import LegacyEntity, discover_legacy_entities


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_discovers_specs_and_doc_legacy_locations(tmp_path: Path) -> None:
    _write(tmp_path, "specs/hypotheses/h01-x.md", '---\nid: "hypothesis:h01-x"\ntype: hypothesis\n---\n')
    _write(tmp_path, "doc/questions/q05-y.md", '---\nid: "question:q05-y"\ntype: question\n---\n')
    _write(tmp_path, "doc/background/papers/Adams2025.md", '---\nid: "paper:Adams2025"\ntype: paper\n---\n')
    found = {e.rel_path: e for e in discover_legacy_entities(tmp_path)}
    assert "specs/hypotheses/h01-x.md" in found
    assert found["specs/hypotheses/h01-x.md"].kind == "hypothesis"
    assert found["doc/questions/q05-y.md"].kind == "question"
    assert found["doc/background/papers/Adams2025.md"].kind == "paper"


def test_ignores_already_migrated_entities_dir(tmp_path: Path) -> None:
    _write(tmp_path, "entities/questions/0001-x.md", '---\nid: "question:0001-x"\ntype: question\n---\n')
    assert discover_legacy_entities(tmp_path) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/test_entity_layout_migration.py -k discover -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement discovery**

Create `science/src/science_tool/entity_layout_migration.py`:

```python
"""One-time migration of legacy doc/ + specs/ entity layouts into entities/.

Pure functions (discover → synthesize → plan → rewrite) plus a `migrate_layout`
orchestrator. Dry-run by default; `--apply` performs git mv + writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

import yaml

from science_tool.entities import is_markdown_entity_kind

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)
# Roots scanned for legacy entities. entities/ is intentionally excluded.
_LEGACY_SCAN_ROOTS = ("doc", "specs")


@dataclass(frozen=True)
class LegacyEntity:
    rel_path: str
    kind: str
    old_id: str | None
    frontmatter: dict
    body: str


def _split_frontmatter(text: str) -> tuple[dict | None, str]:
    match = _FRONTMATTER.match(text)
    if match is None:
        return None, text
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None, text
    return (data if isinstance(data, dict) else None), match.group(2)


def discover_legacy_entities(project_root: Path) -> list[LegacyEntity]:
    results: list[LegacyEntity] = []
    for root_name in _LEGACY_SCAN_ROOTS:
        root = project_root / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(project_root).as_posix()
            if "templates" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            frontmatter, body = _split_frontmatter(text)
            kind = _infer_kind(rel, frontmatter)
            if kind is None or not is_markdown_entity_kind(kind):
                continue
            old_id = None
            if frontmatter is not None:
                raw_id = frontmatter.get("id")
                old_id = raw_id if isinstance(raw_id, str) else None
            results.append(
                LegacyEntity(rel_path=rel, kind=kind, old_id=old_id, frontmatter=frontmatter or {}, body=body)
            )
    return results


def _infer_kind(rel_path: str, frontmatter: dict | None) -> str | None:
    if frontmatter is not None:
        value = frontmatter.get("type") or frontmatter.get("kind")
        if isinstance(value, str) and value:
            return value
    # Frontmatterless file: infer from the parent directory name (singularized).
    parent = Path(rel_path).parent.name
    return _DIR_TO_KIND.get(parent)


# Legacy directory name → kind, for frontmatterless files.
_DIR_TO_KIND: dict[str, str] = {
    "questions": "question",
    "hypotheses": "hypothesis",
    "propositions": "proposition",
    "interpretations": "interpretation",
    "discussions": "discussion",
    "findings": "finding",
    "inquiries": "inquiry",
    "themes": "theme",
    "topics": "topic",
    "observations": "observation",
    "mechanisms": "mechanism",
    "synthesis": "synthesis",
    "papers": "paper",
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/test_entity_layout_migration.py -k discover -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
git commit -m "feat(migrate): discover legacy doc/specs entities"
```

---

## Task 2: Frontmatter synthesis for prose-header files

**Files:**
- Modify: `science/src/science_tool/entity_layout_migration.py`
- Test: same test module (extend)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_entity_layout_migration.py`:

```python
from science_tool.entity_layout_migration import synthesize_frontmatter


def test_synthesize_from_prose_headers() -> None:
    body = "# h01 phase-1 results\n\n**Date:** 2026-05-23\n**Status:** First real-run\n\nText.\n"
    fm = synthesize_frontmatter(kind="interpretation", body=body, fallback_created="2026-01-01")
    assert fm["type"] == "interpretation"
    assert fm["created"] == "2026-05-23"   # parsed from **Date:**
    assert fm["status"]                      # populated (parsed or default)
    assert "title" in fm and fm["title"]


def test_synthesize_uses_fallback_when_no_headers() -> None:
    fm = synthesize_frontmatter(kind="finding", body="Just text.\n", fallback_created="2026-02-02")
    assert fm["created"] == "2026-02-02"
    assert fm["type"] == "finding"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/test_entity_layout_migration.py -k synthesize -v`
Expected: FAIL — `synthesize_frontmatter` not defined.

- [ ] **Step 3: Implement synthesis**

Append to `science/src/science_tool/entity_layout_migration.py`:

```python
_DATE_HEADER_RE = re.compile(r"^\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
_STATUS_HEADER_RE = re.compile(r"^\*\*Status:\*\*\s*(.+)$", re.MULTILINE)
_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def synthesize_frontmatter(*, kind: str, body: str, fallback_created: str) -> dict:
    """Build a minimal valid frontmatter dict from prose headers + fallbacks.

    Used for legacy files that have no (or partial) YAML frontmatter so they
    become loadable before reference rewriting.
    """
    date_match = _DATE_HEADER_RE.search(body)
    created = date_match.group(1) if date_match else fallback_created
    status_match = _STATUS_HEADER_RE.search(body)
    status = status_match.group(1).strip() if status_match else "active"
    title_match = _H1_RE.search(body)
    title = title_match.group(1).strip() if title_match else f"Untitled {kind}"
    return {
        "type": kind,
        "title": title,
        "status": status,
        "created": created,
        "updated": created,
    }


def ensure_frontmatter(entity: "LegacyEntity", *, fallback_created: str) -> dict:
    """Return a complete frontmatter dict, synthesizing missing fields."""
    base = synthesize_frontmatter(kind=entity.kind, body=entity.body, fallback_created=fallback_created)
    base.update({k: v for k, v in entity.frontmatter.items() if v not in (None, "")})
    base["type"] = entity.kind  # canonicalize: type wins over legacy `kind`
    base.pop("kind", None)
    return base
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/test_entity_layout_migration.py -k synthesize -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
git commit -m "feat(migrate): synthesize frontmatter from prose headers"
```

---

## Task 3: Plan target paths + id map

**Files:**
- Modify: `science/src/science_tool/entity_layout_migration.py`
- Test: same test module (extend)

- [ ] **Step 1: Write the failing test**

Append:

```python
from science_tool.entity_layout_migration import plan_migration


def test_plan_assigns_numeric_in_created_order(tmp_path: Path) -> None:
    _write(tmp_path, "doc/questions/q05-late.md",
           '---\nid: "question:q05-late"\ntype: question\ncreated: "2026-02-01"\n---\n')
    _write(tmp_path, "doc/questions/aging-early.md",
           '---\nid: "question:aging-early"\ntype: question\ncreated: "2026-01-01"\n---\n')
    plan = plan_migration(tmp_path)
    # earliest created gets 0001
    by_old = {m.old_id: m for m in plan.moves}
    assert by_old["question:aging-early"].new_id == "question:0001-aging-early"
    assert by_old["question:q05-late"].new_id == "question:0002-late"
    assert plan.id_map["question:aging-early"] == "question:0001-aging-early"


def test_plan_keeps_citekey_for_papers(tmp_path: Path) -> None:
    _write(tmp_path, "doc/background/papers/Adams2025.md", '---\nid: "paper:Adams2025"\ntype: paper\n---\n')
    plan = plan_migration(tmp_path)
    move = plan.moves[0]
    assert move.new_id == "paper:Adams2025"
    assert move.new_rel_path == "entities/papers/Adams2025.md"


def test_plan_preserves_already_conformant_numbers(tmp_path: Path) -> None:
    _write(tmp_path, "specs/hypotheses/0003-x.md", '---\nid: "hypothesis:0003-x"\ntype: hypothesis\n---\n')
    plan = plan_migration(tmp_path)
    assert plan.moves[0].new_id == "hypothesis:0003-x"


def test_plan_date_prefixed_slug_drops_the_date(tmp_path: Path) -> None:
    _write(tmp_path, "doc/interpretations/2026-05-23-foo-bar.md",
           '---\nid: "interpretation:2026-05-23-foo-bar"\ntype: interpretation\ncreated: "2026-05-23"\n---\n')
    plan = plan_migration(tmp_path)
    # slug is "foo-bar", NOT "05-23-foo-bar"
    assert plan.moves[0].new_id == "interpretation:0001-foo-bar"


def test_plan_uses_synthesized_created_for_frontmatterless(tmp_path: Path) -> None:
    # No frontmatter: created must come from the prose **Date:** header so ordering is right.
    _write_raw = (tmp_path / "doc/interpretations/early.md")
    _write_raw.parent.mkdir(parents=True, exist_ok=True)
    _write_raw.write_text("# Early result\n\n**Date:** 2026-01-01\n", encoding="utf-8")
    _write(tmp_path, "doc/interpretations/2026-12-31-late.md",
           '---\nid: "interpretation:2026-12-31-late"\ntype: interpretation\ncreated: "2026-12-31"\n---\n')
    plan = plan_migration(tmp_path)
    paths = {m.new_rel_path for m in plan.moves}
    # The prose-dated file (2026-01-01) sorts first → 0001.
    assert "entities/interpretations/0001-early-result.md" in paths


def test_plan_detects_duplicate_target_collision(tmp_path: Path) -> None:
    # Two papers with the same citekey from the two legacy paper homes.
    _write(tmp_path, "doc/papers/Adams2025.md", '---\nid: "paper:Adams2025"\ntype: paper\n---\n')
    _write(tmp_path, "doc/background/papers/Adams2025.md", '---\nid: "paper:Adams2025"\ntype: paper\n---\n')
    plan = plan_migration(tmp_path)
    assert plan.collisions  # non-empty: same new_rel_path / new_id


def test_plan_relocates_singletons(tmp_path: Path) -> None:
    _write(tmp_path, "specs/research-question.md", '---\nid: "rq:x"\ntitle: RQ\nstatus: active\n---\n')
    (tmp_path / "specs/claim-registry.yaml").write_text("claims: []\n", encoding="utf-8")
    plan = plan_migration(tmp_path)
    targets = {s.new_rel_path for s in plan.singletons}
    assert "entities/research-question.md" in targets
    assert "entities/claim-registry.yaml" in targets
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/test_entity_layout_migration.py -k plan -v`
Expected: FAIL — `plan_migration` not defined.

- [ ] **Step 3: Implement planning**

Append to `science/src/science_tool/entity_layout_migration.py`:

```python
from science_tool.entities import derive_slug, local_part_conforms, resolve_path_policy, singleton_path

# IMPORTANT: date prefix is tried BEFORE the numeric prefix, so 2026-05-23-foo
# yields slug "foo" (not "05-23-foo" from the numeric regex matching "2026").
_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(.*)$")     # 2026-05-23-foo
_LEGACY_LOCAL_RE = re.compile(r"^(?:[A-Za-z]+)?(\d+)-(.*)$")  # h01-foo, q5-foo, 0003-foo

# Known legacy locations of the two singletons (no per-kind dir / no type field).
_SINGLETON_LEGACY_PATHS: dict[str, tuple[str, ...]] = {
    "research-question": ("specs/research-question.md", "doc/research-question.md"),
    "claim-registry": ("specs/claim-registry.yaml",),
}


@dataclass(frozen=True)
class Move:
    old_rel_path: str
    new_rel_path: str
    old_id: str | None
    new_id: str
    kind: str


@dataclass(frozen=True)
class SingletonMove:
    old_rel_path: str
    new_rel_path: str


@dataclass
class MigrationPlan:
    moves: list[Move] = field(default_factory=list)
    singletons: list[SingletonMove] = field(default_factory=list)
    id_map: dict[str, str] = field(default_factory=dict)  # old_id -> new_id
    collisions: list[dict] = field(default_factory=list)  # blocking; reported


def _slug_from_legacy(entity: "LegacyEntity", frontmatter: dict) -> str:
    stem = Path(entity.rel_path).stem
    for pattern in (_DATE_PREFIX_RE, _LEGACY_LOCAL_RE):  # date first — see note above
        match = pattern.match(stem)
        if match is not None and match.groups()[-1]:
            return derive_slug(match.groups()[-1])
    # No recognizable prefix → derive from the (synthesized) title, else the stem.
    title = frontmatter.get("title")
    return derive_slug(str(title)) if title else derive_slug(stem)


def plan_migration(project_root: Path) -> MigrationPlan:
    plan = MigrationPlan()
    _plan_singletons(project_root, plan)

    entities = discover_legacy_entities(project_root)
    # Synthesize complete frontmatter BEFORE planning so created/title/slug are
    # correct even for prose-header (frontmatterless) files.
    normalized: dict[str, dict] = {
        e.rel_path: ensure_frontmatter(e, fallback_created=str(e.frontmatter.get("created") or "9999-99-99"))
        for e in entities
    }
    by_kind: dict[str, list[LegacyEntity]] = {}
    for entity in entities:
        by_kind.setdefault(entity.kind, []).append(entity)

    for kind, items in by_kind.items():
        policy = resolve_path_policy(kind)
        if policy.strategy == "citekey":
            for entity in items:
                local = Path(entity.rel_path).stem
                _add_move(plan, entity, f"{policy.root.as_posix()}/{local}.md", f"{kind}:{local}", kind)
            continue
        # numeric: preserve conformant numbers; assign the rest in created order.
        ordered = sorted(items, key=lambda e: (str(normalized[e.rel_path]["created"]), e.rel_path))
        taken: set[int] = set()
        deferred: list[LegacyEntity] = []
        provisional: dict[str, int] = {}
        for entity in ordered:
            stem = Path(entity.rel_path).stem
            if local_part_conforms(kind, stem):
                number = int(stem.split("-", 1)[0])
                provisional[entity.rel_path] = number
                taken.add(number)  # NB: two pre-conformant 0003-* both keep 3 → collision (detected below)
            else:
                deferred.append(entity)
        nxt = 1
        for entity in deferred:
            while nxt in taken:
                nxt += 1
            provisional[entity.rel_path] = nxt
            taken.add(nxt)
            nxt += 1
        for entity in ordered:
            number = provisional[entity.rel_path]
            local = f"{number:04d}-{_slug_from_legacy(entity, normalized[entity.rel_path])}"
            _add_move(plan, entity, f"{policy.root.as_posix()}/{local}.md", f"{kind}:{local}", kind)

    _detect_collisions(plan)
    return plan


def _add_move(plan: MigrationPlan, entity: "LegacyEntity", new_rel: str, new_id: str, kind: str) -> None:
    plan.moves.append(Move(entity.rel_path, new_rel, entity.old_id, new_id, kind))
    if entity.old_id:
        plan.id_map[entity.old_id] = new_id


def _plan_singletons(project_root: Path, plan: MigrationPlan) -> None:
    for kind, candidates in _SINGLETON_LEGACY_PATHS.items():
        target = singleton_path(kind).as_posix()
        for rel in candidates:
            if (project_root / rel).is_file():
                plan.singletons.append(SingletonMove(old_rel_path=rel, new_rel_path=target))
                break  # first existing candidate wins


def _detect_collisions(plan: MigrationPlan) -> None:
    by_path: dict[str, list[str]] = {}
    by_id: dict[str, list[str]] = {}
    for move in plan.moves:
        by_path.setdefault(move.new_rel_path, []).append(move.old_rel_path)
        by_id.setdefault(move.new_id, []).append(move.old_rel_path)
    for target, sources in sorted(by_path.items()):
        if len(sources) > 1:
            plan.collisions.append({"kind": "path", "target": target, "sources": sorted(sources)})
    for new_id, sources in sorted(by_id.items()):
        if len(sources) > 1:
            plan.collisions.append({"kind": "id", "new_id": new_id, "sources": sorted(sources)})
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/test_entity_layout_migration.py -k plan -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
git commit -m "feat(migrate): plan target paths and old->new id map"
```

---

## Task 4: Reference rewriting (full-id replace + unresolved reporting)

**Files:**
- Modify: `science/src/science_tool/entity_layout_migration.py`
- Test: same test module (extend)

- [ ] **Step 1: Write the failing test**

Append:

```python
from science_tool.entity_layout_migration import rewrite_references


def test_rewrite_replaces_full_ids_not_prefix_collisions() -> None:
    id_map = {"question:q1-a": "question:0001-a", "question:q10-b": "question:0010-b"}
    text = "See question:q1-a and question:q10-b and related: [question:q1-a]\n"
    out, unresolved = rewrite_references(text, id_map)
    assert "question:0001-a" in out and "question:0010-b" in out
    assert "question:q1-a" not in out  # q1 not corrupted by q10 replacement
    assert unresolved == []


def test_rewrite_reports_unmapped_legacy_tokens() -> None:
    # A legacy-shaped reference with no mapping must be reported, never silently kept.
    id_map = {"question:q1-a": "question:0001-a"}
    text = "Depends on hypothesis:h9-ghost which no longer exists.\n"
    out, unresolved = rewrite_references(text, id_map)
    assert "hypothesis:h9-ghost" in unresolved
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/test_entity_layout_migration.py -k rewrite -v`
Expected: FAIL — `rewrite_references` not defined.

- [ ] **Step 3: Implement rewriting**

Append to `science/src/science_tool/entity_layout_migration.py`:

```python
# A reference token: <kind>:<local-part>. Legacy local parts may carry a letter
# prefix (q1, h09) or a date (2026-05-23); canonical are NNNN or a citekey.
_REF_TOKEN_RE = re.compile(r"\b([a-z][a-z-]*):([A-Za-z0-9][A-Za-z0-9_.-]*)\b")
_LEGACY_LOCAL_SHAPE = re.compile(r"^(?:[A-Za-z]+\d+|\d{4}-\d{2}-\d{2})(?:-|$)")


def rewrite_references(text: str, id_map: dict[str, str]) -> tuple[str, list[str]]:
    """Replace every mapped old id with its new id (longest-first to avoid prefix
    collisions). Returns (rewritten_text, unresolved_legacy_tokens).

    A token that *looks* legacy-shaped but has no mapping is reported in
    `unresolved` rather than left to rot into a dead link.
    """
    # Replace longest keys first so question:q10-b is handled before question:q1-b.
    for old_id in sorted(id_map, key=len, reverse=True):
        new_id = id_map[old_id]
        text = re.sub(rf"(?<![\w:.-]){re.escape(old_id)}(?![\w.-])", new_id, text)

    unresolved: list[str] = []
    for match in _REF_TOKEN_RE.finditer(text):
        token, local = match.group(0), match.group(2)
        if token in id_map.values():
            continue  # already canonical (a freshly-written new id)
        if _LEGACY_LOCAL_SHAPE.match(local):
            unresolved.append(token)
    return text, sorted(set(unresolved))
```

> `rewrite_references` operates on a single file's full text (frontmatter + body),
> which covers `id:`, `related:`, inline `<kind>:…`, and `[[<kind>:…]]` uniformly
> because they are all the same token shape. Bare wiki-links without a kind
> prefix (`[[q01-foo]]`) are intentionally surfaced via `unresolved` for manual
> handling — the orchestrator (Task 5) treats a non-empty `unresolved` as a
> blocking error under `--apply`.

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/test_entity_layout_migration.py -k rewrite -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
git commit -m "feat(migrate): reference rewriting with unresolved-token reporting"
```

---

## Task 5: Orchestrator — `migrate_layout`

**Files:**
- Modify: `science/src/science_tool/entity_layout_migration.py`
- Test: same test module (extend)

- [ ] **Step 1: Write the failing test**

Append:

```python
import subprocess

from science_tool.entity_layout_migration import migrate_layout


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"], cwd=root, check=True)


def test_migrate_dry_run_makes_no_changes(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "specs/hypotheses/h01-x.md", '---\nid: "hypothesis:h01-x"\ntype: hypothesis\ncreated: "2026-01-01"\ntitle: X\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n')
    _git_init(tmp_path)
    report = migrate_layout(tmp_path, apply=False)
    assert report["moves"]
    assert (tmp_path / "specs/hypotheses/h01-x.md").exists()  # untouched
    assert not (tmp_path / "entities/hypotheses").exists()


def test_migrate_apply_moves_and_rewrites(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "specs/hypotheses/h01-x.md", '---\nid: "hypothesis:h01-x"\ntype: hypothesis\ncreated: "2026-01-01"\ntitle: X\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n')
    _write(tmp_path, "doc/questions/q01-y.md", '---\nid: "question:q01-y"\ntype: question\ncreated: "2026-01-02"\ntitle: Y\nstatus: active\nupdated: "2026-01-02"\nrelated: ["hypothesis:h01-x"]\n---\nSee hypothesis:h01-x.\n')
    _git_init(tmp_path)
    report = migrate_layout(tmp_path, apply=True)
    assert (tmp_path / "entities/hypotheses/0001-x.md").is_file()
    q = (tmp_path / "entities/questions/0001-y.md").read_text()
    assert "hypothesis:0001-x" in q          # related + inline ref rewritten
    assert "hypothesis:h01-x" not in q
    import yaml as _yaml
    manifest = _yaml.safe_load((tmp_path / "science.yaml").read_text())
    assert manifest["layout_version"] == 3
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/test_entity_layout_migration.py -k migrate -v`
Expected: FAIL — `migrate_layout` not defined.

- [ ] **Step 3: Implement the orchestrator**

Append to `science/src/science_tool/entity_layout_migration.py`:

```python
import subprocess

import yaml as _yaml_mod


def _git_mv(project_root: Path, old_rel: str, new_rel: str) -> None:
    dest = project_root / new_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "mv", old_rel, new_rel], cwd=project_root, check=True)


def _render(frontmatter: dict, body: str) -> str:
    return "---\n" + _yaml_mod.safe_dump(frontmatter, sort_keys=False) + "---\n" + body


def migrate_layout(project_root: Path, *, apply: bool) -> dict:
    plan = plan_migration(project_root)
    entities = {e.rel_path: e for e in discover_legacy_entities(project_root)}

    # 1. Frontmatter synthesis (build complete frontmatter per file, with new id).
    rewritten: dict[str, str] = {}  # new_rel_path -> file text (pre ref-rewrite)
    for move in plan.moves:
        entity = entities[move.old_rel_path]
        fm = ensure_frontmatter(entity, fallback_created=str(entity.frontmatter.get("created") or "9999-99-99"))
        fm["id"] = move.new_id
        rewritten[move.new_rel_path] = _render(fm, entity.body)

    # 2. Reference rewrite across every migrated entity, both singletons, and any
    #    task files that reference entity ids. Collect unresolved tokens per file.
    singleton_text: dict[str, str] = {}
    for sm in plan.singletons:
        singleton_text[sm.new_rel_path] = (project_root / sm.old_rel_path).read_text(encoding="utf-8")
    task_files = {p.relative_to(project_root).as_posix(): p.read_text(encoding="utf-8")
                  for p in sorted((project_root / "tasks").rglob("*.md"))} if (project_root / "tasks").is_dir() else {}

    all_unresolved: dict[str, list[str]] = {}
    for bucket in (rewritten, singleton_text, task_files):
        for rel, text in list(bucket.items()):
            out, unresolved = rewrite_references(text, plan.id_map)
            bucket[rel] = out
            if unresolved:
                all_unresolved[rel] = unresolved

    report = {
        "moves": [vars(m) for m in plan.moves],
        "singletons": [vars(s) for s in plan.singletons],
        "id_map": plan.id_map,
        "collisions": plan.collisions,
        "unresolved_references": all_unresolved,
        "applied": apply,
    }

    if not apply:
        return report
    if plan.collisions:
        raise ValueError(f"collisions block --apply: {plan.collisions}")
    if all_unresolved:
        raise ValueError(f"unresolved references block --apply: {all_unresolved}")

    # 3. git mv + write rewritten content (entities, singletons, tasks) + bump version.
    for move in plan.moves:
        _git_mv(project_root, move.old_rel_path, move.new_rel_path)
        (project_root / move.new_rel_path).write_text(rewritten[move.new_rel_path], encoding="utf-8")
    for sm in plan.singletons:
        _git_mv(project_root, sm.old_rel_path, sm.new_rel_path)
        (project_root / sm.new_rel_path).write_text(singleton_text[sm.new_rel_path], encoding="utf-8")
    for rel, text in task_files.items():
        (project_root / rel).write_text(text, encoding="utf-8")
    manifest_path = project_root / "science.yaml"
    manifest = _yaml_mod.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    manifest["layout_version"] = 3
    manifest_path.write_text(_yaml_mod.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return report
```

> **Singletons & task refs are handled above:** `research-question.md` and
> `claim-registry.yaml` are relocated via `plan.singletons` (planned by
> `_plan_singletons`, including the non-`.md` registry that discovery skips) and
> their bodies are ref-rewritten; `tasks/**/*.md` are ref-rewritten in place
> (not moved — tasks remain adapter-backed per the design). Singletons keep their
> own ids unchanged (relocation only), so they add nothing to `id_map`.

- [ ] **Step 4: Add tests for singletons, tasks, and collision-blocking**

Append tests asserting: (a) `tasks/t001.md` containing `hypothesis:h01-x` is
rewritten to `hypothesis:0001-x`; (b) `specs/claim-registry.yaml` referencing
`hypothesis:h01-x` lands at `entities/claim-registry.yaml` with the ref rewritten;
(c) a project with two `Adams2025.md` paper sources raises `ValueError` under
`apply=True` and lists the collision in the dry-run report.

- [ ] **Step 5: Run to verify pass**

Run: `cd science && uv run pytest tests/test_entity_layout_migration.py -k migrate -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
git commit -m "feat(migrate): migrate_layout orchestrator (git mv + rewrite + bump)"
```

---

## Task 6: `science entities migrate` CLI command

**Files:**
- Modify: `science/src/science_tool/cli.py` (near the existing `entities migrate-identifiers`, ~line 263)
- Test: `science/tests/test_entities_cli.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_entities_cli.py`:

```python
def test_entities_migrate_dry_run_emits_report() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        (root / "science.yaml").write_text("name: t\nlayout_version: 2\n", encoding="utf-8")
        write_markdown_entity(
            root, "specs/hypotheses/h01-x.md",
            {"id": "hypothesis:h01-x", "type": "hypothesis", "title": "X", "status": "proposed",
             "created": "2026-01-01", "updated": "2026-01-01"},
        )
        result = runner.invoke(main, ["entities", "migrate"])
        assert result.exit_code == 0, result.output
        assert "hypothesis:0001-x" in result.output  # report shows planned id
        assert Path("specs/hypotheses/h01-x.md").is_file()  # dry run: unchanged
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/test_entities_cli.py::test_entities_migrate_dry_run_emits_report -v`
Expected: FAIL — no such command.

- [ ] **Step 3: Wire the command**

In `science/src/science_tool/cli.py`, alongside `migrate-identifiers` (model it on
that command at line 263), add:

```python
@entities_group.command("migrate")
@click.option("--apply", "apply_changes", is_flag=True, help="Apply the migration (default: dry run).")
@click.option("--project-path", type=click.Path(exists=True, file_okay=False, path_type=Path), default=Path("."))
def entities_migrate_command(apply_changes: bool, project_path: Path) -> None:
    """Migrate a project's doc/specs entity layout into entities/ (v2 → v3)."""
    from science_tool.entity_layout_migration import migrate_layout

    report = migrate_layout(project_path, apply=apply_changes)
    click.echo(json.dumps(report, indent=2))
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/test_entities_cli.py::test_entities_migrate_dry_run_emits_report -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_entities_cli.py
git commit -m "feat(cli): science entities migrate (dry-run by default)"
```

---

## Task 7: Migration guide

**Files:**
- Create: `docs/entity-layout-migration-guide.md`

- [ ] **Step 1: Write the guide**

Create `docs/entity-layout-migration-guide.md` covering, concretely:

1. **What changes:** `specs/` retired; all markdown entities move to
   `entities/<kind>/NNNN-slug.md` (citekey for `entities/papers/`); singletons
   `entities/research-question.md`, `entities/claim-registry.yaml`;
   `layout_version` 2 → 3.
2. **Preconditions:** clean git working tree; on a branch; Plans 1–2 shipped.
3. **Dry run:** `science entities migrate --project-path <proj>` → review the JSON
   report: `moves`, `id_map`, and especially `unresolved_references`.
4. **Resolve `unresolved_references`:** these are legacy-shaped tokens with no
   mapping (renamed/deleted targets, bare `[[q01-…]]` wiki-links without a kind).
   Fix each by hand (point to the correct id or remove the dead link) and re-run
   the dry run until `unresolved_references` is empty.
5. **Apply:** `science entities migrate --apply --project-path <proj>` (performs
   `git mv`, rewrites refs, sets `layout_version: 3`).
6. **Verify:** `science validate` → expect green; spot-check that
   `science entity show q5`-style shortforms still resolve.
7. **Edge cases:** multi-file `.lock.yaml` hypotheses (the `.md` migrates; reconcile
   the sidecar manually); prose-header interpretations (frontmatter synthesized —
   review the generated `title`/`status`); paper-summary consolidation from
   `doc/papers/` + `doc/background/papers/`.
8. **Rollback:** `git restore`/branch reset — the command makes no changes without
   `--apply`, and `--apply` is a single reviewable commit-worth of `git mv`s.

- [ ] **Step 2: Commit**

```bash
git add docs/entity-layout-migration-guide.md
git commit -m "docs: entity layout migration guide"
```

---

## Task 8: Pilot on a real project (verification)

**Files:** none (verification task; operates on a throwaway copy)

- [ ] **Step 1: Copy the smallest real project to a scratch dir**

Run: `cp -r ~/d/health/processes/cycles /tmp/cycles-migrate && cd /tmp/cycles-migrate && git status`
(Use a project that is already in git so `git mv` works; if it is part of a larger
repo, `git init` the copy and commit first.)

- [ ] **Step 2: Dry run and inspect**

Run: `cd /mnt/ssd/Dropbox/science/science && uv run science entities migrate --project-path /tmp/cycles-migrate`
Review `unresolved_references` in the JSON. If non-empty, this is real signal —
record what the dead/ambiguous refs are (they inform guide refinements).

- [ ] **Step 3: Apply on the copy and validate**

Run: `cd /mnt/ssd/Dropbox/science/science && uv run science entities migrate --apply --project-path /tmp/cycles-migrate && uv run science validate --project-path /tmp/cycles-migrate` (use the validate command's actual flag for project root)
Expected: migration completes; validate is green (no location/filename/frontmatter
conformance WARNs remain). Note the `cycles` questions were the known `NN-`/`q##-`
mix — confirm they all become `entities/questions/NNNN-…`.

- [ ] **Step 4: Record findings**

If the pilot surfaces gaps (unhandled ref shape, a kind without a `_DIR_TO_KIND`
entry, a synthesis edge case), file them back into Tasks 1–5 as follow-up fixes
**before** proceeding to cutover. Do not cut over on a failed pilot.

- [ ] **Step 5: Commit any fixes** (if Step 4 required code changes)

```bash
git add -A && git commit -m "fix(migrate): handle <case> found in cycles pilot"
```

---

## Task 9: CUTOVER — remove fallbacks, promote WARN→ERROR (IRREVERSIBLE; do last)

**Files:** discovery + validation modules listed below.
**Test:** update the corresponding tests to expect the steady-state behavior.

> Do not start this task until Task 8's pilot is green. This task makes
> `entities/` the only supported layout; un-migrated (`layout_version: 2`)
> projects will fail validation by design (design §11).

- [ ] **Step 1: Discovery scans `entities/` only**

`science/src/science_tool/graph/storage_adapters/markdown.py`:

```python
        self._scan_roots = scan_roots or ["entities", "research/packages"]
```

- [ ] **Step 2: Drop singleton fallbacks**

`research_scope.py`: remove the `legacy_rq` fallback — resolve only
`ctx.project_root / singleton_path("research-question")`.
`verdict/registry.py` + `verdict/cli.py`: remove the `specs/claim-registry.yaml`
branch; use only `entities/claim-registry.yaml`.
`entities.py`: set `_ALLOWED_EXPLICIT_ROOTS = (Path("entities"),)`.

- [ ] **Step 3: Drop legacy-dir fallbacks in semantic checks**

In `hypotheses.py`, `discussions.py`, `document_structure.py`, `papers.py`, remove
the `... if entities_dir.is_dir() else legacy_dir` fallbacks introduced in Plan 2;
point only at the `entities/` locations.

- [ ] **Step 4: `layout_version < 3` becomes ERROR**

`manifest.py`: change the Plan 2 WARN to:

```python
    layout_version = ctx.manifest.get("layout_version")
    if not isinstance(layout_version, int) or layout_version < 3:
        yield _result(
            Severity.ERROR,
            "science.yaml: layout_version must be >= 3 — run `science entities migrate`",
        )
```

- [ ] **Step 5: Conformance checks promote to ERROR**

Plan 2 already routes every conformance yield through the `_severity(ctx)` helper
in `entity_conformance.py`. The cutover only changes that helper's **body** to
gate on `layout_version` (no call-site edits needed):

```python
def _severity(ctx: ValidateContext) -> Severity:
    version = ctx.manifest.get("layout_version")
    return Severity.ERROR if isinstance(version, int) and version >= 3 else Severity.WARN
```

(The stranded-file branch in `check_entity_location_coherence` keeps emitting
`Severity.WARN` directly — a file in `doc/` is advisory, not a v3 violation.)

- [ ] **Step 6: Update tests to steady-state expectations**

Update the Plan 1/2 tests that relied on fallbacks (additive discovery of
`doc/specs`, `specs/` singleton fallback, WARN severity) to expect the
`entities/`-only, ERROR behavior. Grep: `cd science && grep -rn "specs\|doc/questions\|Severity.WARN" tests/validate tests/test_entities_cli.py` and reconcile each.

- [ ] **Step 7: Full suite + lint**

Run: `cd science && uv run pytest -q && uv run ruff check src tests && (cd model && uv run pytest -q)`
Expected: PASS / clean.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: entities/ hard cutover — drop legacy fallbacks, enforce layout_version 3"
```

---

## Self-review (coverage against the design)

- `science entities migrate` (synthesis-first → id-map → raw rewrite → git mv → bump) → Tasks 1–6. ✅
- **Synthesis feeds planning** (created/title/slug come from synthesized frontmatter, so prose-header files sort and slug correctly) → Task 3 (`normalized` in `plan_migration`). ✅
- **Singletons** (`research-question.md`, `claim-registry.yaml`) relocated by explicit by-path branch, not kind inference → Task 3 (`_plan_singletons`) + Task 5 (singleton rewrite/move). ✅
- **Date-prefixed slugs** drop the date (regex ordered date-first) → Task 3 (`_slug_from_legacy`). ✅
- **Collision detection** (duplicate target path / new id) as a blocking report → Task 3 (`_detect_collisions`) + Task 5 (raises under `--apply`). ✅
- Reference-rewrite completeness + fail-loud on unresolved → Task 4 (`unresolved` reporting) + Task 5 (blocks `--apply`). ✅
- Claim-registry + task-graph ref rewriting → Task 5 (singleton + `tasks/**/*.md` buckets). ✅
- Migration guide → Task 7. ✅
- Pilot before cutover → Task 8. ✅
- No-fallback cutover (scan roots, singletons, `_ALLOWED_EXPLICIT_ROOTS`, legacy
  semantic-check fallbacks) + `layout_version: 3` ERROR + WARN→ERROR (one-body
  change to the Plan 2 `_severity` helper) → Task 9. ✅

**Known limitations (documented, not silent):**
- YAML re-render via `yaml.safe_dump` does not preserve comments/key-ordering
  nuance in migrated frontmatter. Acceptable: frontmatter is regenerated to a
  canonical field order; bodies (where prose comments live) are untouched except
  for id-token replacement. If comment preservation in frontmatter becomes a
  requirement, swap `yaml` for `ruamel.yaml` in `entity_layout_migration.py` only.
- Bare wiki-links without a kind prefix (`[[q01-foo]]`) are surfaced as
  `unresolved` for manual fixing rather than auto-rewritten — by design, since
  they cannot be disambiguated to a kind safely.

**Verify-before-coding notes:** confirm the `validate` CLI's project-root flag
name (Task 8 Step 3); confirm `discover_legacy_entities` should also walk
`doc/reports/synthesis/` explicitly if synthesis files there lack a `synthesis`
parent dir (extend `_LEGACY_SCAN_ROOTS`/`_DIR_TO_KIND` if the pilot shows misses).
