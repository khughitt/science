# D5 — Entity Schema Convergence: Implementation Plan

> **For agentic workers:** implement this task-by-task. Steps use checkbox (`- [ ]`) syntax.
> Every task ends with a green gate and a commit.

**Goal:** Make one authoritative, versioned, composable JSON Schema the source of truth for a
project-authored entity kind — and migrate `hypothesis` onto it, splitting the collapsed
`status` field into a lifecycle (`status`) and a verdict (`verdict`) without fabricating a
single fact.

**Architecture:** Converge on the schema system that **already exists** (commons'
`entity_schema`: `schema_profile` → `allOf` composition → Draft 2020-12). Do **not** invent a
second one. Project kinds join it via a new **base 2.0** (the base 1.0 `kind` enum structurally
cannot admit them) plus a per-kind mixin. Pydantic becomes a *projection* after schema
validation, never the authority.

**Tech stack:** Python 3.12+, Pydantic v2, `jsonschema` (Draft 2020-12), Click, `uv`, pytest, rdflib.

**Contract inputs (read these first — they are ruled, not proposals):**
- [`2026-07-12-authoritative-entity-schema-design.md`](2026-07-12-authoritative-entity-schema-design.md) — the architecture, rev 7. **§7.3 (the audited contract), §7.4 (the terminal invariant), §9 (D1–D5), §10 rev 7 (the corrected mapping).**
- [`2026-07-12-d4-status-vocabulary-audit.md`](2026-07-12-d4-status-vocabulary-audit.md) — per-kind excavation.

---

## Global constraints

These apply to **every** task. They are not restated per-task.

1. **No "legacy"/"compatibility" layer.** No heuristic dual-read of `status`. A migration slice
   moves schema + sources + templates + consumers **together, or not at all**.
2. **Never fabricate a fact.** The migration may only write values it can *derive*. Where it
   cannot, it **refuses the file, reports it, and exits non-zero**. Three named traps (design §9
   D5): no mechanical `disposition: closed` → `retired`; an existing `status: archived` has
   already destroyed its verdict (leave `verdict` **absent**, report the loss); `paper`'s
   `paywalled`/`preprint`/`stub`/`background` are **not** reading states.
3. **Fail early, no silent fallbacks.** Explicit over defensive.
4. **Composition over inheritance.**
5. **No AI-attribution trailer** on any commit or PR.
6. **Docs/code use `~/d/`**, never `/home/keith/` or `/mnt/ssd/Dropbox/`.
7. **Run from the package dir.** There is no root `pyproject.toml`.
   - `cd science && uv run --frozen pytest` · `uv run ruff check` · `uv run pyright`
   - `cd science/model && uv run --frozen pytest`
8. **A check that only fires on downstream data MUST be run against downstream data before
   shipping.** This plan's own origin is a check that was green in CI and broke five projects.
   Every task that changes validation ends by running `science validate` in a real project.

---

## What the corpus actually says (measured, not assumed)

147 authored hypotheses across `~/d/*` (excluding the `natural-systems--t664` worktree dupe).

| `status` × `phase` | n |
|---|---|
| `proposed` + `active` | **60** |
| `proposed` + `candidate` | 36 |
| `proposed` + *(absent)* | 28 |
| `weakened` + `active` | 6 |
| `supported` + *(absent)* | 4 |
| `under-investigation` + *(absent)* | 4 |
| `supported` + `active` | 2 |
| `active` + *(absent)* | 2 *(off-vocabulary)* |
| `weakened` + `candidate`, `active`+`active`, `partially-supported`+*(absent)* | 1 each |
| **`retired` + `candidate`** | **1** ← `natural-systems/0009` |
| *(no status)* + *(no phase)* | 1 ← test fixture |

**`disposition:` — authored on ZERO of 147.** It ships in the model, the template, the
materializer, and `attention.py`, and **nothing has ever written it**. Deleting it is free: there
is no migration, because there is no data.

**The mapping (design §10 rev 7 — inverted from earlier revisions, which the cross-tab refuted):**

| source | → target |
|---|---|
| `phase: candidate` | `status: draft` |
| `phase: active` **or absent** | `status: active` |
| `status: proposed` \| `under-investigation` | **`verdict` absent** — contributes nothing to lifecycle |
| `status: supported`\|`weakened`\|`partially-supported`\|`refuted` | `verdict: <same>` |

→ **145 deterministic, 2 refused.** The 2: a test fixture with no `status`, and
`natural-systems/0009` (`retired` + `candidate`) — the file whose corruption opened this arc.

---

## File structure

**New (`science/model/src/science_model/`):**
- `schemas/science-entity-base-2.0.json` — base admitting project kinds. Commons stays on 1.0.
- `schemas/mixin-hypothesis-1.0.json` — the hypothesis contract: lifecycle enum, `verdict`, `closure_basis`, terminal invariant.
- `entity_schema/resolution.py` — cross-record invariants JSON Schema cannot express (D3 escape hatch).

**Modified (model):**
- `entity_schema/profile.py` — admit project mixins; per-kind base version.
- `entity_schema/validator.py` — `validate_as(entity, profile)`; drop the base-only rejection's stale message.
- `entities.py` — delete `disposition`/`disposition_basis`; add `verdict`/`closure_basis`.
- `profiles/core.py` — hypothesis `statuses` → the lifecycle; `default_status` → `active`.
- `templates/hypothesis.md` (and the repo-root `templates/hypothesis.md` — **two copies, keep in sync**).

**Modified (tool, `science/src/science_tool/`):**
- `entities.py` — `_LIVE_STATUSES`; `edit_entity` becomes the lifecycle boundary.
- `entities_cli.py` — `--verdict`, `--closure-basis`.
- `hypotheses_cli.py` — `--phase` → `--status`.
- `graph/attention.py` — `DEBT_QUESTION_STATUSES`, the `disposition` reader.
- `graph/materialize.py` — emit `sci:verdict`; drop `sci:disposition`.
- `validate/checks/hypotheses.py` — drop the `phase` check.
- `annotation/promote.py` — `phase: candidate` → `status: draft`.
- `migrations/` — the new migration command.

**Commands (markdown):** `commands/big-picture.md`, `commands/add-hypothesis.md`.

---

## Phase 1 — The inventory instrument (ruled steps 1–2)

*No meaning changes. Report only. This certifies the mapping before anything depends on it.*

### Task 1: `science entity status-inventory`

**Files:**
- Create: `science/src/science_tool/status_inventory.py`
- Modify: `science/src/science_tool/entities_cli.py`
- Test: `science/tests/test_status_inventory.py`

**Interfaces:**
- Produces: `inventory(project_root: Path) -> StatusInventory` where
  `StatusInventory` is a frozen dataclass with
  `rows: list[InventoryRow]`, `deterministic: list[InventoryRow]`, `ambiguous: list[InventoryRow]`.
  `InventoryRow(path: Path, kind: str, status: str | None, phase: str | None, target_status: str | None, target_verdict: str | None, ambiguity: str | None)`.
  Task 8 consumes `inventory()` directly — it is the migration's planner.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_status_inventory.py
from pathlib import Path

from science_tool.status_inventory import inventory


