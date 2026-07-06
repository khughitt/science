# Derived-Dataset Support-Cardinality Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class, opt-in "support-cardinality" gate to the `science` framework so an aggregating output that silently collapses below its declared contributor floor (the MM30 k=1 meta-analysis) fails at `validate` time instead of passing green.

**Architecture:** Three rails, each mirroring the existing identity-stamp/capability-fit machinery. (1) A declared floor: new `WorkflowOutputSupport` model + optional `support` field on `WorkflowOutput` (`science-model`), a sibling of the existing `identity` field. (2) A produced observation: `register-run` (`write_per_output_datapackages`) reads each run-aggregate resource's producer-authored `science.support`, reduces to the **min** observed count (null if any resource is unstamped), and writes it onto the per-output datapackage under `science.support`, beside the existing `science.identity_context`. (3) A verification check: a new `aggregation-support` `validate` check joins each derived dataset's declared floor to its produced observation and emits `Severity.ERROR` for below-floor / stamp-missing / malformed / unit-mismatch, `WARN` for below-expected. The framework never reads parquet; it trusts the producer's stamp exactly as it trusts the identity stamp.

**Tech Stack:** Python 3.11, Pydantic v2 (`extra="forbid"` models), Click CLI, pytest. Two packages: `science-model` (`~/d/science/science/model/`, the schema) and `science-tool` (`~/d/science/science/`, register-run + validate). The tool consumes the model via an editable uv source, so a model schema change is visible to the tool with no reinstall.

## Global Constraints

Every task's requirements implicitly include these (copied verbatim from the design):

- **Opt-in is the only strictness control.** An output is gated **iff** it declares a `support:` block. Outputs without one are never evaluated and never blocked. There is **no** `--strict` coupling and **no** auto-`undeclared` nudge in v1.
- **Blocking = `Severity.ERROR`.** `validate` exits 1 via `if result.errors or result.gated` (`validate/cli.py:105-106`); ERROR findings increment `result.errors`. Below-floor / stamp-missing / malformed-stamp / unit-mismatch are ERROR; below-expected is WARN.
- **Nested under `science`, never top-level.** The per-output datapackage carries the observation as `science.support`, in the same `science` block that already holds `identity_context` — not a top-level key.
- **The framework never reads produced data (parquet/feather).** Support is a producer-authored stamp; the tool only reads/propagates/verifies the stamp.
- **`observed` is a structural contributing-unit count, not `max(num_present)`.** It is the count of distinct contributing units wired into the aggregation, an artifact-level invariant — never the best-case per-row count.
- **Multi-resource rule = fail-closed.** For an opted-in output, **every** listed resource must carry `science.support`; the output observation is the **min** of their `observed`; if **any** resource is unstamped, the propagated observation is `observed: null` (→ `stamp-missing`).
- **Scope: `science` framework only** — contract + stamp propagation + one `validate` check + docs. No `science-commons`, no backfill of existing datasets, no `dataset list`/`prioritize` columns, no MM30 pipeline edits (the MM30 shape is exercised only as a `science` test fixture; real MM30 adoption is a follow-up).
- **`extra="forbid"`** on both `WorkflowOutput` (existing) and the new `WorkflowOutputSupport` model.
- **No AI-attribution trailer/footer** in any commit message.
- **Paths in docs use `~/d/...`,** never `/home/keith/...` or absolute machine paths.

## File Structure

**`science-model` (schema):**
- Modify `science/model/src/science_model/packages/schema.py` — add `WorkflowOutputSupport` model + `support` field on `WorkflowOutput` (Task 1).
- Create `science/model/tests/test_workflow_output_support_models.py` — contract-parsing tests (Task 1).

**`science-tool` (register-run + validate):**
- Modify `science/src/science_tool/datasets_register.py` — extend `write_per_output_datapackages` to reduce+propagate `science.support` (Task 2).
- Modify `science/tests/test_dataset_register_run.py` — propagation tests (Task 2).
- Create `science/src/science_tool/validate/checks/aggregation_support.py` — the check (pure core + ctx wrapper) (Task 3).
- Modify `science/src/science_tool/validate/checks/__init__.py` — register the module (Task 3).
- Create `science/tests/validate/test_checks_aggregation_support.py` — check-logic + registration + runner e2e + CLI-exit tests (Task 3).

**Docs:**
- Modify `science/templates/workflow.md` (or wherever the workflow authoring template lives — confirm in Task 4) — add a commented `support:` example under `outputs[]`.
- Modify the workflow-outputs authoring section of the user guide (confirm path in Task 4) — document the floor, the stamp handoff, and the gate semantics.
- Create `science/docs/... support-cardinality authoring note` if no existing section fits (Task 4).

**Test commands (verbatim):**
- Model: `cd ~/d/science/science/model && uv run pytest tests/test_workflow_output_support_models.py -q`
- Tool: `cd ~/d/science/science && uv run pytest tests/... -q`

---

### Task 1: `WorkflowOutputSupport` contract + `support` field on `WorkflowOutput`

**Files:**
- Modify: `science/model/src/science_model/packages/schema.py` (add model near `WorkflowOutput`, lines 459-468; imports already present at lines 1-8: `ConfigDict`, `Field`, `Literal`, `model_validator`)
- Test: `science/model/tests/test_workflow_output_support_models.py` (new; mirror `science/model/tests/test_workflow_output_identity_models.py`)

