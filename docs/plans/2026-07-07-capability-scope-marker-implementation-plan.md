# capability_scope Marker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a framework-native `capability_scope` marker so entities that are non-molecular by nature stop producing false `dataset-capabilities.*-missing` warnings, without ever gaining molecular coverage credit.

**Architecture:** A small controlled-vocabulary registry module drives three validator behaviors (suppress-on-valid-scope, `scope-unknown` fail-closed, `scope-conflict` mutual-exclusion) and one new coverage state (`out-of-molecular-scope`). The capability-fit matching engine is untouched — a scoped entity keeps empty molecular capabilities, which already fail-close to "not compatible." A final task rolls the marker out across 32 surveyed MM30 entities.

**Tech Stack:** Python ≥3.11, pytest, the `science_tool` package.

## Global Constraints

- Science repo root: `~/d/science`; Python package dir: `~/d/science/science`; work on branch `capability-scope-marker` (already checked out, design committed).
- Run tests from the package dir: `cd ~/d/science/science && uv run --frozen pytest <path> -q`.
- Design of record: `~/d/science/docs/plans/2026-07-07-capability-scope-marker-design.md`. Read it before starting.
- Controlled enum (kebab-case, exactly these 7): `reference-substrate`, `derived-product`, `methodological`, `model-system` (Type II, terminal); `clinical-outcome`, `epidemiological`, `behavioral-instrument` (Type I, transitional).
- New coverage-state string: `out-of-molecular-scope`. New validator rules: `dataset-capabilities.scope-unknown`, `dataset-capabilities.scope-conflict`. **No** `scope-contradicted` lint (retired by the corpus check — see design Resolved decisions).
- **No matching-engine change** (`datasets/capabilities.py` stays as-is).
- Commit messages: conventional-commit type; **no AI-attribution trailer** (no `Co-Authored-By`, no "Generated with" footer).
- MM30 worktree for Task 5: `~/d/cancer/cancer-types/mm30--capability-warnings-cleanup` (consumes this branch via its editable `science` path, so framework changes are live once present in the working tree).

---

### Task 1: capability_scope registry module

**Files:**
- Create: `science/src/science_tool/datasets/capability_scope.py`
- Test: `science/tests/test_capability_scope.py`

**Interfaces:**
- Produces: `VALID_SCOPES: frozenset[str]`, `TYPE_I_SCOPES: frozenset[str]`, `TYPE_II_SCOPES: frozenset[str]`, `CAPABILITY_SCOPE_VALUES: dict[str, str]` (value → one-line definition), and `is_valid_scope(value: object) -> bool`.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_capability_scope.py`:

```python
from __future__ import annotations

from science_tool.datasets.capability_scope import (
    CAPABILITY_SCOPE_VALUES,
    TYPE_I_SCOPES,
    TYPE_II_SCOPES,
    VALID_SCOPES,
    is_valid_scope,
)


def test_valid_scopes_are_the_seven_derived_values() -> None:
    assert VALID_SCOPES == {
        "reference-substrate",
        "derived-product",
        "methodological",
        "model-system",
        "clinical-outcome",
        "epidemiological",
        "behavioral-instrument",
    }


def test_type_partition_is_a_disjoint_cover() -> None:
    assert TYPE_I_SCOPES.isdisjoint(TYPE_II_SCOPES)
    assert TYPE_I_SCOPES | TYPE_II_SCOPES == VALID_SCOPES


def test_every_value_has_a_nonempty_definition() -> None:
    assert set(CAPABILITY_SCOPE_VALUES) == VALID_SCOPES
    assert all(text.strip() for text in CAPABILITY_SCOPE_VALUES.values())


