# Entity Organization & Naming — Implementation Plan 3: Migrate Command, Guide & Cutover

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Design:** `docs/plans/2026-06-03-entity-organization-and-naming-design.md`
**Predecessors:** Plan 1 (foundation) and Plan 2 (validation/hardening) must have landed. The policy table is SSOT, `entities/` is discovered additively, the five conformance checks exist as WARN, and atomic reservation + templates are in place.

**Goal:** Ship `science entities migrate [--apply]` (with frontmatter synthesis → id-map → raw reference rewrite → `git mv` → re-validate), write the migration guide, pilot it on a real project, then perform the irreversible **no-fallback cutover** that makes `entities/` the only supported layout.

**Architecture:** A new pure-function library `entity_layout_migration.py` does all the work (discover → synthesize → plan → rewrite), so every step is unit-testable on `tmp_path`. A thin CLI command orchestrates it: dry-run by default (returns a report), `--apply` performs `git mv` + writes + sets `layout_version: 3`. Reference rewriting is **full-id token replacement** (robust, formatting-preserving) applied across **every project markdown file** that can carry an entity id (moved entities, singletons, pre-existing `entities/`, `doc/` prose/reports, `research/packages`, `tasks/`) — not just the files being moved — because raw body links would otherwise be missed by the structured-only graph audit. Any token it cannot confidently rewrite is **reported for manual review, never silently dropped**, and a final graph re-validation **fails loud** on unresolved references. The cutover (last task) reverses every `doc/`/`specs/` fallback added in Plans 1–2 — including several entity checks Plan 2 left scanning legacy roots only, which Task 8 first repoints additively — and promotes the conformance WARNs to ERROR.

**Tech Stack:** Python 3.13, pytest, Click, PyYAML, git. Tests run from `science/`: `cd science && uv run pytest`.

**Ordering invariant:** Tasks 1–9 keep the repo and downstream projects working (the migrate command is additive; nothing is forced). **Task 10 is the only irreversible step and must be done last**, after the pilot (Task 9) confirms a real project migrates cleanly.

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
| `science/src/science_tool/validate/checks/{prereg,evidence_lines,hypothesis_comparisons}.py` | Additive dual-root (Task 8); cutover: drop legacy | Modify |
| `science/src/science_tool/validate/checks/cross_references.py` | Additive: include `entities/` in id scan (Task 8); cutover: drop legacy | Modify |
| `science/src/science_tool/validate/checks/directory_structure.py` | Additive: version-gate required dirs — `specs/` for v2, `entities/` for v3 (Task 8) | Modify |
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


def test_infers_synthesis_singleton_by_path(tmp_path: Path) -> None:
    # Frontmatterless legacy synthesis singleton: parent dir is "reports", which
    # the derived map would call `report`. The by-path override must classify it
    # as synthesis (matching discussions.py's legacy treatment).
    raw = tmp_path / "doc/reports/synthesis.md"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text("# Synthesis\n\nText.\n", encoding="utf-8")
    found = {e.rel_path: e for e in discover_legacy_entities(tmp_path)}
    assert found["doc/reports/synthesis.md"].kind == "synthesis"
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

from science_tool.entities import is_markdown_entity_kind, markdown_entity_kinds, resolve_path_policy

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


# Specific legacy file paths whose kind cannot be inferred from the parent dir.
# `doc/reports/synthesis.md` is the legacy synthesis singleton: its parent dir is
# "reports", which the generic map would misclassify as `report`. Validation
# already treats this exact path as synthesis (discussions.py), so the migrator
# must agree.
_PATH_KIND_OVERRIDES: dict[str, str] = {
    "doc/reports/synthesis.md": "synthesis",
}


def _infer_kind(rel_path: str, frontmatter: dict | None) -> str | None:
    if frontmatter is not None:
        value = frontmatter.get("type") or frontmatter.get("kind")
        if isinstance(value, str) and value:
            return value
    # Frontmatterless file: explicit by-path override first, then the parent
    # directory name (singularized) via the derived map.
    if rel_path in _PATH_KIND_OVERRIDES:
        return _PATH_KIND_OVERRIDES[rel_path]
    parent = Path(rel_path).parent.name
    return _DIR_TO_KIND.get(parent)


# Legacy directory name → kind, for frontmatterless files. DERIVED from the
# policy table (SSOT) so EVERY numeric/citekey kind's plural directory is covered
# — including evidence-lines, reports, plans, searches, methods, and
# pre-registrations that a hand-written map would silently omit (and thereby
# strand valid legacy entities through cutover). Singletons have no per-kind dir,
# so they are excluded.
_DIR_TO_KIND: dict[str, str] = {
    resolve_path_policy(kind).root.name: kind
    for kind in markdown_entity_kinds()
    if resolve_path_policy(kind).strategy != "singleton"
}
```

> Deriving `_DIR_TO_KIND` from `resolve_path_policy(...).root.name` keeps the
> directory→kind map in lockstep with the policy table: a new numeric kind added
> to `_BUILTIN_MARKDOWN_POLICIES` is covered automatically, with no second list
> to maintain. (`papers` → `paper`, `evidence-lines` → `evidence-line`, etc.)

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
- Modify: `science/src/science_tool/entities.py` (expose status accessors)
- Test: same test module (extend)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_entity_layout_migration.py`:

```python
from science_tool.entity_layout_migration import synthesize_frontmatter


from science_tool.entities import valid_statuses


def test_synthesize_from_prose_headers() -> None:
    body = "# h01 phase-1 results\n\n**Date:** 2026-05-23\n**Status:** First real-run\n\nText.\n"
    fm = synthesize_frontmatter(kind="interpretation", body=body, fallback_created="2026-01-01")
    assert fm["type"] == "interpretation"
    assert fm["created"] == "2026-05-23"   # parsed from **Date:**
    # "First real-run" is NOT a controlled interpretation status → falls back to
    # the per-kind default. Synthesized status must always be a valid value.
    assert fm["status"] in valid_statuses("interpretation")
    assert "title" in fm and fm["title"]


def test_synthesize_uses_controlled_default_status_per_kind() -> None:
    # Defaults are per-kind controlled values (NOT a blanket "active"):
    # hypothesis → "proposed", proposition → "draft".
    h = synthesize_frontmatter(kind="hypothesis", body="Just text.\n", fallback_created="2026-02-02")
    assert h["status"] in valid_statuses("hypothesis")
    assert h["status"] == "proposed"
    p = synthesize_frontmatter(kind="proposition", body="Just text.\n", fallback_created="2026-02-02")
    assert p["status"] == "draft"


def test_synthesize_uses_fallback_when_no_headers() -> None:
    fm = synthesize_frontmatter(kind="finding", body="Just text.\n", fallback_created="2026-02-02")
    assert fm["created"] == "2026-02-02"
    assert fm["type"] == "finding"
    assert fm["status"] in valid_statuses("finding")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/test_entity_layout_migration.py -k synthesize -v`
Expected: FAIL — `synthesize_frontmatter` not defined.

- [ ] **Step 3a: Expose status accessors from `entities.py`**

`_DEFAULT_STATUS` and `_STATUS_VALUES` are module-private. Add thin public
accessors next to them so the migrator (and any other caller) reads the
controlled vocabulary from the SSOT instead of duplicating it:

```python
def default_status(kind: str) -> str:
    """The per-kind default status (e.g. hypothesis → 'proposed')."""
    return _DEFAULT_STATUS[kind]


def valid_statuses(kind: str) -> frozenset[str]:
    """The controlled set of valid statuses for `kind`."""
    return _STATUS_VALUES[kind]
```

- [ ] **Step 3b: Implement synthesis**

Append to `science/src/science_tool/entity_layout_migration.py` (add
`default_status, valid_statuses` to the `from science_tool.entities import ...`
line):

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
    # Status: accept a prose **Status:** value ONLY if it is in the kind's
    # controlled vocabulary; otherwise use the per-kind default (NOT a blanket
    # "active", which is invalid for hypothesis/proposition/evidence-line). The
    # original prose line stays in the body, so nothing is lost.
    status_match = _STATUS_HEADER_RE.search(body)
    parsed_status = status_match.group(1).strip() if status_match else ""
    status = parsed_status if parsed_status in valid_statuses(kind) else default_status(kind)
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
git add science/src/science_tool/entity_layout_migration.py science/src/science_tool/entities.py science/tests/test_entity_layout_migration.py
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


def test_plan_maps_frontmatterless_stem_alias(tmp_path: Path) -> None:
    # A prose-header file has no `old_id`. References to it use the old filename
    # stem (`interpretation:early`). The plan must map that stem alias to the new
    # id so rewrite_references can fix the link instead of reporting it unresolved.
    raw = tmp_path / "doc/interpretations/early.md"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text("# Early result\n\n**Date:** 2026-01-01\n", encoding="utf-8")
    plan = plan_migration(tmp_path)
    assert plan.id_map["interpretation:early"] == "interpretation:0001-early-result"


def test_plan_detects_duplicate_target_collision(tmp_path: Path) -> None:
    # Two papers with the same citekey from the two legacy paper homes.
    _write(tmp_path, "doc/papers/Adams2025.md", '---\nid: "paper:Adams2025"\ntype: paper\n---\n')
    _write(tmp_path, "doc/background/papers/Adams2025.md", '---\nid: "paper:Adams2025"\ntype: paper\n---\n')
    plan = plan_migration(tmp_path)
    assert plan.collisions  # non-empty: same new_rel_path / new_id


def test_plan_detects_duplicate_number_collision(tmp_path: Path) -> None:
    # Two already-conformant files share number 0003 → different ids/paths, but a
    # number-hygiene violation that path/id collision checks alone would miss.
    _write(tmp_path, "specs/hypotheses/0003-a.md", '---\nid: "hypothesis:0003-a"\ntype: hypothesis\n---\n')
    _write(tmp_path, "specs/hypotheses/0003-b.md", '---\nid: "hypothesis:0003-b"\ntype: hypothesis\n---\n')
    plan = plan_migration(tmp_path)
    assert any(c.get("kind") == "number" and c.get("number") == "0003" for c in plan.collisions)


def test_plan_relocates_singletons(tmp_path: Path) -> None:
    _write(tmp_path, "specs/research-question.md", '---\nid: "rq:x"\ntitle: RQ\nstatus: active\n---\n')
    (tmp_path / "specs/claim-registry.yaml").write_text("claims: []\n", encoding="utf-8")
    plan = plan_migration(tmp_path)
    targets = {s.new_rel_path for s in plan.singletons}
    assert "entities/research-question.md" in targets
    assert "entities/claim-registry.yaml" in targets


def test_plan_reserves_numbers_already_under_entities(tmp_path: Path) -> None:
    # Partial migration: entities/questions/0001-* already exists (created
    # additively). A new legacy question must take 0002, NOT collide on 0001.
    _write(tmp_path, "entities/questions/0001-existing.md",
           '---\nid: "question:0001-existing"\ntype: question\n---\n')
    _write(tmp_path, "doc/questions/new-one.md",
           '---\nid: "question:new-one"\ntype: question\ncreated: "2026-01-01"\n---\n')
    plan = plan_migration(tmp_path)
    move = next(m for m in plan.moves if m.old_id == "question:new-one")
    assert move.new_id == "question:0002-new-one"


def test_plan_reports_disk_collision_for_citekey(tmp_path: Path) -> None:
    # entities/papers/Adams2025.md already on disk; a legacy paper would land on
    # the same path → blocking disk collision.
    _write(tmp_path, "entities/papers/Adams2025.md", '---\nid: "paper:Adams2025"\ntype: paper\n---\n')
    _write(tmp_path, "doc/background/papers/Adams2025.md", '---\nid: "paper:Adams2025"\ntype: paper\n---\n')
    plan = plan_migration(tmp_path)
    assert any(c["kind"] == "disk" and c["target"] == "entities/papers/Adams2025.md" for c in plan.collisions)


