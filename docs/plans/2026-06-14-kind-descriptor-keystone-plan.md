# Kind Descriptor Keystone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a single per-kind descriptor manifest in `science_model` and rewire the four kind-keyed dicts in `science_tool/entities.py` to derive from it, deleting the hand-maintained literals — with zero behavior change.

**Architecture:** A new `science_model/kinds.py` holds a frozen `KindDescriptor` dataclass and a `CORE_KINDS` manifest (one entry per file-authored core kind — the kinds with a built-in path policy), plus the `EntityFilenameStrategy` literal moved up from the tool layer. `science_tool/entities.py` rebuilds `_BUILTIN_MARKDOWN_POLICIES`, `_DEFAULT_STATUS`, `_STATUS_VALUES`, and `_SHORTFORM_ENTITY_KINDS` as comprehensions over `CORE_KINDS` (reusing the existing names so no downstream reference changes). A guard test pins the derived dicts to frozen copies of today's literals.

**Tech Stack:** Python 3.13, frozen dataclasses, pytest, uv workspace (`science_model` is a workspace member; the tool depends on the model, never the reverse).

**Design spec:** `~/d/science/docs/plans/2026-06-14-kind-descriptor-keystone-design.md`

---

## Scope decision (matches design §1 roster-scope + §5)

**`CORE_KINDS` in the keystone contains exactly the 28 file-authored kinds — the union of the four dicts — and nothing else.** "File-authored" = the kinds carrying a built-in path policy: 26 markdown-authored kinds plus two singletons (`research-question`, a markdown file; `claim-registry`, a YAML file). Non-file-authored `EntityType` members (`dataset`, `task`, `workflow-run`, `code-file`, …) are **not** listed.

Rationale (design §1, §2): the two sets already drift in **both** directions —

- `EntityType` has members with no path policy (e.g. `dataset`, `task`, `workflow-run`, `code-file`).
- The four dicts configure six kinds that are **not** `EntityType` members (`pre-registration`, `construct`, `decision`, `outcome`, `research-question`, `claim-registry`).

Enumerating empty non-file-authored descriptors would transcribe data no keystone consumer reads (design §2). The full `EntityType` reconciliation is deferred to increment 2 (the registry), where `entity_class`/`model_class` bind kinds to `EntityType`. The validation test therefore asserts dict-coverage and self-consistency, **not** equality with `EntityType`.

## Migration path: how `CORE_KINDS` relates to `ProfileManifest` / `CORE_PROFILE`

The broader Spec 2 direction is "extend `EntityKind` as the SSOT; derive everything," and `EntityKind` (in `science_model/profiles/schema.py`) already carries `home` / `strategy` / `default_status` / `statuses`. `CORE_KINDS` is therefore a **transitional typed manifest, not a permanent parallel surface**: increment 3 (which owns the profile system) folds `CORE_PROFILE`/`EntityKind` onto these descriptors so there is **one** descriptor per kind — `EntityKind` gains the typed precision (`Path`, `frozenset` statuses) and any kinds it is missing, and `CORE_KINDS` is absorbed and deleted. The keystone stands up a separate dataclass now (rather than extending `CORE_PROFILE` immediately) solely to isolate risk: touching `CORE_PROFILE` pulls in templates, `MIGRATED_KINDS`, and profile reconciliation, all explicitly deferred. The keystone commits that `CORE_KINDS` does **not** survive as a second manifest alongside `CORE_PROFILE`.

## File Structure

- **Create** `science/model/src/science_model/kinds.py` — `EntityFilenameStrategy`, `KindDescriptor`, `CORE_KINDS`, `CORE_KINDS_BY_NAME`. The kind SSOT, model layer.
- **Create** `science/model/tests/test_kinds.py` — descriptor self-consistency (model-layer test; imports only `science_model`).
- **Create** `science/tests/test_kind_descriptor_derivation.py` — zero-behavior-change guard (tool-layer test; frozen copies of the four literals reconstructed from `CORE_KINDS`).
- **Modify** `science/src/science_tool/entities.py` — delete the `EntityFilenameStrategy` literal (import from `science_model.kinds`); replace the four literal dicts with comprehensions over `CORE_KINDS`, keeping the existing variable names.

