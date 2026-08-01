# Annotation Base-Shape Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the 792 proposition and evidence-line records that `validate_persisted_base_shape` refuses, so the typed contained update paths can write them again.

**Architecture:** Three code changes and one rollout. The two title derivations become shared scalar helpers in `dag/entity_frontmatter.py`, callable by both the workbench writer and a migration. A new `migrate_annotation_base_shape.py` plans every repair in memory, guards each planned post-image, and refuses the whole batch if any in-scope record has no repair. A thin `science entity migrate-annotation-base-shape` command wraps it report-first. Then the command runs against five project roots.

**Tech Stack:** Python 3.12, Pydantic v2, PyYAML, Click, pytest, Ruff, Pyright, uv.

## Global Constraints

- **Design of record:** `docs/plans/2026-08-01-annotation-base-shape-remediation-design.md`. Section references below (§3.2, §4.1, §5.2 …) are to that file.
- **Work in the worktree.** Every command runs from `.worktrees/proposition-corpus-remediation`, on branch `proposition-corpus-remediation`. Do not commit to `main`. Verify with `git rev-parse --abbrev-ref HEAD` before the first commit of each task.
- **`uv` runs from a package directory, never the repo root.** CLI work: `cd science && uv run --frozen …`. Model work: `cd science/model && uv run --frozen …`.
- **Scoped test selections only.** The full CLI suite is ~12k tests and takes 6:42–7:24, longer than the default command timeout. Task 4 owns the one full run and passes an explicit long timeout. Never run two suites concurrently in this worktree.
- **Conventional commits. No AI-attribution trailer or footer** on any commit, PR, or comment.
- **No "legacy"/"compatibility" layers, no `Unified` prefix.** Composition over inheritance; explicit over defensive; fail early rather than silent fallback.
- **Filepaths in docs and code use `~/d/` or relative paths**, never `/home/keith/` or `/mnt/ssd/Dropbox/`.
- **`science validate` mutates the project it validates** — it writes entity and task files as a side effect, so repeated runs inflate their own error counts. It is never used to verify this migration.

## File Structure

| File | Responsibility |
|---|---|
| `science/src/science_tool/dag/entity_frontmatter.py` | **Modify.** Gains `_collapse`, `derive_proposition_title`, `derive_evidence_line_title` — the scalar derivations both the writer and the migration call. |
| `science/src/science_tool/dag/workbench.py` | **Modify.** Loses `_collapse`, `_proposition_title`, `_evidence_line_title`; its two call sites pass scalars. |
| `science/src/science_tool/migrate_annotation_base_shape.py` | **Create.** Planning, guarding, refusal aggregation, application. No Click, no I/O beyond reading candidates and writing applied post-images. |
| `science/src/science_tool/entities_cli.py` | **Modify.** Registers the `migrate-annotation-base-shape` command. Thin: option parsing, exception→`ClickException`, `emit`. |
| `science/tests/test_annotation_title_derivations.py` | **Create.** Task 1's unit tests. |
| `science/tests/test_migrate_annotation_base_shape.py` | **Create.** Tasks 2 and 3's planner and CLI tests. |

---

### Task 1: Shared scalar title derivations

Implements §3.2. `WorkbenchRow.patch` is a required field under `extra="forbid"`, so a row-taking signature would force the migration to fabricate patch membership. The derivations move to the module both writers already share, on the precedent that put `PROPOSITION_REASONING_FIELDS` there.

**Files:**
- Modify: `science/src/science_tool/dag/entity_frontmatter.py`
- Modify: `science/src/science_tool/dag/workbench.py:253-277` (definitions), `:296` and `:327` (call sites)
- Test: `science/tests/test_annotation_title_derivations.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `derive_proposition_title(*, subject: str, predicate: str, object: str) -> str`
  - `derive_evidence_line_title(*, stance: str | None, target_id: str, source: str | None, evidence_type: EvidenceType | str | None) -> str`

  Both exported from `science_tool.dag.entity_frontmatter`. Task 2 imports both.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_annotation_title_derivations.py`:

```python
"""The two title derivations shared by the workbench writer and the base-shape migration."""

from __future__ import annotations

import pytest
from science_model.reasoning import EvidenceType

from science_tool.dag.entity_frontmatter import (
    derive_evidence_line_title,
    derive_proposition_title,
)


def test_proposition_title_is_the_collapsed_triple():
    assert (
        derive_proposition_title(subject="concept:a", predicate="affects", object="concept:b")
        == "concept:a affects concept:b"
    )


def test_proposition_title_collapses_internal_whitespace():
    assert (
        derive_proposition_title(subject="concept:a  b", predicate="affects\n", object="concept:c")
        == "concept:a b affects concept:c"
    )


def test_evidence_line_title_prefers_source_for_the_tail():
    assert (
        derive_evidence_line_title(
            stance="supports",
            target_id="proposition:p",
            source="paper:Walker2024",
            evidence_type="literature_evidence",
        )
        == "supports proposition:p — paper:Walker2024"
    )


def test_evidence_line_title_defaults_stance_to_supports():
    assert (
        derive_evidence_line_title(
            stance=None, target_id="proposition:p", source="paper:X", evidence_type=None
        )
        == "supports proposition:p — paper:X"
    )


def test_evidence_line_title_head_alone_when_no_tail():
    assert (
        derive_evidence_line_title(
            stance="disputes", target_id="proposition:p", source=None, evidence_type=None
        )
        == "disputes proposition:p"
    )


def test_evidence_line_title_canonicalizes_a_raw_suffixed_token():
    """The create path only ever sees a coerced member; a migration sees raw frontmatter."""
    assert (
        derive_evidence_line_title(
            stance="supports",
            target_id="proposition:p",
            source=None,
            evidence_type="empirical_data_evidence",
        )
        == "supports proposition:p — empirical_data"
    )


def test_evidence_line_title_accepts_an_already_coerced_member():
    assert (
        derive_evidence_line_title(
            stance="supports",
            target_id="proposition:p",
            source=None,
            evidence_type=EvidenceType.EMPIRICAL_DATA,
        )
        == "supports proposition:p — empirical_data"
    )


def test_evidence_line_title_refuses_a_token_that_is_not_a_member():
    """canonical_evidence_type_token does NOT validate membership -- the coercion must."""
    with pytest.raises(ValueError):
        derive_evidence_line_title(
            stance="supports",
            target_id="proposition:p",
            source=None,
            evidence_type="garbage_evidence",
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_annotation_title_derivations.py -q
```

