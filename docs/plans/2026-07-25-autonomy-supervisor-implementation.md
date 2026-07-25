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
  `BUDGETS | EXEMPTIONS | DEFERRED` entry and locks the partition cardinality, which at
  the time of writing is `budgeted 10 / exempt 67 / deferred 202 = 279` (`:24`). It has
  already moved once since Plan C, so **re-read the constant before editing**. This plan
  adds two deferred leaves — `autonomy start` and `autonomy finish` — so the deferred
  count rises by 2. Update `EXPECTED_CLASSIFICATION_COUNTS` and the explanatory docstring
  in the same edit.
- **Validate checks may shell out to git.** `validate/checks/prereg_vehicles.py:49` runs
  `subprocess.run(["git", ...])` inside a check. The "must not spawn subprocesses"
  comment in `tooling.py:28` scopes to that check, not to the framework.
- **A check module on disk but absent from `CANONICAL_CHECK_MODULES` never runs**, and
  `test_check_registry_is_complete.py` derives its scope from the filesystem to catch
  exactly that. Registration is a separate act from writing the module.

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
- Modify: `science/src/science_tool/autonomy/lifecycle.py` (add `file_quarantine_feedback`)
- Modify: `science/src/science_tool/budget/registry.py`
- Modify: `science/tests/test_budget_boundary.py`
- Modify: `docs/user-guide/cli-and-workflows.md`
- Test: `science/tests/test_autonomy_lifecycle_cli.py`

**Interfaces:**
- Consumes: `start_run`, `finish_run`, `RunOutcome` (Task 5).
- Produces:
  - `start_command` / `finish_command` on the existing `autonomy_group`.
  - `file_quarantine_feedback(outcome: RunOutcome, *, feedback_dir: Path, project: str) -> Path`
    in `lifecycle.py`.

**Match the shipped `path-gate` output contract exactly.** It uses
`science_tool.output.emit(output_format=..., payload=..., render_text=...)` with both a
`--format` choice over `OUTPUT_FORMATS` and a `--json` flag kept as a convenience alias
(`effective_format = "json" if as_json else output_format`). Do not invent a third
output style; read `autonomy/cli.py` before writing.

**The cardinality lock has moved.** It is now `budgeted 10 / exempt 67 / deferred 202 =
279` (`tests/test_budget_boundary.py:24`) — the context-budget work changed it after
Plan C. This task adds **two** deferred leaves, so it becomes `10/67/204 = 281`.
Re-read the constant before editing rather than trusting this paragraph.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_autonomy_lifecycle_cli.py`:

```python
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main

AGENT = "curation-sweep"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Reuses Task 5's seeded project; a basis of zero units makes every case vacuous."""
    from tests.test_autonomy_lifecycle import _seed_science_project

    root = tmp_path / "project"
    root.mkdir()
    _seed_science_project(root)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


@pytest.fixture
def baseline_path(tmp_path: Path) -> Path:
    return tmp_path / "supervisor-state" / "run.json"


@pytest.fixture
def feedback_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`feedback_cli._get_feedback_dir` reads SCIENCE_FEEDBACK_DIR before falling back to
    the user's config dir. Redirect it so a test never writes to the real one."""
    target = tmp_path / "feedback"
    monkeypatch.setenv("SCIENCE_FEEDBACK_DIR", str(target))
    return target


def _start(project: Path, baseline_path: Path, *extra: str):
    return CliRunner().invoke(
        main,
        [
            "autonomy", "start", "--project-root", str(project),
            "--agent", AGENT, "--model", "test-model",
            "--short-id", "a3f1", "--baseline-out", str(baseline_path), *extra,
        ],
    )


def _finish(project: Path, baseline_path: Path, *extra: str):
    return CliRunner().invoke(
        main,
        [
            "autonomy", "finish", "--project-root", str(project),
            "--baseline", str(baseline_path), "--head", _git(project, "rev-parse", "HEAD"),
            "--tokens", "100", "--wall-clock-seconds", "1800", *extra,
        ],
    )


