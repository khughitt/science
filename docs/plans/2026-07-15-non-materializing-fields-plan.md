# Non-materializing frontmatter fields — implementation plan (fb-2026-07-11-017)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flag, as an unconditional ERROR, a top-level `supersedes:`/`amends:` frontmatter key that materializes no graph triples — except where a kind legitimately reads it.

**Architecture:** One new canonical validate check, `check_non_materializing_fields`, that mirrors `status_vocabulary.py`: iterate entity markdown under `entities/`, read each file's frontmatter, and yield a `Result` when a non-materializing relation key is present on a kind that has no semantic top-level reader for it. Legitimacy is a small explicit `(kind, key)` set, because it is a behavioral fact (a live consumer) that no kind descriptor declares.

**Tech Stack:** Python 3.13, pytest. Package root is `science/` — **there is no root `pyproject.toml`**.

**Design:** [`2026-07-15-non-materializing-fields-design.md`](2026-07-15-non-materializing-fields-design.md)

## Global Constraints

- **Always `cd science/` before any `uv run`.** Running from the repo root is the most common orientation mistake here.
- Validation from `science/`: `uv run --frozen pytest`; `uv run ruff check`; `uv run pyright`. Default pytest excludes `snapshot`/`real_projects` markers.
- Pyright is configured once at the repo root (`pyrightconfig.json`); **test directories are not type-checked**. Ruff is per-package — run it from `science/`.
- **Severity is unconditional ERROR, NOT routed through `kind_severity.severity_for_kind`.** This rule judges whether authored information has any effect at all, not whether a kind's vocabulary is certified.
- **Trigger on key PRESENCE, not value.** `supersedes: null` and `supersedes: []` are findings. Detect with `key in fm`, never `fm.get(key)`.
- **The legit-reader exception is `(kind, key)`-PAIR-specific**, currently `{("workflow-run", "supersedes")}`. `amends` on `workflow-run` is still an ERROR.
- The fix-suggestion message uses the current relation field name **`target`** (schema requires `["predicate", "target"]`); the withdrawn plan's `object:` is stale. The example is **schematic** (`<target-id>`) — never echo the authored value or assume the target's kind.
- No AI-attribution trailers on commits. No "legacy"/"compat" layers. No `Unified` prefix. Composition over inheritance; explicit over defensive; fail early.
- Branch: `fb017-non-materializing-fields`, in the worktree `~/d/science/.claude/worktrees/instrument-result`. **Do not `cd` to the main checkout.**

---

## Task 1: The `check_non_materializing_fields` validate check

**Files:**
- Create: `science/src/science_tool/validate/checks/materialization.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py` (append `"materialization"` to `CANONICAL_CHECK_MODULES`)
- Test: `science/tests/validate/test_checks_materialization.py`

**Interfaces:**
- Consumes:
  - `Check(section: str, order: int)` decorator and `ValidateContext` — from `science_tool.validate.checks` / `science_tool.validate.context`.
  - `ValidateContext.project_root: Path` and `ValidateContext.frontmatter(path: Path) -> dict[str, Any]`.
  - `iter_entity_markdown(entities_root: Path) -> Iterator[Path]` — from `science_tool.entity_scan`; yields `*.md` Paths, skipping `_`-prefixed segments; missing root yields nothing.
  - `Result(severity, path, line, message, rule, task)` and `Severity.ERROR` — from `science_tool.validate.result`. **`Result` has no entity-id field**, so the id lives in `message`.
- Produces: `check_non_materializing_fields(ctx: ValidateContext) -> Iterator[Result]`, registered under module name `"materialization"`, emitting rule `"non-materializing-field"` at `Severity.ERROR`.

**Registry note.** `tests/test_check_registry_is_complete.py::test_EVERY_check_module_on_disk_is_REGISTERED` compares the checks directory on disk to `CANONICAL_CHECK_MODULES`. Creating `materialization.py` **without** listing it fails that guard — so the create and the tuple edit land together in this task.

- [ ] **Step 1: Write the failing test file**

Create `science/tests/validate/test_checks_materialization.py`:

```python
"""A top-level frontmatter field that materializes no triples is an ERROR (fb-2026-07-11-017).

The graph reads supersession/amendment from a `relations:` entry with the predicate, never
from a top-level `supersedes:`/`amends:` key. Such a key looks authoritative and produces
ZERO triples, silently -- and big-picture then derives a wrong `provenance_coverage`.

`workflow-run.supersedes` is the ONE legitimate top-level use (read by qa_audit/runs.py:47),
so the exception is that exact (kind, key) PAIR -- not a blanket pass for the kind.
"""

from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.materialization import check_non_materializing_fields
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _entity(root: Path, rel: str, *, entity_id: str, kind: str, extra: str) -> None:
    """Seed one entity markdown file. `extra` is raw frontmatter lines (already newline-terminated)."""
    path = root / "entities" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\nid: "{entity_id}"\nkind: {kind}\ntitle: "T"\nstatus: "active"\n{extra}---\n\nBody.\n',
        encoding="utf-8",
    )


def _results(root: Path) -> list:
    (root / "science.yaml").write_text("name: fixture\nprofile: research\n", encoding="utf-8")
    ctx = ValidateContext.from_project_root(root, strict=False, verbose=False)
    return list(check_non_materializing_fields(ctx))


def test_top_level_supersedes_on_interpretation_is_an_error(tmp_path: Path) -> None:
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="supersedes: interpretation:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    msg = results[0].message
    # every required element (design §2)
    assert "interpretation:0001-x" in msg     # the entity id
    assert "supersedes" in msg                # the key
    assert "relations:" in msg                # the replacement form
    assert "sci:supersedes" in msg            # the predicate
    assert results[0].rule == "non-materializing-field"


def test_top_level_amends_on_interpretation_is_an_error(tmp_path: Path) -> None:
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="amends: interpretation:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "interpretation:0001-x" in results[0].message
    assert "sci:amends" in results[0].message


def test_relations_form_is_accepted(tmp_path: Path) -> None:
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="relations:\n  - predicate: sci:supersedes\n    target: interpretation:0000-y\n",
    )
    assert _results(tmp_path) == []


def test_supersedes_on_workflow_run_is_accepted(tmp_path: Path) -> None:
    """The (workflow-run, supersedes) pair is a REAL field read by qa_audit/runs.py:47."""
    _entity(
        tmp_path, "workflow-runs/0001-x.md",
        entity_id="workflow-run:0001-x", kind="workflow-run",
        extra="supersedes: workflow-run:0000-y\n",
    )
    assert _results(tmp_path) == []


def test_amends_on_workflow_run_is_an_error(tmp_path: Path) -> None:
    """The exclusion is PAIR-specific: workflow-run does not get a blanket pass."""
    _entity(
        tmp_path, "workflow-runs/0001-x.md",
        entity_id="workflow-run:0001-x", kind="workflow-run",
        extra="amends: workflow-run:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "sci:amends" in results[0].message


def test_null_valued_supersedes_is_an_error(tmp_path: Path) -> None:
    """Guards against `fm.get(key) is None`-style detection: presence is the defect, not value."""
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="supersedes: null\n",
    )
    assert [r.severity for r in _results(tmp_path)] == [Severity.ERROR]


def test_empty_list_supersedes_is_an_error(tmp_path: Path) -> None:
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="supersedes: []\n",
    )
    assert [r.severity for r in _results(tmp_path)] == [Severity.ERROR]


def test_clean_entity_yields_nothing(tmp_path: Path) -> None:
    """Non-vacuity guard: with no offending key, the check is silent -- so the ERROR cases
    prove it can fire, not that it fires on everything."""
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="",
    )
    assert _results(tmp_path) == []
```

- [ ] **Step 2: Run the test — expect FAIL (module missing)**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_materialization.py -q`
Expected: collection error / `ModuleNotFoundError: ...checks.materialization`.

- [ ] **Step 3: Implement the check**

Create `science/src/science_tool/validate/checks/materialization.py`:

```python
"""A frontmatter field that materializes NOTHING is an error (fb-2026-07-11-017).

The graph's source of truth for a supersession/amendment edge is a `relations:` entry with
the corresponding predicate (`profiles/core.py` RelationKind descriptors; `consolidation.py`
for supersession). A TOP-LEVEL `supersedes:`/`amends:` key looks authoritative but produces
ZERO triples, silently -- and big-picture then derives a wrong `provenance_coverage` from the
missing chains. A pure no-op field is worse than a wrong one: nothing surfaces at all.

Severity is an unconditional ERROR, NOT routed through `kind_severity`: this rule judges
whether authored information has ANY effect, not whether a kind's status/verdict vocabulary
is certified.

Kind-awareness is a small explicit legit-reader set, not a schema derivation. `workflow-run`
carries a real top-level `supersedes` field ONLY because `qa_audit/runs.py:47` reads it for
the QA-audit chain -- a behavioral fact no kind descriptor declares, so it cannot be derived
from the D5 schema, and deriving from the schema would falsely flag it. Note `entities.py`
lists `supersedes` in `_REMOVABLE_FRONTMATTER_REF_KEYS`, but that is generic entity-deletion
reference cleanup with no supersession semantics and no emitted edge; it does not legitimize
the key as lineage authoring on other kinds.
"""

from __future__ import annotations

from collections.abc import Iterator

from science_tool.entity_scan import iter_entity_markdown
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

#: Top-level frontmatter keys that materialize NOTHING and must be authored as a
#: ``relations:`` entry with the given predicate instead.
_NON_MATERIALIZING: dict[str, str] = {
    "supersedes": "sci:supersedes",
    "amends": "sci:amends",
}

#: ``(kind, key)`` pairs where a top-level key IS a real field with a live domain consumer,
#: so it must NOT be flagged. Behavioral fact (a reader), not a schema declaration -- which
#: is exactly why it can't be derived from the kind descriptor.
_LEGIT_TOP_LEVEL: frozenset[tuple[str, str]] = frozenset(
    {
        ("workflow-run", "supersedes"),  # read by qa_audit/runs.py:47 for the QA-audit chain
    }
)


