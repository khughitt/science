# Autonomy Path Gate (Plan C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship §4 (the default-deny path gate) and Layer 3 (the one-way perturbation
alarm) of [`2026-07-24-autonomy-envelope-design.md`](2026-07-24-autonomy-envelope-design.md),
so an autonomous run's write surface is decidable from a `base..head` commit range
before Plan D wires the supervisor around it.

**Architecture:** A new `science_tool.autonomy` package with four modules that form a
one-way pipeline: `policy.py` (frozen allowlists, no I/O) → `changes.py` (change-set
model + path→kind classification) → `extract.py` (git range → change set) →
`path_gate.py` (change set → verdict). A `science autonomy path-gate` CLI drives the
pipeline. Layer 3 is a *test* module, not shipped code: it perturbs each allowlisted
field through a real materialized project and asserts the belief basis does not move.

**Tech Stack:** Python 3.11+ (`requires-python = ">=3.11"` in all three packages;
pyright targets `3.11`), pydantic v2, click, PyYAML, rdflib (via existing graph code),
`git` via `subprocess`. No new dependencies.

## What this plan does NOT ship

Named here so no task invents them:

- **No supervisor, no lifecycle, no quarantine, no `science feedback` filing.** Plan D.
- **No `science validate` check.** Plan D (design §6).
- **No run-record writer.** Plan B shipped the reader; Plan D writes.
- **No attestation that a run's `autonomous_run` values are its own.** Explicitly
  deferred to Plan D by Plan B's design-doc note.
- **No structured-source or non-markdown entity gating.** See "The `task` finding" below.

## Grounding this plan rests on

Verified in the tree at `b0c6dfa7`. An implementer does **not** need to re-verify these,
but must not contradict them.

- **The belief basis is `EntityBasis(entity_id, uri, target_uris, unit_keys, policy_id,
  policy_version)`** — `science/src/science_tool/graph/belief_basis.py:49-60`.
  `capture_basis` (`:62`) enumerates every typed project entity in `graph/knowledge`,
  expands targets with `_evidence_targets_for_uri`, and collects units with
  `collect_evidence_units`. `compare_bases` (`:174`) reports deltas for **pre-existing**
  entities only.
- **Evidence units are read from cito edges whose subject is an `EvidenceLine`**
  (`graph/belief.py:123-158`), with per-line metadata (`strength`, `evidence_role`,
  `evidence_type`, `confidence`, `qa_failed_datasets`, independence) read from
  `graph/provenance`, and polarity read off the target. **A field reaches the belief
  basis only by changing a cito edge, an `rdf:type`, an evidence-line's provenance
  metadata, a target's polarity, or the target closure.**
- **`paper`/`book` materialize a thin bibliographic surface into `graph/knowledge`** —
  `graph/materialize.py:700-710`: `year` → `dcterms:date`, `doi` → `sci:doi`,
  `url` → `dcat:downloadURL`. No other bibliographic field of any kind materializes at
  all (`venue`, `pmid`, `publisher`, `isbn`, `duration_minutes` produce no triple).
- **`Entity.aliases` feeds reference resolution** — `graph/sources.py:787-793` carries
  authored aliases into the `ReferenceResolver`, so an alias can change **which entity a
  reference resolves to**, and therefore the target closure. `aliases` is consequently
  **not** on the seed allowlist. Do not add it.
- **`CORE_PROFILE.entity_kinds` carries each kind's home** (`kind.home`) — a directory
  for most kinds, and a **file** for the two singletons (`entities/research-question.md`,
  `entities/claim-registry.yaml`); 36 kinds declare one. `science_model.profiles.core`
  imports cleanly standalone. **`science_tool.entities.entity_policies` is the richer
  API but is unusable here** — see the import-cycle note in Task 2.
- **`git` honours `.git/refs/replace` by default.** A replacement ref grafts one
  commit's content onto another's identity, so `git diff base head` can report an empty
  diff for a commit that really changed the tree. Every git invocation in this package
  passes `--no-replace-objects` (Task 4).
- **`split_frontmatter(text) -> (dict, body)`**
  (`science/model/src/science_model/frontmatter.py:113`) parses frontmatter from *text*
  — the right tool for a `git show` blob. It returns `({}, text)` when there is no
  parseable block, and never raises on a missing block.
- **`RunTier`** already exists in `science/model/src/science_model/autonomous_runs.py`
  (Plan B) with values `report-only` and `belief-neutral`. **Reuse it. Do not define a
  second tier enum.**
- **Every leaf CLI command must be classified** — `science/tests/test_budget_boundary.py:39`
  requires membership in `BUDGETS | EXEMPTIONS | DEFERRED`, and `:55` **locks the
  cardinality** at `4/67/207 = 278`. Adding a command requires updating both.
- **Every top-level command must appear in the CLI workflow map** —
  `science/tests/test_user_guide_docs.py:105` scans `docs/user-guide/cli-and-workflows.md`
  for backticked spans. A new `autonomy` group fails this test until documented.
- **`science_tool.entities` cannot be imported from this package at all.** As the first
  `science_tool` import it raises `ImportError` through `commons/validator.py`,
  deterministically, on clean `main`. Deferring the import into a function does **not**
  help — the failure is about which module loads first, not when. This is a pre-existing
  toolkit defect that Plan C works around rather than fixes; see Task 2.

### The `task` finding — why the seed allowlist has no task fields

`task` has **no markdown home**: `CORE_PROFILE` gives it `home=None, strategy=None`, so
it is absent from `entity_policies()` and has no frontmatter file to gate. Tasks are
therefore outside a path-and-frontmatter gate entirely, and `task.priority` /
`task.aspects` — plausible-looking curation-sweep targets — **cannot** be on this
allowlist. Extending the gate to structured sources is a separate design conversation,
not a task in this plan. Any implementer who "fixes" this by adding a `task` entry has
added a rule that can never match.

## Global Constraints

Every task's requirements implicitly include this section.

1. **The gate is not project-overridable (design §4).** `autonomy/policy.py` must not
   read project configuration, environment variables, or any file. Task 1 ships an AST
   guard test for this. No later task may weaken it.
2. **Default-deny.** Absence of an entry means denied. No task adds a fallback, a
   wildcard kind, a `"*"` key, or a permissive default.
3. **Layer 3 is one-way (design §5).** A perturbation that moves the basis takes a field
   **off** the allowlist. Observing no movement never puts one on. **No code path may
   write to `FIELD_ALLOWLIST`.**
4. **Entity kind is derived from the path, never from the file's own `kind:`
   frontmatter.** An actor that chose its own kind would choose its own allowlist.
   `kind` is additionally on no allowlist, so relabelling is denied twice.
5. **Every git invocation passes `--no-replace-objects`,** before `-C`. Replacement refs
   are actor-writable and make ordinary git report an empty diff for a commit that
   changed the tree. A gate that reads a tampered history is worse than no gate.
6. **A change the gate cannot account for is denied, never ignored.** An unreadable
   blob, unparseable frontmatter, and a modification with no field-level change (a
   chmod, a byte-level edit) are all denials or errors — never an empty field list that
   evaluates to allowed.
7. **Two-dot commit ranges only.** `git diff <base> <head>` (tree-to-tree). **Never**
   three-dot `<base>...<head>`, which diffs from the merge-base and moves under rebase
   and integration-branch advancement — the failure design §6 explicitly rejects.
   Note `annotation/query.py:326` uses three-dot for an unrelated purpose; it is not a
   precedent for this.
8. **Reuse `RunTier` from `science_model.autonomous_runs`.** Do not redefine tiers, and
   do not add a third one.
9. **pydantic models are `frozen=True, extra="forbid"`**, matching Plan A's `EntityBasis`
   and Plan B's `AutonomousRunRecord`.
10. **Exit-code contract mirrors `science graph belief-basis`** (`graph/cli.py:1249`):
   `0` allowed, `1` denied, `2` could not evaluate. **`2` is explicitly not `0`** — a
   gate that cannot see must not report allowed.
11. **Run the suite with an explicit long timeout.** The suite takes ~290s; the Bash
   tool's default is 120s. Use `timeout: 600000` on every `pytest` call, and never run
   it in the background.
12. **No AI-attribution trailer or footer** on any commit message.
13. **Use `~/d/` or repo-relative paths** in docs and code comments, never
    `/home/keith/` or `/mnt/ssd/Dropbox/`.

## File Structure

| File | Responsibility |
|---|---|
| `science/src/science_tool/autonomy/__init__.py` | Package marker; no re-exports. |
| `science/src/science_tool/autonomy/policy.py` | Frozen allowlists + accessors. Zero I/O. |
| `science/src/science_tool/autonomy/changes.py` | `ChangeType`, `PathChange`, `ChangeSet`, `entity_kind_for_path`. |
| `science/src/science_tool/autonomy/path_gate.py` | `Denial`, `GateVerdict`, `evaluate`. Pure. |
| `science/src/science_tool/autonomy/extract.py` | `extract_change_set`, `ExtractError`. The only module that shells out. |
| `science/src/science_tool/autonomy/cli.py` | `autonomy_group`, `path-gate` command. |
| `science/src/science_tool/cli.py` | Register the group (modify). |
| `science/src/science_tool/budget/registry.py` | `DeferredCommand` entry (modify). |
| `science/tests/test_autonomy_policy.py` | Task 1. |
| `science/tests/test_autonomy_changes.py` | Task 2. |
| `science/tests/test_autonomy_path_gate.py` | Task 3. |
| `science/tests/test_autonomy_extract.py` | Task 4. |
| `science/tests/test_autonomy_cli.py` | Task 5. |
| `science/tests/test_autonomy_perturbation_alarm.py` | Task 6 — Layer 3. |
| `docs/user-guide/agent-workflows.md` | Task 7 (modify). |
| `docs/user-guide/cli-and-workflows.md` | Task 5 (modify) — guard test requires it. |
| `docs/plans/2026-07-24-autonomy-envelope-design.md` | Task 7 (modify) — revision note. |

