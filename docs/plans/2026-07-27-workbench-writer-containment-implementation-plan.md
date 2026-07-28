# Workbench Writer Containment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the workbench lift path persisting entity files whose base-required fields are empty and whose frontmatter is a full-model skeleton dump.

**Architecture:** Titles become deterministically generated at lift time instead of `""`. Both new-file writers emit an explicit per-kind allowlist instead of `model_dump(exclude_defaults=False)`. A separately named `validate_persisted_base_shape` runs on the final mapping of both the create and update paths, and an update targeting a pre-existing empty-title record is **rejected**.

**Tech Stack:** Python 3.13, Pydantic v2, jsonschema, pytest, uv.

Design: [`meta/doc/plans/2026-07-26-schema-first-closure-design.md`](../../meta/doc/plans/2026-07-26-schema-first-closure-design.md) §5, which is the umbrella over this plan and a second one. Read §5 before Task 1; every ruling here traces to it.

This plan is **piece 1 of 3** and is independently mergeable. It does **not** backfill the 769 existing malformed records (piece 3) and does **not** close any kind's schema (piece 2).

## Global Constraints

- **Working directories.** CLI/tool work runs from `science/`; model work runs from `science/model/`. There is **no root `pyproject.toml`** — running `uv run` from the repo root is the most common orientation mistake here.
- **Test commands.** `cd science && uv run --frozen pytest` and `cd science/model && uv run --frozen pytest`. Never run two suites concurrently in the same worktree — they race on shared test-output paths.
- **The full `science/` suite takes ~2-3 min**, longer than the default 120s command timeout. Pass an explicit long timeout, or run a scoped selection.
- **Lint/types**, from `science/`: `uv run ruff check` and `uv run pyright`. Pyright is configured once by `pyrightconfig.json` at the repo root and governs all three source trees.
- **Conventional commits.** No AI-attribution trailer or footer on commits, PRs, or comments.
- **Composition over inheritance; explicit over defensive; fail early instead of silent fallbacks. No "legacy"/"compatibility" layers. No `Unified` prefix.**
- **Use `~/d/` or relative paths in docs and code**, never `/home/keith/` or `/mnt/ssd/Dropbox/`.
- **The two derived title formats are rulings, not implementation choices.** They are frozen in Task 1 and mutation-tested in Task 5.
- **`title` is create-only.** It must never enter a per-kind *update* key set; doing so would overwrite an author's replacement on the next apply.
- **Do not weaken `EntityValidator.validate_as`.** It deliberately rejects base-only profiles. The new base-shape check is a *separate* named operation with a weaker, explicitly-stated contract.
- **Do not backfill existing records.** Not in any step, not as a convenience.

---

## File Structure

| File | Responsibility in this change |
|---|---|
| `science/src/science_tool/dag/workbench.py` | deterministic titles at lift; `min_length` on row inputs; stop emitting safe empties |
| `science/src/science_tool/dag/entity_frontmatter.py` | **new** — the per-kind owned key sets, both renderers, and the persistence certification, shared by the two writers |
| `science/src/science_tool/dag/workbench_apply.py` | create-path allowlist; base-shape validation on both paths |
| `science/model/src/science_model/entity_schema/validator.py` | `validate_persisted_base_shape` — necessary, not sufficient |
| `science/model/tests/test_persisted_base_shape.py` | the new operation's contract and its limits |
| `science/tests/test_workbench_writer_containment.py` | the containment regressions and mutation proofs |

---

### Task 1: Generate deterministic titles at lift time

**Files:**
- Modify: `science/src/science_tool/dag/workbench.py:114-169` (`WorkbenchRow`), `:249-270` (`_proposition_for_row`), `:284-303` (`_evidence_line_for_stub`)
- Test: `science/tests/test_workbench_writer_containment.py` (new)

**Interfaces:**
- Produces: `workbench._proposition_title(row) -> str` and `workbench._evidence_line_title(stub, target_id) -> str`. Task 5 mutation-tests both.
- `WorkbenchRow.subject` and `.object` gain `min_length=1`.

