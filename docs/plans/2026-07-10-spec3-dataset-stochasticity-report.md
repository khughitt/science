# Spec 3 — Dataset Stochasticity Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `science dataset stochasticity <dataset-ref>` — the reader-facing command that, given a derived dataset, names the fingerprinted run it inherited its provenance from and reports which steps were stochastic, the seeds the run realized, and which steps are nondeterministic and therefore not exactly reproducible.

**Architecture:** The graph resolves `dataset → fingerprinted run` (and the `member_of` chain to display); the source layer supplies the fingerprint's `step_seeds`, the workflow's steps, and each step's method `stochasticity`. No new graph facts are materialized — this is the split the umbrella design (Spec 3) mandates, which keeps `t092` off the critical path. The command is read-only.

**Tech Stack:** Python 3, click (CLI), rdflib (graph), pydantic (`science-model` entities), pytest.

## Global Constraints

- Umbrella design (the spec): `meta/doc/plans/2026-07-09-method-stochasticity-umbrella-design.md`, section "Spec 3 — Downstream transparency". Task: `meta/tasks/active.md` `[t089]`.
- Use **inherited** resolution (walk `member_of` to the run-owning ancestor) but **display the chain**, so a member dataset never appears directly run-produced.
- The graph emits exactly one fingerprint fact (`sci:fingerprintPolicy`, a presence marker). Read `step_seeds`, steps, and method stochasticity from the **source layer**, never expect them in the graph.
- `step_seeds` is keyed by the step's canonical id (`workflow-step:<slug>`) → `{param: int}`. The join against step entities is by exact `step.id`.
- Do **not** modify `science/src/science_tool/graph/belief.py` (umbrella-wide non-goal).
- Composition > inheritance; explicit > defensive; fail early / no silent fallbacks; no "legacy"/"compatibility" layers; no `Unified` prefix.
- No AI-attribution trailer/footer on commits.
- CLI work runs from `science/`: `cd science && uv run --frozen pytest`. Ruff from `science/`. Pyright is configured once at repo root.
- A dataset ref that does not resolve to a real `dataset:` entity is an **error** (exit 1). A dataset that resolves but has no fingerprinted run is a **valid report** (exit 0) that states the reason.

---

### Task 1: `resolve_run_chain` — inherited resolution that also returns the chain

**Files:**
- Modify: `science/src/science_tool/graph/run_resolution.py`
- Test: `science/tests/graph/test_run_resolution.py` (create if absent; otherwise add to it)

**Interfaces:**
- Consumes: existing module constants (`KIND_WORKFLOW_RUN`, `KIND_WORKFLOW_RECIPE`, `KIND_MEMBER_OF`, `NoRunReason`, `MemberOfCycleError`) and `SCI_NS`.
- Produces:
  - `@dataclass(frozen=True) class RunChainResolution: run: URIRef | None; named_run: URIRef | None; chain: list[URIRef]; reasons: list[NoRunReason]`
    - `run` is the *fingerprinted* run the dataset resolves to (None if none). `named_run` is the run a derivation edge *named*, fingerprinted or not — so the reader CLI can say "resolves to `workflow-run:r1`, but it is not fingerprinted" instead of only `run-unfingerprinted`. `run` is non-None ⟹ `named_run == run`.
    - `chain` is the list of dataset URIs visited from the queried dataset down to (and including) the dataset whose own derivation named the run. `len(chain) == 1` means the queried dataset owns the run directly (not inherited); `> 1` means inherited.
  - `resolve_run_chain(knowledge: Graph, dataset: URIRef, is_fingerprinted: Callable[[URIRef], bool]) -> RunChainResolution`
  - `resolved_empirical_runs(...)` keeps its exact current signature and return type; it now delegates to `resolve_run_chain` and reads only `.run`/`.reasons`.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/graph/test_run_resolution.py`:

```python
from __future__ import annotations

from rdflib import Graph, Literal, URIRef

from science_tool.graph.io import SCI_NS
from science_tool.graph.run_resolution import (
    NoRunReason,
    resolve_run_chain,
    resolved_empirical_runs,
)

DS = URIRef("urn:ds:")
RUN = URIRef("urn:run:r1")


def _ds(n: int) -> URIRef:
    return URIRef(f"urn:ds:{n}")


def _direct_run_graph() -> Graph:
    g = Graph()
    g.add((_ds(1), SCI_NS.derivationKind, Literal("workflow-run")))
    g.add((_ds(1), SCI_NS.workflowRun, RUN))
    return g


def _inherited_run_graph() -> Graph:
    g = Graph()
    # child --member_of--> parent --workflow-run--> RUN
    g.add((_ds(1), SCI_NS.derivationKind, Literal("member_of")))
    g.add((_ds(1), SCI_NS.memberOfParent, _ds(2)))
    g.add((_ds(2), SCI_NS.derivationKind, Literal("workflow-run")))
    g.add((_ds(2), SCI_NS.workflowRun, RUN))
    return g


def test_direct_run_chain_is_the_dataset_itself() -> None:
    res = resolve_run_chain(_direct_run_graph(), _ds(1), lambda _r: True)
    assert res.run == RUN
    assert res.chain == [_ds(1)]
    assert res.reasons == []