Expected: collection error — `ImportError: cannot import name 'derive_evidence_line_title'`.

- [ ] **Step 3: Add the derivations to `entity_frontmatter.py`**

Add to the import block near the top (`science_model.reasoning` is not currently imported there):

```python
from science_model.reasoning import EvidenceType, canonical_evidence_type_token
```

Add the three functions after `TYPED_VALIDATION_SKELETON_KEYS`:

```python
def _collapse(text: str) -> str:
    """Collapse all runs of whitespace to single spaces. Titles are durable authored source."""
    return " ".join(text.split())


def derive_proposition_title(*, subject: str, predicate: str, object: str) -> str:
    """THE derived proposition title. Deterministic, not good prose.

    Mechanical on purpose: it must be stable and reconstructible from the record's own fields,
    which is what lets the base-shape migration reproduce exactly what the create path minted.
    An author may replace it afterwards, and the update path preserves the replacement because
    `title` is in `CREATE_ONLY_KEYS`.

    Takes scalars, not a `WorkbenchRow`: `WorkbenchRow.patch` is required under
    `extra="forbid"`, so a row-taking signature would force a migration to fabricate patch
    membership it has no business inventing.
    """
    return _collapse(f"{subject} {predicate} {object}")


def derive_evidence_line_title(
    *,
    stance: str | None,
    target_id: str,
    source: str | None,
    evidence_type: EvidenceType | str | None,
) -> str:
    """THE derived evidence-line title.

    `target_id` is supplied by the caller and always present, so the head alone is non-empty.
    `stance` defaults to `supports`, matching the entity field's own default. The tail prefers
    `source` and falls back to the evidence type.

    A raw string `evidence_type` is canonicalized AND coerced to `EvidenceType`. The create path
    only ever sees a coerced member -- `EvidenceStub` strips the `_evidence` suffix in a
    `mode="before"` validator and pydantic then enforces membership -- but a migration reading
    persisted frontmatter sees raw tokens. `canonical_evidence_type_token` is documented as
    "pure string->string (does NOT validate membership)", so without the coercion this would
    mint a title from a token the create path rejects.
    """
    head = f"{stance or 'supports'} {target_id}"
    if source:
        tail: str | None = source
    elif evidence_type is None:
        tail = None
    elif isinstance(evidence_type, EvidenceType):
        tail = evidence_type.value
    else:
        tail = EvidenceType(canonical_evidence_type_token(evidence_type)).value
    return _collapse(f"{head} — {tail}" if tail else head)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_annotation_title_derivations.py -q
```

Expected: 8 passed.

- [ ] **Step 5: Delete the three old functions from `workbench.py` and repoint the call sites**

Delete `_collapse`, `_proposition_title` and `_evidence_line_title` (lines 253-277). `_collapse` has no other caller in that file — verify with `grep -n "_collapse" src/science_tool/dag/workbench.py` after the deletion; expected: no output.

Add to workbench.py's imports:

```python
from science_tool.dag.entity_frontmatter import derive_evidence_line_title, derive_proposition_title
```

In `_proposition_for_row`, replace `title=_proposition_title(row),` with:

```python
        title=derive_proposition_title(
            subject=row.subject, predicate=row.predicate, object=row.object
        ),
```

In `_evidence_line_for_stub`, replace `title=_evidence_line_title(stub, target_id=target_id),` with:

```python
        title=derive_evidence_line_title(
            stance=stub.stance,
            target_id=target_id,
            source=stub.source,
            evidence_type=stub.evidence_type,
        ),
```

`EvidenceType` and `canonical_evidence_type_token` stay imported in workbench.py — `EvidenceStub._canonicalize_evidence_type` and the `is_staged_empirical` check still use them.

- [ ] **Step 6: Run the writer's own suites to verify nothing regressed**

```bash
cd science && uv run --frozen pytest \
  tests/test_annotation_title_derivations.py \
  tests/test_workbench_writer_containment.py \
  tests/test_workbench_apply.py \
  tests/test_workbench.py -q
```

Expected: all pass. These are the suites that assert on minted titles, so a changed derivation surfaces here.

- [ ] **Step 7: Lint, type-check, and commit**

Commit **before** mutating. Mutation testing reverts with `git checkout`, and an uncommitted implementation is reverted along with the mutation — you would be restoring the file to its pre-task state and testing nothing.

```bash
cd science && uv run ruff check && uv run pyright
cd .. && git rev-parse --abbrev-ref HEAD    # expect: proposition-corpus-remediation
git add science/src/science_tool/dag/entity_frontmatter.py \
        science/src/science_tool/dag/workbench.py \
        science/tests/test_annotation_title_derivations.py
git commit -m "refactor(annotation): share scalar title derivations between writer and migration"
```

- [ ] **Step 8: Mutation-certify both derivations**

For each mutation: apply it, run `cd science && uv run --frozen pytest tests/test_annotation_title_derivations.py -q`, confirm RED, then restore the committed implementation with `git checkout HEAD -- science/src/science_tool/dag/entity_frontmatter.py` (run from the worktree root).

`HEAD`, not `--`: the bare form restores the index, which after Step 7 is the same thing — but only because the commit happened. Using `HEAD` says what is being restored and keeps working if the file is staged for some other reason.

1. In `derive_proposition_title`, swap the order to `f"{subject} {object} {predicate}"`. Expect `test_proposition_title_is_the_collapsed_triple` to fail.
2. In `derive_evidence_line_title`, drop the coercion — `tail = canonical_evidence_type_token(evidence_type)`. Expect `test_evidence_line_title_refuses_a_token_that_is_not_a_member` to fail.
3. In `derive_evidence_line_title`, prefer the evidence type over the source. Expect `test_evidence_line_title_prefers_source_for_the_tail` to fail.

After the last restore, confirm the tree is clean: `git status --porcelain` should print nothing.