**Why `min_length` is needed.** An earlier design draft claimed the row model guarantees non-empty triples. It does not — verified, `WorkbenchRow(subject="", predicate="", object="", patch="p")` is **accepted**, because the fields are plain `str`. What actually protects the title today is the later `Predicate(row.predicate)` conversion, which raises `ValueError` on `""`. That leaves `subject` and `object` unguarded.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_workbench_writer_containment.py`:

```python
"""Writer containment: what the workbench persists must satisfy the durable base contract.

The boundary rule (design §5.1): empty fields may be acceptable while constructing an in-memory
entity; they are NOT acceptable once persisted as authored source. `workbench.py` used to cite the
entity-model tests' minimal-construction pattern as precedent for a production write.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_tool.dag.workbench import (
    EvidenceStub,
    WorkbenchRow,
    _evidence_line_for_stub,
    _proposition_for_row,
)


def _row(**over) -> WorkbenchRow:
    # `polarity` is REQUIRED here: `affects` is sign-meaningful, and `PropositionEntity` rejects it
    # without positive/negative/unsigned. Omitting it makes every test below fail during fixture
    # construction, before any title assertion is reached.
    base = {
        "subject": "concept:a",
        "predicate": "affects",
        "object": "concept:b",
        "patch": "p",
        "polarity": "unsigned",
    }
    return WorkbenchRow(**{**base, **over})


def test_proposition_title_is_the_triple() -> None:
    # THE RULING (design §5.2). Deterministic generation, not a required input field: `WorkbenchRow`
    # is extra="forbid" and carries no `title`, so requiring one would widen the authored-input
    # contract. Changing this string is a behaviour change and must fail here.
    prop = _proposition_for_row(_row())
    assert prop.title == "concept:a affects concept:b"


def test_evidence_line_title_uses_source_when_present() -> None:
    stub = EvidenceStub(stance="supports", source="paper:Smith2025")
    line = _evidence_line_for_stub(stub, target_id="proposition:0001-x", index=0)
    assert line.title == "supports proposition:0001-x — paper:Smith2025"


def test_evidence_line_title_falls_back_to_evidence_type() -> None:
    # `EvidenceStub.evidence_type` runs `canonical_evidence_type_token`, which strips the
    # `_evidence` suffix BEFORE storage. The tail is therefore the canonical token, not the
    # spelling passed in — pass the enum member and assert what the model actually holds.
    stub = EvidenceStub(stance="disputes", evidence_type=EvidenceType.LITERATURE)
    line = _evidence_line_for_stub(stub, target_id="proposition:0001-x", index=0)
    assert line.title == "disputes proposition:0001-x — literature"


def test_evidence_line_title_without_qualifiers_is_still_non_empty() -> None:
    # `target_id` is computed and always present, so the head alone satisfies minLength: 1 even
    # when the stub carries no stance, source or evidence_type.
    line = _evidence_line_for_stub(EvidenceStub(), target_id="proposition:0001-x", index=0)
    assert line.title == "supports proposition:0001-x"


def test_generated_titles_are_whitespace_collapsed() -> None:
    prop = _proposition_for_row(_row(subject="concept:a  b", object="concept:c\td"))
    assert prop.title == "concept:a b affects concept:c d"


@pytest.mark.parametrize("field", ["subject", "object"])
def test_empty_triple_terms_fail_at_PARSE_time(field: str) -> None:
    # Not at title construction, and not at base validation. `predicate` is already protected by
    # the `Predicate("")` conversion; subject and object were not protected by anything.
    with pytest.raises(ValidationError):
        _row(**{field: ""})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_workbench_writer_containment.py -q`
Expected: the **five** title tests FAIL with `assert '' == '...'` (title is `""` today); the two parametrized parse tests FAIL because `ValidationError` is not raised — an empty string is currently accepted. Seven failures in total.

- [ ] **Step 3: Add `min_length` to the triple terms**

In `science/src/science_tool/dag/workbench.py`, in `WorkbenchRow`:

```python
    # Core triple. `min_length=1`: these feed the derived proposition title, which must satisfy
    # base 2.0's `minLength: 1`. `predicate` is separately protected by the `Predicate(...)`
    # conversion; subject and object were protected by nothing, so an empty term reached the
    # persisted title. Failing here names the row, not the rendered file.
    subject: str = Field(min_length=1)
    predicate: str
    object: str = Field(min_length=1)
```

`Field` is already imported in this module.

- [ ] **Step 4: Add the two title builders**

Add above `_proposition_for_row`:

```python
def _collapse(text: str) -> str:
    """Collapse all runs of whitespace to single spaces. Titles are durable authored source."""
    return " ".join(text.split())


def _proposition_title(row: WorkbenchRow) -> str:
    """THE derived proposition title (design §5.2). Deterministic, not good prose.

    Mechanical on purpose: it must be stable and reconstructible from the row. An author may
    replace it afterwards, and the update path will preserve the replacement because `title` is
    not in the per-kind workbench key set.
    """
    return _collapse(f"{row.subject} {row.predicate} {row.object}")


def _evidence_line_title(stub: EvidenceStub, *, target_id: str) -> str:
    """THE derived evidence-line title (design §5.2).

    `target_id` is computed by the caller and always present, so the head alone is non-empty.
    `stance` defaults to SUPPORTS at lift, matching the entity field's own default.
    """
    stance = stub.stance or "supports"
    head = f"{stance} {target_id}"
    tail = stub.source or (stub.evidence_type.value if stub.evidence_type else None)
    return _collapse(f"{head} — {tail}" if tail else head)
```

- [ ] **Step 5: Use them at both lift sites**

In `_proposition_for_row`, add to the `PropositionEntity(...)` call:

```python
        title=_proposition_title(row),
```

In `_evidence_line_for_stub`, change **only** the title. Every other field stays:

```python
    return EvidenceLineEntity(
        id=line_id,
        kind="evidence-line",
        type=EntityType.EVIDENCE_LINE,
        title=_evidence_line_title(stub, target_id=target_id),
        # These are REQUIRED by the model and must keep being supplied. They are not persisted --
        # Task 3's owned-key allowlist is what keeps them out of the file. Deleting them here
        # raises `Field required` for all six.
        project="",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="",
        stance=EvidenceStance(stub.stance) if stub.stance is not None else EvidenceStance.SUPPORTS,
        target=target_id,
        source=stub.source,
        evidence_type=stub.evidence_type,
        quantitative_result=stub.quantitative_result,
        belief_eligible=not is_staged_empirical,
    )
```

Replace the old `# Base-required fields that have no value at lift time — safe empties (mirrors the
minimal-construction pattern in the entity model tests)` comment with the one above. The old
comment is the defect's own justification — it cites *test* practice as precedent for a production
write — and the correction is not that the values are wrong in memory, but that **in-memory
required is not the same as persisted**. That distinction is the whole of §5.1.

**Verified, so the plan does not repeat an earlier error:** `project`, `ontology_terms`,
`related`, `source_refs`, `content_preview` and `file_path` are all `required=True` with no
default. An earlier revision of this plan deleted them, claiming they had defaults; constructing
`EvidenceLineEntity` without them raises `Field required` for every one.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_workbench_writer_containment.py -q`
Expected: PASS.

- [ ] **Step 7: Run the tool suite**

Run: `cd science && uv run --frozen pytest -q` (allow ~3 min).
Expected: green, **except** existing workbench tests that assert on rendered frontmatter. Record every failure verbatim — Task 3 is where the rendered shape changes, so a failure here means a test asserted `title: ''`. Fix such a test by updating its expected title to the derived string; do **not** relax the assertion.

- [ ] **Step 8: Commit**

```bash
# Step 7 may have repaired existing modules that asserted `title: ''`. Run `git status --short`
# and add every path it names; these are the ones most likely to appear.
git add science/src/science_tool/dag/workbench.py \
        science/tests/test_workbench_writer_containment.py \
        science/tests/test_workbench_compile.py \
        science/tests/test_workbench_apply.py
git commit -m "feat(workbench): derive entity titles at lift instead of persisting empties

WorkbenchRow.subject/object gain min_length=1: they were plain str, so an empty
term reached the persisted title, and only predicate was protected by its enum
conversion. Titles are now deterministic from the triple and from
stance/target/source, so the lift path no longer writes a base-required field
as an empty string."
```

---

### Task 2: `validate_persisted_base_shape`

**Files:**
- Modify: `science/model/src/science_model/entity_schema/validator.py`
- Test: `science/model/tests/test_persisted_base_shape.py` (new)

`entity_schema/__init__.py` is **not** modified: the operation is a method on the already-exported `EntityValidator`. Step 5 verifies that rather than editing anything.

**Interfaces:**
- Produces: `EntityValidator.validate_persisted_base_shape(mapping: dict[str, Any]) -> None`, raising `EntityValidationError`. Task 4 calls it from both workbench write paths.

**Why a separate operation.** `validate_as` deliberately refuses a base-only profile (`validator.py:51-55`) because passing the base is not proof that an entity satisfies its *kind* schema. Containment nevertheless lands before `proposition` and `evidence-line` have mixins, so it needs a check that is honest about being weaker rather than a loosened `validate_as`.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_persisted_base_shape.py`:

```python
"""`validate_persisted_base_shape` — necessary validation of durable source shape.

