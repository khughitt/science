# Proposition Reasoning Invalidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep workbench updates loadable and provenance-honest by canonicalizing sign-less polarity, invalidating stale synthesis stamps only on effective reasoning changes, and certifying the merged typed entity before writing.

**Architecture:** Extend the existing per-writer `Ownership` value with declarative change triggers and invalidated keys; the shared update renderer compares persisted values with the effective post-merge mapping. Keep absent values preserve-by-default, canonicalize the one predicate-dependent field at workbench lift, and strengthen `certify_persisted` with an explicit absent-only six-key skeleton for typed validation.

**Tech Stack:** Python 3.12, frozen Pydantic v2 models, PyYAML, pytest, Ruff, Pyright, uv.

## Global Constraints

- Preserve an existing optional value when the writer's generated mapping omits it. Do not add general absent-key deletion.
- A workbench row with a sign-less predicate and omitted polarity writes `not_applicable`; a sign-meaningful predicate still requires an authored polarity.
- Clear `reasoning_source` only when the workbench changes an effective `subject`, `object`, `predicate`, `polarity`, or `claim_layer` value.
- An idempotent recompile and a non-reasoning edit preserve `reasoning_source`.
- `clear_on_change` grants deletion-only invalidation authority. It must remain disjoint from `owned`, which is write authority.
- Typed certification may fill only `project`, `ontology_terms`, `related`, `source_refs`, `content_preview`, and `file_path`, and only when absent from the rendered frontmatter. Never validate a blanket model-dump/frontmatter merge.
- This slice changes no corpus files and does not touch the legacy triple, corpus migration, evidence-line clearing semantics, or mm30 validation findings.
- Run uv commands from `science/` or `science/model/`, never the repository root. Never run two pytest suites concurrently in one worktree.
- Use no compatibility layer, no `Unified` prefix, no new dependency, and no AI-attribution commit trailer.

---

## File Structure

| File | Responsibility in this slice |
|---|---|
| `science/src/science_tool/dag/entity_frontmatter.py` | Shared attested-field tuple, ownership invalidation contract, effective-merge invalidation, and typed persisted certification. |
| `science/src/science_tool/annotation/synthesize.py` | Reuse the shared ordered attested-field tuple as `SYNTH_FIELDS`; synthesis behavior otherwise stays unchanged. |
| `science/src/science_tool/dag/workbench.py` | Canonicalize omitted polarity to `not_applicable` for sign-less predicates at row lift. |
| `science/tests/test_workbench_writer_containment.py` | Low-level certification, ownership, merge-order, compile-path, and evidence-line regressions. |
| `science/tests/test_workbench_apply.py` | Apply-path invalidation and unchanged-timestamp/no-op regressions. |

No new source module is warranted: all behavior belongs at one of the three existing boundaries above.

Unless a step says otherwise, run every Task 1-3 `uv` command from `science/` and every `git`
command from the repository root.

Execute Tasks 1-4 in an isolated worktree on branch `proposition-reasoning-invalidation`,
created from the commit containing this final plan revision. Do not put the implementation
commits directly on `main`.

---

### Task 1: Certify the merged typed entity

**Files:**
- Modify: `science/src/science_tool/dag/entity_frontmatter.py:23-25,119-146`
- Test: `science/tests/test_workbench_writer_containment.py:12-21,244-325`

**Interfaces:**
- Consumes: `WorkbenchEntity = PropositionEntity | EvidenceLineEntity`, `split_frontmatter(text)`, and `EntityValidator.validate_persisted_base_shape(frontmatter)`.
- Produces: `TYPED_VALIDATION_SKELETON_KEYS: frozenset[str]` and a strengthened `certify_persisted(entity: WorkbenchEntity, text: str) -> None` that raises `PersistedShapeError` for base or typed failures.

- [ ] **Step 1: Add the invalid merged-proposition regression**

Add this test to `test_workbench_writer_containment.py`. The fixture deliberately includes `title`, `status`, `created`, and `updated`, so base-shape validation passes first. The assertion on `sign-less` proves the failure came from the typed polarity interlock rather than the base validator.