**Interfaces:**
- Consumes: nothing (leaf schema addition).
- Produces:
  - `WorkflowOutputSupport(BaseModel)` — `extra="forbid"`; fields `unit: Literal["dataset","cohort","sample","source"]`, `min: int` (`Field(strict=True, ge=1)`), `expected: int | None` (`Field(default=None, strict=True, ge=1)`); a `model_validator(mode="after")` rejecting `expected < min`.
  - `WorkflowOutput.support: WorkflowOutputSupport | None = None` (new optional field) + a `WorkflowOutput.model_validator(mode="after")` rejecting a declared `support` with empty `resource_names` (an aggregating output must have resources; this makes the empty case fail at parse time, so downstream reduction never hits an empty list).

- [ ] **Step 1: Write the failing tests**

Create `science/model/tests/test_workflow_output_support_models.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError
from science_model.packages.schema import WorkflowOutput, WorkflowOutputSupport


def _output(**support_kw) -> dict:
    base = {
        "slug": "survival-os-combined",
        "title": "Survival OS combined meta-analysis scores",
        "resource_names": ["survival_os_combined_gene", "survival_os_combined_gene_set"],
    }
    if support_kw:
        base["support"] = support_kw
    return base


def test_support_absent_leaves_field_none() -> None:
    output = WorkflowOutput.model_validate(_output())
    assert output.support is None


def test_support_block_parses() -> None:
    output = WorkflowOutput.model_validate(_output(unit="dataset", min=3, expected=5))
    assert output.support is not None
    assert output.support.unit == "dataset"
    assert output.support.min == 3
    assert output.support.expected == 5


def test_support_expected_optional() -> None:
    output = WorkflowOutput.model_validate(_output(unit="cohort", min=2))
    assert output.support is not None
    assert output.support.expected is None


def test_support_roundtrips_json() -> None:
    output = WorkflowOutput.model_validate(_output(unit="dataset", min=3, expected=5))
    dumped = output.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert dumped["support"] == {"unit": "dataset", "min": 3, "expected": 5}


def test_support_min_required_when_block_present() -> None:
    with pytest.raises(ValidationError):
        WorkflowOutput.model_validate(_output(unit="dataset", expected=5))


def test_support_min_must_be_ge_one() -> None:
    with pytest.raises(ValidationError):
        WorkflowOutput.model_validate(_output(unit="dataset", min=0))


def test_support_expected_below_min_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkflowOutput.model_validate(_output(unit="dataset", min=5, expected=3))


def test_support_unknown_unit_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkflowOutput.model_validate(_output(unit="gene", min=3))


def test_support_stray_key_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkflowOutputSupport.model_validate({"unit": "dataset", "min": 3, "floor": 2})


def test_support_min_must_be_strict_int() -> None:
    with pytest.raises(ValidationError):
        WorkflowOutput.model_validate(_output(unit="dataset", min=3.0))


def test_support_requires_non_empty_resource_names() -> None:
    with pytest.raises(ValidationError):
        WorkflowOutput.model_validate(
            {"slug": "x", "title": "X", "resource_names": [], "support": {"unit": "dataset", "min": 3}}
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_workflow_output_support_models.py -q`
Expected: FAIL — `ImportError: cannot import name 'WorkflowOutputSupport'` (and `support` unknown key rejected by `extra="forbid"`).

- [ ] **Step 3: Add the model and field**

In `science/model/src/science_model/packages/schema.py`, **immediately above** the `WorkflowOutput` class (currently line 459), add:

```python
class WorkflowOutputSupport(BaseModel):
    """Declared support-cardinality floor on a workflow ``outputs[]`` entry.

    The floor an aggregating output must not fall below. Distinct from the produced
    stamp: this is the declaration; the observation is written onto the per-output
    datapackage under ``science.support`` by ``register-run``.
    """

    unit: Literal["dataset", "cohort", "sample", "source"]
    min: int = Field(strict=True, ge=1)
    expected: int | None = Field(default=None, strict=True, ge=1)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _expected_ge_min(self) -> "WorkflowOutputSupport":
        if self.expected is not None and self.expected < self.min:
            raise ValueError("support.expected must be >= support.min")
        return self
```

Then add the field to `WorkflowOutput` (currently line 467, right after `identity`):

```python
    identity: WorkflowOutputIdentity | None = None
    support: WorkflowOutputSupport | None = None
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _support_requires_resources(self) -> "WorkflowOutput":
        if self.support is not None and not self.resource_names:
            raise ValueError("outputs[].support requires a non-empty resource_names")
        return self
```

> If `WorkflowOutput` already carries a `model_validator(mode="after")`, add this check to the existing method body rather than declaring a second one.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_workflow_output_support_models.py -q`
Expected: PASS (11 tests).

- [ ] **Step 5: Run the surrounding model suite to confirm no regressions**

Run: `cd ~/d/science/science/model && uv run pytest tests/test_workflow_output_identity_models.py -q`
Expected: PASS (existing identity tests unaffected — `support` is optional and defaults to `None`).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/science
git add model/src/science_model/packages/schema.py model/tests/test_workflow_output_support_models.py
git commit -m "feat(schema): add WorkflowOutputSupport floor to WorkflowOutput"
```

---

### Task 2: `register-run` propagates `science.support` onto per-output datapackages

**Files:**
- Modify: `science/src/science_tool/datasets_register.py` — `write_per_output_datapackages` (lines 81-134); the identity attach point is lines 129-131.
- Test: `science/tests/test_dataset_register_run.py` (extend; mirror `test_register_run_writes_per_output_datapackages` at lines 108-136 and the `science`-namespace assertion at lines 369-406).

