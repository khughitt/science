# Feedback Batch T Implementation Plan — slices 1–4

> **For agentic workers:** implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Close the four execution-geometry gap filings, one guidance filing,
and one positive, by
shipping a cost-gate doctrine leaf, a pre-registration Cost Gate section, and
one validate check that can actually fail.

**Design:** [`2026-07-26-feedback-batch-t-design.md`](2026-07-26-feedback-batch-t-design.md).
Slice 0 (D0) already shipped standalone — `a3611ed2`, merged `c6a57e70`.

**Branch:** `feedback-batch-t`, rebased onto main `ca937131`.

## Global Constraints

- Work from `~/d/science/.worktrees/feedback-batch-t`. **Use
  absolute paths in every command** — the shell cwd silently resets between
  calls in this environment.
- Tests: `cd science && uv run --frozen pytest` (~2–3 min, exceeds the default
  120 s timeout — scope selections per task, full suite only at the end with an
  explicit long timeout). Model: `cd science/model && uv run --frozen pytest`.
- Lint per package: `uv run ruff check`. Types once from `science/`:
  `uv run pyright`.
- No AI-attribution trailers. Conventional commits. No "legacy"/"compatibility"
  layers. No `Unified` prefix. Composition over inheritance; fail early over
  silent fallback.
- Paths in docs/code use `~/d/` or repo-relative form, never
  `/home/keith/` or `/mnt/ssd/Dropbox/`.
- The two pre-registration template copies must stay byte-identical —
  `test_root_and_packaged_migrated_templates_match` enforces it. Edit
  `templates/pre-registration.md`, then copy over
  `science/model/src/science_model/templates/pre-registration.md`.

## Hazards this plan defends against

1. **`CANONICAL_CHECK_MODULES` is an explicit tuple**, and the obvious guard
   against forgetting it does not work. A plain end-to-end test passes without
   the tuple entry, because the unit tests import the module and `@Check` fires
   on import. Task 5 uses the order-robust clear/evict/reload fixture, and
   Step 3a observes it failing before trusting it.
2. **An unbounded antecedent selects the whole corpus and looks like success.**
   The first draft's schedule regex matched **34 of 34** natural-systems
   pre-registrations — `thin ` inside "within", `ess` inside "unless". Tokens
   are word-bounded, and test 5 is the corpus-derived regression.
3. **A heading with no `_template.sections` descriptor breaks the renderer
   unconditionally** — this is what D0 repaired. Task 3 adds both together and
   the D0 guard proves it.
4. **Deleting a row must not be cheaper than filling it, and the coverage must
   be symmetric.** Absent, empty, and placeholder are one verdict for *both*
   required rows — a 2×3 parametrized matrix. Testing three states for one row
   and one state for the other would let an implementation check `Target
   geometry` for placeholders only while every test stayed green.
5. **A fixture that writes the reader's own convention cannot falsify the
   reader.** Task 6 certifies against the four real projects, not fixtures, and
   has explicit authority to send the check back to code.

## File structure

| File | Responsibility |
|---|---|
| `skills/study-design/cost-gate-certification.md` | NEW — the doctrine (Groups A and B) |
| `skills/INDEX.md` | registry row; an orphan skill fails `test_skill_inventory` |
| `skills/study-design/SKILL.md` | Leaves-table row |
| `skills/pipelines/SKILL.md` | routing pointer (no duplicated doctrine) |
| `skills/study-design/estimator-certification.md` | one link from step 3, "price the design" |
| `codex-skills/` | regenerated mirror |
| `templates/pre-registration.md` + packaged copy | `## Cost Gate` + its `sections:` descriptor |
| `science/src/science_tool/validate/prereg_frozen.py` | NEW — `frozen_because`, shared by two checks |
| `science/src/science_tool/validate/checks/prereg_vehicles.py` | re-point to the shared helper |
| `science/src/science_tool/validate/checks/prereg_schedule.py` | NEW — the check |
| `science/src/science_tool/validate/checks/__init__.py` | register the module |
| `science/tests/validate/test_checks_prereg_schedule.py` | NEW — unit + registration tests |

---

### Task 1: The doctrine leaf