```python
def test_typed_certification_rejects_an_invalid_merged_proposition() -> None:
    from science_model.propositions import PropositionEntity
    from science_model.reasoning import Predicate

    from science_tool.dag.entity_frontmatter import (
        Ownership,
        PersistedShapeError,
        render_update,
    )

    existing = {
        "id": "proposition:x",
        "kind": "proposition",
        "title": "A affects B",
        "status": "active",
        "subject": "concept:a",
        "object": "concept:b",
        "predicate": "affects",
        "polarity": "positive",
        "created": "2026-07-01",
        "updated": "2026-07-01",
    }
    entity = PropositionEntity(
        id="proposition:x",
        title="A binds B",
        subject="concept:a",
        object="concept:b",
        predicate=Predicate.BINDS,
    )
    # This synthetic future writer changes predicate but does not own polarity, so the stale
    # signed value survives the merge. No live writer has this ownership shape after Task 3.
    ownership = Ownership(
        frozenset({"id", "kind", "subject", "object", "predicate", "created", "updated"})
    )

    with pytest.raises(PersistedShapeError, match="sign-less"):
        render_update(
            entity,
            ownership=ownership,
            existing_frontmatter=existing,
            body="\n# Affects\n",
            created="2026-07-01",
            updated="2026-07-31",
        )
```

- [ ] **Step 2: Add the evidence-line skeleton regression**

Add this test beside the existing evidence-line containment tests. It proves three separate facts: raw typed validation really fails, writer certification succeeds only with the six-key fill, and none of the fill values leaks into persisted frontmatter.

```python
def test_evidence_line_typed_certification_fills_only_unpersisted_skeleton() -> None:
    from science_model.entities import EvidenceLineEntity
    from science_model.frontmatter import split_frontmatter

    from science_tool.dag.entity_frontmatter import (
        TYPED_VALIDATION_SKELETON_KEYS,
        WORKBENCH_EVIDENCE_LINE,
        certify_persisted,
        render_create,
    )

    line = _evidence_line_for_stub(
        EvidenceStub(stance="supports", source="paper:S"),
        target_id="proposition:0001-x",
        index=0,
    )
    text = render_create(
        line,
        ownership=WORKBENCH_EVIDENCE_LINE,
        body="\n# Evidence\n",
        created="2026-07-01",
        updated="2026-07-01",
    )
    frontmatter, _body = split_frontmatter(text)

    with pytest.raises(ValidationError) as exc:
        EvidenceLineEntity.model_validate(frontmatter)
    missing = {error["loc"][0] for error in exc.value.errors() if error["type"] == "missing"}
    assert missing == TYPED_VALIDATION_SKELETON_KEYS

    certify_persisted(line, text)
    assert not (set(frontmatter) & TYPED_VALIDATION_SKELETON_KEYS)
```

- [ ] **Step 3: Run the new tests and verify the typed guard is red**

Run from `science/`:

```bash
uv run --frozen pytest \
  tests/test_workbench_writer_containment.py::test_typed_certification_rejects_an_invalid_merged_proposition \
  tests/test_workbench_writer_containment.py::test_evidence_line_typed_certification_fills_only_unpersisted_skeleton -q
```

Expected: FAIL. The proposition test reports that `PersistedShapeError` was not raised; the evidence test may also fail to import the not-yet-defined skeleton constant. A base-shape error mentioning `title`, `status`, or dates means the proposition fixture is wrong and must be corrected before continuing.

- [ ] **Step 4: Add the explicit absent-only skeleton and typed validation**

Import Pydantic's error at module scope:

```python
from pydantic import ValidationError
```

Define the exact fill set beside the renderer constants:

```python
TYPED_VALIDATION_SKELETON_KEYS: frozenset[str] = frozenset(
    {"project", "ontology_terms", "related", "source_refs", "content_preview", "file_path"}
)
```

Replace `PersistedShapeError`'s base-only wording and extend `certify_persisted` as follows. Do not replace the loop with a blanket merge.

```python
class PersistedShapeError(ValueError):
    """A write was refused because its result would not satisfy the durable typed shape."""


def certify_persisted(entity: WorkbenchEntity, text: str) -> None:
    """Refuse a rendered result that fails the durable base or merged typed shape."""
    frontmatter, _body = split_frontmatter(text)
    try:
        EntityValidator().validate_persisted_base_shape(frontmatter)

        entity_dump = entity.model_dump(mode="json")
        typed_frontmatter = dict(frontmatter)
        for key in TYPED_VALIDATION_SKELETON_KEYS:
            if key not in typed_frontmatter:
                typed_frontmatter[key] = entity_dump[key]
        type(entity).model_validate(typed_frontmatter)
    except (EntityValidationError, ValidationError) as exc:
        raise PersistedShapeError(
            f"{entity.id} would not satisfy the durable typed shape and was NOT written\n"
            f"  {exc}\n"
            f"  If this record predates writer containment, repair it directly; the workbench "
            f"will not backfill it."
        ) from exc
```