def test_plan_reports_conformant_number_taken_under_entities(tmp_path: Path) -> None:
    # A conformant legacy hypothesis 0003-x wants to keep 0003, but entities/
    # already holds a different 0003 → blocking number collision.
    _write(tmp_path, "entities/hypotheses/0003-other.md",
           '---\nid: "hypothesis:0003-other"\ntype: hypothesis\n---\n')
    _write(tmp_path, "specs/hypotheses/0003-x.md",
           '---\nid: "hypothesis:0003-x"\ntype: hypothesis\n---\n')
    plan = plan_migration(tmp_path)
    assert any(c.get("kind") == "number" and c.get("number") == "0003"
               and c.get("occupied_by") == "entities/" for c in plan.collisions)
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
        if policy.strategy == "singleton":
            # Singleton kinds (research-question, claim-registry) are relocated by
            # _plan_singletons via explicit by-path rules, never numbered. Skip them
            # here so a stray `type: research-question` file is not mis-numbered.
            continue
        if policy.strategy == "citekey":
            for entity in items:
                local = Path(entity.rel_path).stem
                _add_move(plan, entity, f"{policy.root.as_posix()}/{local}.md", f"{kind}:{local}", kind)
            continue
        # numeric: preserve conformant numbers; assign the rest in created order.
        ordered = sorted(items, key=lambda e: (str(normalized[e.rel_path]["created"]), e.rel_path))
        taken: set[int] = set()
        # Seed `taken` with numbers ALREADY committed under entities/<kind>/ so a
        # PARTIALLY-migrated project (entities created additively before/after a
        # prior run) never reassigns an occupied number. These pre-existing files
        # are not moves; they only reserve their slots.
        existing_numbers = _existing_entity_numbers(project_root, policy)
        taken |= existing_numbers
        deferred: list[LegacyEntity] = []
        provisional: dict[str, int] = {}
        for entity in ordered:
            stem = Path(entity.rel_path).stem
            if local_part_conforms(kind, stem):
                number = int(stem.split("-", 1)[0])
                if number in existing_numbers:
                    # A conformant legacy file wants a number an entities/ file
                    # already holds → blocking number collision (manual fix).
                    plan.collisions.append(
                        {"kind": "number", "entity_kind": kind, "number": f"{number:04d}",
                         "sources": [entity.rel_path], "occupied_by": "entities/"}
                    )
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
    _detect_disk_collisions(project_root, plan)
    return plan


def _existing_entity_numbers(project_root: Path, policy) -> set[int]:
    """Numbers already committed under entities/<kind>/ (NNNN-*.md)."""
    directory = project_root / policy.root
    numbers: set[int] = set()
    if directory.is_dir():
        for path in directory.glob("*.md"):
            match = re.match(r"^(\d{4})-", path.name)
            if match is not None:
                numbers.add(int(match.group(1)))
    return numbers


def _detect_disk_collisions(project_root: Path, plan: MigrationPlan) -> None:
    """Flag any planned target path already occupied on disk by a file we are not
    moving (e.g. a pre-existing entities/papers/<citekey>.md or NNNN-*.md). This
    catches partial-migration / re-run cases that the moves-only collision pass
    cannot see."""
    moved_sources = {m.old_rel_path for m in plan.moves} | {s.old_rel_path for s in plan.singletons}
    for new_rel, old_rel in (
        *[(m.new_rel_path, m.old_rel_path) for m in plan.moves],
        *[(s.new_rel_path, s.old_rel_path) for s in plan.singletons],
    ):
        if new_rel in moved_sources:
            continue  # a swap among the files we are moving — handled by path/id checks
        if (project_root / new_rel).exists():
            plan.collisions.append({"kind": "disk", "target": new_rel, "sources": [old_rel]})


def _add_move(plan: MigrationPlan, entity: "LegacyEntity", new_rel: str, new_id: str, kind: str) -> None:
    plan.moves.append(Move(entity.rel_path, new_rel, entity.old_id, new_id, kind))
    if entity.old_id:
        plan.id_map[entity.old_id] = new_id
    # Frontmatterless / prose-header files carry no `old_id`, yet references may
    # still point at them by their old filename stem (e.g. a link to
    # `interpretation:2026-05-23-foo` for a file with no `id:`). Map a
    # filename-derived alias `<kind>:<old-stem>` -> new_id so those refs rewrite
    # instead of being reported unresolved. `setdefault` never clobbers a real
    # `old_id` mapping; stems are unique within a kind's directory, so aliases
    # never collide.
    stem_alias = f"{kind}:{Path(entity.rel_path).stem}"
    plan.id_map.setdefault(stem_alias, new_id)


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
    by_kind_number: dict[tuple[str, str], list[str]] = {}
    for move in plan.moves:
        by_path.setdefault(move.new_rel_path, []).append(move.old_rel_path)
        by_id.setdefault(move.new_id, []).append(move.old_rel_path)
        # number-hygiene collision: two files keep the SAME number within a kind
        # (e.g. pre-conformant 0003-a.md + 0003-b.md → different ids/paths, but a
        # duplicate number, which by_path/by_id alone would miss).
        local = move.new_id.split(":", 1)[1]
        number_match = re.match(r"^(\d{4})-", local)
        if number_match is not None:
            by_kind_number.setdefault((move.kind, number_match.group(1)), []).append(move.old_rel_path)
    for target, sources in sorted(by_path.items()):
        if len(sources) > 1:
            plan.collisions.append({"kind": "path", "target": target, "sources": sorted(sources)})
    for new_id, sources in sorted(by_id.items()):
        if len(sources) > 1:
            plan.collisions.append({"kind": "id", "new_id": new_id, "sources": sorted(sources)})
    for (kind, number), sources in sorted(by_kind_number.items()):
        if len(sources) > 1:
            plan.collisions.append({"kind": "number", "entity_kind": kind, "number": number, "sources": sorted(sources)})
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