---

### Task 1: Policy tables

**Files:**
- Create: `science/src/science_tool/autonomy/__init__.py`
- Create: `science/src/science_tool/autonomy/policy.py`
- Test: `science/tests/test_autonomy_policy.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `FIELD_ALLOWLIST: Mapping[str, frozenset[str]]`,
  `CREATION_ALLOWLIST: Mapping[str, frozenset[str]]`,
  `DENIAL_REASONS: Mapping[str, str]`,
  `is_field_allowed(kind: str, field: str) -> bool`,
  `is_creation_allowed(kind: str, field: str) -> bool`,
  `denial_reason(rel_path: str) -> str`,
  `DEFAULT_DENY_REASON: str`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_autonomy_policy.py`:

```python
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from science_tool.autonomy.policy import (
    CREATION_ALLOWLIST,
    DEFAULT_DENY_REASON,
    FIELD_ALLOWLIST,
    denial_reason,
    is_creation_allowed,
    is_field_allowed,
)

POLICY_SOURCE = Path(__file__).resolve().parents[1] / "src" / "science_tool" / "autonomy" / "policy.py"


def test_an_unregistered_field_is_denied_with_no_registration():
    """Design §4 default-deny: a field nobody has heard of needs no action to be denied."""
    assert is_field_allowed("paper", "zzz_field_invented_tomorrow") is False


def test_an_unregistered_kind_is_denied_entirely():
    assert is_field_allowed("hypothesis", "title") is False
    assert is_field_allowed("evidence-line", "strength") is False


def test_belief_bearing_fields_are_denied_on_every_allowlisted_kind():
    for kind in FIELD_ALLOWLIST:
        for field in ("confidence", "evidence_refs", "claim_layer", "aliases", "kind", "id", "related"):
            assert is_field_allowed(kind, field) is False, f"{kind}.{field} must be denied"


def test_creation_is_denied_for_every_kind():
    """S1 grants no creation surface; the table exists so Plan D has a place to argue."""
    assert dict(CREATION_ALLOWLIST) == {}
    assert is_creation_allowed("paper", "title") is False


def test_named_denial_reasons_cover_the_design_table():
    assert "payload boundary" in denial_reason("data/raw/counts.tsv")
    assert "durable writer" in denial_reason("knowledge/graph.trig")
    assert "schema-version pin" in denial_reason("science.yaml")
    assert "guard integrity" in denial_reason("core/decisions.md")
    assert "supervisor-owned" in denial_reason("runs/2026-07-25-sweep-a3f1.md")
    assert "toolchain" in denial_reason("uv.lock")


def test_an_unnamed_path_still_gets_the_default_deny_reason():
    assert denial_reason("some/path/nobody/enumerated.txt") == DEFAULT_DENY_REASON


def test_allowlists_cannot_be_mutated_at_runtime():
    """Layer 3 is one-way (design §5): nothing may write the allowlist."""
    with pytest.raises(TypeError):
        FIELD_ALLOWLIST["paper"] = frozenset({"confidence"})  # type: ignore[index]


def test_policy_module_reads_no_project_state():
    """Design §4: the gate is NOT project-overridable. An override is a hole that will be
    widened under pressure by the very agents it constrains. This is the guard."""
    # An ALLOWLIST, not a blacklist. A blacklist cannot express "reads no project
    # state": any unlisted module (`science_tool.project_config`, `configparser`,
    # `importlib.resources`, ...) walks straight through it. These four are everything
    # policy.py legitimately needs, so anything else is a design change that must be
    # argued for here first.
    permitted_imports = {"__future__", "collections.abc", "types"}
    tree = ast.parse(POLICY_SOURCE.read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert imported <= permitted_imports, (
        f"policy.py imports {sorted(imported - permitted_imports)}. The gate is not "
        "project-overridable: it must read no project state. Widening this allowlist is "
        "a design change, not a fix."
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_policy.py -q
```

Expected: collection error — `ModuleNotFoundError: No module named 'science_tool.autonomy'`.

- [ ] **Step 3: Write the implementation**

Create `science/src/science_tool/autonomy/__init__.py` containing exactly:

```python
"""Autonomy envelope: the write surface an unattended run is permitted (design §4-§5)."""
```

Create `science/src/science_tool/autonomy/policy.py`:

```python
"""Default-deny write policy for autonomous runs (design §4).

NOT project-overridable by construction: nothing in this module reads project
configuration, environment, or any file. A project needing a different autonomous
write surface is a design conversation, not a config key -- an override is a hole
that will be widened under pressure by the very agents it constrains.

Every entry below is covered by a Layer 3 perturbation case in
`tests/test_autonomy_perturbation_alarm.py`, which fails if an entry is added here
without one.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

#: Per-kind fields an autonomous run may write on a PRE-EXISTING entity. Every kind
#: absent from this mapping, and every field absent from a kind's entry, is DENIED
#: with no registration required.
#:
#: Neutrality arguments, in two tiers:
#:
#:   Tier A -- produces no graph triple at all, so it cannot reach any belief input:
#:     paper.venue, paper.pmid, book.publisher, book.isbn,
#:     talk.venue, talk.duration_minutes
#:
#:   Tier B -- materializes into graph/knowledge (`graph/materialize.py:700-710`) but
#:   emits no cito edge, no rdf:type, no evidence-line provenance metadata, and no
#:   target polarity, so neither the target closure nor any evidence unit reads it:
#:     paper.year, paper.url, book.year, book.url   (dcterms:date / dcat:downloadURL)
#:
#: DELIBERATELY ABSENT, with reasons:
#:   aliases  -- feeds reference resolution (`graph/sources.py:787-793`), so it can
#:               re-point a reference and move the target closure.
#:   doi      -- materializes to sci:doi and is identity-adjacent (xrefs, identity
#:               arbitration). Accepted overbreadth; promote only under design §5
#:               Layer 4 review.
#:   task.*   -- `task` has no markdown home (CORE_PROFILE: home=None), so no rule
#:               here could ever match it.
FIELD_ALLOWLIST: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "paper": frozenset({"venue", "pmid", "year", "url"}),
        "book": frozenset({"publisher", "isbn", "year", "url"}),
        "talk": frozenset({"venue", "duration_minutes"}),
    }
)

#: Kinds an autonomous run may CREATE, and the fields it may set at creation. EMPTY in
#: S1. Creation is not merely "editing a file with no before-value": a created entity
#: can change another entity's belief basis (design §4), and nothing in the envelope
#: needs creation yet. The table exists so Plan D has a place to argue for entries.
CREATION_ALLOWLIST: Mapping[str, frozenset[str]] = MappingProxyType({})

#: Named reasons for the notable denied paths of design §4. This table is
#: DOCUMENTATION, not the mechanism: the mechanism is that everything not explicitly
#: allowed is denied. Deleting a row here does not permit anything.
#:
#: Keys match a path exactly or as a leading directory segment.
DENIAL_REASONS: Mapping[str, str] = MappingProxyType(
    {
        "data": "payload boundary; autonomous runs never touch measurement payload",
        "knowledge/graph.trig": "source is its only durable writer (kernel closure)",
        "science.yaml": "the schema-version pin is sole write authority",
        "core/decisions.md": "guard integrity -- belief machinery reads its flags",
        "runs": "supervisor-owned (design §0)",
        "pyproject.toml": "toolchain selection; high blast radius",
        "uv.lock": "toolchain selection; high blast radius",
    }
)

#: The reason every other path gets. Default-deny means this is the common case, not
#: the exception.
DEFAULT_DENY_REASON = "not on any allowlist (default-deny)"


def is_field_allowed(kind: str, field: str) -> bool:
    """True only when `kind` has an explicit entry that names `field`."""
    return field in FIELD_ALLOWLIST.get(kind, frozenset())


def is_creation_allowed(kind: str, field: str) -> bool:
    """True only when `kind` may be created and `field` set at creation."""
    return field in CREATION_ALLOWLIST.get(kind, frozenset())


def denial_reason(rel_path: str) -> str:
    """A named reason when the design gives one, else the default-deny reason."""
    for prefix, reason in DENIAL_REASONS.items():
        if rel_path == prefix or rel_path.startswith(f"{prefix}/"):
            return reason
    return DEFAULT_DENY_REASON
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_policy.py -q
```

Expected: 8 passed.

- [ ] **Step 5: Lint and type-check**

```bash
cd science && uv run ruff check src/science_tool/autonomy tests/test_autonomy_policy.py && uv run pyright
```