Report any mutation that does **not** go red. Do not adjust the mutation to match the observation.

---

### Task 2: The repair planner

Implements §4.1 (the algorithm), §5.1 (normalized comparison) and §5.2 (the guards). Everything happens in memory: nothing is written until Task 3's `--apply`, and the whole batch is refused if any in-scope record has no repair.

**Files:**
- Create: `science/src/science_tool/migrate_annotation_base_shape.py`
- Test: `science/tests/test_migrate_annotation_base_shape.py`

**Interfaces:**
- Consumes: `derive_proposition_title`, `derive_evidence_line_title` from Task 1.
- Produces:
  - `ANNOTATION_KIND_DIRS: tuple[str, ...]`
  - `class BaseShapeMigrationRefused(Exception)`
  - `@dataclass(frozen=True) class PlannedRepair` — fields `path: Path`, `postimage: str`, `title: str | None`
  - `@dataclass(frozen=True) class Refusal` — fields `path: Path`, `reason: str`
  - `@dataclass(frozen=True) class RepairPlan` — fields `repairs: tuple[PlannedRepair, ...]`, `refusals: tuple[Refusal, ...]`, `skipped: int`
  - `plan_repairs(project_root: Path) -> RepairPlan`
  - `apply_plan(plan: RepairPlan) -> int` — raises `BaseShapeMigrationRefused` if `plan.refusals` is non-empty; returns the number of files written.
  - `migrate(project_root: Path, *, apply: bool) -> dict[str, object]`

  Task 3 imports `BaseShapeMigrationRefused` and `migrate`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_migrate_annotation_base_shape.py`:

```python
"""Planner and CLI for `science entity migrate-annotation-base-shape` (piece 3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from science_model.frontmatter import split_frontmatter

from science_tool.migrate_annotation_base_shape import (
    BaseShapeMigrationRefused,
    apply_plan,
    plan_repairs,
)

VALID_PROPOSITION = """\
---
id: proposition:a-affects-b
kind: proposition
title: An authored title
status: active
subject: concept:a
predicate: affects
object: concept:b
polarity: positive
created: '2026-06-01'
updated: '2026-06-01'
---
# body

## Summary
text
"""


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    for sub in ("propositions", "evidence-lines"):
        (tmp_path / "entities" / sub).mkdir(parents=True)
    return tmp_path


def _write(root: Path, sub: str, name: str, frontmatter: str, body: str = "# b\n\n## Summary\n") -> Path:
    path = root / "entities" / sub / name
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
    return path


EMPTY_TITLE_PROPOSITION = """\
id: proposition:a-affects-b
kind: proposition
title: ''
status: active
subject: concept:a
predicate: affects
object: concept:b
polarity: positive
created: '2026-06-01'
updated: '2026-06-01'
"""

EMPTY_TITLE_EVIDENCE_LINE = """\
id: evidence-line:a-affects-b-ev1
kind: evidence-line
title: ''
status: active
stance: supports
target: proposition:a-affects-b
source: paper:Walker2024
evidence_type: literature_evidence
created: '2026-06-01'
updated: '2026-06-01'
"""

UNQUOTED_DATES_PROPOSITION = """\
id: proposition:c-affects-d
kind: proposition
title: An authored title
status: active
subject: concept:c
predicate: affects
object: concept:d
polarity: positive
created: 2026-06-01
updated: 2026-06-01
"""


def test_plans_a_proposition_title_from_its_own_triple(tmp_path):
    root = _project(tmp_path)
    _write(root, "propositions", "p.md", EMPTY_TITLE_PROPOSITION)
    plan = plan_repairs(root)
    assert plan.refusals == ()
    assert len(plan.repairs) == 1
    assert plan.repairs[0].title == "concept:a affects concept:b"


def test_plans_an_evidence_line_title_from_its_own_fields(tmp_path):
    root = _project(tmp_path)
    _write(root, "evidence-lines", "e.md", EMPTY_TITLE_EVIDENCE_LINE)
    plan = plan_repairs(root)
    assert plan.refusals == ()
    assert plan.repairs[0].title == "supports proposition:a-affects-b — paper:Walker2024"


def test_a_base_valid_record_is_skipped_byte_for_byte(tmp_path):
    root = _project(tmp_path)
    path = root / "entities/propositions/valid.md"
    path.write_text(VALID_PROPOSITION, encoding="utf-8")
    plan = plan_repairs(root)
    assert plan.repairs == ()
    assert plan.refusals == ()
    assert plan.skipped == 1
    assert path.read_text(encoding="utf-8") == VALID_PROPOSITION


def test_a_date_only_repair_changes_no_parsed_value(tmp_path):
    root = _project(tmp_path)
    path = _write(root, "propositions", "d.md", UNQUOTED_DATES_PROPOSITION)
    plan = plan_repairs(root)
    assert len(plan.repairs) == 1
    assert plan.repairs[0].title is None
    before, _ = split_frontmatter(path.read_text(encoding="utf-8"))
    after, _ = split_frontmatter(plan.repairs[0].postimage)
    assert str(before["created"]) == after["created"]
    assert isinstance(after["created"], str)


@pytest.mark.parametrize("literal", ["null", "0"])
def test_a_title_that_is_not_the_empty_string_is_unsupported(tmp_path, literal):
    """The fixtures that discriminate `title == ""` from a naive falsiness check."""
    root = _project(tmp_path)
    frontmatter = EMPTY_TITLE_PROPOSITION.replace("title: ''", f"title: {literal}")
    _write(root, "propositions", "p.md", frontmatter)
    plan = plan_repairs(root)
    assert plan.repairs == ()
    assert len(plan.refusals) == 1


def test_apply_refuses_the_whole_batch_and_names_every_refusal(tmp_path):
    root = _project(tmp_path)
    good = _write(root, "propositions", "good.md", EMPTY_TITLE_PROPOSITION)
    _write(root, "propositions", "bad1.md", EMPTY_TITLE_PROPOSITION.replace("title: ''", "title: null"))
    _write(root, "propositions", "bad2.md", EMPTY_TITLE_PROPOSITION.replace("title: ''", "title: 0"))
    before = good.read_text(encoding="utf-8")

    plan = plan_repairs(root)
    with pytest.raises(BaseShapeMigrationRefused) as excinfo:
        apply_plan(plan)

    assert "bad1.md" in str(excinfo.value)
    assert "bad2.md" in str(excinfo.value)
    assert good.read_text(encoding="utf-8") == before


def test_planning_writes_nothing(tmp_path):
    root = _project(tmp_path)
    path = _write(root, "propositions", "p.md", EMPTY_TITLE_PROPOSITION)
    before = path.read_text(encoding="utf-8")
    plan_repairs(root)
    assert path.read_text(encoding="utf-8") == before


def test_apply_is_idempotent(tmp_path):
    root = _project(tmp_path)
    path = _write(root, "propositions", "p.md", EMPTY_TITLE_PROPOSITION)
    apply_plan(plan_repairs(root))
    once = path.read_text(encoding="utf-8")
    second = plan_repairs(root)
    assert second.repairs == ()
    assert second.skipped == 1
    assert path.read_text(encoding="utf-8") == once


def test_the_repair_does_not_stamp_updated(tmp_path):
    """The repair restores what the writer should have persisted; it asserts no new change."""
    root = _project(tmp_path)
    path = _write(root, "propositions", "p.md", EMPTY_TITLE_PROPOSITION)
    apply_plan(plan_repairs(root))
    frontmatter, _ = split_frontmatter(path.read_text(encoding="utf-8"))
    assert frontmatter["created"] == "2026-06-01"
    assert frontmatter["updated"] == "2026-06-01"


def test_apply_preserves_crlf_body_bytes(tmp_path):
    """Pins the preserving-body reader: Path.read_text would silently rewrite line endings."""
    root = _project(tmp_path)
    path = root / "entities/propositions/crlf.md"
    body = "# b\r\n\r\n## Summary\r\ntext\r\n"
    text = f"---\n{EMPTY_TITLE_PROPOSITION}---\n".replace("\n", "\r\n") + body
    path.write_bytes(text.encode("utf-8"))

    apply_plan(plan_repairs(root))

    # The exact original body bytes, not merely "some CRLF survived" -- a partial
    # rewrite would leave CRLF elsewhere in the file and pass a weaker assertion.
    assert path.read_bytes().endswith(body.encode("utf-8"))


def test_dates_are_force_quoted_by_the_canonical_renderer(tmp_path):
    """Pins the renderer choice: the workbench emitter does NOT force-quote."""
    root = _project(tmp_path)
    path = _write(root, "propositions", "d.md", UNQUOTED_DATES_PROPOSITION)
    apply_plan(plan_repairs(root))
    lines = path.read_text(encoding="utf-8").splitlines()
    assert 'created: "2026-06-01"' in lines
    assert 'updated: "2026-06-01"' in lines


def test_a_datetime_valued_date_is_unsupported(tmp_path):
    """The measured defect is a bare date; a datetime's time component would be discarded."""
    root = _project(tmp_path)
    frontmatter = UNQUOTED_DATES_PROPOSITION.replace("created: 2026-06-01", "created: 2026-06-01 10:30:00")
    _write(root, "propositions", "dt.md", frontmatter)
    plan = plan_repairs(root)
    assert plan.repairs == ()
    assert len(plan.refusals) == 1