@Check(section="non-materializing frontmatter fields", order=23)
def check_non_materializing_fields(ctx: ValidateContext) -> Iterator[Result]:
    entities_root = ctx.project_root / "entities"
    if not entities_root.is_dir():
        return

    for path in iter_entity_markdown(entities_root):
        fm = ctx.frontmatter(path)
        kind = fm.get("kind")
        entity_id = fm.get("id") or path.name
        for key, predicate in _NON_MATERIALIZING.items():
            if key not in fm:  # PRESENCE, not value -- null/[] are still findings
                continue
            if (kind, key) in _LEGIT_TOP_LEVEL:
                continue
            yield Result(
                Severity.ERROR,
                path,
                None,
                (
                    f"{entity_id}: top-level '{key}:' materializes no triples and is "
                    f"silently ignored by the graph. Author it as a relations: entry with "
                    f"'predicate: {predicate}' and a 'target: <target-id>' instead."
                ),
                "non-materializing-field",
                None,
            )
```

- [ ] **Step 4: Register the check**

In `science/src/science_tool/validate/checks/__init__.py`, append `"materialization"` to the end of the `CANONICAL_CHECK_MODULES` tuple (after `"supersession"`):

```python
    "relations",
    "supersession",
    "materialization",
)
```

- [ ] **Step 5: Run the check's tests — expect PASS**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_materialization.py -q`
Expected: 8 passed.

- [ ] **Step 6: Run the registry guard — expect PASS**

Run: `cd science && uv run --frozen pytest tests/test_check_registry_is_complete.py -q`
Expected: PASS — the new module is on disk **and** listed. (If it fails with `unregistered: ['materialization']`, Step 4 was missed.)

- [ ] **Step 7: Full gates**

Run: `cd science && uv run --frozen pytest -q && uv run ruff check && uv run pyright`
Expected: all green. The check adds one rule (`non-materializing-field`) that fires on no in-repo fixture, so no existing test should change. If any pre-existing fixture trips, that is a **finding** — migrate the offending entity to the `relations:` form; do not soften the check.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/validate/checks/materialization.py \
        science/src/science_tool/validate/checks/__init__.py \
        science/tests/validate/test_checks_materialization.py
git commit -m "feat(validate): error on frontmatter fields that materialize no triples

A top-level supersedes:/amends: key is a pure no-op -- the graph reads a
relations: entry with the predicate. MM30 authored two interpretations in the
top-level form and got zero triples, no warning, and a wrong provenance_coverage
downstream. The exception is the (workflow-run, supersedes) pair alone, which
qa_audit/runs.py reads as the QA-audit chain. Unconditional ERROR: the rule
judges whether authored information has any effect (fb-2026-07-11-017)."
```

---

## Task 2: Close the feedback item

fb-2026-07-11-017 is tracked in the design/plan docs, not a self-hosted `science tasks` backlog (this repo has none). Closing it is a documentation act.

**Files:**
- Modify: `docs/plans/2026-07-15-non-materializing-fields-design.md` (status line)

- [ ] **Step 1:** Change the design doc's `**Status:**` line to note the check shipped and the branch, e.g. `**Status:** SHIPPED on branch fb017-non-materializing-fields (not merged). fb-2026-07-11-017 addressed.`
- [ ] **Step 2: Commit**

```bash
git add docs/plans/2026-07-15-non-materializing-fields-design.md
git commit -m "docs(validate): mark fb-2026-07-11-017 addressed by the non-materializing-field check"
```

---

## Self-review

- **Spec coverage:** design §2 (the check) → Task 1 Steps 3–4; §2 message contract → Step 1 test `test_top_level_supersedes...` asserts id/key/`relations:`/predicate; §2 trigger-on-presence → `test_null_valued...`, `test_empty_list...` + `key in fm`; §3 kind-awareness legit set → `_LEGIT_TOP_LEVEL` + `test_supersedes_on_workflow_run...`; §3 pair-specificity → `test_amends_on_workflow_run_is_an_error`; §4 unconditional ERROR → `Severity.ERROR` literal (no `kind_severity` import) + every test asserts `Severity.ERROR`; §5 rollout / clean in-repo scan → Step 7 note; §6 testing matrix → Step 1 (all seven rows + non-vacuity guard); §7 files → Task 1 Files.
- **Placeholder scan:** none — every code step carries complete code; the message string is identical in the test asserts (substrings) and the implementation.
- **Type consistency:** `check_non_materializing_fields(ctx) -> Iterator[Result]`; `Result(Severity.ERROR, path, None, message, "non-materializing-field", None)` matches the `Result(severity, path, line, message, rule, task)` dataclass; `_LEGIT_TOP_LEVEL` and `_NON_MATERIALIZING` names are used identically in the Interfaces block, the implementation, and the design.
- **One known trap:** the registry guard (Task 1 Step 6) — creating the module without listing it fails `test_EVERY_check_module_on_disk_is_REGISTERED`. Steps 4 and 6 cover it.