Retain the existing explanatory paragraphs about round-tripping through `split_frontmatter`, but update "base shape" references to "base and typed shape." The type call is safe because `WorkbenchEntity` is a closed two-type union.

- [ ] **Step 5: Run the focused certification tests**

```bash
uv run --frozen pytest \
  tests/test_workbench_writer_containment.py::test_typed_certification_rejects_an_invalid_merged_proposition \
  tests/test_workbench_writer_containment.py::test_evidence_line_typed_certification_fills_only_unpersisted_skeleton \
  tests/test_workbench_writer_containment.py::test_update_of_an_empty_title_record_is_REJECTED \
  tests/test_workbench_writer_containment.py::test_the_apply_create_path_is_validated_too \
  tests/test_workbench_writer_containment.py::test_the_COMPILE_path_is_validated_and_writes_nothing -q
```

Expected: 5 passed. The first test's `match="sign-less"` is the mutation certificate that removing typed validation would make red.

- [ ] **Step 6: Run the complete pre-existing writer-containment modules**

```bash
uv run --frozen pytest \
  tests/test_workbench_writer_containment.py \
  tests/test_annotation_writer_containment.py \
  tests/test_proposition_synthesize.py -q
```

Expected: all tests pass, including existing evidence-line preservation, promotion creation, and
synthesis update paths. A shared `certify_persisted` change must not remain unverified across later
commits.

- [ ] **Step 7: Lint and commit Task 1**

Run from `science/`:

```bash
uv run --frozen ruff check \
  src/science_tool/dag/entity_frontmatter.py \
  tests/test_workbench_writer_containment.py
```

Then run from the repository root:

```bash
git add \
  science/src/science_tool/dag/entity_frontmatter.py \
  science/tests/test_workbench_writer_containment.py
git commit -m "fix(entity-frontmatter): certify merged typed entities"
```

---

### Task 2: Make synthesis invalidation declarative

**Files:**
- Modify: `science/src/science_tool/dag/entity_frontmatter.py:43-86,192-219`
- Modify: `science/src/science_tool/annotation/synthesize.py:29-38`
- Test: `science/tests/test_workbench_writer_containment.py:328-360`
- Test: `science/tests/test_annotation_writer_containment.py:356-363`

**Interfaces:**
- Consumes: Task 1's unchanged `render_update(...) -> str` and typed certification.
- Produces: `PROPOSITION_REASONING_FIELDS: tuple[str, ...]`, `Ownership.change_triggers`, `Ownership.clear_on_change`, import-time overlap validation, and effective-merge stamp invalidation.

- [ ] **Step 1: Add an update-render helper and reasoning fixture to the containment tests**

Add these helpers near `_row` in `test_workbench_writer_containment.py`:

```python
_SYNTH_STAMP = "llm-synth:m:proposition-synthesize-v1"


def _reasoning_frontmatter() -> dict[str, object]:
    return {
        "id": "proposition:x",
        "kind": "proposition",
        "title": "A affects B",
        "status": "active",
        "subject": "concept:a",
        "object": "concept:b",
        "predicate": "affects",
        "polarity": "positive",
        "claim_layer": "causal_effect",
        "identification_strength": "observational",
        "reasoning_source": _SYNTH_STAMP,
        "created": "2026-07-01",
        "updated": "2026-07-01",
    }


def _rendered_frontmatter(entity, ownership) -> dict[str, object]:
    from science_model.frontmatter import split_frontmatter
    from science_tool.dag.entity_frontmatter import render_update

    text = render_update(
        entity,
        ownership=ownership,
        existing_frontmatter=_reasoning_frontmatter(),
        body="\n# Body\n",
        created="2026-07-01",
        updated="2026-07-31",
    )
    frontmatter, _body = split_frontmatter(text)
    return frontmatter
```

- [ ] **Step 2: Add the ownership invariant and effective-merge regressions**

Add these tests. The five-field parameterization pins the full stamp contract; the omitted
`claim_layer` case is the load-bearing proof that comparison happens after preservation.

