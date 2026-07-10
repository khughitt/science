# Method Stochasticity and Step Seed Bindings — Implementation Plan (umbrella Spec 1, `task:t079`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make stochasticity a first-class, queryable property of a `method`, and make seed *bindings* (never seed values) a first-class property of a `workflow-step`, enforced by a compiler edge guard and six validate checks.

**Architecture:** Vocabulary lives on the **method** (`stochasticity`, `seed_params`); bindings live on the **step** (`method`, `seed_bindings`, `rationale`). A new `sci:applies` edge connects them, materialized by the compiler with the same resolution guard `sci:executes` already uses. `stochasticity` is **optional on the model and required at the point of use**: a validate ERROR fires when a step applies a method that declares no classification. Everything else is warn-only, per `t079`'s "ship as visibility warnings first."

**Tech Stack:** Python 3.12+, Pydantic v2, rdflib, pytest, ruff, pyright.

## Global Constraints

- **The design doc is `meta/doc/plans/2026-07-09-method-stochasticity-umbrella-design.md`, Spec 1 section.** It is authoritative. Read it before Task 1.
- **`stochasticity` is OPTIONAL on `MethodEntity` (`Stochasticity | None = None`).** Do not make it required, and do not give it a non-`None` default. This is a settled ruling, not an oversight — see the Spec 1 section of the design doc for the corpus evidence (46 of 51 live `method` entities are glossary terms or design documents, not procedures). **Do not reopen it.**
- **`seedable` does NOT imply non-empty `seed_params` at the model layer.** There is no model validator tying them together. `method.seed-params-missing` reports it as a *warning*. All four seedable methods in the live corpus name no seed parameter, so a hard requirement would outlaw an honest record.
- **No seed VALUE ever lives on a `workflow-step`.** `seed_bindings` maps a parameter name to a *source*. Realized values are Spec 2's `RunFingerprint.step_seeds`.
- **`seed_bindings` source grammar is exactly two forms:** `config.<key>` and `literal:<int>`. Any other value is a model-level `ValueError`.
- **`science/src/science_tool/graph/belief.py` must not be modified.** Umbrella-wide non-goal.
- **There is no root `pyproject.toml`.** `cd science/` for CLI/tool work; `cd science/model/` for model work. Always `cd` before `uv run`.
- Tests: `cd science && uv run --frozen pytest` and `cd science/model && uv run --frozen pytest`.
- Lint/types: `cd science && uv run ruff check && uv run pyright`. Run `ruff check` from whichever package you changed.
- **Commit messages carry no AI-attribution trailer or footer.** No `Co-Authored-By:`, no "Generated with Claude Code".
- Conventions: composition over inheritance; explicit over defensive; fail early instead of silent fallbacks; no "legacy"/"compatibility" layers; no `Unified` prefix.
- Use `~/d/` (not `/home/keith/d/` or `/mnt/ssd/Dropbox/`) for filepaths written into docs and code.

### Template mirror rule (read before Task 5)

`templates/` at the repo root and `science/model/src/science_model/templates/` are two copies. `test_root_and_packaged_migrated_templates_match` guards them byte-for-byte **only** for the 19 kinds where `EntityKind.template_ready is True`.

- `method` is `template_ready=True` ⇒ **its packaged copy is guarded. You must sync it.**
- `workflow-step` is `template_ready=False` ⇒ its packaged copy is unguarded, but Spec 0 set the precedent of syncing what you touch. **Sync it.**

For a `template_ready=True` template, the literal frontmatter block is inert illustration; the `_template.frontmatter` block is what the `Renderer` actually emits.

---

### Task 1: `Stochasticity` vocabulary and `MethodEntity` fields

**Files:**
- Modify: `science/model/src/science_model/entities.py` (add `Stochasticity`; extend `MethodEntity` at ~line 920)
- Test: `science/model/tests/test_method_stochasticity.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `science_model.entities.Stochasticity` (a `StrEnum` with members `DETERMINISTIC = "deterministic"`, `SEEDABLE = "seedable"`, `NONDETERMINISTIC = "nondeterministic"`); `MethodEntity.stochasticity: Stochasticity | None`; `MethodEntity.seed_params: list[str]`. Tasks 3, 4 and 5 depend on these exact names.

`entities.py` already imports `from enum import StrEnum` (line 7) and `Field` from pydantic (line 10). Define `Stochasticity` immediately above `class MethodEntity`.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_method_stochasticity.py`:

```python
"""MethodEntity stochasticity vocabulary (umbrella Spec 1, task:t079)."""

import pytest
from pydantic import ValidationError

from science_model.entities import MethodEntity, Stochasticity


def _method(**kwargs) -> MethodEntity:
    return MethodEntity(
        id="method:leiden",
        kind="method",
        title="Leiden clustering",
        content_preview="",
        file_path="entities/methods/leiden.md",
        **kwargs,
    )


def test_stochasticity_members() -> None:
    assert Stochasticity.DETERMINISTIC == "deterministic"
    assert Stochasticity.SEEDABLE == "seedable"
    assert Stochasticity.NONDETERMINISTIC == "nondeterministic"


def test_stochasticity_defaults_to_none_meaning_unclassified() -> None:
    # Optional on the model, required at the point of use: an unclassified
    # method must parse, because 46 of 51 live `method` entities are glossary
    # terms and design documents that no workflow step will ever apply.
    assert _method().stochasticity is None
    assert _method().seed_params == []


def test_stochasticity_parses_from_frontmatter_string() -> None:
    assert _method(stochasticity="seedable").stochasticity is Stochasticity.SEEDABLE


def test_stochasticity_rejects_an_unknown_classification() -> None:
    with pytest.raises(ValidationError):
        _method(stochasticity="maybe")


def test_seedable_does_not_require_seed_params() -> None:
    # Deliberate: all four seedable methods in the live corpus describe their
    # stochastic step without naming its parameter. `method.seed-params-missing`
    # warns; the model does not refuse the record.
    method = _method(stochasticity="seedable")
    assert method.stochasticity is Stochasticity.SEEDABLE
    assert method.seed_params == []


def test_seed_params_round_trip() -> None:
    assert _method(seed_params=["random_state", "init_seed"]).seed_params == [
        "random_state",
        "init_seed",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_method_stochasticity.py -v`
Expected: FAIL — `ImportError: cannot import name 'Stochasticity'`

- [ ] **Step 3: Write minimal implementation**

In `science/model/src/science_model/entities.py`, immediately above `class MethodEntity`:

```python
class Stochasticity(StrEnum):
    """How thoroughly a method's randomness is controlled by its seeds.

    A seed-control classification, NOT a reproducibility verdict — that verdict
    is `task:t080`'s question. `nondeterministic` therefore means "not fully
    seed-controlled", which is deliberately wider than "cannot be seeded": a CUDA
    method that accepts a `random_state` but retains residual nondeterminism
    (parallel float reduction order, `atomicAdd`) classifies honestly here.
    """

    DETERMINISTIC = "deterministic"
    SEEDABLE = "seedable"
    NONDETERMINISTIC = "nondeterministic"
```

Then replace the body of `MethodEntity` with:

```python
class MethodEntity(ProjectEntity):
    """Analytical method or computational approach.

    `stochasticity` is optional here and required at the point of use: a
    `workflow-step` that applies an unclassified method is a validate ERROR
    (`workflow-step.method-stochasticity-missing`), and Spec 2's `register-run`
    fails closed on the same condition. `None` means *unclassified* and is
    distinguishable from every classification, so nothing fails open.

    Requiring it here instead would hard-fail the graph build in four live
    projects: 46 of the 51 authored `method` entities are glossary terms or
    design documents rather than computational procedures, and asking whether
    `method:chip-seq` is seed-controlled is a category error.

    `seedable` does not imply a non-empty `seed_params` — a method may be known
    to be seedable before its parameter is identified. `method.seed-params-missing`
    reports that as a warning.
    """

    stochasticity: Stochasticity | None = None
    seed_params: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_method_stochasticity.py -v`
Expected: 6 passed

Then the model suite and the tool suite (a new required field would break fixtures; a new optional one must not):
Run: `cd science/model && uv run --frozen pytest`
Expected: all pass (952 passed on `main` before this task)
Run: `cd science && uv run --frozen pytest -x -q`
Expected: all pass

- [ ] **Step 5: Lint and typecheck**

Run: `cd science/model && uv run ruff check` then `cd ../ && uv run pyright`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/entities.py science/model/tests/test_method_stochasticity.py
git commit -m "Add Stochasticity vocabulary and MethodEntity classification fields"
```

---

### Task 2: `WorkflowStepEntity` seed bindings and binding-source grammar

**Files:**
- Modify: `science/model/src/science_model/entities.py` (extend `WorkflowStepEntity` at ~line 930)
- Test: `science/model/tests/test_workflow_step_seed_bindings.py` (create)

**Interfaces:**
- Consumes: nothing from Task 1 (independent).
- Produces: `WorkflowStepEntity.method: str`, `WorkflowStepEntity.seed_bindings: dict[str, str]`, `WorkflowStepEntity.rationale: str`. Tasks 3, 4 and 5 depend on these exact names.

`entities.py` already imports `re` (line 5) and `field_validator` (line 10).

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_workflow_step_seed_bindings.py`:

```python
"""WorkflowStepEntity seed bindings (umbrella Spec 1, task:t079).

A binding names a SOURCE, never a value. Realized seed values belong to
Spec 2's RunFingerprint.step_seeds.
"""

import pytest
from pydantic import ValidationError

from science_model.entities import WorkflowStepEntity


def _step(**kwargs) -> WorkflowStepEntity:
    # project / ontology_terms / related / source_refs are REQUIRED on base
    # `Entity` (no defaults). Markdown fixtures get them from the loader's
    # `_fill_derived_defaults`; a direct constructor call must pass them.
    return WorkflowStepEntity(
        id="workflow-step:cluster",
        kind="workflow-step",
        title="Cluster",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="entities/workflow-steps/cluster.md",
        **kwargs,
    )


def test_new_fields_default_to_empty() -> None:
    step = _step()
    assert step.method == ""
    assert step.seed_bindings == {}
    assert step.rationale == ""


def test_config_source_is_accepted() -> None:
    step = _step(method="method:leiden", seed_bindings={"random_state": "config.seed"})
    assert step.seed_bindings["random_state"] == "config.seed"


def test_dotted_config_key_is_accepted() -> None:
    assert _step(seed_bindings={"s": "config.cluster.random_state"}).seed_bindings["s"]


def test_literal_source_is_accepted() -> None:
    assert _step(seed_bindings={"random_state": "literal:42"}).seed_bindings["random_state"]


def test_negative_literal_is_accepted() -> None:
    assert _step(seed_bindings={"s": "literal:-1"}).seed_bindings["s"] == "literal:-1"


@pytest.mark.parametrize(
    "source",
    [
        "42",             # a bare value, not a source
        "literal:abc",    # not an int
        "literal:",       # empty
        "config.",        # empty key
        "config",         # no key
        "env.SEED",       # unsupported form
        "",               # empty
    ],
)
def test_malformed_binding_source_is_rejected(source: str) -> None:
    # A malformed source is a syntax error, not an epistemic gap: fail early.
    with pytest.raises(ValidationError, match="binding source"):
        _step(seed_bindings={"random_state": source})


def test_empty_parameter_name_is_rejected() -> None:
    with pytest.raises(ValidationError, match="parameter name"):
        _step(seed_bindings={"": "literal:42"})


def test_rationale_round_trips() -> None:
    assert _step(rationale="GPU atomics").rationale == "GPU atomics"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_workflow_step_seed_bindings.py -v`
Expected: FAIL — `WorkflowStepEntity` has no field `seed_bindings` (with `extra` not forbidden the kwargs are ignored, so `test_config_source_is_accepted` fails on `AttributeError`)

- [ ] **Step 3: Write minimal implementation**

In `science/model/src/science_model/entities.py`, above `class WorkflowStepEntity`:

```python
_CONFIG_BINDING_SOURCE = re.compile(r"^config\.[A-Za-z0-9_][A-Za-z0-9_.-]*$")
_LITERAL_BINDING_SOURCE = re.compile(r"^literal:-?\d+$")
```

Then replace `WorkflowStepEntity` with:

```python
class WorkflowStepEntity(ProjectEntity):
    """One step of a workflow *definition* (not of a run).

    `workflow` names the owning workflow; `method` names the method the step
    applies (materialized as `sci:applies`); `rule_name` names the snakemake rule
    that executes the step.

    `seed_bindings` maps one of the method's `seed_params` to the SOURCE that
    supplies it — never to a value. A realized seed value is an observation of a
    run, and belongs to Spec 2's `RunFingerprint.step_seeds`.

    `rationale` explains why a step applying a `nondeterministic` method is
    acceptable; `workflow-step.rationale-missing` warns when it is absent.
    """

    workflow: str = ""
    method: str = ""
    rule_name: str = ""
    seed_bindings: dict[str, str] = Field(default_factory=dict)
    rationale: str = ""

    @field_validator("seed_bindings")
    @classmethod
    def _validate_binding_sources(cls, value: dict[str, str]) -> dict[str, str]:
        for param, source in value.items():
            if not param:
                raise ValueError("seed_bindings parameter name must not be empty")
            if not (_CONFIG_BINDING_SOURCE.match(source) or _LITERAL_BINDING_SOURCE.match(source)):
                raise ValueError(
                    f"seed_bindings[{param!r}] = {source!r} is not a valid binding source; "
                    "use 'config.<key>' or 'literal:<int>'"
                )
        return value
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_workflow_step_seed_bindings.py -v`
Expected: 14 passed (7 parametrized cases)

Run: `cd science/model && uv run --frozen pytest` and `cd science && uv run --frozen pytest -x -q`
Expected: all pass

- [ ] **Step 5: Lint and typecheck**

Run: `cd science/model && uv run ruff check` then `cd ../ && uv run pyright`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/entities.py science/model/tests/test_workflow_step_seed_bindings.py
git commit -m "Add workflow-step method ref, seed bindings, and rationale"
```

---

### Task 3: `sci:applies` — relation, materialization, and reference audit

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py` (add `RelationKind`, immediately after the `executes` block that ends at ~line 660)
- Modify: `science/src/science_tool/graph/materialize.py` (dispatch at ~line 741; helper after `_add_executes_edge`, ~line 1110)
- Modify: `science/src/science_tool/graph/migrate.py` (~line 322, beside the `workflow_ref` audit)
- Test: `science/tests/test_materialize_step_applies.py` (create)

**Interfaces:**
- Consumes: `WorkflowStepEntity.method` (Task 2).
- Produces: predicate `SCI_NS.applies`; helper `_add_applies_edge`.

`SCI_NS` is `Namespace("http://example.org/science/vocab/")` from `science_tool.graph.io`, so `SCI_NS.applies` is `.../vocab/applies`. `entity_uri_for_ref("workflow-step:cluster")` maps the colon to a slash: `.../workflow-step/cluster`.

**Ordering note (do not "fix" this):** `_compile`'s audit gate raises before the emit phase, so `_add_applies_edge`'s unresolved-ref branch is unreachable through the normal pipeline. It is retained deliberately, exactly as `_add_executes_edge`'s equivalent branch is, to preserve the helper's local invariant for callers that reach the materialization layer outside the audited path. Its wrong-kind branch **is** reachable, because the audit resolves refs without checking the target's kind.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_materialize_step_applies.py`, mirroring `science/tests/test_materialize_run_executes.py`:

```python
"""workflow-step --sci:applies--> method (umbrella Spec 1, task:t079)."""

from pathlib import Path

import pytest
from rdflib import Dataset

from science_tool.graph.io import PROJECT_NS, SCI_NS, entity_uri_for_ref
from science_tool.graph.materialize import materialize_graph


def _project(root: Path, *, step_method: str | None, extra_kind: str = "method") -> Path:
    (root / "science.yaml").write_text(
        "name: applies-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    methods = root / "entities" / "methods"
    methods.mkdir(parents=True, exist_ok=True)
    (methods / "leiden.md").write_text(
        f"---\nid: {extra_kind}:leiden\nkind: {extra_kind}\ntitle: Leiden\n---\n",
        encoding="utf-8",
    )
    steps = root / "entities" / "workflow-steps"
    steps.mkdir(parents=True, exist_ok=True)
    method_line = f"method: {step_method}\n" if step_method is not None else ""
    (steps / "cluster.md").write_text(
        f"---\nid: workflow-step:cluster\nkind: workflow-step\ntitle: Cluster\n{method_line}---\n",
        encoding="utf-8",
    )
    return root


def _knowledge(root: Path) -> Dataset:
    graph_path = root / "knowledge" / "graph.trig"
    materialize_graph(root, graph_path)
    dataset = Dataset()
    dataset.parse(graph_path, format="trig")
    return dataset


def test_step_applies_edge_is_emitted(tmp_path: Path) -> None:
    root = _project(tmp_path, step_method="method:leiden")
    dataset = _knowledge(root)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    triple = (
        entity_uri_for_ref("workflow-step:cluster"),
        SCI_NS.applies,
        entity_uri_for_ref("method:leiden"),
    )
    assert triple in knowledge


def test_step_without_a_method_emits_no_edge(tmp_path: Path) -> None:
    root = _project(tmp_path, step_method=None)
    dataset = _knowledge(root)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    assert not list(knowledge.triples((None, SCI_NS.applies, None)))


def test_step_naming_a_non_method_is_a_hard_error(tmp_path: Path) -> None:
    # `topic:leiden` resolves, so the audit gate passes it; the kind check fires.
    root = _project(tmp_path, step_method="topic:leiden", extra_kind="topic")
    with pytest.raises(ValueError, match="non-method entity"):
        _knowledge(root)


def test_step_naming_an_unresolvable_method_is_a_hard_error(tmp_path: Path) -> None:
    root = _project(tmp_path, step_method="method:does-not-exist")
    with pytest.raises(ValueError):
        _knowledge(root)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_materialize_step_applies.py -v`
Expected: FAIL — no `sci:applies` triple is emitted

- [ ] **Step 3a: Add the relation**

In `science/model/src/science_model/profiles/core.py`, immediately after the `executes` `RelationKind` block:

```python
        RelationKind(
            name="applies",
            predicate="sci:applies",
            source_kinds=["workflow-step"],
            target_kinds=["method"],
            layer="layer/core",
            description="A workflow step applies an analytical method.",
        ),
```

- [ ] **Step 3b: Materialize the edge**

In `science/src/science_tool/graph/materialize.py`, beside the existing `WorkflowRunEntity` dispatch (~line 741):

```python
    if isinstance(entity, WorkflowStepEntity):
        _add_applies_edge(
            entity,
            entity_uri,
            entity_index=entity_index,
            resolver=resolver,
            knowledge=knowledge,
        )
```

Import `WorkflowStepEntity` alongside the existing `WorkflowRunEntity` import. Then add the helper immediately after `_add_executes_edge`:

```python
def _add_applies_edge(
    entity: WorkflowStepEntity,
    step_uri: URIRef,
    *,
    entity_index: dict[str, Entity],
    resolver: ReferenceResolver,
    knowledge,
) -> None:
    """Emit sci:applies for a step that names the method it applies.

    A step that names no method emits no edge. A step that names one it cannot
    resolve is a hard error: silently dropping the edge would delete the link
    that Spec 2 traverses to derive a run's seed policy.
    """
    if not entity.method:
        return
    resolution = resolver.resolve(entity.method)
    if resolution.status != "resolved" or resolution.canonical_id is None:
        raise ValueError(
            f"{entity.canonical_id} applies {entity.method!r}, which does not resolve "
            "to a known entity; a step's method must resolve to a method."
        )
    target = entity_index.get(resolution.canonical_id)
    if target is None or target.kind != "method":
        raise ValueError(
            f"{entity.canonical_id} applies {resolution.canonical_id!r}, which resolved to a "
            "non-method entity; a step's method must name a method."
        )
    knowledge.add((step_uri, SCI_NS.applies, _entity_uri(resolution.canonical_id)))
```

- [ ] **Step 3c: Audit the reference**

In `science/src/science_tool/graph/migrate.py`, immediately after the existing `workflow_ref` block (~line 324):

```python
    # `method` is declared only by WorkflowStepEntity; auditing it here is what
    # makes `_add_applies_edge`'s unresolved-ref branch unreachable in the
    # normal pipeline.
    method_ref = getattr(entity, "method", "")
    if method_ref:
        rows.extend(_audit_reference(entity, "method", method_ref, resolver, ext_prefixes=ext_prefixes))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_materialize_step_applies.py tests/test_materialize_run_executes.py -v`