## Conventions for every task

- All `pytest` runs are from the `science/` workspace subdir: `cd science && uv run --frozen pytest <path> -v`. Running from the repo root fails with `ModuleNotFoundError: No module named 'science_model'`. Keep `uv run --frozen pytest` (do **not** substitute `rtk pytest`): the uv workspace env is required for `science_model`/`science_tool` resolution, and `rtk pytest` collects 0 tests under this workspace. `uv` is not an rtk subcommand, so the rtk hook leaves it untouched.
- Other agent-facing shell commands use `rtk` forms (`rtk git …`, `rtk grep …`) for compact, token-optimized output, per the repo's `RTK.md`.
- Model-layer code/tests must import only from `science_model.*` (never `science_tool.*`).
- Commit after each task. Do **not** push. Do **not** add `Co-Authored-By` trailers.

---

### Task 1: Kind descriptor module + self-consistency test

**Files:**
- Create: `science/model/src/science_model/kinds.py`
- Test: `science/model/tests/test_kinds.py`

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_kinds.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_model.kinds import CORE_KINDS, CORE_KINDS_BY_NAME, KindDescriptor


def test_core_kinds_have_unique_names() -> None:
    names = [k.name for k in CORE_KINDS]
    assert len(names) == len(set(names)), "duplicate kind name in CORE_KINDS"
    assert set(CORE_KINDS_BY_NAME) == set(names)
    assert all(isinstance(k, KindDescriptor) for k in CORE_KINDS)


def test_every_descriptor_sets_path_and_strategy() -> None:
    # Keystone CORE_KINDS = file-authored kinds only; all carry path+strategy.
    for k in CORE_KINDS:
        assert k.path is not None, f"{k.name} missing path"
        assert k.strategy is not None, f"{k.name} missing strategy"


def test_singleton_iff_path_is_a_file() -> None:
    for k in CORE_KINDS:
        assert k.path is not None  # narrows Path | None before .suffix
        is_file = k.path.suffix in {".md", ".yaml"}
        assert (k.strategy == "singleton") == is_file, (
            f"{k.name}: strategy/singleton mismatch (path={k.path}, strategy={k.strategy})"
        )


def test_singletons_have_no_status_vocabulary() -> None:
    for k in CORE_KINDS:
        if k.strategy == "singleton":
            assert k.statuses is None and k.default_status is None, (
                f"singleton {k.name} should not declare statuses/default_status"
            )


def test_default_status_is_a_member_of_statuses() -> None:
    for k in CORE_KINDS:
        if k.default_status is not None:
            assert k.statuses is not None, f"{k.name} has default_status but no statuses"
            assert k.default_status in k.statuses, (
                f"{k.name} default_status {k.default_status!r} not in statuses"
            )


def test_shortforms_are_unique_single_characters() -> None:
    shortforms = [k.shortform for k in CORE_KINDS if k.shortform is not None]
    assert all(len(s) == 1 for s in shortforms), "shortform must be a single character"
    assert len(shortforms) == len(set(shortforms)), "duplicate shortform"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest model/tests/test_kinds.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_model.kinds'`.

- [ ] **Step 3: Write the descriptor module**

Create `science/model/src/science_model/kinds.py`:

```python
"""Single source of truth for per-kind metadata (the kind descriptor manifest).

Every per-kind structure in the tool layer (path policies, default statuses,
status vocabularies, shortform aliases) derives from ``CORE_KINDS``. This module
is the kind SSOT and lives in ``science_model`` so the tool can depend on it.

Keystone scope: ``CORE_KINDS`` enumerates the file-authored core kinds only (the
kinds with a built-in path policy: markdown-authored kinds plus the two singletons).
Non-markdown ``EntityType`` members and the ``model_class`` / ``entity_class`` /
``template`` descriptor fields are deferred to later increments (design §6).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# Moved here from science_tool/entities.py: the filename-strategy vocabulary is
# part of the kind SSOT. The tool imports it from this module.
EntityFilenameStrategy = Literal["numeric", "citekey", "singleton", "slug", "verbatim"]


@dataclass(frozen=True)
class KindDescriptor:
    name: str                                       # canonical kind, e.g. "hypothesis"
    path: Path | None = None                        # file home: a dir, or a file for singletons
    strategy: EntityFilenameStrategy | None = None  # filename strategy; None for non-file-authored kinds
    statuses: frozenset[str] | None = None          # controlled status vocab; None = open set
    default_status: str | None = None
    shortform: str | None = None                    # single-letter alias, e.g. "h" -> hypothesis


CORE_KINDS: tuple[KindDescriptor, ...] = (
    KindDescriptor(
        name="question",
        path=Path("entities/questions"),
        strategy="numeric",
        statuses=frozenset({"active", "partially-answered", "answered", "deferred", "retired"}),
        default_status="active",
        shortform="q",
    ),
    KindDescriptor(
        name="hypothesis",
        path=Path("entities/hypotheses"),
        strategy="numeric",
        statuses=frozenset(
            {"proposed", "under-investigation", "partially-supported", "supported", "weakened", "refuted"}
        ),
        default_status="proposed",
        shortform="h",
    ),
    KindDescriptor(
        name="patch-definition",
        path=Path("entities/patches"),
        strategy="slug",
        statuses=frozenset({"active", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="proposition",
        path=Path("entities/propositions"),
        strategy="slug",
        statuses=frozenset(
            {"draft", "active", "supported", "contested", "weakened", "retired", "superseded"}
        ),
        default_status="draft",
        shortform="p",
    ),
    KindDescriptor(
        name="interpretation",
        path=Path("entities/interpretations"),
        strategy="numeric",
        statuses=frozenset({"active", "complete", "superseded"}),
        default_status="active",
        shortform="i",
    ),
    KindDescriptor(
        name="discussion",
        path=Path("entities/discussions"),
        strategy="numeric",
        statuses=frozenset({"active", "complete", "superseded"}),
        default_status="active",
        shortform="d",
    ),
    KindDescriptor(
        name="finding",
        path=Path("entities/findings"),
        strategy="numeric",
        statuses=frozenset({"active", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="inquiry",
        path=Path("entities/inquiries"),
        strategy="numeric",
        statuses=frozenset({"active", "complete", "superseded"}),
        default_status="active",
    ),
    KindDescriptor(
        name="theme",
        path=Path("entities/themes"),
        strategy="numeric",
        statuses=frozenset({"draft", "active", "superseded", "retired"}),
        default_status="active",
        shortform="t",
    ),
    KindDescriptor(
        name="topic",
        path=Path("entities/topics"),
        strategy="slug",  # was "numeric" (4c: slug identity kind)
        statuses=frozenset({"active", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="evidence-line",
        path=Path("entities/evidence-lines"),
        strategy="slug",
        statuses=frozenset({"draft", "active", "retired"}),
        default_status="draft",
    ),
    KindDescriptor(
        name="observation",
        path=Path("entities/observations"),
        strategy="slug",  # was "numeric": observations carry descriptive slug ids (e.g. observation:swan-stage-shift); enables id-preserving single-type aggregate retirement (§B5)
        statuses=frozenset({"active", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="mechanism",
        path=Path("entities/mechanisms"),
        strategy="numeric",
        statuses=frozenset({"active", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="synthesis",
        path=Path("entities/synthesis"),
        strategy="numeric",
        statuses=frozenset({"active", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="report",
        path=Path("entities/reports"),
        strategy="numeric",
        statuses=frozenset({"active", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="plan",
        path=Path("entities/plans"),
        strategy="numeric",
        statuses=frozenset({"active", "complete", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="search",
        path=Path("entities/searches"),
        strategy="numeric",
        statuses=frozenset({"active", "complete", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="method",
        path=Path("entities/methods"),
        strategy="slug",  # was "numeric" (4c: slug identity kind)
        statuses=frozenset({"active", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="pre-registration",
        path=Path("entities/pre-registrations"),
        strategy="numeric",
        statuses=frozenset({"active", "amended", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="concept",
        path=Path("entities/concepts"),
        strategy="slug",
        statuses=frozenset({"active", "deprecated"}),
        default_status="active",
    ),
    KindDescriptor(
        name="construct",
        path=Path("entities/constructs"),
        strategy="slug",
        statuses=frozenset({"active", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="decision",
        path=Path("entities/decision"),
        strategy="verbatim",
        statuses=frozenset({"active", "superseded", "abandoned"}),
        default_status="active",
    ),
    KindDescriptor(
        name="paper",
        path=Path("entities/papers"),
        strategy="citekey",
        statuses=frozenset({"active", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="book",
        path=Path("entities/books"),
        strategy="citekey",
        statuses=frozenset({"active", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="talk",
        path=Path("entities/talks"),
        strategy="citekey",
        statuses=frozenset({"active", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="outcome",
        path=Path("entities/outcomes"),
        strategy="slug",
        statuses=frozenset({"active", "retired"}),
        default_status="active",
    ),
    # Singletons: `path` is the file path itself, not a directory. No per-instance
    # status vocabulary or default status.
    KindDescriptor(
        name="research-question",
        path=Path("entities/research-question.md"),
        strategy="singleton",
    ),
    KindDescriptor(
        name="claim-registry",
        path=Path("entities/claim-registry.yaml"),
        strategy="singleton",
    ),
)

CORE_KINDS_BY_NAME: dict[str, KindDescriptor] = {k.name: k for k in CORE_KINDS}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest model/tests/test_kinds.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
rtk git add science/model/src/science_model/kinds.py science/model/tests/test_kinds.py
rtk git commit -m "feat(model): add kind descriptor manifest (CORE_KINDS) as kind SSOT"
```