```python
def test_ownership_rejects_owned_clear_overlap_at_construction() -> None:
    from science_tool.dag.entity_frontmatter import Ownership

    with pytest.raises(ValueError, match="owned and clear_on_change overlap.*reasoning_source"):
        Ownership(
            frozenset({"reasoning_source"}),
            clear_on_change=frozenset({"reasoning_source"}),
        )


@pytest.mark.parametrize(
    "change",
    [
        pytest.param({"subject": "concept:a2"}, id="subject"),
        pytest.param({"object": "concept:b2"}, id="object"),
        pytest.param({"predicate": "regulates"}, id="predicate"),
        pytest.param({"polarity": "negative"}, id="polarity"),
        pytest.param({"claim_layer": "structural_claim"}, id="claim-layer"),
    ],
)
def test_each_effective_reasoning_change_clears_synthesis_stamp(change) -> None:
    from science_model.propositions import PropositionEntity
    from science_tool.dag.entity_frontmatter import WORKBENCH_PROPOSITION

    values = {
        "id": "proposition:x",
        "title": "ignored",
        "subject": "concept:a",
        "object": "concept:b",
        "predicate": "affects",
        "polarity": "positive",
        "claim_layer": "causal_effect",
        "identification_strength": "observational",
    }
    entity = PropositionEntity(**(values | change))

    frontmatter = _rendered_frontmatter(entity, WORKBENCH_PROPOSITION)

    assert "reasoning_source" not in frontmatter


def test_preserved_omitted_reasoning_field_does_not_clear_stamp() -> None:
    from science_model.propositions import PropositionEntity
    from science_tool.dag.entity_frontmatter import WORKBENCH_PROPOSITION

    entity = PropositionEntity(
        id="proposition:x",
        title="ignored",
        subject="concept:a",
        object="concept:b",
        predicate="affects",
        polarity="positive",
        claim_layer=None,
        identification_strength="interventional",
    )

    frontmatter = _rendered_frontmatter(entity, WORKBENCH_PROPOSITION)

    assert frontmatter["claim_layer"] == "causal_effect"
    assert frontmatter["identification_strength"] == "interventional"
    assert frontmatter["reasoning_source"] == _SYNTH_STAMP


def test_empty_change_triggers_clear_nothing() -> None:
    from science_model.propositions import PropositionEntity
    from science_tool.dag.entity_frontmatter import Ownership, PROPOSITION_OWNED_KEYS

    entity = PropositionEntity(
        id="proposition:x",
        title="ignored",
        subject="concept:a2",
        object="concept:b",
        predicate="affects",
        polarity="positive",
        claim_layer="causal_effect",
    )

    frontmatter = _rendered_frontmatter(entity, Ownership(PROPOSITION_OWNED_KEYS))

    assert frontmatter["subject"] == "concept:a2"
    assert frontmatter["reasoning_source"] == _SYNTH_STAMP
```

- [ ] **Step 3: Run the new ownership tests and verify they fail**

```bash
uv run --frozen pytest \
  tests/test_workbench_writer_containment.py::test_ownership_rejects_owned_clear_overlap_at_construction \
  tests/test_workbench_writer_containment.py::test_each_effective_reasoning_change_clears_synthesis_stamp \
  tests/test_workbench_writer_containment.py::test_preserved_omitted_reasoning_field_does_not_clear_stamp \
  tests/test_workbench_writer_containment.py::test_empty_change_triggers_clear_nothing -q
```

Expected: FAIL because `Ownership` does not yet accept `clear_on_change`, and workbench ownership has no invalidation metadata.

- [ ] **Step 4: Add the shared attested-field tuple and ownership metadata**

In `entity_frontmatter.py`, define the ordered tuple before the ownership sets:

```python
PROPOSITION_REASONING_FIELDS: tuple[str, ...] = (
    "subject",
    "object",
    "predicate",
    "polarity",
    "claim_layer",
)
```

Extend the frozen dataclass. `__post_init__` runs when module-level constants are constructed, so an invalid declaration fails during import rather than at a later writer call.

```python
@dataclass(frozen=True)
class Ownership:
    """Which frontmatter keys one writer owns and which attestations it invalidates."""

    owned: frozenset[str]
    create_only: frozenset[str] = frozenset()
    change_triggers: frozenset[str] = frozenset()
    clear_on_change: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        overlap = self.owned & self.clear_on_change
        if overlap:
            raise ValueError(
                f"owned and clear_on_change overlap: {sorted(overlap)}"
            )
```

Declare only workbench propositions as invalidators:

```python
WORKBENCH_PROPOSITION = Ownership(
    PROPOSITION_OWNED_KEYS,
    CREATE_ONLY_KEYS,
    change_triggers=frozenset(PROPOSITION_REASONING_FIELDS),
    clear_on_change=frozenset({"reasoning_source"}),
)
WORKBENCH_EVIDENCE_LINE = Ownership(EVIDENCE_LINE_OWNED_KEYS, CREATE_ONLY_KEYS)
```

