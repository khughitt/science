from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from science_model.autonomous_runs import RunDisposition, RunTier

from science_tool.autonomy import lifecycle as lifecycle_module
from science_tool.autonomy import toolkit as toolkit_module
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


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_science_project(root: Path) -> None:
    """A project with a real, non-empty belief basis.

    The shape is copied from `test_autonomy_perturbation_alarm.py`'s `_seed_project`,
    which is known to yield actual evidence units: a proposition, a belief-eligible
    evidence line bearing on it, and the paper the line is sourced from. `pmid` is quoted
    because unquoted digits parse as an int and pydantic rejects an int for a `str` field.
    """
    _write(root, "science.yaml", "name: lifecycle-fixture\nknowledge_profiles:\n  local: local\n")
    _write(root, "entities/propositions/p1.md", "---\nid: proposition:p1\nkind: proposition\ntitle: P1\n---\n\nClaim.\n")
    _write(
        root,
        "entities/papers/x.md",
        "---\n"
        "id: paper:x\n"
        "kind: paper\n"
        "title: X\n"
        "venue: Nature\n"
        'pmid: "111"\n'
        "year: 2020\n"
        "url: https://example.org/x\n"
        "---\n\nBody.\n",
    )
    _write(
        root,
        "entities/evidence-lines/e1.md",
        "---\n"
        "id: evidence-line:e1\n"
        "kind: evidence-line\n"
        "title: Evidence line\n"
        "stance: supports\n"
        "target: proposition:p1\n"
        "source: paper:x\n"
        "strength: strong\n"
        "belief_eligible: true\n"
        "---\n",
    )