**Files:**
- Create: `skills/study-design/cost-gate-certification.md`
- Modify: `skills/INDEX.md`, `skills/study-design/SKILL.md`,
  `skills/pipelines/SKILL.md`, `skills/study-design/estimator-certification.md`
- Regenerate: `codex-skills/`

**Interfaces:**
- Produces: skill id `study-design-cost-gate-certification`; Task 3's template
  comment links to this path.

- [ ] **Step 1: Write the leaf.** Frontmatter exactly:

```yaml
---
name: study-design-cost-gate-certification
description: Use when a sampling schedule, compute budget, or feasibility gate decides whether an analysis is affordable — especially when the benchmark, pilot, or schedule was measured at a different batch size, concurrency, substrate, or run phase than the one that will execute.
archetype: analysis-discipline
provenance: internal
---
```

Body must carry, each traceable to its filing:

- **The fact.** A measurement taken at a different execution geometry than the
  one it authorizes is not evidence about that geometry. State plainly that the
  mismatch has **no fixed direction** — a compile-dominated pilot overstates
  per-unit cost, a batched benchmark charged to a sequential workload
  understates it — and that the reliably optimistic bias comes from **favorable
  probe selection**, not from the mismatch. Do not write "errs optimistic".
- **Freeze the geometry before measuring** (`fb-2026-07-13-001`). The geometry
  is set by the budget being decided, so choosing it after measuring is
  circular and the circularity always resolves favourably.
- **The monotonicity tell** (`fb-2026-07-13-001`). Throughput must be monotone
  in the work parameter; N=64 measuring faster than N=32 proves the measurement
  tracks per-call dispatch overhead, not the computation.
- **Near-worst, one geometry** (`fb-2026-07-13-002`). p90 over R≥5 repeats at
  the single geometry that executes. Never the best across a sweep — a cost
  gate exists to REFUSE work, so selecting the favourable configuration is the
  selection effect that makes it unable to refuse.
- **Steady state and target concurrency** (`fb-2026-07-12-014`). Warmup adapts
  to parameters the run does not ultimately use; JIT/compile masks contention.
  Pin intra-op threads (`XLA_FLAGS=intra_op_parallelism_threads=1`,
  `OMP_NUM_THREADS=1`) and treat throughput at target concurrency as an
  empirical result, never a projection. Name the mechanism: compile
  amortisation, not estimator choice.
- **A schedule's calibration domain** (`fb-2026-07-25-009`). A burn-in/thinning
  schedule validated on one substrate is a hypothesis about a different one
  until probed; a cheap single-chain ACT probe sizes it up front.
- **Profile before ordering a remedy ladder** (`fb-2026-07-25-010`). A remedy
  targeting a negligible cost fraction cannot help regardless of theoretical
  merit. Order rungs by measured bottleneck, and give a decision-maker the cost
  split with the options.
- **What works** (`fb-2026-07-25-011`). Verdict-blind viability/mixing gates
  evaluated before observed-data exposure make repeated sampler failures cost
  nothing epistemically. Record this as the positive pattern, not only the
  failures.
- A `## Companion Skills` section pointing at `estimator-certification.md`
  (cost is the axis it does not cover) and `replicate-count-justification.md`.

- [ ] **Step 2: Register it.** Add to `skills/INDEX.md`, after the
  `study-design-estimator-certification` row:

```markdown
- `study-design-cost-gate-certification`: `skills/study-design/cost-gate-certification.md`
```

Add to the `skills/study-design/SKILL.md` Leaves table:

```markdown
| `cost-gate-certification.md` | a schedule / budget / feasibility gate decides affordability | no cost or schedule decision at stake |
```

- [ ] **Step 3: Cross-link, do not duplicate.** In
  `estimator-certification.md`, the ordering rule's step 3 ("price the design")
  gains a pointer to the new leaf. In `skills/pipelines/SKILL.md`, add a
  routing line so a pipelines-context agent reaches it — a pointer only; the
  XLA/contention doctrine lives in the leaf and is not copied.

- [ ] **Step 4: Regenerate the codex mirror** with the repo's own wrapper — it
  resolves the repo root from its own location, so it cannot be pointed at the
  wrong tree:

```bash
cd ~/d/science/.worktrees/feedback-batch-t/science && uv run --frozen python ../scripts/generate_codex_skills.py
```