---

### Task 2: Zero-behavior-change guard test (proves CORE_KINDS reproduces today's literals)

This test pastes frozen copies of the four current literals and asserts **both** (a) the *live* dicts in `science_tool.entities` and (b) the dicts reconstructed from `CORE_KINDS` equal those frozen copies. Written **before** the rewiring: pre-rewire, assertion (a) proves the frozen copies faithfully transcribe today's literals, while (b) proves `CORE_KINDS` matches the frozen copies — together they prove `CORE_KINDS == literal` *transitively*, closing the gap where the frozen copy and `CORE_KINDS` could share an identical transcription mistake. Post-rewire the live dicts *are* the `CORE_KINDS`-derived comprehensions (same variable names survive Task 3), so both assertions continue to hold.

**Files:**
- Test: `science/tests/test_kind_descriptor_derivation.py`

- [ ] **Step 1: Write the test**

Create `science/tests/test_kind_descriptor_derivation.py`:

```python
"""Guard: the four kind-keyed dicts in science_tool/entities.py must be exactly
reproducible from science_model.kinds.CORE_KINDS, and must match today's literals.
Frozen copies of today's literals are pasted here; each test asserts BOTH the live
dict and the CORE_KINDS-derived dict equal the frozen copy, so a shared transcription
mistake between CORE_KINDS and the frozen copy cannot pass silently.
"""

from __future__ import annotations

from pathlib import Path

from science_model.kinds import CORE_KINDS
from science_tool.entities import (
    EntityPathPolicy,
    _BUILTIN_MARKDOWN_POLICIES,
    _DEFAULT_STATUS,
    _SHORTFORM_ENTITY_KINDS,
    _STATUS_VALUES,
)

# --- Frozen copies of the original literals (do not edit to match drift) ---

FROZEN_MARKDOWN_POLICIES = {
    "question": EntityPathPolicy(Path("entities/questions"), "numeric"),
    "hypothesis": EntityPathPolicy(Path("entities/hypotheses"), "numeric"),
    "patch-definition": EntityPathPolicy(Path("entities/patches"), "slug"),
    "proposition": EntityPathPolicy(Path("entities/propositions"), "slug"),
    "interpretation": EntityPathPolicy(Path("entities/interpretations"), "numeric"),
    "discussion": EntityPathPolicy(Path("entities/discussions"), "numeric"),
    "finding": EntityPathPolicy(Path("entities/findings"), "numeric"),
    "inquiry": EntityPathPolicy(Path("entities/inquiries"), "numeric"),
    "theme": EntityPathPolicy(Path("entities/themes"), "numeric"),
    "topic": EntityPathPolicy(Path("entities/topics"), "slug"),
    "evidence-line": EntityPathPolicy(Path("entities/evidence-lines"), "slug"),
    "observation": EntityPathPolicy(Path("entities/observations"), "slug"),
    "mechanism": EntityPathPolicy(Path("entities/mechanisms"), "numeric"),
    "synthesis": EntityPathPolicy(Path("entities/synthesis"), "numeric"),
    "report": EntityPathPolicy(Path("entities/reports"), "numeric"),
    "plan": EntityPathPolicy(Path("entities/plans"), "numeric"),
    "search": EntityPathPolicy(Path("entities/searches"), "numeric"),
    "method": EntityPathPolicy(Path("entities/methods"), "slug"),
    "pre-registration": EntityPathPolicy(Path("entities/pre-registrations"), "numeric"),
    "concept": EntityPathPolicy(Path("entities/concepts"), "slug"),
    "construct": EntityPathPolicy(Path("entities/constructs"), "slug"),
    "decision": EntityPathPolicy(Path("entities/decision"), "verbatim"),
    "paper": EntityPathPolicy(Path("entities/papers"), "citekey"),
    "book": EntityPathPolicy(Path("entities/books"), "citekey"),
    "talk": EntityPathPolicy(Path("entities/talks"), "citekey"),
    "outcome": EntityPathPolicy(Path("entities/outcomes"), "slug"),
    "research-question": EntityPathPolicy(Path("entities/research-question.md"), "singleton"),
    "claim-registry": EntityPathPolicy(Path("entities/claim-registry.yaml"), "singleton"),
}

FROZEN_DEFAULT_STATUS = {
    "evidence-line": "draft",
    "question": "active",
    "hypothesis": "proposed",
    "discussion": "active",
    "interpretation": "active",
    "theme": "active",
    "patch-definition": "active",
    "proposition": "draft",
    "finding": "active",
    "inquiry": "active",
    "topic": "active",
    "observation": "active",
    "mechanism": "active",
    "synthesis": "active",
    "report": "active",
    "plan": "active",
    "search": "active",
    "method": "active",
    "pre-registration": "active",
    "paper": "active",
    "book": "active",
    "talk": "active",
    "concept": "active",
    "construct": "active",
    "decision": "active",
    "outcome": "active",
}

FROZEN_STATUS_VALUES = {
    "evidence-line": frozenset({"draft", "active", "retired"}),
    "question": frozenset({"active", "partially-answered", "answered", "deferred", "retired"}),
    "hypothesis": frozenset(
        {"proposed", "under-investigation", "partially-supported", "supported", "weakened", "refuted"}
    ),
    "discussion": frozenset({"active", "complete", "superseded"}),
    "interpretation": frozenset({"active", "complete", "superseded"}),
    "theme": frozenset({"draft", "active", "superseded", "retired"}),
    "patch-definition": frozenset({"active", "retired"}),
    "proposition": frozenset(
        {"draft", "active", "supported", "contested", "weakened", "retired", "superseded"}
    ),
    "finding": frozenset({"active", "superseded", "retired"}),
    "inquiry": frozenset({"active", "complete", "superseded"}),
    "topic": frozenset({"active", "superseded", "retired"}),
    "observation": frozenset({"active", "superseded", "retired"}),
    "mechanism": frozenset({"active", "superseded", "retired"}),
    "synthesis": frozenset({"active", "superseded", "retired"}),
    "report": frozenset({"active", "superseded", "retired"}),
    "plan": frozenset({"active", "complete", "superseded", "retired"}),
    "search": frozenset({"active", "complete", "retired"}),
    "method": frozenset({"active", "superseded", "retired"}),
    "pre-registration": frozenset({"active", "amended", "superseded", "retired"}),
    "paper": frozenset({"active", "retired"}),
    "book": frozenset({"active", "retired"}),
    "talk": frozenset({"active", "retired"}),
    "concept": frozenset({"active", "deprecated"}),
    "construct": frozenset({"active", "retired"}),
    "decision": frozenset({"active", "superseded", "abandoned"}),
    "outcome": frozenset({"active", "retired"}),
}

FROZEN_SHORTFORM = {
    "d": "discussion",
    "h": "hypothesis",
    "i": "interpretation",
    "p": "proposition",
    "q": "question",
    "t": "theme",
}


def test_markdown_policies_reconstruct_from_descriptors() -> None:
    assert _BUILTIN_MARKDOWN_POLICIES == FROZEN_MARKDOWN_POLICIES  # live == frozen
    derived = {
        k.name: EntityPathPolicy(k.path, k.strategy)
        for k in CORE_KINDS
        if k.path is not None and k.strategy is not None
    }
    assert derived == FROZEN_MARKDOWN_POLICIES  # CORE_KINDS == frozen


def test_default_status_reconstructs_from_descriptors() -> None:
    assert _DEFAULT_STATUS == FROZEN_DEFAULT_STATUS  # live == frozen
    derived = {k.name: k.default_status for k in CORE_KINDS if k.default_status}
    assert derived == FROZEN_DEFAULT_STATUS  # CORE_KINDS == frozen


def test_status_values_reconstruct_from_descriptors() -> None:
    assert _STATUS_VALUES == FROZEN_STATUS_VALUES  # live == frozen
    derived = {k.name: k.statuses for k in CORE_KINDS if k.statuses}
    assert derived == FROZEN_STATUS_VALUES  # CORE_KINDS == frozen


def test_shortforms_reconstruct_from_descriptors() -> None:
    assert _SHORTFORM_ENTITY_KINDS == FROZEN_SHORTFORM  # live == frozen
    derived = {k.shortform: k.name for k in CORE_KINDS if k.shortform}
    assert derived == FROZEN_SHORTFORM  # CORE_KINDS == frozen


def test_every_configured_kind_has_a_descriptor() -> None:
    names = {k.name for k in CORE_KINDS}
    for frozen in (FROZEN_MARKDOWN_POLICIES, FROZEN_DEFAULT_STATUS, FROZEN_STATUS_VALUES):
        assert set(frozen) <= names
    assert set(FROZEN_SHORTFORM.values()) <= names
```