def test_inherited_run_chain_lists_child_then_parent() -> None:
    res = resolve_run_chain(_inherited_run_graph(), _ds(1), lambda _r: True)
    assert res.run == RUN
    assert res.chain == [_ds(1), _ds(2)]
    assert res.reasons == []


def test_unfingerprinted_run_yields_no_run_but_keeps_the_named_run() -> None:
    res = resolve_run_chain(_direct_run_graph(), _ds(1), lambda _r: False)
    assert res.run is None
    assert res.named_run == RUN  # the CLI can still name it
    assert res.reasons == [NoRunReason.RUN_UNFINGERPRINTED]


def test_resolved_empirical_runs_still_matches_chain_resolution() -> None:
    # Behaviour-preserving delegation: the tuple API returns exactly the run
    # (as a one-element list) and reasons the chain resolver computes.
    g = _inherited_run_graph()
    runs, reasons = resolved_empirical_runs(g, _ds(1), lambda _r: True)
    assert runs == [RUN]
    assert reasons == []
    runs2, reasons2 = resolved_empirical_runs(g, _ds(1), lambda _r: False)
    assert runs2 == []
    assert reasons2 == [NoRunReason.RUN_UNFINGERPRINTED]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/graph/test_run_resolution.py -q --junitxml=/tmp/t1.xml`
Expected: FAIL — `ImportError: cannot import name 'resolve_run_chain'`.

- [ ] **Step 3: Implement `resolve_run_chain` and delegate**

In `science/src/science_tool/graph/run_resolution.py`, add `from dataclasses import dataclass, field` to the imports, then insert the dataclass and function, and rewrite `resolved_empirical_runs` to delegate. The walk is the existing one, but records each visited dataset in `chain` and returns the terminal run instead of a one-element list:

```python
@dataclass(frozen=True)
class RunChainResolution:
    """A dataset's resolution to a fingerprinted run, with the chain walked.

    `chain` runs from the queried dataset (index 0) down to the dataset whose
    own derivation named `run`. `len(chain) > 1` means the run was inherited
    through `member_of` and the caller must display the chain so a member
    dataset never looks directly run-produced.
    """

    run: URIRef | None
    named_run: URIRef | None = None
    chain: list[URIRef] = field(default_factory=list)
    reasons: list[NoRunReason] = field(default_factory=list)


def resolve_run_chain(
    knowledge: Graph,
    dataset: URIRef,
    is_fingerprinted: Callable[[URIRef], bool],
) -> RunChainResolution:
    """Resolve `dataset` to its fingerprinted run, recording the member_of chain.

    Same traversal as `resolved_empirical_runs`, but returns the single run it
    resolves to plus the datasets visited to reach it. `named_run` is the run a
    derivation edge named even when it is not fingerprinted, so a reader CLI can
    name it. `is_fingerprinted` is required: naming a run is not resolving to a
    *fingerprinted* one.
    """
    visited: set[URIRef] = set()
    chain: list[URIRef] = []
    current = dataset

    while True:
        if current in visited:
            raise MemberOfCycleError(f"member_of cycle revisits {current}")
        visited.add(current)
        chain.append(current)

        kind = _derivation_kind(knowledge, current)

        if kind == KIND_WORKFLOW_RUN:
            run = cast("URIRef | None", knowledge.value(current, SCI_NS.workflowRun))
            if run is None:
                return RunChainResolution(None, None, chain, [NoRunReason.NO_PROVENANCE])
            if not is_fingerprinted(run):
                return RunChainResolution(None, run, chain, [NoRunReason.RUN_UNFINGERPRINTED])
            return RunChainResolution(run, run, chain, [])

        if kind == KIND_WORKFLOW_RECIPE:
            return RunChainResolution(None, None, chain, [NoRunReason.RECIPE_ONLY])

        if kind == KIND_MEMBER_OF:
            parent = cast("URIRef | None", knowledge.value(current, SCI_NS.memberOfParent))
            if parent is None:
                return RunChainResolution(None, None, chain, [NoRunReason.NO_PROVENANCE])
            current = parent
            continue

        if kind is not None:
            raise ValueError(f"unknown sci:derivationKind {kind!r} on {current}")

        # No derivation. Code-only provenance is not a run.
        if (current, SCI_NS.producedBy, None) in knowledge:
            return RunChainResolution(None, None, chain, [NoRunReason.CODE_ONLY_NO_RUN])
        return RunChainResolution(None, None, chain, [NoRunReason.NO_PROVENANCE])
```

Then replace the body of `resolved_empirical_runs` with a delegation that preserves its exact `(list, reasons)` contract:

```python
def resolved_empirical_runs(
    knowledge: Graph,
    dataset: URIRef,
    is_fingerprinted: Callable[[URIRef], bool],
) -> tuple[list[URIRef], list[NoRunReason]]:
    """Fingerprinted runs this dataset resolves to, walking member_of to the parent.

    `is_fingerprinted` is required and has no default: naming a workflow-run is
    not the same as resolving to a *fingerprinted* one. Delegates to
    `resolve_run_chain`, discarding the chain — evidence resolution needs only
    the run set.
    """
    result = resolve_run_chain(knowledge, dataset, is_fingerprinted)
    return ([result.run] if result.run is not None else []), result.reasons
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/graph/test_run_resolution.py -q --junitxml=/tmp/t1.xml` then read `/tmp/t1.xml` (`<testsuite tests= failures= errors=>`).
Expected: all pass, 0 failures/errors.

- [ ] **Step 5: Confirm the delegation did not regress evidence validation**

Run: `cd science && uv run --frozen pytest tests/graph -q --junitxml=/tmp/t1b.xml` and read the xml.
Expected: 0 failures/errors — the store validation tests that consume `resolved_empirical_runs` still pass.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/run_resolution.py science/tests/graph/test_run_resolution.py
git commit --no-verify -m "Return the member_of chain alongside the resolved run"
```