Expected: 4 + 4 passed

Run: `cd science && uv run --frozen pytest -q` and `cd science/model && uv run --frozen pytest -q`
Expected: all pass. `science/model/tests/test_profile_manifests.py` may carry a relation-count or manifest literal — if it fails, update the literal to include `applies`; that is a gate being *updated*, not weakened. Do not touch any other assertion in it.

- [ ] **Step 5: Lint and typecheck**

Run: `cd science && uv run ruff check && uv run pyright`; `cd science/model && uv run ruff check`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/profiles/core.py science/src/science_tool/graph/materialize.py science/src/science_tool/graph/migrate.py science/tests/test_materialize_step_applies.py
git commit -m "Add and materialize sci:applies (workflow-step to method)"
```

---

### Task 4: The six validate checks

**Files:**
- Create: `science/src/science_tool/validate/checks/workflow_steps.py`
- Create: `science/src/science_tool/validate/checks/methods.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py` (append to the module-name tuple that currently ends `"workflow_runs",`)
- Test: `science/tests/validate/test_checks_workflow_steps.py` (create)

**Interfaces:**
- Consumes: `Stochasticity`, `MethodEntity.stochasticity`, `MethodEntity.seed_params` (Task 1); `WorkflowStepEntity.method`, `.seed_bindings`, `.rationale` (Task 2).
- Produces: rule identifiers `workflow-step.method-stochasticity-missing` (ERROR), `workflow-step.seed-binding-missing`, `workflow-step.rationale-missing`, `workflow-step.seed-binding-on-deterministic-method`, `workflow-step.seed-binding-unknown-param`, `method.seed-params-missing` (all WARN).

Existing patterns to follow: a check module registers with `@Check(section="...", order=N)` and yields `Result(severity=..., path=..., line=None, message=..., rule=..., task=None)`. The highest `order` currently in use is `53`. `Severity` has `ERROR`, `WARN`, `INFO`. `ctx.project_sources().entities` is a `list[Entity]` of typed, already-validated entities; `Entity.file_path` is relative to the project root.

**Two behaviours that are load-bearing — get them right:**

1. **An unresolvable `step.method` is skipped, not reported.** The compiler and `graph audit` own that defect. If this check also reported it, one defect would be reported twice by two surfaces with different wording.
2. **`seed-binding-unknown-param` is suppressed when the method declares no `seed_params` at all.** `method.seed-params-missing` already reports that gap; firing both would report one defect twice.

- [ ] **Step 1: Write the failing test**

Create `science/tests/validate/test_checks_workflow_steps.py`:

```python
"""Seed-binding and stochasticity checks (umbrella Spec 1, task:t079)."""

from pathlib import Path