Keep `reasoning_source` out of `PROPOSITION_OWNED_KEYS`. Update the docstring to state that `owned` can write while `clear_on_change` can only remove an invalidated attestation.

- [ ] **Step 5: Compare triggers after the effective preserve-by-default merge**

In `render_update`, add invalidation after the owned-key loop and before date stamping:

```python
    for key in ownership.owned:
        if key in generated:
            final[key] = generated[key]
    if any(
        existing_frontmatter.get(key) != final.get(key)
        for key in ownership.change_triggers
    ):
        for key in ownership.clear_on_change:
            final.pop(key, None)
```

Do not compare `existing_frontmatter` to `generated`: an omitted `claim_layer` must compare against its preserved effective value in `final`.

- [ ] **Step 6: Make synthesis reuse the shared ordered tuple**

Change the import in `annotation/synthesize.py`:

```python
from science_tool.dag.entity_frontmatter import (
    PROPOSITION_REASONING_FIELDS as SYNTH_FIELDS,
    Ownership,
    update_entity_file,
)
```

Delete the local retyped `SYNTH_FIELDS` declaration. Keep `SYNTHESIZE_PROPOSITION` derived from the imported tuple:

```python
SYNTHESIZE_PROPOSITION = Ownership(frozenset(SYNTH_FIELDS) | {"reasoning_source"})
```

Keep the alias exactly as shown: `test_annotation_writer_containment.py` imports
`SYNTH_FIELDS` from `annotation.synthesize`, so a bare rename would break the public module
surface pinned by the existing containment test.

- [ ] **Step 7: Strengthen the existing ownership-set test**

Extend `test_workbench_ownership_carries_todays_sets_verbatim`:

```python
    assert WORKBENCH_PROPOSITION.change_triggers == frozenset(
        PROPOSITION_REASONING_FIELDS
    )
    assert WORKBENCH_PROPOSITION.clear_on_change == frozenset({"reasoning_source"})
    assert WORKBENCH_EVIDENCE_LINE.change_triggers == frozenset()
    assert WORKBENCH_EVIDENCE_LINE.clear_on_change == frozenset()
```

Import `PROPOSITION_REASONING_FIELDS` in that test, and change its comment from "ownership
semantics are unchanged" to "write allowlists are unchanged; invalidation authority is asserted
separately." Extend `test_synthesize_ownership_is_derived_from_synth_fields` in
`test_annotation_writer_containment.py`:

```python
    assert SYNTHESIZE_PROPOSITION.change_triggers == frozenset()
    assert SYNTHESIZE_PROPOSITION.clear_on_change == frozenset()
```

- [ ] **Step 8: Run ownership, renderer, and synthesis containment tests**

```bash
uv run --frozen pytest \
  tests/test_workbench_writer_containment.py \
  tests/test_annotation_writer_containment.py::test_synthesize_ownership_is_derived_from_synth_fields \
  tests/test_proposition_synthesize.py \
  tests/test_synthesize_integration.py -q
```

Expected: all pass. This explicitly retains the pre-existing synthesis containment suite; the new empty-trigger assertion is not a substitute for running it.

- [ ] **Step 9: Lint and commit Task 2**

Run from `science/`:

```bash
uv run --frozen ruff check \
  src/science_tool/dag/entity_frontmatter.py \
  src/science_tool/annotation/synthesize.py \
  tests/test_workbench_writer_containment.py \
  tests/test_annotation_writer_containment.py
```

Then run from the repository root:

```bash
git add \
  science/src/science_tool/dag/entity_frontmatter.py \
  science/src/science_tool/annotation/synthesize.py \
  science/tests/test_workbench_writer_containment.py \
  science/tests/test_annotation_writer_containment.py
git commit -m "fix(entity-frontmatter): invalidate stale reasoning stamps"
```

---

### Task 3: Canonicalize workbench polarity and prove both writer paths

**Files:**
- Modify: `science/src/science_tool/dag/workbench.py:16-27,279-302`
- Test: `science/tests/test_workbench_writer_containment.py:38-75,170-198`
- Test: `science/tests/test_workbench_apply.py:195-208`

**Interfaces:**
- Consumes: Task 2's `WORKBENCH_PROPOSITION` invalidation metadata and Task 1's typed certification.
- Produces: `_proposition_for_row(row: WorkbenchRow) -> PropositionEntity` whose sign-less predicates always carry `Polarity.NOT_APPLICABLE` when the row omits polarity.

- [ ] **Step 1: Add lift-level polarity tests**