- [ ] **Step 2: Run test to verify it passes against the current code**

Run: `cd science && uv run --frozen pytest tests/test_kind_descriptor_derivation.py -v`
Expected: PASS (5 tests). This proves `CORE_KINDS` is a faithful copy of the live literals *before* they are deleted. If any assertion fails, the descriptor data in Task 1 diverges from the literals — fix `kinds.py`, not the frozen copies.

- [ ] **Step 3: Commit**

```bash
rtk git add science/tests/test_kind_descriptor_derivation.py
rtk git commit -m "test: guard that CORE_KINDS reproduces the kind-keyed literals exactly"
```

---

### Task 3: Rewire science_tool/entities.py to derive from CORE_KINDS

Delete the four literal dicts and the `EntityFilenameStrategy` literal; rebuild the dicts as comprehensions over `CORE_KINDS` under the **same variable names** so the ~6 downstream references (`_CORE_HOME_DIR_NAMES`, the local-shadow check, `entity_policies`, `find_entity`, `_load_markdown_entities`, status accessors) need no edits.

**Files:**
- Modify: `science/src/science_tool/entities.py`

- [ ] **Step 1: Replace the `EntityFilenameStrategy` literal with an import**

In `science/src/science_tool/entities.py`, delete line 25:

```python
EntityFilenameStrategy = Literal["numeric", "citekey", "singleton", "slug", "verbatim"]
```

