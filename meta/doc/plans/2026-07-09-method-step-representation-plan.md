# Coherent Method and Step Representation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `method` and `workflow-step` typed entity classes, make `workflow-step` definition-only, and materialize the already-declared `workflow-run --sci:executes--> workflow` edge, so that Spec 1 (stochasticity) and Spec 2 (run-observed seeds) have a coherent surface to build on.

**Architecture:** Purely representational. Two new Pydantic classes in `science-model`, registered in the tool's `CORE_KIND_MODELS`; one descriptor corrected in the `CORE_PROFILE` SSOT; one new typed field (`WorkflowRunEntity.workflow`) audited and materialized following the existing `_add_falsification_relations` loud-fail pattern; one dead relation kind (`sci:realizes`) retired; templates corrected and then frozen by a guard test.

**Tech Stack:** Python 3.11+, Pydantic v2, rdflib, click, pytest, uv. Two nested packages: `science/` (the CLI, `src/science_tool/`) and `science/model/` (`src/science_model/`).

**Task order:** 1 → 2 → 3 → 4 → 5. Task 3's guard test depends on Task 2's template fix; Task 4 depends on nothing earlier but is easier to review after 1.

## Source spec

`~/d/science/meta/doc/plans/2026-07-09-method-stochasticity-umbrella-design.md`, section "Spec 0 — Coherent method and step representation". Backlog item: `task:t087` (blocks `t079`).

## Global Constraints

- **Never open `science/src/science_tool/graph/belief.py`.** Non-goal of the umbrella and of every spec under it.
- **No AI-attribution trailer or footer** on any commit message — no `Co-Authored-By:`, no "Generated with Claude Code".
- **There is no root `pyproject.toml`.** `cd science/` before any `uv run` for CLI work; `cd science/model/` for model work. Running `uv run` from the repo root is the most common orientation mistake.
- **Behavior-neutral.** Spec 0 adds no new validation gate and no new user-visible warning beyond what a corrected template implies. The one intended behavior change is that `sci:executes` triples now appear in `graph.trig` when a run declares `workflow:`.
- **`workflow-run` entity population is zero** across every project on this machine. Nothing migrates. Do not write a migration, a shim, or a compatibility layer.
- **Composition over inheritance; explicit over defensive; fail early, never silently fall back.** No `legacy`/`compatibility` layers. No `Unified` prefix on component names.
- **Ruff line length is 120** in every package. Run `uv run ruff check` from the package you changed.
- Pyright is configured once, at `pyrightconfig.json` in the repo root; it covers `science/src`, `science/model/src`, `science/qa/src`. Run `uv run pyright` from `science/`.
- Docs and code comments use `~/d/…` paths, never `/home/keith/…` or `/mnt/ssd/Dropbox/…`.
- Full suite, run from `science/`: `uv run --frozen pytest`. Expected baseline before you start: **7728 passed**. `addopts` already contains `-q`; do **not** pass another `-q` (`-q -q` suppresses the summary line).

## Two rulings that bind Task 4 — read before implementing it

Both were raised against the spec and **decided by the human partner**. They are settled. Do not reopen either, and do not "restore" what the spec's older wording asked for. The umbrella design was amended to match (`2026-07-09-method-stochasticity-umbrella-design.md`).

**1. The `sci:executes` resolution guard lives in the compiler only.** It is a hard `ValueError` in the materializer, exactly like `_add_falsification_relations`. Do **not** add a second check in `graph/store/validation.py`. The compiler is the boundary where an authored ref becomes graph structure, so that is the contract point. A post-hoc graph check would re-read `graph.trig` to assert what the compiler had just refused to emit; it would only protect against out-of-band mutation of `graph.trig`, which does not justify a second validation surface.

**2. `WorkflowRunEntity.workflow` is optional (`str = ""`), not required.** `str = ""` is the neutral shape: it preserves the existing `materialized_knowledge_for_run` fixture (`science/tests/conftest.py:342-350`, which writes a run with no `workflow:`) and already-authored runs, while a value that is *present but unresolvable* fails loudly at materialization and audit. Requiring the field belongs to Spec 2's `register-run`, where deriving `seed_policy` actually depends on run → workflow → steps. Spec 0 is behavior-neutral.

## Facts established by reading the code (do not re-derive)