Add beside the existing proposition-lift tests:

```python
def test_signless_predicate_canonicalizes_omitted_polarity() -> None:
    from science_model.reasoning import Polarity

    prop = _proposition_for_row(_row(predicate="binds", polarity=None))

    assert prop.polarity is Polarity.NOT_APPLICABLE


def test_sign_meaningful_predicate_still_requires_polarity() -> None:
    with pytest.raises(ValidationError, match="polarity must be"):
        _proposition_for_row(_row(polarity=None))
```

- [ ] **Step 2: Add the compile-path stale-polarity/stamp regression**

Add this test to `test_workbench_writer_containment.py`. It starts with a base-valid destination and asserts the written file reloads, so neither base rejection nor string-only assertions can make it false-green.

```python
def test_compile_canonicalizes_stale_polarity_and_invalidates_stamp(tmp_path) -> None:
    import yaml
    from science_model.propositions import PropositionEntity
    from science_tool.dag import workbench as wb

    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    dest = tmp_path / "entities/propositions/x.md"
    dest.parent.mkdir(parents=True)
    dest.write_text(
        "---\n"
        "id: proposition:x\n"
        "kind: proposition\n"
        "title: A affects B\n"
        "status: active\n"
        "subject: concept:a\n"
        "object: concept:b\n"
        "predicate: affects\n"
        "polarity: positive\n"
        "claim_layer: causal_effect\n"
        f"reasoning_source: {_SYNTH_STAMP}\n"
        "created: '2026-07-01'\n"
        "updated: '2026-07-01'\n"
        "---\n\n# Curated body\n",
        encoding="utf-8",
    )
    workbench = wb.WorkbenchFile.model_validate(
        {
            "rows": [
                {
                    "id": "proposition:x",
                    "subject": "concept:a",
                    "predicate": "binds",
                    "object": "concept:b",
                    "patch": "p",
                    "claim_layer": "structural_claim",
                }
            ]
        }
    )

    wb.compile_workbench(workbench, project_root=tmp_path, as_of=date(2026, 7, 31))

    frontmatter = yaml.safe_load(dest.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert frontmatter["predicate"] == "binds"
    assert frontmatter["polarity"] == "not_applicable"
    assert "reasoning_source" not in frontmatter
    PropositionEntity.model_validate(frontmatter)
    assert "# Curated body" in dest.read_text(encoding="utf-8")
```

- [ ] **Step 3: Add the idempotent compile round-trip regression**

Add this test to `test_workbench_writer_containment.py`. Use the same `as_of` value for both
compiles so byte identity measures reasoning preservation rather than intended timestamp churn.
`compile_workbench` rewrites unconditionally; the assertion pins that a no-change full round trip
neither clears the synthesis stamp nor changes the rendered content.

```python
def test_idempotent_compile_preserves_reasoning_stamp_and_bytes(tmp_path) -> None:
    import yaml

    from science_tool.dag import workbench as wb
    from science_tool.dag.entity_frontmatter import render_from_frontmatter

    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    workbench = wb.WorkbenchFile.model_validate(
        {
            "patch": "p",
            "rows": [
                {
                    "id": "proposition:x",
                    "subject": "concept:a",
                    "predicate": "affects",
                    "object": "concept:b",
                    "patch": "p",
                    "polarity": "positive",
                    "claim_layer": "causal_effect",
                }
            ],
        }
    )
    as_of = date(2026, 7, 31)
    wb.compile_workbench(workbench, project_root=tmp_path, as_of=as_of)

    dest = tmp_path / "entities/propositions/x.md"
    frontmatter_text, body = dest.read_text(encoding="utf-8").split("---\n", 2)[1:]
    frontmatter = yaml.safe_load(frontmatter_text)
    frontmatter["reasoning_source"] = _SYNTH_STAMP
    dest.write_text(render_from_frontmatter(frontmatter, body), encoding="utf-8")
    before = dest.read_bytes()

    wb.compile_workbench(workbench, project_root=tmp_path, as_of=as_of)

    after = dest.read_bytes()
    assert after == before
    assert yaml.safe_load(after.decode().split("---\n", 2)[1])["reasoning_source"] == _SYNTH_STAMP
```

- [ ] **Step 4: Add the apply-path stale-polarity/stamp regression**

Add to `test_workbench_apply.py`:

```python
def test_apply_workbench_canonicalizes_polarity_and_invalidates_stamp(tmp_path: Path) -> None:
    from science_model.propositions import PropositionEntity

    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path, inline_evidence=False)
    apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    prop_path = tmp_path / "entities/propositions/a-affects-b.md"
    frontmatter, body = parse_markdown_entity_file_preserving_body(prop_path)
    frontmatter["reasoning_source"] = "llm-synth:m:proposition-synthesize-v1"
    prop_path.write_text(
        "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n" + body,
        encoding="utf-8",
    )
    changed = workbench_path.read_text(encoding="utf-8")
    changed = changed.replace("predicate: affects", "predicate: binds")
    changed = changed.replace("    polarity: positive\n", "")
    workbench_path.write_text(changed, encoding="utf-8")

    result = apply_workbench(
        tmp_path,
        input_path=workbench_path,
        as_of=date(2026, 7, 10),
    )

    assert result.status == "applied"
    persisted = _frontmatter(prop_path)
    assert persisted["predicate"] == "binds"
    assert persisted["polarity"] == "not_applicable"
    assert "reasoning_source" not in persisted
    PropositionEntity.model_validate(persisted)
```

- [ ] **Step 5: Pin idempotent apply behavior with an existing stamp**

In `test_apply_workbench_rerun_is_noop_without_timestamp_churn`, insert a synthesis stamp after the first apply, then take the comparison snapshot:

```python
    frontmatter, body = parse_markdown_entity_file_preserving_body(prop_path)
    frontmatter["reasoning_source"] = "llm-synth:m:proposition-synthesize-v1"
    prop_path.write_text(
        "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n" + body,
        encoding="utf-8",
    )
    first_frontmatter = _frontmatter(prop_path)
```

Keep the existing assertions and add:

```python
    assert first_frontmatter["reasoning_source"] == "llm-synth:m:proposition-synthesize-v1"
```

This test exercises `workbench_apply`'s unchanged-timestamp probe, not merely `render_update` in isolation.

- [ ] **Step 6: Run the new tests and verify canonicalization is red**

```bash
uv run --frozen pytest \
  tests/test_workbench_writer_containment.py::test_signless_predicate_canonicalizes_omitted_polarity \
  tests/test_workbench_writer_containment.py::test_sign_meaningful_predicate_still_requires_polarity \
  tests/test_workbench_writer_containment.py::test_compile_canonicalizes_stale_polarity_and_invalidates_stamp \
  tests/test_workbench_writer_containment.py::test_idempotent_compile_preserves_reasoning_stamp_and_bytes \
  tests/test_workbench_apply.py::test_apply_workbench_canonicalizes_polarity_and_invalidates_stamp \
  tests/test_workbench_apply.py::test_apply_workbench_rerun_is_noop_without_timestamp_churn -q
```

Expected: the sign-less lift assertion fails because polarity is `None`; compile/apply either raise the Task 1 typed `PersistedShapeError` or fail the `not_applicable` assertion. The sign-meaningful rejection and idempotent stamp tests may already pass.

- [ ] **Step 7: Canonicalize polarity once at workbench row lift**

Add `SIGN_MEANINGFUL_PREDICATES` to `workbench.py`'s existing `science_model.reasoning` import. Compute the typed predicate and polarity once before constructing the entity:

```python
    entity_id = row.id or f"proposition:{_slug_for_triple(row.subject, row.predicate, row.object)}"
    predicate = Predicate(row.predicate)
    if row.polarity is not None:
        polarity = Polarity(row.polarity)
    elif predicate in SIGN_MEANINGFUL_PREDICATES:
        polarity = None
    else:
        polarity = Polarity.NOT_APPLICABLE
    return PropositionEntity(
        id=entity_id,
        title=_proposition_title(row),
        subject=row.subject,
        object=row.object,
        predicate=predicate,
        polarity=polarity,
```

Keep the remaining legacy, claim-layer, and identification fields exactly as they are. Do not move canonicalization into `render_update`: create and update must share the same lifted entity.

- [ ] **Step 8: Run both complete public-path modules and synthesis regressions**

```bash
uv run --frozen pytest \
  tests/test_workbench_writer_containment.py \
  tests/test_workbench_apply.py \
  tests/test_workbench_compile.py \
  tests/test_annotation_writer_containment.py \
  tests/test_proposition_synthesize.py \
  tests/test_synthesize_integration.py -q
```

Expected: all pass. This is the required existing containment-suite gate, including evidence-line updates and synthesis preservation.

- [ ] **Step 9: Run lint and types**

```bash
uv run --frozen ruff check
uv run --frozen pyright
```

Expected: Ruff clean; Pyright reports 0 errors.