---

### Task 2: Shared workflow-steps reverse index

**Files:**
- Create: `science/src/science_tool/workflow_steps_index.py`
- Modify: `science/src/science_tool/datasets_register.py` (rewire `_derive_seed_policy_for_run` to use the shared helper — behaviour-preserving)
- Test: `science/tests/test_workflow_steps_index.py`

**Interfaces:**
- Consumes: `ProjectSources` (`science_tool.graph.sources`), `ReferenceResolver` (`science_tool.graph...` — the same class `datasets_register` imports today), `WorkflowStepEntity`, `MethodEntity`.
- Produces:
  - `steps_and_methods_for_workflow(sources: ProjectSources, resolver: ReferenceResolver, workflow_id: str) -> list[tuple[WorkflowStepEntity, MethodEntity | None]]`
    - Returns the workflow's steps (those whose `workflow` resolves to `workflow_id`), each paired with its resolved `MethodEntity` or `None` when the step names no method or the method does not resolve. Sorted by `step.id`. **No** validation/guards — it is a pure query; callers that need fail-closed guards (register-run) keep applying their own.

- [ ] **Step 1: Write the failing test**

`science/tests/test_workflow_steps_index.py`:

```python
from __future__ import annotations

from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import load_project_sources
from science_tool.workflow_steps_index import steps_and_methods_for_workflow


def _write(project_root, rel, frontmatter):
    p = project_root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{frontmatter}\n---\n\nbody\n", encoding="utf-8")
    return p


def test_pairs_each_workflow_step_with_its_method(tmp_path):
    (tmp_path / "science.yaml").write_text("id: project:x\nname: X\nprofile: software\n", encoding="utf-8")
    _write(tmp_path, "entities/workflows/wf.md", 'id: "workflow:wf"\nkind: "workflow"\ntitle: "WF"')
    _write(
        tmp_path,
        "entities/methods/cluster.md",
        'id: "method:cluster"\nkind: "method"\ntitle: "Cluster"\nstochasticity: "seedable"\nseed_params: ["random_state"]',
    )
    _write(
        tmp_path,
        "entities/workflow-steps/s1.md",
        'id: "workflow-step:s1"\nkind: "workflow-step"\ntitle: "S1"\nworkflow: "workflow:wf"\nmethod: "method:cluster"',
    )
    _write(
        tmp_path,
        "entities/workflow-steps/s2.md",
        'id: "workflow-step:s2"\nkind: "workflow-step"\ntitle: "S2"\nworkflow: "workflow:wf"\nmethod: "method:missing"',
    )

    sources = load_project_sources(tmp_path, strict_core_schema=False)
    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)
    pairs = steps_and_methods_for_workflow(sources, resolver, "workflow:wf")

    assert [s.id for s, _m in pairs] == ["workflow-step:s1", "workflow-step:s2"]
    assert pairs[0][1] is not None and pairs[0][1].id == "method:cluster"
    assert pairs[1][1] is None  # method:missing does not resolve
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_workflow_steps_index.py -q --junitxml=/tmp/t2.xml`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the helper**

Create `science/src/science_tool/workflow_steps_index.py` (the `ReferenceResolver` import path `science_tool.graph.reference_resolution` is the one `datasets_register.py` uses — confirmed against current `main`):

```python
"""Reverse index from a workflow to its steps and their methods.

Source-layer query shared by `register-run` (seed_policy derivation) and the
`dataset stochasticity` report. A pure lookup: it resolves refs and pairs each
step with its method, and applies no fail-closed guards — callers that require
them (register-run's `_reject_*_steps`) keep applying their own.
"""

from __future__ import annotations

from science_model.entities import MethodEntity, WorkflowStepEntity

from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import ProjectSources


def steps_and_methods_for_workflow(
    sources: ProjectSources,
    resolver: ReferenceResolver,
    workflow_id: str,
) -> list[tuple[WorkflowStepEntity, MethodEntity | None]]:
    """Steps whose `workflow` resolves to `workflow_id`, each with its method.

    Sorted by `step.id`. The method is `None` when the step names none or the
    named method does not resolve to a `MethodEntity`.
    """
    by_id = {entity.id: entity for entity in sources.entities}
    steps = [
        entity
        for entity in sources.entities
        if isinstance(entity, WorkflowStepEntity)
        and entity.workflow
        and resolver.resolve(entity.workflow).canonical_id == workflow_id
    ]
    steps.sort(key=lambda s: s.id)

    pairs: list[tuple[WorkflowStepEntity, MethodEntity | None]] = []
    for step in steps:
        method: MethodEntity | None = None
        if step.method:
            resolution = resolver.resolve(step.method)
            target = by_id.get(resolution.canonical_id) if resolution.canonical_id else None
            if isinstance(target, MethodEntity):
                method = target
        pairs.append((step, method))
    return pairs
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_workflow_steps_index.py -q --junitxml=/tmp/t2.xml` and read the xml.
Expected: pass.