@pytest.fixture(autouse=True)
def pinned_toolkit(monkeypatch: pytest.MonkeyPatch) -> None:
    """`assert_toolkit_matches` refuses a dirty judging toolkit (Task 2). The checkout
    these tests run in is dirty exactly while this plan is being implemented, and that is
    not what any test in this module is about. One test below drives the other answer."""
    monkeypatch.setattr(toolkit_module, "toolkit_is_clean", lambda root=None: True)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A git project with a real, non-empty belief basis, committed INCLUDING its graph.

    Building and committing `knowledge/graph.trig` here is load-bearing, not tidiness.
    `start_run` materializes, so a fixture that never built the graph leaves it untracked
    the moment `start` returns -- and every dirty-tree test below would then pass because
    of the supervisor's own write instead of the condition it names. With the graph
    already committed, the deterministic rebuild leaves the tree clean.
    """
    from science_tool.graph.materialize import materialize_graph

    root = tmp_path / "project"
    root.mkdir()
    _seed_science_project(root)
    materialize_graph(root)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    assert not _git(root, "status", "--porcelain"), "the fixture must start clean"
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


def test_the_fixture_has_a_non_empty_basis(project: Path):
    """Certification: a basis of zero units makes every assertion in this module vacuous
    -- each one would then pass by finding nothing rather than by finding the right
    thing."""
    from science_tool.graph.belief_basis import capture_basis
    from science_tool.graph.materialize import materialize_graph
    from science_tool.graph.store.identity import graph_uri
    from science_tool.graph.trig import load_trig_dataset_preserving_literals

    dataset = load_trig_dataset_preserving_literals(materialize_graph(project))
    result = capture_basis(
        dataset.graph(graph_uri("graph/knowledge")),
        dataset.graph(graph_uri("graph/provenance")),
    )
    assert result.status != "unwired", result.reason
    assert result.rows
    assert any(row.unit_keys for row in result.rows), "fixture yields no evidence units"


def test_start_writes_no_run_record(project: Path, baseline_path: Path):
    """A supervisor that dies mid-run must leave no attestation."""
    _start(project, baseline_path)
    assert not (project / "runs").exists()
    assert baseline_path.exists()
    assert not _git(project, "status", "--porcelain"), (
        "materialize_graph is not byte-deterministic across two calls; every dirty-tree "
        "test in this module would then pass for the wrong reason"
    )


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
    """The authoritative layer: this must fire even though the path gate would too.

    Weakening `strength` moves the basis -- one `('units',)` delta on `proposition:p1`. It
    does NOT move the aggregated ordinal magnitude, which stays `fragile`; this test
    simply never measures that.
    `test_a_basis_move_that_leaves_the_magnitude_UNCHANGED_still_quarantines` is where the
    magnitude is measured and pinned.
    """
    baseline = _start(project, baseline_path)
    line = project / "entities" / "evidence-lines" / "e1.md"
    line.write_text(line.read_text(encoding="utf-8").replace("strength: strong", "strength: weak"), encoding="utf-8")
    _commit_as_agent(project, "chore: weaken evidence", baseline.run_id)

    outcome = _finish(project, baseline_path)
    assert outcome.disposition is RunDisposition.QUARANTINED
    assert outcome.deltas


def _magnitudes(project: Path) -> dict[str, str]:
    """Every entity's aggregated ordinal magnitude, freshly materialized.

    Design test 1 is about the basis moving while THIS does not, so the test has to be
    able to compute it. `aggregate_belief` is the scalar-free ordinal path, reached
    through the same target expansion `capture_basis` uses -- a second recipe here would
    make the comparison meaningless.
    """
    from rdflib import URIRef

    from science_tool.graph.belief import aggregate_belief, collect_evidence_units
    from science_tool.graph.belief_basis import capture_basis
    from science_tool.graph.materialize import materialize_graph
    from science_tool.graph.store.identity import graph_uri
    from science_tool.graph.trig import load_trig_dataset_preserving_literals

    # The graph names are "graph/knowledge" and "graph/provenance" -- copied from
    # `graph/cli.py:1296`, which is the one place this pattern already works.
    dataset = load_trig_dataset_preserving_literals(materialize_graph(project))
    knowledge = dataset.graph(graph_uri("graph/knowledge"))
    provenance = dataset.graph(graph_uri("graph/provenance"))
    result = capture_basis(knowledge, provenance)
    assert result.rows, "a magnitude comparison over an empty basis proves nothing"
    return {
        row.entity_id: aggregate_belief(
            list(collect_evidence_units(knowledge, provenance, {URIRef(u) for u in row.target_uris}))
        ).magnitude.value
        for row in result.rows
    }


def test_a_basis_move_that_leaves_the_magnitude_UNCHANGED_still_quarantines(
    project: Path, baseline_path: Path
):
    """Design test 1, and the reason the basis is the observable rather than the verdict.

    Renaming the evidence line changes `EvidenceUnit.line_uri` -- the unit's identity, and
    the first key `unit_key` serializes -- while leaving every belief-WEIGHTED attribute
    (stance, strength, source, role) identical. The aggregated ordinal magnitude of the
    surviving `proposition:p1` is therefore unchanged: `fragile` before and after. A guard
    watching the verdict sees nothing here; a guard watching the inputs must not.

    The mutation is broader than that one unit, and the assertions have to account for it.
    The rename also DROPS 8 entities from the basis -- the evidence line itself plus 7
    derived `bears-on-edge:*` entities -- so 8 of the 9 deltas are `('removed',)` and only
    ONE is the `('units',)` delta this test exists to pin. A bare `assert outcome.deltas`
    would pass on the removals alone, so the `units` delta is asserted by name.

    The magnitude equality is MEASURED and asserted, not assumed -- and that, not any
    contrast with `test_a_belief_basis_move_quarantines`, is what makes this test
    load-bearing. In this fixture that sibling's `strength: strong -> weak` also leaves
    `proposition:p1` at `fragile`, so it happens to be magnitude-preserving too; it just
    never checks.
    """
    before = _magnitudes(project)
    baseline = _start(project, baseline_path)

    lines = project / "entities" / "evidence-lines"
    renamed = lines / "e1-renamed.md"
    original = (lines / "e1.md").read_text(encoding="utf-8")
    renamed.write_text(original.replace("id: evidence-line:e1", "id: evidence-line:e1-renamed"), encoding="utf-8")
    (lines / "e1.md").unlink()
    _commit_as_agent(project, "chore: rename the evidence line", baseline.run_id)

    outcome = _finish(project, baseline_path)

    # Over the entities that SURVIVE the rename: the evidence line's own id changed by
    # construction, and comparing a key that no longer exists proves nothing either way.
    #
    # Measured AFTER `_finish`, not before it: `_magnitudes` re-materializes, and
    # `knowledge/graph.trig` is tracked, so taking the after-reading first would leave the
    # tree dirty and land the run on `unwired` by the test's own hand. `finish_run`
    # re-materializes from the same committed sources, so the reading is unchanged.
    after = _magnitudes(project)
    shared = before.keys() & after.keys()
    assert shared, "the rename removed every entity; there is nothing left to compare"
    assert {k: after[k] for k in shared} == {k: before[k] for k in shared}, (
        "the mutation must NOT move the ordinal verdict -- if it does, this test no longer "
        "shows the basis moving where the verdict does not, and design test 1 is undischarged"
    )

    assert outcome.disposition is RunDisposition.QUARANTINED, outcome.reason
    # The SPECIFIC delta, not the truthiness of the list: 8 of the 9 deltas here are
    # `('removed',)` rows from entities the rename dropped, so a bare `assert
    # outcome.deltas` would still hold if unit-key sensitivity regressed away entirely --
    # which is the one thing this test exists to pin.
    assert any(
        delta.entity_id == "proposition:p1" and "units" in delta.changed
        for delta in outcome.deltas
    ), outcome.deltas


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


def test_an_unwired_record_carries_no_digest(project: Path, baseline_path: Path):
    """The other unwired case: identity IS known, so an attestation saying 'we could not
    tell' is written -- with no basis_digest, which the model enforces.

    Driven through a toolkit-revision mismatch because that is the cheapest condition
    that reaches the unwired branch with the baseline already loaded."""
    import json

    _start(project, baseline_path)
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    payload["toolkit_revision"] = "0" * 40
    baseline_path.write_text(json.dumps(payload), encoding="utf-8")

    outcome = _finish(project, baseline_path)
    assert outcome.disposition is RunDisposition.UNWIRED
    assert outcome.record is not None
    assert outcome.record.basis_digest is None


def test_a_dirty_judging_toolkit_is_unwired(project: Path, baseline_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Overrides the autouse pin: a supervisor judging from an unpinned checkout attests
    a revision that does not describe the code that ran."""
    _start(project, baseline_path)
    monkeypatch.setattr(toolkit_module, "toolkit_is_clean", lambda root=None: False)

    outcome = _finish(project, baseline_path)
    assert outcome.disposition is RunDisposition.UNWIRED
    # Names step 2, not merely "uncommitted": the step-3 repository-state message says
    # that word too, so the looser assertion would pass on the wrong refusal.
    assert "the judging toolkit" in outcome.reason


