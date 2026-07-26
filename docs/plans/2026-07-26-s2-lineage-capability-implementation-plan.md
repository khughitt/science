# S2 Lineage Capability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Declare per kind whether it can be superseded, and make the status vocabulary, the relation endpoint list, and the auto-stamping policy all derive from that one declaration.

**Architecture:** `EntityKind` gains a `supersedable: bool` field, declared explicitly on all 53 shipped kinds. Three surfaces that currently infer lineage capability from each other are gated against it by exact equality in both directions. Fifteen kinds are re-ruled so both existing gaps close, and `workflow-run`'s dead top-level `supersedes:` field is retired.

**Tech Stack:** Python 3, Pydantic v2, pytest, uv.

Design: [`meta/doc/plans/2026-07-26-s2-lineage-capability-design.md`](../../meta/doc/plans/2026-07-26-s2-lineage-capability-design.md). Read it before Task 1; every ruling in this plan traces to it.

## Global Constraints

- **Working directories.** CLI/tool work runs from `science/`; model work runs from `science/model/`. There is **no root `pyproject.toml`** — running `uv run` from the repo root is the most common orientation mistake here.
- **Test commands.** `cd science && uv run --frozen pytest` and `cd science/model && uv run --frozen pytest`. Never run two suites concurrently in the same worktree — they race on shared test-output paths.
- **The full `science/` suite takes ~2-3 min**, longer than the default 120s command timeout. Pass an explicit long timeout, or run a scoped selection.
- **Lint/types**, from `science/`: `uv run ruff check` and `uv run pyright`. Pyright is configured once by `pyrightconfig.json` at the repo root and governs all three source trees.
- **Conventional commits.** No AI-attribution trailer or footer on commits, PRs, or comments.
- **Composition over inheritance; explicit over defensive; fail early instead of silent fallbacks. No "legacy"/"compatibility" layers. No `Unified` prefix.**
- **Use `~/d/` or relative paths in docs and code**, never `/home/keith/` or `/mnt/ssd/Dropbox/`.
- **The 18 supersedable kinds, exactly:** `decision`, `discussion`, `finding`, `hypothesis`, `inquiry`, `interpretation`, `mechanism`, `method`, `plan`, `proposition`, `report`, `spec`, `story`, `synthesis`, `theme`, `topic`, `validation-report`, `workflow-step`. Every other kind — 32 in core, 3 in local — is `supersedable=False`.
- **Do not add the ten newly-supersedable kinds to `_CONCLUSION_KINDS`.** That list is shared with the `amends` relation; widening it would silently grant cross-kind amendment admissibility this design did not rule on. They are **self-pairs**.
- **A stale exemption must fail as loudly as a new gap.** Every gate assertion in this plan is exact equality in both directions, with a failure message naming each side.

---

## File Structure

| File | Responsibility in this change |
|---|---|
| `science/model/src/science_model/profiles/schema.py` | declares the `supersedable` field on `EntityKind` |
| `science/model/src/science_model/profiles/core.py` | the 50 core declarations, the 4 status rulings, the `supersedes` endpoint rulings |
| `science/model/src/science_model/profiles/local.py` | the 3 local-profile declarations |
| `science/model/tests/test_supersedable_gate.py` | the gate — all five properties; rewritten from a subset ratchet to exact equality |
| `science/src/science_tool/kind_descriptors.py` | `DECLARED_SUPERSEDABLE`, the tool-side lookup mirroring `DECLARED_STATUSES` |
| `science/src/science_tool/consolidation.py` | the auto-stamping policy derives from the declaration |
| `science/src/science_tool/qa_audit/runs.py`, `verdicts.py` | drop the dead `supersedes` field; correct two docstrings |
| `science/src/science_tool/validate/checks/materialization.py` | remove the one-entry legit-reader exemption |
| `templates/workflow-run.md`, `docs/process/pipeline-audit-and-refactor.md` | user-facing guidance for the retired field |

---

### Task 1: Declare `supersedable` on every shipped kind

**Files:**
- Modify: `science/model/src/science_model/profiles/schema.py:23-48` (the `EntityKind` model)
- Modify: `science/model/src/science_model/profiles/core.py` (all 50 `EntityKind(...)` blocks)
- Modify: `science/model/src/science_model/profiles/local.py` (all 3 `EntityKind(...)` blocks)
- Test: `science/model/tests/test_supersedable_gate.py`

**Interfaces:**
- Produces: `EntityKind.supersedable: bool` (default `False`). Later tasks read it off `CORE_PROFILE.entity_kinds` and off `LOCAL_PROFILE.entity_kinds`.

This task only adds data. No surface consumes it yet, so both suites must stay green.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_supersedable_gate.py`, replacing the existing file wholesale. For this task write only the module docstring and the first property; Tasks 2-4 append theirs.

```python
"""Lineage capability: ONE declaration, and the surfaces that must agree with it.

`EntityKind.supersedable` answers "can an entity of this kind be replaced as canonical by a newer
one?" It is DECLARED per kind, never inferred. The status vocabulary, the `sci:supersedes` endpoint
list, and the auto-stamping policy are all gated against it by EXACT equality in both directions --
so a stale exemption fails as loudly as a new gap.

This file replaced a SUBSET ratchet over `_KNOWN_HALF_WIRED`, a frozen allowlist of twelve
half-wired kinds. That ratchet was correct while the debt existed; S2 rules all fifteen affected
kinds, so there is no debt left to freeze and the assertions became equalities. Restoring a subset
assertion here would re-open the hole by construction.
"""

