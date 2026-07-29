# Mixed-case Rule-kind Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `science health` build valid finding rules when an active ontology contains mixed-case kind names such as `pH`.

**Architecture:** Keep the lowercase dotted kebab-case `FindingRule.id` contract unchanged. Correct the single shared `rule_kind_segment(kind: str) -> str` projection so both dynamic validation families receive lowercase kebab-case segments, while their existing pre-registry collision checks remain authoritative.

**Tech Stack:** Python 3.12, Pydantic 2, pytest, Ruff, Pyright, uv.

## Global Constraints

- Normalize only the rule-ID segment; preserve the original kind for registry lookup, titles, vocabulary lookup, and severity policy.
- Map mixed case to lowercase and underscores to hyphens.
- Preserve fail-fast collision detection after normalization.
- Do not allow uppercase `FindingRule.id` values.
- Do not exclude ontology entity types from dynamic rule families.
- Do not add a legacy or compatibility layer.

---

### Task 1: Normalize mixed-case dynamic rule IDs

**Files:**
- Modify: `science/tests/validate/test_finding_primitives.py`
- Modify: `science/tests/validate/test_finding_families.py`
- Modify: `science/src/science_tool/validate/findings.py:141-142`

**Interfaces:**
- Consumes: active kind names from `known_kinds(...)`, including ontology names such as `pH`.
- Produces: `rule_kind_segment(kind: str) -> str`, the canonical lowercase kebab-case rule-ID segment used by `status_vocabulary_rules(...)` and `supersession_rules(...)`.

- [ ] **Step 1: Add the primitive mixed-case regression assertion**

Extend `test_prose_advisory_count_is_not_an_identity_field` in
`science/tests/validate/test_finding_primitives.py`:

```python
assert rule_kind_segment("canonical_parameter") == "canonical-parameter"
assert rule_kind_segment("paper") == "paper"
assert rule_kind_segment("pH") == "ph"
```

- [ ] **Step 2: Add family-level mixed-case and collision coverage**

Extend `test_declared_status_and_inverse_ids_equal_active_kind_expansion` in
`science/tests/validate/test_finding_families.py` so `active` contains `pH` and
both expected sets contain the corresponding lowercase IDs:

```python
active = frozenset({"hypothesis", "workflow_run", "pre-registration", "pH"})

assert {rule.id for rule in status_vocabulary_rules(active)} == {
    "hypothesis.status-vocabulary",
    "workflow-run.status-vocabulary",
    "pre-registration.status-vocabulary",
    "ph.status-vocabulary",
}
assert {rule.id for rule in supersession_rules(active)} == {
    "hypothesis.unbacked-inverse",
    "workflow-run.unbacked-inverse",
    "pre-registration.unbacked-inverse",
    "ph.unbacked-inverse",
}
```

Parameterize the collision test over both underscore/kebab and mixed/lowercase
collisions:

```python
@pytest.mark.parametrize(
    "active",
    [
        frozenset({"workflow_run", "workflow-run"}),
        frozenset({"pH", "ph"}),
    ],
)
@pytest.mark.parametrize("factory", [status_vocabulary_rules, supersession_rules])
def test_kind_family_collision_fails_before_registry_construction(factory, active) -> None:
    with pytest.raises(ValueError, match="collide"):
        factory(active)
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```bash
cd science
uv run --frozen pytest \
  tests/validate/test_finding_primitives.py::test_prose_advisory_count_is_not_an_identity_field \
  tests/validate/test_finding_families.py::test_declared_status_and_inverse_ids_equal_active_kind_expansion \
  tests/validate/test_finding_families.py::test_kind_family_collision_fails_before_registry_construction \
  -q
```

Expected: failures caused by `rule_kind_segment("pH")` returning `"pH"` and
`FindingRule` rejecting `pH.status-vocabulary`; the `{"pH", "ph"}` case must not
yet satisfy the explicit collision assertion.

- [ ] **Step 4: Implement the canonical mapping**

Change `science/src/science_tool/validate/findings.py`:

```python
def rule_kind_segment(kind: str) -> str:
    return kind.lower().replace("_", "-")
```

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```bash
cd science
uv run --frozen pytest \
  tests/validate/test_finding_primitives.py \
  tests/validate/test_finding_families.py \
  -q
```

Expected: PASS.

- [ ] **Step 6: Run package verification**

Run from `science/`:

```bash
uv run --frozen pytest
uv run ruff check
uv run pyright
```

Expected: all checks pass.

- [ ] **Step 7: Verify the original consumer command against the local toolkit**

Run from `~/d/cancer/cancer-types/multiple-myeloma`:

```bash
uv run --project ~/d/science/science --frozen science health
```

Expected: registry construction succeeds and the command produces a health
report rather than a `FindingRule` validation error for
`pH.status-vocabulary`.

- [ ] **Step 8: Commit the implementation**

```bash
git add \
  science/src/science_tool/validate/findings.py \
  science/tests/validate/test_finding_primitives.py \
  science/tests/validate/test_finding_families.py
git commit -m "fix(findings): normalize mixed-case kind rule ids"
```