def test_an_uncommitted_denied_edit_is_unwired_not_clean(project: Path, baseline_path: Path):
    """THE fail-open this binding closes. `methods_summary` is denied by the path gate but
    does not move the belief basis, so an UNCOMMITTED rewrite is invisible to both layers:
    the gate reads base..head and never sees it, the basis does not move. Without the
    repository-state check this run finishes `clean` with a denied edit in the worktree."""
    _start(project, baseline_path)
    paper = project / "entities" / "papers" / "x.md"
    paper.write_text(
        paper.read_text(encoding="utf-8").replace("venue: Nature", "venue: Nature\nmethods_summary: rewritten"),
        encoding="utf-8",
    )
    # deliberately NOT committed

    outcome = _finish(project, baseline_path)
    assert outcome.disposition is RunDisposition.UNWIRED, outcome.reason
    # Names step 3, not merely "uncommitted": the step-2 toolkit message says that word
    # too, and this test is about the tree being judged, not the toolkit judging it.
    assert "the working tree is not commit" in outcome.reason


def test_an_untracked_file_is_unwired_not_clean(project: Path, baseline_path: Path):
    """An untracked entity file is equally invisible to `base..head` and equally real."""
    _start(project, baseline_path)
    (project / "entities" / "papers" / "planted.md").write_text("---\nkind: paper\n---\n", encoding="utf-8")

    outcome = _finish(project, baseline_path)
    assert outcome.disposition is RunDisposition.UNWIRED, outcome.reason