**Interfaces:**
- Consumes: `WorkflowOutput.support` from Task 1 (visible after `_read_workflow_outputs` validates each output; a declared `support` block survives into `out["support"]` only because the model now accepts it).
- Produces: per-output `datapackage.yaml` carries `science.support = {"unit": <str>, "observed": <int|null|raw>}` for opted-in outputs, coexisting with `science.identity_context`. Reduction rule: min over resources' `observed`; `observed: null` if any resource is unstamped; a malformed resource `observed` is passed through verbatim (so the check, not register-run, is the authority on malformedness). **Conflicting resource units fail loudly:** if an opted-in output's stamped resources disagree on `unit`, `register-run` raises `ValueError` (a single reduced `unit` cannot faithfully represent two, and silently keeping the first would hide the second resource's mismatch from the check — the exact gap this closes).

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_dataset_register_run.py` (reuse the module's existing `_seed_workflow_and_run`, `_seed_resource_files`, `_run_register`/`CliRunner` helpers; a run-aggregate resource dict is written verbatim, so a `science` key on it flows into the run datapackage):

```python
def test_register_run_propagates_support_min_over_resources(tmp_path: Path) -> None:
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[
            {"name": "gene", "path": "gene.csv", "format": "csv", "bytes": 100, "hash": "sha256:a",
             "science": {"support": {"unit": "dataset", "observed": 5}}},
            {"name": "gene_set", "path": "gene_set.csv", "format": "csv", "bytes": 100, "hash": "sha256:b",
             "science": {"support": {"unit": "dataset", "observed": 4}}},
        ],
        workflow_outputs=[
            {"slug": "combined", "title": "Combined", "resource_names": ["gene", "gene_set"],
             "ontology_terms": [], "support": {"unit": "dataset", "min": 3, "expected": 5}},
        ],
    )
    _seed_resource_files(tmp_path, ["gene", "gene_set"])
    res = _run_register(tmp_path)
    assert res.exit_code == 0, res.output
    dp = yaml.safe_load(
        (tmp_path / "results" / "wf" / "r1" / "combined" / "datapackage.yaml").read_text(encoding="utf-8")
    )
    assert dp["science"]["support"] == {"unit": "dataset", "observed": 4}


def test_register_run_support_null_when_a_resource_unstamped(tmp_path: Path) -> None:
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[
            {"name": "gene", "path": "gene.csv", "format": "csv", "bytes": 100, "hash": "sha256:a",
             "science": {"support": {"unit": "dataset", "observed": 5}}},
            {"name": "gene_set", "path": "gene_set.csv", "format": "csv", "bytes": 100, "hash": "sha256:b"},
        ],
        workflow_outputs=[
            {"slug": "combined", "title": "Combined", "resource_names": ["gene", "gene_set"],
             "ontology_terms": [], "support": {"unit": "dataset", "min": 3}},
        ],
    )
    _seed_resource_files(tmp_path, ["gene", "gene_set"])
    res = _run_register(tmp_path)
    assert res.exit_code == 0, res.output
    dp = yaml.safe_load(
        (tmp_path / "results" / "wf" / "r1" / "combined" / "datapackage.yaml").read_text(encoding="utf-8")
    )
    assert dp["science"]["support"]["observed"] is None


def test_register_run_fails_on_conflicting_resource_units(tmp_path: Path) -> None:
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[
            {"name": "gene", "path": "gene.csv", "format": "csv", "bytes": 100, "hash": "sha256:a",
             "science": {"support": {"unit": "dataset", "observed": 5}}},
            {"name": "gene_set", "path": "gene_set.csv", "format": "csv", "bytes": 100, "hash": "sha256:b",
             "science": {"support": {"unit": "cohort", "observed": 4}}},
        ],
        workflow_outputs=[
            {"slug": "combined", "title": "Combined", "resource_names": ["gene", "gene_set"],
             "ontology_terms": [], "support": {"unit": "dataset", "min": 3}},
        ],
    )
    _seed_resource_files(tmp_path, ["gene", "gene_set"])
    res = _run_register(tmp_path)
    assert res.exit_code != 0
    assert "conflicting support units" in res.output


def test_register_run_no_support_block_writes_no_support(tmp_path: Path) -> None:
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[
            {"name": "gene", "path": "gene.csv", "format": "csv", "bytes": 100, "hash": "sha256:a",
             "science": {"support": {"unit": "dataset", "observed": 5}}},
        ],
        workflow_outputs=[
            {"slug": "combined", "title": "Combined", "resource_names": ["gene"], "ontology_terms": []},
        ],
    )
    _seed_resource_files(tmp_path, ["gene"])
    res = _run_register(tmp_path)
    assert res.exit_code == 0, res.output
    dp = yaml.safe_load(
        (tmp_path / "results" / "wf" / "r1" / "combined" / "datapackage.yaml").read_text(encoding="utf-8")
    )
    assert "support" not in (dp.get("science") or {})
```

> If this module lacks a `_run_register` helper, use the inline `CliRunner().invoke(science_cli, ["dataset", "register-run", "workflow-run:wf-r1"], catch_exceptions=False, env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})` form shown at lines 118-124 of the same file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run pytest tests/test_dataset_register_run.py -q -k "support or conflicting"`
Expected: FAIL — `KeyError`/`AssertionError`: no `science.support` key on the per-output datapackage (and the conflicting-units test does not yet raise).