Expected: ruff clean; pyright 0 errors.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/autonomy science/tests/test_autonomy_policy.py
git commit -m "feat(autonomy): add default-deny write policy tables"
```

---

### Task 2: Change-set model and path→kind classification

**Files:**
- Create: `science/src/science_tool/autonomy/changes.py`
- Test: `science/tests/test_autonomy_changes.py`

**`science_tool.entities` is unusable here — this is load-bearing.** On clean `main`
(`b0c6dfa7`), `from science_tool.entities import entity_policies` as the first
`science_tool` import fails **deterministically**:

```
science_tool/commons/cli.py:72 -> commons/validator.py:17
ImportError: cannot import name 'valid_statuses' from partially initialized module
'science_tool.entities' (most likely due to a circular import)
```

Verified in this worktree. (A cycle-breaking refactor extracting
`science_tool/kind_descriptors.py` is in flight uncommitted in the main checkout — do
not depend on it; it is not on `main`.)

This task therefore reads homes from **`science_model.profiles.core.CORE_PROFILE`**,
which imports cleanly on its own. The consequence is deliberate and *safer*, not a
compromise: **project-local kinds are not classified at all**, so their entity files
return `None` and are denied. A project-local kind has no `FIELD_ALLOWLIST` entry
either way, so classifying it could never have allowed anything — dropping the
dependency can only ever deny more, which is the correct direction under default-deny.

**Interfaces:**
- Consumes: `CORE_PROFILE` from `science_model.profiles.core`. **Do not import
  `science_tool.entities`, `entity_policies`, or `resolve_path_policy` anywhere in this
  package.**
- Produces:
  - `class ChangeType(StrEnum)` with `MODIFIED = "modified"`, `ADDED = "added"`,
    `DELETED = "deleted"`.
  - `class PathChange(BaseModel)` — `path: str` (repo-relative posix),
    `change_type: ChangeType`, `entity_kind: str | None`, `fields: tuple[str, ...]`.
  - `class ChangeSet(BaseModel)` — `base_commit: str`, `head_commit: str`,
    `changes: tuple[PathChange, ...]`.
  - `BODY_FIELD: str = "content"`.
  - `entity_kind_for_path(rel_path: str) -> str | None` — **no `project_root` parameter**;
    classification is profile-derived, not project-derived.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_autonomy_changes.py`:

```python
from __future__ import annotations

import pytest

from science_tool.autonomy.changes import (
    BODY_FIELD,
    ChangeSet,
    ChangeType,
    PathChange,
    entity_kind_for_path,
)


def test_a_paper_path_classifies_as_paper():
    assert entity_kind_for_path("entities/papers/smith2020.md") == "paper"


def test_a_hypothesis_path_classifies_as_hypothesis():
    assert entity_kind_for_path("entities/hypotheses/h01-thing.md") == "hypothesis"


def test_a_markdown_singleton_home_classifies():
    assert entity_kind_for_path("entities/research-question.md") == "research-question"


def test_a_non_entity_path_is_not_an_entity():
    assert entity_kind_for_path("core/decisions.md") is None
    assert entity_kind_for_path("data/raw/counts.tsv") is None
    assert entity_kind_for_path("science.yaml") is None
    assert entity_kind_for_path("runs/2026-07-25-sweep-a3f1.md") is None


def test_a_file_nested_below_a_kind_home_is_not_that_kind():
    """Only direct children of a home are that kind; a deeper file is unclassified and
    therefore denied by default."""
    assert entity_kind_for_path("entities/papers/attachments/fig1.md") is None


def test_an_archive_tier_path_is_not_an_entity():
    """`_`-prefixed segments are the archive tier (entities.py `_resolve_local_home`)."""
    assert entity_kind_for_path("entities/papers/_archived/old.md") is None


def test_a_non_markdown_file_in_a_markdown_home_is_not_an_entity():
    assert entity_kind_for_path("entities/papers/smith2020.pdf") is None


def test_a_project_local_kind_home_is_unclassified_and_therefore_denied():
    """Classification is derived from CORE_PROFILE only, so a project-local kind is
    never classified. That is safe by construction: a local kind has no allowlist entry,
    so classifying it could not have allowed anything. Denying more is the correct
    direction under default-deny."""
    assert entity_kind_for_path("entities/designs/d01-thing.md") is None


def test_classification_needs_no_project_root():
    """Guard for the import boundary: `science_tool.entities` cycles when it is the
    first `science_tool` import, so this module must stay profile-derived."""
    import inspect

    assert "project_root" not in inspect.signature(entity_kind_for_path).parameters


def test_path_change_is_frozen_and_closed():
    from pydantic import ValidationError

    change = PathChange(path="a.md", change_type=ChangeType.MODIFIED, entity_kind=None, fields=())
    with pytest.raises(ValidationError):
        change.path = "b.md"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        PathChange(path="a.md", change_type=ChangeType.MODIFIED, entity_kind=None, fields=(), extra=1)  # type: ignore[call-arg]


def test_body_field_is_a_pseudo_field_named_content():
    """Body prose is gated as a field so it is denied by default like any other."""
    assert BODY_FIELD == "content"


def test_change_set_holds_its_range():
    cs = ChangeSet(base_commit="a" * 40, head_commit="b" * 40, changes=())
    assert cs.base_commit.startswith("a")
    assert cs.changes == ()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_changes.py -q
```

Expected: `ModuleNotFoundError: No module named 'science_tool.autonomy.changes'`.

- [ ] **Step 3: Write the implementation**

Create `science/src/science_tool/autonomy/changes.py`:

```python
"""The change set the path gate decides over, and how a path maps to an entity kind."""

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict
from science_model.profiles.core import CORE_PROFILE

#: Body prose is gated as a pseudo-field so it is denied by default exactly like any
#: frontmatter field. It is named for `Entity.content`, which is what it becomes.
BODY_FIELD = "content"


class ChangeType(StrEnum):
    MODIFIED = "modified"
    ADDED = "added"
    DELETED = "deleted"


class PathChange(BaseModel):
    """One repository path the run touched.

    `entity_kind` is derived from the PATH, never from the file's own `kind:`
    frontmatter -- an actor that could choose its own kind could choose the most
    permissive allowlist. `fields` is empty for non-entity paths, whose denial is
    decided by path alone.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    change_type: ChangeType
    entity_kind: str | None
    fields: tuple[str, ...]


class ChangeSet(BaseModel):
    """Everything that changed between two commits, in deterministic path order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_commit: str
    head_commit: str
    changes: tuple[PathChange, ...]


#: kind -> home, derived from CORE_PROFILE at import time.
#:
#: `science_tool.entities` is NOT used: importing it as the first `science_tool` module
#: fails deterministically through `commons/validator.py` (a real cycle on `main`).
#: Reading CORE_PROFILE instead means project-LOCAL kinds are never classified, so their
#: files return None and are denied. That is safe by construction -- a local kind has no
#: FIELD_ALLOWLIST entry, so classifying it could never have allowed anything.
_CORE_HOMES: tuple[tuple[str, PurePosixPath], ...] = tuple(
    sorted(
        ((kind.name, PurePosixPath(kind.home)) for kind in CORE_PROFILE.entity_kinds if kind.home),
        # Longest root first, so a nested home wins over a parent that prefixes it.
        key=lambda item: len(str(item[1])),
        reverse=True,
    )
)


def entity_kind_for_path(rel_path: str) -> str | None:
    """The core kind that owns `rel_path`, or None when it is not a core entity file.

    None means "unclassified", which the gate reads as denied. Every non-entity path,
    every project-local kind, every archive-tier path, and every non-markdown file
    lands here.
    """
    candidate = PurePosixPath(rel_path)
    if any(segment.startswith("_") for segment in candidate.parts):
        return None  # archive tier -- unclassified, therefore denied

    for kind, root in _CORE_HOMES:
        if root.suffix:  # singleton home: the home IS the file
            if candidate == root:
                return kind
            continue
        if candidate.parent == root and candidate.suffix == ".md":
            return kind
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_changes.py -q
```

Expected: 12 passed. Only the `.md` singleton classifies; the `claim-registry.yaml`
singleton stays unclassified (denied), which is correct.

- [ ] **Step 5: Lint and type-check**

```bash
cd science && uv run ruff check src/science_tool/autonomy tests/test_autonomy_changes.py && uv run pyright
```

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/autonomy/changes.py science/tests/test_autonomy_changes.py
git commit -m "feat(autonomy): add change-set model and path-to-kind classification"
```

---

### Task 3: The gate evaluator

**Files:**
- Create: `science/src/science_tool/autonomy/path_gate.py`
- Test: `science/tests/test_autonomy_path_gate.py`

**Interfaces:**
- Consumes: `ChangeSet`, `PathChange`, `ChangeType`, `BODY_FIELD` (Task 2);
  `is_field_allowed`, `is_creation_allowed`, `denial_reason` (Task 1);
  `RunTier` from `science_model.autonomous_runs`.
- Produces:
  - `class Denial(BaseModel)` — `path: str`, `field: str | None`, `reason: str`.
  - `class GateVerdict(BaseModel)` — `allowed: bool`, `denials: tuple[Denial, ...]`.
  - `evaluate(change_set: ChangeSet, *, tier: RunTier, report_path: str | None = None) -> GateVerdict`.
  - `class GateInputError(ValueError)`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_autonomy_path_gate.py`:

```python
from __future__ import annotations

import pytest
from science_model.autonomous_runs import RunTier

from science_tool.autonomy.changes import BODY_FIELD, ChangeSet, ChangeType, PathChange
from science_tool.autonomy.path_gate import GateInputError, evaluate


def _cs(*changes: PathChange) -> ChangeSet:
    return ChangeSet(base_commit="a" * 40, head_commit="b" * 40, changes=changes)


def _paper(fields: tuple[str, ...], change_type: ChangeType = ChangeType.MODIFIED) -> PathChange:
    return PathChange(
        path="entities/papers/smith2020.md",
        change_type=change_type,
        entity_kind="paper",
        fields=fields,
    )


def test_an_allowlisted_field_edit_is_allowed():
    verdict = evaluate(_cs(_paper(("venue",))), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is True
    assert verdict.denials == ()


def test_a_belief_bearing_field_edit_is_denied():
    verdict = evaluate(_cs(_paper(("confidence",))), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is False
    assert [d.field for d in verdict.denials] == ["confidence"]


def test_an_allowed_field_does_not_launder_a_denied_sibling():
    """A single denial in a multi-field edit denies the change."""
    verdict = evaluate(_cs(_paper(("venue", "confidence"))), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is False
    assert [d.field for d in verdict.denials] == ["confidence"]


def test_a_body_prose_edit_is_denied():
    verdict = evaluate(_cs(_paper((BODY_FIELD,))), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is False
    assert verdict.denials[0].field == BODY_FIELD


def test_a_field_nobody_registered_is_denied_with_no_test_edit():
    """Design test #4: default-deny needs no registration and no edit here."""
    verdict = evaluate(_cs(_paper(("zzz_field_invented_tomorrow",))), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is False


def test_entity_creation_is_denied():
    verdict = evaluate(_cs(_paper(("title",), ChangeType.ADDED)), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is False
    assert "creation" in verdict.denials[0].reason


def test_entity_deletion_is_denied():
    verdict = evaluate(_cs(_paper((), ChangeType.DELETED)), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is False
    assert "deletion" in verdict.denials[0].reason


def test_a_kind_with_no_allowlist_entry_is_denied():
    change = PathChange(
        path="entities/hypotheses/h01.md",
        change_type=ChangeType.MODIFIED,
        entity_kind="hypothesis",
        fields=("status",),
    )
    assert evaluate(_cs(change), tier=RunTier.BELIEF_NEUTRAL).allowed is False


def test_a_non_entity_path_is_denied_with_its_named_reason():
    change = PathChange(
        path="core/decisions.md", change_type=ChangeType.MODIFIED, entity_kind=None, fields=()
    )
    verdict = evaluate(_cs(change), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is False
    assert "guard integrity" in verdict.denials[0].reason
    assert verdict.denials[0].field is None


def test_report_only_denies_what_belief_neutral_allows():
    """Design §1: report-only may write ONLY the run's own report path."""
    change_set = _cs(_paper(("venue",)))
    assert evaluate(change_set, tier=RunTier.BELIEF_NEUTRAL).allowed is True
    assert evaluate(change_set, tier=RunTier.REPORT_ONLY).allowed is False


def test_the_report_path_is_allowed_in_both_tiers():
    change = PathChange(
        path="results/sweep-a3f1.md", change_type=ChangeType.ADDED, entity_kind=None, fields=()
    )
    for tier in (RunTier.REPORT_ONLY, RunTier.BELIEF_NEUTRAL):
        verdict = evaluate(_cs(change), tier=tier, report_path="results/sweep-a3f1.md")
        assert verdict.allowed is True, tier


def test_report_only_with_no_report_path_allows_nothing():
    change = PathChange(
        path="results/sweep-a3f1.md", change_type=ChangeType.ADDED, entity_kind=None, fields=()
    )
    assert evaluate(_cs(change), tier=RunTier.REPORT_ONLY).allowed is False


@pytest.mark.parametrize("bad", ["/abs/report.md", "../escape.md", "a/../../escape.md"])
def test_an_unsafe_report_path_is_rejected_rather_than_honoured(bad: str):
    with pytest.raises(GateInputError):
        evaluate(_cs(), tier=RunTier.REPORT_ONLY, report_path=bad)


def test_an_empty_change_set_is_allowed():
    assert evaluate(_cs(), tier=RunTier.BELIEF_NEUTRAL).allowed is True


def test_a_modification_with_no_changed_fields_is_denied():
    """Fail-open regression: git reports a chmod as `M` with identical blobs, so a
    modification carrying no field change must not read as 'nothing to deny'."""
    verdict = evaluate(_cs(_paper(())), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is False
    assert "no field-level change" in verdict.denials[0].reason


def test_denials_are_ordered_by_path_then_field():
    verdict = evaluate(
        _cs(
            _paper(("confidence", "abstract")),
            PathChange(path="core/decisions.md", change_type=ChangeType.MODIFIED, entity_kind=None, fields=()),
        ),
        tier=RunTier.BELIEF_NEUTRAL,
    )
    assert [(d.path, d.field) for d in verdict.denials] == [
        ("core/decisions.md", None),
        ("entities/papers/smith2020.md", "abstract"),
        ("entities/papers/smith2020.md", "confidence"),
    ]
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_path_gate.py -q
```

Expected: `ModuleNotFoundError: No module named 'science_tool.autonomy.path_gate'`.

- [ ] **Step 3: Write the implementation**

Create `science/src/science_tool/autonomy/path_gate.py`:

```python
"""Layer 1 of design §5: the syntactic, default-deny path gate.

Complete by construction -- anything not explicitly allowed is denied -- and its
failure mode is over-restriction. It does NOT prove belief-neutrality; that is Layer 2
(`graph/belief_basis.py`, Plan A), which is authoritative precisely because it does not
depend on this allowlist being correct.

Pure: no filesystem, no git, no project state. The change set arrives already built.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict
from science_model.autonomous_runs import RunTier

from science_tool.autonomy.changes import ChangeSet, ChangeType, PathChange
from science_tool.autonomy.policy import denial_reason, is_creation_allowed, is_field_allowed


class GateInputError(ValueError):
    """The gate was handed an input it cannot decide over."""


class Denial(BaseModel):
    """One reason the run's write surface exceeded its tier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    field: str | None
    reason: str


class GateVerdict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool
    denials: tuple[Denial, ...]


def _validate_report_path(report_path: str | None) -> str | None:
    if report_path is None:
        return None
    candidate = PurePosixPath(report_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise GateInputError(
            f"report_path must be a repository-relative path with no parent traversal, got {report_path!r}"
        )
    return str(candidate)


def _denials_for(change: PathChange) -> list[Denial]:
    if change.entity_kind is None:
        return [Denial(path=change.path, field=None, reason=denial_reason(change.path))]

    if change.change_type is ChangeType.DELETED:
        return [
            Denial(
                path=change.path,
                field=None,
                reason=f"entity deletion is not permitted for kind {change.entity_kind!r}",
            )
        ]

    if change.change_type is ChangeType.ADDED:
        # Creation has its own allowlist (design §4): a created entity can change
        # ANOTHER entity's belief basis, so it is not "editing a file with no
        # before-value". With CREATION_ALLOWLIST empty, every creation lands here.
        denied = [f for f in change.fields if not is_creation_allowed(change.entity_kind, f)]
        if not denied and change.fields:
            return []
        return [
            Denial(
                path=change.path,
                field=None,
                reason=f"entity creation is not permitted for kind {change.entity_kind!r}",
            )
        ]

    if not change.fields:
        # git reports an executable-bit or other metadata-only change as `M` with
        # identical blobs, and frontmatter key REORDERING parses to an identical dict.
        # Both reach here with no changed field. Allowing them would let repository
        # metadata escape the default-deny surface entirely -- so an unexplained
        # modification is denied, like anything else the gate cannot account for.
        return [
            Denial(
                path=change.path,
                field=None,
                reason="modified with no field-level change (file mode or byte-level edit); "
                "nothing about this modification is on an allowlist",
            )
        ]

    return [
        Denial(
            path=change.path,
            field=field,
            reason=f"field {field!r} is not on the {change.entity_kind!r} allowlist (default-deny)",
        )
        for field in change.fields
        if not is_field_allowed(change.entity_kind, field)
    ]


def evaluate(
    change_set: ChangeSet, *, tier: RunTier, report_path: str | None = None
) -> GateVerdict:
    """Decide whether every change in `change_set` is inside `tier`'s write surface.

    `report_path` is the run's own report, supplied by the supervisor (design §0) -- it
    is the ONLY path `report-only` may write, and it is allowed in `belief-neutral` too.
    """
    allowed_report = _validate_report_path(report_path)

    denials: list[Denial] = []
    for change in change_set.changes:
        if allowed_report is not None and change.path == allowed_report:
            continue
        if tier is RunTier.REPORT_ONLY:
            denials.append(
                Denial(
                    path=change.path,
                    field=None,
                    reason="tier 'report-only' may write only the run's own report path",
                )
            )
            continue
        denials.extend(_denials_for(change))

    ordered = tuple(sorted(denials, key=lambda d: (d.path, d.field or "")))
    return GateVerdict(allowed=not ordered, denials=ordered)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_path_gate.py -q
```

Expected: 18 passed (16 test functions, one of which is parametrized over 3 values).

- [ ] **Step 5: Lint and type-check**