def test_rewrite_reports_bare_wikilink() -> None:
    # A bare [[q01-foo]] (no kind prefix) cannot be auto-rewritten; it must be
    # surfaced as unresolved rather than silently left as a dead link.
    out, unresolved = rewrite_references("See [[q01-foo]] for context.\n", {})
    assert "[[q01-foo]]" in unresolved


def test_rewrite_reports_unmapped_plain_slug_reference() -> None:
    # A stale ref to a deleted entity by its OLD plain slug (no q##-/date shape).
    # It is unmapped and does not conform to the numeric policy, so it must be
    # reported — the legacy-shape-only heuristic would have silently kept it.
    id_map = {"question:aging-early": "question:0001-aging-early"}
    text = "Mapped question:aging-early. Dangling question:old-slug stays.\n"
    out, unresolved = rewrite_references(text, id_map)
    assert "question:0001-aging-early" in out
    assert "question:old-slug" in unresolved


def test_rewrite_leaves_external_and_conformant_tokens_alone() -> None:
    # A conformant id and an external/unmanaged prefix must NOT be flagged.
    id_map = {"question:q1-a": "question:0001-a"}
    text = "Canonical question:0002-keep and external doi:10.1/x and url https://e.org.\n"
    out, unresolved = rewrite_references(text, id_map)
    assert unresolved == []
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
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def rewrite_references(text: str, id_map: dict[str, str]) -> tuple[str, list[str]]:
    """Replace every mapped old id with its new id (longest-first to avoid prefix
    collisions). Returns (rewritten_text, unresolved_legacy_tokens).

    A token that *looks* legacy-shaped but has no mapping is reported in
    `unresolved` rather than left to rot into a dead link. This covers both
    `<kind>:<local>` tokens AND bare `[[<local>]]` wiki-links (no colon).
    """
    # Replace longest keys first so question:q10-b is handled before question:q1-b.
    for old_id in sorted(id_map, key=len, reverse=True):
        new_id = id_map[old_id]
        text = re.sub(rf"(?<![\w:.-]){re.escape(old_id)}(?![\w.-])", new_id, text)

    unresolved: list[str] = []
    new_ids = set(id_map.values())
    # (a) kind-qualified tokens (covers id:, related:, inline, and [[kind:local]]).
    #     For a kind WE MANAGE, any local part that (1) was not rewritten to a new
    #     id and (2) does not conform to the kind's filename policy is a
    #     stale/dangling reference — this catches plain slugs like
    #     `question:old-slug` that the old legacy-shape heuristic (q##-/date only)
    #     silently kept. External / unmanaged prefixes (urls, ontology ids) and
    #     already-conformant ids are left untouched.
    for match in _REF_TOKEN_RE.finditer(text):
        token, kind, local = match.group(0), match.group(1), match.group(2)
        if token in new_ids:
            continue  # already canonical (a freshly-written new id)
        if not is_markdown_entity_kind(kind):
            continue  # external prefix / url / kind we do not govern
        if resolve_path_policy(kind).strategy == "singleton":
            continue  # singletons carry no per-instance local part
        if local_part_conforms(kind, local):
            continue  # already a valid local part for this kind
        unresolved.append(token)
    # (b) bare wiki-links with NO kind prefix, e.g. [[q01-foo]] / [[2026-05-23-x]].
    #     These cannot be disambiguated to a kind, so they are reported, not rewritten.
    for match in _WIKILINK_RE.finditer(text):
        inner = match.group(1).strip()
        if ":" in inner:
            continue  # kind-qualified — handled by (a)/token replacement above
        if _LEGACY_LOCAL_SHAPE.match(inner):
            unresolved.append(f"[[{inner}]]")
    return text, sorted(set(unresolved))