- [ ] **Step 5: Rewire `_derive_seed_policy_for_run` to use the shared helper**

In `science/src/science_tool/datasets_register.py`, replace the inline steps/method-gathering block (the `steps = [...]` list comprehension and the `method_for_step` loop, around lines 1213-1228) with:

```python
    from science_tool.workflow_steps_index import steps_and_methods_for_workflow

    pairs = steps_and_methods_for_workflow(sources, resolver, workflow_id)
    steps = [step for step, _method in pairs]
    method_for_step: dict[str, MethodEntity] = {
        step.id: method for step, method in pairs if method is not None
    }
```

This is behaviour-preserving: the old code gathered the same steps (same filter) and the same `method_for_step` mapping (only resolvable `MethodEntity` targets). Leave the surrounding guards (`_reject_skipped_steps`, `_reject_unattributable_steps`) and the `derive_seed_policy` call untouched.

- [ ] **Step 6: Run the register-run suite to prove no regression**

Run: `cd science && uv run --frozen pytest tests/test_datasets_register.py tests/test_datasets_register_fingerprint.py -q --junitxml=/tmp/t2b.xml` and read the xml.
Expected: 0 failures/errors.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/workflow_steps_index.py science/tests/test_workflow_steps_index.py science/src/science_tool/datasets_register.py
git commit --no-verify -m "Extract the workflow-steps reverse index into a shared helper"
```

---

### Task 3: Core reporter `datasets_stochasticity.py`

**Files:**
- Create: `science/src/science_tool/datasets_stochasticity.py`
- Test: `science/tests/test_datasets_stochasticity.py`

**Interfaces:**
- Consumes: Task 1 `resolve_run_chain` + `RunChainResolution`, `_is_fingerprinted`-equivalent marker (`SCI_NS.fingerprintPolicy`), Task 2 `steps_and_methods_for_workflow`, `project_entity_uri` (`graph.dataset_usage`), `canonical_id_from_entity_uri` (`graph.store.identity`), `RunFingerprint` / `Stochasticity`, `load_project_sources`, `ReferenceResolver`, `parse_frontmatter`.
- Produces:
  - `@dataclass(frozen=True) class StepReport: step_id: str; method_id: str; stochasticity: Stochasticity | None; realized_seeds: dict[str, int]; rationale: str`
  - `@dataclass(frozen=True) class StochasticityReport: dataset_id: str; run_id: str | None; named_run_id: str | None; inherited: bool; chain: list[str]; seed_policy_kind: str | None; stochastic_steps: list[StepReport]; deterministic_step_count: int; unresolved_reason: str | None`
  - Error hierarchy: `class DatasetStochasticityError(Exception)` (base), `class DatasetNotFoundError(DatasetStochasticityError)`, `class GraphNotBuiltError(DatasetStochasticityError)`. The graph/source-disagreement case raises the base `DatasetStochasticityError` (a real internal inconsistency, not a "not found"). The CLI maps the whole hierarchy to exit 1.
  - `report_dataset_stochasticity(project_root: Path, dataset_ref: str) -> StochasticityReport`

**Semantics:**
- Resolve `dataset_ref` (accept `slug` or `dataset:slug`) to a canonical `dataset:` id; if no such entity file exists → raise `DatasetNotFoundError` (CLI maps to exit 1).
- Parse `knowledge/graph.trig`; if missing → `GraphNotBuiltError`.
- `resolve_run_chain` on the dataset URI. If `run is None`: return a report with `run_id=None`, `named_run_id` = the named-but-unfingerprinted run (or None), `unresolved_reason=<reason.value>`, empty step lists, `chain` mapped to canonical ids.
- Else map run URI → `workflow-run:<slug>`, read that entity's `fingerprint:` → `RunFingerprint`. If the graph marks it fingerprinted but the source `fingerprint:` is missing/unparseable → raise `DatasetStochasticityError` (fail loud: graph and source disagree).
- Load sources with `strict_core_schema=False`, then **fail loud** (`DatasetStochasticityError`) if any `workflow-step` or `method` entity was skipped — a silently dropped step shrinks the step set and underreports stochasticity, exactly as register-run's `_reject_skipped_steps` guards. Mirror that guard here rather than trusting a lossy load.
- Reverse-index the run's `workflow` steps (Task 2). A step is **stochastic** iff its method's `stochasticity` is `seedable` or `nondeterministic`, OR the method is unclassified (`None`) — an unclassified method cannot be asserted deterministic, so surface it rather than hide it. `deterministic_step_count` counts steps whose method is `deterministic`. For each stochastic step, `realized_seeds = fingerprint.step_seeds.get(step.id, {})` and `rationale = step.rationale`.
- `inherited = len(chain) > 1`; `chain` is the member_of dataset ids in order.

- [ ] **Step 1: Write the failing tests**

`science/tests/test_datasets_stochasticity.py` — build a project with a workflow, three methods (seedable+bound, nondeterministic, deterministic), three steps, and a run entity carrying a **registered** fingerprint, then build the graph and report. (Use the register-run path to produce the fingerprint so the test exercises the real capture, not a hand-authored one.)

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.datasets_stochasticity import (
    DatasetNotFoundError,
    report_dataset_stochasticity,
)

# Reuse the conftest fixture that scaffolds a registrable run project. The exact
# fixture name is discovered in Step 2; this test assumes `registrable_run_project`
# returns (project_root, dataset_id) after `register-run` has been executed.


def test_reports_seeded_and_nondeterministic_steps(registrable_run_project):
    project_root, dataset_id = registrable_run_project
    report = report_dataset_stochasticity(project_root, dataset_id)

    assert report.run_id is not None
    kinds = {s.step_id: s.stochasticity.value for s in report.stochastic_steps}
    assert "seedable" in kinds.values()
    assert "nondeterministic" in kinds.values()
    seeded = next(s for s in report.stochastic_steps if s.stochasticity.value == "seedable")
    assert seeded.realized_seeds  # non-empty
    assert report.deterministic_step_count >= 1


def test_unknown_dataset_raises(tmp_path):
    (tmp_path / "science.yaml").write_text("id: project:x\nname: X\nprofile: software\n", encoding="utf-8")
    with pytest.raises(DatasetNotFoundError):
        report_dataset_stochasticity(tmp_path, "dataset:does-not-exist")
```