def test_a_head_that_is_not_the_repositorys_head_is_unwired(project: Path, baseline_path: Path):
    """`head` is caller-supplied. Gating one range while capturing another state is not a
    comparison, so it is refused rather than reported."""
    baseline = _start(project, baseline_path)
    _edit = project / "entities" / "papers" / "x.md"
    _edit.write_text(_edit.read_text(encoding="utf-8").replace("venue: Nature", "venue: Science"), encoding="utf-8")
    _commit_as_agent(project, "docs: refresh venue", baseline.run_id)

    outcome = finish_run(
        project, baseline_path=baseline_path, head=baseline.base_commit,  # stale
        ended=datetime(2026, 7, 25, 9, 30, tzinfo=UTC), tokens=100, wall_clock_seconds=1800.0,
    )
    assert outcome.disposition is RunDisposition.UNWIRED, outcome.reason
    assert "HEAD" in outcome.reason


def test_start_refuses_a_dirty_tree(project: Path, baseline_path: Path):
    """Otherwise the baseline digest is attested as the basis 'at base_commit' while it
    was taken from a tree that is not that commit."""
    paper = project / "entities" / "papers" / "x.md"
    paper.write_text(paper.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(lifecycle_module.RepositoryStateError):
        _start(project, baseline_path)
    assert not baseline_path.exists()


def test_a_failed_materialization_is_unwired_with_a_record(project: Path, baseline_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Identity is known, so the attestation is written; the verdict is not."""
    _start(project, baseline_path)

    def _boom(root, **kwargs):
        raise RuntimeError("materialization exploded")

    monkeypatch.setattr(lifecycle_module, "materialize_graph", _boom)

    outcome = _finish(project, baseline_path)
    assert outcome.disposition is RunDisposition.UNWIRED
    assert outcome.record is not None and outcome.record.basis_digest is None
    assert "materialization exploded" in outcome.reason


def test_an_unwired_capture_is_unwired(project: Path, baseline_path: Path, monkeypatch: pytest.MonkeyPatch):
    """`capture_basis` returns InstrumentResult.unwired when the graph carries no typed
    project entity. A guard that cannot see must not report clean."""
    from science_tool.instruments import InstrumentResult

    _start(project, baseline_path)
    monkeypatch.setattr(
        lifecycle_module, "capture_basis",
        lambda *a, **k: InstrumentResult.unwired(code="no_typed_entities", reason="nothing typed"),
    )

    outcome = _finish(project, baseline_path)
    assert outcome.disposition is RunDisposition.UNWIRED
    assert "nothing typed" in outcome.reason


def test_a_gate_extraction_failure_is_unwired(project: Path, baseline_path: Path, monkeypatch: pytest.MonkeyPatch):
    """An ExtractError means the change set could not be read at all -- Plan C's own
    fail-closed direction, carried through to a disposition here."""
    from science_tool.autonomy.extract import ExtractError

    baseline = _start(project, baseline_path)
    # The edit is what makes the commit possible at all: `start_run`'s rebuild is
    # byte-identical, so the tree is clean and an empty `git commit` would fail.
    paper = project / "entities" / "papers" / "x.md"
    paper.write_text(paper.read_text(encoding="utf-8").replace("venue: Nature", "venue: Science"), encoding="utf-8")
    _commit_as_agent(project, "docs: work", baseline.run_id)

    def _boom(*a, **k):
        raise ExtractError("could not read the change set")

    monkeypatch.setattr(lifecycle_module, "extract_change_set", _boom)

    outcome = _finish(project, baseline_path)
    assert outcome.disposition is RunDisposition.UNWIRED
    assert "could not read the change set" in outcome.reason


def test_a_project_root_that_is_not_a_repository_is_unwired_not_a_traceback(
    project: Path, baseline_path: Path, tmp_path: Path
):
    """Global Constraint 3: every condition that prevents a verdict yields `unwired`.

    `assert_repository_is_at` asks git through `extract._git`, which fails CLOSED on any
    non-zero exit -- so a `project_root` git cannot read raises `ExtractError`, not
    `RepositoryStateError`. Catching only the latter would let it escape `finish_run`
    entirely, contradicting its own "never raises for an expected condition".

    The baseline is opened against the real project so the run's IDENTITY is known; only
    the tree being judged is unreadable. That is the identity-known unwired shape, so an
    attestation IS written -- with no `basis_digest`.
    """
    baseline = _start(project, baseline_path)
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()

    outcome = finish_run(
        not_a_repo, baseline_path=baseline_path, head=baseline.base_commit,
        ended=datetime(2026, 7, 25, 9, 30, tzinfo=UTC), tokens=100, wall_clock_seconds=1800.0,
    )
    assert outcome.disposition is RunDisposition.UNWIRED, outcome.reason
    assert outcome.record is not None and outcome.record.basis_digest is None
    assert "rev-parse" in outcome.reason


def test_an_unreadable_range_in_verify_marks_is_unwired(project: Path, baseline_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The second escape route. `verify_marks` reads `base..head` through the same
    fail-closed `_git`, and a range whose marks cannot be read is not a range whose marks
    are fine."""
    from science_tool.autonomy.extract import ExtractError

    baseline = _start(project, baseline_path)
    paper = project / "entities" / "papers" / "x.md"
    paper.write_text(paper.read_text(encoding="utf-8").replace("venue: Nature", "venue: Science"), encoding="utf-8")
    _commit_as_agent(project, "docs: refresh venue", baseline.run_id)

    def _boom(*a, **k):
        raise ExtractError("could not read the commit range")

    monkeypatch.setattr(lifecycle_module, "verify_marks", _boom)

    outcome = _finish(project, baseline_path)
    assert outcome.disposition is RunDisposition.UNWIRED, outcome.reason
    assert outcome.record is not None and outcome.record.basis_digest is None
    assert "could not read the commit range" in outcome.reason


def test_start_against_a_non_repository_raises_ExtractError(tmp_path: Path, baseline_path: Path):
    """`start_run` RAISES rather than dispositioning, deliberately: there is no run yet to
    attest to, so there is nothing to be `unwired` about. This pins WHICH exception, so
    the command layer knows exactly what its error boundary must catch."""
    from science_tool.autonomy.extract import ExtractError

    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()

    with pytest.raises(ExtractError):
        _start(not_a_repo, baseline_path)
    assert not baseline_path.exists()


def test_a_record_that_cannot_be_written_never_reports_clean(project: Path, baseline_path: Path):
    """`write_run_record` refuses to overwrite. A second `finish` on an already-attested
    run must surface that, not silently re-report the verdict it cannot record."""
    baseline = _start(project, baseline_path)
    _edit = project / "entities" / "papers" / "x.md"
    _edit.write_text(_edit.read_text(encoding="utf-8").replace("venue: Nature", "venue: Science"), encoding="utf-8")
    _commit_as_agent(project, "docs: refresh venue", baseline.run_id)

    assert _finish(project, baseline_path).disposition is RunDisposition.CLEAN

    # `finish` re-materialized, so `knowledge/graph.trig` is now modified in the tree.
    # Commit it as the agent, or the second attempt stops at the repository-state check
    # and never reaches the writer this test is about. `--allow-empty` because a
    # deterministic rebuild may have produced byte-identical output.
    _git(project, "add", "-A")
    _git(
        project, "commit", "-q", "--allow-empty",
        "-m", f"chore: rebuilt graph\n\nScience-Run: {baseline.run_id}",
        "--author", f"{AGENT} <agent@science.local>",
    )

    outcome = _finish(project, baseline_path)
    assert outcome.disposition is RunDisposition.UNWIRED
    assert "written once" in outcome.reason


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


# --- the control plane must not be reachable from inside the worktree -----------------
#
# `assert_repository_is_at` runs `git status --porcelain` INSIDE the actor's repository,
# and several `.git/config` keys name a program git then runs with the supervisor's
# privileges. `.git/config` is actor-writable, untracked, absent from `base..head` and
# invisible to `git status`, so neither the path gate nor the basis capture can see the
# plant. Each test below first proves the vector is live in this environment with an
# UNHARDENED git, then re-arms it and drives the real code path.


def _sentinel_program(directory: Path, sentinel: Path, *, pipe: bool = False) -> Path:
    """A stand-in for the actor's payload: it records that it ran."""
    program = directory / f"planted-{sentinel.name}.sh"
    body = 'cat\n' if pipe else ''
    program.write_text(f'#!/bin/sh\ntouch "{sentinel}"\n{body}exit 0\n', encoding="utf-8")
    program.chmod(0o755)
    return program


def _rearm(project: Path) -> None:
    """Force git to refresh the index on the next command.

    Changing only the mtime leaves the tree clean but makes git re-stat -- and, where a
    filter driver applies, re-hash the file through it. It is also what makes the
    `post-index-change` hook fire again.
    """
    import os

    os.utime(project / "entities" / "papers" / "x.md", (1, 1))


def _unhardened_status(project: Path) -> None:
    subprocess.run(["git", "-C", str(project), "status", "--porcelain"], capture_output=True)


def _assert_vector_is_live(project: Path, sentinel: Path) -> None:
    """Certification: a plant that never fires would make the assertion below vacuous."""
    _rearm(project)
    _unhardened_status(project)
    assert sentinel.exists(), "the plant never ran, so this test proves nothing"
    sentinel.unlink()
    _rearm(project)


def test_a_repo_local_fsmonitor_program_does_not_run(project: Path, tmp_path: Path):
    """core.fsmonitor is the vector the reviewer drove end to end: a planted program ran
    with the supervisor's privileges and the run still returned `clean`."""
    from science_tool.autonomy.lifecycle import assert_repository_is_at

    sentinel = tmp_path / "fsmonitor-fired"
    program = _sentinel_program(tmp_path, sentinel)
    _git(project, "config", "core.fsmonitor", str(program))
    _assert_vector_is_live(project, sentinel)

    assert_repository_is_at(project)
    assert not sentinel.exists(), "the actor's fsmonitor program ran inside the control plane"


def test_a_repo_local_hook_does_not_run(project: Path, tmp_path: Path):
    """`post-index-change` fires on `git status`. `.git/hooks/` is actor-writable and no
    `-c` key can blank it, so the defense has to move hooks somewhere else entirely."""
    from science_tool.autonomy.lifecycle import assert_repository_is_at

    sentinel = tmp_path / "hook-fired"
    program = _sentinel_program(tmp_path, sentinel)
    (project / ".git" / "hooks" / "post-index-change").write_text(
        f'#!/bin/sh\nexec "{program}"\n', encoding="utf-8"
    )
    (project / ".git" / "hooks" / "post-index-change").chmod(0o755)
    _assert_vector_is_live(project, sentinel)

    assert_repository_is_at(project)
    assert not sentinel.exists(), "the actor's git hook ran inside the control plane"


def test_a_repo_local_filter_driver_does_not_run(project: Path, tmp_path: Path):
    """The vector no fixed `-c` key reaches: the driver NAME is the actor's to choose.

    A same-size touch is enough to force the re-hash that runs the driver, so the actor
    gets execution while the tree still reads clean.
    """
    from science_tool.autonomy.lifecycle import assert_repository_is_at

    sentinel = tmp_path / "filter-fired"
    program = _sentinel_program(tmp_path, sentinel, pipe=True)
    (project / ".gitattributes").write_text("* filter=whatever\n", encoding="utf-8")
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "chore: attributes")
    _git(project, "config", "filter.whatever.clean", str(program))
    _assert_vector_is_live(project, sentinel)

    assert_repository_is_at(project)
    assert not sentinel.exists(), "the actor's clean filter ran inside the control plane"


def test_a_filter_driver_named_so_it_cannot_be_neutralized_is_refused(project: Path):
    """`-c` splits at the first `=`, so a driver named `a=b` would leave the real key
    armed while the override set something else. Refuse instead of pretending."""
    from science_tool.autonomy.extract import ExtractError

    (project / ".git" / "config").write_text(
        (project / ".git" / "config").read_text(encoding="utf-8")
        + '[filter "a=b"]\n\tclean = /bin/false\n',
        encoding="utf-8",
    )
    with pytest.raises(ExtractError, match="cannot be neutralized"):
        lifecycle_module.assert_repository_is_at(project)


def test_a_git_that_cannot_be_invoked_is_unwired_not_quarantined(
    project: Path, baseline_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The one place a blocked run could degrade into a stronger-looking verdict.

    With no `git` on PATH the old `toolkit._git` raised `FileNotFoundError` out of a
    function contracted never to raise for an expected condition; click has no handler,
    so it exited 1 -- the code the shipped docs define as `quarantined`. `unwired` is the
    honest answer, and it is a different exit code for a reason.
    """
    from science_tool.autonomy import git as git_module

    _start(project, baseline_path)

    class _NoGit:
        @staticmethod
        def run(*args, **kwargs):
            raise OSError(2, "No such file or directory: 'git'")

    head = _git(project, "rev-parse", "HEAD")
    monkeypatch.setattr(git_module, "subprocess", _NoGit)

    outcome = finish_run(
        project, baseline_path=baseline_path, head=head,
        ended=datetime(2026, 7, 25, 9, 30, tzinfo=UTC), tokens=100, wall_clock_seconds=1800.0,
    )
    assert outcome.disposition is RunDisposition.UNWIRED, outcome.reason
    assert "could not execute git" in outcome.reason


def test_a_belief_basis_move_quarantines_with_the_path_gate_silent(
    project: Path, baseline_path: Path
):
    """LAYER 2 ON ITS OWN. The basis check is called authoritative precisely because it
    does not depend on the allowlist being correct (`path_gate.py:4-6`), and every other
    basis test in this module is co-satisfied by a path-gate denial -- delete `deltas`
    from the quarantine condition and they all stay green.

    Here the changed file is waived through the gate as the run's own report, so `deltas`
    is the only thing left that can quarantine.
    """
    baseline = _start(project, baseline_path)
    line = project / "entities" / "evidence-lines" / "e1.md"
    line.write_text(
        line.read_text(encoding="utf-8").replace("strength: strong", "strength: weak"),
        encoding="utf-8",
    )
    _commit_as_agent(project, "chore: weaken evidence", baseline.run_id)

    outcome = finish_run(
        project, baseline_path=baseline_path, head=_git(project, "rev-parse", "HEAD"),
        ended=datetime(2026, 7, 25, 9, 30, tzinfo=UTC), tokens=100, wall_clock_seconds=1800.0,
        report_path="entities/evidence-lines/e1.md",
    )
    assert not outcome.denials, "the gate must be silent, or this proves nothing"
    assert not outcome.mark_issues, "the marks must be clean, or this proves nothing"
    assert outcome.deltas
    assert outcome.disposition is RunDisposition.QUARANTINED, outcome.reason
