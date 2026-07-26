# S2 Lineage Capability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Declare per kind whether it can be superseded, and make the status vocabulary, the relation endpoint list, and the auto-stamping policy all derive from that one declaration.

**Architecture:** `EntityKind` gains a `supersedable: bool` field, declared explicitly on all 53 shipped kinds. Three surfaces that currently infer lineage capability from each other are gated against it by exact equality in both directions. Fifteen kinds are re-ruled so both existing gaps close, `workflow-run`'s dead top-level `supersedes:` field is retired, and a post-review correction makes every supersedable shipped kind reachable through the descriptor-derived Markdown write policy.

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
- **Every supersedable shipped kind is writable.** Its descriptor must supply both `home` and `strategy`, so it appears in `_BUILTIN_MARKDOWN_POLICIES`; a dry-run member in `to_mark` must never disappear at the apply lookup boundary.
- **Do not add the ten newly-supersedable kinds to `_CONCLUSION_KINDS`.** That list is shared with the `amends` relation; widening it would silently grant cross-kind amendment admissibility this design did not rule on. They are **self-pairs**.
- **A stale exemption must fail as loudly as a new gap.** Every gate assertion in this plan is exact equality in both directions, with a failure message naming each side.

---

## File Structure

| File | Responsibility in this change |
|---|---|
| `science/model/src/science_model/profiles/schema.py` | declares the `supersedable` field on `EntityKind` |
| `science/model/src/science_model/profiles/core.py` | the 50 core declarations, the 4 status rulings, the `supersedes` endpoint rulings, and the validation-report Markdown write policy |
| `science/model/src/science_model/profiles/local.py` | the 3 local-profile declarations |
| `science/model/tests/test_supersedable_gate.py` | the gate — all five properties; rewritten from a subset ratchet to exact equality |
| `meta/doc/plans/2026-07-26-s2-lineage-capability-design.md` | the authored validation-report write-path ruling and the actual project-local inertness guarantees |
| `science/src/science_tool/kind_descriptors.py` | `DECLARED_SUPERSEDABLE`, the tool-side lookup mirroring `DECLARED_STATUSES` |
| `science/src/science_tool/entities.py` | descriptor-derived built-in Markdown policies and the shared entity lookup/write boundary; unchanged, but guarded by Task 6 parity |
| `science/src/science_tool/consolidation.py` | the auto-stamping policy derives from the declaration |
| `science/src/science_tool/graph/materialize.py` | core-profile relation resolution and endpoint admission; unchanged authority exercised by the local-kind regression |
| `science/tests/test_kind_map_equivalence.py` | frozen status/default/Markdown-policy oracles, re-frozen only against written rulings |
| `science/tests/test_consolidation_mark_superseded.py` | real apply-level coverage for both reverse-gap kinds |
| `science/tests/test_decision_material.py` | direct project-local exclusion from both supported policy and core relation admission |
| `science/src/science_tool/qa_audit/runs.py`, `verdicts.py` | drop the dead `supersedes` field; correct two docstrings |
| `science/src/science_tool/validate/checks/materialization.py` | remove the one-entry legit-reader exemption |
| `science/tests/validate/test_checks_materialization.py` | validator behavior and unconditional top-level `amends:` rationale |
| `templates/workflow-run.md`, `docs/process/pipeline-audit-and-refactor.md` | user-facing guidance for the retired field |
| `commands/next-steps.md` → `codex-skills/science-next-steps/SKILL.md` | live agent guidance naming unreachable workflow-run states; the mirror is regenerated, never hand-edited |

---

### Task 1: Declare `supersedable` on every shipped kind

**Files:**
- Modify: `science/model/src/science_model/profiles/schema.py:23-48` (the `EntityKind` model)
- Modify: `science/model/src/science_model/profiles/core.py` (all 50 `EntityKind(...)` blocks)
- Modify: `science/model/src/science_model/profiles/local.py` (all 3 `EntityKind(...)` blocks)
- Test: `science/model/tests/test_supersedable_gate.py` (**append only** — the existing ratchet must survive this task)
- Test: `science/model/tests/test_entity_kind_schema.py:17` (pin the `False` default)

**Interfaces:**
- Produces: `EntityKind.supersedable: bool` (default `False`). Later tasks read it off `CORE_PROFILE.entity_kinds` and off `LOCAL_PROFILE.entity_kinds`.

This task only adds data. No surface consumes it yet, so both suites must stay green.

- [ ] **Step 1: Write the failing test**

**APPEND to `science/model/tests/test_supersedable_gate.py`. Do not replace the file.**

`_KNOWN_HALF_WIRED` and `test_every_supersedable_kind_can_author_the_CANONICAL_edge` must survive Tasks 1 and 2 — they are the *only* endpoint guard until Task 3 installs the exact gate, and deleting them here would leave two intermediate commits with no endpoint coverage at all. Task 3 removes them at the moment it replaces them. The module docstring is likewise rewritten in Task 3, not here.

The file already imports `CORE_PROFILE` (from `science_model.profiles.core`), `RelationKind`, and `relation_allows_kinds`, and already defines `_supersedes()`. **Do not re-import or redefine any of them** — a second `CORE_PROFILE` import under a different module path is a redefinition Ruff fails on (F811), and Task 3 needs the existing helper intact.

Add only what is genuinely new — extend the existing `science_model.profiles.schema` import rather than writing a second one:

```python
# EXTEND the existing line: `from science_model.profiles.schema import RelationKind`
from science_model.profiles.schema import EntityKind, RelationKind

# NEW imports
import pytest

from science_model.profiles.local import LOCAL_PROFILE

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
Expected: the module still **collects** — nothing at import time touches the new field. 53 failures of `test_every_shipped_kind_DECLARES_supersedable` (`"supersedable"` is not in `model_fields_set`) and one `AttributeError` in `test_the_declared_population_is_exactly_the_ruling` (`EntityKind` has no attribute `supersedable`). The pre-existing tests in the file stay green.

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

- [ ] **Step 5: Pin the `False` default**

The shipped-kind tests all declare explicitly, so none of them can catch the default flipping to `True` — and that default is load-bearing: it is what keeps a project-authored manifest kind inert. Extend the existing `test_entity_kind_new_fields_default_to_neutral` in `science/model/tests/test_entity_kind_schema.py:17`, which constructs a bare `EntityKind`:

```python
    assert ek.supersedable is False