Add to the model imports near the top (after the existing `from science_model.profiles import ...` line):

```python
from science_model.kinds import CORE_KINDS, EntityFilenameStrategy
```

`Literal` was used *only* by the deleted alias, so it is now unused. Edit line 10 to drop it:

```python
from typing import Any, cast
```

(Leaving `Literal` in would be flagged unused by ruff.)

- [ ] **Step 2: Replace the `_BUILTIN_MARKDOWN_POLICIES` literal with a derivation**

Replace the entire literal block (current lines 40–70) with:

```python
_BUILTIN_MARKDOWN_POLICIES: dict[str, EntityPathPolicy] = {
    k.name: EntityPathPolicy(k.path, k.strategy)
    for k in CORE_KINDS
    if k.path is not None and k.strategy is not None
}
```

(`EntityPathPolicy` is defined just above at lines 34–37, so this resolves. The `is not None` on **both** `path` and `strategy` is deliberate: it narrows both `Path | None` and `EntityFilenameStrategy | None` for the type checker — `if k.path` alone narrows only `path`, leaving `strategy` as `EntityFilenameStrategy | None` and tripping a type error against `EntityPathPolicy(root: Path, strategy: EntityFilenameStrategy)`. The carried-over rationale comments now live on the descriptors in `kinds.py`.)