def _hyp(root: Path, name: str, *, status: str | None, phase: str | None) -> None:
    d = root / "entities" / "hypotheses"
    d.mkdir(parents=True, exist_ok=True)
    lines = ["---", f'id: "hypothesis:{name}"', 'kind: "hypothesis"', 'title: "T"']
    if status is not None:
        lines.append(f'status: "{status}"')
    if phase is not None:
        lines.append(f'phase: "{phase}"')
    lines += ["---", "", "body"]
    (d / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")


def test_phase_is_the_lifecycle_and_status_is_the_verdict(tmp_path: Path) -> None:
    # The 60-file cohort: template defaults. `phase` wins the lifecycle; `proposed`
    # means "no verdict yet", which is ABSENCE -- not `draft`.
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")
    row = inventory(tmp_path).rows[0]
    assert row.target_status == "active"
    assert row.target_verdict is None
    assert row.ambiguity is None


def test_absent_phase_defaults_to_active(tmp_path: Path) -> None:
    _hyp(tmp_path, "0002-b", status="proposed", phase=None)
    row = inventory(tmp_path).rows[0]
    assert row.target_status == "active"


def test_candidate_becomes_draft_and_keeps_its_verdict(tmp_path: Path) -> None:
    # Axes are orthogonal: a candidate frame CAN carry a verdict.
    _hyp(tmp_path, "0003-c", status="weakened", phase="candidate")
    row = inventory(tmp_path).rows[0]
    assert row.target_status == "draft"
    assert row.target_verdict == "weakened"


def test_retired_is_refused_not_guessed(tmp_path: Path) -> None:
    # natural-systems/0009. `retired` destroyed lifecycle, verdict AND closure reason.
    # No rule recovers them. The migration must stop.
    _hyp(tmp_path, "0009-d", status="retired", phase="candidate")
    inv = inventory(tmp_path)
    assert inv.deterministic == []
    assert len(inv.ambiguous) == 1
    assert "retired" in inv.ambiguous[0].ambiguity
    assert inv.ambiguous[0].target_status is None  # never guessed


def test_missing_status_is_refused(tmp_path: Path) -> None:
    _hyp(tmp_path, "0010-e", status=None, phase=None)
    inv = inventory(tmp_path)
    assert len(inv.ambiguous) == 1
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd science && uv run --frozen pytest tests/test_status_inventory.py -q
```
Expected: `ModuleNotFoundError: No module named 'science_tool.status_inventory'`

- [ ] **Step 3: Implement**

```python
# science/src/science_tool/status_inventory.py
"""Inventory hypothesis lifecycle/verdict values, and classify each file as
deterministically migratable or requiring authored adjudication.

This is the migration's PLANNER, and it is deliberately a separate, report-only
instrument: nothing may rewrite a source file until this has been run against the
real corpus and read by a human (design §9, D5 — report before apply).

The mapping is design §10 rev 7, and it INVERTS what earlier revisions assumed.
`phase` is the lifecycle; `status` was only ever the verdict. `proposed` and
`under-investigation` are not states -- they are the collapsed field's way of saying
"the evidence has not spoken", which is exactly what an ABSENT verdict already means
(D1). Mapping them to `draft` would have mis-migrated 88 of 147 files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from science_tool.entity_scan import iter_entity_markdown
from science_tool.frontmatter import read_frontmatter

# `status` values that carry an epistemic verdict.
_VERDICTS = frozenset({"supported", "weakened", "partially-supported", "refuted"})

# `status` values that assert the evidence has NOT spoken. They map to verdict ABSENCE,
# and contribute nothing to the lifecycle.
_NO_VERDICT = frozenset({"proposed", "under-investigation"})

# `phase` -> lifecycle. An absent `phase` defaults to `active`: the template ships
# `phase: "active"`, hypotheses_cli.py defaults to it, and commands/big-picture.md:62
# says so explicitly.
_PHASE_TO_STATUS = {"candidate": "draft", "active": "active", None: "active"}

# Off-vocabulary `status` values that are unambiguously LIFECYCLE words (authors reaching
# for a state the schema did not offer). Safe only when `phase` agrees.
_LIFECYCLE_WORDS = frozenset({"active", "draft"})


@dataclass(frozen=True, slots=True)
class InventoryRow:
    path: Path
    kind: str
    status: str | None
    phase: str | None
    target_status: str | None
    target_verdict: str | None
    ambiguity: str | None


@dataclass(frozen=True, slots=True)
class StatusInventory:
    rows: list[InventoryRow]

    @property
    def deterministic(self) -> list[InventoryRow]:
        return [r for r in self.rows if r.ambiguity is None]

    @property
    def ambiguous(self) -> list[InventoryRow]:
        return [r for r in self.rows if r.ambiguity is not None]


def _classify(path: Path, status: str | None, phase: str | None) -> InventoryRow:
    row = lambda **kw: InventoryRow(  # noqa: E731
        path=path, kind="hypothesis", status=status, phase=phase, **kw
    )
    if status is None:
        return row(
            target_status=None,
            target_verdict=None,
            ambiguity="no `status` at all: nothing to derive a verdict from",
        )
    if phase is not None and phase not in _PHASE_TO_STATUS:
        return row(
            target_status=None,
            target_verdict=None,
            ambiguity=f"unknown phase {phase!r} (expected candidate|active)",
        )

    lifecycle = _PHASE_TO_STATUS[phase]

    if status in _NO_VERDICT:
        return row(target_status=lifecycle, target_verdict=None, ambiguity=None)
    if status in _VERDICTS:
        return row(target_status=lifecycle, target_verdict=status, ambiguity=None)
    if status in _LIFECYCLE_WORDS and status == lifecycle:
        # Author wrote a lifecycle word into `status`; `phase` independently agrees.
        return row(target_status=lifecycle, target_verdict=None, ambiguity=None)

    # Everything else -- notably `retired`/`archived`. A terminal word in the collapsed
    # field destroyed the lifecycle, the verdict AND the closure reason simultaneously.
    # There is nothing left to recover, and inventing any of the three would be exactly
    # the fabrication this whole design exists to prevent.
    return row(
        target_status=None,
        target_verdict=None,
        ambiguity=(
            f"status {status!r} is terminal or unknown: the prior verdict and the closure "
            f"reason are unrecoverable. An author must supply status + verdict + closure_basis."
        ),
    )


def inventory(project_root: Path) -> StatusInventory:
    entities_root = project_root / "entities"
    if not entities_root.is_dir():
        return StatusInventory(rows=[])
    rows: list[InventoryRow] = []
    for path in iter_entity_markdown(entities_root):
        fm = read_frontmatter(path)
        if fm.get("kind") != "hypothesis":
            continue
        status = fm.get("status")
        phase = fm.get("phase")
        rows.append(
            _classify(
                path,
                status if isinstance(status, str) and status else None,
                phase if isinstance(phase, str) and phase else None,
            )
        )
    return StatusInventory(rows=rows)
```

> **Check `science_tool.frontmatter`'s real reader name before writing this** — the repo
> converged on one frontmatter API in commit `fa4b3185`. Use that function; do not add a
> second parser. If the name differs, fix the import, not the API.

- [ ] **Step 4: Green**

```bash
cd science && uv run --frozen pytest tests/test_status_inventory.py -q
```
Expected: `5 passed`

- [ ] **Step 5: Wire the CLI (report-only)**

Add to `science/src/science_tool/entities_cli.py`, in the `entity_group`:

```python
@entity_group.command("status-inventory")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
def entity_status_inventory(as_json: bool) -> None:
    """Report hypothesis lifecycle/verdict migration targets. Writes nothing."""
    from science_tool.status_inventory import inventory

    inv = inventory(Path.cwd())
    if as_json:
        click.echo(
            json.dumps(
                [
                    {
                        "path": str(r.path),
                        "status": r.status,
                        "phase": r.phase,
                        "target_status": r.target_status,
                        "target_verdict": r.target_verdict,
                        "ambiguity": r.ambiguity,
                    }
                    for r in inv.rows
                ],
                indent=2,
            )
        )
        return
    click.echo(f"{len(inv.deterministic)} deterministic, {len(inv.ambiguous)} need adjudication")
    for r in inv.ambiguous:
        click.echo(f"  REFUSED {r.path}: {r.ambiguity}")
```

- [ ] **Step 6: Run it against the REAL corpus** (this is the certification, not the unit test)

```bash
cd ~/d/natural-systems && uv run science entity status-inventory
```
Expected: `13 deterministic, 1 need adjudication` and the refused file is
`entities/hypotheses/0009-local-structure-globalization-obstruction.md`.

**If any other file is refused, STOP.** The mapping is not certified and Task 8 must not run.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/status_inventory.py science/src/science_tool/entities_cli.py science/tests/test_status_inventory.py
git commit -m "feat(entities): status-inventory -- certify the hypothesis mapping before applying it"
```

---

## Phase 2 — The schema substrate (ruled step 3)

*Still no meaning change. Build the authority; do not yet point anything at it.*

### Task 2: `science-entity-base-2.0` — a base that can hold a project kind

**Why a new base and not an extension:** composition is a pure `allOf`
(`entity_schema/validator.py:82-87`), and **an `allOf` can only narrow**. Base 1.0 pins
`kind` to `{"enum": ["dataset","paper","topic","theme"]}` and `id` to
`^(dataset|paper|topic|theme):…`. No extension can widen either. This is a base-version bump
by construction.

**Why it is safe:** every mixin pins its own kind with a `const` (`mixin-dataset-1.0.json`:
`"kind": {"const": "dataset"}`, and likewise paper/topic/theme). The base enum is redundant
defence; the **mixin** is the real constraint. Widening the base cannot leak a `hypothesis` into
a dataset profile.

**Why commons does not move:** commons records keep pinning `science-entity-base/1.0`. Two base
versions coexist — that is what versioning is *for*. **Zero commons churn, zero commons risk.**

**Files:**
- Create: `science/model/src/science_model/schemas/science-entity-base-2.0.json`
- Test: `science/model/tests/test_base_2_0.py`

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_base_2_0.py
import json
from importlib.resources import files

import pytest

from science_model.entity_schema import EntityValidationError, EntityValidator, parse_profile

BASE_2 = "science-entity-base/2.0"


def _load(name: str) -> dict:
    return json.loads((files("science_model.schemas") / name).read_text(encoding="utf-8"))


def test_base_2_0_admits_project_kinds() -> None:
    base = _load("science-entity-base-2.0.json")
    assert "hypothesis" in base["properties"]["kind"]["enum"]
    assert "dataset" in base["properties"]["kind"]["enum"]  # commons kinds still admitted


def test_base_2_0_does_not_require_version() -> None:
    # `version` is a commons concept (semver on a shared record). Project entities are
    # versioned by the repo's git history and have no such field.
    assert "version" not in _load("science-entity-base-2.0.json")["required"]


def test_base_1_0_is_untouched() -> None:
    # Commons pins 1.0. If this test ever fails, 369 commons records are at risk.
    base1 = _load("science-entity-base-1.0.json")
    assert base1["properties"]["kind"]["enum"] == ["dataset", "paper", "topic", "theme"]
    assert "version" in base1["required"]


def test_a_dataset_mixin_still_pins_kind_under_base_2() -> None:
    # The safety argument, executed: base 2.0's widened enum cannot leak, because the
    # mixin's `const` narrows it back.
    v = EntityValidator()
    with pytest.raises(EntityValidationError):
        v.validate_as(
            {
                "id": "dataset:x",
                "kind": "hypothesis",  # <- wrong kind for a dataset profile
                "title": "T",
                "created": "2026-07-12",
                "updated": "2026-07-12",
                "origin": "external",
                "tier": "raw",
            },
            parse_profile(f"{BASE_2}+dataset/1.0"),
        )
```

- [ ] **Step 2: Run and fail**

```bash
cd science/model && uv run --frozen pytest tests/test_base_2_0.py -q
```
Expected: FAIL — `FileNotFoundError` / `AttributeError: 'EntityValidator' object has no attribute 'validate_as'`.

- [ ] **Step 3: Create the schema**

Copy `science-entity-base-1.0.json` to `science-entity-base-2.0.json` and change exactly four
things (leave everything else — `$defs`, `licenses`, `contributors`, all `science:merge`
annotations — byte-identical):

```json
{
  "$id": "https://schemas.science/science-entity-base-2.0.json",
  "title": "science entity base profile (admits project-authored kinds)",
  "required": ["id", "kind", "title", "created", "updated"],
  "properties": {
    "schema_profile": {
      "type": "string",
      "pattern": "^science-entity-base/[0-9]+\\.[0-9]+(\\+[a-z][a-z0-9._-]*/[0-9]+\\.[0-9]+)*$"
    },
    "id": {
      "type": "string",
      "pattern": "^(dataset|paper|topic|theme|hypothesis|question|task|report|plan|pre-registration|synthesis|interpretation|discussion|finding|observation|evidence-line|proposition|concept|decision|workflow|workflow-run|method|search|story|mechanism|falsification):[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
    },
    "kind": {
      "enum": ["dataset", "paper", "topic", "theme", "hypothesis", "question", "task", "report", "plan", "pre-registration", "synthesis", "interpretation", "discussion", "finding", "observation", "evidence-line", "proposition", "concept", "decision", "workflow", "workflow-run", "method", "search", "story", "mechanism", "falsification"]
    },
    "version": {
      "type": "string",
      "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$",
      "science:merge": "forbidden"
    }
  }
}
```

Four deltas, and only four: **(a)** `$id`/`title`; **(b)** `required` drops
`schema_profile` (project entities derive it — Task 3) and `version`; **(c)** `kind` enum and
`id` pattern widened to the project kinds; **(d)** the `id` pattern's suffix widened to
`[A-Za-z0-9._-]{0,127}` (hypothesis slugs like `0009-local-structure-globalization-obstruction`
exceed 64 chars).

> Derive the kind list from `CORE_PROFILE.entity_kinds` when you write the file — do **not**
> hand-type it and hope. A guard test in Task 4 pins the two lists together.

- [ ] **Step 4: Green** (after Task 3 lands `validate_as`; run the first three tests now)

```bash
cd science/model && uv run --frozen pytest tests/test_base_2_0.py -q -k "not mixin"
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/schemas/science-entity-base-2.0.json science/model/tests/test_base_2_0.py
git commit -m "feat(schema): science-entity-base-2.0 -- a base that admits project-authored kinds"
```

---

### Task 3: Profile plumbing — project mixins and `validate_as`

**Files:**
- Modify: `science/model/src/science_model/entity_schema/profile.py`
- Modify: `science/model/src/science_model/entity_schema/validator.py`
- Test: `science/model/tests/test_project_profiles.py`

**Interfaces:**
- Produces: `EntityValidator.validate_as(entity: dict[str, Any], profile: ProfileString) -> None`
  — validate against an **explicit** profile rather than reading `entity["schema_profile"]`.
  Project entities do not carry `schema_profile` in their frontmatter; it is derived from `kind`.
  Tasks 5 and 7 call this.
- Produces: `default_profile_for_kind("hypothesis")` → parsed `science-entity-base/2.0+hypothesis/1.0`.

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_project_profiles.py
import pytest

from science_model.entity_schema import default_profile_for_kind, parse_profile
from science_model.entity_schema.profile import ProfileParseError


def test_hypothesis_derives_base_2_profile() -> None:
    assert default_profile_for_kind("hypothesis").render() == "science-entity-base/2.0+hypothesis/1.0"


def test_commons_kinds_stay_on_base_1() -> None:
    # Non-negotiable: 369 live commons records pin base 1.0.
    assert default_profile_for_kind("dataset").render() == "science-entity-base/1.0+dataset/1.0"
    assert default_profile_for_kind("paper").render() == "science-entity-base/1.0+paper/2.0"


def test_parse_accepts_a_project_mixin() -> None:
    p = parse_profile("science-entity-base/2.0+hypothesis/1.0")
    assert p.mixin is not None and p.mixin.name == "hypothesis"


def test_parse_still_rejects_an_unknown_mixin() -> None:
    with pytest.raises(ProfileParseError):
        parse_profile("science-entity-base/2.0+nonsense/1.0")
```

- [ ] **Step 2: Run and fail**

```bash
cd science/model && uv run --frozen pytest tests/test_project_profiles.py -q
```
Expected: FAIL — `ProfileParseError: schema_profile mixin must be one of ['dataset','paper','theme','topic']`

- [ ] **Step 3: Implement**

In `profile.py`, replace lines 16 and 75–102:

```python
BASE_NAME = "science-entity-base"

# Commons type mixins (base 1.0). Their records are shared across repos and versioned.
COMMONS_MIXIN_NAMES = frozenset({"dataset", "paper", "topic", "theme"})

# Project-authored kinds converging onto the same schema system (base 2.0). Grows one
# entry per migrated kind -- this is the P2m slice list.
PROJECT_MIXIN_NAMES = frozenset({"hypothesis"})

TYPE_MIXIN_NAMES = COMMONS_MIXIN_NAMES | PROJECT_MIXIN_NAMES
```

and:

```python
# Default mixin version per kind, used by `default_profile_for_kind`.
_DEFAULT_MIXIN_VERSION: dict[str, str] = {
    "dataset": "1.0",
    "paper": "2.0",
    "topic": "2.0",
    "theme": "2.0",
    "hypothesis": "1.0",
}

# The base version is per-kind, NOT global. Commons kinds pin base 1.0 -- 369 live records
# depend on it and there is no reason to move them. Project kinds need base 2.0, whose
# `kind` enum and `id` pattern admit them (base 1.0's structurally cannot, and an allOf can
# only narrow). Two base versions coexisting is what versioning is FOR.
_BASE_VERSION_FOR_MIXIN: dict[str, str] = {
    **{name: "1.0" for name in COMMONS_MIXIN_NAMES},
    **{name: "2.0" for name in PROJECT_MIXIN_NAMES},
}


def default_profile_for_kind(kind: str) -> ProfileString:
    """Return the default parsed ProfileString for a kind.

    Project-authored entities do NOT carry `schema_profile` in their frontmatter -- the
    profile is derived from `kind` here. (Commons records DO carry it: they are shared
    across repos, so their profile must travel with the record. A project entity is
    versioned by the repo that contains it.)

    Raises ProfileParseError for an unknown kind.
    """
    if kind not in _DEFAULT_MIXIN_VERSION:
        raise ProfileParseError(
            f"unknown kind {kind!r}; expected one of {sorted(_DEFAULT_MIXIN_VERSION)}"
        )
    base_version = _BASE_VERSION_FOR_MIXIN[kind]
    return parse_profile(
        f"{BASE_NAME}/{base_version}+{kind}/{_DEFAULT_MIXIN_VERSION[kind]}"
    )
```

In `validator.py`, add `validate_as` and make `validate` delegate to it:

```python
    def validate(self, entity: dict[str, Any]) -> None:
        """Validate against the entity's OWN declared `schema_profile` (commons path)."""
        profile_str = entity.get("schema_profile")
        if not profile_str:
            raise EntityValidationError("entity is missing required schema_profile field")
        try:
            profile = parse_profile(profile_str)
        except ProfileParseError as exc:
            raise EntityValidationError(f"invalid schema_profile: {exc}") from exc
        self.validate_as(entity, profile)

    def validate_as(self, entity: dict[str, Any], profile: ProfileString) -> None:
        """Validate against an EXPLICIT profile.

        Project entities derive their profile from `kind` (see `default_profile_for_kind`)
        rather than carrying `schema_profile` in frontmatter, so there is nothing in the
        payload to read. Passing the profile in is the honest expression of that: it does
        not mutate the caller's dict, and it keeps `schema_profile` a commons concept.
        """
        if profile.mixin is None:
            raise EntityValidationError(
                f"schema_profile must include a type mixin (one of "
                f"{sorted(TYPE_MIXIN_NAMES)}) — base-only profiles are not valid for "
                f"entity payloads",
            )
        composed = self._compose(profile)
        validator = Draft202012Validator(
            composed, format_checker=Draft202012Validator.FORMAT_CHECKER
        )
        errors = sorted(validator.iter_errors(entity), key=lambda e: list(e.absolute_path))
        if errors:
            joined = "; ".join(_format_error(err) for err in errors)
            raise EntityValidationError(
                f"entity failed schema validation: {joined}", errors=errors
            )
```

Update `validator.py`'s import to pull `TYPE_MIXIN_NAMES` from `profile`. The old hardcoded
message `"(dataset/paper/topic/theme)"` is now a lie — that is why it becomes an f-string.

- [ ] **Step 4: Green**

```bash
cd science/model && uv run --frozen pytest tests/test_project_profiles.py tests/ -q
```
Expected: `4 passed` + the whole model suite still green (the commons profile tests are the
canary: if any commons profile string changed, you broke 369 records).

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/entity_schema/profile.py science/model/src/science_model/entity_schema/validator.py science/model/tests/test_project_profiles.py
git commit -m "feat(schema): admit project mixins on base 2.0; add validate_as for derived profiles"
```

---

### Task 4: `mixin-hypothesis-1.0` — the contract, including the terminal invariant

This is where the ruled invariants become executable.

**Files:**
- Create: `science/model/src/science_model/schemas/mixin-hypothesis-1.0.json`
- Test: `science/model/tests/test_mixin_hypothesis.py`

- [ ] **Step 1: Write the failing test** — one test per ruled invariant

```python
# science/model/tests/test_mixin_hypothesis.py
import pytest

from science_model.entity_schema import (
    EntityValidationError,
    EntityValidator,
    default_profile_for_kind,
)
from science_model.profiles.core import CORE_PROFILE

PROFILE = default_profile_for_kind("hypothesis")
V = EntityValidator()


def _h(**over) -> dict:
    base = {
        "id": "hypothesis:0001-x",
        "kind": "hypothesis",
        "title": "T",
        "created": "2026-07-12",
        "updated": "2026-07-12",
        "status": "active",
    }
    base.update(over)
    return base


def test_lifecycle_vocabulary_is_the_ruled_one() -> None:
    V.validate_as(_h(status="draft"), PROFILE)
    V.validate_as(_h(status="active"), PROFILE)
    for dead in ("proposed", "under-investigation", "supported", "weakened"):
        with pytest.raises(EntityValidationError):
            V.validate_as(_h(status=dead), PROFILE)  # these are verdicts, not lifecycle


def test_verdict_vocabulary_excludes_unassessed_spellings() -> None:
    V.validate_as(_h(status="active", verdict="refuted"), PROFILE)
    for bad in ("proposed", "under-investigation"):
        # D1: absence already means "not yet assessed". Admitting these would make three
        # spellings of one state and re-collapse the axis.
        with pytest.raises(EntityValidationError):
            V.validate_as(_h(verdict=bad), PROFILE)


def test_axes_are_orthogonal() -> None:
    # The cell the collapsed field could not express.
    V.validate_as(_h(status="superseded", verdict="supported", superseded_by="hypothesis:0002-y"), PROFILE)
    V.validate_as(_h(status="draft", verdict="weakened"), PROFILE)  # a weakened candidate frame


def test_complete_REQUIRES_a_verdict() -> None:
    # RULED (design rev 6): prohibited outright, NOT discharged by closure_basis.
    # "You cannot conclude without concluding something."
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="complete"), PROFILE)
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="complete", closure_basis="ran out of time"), PROFILE)
    V.validate_as(_h(status="complete", verdict="supported"), PROFILE)


def test_retired_always_requires_a_closure_basis() -> None:
    # `retired` is the only terminal with NO structural basis available to it.
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="retired"), PROFILE)
    V.validate_as(_h(status="retired", closure_basis="superseded by the h5 reframing"), PROFILE)


def test_superseded_requires_lineage_OR_a_basis() -> None:
    # Presence, not resolution -- resolution is the D3 validator's job (Task 5).
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="superseded"), PROFILE)
    V.validate_as(_h(status="superseded", superseded_by="hypothesis:0002-y"), PROFILE)
    V.validate_as(_h(status="superseded", closure_basis="folded into the h5 reframing"), PROFILE)


def test_phase_and_disposition_are_gone() -> None:
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(phase="candidate"), PROFILE)
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(disposition="closed"), PROFILE)


def test_schema_and_descriptor_agree() -> None:
    # The bidirectional gate. A vocabulary that disagrees with its descriptor is exactly
    # the uncertified instrument that broke five projects.
    import json
    from importlib.resources import files

    schema = json.loads(
        (files("science_model.schemas") / "mixin-hypothesis-1.0.json").read_text(encoding="utf-8")
    )
    descriptor = next(k for k in CORE_PROFILE.entity_kinds if k.name == "hypothesis")
    assert sorted(schema["properties"]["status"]["enum"]) == sorted(descriptor.statuses)
```

- [ ] **Step 2: Run and fail**

```bash
cd science/model && uv run --frozen pytest tests/test_mixin_hypothesis.py -q
```
Expected: FAIL — `SchemaNotFoundError` for `mixin-hypothesis-1.0.json`.

- [ ] **Step 3: Write the schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/mixin-hypothesis-1.0.json",
  "title": "hypothesis type mixin",
  "type": "object",
  "required": ["id", "kind", "status"],
  "properties": {
    "kind": { "const": "hypothesis" },

    "status": {
      "description": "LIFECYCLE. Not the verdict. Sourced from the old `phase` field.",
      "enum": ["draft", "active", "complete", "superseded", "retired", "archived"]
    },

    "verdict": {
      "description": "EPISTEMIC. What the evidence concludes. ABSENT = not yet assessed -- which is why `proposed`/`under-investigation` are NOT admitted here: they would be a third spelling of absence.",
      "enum": ["partially-supported", "supported", "weakened", "refuted"]
    },

    "closure_basis": {
      "description": "The AUTHORED reason a terminal entity closed, required when no structural basis exists. The state is derivable; the reason is not.",
      "type": "string",
      "minLength": 1
    },

    "superseded_by": { "type": "string", "pattern": "^hypothesis:" },
    "resynthesized_into": { "type": "string", "pattern": "^hypothesis:" },

    "phase": false,
    "disposition": false,
    "disposition_basis": false
  },

  "allOf": [
    {
      "$comment": "RULED (design rev 6): you cannot conclude without concluding something. `complete` REQUIRES a verdict, and closure_basis does NOT discharge it -- admitting `complete` + absent-verdict would give `retired + closure_basis` a second spelling that reads to every consumer as though the hypothesis had been resolved.",
      "if": { "properties": { "status": { "const": "complete" } }, "required": ["status"] },
      "then": { "required": ["verdict"] }
    },
    {
      "$comment": "`retired` is the only terminal with no structural basis available to it, so it ALWAYS requires an authored one. This is the fb-005 no-hidden-debt guarantee.",
      "if": { "properties": { "status": { "const": "retired" } }, "required": ["status"] },
      "then": { "required": ["closure_basis"] }
    },
    {
      "$comment": "`superseded` is discharged by lineage OR by an authored basis. The condition is the PRESENCE of the structure, never the status word: the live-lineage contract explicitly permits a live `superseded` with no lineage, so keying off the word alone would let a lineage-less supersession close with no reason recorded anywhere. Whether the lineage RESOLVES is a cross-record fact, and belongs to the D3 validator -- not here.",
      "if": { "properties": { "status": { "const": "superseded" } }, "required": ["status"] },
      "then": {
        "anyOf": [
          { "required": ["superseded_by"] },
          { "required": ["resynthesized_into"] },
          { "required": ["closure_basis"] }
        ]
      }
    },
    {
      "$comment": "`archived` is discharged by an archive record, whose EXISTENCE only the D3 validator can check. The schema can only demand that one be named.",
      "if": { "properties": { "status": { "const": "archived" } }, "required": ["status"] },
      "then": { "anyOf": [{ "required": ["archive_ref"] }, { "required": ["closure_basis"] }] }
    }
  ]
}
```

> `"phase": false` / `"disposition": false` is the JSON Schema idiom for *"this property must
> not appear."* It is what makes the deletion **enforced** rather than merely intended — a
> re-introduced `phase:` becomes a validation error, not a silently-ignored key.

- [ ] **Step 4: Green**

```bash
cd science/model && uv run --frozen pytest tests/test_mixin_hypothesis.py -q
```
Expected: `8 passed`. `test_schema_and_descriptor_agree` will still be RED — it is a
forward reference to Task 6. Mark it `@pytest.mark.xfail(strict=True, reason="descriptor lands in Task 6")`
and **remove the marker in Task 6**.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/schemas/mixin-hypothesis-1.0.json science/model/tests/test_mixin_hypothesis.py
git commit -m "feat(schema): mixin-hypothesis-1.0 -- lifecycle/verdict split with terminal invariants"
```