- [ ] **Step 2: Discover / build the fixture and run the tests to see them fail**

`cd science && grep -rn "register-run\|REGISTER_RUN_EXECUTION_FRONTMATTER\|def .*run.*project\|persist_run_fingerprint" tests/conftest.py tests/test_workflow_registration_e2e.py | head`
If a fixture that scaffolds a registrable run + runs register-run already exists (e.g. in `test_workflow_registration_e2e.py`), lift it into `tests/conftest.py` as `registrable_run_project` returning `(project_root, dataset_id)`. Otherwise author it in `conftest.py`: write workflow/method/step/run entities and the run's `results/` datapackage+config (methods: one `seedable` with `seed_params` + a step binding `literal:42`; one `nondeterministic` + a step with `rationale`; one `deterministic`), then, **in this order**: (1) `science dataset register-run workflow-run:<slug>` — this writes the run's captured `fingerprint:` and creates the derived dataset entities; (2) `science graph build` — *after* registration, so `graph.trig` carries the `sci:fingerprintPolicy` marker and the derived dataset's derivation edge. Building before registering is the bug that makes the reporter see a stale graph and report no fingerprinted run. Return the produced derived `dataset:` id and the project root. Reuse `REGISTER_RUN_EXECUTION_FRONTMATTER` for the run's `execution:` block. (register-run reads the source layer, not the graph, so it needs no pre-built graph.)
Run: `cd science && uv run --frozen pytest tests/test_datasets_stochasticity.py -q --junitxml=/tmp/t3.xml`
Expected: FAIL — `ModuleNotFoundError: science_tool.datasets_stochasticity`.

- [ ] **Step 3: Implement the reporter**

Create `science/src/science_tool/datasets_stochasticity.py`:

```python
"""Reader-facing stochasticity report for a derived dataset (umbrella Spec 3).

Graph resolves `dataset -> fingerprinted run` and the `member_of` chain; the
source layer supplies the fingerprint's realized `step_seeds`, the workflow's
steps, and each step's method `stochasticity`. Read-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

from rdflib import Dataset, Graph, URIRef
from science_model.entities import Stochasticity
from science_model.frontmatter import parse_frontmatter
from science_model.run_fingerprint import RunFingerprint

from science_tool.graph.dataset_usage import project_entity_uri
from science_tool.graph.io import SCI_NS
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.run_resolution import RunChainResolution, resolve_run_chain
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store.identity import canonical_id_from_entity_uri
from science_tool.workflow_steps_index import steps_and_methods_for_workflow

# The named-graph URI `_graph_uri("graph/knowledge")` yields. Import and call it
# (Step 3a) rather than keeping a literal — a wrong URI parses to an EMPTY graph
# silently. Shown here as the call, not a guessed constant:
from science_tool.graph.store.<module> import _graph_uri  # resolved in Step 3a


class DatasetStochasticityError(Exception):
    """Base for stochasticity-report failures."""


class DatasetNotFoundError(DatasetStochasticityError):
    """The dataset ref does not resolve to a dataset entity."""


class GraphNotBuiltError(DatasetStochasticityError):
    """`knowledge/graph.trig` is absent; the report needs a built graph."""


@dataclass(frozen=True)
class StepReport:
    step_id: str
    method_id: str
    stochasticity: Stochasticity | None
    realized_seeds: dict[str, int] = field(default_factory=dict)
    rationale: str = ""


@dataclass(frozen=True)
class StochasticityReport:
    dataset_id: str
    run_id: str | None
    named_run_id: str | None
    inherited: bool
    chain: list[str]
    seed_policy_kind: str | None
    stochastic_steps: list[StepReport]
    deterministic_step_count: int
    unresolved_reason: str | None


def _is_fingerprinted(knowledge: Graph, run_uri: URIRef) -> bool:
    return (run_uri, SCI_NS.fingerprintPolicy, None) in knowledge


def _canonical_dataset_id(project_root: Path, dataset_ref: str) -> str:
    slug = dataset_ref.removeprefix("dataset:")
    path = project_root / "entities" / "datasets" / f"{slug}.md"
    if not path.is_file():
        raise DatasetNotFoundError(f"no dataset entity: dataset:{slug} ({path})")
    return f"dataset:{slug}"


def _load_knowledge(project_root: Path) -> Graph:
    graph_path = project_root / "knowledge" / "graph.trig"
    if not graph_path.is_file():
        raise GraphNotBuiltError(f"graph not built ({graph_path}); run `science graph build`")
    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    return dataset.graph(_graph_uri("graph/knowledge"))


def _run_id_of(uri: URIRef) -> str:
    return canonical_id_from_entity_uri(str(uri)) or str(uri)


def _reject_skipped_stochasticity_sources(sources) -> None:
    """A skipped workflow-step or method underreports stochasticity — fail loud.

    Mirrors register-run's `_reject_skipped_steps`: the non-strict load silently
    drops any entity that fails schema validation, and a dropped step shrinks the
    workflow's step set. Read the loader's own `skipped_entities` record.
    """
    for skipped in sources.skipped_entities:
        if skipped.kind in ("workflow-step", "method"):
            raise DatasetStochasticityError(
                f"{skipped.path} ({skipped.kind}) failed schema validation and was skipped "
                f"({skipped.reason}); stochasticity would be underreported. Run "
                f"`science validate` and fix it."
            )


def _read_run_fingerprint(project_root: Path, run_id: str) -> tuple[str, RunFingerprint]:
    slug = run_id.removeprefix("workflow-run:")
    path = project_root / "entities" / "workflow-runs" / f"{slug}.md"
    parsed = parse_frontmatter(path)  # takes a Path; returns (fm, body) | None
    if parsed is None:
        raise DatasetStochasticityError(
            f"{run_id} is marked fingerprinted in the graph but {path} has no frontmatter"
        )
    fm, _body = parsed
    raw = fm.get("fingerprint")
    if not raw:
        raise DatasetStochasticityError(
            f"{run_id} is marked fingerprinted in the graph but its entity carries no "
            f"`fingerprint:`; rebuild the graph or re-register the run"
        )
    return str(fm.get("workflow") or ""), RunFingerprint.model_validate(raw)


def report_dataset_stochasticity(project_root: Path, dataset_ref: str) -> StochasticityReport:
    dataset_id = _canonical_dataset_id(project_root, dataset_ref)
    knowledge = _load_knowledge(project_root)
    ds_uri = project_entity_uri(dataset_id)

    resolution: RunChainResolution = resolve_run_chain(
        knowledge, ds_uri, partial(_is_fingerprinted, knowledge)
    )
    chain_ids = [canonical_id_from_entity_uri(str(u)) or str(u) for u in resolution.chain]
    named_run_id = _run_id_of(resolution.named_run) if resolution.named_run is not None else None

    if resolution.run is None:
        reason = resolution.reasons[0].value if resolution.reasons else None
        return StochasticityReport(
            dataset_id=dataset_id, run_id=None, named_run_id=named_run_id,
            inherited=len(resolution.chain) > 1, chain=chain_ids, seed_policy_kind=None,
            stochastic_steps=[], deterministic_step_count=0, unresolved_reason=reason,
        )

    run_id = _run_id_of(resolution.run)
    workflow_id_ref, fingerprint = _read_run_fingerprint(project_root, run_id)

    sources = load_project_sources(project_root, strict_core_schema=False)
    _reject_skipped_stochasticity_sources(sources)
    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)
    workflow_id = resolver.resolve(workflow_id_ref).canonical_id or workflow_id_ref
    pairs = steps_and_methods_for_workflow(sources, resolver, workflow_id)

    stochastic: list[StepReport] = []
    deterministic = 0
    for step, method in pairs:
        s = method.stochasticity if method is not None else None
        if s is Stochasticity.DETERMINISTIC:
            deterministic += 1
            continue
        stochastic.append(
            StepReport(
                step_id=step.id,
                method_id=method.id if method is not None else step.method,
                stochasticity=s,
                realized_seeds=dict(fingerprint.step_seeds.get(step.id, {})),
                rationale=step.rationale,
            )
        )

    return StochasticityReport(
        dataset_id=dataset_id, run_id=run_id, named_run_id=named_run_id,
        inherited=len(resolution.chain) > 1, chain=chain_ids,
        seed_policy_kind=fingerprint.seed_policy.kind, stochastic_steps=stochastic,
        deterministic_step_count=deterministic, unresolved_reason=None,
    )
```

- [ ] **Step 3a: Resolve the `_graph_uri` import and the knowledge-graph URI**

`cd science && grep -rn "def _graph_uri" src/science_tool/graph/store/*.py`
Replace the `from science_tool.graph.store.<module> import _graph_uri` placeholder with the real module, and confirm `_graph_uri("graph/knowledge")` is the string the trig file names its knowledge graph. If `_graph_uri` is private/awkward to import, mirror how `graph/store/validation.py` obtains the knowledge graph (`_knowledge_and_provenance` calls `dataset.graph(_graph_uri("graph/knowledge"))`) — reuse that exact call. Do not guess a literal — a wrong URI parses to an empty graph silently.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_datasets_stochasticity.py -q --junitxml=/tmp/t3.xml` and read the xml.
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets_stochasticity.py science/tests/test_datasets_stochasticity.py science/tests/conftest.py
git commit --no-verify -m "Report a derived dataset's stochastic steps and realized seeds"
```