- `MethodEntity` and `WorkflowStepEntity` **do not exist**. `method` and `workflow-step` are `EntityKind` descriptors that resolve to bare `ProjectEntity`, so every field their templates declare (`workflow`, `rule_name`) is **silently dropped** at load — `Entity` does not set `extra="forbid"`, so unknown frontmatter keys are ignored, not rejected.
- The graph loader resolves a class via `registry.resolve(kind)` then calls `schema.model_validate(raw)` (`science/src/science_tool/graph/sources.py:359,376`). `CORE_KIND_MODELS` (`science/src/science_tool/graph/entity_registry.py:56-74`) is the **only** place a kind is bound to a class; kinds absent from it default to `ProjectEntity`. This is the wiring point.
- `science_model/frontmatter.py` has a **separate**, kind-dispatched constructor (`entity_from_frontmatter`). It has a `WORKFLOW` branch but **no `workflow-run` branch**. Since `WorkflowRunEntity` works fine today through the registry path, **do not touch `frontmatter.py`** in this plan.
- `MethodEntity` will be an **empty subclass** in this task. `templates/method.md` declares `datasets: []`, but `datasets: list[str] | None = None` already exists on base `Entity` (`entities.py:332`), so `method` implies no new field until Spec 1 adds `stochasticity`. An empty typed subclass has precedent: `ResearchPackageEntity` (`entities.py:915-918`) is `pass`.
- `sci:executes` (`source_kinds=["workflow-run"], target_kinds=["workflow"]`) is declared at `core.py:661-668` and materialized **nowhere**. `WorkflowRunEntity` (`entities.py:896-906`) carries only `manifest_path`, `resources`, `fingerprint`.
- **`workflow` is already an authored, de-facto-required field on workflow-run frontmatter.** `templates/workflow-run.md:6` declares it, and `science/src/science_tool/qa_audit/runs.py:26-40` errors with `"missing 'workflow'"` when it is absent. The typed model simply never learned about it. That template line's trailing comment — `# materializes the executes link the audit walks` — is **false today** and becomes true in Task 4.
- `sci:realizes` appears in exactly two live places: the `RelationKind` at `core.py:645-652`, and two entries in `PREDICATE_ROLE` at `science/src/science_tool/labnote_export.py:195-196`. All other hits are historical design docs. Unknown predicates degrade safely: `_role_for_predicate` (`labnote_export.py:694-703`) returns `("related", False)` and appends a warning. Nothing tests `PREDICATE_ROLE` against the profile.
- `test_kind_map_equivalence.py` holds **frozen literal** copies of the kind maps. `workflow-step` appears at lines 60, 98, 136, 243. Changing the descriptor's `default_status`/`statuses` **will** fail lines 98 and 136 until you update them. This is the reconciliation gate working as designed, not a bug.
- Of the 10 hand-copied (`template_ready=False`) templates, exactly **two** violate their descriptor today: `workflow-step.md` (id prefix `step:` ≠ `workflow-step:`; status `planned` ∉ `{pending,running,complete,failed}`) and `bias-audit.md` (status `proposed` ∉ `{active,superseded,retired,archived}`). Task 3 fixes both and freezes the contract.
- **Do not touch `science/src/science_tool/validate/checks/id_prefixes.py`.** The `PREFIX_RULES` dict at the top of that file lives inside a raw module docstring — a fossil of the retired bash validator. It is not code. The live `prefix_rules()` derives from `markdown_entity_kinds()` and already emits 34 rules covering `workflow`, `workflow-run`, `workflow-step`, and `method`.

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `science/model/src/science_model/entities.py` | `MethodEntity`, `WorkflowStepEntity`, `WorkflowRunEntity.workflow` | 1, 4 |
| `science/src/science_tool/graph/entity_registry.py` | bind the two new kinds to their classes | 1 |
| `science/model/src/science_model/profiles/core.py` | `workflow-step` descriptor; retire `realizes` | 2, 5 |
| `science/tests/test_kind_map_equivalence.py` | frozen literals — reconciliation gate | 2 |
| `templates/workflow-step.md` | definition-only step template | 2 |
| `templates/bias-audit.md` | status fix demanded by the new guard | 3 |
| `science/tests/test_template_descriptor_contract.py` | **new** — freeze template↔descriptor agreement | 3 |
| `science/src/science_tool/graph/migrate.py` | audit the `workflow` reference | 4 |
| `science/src/science_tool/graph/materialize.py` | emit `sci:executes` | 4 |
| `templates/workflow-run.md` | canonical ref form; comment becomes true | 4 |
| `science/src/science_tool/labnote_export.py` | drop `sci:realizes` rows | 5 |
| `templates/workflow.md` | delete inert `method:` field | 5 |
| `templates/method.md` | reword misleading illustrative `id:` line | 5 |

---

### Task 1: Typed `MethodEntity` and `WorkflowStepEntity`

**Files:**
- Modify: `science/model/src/science_model/entities.py` (after `WorkflowEntity`, ~line 913)
- Modify: `science/src/science_tool/graph/entity_registry.py:15-33` (imports), `:56-74` (`CORE_KIND_MODELS`)
- Test: `science/model/tests/test_method_step_entities.py` (create)
- Test: `science/tests/test_entity_registry_method_step.py` (create)

**Interfaces:**
- Consumes: `ProjectEntity` from `science_model.entities`.
- Produces: `MethodEntity` (no new fields); `WorkflowStepEntity(workflow: str = "", rule_name: str = "")`. Task 2 relies on `WorkflowStepEntity` existing; Spec 1 adds `stochasticity`/`seed_params` to `MethodEntity` and `method`/`seed_bindings` to `WorkflowStepEntity`.

Both classes are constructed by `schema.model_validate(raw)` in the graph loader, so every required base field (`id`, `kind`, `title`, `project`, `ontology_terms`, `related`, `source_refs`) must be supplied in tests.

- [ ] **Step 1: Write the failing model test**

Create `science/model/tests/test_method_step_entities.py`:

```python
"""Typed method / workflow-step entities (umbrella Spec 0, task:t087)."""

from science_model.entities import MethodEntity, ProjectEntity, WorkflowStepEntity


def _base(**overrides) -> dict:
    fields = {
        "id": "workflow-step:cluster",
        "kind": "workflow-step",
        "title": "Cluster",
        "project": "demo",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
    }
    fields.update(overrides)
    return fields


def test_workflow_step_retains_workflow_and_rule_name() -> None:
    step = WorkflowStepEntity.model_validate(
        _base(workflow="workflow:scrna-pipeline", rule_name="cluster")
    )
    assert step.workflow == "workflow:scrna-pipeline"
    assert step.rule_name == "cluster"


def test_workflow_step_fields_default_to_empty() -> None:
    step = WorkflowStepEntity.model_validate(_base())
    assert step.workflow == ""
    assert step.rule_name == ""


def test_method_entity_is_a_project_entity() -> None:
    method = MethodEntity.model_validate(
        _base(id="method:leiden", kind="method", title="Leiden")
    )
    assert isinstance(method, ProjectEntity)
    assert method.canonical_id == ""


def test_bare_project_entity_still_drops_step_fields() -> None:
    """Guards the motivation: the base class silently ignores these keys."""
    entity = ProjectEntity.model_validate(_base(workflow="workflow:x", rule_name="cluster"))
    assert not hasattr(entity, "rule_name")
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd science/model && uv run --frozen pytest tests/test_method_step_entities.py -v
```