```

**These are verified.** The module source and this test file were run together against the real package before this plan was committed: 13 passed. If any fails during implementation, the implementation has diverged from the code in Step 3 — re-read it rather than adjusting the test.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_migrate_annotation_base_shape.py -q
```

Expected: collection error — `ModuleNotFoundError: No module named 'science_tool.migrate_annotation_base_shape'`.

- [ ] **Step 3: Write the module**

Create `science/src/science_tool/migrate_annotation_base_shape.py`:

```python
"""Repair proposition / evidence-line records the durable base shape refuses.

Piece 3 of the schema-first closure program. Writer containment stopped the debt growing and
backfilled nothing; this is the backfill. Design:
`docs/plans/2026-08-01-annotation-base-shape-remediation-design.md`.

Two properties are load-bearing and easy to lose:

- **Preflight atomicity.** Every candidate is planned and every refusal collected BEFORE any
  file is written. A per-file loop that repairs as it goes satisfies the per-record guards and
  still leaves a half-migrated corpus on the first unsupported record.
- **`title == ""` exactly, not falsiness.** A missing key, an explicit null, or a non-string
  title are unsupported, not repairable. The parsed-value allowlist cannot enforce this -- all
  three would satisfy it -- so the condition lives here and is tested directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from science_model.entity_schema import EntityValidationError, EntityValidator
from science_model.frontmatter import render_frontmatter, split_frontmatter

from science_model.frontmatter import atomic_write_text

from science_tool.dag.entity_frontmatter import (
    derive_evidence_line_title,
    derive_proposition_title,
)
from science_tool.entities import parse_markdown_entity_file_preserving_body

ANNOTATION_KIND_DIRS: tuple[str, ...] = ("propositions", "evidence-lines")

_DATE_KEYS: frozenset[str] = frozenset({"created", "updated"})


class BaseShapeMigrationRefused(Exception):
    """An in-scope record has no available repair, so the whole batch is refused."""


@dataclass(frozen=True)
class PlannedRepair:
    path: Path
    postimage: str
    title: str | None


@dataclass(frozen=True)
class Refusal:
    path: Path
    reason: str


@dataclass(frozen=True)
class RepairPlan:
    repairs: tuple[PlannedRepair, ...]
    refusals: tuple[Refusal, ...]
    skipped: int


def _normalized(mapping: dict[str, Any]) -> dict[str, Any]:
    """`created`/`updated` compare equal whether stored as a YAML date or an ISO string.

    Raw YAML changes those values' TYPE across the render -- `datetime.date` in, `str` out --
    so without this the date-only repairs would read as semantic changes and the guard would
    reject its own correct output.

    `datetime` is deliberately NOT normalized. The measured corpus defect is a bare
    `datetime.date`; a `datetime` carries a time component that the canonical renderer would
    discard, and normalizing it here would declare that discard semantics-free. Leaving it
    alone makes the guard REFUSE such a record instead, which is the correct outcome for a
    value this migration was never measured against.
    """
    out: dict[str, Any] = {}
    for key, value in mapping.items():
        if key in _DATE_KEYS and isinstance(value, date) and not isinstance(value, datetime):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def _derived_title(frontmatter: dict[str, Any], kind_dir: str) -> str:
    if kind_dir == "propositions":
        return derive_proposition_title(
            subject=frontmatter["subject"],
            predicate=frontmatter["predicate"],
            object=frontmatter["object"],
        )
    return derive_evidence_line_title(
        stance=frontmatter.get("stance"),
        target_id=frontmatter["target"],
        source=frontmatter.get("source"),
        evidence_type=frontmatter.get("evidence_type"),
    )


def _plan_one(
    path: Path, kind_dir: str, validator: EntityValidator
) -> PlannedRepair | Refusal | None:
    """Plan one candidate. `None` means base-valid: skip it byte for byte."""
    frontmatter, body = parse_markdown_entity_file_preserving_body(path)
    try:
        validator.validate_persisted_base_shape(frontmatter)
    except EntityValidationError:
        pass
    else:
        return None

    planned = dict(frontmatter)
    title: str | None = None
    if "title" in planned and isinstance(planned["title"], str) and planned["title"] == "":
        try:
            title = _derived_title(planned, kind_dir)
        except (KeyError, ValueError) as exc:
            return Refusal(path, f"title cannot be derived: {exc}")
        planned["title"] = title

    postimage = render_frontmatter(planned, body)
    post_frontmatter, post_body = split_frontmatter(postimage)

    if set(post_frontmatter) != set(frontmatter):
        return Refusal(path, "render changed the frontmatter key set")
    if post_body != body:
        return Refusal(path, "render changed the body bytes")
    pre_values, post_values = _normalized(frontmatter), _normalized(post_frontmatter)
    changed = {k for k in pre_values if post_values[k] != pre_values[k]}
    if changed - {"title"}:
        return Refusal(path, f"render changed keys outside the allowlist: {sorted(changed)}")
    try:
        validator.validate_persisted_base_shape(post_frontmatter)
    except EntityValidationError as exc:
        return Refusal(path, f"still refused after repair: {exc}")

    return PlannedRepair(path, postimage, title)


def plan_repairs(project_root: Path) -> RepairPlan:
    """Plan every repair and collect every refusal. Writes nothing."""
    validator = EntityValidator()
    repairs: list[PlannedRepair] = []
    refusals: list[Refusal] = []
    skipped = 0
    for kind_dir in ANNOTATION_KIND_DIRS:
        directory = project_root / "entities" / kind_dir
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            outcome = _plan_one(path, kind_dir, validator)
            if outcome is None:
                skipped += 1
            elif isinstance(outcome, Refusal):
                refusals.append(outcome)
            else:
                repairs.append(outcome)
    return RepairPlan(tuple(repairs), tuple(refusals), skipped)


def _refusal_message(refusals: tuple[Refusal, ...]) -> str:
    listed = "\n".join(f"  {r.path}: {r.reason}" for r in refusals)
    return (
        f"{len(refusals)} in-scope record(s) have no available repair; "
        f"nothing was written:\n{listed}"
    )


def apply_plan(plan: RepairPlan) -> int:
    """Write every planned post-image, or none of them."""
    if plan.refusals:
        raise BaseShapeMigrationRefused(_refusal_message(plan.refusals))
    for repair in plan.repairs:
        atomic_write_text(repair.path, repair.postimage)
    return len(plan.repairs)


def migrate(project_root: Path, *, apply: bool) -> dict[str, object]:
    """Plan, optionally apply, and report.

    Refusals raise whether or not `apply` was requested. A dry run exists to tell the caller
    what the apply WOULD do, and what it would do is refuse -- reporting "would repair N" while
    silently omitting the records that block the run is the opposite of report-first.
    """
    plan = plan_repairs(project_root)
    if plan.refusals:
        raise BaseShapeMigrationRefused(_refusal_message(plan.refusals))
    written = apply_plan(plan) if apply else 0
    # No `refusals` key: this line is unreachable unless the plan had none, so reporting an
    # always-empty list would imply the command can succeed while refusing something.
    return {
        "applied": apply,
        "repairs": [
            {"path": str(r.path.relative_to(project_root)), "title": r.title} for r in plan.repairs
        ],
        "skipped": plan.skipped,
        "written": written,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_migrate_annotation_base_shape.py -q
```