---

### Task 5: The D3 resolution validator — invariants JSON Schema *cannot* express

Schema validates **one record in isolation**. It cannot resolve a successor ID, confirm an
archive record exists, or check that a verdict's evidence is real. **Presence is schema;
resolution is a validator.** Without this, a *present but dangling* `superseded_by:` satisfies
the schema and closes the entity with no real reason behind it — the hole in a subtler dress.

**Files:**
- Create: `science/model/src/science_model/entity_schema/resolution.py`
- Test: `science/model/tests/test_resolution.py`

**Interfaces:**
- Produces: `check_resolution(entity: dict, *, known_ids: set[str]) -> list[str]` — returns
  human-readable violations, empty when clean. Task 7 calls it from `science validate`; Task 9
  calls it from `edit_entity`.

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_resolution.py
from science_model.entity_schema.resolution import check_resolution

KNOWN = {"hypothesis:0002-y"}


def test_dangling_successor_is_caught() -> None:
    # The whole reason this module exists: the schema is satisfied, the entity is closed,
    # and the reason it closed does not exist.
    v = check_resolution(
        {"id": "hypothesis:0001-x", "status": "superseded", "superseded_by": "hypothesis:9999-nope"},
        known_ids=KNOWN,
    )
    assert len(v) == 1 and "9999-nope" in v[0]