def _edit_and_commit(project: Path, old: str, new: str, run_id: str, *, marked: bool = True) -> None:
    paper = project / "entities" / "papers" / "x.md"
    paper.write_text(paper.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    _git(project, "add", "-A")
    message = f"docs: edit\n\nScience-Run: {run_id}" if marked else "docs: edit"
    _git(project, "commit", "-q", "-m", message, "--author", f"{AGENT} <agent@science.local>")


def _run_id(baseline_path: Path) -> str:
    return json.loads(baseline_path.read_text(encoding="utf-8"))["run_id"]


def test_start_exits_zero_and_writes_a_baseline_but_no_record(project: Path, baseline_path: Path):
    result = _start(project, baseline_path)
    assert result.exit_code == 0, result.output
    assert baseline_path.exists()
    assert not (project / "runs").exists()


def test_start_json_names_the_run_and_the_baseline(project: Path, baseline_path: Path):
    result = _start(project, baseline_path, "--json")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["run_id"].startswith("run:")
    assert payload["baseline_path"] == str(baseline_path)
    assert payload["branch"] == f"auto/{payload['run_id'].removeprefix('run:')}"
    assert "snapshot" not in payload, "the payload is a summary, not the whole capture"


def test_start_refuses_a_baseline_inside_the_project(project: Path):
    result = _start(project, project / "runs" / "b.json")
    assert result.exit_code == 2
    assert "inside the project root" in result.output


def test_finish_exits_zero_on_a_clean_run(project: Path, baseline_path: Path, feedback_dir: Path):
    _start(project, baseline_path)
    _edit_and_commit(project, "venue: Nature", "venue: Science", _run_id(baseline_path))

    result = _finish(project, baseline_path)
    assert result.exit_code == 0, result.output
    assert "clean" in result.output
    assert not feedback_dir.exists(), "a clean run files no feedback"


def test_finish_exits_one_on_quarantine_and_names_the_cause(project: Path, baseline_path: Path, feedback_dir: Path):
    _start(project, baseline_path)
    _edit_and_commit(
        project, "venue: Nature", "venue: Nature\nmethods_summary: rewritten", _run_id(baseline_path)
    )

    result = _finish(project, baseline_path)
    assert result.exit_code == 1, result.output
    assert "quarantined" in result.output
    assert "methods_summary" in result.output


def test_a_quarantine_files_exactly_one_feedback_entry(project: Path, baseline_path: Path, feedback_dir: Path):
    import yaml

    _start(project, baseline_path)
    run_id = _run_id(baseline_path)
    _edit_and_commit(project, "venue: Nature", "venue: Nature\nmethods_summary: rewritten", run_id)

    assert _finish(project, baseline_path).exit_code == 1

    entries = sorted(feedback_dir.glob("fb-*.yaml"))
    assert len(entries) == 1
    entry = yaml.safe_load(entries[0].read_text(encoding="utf-8"))
    assert run_id in entry["summary"]
    assert entry["target"] == "command:autonomy-finish"
    assert entry["status"] == "open"
    assert "methods_summary" in entry["detail"]


def test_finish_exits_two_on_a_missing_baseline(project: Path, tmp_path: Path, feedback_dir: Path):
    result = CliRunner().invoke(
        main,
        [
            "autonomy", "finish", "--project-root", str(project),
            "--baseline", str(tmp_path / "absent.json"),
            "--head", _git(project, "rev-parse", "HEAD"),
            "--tokens", "0", "--wall-clock-seconds", "1",
        ],
    )
    assert result.exit_code == 2
    assert "unwired" in result.output
    assert not feedback_dir.exists(), "unwired blocks; it does not file a quarantine item"


def test_finish_refuses_a_baseline_inside_the_project(project: Path):
    result = CliRunner().invoke(
        main,
        [
            "autonomy", "finish", "--project-root", str(project),
            "--baseline", str(project / "runs" / "b.json"),
            "--head", _git(project, "rev-parse", "HEAD"),
            "--tokens", "0", "--wall-clock-seconds", "1",
        ],
    )
    assert result.exit_code == 2
    assert "inside the project root" in result.output


def test_finish_json_carries_the_disposition_and_the_denials(project: Path, baseline_path: Path, feedback_dir: Path):
    _start(project, baseline_path)
    _edit_and_commit(
        project, "venue: Nature", "venue: Nature\nmethods_summary: rewritten", _run_id(baseline_path)
    )

    result = _finish(project, baseline_path, "--json")
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["disposition"] == "quarantined"
    assert any(d["field"] == "methods_summary" for d in payload["denials"])


def test_both_commands_are_registered_under_the_autonomy_group():
    group = main.commands["autonomy"]
    assert {"start", "finish", "path-gate"} <= set(group.commands)  # type: ignore[attr-defined]
```

- [ ] **Step 2: Run to verify failure**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_lifecycle_cli.py -q
```

Expected: every test fails — `start` and `finish` do not exist.

- [ ] **Step 3: Add `file_quarantine_feedback` to `lifecycle.py`**

```python
def file_quarantine_feedback(outcome: RunOutcome, *, feedback_dir: Path, project: str) -> Path:
    """File one feedback item naming the run, the entity, and the delta (design §6).

    Escalation reuses the existing `science feedback` surface rather than inventing a
    second channel. The directory resolves OUTSIDE the project (`$SCIENCE_FEEDBACK_DIR`
    or the user config dir), so escalating writes nothing into the run's worktree.

    Only a QUARANTINE files an item. `unwired` is a blocked run with no finding to
    triage -- filing one would put "we could not tell" into a queue meant for things
    that went wrong.
    """
    from science_tool.feedback import FeedbackEntry, next_feedback_id, save_entry

    if outcome.disposition is not RunDisposition.QUARANTINED:
        raise ValueError(f"only a quarantined run files feedback, got {outcome.disposition.value!r}")
    assert outcome.record is not None  # a quarantine always has a record

    lines: list[str] = []
    for delta in outcome.deltas:
        lines.append(f"belief basis moved for {delta.entity_id}: {', '.join(delta.changed)} -- {delta.detail}")
    for denial in outcome.denials:
        location = denial.path if denial.field is None else f"{denial.path} field {denial.field!r}"
        lines.append(f"path gate denied {location} -- {denial.reason}")
    for issue in outcome.mark_issues:
        lines.append(f"commit {issue.commit[:12]} -- {issue.reason}")

    created = outcome.record.ended.date().isoformat()
    entry = FeedbackEntry(
        id=next_feedback_id(feedback_dir, created),
        created=created,
        project=project,
        target="command:autonomy-finish",
        category="bug",
        status="open",
        summary=f"autonomous run {outcome.record.id} quarantined",
        detail="\n".join(lines),
        concern="tooling",
    )
    return save_entry(feedback_dir, entry)
```

- [ ] **Step 4: Add both commands to `autonomy/cli.py`**

```python
@autonomy_group.command("start")
@click.option("--agent", required=True, help="Agent ROLE (e.g. curation-sweep), not the model.")
@click.option("--model", required=True, help="Model that will execute the run.")
@click.option(
    "--tier",
    type=click.Choice([tier.value for tier in RunTier]),
    default=RunTier.BELIEF_NEUTRAL.value,
    show_default=True,
    help="Tier the supervisor attests this run to (design §1).",
)
@click.option("--short-id", required=True, help="Short disambiguator for the run id.")
@click.option(
    "--baseline-out",
    type=click.Path(path_type=Path),
    required=True,
    help="Where to write the baseline. MUST be outside the project root.",
)
@click.option(
    "--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True,
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit the summary as JSON.")
@click.option(
    "--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
def start_command(
    agent: str, model: str, tier: str, short_id: str, baseline_out: Path,
    project_root: Path, as_json: bool, output_format: str,
) -> None:
    """Open a run: capture the belief basis and write the supervisor's baseline.

    Writes NO run record. A supervisor that dies mid-run leaves no attestation, so its
    branch reads as unattested rather than clean.

    Exit codes: 0 opened, 2 could not open.
    """
    from datetime import UTC, datetime

    from science_tool.autonomy.baseline import BaselineError
    from science_tool.autonomy.lifecycle import start_run
    from science_tool.autonomy.toolkit import ToolkitError

    effective_format = "json" if as_json else output_format
    try:
        baseline = start_run(
            project_root, agent=agent, model=model, tier=RunTier(tier), short_id=short_id,
            started=datetime.now(UTC), baseline_out=baseline_out,
        )
    except (BaselineError, ToolkitError, Exception) as exc:  # see note below
        message = f"could not start: {exc}"
        emit(
            output_format=effective_format,
            payload={"started": False, "error": message},
            render_text=lambda: click.echo(message),
        )
        sys.exit(2)

    payload = {
        "started": True,
        "run_id": baseline.run_id,
        "branch": baseline.branch,
        "base_commit": baseline.base_commit,
        "toolkit_revision": baseline.toolkit_revision,
        "basis_digest": baseline.snapshot.digest,
        "baseline_path": str(baseline_out),
    }
    emit(
        output_format=effective_format,
        payload=payload,
        render_text=lambda: click.echo(
            f"started {baseline.run_id} (base {baseline.base_commit[:12]}) -> {baseline_out}"
        ),
    )
    sys.exit(0)
```

The broad `except` above is deliberate and must carry this comment: *starting is
all-or-nothing, and a partial start that reports success would leave the supervisor
believing it holds a baseline it does not.* Narrow it to
`(BaselineError, ToolkitError, OSError, RunRecordError)` if the implementation's actual
failure modes are exactly those; do **not** leave a bare `except Exception` without the
justification.

```python
@autonomy_group.command("finish")
@click.option(
    "--baseline", "baseline_path", type=click.Path(path_type=Path), required=True,
    help="Baseline written by `autonomy start`. MUST be outside the project root.",
)
@click.option("--head", required=True, help="Commit the run ended at.")
@click.option("--tokens", type=int, default=None, help="Tokens consumed (S4 consumes this).")
@click.option("--wall-clock-seconds", type=float, default=None, help="Wall-clock seconds consumed.")
@click.option(
    "--report-path", default=None,
    help="Repository-relative path of the run's own report, if it wrote one.",
)
@click.option(
    "--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True,
)
@click.option("--json", "as_json", is_flag=True, default=False)
@click.option(
    "--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True,
)
def finish_command(
    baseline_path: Path, head: str, tokens: int | None, wall_clock_seconds: float | None,
    report_path: str | None, project_root: Path, as_json: bool, output_format: str,
) -> None:
    """Close a run: re-materialize, recapture the basis, gate, and attest.

    Exit codes: 0 clean, 1 quarantined, 2 unwired. Exit 2 is explicitly NOT clean --
    a guard that cannot see must not report clean (design §5).
    """
    from datetime import UTC, datetime

    from science_model.autonomous_runs import RunDisposition

    from science_tool.autonomy.lifecycle import file_quarantine_feedback, finish_run
    from science_tool.feedback_cli import _get_feedback_dir

    effective_format = "json" if as_json else output_format
    outcome = finish_run(
        project_root, baseline_path=baseline_path, head=head, ended=datetime.now(UTC),
        tokens=tokens, wall_clock_seconds=wall_clock_seconds, report_path=report_path,
    )

    feedback_path: Path | None = None
    if outcome.disposition is RunDisposition.QUARANTINED:
        feedback_path = file_quarantine_feedback(
            outcome, feedback_dir=_get_feedback_dir(), project=project_root.resolve().name
        )

    payload = outcome.model_dump(mode="json")
    payload["feedback_path"] = str(feedback_path) if feedback_path is not None else None

    def _render_text() -> None:
        click.echo(f"{outcome.disposition.value}: {outcome.reason}")
        for delta in outcome.deltas:
            click.echo(f"  basis moved: {delta.entity_id} ({', '.join(delta.changed)})")
        for denial in outcome.denials:
            location = denial.path if denial.field is None else f"{denial.path} field {denial.field!r}"
            click.echo(f"  denied: {location} -- {denial.reason}")
        for issue in outcome.mark_issues:
            click.echo(f"  mark: {issue.commit[:12]} -- {issue.reason}")
        if feedback_path is not None:
            click.echo(f"  filed {feedback_path}")

    emit(output_format=effective_format, payload=payload, render_text=_render_text)
    sys.exit({RunDisposition.CLEAN: 0, RunDisposition.QUARANTINED: 1, RunDisposition.UNWIRED: 2}[outcome.disposition])
```

`finish_run` never raises for an expected condition (Task 5), so this command has no
`try`. If it grows one, the handler must exit `2`, never `0`.

- [ ] **Step 5: Classify both commands in the budget registry**

In `science/src/science_tool/budget/registry.py`, beside the existing
`"autonomy path-gate"` entry:

```python
    "autonomy start": DeferredCommand(
        "one fixed summary record per invocation",
        "1b",
    ),
    "autonomy finish": DeferredCommand(
        "one output member per basis delta, gate denial, and commit-mark issue",
        "1b",
    ),
```

- [ ] **Step 6: Update the cardinality lock**

In `science/tests/test_budget_boundary.py`, change `EXPECTED_CLASSIFICATION_COUNTS`
`"deferred"` from its current value to that value **+ 2** (at the time of writing:
`202` → `204`, total `279` → `281`). Append to
`test_classification_partition_has_the_audited_cardinality`'s docstring, before the
final "The live partition is therefore" sentence:

```
    The autonomy start and finish commands add two deferred leaves: start emits one fixed
    summary record, and finish emits one row per basis delta, gate denial, and commit-mark
    issue.
```

Then update that final sentence to the new `budgeted/exempt/deferred = total`.

- [ ] **Step 7: Extend the CLI workflow map**

`docs/user-guide/cli-and-workflows.md` already carries an `autonomy` row from Plan C, so
`test_cli_workflow_map_mentions_every_top_level_command` still passes without edits.
Extend that row's **Use** cell so the family description covers the lifecycle, keeping
the four-column shape:

```markdown
| `autonomy` | Derived-state | Mixed | Open and close unattended runs (`start` / `finish`) and decide whether a run's recorded `base..head` range stayed inside its tier's default-deny write surface (`path-gate`). `finish` writes the attested run record; the baseline it reads lives outside the repository. |
```

The Write class changes from `Read-only` to `Mixed` because `finish` now writes
`runs/<slug>.md`. Both tokens already exist in that table's vocabulary.

- [ ] **Step 8: Run the tests**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_lifecycle_cli.py tests/test_budget_boundary.py tests/test_user_guide_docs.py -q
```

Expected: all pass.

- [ ] **Step 9: Lint and type-check**

```bash
cd science && uv run ruff check src/science_tool tests && uv run pyright
```

- [ ] **Step 10: Commit**

```bash
git add science/src/science_tool/autonomy science/src/science_tool/budget/registry.py \
        science/tests/test_autonomy_lifecycle_cli.py science/tests/test_budget_boundary.py \
        docs/user-guide/cli-and-workflows.md
git commit -m "feat(autonomy): add science autonomy start and finish"
```

---

### Task 7: The `validate` check

**Files:**
- Create: `science/src/science_tool/validate/checks/autonomous_runs.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py`
- Test: `science/tests/test_autonomy_validate_check.py`

**Interfaces:**
- Consumes: `Check`, `ValidateContext`, `Result`, `Severity`; `load_run_records` and
  `RunRecordError`.
- Produces: `check_autonomous_runs(ctx: ValidateContext) -> Iterator[Result]`, rule
  string `"autonomous-runs"`.

**Registration is a separate act from writing the module.**
`test_check_registry_is_complete.py` derives its scope from the *filesystem*, so a module
on disk that is missing from `CANONICAL_CHECK_MODULES` fails that guard. Add
`"autonomous_runs"` to the tuple in the same commit.

**Integrity and coverage, never recomputation.** No graph build, no checkout. Cost is
bounded by the number of *autonomous* commits, not by history length, because the
trailer scan is pushed into git with `--grep`.

**One row of the design table is reached through an exception, not a branch.** A record
whose `disposition` is `unwired` while `basis_digest` is set (or the reverse) fails
`AutonomousRunRecord` validation inside `load_run_records`, which raises
`RunRecordError`. There is no separate consistency branch to write — converting
`RunRecordError` into an error `Result` *is* that row. An implementer who writes an
explicit consistency check will have written code no test can reach.

| Condition | Severity | Reached via |
|---|---|---|
| A commit carries `Science-Run:` naming a run with no record | ERROR | trailer scan |
| A record names an unreachable `base_commit`/`head_commit` | ERROR | `rev-parse --verify` |
| A record is internally inconsistent (unwired with a digest, or the reverse) | ERROR | `RunRecordError` |
| A record's `branch` is not `auto/<slug>` | WARN | record field |
| No `runs/` directory, or not a git repo | — no results | early return |

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_autonomy_validate_check.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.validate.checks.autonomous_runs import check_autonomous_runs
from science_tool.validate.result import Severity

RUN_ID = "run:2026-07-25-curation-sweep-a3f1"
SLUG = "2026-07-25-curation-sweep-a3f1"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _ctx(project_root: Path):
    """Minimal ValidateContext -- this check reads only `project_root`."""
    from science_tool.validate.context import ValidateContext

    return ValidateContext(
        project_root=project_root,
        doc_dir=project_root / "doc",
        specs_dir=project_root / "entities" / "specs",
        papers_dir=project_root / "entities" / "papers",
        provenance_dir=None,
        themes_dir=None,
        manifest={},
        strict=False,
        verbose=False,
    )


def _record_text(*, base: str, head: str, branch: str = f"auto/{SLUG}", extra: str = "") -> str:
    return (
        "---\n"
        f"id: {RUN_ID}\n"
        "agent: curation-sweep\n"
        "model: test-model\n"
        "tier: belief-neutral\n"
        f"branch: {branch}\n"
        f"base_commit: {base}\n"
        f"head_commit: {head}\n"
        f"toolkit_revision: {'c' * 40}\n"
        "policy_identity:\n  id: core-default\n  version: '1'\n"
        f"basis_digest: {'d' * 64}\n"
        "started: '2026-07-25T09:00:00+00:00'\n"
        "ended: '2026-07-25T09:30:00+00:00'\n"
        "budget:\n  tokens: 100\n  wall_clock_seconds: 1800.0\n"
        "disposition: clean\n"
        f"{extra}"
        "---\n"
    )


def _write_record(root: Path, text: str, *, stem: str = SLUG) -> None:
    runs = root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / f"{stem}.md").write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "f.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def _commit_with_trailer(root: Path, run_id: str) -> str:
    (root / "f.txt").write_text(f"{run_id}\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", f"docs: work\n\nScience-Run: {run_id}")
    return _git(root, "rev-parse", "HEAD")


def test_a_project_with_no_runs_directory_yields_nothing(repo: Path):
    assert list(check_autonomous_runs(_ctx(repo))) == []


def test_a_non_git_project_yields_nothing(tmp_path: Path):
    (tmp_path / "runs").mkdir()
    assert list(check_autonomous_runs(_ctx(tmp_path))) == []


def test_a_consistent_record_yields_nothing(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit_with_trailer(repo, RUN_ID)
    _write_record(repo, _record_text(base=base, head=head))

    assert list(check_autonomous_runs(_ctx(repo))) == []


def test_an_unattested_autonomous_commit_is_an_error(repo: Path):
    """A commit claiming a run that has no record: exactly the coverage gap §6 names."""
    _commit_with_trailer(repo, "run:2026-01-01-ghost-0000")

    results = list(check_autonomous_runs(_ctx(repo)))
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "run:2026-01-01-ghost-0000" in results[0].message
    assert "no run record" in results[0].message


def test_an_unreachable_base_commit_is_an_error(repo: Path):
    head = _commit_with_trailer(repo, RUN_ID)
    _write_record(repo, _record_text(base="0" * 40, head=head))

    results = list(check_autonomous_runs(_ctx(repo)))
    assert any(r.severity is Severity.ERROR and "base_commit" in r.message for r in results)


def test_an_unreachable_head_commit_is_an_error(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _commit_with_trailer(repo, RUN_ID)
    _write_record(repo, _record_text(base=base, head="0" * 40))

    results = list(check_autonomous_runs(_ctx(repo)))
    assert any(r.severity is Severity.ERROR and "head_commit" in r.message for r in results)


def test_an_internally_inconsistent_record_is_an_error(repo: Path):
    """unwired + a digest fails model validation inside load_run_records, so this row is
    reached by converting RunRecordError -- there is no separate branch to write."""
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit_with_trailer(repo, RUN_ID)
    _write_record(
        repo, _record_text(base=base, head=head).replace("disposition: clean", "disposition: unwired")
    )

    results = list(check_autonomous_runs(_ctx(repo)))
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "basis_digest" in results[0].message


def test_a_malformed_record_does_not_crash_validate(repo: Path):
    _write_record(repo, "not frontmatter at all\n")

    results = list(check_autonomous_runs(_ctx(repo)))
    assert [r.severity for r in results] == [Severity.ERROR]


def test_a_nonconforming_branch_is_a_warning(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit_with_trailer(repo, RUN_ID)
    _write_record(repo, _record_text(base=base, head=head, branch="feature/hand-made"))

    results = list(check_autonomous_runs(_ctx(repo)))
    assert [r.severity for r in results] == [Severity.WARN]
    assert "auto/" in results[0].message


def test_the_check_module_is_registered():
    """Writing the module does not enable it: `validate` runs only what
    CANONICAL_CHECK_MODULES names."""
    from science_tool.validate.checks import CANONICAL_CHECK_MODULES

    assert "autonomous_runs" in CANONICAL_CHECK_MODULES
```

- [ ] **Step 2: Run to verify failure**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_validate_check.py -q
```

Expected: `ModuleNotFoundError: No module named 'science_tool.validate.checks.autonomous_runs'`.

- [ ] **Step 3: Implement the check**

Create `science/src/science_tool/validate/checks/autonomous_runs.py`:

```python
"""Design §6: expose run-record integrity as a `validate` check, so violations are
catchable by anyone, independent of the run harness.

INTEGRITY AND COVERAGE, NOT RECOMPUTATION. This check never builds a graph and never
checks a commit out. `validate` runs constantly, and a check whose cost grows with run
history would make it unusable at the weekly cadence the design targets. The full
before/after comparison lives in `science autonomy finish`, where the pinned
installation and the baseline both are.

`prereg_vehicles.py` establishes the precedent for shelling out to git from a check.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

from science_tool.graph.autonomous_runs import RUNS_DIRNAME, load_run_records
from science_model.autonomous_runs import RunRecordError
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

RULE = "autonomous-runs"
TRAILER_KEY = "Science-Run"
_SEP = "\x1e"


def _result(severity: Severity, relative: str | None, message: str) -> Result:
    return Result(severity, Path(relative) if relative is not None else None, None, message, RULE, None)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # --no-replace-objects, as everywhere in the autonomy surface: replacement refs are
    # actor-writable and would let a tampered repository hide its own history.
    return subprocess.run(
        ["git", "--no-replace-objects", "-C", str(root), *args],
        capture_output=True, text=True,
    )


def _commit_exists(root: Path, sha: str) -> bool:
    return _git(root, "rev-parse", "--verify", f"{sha}^{{commit}}").returncode == 0


def _marked_commits(root: Path) -> list[tuple[str, str]]:
    """(commit, trailer value) for every commit carrying a Science-Run trailer.

    `--grep` pushes the filter into git, so the cost is bounded by the number of
    autonomous commits rather than by history length.
    """
    completed = _git(
        root, "log", "-E", f"--grep=^{TRAILER_KEY}:",
        f"--format=%H{_SEP}%(trailers:key={TRAILER_KEY},valueonly){_SEP}",
    )
    if completed.returncode != 0:
        return []
    marked: list[tuple[str, str]] = []
    for entry in completed.stdout.split(f"{_SEP}\n"):
        if not entry.strip():
            continue
        commit, trailers = entry.split(_SEP, 1)
        for line in trailers.splitlines():
            value = line.strip()
            if value:
                marked.append((commit, value))
    return marked


@Check(section="autonomous runs...", order=0)
def check_autonomous_runs(ctx: ValidateContext) -> Iterator[Result]:
    """Run-record integrity and coverage. Silent in projects that never run unattended."""
    root = ctx.project_root
    runs_dir = root / RUNS_DIRNAME
    is_repo = (root / ".git").exists()
    if not is_repo:
        return
    if not runs_dir.exists() and not _marked_commits(root):
        # No records and no autonomous commits: this project does not run unattended.
        return

    try:
        records = load_run_records(root)
    except RunRecordError as exc:
        # Covers the internally-inconsistent record too: unwired-with-a-digest fails
        # model validation inside the loader. One bad record blinds the whole check, so
        # report and stop rather than proceeding on a partial view.
        yield _result(Severity.ERROR, RUNS_DIRNAME, f"run records could not be read: {exc}")
        return

    by_id = {record.id: record for record in records}

    for commit, run_id in _marked_commits(root):
        if run_id not in by_id:
            yield _result(
                Severity.ERROR,
                None,
                f"commit {commit[:12]} carries {TRAILER_KEY}: {run_id} but there is no run record "
                f"for it -- unwired: autonomous commits with no attestation",
            )

    for record in records:
        relative = f"{RUNS_DIRNAME}/{record.slug}.md"
        for field_name, sha in (("base_commit", record.base_commit), ("head_commit", record.head_commit)):
            if not _commit_exists(root, sha):
                yield _result(
                    Severity.ERROR,
                    relative,
                    f"{record.id}: {field_name} {sha[:12]} is unreachable -- the recorded "
                    "transition cannot be validated",
                )
        expected_branch = f"auto/{record.slug}"
        if record.branch != expected_branch:
            yield _result(
                Severity.WARN,
                relative,
                f"{record.id}: branch {record.branch!r} does not follow the {expected_branch!r} convention",
            )
```

- [ ] **Step 4: Register the module**

In `science/src/science_tool/validate/checks/__init__.py`, add `"autonomous_runs"` to
`CANONICAL_CHECK_MODULES`. Place it after `"graph"`, which is where the other
graph-adjacent checks sit.

- [ ] **Step 5: Run the tests**

```bash
cd science && uv run --frozen pytest tests/test_autonomy_validate_check.py tests/test_check_registry_is_complete.py -q
```

Expected: all pass. `test_EVERY_check_module_on_disk_is_REGISTERED` is the one that
fails if Step 4 was skipped.

- [ ] **Step 6: Lint and type-check**

```bash
cd science && uv run ruff check src/science_tool/validate tests/test_autonomy_validate_check.py && uv run pyright
```

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/validate science/tests/test_autonomy_validate_check.py
git commit -m "feat(validate): check autonomous run record integrity and coverage"
```

---

### Task 8: Documentation

**Files:**
- Modify: `docs/user-guide/agent-workflows.md`
- Modify: `docs/plans/2026-07-24-autonomy-envelope-design.md`

- [ ] **Step 1: Add the lifecycle to the user guide**

`docs/user-guide/agent-workflows.md` already ends with the `## The autonomy path gate`
section from Plan C (it starts at line 42 and ends with the paragraph about
`science graph belief-basis`). **Append** the following after it — do not modify the
existing section. The outer fence here is four backticks because the content contains a
three-backtick block; write the inner block as a normal fence.

````markdown
## Running an unattended run

An unattended run is bracketed by two supervisor commands. Nothing between them is part
of Science: the actor is driven by whatever harness you use.

```bash
science autonomy start --agent curation-sweep --model <model> \
    --short-id a3f1 --baseline-out ~/supervisor-state/a3f1.json

#  ... the actor works on auto/<run-id> ...

science autonomy finish --baseline ~/supervisor-state/a3f1.json \
    --head "$(git rev-parse HEAD)" --tokens 12000 --wall-clock-seconds 900
```

`start` captures the belief basis and writes a **baseline**. It writes no run record: a
supervisor that dies mid-run leaves no attestation, so its branch reads as unattested
rather than clean. The baseline must live **outside the repository** — both commands
refuse a path inside the project root, because the actor's whole job is writing that
tree, and a baseline it can reach is a baseline it can rewrite.

`finish` re-materializes the graph, recaptures the basis, compares it against the
baseline, runs the path gate over the recorded range, verifies the commit marks, and
writes the attested record to `runs/<run-id>.md`. The re-materialization is not
optional: `graph.trig` is derived state the actor controls, so a run that edited
entities and never rebuilt would otherwise be judged against a stale graph.

Three dispositions, and the exit codes match:

| Disposition | Exit | Meaning |
|---|---|---|
| `clean` | 0 | Eligible to merge. |
| `quarantined` | 1 | The branch is held intact and a `science feedback` item is filed naming the entity and the delta. |
| `unwired` | 2 | The basis was not computable. Blocked — a guard that cannot see must not report clean. |

**Nothing is discarded on quarantine.** The branch and its commits stay exactly as the
run left them, so a human triages with the entity and the delta in hand. The first
violations will mostly be design discoveries — a sweep that legitimately needs something
the gate forbids — and destroying the evidence destroys the signal.

`science validate` carries an `autonomous-runs` check so the same violations are
catchable by anyone, independent of the run harness. It verifies record integrity and
coverage — every autonomous commit has a record, every record's commits are reachable —
without rebuilding the graph, so its cost does not grow with run history.
````

- [ ] **Step 2: Record the Plan D rulings in the design doc**

In `docs/plans/2026-07-24-autonomy-envelope-design.md`, append this blockquote to the end
of §6, immediately after the paragraph beginning "Escalation reuses the existing
`science feedback` surface" and before the `## Testing` heading:

```markdown
> **Revised during implementation (Plan D).** Five rulings the design did not settle:
>
> 1. **The record is written only at `finish`.** `AutonomousRunRecord` has no in-flight
>    shape, so `start` writes no record at all. A supervisor that dies mid-run leaves an
>    unattested branch, which is the intended failure direction.
> 2. **The baseline lives outside the repository.** `runs/` accepts only flat `*.md`
>    records, so the before-capture cannot go there — and it must not go anywhere in the
>    worktree, because the actor writes that tree. Both commands refuse a baseline path
>    inside the project root.
> 3. **`finish` re-materializes before capturing.** `graph.trig` is derived and
>    actor-controlled; without this, a run that edited entities and never rebuilt would
>    be judged against a stale graph and pass. This closes the gap Plan A recorded.
> 4. **Gate externality is enforced two ways** — the running toolkit revision must match
>    the one the baseline recorded, and the executing `science_tool` must not resolve
>    inside the project root. Either check alone leaves the other open.
> 5. **The `validate` check verifies integrity and coverage, not the comparison.** It
>    confirms that every autonomous commit has a record and that every record's commits
>    are reachable, without rebuilding the graph. Re-deriving each historical run's basis
>    would make `validate` runtime grow without bound at the cadence this design targets.
>    The authoritative comparison stays in `finish`, where the pinned installation and the
>    baseline both live.
```

- [ ] **Step 3: Update the status line and state what S1 did NOT close**

Replace the `> **Status:**` blockquote at the top of the design doc with:

```markdown
> **Status:** implemented. Slice S1 of the autonomous-research program, shipped as four
> plans — A (belief-basis guard), B (run record), C (path gate + perturbation alarm), and
> D (supervisor lifecycle, quarantine, `validate` wiring). S1 ships **no autonomous
> agent**: it is the contract, verified by tests, that the first one will run inside.
> Downstream slices (S2 recurrence, S3 task eligibility, S4 telemetry→estimates, S5
> harness, S6 multi-agent design→plan, S7 context management) all consume this contract
> and are out of scope here.
>
> **One gap S1 did not close.** `autonomous_run` on an entity is still not an attested
> per-entity binding. `finish` verifies that the run's *commits* carry the run's own
> trailer over the recorded range, but it does not check that each entity's
> `autonomous_run` value names the run that actually wrote that file — so an actor can
> still attribute its work to an unrelated prior run. The commit range remains the only
> authoritative binding (§0). Closing this means having the supervisor stamp
> `autonomous_run` itself, or verifying every value it finds against the recorded
> `base_commit..head_commit` range; it is deferred, not solved.
```

Then update Plan B's existing "Not yet an attested binding" note in §3 to point at this
status line rather than at "Plan D", since Plan D did not close it.

- [ ] **Step 4: Verify the docs guards and commit**

```bash
cd science && uv run --frozen pytest tests/test_user_guide_docs.py tests/test_command_docs.py -q
```

```bash
git add docs/user-guide/agent-workflows.md docs/plans/2026-07-24-autonomy-envelope-design.md
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