- [ ] **Step 5: Verify.**

```bash
cd ~/d/science/.worktrees/feedback-batch-t/science && uv run --frozen pytest tests/skills_lint tests/test_skill_inventory.py tests/test_codex_skills.py -q
```
Expected: PASS. A missing INDEX row fails
`test_registry_rejects_orphan_skill`; a stale mirror fails the codex drift
guard.

- [ ] **Step 6: Commit** — `feat(skills): cost-gate certification doctrine`

---

### Task 2: Extract the frozen-pre-registration helper

Split out so Task 3 and Task 5 do not both edit `prereg_vehicles.py`.

**Files:**
- Create: `science/src/science_tool/validate/prereg_frozen.py`
- Modify: `science/src/science_tool/validate/checks/prereg_vehicles.py`

**Interfaces:**
- Produces: `frozen_because(frontmatter: dict[str, Any]) -> str | None`.

- [ ] **Step 1: Move it verbatim.** Cut `_frozen_because` and `_FROZEN_STATUSES`
  from `prereg_vehicles.py` into the new module as **public** `frozen_because`
  and module-private `_FROZEN_STATUSES`. Keep the existing docstring intact —
  it records why `amendments:` counts as frozen and why `committed:` does not,
  and that reasoning is load-bearing for the new check too.

  Placed in `validate/`, not `validate/checks/`: `checks/` holds check
  definitions named in `CANONICAL_CHECK_MODULES`, and a helper there invites a
  future reader to assume it is registered.

- [ ] **Step 2: Re-point the caller.** `prereg_vehicles.py` imports
  `frozen_because` and calls it where `_frozen_because` was.

- [ ] **Step 3: Verify no behavior change.**

```bash
cd ~/d/science/.worktrees/feedback-batch-t/science && uv run --frozen pytest tests/validate/test_checks_prereg_vehicles.py -q
```
Expected: PASS, unchanged count. A pure move must not alter one result.

- [ ] **Step 4: Commit** — `refactor(validate): share the frozen-pre-registration predicate`

---

### Task 3: The Cost Gate template section

**Files:**
- Modify: `templates/pre-registration.md`, then copy to
  `science/model/src/science_model/templates/pre-registration.md`

**Interfaces:**
- Produces: section key `cost-gate`, heading
  `Cost Gate (execution geometry)`. Task 5's check parses this heading and its
  `Target geometry` / `Calibration domain` rows.

- [ ] **Step 1: Add the descriptor**, immediately after
  `estimator-certification-gate`:

```yaml
    - { key: cost-gate, name: "Cost Gate (execution geometry)", required: false }
```

`required: false` is deliberate — see design D2. It matches the three sibling
conditional gates, and `required: true` would place the marker in every
rendered pre-registration, which would make a marker-presence check pass
universally.

- [ ] **Step 2: Add the section body**, immediately after the Estimator
  Certification Gate table and before `## Execution-Readiness Gate`:

````markdown
## Cost Gate (execution geometry)

<!-- Applies when a sampling schedule, compute budget, or feasibility gate decides whether
     the analysis is affordable. If no cost decision is at stake, DELETE this section.

     A measurement taken at a different execution geometry than the one it authorizes is
     not evidence about that geometry. The mismatch has NO fixed direction -- a
     compile-dominated pilot overstates per-unit cost; a batched benchmark charged to a
     sequential workload understates it. What makes the error reliably optimistic is
     favourable probe selection: the max over a sweep, the convenient batch size, the fast
     part of the run.

     Order, extending estimator-certification's: well-posedness -> certify the estimator ->
     price the design AT THE GEOMETRY THAT WILL EXECUTE -> commit the budget.

     See skills/study-design/cost-gate-certification.md. -->