```

> `rewrite_references` operates on a single file's full text (frontmatter + body),
> covering `id:`, `related:`, inline `<kind>:…`, and `[[<kind>:…]]` uniformly
> (same token shape). Unresolved detection is **policy-conformance based**, not a
> narrow legacy-shape heuristic: for any kind in the policy table, a remaining
> `<kind>:<local>` token whose `<local>` does not satisfy `local_part_conforms`
> (and was not rewritten to a new id) is reported — so a stale ref to a deleted
> entity by its plain old slug (`question:old-slug`) is caught, not just
> `q##-`/date-shaped ones. Bare wiki-links **without** a kind prefix
> (`[[q01-foo]]`) are caught by the dedicated `_WIKILINK_RE` scan and surfaced via
> `unresolved` for manual handling — they cannot be safely disambiguated to a
> kind. The orchestrator (Task 5) treats a non-empty `unresolved` as a blocking
> error under `--apply`.

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

    # 2. Reference rewrite across EVERY project markdown file that can carry an
    #    entity id — not only the moved entities. References live in non-entity
    #    prose too (reports, notes, research/packages, tasks). The final graph
    #    audit (step 4) only inspects STRUCTURED sources (entity frontmatter /
    #    relations / bindings), so raw inline `<kind>:local` and `[[…]]` links in
    #    bodies would slip through unrewritten. This project-wide pass — plus the
    #    unresolved-token report it produces — is that safety net.
    singleton_text: dict[str, str] = {}
    for sm in plan.singletons:
        singleton_text[sm.new_rel_path] = (project_root / sm.old_rel_path).read_text(encoding="utf-8")

    # In-place files: every *.md under the project's content roots that is NOT
    # being moved (moved sources are in `rewritten`, keyed by NEW path; singletons
    # in `singleton_text`). Covers pre-existing entities/ files, doc/ prose,
    # research/packages, and tasks. Templates and .git are skipped.
    moved_sources = {m.old_rel_path for m in plan.moves} | {s.old_rel_path for s in plan.singletons}
    inplace_text: dict[str, str] = {}
    for root_name in ("entities", "doc", "specs", "tasks", "research"):
        root = project_root / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if "templates" in path.parts:
                continue
            rel = path.relative_to(project_root).as_posix()
            if rel in moved_sources:
                continue  # handled via `rewritten` at its new path
            inplace_text[rel] = path.read_text(encoding="utf-8")

    all_unresolved: dict[str, list[str]] = {}
    for bucket in (rewritten, singleton_text, inplace_text):
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
    for rel, text in inplace_text.items():
        (project_root / rel).write_text(text, encoding="utf-8")

    # 4. Final graph validation — token rewriting can miss semantic references, so
    #    load the migrated tree and audit it. Fail loud (do NOT bump layout_version)
    #    if anything fails to resolve. The working tree is left modified for
    #    inspection; `git restore`/branch reset rolls back the uncommitted changes.
    from science_tool.graph.migrate import audit_project_sources
    from science_tool.graph.sources import load_project_sources

    rows, failed = audit_project_sources(load_project_sources(project_root))
    if failed:
        bad = [r for r in rows if r.get("status") == "fail"]
        raise ValueError(
            f"post-migration graph validation failed with {len(bad)} issue(s); "
            f"working tree left modified (git restore to roll back). First issues: {bad[:10]}"
        )

    # 5. Only after a clean audit: bump layout_version to 3.
    manifest_path = project_root / "science.yaml"
    manifest = _yaml_mod.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    manifest["layout_version"] = 3
    manifest_path.write_text(_yaml_mod.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    report["graph_validation"] = "passed"
    return report
```

> **Singletons & in-place refs are handled above:** `research-question.md` and
> `claim-registry.yaml` are relocated via `plan.singletons` (planned by
> `_plan_singletons`, including the non-`.md` registry that discovery skips) and
> their bodies are ref-rewritten; every other in-scope `*.md` (pre-existing
> `entities/`, `doc/` prose/reports, `research/packages`, `tasks/**`) is
> ref-rewritten **in place** (not moved). Singletons keep their own ids unchanged
> (relocation only), so they add nothing to `id_map`. The non-`.md`
> `claim-registry.yaml` is rewritten via the singleton bucket (the in-place pass
> only walks `*.md`).

- [ ] **Step 4: Add tests for in-place refs, singletons, and collision-blocking**

Append tests asserting: (a) `tasks/t001.md` containing `hypothesis:h01-x` is
rewritten to `hypothesis:0001-x`; (b) `specs/claim-registry.yaml` referencing
`hypothesis:h01-x` lands at `entities/claim-registry.yaml` with the ref rewritten;
(c) a project with two `Adams2025.md` paper sources raises `ValueError` under
`apply=True` and lists the collision in the dry-run report; (d) **a non-entity
file** `doc/reports/summary.md` containing both `hypothesis:h01-x` and a
`[[hypothesis:h01-x]]` link is rewritten **in place** to `hypothesis:0001-x`
(proving refs outside moved entities are not stranded); (e) a `doc/reports/`
file containing a dead `hypothesis:h99-ghost` token causes `apply=True` to raise
`ValueError` (unresolved-reference blocking) and the dry-run report lists it under
`unresolved_references`.

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
@click.option("--project-root", type=click.Path(exists=True, file_okay=False, path_type=Path), default=Path("."))
def entities_migrate_command(apply_changes: bool, project_root: Path) -> None:
    """Migrate a project's doc/specs entity layout into entities/ (v2 → v3)."""
    from science_tool.entity_layout_migration import migrate_layout

    try:
        report = migrate_layout(project_root, apply=apply_changes)
    except ValueError as exc:  # collisions / unresolved refs block --apply
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(report, indent=2))
```

> Use `--project-root` (not `--project-path`): it matches `science validate`
> (`validate/cli.py`) and the dominant convention across the CLI. Wrap the
> `ValueError` from `migrate_layout` (raised on blocking collisions / unresolved
> references under `--apply`) as a `ClickException`, mirroring `migrate-identifiers`.

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
3. **Dry run:** `science entities migrate --project-root <proj>` → review the JSON
   report: `moves`, `id_map`, and especially `unresolved_references`.
4. **Resolve `unresolved_references`:** these are legacy-shaped tokens with no
   mapping (renamed/deleted targets, bare `[[q01-…]]` wiki-links without a kind).
   Fix each by hand (point to the correct id or remove the dead link) and re-run
   the dry run until `unresolved_references` is empty.
5. **Apply:** `science entities migrate --apply --project-root <proj>` (performs
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

## Task 8: Additive repoint of entity checks Plan 2 missed (dual-root)

> Plan 2 repointed the main semantic checks to scan **both** `entities/` and the
> legacy roots, but three **active** entity-kind checks were left scanning `doc/`
> only, and two id/structure checks still hard-code the legacy roots. Until they
> are dual-rooted, a freshly *migrated* project (Tasks 1–6 set `layout_version: 3`
> and move files into `entities/`) would silently skip these checks — and the
> pilot (Task 9) would report a **false green**. This task makes them additive
> (`entities/` **and** legacy), exactly as Plan 2 did for the others; the legacy
> root is dropped in the Task 10 cutover.
>
> The affected checks (all in `CANONICAL_CHECK_MODULES`) and their policy roots:
> - `prereg.py` scans `doc/meta/pre-registration-*.md` + `doc/pre-registrations/*.md`; policy root is `entities/pre-registrations`.
> - `evidence_lines.py` scans `doc/evidence-lines` + `doc/propositions`; roots are `entities/evidence-lines` + `entities/propositions`.
> - `hypothesis_comparisons.py` identifies comparison docs purely by the `comparison-*.md` **filename** under `doc/discussions`. Migration canonicalizes discussion filenames to `NNNN-slug.md`, so that glob will never match a migrated comparison — detection must move to a body/frontmatter marker.
> - `cross_references.py` builds its known-id set from `(specs_dir, doc_dir)` only (≈ line 421) — ids defined in `entities/**/*.md` are absent, so refs to them can register as unknown.
> - `directory_structure.py` lists `specs/` and `doc/` as **required** dirs (ERROR if missing) and does not know about `entities/`. A migrated v3 project (entities under `entities/`, `specs/` empty or gone) would wrongly ERROR on a missing `specs/`, and a v3 project missing `entities/` would not be flagged at all. (There is no generic "unexpected dir" check, so `entities/` is not otherwise flagged today.)

**Files:**
- Modify: `science/src/science_tool/validate/checks/prereg.py`
- Modify: `science/src/science_tool/validate/checks/evidence_lines.py`
- Modify: `science/src/science_tool/validate/checks/hypothesis_comparisons.py`
- Modify: `science/src/science_tool/validate/checks/cross_references.py`
- Modify: `science/src/science_tool/validate/checks/directory_structure.py`
- Test: the matching `tests/validate/test_checks_*.py` modules (extend)

- [ ] **Step 1: Write the failing tests**

For each check, add a test that places the entity under its `entities/` policy
root and asserts the check still finds/validates it:
- `prereg`: `entities/pre-registrations/0001-x.md` is discovered.
- `evidence_lines`: `entities/evidence-lines/0001-x.md` and `entities/propositions/0001-y.md` are discovered.
- `hypothesis_comparisons`: a migrated comparison doc at the CONFORMANT path `entities/discussions/0001-comparison-h1-vs-h2.md` containing the `## Hypotheses Compared` marker (filename is `NNNN-slug`, so the legacy `comparison-*.md` glob no longer matches) is still recognized and section-checked; a plain non-comparison discussion `entities/discussions/0002-notes.md` is NOT flagged.
- `cross_references`: an id defined in `entities/questions/0001-x.md` joins the known-id set (a `related:` ref to it is NOT flagged unknown).
- `directory_structure`: a `layout_version: 3` project with `entities/` but **no** `specs/` does NOT error on a missing `specs/`; a `layout_version: 3` project **missing** `entities/` IS flagged; a `layout_version: 2` project still requires `specs/` (additive — v2 behavior unchanged).

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/validate -k "prereg or evidence or comparison or cross_ref or directory" -v`
Expected: the new assertions FAIL (entities/ locations not yet scanned).

- [ ] **Step 3: Repoint each check additively**

- `prereg.py`: also scan `resolve_path_policy("pre-registration").root` (keep the two legacy `doc/` globs for now).
- `evidence_lines.py`: also scan `entities/evidence-lines` and `entities/propositions`.
- `hypothesis_comparisons.py`: do **not** rely on the `comparison-*.md` filename for migrated docs — after migration discussion filenames are `NNNN-slug.md`. Instead, scan all `entities/discussions/*.md` and treat a file as a comparison when its body contains the distinguishing `## Hypotheses Compared` marker (the first of `_SECTIONS`), then require the remaining sections. Keep the legacy `doc/discussions/comparison-*.md` filename glob for un-migrated projects (a legacy comparison file without the marker is still flagged for the missing section, preserving today's behavior).
- `cross_references.py`: add `ctx.project_root / "entities"` to the `(ctx.specs_dir, ctx.doc_dir)` id-collection scan so `entities/**/*.md` ids join `all_ids`.
- `directory_structure.py`: **version-gate** the entity-layout required dirs on `ctx.manifest.get("layout_version")` (mirroring how `entity_conformance`/`manifest` already gate on version). Require `specs/` only when `layout_version < 3`; require `entities/` when `layout_version >= 3`. Leave `doc/`, `knowledge/`, `tasks/`, and the code/research dirs required in both eras. This is additive (v2 projects are unaffected) **and** simultaneously makes a migrated v3 project validate cleanly while flagging a v3 project that is missing `entities/` — so no further cutover edit to this file is needed in Task 10.

Prefer `resolve_path_policy(<kind>).root` over hard-coded `"entities/<plural>"`
strings so the policy table stays the single source of truth.

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/validate -k "prereg or evidence or comparison or cross_ref or directory" -v`
Expected: PASS (both legacy and `entities/` locations are scanned).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/ science/tests/validate/
git commit -m "feat(validate): dual-root the entity checks Plan 2 missed (prereg, evidence-lines, comparisons, xref, dir-structure)"
```

---

## Task 9: Pilot on a real project (verification)

**Files:** none (verification task; operates on a throwaway copy)

- [ ] **Step 1: Copy the smallest real project to a scratch dir**

Run: `cp -r ~/d/health/processes/cycles /tmp/cycles-migrate && cd /tmp/cycles-migrate && git status`
(Use a project that is already in git so `git mv` works; if it is part of a larger
repo, `git init` the copy and commit first.)

- [ ] **Step 2: Dry run and inspect**

Run: `cd /mnt/ssd/Dropbox/science/science && uv run science entities migrate --project-root /tmp/cycles-migrate`
Review `unresolved_references` in the JSON. If non-empty, this is real signal —
record what the dead/ambiguous refs are (they inform guide refinements).

> **Residual-risk check — paper `article:` mentions.** `rewrite_references` only
> touches kinds in the markdown policy table; `article:<bibkey>` is *not* one of
> them, so raw `article:` mentions pass through untouched. That is fine if
> paper-prefix cleanup stays owned by the existing refs/identifier migration — but
> the pilot must confirm it. After the dry run, grep the scratch copy for any
> surviving legacy `article:` tokens (`grep -rn 'article:' /tmp/cycles-migrate`)
> and record whether any remain post-migration. If the layout migration is
> expected to leave them for the refs migration, note that explicitly; if they
> should have been rewritten, file it back into Task 4 before cutover.

- [ ] **Step 3: Apply on the copy and validate**

Run: `cd /mnt/ssd/Dropbox/science/science && uv run science entities migrate --apply --project-root /tmp/cycles-migrate && uv run science validate --project-root /tmp/cycles-migrate`
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

## Task 9 — Pilot results (cycles, 2026-06-05)

Piloted on a faithful copy of `~/d/health/processes/cycles` (layout_version 2; 403
doc + 14 specs markdown, papers under `doc/papers` + `doc/background/papers`).
Outcome: **371 moves, 0 collisions; `--apply` succeeded with `graph_validation:
passed`; `science validate` PASSES on the migrated v3 tree** (68 warnings, all
pre-existing scientific-content — zero migration/location/conformance errors).

The pilot surfaced and fixed **five real tool gaps** (all with regression tests;
module tests 38 → 48, full suite green, ruff clean):

1. **Singleton-kind synthesis crash** (`0d76cafa`): a `type: research-question`
   file (singleton, no status vocab) hit `KeyError` in synthesis because
   `plan_migration` synthesized *all* discovered entities before the singleton
   skip. Fixed by excluding singleton-strategy kinds from the move-planning set.
2. **Filename-date fallback** (`a1ac9a6e`): frontmatterless date-prefixed files
   (`doc/plans/2026-05-30-…md`, no `created`/`**Date:**`) now take the filename
   `YYYY-MM-DD` as the `created` fallback instead of being blocked as undated.
3. **Shortform reference rewriting** (`a1ac9a6e`): prose shortforms `question:01`,
   `hypothesis:h01` are rewritten to the new numbering (`question:0001`,
   `hypothesis:0001`) so refs survive renumbering (decision: rewrite shortforms).
4. **Scope unresolved-detection to migrated kinds** (`a1ac9a6e`): refs to kinds
   stored outside the markdown model (`observation:*` in `observations.yaml`) are
   no longer false-flagged (decision: don't flag non-migrated kinds).
5. **Rewrite refs in YAML registries + `knowledge/`** (`7cc984a6`): the in-place
   rewrite walked only `*.md`, so `doc/observations/observations.yaml` and
   `knowledge/sources/local/*.yaml` kept old ids and broke the post-move graph
   audit (caught fail-loud, exactly as designed). Now walks `*.md`/`*.yaml`/`*.yml`
   across content roots incl. `knowledge/`; manifest `science.yaml` and the moved
   claim-registry singleton remain excluded.

Residual report items were genuine **source-data** issues an operator resolves via
the dry-run report (the documented workflow), not tool defects: 5 genuinely
date-less synthesis docs, dangling topic refs (topics not present as entities), an
informal `question:NN.datasets` field-access notation, and a `question:NN`
placeholder in a YAML comment. Non-entity doc types (`type: spec`, `type:
paper-review`) are correctly left in place (not in the entity policy). The pilot
copy lives at `/mnt/ssd/scratch/cycles-migrate` (throwaway).

---

## Task 10: CUTOVER — remove fallbacks, promote WARN→ERROR (IRREVERSIBLE; do last)

**Files:** discovery + validation modules listed below.
**Test:** update the corresponding tests to expect the steady-state behavior.

> Do not start this task until Task 9's pilot is green. This task makes
> `entities/` the only supported layout; un-migrated (`layout_version: 2`)
> projects will fail validation by design (design §11).

- [x] **Step 1: Discovery scans `entities/` only**

`science/src/science_tool/graph/storage_adapters/markdown.py`:

```python
        self._scan_roots = scan_roots or ["entities", "research/packages"]
```

> **Refinement found during cutover execution (2026-06-05):** the `markdown.py`
> *default* now scans `entities/` + `research/packages` for the 21 layout kinds,
> but the **main graph build** (`graph/sources.py`) must ALSO scan the
> datapackage/workflow family's existing markdown roots — `doc/datasets`,
> `doc/workflows`, `doc/workflow-runs`. Those kinds (`dataset`, `workflow`,
> `workflow-run`) are *not* in `markdown_entity_kinds()`, were never migrated to
> `entities/`, and are the only discoverer of that family's markdown (cf.
> `validate/_helpers.py`, `dataset_promotion_contract.py`, `commons/promote.py`).
> Dropping `doc/` wholesale orphaned them for *every* project (the cycles pilot
> didn't author that markdown, so it wasn't caught). Fix: pass explicit
> `scan_roots=["entities","research/packages","doc/datasets","doc/workflows","doc/workflow-runs"]`
> at the `sources.py` call site; the default stays `entities/`-only. `doc/` is a
> **transitional** home for this family — promoting `dataset` (and reconsidering
> `workflow`/`workflow-run`) to first-class `entities/` kinds, with dataset↔claim
> epistemic edges, is deferred to a dedicated follow-up plan
> (`docs/plans/2026-06-05-dataset-first-class-entity-design.md`).

- [ ] **Step 2: Drop singleton fallbacks**

`research_scope.py`: remove the `legacy_rq` fallback — resolve only
`ctx.project_root / singleton_path("research-question")`.
`verdict/registry.py` + `verdict/cli.py`: remove the `specs/claim-registry.yaml`
branch; use only `entities/claim-registry.yaml`.
`entities.py`: set `_ALLOWED_EXPLICIT_ROOTS = (Path("entities"),)`.

- [ ] **Step 3: Drop legacy-dir fallbacks in semantic checks**

In `hypotheses.py`, `discussions.py`, `document_structure.py`, `papers.py`, the
Plan 2 checks scan **both** the new and legacy roots. Drop the legacy root from
each `roots`/`synth_roots`/loop tuple so only the `entities/` location remains
(e.g. `hypotheses.py` becomes a single `entities/hypotheses` scan). In
`discussions.py`, also drop the legacy `doc/reports/synthesis.md` singleton
candidate retained for v2.

In `id_prefixes.py`, narrow the scan roots from
`(ctx.project_root / "entities", ctx.doc_dir, ctx.specs_dir)` (Plan 2) to
`(ctx.project_root / "entities",)` so the check no longer inspects legacy roots.

Drop the legacy roots added additively in **Task 8** as well: `prereg.py`
(remove the `doc/meta/pre-registration-*.md` + `doc/pre-registrations` globs),
`evidence_lines.py` (remove the `doc/evidence-lines` + `doc/propositions`
scans), `hypothesis_comparisons.py` (remove the legacy `doc/discussions/comparison-*.md`
filename glob, leaving the marker-based `entities/discussions/*.md` scan), and
`cross_references.py` (remove `ctx.specs_dir`/`ctx.doc_dir` from the
id-collection scan, leaving `entities/` only). `directory_structure.py` needs
**no** cutover edit — Task 8 already version-gated its required dirs, so setting
`layout_version: 3` automatically drops the `specs/` requirement and enforces
`entities/`.

- [ ] **Step 4: `layout_version < 3` becomes ERROR**

`manifest.py`: flip the existing Plan 2 `< 3` WARN to ERROR:

```python
    layout_version = ctx.manifest.get("layout_version")
    if isinstance(layout_version, int) and layout_version < 3:
        yield _result(
            Severity.ERROR,
            "science.yaml: layout_version must be >= 3 — run `science entities migrate`",
        )
```

A *missing* `layout_version` is already an ERROR via `_REQUIRED_FIELDS` (it lists
`"layout_version"`), so do **not** add a `not isinstance(...)` arm — it would
double-report the missing case. Flipping the existing `< 3` branch from WARN to
ERROR is sufficient.

- [ ] **Step 5: Conformance checks promote to ERROR**

Plan 2 already routes every conformance yield through the `_severity(ctx)` helper
in `entity_conformance.py`. The cutover only changes that helper's **body** to
gate on `layout_version` (no call-site edits needed):

```python
def _severity(ctx: ValidateContext) -> Severity:
    version = ctx.manifest.get("layout_version")
    return Severity.ERROR if isinstance(version, int) and version >= 3 else Severity.WARN
```

This covers the stranded-file branch in `check_entity_location_coherence` too:
Plan 2 already routes it through `_severity(ctx)` (Plan 2, Task 3, step (a)), so a
markdown entity left in `doc/`/`specs/` becomes an **ERROR** at `layout_version: 3`
— stranded entities are a v3 violation, not merely advisory. (Prose / non-entity
markdown is still skipped by the `is_markdown_entity_kind` guard.)

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
- **Partial-migration safety** (numbers/paths already committed under `entities/` are reserved, not reassigned; disk + existing-number collisions reported) → Task 3 (`_existing_entity_numbers`, `_detect_disk_collisions`). ✅
- **All legacy kinds covered for frontmatterless files** (`_DIR_TO_KIND` derived from the policy table, so evidence-lines/reports/plans/searches/methods/pre-registrations are not stranded) → Task 1. ✅
- **Synthesized status is a controlled per-kind value** (prose `**Status:**` accepted only if valid, else per-kind default; never a blanket invalid `"active"`) → Task 2 (`default_status`/`valid_statuses` accessors). ✅
- Reference-rewrite completeness + fail-loud on unresolved → Task 4 (`<kind>:local` tokens **and** bare `[[local]]` wiki-links via `_WIKILINK_RE`) + Task 5 (rewrites **all** project markdown — entities, singletons, prose/reports, research/packages, tasks — and blocks `--apply` on any unresolved token, the safety net the structured-only graph audit cannot provide). ✅
- **Comparison docs survive filename canonicalization** (detected by the `## Hypotheses Compared` body marker, not a `comparison-*.md` filename) → Task 8 (additive) + Task 10 (cutover). ✅
- **Final graph validation before success** (`audit_project_sources` after writes; no `layout_version` bump if it fails) → Task 5 step 4. ✅
- **Number-hygiene collisions** (two files sharing a number within a kind) detected, not just path/id dupes → Task 3 (`_detect_collisions` `(kind, number)`). ✅
- Claim-registry + task-graph ref rewriting → Task 5 (singleton + `tasks/**/*.md` buckets). ✅
- **Singleton-strategy kinds never numbered** (a stray `type: research-question`
  file is skipped in `plan_migration`, not mis-numbered) → Task 3 (strategy
  guard) + `_plan_singletons`. ✅
- Migration guide → Task 7. ✅
- **Entity checks Plan 2 left scanning legacy roots only** (prereg, evidence-lines,
  propositions, hypothesis-comparisons) + `cross_references` id scan → repointed
  additively in Task 8, legacy dropped in the Task 10 cutover. ✅
- **`directory_structure` required dirs version-gated** (`specs/` for v2,
  `entities/` for v3) so migrated projects validate during the additive window and
  a v3 project missing `entities/` is flagged — no separate cutover edit → Task 8. ✅
- **Frontmatterless synthesis singleton classified correctly** (`doc/reports/synthesis.md`
  → synthesis via by-path override, not `report` from its parent dir) → Task 1. ✅
- **Stale plain-slug references caught** (unresolved detection is policy-conformance
  based, not a `q##-`/date-shape heuristic, so `question:old-slug` is reported) → Task 4. ✅
- Pilot before cutover → Task 9. ✅
- No-fallback cutover (scan roots, singletons, `_ALLOWED_EXPLICIT_ROOTS`, legacy
  semantic-check fallbacks incl. the Task 8 stragglers) + `layout_version: 3`
  ERROR + WARN→ERROR (one-body change to the Plan 2 `_severity` helper) → Task 10. ✅

**Known limitations (documented, not silent):**
- YAML re-render via `yaml.safe_dump` does not preserve comments/key-ordering
  nuance in migrated frontmatter. Acceptable: frontmatter is regenerated to a
  canonical field order; bodies (where prose comments live) are untouched except
  for id-token replacement. If comment preservation in frontmatter becomes a
  requirement, swap `yaml` for `ruamel.yaml` in `entity_layout_migration.py` only.
- Bare wiki-links without a kind prefix (`[[q01-foo]]`) are surfaced as
  `unresolved` for manual fixing rather than auto-rewritten — by design, since
  they cannot be disambiguated to a kind safely.

**Verify-before-coding notes:** the `validate` CLI flag is `--project-root`
(confirmed in `science/src/science_tool/validate/cli.py`); the new `entities
migrate` command uses the same name (Task 6, Task 9 Step 3). Confirm
`discover_legacy_entities` should also walk `doc/reports/synthesis/` explicitly if
synthesis files there lack a `synthesis` parent dir (extend
`_LEGACY_SCAN_ROOTS`/`_DIR_TO_KIND` if the pilot shows misses).