```

- [ ] **Step 6: Verify the declaration is complete and correct**

Run: `cd science/model && uv run --frozen pytest tests/test_supersedable_gate.py tests/test_entity_kind_schema.py -q`
Expected: PASS. The gate file contributes 54 new tests (53 parametrized + the population test) on top of its pre-existing ones.

Then confirm the counts:

```bash
cd science && uv run --frozen python -c "
from science_model.profiles import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
k = [*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds]
print(len(k), sum(x.supersedable for x in k))"
```
Expected: `53 18`

- [ ] **Step 7: Prove the gates can fail (mutation proof 1)**

Temporarily delete `supersedable=False,` from the `question` block in `core.py`. Re-run the test file. Expected: `test_every_shipped_kind_DECLARES_supersedable[question]` FAILS naming `question`. **Revert the mutation** and confirm the file is green again.

Then temporarily change the field default in `schema.py` to `supersedable: bool = True`. Expected: `test_entity_kind_new_fields_default_to_neutral` FAILS. **Revert.** Do not commit either mutation.

- [ ] **Step 8: Run both suites**

Run: `cd science/model && uv run --frozen pytest -q` then `cd science && uv run --frozen pytest -q` (allow ~3 min).
Expected: both green. Nothing consumes the new field yet, and the pre-existing endpoint ratchet is untouched.

- [ ] **Step 9: Commit**

```bash
git add science/model/src/science_model/profiles/schema.py \
        science/model/src/science_model/profiles/core.py \
        science/model/src/science_model/profiles/local.py \
        science/model/tests/test_supersedable_gate.py \
        science/model/tests/test_entity_kind_schema.py
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
- Modify: `science/tests/test_decision_material.py:96-98` (comment only)
- Test: `science/model/tests/test_supersedable_gate.py`

**Interfaces:**
- Consumes: `EntityKind.supersedable` from Task 1.
- Produces: `_SELF_SUPERSEDING_KINDS: list[str]` and `_SELF_SUPERSEDING_PAIRS: list[RelationEndpointPair]` in `core.py`; the `supersedes` relation admits exactly the 18 supersedable kinds as targets.

**Measured expected failures** (from running this change): `test_profile_manifests.py::test_core_profile_declares_amends_and_non_cartesian_supersedes`, `test_graph_materialize.py::test_materialize_graph_preserves_workflow_run_supersedes`, `validate/test_checks_materialization.py::test_inadmissible_kind_is_not_told_to_author_the_relation`, `test_consolidation_candidates.py::test_lineage_reports_kind_lacking_superseded_vocab`, `test_consolidation_mark_superseded.py::test_member_whose_kind_lacks_superseded_vocab_is_skipped_not_crashed`.

- [ ] **Step 1: Write the failing tests**

Append to `science/model/tests/test_supersedable_gate.py`. **Add no imports and no helper.** `RelationKind`, `relation_allows_kinds`, `CORE_PROFILE`, `pytest`, and `_supersedes()` are all already in the file — `_supersedes()` survives this task because `test_supersedes_description_names_spec_replacement` (kept, below) still calls it. Re-declaring any of them is an F811 redefinition:

```python
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

**Only now** delete the old ratchet — this is the task that replaces it, and Tasks 1 and 2 deliberately left it in place as the sole endpoint guard. Remove from the file: `_KNOWN_HALF_WIRED`, the old subset-asserting `test_every_supersedable_kind_can_author_the_CANONICAL_edge`, `test_hypothesis_is_a_supersedes_ENDPOINT`, and `test_spec_is_a_supersedes_ENDPOINT` — the parametrized version above covers both by derivation rather than by naming two kinds. Keep `test_supersedes_description_names_spec_replacement`.

Replace the module docstring, which describes the ratchet, with:

```python
"""Lineage capability: ONE declaration, and the surfaces that must agree with it.

`EntityKind.supersedable` answers "can an entity of this kind be replaced as canonical by a newer
one?" It is DECLARED per kind, never inferred. The status vocabulary, the `sci:supersedes` endpoint
list, and the auto-stamping policy are all gated against it by EXACT equality in both directions --
so a stale exemption fails as loudly as a new gap.

This file used to carry a SUBSET ratchet over `_KNOWN_HALF_WIRED`, a frozen allowlist of twelve
half-wired kinds. That ratchet was right while the debt existed -- exact equality would have made
repairing any one of the twelve fail the suite. S2 rules all fifteen affected kinds, so there is no
debt left to freeze and the assertions became equalities. Restoring a subset assertion here would
re-open the hole by construction.
"""
```

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

**The same test asserts `workflow-run` a second time**, further down at line 111, against the pair set rather than the admission helper:

```python
    assert ("workflow-run", "workflow-run") in supersedes_pairs
```

Invert it, and add the self-pair coverage beside it:

```python
    assert ("workflow-run", "workflow-run") not in supersedes_pairs
    for self_superseding in ("topic", "plan", "decision", "workflow-step"):
        assert (self_superseding, self_superseding) in supersedes_pairs
```

Leave `test_tests_relation_accepts_workflow_run` and `test_executes_relation_targets_workflow` alone — `workflow-run` remains a valid endpoint of `tests` and `executes`; only its *supersession* is retired.

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

- [ ] **Step 10: Correct the invalid-fixture explanation**

`science/tests/test_decision_material.py:96-98` builds the `invalid` fixture — a `workflow-run` authoring `sci:supersedes` at an `interpretation` — and explains it as "an illegal kind pair (`workflow-run` may only supersede `workflow-run`)". After Step 3 that sentence is false: `workflow-run` is not a `sci:supersedes` endpoint in *either* position, so the edge is refused on the source kind, not on the pairing. The fixture stays — it is still a valid inadmissible-relation fixture and the test around it still passes — but the explanation must say why:

```python
    # invalid: an authored relation `materialize` refuses outright. After S2 `workflow-run` is not a
    # `sci:supersedes` endpoint in EITHER position, so this is refused on the source kind -- not,
    # as it once was, for pairing a workflow-run with the wrong target.