NOT sufficient entity-schema validation. It exists because writer containment (design §5.5) must
land before `proposition` and `evidence-line` have mixins, and a writer that persists source it
never checked is the defect the whole programme is about.
"""

from __future__ import annotations

import pytest

from science_model.entity_schema import EntityValidationError, EntityValidator


def _ok() -> dict:
    return {
        "id": "proposition:0001-x",
        "kind": "proposition",
        "title": "concept:a affects concept:b",
        "created": "2026-07-27",
        "updated": "2026-07-27",
    }


def test_a_well_formed_mapping_passes() -> None:
    EntityValidator().validate_persisted_base_shape(_ok())


def test_empty_title_is_refused() -> None:
    # THE case this exists for: base 2.0 declares title {"type": "string", "minLength": 1} and
    # requires it. 769 persisted records violate it today.
    payload = _ok() | {"title": ""}
    with pytest.raises(EntityValidationError, match="title"):
        EntityValidator().validate_persisted_base_shape(payload)


@pytest.mark.parametrize("missing", ["id", "kind", "title", "created", "updated"])
def test_each_base_required_field_is_enforced(missing: str) -> None:
    payload = _ok()
    del payload[missing]
    with pytest.raises(EntityValidationError, match=missing):
        EntityValidator().validate_persisted_base_shape(payload)


def test_an_invalid_date_is_refused() -> None:
    # Load-bearing, and silently defeated if `format_checker` is dropped: JSON Schema treats
    # `format` as an ANNOTATION unless a checker is supplied. Measured -- without it,
    # created="not-a-date" produces zero errors; with it, "'not-a-date' is not a 'date'".
    # Plan 2's finding migration rules `updated = created`, so date validity is not decorative.
    payload = _ok() | {"created": "not-a-date"}
    with pytest.raises(EntityValidationError, match="not a 'date'"):
        EntityValidator().validate_persisted_base_shape(payload)


def test_unknown_keys_are_ALLOWED() -> None:
    # The contract's stated limit. `unevaluatedProperties: false` is NOT applied: these kinds have
    # no mixin, so closing here would reject every field the kind legitimately carries. Shadow-key
    # refusal is piece 2's job, not this operation's.
    EntityValidator().validate_persisted_base_shape(_ok() | {"stance": "supports"})


def test_it_does_not_weaken_validate_as() -> None:
    # `validate_as` must still refuse a base-only profile. If this ever passes, the separate
    # operation has been folded back into the sufficient one and the distinction is lost.
    from science_model.entity_schema.profile import ProfileComponent, ProfileString

    base_only = ProfileString(
        base=ProfileComponent(name="science-entity-base", version="2.0"), mixin=None, extensions=()
    )
    with pytest.raises(EntityValidationError, match="type mixin"):
        EntityValidator().validate_as(_ok(), base_only)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_persisted_base_shape.py -q`
Expected: collection succeeds; every test except `test_it_does_not_weaken_validate_as` fails with `AttributeError: 'EntityValidator' object has no attribute 'validate_persisted_base_shape'`. That last one passes already and is a guard, not a driver.

- [ ] **Step 3: Implement the operation**

In `science/model/src/science_model/entity_schema/validator.py`, add to `EntityValidator`:

```python
    def validate_persisted_base_shape(self, mapping: dict[str, Any]) -> None:
        """Necessary validation of durable source shape, NOT sufficient entity-schema validation.

        Checks the final frontmatter mapping — after titles and dates have been added — against
        base 2.0 alone. It deliberately does NOT apply `unevaluatedProperties: false`: the kinds
        this guards have no mixin yet, so closing here would reject every field they legitimately
        carry. Refusing unknown keys is the closure programme's job.

        Use it at a persistence boundary, where "this will become authored source" is true. Do not
        use it as a substitute for `validate_as`, which is the sufficient check and which refuses
        a base-only profile precisely so this distinction cannot blur.
        """
        schema = self._loader.load(ProfileComponent(name=BASE_NAME, version="2.0"))
        validator = Draft202012Validator(
            schema,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
        errors = sorted(validator.iter_errors(mapping), key=lambda e: list(e.absolute_path))
        if errors:
            joined = "; ".join(_format_error(err) for err in errors)
            raise EntityValidationError(
                f"persisted entity does not satisfy the durable base shape: {joined}",
                errors=errors,
            )
```

Extend the existing profile import at the top of the file:

```python
from science_model.entity_schema.profile import (
    BASE_NAME,
    PROJECT_MIXIN_NAMES,
    TYPE_MIXIN_NAMES,
    ProfileComponent,
    ProfileParseError,
    ProfileString,
    parse_profile,
)
```

`validate_overlay` currently imports `ProfileComponent` inside the function body; leave that alone — narrowing it is unrelated churn.

**On the `match=` strings.** The parametrized test matches the field name. A jsonschema `required` error message reads `'title' is a required property`, and `_format_error` prefixes the path, so the field name appears for both the missing-field and the `minLength` cases. Confirm this in Step 4 rather than assuming it; if a message does not contain the bare field name, fix the **test's** matcher to the observed text — do not reshape the error to satisfy a guess.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science/model && uv run --frozen pytest tests/test_persisted_base_shape.py -q -v`
Expected: PASS. Read the `-v` output and confirm each `match=` actually matched the intended error rather than an incidental substring.

- [ ] **Step 5: Export it**

In `science/model/src/science_model/entity_schema/__init__.py`, no new name is needed — `EntityValidator` and `EntityValidationError` are already exported and the operation is a method. Verify with:

Run: `cd science/model && uv run --frozen python -c "from science_model.entity_schema import EntityValidator; print(EntityValidator.validate_persisted_base_shape.__doc__.splitlines()[0])"`
Expected: prints the first docstring line.

- [ ] **Step 6: Run the model suite**

Run: `cd science/model && uv run --frozen pytest -q`
Expected: green.

- [ ] **Step 7: Commit**

```bash
git add science/model/src/science_model/entity_schema/validator.py \
        science/model/tests/test_persisted_base_shape.py
git commit -m "feat(entity-schema): add validate_persisted_base_shape

A necessary check of durable source shape, explicitly not a sufficient
entity-schema check. Writer containment must land before proposition and
evidence-line have mixins, so it needs a base-only check that says what it is
rather than a loosened validate_as -- which keeps refusing base-only profiles."
```

---

### Task 3: Render both writers from an owned allowlist

**Files:**
- Create: `science/src/science_tool/dag/entity_frontmatter.py`
- Modify: `science/src/science_tool/dag/workbench_apply.py:34-87` (move the key sets out), `:234-286` (move the renderers out), `:289-304` (`_entity_edit` create branch)
- Modify: `science/src/science_tool/dag/workbench.py:313-330` (`_write_entity_file`)
- Test: `science/tests/test_workbench_writer_containment.py`

**Interfaces:**
- Consumes: the derived titles from Task 1.
- Produces, all in `dag/entity_frontmatter.py`: `PROPOSITION_OWNED_KEYS`, `EVIDENCE_LINE_OWNED_KEYS`, `CREATE_ONLY_KEYS`, `owned_keys(kind)`, `generated_frontmatter(entity, *, created, updated)`, `render_from_frontmatter(frontmatter, body)`, `render_create(entity, *, body, created, updated)`.

**There are TWO new-file writers, and both full-dump today.** `workbench_apply._entity_edit` renders with `render_entity_text` when the target does not exist (`:291`); `workbench._write_entity_file` (`:313`) delegates to `entities.write_entity_file`, which renders the same way, and is reached from `compile_workbench` at `:363` and `:374`. Both are live. Fixing only the first leaves the compile path emitting skeletons.

**Why a new module rather than sharing directly.** `workbench_apply` already imports from `workbench` (`:18`), so putting the shared renderer in `workbench_apply` and calling it from `workbench` is a circular import; putting it in `workbench` puts frontmatter rendering inside the lift/compile module. A small third module both import is the only arrangement with one responsibility per file and no cycle — and it makes the duplication structurally impossible rather than merely absent today.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_workbench_writer_containment.py`:

```python
_SKELETON_KEYS = frozenset({
    "datapackage", "accessions", "parent_dataset", "license", "local_path", "xrefs", "siblings",
    "consumed_by", "produced_by", "scope", "provisional", "pre_registered", "deprecated_ids",
    "profile", "project",
})


def _created_frontmatter(tmp_path, entity) -> dict:
    """Frontmatter of the file the CREATE path would write for `entity`."""
    import yaml

    from science_tool.dag.workbench_apply import _entity_edit

    edit = _entity_edit(tmp_path, entity, as_of=date(2026, 7, 27))
    return yaml.safe_load(edit.final_text.split("---\n", 2)[1])


def test_created_proposition_carries_only_owned_keys(tmp_path) -> None:
    from science_tool.dag.entity_frontmatter import CREATE_ONLY_KEYS, PROPOSITION_OWNED_KEYS

    fm = _created_frontmatter(tmp_path, _proposition_for_row(_row()))
    allowed = PROPOSITION_OWNED_KEYS | CREATE_ONLY_KEYS
    assert set(fm) <= allowed, f"unowned keys persisted: {sorted(set(fm) - allowed)}"


def test_created_evidence_line_carries_no_skeleton_fields(tmp_path) -> None:
    # The 391-document uniform set from mm30. Each of these was written as an empty default.
    line = _evidence_line_for_stub(
        EvidenceStub(stance="supports", source="paper:S"), target_id="proposition:0001-x", index=0
    )
    fm = _created_frontmatter(tmp_path, line)
    assert not (set(fm) & _SKELETON_KEYS), f"skeleton fields persisted: {sorted(set(fm) & _SKELETON_KEYS)}"


def test_created_entity_has_a_non_empty_title(tmp_path) -> None:
    fm = _created_frontmatter(tmp_path, _proposition_for_row(_row()))
    assert fm["title"].strip()


def test_created_evidence_line_keeps_a_deliberate_false(tmp_path) -> None:
    # `belief_eligible=False` is a staging DECISION -- an empirical stub with no dataset_usage is
    # staged ineligible. It must survive the allowlist projection, because a stamped-ineligible
    # line that serializes as eligible is a belief-affecting silent change.
    from science_model.reasoning import EvidenceType

    stub = EvidenceStub(stance="supports", evidence_type=EvidenceType.EMPIRICAL_DATA)
    line = _evidence_line_for_stub(stub, target_id="proposition:0001-x", index=0)
    assert line.belief_eligible is False
    fm = _created_frontmatter(tmp_path, line)
    assert fm["belief_eligible"] is False


def test_title_is_CREATE_ONLY() -> None:
    # Adding `title` to a per-kind update set would overwrite an author's replacement on the next
    # apply and contradict design §5.2. The delta between create and update is exactly this.
    from science_tool.dag.entity_frontmatter import (
        CREATE_ONLY_KEYS,
        EVIDENCE_LINE_OWNED_KEYS,
        PROPOSITION_OWNED_KEYS,
    )

    assert CREATE_ONLY_KEYS == frozenset({"title", "status"})
    for owned in (PROPOSITION_OWNED_KEYS, EVIDENCE_LINE_OWNED_KEYS):
        assert "title" not in owned
        assert "status" not in owned


def test_update_preserves_an_authors_replacement_title(tmp_path) -> None:
    # The reason title is create-only, proved behaviourally rather than by set arithmetic.
    from science_tool.dag.workbench_apply import _entity_edit

    import yaml

    entity = _proposition_for_row(_row())
    first = _entity_edit(tmp_path, entity, as_of=date(2026, 7, 27))
    first.path.parent.mkdir(parents=True, exist_ok=True)
    # Replace the title in the FRONTMATTER ONLY. `str.replace` over the whole file also rewrites
    # the body heading, and then a substring assertion passes even when the frontmatter title was
    # overwritten -- an inert proof of exactly the thing this test exists to catch.
    frontmatter, body = first.final_text.split("---\n", 2)[1:]
    edited = yaml.safe_load(frontmatter) | {"title": "An author's real title"}
    first.path.write_text(
        "---\n" + yaml.safe_dump(edited, sort_keys=False, allow_unicode=True) + "---\n" + body,
        encoding="utf-8",
    )

    second = _entity_edit(tmp_path, entity, as_of=date(2026, 7, 28))

    reloaded = yaml.safe_load(second.final_text.split("---\n", 2)[1])
    assert reloaded["title"] == "An author's real title"
```

Add `from datetime import date` to the module imports.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_workbench_writer_containment.py -q`
Expected, and the two failure modes are different:

- `test_title_is_CREATE_ONLY` and `test_created_proposition_carries_only_owned_keys` fail with `ModuleNotFoundError: science_tool.dag.entity_frontmatter` — they import the module, which does not exist yet.
- `test_created_evidence_line_carries_no_skeleton_fields` and `test_created_evidence_line_keeps_a_deliberate_false` do **not** import it. The first fails its skeleton assertion under the old full-dump renderer; the second may pass already.
- `test_created_entity_has_a_non_empty_title` **passes already** — Task 1 supplied the title.
- `test_update_preserves_an_authors_replacement_title` passes too: the update path is correct today and that test is a regression guarding it, not a driver.

- [ ] **Step 3: Create the shared frontmatter module**

Create `science/src/science_tool/dag/entity_frontmatter.py`. **Move** the four blocks named below out of `workbench_apply.py` rather than copying them — two copies of an owned-key set is the defect this module exists to prevent:

```python
"""Which frontmatter keys the workbench owns, and how it renders them.