def test_resolving_successor_passes() -> None:
    assert check_resolution(
        {"id": "hypothesis:0001-x", "status": "superseded", "superseded_by": "hypothesis:0002-y"},
        known_ids=KNOWN,
    ) == []


def test_self_supersession_is_caught() -> None:
    v = check_resolution(
        {"id": "hypothesis:0002-y", "status": "superseded", "superseded_by": "hypothesis:0002-y"},
        known_ids=KNOWN,
    )
    assert len(v) == 1 and "itself" in v[0]


def test_a_basis_closed_entity_needs_no_lineage() -> None:
    assert check_resolution(
        {"id": "hypothesis:0001-x", "status": "superseded", "closure_basis": "folded into h5"},
        known_ids=KNOWN,
    ) == []


def test_live_entity_is_not_checked() -> None:
    assert check_resolution({"id": "hypothesis:0001-x", "status": "active"}, known_ids=set()) == []
```

- [ ] **Step 2: Run and fail**

```bash
cd science/model && uv run --frozen pytest tests/test_resolution.py -q
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# science/model/src/science_model/entity_schema/resolution.py
"""Cross-record invariants — the D3 escape hatch, enumerated.

JSON Schema is the authority for a record's SHAPE and for the PRESENCE of a structural
basis. It validates one record in isolation, so it structurally cannot answer: does this
successor ID resolve? does that archive record exist? Those are cross-record facts.

This module is that second layer, and it is deliberately a CLOSED LIST rather than an
open-ended second authority (design §9, D3). Getting the split wrong re-opens the hole it
was built to close: a PRESENT but DANGLING `superseded_by:` satisfies the schema, closes
the entity, and records no real reason for the closure.
"""