Expected: **13 passed** (12 functions, the `title` parametrize contributing 2 cases). This exact count was observed against the real package while writing this plan.

- [ ] **Step 5: Lint, type-check, and commit**

Commit **before** mutating, for the reason given in Task 1 Step 7.

```bash
cd science && uv run ruff check && uv run pyright
cd .. && git rev-parse --abbrev-ref HEAD    # expect: proposition-corpus-remediation
git add science/src/science_tool/migrate_annotation_base_shape.py \
        science/tests/test_migrate_annotation_base_shape.py
git commit -m "feat(annotation): plan base-shape repairs with preflight atomicity"
```

- [ ] **Step 6: Mutation-certify the properties that are easy to lose**

For each: apply it, run `cd science && uv run --frozen pytest tests/test_migrate_annotation_base_shape.py -q`, confirm RED, then restore with `git checkout HEAD -- science/src/science_tool/migrate_annotation_base_shape.py` from the worktree root.

1. **Falsiness instead of equality.** Change the `_plan_one` condition to `if not planned.get("title"):`. Expect both `test_a_title_that_is_not_the_empty_string_is_unsupported` cases to fail.
2. **Per-file application.** Change `apply_plan` to write each repair before checking `plan.refusals`. Expect `test_apply_refuses_the_whole_batch_and_names_every_refusal` to fail on the `good.md` byte comparison.
3. **Repair base-valid records too.** Delete the `else: return None` early exit so every record is re-rendered. Expect `test_a_base_valid_record_is_skipped_byte_for_byte` to fail.
4. **Drop the date normalization.** Make `_normalized` the identity function. Expect `test_a_date_only_repair_changes_no_parsed_value` to fail — the guard now rejects its own correct output as an out-of-allowlist change.
5. **Stamp `updated`.** Add `planned["updated"] = date.today().isoformat()` after the title branch in `_plan_one`. Expect `test_the_repair_does_not_stamp_updated` to fail.
6. **Read with `Path.read_text`.** Replace the `parse_markdown_entity_file_preserving_body` call with `split_frontmatter(path.read_text(encoding="utf-8"))`. Expect `test_apply_preserves_crlf_body_bytes` to fail.
7. **Normalize `datetime` too.** Add a `datetime` branch to `_normalized` returning `value.date().isoformat()`. Expect `test_a_datetime_valued_date_is_unsupported` to fail — that mutation declares a discarded time component semantics-free.