```

This is a comment-only edit: run `cd science && uv run --frozen pytest tests/test_decision_material.py -q` and expect it green, unchanged.

- [ ] **Step 11: Run both suites**

Run: `cd science/model && uv run --frozen pytest -q` then `cd science && uv run --frozen pytest -q` (allow ~3 min).
Expected: both green.

- [ ] **Step 12: Prove the gates can fail (mutation proofs 3 and 4)**

Mutation 3: temporarily remove `"decision"` from `_SELF_SUPERSEDING_KINDS`. Expected: `test_the_supersedes_TARGETS_agree_with_the_declaration` FAILS naming `decision` on the "supersedable but never an admissible target" side, and `test_every_supersedable_kind_can_author_the_CANONICAL_edge[decision]` FAILS. **Revert.**

Mutation 4: temporarily append `"workflow-run"` to the `supersedes` `source_kinds` only. Expected: `test_the_flat_endpoint_lists_agree_with_the_pairs[supersedes]` FAILS naming `workflow-run` as listed-only. **Revert**, and confirm green.

- [ ] **Step 13: Commit**

```bash
git add science/model/src/science_model/profiles/core.py \
        science/model/tests/test_supersedable_gate.py \
        science/model/tests/test_profile_manifests.py \
        science/tests/test_graph_materialize.py \
        science/tests/validate/test_checks_materialization.py \
        science/tests/test_consolidation_candidates.py \
        science/tests/test_consolidation_mark_superseded.py \
        science/tests/test_decision_material.py
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
- Modify: `science/tests/test_decision_material.py:287` (the driver), `:311`
- Modify: `science/tests/test_consolidation_mark_superseded.py` — `:11` and `:1131` (prose references to the deleted helper), plus two new tests using the `_seed`/`_write`/`_supersedes` helpers already in the file

**Interfaces:**
- Consumes: `EntityKind.supersedable`.
- Produces: `DECLARED_SUPERSEDABLE: dict[str, bool]` in `kind_descriptors.py`.

The live policy is `supported_kinds`, serialized at `consolidation.py:648` and frozen onto the graph. `_supports_superseded` has **no production callers** — repointing it would leave the declaration owning nothing.

**A value-equality test cannot drive this task.** After Task 2 the status-derived set and the declaration-derived set are *identical* — 18 kinds, with the 3 local kinds contributing to neither side because they declare no `statuses`. So `supported_kinds == declared` passes **before** the implementation change and proves nothing about which authority produced it. The driver must be a test that distinguishes the two *sources*, not their current values.

- [ ] **Step 1: Write the failing test**

The discriminating test already exists in skeleton form: `test_material_carries_supported_kinds_and_digest_covers_the_policy` in `science/tests/test_decision_material.py:287` injects a fake eligible kind and asserts the digest moves. Re-point its injection at the new authority — under the old implementation, patching `DECLARED_SUPERSEDABLE` has no effect on a policy built from `_STATUS_VALUES`, so the digest does not move and the test fails.

```python
    from science_model.profiles import CORE_PROFILE
    extended = {ek.name: ek.supersedable for ek in CORE_PROFILE.entity_kinds}
    extended["zzz-fake-kind"] = True  # a new auto-apply-eligible kind
    # Built from the PROFILE, and patched with `raising=False`, because this test must run RED:
    # `DECLARED_SUPERSEDABLE` does not exist on the module until Step 3. Reading `c.DECLARED_SUPERSEDABLE`
    # here -- or letting monkeypatch enforce the attribute -- would raise AttributeError during setup
    # and the red run would never reach the digest assertion that is the actual driver.
    monkeypatch.setattr(c, "DECLARED_SUPERSEDABLE", extended, raising=False)
```

Update its comment to name `DECLARED_SUPERSEDABLE` as the policy source.

Then add the *behavioural* half — a supersedable kind is actually stamped. This is what gives mutation proof 5 something to break beyond an equality. It goes in `science/tests/test_consolidation_mark_superseded.py`, at the end of the interpretation section (immediately before the `# hypothesis — EXECUTABLE for the first time` banner), because `_seed`, `_write`, and `_supersedes` already live there — copying them into a new module would fork the fixture shape this file is the authority on. No new imports: `mark_superseded` and `CORE_PROFILE` are both already imported at the top.

```python
def test_a_newly_supersedable_kind_is_actually_stamped(tmp_path: Path) -> None:
    # `topic` gained its endpoint in Task 3 and has always declared the status. If the policy stops
    # following the declaration, this member silently stops being stamped -- which an equality
    # assertion over two currently-identical sets would not catch.
    _seed(tmp_path)
    _write(tmp_path, "topics", "t-old", {"id": "topic:t-old", "kind": "topic", "status": "active"})
    _write(tmp_path, "topics", "t-new", {"id": "topic:t-new", "kind": "topic", "status": "active",
                                         "relations": [_supersedes("topic:t-old")]})

    report = mark_superseded(tmp_path, apply=False)

    assert report["to_mark"] == ["topic:t-old"]
    assert report["skipped_kinds"] == []


def test_the_frozen_policy_equals_the_profile_declaration(tmp_path: Path) -> None:
    # Regression, not the driver: compared against the PROFILE, reached independently of
    # `kind_descriptors`, because `supported_kinds` is BUILT from `DECLARED_SUPERSEDABLE` and
    # comparing it back to that map would be the identity function.
    from science_tool.consolidation import build_decision_material

    _seed(tmp_path)
    (tmp_path / "entities").mkdir()
    material = build_decision_material(tmp_path)
    declared = sorted(ek.name for ek in CORE_PROFILE.entity_kinds if ek.supersedable)
    assert material.supported_kinds == declared
```

- [ ] **Step 2: Run the tests to verify the driver fails**

Run: `cd science && uv run --frozen pytest \
        tests/test_decision_material.py::test_material_carries_supported_kinds_and_digest_covers_the_policy \
        tests/test_consolidation_mark_superseded.py::test_a_newly_supersedable_kind_is_actually_stamped \
        tests/test_consolidation_mark_superseded.py::test_the_frozen_policy_equals_the_profile_declaration -q`
Expected: the digest test FAILS (`before != after` is false — the patched authority is not consulted). The two new tests PASS already; they are regressions guarding the change, not drivers of it.

- [ ] **Step 3: Add the tool-side lookup**

In `science/src/science_tool/kind_descriptors.py`, after `DECLARED_STATUSES`:

```python
#: Kind -> whether it may be superseded (S2). Built over `KIND_DESCRIPTORS` -- the SHIPPED
#: profiles only -- exactly like `DECLARED_STATUSES`. That population is load-bearing: a kind
#: declared in a project manifest is ABSENT here and cannot enter the frozen `supported_kinds`
#: policy. Authored `sci:supersedes` admission independently resolves against the core relation
#: descriptor, so a project-local endpoint pair is refused. The writer itself supports
#: project-local status vocabularies; inertness does not depend on a write-time failure.
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

**Drop the now-unused import.** `_STATUS_VALUES` was used only by the deleted helper and by the line just replaced, so the import at `consolidation.py:53` becomes dead and Ruff will fail the build:

```python
from science_tool.entities import _commit_write, _PreparedWrite
```

`_SUPERSEDED` (line 61) **stays** — it is still used at lines 687 and 719 to write and compare the status.

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

- [ ] **Step 6: Run the driver to verify it now passes**

Run: `cd science && uv run --frozen pytest \
        tests/test_decision_material.py::test_material_carries_supported_kinds_and_digest_covers_the_policy \
        tests/test_consolidation_mark_superseded.py::test_a_newly_supersedable_kind_is_actually_stamped \
        tests/test_consolidation_mark_superseded.py::test_the_frozen_policy_equals_the_profile_declaration -q`
Expected: PASS. The patched `DECLARED_SUPERSEDABLE` now reaches the policy, so the digest moves.

- [ ] **Step 7: Fix the remaining decision-material test**

In `science/tests/test_decision_material.py`, `test_disposition_reads_supported_kinds_from_the_graph_not_the_module` (line 311) monkeypatches the now-deleted `_supports_superseded`. Preserve the negative control by neutralizing the module-level policy map instead:

```python
    monkeypatch.setattr(c, "DECLARED_SUPERSEDABLE", {})  # would empty to_mark if consulted