from __future__ import annotations

from typing import Any

_LINEAGE_KEYS = ("superseded_by", "resynthesized_into")


def check_resolution(entity: dict[str, Any], *, known_ids: set[str]) -> list[str]:
    """Return violations of cross-record terminal invariants. Empty == clean."""
    violations: list[str] = []
    status = entity.get("status")
    entity_id = entity.get("id", "<unknown>")

    if status not in {"superseded", "archived"}:
        return violations

    for key in _LINEAGE_KEYS:
        target = entity.get(key)
        if not target:
            continue
        if target == entity_id:
            violations.append(f"{entity_id}: {key} points at itself")
        elif target not in known_ids:
            violations.append(
                f"{entity_id}: {key} -> {target!r} does not resolve to any known entity; "
                f"the entity is closed and the reason it closed does not exist"
            )
    return violations
```

- [ ] **Step 4: Green**

```bash
cd science/model && uv run --frozen pytest tests/test_resolution.py -q
```
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/entity_schema/resolution.py science/model/tests/test_resolution.py
git commit -m "feat(schema): D3 resolution validator -- presence is schema, resolution is a validator"
```

---

## Phase 3 — The `hypothesis` P2m slice (ruled steps 4–5)

> **ATOMIC.** Tasks 6–10 change meaning. They land **together or not at all** — schema, sources,
> templates, consumers, graph diff. Do not merge a partial slice: a half-migrated corpus has two
> incompatible meanings of `status` live at once, which is precisely the state that forces the
> heuristic compatibility layer D5 forbids.

### Task 6: Descriptor + model — delete `disposition`, add `verdict`/`closure_basis`

**`disposition` is authored on ZERO of 147 hypotheses.** Deleting it is free: there is no data
to migrate. It ships in the model, the template, the materializer and `attention.py`, and nothing
has ever written it — which is why `list_rehoming_debt` returns `unwired(code="no_disposition_declared")`
on every real project today.

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py:32-51` (the hypothesis descriptor)
- Modify: `science/model/src/science_model/entities.py:797-839` (`HypothesisEntity`)
- Modify: `science/src/science_tool/entities.py` (`_LIVE_STATUSES`)
- Test: `science/model/tests/test_hypothesis_entity.py`

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_hypothesis_entity.py
import pytest
from pydantic import ValidationError

from science_model.entities import HypothesisEntity
from science_model.profiles.core import CORE_PROFILE


def _kind():
    return next(k for k in CORE_PROFILE.entity_kinds if k.name == "hypothesis")


def test_descriptor_declares_the_lifecycle_not_the_verdict() -> None:
    assert sorted(_kind().statuses) == sorted(
        ["draft", "active", "complete", "superseded", "retired", "archived"]
    )
    assert _kind().default_status == "active"


def test_verdict_is_a_first_class_field() -> None:
    h = HypothesisEntity(
        id="hypothesis:1", kind="hypothesis", title="T", project="p",
        status="active", verdict="refuted",
    )
    assert h.verdict == "refuted"


def test_complete_requires_a_verdict_in_the_projection_too() -> None:
    # The schema is the authority, but the projection must not be able to express a state
    # the schema forbids -- or the two drift and the projection becomes a bypass.
    with pytest.raises(ValidationError):
        HypothesisEntity(
            id="hypothesis:1", kind="hypothesis", title="T", project="p", status="complete"
        )


def test_retired_requires_a_closure_basis() -> None:
    with pytest.raises(ValidationError):
        HypothesisEntity(
            id="hypothesis:1", kind="hypothesis", title="T", project="p", status="retired"
        )
    HypothesisEntity(
        id="hypothesis:1", kind="hypothesis", title="T", project="p",
        status="retired", closure_basis="ran out of samples",
    )


def test_disposition_is_gone() -> None:
    assert "disposition" not in HypothesisEntity.model_fields
    assert "disposition_basis" not in HypothesisEntity.model_fields
```

- [ ] **Step 2: Run and fail**

```bash
cd science/model && uv run --frozen pytest tests/test_hypothesis_entity.py -q
```

- [ ] **Step 3: Rewrite the descriptor** (`profiles/core.py`)