from __future__ import annotations

import pytest

from science_model.profiles import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
from science_model.profiles.schema import EntityKind

SHIPPED_KINDS: tuple[EntityKind, ...] = (*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds)

# The authored ruling. Kept here, beside the gate, so a reader sees the population the gate is
# about without opening the profile -- and so a silent edit to the profile fails HERE.
SUPERSEDABLE_KINDS: frozenset[str] = frozenset(
    {
        "decision", "discussion", "finding", "hypothesis", "inquiry", "interpretation",
        "mechanism", "method", "plan", "proposition", "report", "spec", "story",
        "synthesis", "theme", "topic", "validation-report", "workflow-step",
    }
)


@pytest.mark.parametrize("kind", SHIPPED_KINDS, ids=lambda k: k.name)
def test_every_shipped_kind_DECLARES_supersedable(kind: EntityKind) -> None:
    # `model_fields_set` -- not the value. The field defaults to False so a project-authored
    # manifest kind stays inert, which means a shipped kind that simply FORGOT to declare would be
    # indistinguishable from one ruled non-supersedable. Presence is the only thing that separates
    # them, and kind 51 must not be able to arrive silently.
    assert "supersedable" in kind.model_fields_set, (
        f"{kind.name} does not declare `supersedable`; every shipped kind must rule explicitly"
    )