```

- [ ] **Step 8: Run both suites**

Run: `cd science/model && uv run --frozen pytest -q` then `cd science && uv run --frozen pytest -q` (allow ~3 min).
Expected: both green.

- [ ] **Step 9: Prove the gate can fail (mutation proof 5)**

Temporarily change the `supported_kinds=` expression to drop one kind: `sorted(k for k, v in DECLARED_SUPERSEDABLE.items() if v and k != "topic")`.

Expected — **both halves must fail**, and the behavioural one is the point:
- `test_the_frozen_policy_equals_the_profile_declaration` FAILS (the equality half).
- `test_a_newly_supersedable_kind_is_actually_stamped` FAILS — `topic:t-old` drops out of `to_mark` and appears in `skipped_kinds`. A policy that silently stops stamping a ruled kind is the actual harm; an equality over two sets is only its shadow.

**Revert** and confirm both pass again.

Do **not** use "revert line 648 to `_STATUS_VALUES`" as the mutation. After Task 2 the two sources are forced equal by the vocabulary gate, so that mutation produces an identical set and proves nothing — an inert probe.

- [ ] **Step 10: Commit**

```bash
git add science/src/science_tool/kind_descriptors.py \
        science/src/science_tool/consolidation.py \
        science/tests/test_decision_material.py \
        science/tests/test_consolidation_mark_superseded.py
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
- Modify: `commands/next-steps.md:75-76` and `:210`
- Regenerate: `codex-skills/science-next-steps/SKILL.md` (generated mirror — never hand-edited)

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

**Three prose surfaces in the same area go stale with it** and must be corrected in this step:

- `materialization.py:21` (module docstring) — "`sci:supersedes` declares 9 source kinds and `sci:amends` 6". After S2 it is **18** and 6.
- `materialization.py:58` (`_remediation` docstring) — "The `supersedes` RelationKind admits 9 source kinds and `amends` 6". Same correction.
- `science/tests/validate/test_checks_materialization.py:7` (module docstring) — "`workflow-run.supersedes` is the ONE legitimate top-level use (read by qa_audit/runs.py:47), so the exception is that exact (kind, key) PAIR". Replace with a note that S2 retired the field and there is no longer any legitimate top-level use, so the check has no exemptions.

Both numbers describe *why the remediation is kind-aware*, so leaving them stale re-creates the defect this program exists to close — a fact answered two ways.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_materialization.py -q`
Expected: PASS.

- [ ] **Step 5: Drop the dead QA field**

In `science/src/science_tool/qa_audit/runs.py`, remove `supersedes` from the `RunRecord` dataclass and from the `records.append(...)` call. That line is the only use of `field`, so narrow the import or Ruff will fail:

```python
from dataclasses import dataclass
```

**Delete `_as_list` (lines 18-23) in the same step.** `supersedes=_as_list(fm.get("supersedes"))` at line 47 is its only caller; it is module-private and imported nowhere else, so removing the field strands it. (The identically named helpers in `migrate_specs.py` and `datasets/schema.py` are separate module-private functions — leave both alone.)

Then correct `chain_depth`'s docstring:

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

- [ ] **Step 8: Correct the live agent guidance and regenerate the Codex mirror**

`commands/next-steps.md` tells agents to look for workflow-run states that S2 makes unreachable. Two lines, not one:

- **Line 76**, under `#### Workflow Runs`: "Report: recent runs (last 7 days), superseded runs, runs with status `draft`." (Line 75, which supplies its scan, is rewritten with it — see below.)
- **Line 210**, under **Unreflected failures**: "a **discarded / superseded / `draft` workflow run** (already surfaced under Workflow Runs above)…" — this line back-references line 76, so correcting one without the other leaves a dangling pointer.

`superseded` is what S2 removes: `workflow-run` loses the `sci:supersedes` endpoint (Task 3) and the top-level field (this task), and it never declared a `superseded` status. **`discarded` and `draft` are independently unreachable** and were already so before S2 — `workflow-run` declares a closed vocabulary, `statuses=["running", "complete", "failed"]` with `default_status="running"` (`core.py:568-578`). That is a pre-existing defect, not one this change creates, but both tokens sit inside sentences this step is rewriting, and leaving a known-false state name in a line being edited is not defensible. Correct all three against the declared vocabulary.

**The status claim needs a source that carries status.** Line 75 scans `results/` for `datapackage.json` manifests, and run *status* does not live there — the template puts `status` in the workflow-run entity frontmatter (`templates/workflow-run.md:5`) and points at the manifest separately, as `datapackage.yaml`, via `manifest_path` (`:7`, `:47`). Reporting `failed` off a manifest scan would be unreachable guidance, so lines 75-76 are rewritten together: the entity is the status authority, the manifest is the result detail.

Lines 75-76 become:

```markdown
- List workflow-run entities with `science entity list workflow-run --format json`; read result
  details from each run's `manifest_path` manifest.
- Report: recent runs (last 7 days) and runs with status `failed`
  (`science entity list workflow-run --status failed --format json`).
```

Verified against the CLI: `entity list` takes the kind positionally and accepts `--status` and `--format json`. Leave the **Fallback when no manifests exist** paragraph below (lines 79-84) alone — it is about inferring bundles from `results/` directory conventions when no manifest exists, and its "superseded by a later one with the same slug" clause is about bundle filenames, not entity lineage.

Line 210 becomes:

```markdown
- a workflow run with status `failed` (already surfaced under Workflow Runs above)
  with no interpretation and no post-mortem.
```

Leave line 194 alone — `sci:supersedes` plus `status: superseded` on a *conclusion* is exactly the supersedable path S2 keeps.

Then regenerate the mirror. `codex-skills/` is a git-tracked generated tree; `test_committed_codex_skills_match_fresh_generation` (`science/tests/test_codex_skills.py:799`) fails if the committed output drifts from a fresh run, so this is not optional:

```bash
cd science && uv run --frozen python ../scripts/generate_codex_skills.py
```

Expected: `codex-skills/science-next-steps/SKILL.md` picks up all three corrections (its copies of lines 75-76 sit at `:194-195`, and of line 210 at `:329`). Do not hand-edit the mirror.

- [ ] **Step 9: Run both suites, lint and types**

Run: `cd science/model && uv run --frozen pytest -q`, then `cd science && uv run --frozen pytest -q` (allow ~3 min), then `cd science && uv run ruff check && uv run pyright`.
Expected: all green.

- [ ] **Step 10: Verify the live-surface sweep is complete**

From the repository root:

```bash
rg -n "supersedes" templates/workflow-run.md docs/process/pipeline-audit-and-refactor.md
rg -n -i "superseded|discarded|draft" commands/next-steps.md codex-skills/science-next-steps/SKILL.md
```
Expected: the first command reports no matches. The second is deliberately broad — it matches every occurrence of the words, so read its output against this list rather than expecting silence. Exactly three families of match must remain, in both the command and its mirror, and **none of them is a `workflow-run` state**:

| line (command) | match | why it stays |
|---|---|---|
| `:81` | "bundles whose name appears superseded by a later one with the same slug" | analysis-bundle *filenames*, not entity lineage |
| `:111` | "tasks superseded by results or no longer decision-relevant" | ordinary English in task-pruning guidance; no entity state named |
| `:194` | "`sci:supersedes` plus `status: superseded` on the old conclusion" | the supersedable path S2 *keeps* — conclusion kinds |

Any fourth match, or any match naming a `workflow-run`, means the retirement is incomplete.

Do **not** edit the dated design and plan documents under `docs/plans/` that mention the exemption — `2026-07-15-non-materializing-fields-plan.md:20` and `2026-07-12-d4-status-vocabulary-audit.md:47`. They are historical records of completed work; rewriting them would falsify the record of why the exemption existed.

- [ ] **Step 11: Commit**

```bash
git add templates/workflow-run.md \
        docs/process/pipeline-audit-and-refactor.md \
        commands/next-steps.md \
        codex-skills/science-next-steps/SKILL.md \
        science/src/science_tool/qa_audit/runs.py \
        science/src/science_tool/qa_audit/verdicts.py \
        science/src/science_tool/validate/checks/materialization.py \
        science/tests/validate/test_checks_materialization.py \
        science/tests/test_qa_audit_runs.py \
        science/tests/test_qa_audit_audit.py
git commit -m "refactor(qa-audit): retire workflow-run's top-level supersedes field

It materialized no triple, RunRecord.supersedes was written and never read, and
chain_depth counts runs rather than following a chain. No entity in any project
authored the key, so this is a zero-migration change."
```

---

### Task 6: Close the validation-report write path and pin project-local inertness

This is an explicit **post-review correction**. Task 2 remains the historical status-only
intermediate: it makes `validation-report` supersedable in the model but does not make it writable.
After Task 5, that omission is observable: dry-run admits a validation-report chain and places its
old member in `to_mark`, while apply cannot find the member because the descriptor-derived Markdown
policy omits every kind whose `home` or `strategy` is unset. This task closes that runtime gap and
adds the missing end-state guard.

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py` (the
  validation-report `EntityKind` block; `_SELF_SUPERSEDING_KINDS` only during the
  uncommitted mutation proof)
- Modify: `meta/doc/plans/2026-07-26-s2-lineage-capability-design.md` (the project-local guarantee
  paragraph and the validation-report write-path ruling)
- Modify: `docs/plans/2026-07-26-s2-lineage-capability-implementation-plan.md` (Task 4 rationale,
  File Structure, this correction task, and final Verification)
- Modify: `science/src/science_tool/kind_descriptors.py` (`DECLARED_SUPERSEDABLE` rationale; one
  uncommitted mutation line during the proof)
- Read: `science/src/science_tool/entities.py:58-62`, `:365-370`, `:694-744`
  (`_BUILTIN_MARKDOWN_POLICIES`, policy resolution, and entity lookup)
- Read: `science/src/science_tool/graph/materialize.py:1908-1948`
  (core relation lookup and authored endpoint admission)
- Modify: `science/tests/test_kind_map_equivalence.py` (`FROZEN_MARKDOWN_POLICIES`)
- Test: `science/tests/test_consolidation_mark_superseded.py`
  (`test_reverse_gap_kind_is_stamped_on_apply`)
- Test: `science/tests/test_decision_material.py`
  (`test_project_local_kind_is_neither_supported_nor_admitted_for_supersession`)
- Modify: `science/tests/validate/test_checks_materialization.py`
  (`test_amends_on_workflow_run_is_an_error` prose only)

**Interfaces:**
- Consumes: `EntityKind.home: str | None`, `EntityKind.strategy: str | None`, and
  `EntityKind.supersedable: bool` from Tasks 1–2.
- Consumes: `_BUILTIN_MARKDOWN_POLICIES: dict[str, EntityPathPolicy]` from
  `science_tool.entities`; the map contains a shipped descriptor only when both `home` and
  `strategy` are non-null.
- Consumes: `mark_superseded(project_root: Path, *, ids: frozenset[str] | None = None,
  apply: bool) -> dict[str, Any]`; the regression reaches its real graph admission, disposition,
  prepare, shared writer, and disk commit path.
- Consumes: `build_decision_material(project_root: Path) -> SupersessionDecisionMaterial` and the
  core `supersedes` `RelationKind` endpoint pairs.
- Produces: `validation-report` maps to
  `EntityPathPolicy(Path("entities/validation-reports"), "numeric")`.
- Produces: the executable end-state invariant
  `{k.name for k in SHIPPED_KINDS if k.supersedable} <=
  set(_BUILTIN_MARKDOWN_POLICIES)`.

- [ ] **Step 1: Add the apply-level regression before changing the descriptor**

In `science/tests/test_consolidation_mark_superseded.py`, immediately after
`test_apply_sets_superseded_status_on_members`, add this complete test. `pytest`, `Path`,
`read_frontmatter`, `_seed`, `_write`, `_supersedes`, and `mark_superseded` already exist in this
module; add no duplicate imports or helpers.

The starting status is part of the parameterization because the two closed vocabularies differ:
`story` starts at `draft`, while `validation-report` starts at `active`.

```python
@pytest.mark.parametrize(
    ("kind", "kind_dir", "starting_status", "old_name", "new_name"),
    [
        pytest.param("story", "stories", "draft", "old-story", "new-story", id="story"),
        pytest.param(
            "validation-report",
            "validation-reports",
            "active",
            "0001-old",
            "0002-new",
            id="validation-report",
        ),
    ],
)
def test_reverse_gap_kind_is_stamped_on_apply(
    tmp_path: Path,
    kind: str,
    kind_dir: str,
    starting_status: str,
    old_name: str,
    new_name: str,
) -> None:
    _seed(tmp_path)
    old_id = f"{kind}:{old_name}"
    new_id = f"{kind}:{new_name}"
    old_path = _write(
        tmp_path,
        kind_dir,
        old_name,
        {"id": old_id, "kind": kind, "status": starting_status},
    )
    _write(
        tmp_path,
        kind_dir,
        new_name,
        {
            "id": new_id,
            "kind": kind,
            "status": starting_status,
            "relations": [_supersedes(old_id)],
        },
    )

    report = mark_superseded(tmp_path, apply=True)
    frontmatter = read_frontmatter(old_path)

    assert report["applied"] == [old_id]
    assert report["skipped_kinds"] == []
    assert frontmatter is not None
    assert frontmatter["status"] == "superseded"
    assert frontmatter["superseded_by"] == new_id
