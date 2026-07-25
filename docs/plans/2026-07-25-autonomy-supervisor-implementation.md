# Autonomy Supervisor and Lifecycle (Plan D) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship §2, §3, and §6 of
[`2026-07-24-autonomy-envelope-design.md`](2026-07-24-autonomy-envelope-design.md) — the
supervisor that opens a run, renders a verdict on it, writes the attested record, and
escalates a quarantine — closing slice S1.

**Architecture:** Two commands bracketing an actor nobody in this plan launches.
`science autonomy start` captures the belief basis and writes a **baseline outside the
repository**. `science autonomy finish` re-materializes the graph from a
supervisor-owned installation, recaptures the basis, runs the Plan C path gate, verifies
commit marks, renders a disposition, writes the run record, and files a `science
feedback` item on quarantine. A `validate` check makes violations catchable by anyone.

**Tech Stack:** Python 3.11+, pydantic v2, click, PyYAML, rdflib (via existing graph
code), `git` via `subprocess`. No new dependencies.

## What this plan does NOT ship

- **No autonomous agent, and no process that launches one.** The actor runs between the
  two commands, driven by whatever harness. Spawning, budget enforcement, kill switch,
  and loop convergence are S5.
- **No scheduler or trigger.** `triggered_by` stays optional and unwritten until S2.
- **No task eligibility.** S3.
- **No `added_by` vocabulary canonicalization.** Design §3 defers it out of S1.

## Grounding this plan rests on

Verified at `2320124e`. Do not contradict these.

- **A run record has no in-flight shape.** `AutonomousRunRecord`
  (`science/model/src/science_model/autonomous_runs.py:113`) documents it: *"a supervisor
  that dies mid-run leaves no record, so its branch reads as unattested rather than
  clean. That is the intended failure direction."* Every attested field is required.
  **Therefore `start` must not write a run record** — only `finish` does.
- **`runs/` holds only flat `*.md` records.** `load_run_records`
  (`science/src/science_tool/graph/autonomous_runs.py:107`) raises on any child that is
  not a flat regular `*.md` file, on symlinks, and when `record.slug != path.stem`.
  **The baseline cannot live in `runs/`.**
- **Run records parse under attestation-grade rules.** `_parse_run_record_frontmatter`
  (`:62`) requires whole-line `---` delimiters and rejects duplicate and merge keys
  recursively. The writer must emit exactly what that reader accepts.
- **`basis_digest` is conditional in both directions** — required when `disposition` is
  `clean` or `quarantined`, required **absent** when `unwired`. The model enforces it.
  Never write a sentinel, a zero digest, or the digest of an empty basis.
- **Plan A gives the observable.** `capture_basis(knowledge, provenance)` returns an
  `InstrumentResult[EntityBasis]`; `build_snapshot`/`load_snapshot` seal and verify a
  capture with `basis_digest`; `compare_bases(before, after)` yields `BasisDelta` rows
  for **pre-existing** entities only (`graph/belief_basis.py`).
- **Plan C gives the path gate.** `extract_change_set(repo_root, base, head)` and
  `evaluate(change_set, *, tier, report_path)` returning `GateVerdict(allowed, denials)`
  (`science/src/science_tool/autonomy/`). Every git call there passes
  `--no-replace-objects`; this plan's git calls must too.
- **Materialization is one call.** `materialize_graph(project_root)` from
  `science_tool.graph.materialize` writes `knowledge/graph.trig`.
- **Validate checks register by decorator.** `@Check(section=..., order=...)` over a
  function taking `ValidateContext` and yielding `Result(severity, path, line, message,
  rule, task)` (`science/src/science_tool/validate/checks/tooling.py:23`). Modules are
  listed in `CANONICAL_CHECK_MODULES` (`validate/checks/__init__.py:25`).
- **Feedback is stored outside the project.** `feedback_cli.py:27` resolves the
  directory to `$SCIENCE_FEEDBACK_DIR` or `get_science_config_dir()/feedback`. Filing a
  quarantine item therefore writes nothing into the run's worktree. `FeedbackEntry`
  requires `id`, `target`, and `summary`; use `next_feedback_id(dir, date_str)` and
  `save_entry(dir, entry)`.
- **Adding a CLI command trips the budget guards.** `test_budget_boundary.py` requires a
  `BUDGETS | EXEMPTIONS | DEFERRED` entry and locks the partition cardinality. Plan C
  moved it to `4/67/208 = 279`; **re-read the current value before editing** — this plan
  adds three leaves (`autonomy start`, `autonomy finish`, and nothing else), so the
  deferred count rises by 2 (start emits a fixed record; finish emits one row per
  denial/delta). Update `EXPECTED_CLASSIFICATION_COUNTS` and the docstring together.

### The baseline lives outside the repository

`start` must persist the before-capture somewhere `finish` can read it. It cannot go in
`runs/` (flat `*.md` only), and it must not go anywhere in the worktree at all: the
actor's whole purpose is to write the worktree, and a baseline it can reach is a
baseline it can rewrite. Design §0 puts the control plane outside the actor, so the
baseline goes outside too.

Both commands therefore take an explicit path: `start --baseline-out <path>` and
`finish --baseline <path>`, and **both refuse a path inside the project root**. The
supervisor chooses where its own state lives; nothing in the repository references it.

## Global Constraints

1. **`start` writes no run record.** A run that never finishes leaves no attestation.
2. **The baseline is refused inside the project root**, by both commands.
3. **`unwired` never means clean.** Any condition that prevents rendering a verdict —
   unreadable baseline, failed materialization, uncomputable basis, toolkit mismatch,
   gate error — yields `unwired`, which blocks. Exit `0` clean, `1` quarantined, `2`
   unwired, matching `graph belief-basis` and `autonomy path-gate`.
4. **`finish` re-materializes before capturing.** `graph.trig` is derived and the actor
   controls it: an actor that edits entities and never rebuilds would otherwise get a
   clean verdict while belief inputs really changed. This is Plan A's explicitly
   deferred gap and the single reason this step exists.
5. **The gate must be external.** `finish` refuses when the executing `science_tool`
   resolves inside the project root, and when the running toolkit revision differs from
   the one the baseline recorded.