def test_the_declared_population_is_exactly_the_ruling() -> None:
    # Both directions. Adding a kind to the profile without ruling it, or leaving this manifest
    # naming a kind the profile no longer declares supersedable, both fail here.
    declared = {kind.name for kind in SHIPPED_KINDS if kind.supersedable}
    assert declared == SUPERSEDABLE_KINDS, (
        f"declared but not in the ruling: {sorted(declared - SUPERSEDABLE_KINDS)}; "
        f"ruled but not declared: {sorted(SUPERSEDABLE_KINDS - declared)}"
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_supersedable_gate.py -q`
Expected: collection error — `EntityKind` has no field `supersedable`.

- [ ] **Step 3: Add the field**

In `science/model/src/science_model/profiles/schema.py`, inside `class EntityKind`, after the `statuses` line:

```python
    statuses: list[str] | None = None
    # Lineage capability (S2): can an entity of this kind be replaced as canonical by a newer one?
    # DECLARED per kind -- never inferred from `statuses`, which is how the two drifted. Defaults
    # False because project-authored manifest kinds validate through this model and must not be
    # forced to declare; a test asserts every SHIPPED kind sets it explicitly.
    supersedable: bool = False
```

- [ ] **Step 4: Declare it on all 53 shipped kinds**

Add `supersedable=True,` to the `EntityKind(...)` block of each of the 18 kinds named in Global Constraints, and `supersedable=False,` to every other block in `core.py` (32) and `local.py` (3). Place it immediately after `statuses=` where present, otherwise as the last argument.

- [ ] **Step 5: Verify the declaration is complete and correct**

Run: `cd science/model && uv run --frozen pytest tests/test_supersedable_gate.py -q`
Expected: PASS, 55 tests (53 parametrized + the population test).

Then confirm the counts:

```bash
cd science && uv run --frozen python -c "
from science_model.profiles import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
k = [*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds]
print(len(k), sum(x.supersedable for x in k))"
```
Expected: `53 18`

- [ ] **Step 6: Prove the gate can fail (mutation proof 1)**

Temporarily delete `supersedable=False,` from the `question` block in `core.py`. Re-run the test file. Expected: `test_every_shipped_kind_DECLARES_supersedable[question]` FAILS naming `question`. **Revert the mutation** and confirm the file is green again. Do not commit the mutation.

- [ ] **Step 7: Run both suites**

Run: `cd science/model && uv run --frozen pytest -q` then `cd science && uv run --frozen pytest -q` (allow ~3 min).
Expected: both green. Nothing consumes the new field yet.

- [ ] **Step 8: Commit**

```bash
git add science/model/src/science_model/profiles/ science/model/tests/test_supersedable_gate.py
git commit -m "feat(profile): declare lineage capability per kind"
```

---

### Task 2: Rule the status vocabularies

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py` (the `observation`, `pre-registration`, `story`, `validation-report` blocks)
- Modify: `science/tests/test_kind_map_equivalence.py` (`FROZEN_STATUS_VALUES`, `FROZEN_DEFAULT_STATUS`)
- Test: `science/model/tests/test_supersedable_gate.py`

**Interfaces:**
- Consumes: `EntityKind.supersedable` from Task 1.
- Produces: `"superseded" in kind.statuses` ⟺ `kind.supersedable`, for all 53 shipped kinds.

**Measured expected failures** (from running this change): `science/tests/test_kind_map_equivalence.py::test_status_values_equal_prior_literal` and `::test_default_status_equals_prior_literal`. No others.

- [ ] **Step 1: Write the failing test**

Append to `science/model/tests/test_supersedable_gate.py`:

```python
def test_the_status_vocabulary_agrees_with_the_declaration() -> None:
    # The vocabulary is a HAND-AUTHORED declaration, not generated from `supersedable` -- which is
    # what makes this comparison non-vacuous. If `statuses` were derived, this test would be the
    # identity function.
    declares_status = {k.name for k in SHIPPED_KINDS if "superseded" in (k.statuses or ())}
    supersedable = {k.name for k in SHIPPED_KINDS if k.supersedable}
    assert declares_status == supersedable, (
        f"declares `superseded` but is not supersedable: {sorted(declares_status - supersedable)}; "
        f"supersedable but cannot reach the state: {sorted(supersedable - declares_status)}"
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_supersedable_gate.py::test_the_status_vocabulary_agrees_with_the_declaration -q`
Expected: FAIL. Both sides are non-empty — `observation`/`pre-registration` declare the status without being supersedable, and `story`/`validation-report` are supersedable without declaring it.

- [ ] **Step 3: Apply the four rulings**

In `science/model/src/science_model/profiles/core.py`:

`observation` — drop `"superseded"`:
```python
            statuses=["active", "retired", "archived"],
```

`pre-registration` — drop `"superseded"`. The remaining vocabulary is the commitment axis the doctrine names, and `amended` already carries revision-without-replacement:
```python
            statuses=["active", "committed", "amended", "retired"],
```

`story` — add `"superseded"`:
```python
            statuses=["draft", "developing", "mature", "superseded"],
```

`validation-report` — it declares no vocabulary today; give it `report`'s, plus a default so a closed vocabulary is not left without one. Add both lines to its `EntityKind(...)` block:
```python
            default_status="active",
            statuses=["draft", "active", "complete", "superseded", "retired", "archived"],
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science/model && uv run --frozen pytest tests/test_supersedable_gate.py -q`
Expected: PASS.

- [ ] **Step 5: Re-freeze the two status oracles**

This step edits a frozen snapshot, which is normally forbidden. It is permitted **only** because each edit traces to a written ruling in the design's "The rulings" section — cite it in the commit message. An edit here that matches a change nobody ruled on is tuning the instrument to silence the check.

In `science/tests/test_kind_map_equivalence.py`, `FROZEN_STATUS_VALUES`:

```python
    "observation": frozenset({"active", "retired", "archived"}),
    "pre-registration": frozenset({"active", "committed", "amended", "retired"}),
    "story": frozenset({"draft", "developing", "mature", "superseded"}),
    "validation-report": frozenset(
        {"draft", "active", "complete", "superseded", "retired", "archived"}
    ),
```

`observation`, `pre-registration` and `story` are existing entries to edit; `validation-report` is a **new** entry (it is absent today, having declared no vocabulary).

In `FROZEN_DEFAULT_STATUS`, add:
```python
    "validation-report": "active",
```

- [ ] **Step 6: Run the tool suite**

Run: `cd science && uv run --frozen pytest -q` (allow ~3 min).
Expected: green. The two `test_kind_map_equivalence` failures are resolved by Step 5 and nothing else broke — this was measured, not predicted.

Note the pre-existing `test_every_supersedable_kind_can_author_the_CANONICAL_edge` still passes at this point: its `broken` set shrinks to ten kinds, which is still a subset of the twelve-kind allowlist. Task 3 removes it.

- [ ] **Step 7: Prove the gate can fail (mutation proof 2)**

Temporarily set `supersedable=False` on the `topic` block while leaving `"superseded"` in its `statuses`. Re-run `tests/test_supersedable_gate.py`. Expected: `test_the_status_vocabulary_agrees_with_the_declaration` FAILS, naming `topic` on the "declares but is not supersedable" side. **Revert.**

- [ ] **Step 8: Commit**

```bash
git add science/model/src/science_model/profiles/core.py science/model/tests/test_supersedable_gate.py science/tests/test_kind_map_equivalence.py
git commit -m "feat(profile): rule the status vocabularies against lineage capability

observation and pre-registration lose \`superseded\`; story and validation-report
gain it. Each ruling is written in the S2 design's rulings section; the two frozen
oracles are re-frozen to match those rulings, not to silence the check."
```

---

### Task 3: Rule the `sci:supersedes` endpoints

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py:12-25` (add the self-superseding lists) and the `RelationKind(name="supersedes", ...)` block at ~line 735
- Modify: `science/model/tests/test_profile_manifests.py:99-103`
- Modify: `science/tests/test_graph_materialize.py:1109`
- Modify: `science/tests/validate/test_checks_materialization.py:135-155`
- Delete: `science/tests/test_consolidation_candidates.py::test_lineage_reports_kind_lacking_superseded_vocab`
- Modify: `science/tests/test_consolidation_mark_superseded.py:298`
- Test: `science/model/tests/test_supersedable_gate.py`

**Interfaces:**
- Consumes: `EntityKind.supersedable` from Task 1.
- Produces: `_SELF_SUPERSEDING_KINDS: list[str]` and `_SELF_SUPERSEDING_PAIRS: list[RelationEndpointPair]` in `core.py`; the `supersedes` relation admits exactly the 18 supersedable kinds as targets.

**Measured expected failures** (from running this change): `test_profile_manifests.py::test_core_profile_declares_amends_and_non_cartesian_supersedes`, `test_graph_materialize.py::test_materialize_graph_preserves_workflow_run_supersedes`, `validate/test_checks_materialization.py::test_inadmissible_kind_is_not_told_to_author_the_relation`, `test_consolidation_candidates.py::test_lineage_reports_kind_lacking_superseded_vocab`, `test_consolidation_mark_superseded.py::test_member_whose_kind_lacks_superseded_vocab_is_skipped_not_crashed`.

- [ ] **Step 1: Write the failing tests**

Append to `science/model/tests/test_supersedable_gate.py`:

```python
from science_model.profiles.schema import RelationKind
from science_model.relations import relation_allows_kinds


def _supersedes() -> RelationKind:
    return next(r for r in CORE_PROFILE.relation_kinds if r.name == "supersedes")


def test_the_supersedes_TARGETS_agree_with_the_declaration() -> None:
    # The OBJECT is the thing superseded, so it must be able to reach the state. The SUBJECT is the
    # replacement and is deliberately NOT gated -- a non-supersedable kind replacing a supersedable
    # one is legitimate.
    targets = {pair.target_kind for pair in _supersedes().allowed_kind_pairs}
    supersedable = {k.name for k in SHIPPED_KINDS if k.supersedable}
    assert targets == supersedable, (
        f"admissible target but not supersedable: {sorted(targets - supersedable)}; "
        f"supersedable but never an admissible target: {sorted(supersedable - targets)}"
    )


@pytest.mark.parametrize("kind", sorted(SUPERSEDABLE_KINDS))
def test_every_supersedable_kind_can_author_the_CANONICAL_edge(kind: str) -> None:
    # Asked through the AUTHORITATIVE helper. `source_kinds & target_kinds` is NOT the admission
    # rule when `allowed_kind_pairs` is present -- the pairs are a non-Cartesian allow-list, and a
    # check on the flat lists would keep agreeing right up until it didn't.
    assert relation_allows_kinds(_supersedes(), kind, kind)


@pytest.mark.parametrize(
    "relation", [r for r in CORE_PROFILE.relation_kinds if r.allowed_kind_pairs], ids=lambda r: r.name
)
def test_the_flat_endpoint_lists_agree_with_the_pairs(relation: RelationKind) -> None:
    # `allowed_kind_pairs` decides admission, but `source_kinds`/`target_kinds` remain the fallback
    # rule for relations declaring no pairs -- and agents read them. Editing only the pairs leaves
    # the flat projections contradicting the surface that decides.
    sources = {pair.source_kind for pair in relation.allowed_kind_pairs}
    targets = {pair.target_kind for pair in relation.allowed_kind_pairs}
    assert set(relation.source_kinds or ()) == sources, (
        f"{relation.name} source_kinds disagrees with its pairs: "
        f"listed only: {sorted(set(relation.source_kinds or ()) - sources)}; "
        f"paired only: {sorted(sources - set(relation.source_kinds or ()))}"
    )
    assert set(relation.target_kinds or ()) == targets, (
        f"{relation.name} target_kinds disagrees with its pairs: "
        f"listed only: {sorted(set(relation.target_kinds or ()) - targets)}; "
        f"paired only: {sorted(targets - set(relation.target_kinds or ()))}"
    )
```

Then **delete** `_KNOWN_HALF_WIRED`, the old `test_every_supersedable_kind_can_author_the_CANONICAL_edge` subset assertion, `test_hypothesis_is_a_supersedes_ENDPOINT` and `test_spec_is_a_supersedes_ENDPOINT` from the file — the parametrized version above covers both, and by derivation rather than by naming two kinds. Keep `test_supersedes_description_names_spec_replacement`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science/model && uv run --frozen pytest tests/test_supersedable_gate.py -q`
Expected: `test_the_supersedes_TARGETS_agree_with_the_declaration` FAILS listing `workflow-run` as an admissible target that is not supersedable and the ten kinds that are supersedable but never targets; ten of the parametrized `can_author` cases FAIL.

- [ ] **Step 3: Apply the endpoint rulings**

In `science/model/src/science_model/profiles/core.py`, after `_CONCLUSION_KIND_PAIRS`:

```python
# Kinds that supersede only themselves. Deliberately SEPARATE from `_CONCLUSION_KINDS`, which is
# shared with `amends`: adding these there would silently grant ten kinds cross-kind AMENDMENT
# admissibility that no ruling covers.
_SELF_SUPERSEDING_KINDS = [
    "hypothesis",
    "spec",
    "decision",
    "inquiry",
    "mechanism",
    "method",
    "plan",
    "proposition",
    "synthesis",
    "theme",
    "topic",
    "workflow-step",
]

_SELF_SUPERSEDING_PAIRS = [
    RelationEndpointPair(source_kind=kind, target_kind=kind) for kind in _SELF_SUPERSEDING_KINDS
]
```

Replace the `supersedes` relation's endpoint declaration and description. `workflow-run` is removed entirely — a re-run is a new record, not a replacement of an execution that genuinely happened:

```python
            source_kinds=[*_SELF_SUPERSEDING_KINDS, *_CONCLUSION_KINDS],
            target_kinds=[*_SELF_SUPERSEDING_KINDS, *_CONCLUSION_KINDS],
            allowed_kind_pairs=[
                *_SELF_SUPERSEDING_PAIRS,
                *_CONCLUSION_KIND_PAIRS,
            ],
            layer="layer/core",
            description=(
                "A newer entity replaces an older entity as canonical. Valid for "
                "self-replacement of hypothesis, spec, decision, inquiry, mechanism, "
                "method, plan, proposition, synthesis, theme, topic and workflow-step, "
                "and for conclusion-level replacement among interpretation, finding, "
                "discussion, report, validation-report and story."
            ),
```

Delete the comment block above `source_kinds` that names `workflow-run` as fully wired and enumerates the twelve half-wired kinds as frozen debt. Replace it with:

```python
            # Endpoints are gated against `EntityKind.supersedable` (S2): every target kind must
            # be able to reach the `superseded` state, and every supersedable kind must be some
            # pair's target. `test_supersedable_gate.py` asserts both directions exactly, so there
            # is no half-wired debt left to freeze.
```

- [ ] **Step 4: Run the model suite**

Run: `cd science/model && uv run --frozen pytest -q`
Expected: `tests/test_supersedable_gate.py` green; `tests/test_profile_manifests.py::test_core_profile_declares_amends_and_non_cartesian_supersedes` FAILS at its `workflow-run` assertion.

- [ ] **Step 5: Fix the profile-manifest test**

In `science/model/tests/test_profile_manifests.py`, replace the `workflow-run` admission assertion with its inverse and add coverage for the new self-pairs:

```python
    assert not relation_allows_kinds(supersedes, "workflow-run", "workflow-run")
    assert relation_allows_kinds(supersedes, "interpretation", "finding")
    assert relation_allows_kinds(supersedes, "story", "validation-report")
    assert not relation_allows_kinds(supersedes, "interpretation", "workflow-run")
    assert not relation_allows_kinds(supersedes, "workflow-run", "interpretation")
    # Self-superseding kinds are self-only: `topic` replaces a topic, never a plan.
    assert relation_allows_kinds(supersedes, "topic", "topic")
    assert not relation_allows_kinds(supersedes, "topic", "plan")
```

Run: `cd science/model && uv run --frozen pytest -q`
Expected: green.

- [ ] **Step 6: Invert the materialization test**

In `science/tests/test_graph_materialize.py`, `test_materialize_graph_preserves_workflow_run_supersedes` asserts the edge materializes. Rename it and assert the rejection instead. Keep the same two-entity fixture; wrap the materialization call:

```python
def test_materialize_graph_REJECTS_workflow_run_supersedes(tmp_path: Path) -> None:
    # S2: a re-run is a new record, not a replacement. `workflow-run` is no longer a `sci:supersedes`
    # endpoint, so authoring the edge must be refused rather than silently materialized.
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(project / "entities" / "runs" / "old.md", "workflow-run:old-run", "workflow-run", "Old run")
    _write_minimal_entity(
        project / "entities" / "runs" / "new.md",
        "workflow-run:new-run",
        "workflow-run",
        "New run",
        [
            "relations:",
            '  - predicate: "sci:supersedes"',
            '    target: "workflow-run:old-run"',
        ],
    )

    with pytest.raises(RelationRejection, match="invalid authored relation endpoint"):
        materialize_graph(project)
```

Add `from science_tool.graph.materialize import RelationRejection` to the file's imports — no test currently imports it.

**Match on the message, not the code.** `RelationRejection("illegal-kind-pair", "invalid authored relation endpoint: …")` renders only its *second* argument in `str(exc)`, so `match="illegal-kind-pair"` fails even though the rejection is correct. This was confirmed by running the change: the propagated error is
`science_tool.graph.materialize.RelationRejection: invalid authored relation endpoint: workflow-run:new-run sci:supersedes (supersedes) workflow-run:old-run in entities/runs/new.md (got workflow-run -> workflow-run)`.

- [ ] **Step 7: Retarget the remediation test**

In `science/tests/validate/test_checks_materialization.py`, `test_inadmissible_kind_is_not_told_to_author_the_relation` uses `plan`, which S2 makes an admissible `sci:supersedes` source — the test would silently stop testing what it names. Retarget it to `question`, which stays non-supersedable:

```python
def test_inadmissible_kind_is_not_told_to_author_the_relation(tmp_path: Path) -> None:
    """`question` cannot be a `sci:supersedes` source, so the relations: form must NOT be prescribed."""
    _entity(
        tmp_path, "questions/0001-x.md",
        entity_id="question:0001-x", kind="question",
        extra="supersedes: question:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    msg = results[0].message
    assert "question:0001-x" in msg
    assert "top-level 'supersedes:'" in msg
    # The dead-end prescription must be gone...
    assert "relations:" not in msg
    assert "<target-id>" not in msg
```

Rewrite the comment block at lines 135-138, which enumerates the twelve half-wired kinds as the reason for the kind-aware remediation: after S2 that set is empty, and the remediation's population is the 32 non-supersedable kinds.

- [ ] **Step 8: Delete the consolidation-candidates test**

Delete `test_lineage_reports_kind_lacking_superseded_vocab` from `science/tests/test_consolidation_candidates.py`.

It cannot be rebuilt to cover the skip path: `detect_consolidation_candidates` always loads authored input and builds a live graph — it never consumes saved material — and `_lineage_section` reads only `graph.linear`/`graph.non_linear`, never `supported_kinds`. What it actually asserted is that the read-only detector reports a chain regardless of stampability, and after S2 no shipped kind can be admitted-but-unstampable, so that is indistinguishable from the ordinary lineage test directly above it.

- [ ] **Step 9: Rebuild the skip test through the material path**

In `science/tests/test_consolidation_mark_superseded.py`, replace `test_member_whose_kind_lacks_superseded_vocab_is_skipped_not_crashed`. After S2 no authored input can reach the skip path — `_profile_relation_for_predicate` resolves against `CORE_PROFILE.relation_kinds` alone, so a project-local kind is never admitted either. The one reachable direction is **material whose frozen policy disagrees with its admitted edges**, which is exactly what the I4 digest exists to detect.

```python
def test_member_omitted_from_the_frozen_policy_is_skipped_not_crashed(tmp_path: Path) -> None:
    # The fixture is a NORMALLY SUPERSEDABLE kind held out of its material's `supported_kinds` --
    # not a "kind lacking the vocabulary", which after S2 cannot be an admitted member at all.
    # Reachable only from stale or hand-built material, so it is built through the material path
    # rather than by hand-constructing a graph: the point is that inconsistent material SURVIVES
    # `build_supersedes_graph_from_material` and is then skipped, and a hand-built graph would
    # bypass that step entirely.
    _seed(tmp_path)
    _write(tmp_path, "interpretations", "i-old", {"id": "interpretation:i-old", "kind": "interpretation"})
    _write(tmp_path, "interpretations", "i-new", {"id": "interpretation:i-new", "kind": "interpretation",
                                                  "relations": [_supersedes("interpretation:i-old")]})

    material = build_decision_material(tmp_path)
    assert "interpretation" in material.supported_kinds  # the fixture is meaningful only if so
    narrowed = material.model_copy(
        update={"supported_kinds": [k for k in material.supported_kinds if k != "interpretation"]}
    )

    plan = derive_supersede_plan(
        tmp_path,
        narrowed,
        selection=AllSupersessionMembers(kind="all"),
        preview_date="2026-07-26",
    )

    assert plan.preview_report.to_mark == []
    assert {entry.id for entry in plan.preview_report.skipped_kinds} == {"interpretation:i-old"}
```

Add these imports to the file:

```python
from science_tool.consolidation import build_decision_material
from science_tool.plan_common import AllSupersessionMembers
from science_tool.supersede_plan import derive_supersede_plan
```

Signatures confirmed against the source: `derive_supersede_plan(project_root: Path, material: SupersessionDecisionMaterial, *, selection: SupersedeSelection, preview_date: str) -> SupersedePlan`; `SupersedePlan.preview_report: SupersedePreviewReport` carries `to_mark: list[str]` and `skipped_kinds: list[SkippedKind]`, and `SkippedKind` has `id: str` and `kind: str` — attributes, not dict keys.

- [ ] **Step 10: Run both suites**

Run: `cd science/model && uv run --frozen pytest -q` then `cd science && uv run --frozen pytest -q` (allow ~3 min).
Expected: both green.

- [ ] **Step 11: Prove the gates can fail (mutation proofs 3 and 4)**

Mutation 3: temporarily remove `"decision"` from `_SELF_SUPERSEDING_KINDS`. Expected: `test_the_supersedes_TARGETS_agree_with_the_declaration` FAILS naming `decision` on the "supersedable but never an admissible target" side, and `test_every_supersedable_kind_can_author_the_CANONICAL_edge[decision]` FAILS. **Revert.**

Mutation 4: temporarily append `"workflow-run"` to the `supersedes` `source_kinds` only. Expected: `test_the_flat_endpoint_lists_agree_with_the_pairs[supersedes]` FAILS naming `workflow-run` as listed-only. **Revert**, and confirm green.

- [ ] **Step 12: Commit**

```bash
git add science/model/src/science_model/profiles/core.py science/model/tests/ science/tests/
git commit -m "feat(profile): gate supersedes endpoints against lineage capability

Ten kinds gain self-pairs, workflow-run is removed, and the flat endpoint
projections are reconciled with the pairs. The _KNOWN_HALF_WIRED subset ratchet
is deleted: with every kind ruled there is no debt to freeze, so the assertions
are exact equalities in both directions."
```

---

### Task 4: Derive the auto-stamping policy from the declaration

**Files:**
- Modify: `science/src/science_tool/kind_descriptors.py:51-54`
- Modify: `science/src/science_tool/consolidation.py:101-111` (delete), `:640-650`, `:799`
- Modify: `science/tests/test_decision_material.py:287`, `:311`
- Test: `science/tests/test_kind_reconciliation_lineage.py` (new)

**Interfaces:**
- Consumes: `EntityKind.supersedable`.
- Produces: `DECLARED_SUPERSEDABLE: dict[str, bool]` in `kind_descriptors.py`.

The live policy is `supported_kinds`, serialized at `consolidation.py:648` and frozen onto the graph. `_supports_superseded` has **no production callers** — repointing it would leave the declaration owning nothing.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_kind_reconciliation_lineage.py`:

```python
"""The auto-stamping policy carried on the graph must equal the declaration.

Tool-side, not model-side: `build_decision_material` lives in `science_tool`, and `science_model`
must not import its consumer.
"""

from __future__ import annotations

from pathlib import Path

from science_model.profiles import CORE_PROFILE
from science_tool.consolidation import build_decision_material


def test_the_frozen_policy_equals_the_profile_declaration(tmp_path: Path) -> None:
    # Compared against the PROFILE, reached independently of `kind_descriptors` -- because
    # `supported_kinds` will be BUILT from `DECLARED_SUPERSEDABLE`, so comparing it back to that map
    # would be the identity function.
    (tmp_path / "entities").mkdir()
    material = build_decision_material(tmp_path)
    declared = sorted(k.name for k in CORE_PROFILE.entity_kinds if k.supersedable)
    assert material.supported_kinds == declared
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_kind_reconciliation_lineage.py -q`
Expected: FAIL — `supported_kinds` is derived from `_STATUS_VALUES`, which covers core **and local** kinds, so the two lists differ.

If it unexpectedly passes, the assertion is not yet discriminating: widen it by also asserting a local-profile kind is absent, and confirm the failure before proceeding.

- [ ] **Step 3: Add the tool-side lookup**

In `science/src/science_tool/kind_descriptors.py`, after `DECLARED_STATUSES`:

```python
#: Kind -> whether it may be superseded (S2). Built over `KIND_DESCRIPTORS` -- the SHIPPED
#: profiles only -- exactly like `DECLARED_STATUSES`. That population is load-bearing: a kind
#: declared in a project manifest is ABSENT here and resolves to False, which preserves the rule
#: that a project-local kind is never auto-stamped (the write boundary's `_validate_status`
#: indexes `_STATUS_VALUES[kind]` and would raise KeyError).
DECLARED_SUPERSEDABLE: dict[str, bool] = {ek.name: bool(ek.supersedable) for ek in KIND_DESCRIPTORS}
```

- [ ] **Step 4: Derive the policy and delete the dead helper**

In `science/src/science_tool/consolidation.py`, import `DECLARED_SUPERSEDABLE` alongside the existing `kind_descriptors` imports, and replace the `supported_kinds=` line in `_project_inputs`:

```python
        # The auto-apply supported-kind policy IS a decision input (design §5.2): serialize it so
        # the digest covers it. It is the DECLARATION (S2) -- not a re-derivation from the status
        # vocabulary, which was how lineage capability came to be answered by two surfaces.
        supported_kinds=sorted(k for k, v in DECLARED_SUPERSEDABLE.items() if v),
```

Delete `_supports_superseded` (lines 101-111) and the two comments referring to it (at `:646` and `:700`). Its remaining references are prose only, in `science/tests/test_consolidation_mark_superseded.py` at lines 11 and 1131 — update both to name `DECLARED_SUPERSEDABLE`, since a comment pointing at a deleted symbol is the rot this whole change is about.

- [ ] **Step 5: Correct the public return documentation**

In `consolidation.py`, the `mark_superseded` return docs at `:799` define these keys by status capability, which S2 eliminates. Rewrite the two entries:

```python
    - ``to_mark``: member ids a linear chain would stamp ``superseded`` (excludes already-superseded
      members and members whose kind is absent from the graph's frozen ``supported_kinds``).
    - ``skipped_kinds``: ``{"id", "kind"}`` for members whose kind is absent from the graph's frozen
      ``supported_kinds`` policy. After S2 no authored input reaches this: every admissible
      supersedes target is supersedable. It remains reachable from STALE or hand-built decision
      material whose policy disagrees with its admitted edges -- which is what the I4 digest exists
      to detect.
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_kind_reconciliation_lineage.py -q`
Expected: PASS.

- [ ] **Step 7: Fix the two decision-material tests**

In `science/tests/test_decision_material.py`:

`test_material_carries_supported_kinds_and_digest_covers_the_policy` (line 287) injects a fake eligible kind by patching `_STATUS_VALUES`; that patch is now inert. Patch the new authority instead:

```python
    extended = dict(c.DECLARED_SUPERSEDABLE)
    extended["zzz-fake-kind"] = True  # a new auto-apply-eligible kind
    monkeypatch.setattr(c, "DECLARED_SUPERSEDABLE", extended)
```

Update its comment to name `DECLARED_SUPERSEDABLE` as the policy source.

`test_disposition_reads_supported_kinds_from_the_graph_not_the_module` (line 311) monkeypatches the now-deleted `_supports_superseded`. Preserve the negative control by neutralizing the module-level policy map instead:

```python
    monkeypatch.setattr(c, "DECLARED_SUPERSEDABLE", {})  # would empty to_mark if consulted
```

- [ ] **Step 8: Run both suites**

Run: `cd science/model && uv run --frozen pytest -q` then `cd science && uv run --frozen pytest -q` (allow ~3 min).
Expected: both green.

- [ ] **Step 9: Prove the gate can fail (mutation proof 5)**

Temporarily change the `supported_kinds=` expression to drop one kind, e.g. `sorted(k for k, v in DECLARED_SUPERSEDABLE.items() if v and k != "topic")`. Expected: `test_the_frozen_policy_equals_the_profile_declaration` FAILS. **Revert.**

Do **not** use "revert line 648 to `_STATUS_VALUES`" as the mutation. After Task 2 the two sources are forced equal by the vocabulary gate, so that mutation produces an identical set and proves nothing — an inert probe.

- [ ] **Step 10: Commit**

```bash
git add science/src/science_tool/kind_descriptors.py science/src/science_tool/consolidation.py science/tests/
git commit -m "feat(consolidation): derive the auto-stamping policy from the declaration

supported_kinds is built from DECLARED_SUPERSEDABLE rather than re-derived from
the status vocabulary. _supports_superseded is deleted: it had no production
callers, so repointing it would have left the declaration owning nothing."
```

---

### Task 5: Retire `workflow-run`'s top-level `supersedes:`

**Files:**
- Modify: `templates/workflow-run.md:9` and `:54`
- Modify: `science/src/science_tool/qa_audit/runs.py:35-55`
- Modify: `science/src/science_tool/qa_audit/verdicts.py:32-33`
- Modify: `science/src/science_tool/validate/checks/materialization.py:13-19`, `:45-52`
- Modify: `science/tests/validate/test_checks_materialization.py:77`
- Modify: `science/tests/test_qa_audit_runs.py`, `science/tests/test_qa_audit_audit.py`
- Modify: `docs/process/pipeline-audit-and-refactor.md:238`

The field sustains nothing: `RunRecord.supersedes` is written and never read; `chain_depth` counts runs per workflow and follows no link; no entity in any project authors the key.

- [ ] **Step 1: Write the failing test**

In `science/tests/validate/test_checks_materialization.py`, invert `test_supersedes_on_workflow_run_is_accepted`:

```python
def test_supersedes_on_workflow_run_is_an_error(tmp_path: Path) -> None:
    """S2 retired the field: it materialized no triple and no consumer read it."""
    _entity(
        tmp_path, "workflow-runs/0001-x.md",
        entity_id="workflow-run:0001-x", kind="workflow-run",
        extra="supersedes: workflow-run:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "workflow-run:0001-x" in results[0].message
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_materialization.py -q`
Expected: FAIL — the exemption still suppresses the finding, so `_results` is empty.

- [ ] **Step 3: Remove the exemption**

In `science/src/science_tool/validate/checks/materialization.py`, delete `_LEGIT_TOP_LEVEL` entirely — `("workflow-run", "supersedes")` is its only member — and the branch that consults it. Delete the docstring paragraph at lines 13-19 explaining the exemption.

A future top-level key with a genuine reader can reintroduce the mechanism together with the reader that justifies it; keeping an empty exemption set would be documenting a compat projection rather than deleting it.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_materialization.py -q`
Expected: PASS.

- [ ] **Step 5: Drop the dead QA field**

In `science/src/science_tool/qa_audit/runs.py`, remove `supersedes` from the `RunRecord` dataclass and from the `records.append(...)` call, and correct `chain_depth`'s docstring:

```python
def chain_depth(runs: list[RunRecord], workflow: str) -> int:
    """Number of runs recorded for the workflow; 1 == single run.

    Counts runs — it does NOT follow a supersession chain. The top-level `supersedes:` field it
    once loaded was retired in S2: nothing consumed it.
    """
    return sum(1 for r in runs if r.workflow == workflow)
```

In `science/src/science_tool/qa_audit/verdicts.py`, correct the `iteration_verdict` docstring, which calls `chain_depth >= 2` "a supersedes re-run" — it is "more than one recorded run".

- [ ] **Step 6: Fix the QA tests**

In `science/tests/test_qa_audit_runs.py` and `science/tests/test_qa_audit_audit.py`, remove the `supersedes` parameter from the `_run` helpers and every call site.

Rename `test_chain_depth_counts_supersession` to `test_chain_depth_counts_runs_for_the_workflow`. It authored `supersedes:` on two of three runs and asserted `chain_depth == 3` — a value the function returns whether or not those keys exist, making it tautological with respect to its own name.

- [ ] **Step 7: Update the two user-facing surfaces**

In `templates/workflow-run.md`, delete the `supersedes: []` frontmatter line (line 9) **and** the `- **Supersedes:** ...` bullet in the Entity Cross-References section (line 54). Leaving the prose would keep recommending a field the validator now rejects.

In `docs/process/pipeline-audit-and-refactor.md:238`, the playbook says `science qa-audit` "reads each workflow's `workflow-run` / `sci:supersedes` chain". That relation is now rejected for `workflow-run`, and the sentence was already wrong about the mechanism. Replace the clause with: `which counts the runs recorded for each workflow and reads their QA dispositions`.

- [ ] **Step 8: Run both suites, lint and types**

Run: `cd science/model && uv run --frozen pytest -q`, then `cd science && uv run --frozen pytest -q` (allow ~3 min), then `cd science && uv run ruff check && uv run pyright`.
Expected: all green.

- [ ] **Step 9: Verify the live-surface sweep is complete**

```bash
cd /path/to/worktree && rg -n "supersedes" templates/workflow-run.md docs/process/pipeline-audit-and-refactor.md
```
Expected: no matches.

Do **not** edit the dated design and plan documents under `docs/plans/` that mention the exemption — `2026-07-15-non-materializing-fields-plan.md:20` and `2026-07-12-d4-status-vocabulary-audit.md:47`. They are historical records of completed work; rewriting them would falsify the record of why the exemption existed.

- [ ] **Step 10: Commit**

```bash
git add templates/ docs/process/ science/src/science_tool/ science/tests/
git commit -m "refactor(qa-audit): retire workflow-run's top-level supersedes field

It materialized no triple, RunRecord.supersedes was written and never read, and
chain_depth counts runs rather than following a chain. No entity in any project
authored the key, so this is a zero-migration change."
```

---

## Verification

After Task 5, from a clean tree on the branch:

```bash
cd science/model && uv run --frozen pytest -q
cd science && uv run --frozen pytest -q      # ~3 min; run AFTER the model suite, never concurrently
cd science && uv run ruff check && uv run pyright
```

Then confirm the end state:

```bash
cd science && uv run --frozen python -c "
from science_model.profiles import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
from science_tool.kind_descriptors import DECLARED_SUPERSEDABLE
kinds = [*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds]
sup = {k.name for k in kinds if k.supersedable}
vocab = {k.name for k in kinds if 'superseded' in (k.statuses or ())}
rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == 'supersedes')
targets = {p.target_kind for p in rel.allowed_kind_pairs}
policy = {k for k, v in DECLARED_SUPERSEDABLE.items() if v}
print('declared    ', len(sup))
print('vocabulary  ', vocab == sup)
print('endpoints   ', targets == sup)
print('policy      ', policy == sup)
print('flat lists  ', set(rel.source_kinds) == {p.source_kind for p in rel.allowed_kind_pairs})
"
```
Expected:
```
declared     18
vocabulary   True
endpoints    True
policy       True
flat lists   True
```