Expected: collection error — `ImportError: cannot import name 'MethodEntity' from 'science_model.entities'`.

- [ ] **Step 3: Add the two classes**

In `science/model/src/science_model/entities.py`, immediately after the `WorkflowEntity` class (which ends with `outputs: list[WorkflowOutput] = Field(default_factory=list)`) and before `class ResearchPackageEntity`:

```python
class MethodEntity(ProjectEntity):
    """Analytical method or computational approach.

    Carries no fields beyond ProjectEntity today: `templates/method.md`'s only
    non-base key is `datasets`, which base Entity already declares. Spec 1 adds
    `stochasticity` and `seed_params` here — the class exists now so that the
    kind is bound to a real schema rather than to bare ProjectEntity.
    """


class WorkflowStepEntity(ProjectEntity):
    """One step of a workflow *definition* (not of a run).

    `workflow` names the owning workflow; `rule_name` names the snakemake rule
    that executes the step. Both were declared by the template and silently
    dropped at load until this class existed.
    """

    workflow: str = ""
    rule_name: str = ""
```

- [ ] **Step 4: Run the model test — it passes**

```bash
cd science/model && uv run --frozen pytest tests/test_method_step_entities.py -v
```

Expected: `4 passed`.

- [ ] **Step 5: Write the failing registry test**

Create `science/tests/test_entity_registry_method_step.py`:

```python
"""method / workflow-step resolve to typed classes (umbrella Spec 0, task:t087)."""

from science_model.entities import MethodEntity, ProjectEntity, WorkflowStepEntity

from science_tool.graph.entity_registry import EntityRegistry


def test_method_resolves_to_method_entity() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("method") is MethodEntity


def test_workflow_step_resolves_to_workflow_step_entity() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("workflow-step") is WorkflowStepEntity


def test_workflow_still_resolves_to_project_entity() -> None:
    """`workflow` has a WorkflowEntity in the model, but is deliberately NOT bound
    in CORE_KIND_MODELS; binding it is out of scope for Spec 0."""
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("workflow") is ProjectEntity
```

- [ ] **Step 6: Run it and watch it fail**

```bash
cd science && uv run --frozen pytest tests/test_entity_registry_method_step.py -v
```

Expected: 2 failures — `assert ProjectEntity is MethodEntity` and the `workflow-step` equivalent. The third test passes already.

- [ ] **Step 7: Register both kinds**

In `science/src/science_tool/graph/entity_registry.py`, add to the `from science_model.entities import (...)` block, preserving alphabetical order — `MechanismEntity`, then `MethodEntity`, then `PaperEntity`; and `TaskEntity`, `ThemeEntity`, `WorkflowRunEntity`, then `WorkflowStepEntity`:

```python
    MechanismEntity,
    MethodEntity,
    PaperEntity,
```

```python
    WorkflowRunEntity,
    WorkflowStepEntity,
```

Then, in `CORE_KIND_MODELS`, add two entries after `"workflow-run": WorkflowRunEntity,`:

```python
    "workflow-run": WorkflowRunEntity,
    "workflow-step": WorkflowStepEntity,
    "method": MethodEntity,
```

- [ ] **Step 8: Run both test files — all pass**

```bash
cd science && uv run --frozen pytest tests/test_entity_registry_method_step.py -v
cd science/model && uv run --frozen pytest tests/test_method_step_entities.py -v
```

Expected: `3 passed` and `4 passed`.

- [ ] **Step 9: Confirm the reconciliation gate and full suite are still green**

```bash
cd science && uv run --frozen pytest tests/test_kind_map_equivalence.py tests/test_kind_class.py -v
cd science && uv run --frozen pytest
```

Expected: the two files pass; the full run reports `7728 passed`. If the count differs from the baseline by anything other than the 7 tests you just added, stop and report — you have changed behavior.

- [ ] **Step 10: Lint and typecheck**

```bash
cd science && uv run ruff check && uv run pyright
cd science/model && uv run ruff check
```

Expected: `All checks passed!` and pyright `0 errors`.

- [ ] **Step 11: Commit**

```bash
git add science/model/src/science_model/entities.py \
        science/model/tests/test_method_step_entities.py \
        science/src/science_tool/graph/entity_registry.py \
        science/tests/test_entity_registry_method_step.py
git commit -m "Add typed MethodEntity and WorkflowStepEntity

Both kinds resolved to bare ProjectEntity, so the workflow and rule_name
keys their template declares were silently dropped at load."
```

---

### Task 2: `workflow-step` becomes definition-only

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py:518-528`
- Modify: `science/tests/test_kind_map_equivalence.py:98`, `:136`
- Modify: `templates/workflow-step.md`
- Test: `science/model/tests/test_workflow_step_descriptor.py` (create)

**Interfaces:**
- Consumes: nothing from Task 1 at runtime; the descriptor change is independent.
- Produces: `workflow-step` descriptor with `default_status="active"` and `statuses=["active", "superseded", "retired"]`. Task 3's guard test reads these.

The step's statuses today (`pending`/`running`/`complete`/`failed`) are **execution** states on what the umbrella makes a plan-time record. The definition lifecycle replaces them. This mirrors the `workflow` vs `workflow-run` split `t077` already performed one level up.

Note `archived` is deliberately **absent**: it is a consolidation-tier status, and no archive tooling targets `workflow-step`. Do not add it speculatively.

- [ ] **Step 1: Write the failing descriptor test**

Create `science/model/tests/test_workflow_step_descriptor.py`:

```python
"""workflow-step is a definition, not an execution (umbrella Spec 0, task:t087)."""