```

- [ ] **Step 2: Run the apply regression and capture the real RED**

Run:

```bash
cd science
uv run --frozen pytest \
  tests/test_consolidation_mark_superseded.py::test_reverse_gap_kind_is_stamped_on_apply -vv
```

Expected: exit 1. The `story` case passes. The `validation-report` case fails during apply with:

```text
1 failed, 1 passed
science_tool.entities.EntityCommandError:
Entity not found: validation-report:0001-old
```

The failure must come from `find_entity`/`resolve_entity_ref`; a collection error, an invalid
starting status, an empty `to_mark`, or a mocked lookup is the wrong RED.

- [ ] **Step 3: Add the complete validation-report write descriptor**

Replace the post-Task-2 validation-report block in
`science/model/src/science_model/profiles/core.py` with:

```python
        EntityKind(
            name="validation-report",
            canonical_prefix="validation-report",
            layer="layer/core",
            description="Report validating an analysis, model, or pipeline result.",
            entity_class=EntityClass.EPISTEMIC,
            curation_scope=CurationScope.EPISTEMIC,
            category=KindCategory.AUTHORED_CORE,
            home="entities/validation-reports",
            strategy="numeric",
            default_status="active",
            statuses=["draft", "active", "complete", "superseded", "retired", "archived"],
            supersedable=True,
        ),
```

`report` is the complete comparator: it also uses a plural Markdown home and numeric identity.
Do not add a fallback in `find_entity` and do not special-case validation reports in
`consolidation.py`; the descriptor is the missing authority.

- [ ] **Step 4: Re-run the apply regression for GREEN**

Run:

```bash
cd science
uv run --frozen pytest \
  tests/test_consolidation_mark_superseded.py::test_reverse_gap_kind_is_stamped_on_apply -vv
```

Expected: exit 0:

```text
story              PASSED
validation-report  PASSED
2 passed
```

Both cases must assert the committed `status` and derived `superseded_by`; checking only `to_mark`
would leave apply untested.

- [ ] **Step 5: Prove the frozen Markdown-policy oracle detects the descriptor change**

Before changing `FROZEN_MARKDOWN_POLICIES`, run:

```bash
cd science
uv run --frozen pytest \
  tests/test_kind_map_equivalence.py::test_markdown_policies_equal_prior_literal -vv
```

Expected: exit 1, with exactly one extra live item:

```text
validation-report: EntityPathPolicy(
    root=PosixPath("entities/validation-reports"),
    strategy="numeric",
)
```

If the test passes before re-freezing, stop: the oracle is not observing the descriptor-derived
policy.

- [ ] **Step 6: Write the ruling, then deliberately re-freeze the policy**

In `meta/doc/plans/2026-07-26-s2-lineage-capability-design.md`, immediately after the
validation-report item under “Gain the status (2)”, add:

```markdown
#### Validation-report write-path ruling

The capability is operational, not read-only: once `validation-report` is admitted and appears in
`supported_kinds`, `mark_superseded --apply` must be able to locate and rewrite the report it placed
in `to_mark`. Therefore `validation-report` also follows the established report-like Markdown
contract: `home="entities/validation-reports"` and `strategy="numeric"`, parallel to `report`'s
plural home and numeric strategy. Leaving both fields unset produces a split authority: the graph
scanner can discover and admit an authored chain, but the descriptor-derived write policy cannot
find the target. Adding this policy deliberately re-freezes `FROZEN_MARKDOWN_POLICIES`; it repairs
the S2 write path rather than weakening the oracle.
```

Then insert this exact entry after `report` in `FROZEN_MARKDOWN_POLICIES` in
`science/tests/test_kind_map_equivalence.py`:

```python
    # ☠️ DELIBERATE S2 RE-FREEZE. The validation-report ruling makes its supersedable capability
    # operational: the apply writer must find the entity that dry-run placed in `to_mark`. It uses
    # the report-like plural home and numeric strategy; this fixes that write-path gap rather than
    # accepting unexplained descriptor drift.
    "validation-report": EntityPathPolicy(Path("entities/validation-reports"), "numeric"),
```

This is the only permitted Markdown-policy re-freeze in the task. Its commit body must cite the
written ruling and say that the edit fixes the discovered write-path gap rather than silencing the
oracle.

- [ ] **Step 7: Re-run the frozen oracle for GREEN**

Run:

```bash
cd science
uv run --frozen pytest \
  tests/test_kind_map_equivalence.py::test_markdown_policies_equal_prior_literal -vv
