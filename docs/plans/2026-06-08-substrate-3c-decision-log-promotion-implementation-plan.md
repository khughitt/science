# Substrate Phase 3c — decision-log promotion + generated `core/decisions.md` view — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the `decision-log` rows of `entities.yaml` by promoting each real decision to an id-preserving `entities/decision/<local>.md` owner file (prose in the body), and make `core/decisions.md` a generated view rendered from those owners.

**Architecture:** Approach A — a dedicated `graph/decision_log.py` owns all decision-prose knowledge (parser, owner renderer, view generator). The existing 3b retirement executor (`graph/aggregate_retire.py`) gains a decision-kind branch that delegates content to an injected `DecisionLogIndex`; it never reads `core/decisions.md` itself. A new `verbatim` filename strategy makes the uppercase, sequence-style decision ids (`D1`, `D2-treatment-response-category`) id-preserving.

**Tech Stack:** Python 3.13, click, PyYAML, pytest. Package root `~/d/science/science`. Run tests with `uv run --frozen pytest`; lint with `uv run --frozen ruff check . && uv run --frozen ruff format --check .` (120-char). Never `pip`.

**Design doc:** `docs/plans/2026-06-08-substrate-3c-decision-log-promotion-design.md`.

**Branch:** `substrate-3c-decision-log` (already created off `main`).

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `science/src/science_tool/entities.py` (modify) | register `verbatim` strategy + `decision` builtin filename-policy kind | 1 |
| `science/src/science_tool/entity_layout_migration.py` (modify) | `verbatim` migrator branch (preserve stem) | 2 |
| `science/src/science_tool/graph/decision_log.py` (create) | parser → `DecisionLogIndex`; owner renderer; view generator | 3, 4 |
| `science/src/science_tool/graph/aggregate_retire.py` (modify) | decision-kind branch + `delete_cruft` exclusion; inject index | 5 |
| `science/src/science_tool/cli.py` (modify) | `--promote-decisions`; `entities generate-decisions` | 6 |
| `science/tests/test_verbatim_strategy.py` (create) | Task 1 tests |  |
| `science/tests/test_entity_layout_migration.py` (modify) | Task 2 test |  |
| `science/tests/graph/test_decision_log_parse.py` (create) | Task 3 tests |  |
| `science/tests/graph/test_decision_log_render.py` (create) | Task 4 tests |  |
| `science/tests/graph/test_aggregate_retire_decisions.py` (create) | Task 5 tests |  |
| `science/tests/test_cli_entities_decisions.py` (create) | Task 6 tests |  |

All paths below are relative to `~/d/science`. Run pytest from `~/d/science/science`.

---

## Task 1: `verbatim` filename strategy + `decision` builtin filename-policy kind

**Files:**
- Modify: `science/src/science_tool/entities.py`
- Test: `science/tests/test_verbatim_strategy.py` (create)

Context: `verbatim` preserves a local part exactly as the filename stem (no lowercasing, no derivation). It is **builtin-only** — it follows `singleton`'s precedent of being absent from `_VALID_STRATEGIES`, so no local manifest kind may declare it. `decision` is registered as a builtin *filename-policy* kind using `verbatim`; this shadows any local-manifest `decision` **policy** (intended). Note this is the filename-policy table only — `decision` is deliberately NOT added to the graph `EntityRegistry` core kinds in 3c (see "Notes for the executor"); it stays a local registry kind so MM30 keeps loading.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_verbatim_strategy.py`:

```python
"""Phase 3c: the `verbatim` filename strategy + `decision` core kind."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.entities import (
    EntityCommandError,
    _VALID_STRATEGIES,
    entity_policies,
    generate_entity_id,
    local_part_conforms,
    resolve_path_policy,
    validate_entity_id,
)


def test_decision_resolves_to_verbatim_policy():
    policy = resolve_path_policy("decision")
    assert policy.root == Path("entities/decision")
    assert policy.strategy == "verbatim"


def test_verbatim_accepts_uppercase_and_kebab_ids():
    assert local_part_conforms("decision", "D1")
    assert local_part_conforms("decision", "D10")
    assert local_part_conforms("decision", "D2-treatment-response-category")


def test_verbatim_rejects_unsafe_local_parts():
    assert not local_part_conforms("decision", "../escape")
    assert not local_part_conforms("decision", "a/b")
    assert not local_part_conforms("decision", ".hidden")
    assert not local_part_conforms("decision", "D..x")
    assert not local_part_conforms("decision", "")


def test_validate_entity_id_accepts_verbatim_decision():
    assert validate_entity_id("decision", "decision:D1") == "decision:D1"


def test_validate_entity_id_rejects_bad_verbatim_local_part():
    with pytest.raises(EntityCommandError):
        validate_entity_id("decision", "decision:../escape")
    with pytest.raises(EntityCommandError):
        validate_entity_id("decision", "decision:D..x")


def test_generate_entity_id_verbatim_requires_explicit_id():
    # Sequence identities are never derived from a title.
    with pytest.raises(EntityCommandError):
        generate_entity_id(Path("."), "decision", "Some decision title", None, None)
    # An explicit id passes straight through.
    assert generate_entity_id(Path("."), "decision", "ignored", "decision:D7", None) == "decision:D7"


def test_verbatim_is_builtin_only_not_in_valid_strategies():
    # Mirrors `singleton`: a local manifest may not opt into `verbatim`.
    assert "verbatim" not in _VALID_STRATEGIES


def test_builtin_decision_overrides_local_manifest(tmp_path: Path):
    # A project whose local manifest still declares `decision` must still resolve
    # to the builtin verbatim policy (builtins win; local shadowing is silent).
    sources = tmp_path / "knowledge" / "sources" / "local"
    sources.mkdir(parents=True)
    (tmp_path / "science.yaml").write_text(
        "name: t\nprofile: research\nlayout_version: 3\nknowledge:\n  local_profile: local\n",
        encoding="utf-8",
    )
    (sources / "manifest.yaml").write_text(
        "entity_kinds:\n"
        "  - name: decision\n"
        "    canonical_prefix: decision\n"
        "    home: entities/local-decisions\n"
        "    strategy: numeric\n",
        encoding="utf-8",
    )
    policy = resolve_path_policy("decision", project_root=tmp_path)
    assert policy.root == Path("entities/decision")
    assert policy.strategy == "verbatim"
    # And the local declaration of `decision` is absent from the resolved table's
    # local override (builtin key wins on merge).
    assert entity_policies(tmp_path)["decision"].strategy == "verbatim"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_verbatim_strategy.py -q`
Expected: FAIL — `resolve_path_policy("decision")` raises `EntityCommandError: Unsupported source-authored entity kind: decision` (decision not yet registered).

- [ ] **Step 3: Add the `verbatim` regex and strategy literal**

In `science/src/science_tool/entities.py`:

Change the strategy literal (currently line 25):