6. **Commit marks are never evidence.** They are verified against the recorded
   `base_commit..head_commit` range and a mismatch quarantines, but a matching mark
   proves nothing on its own (design §3).
7. **Nothing is discarded on quarantine.** The branch and its work stay intact; the
   record is written with `disposition: quarantined` and a feedback item names the
   entity and the delta.
8. **Every git invocation passes `--no-replace-objects`,** before `-C`, as Plan C's
   `extract._git` already does. Reuse that helper rather than writing a second one.
9. **Two-dot commit ranges only.** Never `...`.
10. **pydantic models are `frozen=True, extra="forbid"`.**
11. **No AI-attribution trailer** on commit messages in this repo. (The `Science-Run:`
    trailer this plan *writes into other repositories' commits* is a different thing —
    design §3 — and is emitted by actors, not by this plan's commits.)
12. **Run the suite with `timeout: 600000`.** It takes ~290s. Never background it.
13. **Use `~/d/` or repo-relative paths** in docs and comments.

## File Structure

| File | Responsibility |
|---|---|
| `science/src/science_tool/autonomy/baseline.py` | `RunBaseline` model, sealed read/write. |
| `science/src/science_tool/autonomy/toolkit.py` | `toolkit_revision()`, `assert_gate_is_external()`. |
| `science/src/science_tool/autonomy/record_writer.py` | Render `AutonomousRunRecord` to `runs/<slug>.md`. |
| `science/src/science_tool/autonomy/marks.py` | Verify authors and `Science-Run:` trailers over a range. |
| `science/src/science_tool/autonomy/lifecycle.py` | `start_run()` / `finish_run()` — the whole verdict, no click. |
| `science/src/science_tool/autonomy/cli.py` | `start` / `finish` commands (modify). |
| `science/src/science_tool/validate/checks/autonomous_runs.py` | The `validate` check. |
| `science/src/science_tool/validate/checks/__init__.py` | Register the module (modify). |
| `science/src/science_tool/budget/registry.py` | Two `DeferredCommand` entries (modify). |
| `science/tests/test_autonomy_baseline.py` … `test_autonomy_validate_check.py` | Per task. |
| `docs/user-guide/agent-workflows.md` | Task 8 (modify). |
| `docs/plans/2026-07-24-autonomy-envelope-design.md` | Task 8 (modify). |

---

### Task 1: The run baseline

**Files:**
- Create: `science/src/science_tool/autonomy/baseline.py`
- Test: `science/tests/test_autonomy_baseline.py`

**Interfaces:**
- Consumes: `BasisSnapshot`, `build_snapshot`, `load_snapshot`, `basis_digest`,
  `EntityBasis` from `science_tool.graph.belief_basis`; `RunTier`, `PolicyIdentity` from
  `science_model.autonomous_runs`.
- Produces:
  - `class RunBaseline(BaseModel)` — `run_id: str`, `agent: str`, `model: str`,
    `tier: RunTier`, `branch: str`, `base_commit: str`, `toolkit_revision: str`,
    `policy_identity: PolicyIdentity`, `started: datetime`, `snapshot: BasisSnapshot`.
  - `class BaselineError(ValueError)`.
  - `write_baseline(path: Path, baseline: RunBaseline, *, project_root: Path) -> None`
  - `read_baseline(path: Path, *, project_root: Path) -> RunBaseline`
  - `reject_baseline_inside_project(path: Path, project_root: Path) -> None`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from science_model.autonomous_runs import PolicyIdentity, RunTier

from science_tool.autonomy.baseline import (
    BaselineError,
    RunBaseline,
    read_baseline,
    reject_baseline_inside_project,
    write_baseline,
)
from science_tool.graph.belief_basis import EntityBasis, build_snapshot


def _baseline() -> RunBaseline:
    rows = [
        EntityBasis(
            entity_id="hypothesis:h01", uri="urn:h01", target_uris=("urn:h01",),
            unit_keys=('{"line_uri": "urn:e1"}',), policy_id="core-default", policy_version="1",
        )
    ]
    return RunBaseline(
        run_id="run:2026-07-25-curation-sweep-a3f1",
        agent="curation-sweep",
        model="test-model",
        tier=RunTier.BELIEF_NEUTRAL,
        branch="auto/2026-07-25-curation-sweep-a3f1",
        base_commit="a" * 40,
        toolkit_revision="b" * 40,
        policy_identity=PolicyIdentity(id="core-default", version="1"),
        started=datetime(2026, 7, 25, 9, 0, tzinfo=UTC),
        snapshot=build_snapshot(rows),
    )


def test_a_baseline_round_trips(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    out = tmp_path / "state" / "run.json"

    write_baseline(out, _baseline(), project_root=project)
    assert read_baseline(out, project_root=project) == _baseline()


def test_a_baseline_inside_the_project_is_refused_on_write(tmp_path: Path):
    """The actor's whole job is writing the worktree; a baseline it can reach is a
    baseline it can rewrite."""
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(BaselineError):
        write_baseline(project / "runs" / "b.json", _baseline(), project_root=project)


def test_a_baseline_inside_the_project_is_refused_on_read(tmp_path: Path):
    project = tmp_path / "project"
    (project / "sub").mkdir(parents=True)
    inside = project / "sub" / "b.json"
    inside.write_text("{}", encoding="utf-8")
    with pytest.raises(BaselineError):
        read_baseline(inside, project_root=project)


def test_the_project_root_itself_is_refused(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(BaselineError):
        reject_baseline_inside_project(project, project)


def test_a_tampered_snapshot_is_refused(tmp_path: Path):
    """The snapshot carries Plan A's digest seal; a rewritten baseline must not load."""
    project = tmp_path / "project"
    project.mkdir()
    out = tmp_path / "state" / "run.json"
    write_baseline(out, _baseline(), project_root=project)
    out.write_text(out.read_text(encoding="utf-8").replace("urn:e1", "urn:e2"), encoding="utf-8")

    with pytest.raises(BaselineError):
        read_baseline(out, project_root=project)


def test_an_unreadable_baseline_is_an_error_not_an_empty_one(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(BaselineError):
        read_baseline(tmp_path / "state" / "absent.json", project_root=project)


def test_the_baseline_is_frozen_and_closed(tmp_path: Path):
    from pydantic import ValidationError

    baseline = _baseline()
    with pytest.raises(ValidationError):
        baseline.run_id = "run:other"  # type: ignore[misc]
```

- [ ] **Step 2: Run to verify failure**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_baseline.py -q
```

Expected: `ModuleNotFoundError: No module named 'science_tool.autonomy.baseline'`.

- [ ] **Step 3: Implement**

```python
"""The supervisor's before-capture, persisted OUTSIDE the run's repository.

Design §0 puts the control plane outside the actor. The baseline is control-plane
state: it fixes what the belief basis looked like before the run, so a baseline the
actor can reach is a baseline it can rewrite. It also cannot live in `runs/`, which
`load_run_records` restricts to flat `*.md` records.

This is NOT an in-flight run record. `AutonomousRunRecord` deliberately has no in-flight
shape: a supervisor that dies mid-run leaves no attestation, and its branch reads as
unattested rather than clean.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError
from science_model.autonomous_runs import PolicyIdentity, RunTier

from science_tool.graph.belief_basis import BasisSnapshot, SnapshotIntegrityError, load_snapshot


class BaselineError(ValueError):
    """The baseline could not be written, read, or trusted."""


class RunBaseline(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    agent: str
    model: str
    tier: RunTier
    branch: str
    base_commit: str
    toolkit_revision: str
    policy_identity: PolicyIdentity
    started: datetime
    snapshot: BasisSnapshot


def reject_baseline_inside_project(path: Path, project_root: Path) -> None:
    """Refuse any baseline path at or under `project_root`."""
    resolved = path.resolve()
    root = project_root.resolve()
    if resolved == root or root in resolved.parents:
        raise BaselineError(
            f"baseline path {path} is inside the project root {project_root}. The run's actor "
            "writes that tree, so a baseline stored there is not a baseline the supervisor owns."
        )


def write_baseline(path: Path, baseline: RunBaseline, *, project_root: Path) -> None:
    reject_baseline_inside_project(path, project_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(baseline.model_dump_json(indent=2), encoding="utf-8")
    except OSError as exc:
        raise BaselineError(f"could not write baseline to {path}: {exc}") from exc


def read_baseline(path: Path, *, project_root: Path) -> RunBaseline:
    """Load and re-verify a baseline. A baseline we cannot trust is never usable:
    every failure here becomes `unwired` upstream, not `clean`."""
    reject_baseline_inside_project(path, project_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineError(f"could not read baseline {path}: {exc}") from exc
    try:
        baseline = RunBaseline.model_validate(payload)
    except ValidationError as exc:
        raise BaselineError(f"invalid baseline {path}: {exc}") from exc
    try:
        # Re-run Plan A's seal over the embedded snapshot: model_validate accepts the
        # envelope's shape but not its integrity, and a hand-edited baseline would
        # otherwise be compared against as if it were the real before-state.
        load_snapshot(json.loads(baseline.snapshot.model_dump_json()))
    except (SnapshotIntegrityError, ValidationError, json.JSONDecodeError) as exc:
        raise BaselineError(f"baseline {path} carries an untrustworthy snapshot: {exc}") from exc
    return baseline
```

- [ ] **Step 4: Run to verify pass**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_baseline.py -q
```

Expected: 7 passed.

- [ ] **Step 5: Lint and type-check**

```bash
cd science && uv run ruff check src/science_tool/autonomy tests/test_autonomy_baseline.py && uv run pyright
```

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/autonomy/baseline.py science/tests/test_autonomy_baseline.py
git commit -m "feat(autonomy): add the supervisor run baseline"
```

---

### Task 2: Toolkit identity and gate externality

**Files:**
- Create: `science/src/science_tool/autonomy/toolkit.py`
- Test: `science/tests/test_autonomy_toolkit.py`

**Interfaces:**
- Produces:
  - `class ToolkitError(ValueError)`
  - `toolkit_source_root() -> Path` — the directory holding the running `science_tool`.
  - `toolkit_revision() -> str` — `git rev-parse HEAD` of that tree.
  - `assert_gate_is_external(project_root: Path) -> None`
  - `assert_toolkit_matches(recorded_revision: str) -> None`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.autonomy.toolkit import (
    ToolkitError,
    assert_gate_is_external,
    assert_toolkit_matches,
    toolkit_revision,
    toolkit_source_root,
)


def test_the_toolkit_source_root_holds_the_running_package():
    assert (toolkit_source_root() / "science_tool" / "__init__.py").exists()


def test_the_revision_is_a_full_sha():
    revision = toolkit_revision()
    assert len(revision) == 40
    assert all(c in "0123456789abcdef" for c in revision)


def test_a_project_that_does_not_contain_the_toolkit_passes(tmp_path: Path):
    assert_gate_is_external(tmp_path)  # does not raise


def test_a_project_containing_the_running_toolkit_is_refused():
    """Design §0 / test #7: a run that edits toolkit code must not be able to alter the
    code that judges it. If the executing science lives inside the run's tree, it can."""
    inside = toolkit_source_root().parent
    with pytest.raises(ToolkitError):
        assert_gate_is_external(inside)


def test_a_mismatched_revision_is_refused():
    with pytest.raises(ToolkitError):
        assert_toolkit_matches("0" * 40)


def test_the_recorded_revision_matches_itself():
    assert_toolkit_matches(toolkit_revision())  # does not raise
```

- [ ] **Step 2: Run to verify failure**

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
"""Which Science is rendering the verdict, and whether the run could have changed it.

Design §0: the authoritative gate executes from a supervisor-owned, pinned Science
installation, treating the run's worktree strictly as input. Both halves matter --
verifying the revision catches a toolkit that moved under the run, and locating the
installation catches a gate executing out of the tree it is judging. Either alone
leaves the other open.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import science_tool


class ToolkitError(ValueError):
    """The judging installation could not be identified, or is not external to the run."""


def toolkit_source_root() -> Path:
    """The directory containing the running `science_tool` package."""
    package_file = science_tool.__file__
    if package_file is None:  # namespace package -- no single source location to pin
        raise ToolkitError("science_tool has no __file__; its source location cannot be pinned")
    return Path(package_file).resolve().parent.parent


def toolkit_revision() -> str:
    """`git rev-parse HEAD` of the tree the running toolkit was loaded from."""
    root = toolkit_source_root()
    result = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise ToolkitError(
            f"could not read the toolkit revision at {root}: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def assert_gate_is_external(project_root: Path) -> None:
    root = project_root.resolve()
    source = toolkit_source_root()
    if source == root or root in source.parents:
        raise ToolkitError(
            f"the running toolkit at {source} is inside the run's project root {root}. A run "
            "that edits toolkit code would be judged by the code it edited; run the gate from "
            "a supervisor-owned installation."
        )


def assert_toolkit_matches(recorded_revision: str) -> None:
    running = toolkit_revision()
    if running != recorded_revision:
        raise ToolkitError(
            f"toolkit revision moved during the run: baseline recorded {recorded_revision}, "
            f"the judging installation is at {running}"
        )
```

- [ ] **Step 4: Run to verify pass** — 6 passed.

- [ ] **Step 5: Lint and type-check**

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(autonomy): identify and externality-check the judging toolkit"
```

---

### Task 3: The run-record writer

**Files:**
- Create: `science/src/science_tool/autonomy/record_writer.py`
- Test: `science/tests/test_autonomy_record_writer.py`

**Interfaces:**
- Produces:
  - `class RecordWriteError(ValueError)`
  - `record_path(project_root: Path, record: AutonomousRunRecord) -> Path`
  - `write_run_record(project_root: Path, record: AutonomousRunRecord) -> Path`
  - `generate_run_id(started: date, agent: str, short_id: str) -> str`

**The writer's contract is the reader.** `load_run_records` must accept everything this
emits — whole-line `---` delimiters, no duplicate keys, `slug == path.stem`. The
round-trip test is the real specification; write it first.

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from science_model.autonomous_runs import (
    AutonomousRunRecord,
    PolicyIdentity,
    RunBudget,
    RunDisposition,
    RunTier,
)

from science_tool.autonomy.record_writer import (
    RecordWriteError,
    generate_run_id,
    record_path,
    write_run_record,
)
from science_tool.graph.autonomous_runs import load_run_records


def _record(**overrides) -> AutonomousRunRecord:
    fields = dict(
        id="run:2026-07-25-curation-sweep-a3f1",
        agent="curation-sweep",
        model="test-model",
        tier=RunTier.BELIEF_NEUTRAL,
        branch="auto/2026-07-25-curation-sweep-a3f1",
        base_commit="a" * 40,
        head_commit="b" * 40,
        toolkit_revision="c" * 40,
        policy_identity=PolicyIdentity(id="core-default", version="1"),
        basis_digest="d" * 64,
        started=datetime(2026, 7, 25, 9, 0, tzinfo=UTC),
        ended=datetime(2026, 7, 25, 9, 30, tzinfo=UTC),
        budget=RunBudget(tokens=1000, wall_clock_seconds=1800.0),
        disposition=RunDisposition.CLEAN,
    )
    fields.update(overrides)
    return AutonomousRunRecord(**fields)


def test_a_written_record_reloads_identically(tmp_path: Path):
    """The reader is the writer's specification."""
    record = _record()
    write_run_record(tmp_path, record)

    loaded = load_run_records(tmp_path)
    assert loaded == [record]


def test_an_unwired_record_omits_the_digest_and_reloads(tmp_path: Path):
    record = _record(disposition=RunDisposition.UNWIRED, basis_digest=None)
    path = write_run_record(tmp_path, record)

    assert "basis_digest" not in path.read_text(encoding="utf-8")
    assert load_run_records(tmp_path) == [record]


def test_a_quarantined_record_reloads(tmp_path: Path):
    record = _record(disposition=RunDisposition.QUARANTINED)
    write_run_record(tmp_path, record)
    assert load_run_records(tmp_path) == [record]


def test_the_filename_stem_is_the_slug(tmp_path: Path):
    record = _record()
    path = write_run_record(tmp_path, record)
    assert path.stem == record.slug
    assert path.parent == tmp_path / "runs"


def test_an_existing_record_is_never_overwritten(tmp_path: Path):
    """An attestation is written once. Silently replacing one would let a second finish
    rewrite the verdict on a run that already has it."""
    write_run_record(tmp_path, _record())
    with pytest.raises(RecordWriteError):
        write_run_record(tmp_path, _record(disposition=RunDisposition.QUARANTINED))


def test_an_omitted_triggered_by_is_absent_not_blank(tmp_path: Path):
    """Design §2: omitted, not blank, when absent."""
    path = write_run_record(tmp_path, _record())
    assert "triggered_by" not in path.read_text(encoding="utf-8")


def test_generated_ids_carry_the_run_prefix_and_parse():
    run_id = generate_run_id(date(2026, 7, 25), "curation-sweep", "a3f1")
    assert run_id == "run:2026-07-25-curation-sweep-a3f1"
    assert _record(id=run_id).slug == "2026-07-25-curation-sweep-a3f1"


def test_record_path_does_not_write(tmp_path: Path):
    assert not record_path(tmp_path, _record()).exists()
```

- [ ] **Step 2: Run to verify failure** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
"""Write the finalized attestation to `runs/<slug>.md`.

`load_run_records` is this module's specification, not a downstream consumer: it
enforces whole-line delimiters, no duplicate or merge keys, flat `*.md` children, and
`slug == path.stem`. Anything this writer emits that the reader rejects is a defect
here.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from science_model.autonomous_runs import RUN_ID_PREFIX, AutonomousRunRecord

from science_tool.graph.autonomous_runs import RUNS_DIRNAME


class RecordWriteError(ValueError):
    """The run record could not be written."""


def generate_run_id(started: date, agent: str, short_id: str) -> str:
    return f"{RUN_ID_PREFIX}{started.isoformat()}-{agent}-{short_id}"


def record_path(project_root: Path, record: AutonomousRunRecord) -> Path:
    return project_root / RUNS_DIRNAME / f"{record.slug}.md"


def write_run_record(project_root: Path, record: AutonomousRunRecord) -> Path:
    """Serialize `record` and return the path written.

    `exclude_none` drops `basis_digest` when the disposition is `unwired` and
    `triggered_by` when it is absent -- design §2 says omitted, not blank. Every other
    field is required by the model, so none can be dropped by accident.
    """
    path = record_path(project_root, record)
    if path.exists():
        raise RecordWriteError(
            f"{path} already exists; a run record is written once and never rewritten"
        )

    payload = record.model_dump(mode="json", exclude_none=True)
    # sort_keys=False keeps the model's declaration order, which reads as the design's
    # table. default_flow_style=False keeps nested blocks (policy_identity, budget)
    # expanded, so a human reviewing an attestation sees one field per line.
    block = yaml.safe_dump(payload, sort_keys=False, default_flow_style=False, allow_unicode=True)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\n{block}---\n", encoding="utf-8")
    except OSError as exc:
        raise RecordWriteError(f"could not write run record to {path}: {exc}") from exc
    return path
```

- [ ] **Step 4: Run to verify pass** — 8 passed.

If `test_a_written_record_reloads_identically` fails on a datetime or enum mismatch,
the fix is in this writer's serialization, **not** in `load_run_records` or the model.

- [ ] **Step 5: Lint and type-check**

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(autonomy): write finalized run records to runs/"
```

---

### Task 4: Commit-mark verification

**Files:**
- Create: `science/src/science_tool/autonomy/marks.py`
- Test: `science/tests/test_autonomy_marks.py`

**Interfaces:**
- Consumes: `_git` from `science_tool.autonomy.extract` (import it; do not write a
  second git helper — Plan C's already passes `--no-replace-objects`).
- Produces:
  - `TRAILER_KEY = "Science-Run"`
  - `class MarkIssue(BaseModel)` — `commit: str`, `reason: str`
  - `verify_marks(repo_root: Path, base: str, head: str, *, run_id: str, agent: str) -> tuple[MarkIssue, ...]`

**These marks are not the security boundary** (design §3). A process that writes commits
can set any author and any trailer. They are verified because a *mismatch* is
informative — it means commits outside the run's own accounting landed in its range —
and a match proves nothing.

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.autonomy.marks import verify_marks

RUN_ID = "run:2026-07-25-curation-sweep-a3f1"
AGENT = "curation-sweep"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _commit(root: Path, message: str, *, author: str | None = None) -> str:
    (root / "f.txt").write_text(message, encoding="utf-8")
    _git(root, "add", "-A")
    args = ["commit", "-q", "-m", message]
    if author is not None:
        args += ["--author", author]
    _git(root, *args)
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _commit(tmp_path, "base")
    return tmp_path


def _good_message(n: int) -> str:
    return f"docs: change {n}\n\nScience-Run: {RUN_ID}"


def test_a_well_marked_range_has_no_issues(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, _good_message(1), author=f"{AGENT} <agent@science.local>")
    assert verify_marks(repo, base, head, run_id=RUN_ID, agent=AGENT) == ()


def test_a_commit_with_no_trailer_is_flagged(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, "docs: untagged", author=f"{AGENT} <agent@science.local>")
    issues = verify_marks(repo, base, head, run_id=RUN_ID, agent=AGENT)
    assert len(issues) == 1
    assert "trailer" in issues[0].reason


def test_a_commit_naming_another_run_is_flagged(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(
        repo, "docs: x\n\nScience-Run: run:2026-01-01-other-0000",
        author=f"{AGENT} <agent@science.local>",
    )
    issues = verify_marks(repo, base, head, run_id=RUN_ID, agent=AGENT)
    assert "another run" in issues[0].reason


def test_a_foreign_author_is_flagged(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, _good_message(1), author="Someone Else <a@b.c>")
    issues = verify_marks(repo, base, head, run_id=RUN_ID, agent=AGENT)
    assert "author" in issues[0].reason


def test_every_commit_in_the_range_is_checked(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, _good_message(1), author=f"{AGENT} <agent@science.local>")
    _commit(repo, "docs: untagged", author=f"{AGENT} <agent@science.local>")
    head = _commit(repo, _good_message(3), author=f"{AGENT} <agent@science.local>")

    issues = verify_marks(repo, base, head, run_id=RUN_ID, agent=AGENT)
    assert len(issues) == 1


def test_an_empty_range_has_no_issues(repo: Path):
    head = _git(repo, "rev-parse", "HEAD")
    assert verify_marks(repo, head, head, run_id=RUN_ID, agent=AGENT) == ()
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

```python
"""Verify the human-legibility marks on a run's commits (design §3).

NOT a security boundary: a process that writes commits can set any author and any
trailer. The authoritative binding is the supervisor-recorded base..head range. A
mismatch is still worth quarantining on, because it means commits the run did not
account for landed inside its own range.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from science_tool.autonomy.extract import _git

TRAILER_KEY = "Science-Run"
_SEP = "\x1e"  # record separator -- cannot occur in an author name or a trailer value


class MarkIssue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    commit: str
    reason: str


def verify_marks(
    repo_root: Path, base: str, head: str, *, run_id: str, agent: str
) -> tuple[MarkIssue, ...]:
    raw = _git(
        repo_root,
        "log",
        f"--format=%H{_SEP}%an{_SEP}%(trailers:key={TRAILER_KEY},valueonly){_SEP}",
        f"{base}..{head}",
    ).decode("utf-8", "replace")

    issues: list[MarkIssue] = []
    for entry in raw.split(f"{_SEP}\n"):
        if not entry.strip():
            continue
        commit, author, trailers = entry.split(_SEP, 2)
        values = [line.strip() for line in trailers.splitlines() if line.strip()]
        if not values:
            issues.append(MarkIssue(commit=commit, reason=f"no {TRAILER_KEY} trailer"))
        elif any(value != run_id for value in values):
            issues.append(
                MarkIssue(commit=commit, reason=f"{TRAILER_KEY} names another run: {values}")
            )
        if author != agent:
            issues.append(
                MarkIssue(commit=commit, reason=f"author {author!r} is not the run's agent {agent!r}")
            )
    return tuple(issues)
```

- [ ] **Step 4: Run to verify pass** — 6 passed.

- [ ] **Step 5: Lint and type-check**

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(autonomy): verify commit marks over a run's recorded range"
```

---

### Task 5: The lifecycle — `start_run` and `finish_run`

**Files:**
- Create: `science/src/science_tool/autonomy/lifecycle.py`
- Test: `science/tests/test_autonomy_lifecycle.py`

**Interfaces:**
- Consumes: everything from Tasks 1–4, plus `capture_basis`, `build_snapshot`,
  `compare_bases`, `basis_digest` (Plan A); `extract_change_set`, `evaluate` (Plan C);
  `materialize_graph`; `load_trig_dataset_preserving_literals`; `graph_uri`.
- Produces:
  - `class RunOutcome(BaseModel)` — `disposition: RunDisposition`,
    `record: AutonomousRunRecord | None`, `reason: str`,
    `deltas: tuple[BasisDelta, ...]`, `denials: tuple[Denial, ...]`,
    `mark_issues: tuple[MarkIssue, ...]`.
  - `start_run(project_root, *, agent, model, tier, short_id, started, baseline_out) -> RunBaseline`
  - `finish_run(project_root, *, baseline_path, head, ended, tokens, wall_clock_seconds, report_path=None) -> RunOutcome`

**Order inside `finish_run` is load-bearing. Implement it exactly:**

1. `read_baseline` — an untrustworthy baseline is `unwired` before anything else runs.
2. `assert_gate_is_external(project_root)` and `assert_toolkit_matches(baseline.toolkit_revision)`.
3. `materialize_graph(project_root)` — **before** capturing. `graph.trig` is derived and
   actor-controlled; skipping this is Plan A's deferred fail-open.
4. `capture_basis` → `unwired` if the result is unwired.
5. `compare_bases(baseline.snapshot.rows, after_rows)` → any delta quarantines.
6. `extract_change_set` + `evaluate` → any denial quarantines.
7. `verify_marks` → any issue quarantines.
8. Build the record. `basis_digest` is **`baseline.snapshot.digest`** — the digest of
   the basis at `base_commit`, per design §2 ("Digest of the belief basis at
   `base_commit`"). **Not** the after-digest: the field exists so a later validation can
   prove what starting state the run was judged against, which the after-state cannot
   establish. It is set only when the disposition is not `unwired`; when unwired it must
   be `None` or the model raises.
9. `write_run_record`.

**Two distinct unwired cases, and only one of them can produce a record.** If the
baseline is missing or untrustworthy, the run's identity — `run_id`, `agent`, `branch`,
`base_commit` — is unknown, so no record can be written and `RunOutcome.record` is
`None`. If the baseline loads but the verdict is uncomputable (materialization failed,
capture returned unwired, the toolkit moved), the identity *is* known: write a record
with `disposition: unwired` and no `basis_digest`. An unwired attestation that says "we
could not tell" is worth more than silence, and design §6 blocks on it either way.

- [ ] **Step 1: Write the failing tests**

Build on the Plan C perturbation fixture shape — a project with a proposition, a paper,
and a belief-eligible evidence line, so the basis is non-empty. Reuse
`science/tests/test_autonomy_perturbation_alarm.py`'s `_seed_project` approach; a basis
of zero units makes every assertion below vacuous.

```python
from __future__ import annotations

import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from science_model.autonomous_runs import RunDisposition, RunTier

from science_tool.autonomy.lifecycle import finish_run, start_run

AGENT = "curation-sweep"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _commit_as_agent(root: Path, message: str, run_id: str) -> str:
    _git(root, "add", "-A")
    _git(
        root, "commit", "-q",
        "-m", f"{message}\n\nScience-Run: {run_id}",
        "--author", f"{AGENT} <agent@science.local>",
    )
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A git project with a real, non-empty belief basis."""
    root = tmp_path / "project"
    root.mkdir()
    _seed_science_project(root)  # see Step 3 note
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


@pytest.fixture
def baseline_path(tmp_path: Path) -> Path:
    return tmp_path / "supervisor-state" / "run.json"


def _start(project: Path, baseline_path: Path):
    return start_run(
        project, agent=AGENT, model="test-model", tier=RunTier.BELIEF_NEUTRAL,
        short_id="a3f1", started=datetime(2026, 7, 25, 9, 0, tzinfo=UTC),
        baseline_out=baseline_path,
    )


def _finish(project: Path, baseline_path: Path):
    return finish_run(
        project, baseline_path=baseline_path, head=_git(project, "rev-parse", "HEAD"),
        ended=datetime(2026, 7, 25, 9, 30, tzinfo=UTC), tokens=100, wall_clock_seconds=1800.0,
    )


def test_start_writes_no_run_record(project: Path, baseline_path: Path):
    """A supervisor that dies mid-run must leave no attestation."""
    _start(project, baseline_path)
    assert not (project / "runs").exists()
    assert baseline_path.exists()


def test_an_allowlisted_edit_finishes_clean(project: Path, baseline_path: Path):
    baseline = _start(project, baseline_path)
    paper = project / "entities" / "papers" / "x.md"
    paper.write_text(paper.read_text(encoding="utf-8").replace("venue: Nature", "venue: Science"), encoding="utf-8")
    _commit_as_agent(project, "docs: refresh venue", baseline.run_id)

    outcome = _finish(project, baseline_path)
    assert outcome.disposition is RunDisposition.CLEAN, outcome.reason
    assert (project / "runs" / f"{baseline.run_id.removeprefix('run:')}.md").exists()


def test_a_denied_field_quarantines(project: Path, baseline_path: Path):
    baseline = _start(project, baseline_path)
    paper = project / "entities" / "papers" / "x.md"
    paper.write_text(paper.read_text(encoding="utf-8").replace("venue: Nature", "venue: Nature\nmethods_summary: rewritten"), encoding="utf-8")
    _commit_as_agent(project, "docs: rewrite methods", baseline.run_id)

    outcome = _finish(project, baseline_path)
    assert outcome.disposition is RunDisposition.QUARANTINED
    assert outcome.denials


def test_a_belief_basis_move_quarantines(project: Path, baseline_path: Path):
    """The authoritative layer: this must fire even though the path gate would too."""
    baseline = _start(project, baseline_path)
    line = project / "entities" / "evidence-lines" / "e1.md"
    line.write_text(line.read_text(encoding="utf-8").replace("strength: strong", "strength: weak"), encoding="utf-8")
    _commit_as_agent(project, "chore: weaken evidence", baseline.run_id)

    outcome = _finish(project, baseline_path)
    assert outcome.disposition is RunDisposition.QUARANTINED
    assert outcome.deltas


def test_an_unrebuilt_graph_still_sees_the_change(project: Path, baseline_path: Path):
    """Plan A's deferred fail-open: `finish` re-materializes, so an actor that edits
    entities and never runs `graph build` is still caught."""
    baseline = _start(project, baseline_path)
    line = project / "entities" / "evidence-lines" / "e1.md"
    line.write_text(line.read_text(encoding="utf-8").replace("strength: strong", "strength: weak"), encoding="utf-8")
    # deliberately no graph build
    _commit_as_agent(project, "chore: weaken evidence", baseline.run_id)

    outcome = _finish(project, baseline_path)
    assert outcome.disposition is RunDisposition.QUARANTINED
    assert outcome.deltas


def test_an_unmarked_commit_quarantines(project: Path, baseline_path: Path):
    _start(project, baseline_path)
    paper = project / "entities" / "papers" / "x.md"
    paper.write_text(paper.read_text(encoding="utf-8").replace("venue: Nature", "venue: Science"), encoding="utf-8")
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "docs: no trailer")

    outcome = _finish(project, baseline_path)
    assert outcome.disposition is RunDisposition.QUARANTINED
    assert outcome.mark_issues


def test_a_missing_baseline_is_unwired_not_clean(project: Path, tmp_path: Path):
    outcome = finish_run(
        project, baseline_path=tmp_path / "absent.json",
        head=_git(project, "rev-parse", "HEAD"),
        ended=datetime(2026, 7, 25, 9, 30, tzinfo=UTC), tokens=0, wall_clock_seconds=1.0,
    )
    assert outcome.disposition is RunDisposition.UNWIRED


def test_an_unreadable_baseline_produces_no_record_at_all(project: Path, tmp_path: Path):
    """The run's identity lives in the baseline. Without it there is nothing to attest
    to -- and an invented record would be the fabrication this slice exists to prevent."""
    outcome = finish_run(
        project, baseline_path=tmp_path / "absent.json",
        head=_git(project, "rev-parse", "HEAD"),
        ended=datetime(2026, 7, 25, 9, 30, tzinfo=UTC), tokens=0, wall_clock_seconds=1.0,
    )
    assert outcome.disposition is RunDisposition.UNWIRED
    assert outcome.record is None
    assert not (project / "runs").exists()


def test_a_toolkit_mismatch_writes_an_unwired_record_with_no_digest(project: Path, baseline_path: Path):
    """The other unwired case: identity IS known, so an attestation saying 'we could not
    tell' is written -- with no basis_digest, which the model enforces."""
    import json

    _start(project, baseline_path)
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    payload["toolkit_revision"] = "0" * 40
    baseline_path.write_text(json.dumps(payload), encoding="utf-8")

    outcome = _finish(project, baseline_path)
    assert outcome.disposition is RunDisposition.UNWIRED
    assert outcome.record is not None
    assert outcome.record.basis_digest is None


def test_a_clean_record_carries_the_BEFORE_digest(project: Path, baseline_path: Path):
    """Design §2: the digest is of the basis at base_commit, so a later validation can
    prove which starting state the run was judged against."""
    baseline = _start(project, baseline_path)
    paper = project / "entities" / "papers" / "x.md"
    paper.write_text(paper.read_text(encoding="utf-8").replace("venue: Nature", "venue: Science"), encoding="utf-8")
    _commit_as_agent(project, "docs: refresh venue", baseline.run_id)

    outcome = _finish(project, baseline_path)
    assert outcome.record is not None
    assert outcome.record.basis_digest == baseline.snapshot.digest


def test_a_quarantined_run_keeps_its_work(project: Path, baseline_path: Path):
    """Design §6: nothing is discarded. The branch and its commits stay intact."""
    baseline = _start(project, baseline_path)
    paper = project / "entities" / "papers" / "x.md"
    paper.write_text(paper.read_text(encoding="utf-8").replace("venue: Nature", "venue: Nature\nmethods_summary: rewritten"), encoding="utf-8")
    head = _commit_as_agent(project, "docs: rewrite", baseline.run_id)

    _finish(project, baseline_path)
    assert _git(project, "rev-parse", "HEAD") == head
    assert "methods_summary" in paper.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

Write `_seed_science_project` in the test module by copying the fixture shape from
`science/tests/test_autonomy_perturbation_alarm.py` (`_seed_project`), which is known to
produce a non-empty basis. Add `test_the_fixture_has_a_non_empty_basis` there too — the
same vacuity trap applies, and every assertion above depends on it.

Implement `lifecycle.py` following the nine-step order above. Keep click out of it: this
module is the whole verdict, and Task 6 is a thin CLI over it.

`start_run` must: assert the gate is external, materialize, capture the basis, seal it
with `build_snapshot`, resolve `base_commit` via `_git(... "rev-parse", "HEAD")`, read
`toolkit_revision()`, generate the run id and `auto/<slug>` branch name, and write the
baseline. It must **not** create the branch, check anything out, or write a record.

`finish_run` returns `RunOutcome` and never raises for an expected condition — every
`BaselineError`, `ToolkitError`, `ExtractError`, `GateInputError`, and unwired capture
becomes `disposition=UNWIRED` with the message in `reason`.

- [ ] **Step 4: Run to verify pass** — 10 passed plus the fixture certification.

- [ ] **Step 5: Lint and type-check**

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(autonomy): add the run lifecycle and verdict"
```

---

### Task 6: `science autonomy start` and `finish`

**Files:**
- Modify: `science/src/science_tool/autonomy/cli.py`
- Modify: `science/src/science_tool/budget/registry.py`
- Modify: `science/tests/test_budget_boundary.py` (cardinality lock and docstring)
- Modify: `docs/user-guide/cli-and-workflows.md` (the `autonomy` row already exists —
  extend its `Use` cell; the guard test needs no new row)
- Test: `science/tests/test_autonomy_lifecycle_cli.py`

Exit codes: `0` clean, `1` quarantined, `2` unwired. On quarantine, `finish` files a
`science feedback` item naming the entity and the delta (design §6), using
`next_feedback_id` + `save_entry` against the directory `feedback_cli.py:27` resolves —
**never** a path inside the project.

**Before editing the cardinality lock, read its current value.** Plan C left it at
`4/67/208 = 279`; this task adds two deferred leaves.

- [ ] **Step 1: Write the failing tests** — cover: `start` exits 0 and writes no record;
  `finish` exits 0 on a clean run, 1 on quarantine, 2 on a missing baseline; a
  quarantine files exactly one feedback entry whose summary names the run id; both
  commands refuse a `--baseline-out` / `--baseline` inside the project root; both are
  registered under the `autonomy` group.

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement the two commands** as thin wrappers over Task 5.

- [ ] **Step 4: Add both `DeferredCommand` entries** (`autonomy start` — fixed record;
  `autonomy finish` — one row per denial and delta).

- [ ] **Step 5: Update `EXPECTED_CLASSIFICATION_COUNTS` and the docstring sentence.**

- [ ] **Step 6: Run** `tests/test_autonomy_lifecycle_cli.py tests/test_budget_boundary.py tests/test_user_guide_docs.py`

- [ ] **Step 7: Lint, type-check, commit**

```bash
git commit -m "feat(autonomy): add science autonomy start and finish"
```

---

### Task 7: The `validate` check

**Files:**
- Create: `science/src/science_tool/validate/checks/autonomous_runs.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py` (add to
  `CANONICAL_CHECK_MODULES`)
- Test: `science/tests/test_autonomy_validate_check.py`

**Integrity and coverage, not recomputation.** The check must not rebuild the graph or
check out commits — `validate` runs constantly and its cost must not grow with run
history. It reports:

| Condition | Severity |
|---|---|
| A commit in the project's history carries a `Science-Run:` trailer with no matching record | error — "unwired: unattested autonomous commits" |
| A record names a `base_commit` or `head_commit` that is unreachable | error |
| A record's `disposition` is `unwired` but a `basis_digest` is present, or vice versa | error |
| A record's `branch` does not match `auto/<slug>` | warning |
| No `runs/` directory | no results — most projects never run unattended |

- [ ] **Step 1: Write the failing tests** — one per row above, plus a clean project
  yielding no results, plus a project with no `runs/` yielding no results.

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement** with `@Check(section="autonomous runs...", order=0)`,
  yielding `Result(Severity.ERROR, path, None, message, "autonomous-runs", None)`.
  Reuse `load_run_records`; let `RunRecordError` surface as an error result rather than
  crashing `validate`.

- [ ] **Step 4: Run** — including `tests/test_check_registry_is_complete.py`, which may
  require registering the new check module.

- [ ] **Step 5: Lint, type-check, commit**

```bash
git commit -m "feat(validate): check autonomous run record integrity and coverage"
```

---

### Task 8: Documentation

**Files:**
- Modify: `docs/user-guide/agent-workflows.md`
- Modify: `docs/plans/2026-07-24-autonomy-envelope-design.md`

- [ ] **Step 1: Extend the autonomy section of the user guide** with the two-command
  lifecycle, the three dispositions and their exit codes, the rule that a quarantined
  run keeps its branch and files feedback, and the requirement that the baseline live
  outside the repository.

- [ ] **Step 2: Append a Plan D revision note to §6** recording: the record is written
  only at finish (no in-flight shape); the baseline lives outside the repository because
  `runs/` accepts only flat `*.md` records *and* because the actor writes the worktree;
  `finish` re-materializes before capturing, closing Plan A's gap; gate externality is
  enforced by both revision match and source location; and `validate` checks integrity
  and coverage rather than recomputing bases.

- [ ] **Step 3: Mark S1 complete** in the design doc's status line, noting that Plans
  A–D all shipped and what remains open (`autonomous_run` is stamped by the supervisor
  but still not cross-checked per-entity against the range — say so plainly if Task 5
  did not close it).

- [ ] **Step 4: Run the docs guards, then commit**

```bash
cd science && uv run --frozen pytest tests/test_user_guide_docs.py tests/test_command_docs.py -q
git commit -m "docs(autonomy): document the run lifecycle and record Plan D rulings"
```

---

## Final verification

From the repository root. Each line is a **subshell** — a bare `cd science` followed by
`cd science/model` resolves to `science/science/model` and fails.

```bash
(cd science && uv run --frozen pytest)          # timeout: 600000
(cd science/model && uv run --frozen pytest)    # timeout: 600000
(cd science && uv run ruff check && uv run pyright)
(cd science/model && uv run ruff check)
```

## Design-test coverage

| Design test | Where |
|---|---|
| 1 — basis change with unchanged magnitude quarantines | Task 5 `test_a_belief_basis_move_quarantines` (Plan A's `compare_bases` is over units, never magnitude) |
| 2 — fail-closed on unwired | Task 5 `test_a_missing_baseline_is_unwired_not_clean`, `test_an_unwired_record_carries_no_digest` |
| 3 — scalar-independence | Inherited from Plan A: the basis is computed without consulting `belief_scalar_enabled()`. Add no scalar comparison in this plan. |
| 6 — self-attestation is impossible | Task 3 `test_an_existing_record_is_never_overwritten`; Task 5 `test_an_unmarked_commit_quarantines`; §4 already denies `runs/` to the actor |
| 7 — gate independence from the worktree | Task 2 `test_a_project_containing_the_running_toolkit_is_refused`, `test_a_mismatched_revision_is_refused` |
| 8 — baseline reproducibility | Task 1 round-trip + seal tests; the recorded `base_commit` is never a merge-base |
| 11 — interactive commits unaffected | Nothing in this plan writes commits in a consumer project; `marks.py` only reads |

Tests 4, 5, 9, and 10 were discharged by Plans B and C.