```bash
cd science && uv run ruff check src/science_tool/autonomy tests/test_autonomy_path_gate.py && uv run pyright
```

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/autonomy/path_gate.py science/tests/test_autonomy_path_gate.py
git commit -m "feat(autonomy): add default-deny path gate evaluator"
```

---

### Task 4: Git change-set extraction

**Files:**
- Create: `science/src/science_tool/autonomy/extract.py`
- Test: `science/tests/test_autonomy_extract.py`

**Interfaces:**
- Consumes: `ChangeSet`, `PathChange`, `ChangeType`, `BODY_FIELD`,
  `entity_kind_for_path` (Task 2); `split_frontmatter` from
  `science_model.frontmatter`.
- Produces:
  - `class ExtractError(ValueError)`.
  - `extract_change_set(repo_root: Path, base: str, head: str) -> ChangeSet`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_autonomy_extract.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.autonomy.changes import BODY_FIELD, ChangeType
from science_tool.autonomy.extract import ExtractError, extract_change_set

PAPER = "entities/papers/smith2020.md"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _commit(root: Path, message: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message, "--allow-empty")
    return _git(root, "rev-parse", "HEAD")


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _paper_text(*, venue: str = "Nature", body: str = "Abstract.\n") -> str:
    return f"---\nid: paper:smith2020\nkind: paper\ntitle: T\nvenue: {venue}\n---\n\n{body}"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    _write(tmp_path, PAPER, _paper_text())
    _commit(tmp_path, "base")
    return tmp_path


def test_a_frontmatter_edit_reports_that_field(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text(venue="Science"))
    head = _commit(repo, "edit venue")

    change_set = extract_change_set(repo, base, head)
    assert len(change_set.changes) == 1
    change = change_set.changes[0]
    assert change.path == PAPER
    assert change.entity_kind == "paper"
    assert change.change_type is ChangeType.MODIFIED
    assert change.fields == ("venue",)


def test_a_body_edit_reports_the_content_pseudo_field(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text(body="Rewritten abstract.\n"))
    head = _commit(repo, "edit body")

    assert extract_change_set(repo, base, head).changes[0].fields == (BODY_FIELD,)


def test_an_added_field_is_reported(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text().replace("venue: Nature\n", "venue: Nature\nconfidence: 0.9\n"))
    head = _commit(repo, "add confidence")

    assert extract_change_set(repo, base, head).changes[0].fields == ("confidence",)


def test_a_removed_field_is_reported(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text().replace("venue: Nature\n", ""))
    head = _commit(repo, "drop venue")

    assert extract_change_set(repo, base, head).changes[0].fields == ("venue",)


def test_a_new_entity_file_is_an_addition(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, "entities/papers/jones2021.md", _paper_text())
    head = _commit(repo, "new paper")

    change = extract_change_set(repo, base, head).changes[0]
    assert change.change_type is ChangeType.ADDED
    assert change.entity_kind == "paper"


def test_a_deleted_entity_file_is_a_deletion(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    (repo / PAPER).unlink()
    head = _commit(repo, "delete paper")

    change = extract_change_set(repo, base, head).changes[0]
    assert change.change_type is ChangeType.DELETED
    assert change.entity_kind == "paper"


def test_a_rename_is_a_deletion_plus_an_addition(repo: Path):
    """--no-renames: a rename that git would summarise as R100 must surface as both
    halves, because both halves are independently denied."""
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "mv", PAPER, "entities/papers/renamed.md")
    head = _commit(repo, "rename")

    kinds = {(c.path, c.change_type) for c in extract_change_set(repo, base, head).changes}
    assert (PAPER, ChangeType.DELETED) in kinds
    assert ("entities/papers/renamed.md", ChangeType.ADDED) in kinds


def test_a_non_entity_path_carries_no_fields(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, "core/decisions.md", "flag: on\n")
    head = _commit(repo, "touch decisions")

    change = next(c for c in extract_change_set(repo, base, head).changes if c.path == "core/decisions.md")
    assert change.entity_kind is None
    assert change.fields == ()


def test_the_range_is_two_dot_not_merge_base(repo: Path):
    """Design §6: a merge-base baseline moves under rebase and integration-branch
    advancement. `base..head` must diff the recorded trees, not their merge-base.

    History: A -- C   (main, C edits venue to 'Cell')
              \\
               B      (branch from A, B edits the body)

    base=C, head=B. Two-dot C..B shows BOTH the body edit and venue reverting to
    'Nature'. Three-dot C...B diffs from merge-base A and shows only the body edit.
    """
    a = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "side", a)
    _write(repo, PAPER, _paper_text(body="Side body.\n"))
    b = _commit(repo, "side edit")
    _git(repo, "checkout", "-q", "-")
    _write(repo, PAPER, _paper_text(venue="Cell"))
    c = _commit(repo, "main edit")

    fields = extract_change_set(repo, c, b).changes[0].fields
    assert set(fields) == {"venue", BODY_FIELD}, "three-dot semantics would report only the body"


def test_an_unresolvable_commit_is_an_error_not_an_empty_change_set(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(ExtractError):
        extract_change_set(repo, base, "0" * 40)


def test_a_replacement_ref_cannot_hide_a_change(repo: Path):
    """`git replace` grafts one commit's content onto another's identity, and ordinary
    git honours it -- a diff over a tampered repository reports NOTHING. Every git
    invocation must pass --no-replace-objects."""
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, "science.yaml", "name: t\nschema_version: 2\n")
    head = _commit(repo, "edit config")
    _git(repo, "replace", head, base)  # graft base's tree onto head's identity

    changes = extract_change_set(repo, base, head).changes
    assert [c.path for c in changes] == ["science.yaml"], (
        "replacement ref hid the change; git ran without --no-replace-objects"
    )


def test_a_mode_only_change_is_reported_as_a_modification(repo: Path):
    """A chmod produces `M` with identical blobs and therefore no changed fields. The
    extractor must still report the modification so the gate can deny it."""
    base = _git(repo, "rev-parse", "HEAD")
    (repo / PAPER).chmod(0o755)
    head = _commit(repo, "chmod")

    changes = extract_change_set(repo, base, head).changes
    assert len(changes) == 1
    assert changes[0].change_type is ChangeType.MODIFIED
    assert changes[0].fields == ()


def test_an_unreadable_entity_blob_is_an_error_not_an_empty_field_list(repo: Path):
    """Fail-open regression: a blob that cannot be decoded must NOT diff to zero
    changed fields, which the evaluator would allow."""
    base = _git(repo, "rev-parse", "HEAD")
    (repo / PAPER).write_bytes(b"---\nid: paper:smith2020\nkind: paper\ntitle: \xff\xfe\n---\n")
    head = _commit(repo, "invalid utf-8")

    with pytest.raises(ExtractError):
        extract_change_set(repo, base, head)


def test_malformed_frontmatter_is_an_error_not_a_body_only_change(repo: Path):
    """A delimited but unparseable block raises out of `split_frontmatter`; it must
    surface as ExtractError so the CLI can report 'could not evaluate' (exit 2)."""
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, "---\nid: paper:smith2020\nvenue: [unclosed\n---\n\nAbstract.\n")
    head = _commit(repo, "malformed frontmatter")

    with pytest.raises(ExtractError):
        extract_change_set(repo, base, head)


def test_changes_are_ordered_by_path(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, "zzz.txt", "z\n")
    _write(repo, "aaa.txt", "a\n")
    head = _commit(repo, "two files")

    paths = [c.path for c in extract_change_set(repo, base, head).changes]
    assert paths == sorted(paths)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_extract.py -q
```

Expected: `ModuleNotFoundError: No module named 'science_tool.autonomy.extract'`.

- [ ] **Step 3: Write the implementation**

Create `science/src/science_tool/autonomy/extract.py`:

```python
"""Build a `ChangeSet` from a recorded `base..head` commit range.

The range is two-dot (tree to tree) by construction. A merge-base range moves under
rebase and under integration-branch advancement, which is exactly the baseline
instability design §6 rejects -- so `...` must never appear here.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from science_model.frontmatter import split_frontmatter

from science_tool.autonomy.changes import (
    BODY_FIELD,
    ChangeSet,
    ChangeType,
    PathChange,
    entity_kind_for_path,
)

_STATUS_TO_CHANGE_TYPE = {"A": ChangeType.ADDED, "D": ChangeType.DELETED, "M": ChangeType.MODIFIED}


class ExtractError(ValueError):
    """The commit range could not be read. Never degrade this to an empty change set:
    an unreadable range is uncomputable, not clean."""


def _git(repo_root: Path, *args: str) -> bytes:
    """Run one git command with replacement objects DISABLED.

    `--no-replace-objects` is a security control, not a tidiness flag. Ordinary git
    honours `.git/refs/replace`, so an actor able to write the repository can graft one
    commit's content onto another's identity and make `git diff base head` report
    NOTHING while the tree really changed. Reproduced: a commit adding `science.yaml`
    diffs empty after `git replace`, and shows `A science.yaml` with this flag. The flag
    is global and must precede `-C`.
    """
    result = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(repo_root), *args], capture_output=True
    )
    if result.returncode != 0:
        raise ExtractError(
            f"git {' '.join(args)} failed in {repo_root}: {result.stderr.decode('utf-8', 'replace').strip()}"
        )
    return result.stdout


def _require_commit(repo_root: Path, rev: str) -> str:
    return _git(repo_root, "rev-parse", "--verify", f"{rev}^{{commit}}").decode().strip()


def _blob(repo_root: Path, commit: str, path: str) -> str:
    """File text at `commit`. Raises rather than returning a sentinel.

    FAIL-OPEN HAZARD: if an unreadable blob degraded to None, a MODIFIED entity whose
    blobs both failed to read would diff to zero changed fields, and the evaluator
    would ALLOW it. An unreadable blob is uncomputable, never clean -- the same rule
    `graph belief-basis` applies with exit 2. `None` in this module means only "absent
    by construction on one side of an add or a delete".
    """
    raw = _git(repo_root, "show", f"{commit}:{path}")  # raises ExtractError on failure
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractError(f"{path} at {commit} is not utf-8 text: {exc}") from exc


#: Sentinel distinguishing "key absent" from "key present with value None", which are
#: different edits and must not compare equal.
_MISSING = object()


def _changed_fields(before_text: str | None, after_text: str | None) -> tuple[str, ...]:
    """Frontmatter keys that differ, plus BODY_FIELD when the body differs.

    Keys are stringified: a YAML key that is not a string (`true:`, `1:`) becomes a
    field name that is on no allowlist, and is therefore denied rather than crashing.

    A file with NO frontmatter delimiters yields `({}, whole_text)`, so its edit
    surfaces as a BODY_FIELD change -- denied like any other. A file with delimiters
    around MALFORMED yaml is different: `split_frontmatter` calls `yaml.safe_load` and
    lets `yaml.YAMLError` escape. That is converted to `ExtractError` here so the CLI
    reports "could not evaluate" (exit 2) instead of crashing, because a change set we
    cannot parse is uncomputable, not clean.
    """
    try:
        before_fm, before_body = split_frontmatter(before_text) if before_text is not None else ({}, "")
        after_fm, after_body = split_frontmatter(after_text) if after_text is not None else ({}, "")
    except yaml.YAMLError as exc:
        raise ExtractError(f"unparseable frontmatter: {exc}") from exc

    before = {str(key): value for key, value in before_fm.items()}
    after = {str(key): value for key, value in after_fm.items()}
    changed = {
        key
        for key in before.keys() | after.keys()
        if before.get(key, _MISSING) != after.get(key, _MISSING)
    }
    if before_body != after_body:
        changed.add(BODY_FIELD)
    return tuple(sorted(changed))


def extract_change_set(repo_root: Path, base: str, head: str) -> ChangeSet:
    """Diff `base` against `head` and describe every changed path.

    `--no-renames` is deliberate: a rename becomes a deletion plus an addition, which is
    what the gate must decide over, since both halves are independently denied and a
    similarity-scored `R100` would hide the addition.
    """
    base_commit = _require_commit(repo_root, base)
    head_commit = _require_commit(repo_root, head)

    raw = _git(
        repo_root, "diff", "--name-status", "-z", "--no-renames", base_commit, head_commit
    ).decode("utf-8", "replace")
    fields_iter = iter([field for field in raw.split("\0") if field])

    changes: list[PathChange] = []
    for status in fields_iter:
        path = next(fields_iter, None)
        if path is None:
            raise ExtractError(f"git diff emitted a status {status!r} with no path")
        change_type = _STATUS_TO_CHANGE_TYPE.get(status[0])
        if change_type is None:
            raise ExtractError(f"unhandled git diff status {status!r} for {path!r}")

        kind = entity_kind_for_path(path)
        if kind is None:
            changes.append(
                PathChange(path=path, change_type=change_type, entity_kind=None, fields=())
            )
            continue

        before = None if change_type is ChangeType.ADDED else _blob(repo_root, base_commit, path)
        after = None if change_type is ChangeType.DELETED else _blob(repo_root, head_commit, path)
        changes.append(
            PathChange(
                path=path,
                change_type=change_type,
                entity_kind=kind,
                fields=_changed_fields(before, after),
            )
        )

    return ChangeSet(
        base_commit=base_commit,
        head_commit=head_commit,
        changes=tuple(sorted(changes, key=lambda c: c.path)),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_extract.py -q
```

Expected: 15 passed.

- [ ] **Step 5: Lint and type-check**

```bash
cd science && uv run ruff check src/science_tool/autonomy tests/test_autonomy_extract.py && uv run pyright
```

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/autonomy/extract.py science/tests/test_autonomy_extract.py
git commit -m "feat(autonomy): extract change sets from a two-dot commit range"
```

---

### Task 5: CLI command, registration, budget classification, and the CLI map

**Files:**
- Create: `science/src/science_tool/autonomy/cli.py`
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/src/science_tool/budget/registry.py`
- Modify: `docs/user-guide/cli-and-workflows.md`
- Modify: `science/tests/test_budget_boundary.py` (the cardinality lock and its docstring)
- Test: `science/tests/test_autonomy_cli.py`

**Interfaces:**
- Consumes: `extract_change_set` (Task 4), `evaluate` (Task 3), `RunTier`.
- Produces: `autonomy_group` (click group named `autonomy`) with the `path-gate` command.

**Three guard tests break the moment this group is registered.** All three must be
satisfied in this task, not deferred:

1. `test_every_leaf_command_is_classified` — needs a `DEFERRED` entry.
2. `test_classification_partition_has_the_audited_cardinality` — the counts are locked
   at `4/67/207 = 278`; adding one deferred leaf makes it `4/67/208 = 279`. Update
   `EXPECTED_CLASSIFICATION_COUNTS` **and** the docstring sentence that explains why.
3. `test_cli_workflow_map_mentions_every_top_level_command` — needs `autonomy` in a
   backticked span in `docs/user-guide/cli-and-workflows.md`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_autonomy_cli.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main

PAPER = "entities/papers/smith2020.md"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _paper_text(*, venue: str = "Nature", extra: str = "") -> str:
    return f"---\nid: paper:smith2020\nkind: paper\ntitle: T\nvenue: {venue}\n{extra}---\n\nAbstract.\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    _write(tmp_path, PAPER, _paper_text())
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def _run(repo: Path, base: str, head: str, *extra: str):
    return CliRunner().invoke(
        main,
        ["autonomy", "path-gate", "--project-root", str(repo), "--base", base, "--head", head, *extra],
    )