from science_model.profiles.core import CORE_PROFILE

_STEP = next(ek for ek in CORE_PROFILE.entity_kinds if ek.name == "workflow-step")


def test_statuses_are_the_definition_lifecycle() -> None:
    assert list(_STEP.statuses) == ["active", "superseded", "retired"]


def test_default_status_is_active() -> None:
    assert _STEP.default_status == "active"


def test_no_execution_states_remain() -> None:
    assert not {"pending", "running", "complete", "failed"} & set(_STEP.statuses)


def test_description_does_not_claim_to_cover_runs() -> None:
    assert "run" not in _STEP.description.lower()
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd science/model && uv run --frozen pytest tests/test_workflow_step_descriptor.py -v
```

Expected: all four fail — statuses are still `['pending', 'running', 'complete', 'failed']`, default is `'pending'`, and the description reads "Individual step within a workflow definition or run."

- [ ] **Step 3: Correct the descriptor**

In `science/model/src/science_model/profiles/core.py`, replace the `workflow-step` `EntityKind` block (currently lines 518-528):

```python
        EntityKind(
            name="workflow-step",
            canonical_prefix="workflow-step",
            layer="layer/core",
            description="Individual step within a workflow definition.",
            entity_class=EntityClass.OPERATIONAL,
            category=KindCategory.AUTHORED_CORE,
            home="entities/workflow-steps",
            strategy="id-local",
            default_status="active",
            statuses=["active", "superseded", "retired"],
        ),
```

- [ ] **Step 4: Run the descriptor test — it passes; the gate now fails**

```bash
cd science/model && uv run --frozen pytest tests/test_workflow_step_descriptor.py -v
cd science && uv run --frozen pytest tests/test_kind_map_equivalence.py -v
```

Expected: `4 passed`, then **2 failures** in `test_default_status_equals_prior_literal` and `test_status_values_equal_prior_literal`. That is the reconciliation gate doing its job — the frozen literals must be updated deliberately, not automatically.

- [ ] **Step 5: Update the frozen literals**

In `science/tests/test_kind_map_equivalence.py`, line 98, inside the default-status map:

```python
    "workflow-step": "active",
```

and line 136, inside the status-values map:

```python
    "workflow-step": frozenset({"active", "superseded", "retired"}),
```

Leave lines 60 (`EntityPathPolicy(Path("entities/workflow-steps"), "id-local")`) and 243 (`"operational"`) untouched — neither changes.

- [ ] **Step 6: Run the gate — it passes**

```bash
cd science && uv run --frozen pytest tests/test_kind_map_equivalence.py -v
```

Expected: all pass.

- [ ] **Step 7: Rewrite the step template as definition-only**

Replace the **frontmatter block** of `templates/workflow-step.md` (everything between the two `---` lines) with:

```yaml
id: "workflow-step:<slug>"
kind: "workflow-step"
title: "<Step Name>"
status: "active"
workflow: "workflow:<slug>"
inquiry: "inquiry:<slug>"
rule_name: "<snakemake-rule-name>"
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
```

Three changes: `id` now uses the canonical `workflow-step:` prefix; `status` is a real member of the kind's status set; the `run:` key is **deleted** — a step definition does not belong to one execution. `workflow` and `inquiry` now carry canonical `<kind>:<slug>` refs rather than bare slugs.

Then, in the same file's `## Related` section, delete the `**Run:**` bullet and correct the step refs:

```markdown
## Related

- **Workflow:** `workflow:<slug>`
- **Inquiry:** `inquiry:<slug>`
- **Upstream:** `workflow-step:<slug>`
- **Downstream:** `workflow-step:<slug>`
```

- [ ] **Step 8: Verify no `step:` or `run:` residue remains in the template**

```bash
cd ~/d/science && grep -n 'step:<slug>\|^run:\|\*\*Run:\*\*' templates/workflow-step.md; echo "exit=$?"
```

Expected: no matching lines, `exit=1`. (`grep` exits 1 when it finds nothing — that is success here.)

- [ ] **Step 9: Full suite**

```bash
cd science && uv run --frozen pytest
```

Expected: `7728 passed` plus the tests added in Tasks 1-2. Any *failure* means a surface you have not accounted for reads the old statuses — report it rather than editing the surface.

- [ ] **Step 10: Commit**

```bash
git add science/model/src/science_model/profiles/core.py \
        science/model/tests/test_workflow_step_descriptor.py \
        science/tests/test_kind_map_equivalence.py \
        templates/workflow-step.md
git commit -m "Make workflow-step a definition, not an execution

Statuses become the definition lifecycle; the run: key leaves the template.
This is the definition/execution split t077 made for workflow vs
workflow-run, applied one level down."
```

---

### Task 3: Freeze the template↔descriptor contract

**Files:**
- Test: `science/tests/test_template_descriptor_contract.py` (create)
- Modify: `templates/bias-audit.md` (frontmatter `status`)

**Interfaces:**
- Consumes: the corrected `workflow-step` descriptor and template from Task 2.
- Produces: a guard test. Nothing depends on it.