def test_is_valid_scope() -> None:
    assert is_valid_scope("clinical-outcome") is True
    assert is_valid_scope("bogus") is False
    assert is_valid_scope(None) is False
    assert is_valid_scope(7) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_capability_scope.py -q`
Expected: FAIL with `ModuleNotFoundError: science_tool.datasets.capability_scope`.

- [ ] **Step 3: Write the module**

Create `science/src/science_tool/datasets/capability_scope.py`:

```python
"""Controlled vocabulary for the `capability_scope` marker.

An entity carries `capability_scope` to positively declare that it sits OUTSIDE
the molecular assay/modality capability gate: its empty provided/required
capabilities are intentional and complete, not a pending annotation. See
docs/plans/2026-07-07-capability-scope-marker-design.md.

Type II values are terminal ("measures nothing"); Type I values are transitional
("measures something non-molecular") and are the forward pointers to a future
outcome/clinical axis.
"""

from __future__ import annotations

CAPABILITY_SCOPE_VALUES: dict[str, str] = {
    # Type II — terminal not-applicable (no measurement axis at all)
    "reference-substrate": (
        "External curated catalog, annotation track, LD panel, gene-set "
        "collection, or corpus/panel metadata registry; enables analysis, "
        "measures nothing itself."
    ),
    "derived-product": (
        "A project-produced result artifact with no independent measurement "
        "capability (NOT merely anything downstream of assays)."
    ),
    "methodological": (
        "Question answered by an algorithm / statistic / pipeline-design / "
        "census / vocabulary-curation decision over already-derived artifacts; "
        "consumes no assay matrix."
    ),
    "model-system": (
        "In-vivo / functional model or analogy pointer with no catalogued assay."
    ),
    # Type I — transitional (non-molecular measurement; future outcome axis)
    "clinical-outcome": (
        "Clinical labs, survival, treatment response / MRD endpoints, symptom / "
        "QoL, frailty, drug-dosing."
    ),
    "epidemiological": "Population incidence / prevalence / burden / exposure.",
    "behavioral-instrument": (
        "Questionnaire / self-report / neurocognitive-task / wearable / EMA."
    ),
}

TYPE_II_SCOPES: frozenset[str] = frozenset(
    {"reference-substrate", "derived-product", "methodological", "model-system"}
)
TYPE_I_SCOPES: frozenset[str] = frozenset(
    {"clinical-outcome", "epidemiological", "behavioral-instrument"}
)
VALID_SCOPES: frozenset[str] = frozenset(CAPABILITY_SCOPE_VALUES)


def is_valid_scope(value: object) -> bool:
    """True iff `value` is one of the controlled capability_scope strings."""
    return isinstance(value, str) and value in VALID_SCOPES
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_capability_scope.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/datasets/capability_scope.py science/tests/test_capability_scope.py
git commit -m "feat: capability_scope controlled vocabulary registry"
```

---

### Task 2: Validator — suppress on valid scope, scope-unknown, scope-conflict

**Files:**
- Modify: `science/src/science_tool/validate/checks/dataset_capabilities.py`
- Test: `science/tests/validate/test_checks_dataset_capabilities.py`

**Interfaces:**
- Consumes: `VALID_SCOPES` from Task 1.
- Produces: two new rules on `Result.rule`: `dataset-capabilities.scope-unknown`, `dataset-capabilities.scope-conflict`. Suppression of `*-missing` when a valid scope is present. Behavior is exercised through the existing `evaluate_dataset_capabilities(entities)` entry point.

Behavior contract (from design Validator changes 1–3):
- Valid `capability_scope` → suppress the entity's `*-missing` warning.
- `capability_scope` set but not a valid value → `scope-unknown` WARN, and do **not** suppress (fail closed: the normal `*-missing` may also fire).
- Valid `capability_scope` **and** a non-empty (present, i.e. shape issue is not `"missing"`) capability field → `scope-conflict` WARN, and suppress the field's own malformed/missing warning (scope-conflict is the single signal).

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/validate/test_checks_dataset_capabilities.py`:

```python
def test_valid_scope_suppresses_dataset_provided_missing() -> None:
    dataset = _dataset()
    dataset.pop("provided_capabilities")
    dataset["capability_scope"] = "clinical-outcome"

    rules = _rules([dataset, _question()])

    assert (Severity.WARN, "dataset-capabilities.provided-missing") not in rules
    assert rules == []


def test_valid_scope_suppresses_question_required_missing() -> None:
    question = _question(status="active")
    question.pop("required_capabilities")
    question["capability_scope"] = "methodological"

    rules = _rules([_dataset(), question])

    assert (Severity.WARN, "dataset-capabilities.required-missing") not in rules


def test_unknown_scope_warns_and_does_not_suppress() -> None:
    dataset = _dataset()
    dataset.pop("provided_capabilities")
    dataset["capability_scope"] = "not-a-real-scope"

    rules = _rules([dataset, _question()])

    assert (Severity.WARN, "dataset-capabilities.scope-unknown") in rules
    # fail closed: the normal missing warning still fires
    assert (Severity.WARN, "dataset-capabilities.provided-missing") in rules


def test_scope_conflicts_with_non_empty_capabilities() -> None:
    # provided_capabilities is present AND a scope is declared -> conflict
    dataset = _dataset(capability_scope="clinical-outcome")

    rules = _rules([dataset, _question()])

    assert (Severity.WARN, "dataset-capabilities.scope-conflict") in rules


def test_scope_conflict_on_question_required_capabilities() -> None:
    question = _question(capability_scope="methodological")

    rules = _rules([_dataset(), question])

    assert (Severity.WARN, "dataset-capabilities.scope-conflict") in rules
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_dataset_capabilities.py -q`
Expected: the five new tests FAIL (suppression not implemented; `scope-*` rules absent).

- [ ] **Step 3: Add the import**

In `science/src/science_tool/validate/checks/dataset_capabilities.py`, add below the existing `science_tool.validate.*` imports (near line 17):

```python
from science_tool.datasets.capability_scope import VALID_SCOPES
```

- [ ] **Step 4: Add the scope-gate helper**

In the same file, add this helper just above `evaluate_dataset_capabilities` (after the `_is_demand_closed` helper, ~line 62):

```python
def _scope_gate(
    scope: Any,
    ident: str,
    path_value: str | None,
    field_issue: str | None,
    field_name: str,
) -> tuple[bool, list[Result]]:
    """Resolve a `capability_scope` value.

    Returns (suppress_missing, results):
    - no scope declared            -> (False, [])  normal handling proceeds
    - unknown scope value          -> (False, [scope-unknown])  fail closed
    - valid scope, field empty     -> (True, [])   suppress *-missing
    - valid scope, field present   -> (True, [scope-conflict])  mutual exclusion
    """
    if scope is None:
        return False, []
    if not (isinstance(scope, str) and scope in VALID_SCOPES):
        return False, [
            _result(
                path_value,
                f"{ident}: unknown capability_scope {scope!r}; allowed: {sorted(VALID_SCOPES)}",
                "dataset-capabilities.scope-unknown",
            )
        ]
    if field_issue != "missing":
        return True, [
            _result(
                path_value,
                f"{ident}: capability_scope {scope!r} conflicts with non-empty {field_name}",
                "dataset-capabilities.scope-conflict",
            )
        ]
    return True, []
```

- [ ] **Step 5: Rewrite the two branches of `evaluate_dataset_capabilities`**

Replace the body of the `for fm in records:` loop (the current lines 69–113, from `ident = fm.get("id")` through the Q/H block) with:

```python
        ident = fm.get("id")
        if not isinstance(ident, str) or not ident:
            continue
        kind = fm.get("kind")
        path = fm.get("_path")
        path_value = path if isinstance(path, str) else None
        scope = fm.get("capability_scope")

        if kind == "dataset":
            issue = _capability_shape_issue(fm.get(_PROVIDED_FIELD))
            suppress, scope_results = _scope_gate(scope, ident, path_value, issue, _PROVIDED_FIELD)
            yield from scope_results
            if suppress:
                continue
            if issue == "malformed":
                yield _result(
                    path_value,
                    f"{ident}: provided_capabilities must be a non-empty list of non-empty string mappings",
                    "dataset-capabilities.provided-malformed",
                )
            elif issue == "missing":
                targets = dataset_to_targets.get(ident)
                if targets and not all(_is_demand_closed(status_by_id.get(t)) for t in targets):
                    yield _result(
                        path_value,
                        f"{ident}: dataset reaches {sorted(targets)} but declares no provided_capabilities",
                        "dataset-capabilities.provided-missing",
                    )
            continue

        if _is_qh(ident):
            issue = _capability_shape_issue(fm.get(_REQUIRED_FIELD))
            suppress, scope_results = _scope_gate(scope, ident, path_value, issue, _REQUIRED_FIELD)
            yield from scope_results
            if suppress:
                continue
            if issue == "malformed":
                yield _result(
                    path_value,
                    f"{ident}: required_capabilities must be a non-empty list of non-empty string mappings",
                    "dataset-capabilities.required-malformed",
                )
            elif issue == "missing" and target_to_datasets.get(ident) and not _is_demand_closed(fm.get("status")):
                yield _result(
                    path_value,
                    f"{ident}: target reaches {sorted(target_to_datasets[ident])} but declares no required_capabilities",
                    "dataset-capabilities.required-missing",
                )
```

- [ ] **Step 6: Run the full validator test module to verify pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_dataset_capabilities.py -q`
Expected: PASS (all prior tests + the five new ones). The prior suppression/demand-closed tests must still pass unchanged.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/validate/checks/dataset_capabilities.py science/tests/validate/test_checks_dataset_capabilities.py
git commit -m "feat: capability_scope suppression, scope-unknown and scope-conflict checks"
```

---

### Task 3: Coverage state `out-of-molecular-scope`

**Files:**
- Modify: `science/src/science_tool/dataset_prioritize.py`
- Test: `science/tests/test_dataset_prioritize.py`

**Interfaces:**
- Consumes: `is_valid_scope` from Task 1.
- Produces: `target_coverage(rows, project_root)` reports `coverage_state == "out-of-molecular-scope"` and `gap_reason == <scope value>` for a target whose frontmatter carries a valid `capability_scope`.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_dataset_prioritize.py` (uses the module's existing `_write`, `prioritize`, `target_coverage` helpers):

```python
def test_target_coverage_reports_out_of_molecular_scope(tmp_path: Path) -> None:
    _write(
        tmp_path / "entities/questions/q-method.md",
        '---\nid: "question:q-method"\nkind: "question"\ntitle: "Meta method"\n'
        'capability_scope: "methodological"\n'
        'datasets: ["dataset:run"]\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/run.md",
        '---\nid: "dataset:run"\nkind: "dataset"\ntitle: "Run"\norigin: "external"\n'
        'dataset_class: "deposit"\ndatapackage: "data/run/datapackage.json"\n'
        'provided_capabilities: [{assay: "gene-expression", modality: "bulk-rna"}]\n'
        'access: {level: "public", verified: true}\n---\n',
    )

    rows = prioritize(tmp_path)
    coverage = target_coverage(rows, tmp_path)[0]

    assert coverage["coverage_state"] == "out-of-molecular-scope"
    assert coverage["gap_reason"] == "methodological"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize.py::test_target_coverage_reports_out_of_molecular_scope -q`
Expected: FAIL (`coverage_state` is a capability-gap/coverage value, not `out-of-molecular-scope`).

- [ ] **Step 3: Add the import**

In `science/src/science_tool/dataset_prioritize.py`, add to the imports near `capability_fit` (find the existing `from science_tool.datasets.capabilities import ...` line and add):

```python
from science_tool.datasets.capability_scope import is_valid_scope
```

- [ ] **Step 4: Short-circuit scoped targets in `target_coverage`**

In `target_coverage`, inside `for target, target_rows in by_target.items():`, immediately after the two lines:

```python
        datasets = sorted(row["id"] for row in target_rows)
        target_fm = targets[target]["frontmatter"]