Shared by the two writers -- `workbench.compile_workbench` (create) and
`workbench_apply._entity_edit` (create + update). It lives in its own module because
`workbench_apply` imports `workbench`, so neither can host code the other needs.

The owned sets are POSITIVE allowlists. `render_entity_text` full-dumps the model
(`exclude_defaults=False`), which is what wrote `datapackage: ''` and `accessions: []` onto 391
evidence lines; rendering from an allowlist is what stops it.

`exclude_defaults=True` would NOT stop it. The skeleton fields are **required** on the model, not
defaulted -- a required field has no default to be excluded by -- so the flag emits them anyway.
No dump-mode flag can express "required for the model, not for the file"; only an allowlist can.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from science_model.entities import EvidenceLineEntity
from science_model.frontmatter import split_frontmatter
from science_model.propositions import PropositionEntity

from science_tool.entities import render_entity_text

WorkbenchEntity = PropositionEntity | EvidenceLineEntity


class FrontmatterRenderError(ValueError):
    """The entity's frontmatter could not be rendered."""


RENDERER_DERIVED_KEYS: frozenset[str] = frozenset(
    ("canonical_id", "content_preview", "content", "file_path", "type")
)

PROPOSITION_OWNED_KEYS: frozenset[str] = frozenset(
    (
        "id", "kind", "subject", "object", "predicate", "polarity",
        "legacy_relation_label", "legacy_patch", "legacy_edge_id", "discusses",
        "claim_layer", "identification_strength", "created", "updated",
    )
)

EVIDENCE_LINE_OWNED_KEYS: frozenset[str] = frozenset(
    (
        "id", "kind", "stance", "target", "source", "evidence_type",
        "quantitative_result", "belief_eligible", "created", "updated",
    )
)

# Keys the workbench owns ONLY when it creates a file. `title` is derived at lift and is a
# create-time default; on update the author's value wins, which is why it is absent from both
# per-kind sets above. `status` is likewise seeded once and then owned by the author.
CREATE_ONLY_KEYS: frozenset[str] = frozenset(("title", "status"))


def owned_keys(kind: str) -> frozenset[str]:
    if kind == "proposition":
        return PROPOSITION_OWNED_KEYS
    if kind == "evidence-line":
        return EVIDENCE_LINE_OWNED_KEYS
    raise FrontmatterRenderError(f"unsupported workbench entity kind: {kind}")


def generated_frontmatter(entity: WorkbenchEntity, *, created: str, updated: str) -> dict[str, object]:
    generated_text = render_entity_text(entity, body="", created=created, updated=updated)
    try:
        _prefix, frontmatter_text, _body = generated_text.split("---\n", 2)
    except ValueError as exc:
        raise FrontmatterRenderError(f"could not render entity frontmatter for {entity.id}") from exc
    loaded = yaml.safe_load(frontmatter_text) or {}
    if not isinstance(loaded, dict):
        raise FrontmatterRenderError(f"could not render entity frontmatter for {entity.id}")
    return loaded


def render_from_frontmatter(frontmatter: dict[str, object], body: str) -> str:
    # allow_unicode + wide: this is a read-modify-write, so an escaping/folding dumper rewrites
    # authored fields the edit never touched. Same rule as `entities._dump_frontmatter`.
    dumped = yaml.safe_dump(
        frontmatter, sort_keys=False, allow_unicode=True, default_flow_style=False, width=10_000
    )
    return "---\n" + dumped + "---\n" + body


def render_create(entity: WorkbenchEntity, *, body: str, created: str, updated: str) -> str:
    """Render a NEW entity file from the owned allowlist plus the create-only keys."""
    generated = generated_frontmatter(entity, created=created, updated=updated)
    allowed = owned_keys(entity.kind) | CREATE_ONLY_KEYS
    final = {key: value for key, value in generated.items() if key in allowed}
    final["created"] = created
    final["updated"] = updated
    return render_from_frontmatter(final, body)


class MalformedTargetError(ValueError):
    """An existing destination cannot be updated: wrong identity, unparseable, or undated."""


def read_existing_target(path: Path, entity: WorkbenchEntity) -> tuple[dict[str, object], str, str]:
    """Admit an existing destination for update, or refuse it.

    MOVED from `workbench_apply._read_existing_target` so BOTH writers share it. It must run
    BEFORE `render_update`, because `render_update` overwrites `id`, `kind`, `created` and
    `updated` -- so a destination with the wrong identity or no dates would be REPAIRED into
    validity before `certify_persisted` ever saw it, and the certification would pass on a file
    that was never admissible. Validating after a repair is not validating.
    """
    expected_id, expected_kind = entity.id, entity.kind
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            current_text = handle.read()
        frontmatter, body = split_frontmatter(current_text)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise MalformedTargetError(f"malformed existing entity target {path}: {exc}") from exc
    if frontmatter.get("id") != expected_id or frontmatter.get("kind") != expected_kind:
        raise MalformedTargetError(
            f"malformed existing entity target {path}: expected {expected_kind} {expected_id}"
        )
    if frontmatter.get("created") is None or frontmatter.get("updated") is None:
        raise MalformedTargetError(f"malformed existing entity target {path}: missing created/updated")
    return frontmatter, body, current_text