Templates for `template_ready=False` kinds are **hand-copied** by authors: the literal `id:` and `status:` lines are what ends up in a real entity file. Templates for `template_ready=True` kinds are rendered by `Renderer` from their `_template` block, so their literal lines are inert illustration (`templates/method.md`'s `id: "method:{{nn}}-{{slug}}"` renders as `id: method:leiden`). **The guard must therefore apply only to `template_ready=False` kinds.** Applying it to rendered templates would produce false failures and invite someone to "fix" a correct file.

A survey of the 10 hand-copied templates found exactly two violations: `workflow-step.md` (fixed in Task 2) and `bias-audit.md`, whose `status: "proposed"` is not among the `report` kind's statuses (`active`/`superseded`/`retired`/`archived`). Fixing `bias-audit.md` is the cost of admission for the guard.

Kinds whose `statuses` list is **empty** are unconstrained — do not treat an empty list as "nothing is allowed". `experiment` and `research-package` are both in this state and must keep passing.

- [ ] **Step 1: Write the guard test**

Create `science/tests/test_template_descriptor_contract.py`:

```python
"""Hand-copied templates must agree with their kind descriptor (task:t087).

`template_ready=True` kinds are rendered by Renderer from their `_template`
block, so their literal `id:`/`status:` lines are illustration and are excluded.
For `template_ready=False` kinds the literal lines are what an author copies,
so a wrong prefix or an undeclared status becomes a wrong entity file.
"""

import re
from pathlib import Path

import pytest
from science_model.profiles.core import CORE_PROFILE

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
_KINDS = {ek.name: ek for ek in CORE_PROFILE.entity_kinds}


def _frontmatter_value(text: str, key: str) -> str | None:
    match = re.search(rf'^{key}:\s*"?([^"\n#]+?)"?\s*(?:#.*)?$', text, re.MULTILINE)
    return match.group(1) if match else None


def _hand_copied_templates() -> list[tuple[Path, str]]:
    found = []
    for path in sorted(TEMPLATES_DIR.glob("*.md")):
        kind = _frontmatter_value(path.read_text(encoding="utf-8"), "kind")
        descriptor = _KINDS.get(kind or "")
        if descriptor is not None and not descriptor.template_ready:
            found.append((path, kind))
    return found


def test_survey_found_the_expected_hand_copied_templates() -> None:
    """Pins the sample size, so a template that stops declaring `kind` is noticed."""
    assert len(_hand_copied_templates()) == 10


@pytest.mark.parametrize("path,kind", _hand_copied_templates(), ids=lambda v: getattr(v, "name", v))
def test_template_id_uses_the_canonical_prefix(path: Path, kind: str) -> None:
    declared = _frontmatter_value(path.read_text(encoding="utf-8"), "id")
    prefix = _KINDS[kind].canonical_prefix
    assert declared is not None, f"{path.name} declares no id:"
    assert declared.startswith(f"{prefix}:"), f"{path.name}: id {declared!r} does not start with {prefix!r}:"


@pytest.mark.parametrize("path,kind", _hand_copied_templates(), ids=lambda v: getattr(v, "name", v))
def test_template_status_is_declared_by_the_kind(path: Path, kind: str) -> None:
    declared = _frontmatter_value(path.read_text(encoding="utf-8"), "status")
    statuses = _KINDS[kind].statuses
    if declared is None or not statuses:
        pytest.skip(f"{path.name}: no status line, or kind declares no status vocabulary")
    assert declared in statuses, f"{path.name}: status {declared!r} not in {list(statuses)}"
```

- [ ] **Step 2: Run it and watch exactly one failure**

```bash
cd science && uv run --frozen pytest tests/test_template_descriptor_contract.py -v
```

Expected: `test_template_status_is_declared_by_the_kind[bias-audit.md]` **fails** with `status 'proposed' not in ['active', 'superseded', 'retired', 'archived']`. Everything else passes — including both `workflow-step.md` cases, because Task 2 already fixed them.

If a `workflow-step.md` case fails here, Task 2 is incomplete; go back rather than weakening the guard.

- [ ] **Step 3: Fix the one real violation**

In `templates/bias-audit.md`, change the frontmatter status line:

```yaml
status: "active"
```

- [ ] **Step 4: Run the guard — all green**

```bash
cd science && uv run --frozen pytest tests/test_template_descriptor_contract.py -v
```

Expected exactly: **`19 passed, 2 skipped`** — 1 survey test, 10 id tests, and 8 status tests. The 2 skips are `experiment.md` and `research-package.md`, whose kinds declare an empty `statuses` list and are therefore unconstrained. A third skip means a template lost its `status:` line; zero skips means the skip condition is wrong.

- [ ] **Step 5: Lint and commit**

```bash
cd science && uv run ruff check
git add science/tests/test_template_descriptor_contract.py templates/bias-audit.md
git commit -m "Freeze the hand-copied template / descriptor contract

Rendered (template_ready) kinds are excluded: their literal id lines are
illustration. Fixes bias-audit's undeclared 'proposed' status, the one
violation the guard surfaced beyond workflow-step."
```

---

### Task 4: `WorkflowRunEntity.workflow` and the `sci:executes` edge

**Files:**
- Modify: `science/model/src/science_model/entities.py:896-906` (`WorkflowRunEntity`)
- Modify: `science/src/science_tool/graph/migrate.py` (inside `_audit_entity`, after the `blocked_by` loop at ~line 316)
- Modify: `science/src/science_tool/graph/materialize.py` (`_add_relations` at ~line 732; new helper near `_add_run_ref_edges` at ~line 1072)
- Modify: `templates/workflow-run.md:6`
- Test: `science/tests/test_materialize_run_executes.py` (create)

**Interfaces:**
- Consumes: `WorkflowRunEntity` (existing), `ReferenceResolver.resolve(raw)` → object with `.status` (`"resolved"` or not) and `.canonical_id: str | None`, `_entity_uri(canonical_id) -> URIRef`, `SCI_NS`.
- Produces: `WorkflowRunEntity.workflow: str = ""`; the triple `<run> sci:executes <workflow>` in the knowledge graph. Spec 2's `register-run` traverses this field.

The `workflow` field is **optional** — see "Deviations" above. When it is empty, no edge is emitted. When it is non-empty and does not resolve to a `workflow` entity, materialization **raises**, exactly as `_add_falsification_relations` does for a dangling `falsifies` target. Silent skipping would let a typo delete a provenance edge.

- [ ] **Step 1: Write the failing materialization test**

Create `science/tests/test_materialize_run_executes.py`:

```python
"""workflow-run --sci:executes--> workflow (umbrella Spec 0, task:t087)."""

from pathlib import Path

import pytest
from rdflib import Dataset

from science_tool.graph.io import PROJECT_NS, SCI_NS, entity_uri_for_ref
from science_tool.graph.materialize import materialize_graph


def _project(root: Path, *, run_workflow: str | None) -> Path:
    (root / "science.yaml").write_text(
        "name: executes-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    workflows = root / "entities" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / "scrna-pipeline.md").write_text(
        "---\nid: workflow:scrna-pipeline\nkind: workflow\ntitle: scRNA pipeline\n---\n",
        encoding="utf-8",
    )
    runs = root / "entities" / "workflow-runs"
    runs.mkdir(parents=True, exist_ok=True)
    workflow_line = f"workflow: {run_workflow}\n" if run_workflow is not None else ""
    (runs / "r1.md").write_text(
        f"---\nid: workflow-run:r1\nkind: workflow-run\ntitle: R1\n{workflow_line}---\n",
        encoding="utf-8",
    )
    return root


def _knowledge(trig_path: Path):
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    return dataset.graph(PROJECT_NS["graph/knowledge"])


def test_run_declaring_a_workflow_emits_executes(tmp_path: Path) -> None:
    trig_path = materialize_graph(_project(tmp_path, run_workflow="workflow:scrna-pipeline"))
    knowledge = _knowledge(trig_path)
    run_uri = entity_uri_for_ref("workflow-run:r1")
    assert list(knowledge.objects(run_uri, SCI_NS.executes)) == [entity_uri_for_ref("workflow:scrna-pipeline")]


def test_run_without_a_workflow_emits_no_edge(tmp_path: Path) -> None:
    trig_path = materialize_graph(_project(tmp_path, run_workflow=None))
    knowledge = _knowledge(trig_path)
    assert list(knowledge.objects(entity_uri_for_ref("workflow-run:r1"), SCI_NS.executes)) == []


def test_run_naming_a_nonexistent_workflow_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="workflow-run:r1"):
        materialize_graph(_project(tmp_path, run_workflow="workflow:does-not-exist"))


def test_run_naming_a_non_workflow_fails_loudly(tmp_path: Path) -> None:
    root = _project(tmp_path, run_workflow="workflow:scrna-pipeline")
    (root / "entities" / "workflow-runs" / "r1.md").write_text(
        "---\nid: workflow-run:r1\nkind: workflow-run\ntitle: R1\nworkflow: workflow-run:r1\n---\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="non-workflow"):
        materialize_graph(root)
```

Two URI facts this test depends on, already verified — do not re-derive, and do **not** build entity URIs by hand:

- `entity_uri_for_ref("workflow-run:r1")` → `http://example.org/project/workflow-run/r1`. The colon becomes a slash. `PROJECT_NS["workflow-run:r1"]` would produce a *different*, wrong URI.
- The knowledge named graph is `PROJECT_NS["graph/knowledge"]` (the idiom used at `science/tests/test_graph_materialize.py:201`).

Confirm before writing the file:

```bash
cd science && uv run --frozen python -c "
from science_tool.graph.io import PROJECT_NS, SCI_NS, entity_uri_for_ref
print(entity_uri_for_ref('workflow-run:r1'), SCI_NS.executes, PROJECT_NS['graph/knowledge'])"
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd science && uv run --frozen pytest tests/test_materialize_run_executes.py -v
```

Expected: `test_run_declaring_a_workflow_emits_executes` fails (`[] != [...]`), and both loud-fail tests fail (`DID NOT RAISE`). `test_run_without_a_workflow_emits_no_edge` passes vacuously.

- [ ] **Step 3: Add the typed field**

In `science/model/src/science_model/entities.py`, in `WorkflowRunEntity`, add `workflow` above `manifest_path`:

```python
class WorkflowRunEntity(ProjectEntity):
    """Workflow run — readiness is `complete` when status == 'complete'."""

    # The workflow this run executed. Authored on every run today (the template
    # declares it and `science qa-audit` errors without it); it was simply never
    # typed, so `sci:executes` could not be materialized. Optional here: Spec 2's
    # register-run is what refuses a run that cannot name its workflow.
    workflow: str = ""
    manifest_path: str = ""
    resources: list[dict[str, Any]] = Field(default_factory=list)
    fingerprint: RunFingerprint | None = None
```

- [ ] **Step 4: Emit the edge**

In `science/src/science_tool/graph/materialize.py`, add this helper immediately before `def _add_run_ref_edges(` (~line 1072):

```python
def _add_executes_edge(
    entity: WorkflowRunEntity,
    run_uri: URIRef,
    *,
    entity_index: dict[str, Entity],
    resolver: ReferenceResolver,
    knowledge,
) -> None:
    """Emit sci:executes for a run that names the workflow it executed.

    A run that names no workflow emits no edge (Spec 2's register-run is the
    gate). A run that names one it cannot resolve is a hard error: silently
    dropping the edge would delete provenance on a typo.
    """
    if not entity.workflow:
        return
    resolution = resolver.resolve(entity.workflow)
    if resolution.status != "resolved" or resolution.canonical_id is None:
        raise ValueError(
            f"{entity.canonical_id} executes {entity.workflow!r}, which does not resolve "
            "to a known entity; a run's workflow must resolve to a workflow."
        )
    target = entity_index.get(resolution.canonical_id)
    if target is None or target.kind != "workflow":
        raise ValueError(
            f"{entity.canonical_id} executes {resolution.canonical_id!r}, which resolved to a "
            "non-workflow entity; a run's workflow must name a workflow."
        )
    knowledge.add((run_uri, SCI_NS.executes, _entity_uri(resolution.canonical_id)))
```

The second message carries the literal substring `non-workflow`, which `test_run_naming_a_non_workflow_fails_loudly` matches on. If you reword it, update the test's `match=` in the same edit.

Then call it from `_add_relations`, immediately after the `FalsificationEntity` block (~line 739):

```python
    if isinstance(entity, WorkflowRunEntity):
        _add_executes_edge(
            entity,
            entity_uri,
            entity_index=entity_index,
            resolver=resolver,
            knowledge=knowledge,
        )
```

`WorkflowRunEntity` is already imported at `materialize.py:16`. Confirm `ReferenceResolver` and `URIRef` are already imported in that module before relying on them:

```bash
cd science && grep -n "^from\|^import" src/science_tool/graph/materialize.py | grep -i "referenceresolver\|rdflib"
```

- [ ] **Step 5: Run the test — all four pass**

```bash
cd science && uv run --frozen pytest tests/test_materialize_run_executes.py -v
```

Expected: `4 passed`. If `test_run_naming_a_nonexistent_workflow_fails_loudly` instead fails with `Cannot materialize graph with unresolved references`, that is the **audit phase** raising before your helper does. That is an acceptable outcome only if the message names `workflow-run:r1` — the `pytest.raises(match=...)` will tell you. Do not loosen the match; if the audit gets there first, keep both guards and note it in your report.

- [ ] **Step 6: Audit the new reference**

An unresolved `workflow` must appear in `science graph audit` as a `fail` row, not only as a materialize crash. `_audit_entity` receives a bare `Entity`, so reach the field with `getattr` and a default — the established idiom in this function (see the `blocked_by` comment at line 315).

In `science/src/science_tool/graph/migrate.py`, inside `_audit_entity`, immediately after the `blocked_by` loop (~line 319):

```python
    # `workflow` lives on WorkflowRunEntity; getattr mirrors `blocked_by` above.
    workflow_ref = getattr(entity, "workflow", "")
    if workflow_ref:
        rows.extend(_audit_reference(entity, "workflow", workflow_ref, resolver, ext_prefixes=ext_prefixes))
```

- [ ] **Step 7: Verify the audit row appears**

```bash
cd science && uv run --frozen python - <<'PY'
import tempfile, pathlib
from science_tool.graph.materialize import materialization_audit
root = pathlib.Path(tempfile.mkdtemp())
(root / "science.yaml").write_text("name: t\nknowledge_profiles:\n  local: local\n")
runs = root / "entities" / "workflow-runs"; runs.mkdir(parents=True)
(runs / "r1.md").write_text("---\nid: workflow-run:r1\nkind: workflow-run\ntitle: R1\nworkflow: workflow:missing\n---\n")
rows, failed = materialization_audit(root)
print("has_failures:", failed)
for r in rows:
    if r["field"] == "workflow":
        print(r)
PY
```

Expected: `has_failures: True` and one row with `field='workflow'`, `target='workflow:missing'`, `status='fail'`.

- [ ] **Step 8: Make the run template's comment true**

`templates/workflow-run.md:6` currently reads:

```yaml
workflow: "<workflow-slug>"          # materializes the executes link the audit walks
```

The comment described an edge that was never emitted, and the value is a bare slug where a canonical ref is required. Replace with:

```yaml
workflow: "workflow:<slug>"          # materializes the sci:executes edge
```

- [ ] **Step 9: Full suite, lint, typecheck**

```bash
cd science && uv run --frozen pytest
cd science && uv run ruff check && uv run pyright
cd science/model && uv run ruff check
```

Expected: full suite green. Pay attention to `tests/test_materialize_run_fingerprint.py` and anything else using the `materialized_knowledge_for_run` fixture (`science/tests/conftest.py:307`): that fixture writes a run with **no** `workflow:` key, which is why the field is optional. If those tests fail, the field was made required — revert that.

- [ ] **Step 10: Commit**

```bash
git add science/model/src/science_model/entities.py \
        science/src/science_tool/graph/migrate.py \
        science/src/science_tool/graph/materialize.py \
        science/tests/test_materialize_run_executes.py \
        templates/workflow-run.md
git commit -m "Materialize workflow-run --sci:executes--> workflow

The relation was declared in the core profile and emitted nowhere, and the
run entity had no typed workflow field, so a run could not name what it ran.
The run template already declared the key and qa-audit already required it."
```

---

### Task 5: Retire `sci:realizes` and the inert `method:` field

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py:645-652` (delete the `RelationKind`)
- Modify: `science/src/science_tool/labnote_export.py:195-196` (delete two `PREDICATE_ROLE` rows)
- Modify: `templates/workflow.md` (delete `method:` frontmatter key; fix the Steps table)
- Modify: `templates/method.md:2` (reword the illustrative `id:` line)
- Test: `science/model/tests/test_realizes_retired.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing. `sci:applies` (`workflow-step` → `method`) is **Spec 1's** to add — do not add it here.

A workflow no longer names one method; its steps each apply one. `templates/workflow.md` declares `method: "<method-slug>"`, which no model reads — an inert field. Retiring the relation is what makes the inert field go away instead of getting quietly implemented.

Unknown predicates degrade safely in the labnote exporter (`_role_for_predicate` returns `("related", False)` and warns), so removing the rows cannot crash an export of an old graph.

- [ ] **Step 1: Write the failing retirement test**

Create `science/model/tests/test_realizes_retired.py`:

```python
"""sci:realizes is retired (umbrella Spec 0, task:t087).

A workflow does not realize one method; each of its steps applies one.
Spec 1 adds sci:applies (workflow-step -> method) in its place.
"""

from science_model.profiles.core import CORE_PROFILE

_NAMES = {rk.name for rk in CORE_PROFILE.relation_kinds}
_PREDICATES = {rk.predicate for rk in CORE_PROFILE.relation_kinds}


def test_realizes_relation_kind_is_gone() -> None:
    assert "realizes" not in _NAMES
    assert "sci:realizes" not in _PREDICATES


def test_the_surviving_workflow_relations_are_untouched() -> None:
    assert {"contains", "executes", "feeds_into", "implements"} <= _NAMES


def test_applies_is_not_added_yet() -> None:
    """Spec 1 owns sci:applies; adding it here would be scope creep."""
    assert "applies" not in _NAMES
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd science/model && uv run --frozen pytest tests/test_realizes_retired.py -v
```

Expected: `test_realizes_relation_kind_is_gone` fails; the other two pass.

- [ ] **Step 3: Delete the relation kind**

In `science/model/src/science_model/profiles/core.py`, delete this entire block (currently lines 645-652):

```python
        RelationKind(
            name="realizes",
            predicate="sci:realizes",
            source_kinds=["workflow"],
            target_kinds=["method"],
            layer="layer/core",
            description="A workflow is the executable realization of a method.",
        ),
```

- [ ] **Step 4: Run the retirement test — it passes**

```bash
cd science/model && uv run --frozen pytest tests/test_realizes_retired.py -v
```

Expected: `3 passed`.

- [ ] **Step 5: Drop the exporter's predicate rows**

In `science/src/science_tool/labnote_export.py`, delete these two lines from `PREDICATE_ROLE` (currently 195-196):

```python
    "sci:realizes": ("realizes", False),
    "realizes": ("realizes", False),
```

- [ ] **Step 6: Delete the inert field from the workflow template**

In `templates/workflow.md`, delete the frontmatter line:

```yaml
method: "<method-slug>"
```

In the same file's `## Steps` table, the step refs use the retired `step:` prefix. Correct them:

```markdown
| Step | Rule | Purpose |
|------|------|---------|
| `workflow-step:<slug>` | `rule_name` | Brief description |
```

And in `## Related`, delete the `- **Method:** \`method:<slug>\`` bullet: a workflow no longer names a method. Leave the `Questions tested` and `Hypotheses tested` bullets.

- [ ] **Step 7: Reword the misleading method-template id line**

`templates/method.md` is `template_ready=True`: `Renderer` rebuilds `id` from `entity_id`, so rendering yields `id: method:leiden` and the literal line is inert illustration. It is **not** a defect — but its `{{nn}}-` prefix wrongly implies a numeric strategy for a `strategy="slug"` kind. Change line 2 only:

```yaml
id: "method:{{slug}}"
```

Leave the `_template:` block entirely alone — `id: { from: entity_id }` is what actually runs.

- [ ] **Step 8: Verify no live `realizes` reference survives**

```bash
cd ~/d/science && grep -rn "realizes" \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=knowledge \
  --exclude-dir=historical science/src science/model/src templates/
echo "exit=$?"
```

Expected: no output, `exit=1`. Hits under `docs/plans/historical/` are frozen design docs and must not be edited.

- [ ] **Step 9: Confirm the method template still renders to a canonical id**

```bash
cd science && uv run --frozen pytest tests/test_template_descriptor_contract.py -v
cd science && uv run --frozen pytest -k "method and template" -v
```

Expected: green. The contract test **skips** `method.md` (it is `template_ready=True`), which is the intended behavior — the guard covers only hand-copied templates.

- [ ] **Step 10: Full suite, lint, typecheck**

```bash
cd science && uv run --frozen pytest
cd science && uv run ruff check && uv run pyright
cd science/model && uv run --frozen pytest && uv run ruff check
```

Expected: everything green.

- [ ] **Step 11: Commit**

```bash
git add science/model/src/science_model/profiles/core.py \
        science/model/tests/test_realizes_retired.py \
        science/src/science_tool/labnote_export.py \
        templates/workflow.md templates/method.md
git commit -m "Retire sci:realizes and the inert workflow method: field

A workflow does not realize one method; each of its steps applies one.
Spec 1 adds sci:applies (workflow-step -> method) in its place."
```

---

## Done when

- `registry.resolve("method") is MethodEntity` and `registry.resolve("workflow-step") is WorkflowStepEntity`.
- `workflow-step`'s statuses are the definition lifecycle; no `run:` key remains in its template.
- Every hand-copied template's `id:` prefix and `status:` agree with its descriptor, enforced by a test.
- A `workflow-run` that names its `workflow` emits `sci:executes`; one that names a bad target fails loudly at audit and at materialization.
- `sci:realizes` exists nowhere in `science/src`, `science/model/src`, or `templates/`.
- `cd science && uv run --frozen pytest` is green, as is `cd science/model && uv run --frozen pytest`.
- `uv run ruff check` and `uv run pyright` are clean.

## Explicitly out of scope

- `sci:applies`, `method.stochasticity`, `method.seed_params`, `workflow-step.method`, `seed_bindings` — all **Spec 1** (`task:t079`).
- `RunFingerprint.step_seeds`, removing `SeedPolicy.seeds`, deriving `seed_policy` — all **Spec 2** (`task:t088`).
- Binding `workflow` to `WorkflowEntity` in `CORE_KIND_MODELS`. `WorkflowEntity` exists and is reachable only through `frontmatter.py`'s dispatch; unifying those two construction paths is a real cleanup and a separate one.
- Making the `template_ready=False` workflow kinds generator-rendered.
- `science/src/science_tool/validate/checks/id_prefixes.py` — nothing needs registering; see Facts.
- Anything touching `graph/belief.py`.