After the last restore, confirm `git status --porcelain` prints nothing.

Report any mutation whose observed result differs from the expectation above. Do not adjust the mutation to match the observation.

---

### Task 3: The CLI command

Implements §4. Thin wrapper: Click options, exception translation, `emit`. All logic stays in Task 2's module. `entity migrate-specs` (`entities_cli.py:450-484`) is the pattern — lazy imports inside the command body, `emit(output_format=…, payload=…, render_text=…)`.

**Files:**
- Modify: `science/src/science_tool/entities_cli.py` (add after `entity_migrate_specs`, before `entity_sections`)
- Test: `science/tests/test_migrate_annotation_base_shape.py` (append)

**Interfaces:**
- Consumes: `BaseShapeMigrationRefused`, `migrate` from Task 2.
- Produces: the `science entity migrate-annotation-base-shape` command. Task 4 runs it.

- [ ] **Step 1: Write the failing tests**

First, extend the **existing import block** at the top of `science/tests/test_migrate_annotation_base_shape.py` — do not put these above the new tests. Ruff's default rule set includes `E4`, so a module-level import after a function definition is `E402 Module level import not at top of file` and Step 7's `ruff check` fails.

The block becomes:

```python
from __future__ import annotations

import json as _json
from pathlib import Path

import pytest
from click.testing import CliRunner
from science_model.frontmatter import split_frontmatter

from science_tool.entities_cli import entity_group
from science_tool.migrate_annotation_base_shape import (
    BaseShapeMigrationRefused,
    apply_plan,
    plan_repairs,
)
```

Then append **only the test functions** to the end of the file:

```python
def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    root = _project(tmp_path)
    path = _write(root, "propositions", "p.md", EMPTY_TITLE_PROPOSITION)
    before = path.read_text(encoding="utf-8")
    monkeypatch.chdir(root)

    result = CliRunner().invoke(entity_group, ["migrate-annotation-base-shape", "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = _json.loads(result.output)
    assert payload["written"] == 0
    assert len(payload["repairs"]) == 1
    assert path.read_text(encoding="utf-8") == before


def test_apply_repairs_the_invalid_and_leaves_the_valid_byte_identical(tmp_path, monkeypatch):
    """Pins the base-valid skip: a command that re-renders everything passes every other test."""
    root = _project(tmp_path)
    valid = root / "entities/propositions/valid.md"
    valid.write_text(VALID_PROPOSITION, encoding="utf-8")
    invalid = _write(root, "propositions", "p.md", EMPTY_TITLE_PROPOSITION)
    monkeypatch.chdir(root)

    result = CliRunner().invoke(
        entity_group, ["migrate-annotation-base-shape", "--apply", "--format", "json"]
    )

    assert result.exit_code == 0, result.output
    assert _json.loads(result.output)["written"] == 1
    assert valid.read_text(encoding="utf-8") == VALID_PROPOSITION
    repaired, _ = split_frontmatter(invalid.read_text(encoding="utf-8"))
    assert repaired["title"] == "concept:a affects concept:b"


def test_dry_run_names_refusals_and_exits_nonzero(tmp_path, monkeypatch):
    """Report-first: a dry run must not print 'would repair' while hiding its blockers."""
    root = _project(tmp_path)
    good = _write(root, "propositions", "good.md", EMPTY_TITLE_PROPOSITION)
    _write(root, "propositions", "bad.md", EMPTY_TITLE_PROPOSITION.replace("title: ''", "title: null"))
    before = good.read_text(encoding="utf-8")
    monkeypatch.chdir(root)

    result = CliRunner().invoke(entity_group, ["migrate-annotation-base-shape"])

    assert result.exit_code != 0
    assert "bad.md" in result.output
    assert "would repair" not in result.output
    assert good.read_text(encoding="utf-8") == before


def test_apply_with_unsupported_records_exits_nonzero_and_writes_nothing(tmp_path, monkeypatch):
    root = _project(tmp_path)
    good = _write(root, "propositions", "good.md", EMPTY_TITLE_PROPOSITION)
    _write(root, "propositions", "bad1.md", EMPTY_TITLE_PROPOSITION.replace("title: ''", "title: null"))
    _write(root, "propositions", "bad2.md", EMPTY_TITLE_PROPOSITION.replace("title: ''", "title: 0"))
    before = good.read_text(encoding="utf-8")
    monkeypatch.chdir(root)

    result = CliRunner().invoke(entity_group, ["migrate-annotation-base-shape", "--apply"])

    assert result.exit_code != 0
    assert "bad1.md" in result.output
    assert "bad2.md" in result.output
    assert good.read_text(encoding="utf-8") == before
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_migrate_annotation_base_shape.py -q -k "dry_run or apply_repairs or unsupported_records"
```

Expected: FAIL — `No such command 'migrate-annotation-base-shape'`.

- [ ] **Step 3: Register the command**

Add to `science/src/science_tool/entities_cli.py`, immediately after `entity_migrate_specs`:

```python
@entity_group.command("migrate-annotation-base-shape")
@click.option("--apply", "apply_changes", is_flag=True, help="Write. Without this, plan only.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", show_default=True)
def entity_migrate_annotation_base_shape(apply_changes: bool, output_format: str) -> None:
    """Repair PROPOSITION and EVIDENCE-LINE records the durable base shape refuses.

    Scope is exactly those two kinds. Other kinds carrying the same unquoted-date defect are
    deliberately NOT touched; that fix is kind-agnostic and belongs to its own migration.

    Backfills a `title` that is exactly the empty string, deriving it from the record's own
    fields with the same derivation the create path uses, and re-renders through the canonical
    frontmatter block, which quotes `created`/`updated`. A base-valid record is skipped byte for
    byte. `updated` is never stamped. If any in-scope record has no available repair, every one
    is named and NOTHING is written. Plan-then-`--apply`.
    """
    from science_tool.migrate_annotation_base_shape import BaseShapeMigrationRefused, migrate
    from science_tool.output import emit

    try:
        report = migrate(Path.cwd(), apply=apply_changes)
    except BaseShapeMigrationRefused as exc:
        raise click.ClickException(str(exc)) from exc

    def _render_text() -> None:
        if apply_changes:
            click.echo(f"repaired {report['written']} record(s); skipped {report['skipped']}")
        else:
            click.echo(
                f"would repair {len(report['repairs'])} record(s); skipped {report['skipped']}"
            )
            click.echo("(dry run — nothing written; re-run with --apply)")

    emit(output_format=output_format, payload=report, render_text=_render_text)
```

- [ ] **Step 4: Classify the command in the output-budget registry**

`test_every_leaf_command_is_classified` turns the full suite red the moment a leaf command exists with no classification, and `EXPECTED_CLASSIFICATION_COUNTS` pins the totals — so this is not optional cleanup, it is part of making Task 4 Step 1 green. The command's JSON payload grows one `repairs` entry per repaired record, so it is **deferred**, not exempt.

In `science/src/science_tool/budget/registry.py`, add the path to the existing `entity …` tuple — the block whose reason already reads *"one output member per entity, field, relation, warning, migration action, or body element"*, which covers this command without a new entry:

```python
        for path in (
            "entity field-inventory",
            "entity migrate-annotation-base-shape",
            "entity migrate-hypothesis",
            "entity migrate-specs",
```

In `science/tests/test_budget_boundary.py`, bump the deferred total from 102 to 103:

```python
EXPECTED_CLASSIFICATION_COUNTS = {
    "budgeted": 69,
    "exempt": 122,
    "deferred": 103,
}
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest \
  tests/test_migrate_annotation_base_shape.py tests/test_budget_boundary.py -q
```

Expected: 17 from `test_migrate_annotation_base_shape.py` (13 from Task 2 plus these 4), and `test_budget_boundary.py` green. If the deferred count is off by more than one, a command was added or removed elsewhere on this branch — reconcile it rather than editing the number until it passes.

- [ ] **Step 6: Verify the help text states the kind boundary**

```bash
cd science && uv run --frozen science entity migrate-annotation-base-shape --help
```

Expected: the output names PROPOSITION and EVIDENCE-LINE and says other kinds are not touched. The design requires a reader not have to infer the boundary.

- [ ] **Step 7: Lint, type-check, and commit**

```bash
cd science && uv run ruff check && uv run pyright
cd .. && git rev-parse --abbrev-ref HEAD    # expect: proposition-corpus-remediation
git add science/src/science_tool/entities_cli.py \
        science/src/science_tool/budget/registry.py \
        science/tests/test_budget_boundary.py \
        science/tests/test_migrate_annotation_base_shape.py
git commit -m "feat(annotation): add entity migrate-annotation-base-shape"
```

---

### Task 4: Validation and corpus rollout

Implements §5.3 and §6. The three implementation commits are done; this task proves them and repairs the corpus.

**Files:**
- Modify: 792 record files across five project roots (four external repositories plus `meta/` in this one).

**Interfaces:**
- Consumes: the command from Task 3.
- Produces: nothing further in code.

- [ ] **Step 1: Run the full CLI suite**

Shared serialization and writer-side behavior changed and the change crosses `dag/` and the CLI, so the full-suite trigger applies. This is the one full run; it takes 6:42–7:24, so pass an explicit long timeout and do not background it.

```bash
cd science && uv run --frozen pytest -q
```

Expected: green. Compare any failure by **test name** against `main` before attributing it to this branch — `-m snapshot` and `-m real_projects` have known pre-existing failures on `main` and are excluded from this default run anyway.

- [ ] **Step 2: Run the model suite**

Task 1 imports from `science_model.reasoning` in a new place but changes no model code, so this is a cheap confirmation.

```bash
cd science/model && uv run --frozen pytest -q
```

Expected: green.

- [ ] **Step 3: Take the pre-migration measurement**

Run from the worktree so the count is against this branch's toolkit:

```bash
cd science && uv run --frozen python -c "
from pathlib import Path
from science_model.entity_schema import EntityValidationError, EntityValidator
from science_model.frontmatter import split_frontmatter
roots = ['~/d/cancer/cancer-types/multiple-myeloma', '~/d/cancer/data-sources/cbioportal',
         '~/d/cancer/mechanisms/evolution', '~/d/protein-landscape', '../meta']
v = EntityValidator()
for r in roots:
    root = Path(r).expanduser()
    n = 0
    for sub in ('propositions', 'evidence-lines'):
        for f in sorted((root / 'entities' / sub).glob('*.md')):
            fm, _ = split_frontmatter(f.read_text(encoding='utf-8'))
            try: v.validate_persisted_base_shape(fm)
            except EntityValidationError: n += 1
    print(f'{n:>4}  {r}')
"
```

Expected: `681 mm30`, `72 cbioportal`, `21 evolution`, `16 protein-landscape`, `2 meta` — 792 total. **If a count differs, stop and report it.** The population is supposed to be frozen; a change means something wrote new debt and the design's premise needs rechecking before any file is repaired.

- [ ] **Step 4: Dry-run every project root**

The external repositories pin an older toolkit revision in their own `uv.lock`, so they cannot see this branch's command. Run the worktree's toolkit against them by setting `--project` and letting the command read `Path.cwd()`.

**Every block from here on is self-contained and starts at the worktree root.** Each recomputes `WT` — execution runs each block in a fresh shell, so a variable set in an earlier block is not in scope, and `$(cd .. && pwd)` would resolve to `.worktrees/` rather than the repo.