```python
        EntityKind(
            name="hypothesis",
            canonical_prefix="hypothesis",
            layer="layer/core",
            description="Testable project hypothesis.",
            entity_class=EntityClass.EPISTEMIC,
            category=KindCategory.AUTHORED_CORE,
            template_ready=True,
            shortform="h",
            home="entities/hypotheses",
            strategy="numeric",
            # `status` is the LIFECYCLE, uniformly, on every kind. The old vocabulary
            # (proposed | under-investigation | partially-supported | supported | weakened |
            # refuted | archived) was the epistemic VERDICT wearing the lifecycle's name --
            # which left `archived` as the only lifecycle word a hypothesis had, and forced
            # authors to hand-roll `phase` to get the rest. The verdict now lives in
            # `verdict`; `phase` folds in here.
            default_status="active",
            statuses=[
                "draft",
                "active",
                "complete",
                "superseded",
                "retired",
                "archived",
            ],
        ),
```

> **`archived` must stay in this list.** `consolidate._is_consolidatable` (`consolidate.py:44-49`)
> returns False for a closed vocabulary lacking `archived` — dropping it silently breaks
> hypothesis consolidation.

**Step 3b — rewrite `HypothesisEntity`** (`entities.py`), replacing the whole class:

```python
class HypothesisEntity(ProjectEntity):
    """Hypothesis — two orthogonal axes, in two fields.

    `status` (inherited) is the LIFECYCLE: where this hypothesis is in its life as a work
    item. `verdict` is the EPISTEMIC conclusion: what the evidence says. Neither may be
    inferred from the other, and the cell that proves it is `superseded` + `supported` —
    formerly supported, now replaced — which the old collapsed field could not express at
    all: writing `superseded` OVERWROTE `supported` and destroyed the conclusion.

    `verdict` is ABSENT until the evidence speaks. That absence is load-bearing, and it is
    why `proposed` and `under-investigation` are not verdict values: they say the evidence
    has NOT spoken, which absence already says. Admitting them would make three spellings
    of one state.

    `closure_basis` is the authored reason a terminal entity closed. The state is
    derivable; the reason is not. It is required exactly when no STRUCTURAL basis exists —
    always for `retired` (which has none available), and for `superseded`/`archived` only
    when their lineage/archive record is missing.

    The JSON Schema (`mixin-hypothesis-1.0`) is the authority for all of this. These
    validators exist so the projection cannot express a state the schema forbids — if it
    could, the projection would be a bypass and the two would drift.
    """

    verdict: Literal["partially-supported", "supported", "weakened", "refuted"] | None = None
    closure_basis: str | None = None
    superseded_by: str | None = None
    resynthesized_into: str | None = None
    archive_ref: str | None = None

    @model_validator(mode="after")
    def _complete_requires_a_verdict(self) -> "HypothesisEntity":
        # RULED: you cannot conclude without concluding something. `closure_basis` does NOT
        # discharge this -- stopping for non-epistemic reasons is `retired` + closure_basis,
        # and admitting `complete` + absent-verdict would give that a second spelling which
        # reads, to every consumer, as though the hypothesis had been resolved.
        if self.status == "complete" and self.verdict is None:
            raise ValueError(
                "status: complete requires a verdict — a hypothesis concluded on "
                "non-epistemic grounds is `retired` with a closure_basis, not `complete`"
            )
        return self

    @model_validator(mode="after")
    def _terminal_requires_a_basis(self) -> "HypothesisEntity":
        if self.status == "retired" and not (self.closure_basis or "").strip():
            raise ValueError("status: retired requires closure_basis (it has no structural basis)")
        if self.status == "superseded" and not (
            self.superseded_by or self.resynthesized_into or (self.closure_basis or "").strip()
        ):
            raise ValueError(
                "status: superseded requires lineage (superseded_by / resynthesized_into) "
                "or an authored closure_basis"
            )
        if self.status == "archived" and not (
            self.archive_ref or (self.closure_basis or "").strip()
        ):
            raise ValueError("status: archived requires archive_ref or closure_basis")
        return self
```

**Step 3c — `_LIVE_STATUSES`** (`science/src/science_tool/entities.py:193-243`): remove
`proposed`, `under-investigation`, `partially-supported`, `supported`, `weakened`, `refuted`
**only if no other kind still declares them** — grep first:

```bash
cd science && rg -n '"(proposed|under-investigation|partially-supported|supported|weakened|refuted)"' ../science/model/src/science_model/profiles/
```

`draft`, `active`, `complete`, `retired` are already present; `superseded`/`archived` are in
`_HIDDEN_STATUSES`. The guard `test_every_declared_status_still_classified` fails loud if you
get this wrong — **let it drive you**.

- [ ] **Step 4: Green, and remove the Task-4 xfail marker**

```bash
cd science/model && uv run --frozen pytest -q
cd ../science && uv run --frozen pytest -q
```
Expected: `test_schema_and_descriptor_agree` now passes — delete its `xfail` marker.
**Other suites WILL go red here** (templates, materialize, attention). That is the slice
working as designed; Tasks 7–10 close them. Do not patch around them.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/profiles/core.py science/model/src/science_model/entities.py science/src/science_tool/entities.py science/model/tests/test_hypothesis_entity.py
git commit -m "feat(hypothesis): status is the lifecycle, verdict is the verdict; disposition deleted"
```

---

### Task 7: Wire the schema into the load path (D3 — schema first, projection after)

**Files:**
- Modify: `science/src/science_tool/graph/sources.py:359-377`
- Test: `science/tests/test_sources_schema_first.py`

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_sources_schema_first.py
def test_undeclared_key_is_a_hard_error_not_a_silent_drop(tmp_project) -> None:
    # THE original defect: `Entity` is extra="ignore", so `schema.model_validate(raw)` at
    # sources.py:377 silently DROPPED any undeclared frontmatter key. That is how `phase`
    # lived for months without ever reaching the graph. Schema-first turns the silent drop
    # into a loud failure.
    write_hypothesis(tmp_project, "0001-x", status="active", extra={"phase": "candidate"})
    result = load_project_sources(tmp_project)
    assert any(f.reason == "entity_schema_validation_failed" for f in result.failures)


def test_schema_valid_extension_field_SURVIVES_the_projection(tmp_project) -> None:
    # D3 point 3: projections MUST preserve schema-valid extension fields. Returning to
    # extra="ignore" at the projection layer would silently undo the entire design.
    write_hypothesis(tmp_project, "0002-y", status="active", extra={"verdict": "refuted"})
    entity = load_project_sources(tmp_project).entities[0]
    assert entity.verdict == "refuted"
```

- [ ] **Step 2: Run and fail.**

- [ ] **Step 3: Implement** — at `sources.py:359-377`, validate against the composed schema
**before** constructing the Pydantic projection:

```python
                try:
                    schema = registry.resolve(kind)
                except EntityKindNotRegisteredError:
                    ...

                # D3: JSON Schema is the AUTHORITY; Pydantic is a PROJECTION taken after it
                # passes. The order is the whole point -- `Entity` is extra="ignore", so if
                # the projection ran first it would silently drop exactly the undeclared keys
                # the schema exists to reject.
                try:
                    profile = default_profile_for_kind(kind)
                except ProfileParseError:
                    profile = None  # kind not yet migrated onto the schema system
                if profile is not None:
                    try:
                        EntityValidator().validate_as(raw, profile)
                    except EntityValidationError as exc:
                        failures.append(
                            SourceFailure(
                                path=path,
                                reason="entity_schema_validation_failed",
                                detail=str(exc),
                            )
                        )
                        continue

                try:
                    entity = schema.model_validate(raw)
                except ValidationError as exc:
                    ...
```

> `profile is None` is **not** a silent fallback — it is the explicit, temporary statement
> *"this kind has not been migrated yet."* `default_profile_for_kind` only knows the five
> migrated kinds. Each future P2m slice adds one entry and removes one kind from this branch.
> **When the last kind lands, delete the branch.** Leave a `# TODO(P2m):` marker saying so.

- [ ] **Step 4: Green.** Run the FULL tool suite — this changes the load path for every project.