- [ ] **Step 3: Implement the reduction + propagation**

In `science/src/science_tool/datasets_register.py`, add this module-level helper (place it near `_read_run_aggregate_datapackage`, ~line 65):

```python
def _reduce_output_support(out: dict, resources: list[dict]) -> dict | None:
    """Reduce producer-authored per-resource ``science.support`` to one per-output stamp.

    Returns None when the output declares no ``support`` floor (not opted in).
    For an opted-in output every resource must carry ``science.support``; the
    observation is the min of their ``observed``. If any resource is unstamped,
    ``observed`` is None (stamp-missing). A malformed ``observed`` is passed
    through verbatim so the validate check, not register-run, judges it. If the
    stamped resources disagree on ``unit``, raise (a single reduced unit cannot
    represent two, and keeping the first would hide the second's mismatch).
    """
    if out.get("support") is None:
        return None
    stamps: list[dict] = []
    for r in resources:
        s = (r.get("science") or {}).get("support")
        if not isinstance(s, dict):
            return {"observed": None}
        stamps.append(s)
    # resource_names is non-empty (WorkflowOutput validator), so stamps is non-empty here.
    units = {s.get("unit") for s in stamps}
    if len(units) > 1:
        raise ValueError(
            f"output {out.get('slug')!r}: resources declare conflicting support units "
            f"{sorted(map(str, units))}"
        )
    unit = stamps[0].get("unit")
    observeds = [s.get("observed") for s in stamps]
    if all(isinstance(o, int) and not isinstance(o, bool) and o >= 0 for o in observeds):
        return {"unit": unit, "observed": min(observeds)}
    # at least one malformed observed: surface it (do not coerce), unit from the (single) stamped unit
    bad = next(o for o in observeds if not (isinstance(o, int) and not isinstance(o, bool) and o >= 0))
    return {"unit": unit, "observed": bad}
```

Then replace the identity attach block (currently lines 128-131):

```python
        resolved_identity = resolutions.get(str(out["slug"]))
        if resolved_identity is not None and resolved_identity.identity_context:
            out_dp["science"] = {"identity_context": derive_stamp(resolved_identity.identity_context)}
```

with an additive `science` block that carries both identity and support:

```python
        science_block: dict = {}
        resolved_identity = resolutions.get(str(out["slug"]))
        if resolved_identity is not None and resolved_identity.identity_context:
            science_block["identity_context"] = derive_stamp(resolved_identity.identity_context)
        support_stamp = _reduce_output_support(out, out_resources)
        if support_stamp is not None:
            science_block["support"] = support_stamp
        if science_block:
            out_dp["science"] = science_block
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_dataset_register_run.py -q -k "support or conflicting"`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the full register-run suite to confirm identity coexistence is intact**