```python
EntityFilenameStrategy = Literal["numeric", "citekey", "singleton", "slug", "verbatim"]
```

Immediately after the `_SLUG_RE` definition (currently line 185), add:

```python
# `verbatim` preserves a sequence-style local part exactly (e.g. decision ids
# D1, D2-treatment-response-category). Unlike `slug` it is case-preserving and
# never derived. Path-safety: no slash, no leading dot, no `..`.
_VERBATIM_RE = re.compile(r"^(?!.*\.\.)[A-Za-z0-9][A-Za-z0-9._-]*$")
```

- [ ] **Step 4: Register the `decision` builtin policy + status vocab**

In `_BUILTIN_MARKDOWN_POLICIES` (the dict ending around line 60), add an entry next to `concept`:

```python
    "concept": EntityPathPolicy(Path("entities/concepts"), "slug"),
    "decision": EntityPathPolicy(Path("entities/decision"), "verbatim"),
    "paper": EntityPathPolicy(Path("entities/papers"), "citekey"),
```

In `_DEFAULT_STATUS` add (after `"concept": "active",`):

```python
    "concept": "active",
    "decision": "active",
}
```

In `_STATUS_VALUES` add (after the `"concept": frozenset({"active", "deprecated"}),` line):

```python
    "concept": frozenset({"active", "deprecated"}),
    "decision": frozenset({"active", "superseded", "abandoned"}),
}
```

Leave `_VALID_STRATEGIES` unchanged (verbatim stays builtin-only, like singleton).

- [ ] **Step 5: Add `verbatim` branches to conform / validate / generate**

In `local_part_conforms` (currently the `slug` branch ends at line 347), add before the final `return False`:

```python
    if strategy == "slug":
        return bool(_SLUG_RE.fullmatch(local_part))
    if strategy == "verbatim":
        return bool(_VERBATIM_RE.fullmatch(local_part))
    return False  # singletons have no per-instance local part
```

In `validate_entity_id` (after the `slug` branch, around line 413), add:

```python
    if strategy == "slug":
        if not _SLUG_RE.fullmatch(local_part):
            raise EntityCommandError(f"Invalid slug local part: {entity_id}")
        return entity_id
    if strategy == "verbatim":
        if not _VERBATIM_RE.fullmatch(local_part):
            raise EntityCommandError(f"Invalid verbatim local part: {entity_id}")
        return entity_id
```

In `generate_entity_id` (after the `citekey`/`singleton` raises, around line 450), add a `verbatim` raise before the `slug_value` line:

```python
    if strategy == "singleton":
        raise EntityCommandError(f"{kind} is a singleton; it is not created via this path")
    if strategy == "verbatim":
        raise EntityCommandError(
            f"{kind} requires an explicit --id; sequence identities are not derived from a title"
        )

    slug_value = validate_slug(slug) if slug is not None else derive_slug(title)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_verbatim_strategy.py -q`
Expected: PASS (8 passed).

- [ ] **Step 7: Run the focused regression + lint**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_entities.py tests/test_entity_layout_migration.py -q && uv run --frozen ruff check src/science_tool/entities.py && uv run --frozen ruff format --check src/science_tool/entities.py`
Expected: PASS / no new lint errors. (If `tests/test_entities.py` does not exist, run `uv run --frozen pytest -k entities -q` instead.)

- [ ] **Step 8: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/entities.py science/tests/test_verbatim_strategy.py
git commit -m "feat(substrate-3c): verbatim filename strategy + decision core kind"
```

---

## Task 2: `verbatim` migrator branch (preserve stem)

**Files:**
- Modify: `science/src/science_tool/entity_layout_migration.py:440-446`
- Test: `science/tests/test_entity_layout_migration.py` (add one test)

Context: the v2→v3 migrator numbers numeric kinds. `slug` kinds are exempted (preserve their kebab stem) by a branch at lines 440-446. Decision ids must likewise be preserved — without this branch a stem like `D1` would reach the numeric branch and `int("D1")` would crash. `verbatim` behaves identically to `slug` here (preserve stem), so the two share one branch.

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_entity_layout_migration.py` (near the existing slug test):

```python
def test_migrator_preserves_verbatim_decision_stem(tmp_path: Path):
    """A `verbatim` (decision) entity keeps its exact stem; never renumbered."""
    from science_tool.entity_layout_migration import plan_migration

    proj = tmp_path
    (proj / "science.yaml").write_text(
        "name: t\nprofile: research\nlayout_version: 2\nknowledge:\n  local_profile: local\n",
        encoding="utf-8",
    )
    legacy = proj / "doc" / "decisions"
    legacy.mkdir(parents=True)
    (legacy / "D1.md").write_text(
        "---\nid: decision:D1\ntype: decision\ntitle: First\nstatus: active\ncreated: 2026-01-01\n---\nbody\n",
        encoding="utf-8",
    )

    plan = plan_migration(proj)
    moves = {m.new_rel_path: m.new_id for m in plan.moves}
    assert "entities/decision/D1.md" in moves
    assert moves["entities/decision/D1.md"] == "decision:D1"
```

Note: if `plan_migration`/move attribute names differ in your tree, mirror the existing slug test in this same file exactly — it exercises the identical code path.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_entity_layout_migration.py::test_migrator_preserves_verbatim_decision_stem -q`
Expected: FAIL — the `D1` stem reaches the numeric branch (`int("D1")` `ValueError`) or is mis-numbered.

- [ ] **Step 3: Extend the slug branch to cover verbatim**

In `science/src/science_tool/entity_layout_migration.py`, change the branch at lines 440-446 from `slug`-only to cover both:

```python
        if policy.strategy in ("slug", "verbatim"):
            # Slug and verbatim kinds preserve their stem; never numbered. Without
            # this branch a stem like "1q-gain" or "D1" reaches the numeric branch
            # and int() crashes.
            for entity in items:
                local = Path(entity.rel_path).stem
                _add_move(plan, entity, f"{policy.root.as_posix()}/{local}.md", f"{kind}:{local}", kind)
            continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_entity_layout_migration.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
git commit -m "feat(substrate-3c): verbatim migrator branch preserves decision stem"
```

---

## Task 3: `decision_log.py` — parser → `DecisionLogIndex`

**Files:**
- Create: `science/src/science_tool/graph/decision_log.py`
- Test: `science/tests/graph/test_decision_log_parse.py` (create)

Context: parses the hand-authored `core/decisions.md` into a `DecisionLogIndex` keyed by `canonical_id`. The heading (`## `) is the only section delimiter — a lone `---` is view formatting, never a boundary. The body is opaque verbatim markdown (only the trailing separator is stripped). `date`/`status` are extracted as queryable copies from either `**Date**:` or `- **Date:**` label forms, while staying verbatim in the body. `title` excludes the leading id token so the renderer's `## <local_id>. <title>` does not duplicate the id.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/graph/test_decision_log_parse.py`:

```python
"""Phase 3c: core/decisions.md section parser."""

from __future__ import annotations

from science_tool.graph.decision_log import parse_decision_log

MM30_STYLE = """\
<!-- header comment -->

# Decisions

## D1. Z-score normalization before meta-analysis (2026-03-31)

**Date**: 2026-03-31
**Status**: active
**Decision**: z-score first.

**Why**: scale differences.

---

## D5. Layered rationale (2026-05-01)

- **Date:** 2026-05-01
- **Status:** active

Body line.

---

A horizontal rule inside the body:

---

Amendment (2026-05-02): later note.

---
"""

META_STYLE = """\
# Decisions

## D-001: Scaffold the meta-project

- **Date:** 2026-04-23
- **Status:** active

Why text.
"""


def test_parses_canonical_ids_from_both_heading_styles():
    idx = parse_decision_log(MM30_STYLE)
    assert set(idx.sections) == {"decision:D1", "decision:D5"}
    idx2 = parse_decision_log(META_STYLE)
    assert set(idx2.sections) == {"decision:D-001"}


def test_title_excludes_leading_id_token():
    idx = parse_decision_log(MM30_STYLE)
    assert idx.sections["decision:D1"].title == "Z-score normalization before meta-analysis (2026-03-31)"
    idx2 = parse_decision_log(META_STYLE)
    assert idx2.sections["decision:D-001"].title == "Scaffold the meta-project"


def test_extracts_date_and_status_from_both_label_forms():
    idx = parse_decision_log(MM30_STYLE)
    assert idx.sections["decision:D1"].date == "2026-03-31"  # **Date**: form
    assert idx.sections["decision:D1"].status == "active"
    assert idx.sections["decision:D5"].date == "2026-05-01"  # - **Date:** form
    assert idx.sections["decision:D5"].status == "active"


def test_body_preserves_internal_horizontal_rule_and_is_not_truncated():
    idx = parse_decision_log(MM30_STYLE)
    body = idx.sections["decision:D5"].body
    assert "Body line." in body
    assert "A horizontal rule inside the body:" in body
    assert "Amendment (2026-05-02): later note." in body
    # The metadata label lines stay verbatim in the body too.
    assert "**Date:**" in body


def test_missing_date_and_status_are_none():
    idx = parse_decision_log("## D9. No metadata here\n\nJust prose.\n")
    sec = idx.sections["decision:D9"]
    assert sec.date is None
    assert sec.status is None
    assert sec.local_id == "D9"


def test_status_superseded_by_normalizes_query_copy_but_preserves_body():
    idx = parse_decision_log("## D-001: Old choice\n\n- **Status:** superseded by D-002\n\nBody.\n")
    sec = idx.sections["decision:D-001"]
    assert sec.status == "superseded"
    assert "superseded by D-002" in sec.body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/graph/test_decision_log_parse.py -q`
Expected: FAIL — `ModuleNotFoundError: science_tool.graph.decision_log`.

- [ ] **Step 3: Write the parser**

Create `science/src/science_tool/graph/decision_log.py`:

```python
"""Phase 3c: parse + render the decision log.

`core/decisions.md` is a hand-authored, append-only log today. 3c makes it a
*generated view* over `entities/decision/*.md` owner files: each decision's
identity and full prose live in an owner file; this module is the only place
that knows how to (a) parse the legacy log into per-decision sections and
(b) render owner files back into the log. The 3b retirement executor delegates
all decision-prose work here via an injected `DecisionLogIndex`.

The section delimiter is the `## ` heading ONLY. A lone `---` is view
formatting, never a hard boundary — so an intentional horizontal rule inside a
decision body survives. The section body is opaque verbatim markdown; only the
trailing separator is stripped.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

# Where the generated log lives, and where promoted owners declare they came from.
DECISIONS_REL = "core/decisions.md"

_GENERATED_BANNER = (
    "<!-- GENERATED — do not edit. Source: entities/decision/*.md. "
    "Regenerate: science entities generate-decisions -->"
)


@dataclass(frozen=True, slots=True)
class DecisionSection:
    canonical_id: str
    local_id: str
    title: str
    date: str | None
    status: str | None
    body: str  # opaque verbatim markdown (trailing separator stripped)


@dataclass(frozen=True, slots=True)
class DecisionLogIndex:
    sections: dict[str, DecisionSection]

    def get(self, canonical_id: str) -> DecisionSection | None:
        return self.sections.get(canonical_id)


def _label_value(line: str, label: str) -> str | None:
    """Return the value after a `**Label**:` / `- **Label:**` style line, else None.

    Both forms normalize identically once `**` and a leading `- ` are removed:
    `- **Date:** 2026-03-31` and `**Date**: 2026-03-31` -> `Date: 2026-03-31`.
    """
    norm = line.strip().replace("**", "").lstrip("- ").strip()
    prefix = f"{label.lower()}:"
    if norm.lower().startswith(prefix):
        return norm[len(prefix) :].strip() or None
    return None


def _split_heading(heading_text: str) -> tuple[str, str]:
    """`D1. Title` -> (`D1`, `Title`); `D-001: Title` -> (`D-001`, `Title`)."""
    token = ""
    for ch in heading_text:
        if ch in ". :\t":
            break
        token += ch
    title = heading_text[len(token) :].lstrip(". :\t").strip()
    return token, title


def _normalized_status(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if value.lower().startswith("superseded by "):
        return "superseded"
    return value


def parse_decision_log(text: str) -> DecisionLogIndex:
    lines = text.splitlines()
    sections: dict[str, DecisionSection] = {}
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("## "):
            heading_text = line[3:].strip()
            local_id, title = _split_heading(heading_text)
            # Capture body until the next `## ` heading or EOF.
            j = i + 1
            body_lines: list[str] = []
            while j < n and not lines[j].startswith("## "):
                body_lines.append(lines[j])
                j += 1
            # Strip a single trailing view separator (--- plus surrounding blanks).
            while body_lines and body_lines[-1].strip() == "":
                body_lines.pop()
            if body_lines and body_lines[-1].strip() == "---":
                body_lines.pop()
            while body_lines and body_lines[-1].strip() == "":
                body_lines.pop()
            date = None
            status = None
            for bl in body_lines:
                if date is None:
                    date = _label_value(bl, "Date")
                if status is None:
                    status = _normalized_status(_label_value(bl, "Status"))
            canonical_id = f"decision:{local_id}"
            sections[canonical_id] = DecisionSection(
                canonical_id=canonical_id,
                local_id=local_id,
                title=title,
                date=date,
                status=status,
                body="\n".join(body_lines).strip("\n"),
            )
            i = j
            continue
        i += 1
    return DecisionLogIndex(sections)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/graph/test_decision_log_parse.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Lint**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/graph/decision_log.py && uv run --frozen ruff format --check src/science_tool/graph/decision_log.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/graph/decision_log.py science/tests/graph/test_decision_log_parse.py
git commit -m "feat(substrate-3c): decision-log section parser (heading-delimited, opaque body)"
```

---

## Task 4: `decision_log.py` — owner renderer + view generator + round-trip

**Files:**
- Modify: `science/src/science_tool/graph/decision_log.py`
- Test: `science/tests/graph/test_decision_log_render.py` (create)

Context: `render_owner_file` writes one promoted decision owner (frontmatter identity/metadata + opaque body + 3b `promoted_from` marker). `read_decision_owners` + `render_decisions_view` regenerate `core/decisions.md` from the owner directory, sorted by natural-numeric local id (`D1 < D2 < D10`), emitting the generated-view banner (not the append-only template header). The headline safety test is semantic round-trip: `parse(original).sections == parse(rendered).sections`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/graph/test_decision_log_render.py`:

```python
"""Phase 3c: decision owner rendering + generated view + round-trip."""

from __future__ import annotations

from pathlib import Path

from science_tool.graph.decision_log import (
    DecisionSection,
    parse_decision_log,
    read_decision_owners,
    render_decisions_view,
    render_owner_file,
)


def _section(local_id: str, title: str, body: str, date=None, status=None) -> DecisionSection:
    return DecisionSection(f"decision:{local_id}", local_id, title, date, status, body)


def test_render_owner_file_shape():
    sec = _section("D1", "Z-score first", "**Why**: scale.\n", date="2026-03-31", status="active")
    text = render_owner_file(sec, promoted_from="knowledge/sources/local/entities.yaml")
    assert text.startswith("---\n")
    assert "id: decision:D1\n" in text
    assert "type: decision\n" in text
    assert "title: Z-score first\n" in text
    assert "date: '2026-03-31'\n" in text or "date: 2026-03-31\n" in text
    assert "status: active\n" in text
    assert "source_path: core/decisions.md\n" in text
    assert "promoted_from: knowledge/sources/local/entities.yaml\n" in text
    assert "**Why**: scale." in text


def test_render_owner_file_omits_absent_date_status():
    sec = _section("D9", "No metadata", "Prose.\n")
    text = render_owner_file(sec, promoted_from="x")
    assert "date:" not in text
    assert "status:" not in text


def test_generated_view_sorts_natural_and_has_banner(tmp_path: Path):
    d = tmp_path / "entities" / "decision"
    d.mkdir(parents=True)
    for local in ("D1", "D2", "D10"):
        (d / f"{local}.md").write_text(
            render_owner_file(_section(local, f"Title {local}", f"Body {local}.\n", status="active"),
                              promoted_from="x"),
            encoding="utf-8",
        )
    out = render_decisions_view(read_decision_owners(d))
    assert out.startswith("<!-- GENERATED")
    # Natural order: D1, D2, D10 (not lexical D1, D10, D2).
    assert out.index("## D1.") < out.index("## D2.") < out.index("## D10.")
    # No duplicated id in the heading.
    assert "## D1. Title D1" in out
    assert "## D1. D1." not in out


def test_round_trip_semantic_equality(tmp_path: Path):
    original = """\
# Decisions

## D1. Z-score first (2026-03-31)

**Date**: 2026-03-31
**Status**: active

**Why**: scale differences.

---

## D10. Later decision (2026-05-01)

- **Date:** 2026-05-01
- **Status:** active

Body with an internal rule:

---

Tail note.

---
"""
    idx = parse_decision_log(original)
    d = tmp_path / "entities" / "decision"
    d.mkdir(parents=True)
    for sec in idx.sections.values():
        (d / f"{sec.local_id}.md").write_text(render_owner_file(sec, promoted_from="x"), encoding="utf-8")
    rendered = render_decisions_view(read_decision_owners(d))
    idx2 = parse_decision_log(rendered)
    assert idx2.sections == idx.sections  # frozen dataclass equality over all fields
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/graph/test_decision_log_render.py -q`
Expected: FAIL — `ImportError` for `render_owner_file` / `read_decision_owners` / `render_decisions_view`.

- [ ] **Step 3: Add the renderer + generator**

Append to `science/src/science_tool/graph/decision_log.py`:

```python
@dataclass(frozen=True, slots=True)
class DecisionOwner:
    local_id: str
    title: str
    date: str | None
    status: str | None
    body: str


def render_owner_file(section: DecisionSection, *, promoted_from: str) -> str:
    """Render one promoted decision owner: frontmatter + opaque body."""
    fm: dict[str, object] = {
        "id": section.canonical_id,
        "type": "decision",
        "title": section.title,
    }
    if section.date is not None:
        fm["date"] = section.date
    if section.status is not None:
        fm["status"] = section.status
    fm["source_path"] = DECISIONS_REL
    fm["promoted_from"] = promoted_from
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
    return f"---\n{front}---\n\n{section.body.rstrip()}\n"


def _front_matter_and_body(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    fm = yaml.safe_load(text[4:end]) or {}
    body = text[end + 4 :].lstrip("\n")
    return fm, body


def read_decision_owners(decision_dir: Path) -> list[DecisionOwner]:
    owners: list[DecisionOwner] = []
    if not decision_dir.is_dir():
        return owners
    for path in sorted(decision_dir.glob("*.md")):
        fm, body = _front_matter_and_body(path.read_text(encoding="utf-8"))
        canonical_id = str(fm.get("id", ""))
        local_id = canonical_id.split(":", 1)[1] if ":" in canonical_id else path.stem
        date = fm.get("date")
        status = fm.get("status")
        owners.append(
            DecisionOwner(
                local_id=local_id,
                title=str(fm.get("title", "")),
                date=str(date) if date is not None else None,
                status=str(status) if status is not None else None,
                body=body.rstrip("\n"),
            )
        )
    return owners


def _natural_key(local_id: str) -> tuple[str, int, str]:
    """Natural sort: D1 < D2 < D10. Split into (alpha-prefix, first-int, suffix)."""
    i = 0
    while i < len(local_id) and not local_id[i].isdigit():
        i += 1
    prefix = local_id[:i]
    j = i
    while j < len(local_id) and local_id[j].isdigit():
        j += 1
    number = int(local_id[i:j]) if j > i else -1
    return (prefix, number, local_id[j:])


def render_decisions_view(owners: list[DecisionOwner]) -> str:
    ordered = sorted(owners, key=lambda o: _natural_key(o.local_id))
    parts: list[str] = [_GENERATED_BANNER, "", "# Decisions", ""]
    for o in ordered:
        parts.append(f"## {o.local_id}. {o.title}")
        parts.append("")
        if o.body:
            parts.append(o.body.rstrip())
            parts.append("")
        parts.append("---")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/graph/test_decision_log_render.py -q`
Expected: PASS (4 passed). If the round-trip test fails on a `date`/`status` mismatch, confirm `read_decision_owners` coerces YAML scalars to `str` (a YAML date scalar must become the original `"2026-03-31"` string — the explicit `str(date)` does this).

- [ ] **Step 5: Lint**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/graph/decision_log.py && uv run --frozen ruff format --check src/science_tool/graph/decision_log.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/graph/decision_log.py science/tests/graph/test_decision_log_render.py
git commit -m "feat(substrate-3c): decision owner renderer + generated view + round-trip"
```

---

## Task 5: executor decision-kind branch + `delete_cruft` exclusion

**Files:**
- Modify: `science/src/science_tool/graph/aggregate_retire.py`
- Test: `science/tests/graph/test_aggregate_retire_decisions.py` (create)

Context: the executor must govern `kind == "decision"` rows by the injected `DecisionLogIndex`, NOT by triage bucket — because the triage classifier sends any `migration:*` source to `CRUFT` before the decision-log rule, so real decisions (MM30 `D9`/`D10`) arrive bucketed `CRUFT`. A decision row is therefore intercepted before bucket dispatch: index hit → promote (owner content from `render_owner_file`); index miss → reject/retain. `delete_cruft` must never delete a decision row. New params default off so existing 3b callers/tests are unaffected.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/graph/test_aggregate_retire_decisions.py`:

```python
"""Phase 3c: decision-kind handling in the retirement executor."""

from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.aggregate_retire import _promote_target, apply_retirement, plan_retirement
from science_tool.graph.aggregate_triage import classify_aggregate_rows
from science_tool.graph.decision_log import DecisionLogIndex, DecisionSection
from science_tool.graph.sources import AggregateRowMeta, load_project_sources


def _project(tmp_path: Path, rows: list[dict], decisions_md: str | None = None) -> Path:
    (tmp_path / "science.yaml").write_text(
        "name: t\nprofile: research\nlayout_version: 3\nknowledge:\n  local_profile: local\n",
        encoding="utf-8",
    )
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    # `decision` is a builtin filename-policy kind but is NOT a graph-core kind in
    # 3c (it stays a local registry kind so MM30 keeps loading). Graph loading only
    # emits rows for registered kinds, so the fixture must declare `decision` in a
    # local manifest exactly as MM30 does — otherwise the rows are skipped pre-triage.
    (src / "manifest.yaml").write_text(
        "name: t-local\nimports:\n  - core\nstrictness: typed-extension\n"
        "entity_kinds:\n"
        "  - name: decision\n    canonical_prefix: decision\n    layer: layer/local\n"
        "    description: Project-local design decision.\n",
        encoding="utf-8",
    )
    (src / "entities.yaml").write_text(yaml.safe_dump({"entities": rows}), encoding="utf-8")
    if decisions_md is not None:
        (tmp_path / "core").mkdir()
        (tmp_path / "core" / "decisions.md").write_text(decisions_md, encoding="utf-8")
    return tmp_path


def _index(*locals_: str) -> DecisionLogIndex:
    return DecisionLogIndex(
        {
            f"decision:{lid}": DecisionSection(
                f"decision:{lid}", lid, f"Title {lid}", "2026-01-01", "active", f"Body {lid}.\n"
            )
            for lid in locals_
        }
    )


def test_migration_audit_decision_with_index_hit_is_promoted_not_deleted(tmp_path: Path):
    # D10: source_path migration:audit -> triage buckets it CRUFT, but it has a
    # real index section. It MUST be promoted, and delete_cruft must NOT delete it.
    proj = _project(
        tmp_path,
        [{"canonical_id": "decision:D10", "kind": "decision", "title": "D10", "source_path": "migration:audit"}],
    )
    sources = load_project_sources(proj, include_commons=False, strict_core_schema=False, strict_identity=False)
    rows = classify_aggregate_rows(sources)
    plan = plan_retirement(
        proj, sources, rows,
        promote_coined=False, delete_cruft=True, delete_shadow=False,
        promote_decisions=True, decision_index=_index("D10"),
    )
    report = apply_retirement(proj, plan, dry_run=False, decision_index=_index("D10"))
    assert "decision:D10" in report.promoted
    assert "decision:D10" not in report.deleted
    owner = proj / "entities" / "decision" / "D10.md"
    assert owner.is_file()
    assert "Body D10." in owner.read_text(encoding="utf-8")


def test_delete_cruft_never_deletes_decision_without_promote(tmp_path: Path):
    # delete_cruft alone (promote_decisions off) must still leave decision rows intact.
    proj = _project(
        tmp_path,
        [{"canonical_id": "decision:D10", "kind": "decision", "title": "D10", "source_path": "migration:audit"}],
    )
    sources = load_project_sources(proj, include_commons=False, strict_core_schema=False, strict_identity=False)
    rows = classify_aggregate_rows(sources)
    plan = plan_retirement(
        proj, sources, rows,
        promote_coined=False, delete_cruft=True, delete_shadow=False,
        promote_decisions=False, decision_index=DecisionLogIndex({}),
    )
    report = apply_retirement(proj, plan, dry_run=False, decision_index=DecisionLogIndex({}))
    assert "decision:D10" not in report.deleted
    assert "decision:D10" not in report.promoted
    # The entities.yaml row is retained.
    remaining = yaml.safe_load((proj / "knowledge/sources/local/entities.yaml").read_text())["entities"]
    assert any(r["canonical_id"] == "decision:D10" for r in remaining)


def test_index_miss_decision_is_rejected_and_retained(tmp_path: Path):
    proj = _project(
        tmp_path,
        [{"canonical_id": "decision:D2-treatment-response-category", "kind": "decision",
          "title": "D2 Treatment Response Category", "source_path": "migration:audit"}],
    )
    sources = load_project_sources(proj, include_commons=False, strict_core_schema=False, strict_identity=False)
    rows = classify_aggregate_rows(sources)
    plan = plan_retirement(
        proj, sources, rows,
        promote_coined=False, delete_cruft=True, delete_shadow=False,
        promote_decisions=True, decision_index=_index("D1"),  # no D2-... section
    )
    report = apply_retirement(proj, plan, dry_run=False, decision_index=_index("D1"))
    assert "decision:D2-treatment-response-category" not in report.promoted
    assert "decision:D2-treatment-response-category" not in report.deleted
    assert any(cid == "decision:D2-treatment-response-category" for cid, _ in report.rejected)


def test_core_decisions_sourced_decision_promotes(tmp_path: Path):
    proj = _project(
        tmp_path,
        [{"canonical_id": "decision:D1", "kind": "decision", "title": "D1. X", "source_path": "core/decisions.md"}],
    )
    sources = load_project_sources(proj, include_commons=False, strict_core_schema=False, strict_identity=False)
    rows = classify_aggregate_rows(sources)
    plan = plan_retirement(
        proj, sources, rows,
        promote_coined=False, delete_cruft=False, delete_shadow=False,
        promote_decisions=True, decision_index=_index("D1"),
    )
    report = apply_retirement(proj, plan, dry_run=False, decision_index=_index("D1"))
    assert report.promoted == ("decision:D1",)
    assert (proj / "entities" / "decision" / "D1.md").is_file()


def test_promote_decisions_off_leaves_decision_untouched(tmp_path: Path):
    # 3b parity: with no decision flag, decision rows are neither promoted nor deleted.
    proj = _project(
        tmp_path,
        [{"canonical_id": "decision:D1", "kind": "decision", "title": "D1. X", "source_path": "core/decisions.md"}],
    )
    sources = load_project_sources(proj, include_commons=False, strict_core_schema=False, strict_identity=False)
    rows = classify_aggregate_rows(sources)
    plan = plan_retirement(
        proj, sources, rows,
        promote_coined=False, delete_cruft=False, delete_shadow=False,
    )  # new params default off
    report = apply_retirement(proj, plan, dry_run=False)  # decision_index defaults to empty
    assert report.promoted == ()
    assert report.deleted == ()


def _meta(canonical_id: str) -> AggregateRowMeta:
    return AggregateRowMeta(
        path="knowledge/sources/local/entities.yaml",
        line=0,
        canonical_id=canonical_id,
        kind="decision",
        source_path="migration:audit",
    )


def test_promote_target_resolves_verbatim_and_blocks_traversal(tmp_path: Path):
    # Directly exercise the path-safety belt: `_is_safe_slug` is lowercase-only, so
    # the helper must special-case verbatim. D10 resolves; `D..x` is blocked by `..`.
    (tmp_path / "science.yaml").write_text(
        "name: t\nprofile: research\nlayout_version: 3\nknowledge:\n  local_profile: local\n",
        encoding="utf-8",
    )
    target, reason = _promote_target(_meta("decision:D10"), tmp_path)
    assert target == "entities/decision/D10.md"
    assert reason is None
    bad_target, bad_reason = _promote_target(_meta("decision:D..x"), tmp_path)
    assert bad_target is None
    assert bad_reason is not None and "unsafe" in bad_reason
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/graph/test_aggregate_retire_decisions.py -q`
Expected: FAIL — `plan_retirement()` got an unexpected keyword argument `promote_decisions`.

- [ ] **Step 3: Extract a shared promote-target resolver**

In `science/src/science_tool/graph/aggregate_retire.py`, add imports near the top (after the existing `from science_tool.entities import ...`):

```python
from science_tool.graph.decision_log import DecisionLogIndex, render_owner_file
```

Add a module-level helper after `_real_owner_path` (around line 67):

```python
def _promote_target(meta: "AggregateRowMeta", project_root: Path) -> tuple[str | None, str | None]:
    """Resolve an id-preserving promote target, or (None, reject_reason).

    Conformance ALWAYS runs (3b is id-preserving; a non-conforming id is
    rejected, never renumbered). The `_is_safe_slug` belt blocks `..`/slashes.
    """
    kind = meta.kind
    local_part = meta.canonical_id.split(":", 1)[1] if ":" in meta.canonical_id else meta.canonical_id
    try:
        policy = resolve_path_policy(kind, project_root=project_root)
    except EntityCommandError:
        return None, f"no path policy for kind {kind!r}"
    if not local_part_conforms(kind, local_part, project_root=project_root):
        return None, f"id {meta.canonical_id!r} does not conform to {policy.strategy} strategy"
    # Path-safety belt, policy-aware. `_is_safe_slug` is lowercase-only and would
    # reject a verbatim id like `D10`. For verbatim, conformance (`_VERBATIM_RE`)
    # already excludes path separators and `..`; keep the explicit check as a
    # cheap second belt. Other strategies keep the lowercase slug firewall.
    if policy.strategy == "verbatim":
        safe = ".." not in local_part
    else:
        safe = _is_safe_slug(local_part)
    if not safe:
        return None, "unsafe local part"
    return (policy.root / f"{local_part}.md").as_posix(), None
```

Add the `AggregateRowMeta` import to the `TYPE_CHECKING` block:

```python
if TYPE_CHECKING:
    from science_tool.graph.sources import AggregateRowMeta, ProjectSources
```

- [ ] **Step 4: Add `promote_decisions`/`decision_index` params + the decision branch to `plan_retirement`**

Change the signature (currently lines 70-78) to add two keyword params with off-by-default values:

```python
def plan_retirement(
    project_root: Path,
    sources: "ProjectSources",
    rows: list[AggregateRowTriage],
    *,
    promote_coined: bool,
    delete_cruft: bool,
    delete_shadow: bool,
    promote_decisions: bool = False,
    decision_index: DecisionLogIndex | None = None,
) -> RetirementPlan:
```

At the top of the function body (after `triage_by_id = ...`), normalize the index:

```python
    idx = decision_index if decision_index is not None else DecisionLogIndex({})
```

Inside the `for meta in sources.aggregate_rows:` loop, immediately after the firewall + `triage = triage_by_id.get(...)` / `if triage is None: continue` block (i.e. before the SHADOW-reconcile block at the current line 97), insert the decision-kind interception:

```python
        # Decision rows are governed by the injected index, NOT the bucket. The
        # triage classifier sends migration:* sources to CRUFT before the
        # decision-log rule, so real decisions (e.g. D9/D10) arrive bucketed
        # CRUFT — they must promote on an index hit and never be cruft-deleted.
        if meta.kind == "decision":
            if not promote_decisions:
                continue  # untouched (3b parity); delete_cruft never reaches here
            if idx.get(meta.canonical_id) is None:
                rejected.append((triage, f"no decision-log section for {meta.canonical_id}"))
                continue
            target, reason = _promote_target(meta, project_root)
            if target is None:
                rejected.append((triage, reason or "unpromotable"))
                continue
            promote.append(PlannedRow(triage, RetireAction.PROMOTE, meta.path, meta.line, target))
            continue
```

Then refactor the existing coined PROMOTE block (current lines 107-125) to use the shared helper:

```python
        # PROMOTE: resolve an id-preserving, conforming, safe target.
        target, reason = _promote_target(meta, project_root)
        if target is None:
            rejected.append((triage, reason or "unpromotable"))
            continue
        promote.append(PlannedRow(triage, action, meta.path, meta.line, target))
```

- [ ] **Step 5: Add `decision_index` to `apply_retirement` and use section content for decision owners**

Change the `apply_retirement` signature (line 175):

```python
def apply_retirement(
    project_root: Path,
    plan: RetirementPlan,
    *,
    dry_run: bool,
    decision_index: DecisionLogIndex | None = None,
) -> RetirementReport:
```

At the top of the body add:

```python
    idx = decision_index if decision_index is not None else DecisionLogIndex({})
```

In the promote loop (the `if not dry_run:` write at lines 205-207), branch the owner text on decision kind:

```python
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            if pr.triage.kind == "decision":
                section = idx.get(pr.triage.canonical_id)
                if section is None:
                    # Planner guaranteed a hit; be explicit rather than write a bad owner.
                    rejected.append((pr.triage.canonical_id, "decision section missing at apply time"))
                    continue
                text = render_owner_file(section, promoted_from=pr.source_path)
            else:
                text = _owner_text(entry, promoted_from=pr.source_path)
            target.write_text(text, encoding="utf-8")
        promoted.append(pr.triage.canonical_id)
        drop_by_file[pr.source_path].add(pr.line)
```

Note: the existing `_REQUIRED_FIELDS` check on `entry` runs before this block and still applies (a decision aggregate row carries `canonical_id`/`kind`/`title`). The owner *content* for a decision comes from the section, not `entry`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/graph/test_aggregate_retire_decisions.py -q`
Expected: PASS (5 passed).

- [ ] **Step 7: Run the full 3b executor regression (no behavior change off-flag)**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/graph/test_aggregate_retire_plan.py tests/graph/test_aggregate_retire_apply.py tests/graph/test_aggregate_retire_roundtrip.py -q && uv run --frozen ruff check src/science_tool/graph/aggregate_retire.py && uv run --frozen ruff format --check src/science_tool/graph/aggregate_retire.py`
Expected: PASS — the new params default off, so all 3b tests stay green.

- [ ] **Step 8: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/graph/aggregate_retire.py science/tests/graph/test_aggregate_retire_decisions.py
git commit -m "feat(substrate-3c): executor decision-kind branch governed by injected index; delete_cruft never deletes a decision"
```

---

## Task 6: CLI — `--promote-decisions` + `entities generate-decisions`

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_cli_entities_decisions.py` (create)

Context: extend `entities triage-aggregate` with `--promote-decisions` (parses `core/decisions.md` into a `DecisionLogIndex` and injects it into plan/apply; still v3-gated by the existing block). Add a new `entities generate-decisions` command that renders `core/decisions.md` from `entities/decision/*.md`, dry-run by default with `--write` to apply, also v3-gated.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_cli_entities_decisions.py`:

```python
"""Phase 3c: CLI surface for decision promotion + the generated view."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.graph.decision_log import DecisionSection, render_owner_file

_LOCAL_MANIFEST = (
    "name: t-local\nimports:\n  - core\nstrictness: typed-extension\n"
    "entity_kinds:\n"
    "  - name: decision\n    canonical_prefix: decision\n    layer: layer/local\n"
    "    description: Project-local design decision.\n"
)


def _v3_project(tmp_path: Path, rows: list[dict], decisions_md: str) -> Path:
    (tmp_path / "science.yaml").write_text(
        "name: t\nprofile: research\nlayout_version: 3\nknowledge:\n  local_profile: local\n",
        encoding="utf-8",
    )
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    # decision is a local registry kind in 3c — declare it so rows load (see Task 5).
    (src / "manifest.yaml").write_text(_LOCAL_MANIFEST, encoding="utf-8")
    (src / "entities.yaml").write_text(yaml.safe_dump({"entities": rows}), encoding="utf-8")
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "decisions.md").write_text(decisions_md, encoding="utf-8")
    return tmp_path


def test_promote_decisions_apply_promotes_on_v3(tmp_path: Path):
    proj = _v3_project(
        tmp_path,
        [{"canonical_id": "decision:D1", "kind": "decision", "title": "D1. X", "source_path": "core/decisions.md"}],
        "# Decisions\n\n## D1. X (2026-03-31)\n\n**Date**: 2026-03-31\n**Status**: active\n\nWhy.\n",
    )
    res = CliRunner().invoke(
        main,
        ["entities", "triage-aggregate", "--project-root", str(proj),
         "--promote-decisions", "--apply", "--format", "json"],
    )
    assert res.exit_code == 0, res.output
    import json
    payload = json.loads(res.output)
    assert "decision:D1" in payload["promoted"]
    assert (proj / "entities" / "decision" / "D1.md").is_file()


def test_promote_decisions_apply_refused_on_v2(tmp_path: Path):
    proj = _v3_project(
        tmp_path,
        [{"canonical_id": "decision:D1", "kind": "decision", "title": "D1", "source_path": "core/decisions.md"}],
        "# Decisions\n\n## D1. X\n\nWhy.\n",
    )
    (proj / "science.yaml").write_text(
        "name: t\nprofile: research\nlayout_version: 2\nknowledge:\n  local_profile: local\n",
        encoding="utf-8",
    )
    res = CliRunner().invoke(
        main,
        ["entities", "triage-aggregate", "--project-root", str(proj), "--promote-decisions", "--apply"],
    )
    assert res.exit_code == 1
    assert "layout_version" in res.output


def test_generate_decisions_write(tmp_path: Path):
    (tmp_path / "science.yaml").write_text(
        "name: t\nprofile: research\nlayout_version: 3\nknowledge:\n  local_profile: local\n",
        encoding="utf-8",
    )
    d = tmp_path / "entities" / "decision"
    d.mkdir(parents=True)
    (d / "D1.md").write_text(
        render_owner_file(DecisionSection("decision:D1", "D1", "First", "2026-01-01", "active", "Why.\n"),
                          promoted_from="x"),
        encoding="utf-8",
    )
    res = CliRunner().invoke(
        main, ["entities", "generate-decisions", "--project-root", str(tmp_path), "--write"]
    )
    assert res.exit_code == 0, res.output
    out = (tmp_path / "core" / "decisions.md").read_text(encoding="utf-8")
    assert out.startswith("<!-- GENERATED")
    assert "## D1. First" in out


def test_generate_decisions_dry_run_does_not_write(tmp_path: Path):
    (tmp_path / "science.yaml").write_text(
        "name: t\nprofile: research\nlayout_version: 3\nknowledge:\n  local_profile: local\n",
        encoding="utf-8",
    )
    d = tmp_path / "entities" / "decision"
    d.mkdir(parents=True)
    (d / "D1.md").write_text(
        render_owner_file(DecisionSection("decision:D1", "D1", "First", None, None, "Why.\n"), promoted_from="x"),
        encoding="utf-8",
    )
    res = CliRunner().invoke(
        main, ["entities", "generate-decisions", "--project-root", str(tmp_path)]
    )
    assert res.exit_code == 0, res.output
    assert "## D1. First" in res.output
    assert not (tmp_path / "core" / "decisions.md").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_cli_entities_decisions.py -q`
Expected: FAIL — `--promote-decisions` is an unknown option and `generate-decisions` is not a command.

- [ ] **Step 3: Add `--promote-decisions` to `triage-aggregate`**

In `science/src/science_tool/cli.py`, add the option (after the `--delete-shadow` option, line 303) and the parameter:

```python
@click.option("--delete-shadow", is_flag=True, help="Delete `shadow` rows (id already has a real owner).")
@click.option("--promote-decisions", is_flag=True, help="Promote `decision` rows backed by core/decisions.md.")
@click.option("--apply", "apply_changes", is_flag=True, help="Execute the plan (default: dry-run).")
def entities_triage_aggregate_command(
    project_root: Path,
    output_format: str,
    promote_coined: bool,
    delete_cruft: bool,
    delete_shadow: bool,
    promote_decisions: bool,
    apply_changes: bool,
) -> None:
```

Update the imports inside the function and the `any_bucket` line:

```python
    from science_tool.graph.aggregate_retire import apply_retirement, plan_retirement
    from science_tool.graph.aggregate_triage import classify_aggregate_rows
    from science_tool.graph.decision_log import DecisionLogIndex, parse_decision_log
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(project_root, include_commons=False, strict_core_schema=False, strict_identity=False)
    rows = classify_aggregate_rows(sources)
    any_bucket = promote_coined or delete_cruft or delete_shadow or promote_decisions
```

Update the `--apply requires...` UsageError message to mention the new flag:

```python
        if apply_changes:
            raise click.UsageError(
                "--apply requires at least one of "
                "--promote-coined/--delete-cruft/--delete-shadow/--promote-decisions."
            )
```

Build the index and pass it to both calls (replace the `plan = plan_retirement(...)` / `report = apply_retirement(...)` block at lines 369-377):

```python
    decisions_path = project_root / "core" / "decisions.md"
    decision_index = (
        parse_decision_log(decisions_path.read_text(encoding="utf-8"))
        if promote_decisions and decisions_path.is_file()
        else DecisionLogIndex({})
    )
    plan = plan_retirement(
        project_root,
        sources,
        rows,
        promote_coined=promote_coined,
        delete_cruft=delete_cruft,
        delete_shadow=delete_shadow,
        promote_decisions=promote_decisions,
        decision_index=decision_index,
    )
    report = apply_retirement(project_root, plan, dry_run=not apply_changes, decision_index=decision_index)
```

- [ ] **Step 4: Add the `generate-decisions` command**

In `science/src/science_tool/cli.py`, add after `entities_triage_aggregate_command` (before `@entities_group.command("register-kind")` at line 406):

```python
@entities_group.command("generate-decisions")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--write", "write_changes", is_flag=True, help="Write core/decisions.md (default: print).")
def entities_generate_decisions_command(project_root: Path, write_changes: bool) -> None:
    """Render core/decisions.md from entities/decision/*.md (generated view, §B5)."""
    import yaml as _yaml

    from science_tool.graph.decision_log import (
        DECISIONS_REL,
        read_decision_owners,
        render_decisions_view,
    )

    _manifest = _yaml.safe_load((project_root / "science.yaml").read_text(encoding="utf-8")) or {}
    _v = _manifest.get("layout_version")
    version = _v if isinstance(_v, int) else None
    if version is None or version < 3:
        raise click.ClickException(
            f"generate-decisions needs an `entities/decision/` owner root; this project is "
            f"layout_version {version} — complete the v2->v3 migration first."
        )

    owners = read_decision_owners(project_root / "entities" / "decision")
    rendered = render_decisions_view(owners)
    if write_changes:
        out = project_root / DECISIONS_REL
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
        click.echo(f"wrote {DECISIONS_REL} ({len(owners)} decisions)")
    else:
        click.echo(rendered)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_cli_entities_decisions.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Run the 3b CLI regression + lint**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_cli_entities_triage_aggregate.py -q && uv run --frozen ruff check src/science_tool/cli.py && uv run --frozen ruff format --check src/science_tool/cli.py`
Expected: PASS — the no-flag 3a/3b path is unchanged; new option defaults off.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/cli.py science/tests/test_cli_entities_decisions.py
git commit -m "feat(substrate-3c): --promote-decisions flag + entities generate-decisions command"
```

---

## Final verification (after all tasks)

- [ ] **Full suite**

Run: `cd ~/d/science/science && uv run --frozen pytest -q`
Expected: exit 0.

- [ ] **Lint (touched files only — the repo carries a pre-existing baseline in untouched files)**

Run:
```bash
cd ~/d/science/science
FILES="src/science_tool/entities.py src/science_tool/entity_layout_migration.py \
src/science_tool/graph/decision_log.py src/science_tool/graph/aggregate_retire.py \
src/science_tool/cli.py tests/test_verbatim_strategy.py tests/graph/test_decision_log_parse.py \
tests/graph/test_decision_log_render.py tests/graph/test_aggregate_retire_decisions.py \
tests/test_cli_entities_decisions.py"
uv run --frozen ruff check $FILES && uv run --frozen ruff format --check $FILES
```
Expected: clean (zero errors on 3c-touched files).

- [ ] **Confirm no net-new baseline errors**

Run: `cd ~/d/science/science && uv run --frozen ruff check . 2>/dev/null | tail -1`
Expected: the total error count equals the pre-3c baseline (record the count on `main` first via `git stash` if needed). 3c must add zero new errors; do **not** treat a nonzero total as a failure — only a *change* from baseline is a regression.

- [ ] **Live MM30 dry-run smoke (read-only; MM30 is v2 so --apply must refuse)**

Run (from MM30): `cd ~/d/cancer/cancer-types/multiple-myeloma && uv run --frozen science entities triage-aggregate --project-root . --promote-decisions --apply 2>&1 | tail -3`
Expected: exit 1 with a `layout_version 2` message — `--apply` is v3-gated; MM30 stays git-clean. (A `--promote-decisions` dry-run without `--apply` is also safe to inspect.)

---

## Notes for the executor

- **Two registries, deliberately split.** `decision` is registered as a builtin *filename-policy* kind in `entities.py` (Task 1) — required because `verbatim` is builtin-only and a project cannot declare it in a local manifest. It is **intentionally NOT added to the graph `EntityRegistry` core kinds.** MM30's local manifest declares `decision`, and `register_extension_kind` raises `EntityKindShadowError` on a core collision (`entity_registry.py`), so core-registering `decision` now would break MM30 graph loading. Consequently: (a) graph-loading fixtures (Tasks 5–6) declare `decision` in a local `manifest.yaml`, exactly as MM30 does; (b) the migrator (Task 2) needs no manifest — it discovers kinds via the filename-policy table (`markdown_entity_kinds`), not the graph registry. Full graph-core registration + `register_extension_kind` shadow handling + MM30 manifest cleanup is **deferred to the v3 cutover (project Task #30)**.
- New executor params (`promote_decisions`, `decision_index`) default off/empty so every existing 3b test and call site stays green without edits.
- The dependency direction is `aggregate_retire.py → decision_log.py` only; `decision_log.py` imports nothing from `aggregate_retire.py` (keep it that way).
- `verbatim` is builtin-only: do **not** add it to `_VALID_STRATEGIES`.
- Decisions are governed by `kind == "decision"`, never by the triage bucket label — a `migration:*`-sourced decision is bucketed `CRUFT` but must promote on an index hit and is never cruft-deleted.
- Round-trip fidelity is a **semantic** assertion (`parse(original).sections == parse(rendered).sections`), never whole-file equality — the regenerated banner differs from the original header by design.