- [ ] **Step 3: Replace the `_SHORTFORM_ENTITY_KINDS` literal with a derivation**

Replace the literal (current lines 202–209) with:

```python
_SHORTFORM_ENTITY_KINDS: dict[str, str] = {k.shortform: k.name for k in CORE_KINDS if k.shortform}
```

- [ ] **Step 4: Replace the `_DEFAULT_STATUS` and `_STATUS_VALUES` literals with derivations**

Replace both literals (current lines 210–284) with:

```python
_DEFAULT_STATUS: dict[str, str] = {k.name: k.default_status for k in CORE_KINDS if k.default_status}
_STATUS_VALUES: dict[str, frozenset[str]] = {k.name: k.statuses for k in CORE_KINDS if k.statuses}
```

- [ ] **Step 5: Run the descriptor guard + the entities suite**

Run: `cd science && uv run --frozen pytest tests/test_kind_descriptor_derivation.py tests/test_entities.py -v`
Expected: PASS. The guard test now compares the derived dicts (built from `CORE_KINDS`) against the frozen copies; `test_entities.py` exercises path resolution, status validation, and id generation against the derived dicts.

- [ ] **Step 6: Run the broader regression set (path, status, layout migration)**

Run: `cd science && uv run --frozen pytest tests/ model/tests/test_kinds.py -q`
Expected: PASS, no new failures. (Pyright/venv-resolution noise from stale worktree paths is unrelated and may be ignored; only test results matter.)

- [ ] **Step 7: Commit**

```bash
rtk git add science/src/science_tool/entities.py
rtk git commit -m "refactor(entities): derive kind policy/status/shortform dicts from CORE_KINDS"
```

---

## Verification (after all tasks)

- [ ] **Full suite green**

Run: `cd science && uv run --frozen pytest -q`
Expected: full suite passes (baseline ~5430 passed before this work; this plan adds 11 tests and removes no behavior, so the count rises and nothing regresses).

- [ ] **Confirm the literals are gone**

Run: `cd science && rtk grep -nE '"(question|hypothesis)": EntityPathPolicy' src/science_tool/entities.py`
Expected: no matches (the literal table is deleted; only the comprehension remains).

---

## Self-review notes

- **Spec coverage:** design §1 (roster scope = file-authored kinds; migration path) → Scope-decision + Migration-path sections. Design §2 (descriptor model + `EntityFilenameStrategy` move) → Task 1, Step 3 + Task 3, Step 1. Design §3 (manifest content, file-authored kinds incl. the two singletons, carried-over comments) → Task 1, Step 3. Design §4 (consumer rewiring table, name reuse, invariants preserved) → Task 3, Steps 2–4 (reusing names means the shadow-check, `_CORE_HOME_DIR_NAMES`, and local fallback are untouched, satisfying the §4 invariants). Design §5 (guard test + descriptor-validation test + regression) → Tasks 2, 1, and Task 3 Steps 5–6. Design §7 non-goals (no behavior change, no new kinds, no shim) → enforced by the guard test and the reuse-existing-names approach.
- **Type consistency:** `EntityPathPolicy(k.path, k.strategy)` — `EntityPathPolicy` takes `(root: Path, strategy: EntityFilenameStrategy)`; `KindDescriptor.path`/`.strategy` are `Path | None`/`EntityFilenameStrategy | None`, narrowed by the `if k.path is not None and k.strategy is not None` filter (every file-authored descriptor sets both — asserted in `test_every_descriptor_sets_path_and_strategy`). `CORE_KINDS` is imported in both `kinds.py` consumers and the tool.
- **No placeholders:** all code blocks are complete and runnable; all 28 descriptors and all four frozen literal copies are spelled out verbatim from the current source.