Run: `cd ~/d/science/science && uv run pytest tests/test_dataset_register_run.py -q`
Expected: PASS — the existing identity/per-output tests (incl. `test_register_run_bare_inherit_uses_shared_input_identity`) still pass; `science.identity_context` unchanged when no support block, and coexists when both present.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/datasets_register.py tests/test_dataset_register_run.py
git commit -m "feat(register-run): propagate producer support stamp to per-output datapackage"
```

---

### Task 3: `aggregation-support` validate check + registration

**Files:**
- Create: `science/src/science_tool/validate/checks/aggregation_support.py` (mirror `validate/checks/dataset_capabilities.py`: pure `evaluate_*` generator + thin `@Check`-decorated `ctx` wrapper + `_result` helper).
- Modify: `science/src/science_tool/validate/checks/__init__.py` — add `"aggregation_support"` to the `CANONICAL_CHECK_MODULES` tuple (near `dataset_capabilities` at line 54).
- Test: `science/tests/validate/test_checks_aggregation_support.py` (new; mirror `tests/validate/test_checks_dataset_capabilities.py` — plain-dict unit tests + registration test + `run(...)` e2e + CLI-exit).

**Interfaces:**
- Consumes: the floor from Task 1 (`workflow.outputs[].support`, read as raw frontmatter dicts) and the observation from Task 2 (`science.support` on the per-output datapackage). `Result`/`Severity` from `science_tool.validate.result` (`Result(severity, path, line, message, rule, task)` — positional; entity id lives inside `message`). `entity_frontmatters(ctx)`, `ValidateContext` (`ctx.project_root`, `ctx.read_yaml(path)`). `Check` decorator from `science_tool.validate.checks`.
- Produces: check codes `aggregation-support.below-floor` (ERROR), `.stamp-missing` (ERROR), `.malformed-stamp` (ERROR), `.unit-mismatch` (ERROR), `.below-expected` (WARN). A pure core `evaluate_aggregation_support(entities, read_datapackage)` where `read_datapackage: Callable[[str], dict | None]` is injected (returns `None` when the datapackage file is absent), so unit tests run on plain dicts without touching disk.

**Join path (verified against the code):** per-output datapackages carry profile `science-pkg-runtime-1.0`, so they are **not** in `entity_frontmatters` (which filters to `science-pkg-entity-1.0`). The join therefore goes through the derived **dataset entity** markdown, whose frontmatter carries `derivation.workflow` (a `workflow:` id) and `datapackage:` (a project-root-relative path ending `<slug>/datapackage.yaml`, so `slug = PurePosixPath(datapackage).parent.name`). The floor is read from the **workflow** entity's `outputs[]`; the observation from that datapackage's `science.support`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/validate/test_checks_aggregation_support.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml
from science_tool.validate.result import Severity


def _workflow(outputs: list[dict]) -> dict:
    return {
        "id": "workflow:meta",
        "kind": "workflow",
        "_path": "entities/workflows/meta.md",
        "outputs": outputs,
    }


def _dataset(slug: str = "combined", **kw) -> dict:
    base = {
        "id": f"dataset:wf-r1-{slug}",
        "kind": "dataset",
        "_path": f"entities/datasets/wf-r1-{slug}.md",
        "derivation": {"workflow": "workflow:meta", "workflow_run": "workflow-run:wf-r1"},
        "datapackage": f"results/meta/r1/{slug}/datapackage.yaml",
    }
    base.update(kw)
    return base


def _output(slug: str = "combined", **support_kw) -> dict:
    out = {"slug": slug, "title": "Combined", "resource_names": ["gene"]}
    if support_kw:
        out["support"] = support_kw
    return out


def _evaluate(entities: list[dict], packages: dict[str, dict | None]):
    from science_tool.validate.checks.aggregation_support import evaluate_aggregation_support

    return list(evaluate_aggregation_support(entities, lambda rel: packages.get(rel)))


def _rules(entities, packages):
    return [(r.severity, r.rule) for r in _evaluate(entities, packages)]


DP = "results/meta/r1/combined/datapackage.yaml"


def test_no_support_block_is_not_evaluated() -> None:
    assert _rules([_workflow([_output()]), _dataset()], {DP: {"science": {}}}) == []


def test_observed_at_or_above_expected_is_clean() -> None:
    entities = [_workflow([_output(unit="dataset", min=3, expected=5)]), _dataset()]
    pkgs = {DP: {"science": {"support": {"unit": "dataset", "observed": 5}}}}
    assert _rules(entities, pkgs) == []


def test_below_floor_is_error() -> None:
    entities = [_workflow([_output(unit="dataset", min=3, expected=5)]), _dataset()]
    pkgs = {DP: {"science": {"support": {"unit": "dataset", "observed": 1}}}}
    assert (Severity.ERROR, "aggregation-support.below-floor") in _rules(entities, pkgs)


def test_zero_observed_is_below_floor_error() -> None:
    entities = [_workflow([_output(unit="dataset", min=3)]), _dataset()]
    pkgs = {DP: {"science": {"support": {"unit": "dataset", "observed": 0}}}}
    assert (Severity.ERROR, "aggregation-support.below-floor") in _rules(entities, pkgs)


def test_below_expected_is_warn() -> None:
    entities = [_workflow([_output(unit="dataset", min=3, expected=5)]), _dataset()]
    pkgs = {DP: {"science": {"support": {"unit": "dataset", "observed": 4}}}}
    assert _rules(entities, pkgs) == [(Severity.WARN, "aggregation-support.below-expected")]


def test_stamp_missing_when_observed_null() -> None:
    entities = [_workflow([_output(unit="dataset", min=3)]), _dataset()]
    pkgs = {DP: {"science": {"support": {"unit": "dataset", "observed": None}}}}
    assert (Severity.ERROR, "aggregation-support.stamp-missing") in _rules(entities, pkgs)


def test_stamp_missing_when_no_support_stamp() -> None:
    entities = [_workflow([_output(unit="dataset", min=3)]), _dataset()]
    pkgs = {DP: {"science": {"identity_context": {}}}}
    assert (Severity.ERROR, "aggregation-support.stamp-missing") in _rules(entities, pkgs)


def test_stamp_missing_when_datapackage_absent() -> None:
    entities = [_workflow([_output(unit="dataset", min=3)]), _dataset()]
    assert (Severity.ERROR, "aggregation-support.stamp-missing") in _rules(entities, {DP: None})


def test_malformed_observed_is_error() -> None:
    entities = [_workflow([_output(unit="dataset", min=3)]), _dataset()]
    for bad in ("5", True, -1, 5.0):
        pkgs = {DP: {"science": {"support": {"unit": "dataset", "observed": bad}}}}
        assert (Severity.ERROR, "aggregation-support.malformed-stamp") in _rules(entities, pkgs), bad


def test_unit_mismatch_is_error_and_suppresses_floor() -> None:
    entities = [_workflow([_output(unit="dataset", min=3)]), _dataset()]
    # observed=1 is below the floor, but the unit mismatch must short-circuit the floor check
    pkgs = {DP: {"science": {"support": {"unit": "cohort", "observed": 1}}}}
    rules = _rules(entities, pkgs)
    assert (Severity.ERROR, "aggregation-support.unit-mismatch") in rules
    assert (Severity.ERROR, "aggregation-support.below-floor") not in rules


def test_module_is_registered() -> None:
    import sys

    import science_tool.validate.checks as checks

    checks.clear_checks_for_tests()
    # Python won't re-run the module's @Check decorators unless it is re-imported.
    sys.modules.pop("science_tool.validate.checks.aggregation_support", None)
    checks._load_canonical_checks()
    assert any(entry.fn.__module__.endswith("aggregation_support") for entry in checks.CANONICAL_CHECKS)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run pytest tests/validate/test_checks_aggregation_support.py -q`
Expected: FAIL — `ModuleNotFoundError: science_tool.validate.checks.aggregation_support`.

- [ ] **Step 3: Implement the check module**

Create `science/src/science_tool/validate/checks/aggregation_support.py`:

```python
"""Validate check: aggregating outputs must meet their declared support floor.

Opt-in and fail-closed. An output is gated iff its workflow ``outputs[]`` entry
declares a ``support`` block. The floor lives on the workflow entity; the observed
support is a producer-authored stamp propagated by register-run onto the per-output
datapackage under ``science.support``. This check joins them and never reads parquet.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from pathlib import Path, PurePosixPath
from typing import Any

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate._helpers import entity_frontmatters
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _valid_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _workflow_support_floors(records: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    """workflow id -> {output slug -> declared support floor dict}."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for fm in records:
        if fm.get("kind") != "workflow":
            continue
        wf_id = fm.get("id")
        if not isinstance(wf_id, str) or not wf_id:
            continue
        floors: dict[str, dict[str, Any]] = {}
        for output in fm.get("outputs") or []:
            if not isinstance(output, dict):
                continue
            slug = output.get("slug")
            support = output.get("support")
            if isinstance(slug, str) and isinstance(support, dict):
                floors[slug] = support
        if floors:
            out[wf_id] = floors
    return out


def evaluate_aggregation_support(
    entities: Iterable[dict[str, Any]],
    read_datapackage: Callable[[str], dict[str, Any] | None],
) -> Iterator[Result]:
    records = list(entities)
    floors_by_workflow = _workflow_support_floors(records)

    for fm in records:
        if fm.get("kind") != "dataset":
            continue
        derivation = fm.get("derivation")
        datapackage = fm.get("datapackage")
        if not isinstance(derivation, dict) or not isinstance(datapackage, str):
            continue
        wf_id = derivation.get("workflow")
        if not isinstance(wf_id, str):
            continue
        slug = PurePosixPath(datapackage).parent.name
        floor = floors_by_workflow.get(wf_id, {}).get(slug)
        if floor is None:
            continue  # output declares no floor -> not evaluated

        ident = fm.get("id")
        path = fm.get("_path") if isinstance(fm.get("_path"), str) else None
        prefix = f"{ident}: output {slug!r}"
        declared_unit = floor.get("unit")
        floor_min = floor.get("min")
        floor_expected = floor.get("expected")

        dp = read_datapackage(datapackage)
        stamp = ((dp or {}).get("science") or {}).get("support") if isinstance(dp, dict) else None
        observed = stamp.get("observed") if isinstance(stamp, dict) else None

        if observed is None:
            yield _result(
                Severity.ERROR, path,
                f"{prefix} declares support floor min={floor_min} but no observed support was stamped",
                "aggregation-support.stamp-missing",
            )
            continue

        stamped_unit = stamp.get("unit")
        if stamped_unit != declared_unit:
            yield _result(
                Severity.ERROR, path,
                f"{prefix} stamped unit {stamped_unit!r} != declared unit {declared_unit!r}",
                "aggregation-support.unit-mismatch",
            )
            continue  # a unit mismatch makes the numeric floor comparison meaningless

        if not _valid_count(observed):
            yield _result(
                Severity.ERROR, path,
                f"{prefix} stamped observed={observed!r} is not a non-negative integer",
                "aggregation-support.malformed-stamp",
            )
            continue

        if isinstance(floor_min, int) and observed < floor_min:
            yield _result(
                Severity.ERROR, path,
                f"{prefix} observed support {observed} < declared floor min={floor_min}",
                "aggregation-support.below-floor",
            )
        elif isinstance(floor_expected, int) and observed < floor_expected:
            yield _result(
                Severity.WARN, path,
                f"{prefix} observed support {observed} < expected {floor_expected} (>= floor min={floor_min})",
                "aggregation-support.below-expected",
            )


@Check(section="aggregation support", order=34)
def check_aggregation_support(ctx: ValidateContext) -> Iterator[Result]:
    def _read(rel: str) -> dict[str, Any] | None:
        p = ctx.project_root / rel
        if not p.is_file():
            return None
        data = ctx.read_yaml(p)
        return data if isinstance(data, dict) else None

    yield from evaluate_aggregation_support(entity_frontmatters(ctx), _read)
```

> If `order=34` collides with an existing check, bump to the next free integer — the registry sorts by `order` and adjacency to `dataset_capabilities` (33) is cosmetic, not semantic. Confirm with `grep -rn "order=3" src/science_tool/validate/checks/`.

- [ ] **Step 4: Register the module**

In `science/src/science_tool/validate/checks/__init__.py`, add `"aggregation_support"` to the `CANONICAL_CHECK_MODULES` tuple, next to `"dataset_capabilities"` (line 54). Add the string exactly as the other entries are formatted (bare module name, no path).

- [ ] **Step 5: Run the unit + registration tests to verify they pass**

Run: `cd ~/d/science/science && uv run pytest tests/validate/test_checks_aggregation_support.py -q`
Expected: PASS (all unit tests + `test_module_is_registered`).

- [ ] **Step 6: Write the runner e2e + CLI-exit tests (the MM30-shape fixture)**

Append to `science/tests/validate/test_checks_aggregation_support.py`. Mirror the on-disk e2e style at `tests/validate/test_checks_dataset_capabilities.py:172-209` (writes `science.yaml` + entity `.md` files, then calls `run(...)`). This exercises the real `ctx.read_yaml` join, not the injected fake:

```python
def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_mm30_shape(root: Path, observed) -> None:
    _write(root / "science.yaml", "name: t\nlayout_version: 3\n")
    _write(
        root / "entities/workflows/meta.md",
        "---\n"
        'id: "workflow:meta"\n'
        'kind: "workflow"\n'
        'title: "Meta"\n'
        "outputs:\n"
        "  - slug: combined\n"
        "    title: Combined\n"
        "    resource_names: [gene]\n"
        "    support:\n"
        "      unit: dataset\n"
        "      min: 3\n"
        "      expected: 5\n"
        "---\n",
    )
    _write(
        root / "entities/datasets/wf-r1-combined.md",
        "---\n"
        'id: "dataset:wf-r1-combined"\n'
        'kind: "dataset"\n'
        'title: "Combined"\n'
        'datapackage: "results/meta/r1/combined/datapackage.yaml"\n'
        "derivation:\n"
        '  workflow: "workflow:meta"\n'
        '  workflow_run: "workflow-run:wf-r1"\n'
        "---\n",
    )
    _write(
        root / "results/meta/r1/combined/datapackage.yaml",
        "profiles: [science-pkg-runtime-1.0]\n"
        "name: meta-r1-combined\n"
        "resources: []\n"
        "science:\n"
        "  support:\n"
        "    unit: dataset\n"
        f"    observed: {observed}\n",
    )


def test_e2e_below_floor_reports_error(tmp_path: Path) -> None:
    from science_tool.validate.runner import run

    _seed_mm30_shape(tmp_path, observed=1)
    result = run(tmp_path, strict=False, verbose=False, enable_python_sidecar=False)
    assert any(r.rule == "aggregation-support.below-floor" for r in result.results)
    assert result.errors >= 1


def test_e2e_at_floor_is_warn_not_error(tmp_path: Path) -> None:
    from science_tool.validate.runner import run

    _seed_mm30_shape(tmp_path, observed=4)  # >= min=3, < expected=5
    result = run(tmp_path, strict=False, verbose=False, enable_python_sidecar=False)
    rules = [r.rule for r in result.results]
    assert "aggregation-support.below-expected" in rules
    assert "aggregation-support.below-floor" not in rules


def test_cli_exit_one_on_below_floor(tmp_path: Path) -> None:
    from click.testing import CliRunner
    from science_tool.cli import main

    _seed_mm30_shape(tmp_path, observed=1)
    res = CliRunner().invoke(
        main, ["validate"], env={"SCIENCE_PROJECT_ROOT": str(tmp_path)}, catch_exceptions=False
    )
    assert res.exit_code == 1, res.output
```

> The register-run test file imports the same object as `from science_tool.cli import main as science_cli`; the validate CLI tests import it as `main` and invoke `["validate"]`. Use `main` here.

> Confirm the exact `run(...)` keyword args and the `validate` CLI arg form against `tests/validate/test_checks_dataset_capabilities.py:172-209` and `validate/cli.py:68-106` before running; match them verbatim. If `run` requires a different signature, copy the working call from the capability e2e test.

- [ ] **Step 7: Run the full check test file + the broader validate suite**

Run: `cd ~/d/science/science && uv run pytest tests/validate/test_checks_aggregation_support.py -q`
Expected: PASS (unit + registration + e2e + CLI-exit).

Run: `cd ~/d/science/science && uv run pytest tests/validate -q`
Expected: PASS — no other validate check regressed by the new registration.

- [ ] **Step 8: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/validate/checks/aggregation_support.py \
        src/science_tool/validate/checks/__init__.py \
        tests/validate/test_checks_aggregation_support.py
git commit -m "feat(validate): add aggregation-support cardinality gate check"
```

---

### Task 4: Docs & authoring template

**Files:**
- Modify: the workflow authoring template (confirm exact path: `ls science/templates/ | grep -i workflow` — the design names `templates/workflow.md`).
- Modify: the workflow-outputs authoring section of the user guide (confirm: `grep -rln "outputs:" science/docs/user-guide/ | head`; the identity contract's authoring section is the anchor to add beside).
- Create: only if no existing section fits — a short `science/docs/...` note; otherwise extend in place.

**Interfaces:**
- Consumes: the finished contract (Task 1), stamp handoff (Task 2), and check semantics (Task 3). Docs only — no code.

- [ ] **Step 1: Locate the anchors**

Run:
```bash
cd ~/d/science/science
ls templates/ | grep -i workflow
grep -rln "identity:" docs/ | grep -i -E "user-guide|workflow" | head
```
Expected: prints the workflow template path and the doc file(s) where `outputs[].identity` is already documented. Add the `support` docs directly beside the existing `identity` docs so the two contract fields are taught together.

- [ ] **Step 2: Add the `support:` example to the workflow template**

In the workflow template's `outputs[]` example, under an aggregating output, add (matching the file's existing comment style):

```yaml
outputs:
  - slug: survival-os-combined
    title: Survival OS combined meta-analysis scores
    resource_names: [survival_os_combined_gene, survival_os_combined_gene_set]
    # Support floor for an AGGREGATING output. Opt-in: omit for non-aggregating outputs.
    # The producing run must stamp science.support.observed on each run-aggregate
    # resource; register-run reduces to the min and validate blocks below-floor.
    support:
      unit: dataset          # dataset | cohort | sample | source
      min: 3                 # hard floor (>= 1); observed < min -> ERROR at validate time
      expected: 5            # optional soft target (>= min); min <= observed < expected -> WARN