```

insert:

```python
        scope = target_fm.get("capability_scope") if isinstance(target_fm, dict) else None
        if is_valid_scope(scope):
            targets[target]["datasets"] = datasets
            targets[target]["dataset_count"] = len(datasets)
            targets[target]["coverage_state"] = "out-of-molecular-scope"
            targets[target]["gap_reason"] = str(scope)
            continue
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize.py -q`
Expected: PASS (new test + all existing prioritize tests).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/dataset_prioritize.py science/tests/test_dataset_prioritize.py
git commit -m "feat: out-of-molecular-scope coverage state for capability_scope targets"
```

---

### Task 4: User-guide documentation

**Files:**
- Modify: `docs/user-guide/entities.md` (repo-root `docs/`, ~lines 1023–1057)

**Interfaces:** none (documentation only). Depends on the strings from Tasks 2–3.

- [ ] **Step 1: Add the coverage state to the states sentence**

In `docs/user-guide/entities.md`, in the sentence listing coverage states (currently ending `..., \`capability-mismatch\`, and \`no-candidate\`.`), add `out-of-molecular-scope` so it reads:

```markdown
`missing-provided-capabilities`, `capability-mismatch`, `out-of-molecular-scope`,
and `no-candidate`.
```

- [ ] **Step 2: Add a capability_scope subsection**

Immediately after the paragraph that ends "... are not non-empty lists of non-empty string mappings." (the paragraph beginning "Within one capability set..."), insert:

```markdown
Some entities are non-molecular by nature and legitimately declare no
capabilities — clinical-only cohorts, outcome/registry data, or method/census
questions. Mark these with `capability_scope` so the missing-capability warning is
suppressed instead of firing on an intentional gap:

```yaml
capability_scope: clinical-outcome
```

`capability_scope` means "this entity is outside the molecular assay/modality
gate." Values are `reference-substrate`, `derived-product`, `methodological`,
`model-system` (terminal — the entity measures nothing on any axis) and
`clinical-outcome`, `epidemiological`, `behavioral-instrument` (transitional —
non-molecular measurement, pending a future outcome axis). A scoped target reports
coverage state `out-of-molecular-scope` rather than a capability gap. The field is
mutually exclusive with any non-empty `provided_capabilities` /
`required_capabilities`; declaring both, or using an unknown value, is a
`science validate` warning. A scoped entity never receives molecular coverage
credit.
```

