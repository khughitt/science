# Spec 2 — Runs Observe Seeds (`task:t088`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `seed_policy` stops being an assertion the author writes and becomes a
fact `register-run` derives from a workflow's steps, their `seed_bindings`, and
the realized values — refusing to invent one when it cannot.

**Architecture:** A pure derivation function (`seed_policy_derivation.py`) maps
(workflow, its steps, their methods, the run's config snapshot) to a
`(SeedPolicy, step_seeds)` pair or raises. `persist_run_fingerprint` gathers
those inputs from `load_project_sources` and the run's `config_snapshot`, then
hands them to `capture_fingerprint`, which no longer reads an authored
`seed_policy`. `RunFingerprint` grows `step_seeds` and loses `SeedPolicy.seeds`.

**Tech Stack:** Python 3.12+, pydantic v2, click, pytest. Packages: `science`
(`science/`) and `science-model` (`science/model/`).

## Global Constraints

- **No root `pyproject.toml`.** `cd science/` for CLI/toolkit work; `cd
  science/model/` for model work. `uv run` from the repo root does not resolve.
- **Do not modify `science/src/science_tool/graph/belief.py`.** Umbrella-wide non-goal.
- **No "legacy" / "compatibility" layer.** `SeedPolicy.seeds` is deleted, not
  deprecated. `extra="forbid"` means an authored `seeds:` raises. Zero
  fingerprints exist in any project, so nothing migrates.
- **Fail early; no silent fallbacks.** Every derivation failure raises and the
  message names *the fix*, not the invariant.
- **No `Unified` prefix** on component names. Composition over inheritance.
- **No AI-attribution trailer or footer** on any commit message. No
  `Co-Authored-By:`, no "Generated with Claude Code".
- **Docs and code use `~/d/`**, never `/home/keith/d/` or `/mnt/ssd/Dropbox/`.
- **`pytest` in this environment never prints its final `N passed` line.** Run
  with `--junitxml=<scratch>/out.xml` and read the `<testsuite errors= failures=
  tests=>` attributes plus the shell exit code. Do not chase the missing line.
- **Verify `git branch --show-current` before every commit** (this repo is
  Dropbox-synced; a concurrent session has committed to a feature branch
  mid-task before). Never `git add -A`; stage named paths.
- Branch: `method-stochasticity-spec2`.

## The derivation contract (binding — every task depends on it)

Let `W` be the workflow named by the run, and `S` the steps whose `workflow:`
ref resolves to `W`. For each step `s` with method entity `M`:

| condition | result |
|---|---|
| `S` is empty | **raise** |
| `s.method` is `""` | **raise** |
| `s.method` does not resolve, or resolves to a non-`method` kind | **raise** |
| `M.stochasticity is None` | **raise** |

Realized seeds, per step:

```
seeds_for(s) = {}                                    if M.stochasticity is DETERMINISTIC
             = {p: realize(src)                       otherwise
                for p, src in s.seed_bindings.items()
                if p in M.seed_params}
step_seeds   = {s.id: seeds_for(s) for s in S if seeds_for(s)}
```

A `deterministic` method contributes no seeds even if its step carries bindings.
Spec 1 already warns on that state (`workflow-step.seed-binding-on-deterministic-method`);
`register-run` observes rather than re-litigates a warning, and a seed that
controls nothing is not a seed. This is what keeps `deterministic ⇒ step_seeds == {}`
true, which `RunFingerprint` enforces.

`realize(src)`:
- `literal:<int>` → that `int`.
- `config.<dotted.key>` → the value at `<dotted.key>` in the run's config
  snapshot. Missing key → **raise**. Non-`int` value → **raise**. (`bool` is a
  Python `int` subclass and must be rejected.)

Classification, from three sets over `S`:

```
nondet    = steps whose M.stochasticity is NONDETERMINISTIC
unbound   = (s, p) for seedable s, for p in M.seed_params, p not in s.seed_bindings
paramless = seedable steps whose M.seed_params is empty
```

| condition (checked in this order) | `seed_policy.kind` |
|---|---|
| `nondet or unbound or paramless` | `stochastic-unseeded` |
| any `seedable` step remains | `seeded` |
| otherwise (every step `deterministic`) | `deterministic` |

`paramless` is load-bearing and easy to miss. Spec 1 made
`method.seed-params-missing` a **warning**, so a `seedable` method with no
`seed_params` is reachable. Without the `paramless` term it would satisfy "every
seedable step bound all its `seed_params`" *vacuously* and derive `seeded` — while
contributing no entry to `step_seeds`, tripping `RunFingerprint`'s
`seeded ⇒ non-empty step_seeds` invariant and crashing. With it, the run derives
`stochastic-unseeded`, which is true.

`rationale` is required for `stochastic-unseeded` and forbidden otherwise. Compose
it deterministically — sort the parts, so the same run yields the same string:

```python
parts = [f"{s.id} applies {m.id}, which is nondeterministic" for s, m in nondet]
parts += [f"{s.id} leaves {m.id} seed_param {p!r} unbound" for s, m, p in unbound]
parts += [f"{s.id} applies seedable {m.id}, which declares no seed_params" for s, m in paramless]
rationale = "; ".join(sorted(parts))
```

---

### Task 1: `RunFingerprint.step_seeds`; delete `SeedPolicy.seeds`

**Files:**
- Modify: `science/model/src/science_model/run_fingerprint.py:72-96` (`SeedPolicy`), `:124-170` (`RunFingerprint`)
- Test: `science/model/tests/test_run_fingerprint.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `SeedPolicy(kind, rationale)`; `RunFingerprint.step_seeds: dict[str, dict[str, int]]`.

Run everything from `science/model/`.

- [ ] **Step 1: Write the failing tests**

Append to `science/model/tests/test_run_fingerprint.py`:

```python
def test_seeds_field_is_gone() -> None:
    assert "seeds" not in SeedPolicy.model_fields
    with pytest.raises(ValidationError):
        SeedPolicy(kind="seeded", seeds={"random_state": 42})  # type: ignore[call-arg]


def test_seeded_requires_non_empty_step_seeds() -> None:
    with pytest.raises(ValidationError, match="step_seeds"):
        _fingerprint(seed_policy=SeedPolicy(kind="seeded"), step_seeds={})


def test_deterministic_requires_empty_step_seeds() -> None:
    with pytest.raises(ValidationError, match="step_seeds"):
        _fingerprint(
            seed_policy=SeedPolicy(kind="deterministic"),
            step_seeds={"workflow-step:cluster": {"random_state": 1}},
        )


def test_stochastic_unseeded_may_carry_step_seeds() -> None:
    # One step seeded, another nondeterministic: the seeds are real and must survive.
    fp = _fingerprint(
        seed_policy=SeedPolicy(kind="stochastic-unseeded", rationale="workflow-step:embed is nondeterministic"),
        step_seeds={"workflow-step:cluster": {"random_state": 1}},
    )
    assert fp.step_seeds["workflow-step:cluster"]["random_state"] == 1


def test_two_steps_seed_the_same_param_with_different_values() -> None:
    # The exact loss `SeedPolicy.seeds: dict[str, int]` could not represent.
    fp = _fingerprint(
        seed_policy=SeedPolicy(kind="seeded"),
        step_seeds={
            "workflow-step:cluster": {"random_state": 1},
            "workflow-step:embed": {"random_state": 2},
        },
    )
    assert fp.step_seeds["workflow-step:cluster"]["random_state"] == 1
    assert fp.step_seeds["workflow-step:embed"]["random_state"] == 2


def test_step_seeds_key_must_be_a_workflow_step_ref() -> None:
    with pytest.raises(ValidationError, match="workflow-step:"):
        _fingerprint(seed_policy=SeedPolicy(kind="seeded"), step_seeds={"cluster": {"s": 1}})


def test_step_seeds_defaults_to_empty() -> None:
    assert _fingerprint(seed_policy=SeedPolicy(kind="deterministic")).step_seeds == {}
```

Add a `_fingerprint(**overrides)` helper to that file if one does not already
exist, building a minimal valid `RunFingerprint` (`executor="local"`, both
localities `"science-managed"`, every `FingerprintComponent` `_captured("x")`,
`code_dirty` value `"false"`) and applying `overrides`. **Read the file first**
— it already constructs fingerprints; reuse its existing helper rather than
adding a second one.

- [ ] **Step 2: Run to verify they fail**

```bash
cd science/model && uv run --frozen pytest tests/test_run_fingerprint.py -x \
  --junitxml=/tmp/claude-1000/-mnt-ssd-Dropbox-science/a4bfdc8e-22fb-4fb1-9122-5af80925422b/scratchpad/t1.xml
```
Expected: failures — `SeedPolicy` still has `seeds`, `RunFingerprint` has no `step_seeds`.

- [ ] **Step 3: Implement**

Replace `SeedPolicy` (lines 72-96):

```python
class SeedPolicy(BaseModel):
    """How thoroughly this run's randomness was seed-controlled.

    Derived by `register-run` from the workflow's steps, never authored. The
    realized seed values live in `RunFingerprint.step_seeds`, not here: a
    `dict[str, int]` keyed by parameter name cannot represent two steps that
    both seed `random_state` with different values.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["seeded", "deterministic", "stochastic-unseeded"]
    rationale: str | None = None

    @model_validator(mode="after")
    def _validate_kind(self) -> "SeedPolicy":
        if self.kind == "stochastic-unseeded":
            if not self.rationale:
                raise ValueError("seed_policy kind='stochastic-unseeded' requires a rationale")
        elif self.rationale is not None:
            raise ValueError(f"seed_policy kind={self.kind!r} must not carry a rationale")
        return self
```

On `RunFingerprint`, add beside `seed_policy`:

```python
    seed_policy: SeedPolicy
    step_seeds: dict[str, dict[str, int]] = Field(default_factory=dict)

    @field_validator("step_seeds")
    @classmethod
    def _step_refs(cls, v: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
        for ref in v:
            if not ref.startswith("workflow-step:"):
                raise ValueError(f"step_seeds key must be a workflow-step: reference, got {ref!r}")
        return v

    @model_validator(mode="after")
    def _seed_policy_matches_step_seeds(self) -> "RunFingerprint":
        kind = self.seed_policy.kind
        if kind == "seeded" and not self.step_seeds:
            raise ValueError("seed_policy kind='seeded' requires non-empty step_seeds")
        if kind == "deterministic" and self.step_seeds:
            raise ValueError("seed_policy kind='deterministic' requires empty step_seeds")
        return self
```

Import `Field` from pydantic (the module does not import it today).

- [ ] **Step 4: Run to verify they pass**

Same command as Step 2, then the whole model suite:
```bash
cd science/model && uv run --frozen pytest --junitxml=<scratch>/t1-all.xml; echo "exit=$?"
```
Expected: `failures="0" errors="0"`. Other suites reference `SeedPolicy(seeds=...)` —
**do not fix them here**; they belong to Task 4's package. If the *model* suite
has such a reference, fix it now.

- [ ] **Step 5: Lint, type-check, commit**

```bash
cd science/model && uv run ruff check
cd /mnt/ssd/Dropbox/science/science && uv run pyright
cd /mnt/ssd/Dropbox/science && git branch --show-current   # must print method-stochasticity-spec2
git add science/model/src/science_model/run_fingerprint.py science/model/tests/test_run_fingerprint.py
git commit -m "Add RunFingerprint.step_seeds and delete SeedPolicy.seeds (t088)"
```

---

### Task 2: `validate` ERROR — `workflow-step.method-missing`

**Files:**
- Modify: `science/src/science_tool/validate/checks/workflow_steps.py`
- Test: `science/tests/validate/test_checks_workflow_steps.py`

**Interfaces:**
- Consumes: `ValidateContext`, `Severity` (already imported by that module).
- Produces: rule id `workflow-step.method-missing`, `Severity.ERROR`.

This adds a **rule** to the existing `check_workflow_step_seed_bindings` check
function, not a new `@Check`. The check count in
`science/tests/validate/snapshots/text_default.txt` must therefore stay at `58`.
If that snapshot changes, you registered a new check by mistake.

- [ ] **Step 1: Flip the existing test and add the new one**

In `science/tests/validate/test_checks_workflow_steps.py`, `test_step_without_a_method_is_skipped`
currently asserts `== []`. That assertion encoded the *absence* of this ruling.
Replace it:

```python
def test_step_without_a_method_is_an_error(tmp_path: Path) -> None:
    # Ruled 2026-07-10: a methodless step contributes no stochasticity
    # classification, so `seed_policy` cannot be derived from it. Skipping it in
    # the derivation would let an all-methodless workflow satisfy "every step is
    # deterministic" vacuously.
    root = _project(tmp_path, method_frontmatter="", step_frontmatter="")
    results = list(check_workflow_step_seed_bindings(_ctx(root)))
    assert _rules(results) == [("workflow-step.method-missing", Severity.ERROR)]
    assert "workflow-step:cluster" in results[0].message


def test_step_with_a_method_does_not_report_method_missing(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: deterministic\n",
        step_frontmatter="method: method:leiden\n",
    )
    assert list(check_workflow_step_seed_bindings(_ctx(root))) == []
```

`test_unresolvable_method_ref_is_skipped` keeps its `== []` assertion: an
unresolvable ref is a *present* `method:`, owned by `graph audit`.

- [ ] **Step 2: Run to verify it fails**

```bash
cd science && uv run --frozen pytest tests/validate/test_checks_workflow_steps.py -x --junitxml=<scratch>/t2.xml
```
Expected: `test_step_without_a_method_is_an_error` fails — the check returns `[]`.

- [ ] **Step 3: Implement**

In `check_workflow_step_seed_bindings`, the loop currently begins by skipping a
step whose `method` is empty. Replace that skip with a yielded ERROR, then
`continue`:

```python
        if not step.method:
            yield Result(
                rule="workflow-step.method-missing",
                severity=Severity.ERROR,
                message=(
                    f"{step.id} declares no method; seed_policy cannot be derived from it. "
                    f"Add `method: method:<slug>` to {step.file_path}."
                ),
            )
            continue
```

Match the module's existing `Result(...)` construction exactly — read a
neighbouring `yield` and copy its keyword shape (it may pass `entity_id` or
`file_path`; this snippet shows only the fields every rule uses).

- [ ] **Step 4: Run to verify it passes**

```bash
cd science && uv run --frozen pytest tests/validate/ --junitxml=<scratch>/t2-all.xml; echo "exit=$?"
```
Expected: `failures="0" errors="0"`, and `snapshots/text_default.txt` unchanged.

- [ ] **Step 5: Commit**

```bash
cd /mnt/ssd/Dropbox/science && git branch --show-current
git add science/src/science_tool/validate/checks/workflow_steps.py science/tests/validate/test_checks_workflow_steps.py
git commit -m "Report a methodless workflow-step as an error (t088)"
```

---

### Task 3: The pure derivation function

**Files:**
- Create: `science/src/science_tool/seed_policy_derivation.py`
- Test: `science/tests/test_seed_policy_derivation.py`

**Interfaces:**
- Consumes: `SeedPolicy` and `Stochasticity` (Task 1 / Spec 1);
  `MethodEntity`, `WorkflowStepEntity` from `science_model.entities`.
- Produces:

```python
class SeedPolicyDerivationError(Exception): ...

def derive_seed_policy(
    *,
    workflow_id: str,
    steps: list[WorkflowStepEntity],
    method_for_step: dict[str, MethodEntity],   # step.id -> its resolved method
    config: dict[str, Any],                     # the parsed config snapshot
    config_path: str,                           # for error messages only
) -> tuple[SeedPolicy, dict[str, dict[str, int]]]: ...
```

Task 4 resolves refs and builds `method_for_step`; **this function does no
resolution and touches no filesystem.** A step absent from `method_for_step`
means "unresolved or wrong kind" and raises. Order `steps` by `id` before
iterating so `rationale` and `step_seeds` are deterministic.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_seed_policy_derivation.py`. Build entities with a
helper that supplies the six required base-`Entity` fields (`project`,
`ontology_terms`, `related`, `source_refs`, `content_preview`, `file_path`) —
direct constructor calls fail without them.

```python
def _method(slug, stochasticity, seed_params=()):
    return MethodEntity(
        id=f"method:{slug}", kind="method", title=slug,
        stochasticity=stochasticity, seed_params=list(seed_params),
        project="demo", ontology_terms=[], related=[], source_refs=[],
        content_preview="", file_path=f"entities/methods/{slug}.md",
    )


def _step(slug, method="", seed_bindings=None):
    return WorkflowStepEntity(
        id=f"workflow-step:{slug}", kind="workflow-step", title=slug,
        workflow="workflow:w", method=method, seed_bindings=seed_bindings or {},
        project="demo", ontology_terms=[], related=[], source_refs=[],
        content_preview="", file_path=f"entities/workflow-steps/{slug}.md",
    )


def _derive(steps, methods, config=None):
    return derive_seed_policy(
        workflow_id="workflow:w", steps=steps, method_for_step=methods,
        config=config or {}, config_path="results/w/r/config.yaml",
    )
```

Tests (each asserts on the message, not only the exception type):

```python
def test_zero_steps_fails_closed():
    with pytest.raises(SeedPolicyDerivationError, match="Declare at least one step"):
        _derive([], {})


def test_methodless_step_fails_closed():
    s = _step("a")
    with pytest.raises(SeedPolicyDerivationError, match="declares no method"):
        _derive([s], {})


def test_unresolved_method_fails_closed():
    s = _step("a", method="method:nope")
    with pytest.raises(SeedPolicyDerivationError, match="does not resolve"):
        _derive([s], {})          # absent from method_for_step


def test_unclassified_method_fails_closed():
    s = _step("a", method="method:m")
    with pytest.raises(SeedPolicyDerivationError, match="has no stochasticity"):
        _derive([s], {s.id: _method("m", None)})


def test_all_deterministic_derives_deterministic_with_no_seeds():
    s = _step("a", method="method:m")
    policy, seeds = _derive([s], {s.id: _method("m", Stochasticity.DETERMINISTIC)})
    assert (policy.kind, policy.rationale, seeds) == ("deterministic", None, {})


def test_binding_on_a_deterministic_method_contributes_no_seed():
    # validate already WARNs on this; a seed that controls nothing is not a seed,
    # and recording it would break `deterministic => empty step_seeds`.
    s = _step("a", method="method:m", seed_bindings={"random_state": "literal:1"})
    policy, seeds = _derive([s], {s.id: _method("m", Stochasticity.DETERMINISTIC)})
    assert (policy.kind, seeds) == ("deterministic", {})


def test_seedable_fully_bound_derives_seeded():
    s = _step("a", method="method:m", seed_bindings={"random_state": "literal:42"})
    policy, seeds = _derive([s], {s.id: _method("m", Stochasticity.SEEDABLE, ["random_state"])})
    assert policy.kind == "seeded" and policy.rationale is None
    assert seeds == {"workflow-step:a": {"random_state": 42}}


def test_seedable_unbound_param_derives_stochastic_unseeded():
    s = _step("a", method="method:m")
    policy, _ = _derive([s], {s.id: _method("m", Stochasticity.SEEDABLE, ["random_state"])})
    assert policy.kind == "stochastic-unseeded"
    assert "'random_state' unbound" in policy.rationale


def test_seedable_with_no_seed_params_derives_stochastic_unseeded():
    # `method.seed-params-missing` is warn-only, so this state is reachable. Without
    # the `paramless` term it would derive `seeded` vacuously with empty step_seeds
    # and crash RunFingerprint's invariant.
    s = _step("a", method="method:m")
    policy, seeds = _derive([s], {s.id: _method("m", Stochasticity.SEEDABLE)})
    assert policy.kind == "stochastic-unseeded"
    assert "declares no seed_params" in policy.rationale
    assert seeds == {}


def test_nondeterministic_derives_stochastic_unseeded_but_keeps_its_seeds():
    # A nondeterministic method MAY declare and bind seed_params (Spec 1 corollary):
    # `nondeterministic` means "not fully seed-controlled", not "cannot be seeded".
    s = _step("a", method="method:m", seed_bindings={"random_state": "literal:7"})
    policy, seeds = _derive([s], {s.id: _method("m", Stochasticity.NONDETERMINISTIC, ["random_state"])})
    assert policy.kind == "stochastic-unseeded"
    assert "which is nondeterministic" in policy.rationale
    assert seeds == {"workflow-step:a": {"random_state": 7}}


def test_two_steps_seed_the_same_param_differently():
    a = _step("a", method="method:m", seed_bindings={"random_state": "literal:1"})
    b = _step("b", method="method:m", seed_bindings={"random_state": "literal:2"})
    m = _method("m", Stochasticity.SEEDABLE, ["random_state"])
    policy, seeds = _derive([a, b], {a.id: m, b.id: m})
    assert policy.kind == "seeded"
    assert seeds == {"workflow-step:a": {"random_state": 1}, "workflow-step:b": {"random_state": 2}}


def test_config_binding_is_realized_from_the_snapshot():
    s = _step("a", method="method:m", seed_bindings={"random_state": "config.cluster.seed"})
    m = _method("m", Stochasticity.SEEDABLE, ["random_state"])
    policy, seeds = _derive([s], {s.id: m}, config={"cluster": {"seed": 99}})
    assert seeds == {"workflow-step:a": {"random_state": 99}}


def test_missing_config_key_fails_closed():
    s = _step("a", method="method:m", seed_bindings={"random_state": "config.absent"})
    m = _method("m", Stochasticity.SEEDABLE, ["random_state"])
    with pytest.raises(SeedPolicyDerivationError, match="has no key 'absent'"):
        _derive([s], {s.id: m}, config={})


def test_non_int_config_value_fails_closed():
    s = _step("a", method="method:m", seed_bindings={"random_state": "config.seed"})
    m = _method("m", Stochasticity.SEEDABLE, ["random_state"])
    with pytest.raises(SeedPolicyDerivationError, match="is not an integer"):
        _derive([s], {s.id: m}, config={"seed": "42"})


def test_bool_config_value_is_not_an_integer():
    # `bool` is an `int` subclass in Python; `isinstance(True, int)` is True.
    s = _step("a", method="method:m", seed_bindings={"random_state": "config.seed"})
    m = _method("m", Stochasticity.SEEDABLE, ["random_state"])
    with pytest.raises(SeedPolicyDerivationError, match="is not an integer"):
        _derive([s], {s.id: m}, config={"seed": True})


def test_binding_to_a_param_the_method_does_not_declare_is_ignored():
    # Spec 1's `seed-binding-unknown-param` WARNs on this; step_seeds records only
    # parameters the method actually declares.
    s = _step("a", method="method:m", seed_bindings={"random_state": "literal:1", "typo": "literal:2"})
    m = _method("m", Stochasticity.SEEDABLE, ["random_state"])
    _, seeds = _derive([s], {s.id: m})
    assert seeds == {"workflow-step:a": {"random_state": 1}}


def test_rationale_is_stable_across_step_order():
    a = _step("a", method="method:ma")
    b = _step("b", method="method:mb")
    ma, mb = _method("ma", Stochasticity.NONDETERMINISTIC), _method("mb", Stochasticity.NONDETERMINISTIC)
    p1, _ = _derive([a, b], {a.id: ma, b.id: mb})
    p2, _ = _derive([b, a], {a.id: ma, b.id: mb})
    assert p1.rationale == p2.rationale


def test_mixed_workflow_derives_stochastic_unseeded_and_records_the_seeded_step():
    a = _step("a", method="method:seedable", seed_bindings={"random_state": "literal:1"})
    b = _step("b", method="method:nondet")
    policy, seeds = _derive(
        [a, b],
        {a.id: _method("seedable", Stochasticity.SEEDABLE, ["random_state"]),
         b.id: _method("nondet", Stochasticity.NONDETERMINISTIC)},
    )
    assert policy.kind == "stochastic-unseeded"
    assert seeds == {"workflow-step:a": {"random_state": 1}}
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_seed_policy_derivation.py --junitxml=<scratch>/t3.xml
```
Expected: collection error — module does not exist.

- [ ] **Step 3: Implement `science/src/science_tool/seed_policy_derivation.py`**

Write it to satisfy the contract table at the top of this plan. Required shape:

```python
"""Derive `seed_policy` from a workflow's steps (umbrella Spec 2, task:t088).

Pure: no filesystem, no reference resolution, no graph. The caller
(`persist_run_fingerprint`) resolves each step's `method:` ref and passes the
resolved entities in. A step missing from `method_for_step` is an unresolved or
wrong-kind reference, and raises.
"""
```

Rules, in order, all raising `SeedPolicyDerivationError` whose message **names
the fix**:

1. `if not steps:` →
   `f"register-run cannot derive seed_policy: {workflow_id} has no workflow-step. "
    f"Declare at least one step (with `workflow: {workflow_id}`) before registering a run."`
2. `if not step.method:` →
   `f"... {step.id} declares no method. Add `method: method:<slug>` to {step.file_path}."`
3. `if step.id not in method_for_step:` →
   `f"... {step.id} references {step.method!r}, which does not resolve to a method entity."`
4. `if method.stochasticity is None:` →
   `f"... {method.id} has no stochasticity. Add `stochasticity: deterministic|seedable|nondeterministic` to {method.file_path}."`

`_realize(source, config, config_path, step, param)`:
- `literal:` prefix → `int(source.removeprefix("literal:"))`. The model already
  validated the grammar (`^literal:-?\d+\Z`), so this cannot raise `ValueError`.
- `config.` prefix → walk the dotted key. Missing → `f"... the config snapshot
  {config_path} has no key {key!r}"`. Then
  `if isinstance(value, bool) or not isinstance(value, int):` →
  `f"... {config_path} key {key!r} is {value!r}, which is not an integer"`.
- Neither prefix is unreachable (the model's `seed_bindings` validator rejects
  it). Raise anyway rather than fall through — no silent default.

Then classify per the table and build `SeedPolicy`. Return
`(policy, step_seeds)`.

- [ ] **Step 4: Run to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_seed_policy_derivation.py --junitxml=<scratch>/t3.xml; echo "exit=$?"
```
Expected: `failures="0" errors="0"`, 17 tests.

- [ ] **Step 5: Lint, type-check, commit**

```bash
cd science && uv run ruff check && uv run pyright
cd /mnt/ssd/Dropbox/science && git branch --show-current
git add science/src/science_tool/seed_policy_derivation.py science/tests/test_seed_policy_derivation.py
git commit -m "Derive seed_policy and step_seeds from a workflow's steps (t088)"
```

---

### Task 4: Wire the derivation into `register-run`

**Files:**
- Modify: `science/src/science_tool/datasets_register.py` — `_AUTHORED_FINGERPRINT_FIELDS:922-927`, `capture_fingerprint:934-987`, `persist_run_fingerprint:1083+`
- Modify: `science/tests/test_datasets_register_fingerprint.py` (`git_project:83-106` and every `capture_fingerprint` unit test)
- Modify: `science/tests/conftest.py` — `REGISTER_RUN_FINGERPRINT_FRONTMATTER:163-170`
- Modify: `science/tests/test_dataset_register_run.py:66,1617` and `science/tests/test_workflow_registration_e2e.py:35` (both import that constant)

**Interfaces:**
- Consumes: `derive_seed_policy`, `SeedPolicyDerivationError` (Task 3);
  `RunFingerprint.step_seeds` (Task 1).
- Produces: `capture_fingerprint(..., seed_policy: SeedPolicy, step_seeds: dict[str, dict[str, int]])`
  — `run_fm` is still a parameter (the hand-authored guard still reads it), but
  `seed_policy` is no longer read from it.

`register-run` reads `entities/workflow-runs/<slug>.md` by run id (`_read_run`).
The 37 run entities the datapackage adapter synthesizes are **not** its input.

**Two traps.** `persist_run_fingerprint` now calls `load_project_sources`, which
needs a `science.yaml` — and `git_project` (line 83) creates none. It must gain
one. And the fixtures gain a `workflow-step`, so any test that materializes a
graph from them will now emit a `sci:applies` edge it did not before; if a graph
snapshot fails, that edge is why, and the snapshot is what changes.

- [ ] **Step 1: Write the failing tests**

Rewrite `git_project` (replacing lines 83-106) so the project is loadable and its
one step is seedable and bound:

```python
@pytest.fixture
def git_project(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "uv.lock").write_text("lock", encoding="utf-8")
    (tmp_path / "config.yaml").write_text("alpha: 1\nseed: 42\n", encoding="utf-8")
    (tmp_path / "science.yaml").write_text(
        "name: fingerprint-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    for sub, name, body in [
        ("workflows", "w1", "id: workflow:w1\nkind: workflow\ntitle: W1\n"),
        ("methods", "leiden",
         "id: method:leiden\nkind: method\ntitle: Leiden\n"
         "stochasticity: seedable\nseed_params: [random_state]\n"),
        ("workflow-steps", "cluster",
         "id: workflow-step:cluster\nkind: workflow-step\ntitle: Cluster\n"
         "workflow: workflow:w1\nmethod: method:leiden\n"
         'seed_bindings:\n  random_state: "config.seed"\n'),
        ("workflow-runs", "r1",
         "id: workflow-run:r1\nkind: workflow-run\ntitle: R1\n"
         "workflow: workflow:w1\nconfig_snapshot: config.yaml\n"
         "fingerprint:\n"
         "  executor: local\n"
         "  input_artifact_locality: science-managed\n"
         "  output_artifact_locality: science-managed\n"),
    ]:
        d = tmp_path / "entities" / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.md").write_text(f"---\n{body}---\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=tmp_path, check=True,
    )
    return tmp_path
```

Note the run's frontmatter no longer carries `seed_policy`. Then add:

```python
def test_persisted_fingerprint_carries_derived_policy_and_step_seeds(git_project):
    fp = persist_run_fingerprint(git_project, "workflow-run:r1")
    assert fp.seed_policy.kind == "seeded"
    assert fp.seed_policy.rationale is None
    assert fp.step_seeds == {"workflow-step:cluster": {"random_state": 42}}
    written = parse_frontmatter(git_project / "entities" / "workflow-runs" / "r1.md")[0]
    assert written["fingerprint"]["step_seeds"] == {"workflow-step:cluster": {"random_state": 42}}
    assert "seeds" not in written["fingerprint"]["seed_policy"]


def test_authored_seed_policy_is_rejected(git_project):
    # Spec 2 inverts t077: seed_policy was the ONE authored fingerprint field.
    run = git_project / "entities" / "workflow-runs" / "r1.md"
    run.write_text(
        run.read_text(encoding="utf-8").replace(
            "  output_artifact_locality: science-managed\n",
            "  output_artifact_locality: science-managed\n  seed_policy: {kind: deterministic}\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(FingerprintCaptureError, match="derived by register-run"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_run_without_a_workflow_ref_fails_closed(git_project):
    run = git_project / "entities" / "workflow-runs" / "r1.md"
    run.write_text(run.read_text(encoding="utf-8").replace("workflow: workflow:w1\n", "", 1), encoding="utf-8")
    with pytest.raises(FingerprintCaptureError, match="declares no workflow"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_workflow_with_no_steps_fails_closed(git_project):
    (git_project / "entities" / "workflow-steps" / "cluster.md").unlink()
    with pytest.raises(FingerprintCaptureError, match="Declare at least one step"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_methodless_step_fails_closed(git_project):
    step = git_project / "entities" / "workflow-steps" / "cluster.md"
    step.write_text(step.read_text(encoding="utf-8").replace("method: method:leiden\n", "", 1), encoding="utf-8")
    with pytest.raises(FingerprintCaptureError, match="declares no method"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_unclassified_method_fails_closed(git_project):
    m = git_project / "entities" / "methods" / "leiden.md"
    m.write_text(m.read_text(encoding="utf-8").replace("stochasticity: seedable\n", "", 1), encoding="utf-8")
    with pytest.raises(FingerprintCaptureError, match="has no stochasticity"):
        persist_run_fingerprint(git_project, "workflow-run:r1")
```

Four existing tests in this file assert the *authored* behaviour and are now
about a surface that no longer exists. Replace, do not delete silently — and say
which you replaced, in the report:

| existing test | becomes |
|---|---|
| `test_hand_authored_seed_policy_is_preserved:54` | `test_authored_seed_policy_is_rejected` (above) |
| `test_missing_seed_policy_defaults_to_stochastic_unseeded_is_rejected:60` | delete — nothing authored can be missing |
| `test_invalid_seed_policy_surfaces_as_capture_error:73` | `test_derivation_error_surfaces_as_capture_error` — assert `SeedPolicyDerivationError` is re-raised as `FingerprintCaptureError` |
| `test_capture_marks_every_component_captured:31` and the other direct `capture_fingerprint` unit tests | pass `seed_policy=SeedPolicy(kind="deterministic"), step_seeds={}` as arguments instead of via `run_fm` |

In `science/tests/conftest.py`, drop the `seed_policy` line from
`REGISTER_RUN_FINGERPRINT_FRONTMATTER` (line 169) and update its comment — it no
longer supplies "an authored executor/localities/seed_policy". The two files that
splice it in (`test_dataset_register_run.py:66,1617`,
`test_workflow_registration_e2e.py:35`) build projects whose runs now need a
`workflow:` ref plus a `workflow` / `workflow-step` / `method` trio and a
config key for any binding. Give their steps a `deterministic` method with no
`seed_params` — the least invasive choice, deriving `seed_policy.kind ==
"deterministic"` and `step_seeds == {}`, which is what those tests already
assumed.

- [ ] **Step 2: Run to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_datasets_register_fingerprint.py --junitxml=<scratch>/t4.xml
```

- [ ] **Step 3: Implement**

1. `_AUTHORED_FINGERPRINT_FIELDS` — drop `"seed_policy"`. It now holds only the
   three declarations (`executor`, `input_artifact_locality`,
   `output_artifact_locality`). Update its comment.

2. In `capture_fingerprint`, delete the `raw_seed = authored.get("seed_policy")`
   block and the `SeedPolicy.model_validate` / `ValidationError` handling. Add
   `seed_policy: SeedPolicy` and `step_seeds: dict[str, dict[str, int]]` as
   keyword-only parameters and pass both to `RunFingerprint(...)`. Extend the
   hand-authored guard so authoring `seed_policy` raises:

```python
    forbidden = sorted(set(authored) & (set(COMPONENT_FIELDS) | {"seed_policy", "step_seeds"}))
    if forbidden:
        raise FingerprintCaptureError(
            "these fingerprint components are derived by register-run and must not be "
            f"hand-authored in the workflow-run frontmatter: {', '.join(forbidden)}"
        )
```

   Note `persist_run_fingerprint`'s `authored_only` filter already strips
   anything not in `_AUTHORED_FINGERPRINT_FIELDS`, so this guard protects direct
   callers of `capture_fingerprint`, exactly as its docstring says of the
   existing one. Keep that docstring accurate.

3. In `persist_run_fingerprint`, before calling `capture_fingerprint`:

```python
    workflow_ref = run_fm.get("workflow") or ""
    if not workflow_ref:
        raise FingerprintCaptureError(
            f"{run_path.name}: declares no workflow, so seed_policy cannot be derived. "
            f"Add `workflow: workflow:<slug>`."
        )

    sources = load_project_sources(project_root, strict_core_schema=True)
    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)
    workflow_id = _resolve_or_raise(resolver, workflow_ref, run_path)

    steps = [
        e for e in sources.entities
        if isinstance(e, WorkflowStepEntity)
        and e.workflow
        and resolver.resolve(e.workflow).canonical_id == workflow_id
    ]
    method_for_step = {}
    by_id = {e.id: e for e in sources.entities}
    for step in steps:
        if not step.method:
            continue                      # derive_seed_policy raises with the right message
        resolution = resolver.resolve(step.method)
        target = by_id.get(resolution.canonical_id) if resolution.canonical_id else None
        if isinstance(target, MethodEntity):
            method_for_step[step.id] = target

    config = yaml.safe_load((project_root / config_snapshot).read_text(encoding="utf-8")) or {}
    try:
        seed_policy, step_seeds = derive_seed_policy(
            workflow_id=workflow_id, steps=steps, method_for_step=method_for_step,
            config=config, config_path=config_snapshot,
        )
    except SeedPolicyDerivationError as exc:
        raise FingerprintCaptureError(str(exc)) from exc
```

   Use the same `ReferenceResolver.from_entities(sources.entities,
   manual_aliases=sources.manual_aliases)` call the validate check uses
   (`validate/checks/workflow_steps.py`) — a second resolution strategy would
   disagree with the compiler. Import `load_project_sources` from
   `science_tool.graph.sources` and `ReferenceResolver` from
   `science_tool.graph.reference_resolution`. **Import them inside the function**
   if a module-level import creates a cycle; check before assuming.

4. `payload = fingerprint.model_dump(mode="json", exclude_none=True)` already
   writes `step_seeds`. Confirm the round-trip test in Step 1 passes; if
   `exclude_none` drops an empty `step_seeds`, that is correct (default `{}`).

- [ ] **Step 4: Run the full toolkit suite**

```bash
cd science && uv run --frozen pytest --junitxml=<scratch>/t4-all.xml; echo "exit=$?"
```
Expected: `failures="0" errors="0"`. Baseline on `main` is 7786 tests, 9 skipped;
this branch adds tests and changes no others' outcomes.

- [ ] **Step 5: Lint, type-check, commit**

```bash
cd science && uv run ruff check && uv run pyright
cd /mnt/ssd/Dropbox/science && git branch --show-current
git add science/src/science_tool/datasets_register.py science/tests/test_datasets_register_fingerprint.py \
        science/tests/conftest.py science/tests/test_dataset_register_run.py \
        science/tests/test_workflow_registration_e2e.py
git commit -m "Derive seed_policy at register-run instead of reading it (t088)"
```

---

### Task 5: Template and user-guide truth

**Files:**
- Modify: `templates/workflow-run.md`, `science/model/src/science_model/templates/workflow-run.md`
- Modify: `science/docs/user-guide/` — the page describing run fingerprints (grep for `seed_policy`)
- Test: `science/model/tests/test_templates.py` (run it; do not necessarily edit)

**Interfaces:** none — documentation and template text only.

`templates/workflow-run.md` today declares **no** `fingerprint:` block and no
`config_snapshot:`, yet `persist_run_fingerprint` requires both. That gap is why
zero runs carry a fingerprint. Close it, now that the authored surface is small
enough to be honest about.

- [ ] **Step 1: Check whether the mirror guard covers this kind**

```bash
cd science/model && uv run --frozen python -c "
from science_model.templates import MIGRATED_KINDS
print('workflow-run guarded:', 'workflow-run' in MIGRATED_KINDS)"
```
If `True`, root and packaged copies must stay byte-identical
(`test_root_and_packaged_migrated_templates_match`). If `False`, they are
hand-copied and **unguarded** — change both by hand and diff them yourself.
(`task:t090` tracks that inverted coverage; do not fix it here.)

- [ ] **Step 2: Edit `templates/workflow-run.md`**

After `manifest_path:`, add:

```yaml
config_snapshot: "results/<workflow>/<slug>/config.yaml"  # required: parameters_digest is its sha256
# Declarations, not observations — `science dataset register-run` captures the rest.
fingerprint:
  executor: "local"                        # local | commons | external
  input_artifact_locality: "science-managed"   # science-managed | external
  output_artifact_locality: "science-managed"
# `seed_policy` and `step_seeds` are DERIVED from the workflow's steps at
# register-run and must not be hand-authored. Declaring either is an error.
```

- [ ] **Step 3: Mirror to the packaged copy and verify**

```bash
cp templates/workflow-run.md science/model/src/science_model/templates/workflow-run.md
cd science/model && uv run --frozen pytest tests/test_templates.py --junitxml=<scratch>/t5.xml; echo "exit=$?"
```

- [ ] **Step 4: Update the user guide**

```bash
cd science && grep -rn "seed_policy" docs/
```
Every passage saying `seed_policy` is authored, or documenting
`seed_policy.seeds`, is now false. Rewrite it: `seed_policy` is derived at
`register-run` from the workflow's steps; realized seeds live in
`fingerprint.step_seeds`, keyed by `workflow-step:` ref. Use `~/d/` in any path.

- [ ] **Step 5: Commit**

```bash
cd /mnt/ssd/Dropbox/science && git branch --show-current
git add templates/workflow-run.md science/model/src/science_model/templates/workflow-run.md science/docs
git commit -m "Document seed_policy as derived, not authored (t088)"
```

---

## Done when

- `register-run` derives `seed_policy` and refuses to invent one.
- A zero-step workflow, a methodless step, and an unclassified method each fail
  closed at `register-run` with a message naming the fix.
- A methodless step is a `validate` ERROR.
- Two steps seeding `random_state` with different values round-trip through
  `step_seeds` without collision.
- `SeedPolicy.seeds` is gone; authoring `seed_policy` raises.
- `cd science && uv run --frozen pytest` and `cd science/model && uv run
  --frozen pytest` are green; `ruff check` clean in both; `pyright` reports
  `0 errors`.
- No commit carries an AI-attribution trailer.