| Axis / commitment | Value | Reference / domain |
|---|---|---|
| Target geometry | <the geometry that will execute: batch size, call pattern, sequencing, target concurrency> | <frozen BEFORE measuring. The geometry is set by the budget being decided, so choosing it after measuring is circular -- and the circularity resolves favourably every time.> |
| Calibration domain | <the substrate and geometry the schedule/benchmark was ACTUALLY measured on: dimensions, sparsity, hardware, library stack> | <if this differs from Target geometry, this gate does not authorize the budget. Recalibrate, or state the transfer argument and what would falsify it.> |
| Statistic | <near-worst over R >= 5 repeats at the ONE target geometry, e.g. p90 of wall time> | <NEVER the best across a configuration sweep. A cost gate exists to REFUSE work; selecting the favourable configuration is what makes it unable to.> |
| Steady state | <warmup / JIT / compile excluded; measured after amortisation> | <early iterations adapt to parameters the run does not ultimately use, and compile time masks multi-process contention entirely> |
| Monotonicity | <throughput is monotone in the work parameter> | <non-monotonicity -- N=64 faster than N=32 -- proves the measurement tracks per-call dispatch overhead, not the computation> |
| Bottleneck profile | <measured per-iteration cost split across components> | <a remedy targeting a negligible cost fraction cannot help regardless of theoretical merit; order any remedy ladder by measured bottleneck> |
| Transfer | <EXECUTED recalibration probe | CONDITIONAL on ...> | <a schedule validated on another substrate is a hypothesis about this one until probed> |
| Invalidation | <what re-opens this gate> | <substrate size or sparsity, hardware, library stack, concurrency, estimator> |
````

- [ ] **Step 3: Sync the packaged copy and verify it renders.**

```bash
cd ~/d/science/.worktrees/feedback-batch-t && cp templates/pre-registration.md science/model/src/science_model/templates/pre-registration.md
cd science/model && uv run --frozen pytest tests/test_templates.py -q
```
Expected: PASS. `test_every_migrated_template_renders` (from D0) is what proves
the descriptor was not forgotten; `test_root_and_packaged_migrated_templates_match`
proves both copies moved together.

- [ ] **Step 4: Confirm opt-in rendering.**

```bash
cd ~/d/science/.worktrees/feedback-batch-t/science/model && uv run --frozen python -c "
from science_model.templates import Renderer
from datetime import date
f={'entity_id':'pre-registration:0001-x','kind':'pre-registration','title':'T','status':'committed','created':'2026-07-27','updated':'2026-07-27','related':[],'nn':'01','slug':'x','local_part':'0001-x'}
r=Renderer(today=date(2026,7,27))
assert 'Cost Gate' not in r.render('pre-registration', fields=f)
assert 'Cost Gate' in r.render('pre-registration', fields=f, with_keys={'cost-gate'})
print('opt-in confirmed')
"
```

- [ ] **Step 5: Commit** — `feat(templates): pre-registration Cost Gate (execution geometry)`

---

### Task 4: The check — failing tests first

**Files:**
- Create: `science/tests/validate/test_checks_prereg_schedule.py`

**Interfaces:**
- Consumes: `frozen_because` (Task 2); the `Cost Gate` heading (Task 3).
- Produces: rule name `prereg.schedule-calibration-domain`.

Write these RED before any implementation. Model the fixtures on
`tests/validate/test_checks_prereg_vehicles.py`.

- [ ] **Step 1: Write the tests.** Six test functions, 11 cases (test 2 parametrizes to 6), each a frozen pre-registration
  (`status: committed`) under `entities/pre-registrations/`:

1. `test_schedule_without_cost_gate_warns` — body declares a schedule
   (`burn-in = 5 x ones`, `thinning`, `ESS >= 400`), no `## Cost Gate`.
   Expect one WARN, rule `prereg.schedule-calibration-domain`, message naming
   the absent gate.
2. `test_unfilled_required_row_warns` — **parametrized over both axes, 2 rows ×
   3 states = 6 cases.** The contract makes absent, empty, and placeholder one
   verdict for *both* load-bearing rows, so the tests must cross them. Covering
   three states for one row and one state for the other lets an implementation
   check `Target geometry` for placeholders only, and every test still passes.

```python
@pytest.mark.parametrize("row", ["Target geometry", "Calibration domain"])
@pytest.mark.parametrize("state", ["absent", "empty", "placeholder"])
def test_unfilled_required_row_warns(tmp_path: Path, row: str, state: str) -> None:
    """Both required rows, all three unfilled states, one verdict.

    The other row is FILLED in every case, so the finding can only come from the
    row under test -- otherwise a check that ignores `Target geometry` entirely
    would still pass, carried by its sibling.
    """
```

   Build the gate with the sibling row filled with real prose, and the row
   under test deleted (`absent`), present with an empty value cell (`empty`),
   or carrying `<...>` (`placeholder`). Assert exactly one WARN, rule
   `prereg.schedule-calibration-domain`, whose message names the row under test
   — not merely that some row was unfilled.