- [ ] **Step 3: Verify no validator/doc drift**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_dataset_capabilities.py tests/test_dataset_prioritize.py -q`
Expected: PASS (sanity that docs match implemented strings; no code changed).

- [ ] **Step 4: Commit**

```bash
cd ~/d/science
git add docs/user-guide/entities.md
git commit -m "docs: document capability_scope marker and out-of-molecular-scope state"
```

---

### Task 5: MM30 rollout — annotate 32 non-molecular entities

**Files (all under `~/d/cancer/cancer-types/mm30--capability-warnings-cleanup/entities/`):** add one `capability_scope:` frontmatter key per entity below. These entities currently have **no** `provided_capabilities` / `required_capabilities`, so no `scope-conflict` will arise.

**Mapping (entity id → scope value):**

`clinical-outcome` (15): `datasets/chabrun2026-dfci`, `datasets/chabrun2026-athens-ucl`, `datasets/chabrun2026-heidelberg`, `datasets/chabrun2026-navarra`, `datasets/chabrun2026-milan`, `datasets/chabrun2026-wurzburg`, `datasets/midas-trial`, `datasets/ifm2020-02-trial`, `datasets/perseus-trial`, `datasets/linker-mm1-trial`, `datasets/chunara2025-rw-bispecific-cohort`, `datasets/tan2025-rw-teclistamab-cohort`, `questions/0018-*`, `questions/0046-*`, `questions/0161-*`.

`model-system` (2): `datasets/chek2-mouse-model`, `datasets/vk-myc-mouse`.

`reference-substrate` (1): `datasets/mm30-geo-microarray-probe-symbol-collapse`.

`methodological` (14): `questions/0109-*`, `questions/0001-*`, `questions/0003-*`, `questions/0005-*`, `questions/0118-*`, `questions/0174-*`, `questions/0175-*`, `questions/0176-*`, `questions/0180-*`, `questions/0181-*`, `questions/0182-*`, `questions/0188-*`, `questions/0195-*`, `hypotheses/0021-*`.

- [ ] **Step 1: Guard — confirm none of the 32 already declare capabilities**

```bash
cd ~/d/cancer/cancer-types/mm30--capability-warnings-cleanup
for g in chabrun2026-dfci chabrun2026-athens-ucl chabrun2026-heidelberg chabrun2026-navarra \
  chabrun2026-milan chabrun2026-wurzburg midas-trial ifm2020-02-trial perseus-trial \
  linker-mm1-trial chunara2025-rw-bispecific-cohort tan2025-rw-teclistamab-cohort \
  chek2-mouse-model vk-myc-mouse mm30-geo-microarray-probe-symbol-collapse; do
  f=$(ls entities/datasets/$g.md 2>/dev/null); grep -lE '^(provided|required)_capabilities:' "$f" 2>/dev/null; done
for n in 0018 0046 0161 0109 0001 0003 0005 0118 0174 0175 0176 0180 0181 0182 0188 0195; do
  f=$(ls entities/questions/$n-*.md 2>/dev/null); grep -lE '^(provided|required)_capabilities:' "$f" 2>/dev/null; done
ls entities/hypotheses/0021-*.md | xargs grep -lE '^(provided|required)_capabilities:' 2>/dev/null
```

Expected: **no output** (empty). Any file printed here already declares capabilities and must be reviewed manually before scoping (it would trigger `scope-conflict`).

- [ ] **Step 2: Apply the marker to each file**

Insert `capability_scope: <value>` on its own line inside each file's frontmatter (immediately after the `status:` line when present, else right after the opening `---`). Apply with this idempotent Python helper (run from the MM30 worktree):

```python
# scratchpad: apply_capability_scope.py — run once, then delete.
import glob, pathlib

MAPPING = {
    "clinical-outcome": [
        "datasets/chabrun2026-dfci", "datasets/chabrun2026-athens-ucl",
        "datasets/chabrun2026-heidelberg", "datasets/chabrun2026-navarra",
        "datasets/chabrun2026-milan", "datasets/chabrun2026-wurzburg",
        "datasets/midas-trial", "datasets/ifm2020-02-trial", "datasets/perseus-trial",
        "datasets/linker-mm1-trial", "datasets/chunara2025-rw-bispecific-cohort",
        "datasets/tan2025-rw-teclistamab-cohort",
        "questions/0018", "questions/0046", "questions/0161",
    ],
    "model-system": ["datasets/chek2-mouse-model", "datasets/vk-myc-mouse"],
    "reference-substrate": ["datasets/mm30-geo-microarray-probe-symbol-collapse"],
    "methodological": [
        "questions/0109", "questions/0001", "questions/0003", "questions/0005",
        "questions/0118", "questions/0174", "questions/0175", "questions/0176",
        "questions/0180", "questions/0181", "questions/0182", "questions/0188",
        "questions/0195", "hypotheses/0021",
    ],
}

def resolve(stem: str) -> pathlib.Path:
    hits = glob.glob(f"entities/{stem}.md") or glob.glob(f"entities/{stem}-*.md")
    if len(hits) != 1:
        raise SystemExit(f"ambiguous/missing: {stem} -> {hits}")
    return pathlib.Path(hits[0])