---

### Task 4: CLI command `science dataset stochasticity`

**Files:**
- Modify: `science/src/science_tool/cli.py` (add command to `dataset_group`, after `register-run`)
- Create: `science/src/science_tool/datasets_stochasticity_format.py` (human + json rendering)
- Test: `science/tests/test_datasets_stochasticity_cli.py`

**Interfaces:**
- Consumes: Task 3 `report_dataset_stochasticity`, `StochasticityReport`, `StepReport`, `DatasetNotFoundError`; `_project_root_from_env` (existing in cli.py).
- Produces:
  - `render_human(report: StochasticityReport) -> list[str]`
  - `render_json(report: StochasticityReport) -> dict` (dataclass → plain dict, `stochasticity` as its `.value` or `null`)

- [ ] **Step 1: Write the failing tests**

`science/tests/test_datasets_stochasticity_cli.py`:

```python
from __future__ import annotations

import json

from click.testing import CliRunner

from science_tool.cli import main  # root click group (confirmed against current main)


def test_human_output_names_run_and_steps(registrable_run_project):
    project_root, dataset_id = registrable_run_project
    result = CliRunner().invoke(
        main, ["dataset", "stochasticity", dataset_id, "--project-root", str(project_root)]
    )
    assert result.exit_code == 0, result.output
    assert "run:" in result.output
    assert "nondeterministic" in result.output


def test_json_output_is_machine_readable(registrable_run_project):
    project_root, dataset_id = registrable_run_project
    result = CliRunner().invoke(
        cli,
        ["dataset", "stochasticity", dataset_id, "--project-root", str(project_root), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["run_id"] is not None
    assert isinstance(payload["stochastic_steps"], list)


def test_unknown_dataset_exits_nonzero(tmp_path):
    (tmp_path / "science.yaml").write_text("id: project:x\nname: X\nprofile: software\n", encoding="utf-8")
    result = CliRunner().invoke(
        main, ["dataset", "stochasticity", "dataset:nope", "--project-root", str(tmp_path)]
    )
    assert result.exit_code == 1
```

- [ ] **Step 2: Confirm the root CLI group symbol and run the tests to see them fail**

`cd science && grep -n "^def cli\|^cli =\|@click.group" src/science_tool/cli.py | head`
Use the actual root group symbol in the test import. Run:
`cd science && uv run --frozen pytest tests/test_datasets_stochasticity_cli.py -q --junitxml=/tmp/t4.xml`
Expected: FAIL — no such command `stochasticity`.

- [ ] **Step 3: Implement the formatter**

Create `science/src/science_tool/datasets_stochasticity_format.py`:

```python
"""Render a StochasticityReport as human lines or a JSON-ready dict."""

from __future__ import annotations

from science_tool.datasets_stochasticity import StochasticityReport


def render_json(report: StochasticityReport) -> dict:
    return {
        "dataset_id": report.dataset_id,
        "run_id": report.run_id,
        "named_run_id": report.named_run_id,
        "inherited": report.inherited,
        "chain": report.chain,
        "seed_policy_kind": report.seed_policy_kind,
        "deterministic_step_count": report.deterministic_step_count,
        "unresolved_reason": report.unresolved_reason,
        "stochastic_steps": [
            {
                "step_id": s.step_id,
                "method_id": s.method_id,
                "stochasticity": s.stochasticity.value if s.stochasticity is not None else None,
                "realized_seeds": s.realized_seeds,
                "rationale": s.rationale,
            }
            for s in report.stochastic_steps
        ],
    }


def render_human(report: StochasticityReport) -> list[str]:
    lines: list[str] = []
    if report.run_id is None:
        if report.named_run_id is not None:
            lines.append(
                f"{report.dataset_id}: resolves to {report.named_run_id}, but it is not "
                f"fingerprinted ({report.unresolved_reason})"
            )
        else:
            lines.append(f"{report.dataset_id}: no fingerprinted run ({report.unresolved_reason})")
        return lines

    suffix = " (inherited)" if report.inherited else ""
    lines.append(f"run: {report.run_id}{suffix}")
    if report.inherited:
        lines.append("  " + " <- member_of <- ".join(report.chain))
    lines.append(f"seed policy: {report.seed_policy_kind}")
    lines.append("")

    total = len(report.stochastic_steps) + report.deterministic_step_count
    lines.append(f"stochastic steps ({len(report.stochastic_steps)} of {total}):")
    for s in report.stochastic_steps:
        klass = s.stochasticity.value if s.stochasticity is not None else "unclassified"
        seeds = ", ".join(f"{k}={v}" for k, v in sorted(s.realized_seeds.items())) or "no realized seed"
        line = f"  {s.step_id}  {klass}  {seeds}"
        if s.stochasticity is not None and s.stochasticity.value == "nondeterministic":
            note = " - not exactly reproducible" + (f": {s.rationale}" if s.rationale else "")
            line += note
        lines.append(line)
    if report.deterministic_step_count:
        lines.append(f"deterministic steps: {report.deterministic_step_count} (omitted)")
    return lines
```

- [ ] **Step 4: Add the CLI command**

In `science/src/science_tool/cli.py`, immediately after the `dataset_register_run` function (ends ~line 7336), add:

```python
@dataset_group.command("stochasticity")
@click.argument("ref")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
@click.option("--format", "output_format", type=click.Choice(["human", "json"]), default="human")
def dataset_stochasticity(ref: str, project_root: Path | None, output_format: str) -> None:
    """Report which steps in a derived dataset's provenance were stochastic.

    Names the fingerprinted run the dataset inherited its provenance from, the
    seeds that run realized, and which steps are nondeterministic and therefore
    not exactly reproducible.
    """
    import json as _json

    from science_tool.datasets_stochasticity import (
        DatasetStochasticityError,
        report_dataset_stochasticity,
    )
    from science_tool.datasets_stochasticity_format import render_human, render_json

    root = project_root.resolve() if project_root else _project_root_from_env()
    try:
        report = report_dataset_stochasticity(root, ref)
    except DatasetStochasticityError as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(1)

    if output_format == "json":
        click.echo(_json.dumps(render_json(report), indent=2))
    else:
        for line in render_human(report):
            click.echo(line)
```

- [ ] **Step 5: Run the CLI tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_datasets_stochasticity_cli.py -q --junitxml=/tmp/t4.xml` and read the xml.
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/cli.py science/src/science_tool/datasets_stochasticity_format.py science/tests/test_datasets_stochasticity_cli.py
git commit --no-verify -m "Add `science dataset stochasticity` reader command"
```

---

### Task 5: Inherited-provenance integration test + full-suite gate

**Files:**
- Modify: `science/tests/test_datasets_stochasticity.py` (add the member_of case)

**Interfaces:**
- Consumes: Task 3 reporter; the `registrable_run_project` fixture.

- [ ] **Step 1: Write the inherited-chain test**

Extend the fixture (or add a sibling) so the run produces a parent dataset and a **member** dataset joined by `member_of`, then assert the report on the member names the parent's run and marks it inherited:

```python
def test_member_dataset_inherits_and_displays_the_chain(registrable_member_project):
    project_root, member_dataset_id, run_id = registrable_member_project
    report = report_dataset_stochasticity(project_root, member_dataset_id)
    assert report.run_id == run_id
    assert report.inherited is True
    assert len(report.chain) >= 2
    assert report.chain[0] == member_dataset_id
```

Author `registrable_member_project` in `conftest.py` if no member/`member_of` scaffold exists: take the Task-3 project, add a member dataset whose derivation is `member_of` the run-produced parent, rebuild the graph, and return `(project_root, member_dataset_id, run_id)`.

- [ ] **Step 2: Run the new test to verify it fails, then passes**

Run: `cd science && uv run --frozen pytest tests/test_datasets_stochasticity.py -q --junitxml=/tmp/t5.xml`
If it fails only because the fixture is missing, add the fixture; if it fails on `inherited`/`chain`, fix the reporter's `chain` mapping. Expected end state: pass.

- [ ] **Step 3: Full gate — suite, lint, types**

```bash
cd science && uv run --frozen pytest -q --junitxml=/tmp/full.xml   # read <testsuite ...>
cd science && uv run ruff check
cd science && uv run pyright   # pyrightconfig.json at the repo root governs; it walks up
```
Expected: science suite green (baseline was 7832 passing; new tests add to it), ruff clean, pyright 0 errors.

- [ ] **Step 4: Model suite sanity (no model change expected)**

`cd science/model && uv run --frozen pytest -q --junitxml=/tmp/model.xml` — expected unchanged (991 passing). This task adds no model code; run it only to confirm nothing was disturbed.

- [ ] **Step 5: Commit**

```bash
git add science/tests/test_datasets_stochasticity.py science/tests/conftest.py
git commit --no-verify -m "Cover inherited member_of provenance in the stochasticity report"
```

---

## Post-implementation (controller, after all tasks green)

- Merge the feature branch `--no-ff` into local `main` (do **not** push; `origin/main` is already 34 behind and pushing is the user's call).
- Update `meta/tasks/active.md`: `science tasks note t089 …` recording the shipped command + the two behaviour-preserving refactors (chain resolver, shared step index), then `--status done`.
- Refresh the meta graph if any meta source changed (`science graph audit` → `graph build` from `meta/`).
- Update the umbrella design doc's Spec 3 "Done when" to reflect the shipped surface.
- Update memory `project_method_stochasticity_umbrella.md`: Spec 3 shipped, umbrella complete.

## Self-Review

- **Spec coverage:** dataset→run resolution (Task 1), source-layer step/method/fingerprint join (Tasks 2-3), stochastic + nondeterministic reporting with realized seeds (Task 3-4), inherited resolution with displayed chain (Tasks 1, 3, 5), read-only / no new graph facts (all). ✓
- **Placeholder scan:** every code step carries complete code; the three "confirm the exact symbol/path" steps (2, 3a, 4/Step2) are deliberate guards against guessing import paths/URIs, each with the grep that resolves it — not placeholders for logic.
- **Type consistency:** `RunChainResolution.chain: list[URIRef]`; reporter maps to `chain: list[str]`; `StepReport.stochasticity: Stochasticity | None` rendered as `.value`/`null` consistently in both formatter branches. `steps_and_methods_for_workflow` returns `list[tuple[WorkflowStepEntity, MethodEntity | None]]`, consumed identically in register (Task 2) and reporter (Task 3).