3. `test_filled_cost_gate_passes` — both rows filled with prose. Expect no
   results.
4. `test_no_schedule_declared_emits_nothing` — no schedule terms, no gate.
   Expect no results — the antecedent must gate the rule.
5. `test_ordinary_prose_does_not_trip_the_antecedent` — a frozen
   pre-registration with **no** schedule whose body contains "within",
   "unless", "process", and "assess", and no Cost Gate. Expect no results.
   This is the corpus-derived regression: the unbounded draft matched 34 of 34
   natural-systems pre-registrations on exactly these substrings.
6. `test_unfrozen_pre_registration_emits_nothing` — schedule declared, no gate,
   but `status: draft` and no `amendments:`. Expect no results: the obligation
   attaches at freeze, matching `prereg.vehicle-undeclared`.

- [ ] **Step 2: Run them RED.**

```bash
cd ~/d/science/.worktrees/feedback-batch-t/science && uv run --frozen pytest tests/validate/test_checks_prereg_schedule.py -q
```
Expected: all 11 FAIL on import (`prereg_schedule` does not exist).

- [ ] **Step 3: Record the red run — do NOT commit yet.** Save the failure
  output as evidence for the results doc. Committing tests that cannot import
  their module would leave the branch in a state where `pytest` cannot even
  collect, so tests and implementation land together in Task 5's commit. The
  red run is the evidence; the separate commit is not.

---

### Task 5: The check — implementation

**Files:**
- Create: `science/src/science_tool/validate/checks/prereg_schedule.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py`
- Modify: `science/tests/validate/test_checks_prereg_schedule.py` (add the
  registration test)