```

Expected: exit 0, `1 passed`.

- [ ] **Step 8: Add the direct project-local inertness regression**

In `science/tests/test_decision_material.py`, add `import pytest` beside the existing third-party
imports:

```python
import pytest
import yaml
```

Then add this complete test immediately after
`test_material_carries_supported_kinds_and_digest_covers_the_policy`:

```python
def test_project_local_kind_is_neither_supported_nor_admitted_for_supersession(
    tmp_path: Path,
) -> None:
    from science_tool.consolidation import SupersessionError, mark_superseded

    (tmp_path / "science.yaml").write_text(
        "name: local-inertness\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        """\
name: local-inertness
imports:
  - core
strictness: typed-extension
entity_kinds:
  - name: project-note
    canonical_prefix: project-note
    layer: layer/local
    description: Project-local note.
    home: entities/project-notes
    strategy: numeric
    default_status: active
    statuses: [active, superseded]
    supersedable: true
relation_kinds: []
""",
        encoding="utf-8",
    )
    _write_entity(
        tmp_path,
        "project-notes",
        "0001-old",
        {"id": "project-note:0001-old", "kind": "project-note", "status": "active"},
    )
    _write_entity(
        tmp_path,
        "project-notes",
        "0002-new",
        {
            "id": "project-note:0002-new",
            "kind": "project-note",
            "status": "active",
            "relations": [_supersedes_edge("project-note:0001-old")],
        },
    )
    old_path = tmp_path / "entities" / "project-notes" / "0001-old.md"
    new_path = tmp_path / "entities" / "project-notes" / "0002-new.md"
    before = {path: path.read_bytes() for path in (old_path, new_path)}

    material = build_decision_material(tmp_path)
    report = mark_superseded(tmp_path, apply=False)

    # This is the discriminating operation-level assertion: reaching `to_mark` would require both
    # core relation admission and entry into the frozen auto-stamping policy.
    assert report["to_mark"] == []
    assert "project-note" not in material.supported_kinds
    assert material.admitted_supersedes == []
    assert [defect.code for defect in material.defects] == ["illegal-kind-pair"]
    assert [defect["code"] for defect in report["invalid_relations"]] == ["illegal-kind-pair"]

    with pytest.raises(SupersessionError, match="invalid authored relation endpoint"):
        mark_superseded(tmp_path, apply=True)
    assert {path: path.read_bytes() for path in (old_path, new_path)} == before
```

Run:

```bash
cd science
uv run --frozen pytest \
  tests/test_decision_material.py::test_project_local_kind_is_neither_supported_nor_admitted_for_supersession \
  -vv
```

Expected: exit 0, `1 passed`. This is a regression for existing inertness, not the production driver;
Step 9 proves that it discriminates the forbidden behavior.

- [ ] **Step 9: Run the two-authority project-local mutation proof and revert it**

Temporarily replace `_SELF_SUPERSEDING_KINDS` in
`science/model/src/science_model/profiles/core.py` with this mutated list:

```python
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
    "project-note",
]
```

Temporarily add this line immediately after the `DECLARED_SUPERSEDABLE` comprehension in
`science/src/science_tool/kind_descriptors.py`:

```python
DECLARED_SUPERSEDABLE["project-note"] = True
```

The first mutation admits the local endpoint through the core relation descriptor. The second puts
it in the frozen auto-stamping policy. Run:

```bash
cd science
uv run --frozen pytest \
  tests/test_decision_material.py::test_project_local_kind_is_neither_supported_nor_admitted_for_supersession \
  -vv
```

Expected: exit 1 at the first operation-level assertion:

```text
assert report["to_mark"] == []
E assert ["project-note:0001-old"] == []
```

Now restore the complete production list:

```python
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
```

and restore the map to the comprehension alone:

```python
DECLARED_SUPERSEDABLE: dict[str, bool] = {ek.name: bool(ek.supersedable) for ek in KIND_DESCRIPTORS}
```

Run:

```bash
cd science
uv run --frozen pytest \
  tests/test_decision_material.py::test_project_local_kind_is_neither_supported_nor_admitted_for_supersession \
  -vv
```

Expected: exit 0, `1 passed`.

Finally run this residue sweep from the repository root:

```bash
rg -n '"project-note"|DECLARED_SUPERSEDABLE\["project-note"\]' \
  science/model/src/science_model/profiles/core.py \
  science/src/science_tool/kind_descriptors.py
```

Expected: no matches, exit 1. Do not commit either mutation.

- [ ] **Step 10: Correct all three false project-local safety rationales**

In `science/src/science_tool/kind_descriptors.py`, replace the comment above the map with:

```python
#: Kind -> whether it may be superseded (S2). Built over `KIND_DESCRIPTORS` -- the SHIPPED
#: profiles only -- exactly like `DECLARED_STATUSES`. That population is load-bearing: a kind
#: declared in a project manifest is ABSENT here and cannot enter the frozen `supported_kinds`
#: policy. Authored `sci:supersedes` admission independently resolves against the core relation
#: descriptor, so a project-local endpoint pair is refused. The writer itself supports
#: project-local status vocabularies; inertness does not depend on a write-time failure.
DECLARED_SUPERSEDABLE: dict[str, bool] = {ek.name: bool(ek.supersedable) for ek in KIND_DESCRIPTORS}
```

In `meta/doc/plans/2026-07-26-s2-lineage-capability-design.md`, replace the project-local guarantee
paragraph under “The three derived surfaces” with:

```markdown
`DECLARED_SUPERSEDABLE` is built in `kind_descriptors.py` from `KIND_DESCRIPTORS`, mirroring
`DECLARED_STATUSES` exactly. That shape is load-bearing, not cosmetic: `KIND_DESCRIPTORS` covers the
shipped profiles only, so a kind declared in a project manifest is **absent** from the map and
cannot enter the frozen `supported_kinds` policy. Independently, authored `sci:supersedes`
admission resolves against the core profile's relation descriptor, whose endpoint pairs contain
shipped kinds only, so a project-local pair is refused before disposition. Those are the two
guarantees that keep project-local kinds inert. The write boundary is not one of them:
`_validate_status` resolves project-local vocabularies explicitly and can write a valid local
status.
```

The third stale copy is Task 4 Step 3 in this implementation plan. Its final code block must be
exactly:

```python
#: Kind -> whether it may be superseded (S2). Built over `KIND_DESCRIPTORS` -- the SHIPPED
#: profiles only -- exactly like `DECLARED_STATUSES`. That population is load-bearing: a kind
#: declared in a project manifest is ABSENT here and cannot enter the frozen `supported_kinds`
#: policy. Authored `sci:supersedes` admission independently resolves against the core relation
#: descriptor, so a project-local endpoint pair is refused. The writer itself supports
#: project-local status vocabularies; inertness does not depend on a write-time failure.
DECLARED_SUPERSEDABLE: dict[str, bool] = {ek.name: bool(ek.supersedable) for ek in KIND_DESCRIPTORS}
```

The safety claim must not mention `_validate_status` raising `KeyError`; that function explicitly
loads project-local vocabularies.

- [ ] **Step 11: Correct the stale validator-test rationale without changing behavior**

In `science/tests/validate/test_checks_materialization.py`, replace the complete workflow-run
`amends` test with:

```python
def test_amends_on_workflow_run_is_an_error(tmp_path: Path) -> None:
    """Top-level `amends:` is independently and unconditionally rejected; there are no exemptions."""
    _entity(
        tmp_path, "workflow-runs/0001-x.md",
        entity_id="workflow-run:0001-x", kind="workflow-run",
        extra="amends: workflow-run:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "sci:amends" in results[0].message
```

This is prose-only. Top-level `amends:` was already rejected unconditionally after Task 5.

- [ ] **Step 12: Run every focused post-review regression together**

Run:

```bash
cd science
uv run --frozen pytest \
  tests/test_consolidation_mark_superseded.py::test_reverse_gap_kind_is_stamped_on_apply \
  tests/test_decision_material.py::test_project_local_kind_is_neither_supported_nor_admitted_for_supersession \
  tests/test_kind_map_equivalence.py::test_markdown_policies_equal_prior_literal \
  tests/validate/test_checks_materialization.py::test_amends_on_workflow_run_is_an_error \
  -q
```

Expected: exit 0, `5 passed` (the parameterized apply test contributes two cases).

- [ ] **Step 13: Run the executable write-path parity/end-state check**

From `science/`, run:

```bash
uv run --frozen python -c "
from science_model.profiles import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
from science_tool.entities import _BUILTIN_MARKDOWN_POLICIES
from science_tool.kind_descriptors import DECLARED_SUPERSEDABLE
kinds = [*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds]
sup = {k.name for k in kinds if k.supersedable}
vocab = {k.name for k in kinds if 'superseded' in (k.statuses or ())}
rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == 'supersedes')
sources = {p.source_kind for p in rel.allowed_kind_pairs}
targets = {p.target_kind for p in rel.allowed_kind_pairs}
policy = {k for k, v in DECLARED_SUPERSEDABLE.items() if v}
missing = sorted(sup - set(_BUILTIN_MARKDOWN_POLICIES))
checks = {
    'vocabulary': vocab == sup,
    'endpoints': targets == sup,
    'policy': policy == sup,
    'write paths': not missing,
    'flat sources': set(rel.source_kinds) == sources,
    'flat targets': set(rel.target_kinds) == targets,
}
print('declared    ', len(sup))
for label, passed in checks.items():
    print(f'{label:12} {passed}')
print('missing     ', missing)
if not all(checks.values()):
    raise SystemExit('S2 end-state parity failed')
"
```

Expected: exit 0:

```text
declared     18
vocabulary   True
endpoints    True
policy       True
write paths  True
flat sources True
flat targets True
missing      []
```

Deleting either validation-report layout field makes `_BUILTIN_MARKDOWN_POLICIES` omit the kind,
prints `write paths  False` and `missing      ['validation-report']`, and exits nonzero. This is the
final check the pre-review plan lacked.

- [ ] **Step 14: Run full verification serially**

Run each command only after the previous one exits:

```bash
cd science/model
uv run --frozen pytest -q
```

Expected: exit 0, `1448 passed`.

```bash
cd science
uv run --frozen pytest -q
```

Expected: exit 0, `10698 passed, 7 skipped, 8 deselected`. Existing third-party deprecation warnings
may still be summarized.

```bash
cd science
uv run ruff check
```

Expected: exit 0, `All checks passed!`.

```bash
cd science
uv run pyright
```

Expected: exit 0, `0 errors, 0 warnings, 0 informations`.

From the repository root:

```bash
git diff --check
```

Expected: exit 0 with no output.

- [ ] **Step 15: Commit the post-review correction**

```bash
git add meta/doc/plans/2026-07-26-s2-lineage-capability-design.md \
        docs/plans/2026-07-26-s2-lineage-capability-implementation-plan.md \
        science/model/src/science_model/profiles/core.py \
        science/src/science_tool/kind_descriptors.py \
        science/tests/test_consolidation_mark_superseded.py \
        science/tests/test_decision_material.py \
        science/tests/test_kind_map_equivalence.py \
        science/tests/validate/test_checks_materialization.py
git commit \
  -m 'fix(consolidation): make validation reports writable' \
  -m 'Apply the written S2 validation-report write-path ruling with the report-like Markdown home and numeric strategy.' \
  -m 'Re-freeze FROZEN_MARKDOWN_POLICIES to close the reproduced dry-run/apply lookup gap, not to silence unexplained oracle drift.'
```

Expected: a conventional commit with no attribution trailer. The two temporary project-local
mutation edits must be absent from the staged diff.

---

## Verification

After Task 6, from a clean tree on the branch, first run the focused runtime/oracle regressions:

```bash
cd science
uv run --frozen pytest \
  tests/test_consolidation_mark_superseded.py::test_reverse_gap_kind_is_stamped_on_apply \
  tests/test_decision_material.py::test_project_local_kind_is_neither_supported_nor_admitted_for_supersession \
  tests/test_kind_map_equivalence.py::test_markdown_policies_equal_prior_literal \
  tests/validate/test_checks_materialization.py::test_amends_on_workflow_run_is_an_error \
  -q
```

Expected: exit 0, `5 passed`.

Then run the full suites serially, followed by lint and types:

```bash
cd science/model
uv run --frozen pytest -q

cd science
uv run --frozen pytest -q

cd science
uv run ruff check

cd science
uv run pyright
```

Expected: both suites, Ruff, and Pyright exit 0. Never run the two pytest suites concurrently.

Finally confirm the complete end state, including the descriptor-derived write policy:

```bash
cd science
uv run --frozen python -c "
from science_model.profiles import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
from science_tool.entities import _BUILTIN_MARKDOWN_POLICIES
from science_tool.kind_descriptors import DECLARED_SUPERSEDABLE
kinds = [*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds]
sup = {k.name for k in kinds if k.supersedable}
vocab = {k.name for k in kinds if 'superseded' in (k.statuses or ())}
rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == 'supersedes')
sources = {p.source_kind for p in rel.allowed_kind_pairs}
targets = {p.target_kind for p in rel.allowed_kind_pairs}
policy = {k for k, v in DECLARED_SUPERSEDABLE.items() if v}
missing = sorted(sup - set(_BUILTIN_MARKDOWN_POLICIES))
checks = {
    'vocabulary': vocab == sup,
    'endpoints': targets == sup,
    'policy': policy == sup,
    'write paths': not missing,
    'flat sources': set(rel.source_kinds) == sources,
    'flat targets': set(rel.target_kinds) == targets,
}
print('declared    ', len(sup))
for label, passed in checks.items():
    print(f'{label:12} {passed}')
print('missing     ', missing)
if not all(checks.values()):
    raise SystemExit('S2 end-state parity failed')
"
```

Expected:

```
declared     18
vocabulary   True
endpoints    True
policy       True
write paths  True
flat sources True
flat targets True
missing      []
```

The command must exit nonzero if any printed invariant is false. In particular, removing
`validation-report.home` or `.strategy` must print
`missing      ['validation-report']` and fail, so this plan cannot report a successful end state
while preserving the dry-run/apply gap.