def test_an_allowed_edit_exits_zero(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text(venue="Science"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "venue")
    head = _git(repo, "rev-parse", "HEAD")

    result = _run(repo, base, head)
    assert result.exit_code == 0, result.output
    assert "allowed" in result.output


def test_a_denied_edit_exits_one_and_names_path_and_field(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text(extra="confidence: 0.9\n"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "confidence")
    head = _git(repo, "rev-parse", "HEAD")

    result = _run(repo, base, head)
    assert result.exit_code == 1
    assert PAPER in result.output
    assert "confidence" in result.output


def test_an_unresolvable_commit_exits_two_not_zero(repo: Path):
    """Exit 2 mirrors `graph belief-basis`: a gate that cannot see must not report
    allowed."""
    base = _git(repo, "rev-parse", "HEAD")
    result = _run(repo, base, "0" * 40)
    assert result.exit_code == 2
    assert "could not evaluate" in result.output


def test_malformed_frontmatter_exits_two_not_a_traceback(repo: Path):
    """An unparseable change set is uncomputable, not clean, and must land on the
    exit-2 branch rather than escaping as an unhandled YAMLError."""
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, "---\nid: paper:smith2020\nvenue: [unclosed\n---\n\nAbstract.\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "malformed")
    head = _git(repo, "rev-parse", "HEAD")

    result = _run(repo, base, head)
    assert result.exit_code == 2, result.output
    assert "could not evaluate" in result.output


def test_report_only_denies_an_entity_edit(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text(venue="Science"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "venue")
    head = _git(repo, "rev-parse", "HEAD")

    assert _run(repo, base, head, "--tier", "report-only").exit_code == 1


def test_json_output_carries_the_denials(repo: Path):
    import json

    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text(extra="confidence: 0.9\n"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "confidence")
    head = _git(repo, "rev-parse", "HEAD")

    result = _run(repo, base, head, "--json")
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["allowed"] is False
    assert payload["denials"][0]["field"] == "confidence"


def test_the_command_is_registered_under_the_autonomy_group():
    assert "autonomy" in main.commands
    assert "path-gate" in main.commands["autonomy"].commands  # type: ignore[attr-defined]
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_cli.py -q
```

Expected: every test fails — `autonomy` is not a registered command.

- [ ] **Step 3: Write the CLI**

Create `science/src/science_tool/autonomy/cli.py`:

```python
"""`science autonomy` -- the supervisor-facing surface of the autonomy envelope."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from science_model.autonomous_runs import RunTier


@click.group("autonomy")
def autonomy_group() -> None:
    """Evaluate what an autonomous run was permitted to write."""


@autonomy_group.command("path-gate")
@click.option("--base", required=True, help="Commit the run started from (the recorded baseline).")
@click.option("--head", required=True, help="Commit the run ended at.")
@click.option(
    "--tier",
    type=click.Choice([tier.value for tier in RunTier]),
    default=RunTier.BELIEF_NEUTRAL.value,
    show_default=True,
    help="Tier the run was attested to (design §1).",
)
@click.option(
    "--report-path",
    default=None,
    help="Repository-relative path of the run's own report -- the only path 'report-only' may write.",
)
@click.option(
    "--project-root",
    type=click.Path(path_type=Path),
    default=Path("."),
    show_default=True,
    help="Repository root the range is read from.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit the verdict as JSON.")
def path_gate_command(
    base: str, head: str, tier: str, report_path: str | None, project_root: Path, as_json: bool
) -> None:
    """Decide whether a base..head range stayed inside the tier's write surface.

    Exit codes: 0 allowed, 1 denied, 2 could not evaluate. Exit 2 is explicitly NOT
    allowed -- a gate that cannot see must not report clean (design §5).
    """
    from science_tool.autonomy.extract import ExtractError, extract_change_set
    from science_tool.autonomy.path_gate import GateInputError, evaluate

    try:
        change_set = extract_change_set(project_root, base, head)
        verdict = evaluate(change_set, tier=RunTier(tier), report_path=report_path)
    except (ExtractError, GateInputError) as exc:
        click.echo(f"could not evaluate: {exc}")
        sys.exit(2)

    if as_json:
        click.echo(verdict.model_dump_json(indent=2))
    elif verdict.allowed:
        click.echo(f"allowed: {len(change_set.changes)} change(s) within tier {tier!r}")
    else:
        for denial in verdict.denials:
            location = denial.path if denial.field is None else f"{denial.path} field {denial.field!r}"
            click.echo(f"denied: {location} -- {denial.reason}")

    sys.exit(0 if verdict.allowed else 1)
```

- [ ] **Step 4: Register the group**

In `science/src/science_tool/cli.py`, add the import beside the other group imports and
the registration beside the other `main.add_command(...)` lines (they run from ~line 192):

```python
from science_tool.autonomy.cli import autonomy_group
```

```python
main.add_command(autonomy_group)
```

- [ ] **Step 5: Classify the command in the budget registry**

In `science/src/science_tool/budget/registry.py`, add to the `DEFERRED` literal beside
the `"graph belief-basis"` entry:

```python
    "autonomy path-gate": DeferredCommand(
        "one output member per denial, which grows with the run's change set",
        "1b",
    ),
```

- [ ] **Step 6: Update the cardinality lock**

In `science/tests/test_budget_boundary.py`, bump the deferred count in
`EXPECTED_CLASSIFICATION_COUNTS` from `207` to `208` (total `278` → `279`), and append
this sentence to `test_classification_partition_has_the_audited_cardinality`'s
docstring, immediately before the final "The live partition is therefore" sentence:

```
    The autonomy path-gate command adds one deferred leaf because it emits one row per
    denial, which grows with the run's change set.
```

Then update that final sentence to read `4/67/208 = 279`.

- [ ] **Step 7: Document the group in the CLI workflow map**

In `docs/user-guide/cli-and-workflows.md`, add a row to the `## Command Families` table
(it starts at line 48 with the header `| Family | Class | Write class | Use |`). Place
it immediately after the `patch` row, keeping the existing four-column shape:

```markdown
| `autonomy` | Derived-state | Read-only | Decide whether an autonomous run's recorded `base..head` range stayed inside its tier's default-deny write surface. Reads git and the frozen policy; writes nothing. |
```

`Derived-state` and `Read-only` are both existing tokens in that table's vocabulary —
do not invent new ones. The guard test at `test_user_guide_docs.py:105` extracts the
word after `science` from backticked spans, and also accepts a lone backticked token,
so the bare `` `autonomy` `` in the Family column satisfies it.

- [ ] **Step 8: Run the tests**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_cli.py tests/test_budget_boundary.py tests/test_user_guide_docs.py -q
```

Expected: all pass. If `test_cli_workflow_map_mentions_every_top_level_command` still
fails, the backticked span in the doc does not start with `science autonomy` — re-read
the test at `test_user_guide_docs.py:105` to see how spans are parsed.

- [ ] **Step 9: Lint and type-check**

```bash
cd science && uv run ruff check src/science_tool tests && uv run pyright
```

- [ ] **Step 10: Commit**

```bash
git add science/src/science_tool/autonomy/cli.py science/src/science_tool/cli.py \
        science/src/science_tool/budget/registry.py science/tests/test_autonomy_cli.py \
        science/tests/test_budget_boundary.py docs/user-guide/cli-and-workflows.md
git commit -m "feat(autonomy): add science autonomy path-gate command"
```

---

### Task 6: Layer 3 — the one-way perturbation alarm

**Files:**
- Test: `science/tests/test_autonomy_perturbation_alarm.py`

This task ships **no source module**. Layer 3 is a test suite by design: its only
authority is to *remove* a field from the allowlist, and a shipped API would invite the
write-back path Global Constraint 3 forbids.

**Interfaces:**
- Consumes: `FIELD_ALLOWLIST`, `is_field_allowed` (Task 1); `capture_basis`,
  `compare_bases` from `science_tool.graph.belief_basis`; the `science graph build` CLI.

**The vacuity trap.** `capture_basis` returns `InstrumentResult.unwired` when
`graph/knowledge` holds no typed project entity, and a fixture with no evidence line
produces rows with empty `unit_keys` — in either case every perturbation "passes" while
proving nothing. The fixture below therefore carries a proposition, a paper, and a
belief-eligible evidence line, and `test_the_alarm_fires_on_a_belief_bearing_field`
certifies that the harness can fail. **Do not simplify the fixture.**

- [ ] **Step 1: Write the alarm**

Create `science/tests/test_autonomy_perturbation_alarm.py`:

```python
"""Layer 3 of design §5: the one-way perturbation alarm.

Perturb every ALLOWED field across a representative context. If a perturbation changes
the belief basis, this suite FAILS and the field must come off the allowlist.

The inverse is deliberately NOT asserted: observing no change never makes a field
writable (design §5 Layer 4 -- promotion requires human review of the materialization
path, and mutation results alone cannot authorize it). This asymmetry is what makes the
alarm sound despite perturbation being incomplete: a false negative can only ever leave
a field denied.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import Dataset

from science_tool.autonomy.policy import FIELD_ALLOWLIST, is_field_allowed
from science_tool.cli import main
from science_tool.graph.belief_basis import capture_basis, compare_bases
from science_tool.graph.io import PROJECT_NS

#: (kind, field, perturbed value as a RAW YAML FRAGMENT). One case per allowlist entry
#: -- `test_every_allowlisted_field_has_a_perturbation_case` is the ratchet that makes
#: an unalarmed allowlist entry impossible.
#:
#: The third element is spliced into the document verbatim, so its YAML type must match
#: the model's. `pmid` and `isbn` are `str` on the entity model, and unquoted `99999999`
#: parses as an int, which pydantic REJECTS -- so those values carry explicit quotes.
#: `year` and `duration_minutes` are `int | None` and must stay unquoted.
PERTURBATIONS: tuple[tuple[str, str, str], ...] = (
    ("paper", "venue", "Journal of Perturbation"),
    ("paper", "pmid", '"99999999"'),
    ("paper", "year", "1999"),
    ("paper", "url", "https://example.org/perturbed"),
    ("book", "publisher", "Perturbation Press"),
    ("book", "isbn", '"978-0-00-000000-0"'),
    ("book", "year", "1999"),
    ("book", "url", "https://example.org/perturbed-book"),
    ("talk", "venue", "Perturbation Symposium"),
    ("talk", "duration_minutes", "45"),
)

#: Where each perturbable kind's fixture entity lives, and its authored frontmatter.
_FIXTURE_ENTITIES: dict[str, tuple[str, str]] = {
    # `pmid` and `isbn` are quoted: unquoted digits parse as int and pydantic rejects
    # an int for a `str` field, so the fixture would fail to materialize at all.
    "paper": (
        "entities/papers/x.md",
        'id: paper:x\nkind: paper\ntitle: X\nvenue: Nature\npmid: "111"\nyear: 2020\nurl: https://example.org/x\n',
    ),
    "book": (
        "entities/books/b.md",
        'id: book:b\nkind: book\ntitle: B\npublisher: Old Press\nisbn: "978-1-11-111111-1"\nyear: 2019\nurl: https://example.org/b\n',
    ),
    "talk": (
        "entities/talks/t.md",
        "id: talk:t\nkind: talk\ntitle: T\nvenue: Old Venue\nduration_minutes: 30\n",
    ),
}


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_project(root: Path) -> None:
    """A project with a real, non-empty belief basis plus one entity of every
    perturbable kind."""
    _write(root, "science.yaml", "name: perturbation-fixture\nknowledge_profiles:\n  local: local\n")
    _write(root, "entities/propositions/p1.md", "---\nid: proposition:p1\nkind: proposition\ntitle: P1\n---\n\nClaim.\n")
    _write(
        root,
        "entities/evidence-lines/e1.md",
        "---\n"
        "id: evidence-line:e1\n"
        "kind: evidence-line\n"
        "title: Evidence line\n"
        "stance: supports\n"
        "target: proposition:p1\n"
        "source: paper:x\n"
        "strength: strong\n"
        "belief_eligible: true\n"
        "---\n",
    )
    for rel, frontmatter in _FIXTURE_ENTITIES.values():
        _write(root, rel, f"---\n{frontmatter}---\n\nBody.\n")


def _build_and_capture(root: Path):
    result = CliRunner().invoke(main, ["graph", "build", "--project-root", str(root)])
    assert result.exit_code == 0, f"graph build failed:\n{result.output}"

    dataset = Dataset()
    dataset.parse(source=str(root / "knowledge" / "graph.trig"), format="trig")
    captured = capture_basis(
        dataset.graph(PROJECT_NS["graph/knowledge"]),
        dataset.graph(PROJECT_NS["graph/provenance"]),
    )
    assert captured.status != "unwired", f"fixture produced no basis: {captured.reason}"
    return captured.rows


def _perturb_field(root: Path, rel: str, field: str, value: str) -> None:
    text = (root / rel).read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith(f"{field}:"):
            lines[index] = f"{field}: {value}\n"
            break
    else:  # a field the fixture does not author is a fixture bug, not a passing case
        raise AssertionError(f"{rel} does not author {field!r}; the fixture cannot perturb it")
    (root / rel).write_text("".join(lines), encoding="utf-8")


@pytest.fixture
def seeded(tmp_path: Path):
    _seed_project(tmp_path)
    return tmp_path


def test_every_allowlisted_field_has_a_perturbation_case():
    """The ratchet: adding an allowlist entry without an alarm case fails HERE, before
    any promotion can happen."""
    covered = {(kind, field) for kind, field, _ in PERTURBATIONS}
    declared = {(kind, field) for kind, fields in FIELD_ALLOWLIST.items() for field in fields}
    assert covered == declared


def test_the_fixture_has_a_non_empty_basis(seeded: Path):
    """Certification: without a real evidence unit, every case below would pass
    vacuously."""
    rows = _build_and_capture(seeded)
    assert any(row.unit_keys for row in rows), "fixture yields no evidence units"


@pytest.mark.parametrize(("kind", "field", "value"), PERTURBATIONS, ids=lambda v: str(v))
def test_an_allowed_field_does_not_move_the_belief_basis(seeded: Path, kind: str, field: str, value: str):
    rel, _ = _FIXTURE_ENTITIES[kind]
    before = _build_and_capture(seeded)
    _perturb_field(seeded, rel, field, value)
    after = _build_and_capture(seeded)

    deltas = compare_bases(before, after)
    assert deltas == [], (
        f"{kind}.{field} moved the belief basis: {deltas}. Design §5 Layer 3: take it OFF "
        "FIELD_ALLOWLIST -- do not weaken this assertion."
    )


def test_the_alarm_fires_on_a_belief_bearing_field(seeded: Path):
    """Certification that the harness CAN fail. An evidence line's `strength` feeds
    `EvidenceUnit`, so perturbing it must move the basis. If this ever passes, every
    case above is meaningless."""
    before = _build_and_capture(seeded)
    _perturb_field(seeded, "entities/evidence-lines/e1.md", "strength", "weak")
    after = _build_and_capture(seeded)

    assert compare_bases(before, after) != []


def test_a_neutral_denied_field_stays_denied(seeded: Path):
    """Design §5 Layer 3, the one-way property. `methods_summary` moves nothing -- and
    that observation must NOT promote it. Overbreadth is an accepted, visible cost."""
    before = _build_and_capture(seeded)
    _write(
        seeded,
        "entities/papers/x.md",
        (seeded / "entities/papers/x.md").read_text(encoding="utf-8").replace(
            "venue: Nature\n", "venue: Nature\nmethods_summary: Rewritten by a run.\n"
        ),
    )
    after = _build_and_capture(seeded)

    assert compare_bases(before, after) == []
    assert is_field_allowed("paper", "methods_summary") is False
```

- [ ] **Step 2: Run the alarm**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_perturbation_alarm.py -q
```

Expected: all pass.

**If `test_an_allowed_field_does_not_move_the_belief_basis` fails for a field:** that is
the alarm working. Remove the field from `FIELD_ALLOWLIST` and from `PERTURBATIONS`,
record which field and what moved in your report, and continue. **Do not** relax the
assertion, and do not special-case the field.

**If `graph build` rejects a fixture entity:** `paper`, `book`, and `talk` all use the
`citekey` filename strategy, so `x.md` / `b.md` / `t.md` may not conform. Check
`local_part_conforms(kind, local_part)` in `science/src/science_tool/entities.py:382`
and rename the fixture files (and their `id:` values) to conforming citekeys such as
`smith2020`. Adjust `_FIXTURE_ENTITIES` and the evidence line's `source:` ref together —
they must stay consistent or the line's target closure will not resolve.

**If `test_the_alarm_fires_on_a_belief_bearing_field` fails:** the fixture is not
producing a real evidence unit, so the whole suite is vacuous. Check that
`belief_eligible: true` and the `target`/`source` refs resolve — read
`science/tests/conftest.py:288` (`materialized_knowledge_for_evidence_line`), which
builds a working version of this shape. Fix the fixture; do not delete the test.

- [ ] **Step 3: Lint**

```bash
cd science && uv run ruff check tests/test_autonomy_perturbation_alarm.py
```

- [ ] **Step 4: Commit**

```bash
git add science/tests/test_autonomy_perturbation_alarm.py
git commit -m "test(autonomy): add one-way perturbation alarm for allowlisted fields"
```

---

### Task 7: Documentation

**Files:**
- Modify: `docs/user-guide/agent-workflows.md`
- Modify: `docs/plans/2026-07-24-autonomy-envelope-design.md`

- [ ] **Step 1: Document the gate in the user guide**

Read `docs/user-guide/agent-workflows.md` first and match its heading level and prose
style. Append the section below. **The outer fence here is four backticks** because the
content itself contains a three-backtick `bash` block — write the inner block into the
document as a normal three-backtick fence, and do not copy the outer fence.

````markdown
## The autonomy path gate

An unattended run is confined to a write surface decided by
`science autonomy path-gate`, which compares the run's recorded `base..head` commit
range against a **default-deny** policy: every repository path, and every entity
frontmatter field, that is not explicitly allowed is denied — including fields nobody
has invented yet.

```bash
science autonomy path-gate --base <sha> --head <sha> --tier belief-neutral
```

Exit `0` means every change was inside the tier's surface, `1` means something was not
(each denial names the path, the field, and the reason), and `2` means the range could
not be read. Exit `2` is deliberately not exit `0`: a gate that cannot see must not
report clean.

Two tiers exist. `report-only` may write only the run's own report path. `belief-neutral`
may additionally edit allowlisted fields on pre-existing entities. There is no third
tier — changing belief is human work by definition.

The allowlist is small on purpose and is **not project-overridable**. A field is added
only after a human traces its materialization path and its belief dependencies; a
perturbation test that observes no movement is not sufficient grounds. The reverse is
automatic: if perturbing an allowed field is ever found to move the belief basis, the
field comes off the list.

The gate is one of four layers. It is syntactic and complete by construction, but it
does not prove belief-neutrality — `science graph belief-basis` does that, and it is
authoritative precisely because it does not depend on this allowlist being correct.
````

- [ ] **Step 2: Record the implementation rulings in the design doc**

In `docs/plans/2026-07-24-autonomy-envelope-design.md`, append to §4 (after the
"Non-entity paths" table, before §5) a blockquote in the same style as Plan B's notes:

```markdown
> **Revised during implementation (Plan C).** Four rulings the design did not settle:
>
> 1. **The seed allowlist is `paper` / `book` / `talk` bibliographic fields only** —
>    `venue`, `pmid`, `publisher`, `isbn`, `duration_minutes` (which materialize no
>    triple at all) plus `year` and `url` on `paper`/`book` (which materialize to
>    `dcterms:date` and `dcat:downloadURL` in `graph/knowledge`, and are read by no
>    evidence unit and no target closure). Every entry is covered by a Layer 3 case,
>    enforced by a ratchet test that fails when an entry has none.
> 2. **`aliases` is denied.** It feeds reference resolution (`graph/sources.py:787-793`),
>    so an alias can re-point a reference and move the target closure. `doi` is denied
>    too, as identity-adjacent — accepted overbreadth per §4.
> 3. **`task` fields cannot be gated at all.** `task` has no markdown home
>    (`CORE_PROFILE`: `home=None`), so it has no frontmatter file for a path-and-field
>    gate to decide over. Extending the gate to structured sources is a separate design
>    conversation.
> 4. **Entity kind is derived from the path, never from the file's own `kind:`
>    frontmatter**, and renames are extracted as deletion-plus-addition (`--no-renames`).
>    An actor that could choose its own kind could choose its own allowlist; a
>    similarity-scored rename would hide the addition half.
```

- [ ] **Step 3: Verify the docs guards still pass**

```bash
cd science && uv run --frozen pytest tests/test_user_guide_docs.py tests/test_command_docs.py -q
```

- [ ] **Step 4: Commit**

```bash
git add docs/user-guide/agent-workflows.md docs/plans/2026-07-24-autonomy-envelope-design.md
git commit -m "docs(autonomy): document the path gate and record Plan C rulings"
```

---

## Final verification

Run before finishing the branch, from the repository root. Each line is a **subshell**:
a bare `cd science` followed by `cd science/model` would resolve to
`science/science/model` and fail, because the working directory persists.

```bash
(cd science && uv run --frozen pytest)          # timeout: 600000
(cd science/model && uv run --frozen pytest)    # timeout: 600000
(cd science && uv run ruff check && uv run pyright)
(cd science/model && uv run ruff check)
```

The same applies to the per-task `cd science && ...` steps if you run several in one
shell — wrap them or return to the repository root between commands.

## Design-test coverage

Which numbered test from the design's Testing section each task discharges. Tests 1, 2,
3, 6, 8, 9, 10, and 11 belong to Plans A, B, and D and are **not** in scope here.

| Design test | Where |
|---|---|
| 4 — default-deny with no registration and no test edit | Task 1 `test_an_unregistered_field_is_denied_with_no_registration`; Task 3 `test_a_field_nobody_registered_is_denied_with_no_test_edit` |
| 5 — one-way alarm asymmetry | Task 6 `test_an_allowed_field_does_not_move_the_belief_basis` (the forward direction) and `test_a_neutral_denied_field_stays_denied` (the withheld inverse) |
| 7 — gate independence from the worktree, partial | Task 1 `test_policy_module_reads_no_project_state` covers the policy half. The pinned-installation half is Plan D's, since it is a property of how the supervisor invokes the gate, not of the gate. |