- [ ] **Step 1: Implement.** Module docstring records the incident
  (`fb-2026-07-25-009`, natural-systems `pre-registration:0034` importing
  `0026`'s schedule onto a 40× larger, far sparser substrate) and states that
  the trigger is content, not a heading.

  Shape, following `prereg_vehicles.check_prereg_vehicles`:
  - iterate `entities/pre-registrations/*.md` via
    `resolve_path_policy("pre-registration").root`
  - skip unless `frontmatter["kind"] == "pre-registration"`
  - skip unless `frozen_because(frontmatter)` is not None
  - skip unless the body declares a schedule. **The tokens must be
    word-bounded and case-sensitive where the token is an acronym:**

```python
# Word-bounded on purpose. An earlier draft used bare `thin ` and a
# case-insensitive `ESS`; measured against the natural-systems corpus that
# matched 34 of 34 pre-registrations -- `thin ` inside "within", `ess` inside
# "unless"/"process"/"assess". An antecedent that selects the whole corpus is
# exactly as uninformative as one that selects none of it, and it looks like a
# success. This pattern selects 5 of 34, the documents that genuinely declare a
# schedule. It remains a PROSE HEURISTIC, which is why the rule is WARN and
# ungated.
_SCHEDULE_TOKENS = re.compile(r"\bburn[- ]in\b|\bthinning\b|\bR[_-]?hat\b|\bESS\b")
```

  - locate the `## Cost Gate` section; if absent → WARN, message
    *"declares a sampling schedule but carries no Cost Gate; the schedule's
    calibration domain is undeclared"*
  - if present, parse its table rows. **A row is unfilled in three distinct
    ways, and all three must be treated alike** — otherwise deleting a row is a
    cheaper way to pass than filling it:

    | state | example | verdict |
    |---|---|---|
    | **absent** | the `Calibration domain` row is not in the table | unfilled |
    | **empty** | `\| Calibration domain \| \| ... \|` | unfilled |
    | **placeholder** | `\| Calibration domain \| <the substrate...> \| ... \|` | unfilled |

    Placeholder detection strips the cell before matching `^<.*>$`, so
    surrounding whitespace does not defeat it. Any of the three → WARN naming
    the specific row and its state.
  - the other rows are doctrine, never part of the trigger (design D3)

- [ ] **Step 2: Register the module.** Add `"prereg_schedule"` to
  `CANONICAL_CHECK_MODULES` in `validate/checks/__init__.py`, immediately after
  `"prereg_vehicles"`.

- [ ] **Step 3: Add the registration test — order-robust, or it proves
  nothing.** A naive end-to-end test does NOT catch a missing tuple entry:
  the unit tests above import `prereg_schedule`, which fires `@Check` as an
  import side effect, so the registry already holds the check by the time the
  end-to-end test runs. It would pass with `CANONICAL_CHECK_MODULES` untouched.

  Use the pattern documented at
  `tests/validate/test_checks_dataset_capabilities.py:14`, whose docstring
  carries a ☠️ on this exact hazard — `@Check` fires only on **first** import,
  so the registry must be cleared, the module evicted from `sys.modules`, and
  the real loader invoked:

```python
@pytest.fixture
def prereg_schedule_registered() -> Generator[None]:
    """Re-register `prereg_schedule` through the real loader, then RESTORE the registry.

    Without the `sys.modules.pop`, `_load_canonical_checks()` re-imports an
    already-imported module -- a no-op, because `@Check` fires only on first
    import -- and the test passes whether or not the module is in
    CANONICAL_CHECK_MODULES. Teardown reloads every canonical module, because a
    cleared registry is PERMANENT for the session and every later `runner.run`
    would otherwise iterate a near-empty check list and silently report nothing.
    """
    checks.clear_checks_for_tests()
    sys.modules.pop("science_tool.validate.checks.prereg_schedule", None)
    checks._load_canonical_checks()
    yield
    checks.clear_checks_for_tests()
    for module_name in CANONICAL_CHECK_MODULES:
        importlib.reload(importlib.import_module(f"science_tool.validate.checks.{module_name}"))
```

  The test uses that fixture, builds a project holding the offending
  pre-registration, runs the pipeline the CLI runs (never
  `check_prereg_schedule` directly), and asserts
  `prereg.schedule-calibration-domain` appears.

- [ ] **Step 3a: Prove the registration test can fail.** Temporarily remove
  `"prereg_schedule"` from `CANONICAL_CHECK_MODULES`, run only the registration
  test, and confirm it FAILS. Restore the entry and confirm it passes. A
  registration test that has never been observed to fail is exactly the
  cannot-fail gate this batch exists to eliminate.

- [ ] **Step 4: Run GREEN.**

```bash
cd ~/d/science/.worktrees/feedback-batch-t/science && uv run --frozen pytest tests/validate/test_checks_prereg_schedule.py tests/validate/test_checks_prereg_vehicles.py -q
```
Expected: all PASS.

- [ ] **Step 5: Confirm no gating.** The rule must NOT appear in
  `validate/gates.py`. Add nothing there. Verify:

```bash
cd ~/d/science/.worktrees/feedback-batch-t/science && uv run --frozen pytest tests/validate -q
```
Expected: PASS, including the snapshot tests — the fixture project declares no
sampling schedule, so no snapshot changes. **If a snapshot does change, stop
and read it** rather than re-recording: it means the antecedent is firing
somewhere unintended.

- [ ] **Step 6: Commit** — `feat(validate): prereg.schedule-calibration-domain`

---

### Task 6: Certify against the real corpus

This is the task that decides whether the check ships as written. **Do not skip
it, and do not tune the check to produce a pleasing count.**

- [ ] **Step 1: Run against all four projects that hold pre-registrations,
  keeping the paths and messages.** A bare count is not a certification
  artifact — adjudicating `0025` requires reading which document produced which
  message, and `grep -c` discards exactly that. Emit JSON to a file and select
  by exact rule:

```bash
cd ~/d/science/.worktrees/feedback-batch-t/science
for p in ~/d/natural-systems ~/d/3d-attention-bias ~/d/protein-landscape ~/d/seq-feats; do
  uv run --frozen science validate --project-root "$p" --format json \
    --output "/tmp/batch-t-$(basename $p).json"
done
uv run --frozen python - <<'PY'
import json, glob
for path in sorted(glob.glob("/tmp/batch-t-*.json")):
    payload = json.load(open(path))
    hits = [r for r in payload["results"]
            if r.get("rule") == "prereg.schedule-calibration-domain"]
    print(f"=== {path}: {len(hits)}")
    for r in hits:
        print(f"  {r.get('path')}\n    {r.get('message')}")
PY
```

  Select on `r["rule"] == "..."`, never a substring match over rendered output
  — a rule name that appears inside another rule's message would inflate the
  count, which is the same measurement error this batch is about.

- [ ] **Step 2: Read every finding.** Expected from the design's survey: 5 in
  natural-systems (`0007`, `0025`, `0026`, `0032`, `0034`), 0 in the other
  three. Open each and record whether the finding is substantively right.

- [ ] **Step 3: Adjudicate `0025` explicitly.** It reports achieved ESS per θ
  (1607–3392 of 10,000) on its own substrate — the calibration evidence the
  check asks for, expressed as a table rather than a Cost Gate section. Read it
  and rule: is the finding substantively right or wrong?

  **If it is wrong, this is a code change and follows the code loop, not a
  prose edit:**

  1. **Stop certifying.** Do not continue reading the remaining findings with
     an instrument you have already judged defective.
  2. **Write a corpus-derived regression test first** — a fixture reproducing
     `0025`'s shape (a schedule plus achieved diagnostics, no Cost Gate),
     asserting no finding. Run it RED.
  3. **Refine minimally.** Widen the escape hatch only by the narrow mechanical
     property that distinguishes `0025` — reported achieved diagnostics for
     this document's own substrate. Nothing broader.
  4. **Re-verify in full**: Task 5's tests, then `tests/validate`, then all
     four projects again from Step 1. A refinement that fixes `0025` and
     silences `0034` has broken the check.
  5. **Commit the code change separately** —
     `fix(validate): narrow schedule-calibration-domain to undeclared calibration`
     — so the refinement is reviewable apart from the certification record.
  6. **Then resume** certification from Step 2.

  **If no narrow mechanical property distinguishes `0025`, stop and revise the
  design.** Do not hand-tune the antecedent to fit one document; that is
  tuning the instrument to the answer, and it is the failure this batch exists
  to close. A check that needs a special case per document is a check whose
  antecedent is wrong.

- [ ] **Step 4: Record the certification domain.** The results doc states
  plainly: one project, one method family. natural-systems does MCMC; the other
  three do none and yield zero findings. This batch does not claim coverage it
  did not measure.

- [ ] **Step 5: Commit** — `docs(feedback): certify schedule-calibration-domain against the corpus`

---

### Task 7: Close the filings and write the results doc

- [ ] **Step 1: Full verification.**

```bash
cd ~/d/science/.worktrees/feedback-batch-t/science && uv run --frozen pytest
cd ~/d/science/.worktrees/feedback-batch-t/science/model && uv run --frozen pytest
cd ~/d/science/.worktrees/feedback-batch-t/science && uv run --frozen ruff check && uv run --frozen pyright
```
Run the science suite with an explicit long timeout (it exceeds 120 s).

- [ ] **Step 2: Write `docs/plans/2026-07-27-feedback-batch-t-results.md`** —
  the certification table, per-filing findings, any corrections to the design
  doc, the deferred `prereg.cost-geometry-undeclared` with its reason (1/46
  corpus uptake), and every behavior change downstream consumers will see.

- [ ] **Step 3: Close the filings** with detailed resolutions:
  `fb-2026-07-13-001`, `fb-2026-07-13-002`, `fb-2026-07-25-009`, and
  `fb-2026-07-25-010` (gaps); `fb-2026-07-12-014` (guidance); and
  `fb-2026-07-25-011` (positive — resolution records where the confirmed
  pattern is now written down).

- [ ] **Step 4: Commit, then hand back for the merge decision.** Do not merge
  without confirmation.

## Self-review

- Every design ruling has a task: D1→T1, D2→T3, D3→T4/T5/T6, D4→T7 step 2.
- All six filings are closed in T7 step 3, including the guidance and positive
  filings.
- Types are consistent: `frozen_because` is defined in T2 and consumed in T5;
  section key `cost-gate` is defined in T3 and parsed in T5.
- No task depends on an artifact a later task creates. T5 depends on T2 and T3;
  both precede it.