for scope, stems in MAPPING.items():
    for stem in stems:
        path = resolve(stem)
        lines = path.read_text().splitlines()
        if any(ln.startswith("capability_scope:") for ln in lines):
            continue  # idempotent
        # frontmatter is the block between the first two '---' delimiters
        fm_end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
        insert_at = fm_end  # fallback: last line of frontmatter block
        for i in range(1, fm_end):
            if lines[i].startswith("status:"):
                insert_at = i + 1
                break
        else:
            insert_at = 1  # no status line: right after opening '---'
        lines.insert(insert_at, f"capability_scope: {scope}")
        path.write_text("\n".join(lines) + "\n")
        print(f"scoped {path} -> {scope}")
```

Run: `cd ~/d/cancer/cancer-types/mm30--capability-warnings-cleanup && uv run python scratchpad/apply_capability_scope.py` (place the script under the worktree scratch dir, not in the repo), then delete it. Spot-check two files (`entities/datasets/chek2-mouse-model.md`, `entities/hypotheses/0021-*.md`) to confirm the key sits in the frontmatter block.

- [ ] **Step 3: Verify warnings clear and no new scope warnings**

```bash
cd ~/d/cancer/cancer-types/mm30--capability-warnings-cleanup
uv run --frozen science validate 2>&1 | grep -c 'dataset-capabilities'          # expect 0
uv run --frozen science validate 2>&1 | grep -E 'scope-unknown|scope-conflict'  # expect no output
```

Expected: zero `dataset-capabilities.*` warnings, and no `scope-unknown` / `scope-conflict`. If any `scope-unknown` fires, a value was mistyped; if `scope-conflict` fires, Step 1's guard was violated.

- [ ] **Step 4: Run the MM30 capability guardrail (registry vocab check)**

The MM30-local guardrail validates `{assay, modality}` vocab; `capability_scope` is a separate scalar it does not police, but run it to confirm no regressions:

```bash
cd ~/d/cancer/cancer-types/mm30--capability-warnings-cleanup
uv run --frozen python -m scripts.data_catalog.needs_audit validate-capabilities \
  --vocab doc/plans/capabilities-vocab.yaml || true
```

Expected: OK (unchanged from before this task).

- [ ] **Step 5: Commit (MM30 worktree)**

```bash
cd ~/d/cancer/cancer-types/mm30--capability-warnings-cleanup
git add entities/
git commit -m "chore: mark 32 non-molecular entities with capability_scope (clears capability warnings)"
```

Note: this commit lands on the MM30 worktree branch `capability-warnings-cleanup`; the user merges it locally per their workflow. It depends on Tasks 1–3 being present in the `~/d/science` working tree (the editable `science` install the worktree consumes).

---

## Self-Review

**Spec coverage:**
- Enum registry module → Task 1. ✓
- Validator behavior 1 (suppress) / 2 (scope-unknown, fail-closed) / 3 (scope-conflict) → Task 2. ✓
- No `scope-contradicted` lint → intentionally absent (Global Constraints + design Resolved decisions). ✓
- `out-of-molecular-scope` coverage state → Task 3. ✓
- No matching-engine change → honored (capabilities.py untouched; scoped entities keep empty caps and fail-close). ✓
- User-guide docs → Task 4. ✓
- MM30 rollout of 32 entities, clearing the 8 live warnings → Task 5 (the 8 = chabrun×6 + chek2 + q0018, all in the mapping). ✓

**Placeholder scan:** none — every step has concrete code/commands and expected output.

**Type consistency:** `is_valid_scope`, `VALID_SCOPES`, `_scope_gate(scope, ident, path_value, field_issue, field_name) -> tuple[bool, list[Result]]`, rule strings `dataset-capabilities.scope-unknown` / `scope-conflict`, and coverage string `out-of-molecular-scope` are used identically across Tasks 1–4.