from science_tool.validate.checks.methods import check_method_seed_params
from science_tool.validate.checks.workflow_steps import check_workflow_step_seed_bindings
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _project(
    root: Path,
    *,
    method_frontmatter: str,
    step_frontmatter: str,
) -> Path:
    (root / "science.yaml").write_text(
        "name: seed-check-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    methods = root / "entities" / "methods"
    methods.mkdir(parents=True, exist_ok=True)
    (methods / "leiden.md").write_text(
        f"---\nid: method:leiden\nkind: method\ntitle: Leiden\n{method_frontmatter}---\n",
        encoding="utf-8",
    )
    steps = root / "entities" / "workflow-steps"
    steps.mkdir(parents=True, exist_ok=True)
    (steps / "cluster.md").write_text(
        f"---\nid: workflow-step:cluster\nkind: workflow-step\ntitle: Cluster\n{step_frontmatter}---\n",
        encoding="utf-8",
    )
    return root


def _ctx(root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _rules(results) -> list[tuple[str, Severity]]:
    return [(r.rule, r.severity) for r in results]


def test_step_applying_unclassified_method_is_an_error(tmp_path: Path) -> None:
    root = _project(tmp_path, method_frontmatter="", step_frontmatter="method: method:leiden\n")
    results = list(check_workflow_step_seed_bindings(_ctx(root)))
    assert _rules(results) == [("workflow-step.method-stochasticity-missing", Severity.ERROR)]


def test_seedable_method_with_unbound_param_warns(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: seedable\nseed_params: [random_state]\n",
        step_frontmatter="method: method:leiden\n",
    )
    results = list(check_workflow_step_seed_bindings(_ctx(root)))
    assert _rules(results) == [("workflow-step.seed-binding-missing", Severity.WARN)]
    assert "random_state" in results[0].message


def test_seedable_method_with_bound_param_is_clean(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: seedable\nseed_params: [random_state]\n",
        step_frontmatter='method: method:leiden\nseed_bindings:\n  random_state: "config.seed"\n',
    )
    assert list(check_workflow_step_seed_bindings(_ctx(root))) == []


def test_partial_binding_warns_once_per_unbound_param(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: seedable\nseed_params: [a, b, c]\n",
        step_frontmatter='method: method:leiden\nseed_bindings:\n  a: "literal:1"\n',
    )
    results = list(check_workflow_step_seed_bindings(_ctx(root)))
    assert _rules(results) == [
        ("workflow-step.seed-binding-missing", Severity.WARN),
        ("workflow-step.seed-binding-missing", Severity.WARN),
    ]


def test_nondeterministic_method_without_rationale_warns(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: nondeterministic\n",
        step_frontmatter="method: method:leiden\n",
    )
    results = list(check_workflow_step_seed_bindings(_ctx(root)))
    assert _rules(results) == [("workflow-step.rationale-missing", Severity.WARN)]


def test_nondeterministic_method_with_rationale_is_clean(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: nondeterministic\n",
        step_frontmatter='method: method:leiden\nrationale: "GPU atomics"\n',
    )
    assert list(check_workflow_step_seed_bindings(_ctx(root))) == []


def test_binding_on_deterministic_method_warns(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: deterministic\n",
        step_frontmatter='method: method:leiden\nseed_bindings:\n  random_state: "literal:42"\n',
    )
    results = list(check_workflow_step_seed_bindings(_ctx(root)))
    assert _rules(results) == [
        ("workflow-step.seed-binding-on-deterministic-method", Severity.WARN)
    ]


def test_binding_naming_an_unknown_param_warns(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: seedable\nseed_params: [random_state]\n",
        step_frontmatter='method: method:leiden\nseed_bindings:\n  random_state: "literal:1"\n  typo: "literal:2"\n',
    )
    results = list(check_workflow_step_seed_bindings(_ctx(root)))
    assert _rules(results) == [("workflow-step.seed-binding-unknown-param", Severity.WARN)]
    assert "typo" in results[0].message


def test_unknown_param_is_suppressed_when_method_declares_no_seed_params(tmp_path: Path) -> None:
    # method.seed-params-missing already owns this defect; do not report it twice.
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: seedable\n",
        step_frontmatter='method: method:leiden\nseed_bindings:\n  whatever: "literal:1"\n',
    )
    assert list(check_workflow_step_seed_bindings(_ctx(root))) == []


def test_unresolvable_method_ref_is_skipped(tmp_path: Path) -> None:
    # The compiler and `graph audit` own the unresolved-reference defect.
    root = _project(tmp_path, method_frontmatter="", step_frontmatter="method: method:nope\n")
    assert list(check_workflow_step_seed_bindings(_ctx(root))) == []


def test_step_without_a_method_is_skipped(tmp_path: Path) -> None:
    root = _project(tmp_path, method_frontmatter="", step_frontmatter="")
    assert list(check_workflow_step_seed_bindings(_ctx(root))) == []


def test_seedable_method_without_seed_params_warns(tmp_path: Path) -> None:
    root = _project(tmp_path, method_frontmatter="stochasticity: seedable\n", step_frontmatter="")
    results = list(check_method_seed_params(_ctx(root)))
    assert _rules(results) == [("method.seed-params-missing", Severity.WARN)]


def test_unclassified_method_does_not_warn_about_seed_params(tmp_path: Path) -> None:
    root = _project(tmp_path, method_frontmatter="", step_frontmatter="")
    assert list(check_method_seed_params(_ctx(root))) == []


def test_deterministic_method_does_not_warn_about_seed_params(tmp_path: Path) -> None:
    root = _project(tmp_path, method_frontmatter="stochasticity: deterministic\n", step_frontmatter="")
    assert list(check_method_seed_params(_ctx(root))) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_workflow_steps.py -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.validate.checks.workflow_steps`

- [ ] **Step 3a: Write `workflow_steps.py`**

```python
"""Seed-binding hygiene for workflow-step definitions (umbrella Spec 1, task:t079).

A step applying an unclassified method is an ERROR: the classification is
required at the point of use, which is the first moment it is both knowable and
checkable. Everything else is a warning -- `task:t079` ships visibility first.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_model.entities import Entity, MethodEntity, Stochasticity, WorkflowStepEntity

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

RULE_STOCHASTICITY_MISSING = "workflow-step.method-stochasticity-missing"
RULE_SEED_BINDING_MISSING = "workflow-step.seed-binding-missing"
RULE_RATIONALE_MISSING = "workflow-step.rationale-missing"
RULE_BINDING_ON_DETERMINISTIC = "workflow-step.seed-binding-on-deterministic-method"
RULE_BINDING_UNKNOWN_PARAM = "workflow-step.seed-binding-unknown-param"


def _method_index(entities: list[Entity]) -> dict[str, MethodEntity]:
    index: dict[str, MethodEntity] = {}
    for entity in entities:
        if not isinstance(entity, MethodEntity):
            continue
        index[entity.canonical_id] = entity
        for alias in entity.aliases or []:
            index.setdefault(alias, entity)
    return index


def _warn(path: Path, message: str, rule: str) -> Result:
    return Result(severity=Severity.WARN, path=path, line=None, message=message, rule=rule, task=None)


def _step_results(step: WorkflowStepEntity, method: MethodEntity, path: Path) -> Iterator[Result]:
    if method.stochasticity is None:
        yield Result(
            severity=Severity.ERROR,
            path=path,
            line=None,
            message=(
                f"{step.canonical_id} applies {method.canonical_id}, which declares no "
                "stochasticity; classify the method as deterministic, seedable, or "
                "nondeterministic."
            ),
            rule=RULE_STOCHASTICITY_MISSING,
            task=None,
        )
        return

    if method.stochasticity is Stochasticity.DETERMINISTIC:
        if step.seed_bindings:
            yield _warn(
                path,
                f"{step.canonical_id} binds seeds for {method.canonical_id}, which is "
                "deterministic; no binding is meaningful.",
                RULE_BINDING_ON_DETERMINISTIC,
            )
        return

    if method.stochasticity is Stochasticity.NONDETERMINISTIC and not step.rationale:
        yield _warn(
            path,
            f"{step.canonical_id} applies {method.canonical_id}, which is nondeterministic, "
            "and supplies no rationale.",
            RULE_RATIONALE_MISSING,
        )

    if not method.seed_params:
        # `method.seed-params-missing` owns this gap; reporting an unknown
        # parameter here as well would report one defect twice.
        return

    for param in sorted(set(step.seed_bindings) - set(method.seed_params)):
        yield _warn(
            path,
            f"{step.canonical_id} binds {param!r}, which is not among "
            f"{method.canonical_id}'s seed_params.",
            RULE_BINDING_UNKNOWN_PARAM,
        )

    if method.stochasticity is Stochasticity.SEEDABLE:
        for param in method.seed_params:
            if param not in step.seed_bindings:
                yield _warn(
                    path,
                    f"{step.canonical_id} applies seedable {method.canonical_id} and leaves "
                    f"{param!r} unbound.",
                    RULE_SEED_BINDING_MISSING,
                )


@Check(section="workflow steps", order=54)
def check_workflow_step_seed_bindings(ctx: ValidateContext) -> Iterator[Result]:
    """A step's seed bindings must agree with the method it applies."""
    sources = ctx.project_sources()
    methods = _method_index(sources.entities)
    for step in sources.entities:
        if not isinstance(step, WorkflowStepEntity) or not step.method:
            continue
        method = methods.get(step.method)
        if method is None:
            # An unresolved reference is the compiler's and `graph audit`'s defect.
            continue
        yield from _step_results(step, method, ctx.project_root / step.file_path)
```

- [ ] **Step 3b: Write `methods.py`**

```python
"""Method-local seed hygiene (umbrella Spec 1, task:t079)."""

from __future__ import annotations

from collections.abc import Iterator

from science_model.entities import MethodEntity, Stochasticity

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

RULE_SEED_PARAMS_MISSING = "method.seed-params-missing"


@Check(section="methods", order=55)
def check_method_seed_params(ctx: ValidateContext) -> Iterator[Result]:
    """A seedable method should name the parameters that control its randomness.

    A warning, not an error: a method may be known to be seedable before its
    parameter is identified, and every seedable method in the live corpus is in
    exactly that state.
    """
    for entity in ctx.project_sources().entities:
        if not isinstance(entity, MethodEntity):
            continue
        if entity.stochasticity is Stochasticity.SEEDABLE and not entity.seed_params:
            yield Result(
                severity=Severity.WARN,
                path=ctx.project_root / entity.file_path,
                line=None,
                message=(
                    f"{entity.canonical_id} is seedable but names no seed_params; "
                    "a step cannot bind a seed it cannot name."
                ),
                rule=RULE_SEED_PARAMS_MISSING,
                task=None,
            )
```

- [ ] **Step 3c: Register both modules**

In `science/src/science_tool/validate/checks/__init__.py`, extend the module-name tuple that currently ends with `"workflow_runs",`:

```python
    "workflow_runs",
    "workflow_steps",
    "methods",
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_workflow_steps.py -v`
Expected: 14 passed

The registration adds two checks to the profile's check count. Run: `cd science && uv run --frozen pytest -q`
Expected: all pass. If a test asserts a literal check count (grep for `56 included` / `Checks:`), update the literal — a gate being updated, not weakened.

- [ ] **Step 5: Lint and typecheck**

Run: `cd science && uv run ruff check && uv run pyright`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/validate/checks/workflow_steps.py science/src/science_tool/validate/checks/methods.py science/src/science_tool/validate/checks/__init__.py science/tests/validate/test_checks_workflow_steps.py
git commit -m "Add stochasticity and seed-binding validate checks"
```

---

### Task 5: Templates (root and packaged mirrors)

**Files:**
- Modify: `templates/workflow-step.md`
- Modify: `templates/method.md`
- Modify: `science/model/src/science_model/templates/workflow-step.md` (sync)
- Modify: `science/model/src/science_model/templates/method.md` (sync — **guarded byte-for-byte**)
- Test: `science/tests/test_template_descriptor_contract.py` and `science/model/tests/` mirror guard must stay green (no new test file)

**Interfaces:**
- Consumes: field names from Tasks 1 and 2.
- Produces: nothing consumed by later tasks.

Re-read the **Template mirror rule** in Global Constraints before starting.

- [ ] **Step 1: Rewrite `templates/workflow-step.md` frontmatter**

Replace the frontmatter block. The `inquiry:` key is **deleted**: no `RelationKind` in `CORE_PROFILE` names `inquiry` as a source or target, and the template's `inquiry AnnotatedParam` hint points at a mechanism `science/tests/test_inquiry.py` records as retired. It is untyped, unaudited, and silently dropped at parse.

```yaml
---
id: "workflow-step:<slug>"
kind: "workflow-step"
title: "<Step Name>"
status: "active"
workflow: "workflow:<slug>"
method: "method:<slug>"           # materializes the sci:applies edge
rule_name: "<snakemake-rule-name>"
seed_bindings:                    # a seed_param -> its SOURCE, never its value
  random_state: "config.seed"     #   config.<key> | literal:<int>
rationale: ""                     # why a nondeterministic method is acceptable here
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---
```

- [ ] **Step 2: Update the body's Parameters table and Related list**

In the `## Parameters` table, replace the `inquiry AnnotatedParam / config.yaml` source hint with `config.yaml / literal`.

In `## Related`, delete the `- **Inquiry:** \`inquiry:<slug>\`` bullet and add a Method bullet, so the list reads:

```markdown
- **Workflow:** `workflow:<slug>`
- **Method:** `method:<slug>`
- **Upstream:** `workflow-step:<slug>`
- **Downstream:** `workflow-step:<slug>`
```

- [ ] **Step 3: Update `templates/method.md`**

`method` is `template_ready=True`, so the `_template.frontmatter` block is what the `Renderer` emits. `templates.py` refuses `default: null` ("default cannot be null; use omit: true or a concrete default"), and the correct default for an unclassified method is *absent*, so both new keys use `omit: true` — the same idiom `templates/evidence-line.md` uses for `dispute_scope`.

Leave the literal frontmatter block **unchanged** (it is inert illustration for a `template_ready` kind, and `dispute_scope` sets the precedent of not listing omitted keys there).

In the `_template.frontmatter` block, immediately after `status: { from: status }`:

```yaml
    stochasticity: { omit: true }
    seed_params: { omit: true }
```

- [ ] **Step 4: Sync both packaged copies**

```bash
cp templates/workflow-step.md science/model/src/science_model/templates/workflow-step.md
cp templates/method.md science/model/src/science_model/templates/method.md
```

- [ ] **Step 5: Run the guards and the full suites**

Run: `cd science && uv run --frozen pytest tests/test_template_descriptor_contract.py -v`
Expected: 19 passed, 2 skipped

Run: `cd science/model && uv run --frozen pytest -k migrated_templates -v`
Expected: `test_root_and_packaged_migrated_templates_match` passes (it guards `method`)

Run: `cd science && uv run --frozen pytest -q` and `cd science/model && uv run --frozen pytest -q`
Expected: all pass

- [ ] **Step 6: Pin the omit contract with a test**

`_render_frontmatter` skips every `omit: true` policy unconditionally (`templates.py`, `if policy.omit: continue`) — `with_keys` does not re-include it. So a freshly scaffolded method carries neither key and parses as *unclassified*, which is the correct default state. Pin that.

Create `science/model/tests/test_method_template_omits_classification.py`:

```python
"""A scaffolded method is unclassified until a human classifies it (task:t079)."""

from science_model.templates import Renderer


def _render() -> str:
    return Renderer().render(
        "method",
        fields={
            "entity_id": "method:probe",
            "title": "Probe",
            "status": "active",
            "source_refs": [],
            "related": [],
            "created": "2026-07-09",
            "updated": "2026-07-09",
        },
    )


def test_rendered_method_omits_stochasticity_and_seed_params() -> None:
    rendered = _render()
    assert "stochasticity:" not in rendered
    assert "seed_params:" not in rendered


def test_rendered_method_still_carries_its_identity() -> None:
    assert "id: method:probe" in _render()
```

Run: `cd science/model && uv run --frozen pytest tests/test_method_template_omits_classification.py -v`
Expected: 2 passed. If `Renderer()` cannot locate the packaged templates without a `template_root`, pass `Renderer(template_root=Path(science_model.__file__).parent / "templates")` and say so in your report.

- [ ] **Step 7: Commit**

```bash
git add templates/workflow-step.md templates/method.md science/model/src/science_model/templates/workflow-step.md science/model/src/science_model/templates/method.md science/model/tests/test_method_template_omits_classification.py
git commit -m "Declare stochasticity, method ref, and seed bindings in templates"
```

---

## Definition of done (whole branch)

- `cd science && uv run --frozen pytest` — green (baseline on `main`: 7754 passed, 9 skipped, 4 deselected)
- `cd science/model && uv run --frozen pytest` — green (baseline: 952 passed)
- `cd science && uv run ruff check && uv run pyright` — clean
- A step applying `method:leiden` (seedable, `seed_params: [random_state]`) with no binding produces exactly one `workflow-step.seed-binding-missing` **warning** and blocks nothing.
- A step applying a method with no `stochasticity` produces a `workflow-step.method-stochasticity-missing` **error**.
- **`science validate` stays green in all four consumer projects with zero entity edits.** Verify explicitly, since this is the ruling's core claim:
  ```bash
  for p in ~/d/cancer ~/d/health ~/d/protein-landscape ~/d/seq-feats; do
    (cd "$p" && uv run --frozen science validate 2>&1 | tail -2)
  done
  ```
  Expected: each reports its pre-existing status, unchanged by this branch. If any newly fails, the ruling has been violated — stop and escalate rather than editing consumer entities.