```bash
cd science && uv run --frozen pytest -q && uv run ruff check && uv run pyright
```

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(sources): validate against the composed schema BEFORE projecting to Pydantic"
```

---

### Task 8: The migration — apply the deterministic 145, refuse the 2

**Files:**
- Create: `science/src/science_tool/migrations/hypothesis_lifecycle.py`
- Modify: `science/src/science_tool/migrations/cli.py` (register the command)
- Test: `science/tests/test_migration_hypothesis_lifecycle.py`

**Interfaces:**
- Consumes: `status_inventory.inventory()` (Task 1) — the planner. The migration adds **no**
  mapping logic of its own; if it needed any, the inventory would be lying.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_migration_hypothesis_lifecycle.py
def test_refuses_to_write_anything_when_any_file_is_ambiguous(tmp_path) -> None:
    # ALL OR NONE. A partially-migrated corpus has two meanings of `status` live at once --
    # the exact state that forces the compatibility layer D5 forbids.
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")     # deterministic
    _hyp(tmp_path, "0009-d", status="retired", phase="candidate")   # ambiguous
    with pytest.raises(MigrationRefused) as exc:
        migrate(tmp_path, apply=True)
    assert "0009-d" in str(exc.value)
    assert 'status: "proposed"' in (tmp_path / "entities/hypotheses/0001-a.md").read_text()


def test_applies_the_mapping_when_the_corpus_is_clean(tmp_path) -> None:
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")
    _hyp(tmp_path, "0002-b", status="weakened", phase="candidate")
    migrate(tmp_path, apply=True)
    a = (tmp_path / "entities/hypotheses/0001-a.md").read_text()
    assert 'status: "active"' in a and "verdict:" not in a and "phase:" not in a
    b = (tmp_path / "entities/hypotheses/0002-b.md").read_text()
    assert 'status: "draft"' in b and 'verdict: "weakened"' in b


def test_dry_run_writes_nothing(tmp_path) -> None:
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")
    before = (tmp_path / "entities/hypotheses/0001-a.md").read_text()
    migrate(tmp_path, apply=False)
    assert (tmp_path / "entities/hypotheses/0001-a.md").read_text() == before


def test_body_and_unrelated_frontmatter_are_preserved(tmp_path) -> None:
    _hyp(tmp_path, "0001-a", status="proposed", phase="active",
         extra={"source_refs": ["paper:Smith2020"]}, body="## Rationale\n\nkeep me.")
    migrate(tmp_path, apply=True)
    t = (tmp_path / "entities/hypotheses/0001-a.md").read_text()
    assert "paper:Smith2020" in t and "keep me." in t
```

- [ ] **Step 2: Run and fail.**

- [ ] **Step 3: Implement**

```python
# science/src/science_tool/migrations/hypothesis_lifecycle.py
"""Migrate hypothesis `status`/`phase` -> `status` (lifecycle) + `verdict` (epistemic).

ALL OR NONE. If ANY file in the corpus is ambiguous, this writes NOTHING and exits
non-zero. A half-migrated corpus carries two incompatible meanings of `status` at once,
and the only way to serve both is the heuristic compatibility layer the design forbids.

The mapping lives in `status_inventory` -- deliberately, and entirely. This module applies
what the planner decided and adds no rule of its own; a rule that existed here and not
there would mean the inventory a human read and approved was not the migration that ran.
"""

from __future__ import annotations

from pathlib import Path

from science_tool.frontmatter import read_frontmatter_and_body, render_markdown
from science_tool.status_inventory import inventory


class MigrationRefused(Exception):
    """Raised when any file requires authored adjudication. Nothing was written."""


def migrate(project_root: Path, *, apply: bool) -> list[Path]:
    inv = inventory(project_root)

    if inv.ambiguous:
        lines = [
            f"{len(inv.ambiguous)} hypothesis file(s) cannot be migrated without an author's "
            f"decision. NOTHING has been written.",
            "",
        ]
        for row in inv.ambiguous:
            lines.append(f"  {row.path}")
            lines.append(f"      status={row.status!r} phase={row.phase!r}")
            lines.append(f"      {row.ambiguity}")
            lines.append("")
        lines.append(
            "Set `status`, `verdict` and `closure_basis` by hand on each file above, then "
            "re-run. Do NOT guess: a terminal status has already destroyed the prior verdict, "
            "and inventing one would fabricate an epistemic conclusion."
        )
        raise MigrationRefused("\n".join(lines))

    written: list[Path] = []
    for row in inv.deterministic:
        fm, body = read_frontmatter_and_body(row.path)
        fm["status"] = row.target_status
        if row.target_verdict is not None:
            fm["verdict"] = row.target_verdict
        fm.pop("phase", None)
        fm.pop("disposition", None)        # authored on 0 of 147 -- nothing to preserve
        fm.pop("disposition_basis", None)
        if apply:
            row.path.write_text(render_markdown(fm, body), encoding="utf-8")
        written.append(row.path)
    return written
```

- [ ] **Step 4: Green**

```bash
cd science && uv run --frozen pytest tests/test_migration_hypothesis_lifecycle.py -q
```

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/migrations/hypothesis_lifecycle.py science/src/science_tool/migrations/cli.py science/tests/test_migration_hypothesis_lifecycle.py
git commit -m "feat(migrate): hypothesis lifecycle/verdict split -- all-or-none, refuses ambiguity"
```

---

### Task 9: Consumers, templates, commands — the rest of the atomic slice

Every surface that reads `phase`, `disposition`, or a verdict-as-status. **Miss one and the
slice is not atomic.**

**Files:**
- `science/model/src/science_model/templates/hypothesis.md` **and** `templates/hypothesis.md` (two copies — the packaged one is what the Renderer reads)
- `science/src/science_tool/hypotheses_cli.py:28-34,62-64` — `--phase` → `--status`; the `promotion-criteria` section now triggers on `status == "draft"`
- `science/src/science_tool/entities_cli.py:94-125` — add `--verdict`, `--closure-basis`
- `science/src/science_tool/entities.py:935-969` (`edit_entity`) — **the lifecycle boundary**
- `science/src/science_tool/entities.py:1377-1379` (`_validate_status`) — also fix the raw `KeyError` (it indexes `_STATUS_VALUES[kind]` directly and ignores project-local manifests, unlike `valid_statuses`)
- `science/src/science_tool/graph/attention.py:25-27,125-137,530-535,572-586` — `DEBT_QUESTION_STATUSES`; delete the `sci:disposition` readers
- `science/src/science_tool/graph/materialize.py` — emit `sci:verdict`; drop `sci:disposition`
- `science/src/science_tool/validate/checks/hypotheses.py:23,64-70,127-136` — delete the `phase` check
- `science/src/science_tool/validate/checks/dataset_capabilities.py:24-54` — `_DEMAND_CLOSED_STATUSES`
- `science/src/science_tool/annotation/promote.py:330-331` — `fields["phase"] = "candidate"` → `fields["status"] = "draft"`
- `commands/big-picture.md:62,213-217` · `commands/add-hypothesis.md:124`

- [ ] **Step 1: Write the failing tests** — the two-axis consumers are the ones that bite

```python
# science/tests/test_two_axis_consumers.py
def test_debt_is_now_a_two_axis_predicate() -> None:
    # These sets MIX lifecycle with answeredness. They must be REWRITTEN, never remapped:
    # a one-axis remap of a two-axis predicate silently changes which entities count.
    assert is_question_debt(status="active", answer_state=None) is True
    assert is_question_debt(status="active", answer_state="answered") is False   # <- the fix
    assert is_question_debt(status="deferred", answer_state=None) is True
    assert is_question_debt(status="complete", answer_state=None) is False


def test_demand_closed_reads_the_verdict_not_the_status() -> None:
    # `refuted` was the ONLY hypothesis-specific value any consumer read
    # (dataset_capabilities.py:46). It is now a verdict, not a status.
    assert is_demand_closed(kind="hypothesis", status="active", verdict="refuted") is True
    assert is_demand_closed(kind="hypothesis", status="active", verdict="supported") is False
    assert is_demand_closed(kind="hypothesis", status="retired", verdict=None) is True


def test_edit_status_is_the_lifecycle_boundary(tmp_project) -> None:
    # One generic boundary, not four invented verbs. It validates against the composed
    # schema, takes --closure-basis ATOMICALLY with the transition, and FAILS BEFORE WRITING.
    with pytest.raises(EntityCommandError, match="closure_basis"):
        edit_entity(tmp_project, "hypothesis:0001-x", status="retired")
    before = (tmp_project / "entities/hypotheses/0001-x.md").read_text()
    assert 'status: "active"' in before   # unchanged -- it failed BEFORE writing

    edit_entity(tmp_project, "hypothesis:0001-x", status="retired", closure_basis="no samples")
    assert 'closure_basis: "no samples"' in (tmp_project / "entities/hypotheses/0001-x.md").read_text()
```

- [ ] **Step 2: Run and fail.**

- [ ] **Step 3: Implement.** Two rewrites carry the real risk:

`attention.py:25-27` — the predicate, not the set:

```python
def is_question_debt(*, status: str | None, answer_state: str | None) -> bool:
    """Open-question debt: still live AND not yet answered.

    This REPLACES `DEBT_QUESTION_STATUSES = {active, partially-answered, deferred}`, which
    was a two-axis predicate hiding in a one-axis field -- it mixed lifecycle (`active`,
    `deferred`) with answeredness (`partially-answered`). Remapping it value-by-value would
    have silently changed which questions count as debt.
    """
    return status in {"active", "deferred"} and answer_state != "answered"