```bash
WT="$(git rev-parse --show-toplevel)/science"    # from the worktree root
for p in ~/d/cancer/cancer-types/multiple-myeloma \
         ~/d/cancer/data-sources/cbioportal \
         ~/d/cancer/mechanisms/evolution \
         ~/d/protein-landscape \
         "$(git rev-parse --show-toplevel)/meta"; do
  echo "=== $p"
  (cd "$p" && uv run --frozen --project "$WT" science entity migrate-annotation-base-shape) || exit 1
done
```

Expected: `would repair` counts of 681, 72, 21, 16, 2 — matching Step 3 — with nothing written. A dry run now exits non-zero and names any unsupported record, so a non-zero exit here means **stop**: there is an in-scope record the command cannot repair, and the design's measured residue of zero no longer holds.

The `|| exit 1` is load-bearing. A `for` loop reports only its **last** iteration's status, so without it a refusal in mm30 — the first and largest root — would be masked by a clean run in `meta` and the rollout would proceed as though everything passed.

- [ ] **Step 5: Apply and commit, one project root at a time**

Do these one at a time, not in a loop — each needs its state confirmed before it is committed. These repositories are Dropbox-synced and both their checked-out branch and their working tree drift without this session's knowledge.

**Measured expectation, taken while writing this plan:** all four external repositories are on `main` with a clean working tree. The gate below enforces exactly that, and it is what makes the `git add` safe — on a clean tree, everything under those two directories afterwards is this command's output and nothing else.

Run this block four times, substituting each path in turn:

- `~/d/cancer/cancer-types/multiple-myeloma` (681 records)
- `~/d/cancer/data-sources/cbioportal` (72)
- `~/d/cancer/mechanisms/evolution` (21)
- `~/d/protein-landscape` (16)

```bash
WT="$(git rev-parse --show-toplevel)/science"    # from the worktree root
TARGET=~/d/cancer/cancer-types/multiple-myeloma  # <- the path for this round
cd "$TARGET"

# Gate. Do NOT proceed past a failure here -- report it instead.
test "$(git rev-parse --abbrev-ref HEAD)" = "main" || { echo "REFUSED: not on main"; exit 1; }
test -z "$(git status --porcelain)" || { echo "REFUSED: working tree is dirty"; exit 1; }

uv run --frozen --project "$WT" science entity migrate-annotation-base-shape --apply
git add entities/propositions entities/evidence-lines
git commit -m "fix(entities): backfill derived titles and quote persisted dates"
```

If a repository is not on `main`, or is dirty, **stop and report it** rather than committing around it. A dirty tree means someone else's uncommitted work is in the same directories, and `git add` cannot tell it apart from the migration's output.

Do not push any of these repositories.

- [ ] **Step 6: Apply to `meta/` inside this worktree**

`meta` is a project root inside this repository, so its repair is a separate commit on this branch, not a separate repository:

```bash
WT="$(git rev-parse --show-toplevel)/science"    # from the worktree root
(cd meta && uv run --frozen --project "$WT" science entity migrate-annotation-base-shape --apply)
git status --porcelain meta/entities              # expect: only the 2 repaired records
git add meta/entities
git commit -m "fix(meta): backfill derived titles and quote persisted dates"
```

No branch gate here: this is the worktree's own branch, already confirmed in Tasks 1-3.

- [ ] **Step 7: Verify the post-condition**

Re-run Step 3's measurement verbatim.

Expected: `0` for every root. This is §5.3, and it is the only durable claim this slice makes about the corpus.

- [ ] **Step 8: Verify idempotence on the real corpus**

```bash
WT="$(git rev-parse --show-toplevel)/science"    # from the worktree root
for p in ~/d/cancer/cancer-types/multiple-myeloma ~/d/protein-landscape; do
  echo "=== $p"
  (cd "$p" && uv run --frozen --project "$WT" science entity migrate-annotation-base-shape --apply \
     && git status --porcelain) || exit 1
done
```

Expected: `repaired 0 record(s); skipped N` and empty `git status` output for each — a second apply is a no-op. `|| exit 1` for the same reason as Step 4: the loop would otherwise report only the last root's status.

- [ ] **Step 9: Verify the diff distribution across all five commits**

`--stat` abbreviates and cannot show a per-file distribution; `--numstat` gives exact added/deleted counts per file, which is what the design's measured shape is stated in.

```bash
WT="$(git rev-parse --show-toplevel)/science"    # from the worktree root
for p in ~/d/cancer/cancer-types/multiple-myeloma \
         ~/d/cancer/data-sources/cbioportal \
         ~/d/cancer/mechanisms/evolution \
         ~/d/protein-landscape \
         "$(git rev-parse --show-toplevel)"; do
  git -C "$p" show --numstat --format= HEAD
done | awk 'NF==3 {print $1+$2}' | sort -n | uniq -c
```

Expected distribution over 792 files, measured during design: **719 files at 6 changed lines, 21 at 4, and 52 spread across 7–12** (2 at 7, 29 at 8, 13 at 9, 8 at 12), where a long scalar additionally unwraps from PyYAML's 80-column default to the canonical `width=10_000`.

Report any bucket that differs, and any file above 12. §5.2 asserts the parsed values are unchanged, so an outsized diff should be reflow — but confirm it rather than assuming, by reading one such file's diff.

Note the last path is the toolkit worktree itself, whose `HEAD` at this point is the `meta` corpus commit from Step 6. If Step 6 was not the most recent commit on this branch, name its SHA explicitly instead of `HEAD`.

---

## Follow-up work this plan does not do

Recorded so a later reader does not mistake these for oversights. All are §7 exclusions in the design.

- The ~20 never-authored dumped defaults each legacy record carries.
- The legacy triple (`legacy_relation_label`, `legacy_patch`, `legacy_edge_id`).
- The remaining unquoted-date records in other kinds.
- Retrofitting the workbench emitter's `created`/`updated` force-quoting — until that lands, a repaired record's dates revert to single quotes on its next workbench update. Expected, harmless, and the reason §3.4 calls the normalization temporary.
- Containing `append_entity_source_ref`, which still writes without `certify_persisted`.
- Arming the `proposition` and `evidence-line` mixins.