def render_update(
    entity: WorkbenchEntity,
    *,
    existing_frontmatter: dict[str, object],
    body: str,
    created: str,
    updated: str,
) -> str:
    """Render an EXISTING entity file: overwrite only owned keys, preserve everything else.

    `CREATE_ONLY_KEYS` is deliberately NOT applied here -- that is what makes `title` create-only
    and lets an author's replacement survive. Both writers use this, so the compile path and the
    apply path cannot diverge on what an update means.
    """
    final = {
        key: value
        for key, value in existing_frontmatter.items()
        if key not in RENDERER_DERIVED_KEYS
    }
    generated = generated_frontmatter(entity, created=created, updated=updated)
    for key in owned_keys(entity.kind):
        if key in generated:
            final[key] = generated[key]
    final["created"] = created
    final["updated"] = updated
    return render_from_frontmatter(final, body)
```

- [ ] **Step 4: Point `workbench_apply` at the module**

In `workbench_apply.py`: delete `_RENDERER_DERIVED_FRONTMATTER_KEYS`, `_PROPOSITION_WORKBENCH_FRONTMATTER_KEYS`, `_EVIDENCE_LINE_WORKBENCH_FRONTMATTER_KEYS`, `_generated_frontmatter`, `_render_entity_text_from_frontmatter` and `_workbench_frontmatter_keys`, and import the replacements:

```python
from science_tool.dag.entity_frontmatter import (
    MalformedTargetError,
    WorkbenchEntity,
    read_existing_target,
    render_create,
    render_update,
)
```

Also delete `_render_workbench_entity_update` entirely — `render_update` replaces it — **move `_read_existing_target` (`:215`) into the module** as `read_existing_target` (public, and now shared). `_parse_existing_target_text` (`:211`) is a one-line wrapper around `split_frontmatter` whose only caller is the function being moved — **delete it** rather than moving it; the module calls `split_frontmatter` directly, and delete the local `WorkbenchEntity = PropositionEntity | EvidenceLineEntity` alias (`:34`) in favour of the imported one.

`_read_existing_target` raised `WorkbenchApplyError`; `read_existing_target` raises `MalformedTargetError`. **`_entity_edit` must catch and re-raise** — `test_workbench_apply.py:383`, `test_apply_workbench_rejects_malformed_existing_target_before_write`, catches `WorkbenchApplyError` explicitly and asserts on its message, so an uncaught `MalformedTargetError` fails it. In the update branch:

```python
    try:
        frontmatter, body, current_text = read_existing_target(path, entity)
    except MalformedTargetError as exc:
        raise WorkbenchApplyError(str(exc)) from exc
```

The message text is preserved verbatim, so that test's `"malformed existing entity target" in str(exc)` assertion keeps holding. The compile path does **not** wrap: it has no `WorkbenchApplyError` contract, and `MalformedTargetError` is what its own inverted test asserts. Update the two `_render_workbench_entity_update(...)` call sites in `_entity_edit` to `render_update(...)`; the keyword arguments are identical.

`_workbench_frontmatter_keys` raised `WorkbenchApplyError` for an unsupported kind; `owned_keys` raises `FrontmatterRenderError`. If any test asserts the former, keep it passing by having `WorkbenchApplyError` subclass nothing new — instead catch and re-raise at the one call site that needs the old type. Check with `rg -n "unsupported workbench entity kind" science/tests` before deciding; if nothing asserts it, no shim is needed.

Then `render_entity_text`, `PropositionEntity` and `EvidenceLineEntity` may become unused imports in `workbench_apply.py` — Ruff will say so. Remove whichever it flags.

- [ ] **Step 5: Use the create renderer in `_entity_edit`**

```python
    if not path.exists():
        body = workbench_entity_body(entity)
        final_text = render_create(entity, body=body, created=today, updated=today)