- [ ] **Step 10: Commit Task 3**

Run from the repository root:

```bash
git add \
  science/src/science_tool/dag/workbench.py \
  science/tests/test_workbench_writer_containment.py \
  science/tests/test_workbench_apply.py
git commit -m "fix(workbench): invalidate changed reasoning provenance"
```

---

### Task 4: Full validation

**Files:**
- Verify only; no planned source changes.

**Interfaces:**
- Consumes: Tasks 1-3 and their three clean commits.
- Produces: evidence that the complete nested packages remain green and the repository contains no unintended changes.

- [ ] **Step 1: Run the science-model suite**

From `science/model/`:

```bash
uv run --frozen pytest
```

Expected: all default model tests pass.

- [ ] **Step 2: Run the complete default Science suite with an explicit long timeout at execution time**

From `science/`:

```bash
uv run --frozen pytest
```

Expected: all default tests pass. The top-level executor must give this command at least 15 minutes; the Dropbox-backed checkout routinely exceeds 120 seconds.

- [ ] **Step 3: Re-run lint and types after the full suites**

From `science/`:

```bash
uv run --frozen ruff check
uv run --frozen pyright
```

Expected: Ruff clean; Pyright reports 0 errors.

- [ ] **Step 4: Verify history and worktree scope**

From the implementation worktree root:

```bash
git status --short
git log --oneline -5
git diff HEAD~3 --check
git diff HEAD~3 -- \
  science/src/science_tool/dag/entity_frontmatter.py \
  science/src/science_tool/dag/workbench.py \
  science/src/science_tool/annotation/synthesize.py \
  science/tests/test_workbench_writer_containment.py \
  science/tests/test_workbench_apply.py \
  science/tests/test_annotation_writer_containment.py
```

Expected: clean status; three implementation commits after the plan commit; no whitespace errors; no corpus files or unrelated sources changed.

After this gate, use `superpowers:finishing-a-development-branch` to present the merge, pull
request, and keep-as-is choices. Integration is not a fifth implementation task and must not happen
automatically.

---

## Spec Coverage Map

| Design requirement | Plan coverage |
|---|---|
| Preserve missing optional values | Task 2 Steps 2 and 5 (`claim_layer` omitted, effective merge compared) |
| Canonicalize sign-less omitted polarity | Task 3 Steps 1, 2, 4, and 7 |
| Keep sign-meaningful polarity requirement | Task 3 Steps 1 and 7 |
| Clear stamp on any of five effective reasoning changes | Task 2 Steps 2, 4, and 5 |
| Preserve stamp for idempotent/non-reasoning updates | Task 2 Step 2; Task 3 Steps 3 and 5 |
| Disjoint deletion and write authority | Task 2 Steps 2 and 4; import-time module constants exercise it immediately |
| Shared attested-field identity without import cycle | Task 2 Steps 4 and 6 |
| Compare after preserve-by-default merge | Task 2 Steps 2 and 5 |
| Conservative absent-to-`not_applicable` comparison | Task 3 compile/apply tests observe a real persisted change and stamp removal |
| Base-first then typed certification | Task 1 Steps 1 and 4; fixture includes the full base shape and matches `sign-less` |
| Explicit absent-only six-key skeleton | Task 1 Steps 2 and 4 |
| Future ownership guard despite no live path | Task 1 Step 1's synthetic ownership |
| Evidence-line compatibility | Task 1 Steps 2, 5, and 6; Task 3 Step 8 |
| Existing synthesis containment stays green | Task 1 Step 6; Task 2 Step 8; Task 3 Step 8 |
| No corpus repair or unrelated migration | Global Constraints; Task 4 Step 4 |

## Notes for the Implementer

- `Ownership` is frozen and all production instances are module constants. The overlap invariant must live in `__post_init__`; a call-site check would defer a declaration error and miss import-time failure.
- Test 1.1 is intentionally not a public workbench flow. Once Task 3 lands, every live proposition writer owns all interlocked fields, so only a synthetic ownership set can prove typed merge certification independently of polarity canonicalization.
- Do not weaken Test 1.1 to `pytest.raises(PersistedShapeError)` without `match="sign-less"`; that recreates the reviewed false-green fixture hazard.
- Do not remove the existing containment modules from the validation commands because the new empty-trigger test passes. The old suites prove body/frontmatter preservation and synthesis behavior that this slice must not disturb.
- No external Science project command is required. This implementation changes writer behavior but writes no corpus file; the measured corpus compatibility is represented by the evidence-line skeleton regression.