```

- [ ] **Step 3: Add the authoring section to the user guide**

Beside the existing `outputs[].identity` documentation, add a "Support-cardinality floor" subsection covering, in prose:
- **What it is:** the declared minimum number of distinct contributing units an aggregating output must rest on; opt-in per output.
- **The two-hop stamp:** the producing pipeline writes `science.support: {unit, observed}` on each run-aggregate resource (`observed` = the count of contributing units wired into the aggregation, **not** `max(num_present)`); `register-run` reduces to the min across the output's resources and writes it onto the per-output datapackage under `science.support`.
- **Multi-resource rule:** every resource in an opted-in output must stamp support; any unstamped resource → `observed: null` → `stamp-missing` ERROR. Keep ancillary non-aggregating resources in a separate, non-opted-in output.
- **The gate:** the table of codes — `below-floor`/`stamp-missing`/`malformed-stamp`/`unit-mismatch` (ERROR, exit 1), `below-expected` (WARN) — and that blocking is driven purely by declaring a `support` block, not by `--strict`.
- One worked example: OS `min: 3, expected: 5` with a run that stamps `observed: 1` → `aggregation-support.below-floor` ERROR (the MM30 k=1 collapse, caught by construction).

- [ ] **Step 4: Verify docs build/lint (if the repo lints docs)**

Run: `cd ~/d/science/science && uv run pytest -q -k "doc or template" 2>/dev/null || echo "no doc tests; visual review only"`
Expected: PASS or the "no doc tests" line. Then re-read the edited files to confirm the `~/d/...` path convention and that `support` is taught beside `identity`.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add templates/ docs/
git commit -m "docs(workflow): document support-cardinality floor and gate"
```

---

## Self-Review

**1. Spec coverage** (design → task):
- Declared floor `WorkflowOutputSupport` + `support` field (design §1) → **Task 1**. ✅
- Produced stamp two-hop, min-reduce, null-on-any-missing, nested `science.support` (design §2) → **Task 2** (register-run hop; the producer→run-aggregate hop is pipeline-side, exercised as a fixture in Tasks 2/3). ✅
- Check + join path + code table + opt-in strictness + zero-is-first-class (design §3, "Strictness = opt-in", "Zero is first-class") → **Task 3**. ✅
- `observed` = contributing-unit count, not `max(num_present)` (design "What observed counts") → enforced as **Global Constraint** + documented in **Task 4**; the framework can't verify it (producer-authored), so it lives in docs + the stamp contract, correctly. ✅
- Testing surfaces (contract parsing / register-run propagation / join path / check logic / CLI exit / e2e MM30 fixture) → Tasks 1, 2, 3 (Steps 1 & 6). ✅
- Docs & template (design's only surfacing) → **Task 4**. ✅
- Non-goals (undeclared nudge, row-level completeness, scoped resource list, backfill, staleness) → **out of scope**, matched by the Global Constraints and the "no backfill/no CLI surfacing" scope line. ✅

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N". The three doc-path lookups in Task 4 are genuine repo-structure confirmations (the design itself left the exact user-guide path open), each with the exact `grep`/`ls` to resolve them and the anchor rule ("beside `identity`"), not deferred work. The two "confirm the signature verbatim" notes (Task 3 Step 6 `run(...)` args; order collision) point at a named source file+line to copy from — belt-and-suspenders against a stale signature, not a gap.

**3. Type consistency:** `WorkflowOutputSupport` fields (`unit`/`min`/`expected`) identical across Tasks 1, 2, 3 and docs. Stamp shape `{"unit": ..., "observed": ...}` identical in Task 2 (writer) and Task 3 (reader). Codes `aggregation-support.{below-floor,stamp-missing,malformed-stamp,unit-mismatch,below-expected}` identical in the design table, the Task 3 implementation, and the Task 3 tests. `Result(severity, path, line, message, rule, task)` positional order matches `validate/result.py:23-40`. `evaluate_aggregation_support(entities, read_datapackage)` signature identical in the wrapper, the pure core, and the test's `_evaluate` fake. CLI object is `main` (register-run test aliases it as `science_cli`; the new validate CLI test imports `main` directly).

**4. Robustness carve-outs (from plan review):**
- *Multi-resource unit divergence:* register-run raises on resources that disagree on `unit` (Task 2), so the reduced per-output `unit` is always faithful and Task 3's single top-level `unit` comparison cannot silently miss a diverging resource. Fail-early over a masked stamp.
- *`support` with empty `resource_names`:* rejected at parse time by the Task 1 `WorkflowOutput` validator, so `_reduce_output_support` never reduces over an empty list.
- *Unit-mismatch short-circuits the numeric floor* (Task 3 `continue`): a mismatched unit makes `observed < min` meaningless, so only `unit-mismatch` is reported, not a confusing paired `below-floor`.

## Notes for the executor

- **Task order is a hard dependency chain:** 1 → 2 → 3. Task 2's tests need Task 1's schema (a `support` block must survive `WorkflowOutput.model_validate` in `_read_workflow_outputs`); Task 3's e2e reads what Task 2 writes. Task 4 (docs) can land any time after 3.
- **Worktree/uv caveat:** run `uv run pytest` from **inside the science package** (`~/d/science/science` for the tool, `~/d/science/science/model` for the model) — that is each package's own uv project, so the editable-source path issue that bites MM30 worktrees does not apply here.
- **Commit hygiene:** no AI-attribution trailer/footer. If science has a commitlint hook, the `feat(...)`/`docs(...)` subjects above are already conventional-commit-conformant.
- **This plan is `science`-only.** MM30 adoption (declaring OS `min:3, expected:5` / PFS `min:3, expected:4` floors on the survival meta workflow outputs and stamping `observed` on the run-aggregate resources) is a separate follow-up in the MM30 repo, not part of this plan.