```

- [ ] **Step 6: Fix the second writer — and make it an upsert, not a create**

`workbench._write_entity_file` (`:313`) delegates to `entities.write_entity_file`, which full-dumps. It is also an **upsert**: `compile_workbench` runs repeatedly over the same rows, and the existing implementation already preserves `created` from the destination — evidence its author knew the file may exist.

**Rendering every call as a create would overwrite the author's `title`, `status`, any non-owned frontmatter, and the body.** That contradicts design §5.3's preservation rule and would defeat the create-only ruling for `title` on the very path that writes most entities. Branch exactly as `_entity_edit` does:

```python
def _write_entity_file(
    entity: PropositionEntity | EvidenceLineEntity,
    *,
    project_root: Path,
    as_of: date | None = None,
) -> None:
    """Workbench writer: owned-allowlist frontmatter, never a full model dump.

    An UPSERT. `compile_workbench` is re-run over the same rows routinely, so the destination
    usually exists; rendering it as a create would overwrite the author's title, status and body
    on every recompile. Deliberately NOT `entities.write_entity_file`, which renders the whole
    model and would re-introduce the skeleton dump on this path.
    """
    from science_tool.dag.entity_frontmatter import read_existing_target, render_create, render_update
    from science_tool.entities import _atomic_replace_text, resolve_path_policy

    today = (as_of or date.today()).isoformat()
    assert entity.id is not None
    local_part = entity.id.split(":", 1)[1]
    dest = project_root / resolve_path_policy(entity.kind, project_root=project_root).root / f"{local_part}.md"

    if dest.exists():
        # ADMIT FIRST. `read_existing_target` refuses a wrong-identity, undated or unparseable
        # destination. Reading the file directly and defaulting `created` -- as an earlier draft
        # of this plan did -- lets `render_update` overwrite id/kind/created/updated and hand
        # `certify_persisted` a mapping that is valid only because it was just repaired.
        existing_frontmatter, existing_body, _current = read_existing_target(dest, entity)
        text = render_update(
            entity,
            existing_frontmatter=existing_frontmatter,
            body=existing_body,
            created=str(existing_frontmatter["created"]),
            updated=today,
        )
    else:
        text = render_create(
            entity, body=workbench_entity_body(entity), created=today, updated=today
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    _atomic_replace_text(dest, text)
```

**The old `try/except (yaml.YAMLError, ValueError, OSError)` around the existing-file read is deliberately gone.** It swallowed a malformed destination and fell through to a full overwrite — a silent fallback that destroys an author's file precisely when something is already wrong with it.

This also **ends an existing divergence**: `_entity_edit` already refuses a malformed target via `_read_existing_target`, while the compile path silently overwrote it. Two writers, two answers to "may I update this file?" — the same defect the shared module exists to remove. Step 9 schedules the behavioural test this inverts.

**Verify the two imported helper names** exist in `science/src/science_tool/entities.py` before writing this — `_atomic_replace_text` (`:1769`) and `resolve_path_policy` (`:365`). Body preservation is handled by `read_existing_target`, which returns it.

- [ ] **Step 7: Write the upsert regression**

Append to `science/tests/test_workbench_writer_containment.py`:

```python
def test_recompiling_preserves_an_authors_title_and_body(tmp_path) -> None:
    # `compile_workbench` is re-run routinely. If its writer rendered every call as a create, the
    # second run would silently overwrite the title an author wrote and the prose under it -- on
    # the path that writes most entities.
    import yaml

    from science_tool.dag import workbench as wb

    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    workbench = wb.WorkbenchFile.model_validate(
        {"patch": "p", "rows": [{"subject": "concept:a", "predicate": "affects",
                                 "object": "concept:b", "patch": "p", "polarity": "unsigned"}]}
    )
    wb.compile_workbench(workbench, project_root=tmp_path, as_of=date(2026, 7, 27))

    written = next((tmp_path / "entities").rglob("*.md"))
    frontmatter, body = written.read_text(encoding="utf-8").split("---\n", 2)[1:]
    edited = yaml.safe_load(frontmatter) | {"title": "An author's real title"}
    written.write_text(
        "---\n" + yaml.safe_dump(edited, sort_keys=False, allow_unicode=True) + "---\n"
        + body + "\nAuthored prose.\n",
        encoding="utf-8",
    )

    wb.compile_workbench(workbench, project_root=tmp_path, as_of=date(2026, 7, 28))

    after = written.read_text(encoding="utf-8")
    assert yaml.safe_load(after.split("---\n", 2)[1])["title"] == "An author's real title"
    assert "Authored prose." in after
```

```python
@pytest.mark.parametrize(
    "corruption",
    [
        pytest.param({"id": "question:wrong"}, id="wrong-id"),
        pytest.param({"kind": "question"}, id="wrong-kind"),
        pytest.param({"created": None}, id="missing-created"),
    ],
)
def test_compile_refuses_a_PARSEABLE_but_inadmissible_destination(tmp_path, corruption) -> None:
    # THE defect this admission rule exists for, and the one the two tests above CANNOT reach:
    # a destination that parses fine but is not this entity's file, or has no dates.
    # `render_update` overwrites id, kind, created and updated, so without `read_existing_target`
    # running FIRST the file is repaired into validity and `certify_persisted` passes on a record
    # that was never admissible. Malformed YAML does not prove this -- it raises during parsing
    # even when the admission checks are skipped entirely.
    import yaml

    from science_tool.dag import workbench as wb
    from science_tool.dag.entity_frontmatter import MalformedTargetError

    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    workbench = wb.WorkbenchFile.model_validate(
        {"patch": "p", "rows": [{"subject": "concept:a", "predicate": "affects",
                                 "object": "concept:b", "patch": "p", "polarity": "unsigned"}]}
    )
    wb.compile_workbench(workbench, project_root=tmp_path, as_of=date(2026, 7, 27))

    written = next((tmp_path / "entities").rglob("*.md"))
    frontmatter, body = written.read_text(encoding="utf-8").split("---\n", 2)[1:]
    corrupted = yaml.safe_load(frontmatter) | corruption
    corrupted = {k: v for k, v in corrupted.items() if v is not None}  # None means "remove the key"
    written.write_text(
        "---\n" + yaml.safe_dump(corrupted, sort_keys=False, allow_unicode=True) + "---\n" + body,
        encoding="utf-8",
    )
    before = written.read_bytes()

    with pytest.raises(MalformedTargetError):
        wb.compile_workbench(workbench, project_root=tmp_path, as_of=date(2026, 7, 28))

    assert written.read_bytes() == before, "a refused destination was modified anyway"
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_workbench_writer_containment.py -q`
Expected: PASS.

- [ ] **Step 9: Run the tool suite and fix rendered-shape expectations**

Run: `cd science && uv run --frozen pytest -q` (allow ~3 min).
**One BEHAVIOURAL failure is expected and must be inverted, not adjusted.** `test_workbench_compile_conformance.py:217`, `test_malformed_existing_entity_falls_back_gracefully`, writes malformed YAML into an existing destination, recompiles, and asserts compile "must NOT raise" — it requires the silent replacement Step 6 deliberately removed. Rewrite it to assert the new, intended behaviour:

```python
def test_malformed_existing_entity_is_REFUSED(tmp_path: Path) -> None:
    """A corrupt existing entity file is refused; the file is left byte-identical.

    Inverted deliberately (design §5.3). The old behaviour silently replaced the file, which
    destroys an author's content exactly when something is already wrong with it -- and it
    disagreed with the apply path, which has always refused a malformed target.
    """
    from science_tool.dag.entity_frontmatter import MalformedTargetError

    ...  # seeding unchanged from the original test, up to and including the malformed write
    prop_path.write_text("---\n: : bad yaml\n---\n", encoding="utf-8")
    before = prop_path.read_bytes()

    with pytest.raises(MalformedTargetError):
        compile_workbench(wb, project_root=tmp_path, as_of=date(2026, 7, 1))

    assert prop_path.read_bytes() == before
```

Rename the test — the old name asserts the behaviour being removed.

**Every other failure should be a rendered-shape expectation** — `test_workbench_apply.py`, `test_workbench_compile.py`, `test_workbench_idempotent.py` and the rest of `test_workbench_compile_conformance.py` are the likely set. For each, the correct fix is to **drop the now-absent skeleton keys from the expectation** and add the derived title. A failure that is neither the malformed-file test above nor a rendered-shape expectation is a real regression: stop and investigate rather than adjusting the test.

- [ ] **Step 10: Commit**

```bash
# Step 9 repairs existing modules that asserted on created-file frontmatter. Run
# `git status --short` and add every path it names; these are the ones Step 9 predicts.
git add science/src/science_tool/dag/entity_frontmatter.py \
        science/src/science_tool/dag/workbench_apply.py \
        science/src/science_tool/dag/workbench.py \
        science/tests/test_workbench_writer_containment.py \
        science/tests/test_workbench_apply.py \
        science/tests/test_workbench_compile.py \
        science/tests/test_workbench_idempotent.py \
        science/tests/test_workbench_compile_conformance.py
git commit -m "feat(workbench): render new entity files from an owned allowlist

Both create paths full-dumped the model, which is what wrote datapackage: ''
and accessions: [] onto 391 evidence lines. They now emit the per-kind owned
set plus title and status, which are create-only so an author's replacement
survives the next apply. Not exclude_defaults=True: the skeleton fields are
required rather than defaulted, so that flag emits them anyway.

The owned sets and both renderers move to dag/entity_frontmatter.py: workbench_apply
imports workbench, so neither could host code the other needs, and a second copy of
an owned-key set is the defect this module prevents."
```

---

### Task 4: Validate at the persistence boundary, and reject stale records

**Files:**
- Modify: `science/src/science_tool/dag/entity_frontmatter.py` (`certify_persisted`, called from `render_create` and `render_update`)
- Test: `science/tests/test_workbench_writer_containment.py`

`workbench_apply.py` is **not** modified by this task: after Task 3 it renders through the shared module, so certification reaches it without any edit here.

**Interfaces:**
- Consumes: `EntityValidator.validate_persisted_base_shape` from Task 2.
- Produces: `entity_frontmatter.certify_persisted(entity, text, *, path)` and `entity_frontmatter.PersistedShapeError`.

**Certification lives in the two module renderers, not in their callers.** There are two create paths (Task 3), and putting the check in the caller would cover only one of them — a compile-path regression could still persist an invalid base shape. After Task 3 all four write paths — `_entity_edit` create and update, `compile_workbench` create and update — go through `render_create` / `render_update`, so certifying inside those two functions covers every one by construction, with no call site that could omit it.

**The ruling being implemented (design §5.4).** An update targeting one of the 769 pre-existing empty-title records **fails**, naming the record and the field. Not skipped, not backfilled. Skipping re-creates the defect being closed; backfilling turns an ordinary update into a silent migration of a record the author did not ask to touch, repairing the population piecemeal in an order set by whoever happened to edit what.

**Accepted cost:** until piece 3 lands, a workbench apply touching any of the 432 evidence-line or 337 proposition records fails. That is a real regression for mm30 and an argument for sequencing piece 3 promptly, not for weakening the rule.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_workbench_writer_containment.py`:

```python
def test_update_of_an_empty_title_record_is_REJECTED(tmp_path) -> None:
    # THE §5.4 ruling. Three implementations were plausible -- reject, skip validation, backfill --
    # and only rejection is fail-early without silently migrating a record nobody asked to touch.
    from science_tool.dag.entity_frontmatter import PersistedShapeError
    from science_tool.dag.workbench_apply import _entity_edit

    entity = _proposition_for_row(_row())
    edit = _entity_edit(tmp_path, entity, as_of=date(2026, 7, 27))
    edit.path.parent.mkdir(parents=True, exist_ok=True)
    edit.path.write_text(
        edit.final_text.replace(f"title: {entity.title}", "title: ''"), encoding="utf-8"
    )

    with pytest.raises(PersistedShapeError) as exc:
        _entity_edit(tmp_path, entity, as_of=date(2026, 7, 28))

    message = str(exc.value)
    assert entity.id in message            # names the record
    assert "title" in message              # names the field
    assert edit.path.read_text(encoding="utf-8").count("title: ''") == 1  # and wrote nothing


def test_the_apply_create_path_is_validated_too(tmp_path, monkeypatch) -> None:
    # Both create paths, not just the risky-looking one. Neutralize the title derivation and the
    # create path must refuse to plan a write rather than emit an empty-title file.
    from science_tool.dag.entity_frontmatter import PersistedShapeError
    from science_tool.dag.workbench_apply import _entity_edit

    entity = _proposition_for_row(_row())
    monkeypatch.setattr(entity, "title", "", raising=False)
    with pytest.raises(PersistedShapeError, match="title"):
        _entity_edit(tmp_path, entity, as_of=date(2026, 7, 27))


def test_the_COMPILE_path_is_validated_and_writes_nothing(tmp_path, monkeypatch) -> None:
    # The second create path, exercised through its real entry point. Task 3 routes it through the
    # shared renderer; without certification INSIDE render_create, a compile-path regression could
    # still persist an invalid base shape while `_entity_edit` stayed green.
    from science_tool.dag import workbench as wb
    from science_tool.dag.entity_frontmatter import PersistedShapeError

    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    monkeypatch.setattr(wb, "_proposition_title", lambda row: "")
    workbench = wb.WorkbenchFile.model_validate(
        {"patch": "p", "rows": [{"subject": "concept:a", "predicate": "affects",
                                 "object": "concept:b", "patch": "p", "polarity": "unsigned"}]}
    )

    with pytest.raises(PersistedShapeError, match="title"):
        wb.compile_workbench(workbench, project_root=tmp_path, as_of=date(2026, 7, 27))

    assert not list((tmp_path / "entities").rglob("*.md")), "a refused compile still wrote a file"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_workbench_writer_containment.py -q`
Expected: **all three FAIL** — `test_update_of_an_empty_title_record_is_REJECTED`, `test_the_apply_create_path_is_validated_too` and `test_the_COMPILE_path_is_validated_and_writes_nothing`. No validation runs at the boundary yet, so each returns or writes instead of raising, and the import of `PersistedShapeError` fails until Step 3 defines it. If the compile test errors on the monkeypatch target instead, correct it to wherever Task 1 placed `_proposition_title`; do not weaken the assertion.

- [ ] **Step 3: Add the boundary check to the shared module**

In `science/src/science_tool/dag/entity_frontmatter.py`:

```python
class PersistedShapeError(ValueError):
    """A write was refused because its result would not satisfy the durable base shape."""


def certify_persisted(entity: WorkbenchEntity, text: str, *, path: Path | None = None) -> None:
    """Refuse to render or plan a write whose result would fail the durable base shape.

    On create this catches a writer regression; on update it catches a record that predates
    containment -- deliberately a REJECTION, not a backfill (design §5.4): a workbench update must
    not silently migrate a record the author did not ask to touch.
    """
    frontmatter = yaml.safe_load(text.split("---\n", 2)[1]) or {}
    try:
        EntityValidator().validate_persisted_base_shape(frontmatter)
    except EntityValidationError as exc:
        where = f"{path}: " if path is not None else ""
        raise PersistedShapeError(
            f"{where}{entity.id} would not satisfy the durable base shape and was NOT written\n"
            f"  {exc}\n"
            f"  If this record predates writer containment, repair it directly; the workbench "
            f"will not backfill it."
        ) from exc
```

Import to add at the top of the module (`Path` is already there from Task 3):

```python
from science_model.entity_schema import EntityValidationError, EntityValidator
```

- [ ] **Step 4: Certify both paths**

Certify inside **both** module renderers, immediately before each returns:

```python
    text = render_from_frontmatter(final, body)
    certify_persisted(entity, text)
    return text
```

Since Task 3 routed all four write paths — `_entity_edit` create and update, `compile_workbench` create and update — through `render_create` / `render_update`, this covers every one of them. `workbench_apply` needs **no** direct call, which is the point: certification cannot be forgotten at a call site because there is no call site to forget it at.

`_entity_edit` renders twice on the update branch — `unchanged_timestamp_text` exists only to decide whether `updated` advances — so certification runs on both renderings. That is harmless: they differ only in the `updated` value and either failing means the write must not proceed.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_workbench_writer_containment.py -q`
Expected: PASS.

- [ ] **Step 6: Run both suites, lint and types**

Run: `cd science/model && uv run --frozen pytest -q`, then `cd science && uv run --frozen pytest -q` (allow ~3 min), then `cd science && uv run ruff check && uv run pyright`.
Expected: all green. Any test that constructs a workbench entity fixture with an empty title now fails **correctly** — fix the fixture, not the boundary.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/dag/entity_frontmatter.py \
        science/tests/test_workbench_writer_containment.py
git commit -m "feat(workbench): certify the persisted shape on every write path

An update targeting a pre-containment empty-title record is now rejected,
naming the record and the field, rather than skipped or backfilled. Skipping
would persist source the writer never checked; backfilling would turn an
ordinary update into a silent migration of a record nobody asked to touch, and
repair the population in whatever order people happened to edit it."
```

---

### Task 5: Mutation proofs

**Files:**
- Test: `science/tests/test_workbench_writer_containment.py`

Every guard in this plan must be shown to fail by a **named** test. A guard nobody has watched fail is a guard nobody has tested. Each mutation below is applied by hand, the expected failure observed, and then **reverted**.

- [ ] **Step 1: Mutation A — the title format**

Change `_proposition_title` to `f"{row.subject} {row.object}"` (drop the predicate).
Run: `cd science && uv run --frozen pytest tests/test_workbench_writer_containment.py -q`
Expected: **two** failures — `test_proposition_title_is_the_triple` and
`test_generated_titles_are_whitespace_collapsed`. Both assert the triple format, so dropping the
predicate breaks each independently; the format is pinned twice, not once. **Revert.**

- [ ] **Step 2: Mutation B — the evidence-line qualifier**

Change `_evidence_line_title` to ignore `stub.source`.
Expected: `test_evidence_line_title_uses_source_when_present` FAILS. **Revert.**

- [ ] **Step 3: Mutation C — the row guard**

Remove `min_length=1` from `WorkbenchRow.subject`.
Expected: `test_empty_triple_terms_fail_at_PARSE_time[subject]` FAILS. **Revert.**

- [ ] **Step 4: Mutation D — title in the update set**

Add `"title"` to `PROPOSITION_OWNED_KEYS` in `entity_frontmatter.py`.
Expected: **four** failures — `test_title_is_CREATE_ONLY` (set arithmetic), `test_update_preserves_an_authors_replacement_title` (apply path), `test_recompiling_preserves_an_authors_title_and_body` (compile path), and `test_update_of_an_empty_title_record_is_REJECTED`. The three behavioural ones are what matter; the set assertion alone would be an equality with no consequence attached. Both write paths failing is the point — a create-only key that leaks into the update set breaks every writer, not one. The fourth is the instructive one: with `title` owned, `render_update` OVERWRITES the record's empty title with the derived one before `certify_persisted` ever sees the mapping, so the rejection silently becomes a backfill. That is the same repair-before-validate mode Mutation G targets, reached here by a different door — which is why a create-only key is a containment property, not a cosmetic one. **Revert.**

- [ ] **Step 5: Mutation E — the allowlist**

In `entity_frontmatter.render_create`, return `render_from_frontmatter(generated, body)` (skip the allowlist filter).
Expected: `test_created_evidence_line_carries_no_skeleton_fields` and `test_created_proposition_carries_only_owned_keys` FAIL, naming the leaked keys. **Revert.**

- [ ] **Step 6: Mutation F — the rejection ruling**

In `entity_frontmatter.certify_persisted`, replace the `raise` with `return` (the "skip validation" implementation §5.4 rejects).
Expected: **three** failures — `test_update_of_an_empty_title_record_is_REJECTED`, `test_the_apply_create_path_is_validated_too`, and `test_the_COMPILE_path_is_validated_and_writes_nothing`. Suppressing the raise defeats certification on every path at once, which is what makes G2 (where certification *lives*) a separate and necessary proof. **Revert.**

- [ ] **Step 7: Mutation G — the backfill temptation**

Implement the backfill for real — mutating the parsed mapping inside `certify_persisted` is **not** enough, because that mapping is discarded and the original invalid text is still what gets persisted. That would prove a validation bypass (Mutation F already does), not a silent migration. Apply it inside **`render_update`** (and `render_create`), repairing the rendered text before certifying — that is the only place the repaired value reaches what is persisted:

```python
    text = render_from_frontmatter(final, body)
    reparsed = yaml.safe_load(text.split("---\n", 2)[1]) or {}
    if not str(reparsed.get("title") or "").strip():
        reparsed["title"] = entity.title
        text = render_from_frontmatter(reparsed, body)   # reassign, or the repair is discarded
    certify_persisted(entity, text)
    return text
```

**Do not attempt this in `_entity_edit`'s update branch.** After Task 4 that branch has no `text` local — the persisted variable is `final_text`, and a mutation that introduces a new `text` local leaves `final_text` untouched and the file unchanged. Applied literally there, the mutation is inert or raises `NameError`, and neither is a proof.
Expected: `test_update_of_an_empty_title_record_is_REJECTED` FAILS — no exception is raised **and the file is silently repaired**. This mutation is listed separately from F because it is the *plausible* wrong answer: it looks helpful, it produces a valid file, and it makes the suite green if the rejection test is missing. F proves the check runs; G proves the check must **refuse** rather than fix. **Revert.**

- [ ] **Step 8: Mutation G2 — certification in the caller instead of the renderer**

Move the `certify_persisted` call out of `render_create` and into `_entity_edit`'s create branch.
Expected: `test_the_COMPILE_path_is_validated_and_writes_nothing` FAILS — `_entity_edit` is still covered, but the compile path is not. This is the mutation that proves *where* certification lives matters, not merely that it exists. **Revert.**

- [ ] **Step 9: Mutation H — the `exclude_defaults` trap**

Make `render_create` filter-free and thread `exclude_defaults=True` into `generated_frontmatter`'s
`render_entity_text` call. (`render_entity_text` takes no such parameter, so this needs a temporary
local variant — that friction is itself informative.)

Expected — **measured, not predicted**: `test_created_evidence_line_carries_no_skeleton_fields`
FAILS, leaking exactly `['ontology_terms', 'project', 'related', 'source_refs']`. Those are
*required* on `EvidenceLineEntity`, so `exclude_defaults` has no default to exclude them by and
they are written regardless.

`test_created_proposition_carries_only_owned_keys` **PASSES** under this mutation — proposition
leaks nothing, because `PropositionEntity` gives those fields defaults where `EvidenceLineEntity`
requires them. The mutation still proves the flag is insufficient; it proves it through
evidence-line alone. An earlier revision predicted both would fail, which was wrong.

This is the mutation's whole point: it shows the flag is not a cheaper substitute for the
allowlist. **`test_created_evidence_line_keeps_a_deliberate_false` is expected to keep PASSING** —
`belief_eligible` defaults to `True`, so a deliberate `False` survives the flag. An earlier
revision of this plan predicted the opposite and was wrong. **Revert.**

- [ ] **Step 10: Mutation I2 — bypass the admission rule**

In `workbench._write_entity_file`, replace the `read_existing_target(dest, entity)` call with a
direct read: `existing_frontmatter, existing_body = split_frontmatter(dest.read_text(encoding="utf-8"))`,
and pass `created=str(existing_frontmatter.get("created") or today)`.

Expected: all three `test_compile_refuses_a_PARSEABLE_but_inadmissible_destination` cases FAIL — no
exception is raised, because `render_update` overwrites `id`, `kind` and `created`, so the mapping
`certify_persisted` sees is valid.

`test_malformed_existing_entity_is_REFUSED` ALSO breaks under this mutation, but by ERRORING rather
than failing: the direct `split_frontmatter` call lets a bare `yaml.parser.ParserError` escape,
where the test asserts `MalformedTargetError`. Invalid YAML does still raise during parsing — the
exception TYPE is what changes, and `read_existing_target` is what converts one into the other. So
that test cannot stand in for this one for two independent reasons: it never exercises a parseable
destination at all, and its raise is a parser artifact rather than an admission decision. **Revert.**

- [ ] **Step 11: Mutation I — the format checker**

Remove `format_checker=Draft202012Validator.FORMAT_CHECKER` from `validate_persisted_base_shape`.
Run: `cd science/model && uv run --frozen pytest tests/test_persisted_base_shape.py -q`
Expected: `test_an_invalid_date_is_refused` FAILS — with no checker, JSON Schema treats `format` as
an annotation and `created="not-a-date"` produces zero errors. Every other test in the module stays
green, which is exactly why this mutation is needed: without it the checker is load-bearing and
untested. **Revert.**

- [ ] **Step 12: Verify the tree is clean and both suites green**

All eleven mutations above (A–I, including G2 and I2) were reverted, and Task 5 adds no code — every test they exercise was written in Tasks 1–4.

Run: `git status --short`
Expected: **empty**. Any remaining modification is an unreverted mutation; revert it before proceeding.

Run: `cd science/model && uv run --frozen pytest -q`, then `cd science && uv run --frozen pytest -q` (allow ~3 min), then `cd science && uv run ruff check && uv run pyright`.
Expected: all green.

There is no commit in this task.

---

## Verification

After Task 5, from a clean tree on the branch:

```bash
cd science/model && uv run --frozen pytest -q
cd science && uv run --frozen pytest -q      # ~3 min; run AFTER the model suite, never concurrently
cd science && uv run ruff check && uv run pyright
```

Then confirm the end state — no create path can emit a skeleton:

```bash
cd science && uv run --frozen python - <<'PY'
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import yaml
from science_tool.dag.workbench import EvidenceStub, WorkbenchRow, _evidence_line_for_stub, _proposition_for_row
from science_tool.dag.entity_frontmatter import (
    CREATE_ONLY_KEYS, EVIDENCE_LINE_OWNED_KEYS, PROPOSITION_OWNED_KEYS,
)
from science_tool.dag.workbench_apply import _entity_edit
row = WorkbenchRow(subject="concept:a", predicate="affects", object="concept:b", patch="p",
                   polarity="unsigned")  # `affects` is sign-meaningful; omitting this raises
cases = [
    (_proposition_for_row(row), PROPOSITION_OWNED_KEYS),
    (_evidence_line_for_stub(EvidenceStub(stance="supports"), target_id="proposition:0001-x", index=0),
     EVIDENCE_LINE_OWNED_KEYS),
]
with TemporaryDirectory() as d:
    for entity, owned in cases:
        fm = yaml.safe_load(_entity_edit(Path(d), entity, as_of=date(2026, 7, 27))
                            .final_text.split("---\n", 2)[1])
        extra = set(fm) - (owned | CREATE_ONLY_KEYS)
        print(f"{entity.kind:14} title={fm['title']!r:46} unowned={sorted(extra)}")
PY
```

Expected: both lines show a non-empty title and `unowned=[]`.

## Out of scope

- **Backfilling the 769 existing records.** Piece 3. This plan makes them *fail loudly* on update; it repairs none of them.
- **Closing any kind's schema.** Piece 2. Nothing here touches `PROJECT_MIXIN_NAMES`, the generation matrix, or any mixin.
- **`entities.render_entity_text` itself.** It is the general typed-entity renderer with callers far beyond the workbench. This plan routes the workbench's two create paths around it rather than changing its contract for everyone.
- **The `legacy_relation_label` / `legacy_patch` / `legacy_edge_id` triple.** They are in `PROPOSITION_OWNED_KEYS` and stay there; deleting them is piece 3's corpus migration.
- **`entities.write_entity_file`'s own full dump.** Task 3 routes the workbench around it; other callers are untouched and out of scope.