```

`dataset_capabilities.py:24-54` — `refuted` moves to the verdict axis:

```python
_CLOSED_LIFECYCLE = frozenset({"complete", "superseded", "retired", "archived"})


def is_demand_closed(*, kind: str, status: str | None, verdict: str | None, answer_state: str | None = None) -> bool:
    """Whether a question/hypothesis still exerts live pull on data.

    Deliberately conservative: a suppressor should fail toward KEEPING the warning, since a
    false-suppress hides a real coverage gap while a false-keep leaves only a low-value
    warning. So `supported` (can still be strengthened) and `weakened` (verdict still open)
    keep warning -- only `refuted` settles the demand.
    """
    if status in _CLOSED_LIFECYCLE:
        return True
    if kind == "hypothesis":
        return verdict == "refuted"
    return answer_state == "answered"
```

`edit_entity` — the generic lifecycle boundary (ruled D4). Validate against the **composed
schema**, accept `closure_basis` **atomically** with the transition, and **fail before writing**:

```python
def edit_entity(
    project_root: Path,
    ref: str,
    *,
    title: str | None = None,
    status: str | None = None,
    verdict: str | None = None,
    closure_basis: str | None = None,
    ...
) -> EntityWriteResult:
    ...
    if status is not None:
        frontmatter["status"] = status
    if verdict is not None:
        frontmatter["verdict"] = verdict
    if closure_basis is not None:
        frontmatter["closure_basis"] = closure_basis

    # THE lifecycle boundary. The composed schema is the authority -- so a terminal
    # transition missing its basis fails HERE, before a single byte is written, rather
    # than landing on disk and surfacing as a validate WARN later.
    try:
        profile = default_profile_for_kind(location.kind)
    except ProfileParseError:
        profile = None
    if profile is not None:
        try:
            EntityValidator().validate_as(frontmatter, profile)
        except EntityValidationError as exc:
            raise EntityCommandError(str(exc)) from exc

    text = _render_markdown(frontmatter, location.body)
    ...
    _atomic_replace_text(location.path, text)
```

- [ ] **Step 4: Green — the whole suite, both packages**

```bash
cd science && uv run --frozen pytest -q && uv run ruff check && uv run pyright
cd ../science/model && uv run --frozen pytest -q
```

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(hypothesis): rewrite the two-axis consumers; edit --status becomes the lifecycle boundary"
```

---

### Task 10: Graph/output diff — prove the slice changed only what it meant to

**Files:**
- Test: `science/tests/test_hypothesis_slice_graph_diff.py`

- [ ] **Step 1: Capture the BEFORE graph** (from the pre-slice commit, in a scratch worktree)

```bash
cd ~/d/natural-systems && git stash list  # ensure clean
uv run science graph build --output /tmp/claude-1000/before.trig
```

- [ ] **Step 2: Migrate and rebuild**

```bash
cd ~/d/natural-systems
uv run science entity status-inventory          # expect: 13 deterministic, 1 refused (0009)
# 0009 must be adjudicated BY THE AUTHOR before the migration will run.
uv run science migrate hypothesis-lifecycle --apply
uv run science graph build --output /tmp/claude-1000/after.trig
uv run science validate                          # MUST be exit 0
```

- [ ] **Step 3: Diff and account for every triple**

```bash
cd science && uv run python -m science_tool.graph.diff /tmp/claude-1000/before.trig /tmp/claude-1000/after.trig
```

**Expected, and nothing else:**
- `sci:projectStatus` values change (`proposed`→`active`/`draft` per the mapping)
- **new** `sci:verdict` triples on the 9 hypotheses that carry one
- **zero** `sci:disposition` triples before **and** after (it was never authored)
- **no** `phase` triples in either (it never reached the graph — `Entity` is `extra="ignore"`)
- **no** change to any non-hypothesis subject

**Any unexplained triple means the slice is not atomic. Stop and find it.**

- [ ] **Step 4: Run `science validate` in EVERY affected project**

```bash
for p in ~/d/natural-systems ~/d/r/mm30 ~/d/r/cbioportal ~/d/protein-landscape \
         ~/d/science/meta ~/d/health/meta ~/d/seq-feats ~/d/cancer/therapeutics \
         ~/d/3d-attention-bias; do
  echo "=== $p"; (cd "$p" && uv run science validate >/dev/null 2>&1; echo "exit=$?")
done
```
**Every one must be exit 0.** This is the step whose absence caused the original incident:
the toolkit repo has no `entities/` of its own, so green CI proves nothing about this change.

- [ ] **Step 5: Commit**

```bash
git commit -am "test(hypothesis): graph/output diff certifies the P2m slice"
```

---

## Phase 4 — The ratchet (ruled step 6)

### Task 11: `hypothesis` goes to ERROR — per kind, and only per kind

**Files:**
- Modify: `science/src/science_tool/validate/checks/status_vocabulary.py`
- Test: `science/tests/test_status_vocabulary_ratchet.py`

- [ ] **Step 1: Write the failing test**

```python
def test_certified_kinds_error_and_uncertified_kinds_warn() -> None:
    # Severity is a property of the KIND, never of layout_version. The first version of
    # this check graded on layout_version >= 3 -- all five projects were v3, so the gate
    # graded NOTHING, and 472 entities errored the moment it landed.
    assert _severity("hypothesis") is Severity.ERROR   # sources AND consumers certified
    assert _severity("report") is Severity.WARN        # not yet migrated
    assert _severity("dataset") is Severity.WARN
```

- [ ] **Step 2: Implement**

```python
# The kinds whose vocabulary has been certified AND whose corpus has been migrated AND
# whose consumers have been rewritten. A kind joins this set at the END of its P2m slice,
# never before -- an uncertified instrument may not fail anyone's build.
_CERTIFIED_KINDS: frozenset[str] = frozenset({"hypothesis"})


def _severity(kind: str) -> Severity:
    return Severity.ERROR if kind in _CERTIFIED_KINDS else Severity.WARN
```

- [ ] **Step 3: Green, then re-run validate across all 9 projects.** Every one still exit 0.

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(validate): ratchet hypothesis to ERROR -- the first certified kind"
```

---

## What this plan does NOT do

Named so nobody assumes coverage that isn't here:

- **The other 32 kinds.** This plan builds the machinery and migrates **one** kind. Each
  subsequent P2m slice reuses Tasks 1/4/8 with a new mixin and a new inventory mapping. `question`
  is the natural second (it is the only kind whose status values actually drive behaviour, and its
  two consumers are already rewritten as two-axis predicates by Task 9).
- **P1 (absorb `provided_capabilities`/`required_capabilities`)** — a designed subsystem reading
  raw frontmatter, bypassing the model, invisible to the graph. Independent of this arc.
- **`science:graph` and `science:axis`** — the field-materialization and axis-category vocabularies
  (design §3, §5). Not needed to migrate `hypothesis`; needed before the `omit`-vs-`node` decisions
  can be declared rather than assumed.
- **The 6 filed defects** (`fb-2026-07-12-004`…`009`), notably **`006`: every commons dataset is on
  a crashing overlay path today.** Independent of this arc and worth fixing sooner.
- **The 169 residual status-vocabulary WARNs** on non-hypothesis kinds. They stay WARNs until
  their own slices land — which is the point of the per-kind ratchet.

## Self-review

- **Spec coverage.** Ruled step 1 → Task 1. Step 2 → Task 1 (`deterministic`/`ambiguous`).
  Step 3 → Tasks 2–5. Step 4 → Tasks 6–10. Step 5 → Task 8 (`MigrationRefused`). Step 6 → Task 11.
  P2m's five atomic sub-parts → schema (4), sources (8), templates (9), consumers (9), graph diff (10).
- **Traps.** `disposition: closed` → nothing (zero authored; Task 6). `status: archived` → verdict
  left **absent**, loss reported (Task 1 `_classify`). `paper` values → out of scope, inventoried
  only. Design §7.4's terminal invariant → Task 4's four `if/then`s + Task 5's resolution pass.
- **Type consistency.** `InventoryRow.target_status`/`target_verdict` (Task 1) are what Task 8
  writes. `validate_as(entity, profile)` (Task 3) is what Tasks 7 and 9 call.
  `check_resolution(entity, known_ids=...)` (Task 5) returns `list[str]`.
- **Known gap:** Task 5's `check_resolution` is defined and tested but only wired into `validate`
  in Task 7's follow-through — if the wiring slips, presence is enforced and **resolution is not**,
  which is the dangling-`superseded_by` hole. **Do not ship Phase 3 without it.**
